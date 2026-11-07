"""Generate the system tables ODT through a real PostgreSQL connection.

Usage: python tests/postgres_tables_report.py <original-z8-root> [postgres-bin]
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_tables_report.py <original-z8-root> [postgres-bin]")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
template = original / "org.zenframework.z8.server/WEB-INF/reports/system/Tables.odt"
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if not language.is_dir() or not template.is_file():
    raise SystemExit("Original BL sources or Tables.odt are unavailable")

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Probe.bl").write_text("public class Probe {}", encoding="utf-8")
    (source / "StoredReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
public class StoredReport extends Report {
    public static file stored;
    virtual protected file execute(guid recordId) { return stored; }
}''', encoding="utf-8")
    (source / "StoredView.bl").write_text('''import org.zenframework.z8.base.query.Query;
[request] public class StoredView extends Query { StoredReport saved; reports = {saved}; }
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated), "--dependency", str(language),
                    "--dependency", str(root / "platform/bl")], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8gen.StoredReport;
import std.file : copy, mkdirRecurse, remove, write;
import std.path : buildPath;
void main(string[] args) {
    z8_file_set_roots(args[2]);
    auto connection = new Z8PostgresConnection(args[1]);
    scope(exit) connection.close();
    connection.execute(`CREATE TEMP TABLE "SystemTables" ("RecordId" uuid PRIMARY KEY, "Name" text, "Description" bytea, "Class" text)`);
    connection.execute(`CREATE TEMP TABLE "SystemFields" ("RecordId" uuid PRIMARY KEY, "Table" uuid, "Name" text, "Type" text, "Description" bytea)`);
    connection.execute(`INSERT INTO "SystemTables" VALUES
      ('00000000-0000-0000-0000-000000000001','Table & <one>',convert_to('Описание','UTF8'),'example.Table'),
      ('00000000-0000-0000-0000-000000000002','Empty',convert_to('No fields','UTF8'),'example.Empty')`);
    connection.execute(`INSERT INTO "SystemFields" VALUES
      ('00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000001','First','String',convert_to('first & value','UTF8')),
      ('00000000-0000-0000-0000-000000000012','00000000-0000-0000-0000-000000000001','Second','Guid',convert_to('second','UTF8'))`);
    auto backend = new Z8PostgresDatabase(connection, "pg_temp"w);
    auto previous = z8_connection_set_current(backend); scope(exit) z8_connection_set_current(previous);
    auto view = z8_object_new_instance("org.zenframework.z8.server.base.table.system.view.TablesView"w);
    auto reports = z8_query_array(view, "reports"w); assert(reports.length == 1);
    auto report = reports[0];
    auto output = z8_native_call!Z8File("org.zenframework.z8.server.base.form.report.Report.m_run"w, report, cast(Z8Guid)null);
    assert(z8_file_exists(output)); copy(z8_file_resolve_path(output), args[3]);
    auto custom = buildPath(args[2], "reports", "system", "Tables.odt");
    mkdirRecurse(buildPath(args[2], "reports", "system"));
    write(custom, "not an ODT");
    bool rejected; try { z8_native_call!Z8File("org.zenframework.z8.server.base.form.report.Report.m_run"w, report, cast(Z8Guid)null); }
    catch (Exception) { rejected = true; } assert(rejected);
    remove(custom); copy(args[4], custom);
    auto firstOutput = output;
    output = z8_native_call!Z8File("org.zenframework.z8.server.base.form.report.Report.m_run"w, report, cast(Z8Guid)null);
    assert(z8_file_exists(output) && z8_file_resolve_path(output) != z8_file_resolve_path(firstOutput));
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    auto monitor = new Z8RequestMonitor(); request.monitor = monitor;
    enum viewName = "org.zenframework.z8.server.base.table.system.view.TablesView"w;
    request.parameters.z8_add("request"w, viewName); request.parameters.z8_add("action"w, "report"w);
    request.parameters.z8_add("id"w, report.z8_id());
    auto previousRequest = z8_application_set_request(request); scope(exit) z8_application_set_request(previousRequest);
    z8_application_start_response(request, viewName);
    z8_application_dispatch_query_report(viewName);
    z8_application_finish_response(request, monitor);
    assert(monitor.files().length == 1);
    auto published = monitor.files()[0]; assert(published.id is null);
    auto download = new Z8ApplicationRequest(); download.session = request.session;
    z8_application_set_request(download);
    z8_application_dispatch_file_download("/"w ~ published.path);
    auto data = z8_application_response_binary(download);
    assert(z8_binary_snapshot(data, 64 * 1024 * 1024).length > 100);
    z8_binary_close(data);
    published.id = z8_guid_zero(); // A returned archive must not expose an attachment ID.
    Z8_StoredReport.f_stored = published;
    auto storedView = z8_object_new_instance("StoredView"w);
    auto storedRequest = new Z8ApplicationRequest(); storedRequest.session = request.session;
    auto storedMonitor = new Z8RequestMonitor(); storedRequest.monitor = storedMonitor;
    storedRequest.parameters.z8_add("action"w, "report"w);
    storedRequest.parameters.z8_add("id"w, z8_query_array(storedView, "reports"w)[0].z8_id());
    z8_application_set_request(storedRequest); z8_application_start_response(storedRequest, "StoredView"w);
    z8_application_dispatch_query_report("StoredView"w);
    z8_application_finish_response(storedRequest, storedMonitor);
    assert(storedMonitor.files().length == 1 && storedMonitor.files()[0].id is null);
    z8_application_set_request(download);
    z8_application_dispatch_file_download("/"w ~ storedMonitor.files()[0].path);
    data = z8_application_response_binary(download);
    assert(z8_binary_snapshot(data, 64 * 1024 * 1024).length > 100);
    z8_binary_close(data);
    download.session = new Z8ApplicationSession("other"w, user, user);
    bool inaccessible; try { z8_application_dispatch_file_download("/"w ~ published.path); }
    catch (Exception) { inaccessible = true; } assert(inaccessible);
}
''', encoding="utf-8")
    executable = temp / ("tables-report.exe" if os.name == "nt" else "tables-report")
    args = ["-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
            *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(harness), str(runtime)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    args += ["-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    output = temp / "result.odt"
    with temporary_postgres(bin_dir) as (connection, env):
        subprocess.run([str(executable), connection, str(temp), str(output), str(template)], cwd=temp, env=env, check=True)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        root_xml = ET.fromstring(archive.read("content.xml"))
        paragraphs = ["".join(item.itertext()) for item in root_xml.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p")]
        assert any("Table & <one>" in text for text in paragraphs), paragraphs
        for value in ("example.Table", "Описание", "First", "String", "first & value", "Second", "Guid", "Empty", "example.Empty"):
            assert any(value in text for text in paragraphs), (value, paragraphs)
print("System tables report generated from PostgreSQL and the bundled or configured ODT template")
