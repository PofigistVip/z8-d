"""Exercise a POI report that preserves an XLSX template without ranges."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from runtime_support import import_args, runtime_library, ROOT

compiler = ROOT / ("z8d.exe" if os.name == "nt" else "z8d")
language = ROOT / "vendor/z8/org.zenframework.z8.lang/src/bl"
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "StaticReportProbe.bl").write_text('''
import org.zenframework.z8.base.form.report.Report;
public class StaticReportProbe {
    public static file run(string templateName, string outputName) {
        Report report; report.engine = Report.POI; report.template = templateName; report.name = outputName;
        return report.run(guid.Null);
    }
    public static file hidden(string templateName) {
        Report report; report.engine = Report.POI; report.template = templateName;
        string[] columns = {"B", "D", "G"}; report.hiddenColumns.add(0, columns);
        return report.run(guid.Null);
    }
    public static file secondSheet() {
        Report report; report.engine = Report.POI; report.template = "multiple";
        string[] columns = {"A"}; report.hiddenColumns.add(1, columns);
        return report.run(guid.Null);
    }
    public static file invalidSheet() {
        Report report; report.engine = Report.POI; report.template = "sample";
        string[] columns = {"A"}; report.hiddenColumns.add(4, columns);
        return report.run(guid.Null);
    }
    public static file invalidColumn() {
        Report report; report.engine = Report.POI; report.template = "sample";
        string[] columns = {""}; report.hiddenColumns.add(0, columns);
        return report.run(guid.Null);
    }
}
''', encoding="utf-8")
    application, working = temp / "application", temp / "working"
    (application / "reports").mkdir(parents=True)
    working.mkdir()
    workbook = application / "reports/sample.xlsx"
    entries = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Example</t></is></c></row></sheetData></worksheet>',
    }
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    original_sheet = entries["xl/worksheets/sheet1.xml"]
    entries["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>",
        '<cols><col min="1" max="4" width="12" customWidth="1"/><col min="8" max="8" hidden="1" width="9"/></cols><sheetData>')
    with zipfile.ZipFile(application / "reports/styled.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    overlapping = dict(entries)
    overlapping["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>",
        '<cols><col min="3" max="6" width="20" customWidth="1" outlineLevel="2"/><col min="1" max="4" width="12" customWidth="1" outlineLevel="1"/></cols><cols><col min="5" max="8" hidden="1"/></cols><sheetData>')
    with zipfile.ZipFile(application / "reports/overlap.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in overlapping.items():
            archive.writestr(name, content)
    multiple = dict(entries)
    multiple["xl/workbook.xml"] = multiple["xl/workbook.xml"].replace('</sheets>', '<sheet name="Second" sheetId="2" r:id="rId2"/></sheets>')
    multiple["xl/_rels/workbook.xml.rels"] = multiple["xl/_rels/workbook.xml.rels"].replace('</Relationships>',
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
    multiple["[Content_Types].xml"] = multiple["[Content_Types].xml"].replace('</Types>',
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    second_xml = '''<?xml version="1.0" encoding="UTF-16"?><x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:cols/><x:sheetData><x:row r="1"><x:c r="A1" t="inlineStr"><x:is><x:t>😀</x:t></x:is></x:c></x:row></x:sheetData></x:worksheet>'''
    multiple["xl/worksheets/sheet2.xml"] = b"\xff\xfe" + second_xml.encode("utf-16-le")
    with zipfile.ZipFile(application / "reports/multiple.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in multiple.items():
            archive.writestr(name, content)
    (application / "reports/broken.xlsx").write_text("not a workbook", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "report.d"
    harness.write_text('''import z8.runtime;
import z8gen.StaticReportProbe;
import std.file : read, copy;
import std.path : buildPath;
class Database : IZ8DatabaseConnection {
    int begins, rollbacks;
    void beginTransaction() { ++begins; }
    void rollback() { ++rollbacks; }
    void commit() { assert(false); }
    void execute(wstring sql) { assert(false); }
    void call(wstring name, Z8Array!Z8Primary values) { assert(false); }
    void flush() { assert(false); }
    IZ8QueryExecutor queryExecutor(Z8Object query) { return null; }
}
void main(string[] args) {
    z8_resources_set_application_root(args[1]); z8_file_set_roots(args[2]);
    auto database = new Database(); z8_connection_set_current(database);
    alias P = Z8_StaticReportProbe;
    auto first = P.m_run("sample"w, "hello:report"w);
    auto second = P.m_run("sample.xlsx"w, null);
    assert(first.name == "hello-report.xlsx"w && second.name == "sample.xlsx"w && first.path != second.path);
    assert(read(z8_file_resolve_path(first)) == read(buildPath(args[1], "reports", "sample.xlsx")));
    assert(database.begins == 2 && database.rollbacks == 2);
    bool invalid; try { P.m_run("broken"w, null); } catch (Exception) { invalid = true; }
    assert(invalid && database.begins == 3 && database.rollbacks == 3);
    auto hidden = P.m_hidden("sample"w), styled = P.m_hidden("styled"w);
    copy(z8_file_resolve_path(hidden), buildPath(args[2], "hidden.xlsx"));
    copy(z8_file_resolve_path(styled), buildPath(args[2], "styled.xlsx"));
    auto secondSheet = P.m_secondSheet();
    copy(z8_file_resolve_path(secondSheet), buildPath(args[2], "multiple.xlsx"));
    auto overlap = P.m_hidden("overlap"w);
    copy(z8_file_resolve_path(overlap), buildPath(args[2], "overlap.xlsx"));
    assert(database.begins == 7 && database.rollbacks == 7);
    bool badSheet; try { P.m_invalidSheet(); } catch (Exception) { badSheet = true; } assert(badSheet);
    bool badColumn; try { P.m_invalidColumn(); } catch (Exception) { badColumn = true; } assert(badColumn);
    assert(database.begins == 9 && database.rollbacks == 9);
}
''', encoding="utf-8")
    executable = temp / ("report.exe" if os.name == "nt" else "report")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(application), str(working)], cwd=temp, check=True)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    def columns(path):
        with zipfile.ZipFile(path) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            assert sheet.find("x:sheetData/x:row/x:c/x:is/x:t", namespace).text == "Example"
            return [item.attrib for item in sheet.findall("x:cols/x:col", namespace)]
    assert columns(working / "hidden.xlsx") == [
        {"min": "2", "max": "2", "hidden": "1"}, {"min": "4", "max": "4", "hidden": "1"},
        {"min": "7", "max": "7", "hidden": "1"}]
    assert columns(working / "styled.xlsx") == [
        {"min": "1", "max": "1", "width": "12", "customWidth": "1"},
        {"min": "2", "max": "2", "width": "12", "customWidth": "1", "hidden": "1"},
        {"min": "3", "max": "3", "width": "12", "customWidth": "1"},
        {"min": "4", "max": "4", "width": "12", "customWidth": "1", "hidden": "1"},
        {"min": "7", "max": "7", "hidden": "1"},
        {"min": "8", "max": "8", "hidden": "1", "width": "9"}]
    with zipfile.ZipFile(working / "multiple.xlsx") as archive:
        second = archive.read("xl/worksheets/sheet2.xml")
        assert second.startswith(b"\xff\xfe")
        sheet = ET.fromstring(second)
        assert sheet.find("x:sheetData/x:row/x:c/x:is/x:t", namespace).text == "😀"
        assert [item.attrib for item in sheet.findall("x:cols/x:col", namespace)] == [{"min": "1", "max": "1", "hidden": "1"}]
    # Apache POI is optional for ordinary D builds; when available, compare
    # visibility and widths with the version used by the original server.
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
    jars = sorted(p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar")
                  if not p.name.endswith("-sources.jar"))
    if any("poi-3.16" in p.name for p in jars) and shutil.which("javac") and shutil.which("java"):
        oracle = temp / "PoiHiddenOracle.java"
        oracle.write_text('''import java.io.FileInputStream;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
class PoiHiddenOracle {
  public static void main(String[] args) throws Exception {
    try (XSSFWorkbook original = new XSSFWorkbook(new FileInputStream(args[0]));
         XSSFWorkbook actual = new XSSFWorkbook(new FileInputStream(args[1]))) {
      Sheet expected = original.getSheetAt(0), result = actual.getSheetAt(0);
      for (int column : new int[]{1, 3, 6}) expected.setColumnHidden(column, true);
      for (int column = 0; column < 10; column++)
        if (expected.isColumnHidden(column) != result.isColumnHidden(column) ||
            expected.getColumnWidth(column) != result.getColumnWidth(column) ||
            expected.getColumnOutlineLevel(column) != result.getColumnOutlineLevel(column))
          throw new AssertionError("Column " + column + " differs");
      if (!"Example".equals(result.getRow(0).getCell(0).getStringCellValue()))
        throw new AssertionError("Cell was changed");
    }
  }
}''', encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(oracle)], cwd=temp, check=True)
        for source_path, result_path in ((workbook, working / "hidden.xlsx"),
                                         (application / "reports/styled.xlsx", working / "styled.xlsx"),
                                         (application / "reports/overlap.xlsx", working / "overlap.xlsx")):
            subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "PoiHiddenOracle",
                            str(source_path), str(result_path)], cwd=temp, check=True)
print("POI static report template, naming and transaction verified")
