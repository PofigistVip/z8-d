"""Compare GUID-key map iteration with Java UUID HashMap."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

java = r'''
import java.util.*;
public class GuidOrder {
    static void show(HashMap<UUID,String> map) {
        StringJoiner keys = new StringJoiner("|"), values = new StringJoiner("|");
        for (UUID key : map.keySet()) keys.add(key == null ? "null" : key.toString());
        for (String value : map.values()) values.add(value == null ? "null" : value);
        System.out.println(keys + ";" + values);
    }
    public static void main(String[] args) {
        HashMap<UUID,String> map = new HashMap<>();
        map.put(new UUID(0,0), "zero"); map.put(null,"null"); map.put(new UUID(1,2),"first"); map.put(new UUID(-1,42),"second"); show(map);
        for (long i=0; i<50; ++i) map.put(new UUID(i*173, i*89), "v"+i);
        for (long i=0; i<43; ++i) map.remove(new UUID(i*173, i*89)); show(map);
        HashMap<UUID,String> copy = new HashMap<>(); copy.putAll(map); show(copy);
        map.clear(); map.put(new UUID(0,0),"zero"); map.put(null,"none"); map.put(new UUID(1,2),"one"); show(map);
    }
}
'''
d_source = r'''
import z8.runtime;
import std.array : join;
import std.conv : to;
import std.stdio : writeln;
import std.string : toLower;
void show(Z8GuidMap!wstring map) {
    string[] names, values; auto keys = map.z8_keys(), vals = map.z8_values();
    for (long i; i<keys.z8_size(); ++i) {
        auto key = keys.z8_get(i); auto value = vals.z8_get(i);
        names ~= key is null ? "null" : z8_guid_to_string(key).to!string.toLower();
        values ~= value is null ? "null" : value.to!string;
    }
    writeln(names.join("|"), ";", values.join("|"));
}
void main() {
    auto map = new Z8GuidMap!wstring();
    map.z8_add(z8_guid_create(0,0),"zero"w); map.z8_add(null,"null"w);
    map.z8_add(z8_guid_create(1,2),"first"w); map.z8_add(z8_guid_create(-1,42),"second"w); show(map);
    for (long i; i<50; ++i) map.z8_add(z8_guid_create(i*173,i*89), "v"w ~ i.to!wstring);
    for (long i; i<43; ++i) map.z8_remove(z8_guid_create(i*173,i*89)); show(map);
    auto copy = new Z8GuidMap!wstring(); copy.z8_add(map); show(copy);
    map.z8_clear(); map.z8_add(z8_guid_create(0,0),"zero"w); map.z8_add(null,"none"w); map.z8_add(z8_guid_create(1,2),"one"w); show(map);
    auto mutableKey = z8_guid_create(5); auto mutableMap = new Z8GuidMap!wstring();
    mutableMap.z8_add(mutableKey, "saved"w); mutableKey.minorBits = 99;
    assert(mutableMap.z8_keys().z8_get(0) is mutableKey && mutableMap.z8_values().z8_get(0) == "saved"w);
    auto copied = new Z8GuidMap!wstring(); copied.z8_add(mutableMap);
    assert(copied.z8_get(z8_guid_create(99)) == "saved"w);
}
'''

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    (temp / "GuidOrder.java").write_text(java, encoding="utf-8")
    (temp / "guid_order.d").write_text(d_source, encoding="utf-8")
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", str(temp / "GuidOrder.java")], cwd=temp, check=True)
    executable = temp / ("guid-order.exe" if os.name == "nt" else "guid-order")
    subprocess.run(["dmd", str(temp / "guid_order.d"), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "GuidOrder"], cwd=temp, text=True, encoding="utf-8").splitlines()
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, [(index, a, b) for index, (a, b) in enumerate(zip(actual, expected)) if a != b]
print("GUID map bucket order matches Java and preserves mutable key references")
