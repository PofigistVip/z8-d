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
import org.zenframework.z8.base.application.Application;
[name "User"] public class CustomUser extends User {
    bool hasAddress;
    virtual protected void onBeforeLoad(string input) { hasAddress = Application.requestParameters().containsKey("address"); }
    virtual protected bool authenticate(string password) { return login == "Bob" && password == "override" && hasAddress; }
    virtual protected void onLoad() { parameters.add("custom", true); parameters.add("plainPasswordVisible", Application.requestParameters().containsKey("plainPassword")); }
}
''', encoding="utf-8")
    (source / "CustomUsers.bl").write_text('''
import org.zenframework.z8.base.table.system.Users;
import org.zenframework.z8.base.security.LoginParameters;
import org.zenframework.z8.base.application.Application;
public class CustomUsers extends Users {
    virtual protected void beforeCreate(guid id) {
        if (name.get() == "New Trusted") {
            if (!Application.requestParameters().containsKey("plainPassword")) throw "missing one-time password";
            firstName = "hook-ok";
        }
        if (name.get() == "Banned New") banned = true;
        if (name.get() == "Rejected New") throw "rejected by hook";
    }
    virtual protected bool getParameters(LoginParameters login, primary[string] parameters) {
        if (login.login() == "Denied New") return false;
        parameters.add("tenant", login.schema()); return true;
    }
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
import z8.integration.protobuf_postgres_authority;
import z8.integration.protobuf_http_authority;
import z8.authority.notifications;
import z8.authority.messages;
import z8.authority.service;
import z8.authority.client;
import z8.authority.transport;
import z8gen.p_Probe;
import z8gen.p_CustomUser;
import z8gen.p_CustomUsers;
import std.stdio : writeln, stdout, readln;
import std.string : strip;
import std.conv : to;
import core.thread : Thread;
class LoopbackPublisher : IZ8AuthorityChangePublisher {
    Z8SessionManager sessions;
    this(Z8SessionManager sessions) { this.sessions = sessions; }
    void publish(Z8AuthorityChangeKind kind, const(ubyte)[] payload) { z8_apply_authority_change(sessions, kind, payload); }
}
class LoopbackRpc : IZ8AuthorityRpcTransport {
    Z8ProtobufAuthorityService service;
    this(Z8ProtobufAuthorityService service) { this.service = service; }
    ubyte[] call(Z8AuthorityMethod method, const(ubyte)[] payload) { return service.dispatch(method, payload); }
}
class FailingNotifier : IZ8UserChangeNotifier {
    void userChanged(Z8Guid id, wstring schema) { throw new Exception("notification failed"); }
}
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto connection = new Z8PostgresConnection(args[1]);
    auto registry = new Z8RuntimeRegistry(); auto sample = P.m_sample();
    registry.registerTable(sample); registry.registerRequest(sample);
    registry.registerNamedType("User"w, "CustomUser"w, typeid(Z8p_437573746F6D55736572));
    registry.registerNamedType("SystemUsers"w, "CustomUsers"w, typeid(Z8p_437573746F6D5573657273));
    z8_postgres_bootstrap(connection, "public"w, [P.m_userRoles(), P.m_userEntries(), P.m_entries(), P.m_roles(), P.m_users(), P.m_sequences(), P.m_tables(), P.m_fields(), P.m_requests(), P.m_tableAccess(), P.m_fieldAccess(), P.m_requestAccess(), sample], registry);
    connection.execute(`UPDATE "SystemUsers" SET "Password" = md5('secret'), "Change Password" = 1 WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    connection.execute(`INSERT INTO "SystemUsers" ("RecordId", "Name", "Password") VALUES ('00000000-0000-0000-0000-000000000055', 'Bob', md5('bobsecret'))`);
    connection.execute(`INSERT INTO "SystemUsers" ("RecordId", "Name", "Password") VALUES ('00000000-0000-0000-0000-000000000057', 'Fail', md5('secret'))`);
    connection.execute(`INSERT INTO "SystemUserRoles" ("RecordId", "User", "Role") VALUES ('00000000-0000-0000-0000-000000000056', '00000000-0000-0000-0000-000000000055', '421A8413-A8EC-4DAB-9235-9A5FF83341C5')`);
    auto applicationConfig = z8_application_configuration(); applicationConfig.clientHashesPasswords = false; z8_application_configure(applicationConfig);
    Z8PostgresAuthenticationConfig config; config.clientHashesPasswords = false; config.maxFailedAttempts = 2; config.banMilliseconds = 60_000;
    auto failingConfig = config; failingConfig.maxFailedAttempts = 1;
    auto failingAuth = new Z8PostgresAuthenticator(connection, "public"w, null, failingConfig, new FailingNotifier());
    bool notificationFailed;
    try { failingAuth.authenticate("Fail"w, "wrong"w); } catch (Exception) { notificationFailed = true; }
    assert(notificationFailed && !connection.inTransaction());
    assert(connection.execute(`SELECT "Banned Until" > 0 FROM "SystemUsers" WHERE "Name" = 'Fail'`).rows[0][0].text == "t");
    auto sessions = new Z8SessionManager(60_000, true);
    auto remoteSessions = new Z8SessionManager();
    auto remoteBob = new Z8UserData(); remoteBob.id = z8_guid_create(85); remoteBob.roles = [z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5")];
    remoteSessions.create("remote-bob"w, remoteBob, remoteBob, "public"w);
    auto notifier = new Z8ProtobufAuthorityNotifier(new LoopbackPublisher(remoteSessions));
    auto authority = new Z8PostgresHttpAuthority(connection, "public"w, registry, config, sessions, "test"w, notifier, notifier);
    auto expiredUser = new Z8UserData(); expiredUser.id = z8_guid_create(500);
    auto expired = sessions.create("expired"w, expiredUser, expiredUser, "public"w); expired.lastAccessTime = 0;
    assert(authority.authorize(null, "expired"w, "test"w) is null);
    auto service = new Z8ProtobufAuthorityService(new Z8ProtobufPostgresAuthority(authority));
    auto trustedRequest = Z8AuthorityTrustedLogin(z8_guid_create(85), "ignored"w, "public"w, "10.0.0.1"w, false);
    bool trustedDisabled;
    try { service.trustedLogin(z8_encode_authority_trusted_login(trustedRequest)); } catch (Exception) { trustedDisabled = true; }
    assert(trustedDisabled);
    auto trustedService = new Z8ProtobufAuthorityService(new Z8ProtobufPostgresAuthority(authority, true));
    auto trustedClient = new Z8ProtobufAuthorityClient(new LoopbackRpc(trustedService));
    auto trustedSession = trustedClient.trustedLogin(trustedRequest);
    assert(trustedSession !is null && trustedSession.user.id == z8_guid_create(85) && trustedSession.user.login == "Bob"w);
    assert(z8_optional_require(z8_primary_cast!bool(trustedSession.user.parameters.z8_get("custom"w))));
    assert(z8_primary_cast!wstring(trustedSession.user.parameters.z8_get("tenant"w)) == "public"w);
    trustedRequest.userId = z8_guid_create(87); trustedRequest.login = null;
    assert(trustedClient.trustedLogin(trustedRequest) is null); // Timed bans still apply.
    trustedRequest.userId = null; trustedRequest.login = "bob"w; trustedRequest.createIfMissing = true;
    assert(trustedClient.trustedLogin(trustedRequest) !is null);
    trustedRequest.schema = "other"w; assert(trustedClient.trustedLogin(trustedRequest) is null);
    trustedRequest.schema = "public"w; trustedRequest.login = "New Trusted"w;
    auto createdSession = trustedClient.trustedLogin(trustedRequest);
    assert(createdSession !is null && createdSession.user.login == "New Trusted"w && createdSession.user.firstName == "hook-ok"w);
    assert(!z8_optional_require(z8_primary_cast!bool(createdSession.user.parameters.z8_get("plainPasswordVisible"w))));
    auto createdRow = connection.execute(`SELECT "Password", "Change Password" FROM "SystemUsers" WHERE "Name" = 'New Trusted'`);
    assert(createdRow.rows.length == 1 && createdRow.rows[0][0].text.length == 32 && createdRow.rows[0][0].text != "d41d8cd98f00b204e9800998ecf8427e" && createdRow.rows[0][1].text == "1");
    trustedRequest.login = "Denied New"w;
    assert(trustedClient.trustedLogin(trustedRequest) is null);
    assert(connection.execute(`SELECT count(*) FROM "SystemUsers" WHERE "Name" = 'Denied New'`).rows[0][0].text == "0");
    trustedRequest.login = "Banned New"w;
    assert(trustedClient.trustedLogin(trustedRequest) is null);
    assert(connection.execute(`SELECT count(*) FROM "SystemUsers" WHERE "Name" = 'Banned New'`).rows[0][0].text == "0");
    trustedRequest.login = "Rejected New"w; bool creationHookRejected;
    try { trustedClient.trustedLogin(trustedRequest); } catch (Exception) { creationHookRejected = true; }
    assert(creationHookRejected && connection.execute(`SELECT count(*) FROM "SystemUsers" WHERE "Name" = 'Rejected New'`).rows[0][0].text == "0");
    trustedRequest.userId = z8_guid_create(99999); trustedRequest.login = "Requested ID"w; bool missingIdRejected;
    try { trustedClient.trustedLogin(trustedRequest); } catch (Exception) { missingIdRejected = true; }
    assert(missingIdRejected);
    trustedRequest.userId = z8_guid_create(85); trustedRequest.login = null;
    assert(trustedClient.trustedLogin(trustedRequest) !is null);
    Z8ApplicationSession concurrentA, concurrentB; string concurrentErrorA, concurrentErrorB;
    auto workerA = new Thread({ try { concurrentA = trustedClient.trustedLogin(Z8AuthorityTrustedLogin(null, "Concurrent"w, "public"w, null, true)); } catch (Throwable error) { concurrentErrorA = error.msg; } });
    auto workerB = new Thread({ try { concurrentB = trustedClient.trustedLogin(Z8AuthorityTrustedLogin(null, "cOnCuRrEnT"w, "public"w, null, true)); } catch (Throwable error) { concurrentErrorB = error.msg; } });
    workerA.start(); workerB.start(); workerA.join(); workerB.join();
    assert(!concurrentErrorA.length && !concurrentErrorB.length && concurrentA !is null && concurrentB !is null && concurrentA.user.id == concurrentB.user.id);
    assert(connection.execute(`SELECT count(*) FROM "SystemUsers" WHERE lower("Name") = 'concurrent'`).rows[0][0].text == "1");
    auto loginRequest = Z8AuthorityLogin("Bob"w, "override"w, "public"w, "10.0.0.1"w);
    auto rpcLogin = z8_decode_authority_reply(service.login(z8_encode_authority_login(loginRequest)));
    assert(!rpcLogin.denied && rpcLogin.session.session.user.login == "Bob"w);
    auto rpcAuth = Z8AuthorityAuthorize(rpcLogin.session.session.id, "public"w, "test"w);
    assert(!z8_decode_authority_reply(service.authorize(z8_encode_authority_authorize(rpcAuth))).denied);
    rpcAuth.schema = "other"w;
    assert(z8_decode_authority_reply(service.authorize(z8_encode_authority_authorize(rpcAuth))).denied);
    Z8AuthorityChange roleChange; roleChange.id = z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5"); roleChange.schema = "public"w;
    assert(service.applyRoleChanged(z8_encode_authority_change(roleChange)).length == 0);
    assert(remoteSessions.getSession("remote-bob"w) !is null);
    rpcAuth.schema = "public"w;
    assert(z8_decode_authority_reply(service.authorize(z8_encode_authority_authorize(rpcAuth))).denied);
    rpcLogin = z8_decode_authority_reply(service.login(z8_encode_authority_login(loginRequest)));
    rpcAuth.sessionId = rpcLogin.session.session.id;
    Z8AuthorityChange userChange; userChange.id = z8_guid_create(85); userChange.schema = "public"w;
    assert(service.applyUserChanged(z8_encode_authority_change(userChange)).length == 0);
    assert(z8_decode_authority_reply(service.authorize(z8_encode_authority_authorize(rpcAuth))).denied);
    assert(remoteSessions.getSession("remote-bob"w) !is null);
    auto client = new Z8ProtobufAuthorityClient(new LoopbackRpc(service));
    auto remoteLogin = client.login(loginRequest); assert(remoteLogin !is null && remoteLogin.user.login == "Bob"w);
    auto remoteRequest = Z8AuthorityAuthorize(remoteLogin.id, "public"w, "test"w);
    assert(client.authorize(remoteRequest) !is null);
    bool badLogout;
    try { client.logout(Z8AuthorityLogout(remoteLogin.id, "other"w)); } catch (Exception) { badLogout = true; }
    assert(badLogout && client.authorize(remoteRequest) !is null);
    client.userChanged(z8_guid_create(85), "public"w); assert(client.authorize(remoteRequest) is null);
    assert(remoteSessions.getSession("remote-bob"w) is null);
    remoteSessions.create("remote-bob"w, remoteBob, remoteBob, "public"w);
    roleChange.schema = "other"w; bool rejected;
    try { service.roleChanged(z8_encode_authority_change(roleChange)); } catch (Exception) { rejected = true; } assert(rejected);
    auto httpAuthority = new Z8ProtobufHttpAuthority(client, "public"w);
    z8_runtime_set_registry(registry);
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto db = connection.openSibling(); scope(exit) db.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(db, "public"w, registry));
        scope(exit) z8_connection_set_current(previous);
        z8_application_dispatch_request();
    }, 8192, Z8ResponseMode.application, "test"w, httpAuthority);
    writeln(server.port()); stdout.flush(); readln();
    assert(remoteSessions.getSession("remote-bob"w) is null); // Failed login was broadcast.
    remoteSessions.create("remote-bob"w, remoteBob, remoteBob, "public"w);
    authority.roleChanged(z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5"), "public"w);
    assert(remoteSessions.getSession("remote-bob"w) is null);
    writeln("invalidated"); stdout.flush();
    readln();
    server.stop(); connection.close();
}
''', encoding="utf-8")
    exe = temp / ("authority.exe" if os.name == "nt" else "authority")
    args = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"),
            "-I" + str(root / "webserver/source"), "-I" + str(root / "integrations/postgres_webserver/source"),
            "-I" + str(root / "integrations/protobuf_postgres_webserver/source"), "-I" + str(root / "integrations/protobuf_webserver/source"),
            "-I" + str(root / "protocol/source"),
            *import_args(), *map(str, generated.rglob("*.d")),
            *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(root / "webserver/source/z8/webserver/civetweb.d"),
            str(root / "integrations/postgres_webserver/source/z8/integration/postgres_authority.d"),
            str(root / "integrations/protobuf_postgres_webserver/source/z8/integration/protobuf_postgres_authority.d"),
            str(root / "integrations/protobuf_webserver/source/z8/integration/protobuf_http_authority.d"),
            *map(str, (root / "protocol/source/z8/protobuf").glob("*.d")),
            *map(str, (root / "protocol/source/z8/authority").glob("*.d")),
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
            assert admin["user"]["changePassword"]
            assert request(request="settings", session=admin_token, server="test", data='{"theme":"night"}')[1]["success"]
            assert request(request="login", session=admin_token, server="test", email="first@example.org")[1]["success"]
            assert request(request="login", session=admin_token, server="test", email="second@example.org")[1]["success"]
            assert request(request="login", session=admin_token, server="test", password="secret", newPassword="new-secret")[1]["success"]
            status, refreshed = request(request="login", session=admin_token, server="test")
            assert status == 200 and refreshed["success"]
            assert refreshed["user"]["settings"] == '{"theme":"night"}'
            assert refreshed["user"]["email"] == "second@example.org" and not refreshed["user"]["changePassword"]
            status, bob = request(request="login", login="Bob", password="override")
            assert status == 200 and bob["success"] and not bob["user"]["administrator"] and bob["user"]["parameters"]["custom"]
            assert bob["user"]["parameters"]["tenant"] == "public"
            bob_token = bob["session"]
            assert re.fullmatch(r"[0-9a-f]{64}", bob_token) and bob_token != admin_token
            # Failed login updates the user's counter and revokes existing sessions.
            assert request(request="login", login="Bob", password="wrong")[0] == 401
            assert request(request="login", session=bob_token, server="test")[0] == 401
            status, bob = request(request="login", login="Bob", password="override")
            assert status == 200 and bob["success"]
            bob_token = bob["session"]
            # Built-in administrator sessions are excluded from these notifications.
            assert request(request="login", login="Admin", password="wrong")[0] == 401
            assert request(request="login", session=admin_token, server="test")[0] == 200
            assert request(request="login", session=bob_token, server="wrong")[0] == 401
            assert request(request="login", session=bob_token, server="test")[0] == 200
            process.stdin.write("invalidate\n"); process.stdin.flush()
            assert process.stdout.readline().strip() == "invalidated"
            assert request(request="login", session=bob_token, server="test")[0] == 401
            assert request(request="login", session=admin_token, server="test")[0] == 200
            status, second_admin = request(request="login", login="Admin", password="new-secret")
            assert status == 200 and second_admin["session"] != admin_token
            assert request(request="login", session=admin_token, server="test")[0] == 401
            admin_token = second_admin["session"]
            status, result = request(request="logout", session=admin_token, server="test")
            assert status == 200 and result["success"]
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
