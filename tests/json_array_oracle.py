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
import org.zenframework.z8.base.json.JsonObject;
import org.zenframework.z8.base.json.JsonPath;
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
    public static JsonArray add(JsonArray array, primary value) { return array.add(value); }
    public static JsonArray insert(JsonArray array, int index, primary value) { return array.insert(index, value); }
    public static JsonArray put(JsonArray array, int index, primary value) { return array.put(index, value); }
    public static JsonArray remove(JsonArray array, int index) { return array.remove(index); }
    public static JsonArray from(primary[] values) { return JsonArray.fromArray(values); }
    public static void assignValues(JsonArray array, primary[] values) { array = values; }
    public static JsonArray concat(JsonArray left, JsonArray right) { return left + right; }
    public static JsonObject parseObject(string text) { return JsonObject.parse(text); }
    public static JsonArray objectArray(JsonObject object, string key) { return object.getJsonArray(key); }
    public static JsonObject objectObject(JsonObject object, string key) { return object.getJsonObject(key); }
    public static JsonObject arrayObject(JsonArray array, int index) { return array.getJsonObject(index); }
    public static JsonArray arrayArray(JsonArray array, int index) { return array.getJsonArray(index); }
    public static void objectPut(JsonObject object, string key, primary value) { object.set(key, value); }
    public static void setArray(JsonObject object, string key, JsonArray value) { object.set(key, value); }
    public static void setObject(JsonObject object, string key, JsonObject value) { object.set(key, value); }
    public static void addArray(JsonArray array, JsonArray value) { array.add(value); }
    public static void addObject(JsonArray array, JsonObject value) { array.add(value); }
    public static void insertObject(JsonArray array, int index, JsonObject value) { array.insert(index, value); }
    public static void putArray(JsonArray array, int index, JsonArray value) { array.put(index, value); }
    public static void putObject(JsonObject object, string key, JsonObject value) { object.put(key, value); }
    public static string objectRender(JsonObject object) { return (string)object; }
    public static string objectText(JsonObject object, string key) { return object.getString(key); }
    public static void assignObject(JsonObject object, string text) { object = text; }
    public static JsonObject mergeObjects(JsonObject left, JsonObject right) { return left + right; }
    public static int objectSize(JsonObject object) { return object.size(); }
    public static JsonObject fromMap(primary[primary] values) { return JsonObject.fromPrimaryMap(values); }
    public static bool objectHas(JsonObject object, string key) { return object.has(key); }
    public static JsonObject fromArrayMap(JsonArray[primary] values) { return JsonObject.fromJsonArrayMap(values); }
    public static JsonObject fromObjectMap(JsonObject[primary] values) { return JsonObject.fromJsonObjectMap(values); }
    public static JsonPath path(string text) { return JsonPath.path(text); }
    public static JsonPath pathAssign(JsonPath path, string text) { path = text; return path; }
    public static int pathLength(JsonPath path) { return path.length(); }
    public static string pathName(JsonPath path, int index) { return path.name(index); }
    public static JsonPath pathParent(JsonPath path) { return path.getParent(); }
    public static string pathText(JsonPath path) { return path.toString(); }
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
        JsonArray changed = parse("[1,2]");
        if (changed.z8_add(new decimal("12345678901234567890.2500")).get() != changed) throw new AssertionError();
        changed.z8_insert(new integer(0), new bool(true));
        changed.z8_put(new integer(2), new string("x"));
        changed.z8_add((primary)null);
        System.out.println("m:" + changed.string().get());
        System.out.println("v:" + changed.z8_getString(new integer(4)).get() + ":" + changed.z8_getInt(new integer(4)).get() + ":" + changed.z8_getDecimal(new integer(4)).toString());
        changed.z8_remove(new integer(1));
        System.out.println("r:" + changed.string().get() + ":" + changed.z8_getString(new integer(3)).get());
        try { changed.z8_remove(new integer(-1)); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("index:error"); }
        try { changed.z8_insert(new integer(10), new integer(1)); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("index:error"); }
        System.out.println("r:" + changed.string().get());
        JsonArray numbers = parse("[]");
        numbers.z8_add(new decimal("1.2500"));
        numbers.z8_add(new decimal("1E+3"));
        numbers.z8_add(new decimal("1E-7"));
        for (string x : numbers.z8_toStringArray()) System.out.println("ms:" + x.get());
        for (integer x : numbers.z8_toIntArray()) System.out.println("mi:" + x.get());
        for (decimal x : numbers.z8_toDecimalArray()) System.out.println("md:" + x.toString());
        System.out.println("n:" + numbers.string().get());
        numbers.operatorAssign(new string("[7]"));
        System.out.println("a:" + numbers.z8_getString(new integer(0)).get());
        JsonArray scalars = parse("[]");
        scalars.z8_add(new integer(43)); scalars.z8_add(new bool(false)); scalars.z8_add(new string("hello"));
        scalars.z8_add(new guid("00112233-4455-6677-8899-aabbccddeeff"));
        scalars.z8_add(new org.zenframework.z8.server.types.datespan(12345));
        scalars.z8_add(new date(0)); scalars.z8_add(new date(date.MinTicks)); scalars.z8_add(decimal.NaN);
        System.out.println("scalars:" + scalars.string().get());
        org.zenframework.z8.server.runtime.RCollection<primary> values = new org.zenframework.z8.server.runtime.RCollection<>();
        values.add(new decimal("1.2500")); values.add(new integer(9)); values.add(null);
        JsonArray from = JsonArray.z8_fromArray(values).get();
        System.out.println("from:" + from.string().get());
        JsonArray.CLASS<JsonArray> rightClass = JsonArray.z8_parse(new string("[4]"));
        JsonArray right = rightClass.get(); right.z8_add(new decimal("1E-7"));
        JsonArray combined = from.operatorAdd(rightClass).get();
        System.out.println("concat:" + combined.string().get());
        from.z8_remove(new integer(0)); right.z8_add(new integer(5));
        System.out.println("copies:" + combined.string().get() + ":" + from.string().get() + ":" + right.string().get());
        from.operatorAssign(values);
        System.out.println("assigned:" + from.string().get());
        from.operatorAssign((org.zenframework.z8.server.runtime.RCollection)null);
        System.out.println("empty:" + from.string().get() + ":" + (JsonArray.z8_fromArray(null) == null));
        org.zenframework.z8.server.base.json.parser.JsonObject rootObject = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{a:[{v:1}]}")).get();
        JsonArray nestedArray = rootObject.z8_getJsonArray(new string("a")).get();
        org.zenframework.z8.server.base.json.parser.JsonObject nestedObject = nestedArray.z8_getJsonObject(new integer(0)).get();
        nestedObject.z8_set(new string("v"), new decimal("1.2500"));
        nestedArray.z8_add(new integer(2));
        System.out.println("nested:" + rootObject.string().get() + ":" + rootObject.z8_getString(new string("a")).get() + ":" + nestedArray.z8_getString(new integer(0)).get());
        nestedObject.operatorAssign(new string("{v:9}"));
        nestedArray.operatorAssign(new string("[7]"));
        System.out.println("detached:" + rootObject.string().get() + ":" + nestedArray.string().get() + ":" + nestedObject.string().get());
        JsonArray.CLASS<JsonArray> insertedArray = JsonArray.z8_parse(new string("[3]"));
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> insertedObject = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{x:4}"));
        JsonArray.CLASS<JsonArray> containerClass = JsonArray.z8_parse(new string("[]"));
        JsonArray container = containerClass.get();
        container.z8_add(insertedArray); container.z8_insert(new integer(0), insertedObject);
        insertedArray.get().z8_add(new integer(5)); insertedObject.get().z8_set(new string("x"), new integer(6));
        System.out.println("inserted:" + container.string().get());
        org.zenframework.z8.server.base.json.parser.JsonObject holder = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{}")).get();
        holder.z8_set(new string("a"), containerClass);
        container.z8_remove(new integer(0));
        System.out.println("holder:" + holder.string().get());
        JsonArray.CLASS<JsonArray> sourceClass = JsonArray.z8_parse(new string("[[1]]"));
        JsonArray sourceArray = sourceClass.get();
        JsonArray merged = sourceArray.operatorAdd(JsonArray.z8_parse(new string("[]"))).get();
        sourceArray.z8_getJsonArray(new integer(0)).get().z8_add(new integer(2));
        System.out.println("shared:" + merged.string().get());
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> outerClass = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{}"));
        outerClass.get().z8_put(new string("o"), insertedObject);
        insertedObject.get().z8_set(new string("x"), new integer(8));
        System.out.println("object:" + outerClass.get().z8_getJsonObject(new string("o")).get().string().get());
        container.z8_put(new integer(0), insertedArray);
        insertedArray.get().z8_add(new integer(9));
        System.out.println("shift:" + container.string().get() + ":" + container.z8_getJsonArray(new integer(1)).get().string().get());
        System.out.println("missing:" + (outerClass.get().z8_getJsonObject(new string("absent")) == null));
        try { container.z8_getJsonObject(new integer(0)); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("type:error"); }
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> leftClass = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{a:[1],b:2}"));
        org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject> rightObjectClass = org.zenframework.z8.server.base.json.parser.JsonObject.z8_parse(new string("{b:3,c:[4]}"));
        org.zenframework.z8.server.base.json.parser.JsonObject leftObject = leftClass.get(), rightObject = rightObjectClass.get();
        leftObject.z8_set(new string("b"), new decimal("1.2500"));
        org.zenframework.z8.server.base.json.parser.JsonObject combinedObject = leftObject.operatorAdd(rightObjectClass).get();
        leftObject.z8_getJsonArray(new string("a")).get().z8_add(new integer(5));
        rightObject.z8_getJsonArray(new string("c")).get().z8_add(new integer(6));
        leftObject.z8_set(new string("b"), new integer(8)); rightObject.z8_set(new string("b"), new integer(9));
        System.out.println("merge:" + combinedObject.z8_length().get() + ":" + combinedObject.z8_getString(new string("a")).get() + ":" + combinedObject.z8_getString(new string("b")).get() + ":" + combinedObject.z8_getString(new string("c")).get());
        org.zenframework.z8.server.runtime.RLinkedHashMap<primary, primary> map = new org.zenframework.z8.server.runtime.RLinkedHashMap<>();
        map.put(new integer(7), new decimal("1.2500")); map.put(new string("absent"), null); map.put(new bool(true), decimal.NaN);
        org.zenframework.z8.server.base.json.parser.JsonObject mapped = org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromPrimaryMap(map).get();
        System.out.println("map:" + mapped.z8_getString(new string("7")).get() + ":" + mapped.z8_has(new string("absent")).get() + ":" + mapped.z8_has(new string("true")).get());
        System.out.println("mapnull:" + (org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromPrimaryMap(null) == null));
        org.zenframework.z8.server.runtime.RLinkedHashMap<primary, JsonArray.CLASS<JsonArray>> arrayMap = new org.zenframework.z8.server.runtime.RLinkedHashMap<>();
        arrayMap.put(new integer(1), insertedArray);
        org.zenframework.z8.server.base.json.parser.JsonObject mappedArray = org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromJsonArrayMap(arrayMap).get();
        insertedArray.get().z8_add(new integer(11));
        System.out.println("amap:" + mappedArray.z8_getString(new string("1")).get());
        org.zenframework.z8.server.runtime.RLinkedHashMap<primary, org.zenframework.z8.server.base.json.parser.JsonObject.CLASS<org.zenframework.z8.server.base.json.parser.JsonObject>> objectMap = new org.zenframework.z8.server.runtime.RLinkedHashMap<>();
        objectMap.put(new string("k"), insertedObject);
        org.zenframework.z8.server.base.json.parser.JsonObject mappedObject = org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromJsonObjectMap(objectMap).get();
        insertedObject.get().z8_set(new string("x"), new integer(10));
        System.out.println("omap:" + mappedObject.z8_getString(new string("k")).get());
        System.out.println("jsonmapnull:" + (org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromJsonArrayMap(null) == null) + ":" + (org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromJsonObjectMap(null) == null));
        arrayMap.put(new integer(2), null);
        try { org.zenframework.z8.server.base.json.parser.JsonObject.z8_fromJsonArrayMap(arrayMap); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("jsonmapvalue:error"); }
        for (String pathText : new String[] {" a/b[02]/c ", "/x//y[1]garbage/z", "[0]/root[3]", "", "/a-b/c"}) {
            org.zenframework.z8.server.base.json.parser.JsonPath path = org.zenframework.z8.server.base.json.parser.JsonPath.z8_path(new string(pathText)).get();
            System.out.println("path:" + path.z8_toString().get() + ":" + path.z8_length().get());
            for (int i = 0; i < path.z8_length().get(); i++) {
                try { System.out.println("part:" + path.z8_name(new integer(i)).get()); } catch (RuntimeException expected) { System.out.println("part:error"); }
            }
            try { System.out.println("parent:" + path.z8_getParent().get().z8_toString().get()); } catch (RuntimeException expected) { System.out.println("parent:error"); }
        }
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
        server_source / "base/json/parser/JsonPath.java",
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
import std.traits : Parameters;
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
    auto changed = P.m_parse("[1,2]"w);
    assert(P.m_add(changed, z8_primary_box(z8_decimal_parse("12345678901234567890.2500"w))) is changed);
    P.m_insert(changed, 0, z8_primary_box(true));
    P.m_put(changed, 2, z8_primary_box("x"w));
    P.m_add(changed, null);
    writeln("m:", P.m_render(changed).to!string);
    writeln("v:", P.m_text(changed, 4).to!string, ":", z8_optional_require(P.m_integer(changed, 4)), ":", z8_optional_require(P.m_decimalValue(changed, 4)).z8_string());
    P.m_remove(changed, 1);
    writeln("r:", P.m_render(changed).to!string, ":", P.m_text(changed, 3).to!string);
    try { P.m_remove(changed, -1); writeln("bad"); } catch (Exception) { writeln("index:error"); }
    try { P.m_insert(changed, 10, z8_primary_box(1L)); writeln("bad"); } catch (Exception) { writeln("index:error"); }
    writeln("r:", P.m_render(changed).to!string);
    auto numbers = P.m_parse("[]"w);
    foreach (number; ["1.2500"w, "1E+3"w, "1E-7"w]) P.m_add(numbers, z8_primary_box(z8_decimal_parse(number)));
    auto numberStrings = P.m_strings(numbers);
    foreach (i; 0 .. numberStrings.z8_size()) writeln("ms:", numberStrings.z8_get(i).to!string);
    auto numberInts = P.m_ints(numbers);
    foreach (i; 0 .. numberInts.z8_size()) writeln("mi:", z8_optional_require(numberInts.z8_get(i)));
    auto numberDecimals = P.m_decimals(numbers);
    foreach (i; 0 .. numberDecimals.z8_size()) writeln("md:", z8_optional_require(numberDecimals.z8_get(i)).z8_string());
    writeln("n:", P.m_render(numbers).to!string);
    P.m_assign(numbers, "[7]"w);
    writeln("a:", P.m_text(numbers, 0).to!string);
    auto scalars = P.m_parse("[]"w);
    P.m_add(scalars, z8_primary_box(43L)); P.m_add(scalars, z8_primary_box(false)); P.m_add(scalars, z8_primary_box("hello"w));
    P.m_add(scalars, z8_primary_box(z8_guid_literal("00112233-4455-6677-8899-aabbccddeeff")));
    P.m_add(scalars, z8_primary_box(new Z8Datespan(12345)));
    P.m_add(scalars, z8_primary_box(z8_date_from_ticks(0))); P.m_add(scalars, z8_primary_box(z8_date_min)); P.m_add(scalars, z8_primary_box(z8_decimal_nan()));
    writeln("scalars:", P.m_render(scalars).to!string);
    auto beforeInvalid = P.m_render(scalars);
    bool rejected;
    try { P.m_add(scalars, z8_primary_box(new Z8Binary())); } catch (Exception) { rejected = true; }
    assert(rejected && P.m_render(scalars) == beforeInvalid);
    auto values = new Z8Array!Z8Primary([z8_primary_box(z8_decimal_parse("1.2500"w)), z8_primary_box(9L), null]);
    auto from = P.m_from(values);
    writeln("from:", P.m_render(from).to!string);
    auto right = P.m_parse("[4]"w); P.m_add(right, z8_primary_box(z8_decimal_parse("1E-7"w)));
    auto combined = P.m_concat(from, right);
    writeln("concat:", P.m_render(combined).to!string);
    P.m_remove(from, 0); P.m_add(right, z8_primary_box(5L));
    writeln("copies:", P.m_render(combined).to!string, ":", P.m_render(from).to!string, ":", P.m_render(right).to!string);
    P.m_assignValues(from, values);
    writeln("assigned:", P.m_render(from).to!string);
    P.m_assignValues(from, null);
    writeln("empty:", P.m_render(from).to!string, ":", P.m_from(null) is null);
    auto rootObject = P.m_parseObject("{a:[{v:1}]}"w);
    auto nestedArray = P.m_objectArray(rootObject, "a"w);
    auto nestedObject = P.m_arrayObject(nestedArray, 0);
    P.m_objectPut(nestedObject, "v"w, z8_primary_box(z8_decimal_parse("1.2500"w)));
    P.m_add(nestedArray, z8_primary_box(2L));
    writeln("nested:", P.m_objectRender(rootObject).to!string, ":", P.m_objectText(rootObject, "a"w).to!string, ":", P.m_text(nestedArray, 0).to!string);
    P.m_assignObject(nestedObject, "{v:9}"w); P.m_assign(nestedArray, "[7]"w);
    writeln("detached:", P.m_objectRender(rootObject).to!string, ":", P.m_render(nestedArray).to!string, ":", P.m_objectRender(nestedObject).to!string);
    auto insertedArray = P.m_parse("[3]"w); auto insertedObject = P.m_parseObject("{x:4}"w);
    auto container = P.m_parse("[]"w);
    P.m_addArray(container, insertedArray); P.m_insertObject(container, 0, insertedObject);
    P.m_add(insertedArray, z8_primary_box(5L)); P.m_objectPut(insertedObject, "x"w, z8_primary_box(6L));
    writeln("inserted:", P.m_render(container).to!string);
    auto holder = P.m_parseObject("{}"w); P.m_setArray(holder, "a"w, container); P.m_remove(container, 0);
    writeln("holder:", P.m_objectRender(holder).to!string);
    auto sourceArray = P.m_parse("[[1]]"w); auto merged = P.m_concat(sourceArray, P.m_parse("[]"w));
    P.m_add(P.m_arrayArray(sourceArray, 0), z8_primary_box(2L));
    writeln("shared:", P.m_render(merged).to!string);
    auto outer = P.m_parseObject("{}"w); P.m_putObject(outer, "o"w, insertedObject);
    P.m_objectPut(insertedObject, "x"w, z8_primary_box(8L));
    writeln("object:", P.m_objectRender(P.m_objectObject(outer, "o"w)).to!string);
    P.m_putArray(container, 0, insertedArray); P.m_add(insertedArray, z8_primary_box(9L));
    writeln("shift:", P.m_render(container).to!string, ":", P.m_render(P.m_arrayArray(container, 1)).to!string);
    writeln("missing:", P.m_objectObject(outer, "absent"w) is null);
    try { P.m_arrayObject(container, 0); writeln("bad"); } catch (Exception) { writeln("type:error"); }
    auto leftObject = P.m_parseObject("{a:[1],b:2}"w); auto rightObject = P.m_parseObject("{b:3,c:[4]}"w);
    P.m_objectPut(leftObject, "b"w, z8_primary_box(z8_decimal_parse("1.2500"w)));
    auto combinedObject = P.m_mergeObjects(leftObject, rightObject);
    P.m_add(P.m_objectArray(leftObject, "a"w), z8_primary_box(5L)); P.m_add(P.m_objectArray(rightObject, "c"w), z8_primary_box(6L));
    P.m_objectPut(leftObject, "b"w, z8_primary_box(8L)); P.m_objectPut(rightObject, "b"w, z8_primary_box(9L));
    writeln("merge:", z8_optional_require(P.m_objectSize(combinedObject)), ":", P.m_objectText(combinedObject, "a"w).to!string, ":", P.m_objectText(combinedObject, "b"w).to!string, ":", P.m_objectText(combinedObject, "c"w).to!string);
    auto map = new Z8PrimaryKeyMap!Z8Primary();
    map.z8_add(z8_primary_box(7L), z8_primary_box(z8_decimal_parse("1.2500"w)));
    map.z8_add(z8_primary_box("absent"w), null); map.z8_add(z8_primary_box(true), z8_primary_box(z8_decimal_nan()));
    auto mapped = P.m_fromMap(map);
    writeln("map:", P.m_objectText(mapped, "7"w).to!string, ":", z8_optional_require(P.m_objectHas(mapped, "absent"w)), ":", z8_optional_require(P.m_objectHas(mapped, "true"w)));
    writeln("mapnull:", P.m_fromMap(null) is null);
    alias ArrayMap = Parameters!(P.m_fromArrayMap)[0];
    auto arrayMap = new ArrayMap(); arrayMap.z8_add(z8_primary_box(1L), insertedArray);
    auto mappedArray = P.m_fromArrayMap(arrayMap); P.m_add(insertedArray, z8_primary_box(11L));
    writeln("amap:", P.m_objectText(mappedArray, "1"w).to!string);
    alias ObjectMap = Parameters!(P.m_fromObjectMap)[0];
    auto objectMap = new ObjectMap(); objectMap.z8_add(z8_primary_box("k"w), insertedObject);
    auto mappedObject = P.m_fromObjectMap(objectMap); P.m_objectPut(insertedObject, "x"w, z8_primary_box(10L));
    writeln("omap:", P.m_objectText(mappedObject, "k"w).to!string);
    writeln("jsonmapnull:", P.m_fromArrayMap(null) is null, ":", P.m_fromObjectMap(null) is null);
    arrayMap.z8_add(z8_primary_box(2L), null);
    try { P.m_fromArrayMap(arrayMap); writeln("bad"); } catch (Exception) { writeln("jsonmapvalue:error"); }
    foreach (text; [" a/b[02]/c "w, "/x//y[1]garbage/z"w, "[0]/root[3]"w, ""w, "/a-b/c"w]) {
        auto path = P.m_path(text);
        writeln("path:", P.m_pathText(path).to!string, ":", z8_optional_require(P.m_pathLength(path)));
        foreach (i; 0 .. z8_optional_require(P.m_pathLength(path))) {
            try { writeln("part:", P.m_pathName(path, i).to!string); } catch (Exception) { writeln("part:error"); }
        }
        try { writeln("parent:", P.m_pathText(P.m_pathParent(path)).to!string); } catch (Exception) { writeln("parent:error"); }
    }
    auto assignedPath = P.m_path("/old"w); assert(P.m_pathAssign(assignedPath, "/new"w) is assignedPath);
    assert(P.m_pathText(assignedPath) == "/new"w);
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
print("JSON operations, nested references and path parsing match Java")
