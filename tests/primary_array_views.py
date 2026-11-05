"""Check shared string/primary array storage and checked typed reads."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
void main() {
    auto strings = new Z8Array!wstring(["one"w, "two"w]);
    auto before = strings.z8_version;
    auto values = z8_primary_array_view(strings);
    assert(values is z8_primary_array_view(strings));
    assert(strings.z8_version == before && values.z8_size() == 2);
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "one"w);
    strings.z8_set(0, "changed"w);
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "changed"w);
    values.z8_set(1, z8_primary_box("other"w));
    assert(strings.z8_get(1) == "other"w);
    values.z8_add(null);
    assert(strings.z8_size() == 3 && strings.z8_get(2) is null);
    strings.z8_set(2, "last"w);
    assert(z8_primary_cast!wstring(values.z8_get(2)) == "last"w);
    values.z8_add(z8_primary_box(7L));
    bool invalid;
    try { strings.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid && strings.z8_size() == 4);
    invalid = false;
    try { strings.z8_removeAt(3); } catch (Exception) { invalid = true; }
    assert(invalid && values.z8_size() == 3);
    auto same = new Z8Array!wstring(["changed"w, "other"w, "last"w]);
    assert(strings == same && values.opEquals(strings) && strings.opEquals(values));
    auto saved = values.z8_version;
    strings.z8_add("more"w);
    assert(values.z8_version == saved + 1 && strings.z8_version == values.z8_version);
    strings.z8_reverse();
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "more"w);
    strings.z8_sort();
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "changed"w);
    auto extra = new Z8Array!wstring(["x"w]);
    extra.z8_addAll(strings);
    assert(extra.z8_size() == 5 && extra.z8_get(1) == "changed"w);
    values.z8_clear();
    assert(strings.z8_isEmpty());
    assert(z8_primary_array_view(cast(Z8Array!wstring)null) is null);
    auto first = z8_guid_create(1), second = z8_guid_create(2);
    auto ids = new Z8Array!Z8Guid([first, second]);
    auto primaryIds = z8_primary_array_view(ids);
    primaryIds.z8_set(0, z8_primary_box(second)); ids.z8_set(1, first);
    assert(ids.z8_get(0) is second && z8_primary_cast!Z8Guid(primaryIds.z8_get(1)) is first);
    primaryIds.z8_add(null); assert(ids.z8_get(2) is null);
    ids.z8_set(2, z8_guid_create(-1));
    primaryIds.z8_add(z8_primary_box("wrong"w));
    invalid = false; try { ids.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid); primaryIds.z8_removeAt(3);
    ids.z8_sort();
    assert(ids.z8_first().minorBits == ulong.max && ids.z8_last().minorBits == 2);
    assert(primaryIds.opEquals(ids) && ids.opEquals(primaryIds));
    auto unshared = new Z8Array!Z8Guid([second, first]);
    unshared.z8_sort(); assert(unshared.z8_first() is first && unshared.z8_last() is second);
    auto ints = new Z8Array!long([1L, 2L]); auto primaryInts = z8_primary_array_view(ints);
    primaryInts.z8_set(0, z8_primary_box(9L)); ints.z8_set(1, 8L);
    assert(z8_optional_require(ints.z8_get(0)) == 9 && z8_optional_require(z8_primary_cast!long(primaryInts.z8_get(1))) == 8);
    primaryInts.z8_add(null); assert(!ints.z8_get(2).present); ints.z8_set(2, 3L);
    primaryInts.z8_add(z8_primary_box("wrong"w));
    invalid = false; try { ints.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid); primaryInts.z8_removeAt(3); ints.z8_sort();
    assert(z8_optional_require(ints.z8_first()) == 3 && z8_optional_require(ints.z8_last()) == 9);
    auto bools = new Z8Array!bool([true, false]); auto primaryBools = z8_primary_array_view(bools);
    primaryBools.z8_set(0, z8_primary_box(false)); bools.z8_set(1, true);
    assert(!z8_optional_require(bools.z8_get(0)) && z8_optional_require(z8_primary_cast!bool(primaryBools.z8_get(1))));
    bools.z8_sort(); assert(bools.z8_join(","w) == "false,true"w);
    auto decimals = new Z8Array!Z8Decimal([z8_decimal_parse("1.5"w)]); auto primaryDecimals = z8_primary_array_view(decimals);
    primaryDecimals.z8_set(0, z8_primary_box(z8_decimal_parse("2.25"w)));
    assert(z8_optional_require(decimals.z8_get(0)).z8_string() == "2.25"w);
    decimals.z8_add(z8_decimal_parse("1.0"w)); decimals.z8_sort();
    assert(decimals.z8_join(","w) == "1.0,2.25"w);
}
''', encoding="utf-8")
    executable = temp / ("primary-array-views.exe" if os.name == "nt" else "primary-array-views")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)],
                   cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    bl, generated = temp / "bl", temp / "generated"
    bl.mkdir()
    (bl / "Input.bl").write_text('''
[native "example.Input"] public class Input { public static int size(primary[] values); }
''', encoding="utf-8")
    (bl / "Probe.bl").write_text('''
public class Probe {
    public static primary[] asPrimary(string[] values) { return values; }
    public static primary[] choice(bool first, primary[] left, string[] right) { return first ? left : right; }
    public static int count(string[] values) { int result = 0; for (primary part : values) { result += 1; } return result; }
    public static int guidCount(guid[] values) { int result = 0; for (primary part : values) { result += 1; } return result; }
    public static int guidRun() {
        guid[] ids = {guid.create(1), guid.create(2)};
        primary[] values = ids;
        values.set(0, guid.create(9)); ids[1] = guid.create(8);
        if (ids[0].minor() != 9 || ((guid) values[1]).minor() != 8) return 1;
        values.add("wrong");
        try { guid wrong = ids[2]; return 2; } catch (exception expected) {}
        values.set(2, guid.create(3)); values.add(null); ids[3] = guid.create(4);
        if (ids[2].minor() != 3 || ((guid) values[3]).minor() != 4) return 3;
        if (guidCount(ids) != 4 || Input.size(ids) != 4) return 4;
        return 0;
    }
    public static int primitiveRun() {
        bool[] flags = {true, false}; primary[] allFlags = flags;
        allFlags.set(0, false); flags[1] = true;
        if (flags[0] || !(bool)allFlags[1] || Input.size(flags) != 2) return 1;
        allFlags.add("wrong");
        try { bool invalid = flags[2]; return 2; } catch (exception expected) {}
        allFlags.set(2, true);
        int[] numbers = {1, 2}; primary[] allNumbers = numbers;
        allNumbers.set(0, 5); numbers[1] += 7;
        if (numbers[0] != 5 || (int)allNumbers[1] != 9) return 3;
        decimal[] decimals = {1.5}; primary[] allDecimals = decimals;
        allDecimals.set(0, 2.5); decimals[0] += 1.0;
        if ((decimal)allDecimals[0] != 3.5) return 4;
        int count = 0; for (primary item : numbers) { count += 1; }
        if (count != 2) return 5;
        return 0;
    }
    public static int run() {
        string[] words = {"one", "two"};
        primary[] values = words;
        values.set(0, "north"); words.set(1, "south");
        if (words[0] != "north" || (string) values[1] != "south") return 1;
        words[0] = "fresh"; words[0] += "!";
        if ((string) values[0] != "fresh!") return 2;
        values.add(7);
        try { string wrong = words[2]; return 3; } catch (exception expected) {}
        values.set(2, "fixed"); values.add(null); words[3] = "last";
        if (words[2] != "fixed" || (string) values[3] != "last") return 4;
        if (count(words) != 4 || Input.size(words) != 4) return 5;
        if (choice(false, values, words).size() != 4) return 6;
        try { for (primary part : words) { words.add("more"); } return 7; } catch (exception expected) {}
        if (values.size() != 5) return 8;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(bl), str(generated)], check=True)
    harness = temp / "bl_main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
Z8Optional!long count(Z8Array!Z8Primary values) { return z8_optional_wrap(z8_nonnull(values).z8_size()); }
void main() {
    z8_native_bind("example.Input.m_size"w, &count);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_guidRun()) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_primitiveRun()) == 0);
}
''', encoding="utf-8")
    executable = temp / ("primary-array-bl.exe" if os.name == "nt" else "primary-array-bl")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Primitive, string, GUID and primary array views share storage")
