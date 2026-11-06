"""Compare integer, boolean and decimal map iteration with Java HashMap."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

java = r'''
import java.util.*;
import java.math.BigDecimal;
public class ScalarOrder {
    static <K> void show(HashMap<K, String> map) {
        StringJoiner keys = new StringJoiner("|"), values = new StringJoiner("|");
        for (K key : map.keySet()) keys.add(key == null ? "<null>" : key.toString());
        for (String value : map.values()) values.add(value == null ? "<null>" : value);
        System.out.println(keys + ";" + values);
    }
    public static void main(String[] args) {
        HashMap<Long,String> nums = new HashMap<>();
        nums.put(0L,"zero"); nums.put(null,"null"); nums.put(-1L,"negative"); nums.put(Long.MIN_VALUE,"min"); nums.put(4294967297L,"large"); show(nums);
        for (long i=0; i<80; ++i) nums.put(i*17-30, "v"+i);
        for (long i=0; i<55; ++i) nums.remove(i*17-30); show(nums);
        HashMap<Long,String> copy = new HashMap<>(); copy.putAll(nums); show(copy);
        nums.clear(); nums.put(0L,"0"); nums.put(null,"1"); nums.put(4294967297L,"2"); show(nums);
        HashMap<Boolean,String> flags = new HashMap<>(); flags.put(true,"yes"); flags.put(null,"none"); flags.put(false,"no"); show(flags);
        flags.remove(true); flags.put(true,"again"); show(flags);
        HashMap<BigDecimal,String> decimals = new HashMap<>();
        String[] values = {"0", "0.0", "1.0", "1.00", "-12.34", "12345678901234567890.123", "9.99"};
        for (int i=0; i<values.length; ++i) decimals.put(new BigDecimal(values[i]), "d"+i);
        decimals.put(null,"none"); show(decimals);
        decimals.remove(new BigDecimal("1.0")); decimals.put(new BigDecimal("1.0"),"again"); show(decimals);
        HashMap<BigDecimal,String> dc = new HashMap<>(); dc.putAll(decimals); show(dc);
    }
}
'''
d_source = r'''
import z8.runtime;
import std.array : join;
import std.conv : to;
import std.stdio : writeln;
void show(K)(Z8ScalarKeyMap!(K,wstring) map) {
    string[] names, values; auto keys = map.z8_keys(), vals = map.z8_values();
    for (long i; i<keys.z8_size(); ++i) {
        auto key = keys.z8_get(i); auto value = vals.z8_get(i);
        if (!key.present) names ~= "<null>";
        else static if (is(K == Z8Decimal)) names ~= key.value.z8_string().to!string;
        else names ~= key.value.to!string;
        values ~= value is null ? "<null>" : value.to!string;
        assert(z8_string_equals(value, map.z8_get(key)));
    }
    writeln(names.join("|"), ";", values.join("|"));
}
void main() {
    auto nums = new Z8IntMap!wstring();
    nums.z8_add(z8_optional_wrap(0L),"zero"w); nums.z8_add(Z8Optional!long.init,"null"w);
    nums.z8_add(z8_optional_wrap(-1L),"negative"w); nums.z8_add(z8_optional_wrap(long.min),"min"w); nums.z8_add(z8_optional_wrap(4294967297L),"large"w); show(nums);
    for (long i; i<80; ++i) nums.z8_add(z8_optional_wrap(i*17-30), "v"w ~ i.to!wstring);
    for (long i; i<55; ++i) nums.z8_remove(z8_optional_wrap(i*17-30)); show(nums);
    auto copy = new Z8IntMap!wstring(); copy.z8_add(nums); show(copy);
    nums.z8_clear(); nums.z8_add(z8_optional_wrap(0L),"0"w); nums.z8_add(Z8Optional!long.init,"1"w); nums.z8_add(z8_optional_wrap(4294967297L),"2"w); show(nums);
    auto flags = new Z8BoolMap!wstring(); flags.z8_add(z8_optional_wrap(true),"yes"w); flags.z8_add(Z8Optional!bool.init,"none"w); flags.z8_add(z8_optional_wrap(false),"no"w); show(flags);
    flags.z8_remove(z8_optional_wrap(true)); flags.z8_add(z8_optional_wrap(true),"again"w); show(flags);
    auto decimals = new Z8DecimalMap!wstring();
    foreach (i, value; ["0"w, "0.0"w, "1.0"w, "1.00"w, "-12.34"w, "12345678901234567890.123"w, "9.99"w])
        decimals.z8_add(z8_optional_wrap(z8_decimal_parse(value)), "d"w ~ i.to!wstring);
    decimals.z8_add(Z8Optional!Z8Decimal.init,"none"w); show(decimals);
    decimals.z8_remove(z8_optional_wrap(z8_decimal_parse("1.0"w))); decimals.z8_add(z8_optional_wrap(z8_decimal_parse("1.0"w)),"again"w); show(decimals);
    auto dc = new Z8DecimalMap!wstring(); dc.z8_add(decimals); show(dc);
}
'''

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    (temp / "ScalarOrder.java").write_text(java, encoding="utf-8")
    (temp / "scalar_order.d").write_text(d_source, encoding="utf-8")
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", str(temp / "ScalarOrder.java")], cwd=temp, check=True)
    executable = temp / ("scalar-order.exe" if os.name == "nt" else "scalar-order")
    subprocess.run(["dmd", str(temp / "scalar_order.d"), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "ScalarOrder"], cwd=temp, text=True, encoding="utf-8").splitlines()
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, [(index, a, b) for index, (a, b) in enumerate(zip(actual, expected)) if a != b]
print("Integer, boolean and decimal map bucket order matches Java")
