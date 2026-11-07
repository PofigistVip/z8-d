"""Widen int, bool and decimal map keys to primary without copying."""
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
    (source / "Item.bl").write_text('''public class Item { public int number; }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(string[primary] values) { return values.size(); }
    static string[primary] choice(bool flag, string[primary] a, string[int] b) { return flag ? a : b; }
    public static int run() {
        string[int] typed = {(1, "one")}; string[primary] values = typed;
        values.add(1, "two"); if (typed.get(1) != "two") return 1;
        values.add("wrong", "bad"); try { for (int key : typed.keys()) {} return 2; } catch (exception expected) {}
        values.remove("wrong"); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 3;
        string[bool] flags = {(true, "yes")}; string[primary] primaryFlags = flags;
        primaryFlags.add(true, "changed"); if (flags.get(true) != "changed") return 4;
        string[decimal] decimals = {(1.5, "before")}; string[primary] primaryDecimals = decimals;
        primaryDecimals.add(1.5, "after"); if (decimals.get(1.5) != "after") return 5;
        int[int] both = {(1, 10)}; int[primary] keysFirst = both; primary[int] valuesSecond = both;
        keysFirst.add("extra", 30); valuesSecond.add(1, "text");
        try { int bad = both.get(1); return 6; } catch (exception expected) {}
        both.add(1, 40); if ((int)valuesSecond.get(1) != 40 || keysFirst.get("extra") != 30) return 7;
        int[int] other = {(2, 20)}; primary[int] valuesFirst = other; int[primary] keysSecond = other;
        valuesFirst.add(2, "text"); try { int bad = keysSecond.get(2); return 8; } catch (exception expected) {}
        other.add(2, 25); keysSecond.add("extra", 35);
        if ((int)valuesFirst.get(2) != 25 || keysSecond.get("extra") != 35) return 9;
        int[] row = {1, 2}; int[][int] nested = {(1, row)}; int[][primary] allRows = nested;
        allRows.add("extra", row); if (nested.size() != 2 || allRows.get(1).get(1) != 2) return 12;
        Item item = new Item; item.number = 5; Item[int] objects = {(1, item)}; Item[primary] all = objects;
        all.add("extra", item); if (objects.size() != 2 || all.get(1).number != 5) return 10;
        try { for (int key : objects.keys()) {} return 11; } catch (exception expected) {}
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Item : Z8Object {}
void checkKey(K)(K key) {
    auto map = new Z8ScalarKeyMap!(K, long)();
    auto boxed = z8_optional_wrap(key), missing = Z8Optional!K.init;
    map.z8_add(boxed, z8_optional_wrap(1L)); map.z8_add(missing, z8_optional_wrap(2L));
    auto before = z8_primary_array_view(map.z8_keys()); auto primary = z8_primary_key_map_view(map);
    assert(before.opEquals(primary.z8_keys()) && primary is z8_primary_key_map_view(map));
    primary.z8_add(z8_primary_box(boxed), z8_optional_wrap(3L)); assert(z8_optional_require(map.z8_get(boxed)) == 3);
    primary.z8_add(z8_primary_box("wrong"w), z8_optional_wrap(4L));
    auto keys = map.z8_keys(); bool invalid;
    foreach (i; 0 .. keys.z8_size()) try { keys.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); primary.z8_remove(z8_primary_box("wrong"w));
    assert(map.opEquals(primary) && primary.opEquals(map));
    auto primaryValues = z8_primary_map_view(map); primaryValues.z8_add(boxed, z8_primary_box("wrong"w));
    invalid = false; try { map.z8_get(boxed); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(map, boxed, z8_optional_wrap(5L));
    assert(z8_optional_require(primary.z8_get(z8_primary_box(boxed))) == 5);
}
void main() {
    checkKey(1L); checkKey(true); checkKey(z8_decimal_parse("1.50"w));
    auto many = new Z8IntMap!long();
    foreach (i; 0 .. 160) many.z8_add(z8_optional_wrap(cast(long)(i * 17 - 1000)), z8_optional_wrap(cast(long)i));
    foreach (i; 0 .. 110) many.z8_remove(z8_optional_wrap(cast(long)(i * 17 - 1000)));
    many.z8_add(Z8Optional!long.init, z8_optional_wrap(999L));
    auto before = z8_primary_array_view(many.z8_keys()); auto manyPrimary = z8_primary_key_map_view(many);
    assert(before.opEquals(manyPrimary.z8_keys()));
    auto manyKeys = manyPrimary.z8_keys(), manyValues = manyPrimary.z8_values();
    foreach (i; 0 .. manyKeys.z8_size()) assert(manyValues.z8_get(i) == manyPrimary.z8_get(manyKeys.z8_get(i)));

    auto map = new Z8IntMap!long(); auto key = z8_optional_wrap(1L);
    map.z8_add(key, z8_optional_wrap(1L)); auto valuesFirst = z8_primary_map_view(map);
    auto keysSecond = z8_primary_key_map_view(map);
    valuesFirst.z8_add(key, z8_primary_box("wrong"w)); bool invalid;
    try { keysSecond.z8_get(z8_primary_box(key)); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(map, key, z8_optional_wrap(9L));
    assert(z8_optional_require(keysSecond.z8_get(z8_primary_box(key))) == 9);
    alias ObjectMap = Z8CovariantMap!(long, Item, Z8ScalarKeyMap!(long, Object), false, true);
    auto objects = new ObjectMap(); auto item = new Item(); objects.z8_add(key, item);
    auto primaryObjects = z8_primary_key_map_view(objects); primaryObjects.z8_add(z8_primary_box("x"w), item);
    assert(objects.z8_size() == 2 && objects.opEquals(primaryObjects) && primaryObjects.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-scalar-key-views.exe" if os.name == "nt" else "primary-scalar-key-views")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Scalar map keys share storage with primary keys")
