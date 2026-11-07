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
import org.zenframework.z8.base.form.report.Range;
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
    public static file ordered() {
        Report report; report.engine = Report.POI; report.template = "order";
        string[] columns = {"Q", "B", "R", "D"}; report.hiddenColumns.add(0, columns);
        return report.run(guid.Null);
    }
    public static file simpleRange() { SimpleRangeReport report; return report.run(guid.Null); }
    public static file invalidRange() { InvalidRangeReport report; return report.run(guid.Null); }
    public static file expressionRange() { ExpressionRangeReport report; return report.run(guid.Null); }
    public static file constantRange() { ConstantRangeReport report; return report.run(guid.Null); }
    public static file constantComment() { ConstantCommentRangeReport report; return report.run(guid.Null); }
    public static file parametersRange() { ParametersRangeReport report; return report.run(guid.Null); }
    public static file mapOperationRange() { MapOperationRangeReport report; return report.run(guid.Null); }
    public static file mixedRange() { MixedRangeReport report; return report.run(guid.Null); }
    public static file unknownMixedRange() { UnknownMixedRangeReport report; return report.run(guid.Null); }
    public static file plainSymbolsRange() { PlainSymbolsRangeReport report; return report.run(guid.Null); }
    public static file doubleQuotedRange() { DoubleQuotedRangeReport report; return report.run(guid.Null); }
    public static file implicitRange() { ImplicitRangeReport report; return report.run(guid.Null); }
    public static file invalidImplicitRange() { InvalidImplicitRangeReport report; return report.run(guid.Null); }
    public static file mergedRange() { MergedRangeReport report; return report.run(guid.Null); }
    public static file renamedRange() { RenamedRangeReport report; return report.run(guid.Null); }
    public static file commentRename() { CommentRenameReport report; return report.run(guid.Null); }
    public static file invalidRename() { InvalidRenameReport report; return report.run(guid.Null); }
    public static file formulaRename() { FormulaRenameReport report; return report.run(guid.Null); }
    public static file duplicateRename() { DuplicateRenameReport report; return report.run(guid.Null); }
    public static file longRename() { LongRenameReport report; return report.run(guid.Null); }
}
''', encoding="utf-8")
    for name, template, address, boundaries in (
            ("SimpleRangeReport", "sample", "$A$1:A1", "A1:B2"),
            ("InvalidRangeReport", "sample", "A1:B2", "A1"),
            ("ExpressionRangeReport", "expression", "A1", "A1"),
            ("ConstantRangeReport", "constant", "A1:G1", "A1:G1"),
            ("ConstantCommentRangeReport", "constant-comment", "A1:G1", "A1:G1"),
            ("ParametersRangeReport", "parameters", "A1:E1", "A1:E1"),
            ("MapOperationRangeReport", "map-operation", "A1", "A1"),
            ("MixedRangeReport", "mixed", "A1", "A1"),
            ("UnknownMixedRangeReport", "unknown-mixed", "A1", "A1"),
            ("PlainSymbolsRangeReport", "plain-symbols", "A1", "A1"),
            ("DoubleQuotedRangeReport", "double-quoted", "A1", "A1")):
        (source / (name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    [address "%s"] [boundaries "%s"] Range region;
    ranges = {region};
}''' % (name, template, address, boundaries), encoding="utf-8")
    for name, template, address in (("ImplicitRangeReport", "sample", "B1"),
                                    ("InvalidImplicitRangeReport", "sample", "C1"),
                                    ("MergedRangeReport", "merged", "A1")):
        (source / (name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    [address "%s"] Range region;
    ranges = {region};
}''' % (name, template, address), encoding="utf-8")
    for name, template, sheet_name in (("RenamedRangeReport", "sample", "Отчёт 😀"),
                                       ("CommentRenameReport", "comment", "Comment renamed"),
                                       ("InvalidRenameReport", "sample", "bad:name"),
                                       ("FormulaRenameReport", "formula", "Renamed"),
                                       ("DuplicateRenameReport", "multiple", "second"),
                                       ("LongRenameReport", "sample", "abcdefghijklmnopqrstuvwxyz123456789")):
        (source / (name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    [address "A1"] [boundaries "A1"] [sheetName "%s"] Range region;
    ranges = {region};
}''' % (name, template, sheet_name), encoding="utf-8")
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
    comment_book = application / "reports/comment.xlsx"
    shutil.copy2(workbook, comment_book)
    with zipfile.ZipFile(comment_book, "a") as archive:
        archive.comment = b"preserve ZIP comment"
    utf16_book = application / "reports/utf16-metadata.xlsx"
    with zipfile.ZipFile(utf16_book, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            if name == "xl/workbook.xml":
                content = b"\xff\xfe" + ('<?xml version="1.0" encoding="UTF-16"?>' + content).encode("utf-16-le")
            archive.writestr(name, content)
    original_sheet = entries["xl/worksheets/sheet1.xml"]
    entries["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>",
        '<cols><col min="1" max="4" width="12" customWidth="1"/><col min="8" max="8" hidden="1" width="9"/></cols><sheetData>')
    with zipfile.ZipFile(application / "reports/styled.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    overlapping = dict(entries)
    overlapping["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>",
        '<cols><col min="3" max="6" width="20" customWidth="1" outlineLevel="2" collapsed="0"/><col min="1" max="4" width="12" customWidth="1" outlineLevel="1"/></cols><cols xmlns:c="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><c:col min="5" max="8" hidden="1"/></cols><sheetData>')
    with zipfile.ZipFile(application / "reports/overlap.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in overlapping.items():
            archive.writestr(name, content)
    cases = [
        '<col min="1" max="9" width="15"/><col min="3" max="5" width="24" hidden="1"/>',
        '<col min="1" max="4" width="10"/><col min="1" max="4" hidden="1"/>',
        '<col min="2" max="3" width="10"/><col min="6" max="7" width="12"/><col min="1" max="8" outlineLevel="2"/>',
        '<col min="2" max="4" width="10" hidden="1"/><col min="3" max="6" hidden="0" width="11"/><col min="1" max="8" width="14"/>',
    ]
    for number, column_xml in enumerate(cases):
        case = dict(entries)
        case["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>", "<cols>" + column_xml + "</cols><sheetData>")
        with zipfile.ZipFile(application / ("reports/case" + str(number) + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in case.items():
                archive.writestr(name, content)
    ordered = dict(entries)
    ordered["xl/worksheets/sheet1.xml"] = original_sheet.replace("<sheetData>",
        '<cols><col min="2" max="8" width="10"/><col min="15" max="20" width="12"/><col min="1" max="22" outlineLevel="2"/></cols><sheetData>')
    with zipfile.ZipFile(application / "reports/order.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in ordered.items():
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
    expression = dict(entries)
    expression["xl/worksheets/sheet1.xml"] = original_sheet.replace("Example", "${value}")
    with zipfile.ZipFile(application / "reports/expression.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in expression.items():
            archive.writestr(name, content)
    for name, expression_text in (("mixed", "prefix ${1+2}"), ("unknown-mixed", "prefix ${value}"),
                                  ("plain-symbols", "cost $5 {literal}"), ("double-quoted", '${"text"}'),
                                  ("map-operation", "${1 == parameters}")):
        fixture = dict(entries)
        fixture["xl/worksheets/sheet1.xml"] = original_sheet.replace("Example", expression_text)
        with zipfile.ZipFile(application / ("reports/" + name + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in fixture.items():
                archive.writestr(entry_name, content)
    constants = dict(entries)
    constants["[Content_Types].xml"] = constants["[Content_Types].xml"].replace(
        "</Types>", '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
    constants["xl/_rels/workbook.xml.rels"] = constants["xl/_rels/workbook.xml.rels"].replace(
        "</Relationships>", '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
    constants["xl/sharedStrings.xml"] = '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1"><si><t>Hello ${\'literal\'} / ${1+2} / ${1.25} / ${true}</t></si></sst>'
    constants["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="inlineStr"><is><t>${1+2}</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>${true}</t></is></c>'
        '<c r="C1" t="s"><v>0</v></c>'
        '<c r="D1" t="inlineStr"><is><t>${2.5}</t></is></c>'
        "<c r=\"E1\" t=\"inlineStr\"><is><t>${'inline'}</t></is></c>"
        '<c r="F1" t="inlineStr"><is><t>${2147483648}</t></is></c>'
        '<c r="G1" t="inlineStr"><is><t>${4294967297}</t></is></c>')
    with zipfile.ZipFile(application / "reports/constant.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in constants.items():
            archive.writestr(name, content)
    constant_comment = application / "reports/constant-comment.xlsx"
    shutil.copy2(application / "reports/constant.xlsx", constant_comment)
    with zipfile.ZipFile(constant_comment, "a") as archive:
        archive.comment = b"preserve expression ZIP comment"
    parameters = dict(constants)
    parameters["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${parameters['foo']}</t></si><si><t>Value: ${parameters['foo']}!</t></si><si><t>${parameters['missing']}</t></si><si><t>${parameters.foo}</t></si><si><t>${parameters ? 7 : 9}</t></si></sst>'''
    parameters["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c><c r="E1" t="s"><v>4</v></c>')
    with zipfile.ZipFile(application / "reports/parameters.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parameters.items():
            archive.writestr(name, content)
    merged = dict(entries)
    merged["xl/worksheets/sheet1.xml"] = original_sheet.replace("</worksheet>", '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    with zipfile.ZipFile(application / "reports/merged.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in merged.items():
            archive.writestr(name, content)
    formula = dict(entries)
    formula["xl/worksheets/sheet1.xml"] = original_sheet.replace('</row>', '<c r="B1"><f>1+1</f><v>2</v></c></row>')
    with zipfile.ZipFile(application / "reports/formula.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in formula.items():
            archive.writestr(name, content)
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "report.d"
    harness.write_text('''import z8.runtime;
import z8gen.StaticReportProbe;
import std.file : read, copy;
import std.path : buildPath;
import std.conv : to;
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
    auto request = new Z8ApplicationRequest();
    request.parameters.z8_add("foo"w, "данные 😀 _x0041_"w);
    auto previousRequest = z8_application_set_request(request);
    scope(exit) z8_application_set_request(previousRequest);
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
    foreach (i; 0 .. 4) {
        auto name = "case" ~ i.to!string;
        auto result = P.m_hidden(name.to!wstring);
        copy(z8_file_resolve_path(result), buildPath(args[2], name ~ ".xlsx"));
    }
    auto ordered = P.m_ordered(); copy(z8_file_resolve_path(ordered), buildPath(args[2], "order.xlsx"));
    assert(database.begins == 12 && database.rollbacks == 12);
    bool badSheet; try { P.m_invalidSheet(); } catch (Exception) { badSheet = true; } assert(badSheet);
    bool badColumn; try { P.m_invalidColumn(); } catch (Exception) { badColumn = true; } assert(badColumn);
    assert(database.begins == 14 && database.rollbacks == 14);
    auto range = P.m_simpleRange();
    assert(read(z8_file_resolve_path(range)) == read(buildPath(args[1], "reports", "sample.xlsx")));
    copy(z8_file_resolve_path(range), buildPath(args[2], "range.xlsx"));
    bool badRange; try { P.m_invalidRange(); } catch (Exception) { badRange = true; } assert(badRange);
    bool expression; try { P.m_expressionRange(); } catch (Exception) { expression = true; } assert(expression);
    assert(z8_file_exists(P.m_implicitRange()));
    bool outside; try { P.m_invalidImplicitRange(); } catch (Exception) { outside = true; } assert(outside);
    bool merged; try { P.m_mergedRange(); } catch (Exception) { merged = true; } assert(merged);
    assert(database.begins == 20 && database.rollbacks == 20);
    auto renamed = P.m_renamedRange();
    copy(z8_file_resolve_path(renamed), buildPath(args[2], "renamed.xlsx"));
    bool invalidName; try { P.m_invalidRename(); } catch (Exception) { invalidName = true; } assert(invalidName);
    bool formula; try { P.m_formulaRename(); } catch (Exception) { formula = true; } assert(formula);
    bool duplicate; try { P.m_duplicateRename(); } catch (Exception) { duplicate = true; } assert(duplicate);
    auto longName = P.m_longRename(); copy(z8_file_resolve_path(longName), buildPath(args[2], "long-name.xlsx"));
    assert(database.begins == 25 && database.rollbacks == 25);
    auto comment = P.m_commentRename(); copy(z8_file_resolve_path(comment), buildPath(args[2], "comment.xlsx"));
    assert(database.begins == 26 && database.rollbacks == 26);
    auto commentHidden = P.m_hidden("comment"w); copy(z8_file_resolve_path(commentHidden), buildPath(args[2], "comment-hidden.xlsx"));
    assert(database.begins == 27 && database.rollbacks == 27);
    bool constants; try { P.m_constantRange(); } catch (Exception) { constants = true; } assert(constants);
    assert(database.begins == 28 && database.rollbacks == 28);
    bool unsafe; try { P.m_constantComment(); } catch (Exception) { unsafe = true; } assert(unsafe);
    auto utf16 = P.m_hidden("utf16-metadata"w); copy(z8_file_resolve_path(utf16), buildPath(args[2], "utf16-metadata.xlsx"));
    assert(database.begins == 30 && database.rollbacks == 30);
    auto mixed = P.m_mixedRange();
    assert(read(z8_file_resolve_path(mixed)) == read(buildPath(args[1], "reports", "mixed.xlsx")));
    bool quoted; try { P.m_doubleQuotedRange(); } catch (Exception) { quoted = true; } assert(quoted);
    assert(database.begins == 32 && database.rollbacks == 32);
    bool unknown; try { P.m_unknownMixedRange(); } catch (Exception) { unknown = true; } assert(unknown);
    auto plain = P.m_plainSymbolsRange();
    assert(read(z8_file_resolve_path(plain)) == read(buildPath(args[1], "reports", "plain-symbols.xlsx")));
    assert(database.begins == 34 && database.rollbacks == 34);
    bool parameters; try { P.m_parametersRange(); } catch (Exception) { parameters = true; } assert(parameters);
    assert(database.begins == 35 && database.rollbacks == 35);
    bool mapOperation; try { P.m_mapOperationRange(); } catch (Exception) { mapOperation = true; } assert(mapOperation);
    assert(database.begins == 36 && database.rollbacks == 36);
    z8_application_set_request(null);
    assert(z8_file_exists(P.m_simpleRange()));
    bool noRequest; try { P.m_parametersRange(); } catch (Exception) { noRequest = true; } assert(noRequest);
    assert(database.begins == 38 && database.rollbacks == 38);
}
''', encoding="utf-8")
    executable = temp / ("report.exe" if os.name == "nt" else "report")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    environment = os.environ.copy()
    library_dir = os.environ.get("Z8_OPENXLSX_DIR")
    if library_dir:
        library_dir = Path(library_dir).resolve()
        bridge = ROOT / "xlsx/source"
        contents = harness.read_text(encoding="utf-8")
        contents = contents.replace("import z8.runtime;", "import z8.runtime;\nimport z8.xlsx.poi : z8_openxlsx_configure;")
        contents = contents.replace("void main(string[] args) {", '''class CountingProvider : IZ8PoiProvider, IZ8PoiReportWriter {
    IZ8PoiProvider reader;
    IZ8PoiReportWriter writer;
    uint renames, hides, writes;
    this(IZ8PoiProvider provider) { reader = provider; writer = cast(IZ8PoiReportWriter)provider; assert(writer !is null); }
    IZ8PoiDocument open(const(ubyte)[] input) { return reader.open(input); }
    ubyte[] renameReportSheet(const(ubyte)[] input, uint index, wstring name) {
        auto result = writer.renameReportSheet(input, index, name);
        ++renames; return result;
    }
    ubyte[] hideReportColumns(const(ubyte)[] input, const(Z8PoiHiddenColumn)[] columns) {
        auto result = writer.hideReportColumns(input, columns);
        ++hides; return result;
    }
    ubyte[] writeReportCells(const(ubyte)[] input, const(Z8PoiCellEdit)[] cells) {
        auto result = writer.writeReportCells(input, cells);
        ++writes; return result;
    }
}
void main(string[] args) {
    z8_openxlsx_configure();
    auto counter = new CountingProvider(z8_poi_set_provider(null));
    z8_poi_set_provider(counter);''')
        contents = contents.replace(
            'bool constants; try { P.m_constantRange(); } catch (Exception) { constants = true; } assert(constants);',
            'auto constants = P.m_constantRange(); copy(z8_file_resolve_path(constants), buildPath(args[2], "constant.xlsx"));')
        contents = contents.replace(
            'bool parameters; try { P.m_parametersRange(); } catch (Exception) { parameters = true; } assert(parameters);',
            'auto parameters = P.m_parametersRange(); copy(z8_file_resolve_path(parameters), buildPath(args[2], "parameters.xlsx"));')
        contents = contents.replace("assert(database.begins == 36 && database.rollbacks == 36);",
                                    "assert(database.begins == 36 && database.rollbacks == 36); assert(counter.renames == 2 && counter.hides == 1 && counter.writes == 2);")
        harness.write_text(contents, encoding="utf-8")
        args.extend(["-I" + str(bridge), str(bridge / "z8/xlsx/openxlsx.d"), str(bridge / "z8/xlsx/poi.d")])
        if os.name == "nt":
            args.append(str(library_dir / "z8_openxlsx.lib"))
            shutil.copy2(library_dir / "z8_openxlsx.dll", temp)
        else:
            args.extend(["-L-L" + str(library_dir), "-L-lz8_openxlsx"])
            environment["LD_LIBRARY_PATH"] = str(library_dir) + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(application), str(working)], cwd=temp, env=environment, check=True)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    def columns(path):
        with zipfile.ZipFile(path) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            assert sheet.find("x:sheetData/x:row/x:c/x:is/x:t", namespace).text == "Example"
            return [item.attrib for item in sheet.findall("x:cols/x:col", namespace)]
    assert columns(working / "hidden.xlsx") == [
        {"min": "2", "max": "2", "hidden": "1"}, {"min": "4", "max": "4", "hidden": "1"},
        {"min": "7", "max": "7", "hidden": "1"}]
    styled_columns = columns(working / "styled.xlsx")
    assert styled_columns == [
        {"min": "1", "max": "1", "width": "12", "customWidth": "1", "collapsed": "1"},
        {"min": "2", "max": "2", "width": "12", "customWidth": "1", "hidden": "1"},
        {"min": "3", "max": "3", "width": "12", "customWidth": "1", "collapsed": "1"},
        {"min": "4", "max": "4", "width": "12", "customWidth": "1", "hidden": "1", "collapsed": "1"},
        {"min": "7", "max": "7", "hidden": "1"},
        {"min": "8", "max": "8", "hidden": "1", "width": "9"}], styled_columns
    with zipfile.ZipFile(working / "multiple.xlsx") as archive:
        second = archive.read("xl/worksheets/sheet2.xml")
        assert second.startswith(b"\xff\xfe")
        sheet = ET.fromstring(second)
        assert sheet.find("x:sheetData/x:row/x:c/x:is/x:t", namespace).text == "😀"
        assert [item.attrib for item in sheet.findall("x:cols/x:col", namespace)] == [{"min": "1", "max": "1", "hidden": "1"}]
    with zipfile.ZipFile(working / "renamed.xlsx") as archive:
        renamed = ET.fromstring(archive.read("xl/workbook.xml"))
        assert renamed.find("x:sheets/x:sheet", namespace).attrib["name"] == "Отчёт 😀"
    with zipfile.ZipFile(working / "long-name.xlsx") as archive:
        renamed = ET.fromstring(archive.read("xl/workbook.xml"))
        assert renamed.find("x:sheets/x:sheet", namespace).attrib["name"] == "abcdefghijklmnopqrstuvwxyz12345"
    with zipfile.ZipFile(working / "comment.xlsx") as archive:
        assert archive.comment == b"preserve ZIP comment"
        renamed = ET.fromstring(archive.read("xl/workbook.xml"))
        assert renamed.find("x:sheets/x:sheet", namespace).attrib["name"] == "Comment renamed"
    with zipfile.ZipFile(working / "comment-hidden.xlsx") as archive:
        assert archive.comment == b"preserve ZIP comment"
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert [item.attrib for item in sheet.findall("x:cols/x:col", namespace)] == [
            {"min": "2", "max": "2", "hidden": "1"}, {"min": "4", "max": "4", "hidden": "1"},
            {"min": "7", "max": "7", "hidden": "1"}]
    with zipfile.ZipFile(working / "utf16-metadata.xlsx") as archive:
        assert archive.read("xl/workbook.xml").startswith(b"\xff\xfe")
    if library_dir:
        with zipfile.ZipFile(working / "constant.xlsx") as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            cells = sheet.findall("x:sheetData/x:row/x:c", namespace)
            assert len(cells) == 7
            assert float(cells[0].find("x:v", namespace).text) == 3
            assert cells[1].attrib["t"] == "b" and cells[1].find("x:v", namespace).text == "1"
            assert cells[2].attrib["t"] == "s"
            shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            text_index = int(cells[2].find("x:v", namespace).text)
            actual_text = shared.findall("x:si", namespace)[text_index].find("x:t", namespace).text
            assert "${" not in actual_text and actual_text.startswith("Hello literal / 3 / "), actual_text
            assert float(cells[3].find("x:v", namespace).text) == 2.5
            assert cells[4].find("x:is/x:t", namespace).text == "${'inline'}"
            assert float(cells[5].find("x:v", namespace).text) == -2147483648
            assert float(cells[6].find("x:v", namespace).text) == 1
        with zipfile.ZipFile(working / "parameters.xlsx") as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            shared = ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("x:si", namespace)
            cells = sheet.findall("x:sheetData/x:row/x:c", namespace)
            values = [(shared[int(cell.find("x:v", namespace).text)].find("x:t", namespace).text or "") for cell in cells[:4]]
            assert values == ["данные 😀 _x0041_", "Value: данные 😀 _x0041_!", "", ""], values
            assert float(cells[4].find("x:v", namespace).text) == 7
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
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.openxmlformats.schemas.spreadsheetml.x2006.main.CTCol;
import java.util.HashSet;
class PoiHiddenOracle {
  public static void main(String[] args) throws Exception {
    try (XSSFWorkbook original = new XSSFWorkbook(new FileInputStream(args[0]));
         XSSFWorkbook actual = new XSSFWorkbook(new FileInputStream(args[1]))) {
      Sheet expected = original.getSheetAt(0), result = actual.getSheetAt(0);
      HashSet<Integer> hidden = new HashSet<>();
      for (int column : args.length > 2 ? new int[]{16, 1, 17, 3} : new int[]{1, 3, 6}) hidden.add(column);
      for (int column : hidden) expected.setColumnHidden(column, true);
      for (int column = 0; column < 24; column++)
      {
        CTCol e = ((XSSFSheet)expected).getColumnHelper().getColumn(column, false);
        CTCol r = ((XSSFSheet)result).getColumnHelper().getColumn(column, false);
        if (expected.isColumnHidden(column) != result.isColumnHidden(column) ||
            expected.getColumnWidth(column) != result.getColumnWidth(column) ||
            expected.getColumnOutlineLevel(column) != result.getColumnOutlineLevel(column) ||
            (e != null && e.getCollapsed()) != (r != null && r.getCollapsed()))
          throw new AssertionError(args[0] + " column " + column + " expected=" + expected.isColumnHidden(column) +
              "/" + expected.getColumnWidth(column) + "/" + expected.getColumnOutlineLevel(column) + " actual=" +
              result.isColumnHidden(column) + "/" + result.getColumnWidth(column) + "/" + result.getColumnOutlineLevel(column) +
              " collapsed=" + (e != null && e.getCollapsed()) + "/" + (r != null && r.getCollapsed()));
      }
      if (!"Example".equals(result.getRow(0).getCell(0).getStringCellValue()))
        throw new AssertionError("Cell was changed");
    }
  }
}''', encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(oracle)], cwd=temp, check=True)
        pairs = [(workbook, working / "hidden.xlsx"),
                                         (application / "reports/styled.xlsx", working / "styled.xlsx"),
                                         (application / "reports/overlap.xlsx", working / "overlap.xlsx")]
        pairs += [(application / ("reports/case" + str(number) + ".xlsx"), working / ("case" + str(number) + ".xlsx"))
                  for number in range(len(cases))]
        for source_path, result_path in pairs:
            result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "PoiHiddenOracle",
                                     str(source_path), str(result_path)], cwd=temp, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "PoiHiddenOracle",
                                 str(application / "reports/order.xlsx"), str(working / "order.xlsx"), "ordered"],
                                cwd=temp, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        original_root = os.environ.get("Z8_ORIGINAL_ROOT")
        if original_root:
            server_jars = list((Path(original_root) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
            antlr = list(cache.glob("org.antlr/antlr4-runtime/4.13.2/**/*.jar"))
            commons = [p for p in cache.rglob("*.jar") if p.name.startswith(
                ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]
            if not server_jars or not antlr:
                raise SystemExit("Original Z8 server JAR or ANTLR runtime is unavailable")
            range_classpath = os.pathsep.join(map(str, [*server_jars, *antlr, *commons, *jars]))
            range_oracle = temp / "PoiRangeOracle.java"
            range_oracle.write_text('''import java.io.FileInputStream;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.zenframework.z8.server.config.ServerConfig;
import org.zenframework.z8.server.engine.ApplicationServer;
import org.zenframework.z8.server.engine.Session;
import org.zenframework.z8.server.request.Request;
import org.zenframework.z8.server.runtime.OBJECT;
import org.zenframework.z8.server.reports.poi.*;
class PoiRangeOracle {
  public static void main(String[] args) throws Exception {
    ServerConfig.load(args[2]);
    Request request = new Request(new Session("test"));
    request.getParameters().put(new org.zenframework.z8.server.types.string("foo"), new org.zenframework.z8.server.types.string("данные 😀 _x0041_"));
    ApplicationServer.setRequest(request);
    try (XSSFWorkbook original = new XSSFWorkbook(new FileInputStream(args[0]));
         XSSFWorkbook actual = new XSSFWorkbook(new FileInputStream(args[1]))) {
      PoiReport report = new PoiReport(new ReportOptions()).setContext(new OBJECT.CLASS<OBJECT>(null).get());
      boolean constants = args.length > 3 && "constants".equals(args[3]);
      boolean parameters = args.length > 3 && "parameters".equals(args[3]);
      Range child = new Range().setSource(SimpleSource.newDefault())
          .setBlock(constants ? "A1:G1" : parameters ? "A1:E1" : "$A$1:A1")
          .setBoundaries(constants ? "A1:G1" : parameters ? "A1:E1" : "A1:B2");
      report.addRange(0, child);
      if (args.length > 3 && "rename".equals(args[3])) original.setSheetName(0, "Отчёт \\uD83D\\uDE00");
      SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
      report.getRange(0).apply(modifier); modifier.close();
      if (constants || parameters) {
        for (int i = 0; i < (constants ? 7 : 5); ++i) {
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(0).getRow(0).getCell(i);
          org.apache.poi.ss.usermodel.Cell result = actual.getSheetAt(0).getRow(0).getCell(i);
          if (expected.getCellType() != result.getCellType()) throw new AssertionError("cell type differs at " + i);
          switch (expected.getCellType()) {
            case org.apache.poi.ss.usermodel.Cell.CELL_TYPE_NUMERIC:
              if (expected.getNumericCellValue() != result.getNumericCellValue()) throw new AssertionError("number differs at " + i); break;
            case org.apache.poi.ss.usermodel.Cell.CELL_TYPE_BOOLEAN:
              if (expected.getBooleanCellValue() != result.getBooleanCellValue()) throw new AssertionError("boolean differs at " + i); break;
            case org.apache.poi.ss.usermodel.Cell.CELL_TYPE_STRING:
              if (!expected.getStringCellValue().equals(result.getStringCellValue()))
                throw new AssertionError("text differs at " + i + ": [" + expected.getStringCellValue() + "] != [" + result.getStringCellValue() + "]"); break;
            default: throw new AssertionError("unexpected result type");
          }
        }
      } else {
        String expected = original.getSheetAt(0).getRow(0).getCell(0).getStringCellValue();
        String result = actual.getSheetAt(0).getRow(0).getCell(0).getStringCellValue();
        if (!expected.equals(result)) throw new AssertionError(expected + " != " + result);
      }
      if (!original.getSheetName(0).equals(actual.getSheetName(0))) throw new AssertionError("sheet name differs");
    } finally { ApplicationServer.setRequest(null); }
  }
}''', encoding="utf-8")
            config = temp / "oracle.properties"
            config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", range_classpath, str(range_oracle)], cwd=temp, check=True)
            result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                     str(workbook), str(working / "range.xlsx"), str(config)], cwd=temp, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                     str(workbook), str(working / "renamed.xlsx"), str(config), "rename"],
                                    cwd=temp, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            if library_dir:
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/constant.xlsx"), str(working / "constant.xlsx"), str(config), "constants"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/parameters.xlsx"), str(working / "parameters.xlsx"), str(config), "parameters"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
print("POI static report template, naming and transaction verified")
