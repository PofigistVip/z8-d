"""Share reference-keyed maps of typed arrays with maps of primary arrays."""
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
    static int size(primary[][guid] values) { return values.size(); }
    static primary[][guid] choice(bool flag, primary[][guid] a, int[][guid] b) { return flag ? a : b; }
    public static int run() {
        guid id = guid.create(1); int[] row = {1, 2}; int[][guid] typed = {(id, row)}; primary[][guid] values = typed;
        values.get(id).set(0, 8); typed.get(id).set(1, 9);
        if (typed.get(id).get(0) != 8 || (int)values.get(id).get(1) != 9) return 1;
        primary[] replacement = {5, 6}; values.add(id, replacement);
        if (typed.get(id).get(1) != 6) return 2;
        typed.get(id).set(0, 7); if ((int)replacement.get(0) != 7) return 3;
        replacement.add("wrong"); try { int bad = typed.get(id).get(2); return 4; } catch (exception expected) {}
        replacement.removeAt(2); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 5;
        int[][primary] keys = typed; primary[][primary] both = keys;
        both.add("extra", replacement); if (typed.size() != 2 || (int)both.get(id).get(0) != 7) return 6;
        date d = '01/01/2024'; int[][date] dates = {(d, row)}; primary[][date] pd = dates;
        pd.get(d).set(0, 10); if (dates.get(d).get(0) != 10) return 7;
        datespan span = '1 00:00:00'; int[][datespan] spans = {(span, row)}; primary[][datespan] ps = spans;
        ps.get(span).set(0, 11); if (spans.get(span).get(0) != 11) return 8;
        binary b = '65'; int[][binary] binaries = {(b, row)}; primary[][binary] pb = binaries;
        pb.get(b).set(0, 12); if (binaries.get(b).get(0) != 12) return 9;
        geometry g = geometry.point(1, 2, 4326); int[][geometry] points = {(g, row)}; primary[][geometry] pg = points;
        pg.get(g).set(0, 13); if (points.get(g).get(0) != 13) return 10;
        file f = "some.txt"; int[][file] files = {(f, row)}; primary[][file] pf = files;
        pf.get(f).set(0, 14); if (files.get(f).get(0) != 14) return 11;
        Custom first; first.number = 1; Custom second; second.number = 2;
        Custom[] rowCustom = {first}; Custom[][guid] custom = {(id, rowCustom)}; primary[][guid] primaryCustom = custom;
        primaryCustom.get(id).set(0, second); if (custom.get(id).get(0).number != 2) return 12;
        primary[] customReplacement = {first}; primaryCustom.add(id, customReplacement);
        if (custom.get(id).get(0).number != 1) return 13;
        Custom[][primary] allCustom = custom; allCustom.add("extra", rowCustom);
        if (primaryCustom.size() != 2 || allCustom.get("extra").get(0).number != 2) return 14;
        Custom[][guid] otherCustom = {(id, rowCustom)}; Custom[][primary] customKeysFirst = otherCustom;
        primary[][guid] customValuesSecond = otherCustom; customKeysFirst.add("extra", rowCustom);
        customValuesSecond.get(id).set(0, second); if (customKeysFirst.get("extra").get(0).number != 2) return 16;
        Custom[][date] dateCustom = {(d, rowCustom)}; primary[][date] primaryDateCustom = dateCustom;
        primaryDateCustom.get(d).set(0, first); if (dateCustom.get(d).get(0).number != 1) return 15;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void check(K)(K key) {
    auto row = new Z8Array!long([1L, 2L]); auto typed = new Z8ReferenceKeyMap!(K, Z8Array!long)();
    typed.z8_add(key, row); auto values = z8_primary_nested_map_view(typed);
    values.z8_get(key).z8_set(0, z8_primary_box(3L)); assert(z8_optional_require(row.z8_get(0)) == 3);
    auto replacement = new Z8Array!Z8Primary([z8_primary_box(5L)]); values.z8_add(key, replacement);
    assert(z8_optional_require(typed.z8_get(key).z8_get(0)) == 5);
    auto keys = z8_primary_key_map_view(typed); auto both = z8_primary_nested_map_view(keys);
    both.z8_add(z8_primary_box("extra"w), replacement); assert(values.z8_size() == 2);
    replacement.z8_add(z8_primary_box("wrong"w)); bool invalid;
    try { typed.z8_get(key).z8_get(1); } catch (Exception) { invalid = true; } assert(invalid);
    assert(typed.opEquals(values) && values.opEquals(typed));
}
void main() {
    auto id = z8_guid_create(1, 2), row = new Z8Array!long([1L]);
    auto typed = new Z8GuidMap!(Z8Array!long)(); typed.z8_add(id, row); auto values = z8_primary_nested_map_view(typed);
    values.z8_get(id).z8_set(0, z8_primary_box(2L)); assert(z8_optional_require(row.z8_get(0)) == 2);
    assert(typed.opEquals(values) && values.opEquals(typed));
    check(z8_date_from_ticks(1)); check(z8_datespan_literal("1 00:00:00")); check(z8_binary_literal("65"));
    check(z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 4326)); check(z8_file_from_path("some.txt"w));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-nested-ref-maps.exe" if os.name == "nt" else "primary-nested-ref-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void f() { Plain[][guid] source; primary[][guid] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted non-primary array elements")
    (source / "Bad.bl").write_text('public class Bad { static void choose(int[][guid] x) {} static void choose(primary[][guid] x) {} static void f() { int[][guid] x; choose(x); } }', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous" not in result.stderr:
        raise SystemExit("Expected ambiguous nested map overloads: " + result.stderr)
print("Reference-keyed maps of typed arrays share primary array views")
