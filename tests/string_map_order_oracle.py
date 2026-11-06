"""Compare ordinary string-key map iteration with Java HashMap."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

java = r'''
import java.util.*;
public class MapOrder {
    static void show(HashMap<String, String> map) {
        StringJoiner keys = new StringJoiner("|"), values = new StringJoiner("|");
        for (String key : map.keySet()) keys.add(key == null ? "<null>" : key.isEmpty() ? "<empty>" : key);
        for (String value : map.values()) values.add(value == null ? "<null>" : value);
        System.out.println(keys + ";" + values);
    }
    static void populate(HashMap<String, String> map) {
        map.put("z", "1"); map.put("a", "2"); map.put(null, "3"); map.put("", "4");
        map.put("Aa", "5"); map.put("BB", "6"); map.put("🌍", "7"); map.put("кириллица", null);
    }
    public static void main(String[] args) {
        HashMap<String,String> map = new HashMap<>(); populate(map); show(map);
        map.put("a", "updated"); map.remove("Aa"); map.put("Aa", "again"); map.remove(null); map.put(null,"new"); show(map);
        for (int i=0; i<50; ++i) map.put("k"+i, "v"+i);
        for (int i=0; i<47; ++i) map.remove("k"+i); show(map);
        HashMap<String,String> copied = new HashMap<>(); copied.putAll(map); show(copied);
        map.clear(); map.put("Aa", "1"); map.put(null, "2"); map.put("", "3"); map.put("BB", "4"); show(map);
        HashMap<String,String> other = new HashMap<>(); for (int i=0; i<20; ++i) other.put("p"+i, "q"+i);
        copied.putAll(other); show(copied);
        HashMap<String,String> sequence = new HashMap<>();
        for (int i=0; i<1500; ++i) {
            String key = i % 13 == 0 ? null : "key" + ((i * 17) % 101);
            if (i % 313 == 0) sequence.clear();
            else if (i % 7 == 0) sequence.remove(key);
            else sequence.put(key, "value" + i);
            if (i % 173 == 0) {
                HashMap<String,String> more = new HashMap<>();
                for (int j=0; j<13; ++j) more.put("merge" + j, "item" + (i+j));
                sequence.putAll(more);
            }
            if (i % 97 == 0) show(sequence);
        }
        HashMap<String,String> collisions = new HashMap<>();
        for (int i=0; i<10; ++i) {
            String key = ""; for (int bit=0; bit<4; ++bit) key += (i & (1 << bit)) == 0 ? "Aa" : "BB";
            collisions.put(key, "c" + i);
            if (i >= 7) show(collisions);
        }
    }
}
'''
d_source = r'''
import z8.runtime;
import std.array : join;
import std.conv : to;
import std.stdio : writeln;
void show(Z8StringMap map) {
    string[] keys, values;
    auto allKeys = map.z8_keys(), allValues = map.z8_values();
    for (long i; i < allKeys.z8_size(); ++i) {
        auto key = allKeys.z8_get(i), value = allValues.z8_get(i);
        keys ~= key is null ? "<null>" : !key.length ? "<empty>" : key.to!string;
        values ~= value is null ? "<null>" : value.to!string;
        assert(z8_string_equals(value, map.z8_get(key)));
    }
    writeln(keys.join("|"), ";", values.join("|"));
}
void main() {
    auto map = new Z8StringMap();
    map.z8_add("z"w, "1"w); map.z8_add("a"w, "2"w); map.z8_add(null, "3"w); map.z8_add(""w, "4"w);
    map.z8_add("Aa"w, "5"w); map.z8_add("BB"w, "6"w); map.z8_add("🌍"w, "7"w); map.z8_add("кириллица"w, null); show(map);
    map.z8_add("a"w, "updated"w); map.z8_remove("Aa"w); map.z8_add("Aa"w, "again"w); map.z8_remove(null); map.z8_add(null, "new"w); show(map);
    for (int i; i<50; ++i) map.z8_add("k"w ~ i.to!wstring, "v"w ~ i.to!wstring);
    for (int i; i<47; ++i) map.z8_remove("k"w ~ i.to!wstring); show(map);
    auto copied = new Z8StringMap(); copied.z8_add(map); show(copied);
    map.z8_clear(); map.z8_add("Aa"w, "1"w); map.z8_add(null, "2"w); map.z8_add(""w, "3"w); map.z8_add("BB"w, "4"w); show(map);
    auto other = new Z8StringMap(); for (int i; i<20; ++i) other.z8_add("p"w ~ i.to!wstring, "q"w ~ i.to!wstring);
    copied.z8_add(other); show(copied);
    auto sequence = new Z8StringMap();
    for (int i; i<1500; ++i) {
        auto key = i % 13 == 0 ? null : "key"w ~ ((i * 17) % 101).to!wstring;
        if (i % 313 == 0) sequence.z8_clear();
        else if (i % 7 == 0) sequence.z8_remove(key);
        else sequence.z8_add(key, "value"w ~ i.to!wstring);
        if (i % 173 == 0) {
            auto more = new Z8StringMap();
            for (int j; j<13; ++j) more.z8_add("merge"w ~ j.to!wstring, "item"w ~ (i+j).to!wstring);
            sequence.z8_add(more);
        }
        if (i % 97 == 0) show(sequence);
    }
    auto collisions = new Z8StringMap();
    for (int i; i<10; ++i) {
        wstring key = ""w; for (int bit; bit<4; ++bit) key ~= (i & (1 << bit)) == 0 ? "Aa"w : "BB"w;
        collisions.z8_add(key, "c"w ~ i.to!wstring);
        if (i >= 7) show(collisions);
    }
    auto typed = new Z8StringValueMap!long();
    typed.z8_add("BB"w, z8_optional_wrap(6L)); typed.z8_add(null, z8_optional_wrap(3L)); typed.z8_add("Aa"w, z8_optional_wrap(5L));
    auto names = typed.z8_keys(); auto values = typed.z8_values();
    for (long i; i < names.z8_size(); ++i) assert(values.z8_get(i) == typed.z8_get(names.z8_get(i)));
    assert(names.z8_get(0) == "BB"w && names.z8_get(1) is null && names.z8_get(2) == "Aa"w);
    auto clone = new Z8StringValueMap!long(); clone.z8_add(typed); assert(clone == typed);
}
'''

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    (temp / "MapOrder.java").write_text(java, encoding="utf-8")
    (temp / "map_order.d").write_text(d_source, encoding="utf-8")
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", str(temp / "MapOrder.java")], cwd=temp, check=True)
    executable = temp / ("map-order.exe" if os.name == "nt" else "map-order")
    subprocess.run(["dmd", str(temp / "map_order.d"), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "MapOrder"], cwd=temp, text=True, encoding="utf-8").splitlines()
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, [(index, a, b) for index, (a, b) in enumerate(zip(actual, expected)) if a != b]
print("String-key map bucket ordering matches Java for ordinary cases")
