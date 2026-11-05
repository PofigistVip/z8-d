"""Compare unbound IntegerField and StringField values with Java Z8."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2: raise SystemExit("Usage: python tests/typed_fields_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not jars: raise SystemExit("Original server JAR not found")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "TypedOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.value.*;
import org.zenframework.z8.server.types.*;
public class TypedOracle {
    static void show(Field f) { System.out.println(f.get().toString() + ":" + f.changed() + ":" + f.wasNull()); }
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        IntegerField number = new IntegerField(null); show(number);
        number.defaultValue = new integer(4); show(number);
        number.set(new integer(7)); show(number);
        number.setDefault(new integer(11)); show(number); number.reset(); show(number);
        StringField text = new StringField(null); show(text);
        text.defaultValue = new string("start"); show(text);
        text.set(new string("changed")); show(text);
        text.setDefault(new string("replacement")); show(text); text.reset(); show(text);
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp, str(java)], check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "TypedOracle"], text=True, encoding="utf-8").splitlines()
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import std.stdio : writeln;
class Field : Z8Object {}
class IntegerField : Field {}
class StringField : Field {}
Z8Object makeField() { return new Field(); }
Z8Object makeInt() { return new IntegerField(); }
Z8Object makeText() { return new StringField(); }
void show(Z8Object f) {
    auto p = z8_native_call!Z8Primary("org.zenframework.z8.server.base.table.value.Field.m_primary"w, f);
    auto changed = z8_native_call!(Z8Optional!bool)("org.zenframework.z8.server.base.table.value.Field.m_isChanged"w, f);
    auto wasNull = z8_native_call!(Z8Optional!bool)("org.zenframework.z8.server.base.table.value.Field.m_wasNull"w, f);
    writeln(z8_primary_to_string(p), ":", z8_optional_require(changed), ":", z8_optional_require(wasNull));
}
void main() {
    enum prefix = "org.zenframework.z8.server.base.table.value."w;
    z8_native_register_factory(prefix ~ "Field"w, typeid(Field), &makeField);
    z8_native_register_factory(prefix ~ "IntegerField"w, typeid(IntegerField), &makeInt);
    z8_native_register_factory(prefix ~ "StringField"w, typeid(StringField), &makeText);
    auto number = makeInt(); z8_native_call!void(prefix ~ "IntegerField.m_new"w, number); show(number);
    z8_native_field!(Z8Optional!long)(prefix ~ "IntegerField.f_defaultValue"w, number) = z8_optional_wrap(4L); show(number);
    z8_field_set(number, z8_primary_box(7L)); show(number);
    z8_field_set_default(number, z8_primary_box(11L)); show(number); z8_field_reset(number); show(number);
    auto text = makeText(); z8_native_call!void(prefix ~ "StringField.m_new"w, text); show(text);
    z8_native_field!wstring(prefix ~ "StringField.f_defaultValue"w, text) = "start"w; show(text);
    z8_field_set(text, z8_primary_box("changed"w)); show(text);
    z8_field_set_default(text, z8_primary_box("replacement"w)); show(text); z8_field_reset(text); show(text);
}
''', encoding="utf-8")
    exe = temp / ("typed.exe" if os.name == "nt" else "typed")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(exe)], check=True)
    actual = subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()
    if actual != expected: raise SystemExit(f"Typed fields differ:\nD: {actual}\nJava: {expected}")
print("Integer and string field values match Java Z8")
