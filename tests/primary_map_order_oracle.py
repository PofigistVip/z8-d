"""Compare mixed primary-key map iteration with Java HashMap."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

java = r'''
import java.util.*;
import java.math.BigDecimal;
public class PrimaryOrder {
    static String name(Object key) {
        if (key == null) return "null";
        if (key instanceof Long) return "L:" + key;
        if (key instanceof Boolean) return "B:" + key;
        if (key instanceof BigDecimal) return "D:" + key;
        if (key instanceof UUID) return "G:" + key;
        return "S:" + key;
    }
    static void show(HashMap<Object,String> map) {
        StringJoiner keys = new StringJoiner("|"), values = new StringJoiner("|");
        for (Object key : map.keySet()) keys.add(name(key));
        for (String value : map.values()) values.add(value == null ? "null" : value);
        System.out.println(keys + ";" + values);
    }
    public static void main(String[] args) {
        HashMap<Object,String> map = new HashMap<>();
        map.put(null,"null"); map.put(0L,"zero"); map.put("", "empty"); map.put(2112L,"number");
        map.put("Aa","first"); map.put("BB","second"); map.put(true,"true"); map.put(false,"false");
        map.put(new BigDecimal("1.0"),"decimal"); map.put(new BigDecimal("1.00"),"scaled"); map.put(new UUID(1,2),"guid"); show(map);
        for (long i=0; i<40; ++i) map.put(i*17-30, "v"+i);
        for (long i=0; i<35; ++i) map.remove(i*17-30); show(map);
        HashMap<Object,String> copy = new HashMap<>(); copy.putAll(map); show(copy);
        map.clear(); map.put("Aa","a"); map.put(null,"n"); map.put(2112L,"n2"); map.put("BB","b"); show(map);
    }
}
'''
d_source = r'''
import z8.runtime;
import std.array : join;
import std.conv : to;
import std.stdio : writeln;
import std.string : toLower;
void show(Z8PrimaryKeyMap!wstring map) {
    string[] names, values; auto keys = map.z8_keys(), vals = map.z8_values();
    for (long i; i<keys.z8_size(); ++i) {
        auto key = keys.z8_get(i); auto value = vals.z8_get(i);
        if (key is null) names ~= "null";
        else switch (key.kind) {
            case Z8PrimaryKind.integer: names ~= "L:" ~ key.integerValue.to!string; break;
            case Z8PrimaryKind.boolean: names ~= "B:" ~ key.booleanValue.to!string; break;
            case Z8PrimaryKind.decimal: names ~= "D:" ~ key.decimalValue.z8_string().to!string; break;
            case Z8PrimaryKind.guid: names ~= "G:" ~ z8_guid_to_string(key.guidValue).to!string.toLower(); break;
            case Z8PrimaryKind.text: names ~= "S:" ~ key.textValue.to!string; break;
            default: assert(0);
        }
        values ~= value is null ? "null" : value.to!string;
    }
    writeln(names.join("|"), ";", values.join("|"));
}
void main() {
    auto map = new Z8PrimaryKeyMap!wstring();
    map.z8_add(null,"null"w); map.z8_add(z8_primary_box(0L),"zero"w); map.z8_add(z8_primary_box(""w),"empty"w); map.z8_add(z8_primary_box(2112L),"number"w);
    map.z8_add(z8_primary_box("Aa"w),"first"w); map.z8_add(z8_primary_box("BB"w),"second"w); map.z8_add(z8_primary_box(true),"true"w); map.z8_add(z8_primary_box(false),"false"w);
    map.z8_add(z8_primary_box(z8_decimal_parse("1.0"w)),"decimal"w); map.z8_add(z8_primary_box(z8_decimal_parse("1.00"w)),"scaled"w); map.z8_add(z8_primary_box(z8_guid_create(1,2)),"guid"w); show(map);
    for (long i; i<40; ++i) map.z8_add(z8_primary_box(i*17-30), "v"w ~ i.to!wstring);
    for (long i; i<35; ++i) map.z8_remove(z8_primary_box(i*17-30)); show(map);
    auto copy = new Z8PrimaryKeyMap!wstring(); copy.z8_add(map); show(copy);
    map.z8_clear(); map.z8_add(z8_primary_box("Aa"w),"a"w); map.z8_add(null,"n"w); map.z8_add(z8_primary_box(2112L),"n2"w); map.z8_add(z8_primary_box("BB"w),"b"w); show(map);
    auto guid = z8_guid_create(5); auto mutableMap = new Z8PrimaryKeyMap!wstring();
    mutableMap.z8_add(z8_primary_box(guid),"saved"w); guid.minorBits = 99;
    assert(mutableMap.z8_keys().z8_get(0).guidValue is guid && mutableMap.z8_values().z8_get(0) == "saved"w);
    auto rehashed = new Z8PrimaryKeyMap!wstring(); rehashed.z8_add(mutableMap);
    assert(rehashed.z8_get(z8_primary_box(z8_guid_create(99))) == "saved"w);
    auto date = z8_date_from_ticks(1234); auto references = new Z8ReferenceKeyMap!(Z8Date, wstring)();
    references.z8_add(date, "date"w); z8_date_assign(date, 5678);
    assert(references.z8_keys().z8_get(0) is date && references.z8_values().z8_get(0) == "date"w);
    auto referenceCopy = new Z8ReferenceKeyMap!(Z8Date, wstring)(); referenceCopy.z8_add(references);
    assert(referenceCopy.z8_get(z8_date_from_ticks(5678)) == "date"w);
}
'''

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    (temp / "PrimaryOrder.java").write_text(java, encoding="utf-8")
    (temp / "primary_order.d").write_text(d_source, encoding="utf-8")
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", str(temp / "PrimaryOrder.java")], cwd=temp, check=True)
    executable = temp / ("primary-order.exe" if os.name == "nt" else "primary-order")
    subprocess.run(["dmd", str(temp / "primary_order.d"), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "PrimaryOrder"], cwd=temp, text=True, encoding="utf-8").splitlines()
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, [(index, a, b) for index, (a, b) in enumerate(zip(actual, expected)) if a != b]
print("Mixed primary-key map bucket order matches Java")
