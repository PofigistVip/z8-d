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
import org.zenframework.z8.base.table.value.IntField;
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
    public static file contextRange() { ContextRangeReport report; return report.run(guid.Null); }
    public static file unsupportedContextRange() { UnsupportedContextRangeReport report; return report.run(guid.Null); }
    public static file dateRange() { DateRangeReport report; return report.run(guid.Null); }
    public static file date1904Range() { Date1904RangeReport report; return report.run(guid.Null); }
    public static FieldRangeReport createFieldReport() { FieldRangeReport report; return report; }
    public static IntField field(FieldRangeReport report) { return report.amount; }
    public static IntField groupField(FieldRangeReport report) { return report.group.count; }
    public static file runFieldReport(FieldRangeReport report) { return report.run(guid.Null); }
    public static CustomRangeReport createCustomReport() { CustomRangeReport report; return report; }
    public static file runCustomReport(CustomRangeReport report) { return report.run(guid.Null); }
    public static int opened(CustomRangeReport report) { return report.rows.opened; }
    public static int closed(CustomRangeReport report) { return report.rows.closed; }
    public static void customCount(CustomRangeReport report, int count) { report.rows.n = count; }
    public static void customFail(CustomRangeReport report) { report.rows.fail = true; }
    public static file jsonRange() { JsonRangeReport report; return report.run(guid.Null); }
    public static JsonRangeReport createJsonReport() { JsonRangeReport report; return report; }
    public static void jsonCount(JsonRangeReport report, int count) { report.copies = count; }
    public static file runJsonReport(JsonRangeReport report) { return report.run(guid.Null); }
    public static QueryRangeReport createQueryReport() { QueryRangeReport report; return report; }
    public static QueryRows query(QueryRangeReport report) { return report.q; }
    public static file runQueryReport(QueryRangeReport report) { return report.run(guid.Null); }
    public static file multipleRanges() { MultipleRangeReport report; return report.run(guid.Null); }
    public static file overlappingRanges() { OverlappingRangeReport report; return report.run(guid.Null); }
    public static file outsideRanges() { OutsideRangesReport report; return report.run(guid.Null); }
    public static file missingBoundaries() { MissingBoundariesReport report; return report.run(guid.Null); }
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
            ("DateRangeReport", "dates", "A1:J1", "A1:J1"),
            ("Date1904RangeReport", "dates1904", "A1:J1", "A1:J1"),
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
    (source / "ContextRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
public class ContextRangeReport extends Report {
    engine = Report.POI; template = "context";
    JsonObject info; JsonObject parameters; ContextGroup group;
    objects = {info, parameters, group};
    [address "A1:E1"] [boundaries "A1:E1"] Range region;
    ranges = {region};
    virtual protected void prepare(guid recordId) {
        info.set("title", "Ada 😀"); info.set("amount", 42);
        parameters.set("foo", "member value");
        group.data.set("amount", 42);
    }
}''', encoding="utf-8")
    (source / "ContextGroup.bl").write_text('''import org.zenframework.z8.lang.Object;
import org.zenframework.z8.base.json.JsonObject;
public class ContextGroup extends Object {
    public JsonObject data; objects = {data};
}''', encoding="utf-8")
    (source / "FieldRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.table.value.IntField;
public class FieldRangeReport extends Report {
    engine = Report.POI; template = "fields";
    public IntField amount; public FieldGroup group; objects = {amount, group};
    [address "A1:E1"] [boundaries "A1:E1"] Range region;
    ranges = {region};
}''', encoding="utf-8")
    (source / "FieldGroup.bl").write_text('''import org.zenframework.z8.lang.Object;
import org.zenframework.z8.base.table.value.IntField;
public class FieldGroup extends Object {
    public IntField count; objects = {count};
}''', encoding="utf-8")
    (source / "ReportRows.bl").write_text('''import org.zenframework.z8.base.form.report.CustomData;
import org.zenframework.z8.base.json.JsonObject;
public class ReportRows extends CustomData {
    public int opened = 0; public int closed = 0; public int n = 1; public bool fail = false;
    public JsonObject data; objects = {data};
    virtual public int count() { return n; }
    virtual public void open() { opened += 1; data.set("value", 123); if (fail) throw "open failed"; }
    virtual public void close() { closed += 1; }
}''', encoding="utf-8")
    (source / "CustomRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class CustomRangeReport extends Report {
    engine = Report.POI; template = "custom";
    public ReportRows rows; objects = {rows};
    [address "A1:D1"] [boundaries "A1:D1"] Range region;
    region.source = rows; ranges = {region};
}''', encoding="utf-8")
    (source / "JsonRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class JsonRangeReport extends Report {
    engine = Report.POI; template = "json";
    JsonArray rows; public int copies = 1; objects = {rows};
    [address "A1:E1"] [boundaries "A1:E1"] Range region;
    region.source = rows; ranges = {region};
    virtual protected void prepare(guid recordId) {
        JsonObject item; item.set("title", "Ada 😀"); item.set("amount", 42);
        if (copies > 0) rows.add(item); if (copies > 1) rows.add(item);
    }
}''', encoding="utf-8")
    (source / "QueryRows.bl").write_text('''import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.IntField;
public class QueryRows extends Query {
    public IntField amount; public IntField ignored; public IntField extra;
    objects = {amount, ignored, extra}; extraFields = {extra};
    public void start() { Field[] fields = {amount}; read(fields); }
    public bool advance() { return next(); }
    public int value() { return amount.get(); }
}''', encoding="utf-8")
    (source / "QueryRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class QueryRangeReport extends Report {
    engine = Report.POI; template = "query";
    public QueryRows q; objects = {q};
    [address "A1:E1"] [boundaries "A1:E1"] Range region;
    region.source = q; ranges = {region};
}''', encoding="utf-8")
    (source / "OrderedRows.bl").write_text('''import org.zenframework.z8.base.form.report.CustomData;
import org.zenframework.z8.base.json.JsonObject;
public class OrderedRows extends CustomData {
    static public int sequence = 0; public JsonObject data; objects = {data};
    virtual public int count() { return 1; }
    virtual public void open() { sequence += 1; data.set("value", sequence); }
}''', encoding="utf-8")
    for class_name, template, left_bound, right_bound in (
            ("MultipleRangeReport", "multi-range", "A1", "C1"),
            ("OverlappingRangeReport", "multi-range", "A1:B1", "B1:C1"),
            ("OutsideRangesReport", "outside-range", "A1", "C1")):
        (source / (class_name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    OrderedRows left; OrderedRows right; objects = {left, right};
    [address "A1"] [boundaries "%s"] Range first;
    [address "C1"] [boundaries "%s"] Range second;
    first.source = left; second.source = right; ranges = {second, first};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''' % (class_name, template, left_bound, right_bound), encoding="utf-8")
    (source / "MissingBoundariesReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class MissingBoundariesReport extends Report {
    engine = Report.POI; template = "multi-range";
    [address "A1"] Range first; [address "C1"] Range second;
    ranges = {first, second};
}''', encoding="utf-8")
    (source / "UnsupportedContextRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.lang.Object;
public class UnsupportedContextRangeReport extends Report {
    engine = Report.POI; template = "parameters";
    Object parameters; objects = {parameters};
    [address "A1:E1"] [boundaries "A1:E1"] Range region;
    ranges = {region};
}''', encoding="utf-8")
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
    context = dict(parameters)
    context["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${info['title']}</t></si><si><t>${group.data.amount}</t></si><si><t>${parameters.foo}</t></si><si><t>Title: ${info.title}!</t></si><si><t>${info.missing}</t></si></sst>'''
    with zipfile.ZipFile(application / "reports/context.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in context.items():
            archive.writestr(name, content)
    dates = dict(constants)
    dates["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="9" uniqueCount="9"><si><t>${date.parse('01/01/1900', 'dd/MM/yyyy')}</t></si><si><t>${date.parse('28/02/1900', 'dd/MM/yyyy')}</t></si><si><t>${date.parse('01/03/1900', 'dd/MM/yyyy')}</t></si><si><t>${date.parse('31/12/1899', 'dd/MM/yyyy')}</t></si><si><t>${date.parse('01/01/1904', 'dd/MM/yyyy')}</t></si><si><t>${date.parse('2024-02-29 15:16:17.123', 'yyyy-MM-dd HH:mm:ss.SSS')}</t></si><si><t>${date.parseIsoString('2024-02-29T23:30:00+02:00')}</t></si><si><t>${guid.parse('00000000-0000-0000-0000-000000000001')}</t></si><si><t>${datespan.parse('1 02:03:04')}</t></si></sst>'''
    dates["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        ''.join('<c r="%s1" t="s"><v>%d</v></c>' % (chr(65 + i), i) for i in range(9)) +
        '<c r="J1" t="inlineStr"><is><t>${guid.parse(\'00000000-0000-0000-0000-000000000001\')}</t></is></c>')
    for name, use1904 in (("dates", False), ("dates1904", True)):
        book = dict(dates)
        if use1904:
            book["xl/workbook.xml"] = book["xl/workbook.xml"].replace("<sheets>", '<workbookPr date1904="1"/><sheets>')
        with zipfile.ZipFile(application / ("reports/" + name + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in book.items():
                archive.writestr(entry_name, content)
    fields = dict(parameters)
    fields["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${amount}</t></si><si><t>${amount + 1}</t></si><si><t>Value: ${amount}</t></si><si><t>${group.count}</t></si><si><t>${group.count + 1}</t></si></sst>'''
    fields["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        ''.join('<c r="%s1" t="s"><v>%d</v></c>' % (chr(65 + i), i) for i in range(5)))
    with zipfile.ZipFile(application / "reports/fields.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in fields.items():
            archive.writestr(entry_name, content)
    custom = dict(parameters)
    custom["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4"><si><t>${rows.data.value}</t></si><si><t>Value: ${rows.data.value}</t></si><si><t>${rows.index}</t></si><si><t>${rows.sheet}</t></si></sst>'''
    custom["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c>')
    with zipfile.ZipFile(application / "reports/custom.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in custom.items():
            archive.writestr(entry_name, content)
    json_source = dict(parameters)
    json_source["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${rows.item.title}</t></si><si><t>${rows.item.amount}</t></si><si><t>${rows.index}</t></si><si><t>${rows.sheet}</t></si><si><t>Title: ${rows.item.title}</t></si></sst>'''
    with zipfile.ZipFile(application / "reports/json.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in json_source.items():
            archive.writestr(entry_name, content)
    query = dict(parameters)
    query["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${q.amount}</t></si><si><t>${q . amount + 1}</t></si><si><t>Value: ${q.amount}</t></si><si><t>${q.index}</t></si><si><t>${'q.ignored'}</t></si></sst>'''
    with zipfile.ZipFile(application / "reports/query.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in query.items():
            archive.writestr(entry_name, content)
    multi = dict(parameters)
    multi["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>${left.data.value}</t></si><si><t>${right.data.value}</t></si></sst>'''
    multi["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>${10+20}</t></is></c><c r="C1" t="s"><v>1</v></c>')
    for filename in ("multi-range", "outside-range"):
        book = dict(multi)
        if filename == "outside-range":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('</row>', '<c r="D1" t="inlineStr"><is><t>${1}</t></is></c></row>')
        with zipfile.ZipFile(application / ("reports/" + filename + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in book.items():
                archive.writestr(entry_name, content)
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
class FieldCursor : IZ8FieldCursor {
    bool closed;
    bool isClosed() { return closed; }
    bool isGrouped() { return false; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        assert(!asArray); wasNull = false; return z8_primary_box(42L);
    }
}
class QueryCursor : IZ8QueryCursor {
    Z8Object[] selected; long value; int remaining; bool closed;
    this(Z8Object[] fields, long initial, int count) { selected = fields.dup; value = initial - 1; remaining = count; }
    Z8Object[] fields() { return selected; }
    bool next() { if (closed || remaining <= 0) return false; --remaining; ++value; return true; }
    void close() { closed = true; }
    bool isClosed() { return closed; }
    bool isGrouped() { return false; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) { wasNull = false; return z8_primary_box(value); }
}
class QueryExecutor : IZ8QueryExecutor {
    bool reportMode, fail; int reportRows = 1; Z8Object amount, extra;
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) {
        if (fail) throw new Exception("query failed");
        if (reportMode) {
            assert(request.fields.length == 2);
            assert((request.fields[0] is amount && request.fields[1] is extra) ||
                   (request.fields[1] is amount && request.fields[0] is extra));
            return new QueryCursor(request.fields, 42, reportRows);
        }
        return new QueryCursor(request.fields, 7, 2);
    }
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
    z8_application_set_request(request);
    bool context; try { P.m_contextRange(); } catch (Exception) { context = true; } assert(context);
    assert(database.begins == 39 && database.rollbacks == 39);
    bool unsupported; try { P.m_unsupportedContextRange(); } catch (Exception e) {
        unsupported = e.msg == "POI report object context member is not implemented";
    } assert(unsupported);
    assert(database.begins == 40 && database.rollbacks == 40);
    bool dates; try { P.m_dateRange(); } catch (Exception) { dates = true; } assert(dates);
    bool dates1904; try { P.m_date1904Range(); } catch (Exception) { dates1904 = true; } assert(dates1904);
    assert(database.begins == 42 && database.rollbacks == 42);
    auto fieldReport = P.m_createFieldReport();
    auto fieldCursor = new FieldCursor(); z8_field_set_cursor(P.m_field(fieldReport), fieldCursor);
    z8_field_set_cursor(P.m_groupField(fieldReport), fieldCursor);
    bool fieldResult; try { P.m_runFieldReport(fieldReport); } catch (Exception) { fieldResult = true; } assert(fieldResult);
    fieldCursor.closed = true;
    bool fieldClosed; try { P.m_runFieldReport(fieldReport); } catch (Exception) { fieldClosed = true; } assert(fieldClosed);
    assert(database.begins == 44 && database.rollbacks == 44);
    auto customReport = P.m_createCustomReport();
    bool customResult; try { P.m_runCustomReport(customReport); } catch (Exception) { customResult = true; } assert(customResult);
    assert(z8_optional_require(P.m_opened(customReport)) == 1 && z8_optional_require(P.m_closed(customReport)) == 1);
    P.m_customCount(customReport, z8_optional_wrap(2L));
    bool customMany; try { P.m_runCustomReport(customReport); } catch (Exception) { customMany = true; } assert(customMany);
    P.m_customFail(customReport);
    bool customFailedOpen; try { P.m_runCustomReport(customReport); } catch (Exception) { customFailedOpen = true; } assert(customFailedOpen);
    assert(z8_optional_require(P.m_opened(customReport)) == 3 && z8_optional_require(P.m_closed(customReport)) == 3);
    assert(database.begins == 47 && database.rollbacks == 47);
    bool json; try { P.m_jsonRange(); } catch (Exception) { json = true; } assert(json);
    assert(database.begins == 48 && database.rollbacks == 48);
    auto jsonEmpty = P.m_createJsonReport(); P.m_jsonCount(jsonEmpty, z8_optional_wrap(0L));
    bool empty; try { P.m_runJsonReport(jsonEmpty); } catch (Exception) { empty = true; } assert(empty);
    auto jsonMany = P.m_createJsonReport(); P.m_jsonCount(jsonMany, z8_optional_wrap(2L));
    bool many; try { P.m_runJsonReport(jsonMany); } catch (Exception) { many = true; } assert(many);
    assert(database.begins == 50 && database.rollbacks == 50);
    auto queryReport = P.m_createQueryReport(); auto query = P.m_query(queryReport);
    auto executor = new QueryExecutor(); executor.amount = query.f_amount; executor.extra = query.f_extra;
    z8_query_set_executor(query, executor); query.m_start();
    assert(z8_optional_require(query.m_advance()) && z8_optional_require(query.m_value()) == 7);
    executor.reportMode = true;
    bool queryResult; try { P.m_runQueryReport(queryReport); } catch (Exception) { queryResult = true; } assert(queryResult);
    assert(z8_optional_require(query.m_value()) == 7 && z8_optional_require(query.m_advance()) && z8_optional_require(query.m_value()) == 8);
    executor.reportRows = 2;
    bool queryMany; try { P.m_runQueryReport(queryReport); } catch (Exception) { queryMany = true; } assert(queryMany);
    assert(z8_optional_require(query.m_value()) == 8);
    executor.fail = true;
    bool queryFailure; try { P.m_runQueryReport(queryReport); } catch (Exception) { queryFailure = true; } assert(queryFailure);
    assert(z8_optional_require(query.m_value()) == 8);
    assert(database.begins == 53 && database.rollbacks == 53);
    bool multipleRanges; try { P.m_multipleRanges(); } catch (Exception) { multipleRanges = true; } assert(multipleRanges);
    bool overlapRanges; try { P.m_overlappingRanges(); } catch (Exception) { overlapRanges = true; } assert(overlapRanges);
    bool outsideRanges; try { P.m_outsideRanges(); } catch (Exception) { outsideRanges = true; } assert(outsideRanges);
    bool missingBoundaries; try { P.m_missingBoundaries(); } catch (Exception) { missingBoundaries = true; } assert(missingBoundaries);
    assert(database.begins == 57 && database.rollbacks == 57);
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
        contents = contents.replace(
            'bool context; try { P.m_contextRange(); } catch (Exception) { context = true; } assert(context);',
            'auto context = P.m_contextRange(); copy(z8_file_resolve_path(context), buildPath(args[2], "context.xlsx")); assert(counter.writes == 3);')
        contents = contents.replace(
            'bool dates; try { P.m_dateRange(); } catch (Exception) { dates = true; } assert(dates);',
            'auto dates = P.m_dateRange(); copy(z8_file_resolve_path(dates), buildPath(args[2], "dates.xlsx"));')
        contents = contents.replace(
            'bool dates1904; try { P.m_date1904Range(); } catch (Exception) { dates1904 = true; } assert(dates1904);',
            'auto dates1904 = P.m_date1904Range(); copy(z8_file_resolve_path(dates1904), buildPath(args[2], "dates1904.xlsx")); assert(counter.writes == 5);')
        contents = contents.replace(
            'bool fieldResult; try { P.m_runFieldReport(fieldReport); } catch (Exception) { fieldResult = true; } assert(fieldResult);',
            'auto fieldResult = P.m_runFieldReport(fieldReport); copy(z8_file_resolve_path(fieldResult), buildPath(args[2], "fields.xlsx")); assert(counter.writes == 6);')
        contents = contents.replace(
            'bool customResult; try { P.m_runCustomReport(customReport); } catch (Exception) { customResult = true; } assert(customResult);',
            'auto customResult = P.m_runCustomReport(customReport); copy(z8_file_resolve_path(customResult), buildPath(args[2], "custom.xlsx")); assert(counter.writes == 7);')
        contents = contents.replace(
            'bool json; try { P.m_jsonRange(); } catch (Exception) { json = true; } assert(json);',
            'auto json = P.m_jsonRange(); copy(z8_file_resolve_path(json), buildPath(args[2], "json.xlsx")); assert(counter.writes == 8);')
        contents = contents.replace(
            'bool queryResult; try { P.m_runQueryReport(queryReport); } catch (Exception) { queryResult = true; } assert(queryResult);',
            'auto queryResult = P.m_runQueryReport(queryReport); copy(z8_file_resolve_path(queryResult), buildPath(args[2], "query.xlsx")); assert(counter.writes == 9);')
        contents = contents.replace(
            'bool multipleRanges; try { P.m_multipleRanges(); } catch (Exception) { multipleRanges = true; } assert(multipleRanges);',
            'auto multipleRanges = P.m_multipleRanges(); copy(z8_file_resolve_path(multipleRanges), buildPath(args[2], "multi-range.xlsx")); assert(counter.writes == 10);')
        contents = contents.replace(
            'bool outsideRanges; try { P.m_outsideRanges(); } catch (Exception) { outsideRanges = true; } assert(outsideRanges);',
            'auto outsideRanges = P.m_outsideRanges(); copy(z8_file_resolve_path(outsideRanges), buildPath(args[2], "outside-range.xlsx")); assert(counter.writes == 11);')
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
  static class FakeQuery extends org.zenframework.z8.server.base.query.Query {
    int position;
    FakeQuery(org.zenframework.z8.server.runtime.IObject owner) { super(owner); }
    @Override public void saveState() {}
    @Override public void restoreState() {}
    @Override public void read(java.util.Collection<org.zenframework.z8.server.base.table.value.Field> fields,
                               java.util.Collection<org.zenframework.z8.server.base.table.value.Field> sort,
                               org.zenframework.z8.server.db.sql.SqlToken where) {
      java.util.Set<String> names = new java.util.HashSet<>();
      org.zenframework.z8.server.db.Select cursor = new org.zenframework.z8.server.db.Select() {
        @Override public boolean isClosed() { return false; }
        @Override public org.zenframework.z8.server.types.primary get(org.zenframework.z8.server.base.table.value.Field field) {
          return new org.zenframework.z8.server.types.integer(42);
        }
      };
      for (org.zenframework.z8.server.base.table.value.Field field : fields) { names.add(field.index()); field.setCursor(cursor); }
      if (!names.equals(new java.util.HashSet<>(java.util.Arrays.asList("amount", "extra"))))
        throw new AssertionError("query fields: " + names);
      position = 0;
    }
    @Override public boolean next() { return position++ == 0; }
  }
  static class FakeQueryClass extends org.zenframework.z8.server.base.query.Query.CLASS<FakeQuery> {
    FakeQueryClass(org.zenframework.z8.server.runtime.IObject owner) { super(owner); setJavaClass(FakeQuery.class); }
    @Override public Object newObject(org.zenframework.z8.server.runtime.IObject owner) { return new FakeQuery(owner); }
  }
  public static void main(String[] args) throws Exception {
    ServerConfig.load(args[2]);
    Request request = new Request(new Session("test"));
    request.getParameters().put(new org.zenframework.z8.server.types.string("foo"), new org.zenframework.z8.server.types.string("данные 😀 _x0041_"));
    ApplicationServer.setRequest(request);
    try (XSSFWorkbook original = new XSSFWorkbook(new FileInputStream(args[0]));
         XSSFWorkbook actual = new XSSFWorkbook(new FileInputStream(args[1]))) {
      OBJECT context = new OBJECT.CLASS<OBJECT>(null).get();
      boolean contextCase = args.length > 3 && "context".equals(args[3]);
      boolean fieldCase = args.length > 3 && "fields".equals(args[3]);
      boolean customCase = args.length > 3 && "custom".equals(args[3]);
      boolean jsonCase = args.length > 3 && "json".equals(args[3]);
      boolean queryCase = args.length > 3 && "query".equals(args[3]);
      boolean outsideCase = args.length > 3 && "outside".equals(args[3]);
      boolean multipleCase = outsideCase || (args.length > 3 && "multiple".equals(args[3]));
      DataSource customSource = null;
      DataSource[] orderedSources = new DataSource[2];
      if (contextCase) {
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> info =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(context);
        info.setIndex("info"); context.members().add(info);
        info.get().z8_set(new org.zenframework.z8.server.types.string("title"), new org.zenframework.z8.server.types.string("Ada 😀"));
        info.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(42));
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> parametersObject =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(context);
        parametersObject.setIndex("parameters"); context.members().add(parametersObject);
        parametersObject.get().z8_set(new org.zenframework.z8.server.types.string("foo"), new org.zenframework.z8.server.types.string("member value"));
        OBJECT.CLASS<OBJECT> group = new OBJECT.CLASS<>(context);
        group.setIndex("group"); context.members().add(group);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(group.get());
        data.setIndex("data"); group.get().members().add(data);
        data.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(42));
      }
      if (fieldCase) {
        org.zenframework.z8.server.base.table.value.IntegerField.CLASS<org.zenframework.z8.server.base.table.value.IntegerField> amount =
            new org.zenframework.z8.server.base.table.value.IntegerField.CLASS<>(context);
        amount.setIndex("amount"); context.members().add(amount);
        org.zenframework.z8.server.db.Select cursor = new org.zenframework.z8.server.db.Select() {
          @Override public boolean isClosed() { return false; }
          @Override public org.zenframework.z8.server.types.primary get(org.zenframework.z8.server.base.table.value.Field field) {
            return new org.zenframework.z8.server.types.integer(42);
          }
        };
        amount.get().setCursor(cursor);
        OBJECT.CLASS<OBJECT> group = new OBJECT.CLASS<>(context);
        group.setIndex("group"); context.members().add(group);
        org.zenframework.z8.server.base.table.value.IntegerField.CLASS<org.zenframework.z8.server.base.table.value.IntegerField> count =
            new org.zenframework.z8.server.base.table.value.IntegerField.CLASS<>(group.get());
        count.setIndex("count"); group.get().members().add(count); count.get().setCursor(cursor);
      }
      if (customCase) {
        OBJECT.CLASS<OBJECT> rows = new OBJECT.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
        data.setIndex("data"); rows.get().members().add(data);
        customSource = new SimpleSource(rows.get()) {
          @Override public void open() {
            super.open(); data.get().z8_set(new org.zenframework.z8.server.types.string("value"),
                                             new org.zenframework.z8.server.types.integer(123));
          }
        };
      }
      if (jsonCase) {
        org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<org.zenframework.z8.server.base.json.parser.JsonArray> rows =
            new org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> item =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(null);
        item.get().z8_set(new org.zenframework.z8.server.types.string("title"), new org.zenframework.z8.server.types.string("Ada 😀"));
        item.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(42));
        rows.get().z8_add(item); customSource = new JsonSource(rows.get());
      }
      if (queryCase) {
        FakeQueryClass q = new FakeQueryClass(context); q.setIndex("q"); context.members().add(q);
        for (String name : new String[] {"amount", "ignored", "extra"}) {
          org.zenframework.z8.server.base.table.value.IntegerField.CLASS<org.zenframework.z8.server.base.table.value.IntegerField> field =
              new org.zenframework.z8.server.base.table.value.IntegerField.CLASS<>(q.get());
          field.setIndex(name); q.get().members().add(field);
          if ("extra".equals(name)) q.get().extraFields.add(field);
        }
        customSource = new QuerySource(q.get());
      }
      if (multipleCase) {
        final int[] order = {0};
        for (int i = 0; i < 2; ++i) {
          OBJECT.CLASS<OBJECT> node = new OBJECT.CLASS<>(context);
          node.setIndex(i == 0 ? "left" : "right"); context.members().add(node);
          final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
              new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(node.get());
          data.setIndex("data"); node.get().members().add(data);
          orderedSources[i] = new SimpleSource(node.get()) {
            @Override public void open() {
              super.open(); data.get().z8_set(new org.zenframework.z8.server.types.string("value"),
                                               new org.zenframework.z8.server.types.integer(++order[0]));
            }
          };
        }
      }
      PoiReport report = new PoiReport(new ReportOptions()).setContext(context);
      boolean constants = args.length > 3 && "constants".equals(args[3]);
      boolean parameters = args.length > 3 && "parameters".equals(args[3]);
      boolean dates = args.length > 3 && "dates".equals(args[3]);
      Range child = new Range().setSource(customCase || jsonCase || queryCase ? customSource : SimpleSource.newDefault())
          .setBlock(customCase ? "A1:D1" : fieldCase || jsonCase || queryCase ? "A1:E1" : dates ? "A1:J1" : constants ? "A1:G1" : parameters || contextCase ? "A1:E1" : "$A$1:A1")
          .setBoundaries(customCase ? "A1:D1" : fieldCase || jsonCase || queryCase ? "A1:E1" : dates ? "A1:J1" : constants ? "A1:G1" : parameters || contextCase ? "A1:E1" : "A1:B2");
      if (multipleCase) {
        report.addRange(0, new Range().setSource(orderedSources[1]).setBlock("C1").setBoundaries("C1"));
        report.addRange(0, new Range().setSource(orderedSources[0]).setBlock("A1").setBoundaries("A1"));
      } else report.addRange(0, child);
      if (args.length > 3 && "rename".equals(args[3])) original.setSheetName(0, "Отчёт \\uD83D\\uDE00");
      SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
      report.getRange(0).apply(modifier); modifier.close();
      if (constants || parameters || contextCase || dates || fieldCase || customCase || jsonCase || queryCase || multipleCase) {
        for (int i = 0; i < (outsideCase ? 4 : multipleCase ? 3 : customCase ? 4 : dates ? 10 : constants ? 7 : 5); ++i) {
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(0).getRow(0).getCell(i);
          org.apache.poi.ss.usermodel.Cell result = actual.getSheetAt(0).getRow(0).getCell(i);
          if (expected.getCellType() != result.getCellType()) throw new AssertionError("cell type differs at " + i);
          switch (expected.getCellType()) {
            case org.apache.poi.ss.usermodel.Cell.CELL_TYPE_NUMERIC:
              if (expected.getNumericCellValue() != result.getNumericCellValue()) throw new AssertionError("number differs at " + i + ": " + expected.getNumericCellValue() + " != " + result.getNumericCellValue()); break;
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
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/context.xlsx"), str(working / "context.xlsx"), str(config), "context"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for name in ("dates", "dates1904"):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + name + ".xlsx")), str(working / (name + ".xlsx")), str(config), "dates"],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/fields.xlsx"), str(working / "fields.xlsx"), str(config), "fields"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/custom.xlsx"), str(working / "custom.xlsx"), str(config), "custom"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/json.xlsx"), str(working / "json.xlsx"), str(config), "json"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/query.xlsx"), str(working / "query.xlsx"), str(config), "query"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/multi-range.xlsx"), str(working / "multi-range.xlsx"), str(config), "multiple"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/outside-range.xlsx"), str(working / "outside-range.xlsx"), str(config), "outside"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
print("POI static report template, naming and transaction verified")
