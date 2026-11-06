"""Exercise authorized BL table reads through CivetWeb and PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from urllib.parse import quote, urlencode

from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_http.py <original-z8-root> [postgres-bin-directory]")
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
    (source / "ApplyAction.bl").write_text('''
import org.zenframework.z8.base.form.action.Action;
import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.sql.Connection;
import org.zenframework.z8.base.application.Application;
public class ApplyAction extends Action {
    virtual protected void execute(guid id, Query context, guid[] selected, Query query) {
        Connection.get().execute("UPDATE \\"Sample\\" SET \\"Amount\\" = \\"Amount\\" + 1 WHERE \\"RecordId\\" = '" + id.toString() + "'");
        if (selected.size() > 0 && id == '00000000-0000-0000-0000-000000000002') throw "action failed";
        Application.info("applied");
    }
}
''', encoding="utf-8")
    (source / "NoTransactionAction.bl").write_text('''
public class NoTransactionAction extends ApplyAction { useTransaction = false; }
''', encoding="utf-8")
    (source / "IncrementAction.bl").write_text('''
import org.zenframework.z8.base.form.action.Action;
import org.zenframework.z8.base.form.action.Parameter;
import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.sql.Connection;
public class IncrementAction extends Action {
    Parameter delta = Parameter.create("delta", 1);
    Parameter enabled = Parameter.create("enabled", true);
    Parameter message = Parameter.create("message", "ready");
    parameters = {delta, enabled, message};
    virtual protected void execute(guid id, Query context, guid[] selected, Query query) {
        if (!(bool)enabled || (string)message != "ready") throw "invalid parameters";
        Connection.get().execute("UPDATE \\"Sample\\" SET \\"Amount\\" = \\"Amount\\" + " + ((int)delta).toString() + " WHERE \\"RecordId\\" = '" + id.toString() + "'");
    }
}
''', encoding="utf-8")
    (source / "ContextAction.bl").write_text('''
import org.zenframework.z8.base.form.action.Action;
import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.application.Application;
public class ContextAction extends Action {
    virtual protected void execute(guid id, Query context, guid[] selected, Query query) {
        if (context == query) Application.info("root");
        else Application.info(query.id());
    }
}
''', encoding="utf-8")
    (source / "CustomReport.bl").write_text('''
import org.zenframework.z8.base.form.report.Report;
public class CustomReport extends Report {
    virtual protected void prepare(guid id) {
        if (id != '00000000-0000-0000-0000-000000000001') throw "invalid report record";
    }
    virtual protected file execute(guid id) { file result = name + "." + format; return result; }
}
''', encoding="utf-8")
    (source / "UpdateJob.bl").write_text('''
import org.zenframework.z8.base.Executable;
import org.zenframework.z8.base.form.action.Parameter;
import org.zenframework.z8.base.sql.Connection;
public class UpdateJob extends Executable {
    Parameter amount = Parameter.create("amount", 1); Parameter fail = Parameter.create("fail", false); Parameter wait = Parameter.create("wait", false);
    parameters = {amount, fail, wait};
    virtual protected void execute(Parameter[] args) {
        Connection.get().execute("UPDATE \\"Sample\\" SET \\"CreatedAt\\" = COALESCE(\\"CreatedAt\\", 0) + " + ((int)amount).toString() + " WHERE \\"RecordId\\" = '00000000-0000-0000-0000-000000000002'");
        progress(50); if ((bool)wait) Connection.get().execute("SELECT pg_sleep(0.4)");
        if ((bool)fail) throw "job failed"; info("job complete");
    }
}
''', encoding="utf-8")
    (source / "NonTransactionalJob.bl").write_text('''
public class NonTransactionalJob extends UpdateJob { useTransaction = false; }
''', encoding="utf-8")
    (source / "ImpersonateJob.bl").write_text('''
import org.zenframework.z8.base.Executable;
import org.zenframework.z8.base.application.Application;
public class ImpersonateJob extends Executable {
    useTransaction = false;
    virtual protected void execute() {
        switchUser('00000000-0000-0000-0000-000000000004'); info(Application.userId().toString());
        resetUser(); info(Application.userId().toString());
    }
}
''', encoding="utf-8")
    (source / "DemoDesktop.bl").write_text('''
import org.zenframework.z8.base.form.Desktop;
[displayName "Dashboard"] public class DemoDesktop extends Desktop { UpdateJob visible; HiddenJob hidden; }
''', encoding="utf-8")
    (source / "HiddenJob.bl").write_text('''
import org.zenframework.z8.base.Executable;
public class HiddenJob extends Executable {}
''', encoding="utf-8")
    (source / "NestedAttachment.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.AttachmentField;
public class NestedAttachment extends Table { [name "Documents"] public AttachmentField documents; }
''', encoding="utf-8")
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.AttachmentField;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.sql.Connection;
public class Sample extends Table {
    [name "Title"] public StringField title;
    [name "Amount"] public IntField amount;
    [name "Blob"] public BinaryField blob;
    [name "Documents"] public AttachmentField documents;
    Table child; [name "ChildLink"] Link childLink = child;
    NestedAttachment nested; [name "NestedLink"] Link nestedLink = nested;
    ApplyAction apply; NoTransactionAction noTransaction; IncrementAction increment; ContextAction inspect;
    actions = {apply, noTransaction, increment, inspect};
    CustomReport exported; reports = {exported};
    virtual protected binary processContentRequest(string[string] params, file[] files) {
        Connection.get().execute("INSERT INTO \\"ContentLog\\" VALUES (1)");
        if (params.containsKey("fail")) throw "content failed";
        if (params.containsKey("empty")) return null;
        return '0, 255, 65, 0';
    }
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
import z8.webserver.civetweb;
import std.stdio : writeln, stdout, readln;
import std.string : startsWith;
import std.conv : to;
__gshared string databaseInfo;

class Authority : IZ8HttpAuthority, IZ8JobUserResolver {
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring id, wstring server) {
        if (server != "test"w || (id != "full"w && id != "full2"w && id != "limited"w && id != "denied"w && id != "field-denied"w && id != "relation-denied"w)) return null;
        auto user = new Z8UserData(); user.id = z8_guid_create(id == "full"w || id == "full2"w ? 2 : 3);
        user.builtinAdministrator = id == "full"w || id == "full2"w;
        user.login = "Alice"w; user.firstName = "Alice"w; user.email = "old@example.org"w; user.settings = "{}"w; user.changePassword = true;
        user.roles = [z8_guid_create(9)]; user.roleNames = ["Operators"w];
        user.entries = [Z8UserEntry(z8_guid_create_name("Sample"w), "Sample"w, "Sample"w),
            Z8UserEntry(z8_guid_create_name("DemoDesktop"w), "DemoDesktop"w, "Dashboard"w), Z8UserEntry(z8_guid_create(9), "MissingEntry"w, "Missing"w)];
        user.parameters.z8_add("theme"w, z8_primary_box("dark"w));
        user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
        user.privileges.setRequestAccess(z8_guid_create_name("HiddenJob"w), Z8Access.init);
        if (id == "limited"w) {
            user.privileges.setFieldAccess(z8_guid_create_name("Sample.Title"w), Z8Access.init);
            user.privileges.setTableAccess(z8_guid_create_name("Sample"w), Z8Access(true, false, false, false, false, true));
        }
        if (id == "denied"w) user.privileges.setRequestAccess(z8_guid_create_name("Sample"w), Z8Access.init);
        if (id == "field-denied"w) {
            user.privileges.setFieldAccess(z8_guid_create_name("Sample.Documents"w), Z8Access.init);
            user.privileges.setFieldAccess(z8_guid_create_name("NestedAttachment.Documents"w), Z8Access.init);
        }
        if (id == "relation-denied"w) user.privileges.setFieldAccess(z8_guid_create_name("Sample.NestedLink"w), Z8Access.init);
        return new Z8ApplicationSession(id, user, user);
    }
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password) {
        return login == "alice"w && password == "secret"w ? authorize(request, "full"w, "test"w) : null;
    }
    Z8UserData resolveJobUser(Z8Guid id) {
        if (id != z8_guid_create(4)) return null;
        auto user = new Z8UserData(); user.id = id;
        user.privileges = new Z8Privileges(Z8Access(true, false, false, false, false, true));
        return user;
    }
}
void main(string[] args) {
    databaseInfo = args[1];
    auto setup = new Z8PostgresConnection(databaseInfo);
    setup.execute(`CREATE TABLE "Sample" ("RecordId" uuid PRIMARY KEY, "Title" text, "Amount" bigint, "Blob" bytea, "Documents" bytea, "ChildLink" uuid, "NestedLink" uuid, "Lock" bigint DEFAULT 0, "CreatedAt" bigint, "CreatedBy" uuid, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
    setup.execute(`CREATE TABLE "NestedAttachment" ("RecordId" uuid PRIMARY KEY, "Documents" bytea, "Lock" bigint DEFAULT 0, "CreatedAt" bigint, "CreatedBy" uuid, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
    setup.execute(`INSERT INTO "NestedAttachment" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000088')`);
    setup.execute(`CREATE TABLE "SystemFiles" ("RecordId" uuid PRIMARY KEY, "Name" text, "File" bytea, "Path" text, "Size" bigint, "Time" bigint, "Last modified" bigint, "Location" bigint, "Lock" bigint DEFAULT 0, "CreatedAt" bigint, "CreatedBy" uuid, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
    setup.execute(`CREATE TABLE "ContentLog" (value integer)`);
    setup.execute(`CREATE TABLE "SystemUsers" ("RecordId" uuid PRIMARY KEY, "Settings" bytea, "Password" text, "Change Password" smallint, "Email" text, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
    setup.execute(`INSERT INTO "SystemUsers" ("RecordId", "Settings", "Password", "Change Password", "Email") VALUES ('00000000-0000-0000-0000-000000000002', convert_to('{}','UTF8'), 'oldhash', 1, 'old@example.org')`);
    setup.execute(`INSERT INTO "Sample" ("RecordId", "Title", "Amount") VALUES ('00000000-0000-0000-0000-000000000001', 'First', 5), ('00000000-0000-0000-0000-000000000002', 'Second', 10)`);
    setup.close();
    auto authority = new Authority();
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto connection = new Z8PostgresConnection(databaseInfo);
        scope(exit) connection.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(connection, "public"w));
        scope(exit) z8_connection_set_current(previous);
        if (request.path.startsWith("/storage/")) z8_application_dispatch_file_download(request.path.to!wstring);
        else z8_application_dispatch_request();
    }, 2048, Z8ResponseMode.application, "test"w, authority, "Denied"w, null, "/request.json", true);
    scope(exit) server.stop();
    writeln(server.port()); stdout.flush(); readln(); server.stop();
    auto verify = new Z8PostgresConnection(databaseInfo);
    auto row = verify.execute(`SELECT encode("Blob", 'hex') FROM "Sample" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "00ff4100");
    row = verify.execute(`SELECT "CreatedAt" FROM "Sample" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "10");
    assert(verify.execute(`SELECT convert_from("Settings", 'UTF8') FROM "SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`).rows[0][0].text == `{"theme":"ночь"}`);
    row = verify.execute(`SELECT "Password", "Change Password", "Email" FROM "SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(row.rows[0][0].text == "newhash" && row.rows[0][1].text == "0" && row.rows[0][2].text == "new@example.org");
    assert(verify.execute(`SELECT count(*) FROM "ContentLog"`).rows[0][0].text == "2");
    assert(verify.execute(`SELECT count(*) FROM "SystemFiles"`).rows[0][0].text == "0");
    verify.execute(`UPDATE "SystemUsers" SET "Password" = md5('old secret') WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    auto originalConfig = z8_application_configuration(), plainConfig = z8_application_configuration();
    plainConfig.clientHashesPasswords = false; z8_application_configure(plainConfig);
    auto plainUser = new Z8UserData(); plainUser.id = z8_guid_create(2);
    auto plainRequest = new Z8ApplicationRequest(); plainRequest.session = new Z8ApplicationSession("plain"w, plainUser, plainUser);
    plainRequest.monitor = new Z8RequestMonitor(); plainRequest.parameters.z8_add("request"w, "login"w);
    plainRequest.parameters.z8_add("password"w, "old secret"w); plainRequest.parameters.z8_add("newPassword"w, "new secret"w);
    auto previousRequest = z8_application_set_request(plainRequest);
    auto previousBackend = z8_connection_set_current(new Z8PostgresDatabase(verify, "public"w));
    z8_application_start_response(plainRequest, "login"w); z8_application_dispatch_request();
    z8_connection_set_current(previousBackend); z8_application_set_request(previousRequest); z8_application_configure(originalConfig);
    assert(verify.execute(`SELECT "Password" = md5('new secret') FROM "SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`).rows[0][0].text == "t");
    verify.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-http.exe" if os.name == "nt" else "postgres-http")
    args = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"),
            "-I" + str(root / "webserver/source"), *import_args(), *map(str, generated.rglob("*.d")),
            *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(root / "webserver/source/z8/webserver/civetweb.d"), str(harness), str(civet), str(runtime),
            "-of=" + str(exe)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq", "-L-lpthread", "-L-ldl"]
    response_file = temp / "dmd.rsp"
    response_file.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response_file)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        process = subprocess.Popen([str(exe), connection], cwd=temp, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            line = process.stdout.readline().strip()
            if not line.isdigit():
                raise RuntimeError("Server did not start: " + line + process.stderr.read())
            port = int(line)
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("GET", "/request.json?" + urlencode(dict(request="login", login="alice", password="secret")))
                response = conn.getresponse(); login = json.loads(response.read())
                assert response.status == 200 and login["success"] and login["session"] == "full", login
                assert login["user"]["login"] == "Alice" and login["user"]["administrator"] and login["user"]["changePassword"], login
                assert login["user"]["roles"][0]["name"] == "Operators" and login["user"]["parameters"]["theme"] == "dark", login
                assert len(login["user"]["entries"]) == 2 and login["user"]["entries"][0]["request"] == "Sample", login
                assert login["maxUploadSize"] == 5 and "password" not in login["user"], login
            finally:
                conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("GET", "/request.json?" + urlencode(dict(request="login", session="full", server="test", experimental="1")))
                response = conn.getresponse(); login = json.loads(response.read())
                assert response.status == 200 and login["success"] and len(login["user"]["data"]) == 2, login
                dashboard = login["user"]["data"][1]
                assert dashboard["text"] == "Dashboard" and len(dashboard["items"]) == 1 and dashboard["items"][0]["request"] == "UpdateJob", login
            finally:
                conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("GET", "/request.json?" + urlencode(dict(request="settings", session="full", server="test", data='{"theme":"ночь"}')))
                response = conn.getresponse(); settings = json.loads(response.read())
                assert response.status == 200 and settings["success"], settings
            finally:
                conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("GET", "/request.json?" + urlencode(dict(request="settings", session="limited", server="test", id="00000000-0000-0000-0000-000000000002", data="attacker")))
                response = conn.getresponse(); settings = json.loads(response.read())
                assert response.status == 200 and settings["success"], settings
            finally:
                conn.close()
            def request(session="full", **params):
                query = dict(request="Sample", action="read", session=session, server="test",
                             fields='["title","amount"]')
                query.update(params)
                if query["action"] is None:
                    query.pop("action")
                if query.get("action") in ("destroy", "action", "report", "archive"):
                    query.pop("fields")
                if query["request"] in ("UpdateJob", "NonTransactionalJob", "ImpersonateJob"):
                    query.pop("fields", None)
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    conn.request("GET", "/request.json?" + urlencode(query))
                    response = conn.getresponse()
                    assert response.status == 200
                    return json.loads(response.read())
                finally:
                    conn.close()
            result = request(request="login", action=None, password="wrong", newPassword="newhash")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(request="login", action=None, password="oldhash", newPassword="newhash")
            assert result["success"], result
            result = request(request="login", action=None, email="OLD@EXAMPLE.ORG")
            assert result["success"], result
            result = request(request="login", action=None, email="new@example.org")
            assert result["success"], result
            result = request(sort='[{"property":"amount","direction":"DESC"}]', limit="1")
            assert result["success"] and result["data"][0]["title"] == "Second", result
            result = request(session="limited")
            assert result["success"] and len(result["data"]) == 2 and all("title" not in row for row in result["data"]), result
            result = request(action="meta")
            assert result["success"] and result["isQuery"] and result["primaryKey"] == "recordId", result
            assert {field["name"] for field in result["fields"]} == {"title", "amount", "recordId", "lock"}, result
            result = request(session="limited", action="meta")
            assert result["success"] and "title" not in {field["name"] for field in result["fields"]}, result
            result = request(action=None)
            assert result["success"] and result["isQuery"] and len(result["data"]) == 2, result
            result = request(action=None, count="true")
            assert result["success"] and result["isQuery"] and result["total"] == 2 and "data" not in result, result
            result = request(session="limited", filter='{"property":"title","value":"First"}')
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(session="denied")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(count="true", filter='{"property":"amount","operator":"gt","value":"5"}')
            assert result["success"] and result["total"] == 1, result
            result = request(totals="true")
            assert result["success"] and result["data"]["amount"] == 15 and "title" not in result["data"], result
            with ThreadPoolExecutor(max_workers=8) as workers:
                results = list(workers.map(lambda i: request(session="limited" if i % 2 else "full"), range(16)))
            assert all(result["success"] and len(result["data"]) == 2 for result in results)
            assert all(("title" not in result["data"][0]) == (i % 2 == 1) for i, result in enumerate(results))
            ids = '["00000000-0000-0000-0000-000000000001","00000000-0000-0000-0000-000000000002"]'
            result = request(session="denied", action="action", name="apply", records=ids)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="action", name="apply", records=ids, selection='["00000000-0000-0000-0000-000000000001"]')
            assert not result["success"] and "action failed" in result["info"]["messages"][-1]["text"], result
            result = request(sort='[{"property":"amount"}]')
            assert [row["amount"] for row in result["data"]] == [5, 10], result
            result = request(action="action", name="apply", records='["00000000-0000-0000-0000-000000000001"]', parameters="[]")
            assert result["success"] and result["info"]["messages"][0]["text"] == "applied", result
            result = request(action="action", name="missing", records=ids)
            assert not result["success"], result
            result = request(action="action", name="apply", records=ids, parameters='[{"id":"unknown","value":"x"}]')
            assert not result["success"], result
            result = request(action="action", name="noTransaction", records=ids, selection='["00000000-0000-0000-0000-000000000001"]')
            assert not result["success"], result
            result = request(sort='[{"property":"amount"}]')
            assert [row["amount"] for row in result["data"]] == [7, 11], result
            one = '["00000000-0000-0000-0000-000000000001"]'
            result = request(action="action", name="increment", records=one)
            assert result["success"], result
            result = request(action="action", name="increment", records=one, parameters='[{"id":"delta","value":3},{"id":"enabled","value":true},{"id":"message","value":"ready"}]')
            assert result["success"], result
            result = request(action="action", name="increment", records=one, parameters='[{"id":"delta","value":"invalid"}]')
            assert not result["success"], result
            result = request(action="action", name="increment", records=one, parameters='[{"id":"enabled","value":false}]')
            assert not result["success"] and "invalid parameters" in result["info"]["messages"][-1]["text"], result
            result = request(action="action", name="inspect", records=one)
            assert result["success"] and result["info"]["messages"][0]["text"] == "root", result
            result = request(action="action", name="inspect", records=one, query="child")
            assert result["success"] and result["info"]["messages"][0]["text"] == "child", result
            result = request(action="action", name="inspect", records=one, link="childLink", query="missing")
            assert result["success"] and result["info"]["messages"][0]["text"] == "child", result
            result = request(action="action", name="inspect", records=one, query="missing")
            assert not result["success"], result
            result = request(action="report", id="exported", recordId="00000000-0000-0000-0000-000000000001", name="invoice", format="pdf")
            assert result["success"] and result["info"]["files"][0]["name"] == "invoice.pdf", result
            result = request(action="report", id="missing", recordId="00000000-0000-0000-0000-000000000001")
            assert not result["success"], result
            result = request(session="denied", action="report", id="exported", recordId="00000000-0000-0000-0000-000000000001")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("GET", "/request.json?" + urlencode(dict(request="Sample", session="full", server="test", action="content")))
                response = conn.getresponse()
                assert response.status == 200 and response.read() == bytes([0, 255, 65, 0])
            finally:
                conn.close()
            result = request(action="content", empty="true")
            assert result["success"], result
            result = request(action="content", fail="true")
            assert not result["success"] and "content failed" in result["info"]["messages"][-1]["text"], result
            result = request(session="denied", action="content")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"amount":5}')
            assert result["success"] and result["info"]["messages"][-1]["text"] == "job complete", result
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"amount":9,"fail":true}')
            assert result["success"] and "job failed" in result["info"]["messages"][-1]["text"], result
            result = request(request="NonTransactionalJob", action=None, scheduled="true", parameters='{"amount":2,"fail":true}')
            assert result["success"] and "job failed" in result["info"]["messages"][-1]["text"], result
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"missing":1}')
            assert not result["success"], result
            result = request(request="ImpersonateJob", action=None, scheduled="true")
            assert result["success"] and [m["text"] for m in result["info"]["messages"]] == [
                "00000000-0000-0000-0000-000000000004", "00000000-0000-0000-0000-000000000002"], result
            result = request(session="limited", request="ImpersonateJob", action=None, scheduled="true")
            assert result["success"] and "switch access denied" in result["info"]["messages"][-1]["text"], result
            result = request(request="ImpersonateJob", action=None)
            assert result["success"] and result["id"], result
            impersonate_id = result["id"]; impersonate_messages = []
            for _ in range(100):
                result = request(request="ImpersonateJob", action=None, job=impersonate_id)
                impersonate_messages.extend(entry["text"] for entry in result["info"]["messages"])
                if result["done"]:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("impersonating job did not finish")
            assert impersonate_messages == ["00000000-0000-0000-0000-000000000004", "00000000-0000-0000-0000-000000000002"], result
            result = request(request="UpdateJob", action=None, parameters='{"amount":3,"wait":true}')
            assert result["success"] and result["id"], result
            job = result["id"]
            result = request(session="limited", request="UpdateJob", action=None, job=job)
            assert not result["success"] and "job access denied" in result["info"]["messages"][-1]["text"], result
            messages = []
            for _ in range(100):
                result = request(request="UpdateJob", action=None, job=job)
                assert result["success"] and result["isJob"] and result["id"] == job, result
                messages.extend(entry["text"] for entry in result["info"]["messages"])
                if result["done"]:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("background job did not finish")
            assert result["worked"] == 50 and "job complete" in messages, result
            result = request(request="UpdateJob", action=None, job=job)
            assert result["done"] and result["worked"] == 100, result
            result = request(request="UpdateJob", action=None, parameters='{"amount":8,"fail":true}')
            assert result["success"] and result["id"], result
            job = result["id"]; messages = []
            for _ in range(100):
                result = request(request="UpdateJob", action=None, job=job)
                messages.extend(entry["text"] for entry in result["info"]["messages"])
                if result["done"]:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("failing background job did not finish")
            assert any("job failed" in text for text in messages), result
            result = request(sort='[{"property":"amount"}]')
            assert [row["amount"] for row in result["data"]] == [11, 11], result
            new_record = '[{"recordId":"00000000-0000-0000-0000-000000000003","title":"Third","amount":25}]'
            result = request(session="limited", action="create", data=new_record)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="create", data=new_record)
            assert result["success"] and result["data"][0]["title"] == "Third", result
            copy_record = '[{"recordId":"00000000-0000-0000-0000-000000000004","title":"Copied"}]'
            result = request(session="limited", action="copy", recordId="00000000-0000-0000-0000-000000000003", data=copy_record)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="copy", recordId="00000000-0000-0000-0000-000000000003", data=copy_record)
            assert result["success"] and result["data"][0]["title"] == "Copied" and result["data"][0]["amount"] == 25, result
            change = '[{"recordId":"00000000-0000-0000-0000-000000000002","title":"Updated","amount":12}]'
            result = request(session="limited", action="update", data=change)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="update", data=change)
            assert result["success"] and result["data"][0]["title"] == "Updated" and result["data"][0]["amount"] == 12, result
            parts = {"request": "Sample", "session": "full", "server": "test", "action": "update",
                     "fields": '["title","amount"]',
                     "data": '[{"recordId":"00000000-0000-0000-0000-000000000002","blob":0}]'}
            boundary = "z8-upload"
            body = b""
            for key, value in parts.items():
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="data.bin"\r\n'
                     'Content-Type: application/octet-stream\r\n\r\n').encode() + bytes([0, 255, 65, 0]) + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("POST", "/request.json", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
                response = conn.getresponse(); result = json.loads(response.read())
                assert response.status == 200 and result["success"], result
            finally:
                conn.close()
            def attach_file(session, record_id, filename, content, details='{"kind":"document"}', nested=False):
                params = {"request": "Sample", "session": session, "server": "test", "action": "attach",
                          "recordId": record_id, "field": "documents", "fields": '["documents"]', "details": details}
                if nested:
                    params.update(query="nested", field="nested.documents", fields='["nested.documents"]',
                                  values=json.dumps({"recordId": "00000000-0000-0000-0000-000000000001"}))
                marker = "z8-attachment-boundary"
                payload = b""
                for key, value in params.items():
                    payload += (f'--{marker}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
                payload += (f'--{marker}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                            'Content-Type: application/octet-stream\r\n\r\n').encode() + content + b"\r\n"
                payload += f"--{marker}--\r\n".encode()
                client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    client.request("POST", "/request.json", payload, {"Content-Type": f"multipart/form-data; boundary={marker}"})
                    response = client.getresponse(); result = json.loads(response.read())
                    assert response.status == 200
                    return result
                finally:
                    client.close()
            target = "00000000-0000-0000-0000-000000000002"
            result = attach_file("limited", target, "denied.txt", b"no")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = attach_file("field-denied", target, "denied.txt", b"no")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = attach_file("full", target, "invalid.txt", b"no", details='{"kind":1}')
            assert not result["success"] and "invalid attachment detail" in result["info"]["messages"][-1]["text"], result
            result = attach_file("full", "00000000-0000-0000-0000-000000000099", "missing.txt", b"no")
            assert not result["success"], result
            result = attach_file("full", target, "данные.txt", bytes([0, 255, 65]))
            assert result["success"], result
            metadata = json.loads(result["data"][0]["documents"])
            assert len(metadata) == 1 and metadata[0]["name"] == "данные.txt" and metadata[0]["details"]["kind"] == "document", result
            first_id = metadata[0]["id"]
            download_path = "/" + quote(metadata[0]["path"], safe="/")
            def download(path, session, file_id, method="GET"):
                client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    params = {"session": session}
                    if file_id is not None:
                        params["id"] = file_id
                    client.request(method, path + "?&" + urlencode(params) + "&noCache")
                    response = client.getresponse(); body = response.read()
                    return response.status, dict(response.getheaders()), body
                finally:
                    client.close()
            status, headers, content = download(download_path, "full", first_id)
            assert status == 200 and content == bytes([0, 255, 65]), (status, headers, content)
            nested_target = "00000000-0000-0000-0000-000000000088"
            result = attach_file("field-denied", nested_target, "denied.txt", b"no", nested=True)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = attach_file("relation-denied", nested_target, "denied.txt", b"no", nested=True)
            assert not result["success"] and "relation access denied" in result["info"]["messages"][-1]["text"], result
            result = attach_file("full", nested_target, "nested.txt", b"nested", nested=True)
            assert result["success"], result
            nested_file = json.loads(result["data"][0]["nested.documents"])[0]
            assert download("/" + quote(nested_file["path"], safe="/"), "full", nested_file["id"])[2] == b"nested"
            result = request(action="detach", query="nested", field="nested.documents", fields='["nested.documents"]',
                             recordId=nested_target, data=json.dumps([nested_file["id"]]),
                             values=json.dumps({"recordId": "00000000-0000-0000-0000-000000000001"}))
            assert result["success"] and json.loads(result["data"][0]["nested.documents"]) == [], result
            assert headers["Content-Type"] == "application/octet-stream" and "filename*=UTF-8''" + quote("данные.txt") in headers["Content-Disposition"], headers
            assert download(download_path, "unknown", first_id)[0] == 401
            status, headers, content = download(download_path, "full", "00000000-0000-0000-0000-000000000099")
            assert status == 404 and json.loads(content)["info"]["messages"][-1]["text"] == "File not found"
            assert download(download_path + "-other", "full", first_id)[0] == 404
            assert download(download_path, "full", first_id, "POST")[0] == 405
            result = request(action="detach", field="documents", fields='["documents"]', recordId=target,
                             data=json.dumps(["00000000-0000-0000-0000-000000000099"]))
            assert not result["success"] and "does not belong" in result["info"]["messages"][-1]["text"], result
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(attach_file, "full", target, f"parallel-{i}.txt", bytes([i])) for i in range(2)]
                concurrent = [future.result() for future in futures]
            assert all(item["success"] for item in concurrent), concurrent
            file_ids = {first_id}
            archive_files = {first_id: metadata[0]}
            for item in concurrent:
                for file in json.loads(item["data"][0]["documents"]):
                    file_ids.add(file["id"]); archive_files[file["id"]] = file
            assert len(file_ids) == 3, concurrent
            file_list = list(archive_files.values())
            result = request(session="denied", action="archive", archive=json.dumps(file_list))
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="archive", archive=json.dumps(file_list + [file_list[0]]))
            assert not result["success"] and "duplicate archive filename" in result["info"]["messages"][-1]["text"], result
            result = request(action="archive", archive=json.dumps(file_list + [{"id": "00000000-0000-0000-0000-000000000099"}]))
            assert not result["success"], result
            result = request(action="archive", archive=json.dumps(file_list))
            assert result["success"] and result["source"].startswith("storage/z8-archive/") and result["server"] == "test", result
            archive_path = "/" + quote(result["source"], safe="/")
            assert download(archive_path, "limited", None)[0] == 404
            assert download(archive_path, "full2", None)[0] == 404
            assert download(archive_path, "unknown", None)[0] == 401
            status, headers, content = download(archive_path, "full", None)
            assert status == 200 and "filename*=UTF-8''archive.zip" in headers["Content-Disposition"], (status, headers)
            with zipfile.ZipFile(io.BytesIO(content)) as zipped:
                assert set(zipped.namelist()) == {"данные.txt", "parallel-0.txt", "parallel-1.txt"}
                assert zipped.read("данные.txt") == bytes([0, 255, 65])
                assert zipped.read("parallel-0.txt") == b"\x00" and zipped.read("parallel-1.txt") == b"\x01"
            result = request(action="detach", field="documents", fields='["documents"]', recordId=target,
                             data=json.dumps(list(file_ids)))
            assert result["success"] and json.loads(result["data"][0]["documents"]) == [], result
            result = attach_file("full", "", "new.txt", b"new")
            assert result["success"], result
            new_target = result["data"][0]["recordId"]
            new_file = json.loads(result["data"][0]["documents"])[0]["id"]
            result = request(action="detach", field="documents", fields='["documents"]', recordId=new_target, data=json.dumps([new_file]))
            assert result["success"], result
            result = request(action="destroy", data=json.dumps([new_target]))
            assert result["success"], result
            data = '["00000000-0000-0000-0000-000000000001","00000000-0000-0000-0000-000000000003","00000000-0000-0000-0000-000000000004"]'
            result = request(session="limited", action="destroy", data=data)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="destroy", data=data)
            assert result["success"], result
            result = request()
            assert len(result["data"]) == 1 and result["data"][0]["title"] == "Updated", result
        finally:
            if process.poll() is None:
                try:
                    process.stdin.write("\n")
                    process.stdin.flush()
                except OSError:
                    pass
            process.wait(timeout=15)
            stderr = process.stderr.read()
            if process.returncode:
                raise RuntimeError("Server exited with code " + str(process.returncode) + ": " + stderr)
print("CivetWeb table reads and per-request PostgreSQL privileges verified")
