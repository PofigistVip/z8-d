"""Check primary-valued maps with enum and other native object keys."""
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
    (source / "Flavor.bl").write_text('''public enum Flavor { First, Second }''', encoding="utf-8")
    (source / "Other.bl").write_text('''public enum Other { First, Second }''', encoding="utf-8")
    (source / "Value.bl").write_text('''public class Value extends primary {
        public int number; public void operator = (Value value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[Flavor] values) { return values.size(); }
    static primary[Flavor] choice(bool flag, primary[Flavor] a, int[Flavor] b) { return flag ? a : b; }
    public static int run() {
        int[Flavor] typed = {(Flavor.First, 10)}; primary[Flavor] values = typed;
        values.add(Flavor.First, 30); if (typed.get(Flavor.First) != 30) return 1;
        values.add(Flavor.First, "wrong"); try { int bad = typed.get(Flavor.First); return 2; } catch (exception expected) {}
        typed.add(Flavor.First, 50); if ((int)values.get(Flavor.First) != 50) return 3;
        if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 4;
        primary[Flavor] copy = {}; copy.add(typed); if ((int)copy.get(Flavor.First) != 50) return 5;
        int[encoding] enc = {(encoding.UTF8, 1)}; primary[encoding] pe = enc;
        pe.add(encoding.UTF8, 2); if (enc.get(encoding.UTF8) != 2) return 6;
        exception problem = "problem"; string[exception] errors = {(problem, "yes")}; primary[exception] perr = errors;
        perr.add(problem, "changed"); if (errors.get(problem) != "changed") return 7;
        sql_int sql = 1; int[sql_int] sqlMap = {(sql, 1)}; primary[sql_int] ps = sqlMap;
        ps.add(sql, 2); if (sqlMap.get(sql) != 2) return 8;
        Value one; one.number = 1; Value two; two.number = 2;
        Value[Flavor] objects = {(Flavor.First, one)}; primary[Flavor] pv = objects;
        pv.add(Flavor.First, two); if (objects.get(Flavor.First).number != 2) return 9;
        pv.add(Flavor.First, 7); objects.add(Flavor.First, one); if (((Value)pv.get(Flavor.First)).number != 1) return 10;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Key {}
class Item : Z8Object {}
void main() {
    auto large = new Z8ObjectKeyMap!(Key, long)(); Key[] allKeys;
    foreach (i; 0 .. 160) { auto added = new Key(); allKeys ~= added; large.z8_add(added, z8_optional_wrap(cast(long)i)); }
    foreach (i; 0 .. 110) large.z8_remove(allKeys[i]);
    auto orderBefore = large.z8_keys(); auto largePrimary = z8_primary_map_view(large);
    assert(orderBefore.opEquals(largePrimary.z8_keys()));
    auto removed = orderBefore.z8_get(10);
    largePrimary.z8_add(removed, z8_primary_box(999L)); assert(orderBefore.opEquals(largePrimary.z8_keys()));
    largePrimary.z8_remove(removed); auto remaining = largePrimary.z8_keys();
    assert(remaining.z8_size() == orderBefore.z8_size() - 1);
    foreach (i; 0 .. remaining.z8_size()) assert(remaining.z8_get(i) is orderBefore.z8_get(i < 10 ? i : i + 1));
    auto orderedValues = largePrimary.z8_values();
    foreach (i; 0 .. remaining.z8_size()) assert(orderedValues.z8_get(i) == largePrimary.z8_get(remaining.z8_get(i)));
    auto key = new Key(); auto map = new Z8ObjectKeyMap!(Key, long)();
    map.z8_add(key, z8_optional_wrap(1L)); map.z8_add(null, z8_optional_wrap(2L));
    auto prior = map.z8_keys(); auto primary = z8_primary_map_view(map);
    assert(prior.opEquals(primary.z8_keys()) && primary is z8_primary_map_view(map));
    primary.z8_add(key, z8_primary_box(3L)); assert(z8_optional_require(map.z8_get(key)) == 3);
    primary.z8_add(key, z8_primary_box("wrong"w)); bool invalid;
    try { map.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    auto snapshot = map.z8_values(); invalid = false;
    foreach (i; 0 .. snapshot.z8_size()) try { snapshot.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); z8_map_add_discard(map, key, z8_optional_wrap(4L));
    assert(map.opEquals(primary) && primary.opEquals(map));
    alias ObjectMap = Z8CovariantMap!(Key, Item, Z8ObjectKeyMap!(Key, Object), false, true);
    auto objects = new ObjectMap(); auto item = new Item(); objects.z8_add(key, item);
    auto primaryObjects = z8_primary_map_view(objects); primaryObjects.z8_add(key, z8_primary_box("wrong"w)); invalid = false;
    try { objects.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(objects, key, item);
    assert(objects.z8_get(key) is item && objects.opEquals(primaryObjects) && primaryObjects.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-native-maps.exe" if os.name == "nt" else "primary-native-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void run() { int[Flavor] source; primary[Other] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted different enum map keys")
print("Native-object-key maps and primary-valued views share storage")
