"""Scalar-valued string maps share storage with primary[string]."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[string] values) { return values.size(); }
    static int choose(int[string] values) { return 2; }
    static primary[string] choice(bool flag, primary[string] left, int[string] right) { return flag ? left : right; }
    public static int run() {
        int[string] typed = {("one", 1), ("two", 2)}; primary[string] values = typed;
        values.add("one", 5); typed.add("two", 6);
        if (typed.get("one") != 5 || (int)values.get("two") != 6) return 1;
        values.add("wrong", "text");
        try { int bad = typed.get("wrong"); return 2; } catch (exception expected) {}
        typed.add("wrong", 3); if (typed.get("wrong") != 3) return 7;
        values.add("wrong", "bad"); typed.remove("wrong"); if (typed.containsKey("wrong")) return 8;
        values.add("wrong", "bad"); typed["wrong"] = 4; if (typed.get("wrong") != 4) return 9;
        values.add("wrong", "bad");
        try { int previous = typed.add("wrong", 5); return 10; } catch (exception expected) {}
        if (typed.get("wrong") != 5) return 11;
        values.remove("wrong"); values.add("null", null);
        int missing = typed.get("null"); if (missing != null) return 3;
        if (size(typed) != 3 || choose(typed) != 2 || choice(false, values, typed).size() != 3) return 4;
        primary[string] copy = {}; copy.add(typed);
        if (copy.size() != 3 || (int)copy.get("one") != 5) return 5;
        date[string] dates = {}; primary[string] dateValues = dates;
        date d = '01/01/2024'; dateValues.add("date", d);
        if (dates.get("date") != d) return 6;
        string[string] strings = {("first", "one"), ("second", "two")};
        primary[string] mixed = strings;
        mixed.add("first", "updated"); strings.add("second", "changed");
        if (strings.get("first") != "updated" || (string)mixed.get("second") != "changed") return 12;
        mixed.add("wrong", 7); try { string bad = strings.get("wrong"); return 13; } catch (exception expected) {}
        strings.add("wrong", "fixed"); if ((string)mixed.get("wrong") != "fixed") return 14;
        mixed.add("wrong", 7);
        try { string previousText = strings.add("wrong", "after"); return 16; } catch (exception expected) {}
        if (strings.get("wrong") != "after") return 17;
        mixed.add("wrong", 7); strings.remove("wrong"); if (mixed.containsKey("wrong")) return 15;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() {
    auto typed = new Z8StringValueMap!long();
    typed.z8_add("Aa"w, z8_optional_wrap(1L)); typed.z8_add("BB"w, z8_optional_wrap(2L));
    typed.z8_add(null, Z8Optional!long.init);
    auto priorKeys = typed.z8_keys();
    auto primary = z8_primary_map_view(typed);
    assert(primary is z8_primary_map_view(typed) && primary.z8_containsKey(null));
    auto afterKeys = primary.z8_keys(); assert(priorKeys.opEquals(afterKeys));
    primary.z8_add("Aa"w, z8_primary_box(7L));
    assert(z8_optional_require(typed.z8_get("Aa"w)) == 7);
    typed.z8_add("BB"w, z8_optional_wrap(8L));
    assert(z8_optional_require(z8_primary_cast!long(primary.z8_get("BB"w))) == 8);
    primary.z8_add("wrong"w, z8_primary_box("bad"w));
    bool invalid; try { typed.z8_get("wrong"w); } catch (Exception) { invalid = true; }
    assert(invalid);
    auto values = typed.z8_values(); invalid = false;
    foreach (i; 0 .. values.z8_size()) try { values.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); primary.z8_remove("wrong"w);
    assert(primary.opEquals(typed) && typed.opEquals(primary));
    primary.z8_clear(); assert(typed.z8_isEmpty());
    assert(z8_primary_map_view(cast(Z8StringValueMap!long)null) is null);
    auto strings = new Z8StringMap();
    strings.z8_add("Aa"w, "one"w); strings.z8_add("BB"w, "two"w); strings.z8_add(null, null);
    auto insertion = strings.z8_insertion_keys(); auto primaryStrings = z8_primary_map_view(strings);
    assert(primaryStrings.z8_insertion_keys().opEquals(insertion));
    primaryStrings.z8_add("third"w, z8_primary_box("three"w));
    assert(strings.z8_insertion_keys().z8_size() == 4 && strings.z8_insertion_keys().z8_get(2) == "third"w);
    primaryStrings.z8_remove("Aa"w);
    assert(strings.z8_insertion_keys().z8_get(0) == "BB"w);
    strings.z8_add("BB"w, "changed"w);
    assert(z8_primary_cast!wstring(primaryStrings.z8_get("BB"w)) == "changed"w);
    primaryStrings.z8_add("wrong"w, z8_primary_box(42L)); invalid = false;
    try { strings.z8_get("wrong"w); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(strings, "wrong"w, "fixed"w);
    assert(z8_primary_cast!wstring(primaryStrings.z8_get("wrong"w)) == "fixed"w);
    assert(strings.opEquals(primaryStrings) && primaryStrings.opEquals(strings));
    assert(z8_primary_map_view(cast(Z8StringMap)null) is null);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-maps.exe" if os.name == "nt" else "primary-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for typed, primary in (("int[]", "primary[]"), ("int[][]", "primary[][]"), ("int[string]", "primary[string]"), ("string[string]", "primary[string]")):
        (source / "Bad.bl").write_text('public class Bad { static void choose(' + typed + ' x) {} static void choose(' + primary + ' x) {} static void run() { ' + typed + ' x; choose(x); } }', encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
        if result.returncode == 0 or "ambiguous" not in result.stderr:
            raise SystemExit("Expected ambiguous collection overloads: " + typed + ": " + result.stderr)
print("Scalar string-keyed maps and primary maps share storage")
