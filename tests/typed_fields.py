"""Exercise native integer and string field values without a database cursor."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/typed_fields.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Object.bl").write_text('[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {}', encoding="utf-8")
    (source / "Field.bl").write_text('''
[native "org.zenframework.z8.server.base.table.value.Field"] public class Field extends Object {
    public primary primary(); public int int(); public string string(); public bool bool(); public decimal decimal(); public guid guid();
    public bool isChanged(); public bool wasNull();
}
''', encoding="utf-8")
    (source / "IntField.bl").write_text('''
[native "org.zenframework.z8.server.base.table.value.IntegerField"] public class IntField extends Field {
    public int defaultValue = 0; virtual public int getDefault(); public void setDefault(int value);
    virtual public int get(); public IntField operator = (int value);
}
''', encoding="utf-8")
    (source / "StringField.bl").write_text('''
[native "org.zenframework.z8.server.base.table.value.StringField"] public class StringField extends Field {
    public string defaultValue = ""; virtual public string getDefault(); public void setDefault(string value);
    virtual public string get(); public StringField operator = (string value);
}
''', encoding="utf-8")
    for name, kind, native in (("BoolField", "bool", "BoolField"), ("DecimalField", "decimal", "DecimalField"), ("GuidField", "guid", "GuidField")):
        (source / (name + ".bl")).write_text(f'''
[native "org.zenframework.z8.server.base.table.value.{native}"] public class {name} extends Field {{
    public {kind} defaultValue; virtual public {kind} getDefault(); public void setDefault({kind} value);
    virtual public {kind} get(); public {name} operator = ({kind} value);
}}
''', encoding="utf-8")
    (source / "Custom.bl").write_text('public class Custom extends IntField { virtual public int get() { return 99; } }', encoding="utf-8")
    (source / "CustomBool.bl").write_text('public class CustomBool extends BoolField { virtual public bool get() { return true; } }', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static IntField make() { IntField field; field.defaultValue = 4; return field; }
    public static bool run() {
        IntField number;
        if (number.get() != 0 || number.defaultValue != 0 || number.isChanged() || !number.wasNull()) return false;
        number.defaultValue = 4;
        if (number.getDefault() != 4 || number.int() != 4 || number.isChanged()) return false;
        number = 7;
        if (number.get() != 7 || number.defaultValue != 7 || !number.isChanged() || !number.wasNull()) return false;
        number.setDefault(11);
        if (number.get() != 11 || !number.isChanged()) return false;
        StringField text;
        if (text.get() != "" || text.defaultValue != "" || text.isChanged()) return false;
        text.defaultValue = "start";
        if (text.getDefault() != "start" || text.string() != "start") return false;
        text = "changed";
        if (text.get() != "changed" || text.defaultValue != "changed" || !text.isChanged()) return false;
        text.setDefault("replacement");
        if (text.get() != "replacement" || !text.isChanged()) return false;
        BoolField flag;
        if (flag.get() || flag.defaultValue || flag.isChanged()) return false;
        flag.defaultValue = true; if (!flag.getDefault() || !flag.bool()) return false;
        flag = false; if (flag.get() || !flag.isChanged()) return false;
        DecimalField amount;
        if (amount.get() != decimal.parse("0")) return false;
        amount.defaultValue = 12.5; if (amount.decimal() != 12.5) return false;
        amount = 7.25; if (amount.get() != 7.25 || !amount.isChanged()) return false;
        GuidField id;
        if (id.get() != guid.Null) return false;
        id.defaultValue = guid.create(1); if (id.guid() != guid.create(1)) return false;
        id = guid.create(2); if (id.get() != guid.create(2) || !id.isChanged()) return false;
        CustomBool customBool; if (!customBool.bool() || customBool.primary().toString() != "true") return false;
        Custom custom;
        return custom.get() == 99 && custom.int() == 99 && custom.primary().toString() == "99";
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        for name in ("Object", "Field", "IntField", "StringField", "BoolField", "DecimalField", "GuidField"): (source / (name + ".bl")).unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        for name in ("Custom", "CustomBool", "Probe"):
            path = source / (name + ".bl")
            path.write_text("import org.zenframework.z8.base.table.value.IntField;\nimport org.zenframework.z8.base.table.value.StringField;\nimport org.zenframework.z8.base.table.value.BoolField;\nimport org.zenframework.z8.base.table.value.DecimalField;\nimport org.zenframework.z8.base.table.value.GuidField;\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    assert(z8_optional_require(P.m_run()));
    auto field = P.m_make();
    z8_field_set(field, z8_primary_box(9L));
    z8_field_set_default(field, z8_primary_box(11L));
    z8_field_reset(field);
    assert(z8_optional_require(z8_primary_cast!long(z8_native_call!Z8Primary(
        "org.zenframework.z8.server.base.table.value.Field.m_primary"w, field))) == 4);
}
''', encoding="utf-8")
    exe = temp / ("typed-fields.exe" if os.name == "nt" else "typed-fields")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Integer, string, boolean, decimal and GUID field values verified")
