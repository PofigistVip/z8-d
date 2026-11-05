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
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
public class Sample extends Table {
    [name "Title"] public StringField title;
    [name "Amount"] public IntField amount;
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
        auto user = new Z8UserData(); user.id = z8_guid_create(1);
        user.privileges = new Z8Privileges(Z8Access(true, true, false, false, true, true));
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
    setup.execute(`CREATE TABLE "Sample" ("RecordId" uuid PRIMARY KEY, "Title" text, "Amount" bigint, "Lock" bigint DEFAULT 0, "ModifiedAt" bigint, "ModifiedBy" uuid)`);
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
    writeln(server.port()); stdout.flush(); readln();
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
                if query["action"] == "destroy":
                    query.pop("fields")
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
            result = request(session="limited", filter='{"property":"title","value":"First"}')
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(session="denied")
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(count="true", filter='{"property":"amount","operator":"gt","value":"5"}')
            assert result["success"] and result["total"] == 1, result
            with ThreadPoolExecutor(max_workers=8) as workers:
                results = list(workers.map(lambda i: request(session="limited" if i % 2 else "full"), range(16)))
            assert all(result["success"] and len(result["data"]) == 2 for result in results)
            assert all(("title" not in result["data"][0]) == (i % 2 == 1) for i, result in enumerate(results))
            change = '[{"recordId":"00000000-0000-0000-0000-000000000002","title":"Updated","amount":12}]'
            result = request(session="limited", action="update", data=change)
            assert not result["success"] and "access denied" in result["info"]["messages"][-1]["text"], result
            result = request(action="update", data=change)
            assert result["success"] and result["data"][0]["title"] == "Updated" and result["data"][0]["amount"] == 12, result
            data = '["00000000-0000-0000-0000-000000000001"]'
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
