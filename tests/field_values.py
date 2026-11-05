"""Exercise the common native Field value interface and JsonWriter binding."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/field_values.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Object.bl").write_text('[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object { virtual public string toString(); public bool operator == (Object object); public bool operator != (Object object); }', encoding="utf-8")
    (source / "Field.bl").write_text('''
[native "org.zenframework.z8.server.base.table.value.Field"] public class Field extends Object {
    public Field valueFrom; public Field valueFor; public Field[] usedFields; public Field[] columns;
    public primary primary(); public int int(); public string string(); public bool bool(); public guid guid();
    public bool isChanged(); public bool wasNull();
}
''', encoding="utf-8")
    (source / "JsonWriter.bl").write_text('''
[native "org.zenframework.z8.server.base.json.JsonWriter"] public class JsonWriter {
    public JsonWriter startObject(); public JsonWriter finishObject(); public JsonWriter writeProperty(Field field); public string toString();
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static Field create() { Field value; return value; }
    public static bool original(Field value) {
        return value.int() == 42 && value.primary().toString() == "42" && value.toString() == "42" && !value.isChanged() && value.wasNull();
    }
    public static bool changed(Field value) { return value.string() == "new" && value.isChanged() && !value.wasNull(); }
    public static Field links(Field value) {
        Field first; Field second;
        if (value.valueFrom != null || value.valueFor != null || value.usedFields.size() != 0 || value.columns.size() != 0) return null;
        value.valueFrom = second; value.valueFor = first;
        value.usedFields.add(first); value.usedFields.add(value); value.usedFields.add(first);
        value.columns.add(second);
        if (value.valueFrom != second || value.valueFor != first || value.usedFields.size() != 3 || value.columns[0] != second) return null;
        return first;
    }
    public static string json(Field value) {
        JsonWriter writer; writer.startObject().writeProperty(value).finishObject(); return writer.toString();
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        for name in ("Object", "Field", "JsonWriter"): (source / (name + ".bl")).unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.table.value.Field;\nimport org.zenframework.z8.base.json.JsonWriter;\n" + probe.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    auto field = P.m_create(); field.z8_set_container(new Z8Object()); field.z8_set_index("amount"w);
    auto state = new Z8FieldState(z8_primary_box(42L)); z8_field_attach(field, state);
    auto first = P.m_links(field); assert(first !is null);
    auto related = z8_field_fields(field);
    assert(related.length == 3 && related[0] is field && related[1] is first && related[2] is state.valueFrom);
    assert(state.valueFor is first);
    assert(z8_optional_require(P.m_original(field)));
    assert(P.m_json(field) == `{"amount":42}`w);
    z8_field_set(field, z8_primary_box("new"w)); state.wasNull = false;
    assert(z8_optional_require(P.m_changed(field)));
    assert(P.m_json(field) == `{"amount":"new"}`w);
    z8_field_set(field, z8_primary_box("another"w));
    z8_field_reset(field); state.wasNull = true;
    assert(z8_optional_require(P.m_original(field)));
    z8_field_set_default(field, z8_primary_box(7L));
    assert(!state.changed && z8_optional_require(z8_primary_cast!long(state.value)) == 7);
}
''', encoding="utf-8")
    exe = temp / ("field-values.exe" if os.name == "nt" else "field-values")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Native Field values, changes, null flag and JSON verified")
