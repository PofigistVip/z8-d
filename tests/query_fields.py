"""Exercise Query field discovery on generated BL objects."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/query_fields.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Nested.bl").write_text('''
import org.zenframework.z8.lang.Object;
import org.zenframework.z8.base.table.value.StringField;
public class Nested extends Object { public StringField tag; }
''', encoding="utf-8")
    (source / "Report.bl").write_text('''
import org.zenframework.z8.base.query.Query;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.IntExpression;
import org.zenframework.z8.base.table.value.StringField;
public class Report extends Query {
    [name "Amount"] public IntField amount;
    public IntExpression calculated;
    public StringField label;
    public Nested nested;
}
''', encoding="utf-8")
    (source / "Configured.bl").write_text('''
public class Configured extends Report {
    columns = { amount, label };
    controls = { amount };
    limit = 17;
}
''', encoding="utf-8")
    (source / "DetailTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
public class DetailTable extends Table { public StringField detailName; public StringField detailCode; }
''', encoding="utf-8")
    (source / "DependentTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.form.Form;
import org.zenframework.z8.base.form.Listbox;
public class DependentTable extends Table {
    public DetailTable detail;
    public Form form; form.controls = {detail.detailName};
    public Form next; next.controls = {detail.detailCode}; form.dependencies = {next};
    public Listbox list; list.query = detail; list.dependencies = {form};
    controls = {list, form, next};
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.query.ReadLock;
public class Probe {
    public static Report make() { Report query; return query; }
    public static Configured configured() { Configured query; return query; }
    public static DependentTable dependent() { DependentTable query; return query; }
    public static bool checkDependent(DependentTable query) {
        return query.detail.extraFields.size() == 2 && query.detail.extraFields[0] == query.detail.detailName &&
            query.detail.extraFields[1] == query.detail.detailCode;
    }
    public static bool checkConfigured(Configured query) {
        return query.limit == 17 && query.columns.size() == 2 && query.columns[0] == query.amount && query.columns[1] == query.label && query.controls[0] == query.amount;
    }
    public static bool check(Report query) {
        if (query.priority != null || query.limit != null || query.colCount != 4 || query.readOnly || query.totals || query.readLock != ReadLock.None) return false;
        if (query.controls.size() != 0 || query.columns.size() != 0 || query.names.size() != 0 || query.groupBy.size() != 0) return false;
        query.priority = 2; query.limit = 50; query.colCount = 3; query.readOnly = true; query.totals = true;
        query.readLock = ReadLock.ShareNoWait; query.period = query.amount;
        query.columns.add(query.amount); query.names.add(query.label); query.controls.add(query.amount); query.groupBy.add(query.label);
        if (query.priority != 2 || query.limit != 50 || query.colCount != 3 || !query.readOnly || !query.totals || query.readLock != ReadLock.ShareNoWait) return false;
        if (query.period != query.amount || query.columns[0] != query.amount || query.names[0] != query.label || query.controls[0] != query.amount || query.groupBy[0] != query.label) return false;
        Field[] all = query.fields(); Field[] primary = query.primaryFields();
        if (all.size() != 3 || primary.size() != 2) return false;
        if (all[0] != query.amount || all[1] != query.calculated || all[2] != query.label) return false;
        if (primary[0] != query.amount || primary[1] != query.label) return false;
        if (query.getFieldByIndex("amount") != query.amount || query.getFieldById("amount") != query.amount) return false;
        if (query.getFieldByName("Amount") != query.amount) return false;
        if (query.findFieldById("nested.tag") != query.nested.tag) return false;
        all.clear(); return query.fields().size() == 3;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    auto query = P.m_make(); assert(z8_optional_require(P.m_check(query)));
    auto configured = P.m_configured(); assert(z8_optional_require(P.m_checkConfigured(configured)) && z8_query_limit(configured) == 17);
    assert(z8_query_read_lock(query) == Z8QueryReadLock.shareNoWait);
    assert(z8_query_limit(query) == 50 && z8_query_array(query, "columns"w).length == 1 && z8_query_array(query, "groupBy"w).length == 1);
    assert(z8_query_array(query, "sortFields"w).length == 0);
    auto dependent = P.m_dependent();
    assert(z8_query_form_fields(dependent).length == 0);
    assert(z8_query_array(dependent.f_detail, "extraFields"w).length == 2);
    assert(z8_optional_require(P.m_checkDependent(dependent)));
    assert(z8_query_form_fields(dependent.f_detail).length == 2);
    bool missing; try { query.m_getFieldByIndex("missing"w); } catch (Exception) { missing = true; }
    assert(missing);
}
''', encoding="utf-8")
    exe = temp / ("query-fields.exe" if os.name == "nt" else "query-fields")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Query data and primary field discovery verified")
