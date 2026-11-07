"""Check shared scalar/primary array storage and checked typed reads."""
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
void checkReferenceView(T)(T first, T second) {
    auto typed = new Z8Array!T([first, null]);
    auto sharedValues = z8_primary_array_view(typed);
    assert(sharedValues is z8_primary_array_view(typed) && typed.z8_get(1) is null);
    sharedValues.z8_set(1, z8_primary_box(second));
    assert(typed.z8_get(1) is second);
    typed.z8_at(0) = second;
    assert(z8_primary_cast!T(sharedValues.z8_get(0)) is second);
    sharedValues.z8_add(z8_primary_box("wrong"w));
    bool rejected;
    try { typed.z8_get(2); } catch (Exception) { rejected = true; }
    assert(rejected); sharedValues.z8_removeAt(2);
    assert(sharedValues.opEquals(typed) && typed.opEquals(sharedValues));
    assert(z8_primary_array_view(cast(Z8Array!T)null) is null);
}
void main() {
    checkReferenceView(z8_binary_literal("65"), z8_binary_literal("66"));
    checkReferenceView(z8_datespan_literal("1 00:00:00"), z8_datespan_literal("2 00:00:00"));
    checkReferenceView(z8_date_from_ticks(0), z8_date_from_ticks(1_000));
    checkReferenceView(z8_geometry_none(4326), z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 4326));
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
    auto file1 = z8_file_from_path("one.txt"w), file2 = z8_file_from_path("two.txt"w);
    auto files = new Z8Array!Z8File([file1, file2]); auto primaryFiles = z8_primary_array_view(files);
    primaryFiles.z8_set(0, z8_primary_box(file2)); files.z8_set(1, file1);
    assert(files.z8_get(0) is file2 && z8_primary_cast!Z8File(primaryFiles.z8_get(1)) is file1);
    primaryFiles.z8_add(null); assert(files.z8_get(2) is null);
    files.z8_set(2, file2); primaryFiles.z8_add(z8_primary_box("wrong"w));
    invalid = false; try { files.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid); primaryFiles.z8_removeAt(3);
    assert(primaryFiles.opEquals(files) && files.opEquals(primaryFiles));
    assert(z8_primary_array_view(cast(Z8Array!Z8File)null) is null);
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
    public static primary[] dateChoice(bool first, primary[] left, date[] right) { return first ? left : right; }
    private static int choose(primary[] values) { return 1; }
    private static int choose(date[] values) { return 2; }
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
    public static int fileRun() {
        file first = "one.txt"; file second = "two.txt";
        file[] files = {first, second}; primary[] values = files;
        values.set(0, second); files[1] = first;
        if (files[0].path != "two.txt" || ((file)values[1]).path != "one.txt") return 1;
        values.add("wrong");
        try { file wrong = files[2]; return 2; } catch (exception expected) {}
        values.set(2, first); values.add(null); files[3] = second;
        if (files[2].path != "one.txt" || ((file)values[3]).path != "two.txt") return 3;
        if (Input.size(files) != 4) return 4;
        int count = 0; for (primary item : files) { count += 1; }
        if (count != 4) return 5;
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
    public static int otherPrimaryRun() {
        binary first = '65'; first.setName("first"); binary second = '66'; second.setName("second");
        binary[] binaries = {first, null}; primary[] binaryValues = binaries;
        binaryValues.set(1, second); if (binaries[1].getName() != "second") return 1;
        binaryValues.add("wrong");
        try { binary bad = binaries[2]; return 2; } catch (exception expected) {}
        binaryValues.removeAt(2); if (Input.size(binaries) != 2) return 3;
        date a = '01/01/2024'; date b = '02/01/2024';
        date[] dates = {a, null}; primary[] dateValues = dates;
        dateValues.set(1, b); dates[0] = b;
        if (dates[1] != b || (date)dateValues[0] != b || dateChoice(false, dateValues, dates).size() != 2) return 4;
        dateValues.add(null); dates[2] = a;
        if ((date)dateValues[2] != a || choose(dates) != 2) return 9;
        int count = 0; for (primary value : dates) count += 1;
        if (count != 3) return 5;
        datespan aSpan = '1 00:00:00'; datespan bSpan = '2 00:00:00';
        datespan[] spans = {aSpan}; primary[] spanValues = spans;
        spanValues.set(0, bSpan); if (spans[0] != bSpan || Input.size(spans) != 1) return 6;
        geometry firstPoint = geometry.point(1, 2, 4326); geometry nextPoint = geometry.point(3, 4, 4326);
        geometry[] points = {firstPoint}; primary[] geometryValues = points;
        geometryValues.set(0, nextPoint); if (points[0].toString() != nextPoint.toString() || Input.size(points) != 1) return 7;
        primary[] mixed = {1, 2, "keep"}; int[] removeNumbers = {1}; mixed.removeAll(removeNumbers);
        if (mixed.size() != 2 || mixed.contains(1)) return 8;
        primary[] mixedRefs = {first, aSpan, a, firstPoint, "keep"};
        binary[] removeBinaries = {first}; datespan[] removeSpans = {aSpan};
        date[] removeDates = {a}; geometry[] removeGeometries = {firstPoint};
        mixedRefs.removeAll(removeBinaries); mixedRefs.removeAll(removeSpans);
        mixedRefs.removeAll(removeDates); mixedRefs.removeAll(removeGeometries);
        if (mixedRefs.size() != 1 || !mixedRefs.contains("keep")) return 10;
        int missing = null; int[] nullable = {null, 1}; nullable.removeAll(missing);
        if (nullable.size() != 1 || nullable[0] != 1) return 11;
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
import z8gen.Probe;
import std.conv : to;
Z8Optional!long count(Z8Array!Z8Primary values) { return z8_optional_wrap(z8_nonnull(values).z8_size()); }
void main() {
    z8_native_bind("example.Input.m_size"w, &count);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_guidRun()) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_fileRun()) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_primitiveRun()) == 0);
    auto otherResult = z8_optional_require(Z8p_50726F6265.m_otherPrimaryRun());
    assert(otherResult == 0, "otherPrimaryRun failed: " ~ otherResult.to!string);
}
''', encoding="utf-8")
    executable = temp / ("primary-array-bl.exe" if os.name == "nt" else "primary-array-bl")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for body in ('int[] values; values.removeAll(null);', 'string[] values; values.removeAll(null);', 'date[] values; values.removeAll(null);',
                 'primary[] values; values.removeAll(null);'):
        (bl / "Bad.bl").write_text('public class Bad { static void f() { ' + body + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(bl), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted ambiguous removeAll(null): " + body)
print("Base-type and primary array views share storage")
