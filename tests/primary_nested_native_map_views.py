"""Share nested primary-array values with enum and native object map keys."""
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
    (source / "Flavor.bl").write_text('public enum Flavor { First, Second }', encoding="utf-8")
    (source / "Other.bl").write_text('public enum Other { First, Second }', encoding="utf-8")
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public int number; public void operator = (Custom value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[][Flavor] values) { return values.size(); }
    static primary[][Flavor] choice(bool flag, primary[][Flavor] a, int[][Flavor] b) { return flag ? a : b; }
    public static int run() {
        int[] row = {1, 2}; int[][Flavor] typed = {(Flavor.First, row)}; primary[][Flavor] values = typed;
        values.get(Flavor.First).set(0, 3); if (typed.get(Flavor.First).get(0) != 3) return 1;
        primary[] replacement = {4, 5}; values.add(Flavor.First, replacement);
        if (typed.get(Flavor.First).get(1) != 5 || size(typed) != 1 || choice(false, values, typed).size() != 1) return 2;
        replacement.add("wrong"); try { int bad = typed.get(Flavor.First).get(2); return 3; } catch (exception expected) {}
        int[][encoding] enc = {(encoding.UTF8, row)}; primary[][encoding] pe = enc;
        pe.get(encoding.UTF8).set(0, 6); if (enc.get(encoding.UTF8).get(0) != 6) return 4;
        exception problem = "problem"; int[][exception] errors = {(problem, row)}; primary[][exception] perr = errors;
        perr.get(problem).set(0, 7); if (errors.get(problem).get(0) != 7) return 5;
        sql_int sql = 1; int[][sql_int] sqlMap = {(sql, row)}; primary[][sql_int] ps = sqlMap;
        ps.get(sql).set(0, 8); if (sqlMap.get(sql).get(0) != 8) return 6;
        Custom one; one.number = 1; Custom two; two.number = 2;
        Custom[] customRow = {one}; Custom[][Flavor] custom = {(Flavor.First, customRow)}; primary[][Flavor] pc = custom;
        pc.get(Flavor.First).set(0, two); if (custom.get(Flavor.First).get(0).number != 2) return 7;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Key {}
void main() {
    auto map = new Z8ObjectKeyMap!(Key, Z8Array!long)(); Key[] keys;
    foreach (i; 0 .. 160) { auto key = new Key(); keys ~= key; map.z8_add(key, new Z8Array!long([cast(long)i])); }
    foreach (i; 0 .. 110) map.z8_remove(keys[i]);
    map.z8_add(null, new Z8Array!long([200L]));
    auto before = map.z8_keys(); auto primary = z8_primary_nested_map_view(map);
    assert(before.opEquals(primary.z8_keys()));
    auto replacement = new Z8Array!Z8Primary([z8_primary_box(9L)]); primary.z8_add(null, replacement);
    assert(z8_optional_require(map.z8_get(null).z8_get(0)) == 9);
    replacement.z8_add(z8_primary_box("bad"w)); bool invalid;
    try { map.z8_get(null).z8_get(1); } catch (Exception) { invalid = true; } assert(invalid);
    auto removed = before.z8_get(10); primary.z8_remove(removed); auto after = primary.z8_keys();
    foreach (i; 0 .. after.z8_size()) assert(after.z8_get(i) is before.z8_get(i < 10 ? i : i + 1));
    assert(map.opEquals(primary) && primary.opEquals(map));
    auto snapshot = map.z8_values(); assert(snapshot.z8_size() == map.z8_size());
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-nested-native-maps.exe" if os.name == "nt" else "primary-nested-native-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void f() { int[][Flavor] source; primary[][Other] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted different enum map keys")
print("Native-object-key maps of typed arrays share primary array views")
