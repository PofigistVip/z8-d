"""Run query-backed POI reports against PostgreSQL and OpenXLSX."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (3, 4):
    raise SystemExit("Usage: python tests/postgres_poi_report.py <original-z8-root> <openxlsx-bin> [postgres-bin]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
bridge = Path(sys.argv[2]).resolve()
bin_dir = postgres_bin(sys.argv[3] if len(sys.argv) == 4 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ReportRows.bl").write_text('''import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.IntField;
public class ReportRows extends Table {
    [name "Amount"] public IntField amount;
    sortFields = {amount};
    public void start() { Field[] fields = {amount}; read(fields); }
    public bool advance() { return next(); }
    public int value() { return amount.get(); }
}''', encoding="utf-8")
    (source / "QueryReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class QueryReport extends Report {
    engine = Report.POI; template = "query";
    public ReportRows rows; objects = {rows};
    [address "A1:B1"] [boundaries "A1:B1"] Range region;
    region.source = rows; ranges = {region};
    public file generate() { return run(guid.Null); }
}''', encoding="utf-8")
    app, work = temp / "application", temp / "working"
    (app / "reports").mkdir(parents=True)
    work.mkdir()
    entries = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>',
        "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>${rows.amount}</t></si><si><t>${rows.amount + 1}</t></si></sst>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row></sheetData></worksheet>',
    }
    with zipfile.ZipFile(app / "reports/query.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.schema;
import z8.database.query;
import z8.xlsx.poi : z8_openxlsx_configure;
import z8gen.QueryReport;
import z8gen.ReportRows;
import std.file : copy;
void main(string[] args) {
    z8_openxlsx_configure(); z8_resources_set_application_root(args[2]); z8_file_set_roots(args[3]);
    auto db = new Z8PostgresConnection(args[1]); scope(exit) db.close();
    z8_connection_set_current(new Z8PostgresDatabase(db, "report_test"w));
    db.execute("CREATE SCHEMA report_test");
    auto report = z8_new!Z8_QueryReport(); report.z8_ensure(); auto table = report.f_rows; table.z8_ensure();
    auto prototype = z8_new!Z8_ReportRows(); z8_nonnull(prototype);
    z8_postgres_create_tables(db, "report_test"w, [prototype]);
    db.execute(`INSERT INTO "report_test"."ReportRows" ("RecordId", "Amount") VALUES ('00000000-0000-0000-0000-000000000011', 42)`);
    z8_query_set_executor(table, new Z8PostgresQueryExecutor(db, "report_test"w, "ReportRows"w));
    auto request = new Z8ApplicationRequest(); z8_application_set_request(request);
    table.m_start(); assert(z8_optional_require(table.m_advance()) && z8_optional_require(table.m_value()) == 42);
    auto result = report.m_generate(); copy(z8_file_resolve_path(result), args[4]);
    assert(z8_optional_require(table.m_value()) == 42);
    db.execute(`INSERT INTO "report_test"."ReportRows" ("RecordId", "Amount") VALUES ('00000000-0000-0000-0000-000000000012', 70)`);
    auto expanded = report.m_generate(); copy(z8_file_resolve_path(expanded), args[5]);
    assert(z8_optional_require(table.m_value()) == 42);
}''', encoding="utf-8")
    executable = temp / ("report.exe" if os.name == "nt" else "report")
    args = ["-I" + str(generated), "-I" + str(root / "postgres/source"), "-I" + str(root / "xlsx/source"),
            *import_args(), *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(root / "xlsx/source/z8/xlsx/openxlsx.d"), str(root / "xlsx/source/z8/xlsx/poi.d"),
            str(harness), str(runtime), "-of=" + str(executable)]
    if os.name == "nt":
        args += [str(bin_dir.parent / "lib/libpq.lib"), str(bridge / "z8_openxlsx.lib")]
        shutil.copy2(bridge / "z8_openxlsx.dll", temp)
    else:
        args += ["-L-lpq", "-L-L" + str(bridge), "-L-lz8_openxlsx"]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    output = temp / "result.xlsx"
    expanded_output = temp / "expanded.xlsx"
    with temporary_postgres(bin_dir) as (connection, environment):
        if os.name != "nt":
            environment["LD_LIBRARY_PATH"] = str(bridge) + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        subprocess.run([str(executable), connection, str(app), str(work), str(output), str(expanded_output)], env=environment, cwd=temp, check=True)
    for path, expected in ((output, [42, 43]), (expanded_output, [42, 43, 70, 71])):
        with zipfile.ZipFile(path) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            assert [float(c.find("x:v", ns).text) for c in sheet.findall("x:sheetData/x:row/x:c", ns)] == expected
print("PostgreSQL query report values and cursor restoration verified")
