"""Compare native JsonArray reading with current original Z8 sources.

Usage: python tests/json_array_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/json_array_oracle.py <original-z8-root>")
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
import org.zenframework.z8.base.json.JsonArray;
public class Probe {
    public static JsonArray parse(string text) { return JsonArray.parse(text); }
    public static void assign(JsonArray array, string text) { array = text; }
    public static bool empty(JsonArray array) { return array.isEmpty(); }
    public static int size(JsonArray array) { return array.size(); }
    public static string text(JsonArray array, int index) { return array.getString(index); }
    public static int integer(JsonArray array, int index) { return array.getInt(index); }
    public static decimal decimalValue(JsonArray array, int index) { return array.getDecimal(index); }
    public static bool flag(JsonArray array, int index) { return array.getBool(index); }
    public static guid id(JsonArray array, int index) { return array.getGuid(index); }
    public static int[] ints(JsonArray array) { return array.toIntArray(); }
    public static string[] strings(JsonArray array) { return array.toStringArray(); }
    public static bool[] bools(JsonArray array) { return array.toBoolArray(); }
    public static decimal[] decimals(JsonArray array) { return array.toDecimalArray(); }
    public static guid[] ids(JsonArray array) { return array.toGuidArray(); }
    public static date[] dates(JsonArray array) { return array.toDateArray(); }
    public static string render(JsonArray array) { return (string)array; }
    public static string display(JsonArray array) { return array.toString(); }
}
""", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    java = temp / "JsonArrayOracle.java"
    java.write_text("""
import org.zenframework.z8.server.base.json.parser.JsonArray;
import org.zenframework.z8.server.types.*;
class JsonArrayOracle {
    static JsonArray parse(String value) { return JsonArray.z8_parse(new string(value)).get(); }
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        JsonArray value = parse("[1,2147483648,3.9,'-9',true,'yes',null,'00112233-4455-6677-8899-aabbccddeeff']");
        System.out.println(value.z8_isEmpty().get() + ":" + value.z8_size().get());
        for (int i : new int[] {0,1,2,3}) System.out.println(value.z8_getInt(new integer(i)).get());
        System.out.println(value.z8_getInt(new integer(4294967296L)).get());
        System.out.println(value.z8_getDecimal(new integer(2)).toString());
        System.out.println(value.z8_getBool(new integer(4)).get() + ":" + value.z8_getBool(new integer(5)).get());
        System.out.println(value.z8_getString(new integer(6)).get());
        System.out.println(value.z8_getGuid(new integer(7)).toString());
        try { value.z8_getBool(new integer(6)); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        try { value.z8_getInt(new integer(8)); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        System.out.println(value.string().get());
        System.out.println(value.z8_toString().get());
        for (integer x : parse("[1,-2,'3',2147483648]").z8_toIntArray()) System.out.println("i:" + x.get());
        for (string x : parse("['Привет',null,'',12,true]").z8_toStringArray()) System.out.println("s:" + (x == null ? "<null>" : x.get()));
        for (bool x : parse("[true,false,'yes',null,'0']").z8_toBoolArray()) System.out.println("b:" + x.get());
        for (decimal x : parse("[1.25,'2.5',-3]").z8_toDecimalArray()) System.out.println("d:" + x.toString());
        for (guid x : parse("['00112233-4455-6677-8899-aabbccddeeff',null]").z8_toGuidArray()) System.out.println("g:" + (x == null ? "<null>" : x.toString()));
        for (date x : parse("['2024-02-29T12:34:56',null,'0','']").z8_toDateArray()) System.out.println("t:" + (x == null ? "<null>" : x.getTicks()));
        for (String input : new String[] {"", "1,2", " [1,2]", "[1,]", "[1,,2]", "[1", "{x:1}"}) {
            try { System.out.println("p:" + parse(input).string().get()); } catch (RuntimeException expected) { System.out.println("p:error"); }
        }
        value.operatorAssign(new string(""));
        System.out.println(value.z8_isEmpty().get());
        System.out.println(JsonArray.z8_parse(null) == null);
    }
}
""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    server_source = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server"
    current_sources = list((server_source / "json/parser").glob("*.java")) + [
        server_source / "base/json/parser/JsonObject.java", server_source / "base/json/parser/JsonArray.java",
        server_source / "types/date.java", server_source / "types/decimal.java",
    ]
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, "-d", str(temp),
                    *map(str, current_sources)], cwd=temp, check=True)
    current_classpath = str(temp) + os.pathsep + classpath
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", current_classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", current_classpath, "JsonArrayOracle", str(config)],
                                       cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
void main() {
    alias P = Z8p_50726F6265;
    auto value = P.m_parse("[1,2147483648,3.9,'-9',true,'yes',null,'00112233-4455-6677-8899-aabbccddeeff']"w);
    writeln(z8_optional_require(P.m_empty(value)), ":", z8_optional_require(P.m_size(value)));
    foreach (i; [0, 1, 2, 3]) writeln(z8_optional_require(P.m_integer(value, i)));
    writeln(z8_optional_require(P.m_integer(value, 4294967296L)));
    writeln(z8_optional_require(P.m_decimalValue(value, 2)).z8_string());
    writeln(z8_optional_require(P.m_flag(value, 4)), ":", z8_optional_require(P.m_flag(value, 5)));
    writeln(P.m_text(value, 6).to!string);
    writeln(z8_guid_to_string(P.m_id(value, 7)).to!string);
    try { P.m_flag(value, 6); writeln("bad"); } catch (Exception) { writeln("error"); }
    try { P.m_integer(value, 8); writeln("bad"); } catch (Exception) { writeln("error"); }
    writeln(P.m_render(value).to!string);
    writeln(P.m_display(value).to!string);
    auto ints = P.m_ints(P.m_parse("[1,-2,'3',2147483648]"w));
    foreach (i; 0 .. ints.z8_size()) writeln("i:", z8_optional_require(ints.z8_get(i)));
    auto strings = P.m_strings(P.m_parse("['Привет',null,'',12,true]"w));
    foreach (i; 0 .. strings.z8_size()) { auto x = strings.z8_get(i); writeln("s:", x is null ? "<null>" : x.to!string); }
    auto bools = P.m_bools(P.m_parse("[true,false,'yes',null,'0']"w));
    foreach (i; 0 .. bools.z8_size()) writeln("b:", z8_optional_require(bools.z8_get(i)));
    auto decimals = P.m_decimals(P.m_parse("[1.25,'2.5',-3]"w));
    foreach (i; 0 .. decimals.z8_size()) writeln("d:", z8_optional_require(decimals.z8_get(i)).z8_string());
    auto ids = P.m_ids(P.m_parse("['00112233-4455-6677-8899-aabbccddeeff',null]"w));
    foreach (i; 0 .. ids.z8_size()) { auto x = ids.z8_get(i); writeln("g:", x is null ? "<null>" : z8_guid_to_string(x).to!string); }
    auto dates = P.m_dates(P.m_parse("['2024-02-29T12:34:56',null,'0','']"w));
    foreach (i; 0 .. dates.z8_size()) { auto x = dates.z8_get(i); writeln("t:", x is null ? "<null>" : z8_date_ticks(x).to!string); }
    foreach (input; [""w, "1,2"w, " [1,2]"w, "[1,]"w, "[1,,2]"w, "[1"w, "{x:1}"w]) {
        try { writeln("p:", P.m_render(P.m_parse(input)).to!string); } catch (Exception) { writeln("p:error"); }
    }
    P.m_assign(value, ""w);
    writeln(z8_optional_require(P.m_empty(value)));
    writeln(P.m_parse(null) is null);
    z8_native_clear_bindings();
    z8_bind_builtin_object();
    z8_bind_builtin_json_array();
    assert(z8_optional_require(P.m_empty(P.m_parse(""w))));
}
""", encoding="utf-8")
    executable = temp / ("json-array.exe" if os.name == "nt" else "json-array")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"JsonArray differs:\nJava={expected!r}\nD={actual!r}")
print("JsonArray parsing, getters and typed arrays match Java")
