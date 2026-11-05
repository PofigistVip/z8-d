"""Compare the native BL JsonWriter adapter with the original Java writer.

Usage: python tests/json_writer_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/json_writer_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
server_jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
deps = [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
deps += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not server_jars:
    raise SystemExit("Original server JAR not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "JsonObject.bl").write_text('''
[native "org.zenframework.z8.server.base.json.parser.JsonObject"] public class JsonObject {
    public static JsonObject parse(string value);
}
''', encoding="utf-8")
    (source / "JsonArray.bl").write_text('''
[native "org.zenframework.z8.server.base.json.parser.JsonArray"] public class JsonArray {
    public static JsonArray parse(string value);
}
''', encoding="utf-8")
    (source / "Field.bl").write_text('[native "org.zenframework.z8.server.base.table.value.Field"] public class Field {}', encoding="utf-8")
    (source / "JsonWriter.bl").write_text('''
[native "org.zenframework.z8.server.base.json.JsonWriter"] public class JsonWriter {
    public JsonWriter startObject(); public JsonWriter startObject(string name); public JsonWriter finishObject();
    public JsonWriter startArray(); public JsonWriter startArray(string name); public JsonWriter finishArray();
    public JsonWriter write(primary value); public JsonWriter write(primary[] value);
    public JsonWriter write(JsonObject value); public JsonWriter write(JsonArray value);
    public JsonWriter writeProperty(string name, primary value); public JsonWriter writeProperty(string name, primary[] value);
    public JsonWriter writeProperty(string name, JsonObject value); public JsonWriter writeProperty(string name, JsonArray value);
    public JsonWriter writeProperty(Field value);
    public string toString();
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static string run() {
        JsonWriter writer;
        primary nil = null;
        writer.startObject().writeProperty("message", "line\\n</tag>")
            .writeProperty("n", 42).writeProperty("flag", true).writeProperty("missing", nil)
            .writeProperty("amount", decimal.parse("12.30")).writeProperty("max", int.Max)
            .writeProperty("day", date.Min).writeProperty("id", guid.create(5))
            .writeProperty("geo", geometry.point(1, 2, 4326))
            .writeProperty("list", primary[] {1, true, "x"})
            .writeProperty("nested", JsonArray.parse("[1,2]"))
            .writeProperty("object", JsonObject.parse("{v:1}"));
        Field field; writer.writeProperty(field);
        writer.startArray("items").write("one").write(2).startObject().writeProperty("ok", false).finishObject().finishArray();
        writer.finishObject();
        return writer.toString();
    }
    public static bool empty() { JsonWriter writer; return writer.toString() != null && writer.toString() == ""; }
    public static string failure() {
        JsonWriter writer; writer.startObject();
        try { writer.writeProperty("bad", primary[] {null}); } catch (exception expected) {}
        return writer.toString();
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
wstring fieldId(Z8Object value) { return "field"w; }
Z8Primary fieldValue(Z8Object value) { return z8_primary_box(99L); }
void main() {
    z8_native_bind("org.zenframework.z8.server.runtime.OBJECT.m_id"w, &fieldId);
    z8_native_bind("org.zenframework.z8.server.base.table.value.Field.m_primary"w, &fieldValue);
    assert(z8_optional_require(Z8p_50726F6265.m_empty()));
    writeln(Z8p_50726F6265.m_run());
    writeln(Z8p_50726F6265.m_failure());
}
''', encoding="utf-8")
    executable = temp / ("json-writer.exe" if os.name == "nt" else "json-writer")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").strip()
    java = temp / "WriterOracle.java"
    java.write_text('''
import org.zenframework.z8.server.json.JsonWriter;
import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.*;
public class WriterOracle {
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        JsonWriter w = new JsonWriter(true);
        RCollection<primary> values = new RCollection<primary>();
        values.add(new integer(1)); values.add(new bool(true)); values.add(new string("x"));
        w.startObject().writeProperty("message", new string("line\\n</tag>"))
         .writeProperty("n", new integer(42)).writeProperty("flag", new bool(true))
         .writeProperty("missing", (primary)null).writeProperty("amount", new decimal("12.30"))
         .writeProperty("max", integer.Max).writeProperty("day", date.Min).writeProperty("id", guid.create(5))
         .writeProperty("geo", geometry.z8_point(new decimal(1), new decimal(2), new integer(4326)))
         .writeProperty("list", values).writeProperty("nested", new org.zenframework.z8.server.json.parser.JsonArray("[1,2]"))
         .writeProperty("object", new org.zenframework.z8.server.json.parser.JsonObject("{v:1}"))
         .writeProperty("field", new integer(99));
        w.startArray("items").write(new string("one")).write(new integer(2))
         .startObject().writeProperty("ok", new bool(false)).finishObject().finishArray();
        w.finishObject();
        System.out.println(w.toString());
        JsonWriter broken = new JsonWriter(true); broken.startObject();
        RCollection<primary> nulls = new RCollection<primary>(); nulls.add(null);
        try { broken.writeProperty("bad", nulls); } catch (RuntimeException expected) {}
        System.out.println(broken.toString());
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, [*server_jars, *deps]))
    current_writer = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/json/JsonWriter.java"
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp, "-d", str(temp), str(current_writer), str(original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/geometry/parser/GeoJsonWriter.java"), str(original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/types/decimal.java"), str(original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/types/date.java"), str(original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/json/parser/JsonObject.java"), str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "WriterOracle"], cwd=temp, text=True, encoding="utf-8").strip()
    if actual != expected:
        raise SystemExit("JsonWriter differs from Java:\nD: " + actual + "\nJava: " + expected)
print("JsonWriter native adapter matches original Java output")
