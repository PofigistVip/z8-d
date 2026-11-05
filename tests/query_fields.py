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
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
public class Probe {
    public static Report make() { Report query; return query; }
    public static bool check(Report query) {
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
    bool missing; try { query.m_getFieldByIndex("missing"w); } catch (Exception) { missing = true; }
    assert(missing);
}
''', encoding="utf-8")
    exe = temp / ("query-fields.exe" if os.name == "nt" else "query-fields")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Query data and primary field discovery verified")
