"""Exercise report sources, static overloads and CustomData callbacks."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/report_source.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomRows.bl").write_text('''
import org.zenframework.z8.base.form.report.CustomData;
public class CustomRows extends CustomData {
    public int opened = 0; public int closed = 0;
    virtual public int count() { return 2; }
    virtual public void open() { if (getIndex() == -1 && getSheet() == 3) opened += 1; }
    virtual public void close() { closed += 1; }
}
''', encoding="utf-8")
    (source / "SourceProbe.bl").write_text('''
import org.zenframework.z8.base.form.report.DataSource;
import org.zenframework.z8.base.json.JsonArray;
import org.zenframework.z8.lang.Object;
public class SourceProbe {
    public static DataSource custom(CustomRows rows) { DataSource value; value = rows; return value; }
    public static DataSource json(JsonArray rows) { DataSource value; value = rows; return value; }
    public static DataSource simple(Object object) { DataSource value; value = object; return value; }
    public static JsonArray values() { JsonArray result; result.add("one"); result.add("two"); return result; }
}
''', encoding="utf-8")
    (source / "ConfiguredReport.bl").write_text('''
import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.form.report.Range;
import org.zenframework.z8.base.form.report.DataSource;
import org.zenframework.z8.base.json.JsonArray;
import org.zenframework.z8.lang.Object;
public class ConfiguredReport extends Report {
    [address "A1:B2"] public Range parent;
    public Range child;
    parent.ranges = {child}; ranges = {parent};
    public void configure(JsonArray rows) {
        parent.source = rows;
        string[] columns = {"B", "C"}; hiddenColumns.add(0, columns);
    }
    public bool verify() {
        return ranges.size() == 1 && parent.ranges.size() == 1 && parent.ranges[0] == child &&
            hiddenColumns.get(0).size() == 2 && Range.Vertical == 0 && Range.Horizontal == 1;
    }
    public DataSource sourceByName(string name) { return getDataSource(name); }
    public DataSource sourceByObject(Object value) { return getDataSource(value); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_SourceProbe;
import z8gen.p_CustomRows;
import z8gen.p_ConfiguredReport;
void main() {
    alias P = Z8p_536F7572636550726F6265;
    auto rows = z8_new!Z8p_437573746F6D526F7773(); z8_nonnull(rows);
    auto custom = P.m_custom(rows); z8_nonnull(custom);
    bool unopened; try { custom.m_getIndex(); } catch (Exception) { unopened = true; } assert(unopened);
    z8_report_source_open(custom, 3); assert(z8_optional_require(rows.f_opened) == 1);
    assert(z8_optional_require(custom.m_getIndex()) == -1 && z8_report_source_count(custom) == 2);
    assert(z8_report_source_next(custom) && z8_optional_require(rows.m_getIndex()) == 0);
    assert(z8_report_source_next(custom) && z8_optional_require(rows.m_getIndex()) == 1);
    assert(!z8_report_source_next(custom)); z8_report_source_close(custom);
    assert(z8_optional_require(rows.f_closed) == 1);
    auto values = P.m_values(); auto json = P.m_json(values); z8_report_source_open(json, 0);
    assert(z8_report_source_count(json) == 2 && z8_report_source_next(json) && z8_report_source_next(json) && !z8_report_source_next(json));
    auto simple = P.m_simple(values); z8_report_source_open(simple, 0);
    assert(z8_report_source_count(simple) == 1 && z8_report_source_next(simple) && !z8_report_source_next(simple));
    auto report = z8_new!Z8p_436F6E666967757265645265706F7274(); z8_nonnull(report);
    values.z8_set_container(report); values.z8_set_index("rows"w);
    report.m_configure(values); assert(z8_optional_require(report.m_verify()));
    auto range = report.f_parent; assert(range.z8_get_attribute("address"w) == "A1:B2"w);
    auto rangeSource = range.f_source; assert(z8_report_source_object(rangeSource) is values);
    z8_report_register_data_source(report, rangeSource);
    assert(report.m_sourceByName("rows"w) is rangeSource && report.m_sourceByObject(values) is rangeSource);
}
''', encoding="utf-8")
    executable = temp / ("report-source.exe" if os.name == "nt" else "report-source")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Report data source overloads and custom callbacks verified")
