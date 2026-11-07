"""Share maps of typed arrays with maps of primary arrays."""
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
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public int number; public void operator = (Custom value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Plain.bl").write_text('''public class Plain { public operator int() { return 1; } }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[][primary] values) { return values.size(); }
    static primary[][primary] choice(bool flag, primary[][primary] a, int[][primary] b) { return flag ? a : b; }
    static primary[][primary] customChoice(bool flag, primary[][primary] a, Custom[][primary] b) { return flag ? a : b; }
    public static int run() {
        int[] row = {1, 2}; int[][primary] typed = {(1, row)}; primary[][primary] values = typed;
        values.get(1).set(0, 8); typed.get(1).set(1, 9);
        if (typed.get(1).get(0) != 8 || (int)values.get(1).get(1) != 9) return 1;
        primary[] replacement = {5, 6}; values.add(1, replacement);
        if (typed.get(1).get(1) != 6) return 2;
        typed.get(1).set(0, 7); if ((int)replacement.get(0) != 7) return 3;
        replacement.add("wrong"); try { int bad = typed.get(1).get(2); return 4; } catch (exception expected) {}
        replacement.removeAt(2);
        if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 5;
        primary[][primary] copy = {}; copy.add(typed); if ((int)copy.get(1).get(0) != 7) return 6;
        values.add("null", null); typed.add("null", row); if ((int)values.get("null").get(0) != 8) return 7;
        string[] words = {"a"}; string[][primary] strings = {(1, words)}; primary[][primary] primaryStrings = strings;
        primaryStrings.get(1).set(0, "b"); if (strings.get(1).get(0) != "b") return 8;
        Custom first; first.number = 1; Custom second; second.number = 2;
        Custom[] rowCustom = {first}; Custom[][primary] custom = {(1, rowCustom)}; primary[][primary] primaryCustom = custom;
        primaryCustom.get(1).set(0, second); if (custom.get(1).get(0).number != 2) return 9;
        if (size(custom) != 1 || customChoice(false, primaryCustom, custom).size() != 1) return 12;
        primary[] customReplacement = {first}; primaryCustom.add(1, customReplacement);
        if (custom.get(1).get(0).number != 1) return 10;
        customReplacement.add("wrong"); try { int bad = custom.get(1).get(1).number; return 11; } catch (exception expected) {}
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() {
    auto row = new Z8Array!long([1L, 2L]); auto key = z8_primary_box(1L);
    auto typed = new Z8PrimaryKeyMap!(Z8Array!long)(); typed.z8_add(key, row);
    auto values = z8_primary_nested_map_view(typed);
    values.z8_get(key).z8_set(0, z8_primary_box(3L)); assert(z8_optional_require(row.z8_get(0)) == 3);
    auto replacement = new Z8Array!Z8Primary([z8_primary_box(5L)]); values.z8_add(key, replacement);
    assert(z8_optional_require(typed.z8_get(key).z8_get(0)) == 5);
    typed.z8_get(key).z8_set(0, 6L); assert(z8_optional_require(z8_primary_cast!long(replacement.z8_get(0))) == 6);
    replacement.z8_add(z8_primary_box("wrong"w)); bool invalid;
    try { typed.z8_get(key).z8_get(1); } catch (Exception) { invalid = true; } assert(invalid);
    auto snapshot = typed.z8_values(); invalid = false;
    try { snapshot.z8_get(0).z8_get(1); } catch (Exception) { invalid = true; } assert(invalid);
    assert(typed.opEquals(values) && values.opEquals(typed));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-nested-maps.exe" if os.name == "nt" else "primary-nested-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void f() { Plain[][primary] source; primary[][primary] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted non-primary array elements")
    (source / "Bad.bl").write_text('public class Bad { static void choose(int[][primary] x) {} static void choose(primary[][primary] x) {} static void f() { int[][primary] x; choose(x); } }', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous" not in result.stderr:
        raise SystemExit("Expected ambiguous nested map overloads: " + result.stderr)
print("Maps of typed arrays and primary arrays share storage")
