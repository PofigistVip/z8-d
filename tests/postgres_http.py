"""Exercise authorized BL table reads through CivetWeb and PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

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
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.Link;
public class Sample extends Table {
    [name "Title"] public StringField title;
    [name "Amount"] public IntField amount;
    [name "Blob"] public BinaryField blob;
    Table child; [name "ChildLink"] Link childLink = child;
    ApplyAction apply; NoTransactionAction noTransaction; IncrementAction increment; ContextAction inspect;
    actions = {apply, noTransaction, increment, inspect};
    CustomReport exported; reports = {exported};
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
__gshared string databaseInfo;

class Authority : IZ8HttpAuthority {
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring id, wstring server) {
        if (server != "test"w || (id != "full"w && id != "limited"w && id != "denied"w)) return null;
        auto user = new Z8UserData(); user.id = z8_guid_create(id == "limited"w ? 3 : 1);
        user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
        if (id == "limited"w) {
            user.privileges.setFieldAccess(z8_guid_create_name("Sample.Title"w), Z8Access.init);
            user.privileges.setTableAccess(z8_guid_create_name("Sample"w), Z8Access(true, false, false, false, false, true));
        }
        if (id == "denied"w) user.privileges.setRequestAccess(z8_guid_create_name("Sample"w), Z8Access.init);
        return new Z8ApplicationSession(id, user, user);
    }
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password) { return null; }
}
void main(string[] args) {
    databaseInfo = args[1];
    auto setup = new Z8PostgresConnection(databaseInfo);
    setup.execute(`CREATE TABLE "Sample" ("RecordId" uuid PRIMARY KEY, "Title" text, "Amount" bigint, "Blob" bytea, "ChildLink" uuid, "Lock" bigint DEFAULT 0, "CreatedAt" bigint, "CreatedBy" uuid, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
    setup.execute(`INSERT INTO "Sample" ("RecordId", "Title", "Amount") VALUES ('00000000-0000-0000-0000-000000000001', 'First', 5), ('00000000-0000-0000-0000-000000000002', 'Second', 10)`);
    setup.close();
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto connection = new Z8PostgresConnection(databaseInfo);
        scope(exit) connection.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(connection, "public"w));
        scope(exit) z8_connection_set_current(previous);
        z8_application_dispatch_request();
    }, 2048, Z8ResponseMode.application, "test"w, new Authority(), "Denied"w, null, "/request.json");
    scope(exit) server.stop();
    writeln(server.port()); stdout.flush(); readln(); server.stop();
    auto verify = new Z8PostgresConnection(databaseInfo);
    auto row = verify.execute(`SELECT encode("Blob", 'hex') FROM "Sample" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "00ff4100");
    row = verify.execute(`SELECT "CreatedAt" FROM "Sample" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "10"); verify.close();
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
            def request(session="full", **params):
                query = dict(request="Sample", action="read", session=session, server="test",
                             fields='["title","amount"]')
                query.update(params)
                if query["action"] is None:
                    query.pop("action")
                if query.get("action") in ("destroy", "action", "report"):
                    query.pop("fields")
                if query["request"] in ("UpdateJob", "NonTransactionalJob"):
                    query.pop("fields", None)
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    conn.request("GET", "/request.json?" + urlencode(query))
                    response = conn.getresponse()
                    assert response.status == 200
                    return json.loads(response.read())
                finally:
                    conn.close()
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
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"amount":5}')
            assert result["success"] and result["info"]["messages"][-1]["text"] == "job complete", result
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"amount":9,"fail":true}')
            assert result["success"] and "job failed" in result["info"]["messages"][-1]["text"], result
            result = request(request="NonTransactionalJob", action=None, scheduled="true", parameters='{"amount":2,"fail":true}')
            assert result["success"] and "job failed" in result["info"]["messages"][-1]["text"], result
            result = request(request="UpdateJob", action=None, scheduled="true", parameters='{"missing":1}')
            assert not result["success"], result
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
