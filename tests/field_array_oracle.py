"""Compare grouped Field.array conversions with the original Java runtime."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/field_array_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not jars:
    raise SystemExit("Original server JAR not found")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "FieldArrayOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.value.*;
import org.zenframework.z8.server.types.*;
import org.zenframework.z8.server.runtime.RCollection;
public class FieldArrayOracle {
    static void show(Field field, String input) {
        try {
            RCollection values = field.array(new string(input));
            StringBuilder line = new StringBuilder("OK");
            for (Object value : values) line.append(':').append(value.toString());
            System.out.println(line);
        } catch (RuntimeException e) { System.out.println("ERROR"); }
    }
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field lang = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        lang.setAccessible(true); lang.set(null, "en");
        IntegerField i = new IntegerField(null); BoolField b = new BoolField(null);
        StringField s = new StringField(null); DecimalField d = new DecimalField(null); GuidField g = new GuidField(null);
        show(i, "[1,2,\\"3L\\"]"); show(i, "[]");
        show(b, "[true,false,\\"yes\\"]"); show(b, "[\\"invalid\\"]");
        show(s, "[\\"first\\",42]"); show(s, "[]");
        show(d, "[1.25,\\"2\\",\\"\\"]");
        show(g, "[\\"00000000-0000-0000-0000-000000000005\\"]");
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp, str(java)], check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "FieldArrayOracle"], text=True, encoding="utf-8").splitlines()
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import std.stdio : writeln;
class Field : Z8Object {}
class IntegerField : Field {}
class BoolField : Field {}
class StringField : Field {}
class DecimalField : Field {}
class GuidField : Field {}
Z8Object makeField() { return new Field(); }
Z8Object makeInt() { return new IntegerField(); }
Z8Object makeBool() { return new BoolField(); }
Z8Object makeString() { return new StringField(); }
Z8Object makeDecimal() { return new DecimalField(); }
Z8Object makeGuid() { return new GuidField(); }
class Cursor : IZ8FieldCursor {
    wstring json;
    bool isClosed() { return false; }
    bool isGrouped() { return true; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) { assert(asArray); return z8_primary_box(json); }
}
void show(T)(Z8Object field, Cursor cursor, wstring input, wstring name) {
    cursor.json = input;
    try {
        auto values = z8_native_call!(Z8Array!T)(name, field);
        wstring line = "OK"w;
        for (long i; i < values.z8_size(); ++i) {
            static if (is(T == wstring)) {
                auto value = values.z8_get(i); line ~= ":"w ~ (value is null ? "null"w : value);
            } else line ~= ":"w ~ z8_primary_to_string(z8_primary_box(values.z8_get(i)));
        }
        writeln(line);
    } catch (Exception e) { writeln("ERROR"); }
}
void main() {
    enum p = "org.zenframework.z8.server.base.table.value."w;
    z8_native_register_factory(p ~ "Field"w, typeid(Field), &makeField);
    z8_native_register_factory(p ~ "IntegerField"w, typeid(IntegerField), &makeInt);
    z8_native_register_factory(p ~ "BoolField"w, typeid(BoolField), &makeBool);
    z8_native_register_factory(p ~ "StringField"w, typeid(StringField), &makeString);
    z8_native_register_factory(p ~ "DecimalField"w, typeid(DecimalField), &makeDecimal);
    z8_native_register_factory(p ~ "GuidField"w, typeid(GuidField), &makeGuid);
    auto cursor = new Cursor(); auto i = makeInt(); auto b = makeBool(); auto s = makeString(); auto d = makeDecimal(); auto g = makeGuid();
    foreach (field; [i,b,s,d,g]) { z8_field_set_cursor(field, cursor); z8_field_set_aggregation(field, Z8FieldAggregation.array); }
    show!long(i,cursor,`[1,2,"3L"]`w,p ~ "IntegerField.m_array"w); show!long(i,cursor,`[]`w,p ~ "IntegerField.m_array"w);
    show!bool(b,cursor,`[true,false,"yes"]`w,p ~ "BoolField.m_array"w); show!bool(b,cursor,`["invalid"]`w,p ~ "BoolField.m_array"w);
    show!wstring(s,cursor,`["first",42]`w,p ~ "StringField.m_array"w); show!wstring(s,cursor,`[]`w,p ~ "StringField.m_array"w);
    show!Z8Decimal(d,cursor,`[1.25,"2",""]`w,p ~ "DecimalField.m_array"w);
    show!Z8Guid(g,cursor,`["00000000-0000-0000-0000-000000000005"]`w,p ~ "GuidField.m_array"w);
}
''', encoding="utf-8")
    exe = temp / ("field-array.exe" if os.name == "nt" else "field-array")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    actual = subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"Field arrays differ:\nD: {actual}\nJava: {expected}")
print("Grouped Field.array conversions match Java Z8")
