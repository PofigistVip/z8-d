"""Exercise the Windows LDAP transport against a local LDAP protocol fixture."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading

from runtime_support import import_args, runtime_library, ROOT

if os.name != "nt":
    raise SystemExit("This test requires Windows WinLDAP")


def tlv(tag, value):
    size = len(value)
    length = bytes([size]) if size < 128 else bytes([0x82, size >> 8, size & 255])
    return bytes([tag]) + length + value


def read_tlv(data, offset=0):
    tag, length = data[offset:offset + 2]
    offset += 2
    if length & 0x80:
        count = length & 0x7f
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    return tag, data[offset:offset + length], offset + length


def recv_message(sock):
    def receive(size):
        result = b""
        while len(result) < size:
            part = sock.recv(size - len(result))
            if not part:
                raise EOFError()
            result += part
        return result
    head = receive(2)
    length = head[1]
    if length & 0x80:
        length = int.from_bytes(receive(length & 0x7f), "big")
    return receive(length)


def result(code=0):
    return tlv(0x0a, bytes([code])) + tlv(4, b"") + tlv(4, b"")


def entry(name):
    def attr(key, *values):
        return tlv(0x30, tlv(4, key.encode()) + tlv(0x31, b"".join(tlv(4, value.encode()) for value in values)))
    return tlv(0x64, tlv(4, ("cn=" + name + ",dc=example").encode()) +
               tlv(0x30, attr("uid", name) + attr("memberOf", "cn=one", "cn=two")))


def page_control(cookie):
    value = tlv(0x30, tlv(2, b"\x02") + tlv(4, cookie))
    return tlv(0xa0, tlv(0x30, tlv(4, b"1.2.840.113556.1.4.319") + tlv(4, value)))


class Fixture:
    def __init__(self):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(15)
        self.port = self.listener.getsockname()[1]
        self.events = []
        self.failure = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            connection, _ = self.listener.accept()
            with connection:
                connection.settimeout(15)
                page = 0
                while True:
                    message = recv_message(connection)
                    _, mid, offset = read_tlv(message)
                    tag, operation, offset = read_tlv(message, offset)
                    message_id = tlv(2, mid)
                    if tag == 0x60:
                        _, _, pos = read_tlv(operation)
                        _, principal, pos = read_tlv(operation, pos)
                        _, password, _ = read_tlv(operation, pos)
                        self.events.append(("bind", principal, password))
                        connection.sendall(tlv(0x30, message_id + tlv(0x61, result())))
                    elif tag == 0x63:
                        _, base, pos = read_tlv(operation)
                        _, scope, pos = read_tlv(operation, pos)
                        assert scope == b"\x02"  # subtree
                        for _ in range(4):
                            _, _, pos = read_tlv(operation, pos)
                        filter_tag, filter_value, _ = read_tlv(operation, pos)
                        assert (filter_tag, filter_value) == (0x87, b"objectClass")
                        paged = offset < len(message)
                        request_cookie = None
                        if paged:
                            _, controls, _ = read_tlv(message, offset)
                            _, control, _ = read_tlv(controls)
                            _, oid, pos = read_tlv(control)
                            assert oid == b"1.2.840.113556.1.4.319"
                            tag, critical, pos = read_tlv(control, pos)
                            assert tag == 1 and critical != b"\x00"
                            _, value, _ = read_tlv(control, pos)
                            _, page_request, _ = read_tlv(value)
                            _, size, pos = read_tlv(page_request)
                            _, request_cookie, _ = read_tlv(page_request, pos)
                            assert size == b"\x01"
                        self.events.append(("search", base, request_cookie))
                        if paged:
                            page += 1
                            name, cookie = ("alice", b"next") if page == 1 else ("bob", b"")
                        else:
                            name, cookie = "алиса", b""
                        connection.sendall(tlv(0x30, message_id + entry(name)))
                        controls = page_control(cookie) if paged else b""
                        connection.sendall(tlv(0x30, message_id + tlv(0x65, result()) + controls))
                    elif tag == 0x42:
                        self.events.append(("unbind",))
                        break
                    else:
                        raise AssertionError("Unexpected LDAP operation: " + hex(tag))
        except BaseException as exc:
            self.failure = exc
        finally:
            self.listener.close()


with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "transport.d"
    source.write_text('''import z8.runtime;
import z8.ldap.windows;
import std.conv : to;
void main(string[] args) {
    z8_server_config_replace(["ldap.ssl.trusted"w: "true"w]);
    bool unsupported; try { z8_windows_ldap_configure(); } catch (Exception) { unsupported = true; } assert(unsupported);
    z8_server_config_replace(["ldap.read.pageSize"w: "-1"w]);
    bool invalid; try { z8_windows_ldap_configure(); } catch (Exception) { invalid = true; } assert(invalid);
    z8_server_config_replace(["ldap.read.pageSize"w: "1"w, "ldap.connect.timeout"w: "3000"w]);
    auto previous = z8_windows_ldap_configure(); auto configured = z8_ldap_set_provider(previous);
    if (args.length > 2) {
        auto session = configured.open("ldap://127.0.0.1:"w ~ args[1].to!wstring, "cn=admin"w, "secret"w,
            `{users:{loginField:"uid",groupField:"memberOf"}}`w);
        auto users = session.users("dc=example"w, "(objectClass=*)"w);
        assert(users.length == 2 && users[0].login == "alice"w && users[1].login == "bob"w);
        assert(users[0].memberOf == ["cn=one"w, "cn=two"w]);
        session.close(); return;
    }
    auto transport = new Z8WindowsLdapTransport();
    foreach (url; ["http://host"w, "ldap://"w, "ldap://host:"w, "ldap://host:0"w, "ldap://host:65536"w, "ldap://host/path"w]) {
        bool failed; try { transport.connect(url, ""w, ""w); } catch (Exception) { failed = true; } assert(failed);
    }
    auto directory = transport.connect("ldap://127.0.0.1:"w ~ args[1].to!wstring, "cn=admin"w, "secret"w);
    assert(directory.isOpen());
    auto one = directory.search("dc=example"w, "(objectClass=*)"w, 0);
    assert(one.length == 1 && one[0].attributes["uid"w][0] == "алиса"w);
    assert(one[0].attributes["memberOf"w] == ["cn=one"w, "cn=two"w]);
    auto all = directory.search("dc=example"w, "(objectClass=*)"w, 1);
    assert(all.length == 2 && all[0].attributes["uid"w][0] == "alice"w && all[1].attributes["uid"w][0] == "bob"w);
    directory.close(); directory.close(); assert(!directory.isOpen());
    bool failed; try { directory.search(""w, "(objectClass=*)"w, 0); } catch (Exception) { failed = true; } assert(failed);
}
''', encoding="utf-8")
    exe = temp / "transport.exe"
    subprocess.run(["dmd", *import_args(), "-I" + str(ROOT / "ldap/source"), str(source),
                    str(ROOT / "ldap/source/z8/ldap/windows.d"), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    fixture = Fixture()
    try:
        subprocess.run([str(exe), str(fixture.port)], cwd=temp, timeout=20, check=True)
    finally:
        fixture.thread.join(20)
    if fixture.failure:
        raise fixture.failure
    assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"dc=example", None),
                              ("search", b"dc=example", b""), ("search", b"dc=example", b"next"), ("unbind",)]
    fixture = Fixture()
    try:
        subprocess.run([str(exe), str(fixture.port), "provider"], cwd=temp, timeout=20, check=True)
    finally:
        fixture.thread.join(20)
    if fixture.failure:
        raise fixture.failure
    assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"dc=example", b""),
                              ("search", b"dc=example", b"next"), ("unbind",)]
    print("Windows LDAP transport: OK")
