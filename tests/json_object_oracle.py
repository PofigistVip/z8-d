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
        String source = "{name:'Привет',count:'-9',fraction:12.75,precise:7413.04345526901443,suffix:'1L',flag:true,word:'true',empty:null,id:'00112233-4455-6677-8899-aabbccddeeff',day:'2024-02-29T12:34:56',nested:{k:1},list:[1,2]}";
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
        value.operatorAssign(new string(""));
        System.out.println(value.z8_isEmpty().get());
        System.out.println(JsonObject.z8_parse(null) == null);
        for (String input : new String[] {"", "  ", "{}", "{x:1; y=2}", "[]", "{name:'unterminated", "{a:1,}", "null", "42"}) {
            try { JsonObject.z8_parse(new string(input)); System.out.println("ok"); }
            catch (RuntimeException expected) { System.out.println("error"); }
        }
    }
}
""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    server_source = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server"
    current_sources = list((server_source / "json/parser").glob("*.java")) + [
        server_source / "base/json/parser/JsonObject.java",
        server_source / "base/json/parser/JsonArray.java",
        server_source / "types/date.java",
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
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
import std.algorithm : sort;
import std.array : join;
void main() {
    alias P = Z8p_50726F6265;
    auto value = P.m_parse("{name:'Привет',count:'-9',fraction:12.75,precise:7413.04345526901443,suffix:'1L',flag:true,word:'true',empty:null,id:'00112233-4455-6677-8899-aabbccddeeff',day:'2024-02-29T12:34:56',nested:{k:1},list:[1,2]}"w);
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
    P.m_assign(value, ""w);
    writeln(z8_optional_require(P.m_empty(value)));
    writeln(P.m_parse(null) is null);
    foreach (input; [""w, "  "w, "{}"w, "{x:1; y=2}"w, "[]"w, "{name:'unterminated"w, "{a:1,}"w, "null"w, "42"w]) {
        try { P.m_parse(input); writeln("ok"); } catch (Exception) { writeln("error"); }
    }
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
