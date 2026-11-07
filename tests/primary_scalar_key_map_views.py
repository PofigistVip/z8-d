"""Check primary-valued views of maps with scalar keys."""
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
    (source / "Value.bl").write_text('''public class Value extends primary {
        public int number; public void operator = (Value value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[int] values) { return values.size(); }
    static primary[int] choice(bool flag, primary[int] a, int[int] b) { return flag ? a : b; }
    public static int run() {
        int[int] typed = {(1, 10), (2, 20)}; primary[int] values = typed;
        values.add(1, 30); typed.add(2, 40);
        if (typed.get(1) != 30 || (int)values.get(2) != 40) return 1;
        values.add(3, "wrong"); try { int bad = typed.get(3); return 2; } catch (exception expected) {}
        typed.add(3, 50); if ((int)values.get(3) != 50) return 3;
        values.add(3, "wrong"); typed.remove(3); if (values.containsKey(3)) return 4;
        int missing = null; values.add(missing, 60); if (typed.get(missing) != 60) return 5;
        if (size(typed) != 3 || choice(false, values, typed).size() != 3) return 6;
        primary[int] copy = {}; copy.add(typed); if ((int)copy.get(1) != 30) return 7;
        string[bool] flags = {(true, "yes")}; primary[bool] primaryFlags = flags;
        primaryFlags.add(false, "no"); if (flags.get(false) != "no") return 8;
        date[decimal] dates = {}; primary[decimal] primaryDates = dates;
        date d = '01/01/2024'; primaryDates.add(1.5, d); if (dates.get(1.5) != d) return 9;
        Value first; first.number = 1; Value second; second.number = 2;
        Value[int] objects = {(1, first)}; primary[int] primaryObjects = objects;
        primaryObjects.add(1, second); if (objects.get(1).number != 2) return 10;
        primaryObjects.add(2, 3); try { int bad = objects.get(2).number; return 11; } catch (exception expected) {}
        objects.add(2, first); if (((Value)primaryObjects.get(2)).number != 1) return 12;
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
    auto before = map.z8_keys(); auto primary = z8_primary_map_view(map);
    assert(before.opEquals(primary.z8_keys()) && primary is z8_primary_map_view(map));
    primary.z8_add(boxed, z8_primary_box(3L)); assert(z8_optional_require(map.z8_get(boxed)) == 3);
    map.z8_add(missing, z8_optional_wrap(4L)); assert(z8_optional_require(z8_primary_cast!long(primary.z8_get(missing))) == 4);
    primary.z8_add(boxed, z8_primary_box("wrong"w));
    bool invalid; try { map.z8_get(boxed); } catch (Exception) { invalid = true; } assert(invalid);
    auto snapshot = map.z8_values(); invalid = false;
    foreach (i; 0 .. snapshot.z8_size()) try { snapshot.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); z8_map_add_discard(map, boxed, z8_optional_wrap(8L));
    assert(map.opEquals(primary) && primary.opEquals(map));
    primary.z8_clear(); assert(map.z8_isEmpty());
}
void main() {
    checkKey(1L); checkKey(true); checkKey(z8_decimal_parse("1.50"w));
    alias ObjectMap = Z8CovariantMap!(long, Item, Z8ScalarKeyMap!(long, Object), false, true);
    auto objects = new ObjectMap(); auto item = new Item(); auto key = z8_optional_wrap(1L);
    objects.z8_add(key, item); auto primary = z8_primary_map_view(objects);
    assert(z8_primary_cast!Item(primary.z8_get(key)) is item);
    primary.z8_add(key, z8_primary_box("wrong"w)); bool invalid;
    try { objects.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(objects, key, item);
    assert(objects.z8_get(key) is item && objects.opEquals(primary) && primary.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-scalar-maps.exe" if os.name == "nt" else "primary-scalar-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text("public class Bad { static void choose(int[int] x) {} static void choose(primary[int] x) {} static void run() { int[int] x; choose(x); } }", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous" not in result.stderr:
        raise SystemExit("Expected ambiguous map overloads: " + result.stderr)
print("Scalar-key maps and primary-valued views share storage")
