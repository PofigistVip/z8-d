"""Exercise PostgreSQL-backed authentication through CivetWeb over loopback."""
from pathlib import Path
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlencode

from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_authority_http.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
sys.path.insert(0, str(root / "webserver"))
from build_civetweb import build

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "Sample"] [generatable] [request] public class Sample extends Table { [name "Title"] StringField title; }
''', encoding="utf-8")
    (source / "CustomUser.bl").write_text('''
import org.zenframework.z8.base.security.User;
[name "User"] public class CustomUser extends User {
    virtual protected bool authenticate(string password) { return login == "Bob" && password == "override"; }
    virtual protected void onLoad() { parameters.add("custom", true); }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.system.Roles;
import org.zenframework.z8.base.table.system.Users;
import org.zenframework.z8.base.table.system.UserRoles;
import org.zenframework.z8.base.table.system.Entries;
import org.zenframework.z8.base.table.system.UserEntries;
import org.zenframework.z8.base.table.system.Sequences;
import org.zenframework.z8.base.table.system.Tables;
import org.zenframework.z8.base.table.system.Fields;
import org.zenframework.z8.base.table.system.Requests;
import org.zenframework.z8.base.table.system.RoleTableAccess;
import org.zenframework.z8.base.table.system.RoleFieldAccess;
import org.zenframework.z8.base.table.system.RoleRequestAccess;
public class Probe {
    public static Sample sample() { Sample v; return v; }
    public static Roles roles() { Roles v; return v; }
    public static Users users() { Users v; return v; }
    public static UserRoles userRoles() { UserRoles v; return v; }
    public static Entries entries() { Entries v; return v; }
    public static UserEntries userEntries() { UserEntries v; return v; }
    public static Sequences sequences() { Sequences v; return v; }
    public static Tables tables() { Tables v; return v; }
    public static Fields fields() { Fields v; return v; }
    public static Requests requests() { Requests v; return v; }
    public static RoleTableAccess tableAccess() { RoleTableAccess v; return v; }
    public static RoleFieldAccess fieldAccess() { RoleFieldAccess v; return v; }
    public static RoleRequestAccess requestAccess() { RoleRequestAccess v; return v; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    civet = temp / ("civetweb.obj" if os.name == "nt" else "civetweb.o")
    build(civet)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.bootstrap;
import z8.database.authentication;
import z8.webserver.civetweb;
import z8.integration.postgres_authority;
import z8.authority.notifications;
import z8gen.p_Probe;
import z8gen.p_CustomUser;
import std.stdio : writeln, stdout, readln;
import std.string : strip;
import std.conv : to;
class LoopbackPublisher : IZ8AuthorityChangePublisher {
    Z8SessionManager sessions;
    this(Z8SessionManager sessions) { this.sessions = sessions; }
    void publish(Z8AuthorityChangeKind kind, const(ubyte)[] payload) { z8_apply_authority_change(sessions, kind, payload); }
}
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto connection = new Z8PostgresConnection(args[1]);
    auto registry = new Z8RuntimeRegistry(); auto sample = P.m_sample();
    registry.registerTable(sample); registry.registerRequest(sample);
    registry.registerNamedType("User"w, "CustomUser"w, typeid(Z8p_437573746F6D55736572));
    z8_postgres_bootstrap(connection, "public"w, [P.m_userRoles(), P.m_userEntries(), P.m_entries(), P.m_roles(), P.m_users(), P.m_sequences(), P.m_tables(), P.m_fields(), P.m_requests(), P.m_tableAccess(), P.m_fieldAccess(), P.m_requestAccess(), sample], registry);
    connection.execute(`UPDATE "SystemUsers" SET "Password" = md5('secret') WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    connection.execute(`INSERT INTO "SystemUsers" ("RecordId", "Name", "Password") VALUES ('00000000-0000-0000-0000-000000000055', 'Bob', md5('bobsecret'))`);
    connection.execute(`INSERT INTO "SystemUserRoles" ("RecordId", "User", "Role") VALUES ('00000000-0000-0000-0000-000000000056', '00000000-0000-0000-0000-000000000055', '421A8413-A8EC-4DAB-9235-9A5FF83341C5')`);
    auto applicationConfig = z8_application_configuration(); applicationConfig.clientHashesPasswords = false; z8_application_configure(applicationConfig);
    Z8PostgresAuthenticationConfig config; config.clientHashesPasswords = false;
    auto sessions = new Z8SessionManager(60_000, true);
    auto remoteSessions = new Z8SessionManager();
    auto remoteBob = new Z8UserData(); remoteBob.id = z8_guid_create(85); remoteBob.roles = [z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5")];
    remoteSessions.create("remote-bob"w, remoteBob, remoteBob, "public"w);
    auto notifier = new Z8ProtobufAuthorityNotifier(new LoopbackPublisher(remoteSessions));
    auto authority = new Z8PostgresHttpAuthority(connection, "public"w, registry, config, sessions, "test"w, notifier, notifier);
    auto expiredUser = new Z8UserData(); expiredUser.id = z8_guid_create(500);
    auto expired = sessions.create("expired"w, expiredUser, expiredUser, "public"w); expired.lastAccessTime = 0;
    assert(authority.authorize(null, "expired"w, "test"w) is null);
    z8_runtime_set_registry(registry);
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto db = connection.openSibling(); scope(exit) db.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(db, "public"w, registry));
        scope(exit) z8_connection_set_current(previous);
        z8_application_dispatch_request();
    }, 8192, Z8ResponseMode.application, "test"w, authority);
    writeln(server.port()); stdout.flush(); readln();
    authority.roleChanged(z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5"), "public"w);
    assert(remoteSessions.getSession("remote-bob"w) is null);
    writeln("invalidated"); stdout.flush();
    authority.logout(readln().strip().to!wstring); writeln("logged out"); stdout.flush(); readln();
    server.stop(); connection.close();
}
''', encoding="utf-8")
    exe = temp / ("authority.exe" if os.name == "nt" else "authority")
    args = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"),
            "-I" + str(root / "webserver/source"), "-I" + str(root / "integrations/postgres_webserver/source"), "-I" + str(root / "protocol/source"),
            *import_args(), *map(str, generated.rglob("*.d")),
            *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(root / "webserver/source/z8/webserver/civetweb.d"),
            str(root / "integrations/postgres_webserver/source/z8/integration/postgres_authority.d"),
            str(root / "protocol/source/z8/protobuf/wire.d"), str(root / "protocol/source/z8/authority/notifications.d"),
            str(root / "protocol/source/z8/protobuf/guid.d"),
            str(harness), str(civet), str(runtime), "-of=" + str(exe)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq", "-L-lpthread", "-L-ldl"]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        process = subprocess.Popen([str(exe), connection], cwd=temp, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            line = process.stdout.readline().strip()
            if not line.isdigit():
                raise RuntimeError("Server did not start: " + line + process.stderr.read())
            port = int(line)
            def request(**parameters):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    conn.request("GET", "/request.json?" + urlencode(parameters))
                    response = conn.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    conn.close()
            status, denied = request(request="login", login="Admin", password="wrong")
            assert status == 401 and not denied["success"]
            status, admin = request(request="login", login="admin", password="secret")
            assert status == 200 and admin["success"] and admin["user"]["administrator"]
            admin_token = admin["session"]
            assert re.fullmatch(r"[0-9a-f]{64}", admin_token)
            status, bob = request(request="login", login="Bob", password="override")
            assert status == 200 and bob["success"] and not bob["user"]["administrator"] and bob["user"]["parameters"]["custom"]
            bob_token = bob["session"]
            assert re.fullmatch(r"[0-9a-f]{64}", bob_token) and bob_token != admin_token
            assert request(request="login", session=bob_token, server="wrong")[0] == 401
            assert request(request="login", session=bob_token, server="test")[0] == 200
            process.stdin.write("invalidate\n"); process.stdin.flush()
            assert process.stdout.readline().strip() == "invalidated"
            assert request(request="login", session=bob_token, server="test")[0] == 401
            assert request(request="login", session=admin_token, server="test")[0] == 200
            status, second_admin = request(request="login", login="Admin", password="secret")
            assert status == 200 and second_admin["session"] != admin_token
            assert request(request="login", session=admin_token, server="test")[0] == 401
            admin_token = second_admin["session"]
            process.stdin.write(admin_token + "\n"); process.stdin.flush()
            assert process.stdout.readline().strip() == "logged out"
            assert request(request="login", session=admin_token, server="test")[0] == 401
        finally:
            if process.poll() is None:
                process.stdin.write("stop\n"); process.stdin.flush()
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); stdout, stderr = process.communicate()
                raise RuntimeError("Authority server did not stop")
            if process.returncode:
                raise RuntimeError(f"Authority server failed ({process.returncode}): {stdout}\n{stderr}")
print("PostgreSQL HTTP login, cryptographic sessions and role invalidation verified")
