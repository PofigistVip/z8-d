"""Share string-keyed maps of typed arrays with maps of primary arrays."""
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
    (source / "Plain.bl").write_text('''public class Plain { public operator int() { return 1; } }''', encoding="utf-8")
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public int number; public void operator = (Custom value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[][string] values) { return values.size(); }
    static primary[][string] choice(bool flag, primary[][string] a, int[][string] b) { return flag ? a : b; }
    public static int run() {
        int[] row = {1, 2}; int[][string] typed = {("a", row)}; primary[][string] values = typed;
        values.get("a").set(0, 8); typed.get("a").set(1, 9);
        if (typed.get("a").get(0) != 8 || (int)values.get("a").get(1) != 9) return 1;
        primary[] replacement = {5, 6}; values.add("a", replacement);
        if (typed.get("a").get(1) != 6) return 2;
        typed.get("a").set(0, 7); if ((int)replacement.get(0) != 7) return 3;
        replacement.add("wrong"); try { int bad = typed.get("a").get(2); return 4; } catch (exception expected) {}
        replacement.removeAt(2);
        if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 5;
        int[][primary] keys = typed; primary[][primary] both = keys;
        both.add(7, replacement); if (typed.size() != 2 || (int)both.get("a").get(0) != 7) return 6;
        int[][string] other = {("a", row)}; int[][primary] keysFirst = other; primary[][string] nestedSecond = other;
        keysFirst.add(7, row); nestedSecond.get("a").set(0, 10);
        if (other.size() != 2 || keysFirst.get(7).get(0) != 10) return 7;
        Custom first; first.number = 1; Custom second; second.number = 2;
        Custom[] rowCustom = {first}; Custom[][string] custom = {("a", rowCustom)}; primary[][string] primaryCustom = custom;
        primaryCustom.get("a").set(0, second); if (custom.get("a").get(0).number != 2) return 8;
        primary[] customReplacement = {first}; primaryCustom.add("a", customReplacement);
        if (custom.get("a").get(0).number != 1) return 9;
        Custom[][primary] allCustom = custom; allCustom.add(7, rowCustom);
        if (primaryCustom.size() != 2 || allCustom.get(7).get(0).number != 2) return 10;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() {
    auto row = new Z8Array!long([1L, 2L]); auto typed = new Z8StringValueMap!(Z8Array!long)();
    typed.z8_add("a"w, row); auto values = z8_primary_nested_map_view(typed);
    values.z8_get("a"w).z8_set(0, z8_primary_box(3L)); assert(z8_optional_require(row.z8_get(0)) == 3);
    auto replacement = new Z8Array!Z8Primary([z8_primary_box(5L)]); values.z8_add("a"w, replacement);
    assert(z8_optional_require(typed.z8_get("a"w).z8_get(0)) == 5);
    auto keys = z8_primary_key_map_view(typed); auto both = z8_primary_nested_map_view(keys);
    both.z8_add(z8_primary_box(7L), replacement); assert(values.z8_size() == 2);
    replacement.z8_add(z8_primary_box("wrong"w)); bool invalid;
    try { typed.z8_get("a"w).z8_get(1); } catch (Exception) { invalid = true; } assert(invalid);
    auto snapshot = typed.z8_values(); invalid = false;
    foreach (i; 0 .. snapshot.z8_size()) try { snapshot.z8_get(i).z8_get(1); } catch (Exception) { invalid = true; }
    assert(invalid);
    auto other = new Z8StringValueMap!(Z8Array!long)(); other.z8_add("a"w, row);
    auto otherKeys = z8_primary_key_map_view(other); auto otherValues = z8_primary_nested_map_view(other);
    otherKeys.z8_add(z8_primary_box(7L), row); otherValues.z8_get("a"w).z8_set(0, z8_primary_box(10L));
    assert(other.z8_size() == 2 && z8_optional_require(otherKeys.z8_get(z8_primary_box(7L)).z8_get(0)) == 10);
    assert(other.opEquals(otherValues) && otherValues.opEquals(other));
    auto different = new Z8StringValueMap!(Z8Array!long)(); different.z8_add("a"w, new Z8Array!long([123L]));
    z8_primary_key_map_view(different);
    assert(!different.opEquals(otherValues) && !otherValues.opEquals(different));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-nested-string-maps.exe" if os.name == "nt" else "primary-nested-string-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void f() { Plain[][string] source; primary[][string] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted non-primary array elements")
    (source / "Bad.bl").write_text('public class Bad { static void choose(int[][string] x) {} static void choose(primary[][string] x) {} static void f() { int[][string] x; choose(x); } }', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous" not in result.stderr:
        raise SystemExit("Expected ambiguous nested map overloads: " + result.stderr)
print("String-keyed maps of typed arrays share primary array views")
