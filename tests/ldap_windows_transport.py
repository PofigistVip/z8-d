"""Exercise the Windows LDAP transport against a local LDAP protocol fixture."""
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading

from runtime_support import import_args, runtime_library, ROOT

if os.name != "nt":
    raise SystemExit("This test requires Windows WinLDAP")
sys.path.insert(0, str(ROOT / "ldap"))
from dub_package import source as ldap_package_source


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
    def __init__(self, tls_context=None, reject_tls=False, bind_code=0):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(15)
        self.port = self.listener.getsockname()[1]
        self.events = []
        self.failure = None
        self.tls_context = tls_context
        self.reject_tls = reject_tls
        self.bind_code = bind_code
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            connection, _ = self.listener.accept()
            if self.tls_context:
                try:
                    connection = self.tls_context.wrap_socket(connection, server_side=True)
                except (ssl.SSLError, ConnectionResetError):
                    if self.reject_tls:
                        return
                    raise
            with connection:
                connection.settimeout(15)
                page = 0
                while True:
                    try:
                        message = recv_message(connection)
                    except EOFError:
                        if self.bind_code:
                            break
                        raise
                    _, mid, offset = read_tlv(message)
                    tag, operation, offset = read_tlv(message, offset)
                    message_id = tlv(2, mid)
                    if tag == 0x60:
                        _, _, pos = read_tlv(operation)
                        _, principal, pos = read_tlv(operation, pos)
                        _, password, _ = read_tlv(operation, pos)
                        self.events.append(("bind", principal, password))
                        connection.sendall(tlv(0x30, message_id + tlv(0x61, result(self.bind_code))))
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
                            paged = oid == b"1.2.840.113556.1.4.319"
                            if paged:
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
    z8_server_config_replace(["ldap.read.pageSize"w: "-1"w]);
    bool invalid; try { z8_windows_ldap_configure(); } catch (Exception) { invalid = true; } assert(invalid);
    bool tls = args.length > 2 && (args[2] == "tls-verified" || args[2] == "tls-trusted");
    bool trusted = args.length > 2 && args[2] == "tls-trusted";
    z8_server_config_replace(["ldap.read.pageSize"w: "1"w, "ldap.connect.timeout"w: "3000"w,
                              "ldap.ssl.trusted"w: trusted ? "true"w : "false"w]);
    auto previous = z8_windows_ldap_configure(); auto configured = z8_ldap_set_provider(previous);
    auto url = (tls ? "ldaps://127.0.0.1:"w : "ldap://127.0.0.1:"w) ~ args[1].to!wstring;
    if (args.length > 3 && args[2] == "failover")
        url = " \tldap://127.0.0.1:"w ~ args[3].to!wstring ~ "  "w ~ url ~ "  "w;
    if (args.length > 2 && args[2] == "urlbase") url ~= "/dc%3Dexample"w;
    if (tls && !trusted) {
        bool rejected; try { configured.open(url, "cn=admin"w, "secret"w, "{}"w); } catch (Exception) { rejected = true; }
        assert(rejected); return;
    }
    if (args.length > 2 && args[2] == "unicode") {
        auto session = configured.open(url, "cn=Пользователь"w, "пароль😀"w, "{}"w);
        session.close(); return;
    }
    if (args.length > 2) {
        auto session = configured.open(url, "cn=admin"w, "secret"w,
            `{users:{loginField:"uid",groupField:"memberOf"}}`w);
        auto users = session.users(args[2] == "urlbase" ? "ou=users"w : "dc=example"w, "(objectClass=*)"w);
        assert(users.length == 2 && users[0].login == "alice"w && users[1].login == "bob"w);
        assert(users[0].memberOf == ["cn=one"w, "cn=two"w]);
        session.close(); return;
    }
    auto transport = new Z8WindowsLdapTransport();
    foreach (invalidUrl; ["http://host"w, "ldap://"w, "ldap://host:"w, "ldap://host:0"w, "ldap://host:65536"w, "ldap://host/?query"w]) {
        bool failed; try { transport.connect(invalidUrl, ""w, ""w); } catch (Exception) { failed = true; } assert(failed);
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
    package = ldap_package_source(ROOT)
    subprocess.run(["dmd", *import_args(), "-I" + str(ROOT / "ldap/source"), "-I" + str(package.parent), str(source),
                    str(ROOT / "ldap/source/z8/ldap/windows.d"), str(package), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    fixture = Fixture()
    try:
        subprocess.run([str(exe), str(fixture.port), "unicode"], cwd=temp, timeout=20, check=True)
    finally:
        fixture.thread.join(20)
    if fixture.failure:
        raise fixture.failure
    assert fixture.events == [("bind", "cn=Пользователь".encode(), "пароль😀".encode()), ("unbind",)]
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
    fixture = Fixture()
    try:
        subprocess.run([str(exe), str(fixture.port), "urlbase"], cwd=temp, timeout=20, check=True)
    finally:
        fixture.thread.join(20)
    if fixture.failure:
        raise fixture.failure
    assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"ou=users,dc=example", b""),
                              ("search", b"ou=users,dc=example", b"next"), ("unbind",)]
    unavailable = socket.socket()
    unavailable.bind(("127.0.0.1", 0))  # A reserved port without a listener.
    try:
        fixture = Fixture()
        try:
            subprocess.run([str(exe), str(fixture.port), "failover", str(unavailable.getsockname()[1])],
                           cwd=temp, timeout=20, check=True)
        finally:
            fixture.thread.join(20)
        if fixture.failure:
            raise fixture.failure
        assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"dc=example", b""),
                                  ("search", b"dc=example", b"next"), ("unbind",)]
        # Compare failover with the JNDI provider used by the Java LdapAPI.
        if shutil.which("javac") and shutil.which("java"):
            oracle = temp / "LdapFailoverOracle.java"
            oracle.write_text('''import java.util.Hashtable;
import javax.naming.Context;
import javax.naming.directory.InitialDirContext;
import javax.naming.directory.SearchControls;
class LdapFailoverOracle {
    public static void main(String[] args) throws Exception {
        Hashtable<String, String> env = new Hashtable<>();
        env.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");
        env.put(Context.PROVIDER_URL, "ldap://127.0.0.1:" + args[0] + " ldap://127.0.0.1:" + args[1]);
        if (args.length > 2) env.put(Context.PROVIDER_URL, "ldap://127.0.0.1:" + args[1] + "/dc%3Dexample");
        env.put(Context.SECURITY_AUTHENTICATION, "simple");
        env.put(Context.SECURITY_PRINCIPAL, "cn=admin");
        env.put(Context.SECURITY_CREDENTIALS, "secret");
        env.put("com.sun.jndi.ldap.connect.timeout", "3000");
        InitialDirContext context = new InitialDirContext(env);
        if (args.length > 2) {
            SearchControls controls = new SearchControls(); controls.setSearchScope(SearchControls.SUBTREE_SCOPE);
            context.search("ou=users", "(objectClass=*)", controls).close();
        }
        context.close();
    }
}
''', encoding="utf-8")
            subprocess.run(["javac", "-source", "8", "-target", "8", str(oracle)], cwd=temp, check=True)
            fixture = Fixture()
            try:
                subprocess.run(["java", "-cp", str(temp), "LdapFailoverOracle",
                                str(unavailable.getsockname()[1]), str(fixture.port)], cwd=temp, timeout=20, check=True)
            finally:
                fixture.thread.join(20)
            if fixture.failure:
                raise fixture.failure
            assert fixture.events == [("bind", b"cn=admin", b"secret"), ("unbind",)]
            denied, fixture = Fixture(bind_code=49), Fixture()
            try:
                subprocess.run(["java", "-cp", str(temp), "LdapFailoverOracle", str(denied.port), str(fixture.port)],
                               cwd=temp, timeout=20, check=True)
            finally:
                denied.thread.join(20)
                fixture.thread.join(20)
            if denied.failure:
                raise denied.failure
            if fixture.failure:
                raise fixture.failure
            assert denied.events[0] == ("bind", b"cn=admin", b"secret")
            assert fixture.events == [("bind", b"cn=admin", b"secret"), ("unbind",)]
            fixture = Fixture()
            try:
                oracle_process = subprocess.run(["java", "-cp", str(temp), "LdapFailoverOracle", "0", str(fixture.port), "base"],
                                                cwd=temp, timeout=20)
            finally:
                fixture.thread.join(20)
            if fixture.failure:
                raise fixture.failure
            assert oracle_process.returncode == 0
            assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"ou=users,dc=example", None), ("unbind",)]
    finally:
        unavailable.close()
    denied, fixture = Fixture(bind_code=49), Fixture()
    try:
        subprocess.run([str(exe), str(fixture.port), "failover", str(denied.port)], cwd=temp, timeout=20, check=True)
    finally:
        denied.thread.join(20)
        fixture.thread.join(20)
    if denied.failure:
        raise denied.failure
    if fixture.failure:
        raise fixture.failure
    assert denied.events[0] == ("bind", b"cn=admin", b"secret")
    assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"dc=example", b""),
                              ("search", b"dc=example", b"next"), ("unbind",)]
    openssl = shutil.which("openssl")
    if not openssl:
        git_openssl = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/mingw64/bin/openssl.exe"
        openssl = str(git_openssl) if git_openssl.is_file() else None
    if openssl:
        key, cert = temp / "key.pem", temp / "cert.pem"
        subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                        "-out", str(cert), "-days", "1", "-subj", "/CN=127.0.0.1"],
                       cwd=temp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        for mode in ("tls-verified", "tls-trusted"):
            fixture = Fixture(context, reject_tls=mode == "tls-verified")
            try:
                subprocess.run([str(exe), str(fixture.port), mode], cwd=temp, timeout=20, check=True)
            finally:
                fixture.thread.join(20)
            if fixture.failure:
                raise fixture.failure
            if mode == "tls-trusted":
                assert fixture.events == [("bind", b"cn=admin", b"secret"), ("search", b"dc=example", b""),
                                          ("search", b"dc=example", b"next"), ("unbind",)]
            else:
                assert fixture.events == []
    else:
        print("TLS fixture skipped: openssl not found")
    print("Windows LDAP transport: OK")
