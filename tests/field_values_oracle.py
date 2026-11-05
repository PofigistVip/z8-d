"""Compare host-populated field state with the original Java IntegerField."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2: raise SystemExit("Usage: python tests/field_values_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not jars: raise SystemExit("Original server JAR not found")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "FieldOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.value.IntegerField;
import org.zenframework.z8.server.types.integer;
public class FieldOracle {
    static void show(IntegerField field) {
        System.out.println(field.get().toString() + ":" + field.changed() + ":" + field.wasNull());
    }
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        IntegerField field = new IntegerField(null);
        field.setDefault(new integer(42)); show(field);
        field.set(new integer(7)); field.setWasNull(false); show(field);
        field.set(new integer(9)); show(field);
        field.reset(); show(field);
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp, str(java)], check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "FieldOracle"], text=True, encoding="utf-8").splitlines()
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import std.stdio : writeln;
class Field : Z8Object {}
Z8Object createField() { return new Field(); }
void show(Z8Object field) {
    auto value = z8_native_call!Z8Primary("org.zenframework.z8.server.base.table.value.Field.m_primary"w, field);
    auto changed = z8_native_call!(Z8Optional!bool)("org.zenframework.z8.server.base.table.value.Field.m_isChanged"w, field);
    auto wasNull = z8_native_call!(Z8Optional!bool)("org.zenframework.z8.server.base.table.value.Field.m_wasNull"w, field);
    writeln(z8_primary_to_string(value), ":", z8_optional_require(changed), ":", z8_optional_require(wasNull));
}
void main() {
    z8_native_register_factory("org.zenframework.z8.server.base.table.value.Field"w, typeid(Field), &createField);
    auto field = new Field(); auto state = new Z8FieldState(z8_primary_box(42L)); z8_field_attach(field, state);
    show(field); z8_field_set(field, z8_primary_box(7L)); state.wasNull = false; show(field);
    z8_field_set(field, z8_primary_box(9L)); show(field); z8_field_reset(field); show(field);
}
''', encoding="utf-8")
    exe = temp / ("field.exe" if os.name == "nt" else "field")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(exe)], check=True)
    actual = subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()
    if actual != expected: raise SystemExit(f"Field values differ:\nD: {actual}\nJava: {expected}")
print("Field values and changes match the original Java runtime")
