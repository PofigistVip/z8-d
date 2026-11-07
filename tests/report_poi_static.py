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
    public static file expanded() { ExpandedReport report; return report.run(guid.Null); }
    public static file expandedInline() { ExpandedInlineReport report; return report.run(guid.Null); }
    public static file expandedOccupied() { ExpandedOccupiedReport report; return report.run(guid.Null); }
    public static file expandedStatic() { ExpandedStaticReport report; return report.run(guid.Null); }
    public static file expandedFormula() { ExpandedFormulaReport report; return report.run(guid.Null); }
    public static file expandedMetadata() { ExpandedMetadataReport report; return report.run(guid.Null); }
    public static file expandedRich() { ExpandedRichReport report; return report.run(guid.Null); }
    public static file expandedCustom() { ExpandedCustomReport report; return report.run(guid.Null); }
    public static file repeatRange() { RepeatRangeReport report; return report.run(guid.Null); }
    public static file jsonInlineRange() { JsonInlineRangeReport report; return report.run(guid.Null); }
    public static file expandedInlineNumber() { ExpandedInlineNumberReport report; return report.run(guid.Null); }
    public static file expandedInlineConstant() { ExpandedInlineConstantReport report; return report.run(guid.Null); }
    public static file expandedOtherColumns() { ExpandedOtherColumnsReport report; return report.run(guid.Null); }
    public static file expandedRowHeight() { ExpandedRowHeightReport report; return report.run(guid.Null); }
    public static file expandedInlineTarget() { ExpandedInlineTargetReport report; return report.run(guid.Null); }
    public static file expandedMissingSource() { ExpandedMissingSourceReport report; return report.run(guid.Null); }
    public static file expandedTwoRows() { ExpandedTwoRowsReport report; return report.run(guid.Null); }
    public static file expandedEmptyRow() { ExpandedEmptyRowReport report; return report.run(guid.Null); }
    public static file expandedHorizontal() { ExpandedHorizontalReport report; return report.run(guid.Null); }
    public static file expandedSharedFormula() { ExpandedSharedFormulaReport report; return report.run(guid.Null); }
    public static file expandedComplexFormula() { ExpandedComplexFormulaReport report; return report.run(guid.Null); }
    public static file expandedInvalidFormula() { ExpandedInvalidFormulaReport report; return report.run(guid.Null); }
    public static file expandedParenthesized() { ExpandedParenthesizedReport report; return report.run(guid.Null); }
    public static file expandedUnknownFunction() { ExpandedUnknownFunctionReport report; return report.run(guid.Null); }
    public static file expandedFunctions() { ExpandedFunctionsReport report; return report.run(guid.Null); }
    public static file mergedInside() { MergedInsideReport report; return report.run(guid.Null); }
    public static file mergedInsideStatic() { MergedInsideStaticReport report; return report.run(guid.Null); }
    public static file expandedMerged() { ExpandedMergedReport report; return report.run(guid.Null); }
    public static file mergedOverlap() { MergedOverlapReport report; return report.run(guid.Null); }
    public static file expandedHorizontalMerged() { ExpandedHorizontalMergedReport report; return report.run(guid.Null); }
    public static file expandedMergedFormula() { ExpandedMergedFormulaReport report; return report.run(guid.Null); }
    public static file expandedFooter() { ExpandedFooterReport report; return report.run(guid.Null); }
    public static file expandedSparseFooter() { ExpandedSparseFooterReport report; return report.run(guid.Null); }
    public static file expandedSparseFormula() { ExpandedSparseFormulaReport report; return report.run(guid.Null); }
    public static file expandedSparseSharedFormula() { ExpandedSparseSharedFormulaReport report; return report.run(guid.Null); }
    public static file expandedSparseChainFormula() { ExpandedSparseChainFormulaReport report; return report.run(guid.Null); }
    public static file expandedFooterConflict() { ExpandedFooterConflictReport report; return report.run(guid.Null); }
    public static file expandedHorizontalFooter() { ExpandedHorizontalFooterReport report; return report.run(guid.Null); }
    public static file expandedMultiFooter() { ExpandedMultiFooterReport report; return report.run(guid.Null); }
    public static file expandedHorizontalMultiFooter() { ExpandedHorizontalMultiFooterReport report; return report.run(guid.Null); }
    public static file expandedSparseBlock() { ExpandedSparseBlockReport report; return report.run(guid.Null); }
    public static file expandedHeaderFooter() { ExpandedHeaderFooterReport report; return report.run(guid.Null); }
    public static file expandedHorizontalHeader() { ExpandedHorizontalHeaderReport report; return report.run(guid.Null); }
    public static file expandedSideConflict() { ExpandedSideConflictReport report; return report.run(guid.Null); }
    public static file expandedHorizontalSideConflict() { ExpandedHorizontalSideConflictReport report; return report.run(guid.Null); }
    public static file multipleSheets() { MultipleSheetReport report; return report.run(guid.Null); }
    public static file multipleSheetsRename() { MultipleSheetRenameReport report; return report.run(guid.Null); }
    public static file multipleSheetsBothRename() { MultipleSheetBothRenameReport report; return report.run(guid.Null); }
    public static file multipleSheetsDuplicate() { MultipleSheetDuplicateReport report; return report.run(guid.Null); }
    public static file cloneSheets() { CloneSheetsReport report; return report.run(guid.Null); }
    public static file cloneHighSheet() { CloneHighSheetReport report; return report.run(guid.Null); }
    public static file cloneHighMultiple() { CloneHighMultipleReport report; return report.run(guid.Null); }
    public static file cloneHighRenameConflict() { CloneHighRenameConflictReport report; return report.run(guid.Null); }
    public static file nestedSimple() { NestedSimpleReport report; return report.run(guid.Null); }
    public static file nestedImplicitSingle() { NestedImplicitSingleReport report; return report.run(guid.Null); }
    public static file nestedImplicitSiblings() { NestedImplicitSiblingsReport report; return report.run(guid.Null); }
    public static file nestedImplicitInvalid() { NestedImplicitInvalidReport report; return report.run(guid.Null); }
    public static file nestedUnsupported() { NestedUnsupportedReport report; return report.run(guid.Null); }
    public static file nestedText() { NestedTextReport report; return report.run(guid.Null); }
    public static file nestedEval() { NestedEvalReport report; return report.run(guid.Null); }
    public static file nestedCascade() { NestedCascadeReport report; return report.run(guid.Null); }
    public static file nestedDeep() { NestedDeepReport report; return report.run(guid.Null); }
    public static file nestedDeepImplicit() { NestedDeepImplicitReport report; return report.run(guid.Null); }
    public static file nestedParent() { NestedParentReport report; return report.run(guid.Null); }
    public static NestedParentQueryReport createNestedParentQuery() { NestedParentQueryReport report; return report; }
    public static QueryRows nestedParentQuery(NestedParentQueryReport report) { return report.q; }
    public static file runNestedParentQuery(NestedParentQueryReport report) { return report.run(guid.Null); }
    public static file nestedParentJson() { NestedParentJsonReport report; return report.run(guid.Null); }
    public static file nestedParentJsonEmpty() { NestedParentJsonEmptyReport report; return report.run(guid.Null); }
    public static file nestedParentJsonMany() { NestedParentJsonManyReport report; return report.run(guid.Null); }
    public static file nestedParentMany() { NestedParentManyReport report; return report.run(guid.Null); }
    public static NestedParentFailReport nestedParentFail() { NestedParentFailReport report; return report; }
    public static file runNestedParentFail(NestedParentFailReport report) { return report.run(guid.Null); }
    public static int nestedParentFailClosed(NestedParentFailReport report) { return report.parentRows.closed; }
    public static file nestedCycle() { NestedCycleReport report; return report.run(guid.Null); }
    public static file nestedSourceReuse() { NestedSourceReuseReport report; return report.run(guid.Null); }
    public static file nestedMany() { NestedManyReport report; return report.run(guid.Null); }
    public static file nestedSiblings() { NestedSiblingsReport report; return report.run(guid.Null); }
    public static file nestedOverlap() { NestedOverlapReport report; return report.run(guid.Null); }
    public static file nestedThree() { NestedThreeReport report; return report.run(guid.Null); }
    public static file nestedThreeVertical() { NestedThreeVerticalReport report; return report.run(guid.Null); }
    public static file nestedThreeUnsupported() { NestedThreeUnsupportedReport report; return report.run(guid.Null); }
    public static file cloneTooManySheets() { CloneTooManySheetsReport report; return report.run(guid.Null); }
    public static file cloneUnsupported() { CloneUnsupportedReport report; return report.run(guid.Null); }
    public static file cloneSuffix() { CloneSuffixReport report; return report.run(guid.Null); }
    public static file cloneLong() { CloneLongReport report; return report.run(guid.Null); }
    public static file cloneExisting() { CloneExistingReport report; return report.run(guid.Null); }
    public static file cloneViews() { CloneViewsReport report; return report.run(guid.Null); }
    public static file cloneSetup() { CloneSetupReport report; return report.run(guid.Null); }
    public static file clonePrint() { ClonePrintReport report; return report.run(guid.Null); }
    public static file cloneFilter() { CloneFilterReport report; return report.run(guid.Null); }
    public static file cloneNamed() { CloneNamedReport report; return report.run(guid.Null); }
    public static file cloneNamedRename() { CloneNamedRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedOriginalRename() { CloneNamedOriginalRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedUnsupportedRename() { CloneNamedUnsupportedRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedQuotedRename() { CloneNamedQuotedRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedDigitRename() { CloneNamedDigitRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedCellRename() { CloneNamedCellRenameReport report; return report.run(guid.Null); }
    public static file cloneNamedRussianRename() { CloneNamedRussianRenameReport report; return report.run(guid.Null); }
    public static file collectionRange() { CollectionRangeReport report; return report.run(guid.Null); }
    public static file mapValueRange() { MapValueRangeReport report; return report.run(guid.Null); }
    public static file mapDerivedRange() { MapDerivedRangeReport report; return report.run(guid.Null); }
    public static int orderedCount() { return OrderedRows.sequence; }
    public static file expandedMultipleSheets() { ExpandedMultipleSheetReport report; return report.run(guid.Null); }
    public static file emptyFooter() { EmptyFooterReport report; return report.run(guid.Null); }
    public static file emptyHorizontalFooter() { EmptyHorizontalFooterReport report; return report.run(guid.Null); }
    public static file emptyMultiFooter() { EmptyMultiFooterReport report; return report.run(guid.Null); }
    public static file emptyHorizontalMultiFooter() { EmptyHorizontalMultiFooterReport report; return report.run(guid.Null); }
    public static file emptySparseFooter() { EmptySparseFooterReport report; return report.run(guid.Null); }
    public static file expandedMultiSide() { ExpandedMultiSideReport report; return report.run(guid.Null); }
    public static file expandedHorizontalMultiSide() { ExpandedHorizontalMultiSideReport report; return report.run(guid.Null); }
    public static file emptySideFooter() { EmptySideFooterReport report; return report.run(guid.Null); }
    public static file emptyHorizontalSideFooter() { EmptyHorizontalSideFooterReport report; return report.run(guid.Null); }
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
            ("CollectionRangeReport", "collection", "A1:I1", "A1:I1"),
            ("MapValueRangeReport", "map-value", "A1:D1", "A1:D1"),
            ("MapDerivedRangeReport", "map-derived", "A1", "A1"),
            ("ConstantCommentRangeReport", "constant-comment", "A1:G1", "A1:G1"),
            ("ParametersRangeReport", "parameters", "A1:E1", "A1:E1"),
            ("DateRangeReport", "dates", "A1:J1", "A1:J1"),
            ("Date1904RangeReport", "dates1904", "A1:J1", "A1:J1"),
            ("RepeatRangeReport", "repeat", "A1", "A1"),
            ("MergedInsideReport", "merged-inside", "A1:B1", "A1:B1"),
            ("MergedInsideStaticReport", "merged", "A1:B1", "A1:B1"),
            ("MergedOverlapReport", "merged-overlap", "A1:C1", "A1:C1"),
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
    [address "A1:O1"] [boundaries "A1:O1"] Range region;
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
    (source / "JsonInlineRangeReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class JsonInlineRangeReport extends Report {
    engine = Report.POI; template = "json-inline";
    JsonArray rows; objects = {rows};
    [address "A1"] [boundaries "A1"] Range region;
    region.source = rows; ranges = {region};
    virtual protected void prepare(guid recordId) { JsonObject item; item.set("title", "Ada"); rows.add(item); }
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
    (source / "MultipleSheetReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class MultipleSheetReport extends Report {
    engine = Report.POI; template = "multi-sheet";
    OrderedRows left; OrderedRows right; objects = {left, right};
    [sheet "0"] [address "A1"] [boundaries "A1"] Range first;
    [sheet "1"] [address "A1"] [boundaries "A1"] Range second;
    first.source = left; second.source = right; ranges = {second, first};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "MultipleSheetRenameReport.bl").write_text(
        (source / "MultipleSheetReport.bl").read_text(encoding="utf-8")
        .replace("MultipleSheetReport", "MultipleSheetRenameReport").replace('[sheet "1"]', '[sheet "1"] [sheetName "Renamed"]'), encoding="utf-8")
    (source / "MultipleSheetBothRenameReport.bl").write_text(
        (source / "MultipleSheetReport.bl").read_text(encoding="utf-8")
        .replace("MultipleSheetReport", "MultipleSheetBothRenameReport").replace('[sheet "0"]', '[sheet "0"] [sheetName "First renamed"]')
        .replace('[sheet "1"]', '[sheet "1"] [sheetName "Second renamed"]'), encoding="utf-8")
    (source / "MultipleSheetDuplicateReport.bl").write_text(
        (source / "MultipleSheetReport.bl").read_text(encoding="utf-8")
        .replace("MultipleSheetReport", "MultipleSheetDuplicateReport").replace('[sheet "1"]', '[sheet "1"] [sheetName "Sheet1"]'), encoding="utf-8")
    (source / "CloneSheetsReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class CloneSheetsReport extends Report {
    engine = Report.POI; template = "constant";
    [sheet "0"] [address "A1"] [boundaries "A1"] Range first;
    [sheet "2"] [address "A1"] [boundaries "A1"] [sheetName "Final"] Range second;
    ranges = {second, first};
}''', encoding="utf-8")
    (source / "CloneUnsupportedReport.bl").write_text(
        (source / "CloneSheetsReport.bl").read_text(encoding="utf-8")
        .replace("CloneSheetsReport", "CloneUnsupportedReport").replace('template = "constant"', 'template = "clone-unsupported"'), encoding="utf-8")
    (source / "CloneHighSheetReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class CloneHighSheetReport extends Report {
    engine = Report.POI; template = "constant";
    [sheet "16"] [sheetName "Final"] [address "A1"] [boundaries "A1"] Range region;
    ranges = {region};
}''', encoding="utf-8")
    (source / "CloneTooManySheetsReport.bl").write_text(
        (source / "CloneHighSheetReport.bl").read_text(encoding="utf-8")
        .replace("CloneHighSheetReport", "CloneTooManySheetsReport").replace('[sheet "16"]', '[sheet "257"]'), encoding="utf-8")
    (source / "CloneHighMultipleReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class CloneHighMultipleReport extends Report {
    engine = Report.POI; template = "ordered-high";
    OrderedRows rows; objects = {rows};
    [sheet "0"] [address "A1"] [boundaries "A1"] Range first;
    [sheet "16"] [address "A1"] [boundaries "A1"] Range second;
    first.source = rows; second.source = rows; ranges = {second, first};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "CloneHighRenameConflictReport.bl").write_text(
        (source / "CloneHighMultipleReport.bl").read_text(encoding="utf-8")
        .replace("CloneHighMultipleReport", "CloneHighRenameConflictReport")
        .replace('[sheet "0"]', '[sheet "0"] [sheetName "Renamed"]')
        .replace('[sheet "16"]', '[sheet "16"] [sheetName "Sheet1"]'), encoding="utf-8")
    (source / "NestedSimpleReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class NestedSimpleReport extends Report {
    engine = Report.POI; template = "nested-simple";
    OrderedRows rows; objects = {rows};
    [address "A1:B1"] [boundaries "A1:B1"] Range outer;
    [sheet "99"] [address "B1"] [boundaries "B1"] Range inner;
    inner.source = rows; outer.ranges = {inner}; ranges = {outer};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "NestedImplicitSingleReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedImplicitSingleReport").replace('[address "B1"] [boundaries "B1"]', '[address "A1:B1"]'), encoding="utf-8")
    (source / "NestedImplicitInvalidReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedImplicitInvalidReport").replace('[address "B1"] [boundaries "B1"]', '[address "B1"]'), encoding="utf-8")
    (source / "NestedUnsupportedReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedUnsupportedReport").replace('[address "B1"] [boundaries "B1"]', '[address "A1"] [boundaries "A1"]'), encoding="utf-8")
    (source / "NestedTextRows.bl").write_text('''public class NestedTextRows extends OrderedRows {
    virtual public void open() { data.set("value", "обычный текст"); }
}''', encoding="utf-8")
    (source / "NestedTextReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedTextReport").replace("OrderedRows rows;", "NestedTextRows rows;"), encoding="utf-8")
    (source / "NestedEvalRows.bl").write_text('''public class NestedEvalRows extends OrderedRows {
    virtual public void open() { data.set("value", "${1+2}"); }
}''', encoding="utf-8")
    (source / "NestedEvalReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedEvalReport").replace("OrderedRows rows;", "NestedEvalRows rows;"), encoding="utf-8")
    (source / "NestedCascadeRows.bl").write_text('''public class NestedCascadeRows extends OrderedRows {
    virtual public void open() { data.set("value", "${rows.data.after}"); data.set("after", "${1+2}"); }
}''', encoding="utf-8")
    (source / "NestedCascadeReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedCascadeReport").replace("OrderedRows rows;", "NestedCascadeRows rows;"), encoding="utf-8")
    (source / "NestedDeepRows.bl").write_text('''public class NestedDeepRows extends OrderedRows {
    virtual public void open() {
        data.set("value", "${rows.data.step1}"); data.set("step1", "${rows.data.step2}"); data.set("step2", "${1+2}");
    }
}''', encoding="utf-8")
    (source / "NestedDeepReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class NestedDeepReport extends Report {
    engine = Report.POI; template = "nested-deep";
    NestedDeepRows rows; objects = {rows};
    [address "A1:C1"] [boundaries "A1:C1"] Range outer;
    [address "B1:C1"] [boundaries "B1:C1"] Range middle;
    [address "C1"] [boundaries "C1"] Range inner;
    inner.source = rows; middle.ranges = {inner}; outer.ranges = {middle}; ranges = {outer};
}''', encoding="utf-8")
    (source / "NestedDeepImplicitReport.bl").write_text(
        (source / "NestedDeepReport.bl").read_text(encoding="utf-8")
        .replace("NestedDeepReport", "NestedDeepImplicitReport")
        .replace('[address "B1:C1"] [boundaries "B1:C1"]', '[address "A1:C1"]')
        .replace('[address "C1"] [boundaries "C1"]', '[address "A1:C1"]'), encoding="utf-8")
    (source / "NestedCycleReport.bl").write_text(
        (source / "NestedDeepReport.bl").read_text(encoding="utf-8")
        .replace("NestedDeepReport", "NestedCycleReport").replace('inner.source = rows;', 'inner.source = rows; inner.ranges = {outer};'), encoding="utf-8")
    (source / "NestedSourceReuseReport.bl").write_text(
        (source / "NestedDeepReport.bl").read_text(encoding="utf-8")
        .replace("NestedDeepReport", "NestedSourceReuseReport").replace('inner.source = rows;', 'inner.source = outer.source;'), encoding="utf-8")
    (source / "NestedParentReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class NestedParentReport extends Report {
    engine = Report.POI; template = "nested-parent";
    OrderedRows parentRows; OrderedRows childRows; objects = {parentRows, childRows};
    [address "A1:B1"] [boundaries "A1:B1"] Range outer;
    [address "B1"] [boundaries "B1"] Range inner;
    outer.source = parentRows; inner.source = childRows; outer.ranges = {inner}; ranges = {outer};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "NestedParentManyReport.bl").write_text(
        (source / "NestedParentReport.bl").read_text(encoding="utf-8")
        .replace("NestedParentReport", "NestedParentManyReport").replace('OrderedRows parentRows;', 'ReportRows parentRows; parentRows.n = 2;'), encoding="utf-8")
    (source / "NestedParentFailReport.bl").write_text(
        (source / "NestedParentReport.bl").read_text(encoding="utf-8")
        .replace("NestedParentReport", "NestedParentFailReport").replace('OrderedRows parentRows;', 'public ReportRows parentRows; parentRows.fail = true;'), encoding="utf-8")
    (source / "NestedParentQueryReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class NestedParentQueryReport extends Report {
    engine = Report.POI; template = "nested-parent-query";
    public QueryRows q; OrderedRows childRows; objects = {q, childRows};
    [address "A1:B1"] [boundaries "A1:B1"] Range outer;
    [address "B1"] [boundaries "B1"] Range inner;
    outer.source = q; inner.source = childRows; outer.ranges = {inner}; ranges = {outer};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "NestedParentJsonReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class NestedParentJsonReport extends Report {
    engine = Report.POI; template = "nested-parent-json";
    JsonArray parentRows; OrderedRows childRows; objects = {parentRows, childRows};
    [address "A1:B1"] [boundaries "A1:B1"] Range outer;
    [address "B1"] [boundaries "B1"] Range inner;
    outer.source = parentRows; inner.source = childRows; outer.ranges = {inner}; ranges = {outer};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; JsonObject item; item.set("amount", 42); parentRows.add(item); }
}''', encoding="utf-8")
    (source / "NestedParentJsonEmptyReport.bl").write_text(
        (source / "NestedParentJsonReport.bl").read_text(encoding="utf-8")
        .replace("NestedParentJsonReport", "NestedParentJsonEmptyReport").replace('parentRows.add(item);', ''), encoding="utf-8")
    (source / "NestedParentJsonManyReport.bl").write_text(
        (source / "NestedParentJsonReport.bl").read_text(encoding="utf-8")
        .replace("NestedParentJsonReport", "NestedParentJsonManyReport").replace('parentRows.add(item);', 'parentRows.add(item); parentRows.add(item);'), encoding="utf-8")
    (source / "NestedSiblingsReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class NestedSiblingsReport extends Report {
    engine = Report.POI; template = "nested-siblings";
    OrderedRows rows; objects = {rows};
    [address "A1:C1"] [boundaries "A1:C1"] Range outer;
    [address "B1"] [boundaries "B1"] Range left;
    [address "C1"] [boundaries "C1"] Range right;
    left.source = rows; right.source = rows; outer.ranges = {right, left}; ranges = {outer};
    virtual protected void prepare(guid recordId) { OrderedRows.sequence = 0; }
}''', encoding="utf-8")
    (source / "NestedImplicitSiblingsReport.bl").write_text(
        (source / "NestedSiblingsReport.bl").read_text(encoding="utf-8")
        .replace("NestedSiblingsReport", "NestedImplicitSiblingsReport").replace(' [boundaries "B1"]', '').replace(' [boundaries "C1"]', ''), encoding="utf-8")
    (source / "NestedOverlapReport.bl").write_text(
        (source / "NestedSiblingsReport.bl").read_text(encoding="utf-8")
        .replace("NestedSiblingsReport", "NestedOverlapReport").replace('[address "C1"] [boundaries "C1"]', '[address "B1"] [boundaries "B1"]'), encoding="utf-8")
    (source / "NestedThreeReport.bl").write_text(
        (source / "NestedSiblingsReport.bl").read_text(encoding="utf-8")
        .replace("NestedSiblingsReport", "NestedThreeReport").replace("A1:C1", "A1:D1").replace("nested-siblings", "nested-three")
        .replace('left.source = rows;', '[address "D1"] [boundaries "D1"] Range third; third.source = rows; left.source = rows;')
        .replace('outer.ranges = {right, left}', 'outer.ranges = {right, third, left}'), encoding="utf-8")
    (source / "NestedThreeVerticalReport.bl").write_text(
        (source / "NestedThreeReport.bl").read_text(encoding="utf-8")
        .replace("NestedThreeReport", "NestedThreeVerticalReport").replace("nested-three", "nested-three-vertical")
        .replace("A1:D1", "A1:A4").replace('"B1"', '"A2"').replace('"C1"', '"A3"').replace('"D1"', '"A4"'), encoding="utf-8")
    (source / "NestedThreeUnsupportedReport.bl").write_text(
        (source / "NestedThreeReport.bl").read_text(encoding="utf-8")
        .replace("NestedThreeReport", "NestedThreeUnsupportedReport").replace("A1:D1", "A1:D2")
        .replace('[address "D1"] [boundaries "D1"]', '[address "D2"] [boundaries "D2"]'), encoding="utf-8")
    (source / "NestedManyReport.bl").write_text(
        (source / "NestedSimpleReport.bl").read_text(encoding="utf-8")
        .replace("NestedSimpleReport", "NestedManyReport").replace("OrderedRows rows;", "ReportRows rows; rows.n = 2;"), encoding="utf-8")
    for name, template in (("CloneSuffixReport", "clone-suffix"), ("CloneLongReport", "clone-long"), ("CloneExistingReport", "clone-existing"), ("CloneViewsReport", "clone-views"), ("CloneSetupReport", "clone-setup"), ("ClonePrintReport", "clone-print"), ("CloneFilterReport", "clone-filter"), ("CloneNamedReport", "clone-named"), ("CloneNamedRenameReport", "clone-named"), ("CloneNamedOriginalRenameReport", "clone-named"), ("CloneNamedUnsupportedRenameReport", "clone-named"), ("CloneNamedQuotedRenameReport", "clone-named"), ("CloneNamedDigitRenameReport", "clone-named"), ("CloneNamedCellRenameReport", "clone-named"), ("CloneNamedRussianRenameReport", "clone-named")):
        content = (source / "CloneSheetsReport.bl").read_text(encoding="utf-8").replace("CloneSheetsReport", name).replace('template = "constant"', 'template = "' + template + '"')
        if name == "CloneExistingReport": content = content.replace('[sheet "2"]', '[sheet "3"]')
        if name == "CloneNamedReport": content = content.replace(' [sheetName "Final"]', '')
        if name == "CloneNamedOriginalRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "Renamed"]')
        if name == "CloneNamedUnsupportedRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "漢"]')
        if name == "CloneNamedQuotedRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "New Name"]')
        if name == "CloneNamedDigitRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "Sheet123"]')
        if name == "CloneNamedCellRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "A1"]')
        if name == "CloneNamedRussianRenameReport": content = content.replace('[sheet "0"]', '[sheet "0"] [sheetName "Лист"]')
        (source / (name + ".bl")).write_text(content, encoding="utf-8")
    (source / "MissingBoundariesReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class MissingBoundariesReport extends Report {
    engine = Report.POI; template = "multi-range";
    [address "A1"] Range first; [address "C1"] Range second;
    ranges = {first, second};
}''', encoding="utf-8")
    for name, template in (("ExpandedReport", "expanded"), ("ExpandedInlineReport", "expanded-inline"),
                           ("ExpandedOccupiedReport", "expanded-occupied"), ("ExpandedStaticReport", "expanded-static"),
                           ("ExpandedFormulaReport", "expanded-formula"), ("ExpandedMetadataReport", "expanded-metadata"),
                           ("ExpandedRichReport", "expanded-rich"), ("ExpandedInlineNumberReport", "expanded-inline-number"),
                           ("ExpandedInlineConstantReport", "expanded-inline-constant"),
                           ("ExpandedOtherColumnsReport", "expanded-other-columns"), ("ExpandedRowHeightReport", "expanded-row-height"),
                           ("ExpandedInlineTargetReport", "expanded-inline-target"), ("ExpandedMissingSourceReport", "expanded-missing-source"),
                           ("ExpandedSharedFormulaReport", "expanded-shared-formula"), ("ExpandedComplexFormulaReport", "expanded-complex-formula"),
                           ("ExpandedInvalidFormulaReport", "expanded-invalid-formula"), ("ExpandedParenthesizedReport", "expanded-parenthesized"),
                           ("ExpandedUnknownFunctionReport", "expanded-unknown-function"), ("ExpandedFunctionsReport", "expanded-functions")):
        (source / (name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    JsonArray rows; objects = {rows};
    [address "A1:D1"] [boundaries "A1:D1"] Range region;
    region.source = rows; ranges = {region};
    virtual protected void prepare(guid recordId) {
        JsonObject one; one.set("amount", 10); one.set("title", "First"); rows.add(one);
        JsonObject two; two.set("amount", 20); two.set("title", "Второй 😀"); rows.add(two);
        JsonObject three; three.set("amount", 30); three.set("title", "Third"); rows.add(three);
    }
}''' % (name, template), encoding="utf-8")
    (source / "ExpandedMultipleSheetReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class ExpandedMultipleSheetReport extends Report {
    engine = Report.POI; template = "expanded-multi-sheet";
    JsonArray rows; OrderedRows right; objects = {rows, right};
    [sheet "0"] [address "A1:D1"] [boundaries "A1:D1"] Range first;
    [sheet "1"] [address "A1"] [boundaries "A1"] Range second;
    first.source = rows; second.source = right; ranges = {second, first};
    virtual protected void prepare(guid recordId) {
        OrderedRows.sequence = 0;
        JsonObject one; one.set("amount", 10); one.set("title", "First"); rows.add(one);
        JsonObject two; two.set("amount", 20); two.set("title", "Второй 😀"); rows.add(two);
        JsonObject three; three.set("amount", 30); three.set("title", "Third"); rows.add(three);
    }
}''', encoding="utf-8")
    (source / "ThreeRows.bl").write_text('''import org.zenframework.z8.base.form.report.CustomData;
public class ThreeRows extends CustomData { virtual public int count() { return 3; } }''', encoding="utf-8")
    (source / "ExpandedCustomReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
public class ExpandedCustomReport extends Report {
    engine = Report.POI; template = "expanded-custom";
    ThreeRows rows; objects = {rows};
    [address "A1:D1"] [boundaries "A1:D1"] Range region;
    region.source = rows; ranges = {region};
}''', encoding="utf-8")
    (source / "ExpandedTwoRowsReport.bl").write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonArray;
public class ExpandedTwoRowsReport extends Report {
    engine = Report.POI; template = "expanded-two";
    JsonArray rows; objects = {rows};
    [address "A1:B2"] [boundaries "A1:B2"] Range region;
    region.source = rows; ranges = {region};
    virtual protected void prepare(guid recordId) {
        JsonObject one; one.set("amount", 10); one.set("title", "First"); rows.add(one);
        JsonObject two; two.set("amount", 20); two.set("title", "Второй 😀"); rows.add(two);
        JsonObject three; three.set("amount", 30); three.set("title", "Third"); rows.add(three);
    }
}''', encoding="utf-8")
    (source / "ExpandedEmptyRowReport.bl").write_text(
        (source / "ExpandedTwoRowsReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedTwoRowsReport", "ExpandedEmptyRowReport").replace('template = "expanded-two"', 'template = "expanded-empty-row"'),
        encoding="utf-8")
    (source / "ExpandedMergedReport.bl").write_text(
        (source / "ExpandedReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedReport", "ExpandedMergedReport").replace('template = "expanded"', 'template = "expanded-merged"'),
        encoding="utf-8")
    (source / "ExpandedMergedFormulaReport.bl").write_text(
        (source / "ExpandedMergedReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedMergedReport", "ExpandedMergedFormulaReport").replace('template = "expanded-merged"', 'template = "expanded-merged-formula"'),
        encoding="utf-8")
    for name, template in (("ExpandedFooterReport", "expanded-footer"), ("ExpandedSparseFooterReport", "expanded-sparse-footer"),
                           ("ExpandedSparseFormulaReport", "expanded-sparse-formula"), ("ExpandedSparseSharedFormulaReport", "expanded-sparse-shared-formula"),
                           ("ExpandedSparseChainFormulaReport", "expanded-sparse-chain-formula"),
                           ("ExpandedFooterConflictReport", "expanded-footer-conflict"), ("ExpandedSparseBlockReport", "expanded-sparse-block")):
        (source / (name + ".bl")).write_text(
            (source / "ExpandedReport.bl").read_text(encoding="utf-8")
            .replace("ExpandedReport", name).replace('template = "expanded"', 'template = "' + template + '"')
            .replace('[boundaries "A1:D1"]', '[boundaries "A1:D2"]'), encoding="utf-8")
    (source / "ExpandedMultiFooterReport.bl").write_text(
        (source / "ExpandedFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedFooterReport", "ExpandedMultiFooterReport")
        .replace('template = "expanded-footer"', 'template = "expanded-multi-footer"')
        .replace('[boundaries "A1:D2"]', '[boundaries "A1:D4"]'), encoding="utf-8")
    (source / "ExpandedMultiSideReport.bl").write_text(
        (source / "ExpandedMultiFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedMultiFooterReport", "ExpandedMultiSideReport").replace('template = "expanded-multi-footer"', 'template = "expanded-multi-side"')
        .replace('[boundaries "A1:D4"]', '[boundaries "A1:E4"]'), encoding="utf-8")
    (source / "ExpandedHeaderFooterReport.bl").write_text(
        (source / "ExpandedFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedFooterReport", "ExpandedHeaderFooterReport")
        .replace('template = "expanded-footer"', 'template = "expanded-header-footer"')
        .replace('[address "A1:D1"]', '[address "A2:D2"]').replace('[boundaries "A1:D2"]', '[boundaries "A1:E3"]'), encoding="utf-8")
    (source / "ExpandedSideConflictReport.bl").write_text(
        (source / "ExpandedHeaderFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHeaderFooterReport", "ExpandedSideConflictReport")
        .replace('template = "expanded-header-footer"', 'template = "expanded-side-conflict"'), encoding="utf-8")
    (source / "ExpandedHorizontalReport.bl").write_text(
        (source / "ExpandedTwoRowsReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedTwoRowsReport", "ExpandedHorizontalReport")
        .replace('template = "expanded-two"', 'template = "expanded-horizontal"')
        .replace('[address "A1:B2"]', '[axis "1"] [address "A1:B2"]'), encoding="utf-8")
    (source / "ExpandedHorizontalMergedReport.bl").write_text(
        (source / "ExpandedHorizontalReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalReport", "ExpandedHorizontalMergedReport")
        .replace('template = "expanded-horizontal"', 'template = "expanded-horizontal-merged"'), encoding="utf-8")
    (source / "ExpandedHorizontalFooterReport.bl").write_text(
        (source / "ExpandedHorizontalReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalReport", "ExpandedHorizontalFooterReport")
        .replace('template = "expanded-horizontal"', 'template = "expanded-horizontal-footer"')
        .replace('[boundaries "A1:B2"]', '[boundaries "A1:C2"]'), encoding="utf-8")
    (source / "ExpandedHorizontalMultiFooterReport.bl").write_text(
        (source / "ExpandedHorizontalFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalFooterReport", "ExpandedHorizontalMultiFooterReport")
        .replace('template = "expanded-horizontal-footer"', 'template = "expanded-horizontal-multi-footer"')
        .replace('[boundaries "A1:C2"]', '[boundaries "A1:G2"]'), encoding="utf-8")
    (source / "ExpandedHorizontalMultiSideReport.bl").write_text(
        (source / "ExpandedHorizontalMultiFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalMultiFooterReport", "ExpandedHorizontalMultiSideReport")
        .replace('template = "expanded-horizontal-multi-footer"', 'template = "expanded-horizontal-multi-side"')
        .replace('[boundaries "A1:G2"]', '[boundaries "A1:G3"]'), encoding="utf-8")
    (source / "ExpandedHorizontalHeaderReport.bl").write_text(
        (source / "ExpandedHorizontalFooterReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalFooterReport", "ExpandedHorizontalHeaderReport")
        .replace('template = "expanded-horizontal-footer"', 'template = "expanded-horizontal-header"')
        .replace('[address "A1:B2"]', '[address "B1:C2"]').replace('[boundaries "A1:C2"]', '[boundaries "A1:D3"]'), encoding="utf-8")
    (source / "ExpandedHorizontalSideConflictReport.bl").write_text(
        (source / "ExpandedHorizontalHeaderReport.bl").read_text(encoding="utf-8")
        .replace("ExpandedHorizontalHeaderReport", "ExpandedHorizontalSideConflictReport")
        .replace('template = "expanded-horizontal-header"', 'template = "expanded-horizontal-side-conflict"'), encoding="utf-8")
    for name, template, address, boundaries, axis in (
            ("EmptyFooterReport", "expanded-footer", "A1:D1", "A1:D2", "0"),
            ("EmptySparseFooterReport", "expanded-sparse-footer", "A1:D1", "A1:D2", "0"),
            ("EmptySideFooterReport", "expanded-side-conflict", "A2:D2", "A1:E3", "0"),
            ("EmptyHorizontalSideFooterReport", "expanded-horizontal-side-conflict", "B1:C2", "A1:D3", "1"),
            ("EmptyHorizontalFooterReport", "expanded-horizontal-footer", "A1:B2", "A1:C2", "1"),
            ("EmptyMultiFooterReport", "expanded-multi-footer", "A1:D1", "A1:D4", "0"),
            ("EmptyHorizontalMultiFooterReport", "expanded-horizontal-multi-footer", "A1:B2", "A1:G2", "1")):
        (source / (name + ".bl")).write_text('''import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.json.JsonArray;
public class %s extends Report {
    engine = Report.POI; template = "%s";
    JsonArray rows; objects = {rows};
    [axis "%s"] [address "%s"] [boundaries "%s"] Range region;
    region.source = rows; ranges = {region};
}''' % (name, template, axis, address, boundaries), encoding="utf-8")
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
    for filename, sheet_name in (("clone-suffix", "X (7)"), ("clone-long", "ABCDEFGHIJKLMNOPQRSTUVWXYZ12345")):
        book = dict(constants)
        book["xl/workbook.xml"] = book["xl/workbook.xml"].replace('name="Sheet1"', 'name="' + sheet_name + '"')
        with zipfile.ZipFile(application / ("reports/" + filename + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in book.items(): archive.writestr(name, content)
    clone_existing = dict(constants)
    clone_existing["xl/workbook.xml"] = clone_existing["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="Second (3)"').replace('</sheets>', '<sheet name="Second (2)" sheetId="2" r:id="rId3"/></sheets>')
    clone_existing["xl/_rels/workbook.xml.rels"] = clone_existing["xl/_rels/workbook.xml.rels"].replace(
        '</Relationships>', '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
    clone_existing["[Content_Types].xml"] = clone_existing["[Content_Types].xml"].replace(
        '</Types>', '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    clone_existing["xl/worksheets/sheet2.xml"] = clone_existing["xl/worksheets/sheet1.xml"]
    with zipfile.ZipFile(application / "reports/clone-existing.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_existing.items(): archive.writestr(name, content)
    clone_views = dict(constants)
    clone_views["xl/worksheets/sheet1.xml"] = clone_views["xl/worksheets/sheet1.xml"].replace(
        "<sheetData>", '<sheetViews><sheetView workbookViewId="0" tabSelected="1" zoomScale="125"><selection activeCell="B2" sqref="B2"/></sheetView>'
        '<sheetView workbookViewId="1" tabSelected="1"/></sheetViews><sheetData>')
    with zipfile.ZipFile(application / "reports/clone-views.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_views.items():
            archive.writestr(name, content)
    clone_setup = dict(constants)
    clone_setup["xl/worksheets/sheet1.xml"] = clone_setup["xl/worksheets/sheet1.xml"].replace(
        '</worksheet>', '<pageSetup paperSize="9"/></worksheet>')
    with zipfile.ZipFile(application / "reports/clone-setup.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_setup.items(): archive.writestr(name, content)
    clone_print = dict(clone_setup)
    clone_print["xl/worksheets/sheet1.xml"] = clone_print["xl/worksheets/sheet1.xml"].replace(
        '<sheetData>', '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetData>').replace(
        '<pageSetup paperSize="9"/>', '<printOptions horizontalCentered="1"/><pageMargins left="0.5" right="0.5" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
        '<pageSetup paperSize="9"/><headerFooter><oddHeader>Confidential</oddHeader></headerFooter>')
    with zipfile.ZipFile(application / "reports/clone-print.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_print.items(): archive.writestr(name, content)
    clone_filter = dict(constants)
    clone_filter["xl/worksheets/sheet1.xml"] = clone_filter["xl/worksheets/sheet1.xml"].replace(
        '</worksheet>', '<autoFilter ref="A1:A4"><filterColumn colId="0"><filters><filter val="Example"/></filters></filterColumn></autoFilter></worksheet>')
    with zipfile.ZipFile(application / "reports/clone-filter.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_filter.items(): archive.writestr(name, content)
    clone_named = dict(clone_filter)
    clone_named["xl/workbook.xml"] = clone_named["xl/workbook.xml"].replace(
        '</workbook>', '<definedNames><definedName name="MyRange">Sheet1!$a$1:$a$4</definedName>'
        '<definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Sheet1!$A$1:$A$4</definedName>'
        '<definedName name="ColumnRange">Sheet1!$A:$B</definedName><definedName name="_xlnm.Print_Area" localSheetId="0">Sheet1!$A$1:$B$4</definedName>'
        '<definedName name="_xlnm.Print_Titles" localSheetId="0">Sheet1!$1:$1</definedName></definedNames></workbook>')
    with zipfile.ZipFile(application / "reports/clone-named.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_named.items(): archive.writestr(name, content)
    clone_unsupported = dict(constants)
    clone_unsupported["xl/worksheets/sheet1.xml"] = clone_unsupported["xl/worksheets/sheet1.xml"].replace(
        '</worksheet>', '<sheetProtection sheet="1"/></worksheet>')
    with zipfile.ZipFile(application / "reports/clone-unsupported.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in clone_unsupported.items(): archive.writestr(name, content)
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
    collection = dict(constants)
    collection["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="8" uniqueCount="8"><si><t>${'a,b'.split(',')}</t></si><si><t>items: ${'a,b'.split(',')}</t></si><si><t>${'a,b'.split(',').size()}</t></si><si><t>$a${1.25}</t></si><si><t>x$${1+2}y</t></si><si><t>cost $5 {literal}</t></si><si><t>${1+2</t></si><si><t>value ${1+2</t></si></sst>'''
    collection["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>${\'a,b\'.split(\',\')}</t></is></c>'
        '<c r="C1" t="s"><v>1</v></c><c r="D1" t="s"><v>2</v></c>'
        '<c r="E1" t="s"><v>3</v></c><c r="F1" t="s"><v>4</v></c><c r="G1" t="s"><v>5</v></c>'
        '<c r="H1" t="s"><v>6</v></c><c r="I1" t="s"><v>7</v></c>')
    with zipfile.ZipFile(application / "reports/collection.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in collection.items(): archive.writestr(name, content)
    map_value = dict(collection)
    map_value["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3"><si><t>${parameters}</t></si><si><t>values: ${parameters}</t></si><si><t>${parameters.size()}</t></si></sst>'''
    map_value["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>${parameters}</t></is></c>'
        '<c r="C1" t="s"><v>1</v></c><c r="D1" t="s"><v>2</v></c>')
    with zipfile.ZipFile(application / "reports/map-value.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in map_value.items(): archive.writestr(name, content)
    map_derived = dict(collection)
    map_derived["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1"><si><t>${('prefix ' + parameters).toUpperCase()}</t></si></sst>'''
    map_derived["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>0</v></c>')
    with zipfile.ZipFile(application / "reports/map-derived.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in map_derived.items(): archive.writestr(name, content)
    repeat = dict(parameters)
    repeat["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1"><si><t>${parameters['nested']}</t></si></sst>'''
    repeat["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>0</v></c>')
    with zipfile.ZipFile(application / "reports/repeat.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in repeat.items():
            archive.writestr(entry_name, content)
    json_inline = dict(entries)
    json_inline["xl/worksheets/sheet1.xml"] = original_sheet.replace("Example", "${rows.item.title}")
    with zipfile.ZipFile(application / "reports/json-inline.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in json_inline.items():
            archive.writestr(entry_name, content)
    context = dict(parameters)
    context["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="15" uniqueCount="15"><si><t>${info['title']}</t></si><si><t>${group.data.amount}</t></si><si><t>${parameters.foo}</t></si><si><t>Title: ${info.title}!</t></si><si><t>${info.missing}</t></si><si><t>${group ? 'yes' : 'no'}</t></si><si><t>${(group ?: info.missing).data.amount}</t></si><si><t>${"text"}</t></si><si><t>prefix ${"hi"}!</t></si><si><t>${'say "yes"'}</t></si><si><t>${«Привет»}</t></si><si><t>prefix ${„мир“}!</t></si><si><t>${.5}</t></si><si><t>${1e3}</t></si><si><t>${9L}</t></si></sst>'''
    context["xl/worksheets/sheet1.xml"] = context["xl/worksheets/sheet1.xml"].replace(
        '<c r="E1" t="s"><v>4</v></c>', '<c r="E1" t="s"><v>4</v></c><c r="F1" t="s"><v>5</v></c><c r="G1" t="s"><v>6</v></c><c r="H1" t="s"><v>7</v></c><c r="I1" t="s"><v>8</v></c><c r="J1" t="s"><v>9</v></c><c r="K1" t="s"><v>10</v></c><c r="L1" t="s"><v>11</v></c><c r="M1" t="s"><v>12</v></c><c r="N1" t="s"><v>13</v></c><c r="O1" t="s"><v>14</v></c>')
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
    custom["xl/worksheets/sheet1.xml"] = custom["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="2" ht="30" customHeight="1"><c r="A2"><v>77</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/custom.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in custom.items():
            archive.writestr(entry_name, content)
    json_source = dict(parameters)
    json_source["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${rows.item.title}</t></si><si><t>${rows.item.amount}</t></si><si><t>${rows.index}</t></si><si><t>${rows.sheet}</t></si><si><t>Title: ${rows.item.title}</t></si></sst>'''
    json_source["xl/worksheets/sheet1.xml"] = json_source["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="2" ht="30" customHeight="1"><c r="A2"><v>77</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/json.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in json_source.items():
            archive.writestr(entry_name, content)
    query = dict(parameters)
    query["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5" uniqueCount="5"><si><t>${q.amount}</t></si><si><t>${q . amount + 1}</t></si><si><t>Value: ${q.amount}</t></si><si><t>${q.index}</t></si><si><t>${'q.ignored'}</t></si></sst>'''
    query["xl/worksheets/sheet1.xml"] = query["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="2" ht="30" customHeight="1"><c r="A2"><v>77</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/query.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in query.items():
            archive.writestr(entry_name, content)
    multi = dict(parameters)
    multi["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>${left.data.value}</t></si><si><t>${right.data.value}</t></si></sst>'''
    multi["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>${10+20}</t></is></c><c r="C1" t="s"><v>1</v></c>')
    ordered_high = dict(parameters)
    ordered_high["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1"><si><t>${rows.data.value}</t></si></sst>'''
    ordered_high["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>0</v></c>')
    with zipfile.ZipFile(application / "reports/ordered-high.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in ordered_high.items(): archive.writestr(entry_name, content)
    nested_simple = dict(parameters)
    nested_simple["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>${1+2}</t></si><si><t>${rows.data.value}</t></si></sst>'''
    nested_simple["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>')
    with zipfile.ZipFile(application / "reports/nested-simple.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_simple.items(): archive.writestr(entry_name, content)
    nested_parent = dict(nested_simple)
    nested_parent["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2"><si><t>${parentRows.data.value}</t></si><si><t>${childRows.data.value}</t></si></sst>'''
    with zipfile.ZipFile(application / "reports/nested-parent.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_parent.items(): archive.writestr(entry_name, content)
    nested_parent_query = dict(nested_parent)
    nested_parent_query["xl/sharedStrings.xml"] = nested_parent["xl/sharedStrings.xml"].replace('parentRows.data.value', 'q.amount')
    with zipfile.ZipFile(application / "reports/nested-parent-query.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_parent_query.items(): archive.writestr(entry_name, content)
    nested_parent_json = dict(nested_parent)
    nested_parent_json["xl/sharedStrings.xml"] = nested_parent["xl/sharedStrings.xml"].replace('parentRows.data.value', 'parentRows.item.amount')
    with zipfile.ZipFile(application / "reports/nested-parent-json.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_parent_json.items(): archive.writestr(entry_name, content)
    nested_siblings = dict(nested_simple)
    nested_siblings["xl/worksheets/sheet1.xml"] = nested_simple["xl/worksheets/sheet1.xml"].replace(
        '<c r="B1" t="s"><v>1</v></c>', '<c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>1</v></c>')
    with zipfile.ZipFile(application / "reports/nested-siblings.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_siblings.items(): archive.writestr(entry_name, content)
    nested_deep = dict(nested_siblings)
    nested_deep["xl/worksheets/sheet1.xml"] = nested_siblings["xl/worksheets/sheet1.xml"].replace(
        '<c r="B1" t="s"><v>1</v></c>', '<c r="B1" t="s"><v>0</v></c>')
    with zipfile.ZipFile(application / "reports/nested-deep.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_deep.items(): archive.writestr(entry_name, content)
    nested_three = dict(nested_siblings)
    nested_three["xl/worksheets/sheet1.xml"] = nested_siblings["xl/worksheets/sheet1.xml"].replace(
        '<c r="C1" t="s"><v>1</v></c>', '<c r="C1" t="s"><v>1</v></c><c r="D1" t="s"><v>1</v></c>')
    with zipfile.ZipFile(application / "reports/nested-three.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_three.items(): archive.writestr(entry_name, content)
    nested_three_vertical = dict(nested_three)
    nested_three_vertical["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Example</t></is></c></row>',
        '<row r="1"><c r="A1" t="s"><v>0</v></c></row>' + ''.join(
            '<row r="%d"><c r="A%d" t="s"><v>1</v></c></row>' % (i, i) for i in range(2, 5)))
    with zipfile.ZipFile(application / "reports/nested-three-vertical.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in nested_three_vertical.items(): archive.writestr(entry_name, content)
    for filename in ("multi-range", "outside-range"):
        book = dict(multi)
        if filename == "outside-range":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('</row>', '<c r="D1" t="inlineStr"><is><t>${1}</t></is></c></row>')
        with zipfile.ZipFile(application / ("reports/" + filename + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in book.items():
                archive.writestr(entry_name, content)
    multi_sheet = dict(parameters)
    for name in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels", "[Content_Types].xml"):
        if name == "xl/workbook.xml": multi_sheet[name] = multiple[name].replace('r:id="rId2"', 'r:id="rId3"')
    multi_sheet["xl/_rels/workbook.xml.rels"] = multi_sheet["xl/_rels/workbook.xml.rels"].replace(
        '</Relationships>', '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
    multi_sheet["[Content_Types].xml"] = multi_sheet["[Content_Types].xml"].replace(
        '</Types>', '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    multi_sheet["xl/sharedStrings.xml"] = multi["xl/sharedStrings.xml"]
    for index in range(2):
        multi_sheet["xl/worksheets/sheet%d.xml" % (index + 1)] = original_sheet.replace(
            '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>%d</v></c>' % index)
    with zipfile.ZipFile(application / "reports/multi-sheet.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in multi_sheet.items():
            archive.writestr(entry_name, content)
    expanded = dict(parameters)
    expanded["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3"><si><t>${rows.item.amount}</t></si><si><t>${rows.item.title}</t></si><si><t>${rows.index}</t></si></sst>'''
    expanded["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>',
        '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" s="0"><v>99</v></c><c r="D1" t="s"><v>2</v></c>')
    expanded_multi_sheet = dict(multi_sheet)
    expanded_multi_sheet["xl/worksheets/sheet1.xml"] = expanded["xl/worksheets/sheet1.xml"]
    expanded_multi_sheet["xl/worksheets/sheet2.xml"] = original_sheet.replace(
        '<c r="A1" t="inlineStr"><is><t>Example</t></is></c>', '<c r="A1" t="s"><v>3</v></c>')
    expanded_multi_sheet["xl/sharedStrings.xml"] = expanded["xl/sharedStrings.xml"].replace(
        'count="3" uniqueCount="3"', 'count="4" uniqueCount="4"').replace('</sst>', '<si><t>${right.data.value}</t></si></sst>')
    with zipfile.ZipFile(application / "reports/expanded-multi-sheet.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in expanded_multi_sheet.items():
            archive.writestr(entry_name, content)
    for filename in ("expanded", "expanded-inline", "expanded-occupied", "expanded-static", "expanded-formula", "expanded-metadata", "expanded-rich", "expanded-inline-number", "expanded-inline-constant", "expanded-other-columns", "expanded-row-height", "expanded-inline-target", "expanded-missing-source", "expanded-shared-formula", "expanded-complex-formula", "expanded-invalid-formula", "expanded-parenthesized", "expanded-unknown-function", "expanded-functions"):
        book = dict(expanded)
        if filename == "expanded-inline":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '<c r="B1" t="s"><v>1</v></c>', '<c r="B1" t="inlineStr"><is><t>${rows.item.title}</t></is></c>')
        if filename == "expanded-rich":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '<c r="B1" t="s"><v>1</v></c>', '<c r="B1" t="inlineStr"><is><r><t>Rich </t></r><r><t>_x0041_</t></r></is></c>')
        if filename == "expanded-inline-number":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '<c r="A1" t="s"><v>0</v></c>', '<c r="A1" t="inlineStr"><is><t>${rows.item.amount}</t></is></c>')
        if filename == "expanded-inline-constant":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '<c r="B1" t="s"><v>1</v></c>', '<c r="B1" t="inlineStr"><is><t>${\'fixed\'}</t></is></c>')
        if filename == "expanded-occupied":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '</sheetData>', '<row r="2"><c r="A2"><v>77</v></c><c r="B2" t="s"><v>2</v></c><c r="C2" t="s"><v>2</v></c></row></sheetData>')
        if filename == "expanded-inline-target":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="2"><c r="A2" t="inlineStr"><is><t>old</t></is></c></row></sheetData>')
        if filename == "expanded-missing-source":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '')
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="2"><c r="C2"><v>77</v></c></row></sheetData>')
        if filename == "expanded-static":
            book["xl/sharedStrings.xml"] = book["xl/sharedStrings.xml"].replace('${rows.item.title}', 'Static _x005F_x005F_x0041_')
        if filename == "expanded-formula":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>$A$1+1</f><v>2</v></c>')
        if filename == "expanded-shared-formula":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f t="shared" si="0" ref="C1:C1">1+1</f><v>2</v></c>')
        if filename == "expanded-complex-formula":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>SUM(A1:A2)</f><v>2</v></c>')
        if filename == "expanded-invalid-formula":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>XFE1+1</f><v>2</v></c>')
        if filename == "expanded-parenthesized":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>SUM($A$1:A2,(3+4)*2)</f><v>2</v></c>')
        if filename == "expanded-unknown-function":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>UNKNOWN(A1)</f><v>2</v></c>')
        if filename == "expanded-functions":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>MAX(MIN(A1,A2),AVERAGE(A1:A2),COUNT(A1:A2),sum(1,2))</f><v>2</v></c>')
        if filename == "expanded-metadata":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C1" s="0">', '<c r="C1" s="0" cm="1">')
        if filename in ("expanded-other-columns", "expanded-row-height"):
            attrs = ' r="2" spans="5:5"' if filename == "expanded-other-columns" else ' r="2" ht="30" customHeight="1"'
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '</sheetData>', '<row' + attrs + '><c r="E2"><v>77</v></c></row><row r="3"><c r="E3"><v>88</v></c></row></sheetData>')
        with zipfile.ZipFile(application / ("reports/" + filename + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in book.items():
                archive.writestr(entry_name, content)
    expanded_merged = dict(expanded)
    expanded_merged["xl/worksheets/sheet1.xml"] = expanded_merged["xl/worksheets/sheet1.xml"].replace(
        '</worksheet>', '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    with zipfile.ZipFile(application / "reports/expanded-merged.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in expanded_merged.items():
            archive.writestr(entry_name, content)
    merged_formula = dict(expanded_merged)
    merged_formula["xl/worksheets/sheet1.xml"] = merged_formula["xl/worksheets/sheet1.xml"].replace(
        '<c r="C1" s="0"><v>99</v></c>', '<c r="C1" s="0"><f>$A$1+1</f><v>2</v></c>')
    with zipfile.ZipFile(application / "reports/expanded-merged-formula.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in merged_formula.items():
            archive.writestr(entry_name, content)
    footer = dict(expanded)
    footer["xl/sharedStrings.xml"] = footer["xl/sharedStrings.xml"].replace('count="3" uniqueCount="3"', 'count="5" uniqueCount="5"').replace(
        '</sst>', '<si><t>Footer</t></si><si><t>${parameters[\'nested\']}</t></si></sst>')
    footer["xl/worksheets/sheet1.xml"] = footer["xl/worksheets/sheet1.xml"].replace(
        '</sheetData>', '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c>'
        '<c r="C2"><v>123</v></c><c r="D2"><v>456</v></c></row></sheetData>')
    for filename in ("expanded-footer", "expanded-sparse-footer", "expanded-sparse-formula", "expanded-sparse-shared-formula", "expanded-sparse-chain-formula", "expanded-footer-conflict", "expanded-sparse-block"):
        book = dict(footer)
        if filename in ("expanded-sparse-footer", "expanded-sparse-formula", "expanded-sparse-shared-formula", "expanded-sparse-chain-formula"):
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="C2"><v>123</v></c>', '')
            formula = '<f>1+1</f><v>2</v>' if filename in ("expanded-sparse-formula", "expanded-sparse-chain-formula") else '<f t="shared" si="0" ref="C4:C4">1+1</f><v>2</v>' if filename == "expanded-sparse-shared-formula" else '<v>55</v>'
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('</sheetData>', '<row r="4"><c r="C4">' + formula + '</c></row></sheetData>')
        if filename == "expanded-sparse-chain-formula":
            book["[Content_Types].xml"] = book["[Content_Types].xml"].replace('</Types>', '<Override PartName="/xl/calcChain.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/></Types>')
            book["xl/_rels/workbook.xml.rels"] = book["xl/_rels/workbook.xml.rels"].replace('</Relationships>', '<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/></Relationships>')
            book["xl/calcChain.xml"] = '<calcChain xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><c r="C4" i="1"/></calcChain>'
        if filename == "expanded-sparse-block":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace('<c r="B1" t="s"><v>1</v></c>', '')
        if filename == "expanded-footer-conflict":
            book["xl/worksheets/sheet1.xml"] = book["xl/worksheets/sheet1.xml"].replace(
                '</sheetData>', '<row r="4"><c r="A4" t="inlineStr"><is><t>occupied</t></is></c></row></sheetData>')
        with zipfile.ZipFile(application / ("reports/" + filename + ".xlsx"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in book.items():
                archive.writestr(entry_name, content)
    multi_footer = dict(footer)
    multi_footer["xl/worksheets/sheet1.xml"] = multi_footer["xl/worksheets/sheet1.xml"].replace(
        '</sheetData>', '<row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3"><v>301</v></c><c r="C3"><v>302</v></c><c r="D3"><v>303</v></c></row>'
        '<row r="4"><c r="A4" t="s"><v>3</v></c><c r="B4"><v>401</v></c><c r="C4"><v>402</v></c><c r="D4"><v>403</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/expanded-multi-footer.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in multi_footer.items():
            archive.writestr(entry_name, content)
    multi_side = dict(multi_footer)
    multi_side["xl/worksheets/sheet1.xml"] = multi_side["xl/worksheets/sheet1.xml"].replace(
        '<c r="D2"><v>456</v></c></row>', '<c r="D2"><v>456</v></c><c r="E2"><v>2</v></c></row>').replace(
        '<c r="D3"><v>303</v></c></row>', '<c r="D3"><v>303</v></c><c r="E3"><v>3</v></c></row>').replace(
        '<c r="D4"><v>403</v></c></row>', '<c r="D4"><v>403</v></c><c r="E4"><v>4</v></c></row>').replace(
        '</sheetData>', '<row r="5"><c r="E5"><v>55</v></c></row><row r="6"><c r="E6"><v>66</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/expanded-multi-side.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in multi_side.items():
            archive.writestr(entry_name, content)
    header_footer = dict(footer)
    header_footer["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Example</t></is></c></row>',
        '<row r="1"><c r="A1" t="s"><v>3</v></c><c r="B1" t="s"><v>4</v></c><c r="C1"><v>444</v></c><c r="D1"><v>445</v></c><c r="E1" t="s"><v>4</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="B2" t="s"><v>1</v></c><c r="C2" s="0"><v>99</v></c><c r="D2" t="s"><v>2</v></c></row>'
        '<row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3" t="s"><v>4</v></c><c r="C3"><v>123</v></c><c r="D3"><v>456</v></c></row>')
    with zipfile.ZipFile(application / "reports/expanded-header-footer.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in header_footer.items():
            archive.writestr(entry_name, content)
    side_conflict = dict(header_footer)
    side_conflict["xl/worksheets/sheet1.xml"] = side_conflict["xl/worksheets/sheet1.xml"].replace(
        '<c r="D3"><v>456</v></c>', '<c r="D3"><v>456</v></c><c r="E3"><v>1</v></c>')
    with zipfile.ZipFile(application / "reports/expanded-side-conflict.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in side_conflict.items():
            archive.writestr(entry_name, content)
    custom_expanded = dict(expanded)
    custom_expanded["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3"><si><t>${rows.index}</t></si><si><t>${rows.index + 10}</t></si><si><t>Static</t></si></sst>'''
    with zipfile.ZipFile(application / "reports/expanded-custom.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in custom_expanded.items():
            archive.writestr(entry_name, content)
    two_rows = dict(expanded)
    two_rows["xl/sharedStrings.xml"] = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4"><si><t>${rows.item.amount}</t></si><si><t>Top</t></si><si><t>Detail</t></si><si><t>${rows.index}</t></si></sst>'''
    two_rows["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Example</t></is></c></row>',
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>')
    with zipfile.ZipFile(application / "reports/expanded-two.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in two_rows.items():
            archive.writestr(entry_name, content)
    empty_row = dict(two_rows)
    empty_row["xl/worksheets/sheet1.xml"] = empty_row["xl/worksheets/sheet1.xml"].replace(
        '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>', '')
    empty_row["xl/worksheets/sheet1.xml"] = empty_row["xl/worksheets/sheet1.xml"].replace(
        '</sheetData>', '<row r="4"><c r="A4" t="s"><v>0</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/expanded-empty-row.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in empty_row.items():
            archive.writestr(entry_name, content)
    horizontal = dict(two_rows)
    horizontal["xl/worksheets/sheet1.xml"] = horizontal["xl/worksheets/sheet1.xml"].replace(
        '<c r="B1" t="s"><v>1</v></c></row>', '<c r="B1" t="s"><v>1</v></c><c r="C1"><v>77</v></c></row>').replace(
        '<c r="B2" t="s"><v>3</v></c></row>', '<c r="B2" t="s"><v>3</v></c><c r="E2" t="s"><v>1</v></c></row>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal.items():
            archive.writestr(entry_name, content)
    horizontal_merged = dict(horizontal)
    horizontal_merged["xl/worksheets/sheet1.xml"] = horizontal_merged["xl/worksheets/sheet1.xml"].replace(
        '</worksheet>', '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-merged.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_merged.items():
            archive.writestr(entry_name, content)
    horizontal_footer = dict(two_rows)
    horizontal_footer["xl/sharedStrings.xml"] = horizontal_footer["xl/sharedStrings.xml"].replace('count="4" uniqueCount="4"', 'count="6" uniqueCount="6"').replace(
        '</sst>', '<si><t>Footer</t></si><si><t>${parameters[\'nested\']}</t></si></sst>')
    horizontal_footer["xl/worksheets/sheet1.xml"] = horizontal_footer["xl/worksheets/sheet1.xml"].replace(
        '<c r="B1" t="s"><v>1</v></c></row>', '<c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>4</v></c></row>').replace(
        '<c r="B2" t="s"><v>3</v></c></row>', '<c r="B2" t="s"><v>3</v></c><c r="C2" t="s"><v>5</v></c></row>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-footer.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_footer.items():
            archive.writestr(entry_name, content)
    horizontal_multi = dict(horizontal_footer)
    horizontal_multi["xl/worksheets/sheet1.xml"] = horizontal_multi["xl/worksheets/sheet1.xml"].replace(
        '<c r="C1" t="s"><v>4</v></c></row>', '<c r="C1" t="s"><v>4</v></c>' +
        ''.join('<c r="%s1"><v>%d</v></c>' % (chr(68 + i), 41 + i) for i in range(4)) + '</row>').replace(
        '<c r="C2" t="s"><v>5</v></c></row>', '<c r="C2" t="s"><v>5</v></c>' +
        ''.join('<c r="%s2"><v>%d</v></c>' % (chr(68 + i), 51 + i) for i in range(4)) + '</row>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-multi-footer.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_multi.items():
            archive.writestr(entry_name, content)
    horizontal_multi_side = dict(horizontal_multi)
    horizontal_multi_side["xl/worksheets/sheet1.xml"] = horizontal_multi_side["xl/worksheets/sheet1.xml"].replace(
        '</sheetData>', '<row r="3"><c r="A3"><v>5</v></c><c r="C3"><v>10</v></c><c r="D3"><v>20</v></c>'
        '<c r="F3"><v>40</v></c><c r="G3"><v>50</v></c><c r="I3"><v>99</v></c></row></sheetData>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-multi-side.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_multi_side.items():
            archive.writestr(entry_name, content)
    horizontal_header = dict(horizontal_footer)
    horizontal_header["xl/worksheets/sheet1.xml"] = original_sheet.replace(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Example</t></is></c></row>',
        '<row r="1"><c r="A1" t="s"><v>4</v></c><c r="B1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c><c r="D1" t="s"><v>4</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>5</v></c><c r="B2" t="s"><v>2</v></c><c r="C2" t="s"><v>3</v></c><c r="D2" t="s"><v>5</v></c></row>'
        '<row r="3"><c r="A3" t="s"><v>5</v></c></row>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-header.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_header.items():
            archive.writestr(entry_name, content)
    horizontal_side_conflict = dict(horizontal_header)
    horizontal_side_conflict["xl/worksheets/sheet1.xml"] = horizontal_side_conflict["xl/worksheets/sheet1.xml"].replace(
        '<c r="A3" t="s"><v>5</v></c>', '<c r="A3" t="s"><v>5</v></c><c r="D3"><v>1</v></c>')
    with zipfile.ZipFile(application / "reports/expanded-horizontal-side-conflict.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in horizontal_side_conflict.items():
            archive.writestr(entry_name, content)
    merged = dict(entries)
    merged["xl/worksheets/sheet1.xml"] = original_sheet.replace("</worksheet>", '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
    with zipfile.ZipFile(application / "reports/merged.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in merged.items():
            archive.writestr(name, content)
    merged_inside = dict(merged)
    merged_inside["xl/worksheets/sheet1.xml"] = merged_inside["xl/worksheets/sheet1.xml"].replace("Example", "${1+2}")
    with zipfile.ZipFile(application / "reports/merged-inside.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in merged_inside.items():
            archive.writestr(entry_name, content)
    merged_overlap = dict(merged)
    merged_overlap["xl/worksheets/sheet1.xml"] = merged_overlap["xl/worksheets/sheet1.xml"].replace(
        '<mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells>',
        '<mergeCells count="2"><mergeCell ref="A1:B1"/><mergeCell ref="B1:C1"/></mergeCells>')
    with zipfile.ZipFile(application / "reports/merged-overlap.xlsx", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in merged_overlap.items():
            archive.writestr(entry_name, content)
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
    request.parameters.z8_add("foo"w, "данные 😀 _x0041_ _x005F_x0041_"w);
    request.parameters.z8_add("nested"w, "${1+2}"w);
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
    auto quoted = P.m_doubleQuotedRange();
    assert(read(z8_file_resolve_path(quoted)) == read(buildPath(args[1], "reports", "double-quoted.xlsx")));
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
    bool expanded; try { P.m_expanded(); } catch (Exception) { expanded = true; } assert(expanded);
    bool expandedInline; try { P.m_expandedInline(); } catch (Exception) { expandedInline = true; } assert(expandedInline);
    bool expandedOccupied; try { P.m_expandedOccupied(); } catch (Exception) { expandedOccupied = true; } assert(expandedOccupied);
    bool expandedStatic; try { P.m_expandedStatic(); } catch (Exception) { expandedStatic = true; } assert(expandedStatic);
    bool expandedFormula; try { P.m_expandedFormula(); } catch (Exception) { expandedFormula = true; } assert(expandedFormula);
    bool expandedMetadata; try { P.m_expandedMetadata(); } catch (Exception) { expandedMetadata = true; } assert(expandedMetadata);
    bool expandedRich; try { P.m_expandedRich(); } catch (Exception) { expandedRich = true; } assert(expandedRich);
    bool expandedCustom; try { P.m_expandedCustom(); } catch (Exception) { expandedCustom = true; } assert(expandedCustom);
    assert(database.begins == 65 && database.rollbacks == 65);
    bool repeat; try { P.m_repeatRange(); } catch (Exception) { repeat = true; } assert(repeat);
    bool jsonInline; try { P.m_jsonInlineRange(); } catch (Exception) { jsonInline = true; } assert(jsonInline);
    bool inlineNumber; try { P.m_expandedInlineNumber(); } catch (Exception) { inlineNumber = true; } assert(inlineNumber);
    bool inlineConstant; try { P.m_expandedInlineConstant(); } catch (Exception) { inlineConstant = true; } assert(inlineConstant);
    bool otherColumns; try { P.m_expandedOtherColumns(); } catch (Exception) { otherColumns = true; } assert(otherColumns);
    bool rowHeight; try { P.m_expandedRowHeight(); } catch (Exception) { rowHeight = true; } assert(rowHeight);
    bool inlineTarget; try { P.m_expandedInlineTarget(); } catch (Exception) { inlineTarget = true; } assert(inlineTarget);
    bool missingSource; try { P.m_expandedMissingSource(); } catch (Exception) { missingSource = true; } assert(missingSource);
    bool twoRows; try { P.m_expandedTwoRows(); } catch (Exception) { twoRows = true; } assert(twoRows);
    bool emptyRow; try { P.m_expandedEmptyRow(); } catch (Exception) { emptyRow = true; } assert(emptyRow);
    bool horizontal; try { P.m_expandedHorizontal(); } catch (Exception) { horizontal = true; } assert(horizontal);
    bool sharedFormula; try { P.m_expandedSharedFormula(); } catch (Exception) { sharedFormula = true; } assert(sharedFormula);
    bool complexFormula; try { P.m_expandedComplexFormula(); } catch (Exception) { complexFormula = true; } assert(complexFormula);
    bool invalidFormula; try { P.m_expandedInvalidFormula(); } catch (Exception) { invalidFormula = true; } assert(invalidFormula);
    bool parenthesized; try { P.m_expandedParenthesized(); } catch (Exception) { parenthesized = true; } assert(parenthesized);
    bool unknownFunction; try { P.m_expandedUnknownFunction(); } catch (Exception) { unknownFunction = true; } assert(unknownFunction);
    bool functions; try { P.m_expandedFunctions(); } catch (Exception) { functions = true; } assert(functions);
    bool mergedInside; try { P.m_mergedInside(); } catch (Exception) { mergedInside = true; } assert(mergedInside);
    assert(z8_file_exists(P.m_mergedInsideStatic()));
    bool expandedMerged; try { P.m_expandedMerged(); } catch (Exception) { expandedMerged = true; } assert(expandedMerged);
    bool mergedOverlap; try { P.m_mergedOverlap(); } catch (Exception) { mergedOverlap = true; } assert(mergedOverlap);
    bool horizontalMerged; try { P.m_expandedHorizontalMerged(); } catch (Exception) { horizontalMerged = true; } assert(horizontalMerged);
    bool mergedFormula; try { P.m_expandedMergedFormula(); } catch (Exception) { mergedFormula = true; } assert(mergedFormula);
    bool footer; try { P.m_expandedFooter(); } catch (Exception) { footer = true; } assert(footer);
    bool sparseFooter; try { P.m_expandedSparseFooter(); } catch (Exception) { sparseFooter = true; } assert(sparseFooter);
    bool footerConflict; try { P.m_expandedFooterConflict(); } catch (Exception) { footerConflict = true; } assert(footerConflict);
    bool horizontalFooter; try { P.m_expandedHorizontalFooter(); } catch (Exception) { horizontalFooter = true; } assert(horizontalFooter);
    bool multiFooter; try { P.m_expandedMultiFooter(); } catch (Exception) { multiFooter = true; } assert(multiFooter);
    bool horizontalMultiFooter; try { P.m_expandedHorizontalMultiFooter(); } catch (Exception) { horizontalMultiFooter = true; } assert(horizontalMultiFooter);
    bool sparseBlock; try { P.m_expandedSparseBlock(); } catch (Exception) { sparseBlock = true; } assert(sparseBlock);
    bool headerFooter; try { P.m_expandedHeaderFooter(); } catch (Exception) { headerFooter = true; } assert(headerFooter);
    bool horizontalHeader; try { P.m_expandedHorizontalHeader(); } catch (Exception) { horizontalHeader = true; } assert(horizontalHeader);
    bool sideConflict; try { P.m_expandedSideConflict(); } catch (Exception) { sideConflict = true; } assert(sideConflict);
    bool horizontalSideConflict; try { P.m_expandedHorizontalSideConflict(); } catch (Exception) { horizontalSideConflict = true; } assert(horizontalSideConflict);
    bool emptyFooter; try { P.m_emptyFooter(); } catch (Exception) { emptyFooter = true; } assert(emptyFooter);
    bool emptyHorizontalFooter; try { P.m_emptyHorizontalFooter(); } catch (Exception) { emptyHorizontalFooter = true; } assert(emptyHorizontalFooter);
    bool emptyMultiFooter; try { P.m_emptyMultiFooter(); } catch (Exception) { emptyMultiFooter = true; } assert(emptyMultiFooter);
    bool emptyHorizontalMultiFooter; try { P.m_emptyHorizontalMultiFooter(); } catch (Exception) { emptyHorizontalMultiFooter = true; } assert(emptyHorizontalMultiFooter);
    bool emptySparseFooter; try { P.m_emptySparseFooter(); } catch (Exception) { emptySparseFooter = true; } assert(emptySparseFooter);
    bool expandedMultiSide; try { P.m_expandedMultiSide(); } catch (Exception) { expandedMultiSide = true; } assert(expandedMultiSide);
    bool expandedHorizontalMultiSide; try { P.m_expandedHorizontalMultiSide(); } catch (Exception) { expandedHorizontalMultiSide = true; } assert(expandedHorizontalMultiSide);
    bool emptySideFooter; try { P.m_emptySideFooter(); } catch (Exception) { emptySideFooter = true; } assert(emptySideFooter);
    bool emptyHorizontalSideFooter; try { P.m_emptyHorizontalSideFooter(); } catch (Exception) { emptyHorizontalSideFooter = true; } assert(emptyHorizontalSideFooter);
    bool multipleSheets; try { P.m_multipleSheets(); } catch (Exception) { multipleSheets = true; } assert(multipleSheets);
    bool multipleSheetsRename; try { P.m_multipleSheetsRename(); } catch (Exception) { multipleSheetsRename = true; } assert(multipleSheetsRename);
    bool multipleSheetsBothRename; try { P.m_multipleSheetsBothRename(); } catch (Exception) { multipleSheetsBothRename = true; } assert(multipleSheetsBothRename);
    bool multipleSheetsDuplicate; try { P.m_multipleSheetsDuplicate(); } catch (Exception e) {
        multipleSheetsDuplicate = e.msg == "duplicate POI report sheet name";
    } assert(multipleSheetsDuplicate && z8_optional_require(P.m_orderedCount()) == 0);
    bool expandedMultipleSheets; try { P.m_expandedMultipleSheets(); } catch (Exception) { expandedMultipleSheets = true; } assert(expandedMultipleSheets);
    bool cloneSheets; try { P.m_cloneSheets(); } catch (Exception) { cloneSheets = true; } assert(cloneSheets);
    bool cloneUnsupported; try { P.m_cloneUnsupported(); } catch (Exception e) {
        cloneUnsupported = e.msg == "POI report sheet cloning is unsupported for this workbook layout";
    } assert(cloneUnsupported);
    bool cloneSuffix; try { P.m_cloneSuffix(); } catch (Exception) { cloneSuffix = true; } assert(cloneSuffix);
    bool cloneLong; try { P.m_cloneLong(); } catch (Exception) { cloneLong = true; } assert(cloneLong);
    bool cloneExisting; try { P.m_cloneExisting(); } catch (Exception) { cloneExisting = true; } assert(cloneExisting);
    bool cloneViews; try { P.m_cloneViews(); } catch (Exception) { cloneViews = true; } assert(cloneViews);
    bool cloneSetup; try { P.m_cloneSetup(); } catch (Exception) { cloneSetup = true; } assert(cloneSetup);
    bool clonePrint; try { P.m_clonePrint(); } catch (Exception) { clonePrint = true; } assert(clonePrint);
    bool cloneFilter; try { P.m_cloneFilter(); } catch (Exception) { cloneFilter = true; } assert(cloneFilter);
    bool cloneNamed; try { P.m_cloneNamed(); } catch (Exception) { cloneNamed = true; } assert(cloneNamed);
    bool cloneNamedRename; try { P.m_cloneNamedRename(); } catch (Exception) { cloneNamedRename = true; } assert(cloneNamedRename);
    bool cloneNamedOriginalRename; try { P.m_cloneNamedOriginalRename(); } catch (Exception) { cloneNamedOriginalRename = true; } assert(cloneNamedOriginalRename);
    bool cloneNamedUnsupportedRename; try { P.m_cloneNamedUnsupportedRename(); } catch (Exception) { cloneNamedUnsupportedRename = true; } assert(cloneNamedUnsupportedRename);
    bool cloneNamedQuotedRename; try { P.m_cloneNamedQuotedRename(); } catch (Exception) { cloneNamedQuotedRename = true; } assert(cloneNamedQuotedRename);
    bool cloneNamedDigitRename; try { P.m_cloneNamedDigitRename(); } catch (Exception) { cloneNamedDigitRename = true; } assert(cloneNamedDigitRename);
    bool cloneNamedCellRename; try { P.m_cloneNamedCellRename(); } catch (Exception) { cloneNamedCellRename = true; } assert(cloneNamedCellRename);
    bool cloneNamedRussianRename; try { P.m_cloneNamedRussianRename(); } catch (Exception) { cloneNamedRussianRename = true; } assert(cloneNamedRussianRename);
    bool collectionRange; try { P.m_collectionRange(); } catch (Exception) { collectionRange = true; } assert(collectionRange);
    bool mapValueRange; try { P.m_mapValueRange(); } catch (Exception) { mapValueRange = true; } assert(mapValueRange);
    bool mapDerivedRange; try { P.m_mapDerivedRange(); } catch (Exception) { mapDerivedRange = true; } assert(mapDerivedRange);
    assert(database.begins == 133 && database.rollbacks == 133);
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
        contents = contents.replace("void main(string[] args) {", '''class CountingProvider : IZ8PoiProvider, IZ8PoiReportWriter, IZ8PoiReportExpander, IZ8PoiReportMergeWriter, IZ8PoiReportCellRemover, IZ8PoiReportSheetCloner {
    IZ8PoiProvider reader;
    IZ8PoiReportWriter writer;
    IZ8PoiReportExpander expander;
    IZ8PoiReportMergeWriter mergeWriter;
    IZ8PoiReportCellRemover remover;
    IZ8PoiReportSheetCloner cloner;
    uint renames, hides, writes, expansions, merges;
    this(IZ8PoiProvider provider) { reader = provider; writer = cast(IZ8PoiReportWriter)provider; expander = cast(IZ8PoiReportExpander)provider; mergeWriter = cast(IZ8PoiReportMergeWriter)provider; remover = cast(IZ8PoiReportCellRemover)provider; cloner = cast(IZ8PoiReportSheetCloner)provider; assert(writer !is null && expander !is null && mergeWriter !is null && remover !is null && cloner !is null); }
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
    ubyte[] writeExpandedReport(const(ubyte)[] input, const(Z8PoiCellCopy)[] copies, const(Z8PoiCellEdit)[] cells) {
        assert(copies.length == 2 || copies.length == 3 || copies.length == 5 || copies.length == 8 || copies.length == 4 || copies.length == 6 || copies.length == 10 || copies.length == 11 || copies.length == 12 || copies.length == 13 || copies.length == 18 || copies.length == 20 || copies.length == 22 || copies.length == 23); auto result = expander.writeExpandedReport(input, copies, cells);
        ++expansions; return result;
    }
    ubyte[] addReportMerges(const(ubyte)[] input, const(Z8PoiMergedRegion)[] regions) {
        assert(regions.length == 2); auto result = mergeWriter.addReportMerges(input, regions);
        ++merges; return result;
    }
    ubyte[] removeReportCells(const(ubyte)[] input, const(Z8PoiCellRemoval)[] cells) {
        assert((cells.length == 1 && ((cells[0].row == 2 && (cells[0].column == 3 || cells[0].column == 4)) ||
                                      (cells[0].row == 1 && (cells[0].column == 1 || cells[0].column == 2)) ||
                                      (cells[0].row == 3 && (cells[0].column == 0 || cells[0].column == 2)))) ||
               cells.length == 5 || cells.length == 4 || cells.length == 3 || cells.length == 2);
        return remover.removeReportCells(input, cells);
    }
    ubyte[] cloneReportSheets(const(ubyte)[] input, uint prototype, const(wstring)[] names) {
        assert(prototype <= 1 && (names.length == 2 || names.length == 16) && names[0] != names[1]);
        return cloner.cloneReportSheets(input, prototype, names);
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
            'bool empty; try { P.m_runJsonReport(jsonEmpty); } catch (Exception) { empty = true; } assert(empty);',
            'auto empty = P.m_runJsonReport(jsonEmpty); copy(z8_file_resolve_path(empty), buildPath(args[2], "json-empty.xlsx"));')
        contents = contents.replace(
            'bool queryResult; try { P.m_runQueryReport(queryReport); } catch (Exception) { queryResult = true; } assert(queryResult);',
            'auto queryResult = P.m_runQueryReport(queryReport); copy(z8_file_resolve_path(queryResult), buildPath(args[2], "query.xlsx")); assert(counter.writes == 9);')
        contents = contents.replace(
            'bool multipleRanges; try { P.m_multipleRanges(); } catch (Exception) { multipleRanges = true; } assert(multipleRanges);',
            'auto multipleRanges = P.m_multipleRanges(); copy(z8_file_resolve_path(multipleRanges), buildPath(args[2], "multi-range.xlsx")); assert(counter.writes == 10);')
        contents = contents.replace(
            'bool outsideRanges; try { P.m_outsideRanges(); } catch (Exception) { outsideRanges = true; } assert(outsideRanges);',
            'auto outsideRanges = P.m_outsideRanges(); copy(z8_file_resolve_path(outsideRanges), buildPath(args[2], "outside-range.xlsx")); assert(counter.writes == 11);')
        contents = contents.replace(
            'bool expanded; try { P.m_expanded(); } catch (Exception) { expanded = true; } assert(expanded);',
            'auto expanded = P.m_expanded(); copy(z8_file_resolve_path(expanded), buildPath(args[2], "expanded.xlsx")); assert(counter.expansions == 1);')
        contents = contents.replace(
            'bool expandedOccupied; try { P.m_expandedOccupied(); } catch (Exception) { expandedOccupied = true; } assert(expandedOccupied);',
            'auto expandedOccupied = P.m_expandedOccupied(); copy(z8_file_resolve_path(expandedOccupied), buildPath(args[2], "expanded-occupied.xlsx")); assert(counter.expansions == 2);')
        contents = contents.replace(
            'bool expandedStatic; try { P.m_expandedStatic(); } catch (Exception) { expandedStatic = true; } assert(expandedStatic);',
            'auto expandedStatic = P.m_expandedStatic(); copy(z8_file_resolve_path(expandedStatic), buildPath(args[2], "expanded-static.xlsx")); assert(counter.expansions == 3);')
        contents = contents.replace(
            'bool expandedFormula; try { P.m_expandedFormula(); } catch (Exception) { expandedFormula = true; } assert(expandedFormula);',
            'auto expandedFormula = P.m_expandedFormula(); copy(z8_file_resolve_path(expandedFormula), buildPath(args[2], "expanded-formula.xlsx")); assert(counter.expansions == 4);')
        contents = contents.replace(
            'bool expandedRich; try { P.m_expandedRich(); } catch (Exception) { expandedRich = true; } assert(expandedRich);',
            'auto expandedRich = P.m_expandedRich(); copy(z8_file_resolve_path(expandedRich), buildPath(args[2], "expanded-rich.xlsx")); assert(counter.expansions == 5);')
        contents = contents.replace(
            'bool expandedCustom; try { P.m_expandedCustom(); } catch (Exception) { expandedCustom = true; } assert(expandedCustom);',
            'auto expandedCustom = P.m_expandedCustom(); copy(z8_file_resolve_path(expandedCustom), buildPath(args[2], "expanded-custom.xlsx")); assert(counter.expansions == 6);')
        contents = contents.replace(
            'bool repeat; try { P.m_repeatRange(); } catch (Exception) { repeat = true; } assert(repeat);',
            'auto repeat = P.m_repeatRange(); copy(z8_file_resolve_path(repeat), buildPath(args[2], "repeat.xlsx")); assert(counter.writes == 12);')
        contents = contents.replace(
            'bool inlineNumber; try { P.m_expandedInlineNumber(); } catch (Exception) { inlineNumber = true; } assert(inlineNumber);',
            'auto inlineNumber = P.m_expandedInlineNumber(); copy(z8_file_resolve_path(inlineNumber), buildPath(args[2], "expanded-inline-number.xlsx")); assert(counter.expansions == 7);')
        contents = contents.replace(
            'bool inlineConstant; try { P.m_expandedInlineConstant(); } catch (Exception) { inlineConstant = true; } assert(inlineConstant);',
            'auto inlineConstant = P.m_expandedInlineConstant(); copy(z8_file_resolve_path(inlineConstant), buildPath(args[2], "expanded-inline-constant.xlsx")); assert(counter.expansions == 8);')
        contents = contents.replace(
            'bool otherColumns; try { P.m_expandedOtherColumns(); } catch (Exception) { otherColumns = true; } assert(otherColumns);',
            'auto otherColumns = P.m_expandedOtherColumns(); copy(z8_file_resolve_path(otherColumns), buildPath(args[2], "expanded-other-columns.xlsx")); assert(counter.expansions == 9);')
        contents = contents.replace(
            'bool twoRows; try { P.m_expandedTwoRows(); } catch (Exception) { twoRows = true; } assert(twoRows);',
            'auto twoRows = P.m_expandedTwoRows(); copy(z8_file_resolve_path(twoRows), buildPath(args[2], "expanded-two.xlsx")); assert(counter.expansions == 10);')
        contents = contents.replace(
            'bool horizontal; try { P.m_expandedHorizontal(); } catch (Exception) { horizontal = true; } assert(horizontal);',
            'auto horizontal = P.m_expandedHorizontal(); copy(z8_file_resolve_path(horizontal), buildPath(args[2], "expanded-horizontal.xlsx")); assert(counter.expansions == 12);')
        contents = contents.replace(
            'bool emptyRow; try { P.m_expandedEmptyRow(); } catch (Exception) { emptyRow = true; } assert(emptyRow);',
            'auto emptyRow = P.m_expandedEmptyRow(); copy(z8_file_resolve_path(emptyRow), buildPath(args[2], "expanded-empty-row.xlsx")); assert(counter.expansions == 11);')
        contents = contents.replace(
            'bool complexFormula; try { P.m_expandedComplexFormula(); } catch (Exception) { complexFormula = true; } assert(complexFormula);',
            'auto complexFormula = P.m_expandedComplexFormula(); copy(z8_file_resolve_path(complexFormula), buildPath(args[2], "expanded-complex-formula.xlsx")); assert(counter.expansions == 13);')
        contents = contents.replace(
            'bool parenthesized; try { P.m_expandedParenthesized(); } catch (Exception) { parenthesized = true; } assert(parenthesized);',
            'auto parenthesized = P.m_expandedParenthesized(); copy(z8_file_resolve_path(parenthesized), buildPath(args[2], "expanded-parenthesized.xlsx")); assert(counter.expansions == 14);')
        contents = contents.replace(
            'bool functions; try { P.m_expandedFunctions(); } catch (Exception) { functions = true; } assert(functions);',
            'auto functions = P.m_expandedFunctions(); copy(z8_file_resolve_path(functions), buildPath(args[2], "expanded-functions.xlsx")); assert(counter.expansions == 15);')
        contents = contents.replace(
            'bool mergedInside; try { P.m_mergedInside(); } catch (Exception) { mergedInside = true; } assert(mergedInside);',
            'auto mergedInside = P.m_mergedInside(); copy(z8_file_resolve_path(mergedInside), buildPath(args[2], "merged-inside.xlsx")); assert(counter.writes == 13);')
        contents = contents.replace(
            'bool expandedMerged; try { P.m_expandedMerged(); } catch (Exception) { expandedMerged = true; } assert(expandedMerged);',
            'auto expandedMerged = P.m_expandedMerged(); copy(z8_file_resolve_path(expandedMerged), buildPath(args[2], "expanded-merged.xlsx")); assert(counter.expansions == 16 && counter.merges == 1);')
        contents = contents.replace(
            'bool horizontalMerged; try { P.m_expandedHorizontalMerged(); } catch (Exception) { horizontalMerged = true; } assert(horizontalMerged);',
            'auto horizontalMerged = P.m_expandedHorizontalMerged(); copy(z8_file_resolve_path(horizontalMerged), buildPath(args[2], "expanded-horizontal-merged.xlsx")); assert(counter.expansions == 17 && counter.merges == 2);')
        contents = contents.replace(
            'bool mergedFormula; try { P.m_expandedMergedFormula(); } catch (Exception) { mergedFormula = true; } assert(mergedFormula);',
            'auto mergedFormula = P.m_expandedMergedFormula(); copy(z8_file_resolve_path(mergedFormula), buildPath(args[2], "expanded-merged-formula.xlsx")); assert(counter.expansions == 18 && counter.merges == 3);')
        contents = contents.replace(
            'bool footer; try { P.m_expandedFooter(); } catch (Exception) { footer = true; } assert(footer);',
            'auto footer = P.m_expandedFooter(); copy(z8_file_resolve_path(footer), buildPath(args[2], "expanded-footer.xlsx")); assert(counter.expansions == 19);')
        contents = contents.replace(
            'bool horizontalFooter; try { P.m_expandedHorizontalFooter(); } catch (Exception) { horizontalFooter = true; } assert(horizontalFooter);',
            'auto horizontalFooter = P.m_expandedHorizontalFooter(); copy(z8_file_resolve_path(horizontalFooter), buildPath(args[2], "expanded-horizontal-footer.xlsx")); assert(counter.expansions == 20);')
        contents = contents.replace(
            'bool multiFooter; try { P.m_expandedMultiFooter(); } catch (Exception) { multiFooter = true; } assert(multiFooter);',
            'auto multiFooter = P.m_expandedMultiFooter(); copy(z8_file_resolve_path(multiFooter), buildPath(args[2], "expanded-multi-footer.xlsx")); assert(counter.expansions == 21);')
        contents = contents.replace(
            'bool horizontalMultiFooter; try { P.m_expandedHorizontalMultiFooter(); } catch (Exception) { horizontalMultiFooter = true; } assert(horizontalMultiFooter);',
            'auto horizontalMultiFooter = P.m_expandedHorizontalMultiFooter(); copy(z8_file_resolve_path(horizontalMultiFooter), buildPath(args[2], "expanded-horizontal-multi-footer.xlsx")); assert(counter.expansions == 22);')
        contents = contents.replace(
            'bool headerFooter; try { P.m_expandedHeaderFooter(); } catch (Exception) { headerFooter = true; } assert(headerFooter);',
            'auto headerFooter = P.m_expandedHeaderFooter(); copy(z8_file_resolve_path(headerFooter), buildPath(args[2], "expanded-header-footer.xlsx")); assert(counter.expansions == 23);')
        contents = contents.replace(
            'bool horizontalHeader; try { P.m_expandedHorizontalHeader(); } catch (Exception) { horizontalHeader = true; } assert(horizontalHeader);',
            'auto horizontalHeader = P.m_expandedHorizontalHeader(); copy(z8_file_resolve_path(horizontalHeader), buildPath(args[2], "expanded-horizontal-header.xlsx")); assert(counter.expansions == 24);')
        contents = contents.replace('bool missingSource; try { P.m_expandedMissingSource(); } catch (Exception) { missingSource = true; } assert(missingSource);', '')
        contents = contents.replace('bool sparseFooter; try { P.m_expandedSparseFooter(); } catch (Exception) { sparseFooter = true; } assert(sparseFooter);', '')
        contents = contents.replace('bool sparseBlock; try { P.m_expandedSparseBlock(); } catch (Exception) { sparseBlock = true; } assert(sparseBlock);', '')
        contents = contents.replace(
            'bool sideConflict; try { P.m_expandedSideConflict(); } catch (Exception) { sideConflict = true; } assert(sideConflict);',
            'auto sideConflict = P.m_expandedSideConflict(); copy(z8_file_resolve_path(sideConflict), buildPath(args[2], "expanded-side-conflict.xlsx"));')
        contents = contents.replace(
            'bool horizontalSideConflict; try { P.m_expandedHorizontalSideConflict(); } catch (Exception) { horizontalSideConflict = true; } assert(horizontalSideConflict);',
            'auto horizontalSideConflict = P.m_expandedHorizontalSideConflict(); copy(z8_file_resolve_path(horizontalSideConflict), buildPath(args[2], "expanded-horizontal-side-conflict.xlsx"));')
        contents = contents.replace(
            'bool emptyFooter; try { P.m_emptyFooter(); } catch (Exception) { emptyFooter = true; } assert(emptyFooter);',
            'auto emptyFooter = P.m_emptyFooter(); copy(z8_file_resolve_path(emptyFooter), buildPath(args[2], "empty-footer.xlsx"));')
        contents = contents.replace(
            'bool emptyHorizontalFooter; try { P.m_emptyHorizontalFooter(); } catch (Exception) { emptyHorizontalFooter = true; } assert(emptyHorizontalFooter);',
            'auto emptyHorizontalFooter = P.m_emptyHorizontalFooter(); copy(z8_file_resolve_path(emptyHorizontalFooter), buildPath(args[2], "empty-horizontal-footer.xlsx"));')
        contents = contents.replace(
            'bool emptyMultiFooter; try { P.m_emptyMultiFooter(); } catch (Exception) { emptyMultiFooter = true; } assert(emptyMultiFooter);',
            'auto emptyMultiFooter = P.m_emptyMultiFooter(); copy(z8_file_resolve_path(emptyMultiFooter), buildPath(args[2], "empty-multi-footer.xlsx"));')
        contents = contents.replace(
            'bool emptyHorizontalMultiFooter; try { P.m_emptyHorizontalMultiFooter(); } catch (Exception) { emptyHorizontalMultiFooter = true; } assert(emptyHorizontalMultiFooter);',
            'auto emptyHorizontalMultiFooter = P.m_emptyHorizontalMultiFooter(); copy(z8_file_resolve_path(emptyHorizontalMultiFooter), buildPath(args[2], "empty-horizontal-multi-footer.xlsx"));')
        contents = contents.replace(
            'bool emptySparseFooter; try { P.m_emptySparseFooter(); } catch (Exception) { emptySparseFooter = true; } assert(emptySparseFooter);',
            'auto emptySparseFooter = P.m_emptySparseFooter(); copy(z8_file_resolve_path(emptySparseFooter), buildPath(args[2], "empty-sparse-footer.xlsx"));')
        contents = contents.replace(
            'bool expandedMultiSide; try { P.m_expandedMultiSide(); } catch (Exception) { expandedMultiSide = true; } assert(expandedMultiSide);',
            'auto expandedMultiSide = P.m_expandedMultiSide(); copy(z8_file_resolve_path(expandedMultiSide), buildPath(args[2], "expanded-multi-side.xlsx"));')
        contents = contents.replace(
            'bool expandedHorizontalMultiSide; try { P.m_expandedHorizontalMultiSide(); } catch (Exception) { expandedHorizontalMultiSide = true; } assert(expandedHorizontalMultiSide);',
            'auto expandedHorizontalMultiSide = P.m_expandedHorizontalMultiSide(); copy(z8_file_resolve_path(expandedHorizontalMultiSide), buildPath(args[2], "expanded-horizontal-multi-side.xlsx"));')
        contents = contents.replace(
            'bool emptySideFooter; try { P.m_emptySideFooter(); } catch (Exception) { emptySideFooter = true; } assert(emptySideFooter);',
            'auto emptySideFooter = P.m_emptySideFooter(); copy(z8_file_resolve_path(emptySideFooter), buildPath(args[2], "empty-side-footer.xlsx"));')
        contents = contents.replace(
            'bool emptyHorizontalSideFooter; try { P.m_emptyHorizontalSideFooter(); } catch (Exception) { emptyHorizontalSideFooter = true; } assert(emptyHorizontalSideFooter);',
            'auto emptyHorizontalSideFooter = P.m_emptyHorizontalSideFooter(); copy(z8_file_resolve_path(emptyHorizontalSideFooter), buildPath(args[2], "empty-horizontal-side-footer.xlsx"));')
        contents = contents.replace(
            'bool multipleSheets; try { P.m_multipleSheets(); } catch (Exception) { multipleSheets = true; } assert(multipleSheets);',
            'auto multipleSheets = P.m_multipleSheets(); copy(z8_file_resolve_path(multipleSheets), buildPath(args[2], "multi-sheet.xlsx"));')
        contents = contents.replace(
            'bool multipleSheetsRename; try { P.m_multipleSheetsRename(); } catch (Exception) { multipleSheetsRename = true; } assert(multipleSheetsRename);',
            'auto multipleSheetsRename = P.m_multipleSheetsRename(); copy(z8_file_resolve_path(multipleSheetsRename), buildPath(args[2], "multi-sheet-rename.xlsx"));')
        contents = contents.replace(
            'bool multipleSheetsBothRename; try { P.m_multipleSheetsBothRename(); } catch (Exception) { multipleSheetsBothRename = true; } assert(multipleSheetsBothRename);',
            'auto multipleSheetsBothRename = P.m_multipleSheetsBothRename(); copy(z8_file_resolve_path(multipleSheetsBothRename), buildPath(args[2], "multi-sheet-both-rename.xlsx"));')
        contents = contents.replace(
            'bool expandedMultipleSheets; try { P.m_expandedMultipleSheets(); } catch (Exception) { expandedMultipleSheets = true; } assert(expandedMultipleSheets);',
            'auto expandedMultipleSheets = P.m_expandedMultipleSheets(); copy(z8_file_resolve_path(expandedMultipleSheets), buildPath(args[2], "expanded-multi-sheet.xlsx"));')
        contents = contents.replace(
            'bool cloneSheets; try { P.m_cloneSheets(); } catch (Exception) { cloneSheets = true; } assert(cloneSheets);',
            'auto cloneSheets = P.m_cloneSheets(); copy(z8_file_resolve_path(cloneSheets), buildPath(args[2], "cloned-sheets.xlsx"));')
        for variable, method, output in (("cloneSuffix", "cloneSuffix", "cloned-suffix"), ("cloneLong", "cloneLong", "cloned-long"), ("cloneExisting", "cloneExisting", "cloned-existing"), ("cloneViews", "cloneViews", "cloned-views"), ("cloneSetup", "cloneSetup", "cloned-setup"), ("clonePrint", "clonePrint", "cloned-print"), ("cloneFilter", "cloneFilter", "cloned-filter"), ("cloneNamed", "cloneNamed", "cloned-named"), ("cloneNamedRename", "cloneNamedRename", "cloned-named-rename"), ("cloneNamedOriginalRename", "cloneNamedOriginalRename", "cloned-named-original-rename"), ("cloneNamedQuotedRename", "cloneNamedQuotedRename", "cloned-named-quoted-rename"), ("cloneNamedDigitRename", "cloneNamedDigitRename", "cloned-named-digit-rename"), ("cloneNamedCellRename", "cloneNamedCellRename", "cloned-named-cell-rename"), ("cloneNamedRussianRename", "cloneNamedRussianRename", "cloned-named-russian-rename")):
            contents = contents.replace(
                'bool %s; try { P.m_%s(); } catch (Exception) { %s = true; } assert(%s);' % (variable, method, variable, variable),
                'auto %s = P.m_%s(); copy(z8_file_resolve_path(%s), buildPath(args[2], "%s.xlsx"));' % (variable, method, variable, output))
        contents = contents.replace('bool collectionRange; try { P.m_collectionRange(); } catch (Exception) { collectionRange = true; } assert(collectionRange);',
            'auto collectionRange = P.m_collectionRange(); copy(z8_file_resolve_path(collectionRange), buildPath(args[2], "collection.xlsx"));')
        contents = contents.replace('bool mapValueRange; try { P.m_mapValueRange(); } catch (Exception) { mapValueRange = true; } assert(mapValueRange);',
            'auto mapValueRange = P.m_mapValueRange(); copy(z8_file_resolve_path(mapValueRange), buildPath(args[2], "map-value.xlsx"));')
        contents = contents.replace('bool mapDerivedRange; try { P.m_mapDerivedRange(); } catch (Exception) { mapDerivedRange = true; } assert(mapDerivedRange);',
            'auto mapDerivedRange = P.m_mapDerivedRange(); copy(z8_file_resolve_path(mapDerivedRange), buildPath(args[2], "map-derived.xlsx"));')
        contents = contents.replace('assert(database.begins == 133 && database.rollbacks == 133);',
            'auto missingSource = P.m_expandedMissingSource(); copy(z8_file_resolve_path(missingSource), buildPath(args[2], "expanded-missing-source.xlsx")); assert(counter.expansions == 37); auto sparseFooter = P.m_expandedSparseFooter(); copy(z8_file_resolve_path(sparseFooter), buildPath(args[2], "expanded-sparse-footer.xlsx")); assert(counter.expansions == 38); auto sparseBlock = P.m_expandedSparseBlock(); copy(z8_file_resolve_path(sparseBlock), buildPath(args[2], "expanded-sparse-block.xlsx")); assert(counter.expansions == 39); assert(database.begins == 133 && database.rollbacks == 133); auto sparseFormula = P.m_expandedSparseFormula(); copy(z8_file_resolve_path(sparseFormula), buildPath(args[2], "expanded-sparse-formula.xlsx")); bool sparseSharedBlocked; try { P.m_expandedSparseSharedFormula(); } catch (Exception) { sparseSharedBlocked = true; } assert(sparseSharedBlocked); bool chain; try { P.m_expandedSparseChainFormula(); } catch (Exception) { chain = true; } assert(chain);')
        contents = contents.replace("assert(database.begins == 36 && database.rollbacks == 36);",
                                    "assert(database.begins == 36 && database.rollbacks == 36); assert(counter.renames == 2 && counter.hides == 1 && counter.writes == 2);")
        contents = contents.replace('assert(chain);', 'assert(chain); auto highSheet = P.m_cloneHighSheet(); copy(z8_file_resolve_path(highSheet), buildPath(args[2], "cloned-high-sheet.xlsx")); bool tooManySheets; try { P.m_cloneTooManySheets(); } catch (Exception e) { tooManySheets = e.msg == "POI report sheet expansion is not implemented"; } assert(tooManySheets); auto highMultiple = P.m_cloneHighMultiple(); copy(z8_file_resolve_path(highMultiple), buildPath(args[2], "cloned-high-multiple.xlsx")); bool renameConflict; try { P.m_cloneHighRenameConflict(); } catch (Exception e) { renameConflict = e.msg == "duplicate POI report sheet name"; } assert(renameConflict);')
        contents = contents.replace('assert(renameConflict);', 'assert(renameConflict); auto implicitSingle = P.m_nestedImplicitSingle(); copy(z8_file_resolve_path(implicitSingle), buildPath(args[2], "nested-implicit-single.xlsx")); auto implicitSiblings = P.m_nestedImplicitSiblings(); copy(z8_file_resolve_path(implicitSiblings), buildPath(args[2], "nested-implicit-siblings.xlsx")); bool implicitInvalid; try { P.m_nestedImplicitInvalid(); } catch (Exception e) { implicitInvalid = e.msg == "nested POI report range layout is not implemented"; } assert(implicitInvalid); auto nestedSimple = P.m_nestedSimple(); copy(z8_file_resolve_path(nestedSimple), buildPath(args[2], "nested-simple.xlsx")); bool nestedUnsupported; try { P.m_nestedUnsupported(); } catch (Exception e) { nestedUnsupported = e.msg == "nested POI report range layout is not implemented"; } assert(nestedUnsupported); auto nestedText = P.m_nestedText(); copy(z8_file_resolve_path(nestedText), buildPath(args[2], "nested-text.xlsx")); bool nestedMany; try { P.m_nestedMany(); } catch (Exception e) { nestedMany = e.msg == "POI report range expansion layout is not implemented"; } assert(nestedMany);')
        contents = contents.replace('assert(nestedMany);', 'assert(nestedMany); auto nestedEval = P.m_nestedEval(); copy(z8_file_resolve_path(nestedEval), buildPath(args[2], "nested-eval.xlsx")); auto nestedQueryReport = P.m_createNestedParentQuery(); auto nestedQuery = P.m_nestedParentQuery(nestedQueryReport); auto nestedExecutor = new QueryExecutor(); nestedExecutor.amount = nestedQuery.f_amount; nestedExecutor.extra = nestedQuery.f_extra; z8_query_set_executor(nestedQuery, nestedExecutor); nestedQuery.m_start(); assert(z8_optional_require(nestedQuery.m_advance()) && z8_optional_require(nestedQuery.m_value()) == 7); nestedExecutor.reportMode = true; auto nestedQueryFile = P.m_runNestedParentQuery(nestedQueryReport); copy(z8_file_resolve_path(nestedQueryFile), buildPath(args[2], "nested-parent-query.xlsx")); assert(z8_optional_require(nestedQuery.m_value()) == 7 && z8_optional_require(nestedQuery.m_advance()) && z8_optional_require(nestedQuery.m_value()) == 8); nestedExecutor.reportRows = 2; bool nestedQueryMany; try { P.m_runNestedParentQuery(nestedQueryReport); } catch (Exception e) { nestedQueryMany = e.msg == "nested POI report expansion is not implemented"; } assert(nestedQueryMany && z8_optional_require(nestedQuery.m_value()) == 8); nestedExecutor.fail = true; bool nestedQueryFail; try { P.m_runNestedParentQuery(nestedQueryReport); } catch (Exception) { nestedQueryFail = true; } assert(nestedQueryFail && z8_optional_require(nestedQuery.m_value()) == 8); auto nestedParentJson = P.m_nestedParentJson(); copy(z8_file_resolve_path(nestedParentJson), buildPath(args[2], "nested-parent-json.xlsx")); bool nestedParentJsonEmpty; try { P.m_nestedParentJsonEmpty(); } catch (Exception e) { nestedParentJsonEmpty = e.msg == "nested POI report source is empty"; } assert(nestedParentJsonEmpty); bool nestedParentJsonMany; try { P.m_nestedParentJsonMany(); } catch (Exception e) { nestedParentJsonMany = e.msg == "nested POI report expansion is not implemented"; } assert(nestedParentJsonMany); auto nestedParent = P.m_nestedParent(); copy(z8_file_resolve_path(nestedParent), buildPath(args[2], "nested-parent.xlsx")); bool nestedParentMany; try { P.m_nestedParentMany(); } catch (Exception e) { nestedParentMany = e.msg == "nested POI report expansion is not implemented"; } assert(nestedParentMany); auto parentFail = P.m_nestedParentFail(); bool nestedParentFail; try { P.m_runNestedParentFail(parentFail); } catch (Exception) { nestedParentFail = true; } assert(nestedParentFail && z8_optional_require(P.m_nestedParentFailClosed(parentFail)) == 1); auto nestedDeepImplicit = P.m_nestedDeepImplicit(); copy(z8_file_resolve_path(nestedDeepImplicit), buildPath(args[2], "nested-deep-implicit.xlsx")); auto nestedDeep = P.m_nestedDeep(); copy(z8_file_resolve_path(nestedDeep), buildPath(args[2], "nested-deep.xlsx")); bool nestedCycle; try { P.m_nestedCycle(); } catch (Exception e) { nestedCycle = e.msg == "cyclic POI report ranges"; } assert(nestedCycle, "cycle was not rejected"); bool nestedSourceReuse; try { P.m_nestedSourceReuse(); } catch (Exception e) { nestedSourceReuse = e.msg == "nested POI report source is not implemented"; } assert(nestedSourceReuse, "ancestor source reuse was not rejected"); auto nestedCascade = P.m_nestedCascade(); copy(z8_file_resolve_path(nestedCascade), buildPath(args[2], "nested-cascade.xlsx")); auto nestedSiblings = P.m_nestedSiblings(); copy(z8_file_resolve_path(nestedSiblings), buildPath(args[2], "nested-siblings.xlsx")); bool nestedOverlap; try { P.m_nestedOverlap(); } catch (Exception e) { nestedOverlap = e.msg == "nested POI report range layout is not implemented"; } assert(nestedOverlap); auto nestedThree = P.m_nestedThree(); copy(z8_file_resolve_path(nestedThree), buildPath(args[2], "nested-three.xlsx")); auto nestedThreeVertical = P.m_nestedThreeVertical(); copy(z8_file_resolve_path(nestedThreeVertical), buildPath(args[2], "nested-three-vertical.xlsx")); bool nestedThreeUnsupported; try { P.m_nestedThreeUnsupported(); } catch (Exception e) { nestedThreeUnsupported = e.msg == "nested POI report ranges are not implemented"; } assert(nestedThreeUnsupported);')
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
            assert values == ["данные 😀 A _x0041_", "Value: данные 😀 A _x0041_!", "", ""], values
            assert float(cells[4].find("x:v", namespace).text) == 7
        with zipfile.ZipFile(working / "expanded-formula.xlsx") as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            cells = {cell.attrib["r"]: cell for cell in sheet.findall("x:sheetData/x:row/x:c", namespace)}
            assert cells["C1"].find("x:v", namespace).text == "2"
            for address in ("C2", "C3"):
                assert cells[address].find("x:f", namespace).text == "$A$1+1"
                assert cells[address].find("x:v", namespace) is None
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
  static class FakeCustom extends org.zenframework.z8.server.base.form.report.CustomData {
    FakeCustom(org.zenframework.z8.server.runtime.IObject owner) { super(owner); }
    @Override public org.zenframework.z8.server.types.integer z8_count() { return new org.zenframework.z8.server.types.integer(3); }
  }
  static class FakeCustomClass extends org.zenframework.z8.server.base.form.report.CustomData.CLASS<FakeCustom> {
    FakeCustomClass(org.zenframework.z8.server.runtime.IObject owner) { super(owner); setJavaClass(FakeCustom.class); }
    @Override public Object newObject(org.zenframework.z8.server.runtime.IObject owner) { return new FakeCustom(owner); }
  }
  static class OrderedCustom extends org.zenframework.z8.server.base.form.report.CustomData {
    static int sequence = 0;
    OrderedCustom(org.zenframework.z8.server.runtime.IObject owner) { super(owner); }
    @Override public org.zenframework.z8.server.types.integer z8_count() { return new org.zenframework.z8.server.types.integer(1); }
    @Override public void z8_open() {
      org.zenframework.z8.server.base.json.parser.JsonObject data = (org.zenframework.z8.server.base.json.parser.JsonObject)getMember("data").get();
      data.z8_set(new org.zenframework.z8.server.types.string("value"), new org.zenframework.z8.server.types.integer(++sequence));
    }
  }
  static class OrderedCustomClass extends org.zenframework.z8.server.base.form.report.CustomData.CLASS<OrderedCustom> {
    OrderedCustomClass(org.zenframework.z8.server.runtime.IObject owner) { super(owner); setJavaClass(OrderedCustom.class); }
    @Override public Object newObject(org.zenframework.z8.server.runtime.IObject owner) { return new OrderedCustom(owner); }
  }
  public static void main(String[] args) throws Exception {
    ServerConfig.load(args[2]);
    Request request = new Request(new Session("test"));
    request.getParameters().put(new org.zenframework.z8.server.types.string("foo"), new org.zenframework.z8.server.types.string("данные 😀 _x0041_ _x005F_x0041_"));
    request.getParameters().put(new org.zenframework.z8.server.types.string("nested"), new org.zenframework.z8.server.types.string("${1+2}"));
    ApplicationServer.setRequest(request);
    try (XSSFWorkbook original = new XSSFWorkbook(new FileInputStream(args[0]));
         XSSFWorkbook actual = new XSSFWorkbook(new FileInputStream(args[1]))) {
      OBJECT context = new OBJECT.CLASS<OBJECT>(null).get();
      if (args.length > 3 && ("nested-simple".equals(args[3]) || "nested-implicit-single".equals(args[3]) || "nested-text".equals(args[3]) || "nested-eval".equals(args[3]) || "nested-cascade".equals(args[3]))) {
        final boolean singleImplicitCase = "nested-implicit-single".equals(args[3]);
        final boolean textCase = "nested-text".equals(args[3]);
        final boolean cascadeCase = "nested-cascade".equals(args[3]);
        final boolean evalCase = "nested-eval".equals(args[3]) || cascadeCase;
        OBJECT.CLASS<OBJECT> rows = new OBJECT.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
        data.setIndex("data"); rows.get().members().add(data);
        final int[] sequence = {0};
        DataSource childSource = new SimpleSource(rows.get()) {
          @Override public void open() {
            super.open(); ++sequence[0];
            if (cascadeCase) data.get().z8_set(new org.zenframework.z8.server.types.string("after"), new org.zenframework.z8.server.types.string("${1+2}"));
            data.get().z8_set(new org.zenframework.z8.server.types.string("value"), textCase ?
                new org.zenframework.z8.server.types.string("обычный текст") : evalCase ?
                new org.zenframework.z8.server.types.string(cascadeCase ? "${rows.data.after}" : "${1+2}") : new org.zenframework.z8.server.types.integer(sequence[0]));
          }
        };
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context);
        Range parent = new Range().setSource(SimpleSource.newDefault()).setBlock("A1:B1").setBoundaries("A1:B1");
        parent.addRange(singleImplicitCase ? new Range().setSource(childSource).setBlock("A1:B1") : new Range().setSource(childSource).setBlock("B1").setBoundaries("B1"));
        nested.addRange(0, parent);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        if (actual.getSheetAt(0).getRow(0).getCell(0).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(0).getNumericCellValue())
          throw new AssertionError("nested parent result differs");
        if (textCase ? !actual.getSheetAt(0).getRow(0).getCell(1).getStringCellValue().equals(original.getSheetAt(0).getRow(0).getCell(1).getStringCellValue()) :
            actual.getSheetAt(0).getRow(0).getCell(1).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(1).getNumericCellValue())
          throw new AssertionError("nested child result differs");
        if (sequence[0] != 1 || original.getSheetAt(0).getRow(0).getCell(0).getNumericCellValue() != 3 ||
            (textCase ? !original.getSheetAt(0).getRow(0).getCell(1).getStringCellValue().equals("обычный текст") :
                        original.getSheetAt(0).getRow(0).getCell(1).getNumericCellValue() != (evalCase ? 3 : 1)))
          throw new AssertionError("unexpected nested range evaluation");
        return;
      }
      if (args.length > 3 && "nested-parent-query".equals(args[3])) {
        FakeQueryClass q = new FakeQueryClass(context); q.setIndex("q"); context.members().add(q);
        for (String name : new String[] {"amount", "ignored", "extra"}) {
          org.zenframework.z8.server.base.table.value.IntegerField.CLASS<org.zenframework.z8.server.base.table.value.IntegerField> field =
              new org.zenframework.z8.server.base.table.value.IntegerField.CLASS<>(q.get());
          field.setIndex(name); q.get().members().add(field);
          if ("extra".equals(name)) q.get().extraFields.add(field);
        }
        OrderedCustom.sequence = 0;
        OrderedCustomClass childRows = new OrderedCustomClass(context); childRows.setIndex("childRows"); context.members().add(childRows);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(childRows.get());
        data.setIndex("data"); childRows.get().members().add(data);
        Range parent = new Range().setSource(new QuerySource(q.get())).setBlock("A1:B1").setBoundaries("A1:B1");
        parent.addRange(new Range().setSource(new CustomSource(childRows.get())).setBlock("B1").setBoundaries("B1"));
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context); nested.addRange(0, parent);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        for (int col = 0; col < 2; ++col)
          if (actual.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() ||
              original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != (col == 0 ? 42 : 1))
            throw new AssertionError("nested query parent differs at column " + col);
        return;
      }
      if (args.length > 3 && "nested-parent-json".equals(args[3])) {
        org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<org.zenframework.z8.server.base.json.parser.JsonArray> parentRows =
            new org.zenframework.z8.server.base.json.parser.JsonArray.CLASS<>(context);
        parentRows.setIndex("parentRows"); context.members().add(parentRows);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> item =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(null);
        item.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(42));
        parentRows.get().z8_add(item);
        OrderedCustom.sequence = 0;
        OrderedCustomClass childRows = new OrderedCustomClass(context); childRows.setIndex("childRows"); context.members().add(childRows);
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(childRows.get());
        data.setIndex("data"); childRows.get().members().add(data);
        Range parent = new Range().setSource(new JsonSource(parentRows.get())).setBlock("A1:B1").setBoundaries("A1:B1");
        parent.addRange(new Range().setSource(new CustomSource(childRows.get())).setBlock("B1").setBoundaries("B1"));
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context); nested.addRange(0, parent);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        for (int col = 0; col < 2; ++col)
          if (actual.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() ||
              original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != (col == 0 ? 42 : 1))
            throw new AssertionError("nested JSON parent differs at column " + col);
        return;
      }
      if (args.length > 3 && "nested-parent".equals(args[3])) {
        OrderedCustom.sequence = 0;
        OrderedCustomClass parentRows = new OrderedCustomClass(context); parentRows.setIndex("parentRows"); context.members().add(parentRows);
        OrderedCustomClass childRows = new OrderedCustomClass(context); childRows.setIndex("childRows"); context.members().add(childRows);
        for (OrderedCustomClass rows : new OrderedCustomClass[]{parentRows, childRows}) {
          org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
              new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
          data.setIndex("data"); rows.get().members().add(data);
        }
        Range parent = new Range().setSource(new CustomSource(parentRows.get())).setBlock("A1:B1").setBoundaries("A1:B1");
        parent.addRange(new Range().setSource(new CustomSource(childRows.get())).setBlock("B1").setBoundaries("B1"));
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context); nested.addRange(0, parent);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        for (int col = 0; col < 2; ++col)
          if (actual.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() ||
              original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != col + 1)
            throw new AssertionError("nested custom parent differs at column " + col);
        if (OrderedCustom.sequence != 2) throw new AssertionError("unexpected source opening count");
        return;
      }
      if (args.length > 3 && ("nested-deep".equals(args[3]) || "nested-deep-implicit".equals(args[3]))) {
        final boolean implicitDeep = "nested-deep-implicit".equals(args[3]);
        OBJECT.CLASS<OBJECT> rows = new OBJECT.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
        data.setIndex("data"); rows.get().members().add(data);
        DataSource childSource = new SimpleSource(rows.get()) {
          @Override public void open() {
            super.open();
            data.get().z8_set(new org.zenframework.z8.server.types.string("value"), new org.zenframework.z8.server.types.string("${rows.data.step1}"));
            data.get().z8_set(new org.zenframework.z8.server.types.string("step1"), new org.zenframework.z8.server.types.string("${rows.data.step2}"));
            data.get().z8_set(new org.zenframework.z8.server.types.string("step2"), new org.zenframework.z8.server.types.string("${1+2}"));
          }
        };
        Range outer = new Range().setSource(SimpleSource.newDefault()).setBlock("A1:C1").setBoundaries("A1:C1");
        Range middle = new Range().setSource(SimpleSource.newDefault()).setBlock(implicitDeep ? "A1:C1" : "B1:C1");
        Range inner = new Range().setSource(childSource).setBlock(implicitDeep ? "A1:C1" : "C1");
        if (!implicitDeep) { middle.setBoundaries("B1:C1"); inner.setBoundaries("C1"); }
        middle.addRange(inner);
        outer.addRange(middle);
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context); nested.addRange(0, outer);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        for (int col = 0; col < 3; ++col)
          if (actual.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() ||
              original.getSheetAt(0).getRow(0).getCell(col).getNumericCellValue() != 3)
            throw new AssertionError("deep nested result differs at column " + col);
        return;
      }
      if (args.length > 3 && ("nested-siblings".equals(args[3]) || "nested-implicit-siblings".equals(args[3]) || "nested-three".equals(args[3]) || "nested-three-vertical".equals(args[3]))) {
        final boolean implicitSiblingsCase = "nested-implicit-siblings".equals(args[3]);
        final boolean verticalCase = "nested-three-vertical".equals(args[3]);
        final boolean threeCase = "nested-three".equals(args[3]) || verticalCase;
        OBJECT.CLASS<OBJECT> rows = new OBJECT.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
        data.setIndex("data"); rows.get().members().add(data);
        final int[] sequence = {0};
        DataSource childSource = new SimpleSource(rows.get()) {
          @Override public void open() {
            super.open(); data.get().z8_set(new org.zenframework.z8.server.types.string("value"),
                new org.zenframework.z8.server.types.integer(++sequence[0]));
          }
        };
        PoiReport nested = new PoiReport(new ReportOptions()).setContext(context);
        String parentBlock = verticalCase ? "A1:A4" : threeCase ? "A1:D1" : "A1:C1";
        Range parent = new Range().setSource(SimpleSource.newDefault()).setBlock(parentBlock).setBoundaries(parentBlock);
        if (threeCase) parent.addRange(new Range().setSource(childSource).setBlock(verticalCase ? "A4" : "D1").setBoundaries(verticalCase ? "A4" : "D1"));
        Range right = new Range().setSource(childSource).setBlock(verticalCase ? "A3" : "C1");
        Range left = new Range().setSource(childSource).setBlock(verticalCase ? "A2" : "B1");
        if (!implicitSiblingsCase) { right.setBoundaries(verticalCase ? "A3" : "C1"); left.setBoundaries(verticalCase ? "A2" : "B1"); }
        parent.addRange(right); parent.addRange(left);
        nested.addRange(0, parent);
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
        nested.getRange(0).apply(modifier); modifier.close();
        for (int i = 0; i < (threeCase ? 4 : 3); ++i) {
          int row = verticalCase ? i : 0, col = verticalCase ? 0 : i;
          double expected = i == 0 ? 3 : i;
          if (actual.getSheetAt(0).getRow(row).getCell(col).getNumericCellValue() != original.getSheetAt(0).getRow(row).getCell(col).getNumericCellValue() ||
              original.getSheetAt(0).getRow(row).getCell(col).getNumericCellValue() != expected)
            throw new AssertionError("nested sibling result differs at position " + i);
        }
        if (sequence[0] != (threeCase ? 3 : 2)) throw new AssertionError("unexpected nested sibling ordering");
        return;
      }
      if (args.length > 3 && "cloned-high-sheet".equals(args[3])) {
        for (int i = 0; i < 16; ++i) original.cloneSheet(0);
        original.setSheetName(16, "Final");
        PoiReport high = new PoiReport(new ReportOptions()).setContext(context);
        high.addRange(16, new Range().setSource(SimpleSource.newDefault()).setBlock("A1").setBoundaries("A1"));
        SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(16);
        high.getRange(16).apply(modifier); modifier.close();
        if (actual.getNumberOfSheets() != original.getNumberOfSheets()) throw new AssertionError("sheet count differs");
        for (int i = 0; i < original.getNumberOfSheets(); ++i)
          if (!original.getSheetName(i).equals(actual.getSheetName(i))) throw new AssertionError("sheet name differs at " + i);
        if (actual.getSheetAt(16).getRow(0).getCell(0).getNumericCellValue() != original.getSheetAt(16).getRow(0).getCell(0).getNumericCellValue())
          throw new AssertionError("high-sheet expression differs");
        return;
      }
      if (args.length > 3 && "cloned-high-multiple".equals(args[3])) {
        for (int i = 0; i < 16; ++i) original.cloneSheet(0);
        OBJECT.CLASS<OBJECT> rows = new OBJECT.CLASS<>(context);
        rows.setIndex("rows"); context.members().add(rows);
        final org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> data =
            new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(rows.get());
        data.setIndex("data"); rows.get().members().add(data);
        final int[] sequence = {0};
        DataSource source = new SimpleSource(rows.get()) {
          @Override public void open() {
            super.open(); data.get().z8_set(new org.zenframework.z8.server.types.string("value"),
                                            new org.zenframework.z8.server.types.integer(++sequence[0]));
          }
        };
        PoiReport high = new PoiReport(new ReportOptions()).setContext(context);
        high.addRange(16, new Range().setSource(source).setBlock("A1").setBoundaries("A1"));
        high.addRange(0, new Range().setSource(source).setBlock("A1").setBoundaries("A1"));
        java.util.Map<Integer, Boolean> order = new java.util.HashMap<>();
        order.put(16, true); order.put(0, true);
        SheetModifier modifier = new SheetModifier().setWorkbook(original);
        for (int sheet : order.keySet()) high.getRange(sheet).apply(modifier.setSheet(sheet));
        modifier.close();
        for (int sheet : new int[]{0, 16})
          if (actual.getSheetAt(sheet).getRow(0).getCell(0).getNumericCellValue() != original.getSheetAt(sheet).getRow(0).getCell(0).getNumericCellValue())
            throw new AssertionError("multi-sheet source order differs at " + sheet);
        if (original.getSheetAt(16).getRow(0).getCell(0).getNumericCellValue() != 1 ||
            original.getSheetAt(0).getRow(0).getCell(0).getNumericCellValue() != 2)
          throw new AssertionError("unexpected Java HashMap order");
        try (XSSFWorkbook renames = new XSSFWorkbook(new FileInputStream(args[0]))) {
          for (int i = 0; i < 16; ++i) renames.cloneSheet(0);
          java.util.Map<Integer, String> names = new java.util.HashMap<>();
          names.put(16, "Sheet1"); names.put(0, "Renamed");
          boolean duplicate = false;
          try { for (java.util.Map.Entry<Integer, String> entry : names.entrySet()) renames.setSheetName(entry.getKey(), entry.getValue()); }
          catch (IllegalArgumentException e) { duplicate = true; }
          if (!duplicate) throw new AssertionError("expected Java sheet rename conflict");
        }
        return;
      }
      boolean contextCase = args.length > 3 && "context".equals(args[3]);
      boolean fieldCase = args.length > 3 && "fields".equals(args[3]);
      boolean customCase = args.length > 3 && "custom".equals(args[3]);
      boolean expandedCustomCase = args.length > 3 && "expanded-custom".equals(args[3]);
      boolean sideConflictCase = args.length > 3 && "expanded-side-conflict".equals(args[3]);
      boolean horizontalSideConflictCase = args.length > 3 && "expanded-horizontal-side-conflict".equals(args[3]);
      boolean headerFooterCase = sideConflictCase || (args.length > 3 && "expanded-header-footer".equals(args[3]));
      boolean horizontalHeaderCase = horizontalSideConflictCase || (args.length > 3 && "expanded-horizontal-header".equals(args[3]));
      boolean multiSideCase = args.length > 3 && "expanded-multi-side".equals(args[3]);
      boolean horizontalMultiSideCase = args.length > 3 && "expanded-horizontal-multi-side".equals(args[3]);
      boolean multiFooterCase = multiSideCase || (args.length > 3 && "expanded-multi-footer".equals(args[3]));
      boolean horizontalMultiFooterCase = horizontalMultiSideCase || (args.length > 3 && "expanded-horizontal-multi-footer".equals(args[3]));
      boolean emptyMultiFooterCase = args.length > 3 && "empty-multi-footer".equals(args[3]);
      boolean emptyHorizontalMultiFooterCase = args.length > 3 && "empty-horizontal-multi-footer".equals(args[3]);
      boolean emptySideFooterCase = args.length > 3 && "empty-side-footer".equals(args[3]);
      boolean emptyHorizontalSideFooterCase = args.length > 3 && "empty-horizontal-side-footer".equals(args[3]);
      boolean emptyVerticalFooterCase = emptySideFooterCase || emptyMultiFooterCase || (args.length > 3 && ("empty-footer".equals(args[3]) || "empty-sparse-footer".equals(args[3])));
      boolean emptyHorizontalFooterCase = emptyHorizontalSideFooterCase || emptyHorizontalMultiFooterCase || (args.length > 3 && "empty-horizontal-footer".equals(args[3]));
      boolean emptyFooterCase = emptyVerticalFooterCase || emptyHorizontalFooterCase;
      boolean footerCase = headerFooterCase || multiFooterCase || (args.length > 3 && "expanded-footer".equals(args[3]));
      boolean horizontalFooterCase = horizontalHeaderCase || horizontalMultiFooterCase || (args.length > 3 && "expanded-horizontal-footer".equals(args[3]));
      boolean expandedMergedCase = args.length > 3 && ("expanded-merged".equals(args[3]) || "expanded-horizontal-merged".equals(args[3]) || "expanded-merged-formula".equals(args[3]));
      boolean expandedMultipleSheetCase = args.length > 3 && "expanded-multi-sheet".equals(args[3]);
      boolean clonedExistingCase = args.length > 3 && "cloned-existing".equals(args[3]);
      boolean clonedNamedCase = args.length > 3 && ("cloned-named".equals(args[3]) || "cloned-named-rename".equals(args[3]) || "cloned-named-original-rename".equals(args[3]) || "cloned-named-quoted-rename".equals(args[3]) || "cloned-named-digit-rename".equals(args[3]) || "cloned-named-cell-rename".equals(args[3]) || "cloned-named-russian-rename".equals(args[3]));
      boolean clonedSheetsCase = clonedExistingCase || clonedNamedCase || (args.length > 3 && ("cloned-sheets".equals(args[3]) || "cloned-suffix".equals(args[3]) || "cloned-long".equals(args[3]) || "cloned-views".equals(args[3]) || "cloned-setup".equals(args[3]) || "cloned-print".equals(args[3]) || "cloned-filter".equals(args[3])));
      boolean horizontalCase = emptyHorizontalFooterCase || horizontalFooterCase || (args.length > 3 && ("expanded-horizontal".equals(args[3]) || "expanded-horizontal-merged".equals(args[3])));
      boolean expandedEmptyCase = args.length > 3 && "expanded-empty".equals(args[3]);
      boolean jsonEmptyCase = args.length > 3 && "json-empty".equals(args[3]);
      boolean expandedTwoCase = horizontalCase || expandedEmptyCase || (args.length > 3 && "expanded-two".equals(args[3]));
      boolean expandedCase = expandedMultipleSheetCase || footerCase || expandedCustomCase || expandedTwoCase || expandedMergedCase || (args.length > 3 && "expanded".equals(args[3]));
      boolean jsonInlineCase = args.length > 3 && "json-inline".equals(args[3]);
      boolean repeatCase = args.length > 3 && "repeat".equals(args[3]);
      boolean mergedCase = args.length > 3 && "merged".equals(args[3]);
      boolean jsonCase = emptyFooterCase || jsonEmptyCase || jsonInlineCase || (expandedCase && !expandedCustomCase) || (args.length > 3 && "json".equals(args[3]));
      boolean queryCase = args.length > 3 && "query".equals(args[3]);
      boolean outsideCase = args.length > 3 && "outside".equals(args[3]);
      boolean multiSheetRenameCase = args.length > 3 && "multi-sheet-rename".equals(args[3]);
      boolean multiSheetBothRenameCase = args.length > 3 && "multi-sheet-both-rename".equals(args[3]);
      boolean multipleSheetCase = expandedMultipleSheetCase || multiSheetRenameCase || multiSheetBothRenameCase || (args.length > 3 && "multi-sheet".equals(args[3]));
      boolean multipleCase = multipleSheetCase || outsideCase || (args.length > 3 && "multiple".equals(args[3]));
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
        if (expandedCase && !emptyFooterCase) {
          item.get().z8_set(new org.zenframework.z8.server.types.string("title"), new org.zenframework.z8.server.types.string("First"));
          item.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(10));
          rows.get().z8_add(item);
          for (int i = 1; i < 3; ++i) {
            org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> next =
                new org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<>(null);
            next.get().z8_set(new org.zenframework.z8.server.types.string("title"), new org.zenframework.z8.server.types.string(i == 1 ? "Второй 😀" : "Third"));
            next.get().z8_set(new org.zenframework.z8.server.types.string("amount"), new org.zenframework.z8.server.types.integer(i == 1 ? 20 : 30));
            rows.get().z8_add(next);
          }
        } else if (!jsonEmptyCase && !emptyFooterCase) rows.get().z8_add(item);
        customSource = new JsonSource(rows.get());
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
      if (expandedCustomCase) {
        FakeCustomClass rows = new FakeCustomClass(context); rows.setIndex("rows"); context.members().add(rows);
        customSource = new CustomSource(rows.get());
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
      boolean collectionCase = args.length > 3 && "collection".equals(args[3]);
      boolean mapValueCase = args.length > 3 && "map-value".equals(args[3]);
      boolean parameters = args.length > 3 && "parameters".equals(args[3]);
      boolean dates = args.length > 3 && "dates".equals(args[3]);
      Range child = new Range().setSource(customCase || jsonCase || queryCase || expandedCustomCase ? customSource : SimpleSource.newDefault())
          .setBlock(emptySideFooterCase ? "A2:D2" : emptyHorizontalSideFooterCase ? "B1:C2" : emptyVerticalFooterCase ? "A1:D1" : headerFooterCase ? "A2:D2" : horizontalHeaderCase ? "B1:C2" : mergedCase ? "A1:B1" : expandedTwoCase ? "A1:B2" : repeatCase || jsonInlineCase ? "A1" : customCase || expandedCase || mapValueCase ? "A1:D1" : fieldCase || jsonCase || queryCase ? "A1:E1" : contextCase ? "A1:O1" : dates ? "A1:J1" : collectionCase ? "A1:I1" : constants ? "A1:G1" : parameters ? "A1:E1" : "$A$1:A1")
          .setBoundaries(emptySideFooterCase ? "A1:E3" : emptyHorizontalSideFooterCase ? "A1:D3" : multiSideCase ? "A1:E4" : horizontalMultiSideCase ? "A1:G3" : emptyMultiFooterCase ? "A1:D4" : emptyHorizontalMultiFooterCase ? "A1:G2" : emptyVerticalFooterCase ? "A1:D2" : emptyHorizontalFooterCase ? "A1:C2" : headerFooterCase ? "A1:E3" : horizontalHeaderCase ? "A1:D3" : multiFooterCase ? "A1:D4" : horizontalMultiFooterCase ? "A1:G2" : footerCase ? "A1:D2" : horizontalFooterCase ? "A1:C2" : mergedCase ? "A1:B1" : expandedTwoCase ? "A1:B2" : repeatCase || jsonInlineCase ? "A1" : customCase || expandedCase || mapValueCase ? "A1:D1" : fieldCase || jsonCase || queryCase ? "A1:E1" : contextCase ? "A1:O1" : dates ? "A1:J1" : collectionCase ? "A1:I1" : constants ? "A1:G1" : parameters ? "A1:E1" : "A1:B2");
      if (horizontalCase) child.setAxis(1);
      if (clonedSheetsCase) {
        int prototype = clonedExistingCase ? 1 : 0;
        original.cloneSheet(prototype); original.cloneSheet(prototype);
        if ("cloned-named-original-rename".equals(args[3])) original.setSheetName(0, "Renamed");
        if ("cloned-named-quoted-rename".equals(args[3])) original.setSheetName(0, "New Name");
        if ("cloned-named-digit-rename".equals(args[3])) original.setSheetName(0, "Sheet123");
        if ("cloned-named-cell-rename".equals(args[3])) original.setSheetName(0, "A1");
        if ("cloned-named-russian-rename".equals(args[3])) original.setSheetName(0, "Лист");
        if (!"cloned-named".equals(args[3])) original.setSheetName(prototype + 2, "Final");
        report.addRange(prototype + 2, new Range().setSource(SimpleSource.newDefault()).setBlock("A1").setBoundaries("A1"));
        report.addRange(0, new Range().setSource(SimpleSource.newDefault()).setBlock("A1").setBoundaries("A1"));
      } else if (expandedMultipleSheetCase) {
        report.addRange(1, new Range().setSource(orderedSources[1]).setBlock("A1").setBoundaries("A1"));
        report.addRange(0, child);
      } else if (multipleSheetCase) {
        report.addRange(1, new Range().setSource(orderedSources[1]).setBlock("A1").setBoundaries("A1"));
        report.addRange(0, new Range().setSource(orderedSources[0]).setBlock("A1").setBoundaries("A1"));
      } else if (multipleCase) {
        report.addRange(0, new Range().setSource(orderedSources[1]).setBlock("C1").setBoundaries("C1"));
        report.addRange(0, new Range().setSource(orderedSources[0]).setBlock("A1").setBoundaries("A1"));
      } else report.addRange(0, child);
      if (args.length > 3 && "rename".equals(args[3])) original.setSheetName(0, "Отчёт \\uD83D\\uDE00");
      if (multiSheetRenameCase) original.setSheetName(1, "Renamed");
      if (multiSheetBothRenameCase) { original.setSheetName(0, "First renamed"); original.setSheetName(1, "Second renamed"); }
      SheetModifier modifier = new SheetModifier().setWorkbook(original).setSheet(0);
      report.getRange(0).apply(modifier);
      if (multipleSheetCase) report.getRange(1).apply(modifier.setSheet(1));
      if (clonedSheetsCase) { int lastSheet = clonedExistingCase ? 3 : 2; report.getRange(lastSheet).apply(modifier.setSheet(lastSheet)); }
      modifier.close();
      if (expandedMultipleSheetCase) {
        double expected = original.getSheetAt(1).getRow(0).getCell(0).getNumericCellValue();
        double result = actual.getSheetAt(1).getRow(0).getCell(0).getNumericCellValue();
        if (expected != 1 || expected != result) throw new AssertionError("second sheet value differs");
      }
      if (clonedSheetsCase) {
        int count = clonedExistingCase ? 4 : 3;
        if (original.getNumberOfSheets() != count || actual.getNumberOfSheets() != count) throw new AssertionError("cloned sheet count differs");
        if (clonedNamedCase) {
          if (original.getNumberOfNames() != actual.getNumberOfNames()) throw new AssertionError("defined name count differs");
          for (int n = 0; n < original.getNumberOfNames(); ++n) {
            org.apache.poi.ss.usermodel.Name expectedName = original.getNameAt(n), actualName = actual.getNameAt(n);
            if (!expectedName.getNameName().equals(actualName.getNameName()) || expectedName.getSheetIndex() != actualName.getSheetIndex() ||
                !expectedName.getRefersToFormula().equals(actualName.getRefersToFormula())) throw new AssertionError("defined name differs: " + expectedName.getNameName() + " expected=" + expectedName.getRefersToFormula() + " actual=" + actualName.getRefersToFormula());
          }
        }
        for (int sheet = 0; sheet < count; ++sheet) {
          if (!original.getSheetName(sheet).equals(actual.getSheetName(sheet))) throw new AssertionError("cloned sheet name differs");
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(sheet).getRow(0).getCell(0), result = actual.getSheetAt(sheet).getRow(0).getCell(0);
          if (expected.getCellType() != result.getCellType() || (sheet > 0 && sheet < count - 1 ?
              !expected.getStringCellValue().equals(result.getStringCellValue()) : expected.getNumericCellValue() != result.getNumericCellValue()))
            throw new AssertionError("cloned sheet cell differs");
          if (sheet > (clonedExistingCase ? 1 : 0)) {
            if (original.getSheetAt(sheet).getCTWorksheet().isSetPageSetup() || actual.getSheetAt(sheet).getCTWorksheet().isSetPageSetup())
              throw new AssertionError("cloned page setup was not removed");
            org.openxmlformats.schemas.spreadsheetml.x2006.main.CTSheetView[] expectedViews = original.getSheetAt(sheet).getCTWorksheet().getSheetViews().getSheetViewArray();
            org.openxmlformats.schemas.spreadsheetml.x2006.main.CTSheetView[] actualViews = actual.getSheetAt(sheet).getCTWorksheet().getSheetViews().getSheetViewArray();
            if (expectedViews.length != actualViews.length) throw new AssertionError("cloned view count differs");
            for (int i = 0; i < expectedViews.length; ++i)
              if (expectedViews[i].getTabSelected() != actualViews[i].getTabSelected() || expectedViews[i].getWorkbookViewId() != actualViews[i].getWorkbookViewId() ||
                  expectedViews[i].getZoomScale() != actualViews[i].getZoomScale()) throw new AssertionError("cloned sheet view differs");
          }
          if ("cloned-print".equals(args[3])) {
            org.openxmlformats.schemas.spreadsheetml.x2006.main.CTWorksheet expectedPrint = original.getSheetAt(sheet).getCTWorksheet(), actualPrint = actual.getSheetAt(sheet).getCTWorksheet();
            if (expectedPrint.getSheetPr().getPageSetUpPr().getFitToPage() != actualPrint.getSheetPr().getPageSetUpPr().getFitToPage() ||
                expectedPrint.getPrintOptions().getHorizontalCentered() != actualPrint.getPrintOptions().getHorizontalCentered() ||
                expectedPrint.getPageMargins().getLeft() != actualPrint.getPageMargins().getLeft() ||
                !expectedPrint.getHeaderFooter().getOddHeader().equals(actualPrint.getHeaderFooter().getOddHeader()) ||
                expectedPrint.isSetPageSetup() != actualPrint.isSetPageSetup()) throw new AssertionError("print settings differ");
          }
          if ("cloned-filter".equals(args[3])) {
            org.openxmlformats.schemas.spreadsheetml.x2006.main.CTAutoFilter expectedFilter = original.getSheetAt(sheet).getCTWorksheet().getAutoFilter(), actualFilter = actual.getSheetAt(sheet).getCTWorksheet().getAutoFilter();
            if (!expectedFilter.getRef().equals(actualFilter.getRef()) || expectedFilter.sizeOfFilterColumnArray() != actualFilter.sizeOfFilterColumnArray() ||
                !expectedFilter.getFilterColumnArray(0).getFilters().getFilterArray(0).getVal().equals(actualFilter.getFilterColumnArray(0).getFilters().getFilterArray(0).getVal()))
              throw new AssertionError("cloned filter differs");
          }
        }
      } else if (multipleSheetCase && !expandedMultipleSheetCase) {
        for (int sheet = 0; sheet < 2; ++sheet) {
          double expected = original.getSheetAt(sheet).getRow(0).getCell(0).getNumericCellValue();
          double result = actual.getSheetAt(sheet).getRow(0).getCell(0).getNumericCellValue();
          if (expected != sheet + 1 || expected != result) throw new AssertionError("sheet range value differs at " + sheet);
        }
      } else if (emptyFooterCase) {
        for (int row = 0; row < (emptyMultiFooterCase ? 4 : emptySideFooterCase || emptyHorizontalSideFooterCase ? 3 : 2); ++row)
          for (int col = 0; col < (emptySideFooterCase ? 5 : emptyHorizontalSideFooterCase ? 4 : emptyVerticalFooterCase ? 4 : emptyHorizontalMultiFooterCase ? 7 : 3); ++col) {
          org.apache.poi.ss.usermodel.Row expectedRow = original.getSheetAt(0).getRow(row), actualRow = actual.getSheetAt(0).getRow(row);
          if (expectedRow == null || actualRow == null) { if (expectedRow != actualRow) throw new AssertionError("empty footer row differs"); continue; }
          org.apache.poi.ss.usermodel.Cell expected = expectedRow.getCell(col), result = actualRow.getCell(col);
          if (expected == null || result == null) { if (expected != result) throw new AssertionError("empty footer cell differs"); continue; }
          if (expected.getCellType() != result.getCellType() || expected.getCellStyle().getIndex() != result.getCellStyle().getIndex())
            throw new AssertionError("empty footer type differs");
          if (expected.getCellType() == org.apache.poi.ss.usermodel.Cell.CELL_TYPE_STRING ?
              !expected.getStringCellValue().equals(result.getStringCellValue()) : expected.getNumericCellValue() != result.getNumericCellValue())
            throw new AssertionError("empty footer value differs");
        }
      } else if (expandedCase) {
        for (int row = 0; row < (horizontalCase ? 2 : expandedTwoCase || multiFooterCase ? 6 : headerFooterCase ? 5 : footerCase ? 4 : 3); ++row)
          for (int col = 0; col < (horizontalMultiFooterCase ? 11 : horizontalHeaderCase ? 8 : horizontalFooterCase ? 7 : horizontalCase ? 6 : expandedTwoCase ? 2 : 4); ++col) {
          if (original.getSheetAt(0).getRow(row) == null) {
            if (actual.getSheetAt(0).getRow(row) != null) throw new AssertionError("unexpected physical row " + row);
            continue;
          }
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(0).getRow(row).getCell(col);
          org.apache.poi.ss.usermodel.Cell result = actual.getSheetAt(0).getRow(row).getCell(col);
          if (expected == null || result == null) {
            if (expected != result) throw new AssertionError("physical cell differs at " + row + "," + col);
            continue;
          }
          if (expected.getCellType() != result.getCellType() || expected.getCellStyle().getIndex() != result.getCellStyle().getIndex())
            throw new AssertionError("expanded cell type/style differs at " + row + "," + col);
          if (expected.getCellType() == org.apache.poi.ss.usermodel.Cell.CELL_TYPE_STRING) {
            if (!expected.getStringCellValue().equals(result.getStringCellValue())) throw new AssertionError("expanded text differs at " + row + "," + col);
          } else if (expected.getCellType() == org.apache.poi.ss.usermodel.Cell.CELL_TYPE_FORMULA) {
            if (!expected.getCellFormula().equals(result.getCellFormula()) || expected.getNumericCellValue() != result.getNumericCellValue())
              throw new AssertionError("expanded formula differs at " + row + "," + col);
          } else if (expected.getNumericCellValue() != result.getNumericCellValue())
            throw new AssertionError("expanded number differs at " + row + "," + col);
        }
        if (args[0].contains("expanded-other-columns")) for (int row = 1; row < 3; ++row) {
          double expected = original.getSheetAt(0).getRow(row).getCell(4).getNumericCellValue();
          double result = actual.getSheetAt(0).getRow(row).getCell(4).getNumericCellValue();
          if (expected != result) throw new AssertionError("unrelated cell differs at row " + row);
        }
        if (headerFooterCase || horizontalHeaderCase) {
          int sideRow = headerFooterCase ? 0 : 2, sideColumn = headerFooterCase ? 4 : 0;
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(0).getRow(sideRow).getCell(sideColumn);
          org.apache.poi.ss.usermodel.Cell result = actual.getSheetAt(0).getRow(sideRow).getCell(sideColumn);
          if (expected.getCellType() != result.getCellType() ||
              (expected.getCellType() == org.apache.poi.ss.usermodel.Cell.CELL_TYPE_STRING ?
               !expected.getStringCellValue().equals(result.getStringCellValue()) :
               expected.getNumericCellValue() != result.getNumericCellValue()))
            throw new AssertionError("side header differs");
        }
        if (sideConflictCase || horizontalSideConflictCase) {
          int row = sideConflictCase ? 4 : 2, col = sideConflictCase ? 4 : 7;
          org.apache.poi.ss.usermodel.Cell expected = original.getSheetAt(0).getRow(row).getCell(col);
          org.apache.poi.ss.usermodel.Cell result = actual.getSheetAt(0).getRow(row).getCell(col);
          if (expected == null || result == null || expected.getNumericCellValue() != result.getNumericCellValue())
            throw new AssertionError("moved side cell differs");
          row = 2; col = sideConflictCase ? 4 : 3;
          if (original.getSheetAt(0).getRow(row).getCell(col) != null || actual.getSheetAt(0).getRow(row).getCell(col) != null)
            throw new AssertionError("side cell was not cleared");
        }
        if (multiSideCase || horizontalMultiSideCase) {
          for (int i = 0; i < (multiSideCase ? 6 : 11); ++i) {
            int row = multiSideCase ? i : 2, col = multiSideCase ? 4 : i;
            org.apache.poi.ss.usermodel.Row er = original.getSheetAt(0).getRow(row), ar = actual.getSheetAt(0).getRow(row);
            org.apache.poi.ss.usermodel.Cell expected = er == null ? null : er.getCell(col), result = ar == null ? null : ar.getCell(col);
            if (expected == null || result == null) { if (expected != result) throw new AssertionError("multi-side cell differs at " + i); continue; }
            if (expected.getCellType() != result.getCellType() || expected.getNumericCellValue() != result.getNumericCellValue())
              throw new AssertionError("multi-side value differs at " + i);
          }
        }
      } else if (jsonEmptyCase) {
        org.apache.poi.ss.usermodel.Row expected = original.getSheetAt(0).getRow(0), result = actual.getSheetAt(0).getRow(0);
        if (expected == null || result == null || expected.getPhysicalNumberOfCells() != 0 || result.getPhysicalNumberOfCells() != 0 ||
            original.getSheetAt(0).getRow(1).getCell(0).getNumericCellValue() != actual.getSheetAt(0).getRow(1).getCell(0).getNumericCellValue())
          throw new AssertionError("empty source physical cells differ");
      } else if (constants || collectionCase || mapValueCase || parameters || contextCase || dates || fieldCase || customCase || jsonCase || queryCase || multipleCase || repeatCase || mergedCase) {
        for (int i = 0; i < (repeatCase || mergedCase ? 1 : outsideCase || mapValueCase ? 4 : multipleCase ? 3 : customCase ? 4 : contextCase ? 15 : dates ? 10 : collectionCase ? 9 : constants ? 7 : 5); ++i) {
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
      if (mergedCase && (original.getSheetAt(0).getNumMergedRegions() != 1 || actual.getSheetAt(0).getNumMergedRegions() != 1 ||
          !original.getSheetAt(0).getMergedRegion(0).formatAsString().equals(actual.getSheetAt(0).getMergedRegion(0).formatAsString())))
        throw new AssertionError("merged region differs");
      if (expandedMergedCase) {
        java.util.Set<String> expected = new java.util.HashSet<>(), result = new java.util.HashSet<>();
        for (int i = 0; i < original.getSheetAt(0).getNumMergedRegions(); ++i) expected.add(original.getSheetAt(0).getMergedRegion(i).formatAsString());
        for (int i = 0; i < actual.getSheetAt(0).getNumMergedRegions(); ++i) result.add(actual.getSheetAt(0).getMergedRegion(i).formatAsString());
        if (expected.size() != 3 || !expected.equals(result)) throw new AssertionError("expanded merged regions: " + expected + " != " + result);
      }
      if (!original.getSheetName(0).equals(actual.getSheetName(0))) throw new AssertionError("sheet name differs");
      if (multipleSheetCase && !original.getSheetName(1).equals(actual.getSheetName(1))) throw new AssertionError("second sheet name differs");
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
                                         str(application / "reports/collection.xlsx"), str(working / "collection.xlsx"), str(config), "collection"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/map-value.xlsx"), str(working / "map-value.xlsx"), str(config), "map-value"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/map-derived.xlsx"), str(working / "map-derived.xlsx"), str(config)],
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
                                         str(application / "reports/json.xlsx"), str(working / "json-empty.xlsx"), str(config), "json-empty"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for source_name, name in (("expanded-footer", "empty-footer"), ("expanded-sparse-footer", "empty-sparse-footer"), ("expanded-horizontal-footer", "empty-horizontal-footer"),
                                          ("expanded-side-conflict", "empty-side-footer"), ("expanded-horizontal-side-conflict", "empty-horizontal-side-footer"),
                                          ("expanded-multi-footer", "empty-multi-footer"), ("expanded-horizontal-multi-footer", "empty-horizontal-multi-footer")):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + source_name + ".xlsx")), str(working / (name + ".xlsx")), str(config), name],
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
                                         str(application / "reports/multi-sheet.xlsx"), str(working / "multi-sheet.xlsx"), str(config), "multi-sheet"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for name in ("multi-sheet-rename", "multi-sheet-both-rename"):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / "reports/multi-sheet.xlsx"), str(working / (name + ".xlsx")), str(config), name],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-multi-sheet.xlsx"), str(working / "expanded-multi-sheet.xlsx"), str(config), "expanded-multi-sheet"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/constant.xlsx"), str(working / "cloned-sheets.xlsx"), str(config), "cloned-sheets"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/constant.xlsx"), str(working / "cloned-high-sheet.xlsx"), str(config), "cloned-high-sheet"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/ordered-high.xlsx"), str(working / "cloned-high-multiple.xlsx"), str(config), "cloned-high-multiple"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-simple.xlsx"), str(working / "nested-simple.xlsx"), str(config), "nested-simple"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-simple.xlsx"), str(working / "nested-text.xlsx"), str(config), "nested-text"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-simple.xlsx"), str(working / "nested-eval.xlsx"), str(config), "nested-eval"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-simple.xlsx"), str(working / "nested-cascade.xlsx"), str(config), "nested-cascade"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-siblings.xlsx"), str(working / "nested-siblings.xlsx"), str(config), "nested-siblings"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-three.xlsx"), str(working / "nested-three.xlsx"), str(config), "nested-three"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-three-vertical.xlsx"), str(working / "nested-three-vertical.xlsx"), str(config), "nested-three-vertical"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-deep.xlsx"), str(working / "nested-deep.xlsx"), str(config), "nested-deep"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-parent.xlsx"), str(working / "nested-parent.xlsx"), str(config), "nested-parent"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-parent-json.xlsx"), str(working / "nested-parent-json.xlsx"), str(config), "nested-parent-json"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-parent-query.xlsx"), str(working / "nested-parent-query.xlsx"), str(config), "nested-parent-query"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for fixture, case in (("nested-simple", "nested-implicit-single"), ("nested-siblings", "nested-implicit-siblings")):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + fixture + ".xlsx")), str(working / (case + ".xlsx")), str(config), case],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/nested-deep.xlsx"), str(working / "nested-deep-implicit.xlsx"), str(config), "nested-deep-implicit"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for source_name, name in (("clone-suffix", "cloned-suffix"), ("clone-long", "cloned-long"), ("clone-existing", "cloned-existing"), ("clone-views", "cloned-views"), ("clone-setup", "cloned-setup"), ("clone-print", "cloned-print"), ("clone-filter", "cloned-filter"), ("clone-named", "cloned-named"), ("clone-named", "cloned-named-rename"), ("clone-named", "cloned-named-original-rename"), ("clone-named", "cloned-named-quoted-rename"), ("clone-named", "cloned-named-digit-rename"), ("clone-named", "cloned-named-cell-rename"), ("clone-named", "cloned-named-russian-rename")):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + source_name + ".xlsx")), str(working / (name + ".xlsx")), str(config), name],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/outside-range.xlsx"), str(working / "outside-range.xlsx"), str(config), "outside"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded.xlsx"), str(working / "expanded.xlsx"), str(config), "expanded"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for name in ("expanded-static", "expanded-rich", "expanded-inline-number", "expanded-inline-constant", "expanded-other-columns", "expanded-occupied", "expanded-formula", "expanded-complex-formula", "expanded-parenthesized", "expanded-functions", "expanded-missing-source"):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + name + ".xlsx")), str(working / (name + ".xlsx")), str(config), "expanded"],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                inline = application / "reports/expanded-inline.xlsx"
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(inline), str(inline), str(config), "expanded"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode != 0 and "NullPointerException" in result.stderr, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-custom.xlsx"), str(working / "expanded-custom.xlsx"), str(config), "expanded-custom"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-two.xlsx"), str(working / "expanded-two.xlsx"), str(config), "expanded-two"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-empty-row.xlsx"), str(working / "expanded-empty-row.xlsx"), str(config), "expanded-empty"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-horizontal.xlsx"), str(working / "expanded-horizontal.xlsx"), str(config), "expanded-horizontal"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/repeat.xlsx"), str(working / "repeat.xlsx"), str(config), "repeat"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                inline = application / "reports/json-inline.xlsx"
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(inline), str(inline), str(config), "json-inline"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode != 0 and "NullPointerException" in result.stderr, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/merged-inside.xlsx"), str(working / "merged-inside.xlsx"), str(config), "merged"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                for name in ("expanded-merged", "expanded-horizontal-merged", "expanded-merged-formula"):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + name + ".xlsx")), str(working / (name + ".xlsx")), str(config), name],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                for name in ("expanded-footer", "expanded-horizontal-footer", "expanded-multi-footer", "expanded-horizontal-multi-footer", "expanded-header-footer", "expanded-horizontal-header", "expanded-side-conflict", "expanded-horizontal-side-conflict", "expanded-multi-side", "expanded-horizontal-multi-side"):
                    result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                             str(application / ("reports/" + name + ".xlsx")), str(working / (name + ".xlsx")), str(config), name],
                                            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-sparse-footer.xlsx"), str(working / "expanded-sparse-footer.xlsx"), str(config), "expanded-footer"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-sparse-formula.xlsx"), str(working / "expanded-sparse-formula.xlsx"), str(config), "expanded-footer"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
                result = subprocess.run(["java", "-cp", str(temp) + os.pathsep + range_classpath, "PoiRangeOracle",
                                         str(application / "reports/expanded-sparse-block.xlsx"), str(working / "expanded-sparse-block.xlsx"), str(config), "expanded-footer"],
                                        cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
                assert result.returncode == 0, result.stderr
print("POI static report template, naming and transaction verified")
