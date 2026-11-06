"""Compare native JsonObject reading with the original Z8 implementation.

Usage: python tests/json_object_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/json_object_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
jars = sorted((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
if not language.is_dir() or not any(p.name.startswith("org.zenframework.z8.server-") for p in jars):
    raise SystemExit("Original BL library or server JAR not found")
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
for dependency in (cache / "commons-logging/commons-logging", cache / "org.zenframework.z8.dependencies.commons",
                   cache / "commons-io/commons-io/2.7"):
    if dependency.exists():
        jars.extend(p for p in dependency.rglob("*.jar") if not p.name.endswith("-sources.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Probe.bl").write_text("""
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonUtil;
public class Probe {
    public static JsonObject parse(string text) { return JsonObject.parse(text); }
    public static void assign(JsonObject object, string text) { object = text; }
    public static bool empty(JsonObject object) { return object.isEmpty(); }
    public static bool has(JsonObject object, string name) { return object.has(name); }
    public static string text(JsonObject object, string name) { return object.getString(name); }
    public static int integer(JsonObject object, string name) { return object.getInt(name); }
    public static decimal decimalValue(JsonObject object, string name) { return object.getDecimal(name); }
    public static bool flag(JsonObject object, string name) { return object.getBool(name); }
    public static guid id(JsonObject object, string name) { return object.getGuid(name); }
    public static date day(JsonObject object, string name) { return object.getDate(name); }
    public static string[] names(JsonObject object) { return object.getNames(); }
    public static JsonObject put(JsonObject object, string name, primary entry) { return object.set(name, entry); }
    public static JsonObject putLegacy(JsonObject object, string name, primary entry) { return object.put(name, entry); }
    public static JsonObject nested(JsonObject object, string name) { return object.getJsonObject(name); }
    public static JsonObject remove(JsonObject object, string name) { return object.remove(name); }
    public static string render(JsonObject object) { return (string)object; }
    public static string display(JsonObject object) { return object.toString(); }
    public static string pretty(JsonObject object, int indent) { return JsonUtil.prettyPrint(object, indent); }
}
""", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    java = temp / "JsonObjectOracle.java"
    java.write_text("""
import java.util.*;
import org.zenframework.z8.server.base.json.parser.JsonObject;
import org.zenframework.z8.server.types.string;
class JsonObjectOracle {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        String source = "{name:'Привет',count:'-9',fraction:12.75,precise:7413.04345526901443,suffix:'1L',flag:true,word:'true',empty:null,id:'00112233-4455-6677-8899-aabbccddeeff',day:'2024-02-29T12:34:56',nested:{k:1},list:[1.0,2]}";
        JsonObject value = JsonObject.z8_parse(new string(source)).get();
        System.out.println(value.z8_isEmpty().get());
        for (String key : new String[] {"name", "count", "precise", "flag", "word", "empty", "missing", "nested", "list"})
            System.out.println(value.z8_has(new string(key)).get() + ":" + value.z8_getString(new string(key)).get());
        System.out.println(value.z8_getInt(new string("count")).get());
        System.out.println(value.z8_getInt(new string("fraction")).get());
        System.out.println(value.z8_getDecimal(new string("fraction")).toString());
        System.out.println(value.z8_getDecimal(new string("count")).toString());
        System.out.println(value.z8_getDecimal(new string("precise")).toString());
        System.out.println(value.z8_getBool(new string("flag")).get() + ":" + value.z8_getBool(new string("word")).get());
        System.out.println(value.z8_getGuid(new string("id")).toString());
        System.out.println(value.z8_getGuid(new string("missing")) == null);
        System.out.println(value.z8_getDate(new string("day")).getTicks());
        ArrayList<String> names = new ArrayList<String>();
        for (string name : value.z8_getNames()) names.add(name.get());
        Collections.sort(names);
        System.out.println(String.join(",", names));
        try { value.z8_getBool(new string("missing")); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        try { value.z8_getInt(new string("flag")); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        try { value.z8_getInt(new string("suffix")); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        value.z8_set(new string("storedInt"), new org.zenframework.z8.server.types.integer(43));
        value.z8_put(new string("legacy"), new org.zenframework.z8.server.types.integer(19));
        System.out.println(value.z8_getInt(new string("legacy")).get());
        value.z8_set(new string("storedBool"), new org.zenframework.z8.server.types.bool(false));
        value.z8_set(new string("storedText"), new string("hello"));
        value.z8_set(new string("storedGuid"), new org.zenframework.z8.server.types.guid("00112233-4455-6677-8899-aabbccddeeff"));
        value.z8_set(new string("storedSpan"), new org.zenframework.z8.server.types.datespan(12345));
        value.z8_set(new string("storedDate"), new org.zenframework.z8.server.types.date(0L));
        value.z8_set(new string("storedMin"), org.zenframework.z8.server.types.date.Min);
        value.z8_set(new string("storedNaN"), org.zenframework.z8.server.types.decimal.NaN);
        value.z8_set(new string("storedNull"), (org.zenframework.z8.server.types.primary)null);
        for (String key : new String[] {"storedInt", "storedBool", "storedText", "storedGuid", "storedSpan", "storedDate", "storedMin", "storedNaN", "storedNull"})
            System.out.println(value.z8_has(new string(key)).get() + ":" + value.z8_getString(new string(key)).get());
        org.zenframework.z8.server.types.file attachment = new org.zenframework.z8.server.types.file();
        attachment.name = new string("документ.txt"); attachment.path = new string("files/doc.txt");
        attachment.size = new org.zenframework.z8.server.types.integer(123);
        attachment.time = new org.zenframework.z8.server.types.date(0L);
        attachment.details.put(new string("language"), new string("русский"));
        value.z8_set(new string("attachment"), attachment);
        attachment.name = new string("changed"); attachment.details.put(new string("language"), new string("changed"));
        JsonObject stored = value.z8_getJsonObject(new string("attachment")).get();
        for (String key : new String[] {"name", "path", "size", "time", "id", "user"})
            System.out.println("file:" + key + ":" + stored.z8_getString(new string(key)).get());
        System.out.println("file:detail:" + stored.z8_getJsonObject(new string("details")).get().z8_getString(new string("language")).get());
        stored.z8_set(new string("name"), new string("nested change"));
        System.out.println("file:mutated:" + value.z8_getJsonObject(new string("attachment")).get().z8_getString(new string("name")).get());
        org.zenframework.z8.server.types.geometry shape = new org.zenframework.z8.server.types.geometry(1, 2, 3857);
        JsonObject geometryObject = JsonObject.z8_parse(new string("{}")).get();
        geometryObject.z8_set(new string("shape"), shape);
        System.out.println("geometry:" + geometryObject.z8_getString(new string("shape")).get() + ":" + geometryObject.string().get());
        shape.set(new org.zenframework.z8.server.types.geometry(3, 4, 4326));
        System.out.println("geometry:changed:" + geometryObject.string().get());
        shape.set(new org.zenframework.z8.server.types.geometry());
        System.out.println("geometry:empty:" + geometryObject.z8_getString(new string("shape")).get() + ":" + geometryObject.string().get());
        geometryObject.z8_set(new string("shape"), new string("replacement"));
        System.out.println("geometry:replaced:" + geometryObject.string().get());
        for (String input : new String[] {"12345678901234567890.2500", "1E+3", "1E-7", "-18446744073709551617.99"}) {
            value.z8_set(new string("decimal"), new org.zenframework.z8.server.types.decimal(input));
            System.out.println(value.z8_getString(new string("decimal")).get() + ":" + value.z8_getInt(new string("decimal")).get());
            System.out.println(value.z8_getDecimal(new string("decimal")).toString() + ":" + value.z8_getBool(new string("decimal")).get());
        }
        try { value.z8_set(new string("decimal"), new org.zenframework.z8.server.types.binary()); System.out.println("bad"); }
        catch (RuntimeException expected) { System.out.println(value.z8_getString(new string("decimal")).get()); }
        value.z8_set(new string("decimal"), new org.zenframework.z8.server.types.integer(7));
        System.out.println(value.z8_getString(new string("decimal")).get());
        value.z8_remove(new string("decimal"));
        System.out.println(value.z8_has(new string("decimal")).get());
        value.operatorAssign(new string(""));
        System.out.println(value.z8_isEmpty().get());
        System.out.println(JsonObject.z8_parse(null) == null);
        for (String input : new String[] {"", "  ", "{}", "{x:1; y=2}", "[]", "{name:'unterminated", "{a:1,}", "null", "42"}) {
            try { JsonObject.z8_parse(new string(input)); System.out.println("ok"); }
            catch (RuntimeException expected) { System.out.println("error"); }
        }
        for (String input : new String[] {"{}", "{a:1.0}", "{a:-0.0}", "{a:'</script>'}", "{a:' '}", "{a:[1.0,true,null]}"}) {
            JsonObject item = JsonObject.z8_parse(new string(input)).get();
            System.out.println(item.string().get());
            System.out.println(item.z8_toString().get());
        }
        for (String number : new String[] {"1.2500", "1E+3", "1E-7", "12345678901234567890.2500"}) {
            JsonObject item = JsonObject.z8_parse(new string("{}")).get();
            item.z8_set(new string("a"), new org.zenframework.z8.server.types.decimal(number));
            System.out.println(item.string().get());
        }
        JsonObject escaped = JsonObject.z8_parse(new string("{}")).get();
        escaped.z8_set(new string("a"), new string("line\\n\\t\\"\\\\end"));
        System.out.println(escaped.string().get());
        for (String input : new String[] {"{}", "{a:[1,null,{b:'<>&=中文'}]}", "{a:null}", "{a:null,b:1}", "{a:{b:null}}", "{a:1234567890123}"}) {
            JsonObject item = JsonObject.z8_parse(new string(input)).get();
            for (int indent : new int[] {-1, 0, 2, 4}) {
                System.out.println("pretty:");
                System.out.println(org.zenframework.z8.server.base.json.parser.JsonUtil.prettyPrint(item.get(), indent));
            }
        }
        escaped.z8_set(new string("a"), new string("apostrophe ' and \\n newline"));
        System.out.println("pretty:"); System.out.println(org.zenframework.z8.server.base.json.parser.JsonUtil.prettyPrint(escaped.get(), 2));
        escaped.z8_set(new string("a"), new org.zenframework.z8.server.types.decimal("12345678901234567890.2500"));
        System.out.println("pretty:"); System.out.println(org.zenframework.z8.server.base.json.parser.JsonUtil.prettyPrint(escaped.get(), 2));
    }
}
""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    server_source = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server"
    current_sources = list((server_source / "json/parser").glob("*.java")) + [
        server_source / "base/json/parser/JsonObject.java",
        server_source / "base/json/parser/JsonArray.java",
        server_source / "base/json/parser/JsonUtil.java",
        server_source / "types/date.java",
        server_source / "types/decimal.java",
        server_source / "types/file.java",
        server_source / "types/binary.java",
        original / "org.zenframework.z8.boot/src/main/java/org/zenframework/z8/rmi/ObjectIO.java",
    ]
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, "-d", str(temp),
                    *map(str, current_sources)], cwd=temp, check=True)
    current_classpath = str(temp) + os.pathsep + classpath
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", current_classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", current_classpath, "JsonObjectOracle", str(config)],
                                       cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
import std.conv : to;
import std.algorithm : sort;
import std.array : join;
void main() {
    alias P = Z8p_50726F6265;
    auto value = P.m_parse("{name:'Привет',count:'-9',fraction:12.75,precise:7413.04345526901443,suffix:'1L',flag:true,word:'true',empty:null,id:'00112233-4455-6677-8899-aabbccddeeff',day:'2024-02-29T12:34:56',nested:{k:1},list:[1.0,2]}"w);
    writeln(z8_optional_require(P.m_empty(value)));
    foreach (key; ["name"w, "count"w, "precise"w, "flag"w, "word"w, "empty"w, "missing"w, "nested"w, "list"w])
        writeln(z8_optional_require(P.m_has(value, key)), ":", P.m_text(value, key).to!string);
    writeln(z8_optional_require(P.m_integer(value, "count"w)));
    writeln(z8_optional_require(P.m_integer(value, "fraction"w)));
    writeln(z8_optional_require(P.m_decimalValue(value, "fraction"w)).z8_string());
    writeln(z8_optional_require(P.m_decimalValue(value, "count"w)).z8_string());
    writeln(z8_optional_require(P.m_decimalValue(value, "precise"w)).z8_string());
    writeln(z8_optional_require(P.m_flag(value, "flag"w)), ":", z8_optional_require(P.m_flag(value, "word"w)));
    writeln(z8_guid_to_string(P.m_id(value, "id"w)).to!string);
    writeln(P.m_id(value, "missing"w) is null);
    writeln(z8_date_ticks(P.m_day(value, "day"w)));
    auto names = P.m_names(value);
    string[] strings;
    foreach (i; 0 .. names.z8_size()) strings ~= names.z8_get(i).to!string;
    sort(strings);
    writeln(strings.join(","));
    try { P.m_flag(value, "missing"w); writeln("bad"); } catch (Exception) { writeln("error"); }
    try { P.m_integer(value, "flag"w); writeln("bad"); } catch (Exception) { writeln("error"); }
    try { P.m_integer(value, "suffix"w); writeln("bad"); } catch (Exception) { writeln("error"); }
    assert(P.m_put(value, "storedInt"w, z8_primary_box(43L)) is value);
    assert(P.m_putLegacy(value, "legacy"w, z8_primary_box(19L)) is value);
    writeln(z8_optional_require(P.m_integer(value, "legacy"w)));
    P.m_put(value, "storedBool"w, z8_primary_box(false));
    P.m_put(value, "storedText"w, z8_primary_box("hello"w));
    P.m_put(value, "storedGuid"w, z8_primary_box(z8_guid_literal("00112233-4455-6677-8899-aabbccddeeff")));
    P.m_put(value, "storedSpan"w, z8_primary_box(new Z8Datespan(12345)));
    P.m_put(value, "storedDate"w, z8_primary_box(z8_date_from_ticks(0)));
    P.m_put(value, "storedMin"w, z8_primary_box(z8_date_min));
    P.m_put(value, "storedNaN"w, z8_primary_box(z8_decimal_nan()));
    P.m_put(value, "storedNull"w, null);
    foreach (key; ["storedInt"w, "storedBool"w, "storedText"w, "storedGuid"w, "storedSpan"w, "storedDate"w, "storedMin"w, "storedNaN"w, "storedNull"w])
        writeln(z8_optional_require(P.m_has(value, key)), ":", P.m_text(value, key).to!string);
    auto attachment = new Z8File(); attachment.name = "документ.txt"w; attachment.path = "files/doc.txt"w;
    attachment.size = z8_optional_wrap(123L); attachment.time = z8_date_from_ticks(0);
    attachment.details.z8_add("language"w, "русский"w);
    P.m_put(value, "attachment"w, z8_primary_box(attachment));
    attachment.name = "changed"w; attachment.details.z8_add("language"w, "changed"w);
    auto stored = P.m_nested(value, "attachment"w);
    foreach (key; ["name"w, "path"w, "size"w, "time"w, "id"w, "user"w])
        writeln("file:", key.to!string, ":", P.m_text(stored, key).to!string);
    writeln("file:detail:", P.m_text(P.m_nested(stored, "details"w), "language"w).to!string);
    P.m_put(stored, "name"w, z8_primary_box("nested change"w));
    writeln("file:mutated:", P.m_text(P.m_nested(value, "attachment"w), "name"w).to!string);
    auto shape = z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 3857);
    auto geometryObject = P.m_parse("{}"w);
    P.m_put(geometryObject, "shape"w, z8_primary_box(shape));
    writeln("geometry:", P.m_text(geometryObject, "shape"w).to!string, ":", P.m_render(geometryObject).to!string);
    shape.x = 3; shape.y = 4; shape.srs = 4326; shape.rawHex = null;
    writeln("geometry:changed:", P.m_render(geometryObject).to!string);
    shape.shape = -1; shape.rawHex = null;
    writeln("geometry:empty:", P.m_text(geometryObject, "shape"w).to!string, ":", P.m_render(geometryObject).to!string);
    P.m_put(geometryObject, "shape"w, z8_primary_box("replacement"w));
    writeln("geometry:replaced:", P.m_render(geometryObject).to!string);
    foreach (input; ["12345678901234567890.2500"w, "1E+3"w, "1E-7"w, "-18446744073709551617.99"w]) {
        P.m_put(value, "decimal"w, z8_primary_box(z8_decimal_parse(input)));
        writeln(P.m_text(value, "decimal"w).to!string, ":", z8_optional_require(P.m_integer(value, "decimal"w)));
        writeln(z8_optional_require(P.m_decimalValue(value, "decimal"w)).z8_string(), ":", z8_optional_require(P.m_flag(value, "decimal"w)));
    }
    try { P.m_put(value, "decimal"w, z8_primary_box(new Z8Binary())); writeln("bad"); }
    catch (Exception) { writeln(P.m_text(value, "decimal"w).to!string); }
    P.m_put(value, "decimal"w, z8_primary_box(7L));
    writeln(P.m_text(value, "decimal"w).to!string);
    assert(P.m_remove(value, "decimal"w) is value);
    writeln(z8_optional_require(P.m_has(value, "decimal"w)));
    P.m_assign(value, ""w);
    writeln(z8_optional_require(P.m_empty(value)));
    writeln(P.m_parse(null) is null);
    foreach (input; [""w, "  "w, "{}"w, "{x:1; y=2}"w, "[]"w, "{name:'unterminated"w, "{a:1,}"w, "null"w, "42"w]) {
        try { P.m_parse(input); writeln("ok"); } catch (Exception) { writeln("error"); }
    }
    foreach (input; ["{}"w, "{a:1.0}"w, "{a:-0.0}"w, "{a:'</script>'}"w, "{a:' '}"w, "{a:[1.0,true,null]}"w]) {
        auto item = P.m_parse(input);
        writeln(P.m_render(item).to!string);
        writeln(P.m_display(item).to!string);
    }
    foreach (number; ["1.2500"w, "1E+3"w, "1E-7"w, "12345678901234567890.2500"w]) {
        auto item = P.m_parse("{}"w);
        P.m_put(item, "a"w, z8_primary_box(z8_decimal_parse(number)));
        writeln(P.m_render(item).to!string);
    }
    auto escaped = P.m_parse("{}"w);
    P.m_put(escaped, "a"w, z8_primary_box("line\\n\\t\\"\\\\end"w));
    writeln(P.m_render(escaped).to!string);
    foreach (input; ["{}"w, "{a:[1,null,{b:'<>&=中文'}]}"w, "{a:null}"w, "{a:null,b:1}"w, "{a:{b:null}}"w, "{a:1234567890123}"w]) {
        auto item = P.m_parse(input);
        foreach (indent; [-1L, 0L, 2L, 4L]) { writeln("pretty:"); writeln(P.m_pretty(item, indent).to!string); }
    }
    P.m_put(escaped, "a"w, z8_primary_box("apostrophe ' and \\n newline"w));
    writeln("pretty:"); writeln(P.m_pretty(escaped, 2).to!string);
    P.m_put(escaped, "a"w, z8_primary_box(z8_decimal_parse("12345678901234567890.2500"w)));
    writeln("pretty:"); writeln(P.m_pretty(escaped, 2).to!string);
    z8_native_clear_bindings();
    z8_bind_builtin_object();
    z8_bind_builtin_json_object();
    assert(z8_optional_require(P.m_empty(P.m_parse(""w))));
}
""", encoding="utf-8")
    executable = temp / ("json-object.exe" if os.name == "nt" else "json-object")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"JsonObject differs:\nJava={expected!r}\nD={actual!r}")
print("JsonObject parsing, getters and assignment match Java")
