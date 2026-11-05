"""Verify native Table system fields on a generated BL subclass."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/table_fields.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Report.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
public class Report extends Table { public IntField amount; }
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
public class Probe {
    public static Report make() { Report value; return value; }
    public static bool check(Report value) {
        Field[] fields = value.fields();
        if (fields.size() != 7 || value.primaryFields().size() != 7 || value.objects.size() != 7) return false;
        if (fields[0] != value.recordId || fields[1] != value.createdAt || fields[2] != value.modifiedAt) return false;
        if (fields[3] != value.createdBy || fields[4] != value.modifiedBy || fields[5] != value.lock || fields[6] != value.amount) return false;
        if (value.recordId.id() != "recordId" || value.recordId.name() != "RecordId") return false;
        if (value.getFieldByName("Lock") != value.lock || value.getFieldByIndex("amount") != value.amount) return false;
        if (value.recordId.get() != guid.Null || value.recordId() != guid.Null || value.lock.get() != 0 || value.createdAt.get() != date.Min) return false;
        value.recordId = guid.create(7); if (value.recordId() != guid.create(7)) return false;
        return true;
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
    auto table = P.m_make(); assert(z8_optional_require(P.m_check(table)));
    assert(z8_query_primary_key(table) is table.f_recordId());
    assert(table.f_recordId().z8_get_attribute("primaryKey"w) == ""w);
    assert(table.f_lock().z8_get_attribute("lockKey"w) == ""w);
}
''', encoding="utf-8")
    exe = temp / ("table-fields.exe" if os.name == "nt" else "table-fields")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Table system fields and metadata verified")
