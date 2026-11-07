"""Check primary-valued views of maps whose keys are primary values."""
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
    static int size(primary[primary] values) { return values.size(); }
    static primary[primary] choice(bool flag, primary[primary] a, int[primary] b) { return flag ? a : b; }
    public static int run() {
        int[primary] typed = {(1, 10), ("text", 20)}; primary[primary] values = typed;
        values.add(1, 30); typed.add("text", 40);
        if (typed.get(1) != 30 || (int)values.get("text") != 40) return 1;
        values.add(3, "wrong"); try { int bad = typed.get(3); return 2; } catch (exception expected) {}
        typed.add(3, 50); if ((int)values.get(3) != 50) return 3;
        values.add(3, "wrong"); typed.remove(3); if (values.containsKey(3)) return 4;
        primary missing = null; values.add(missing, 60); if (typed.get(missing) != 60) return 5;
        if (size(typed) != 3 || choice(false, values, typed).size() != 3) return 6;
        primary[primary] copy = {}; copy.add(typed); if ((int)copy.get(1) != 30) return 7;
        Value first; first.number = 1; Value second; second.number = 2;
        Value[primary] objects = {(1, first)}; primary[primary] primaryObjects = objects;
        primaryObjects.add(1, second); if (objects.get(1).number != 2) return 8;
        primaryObjects.add(2, 3); try { int bad = objects.get(2).number; return 9; } catch (exception expected) {}
        objects.add(2, first); if (((Value)primaryObjects.get(2)).number != 1) return 10;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Item : Z8Object {}
void main() {
    auto map = new Z8PrimaryKeyMap!long();
    auto key = z8_guid_create(1, 2), boxed = z8_primary_box(key);
    map.z8_add(boxed, z8_optional_wrap(1L));
    map.z8_add(z8_primary_box("Aa"w), z8_optional_wrap(2L));
    map.z8_add(z8_primary_box("BB"w), z8_optional_wrap(3L));
    map.z8_add(null, z8_optional_wrap(4L));
    auto before = map.z8_keys(); auto oldMinor = key.minorBits; key.minorBits = oldMinor + 1;
    assert(!map.z8_containsKey(boxed)); auto primary = z8_primary_map_view(map);
    assert(!primary.z8_containsKey(boxed)); key.minorBits = oldMinor; assert(primary.z8_containsKey(boxed));
    assert(before.opEquals(primary.z8_keys()) && primary is z8_primary_map_view(map));
    primary.z8_add(boxed, z8_primary_box(5L)); assert(z8_optional_require(map.z8_get(boxed)) == 5);
    map.z8_add(null, z8_optional_wrap(6L)); assert(z8_optional_require(z8_primary_cast!long(primary.z8_get(null))) == 6);
    primary.z8_add(boxed, z8_primary_box("wrong"w)); bool invalid;
    try { map.z8_get(boxed); } catch (Exception) { invalid = true; } assert(invalid);
    auto snapshot = map.z8_values(); invalid = false;
    foreach (i; 0 .. snapshot.z8_size()) try { snapshot.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); z8_map_add_discard(map, boxed, z8_optional_wrap(8L));
    assert(map.opEquals(primary) && primary.opEquals(map));
    // HashMap retains the hash recorded on insertion even if a key mutates.
    oldMinor = key.minorBits; key.minorBits = oldMinor + 1;
    assert(!map.z8_containsKey(boxed)); key.minorBits = oldMinor; assert(map.z8_containsKey(boxed));
    alias ObjectMap = Z8CovariantMap!(Z8Primary, Item, Z8PrimaryKeyMap!Object, false, true);
    auto objects = new ObjectMap(); auto item = new Item(); auto objectKey = z8_primary_box(1L);
    objects.z8_add(objectKey, item); auto primaryObjects = z8_primary_map_view(objects);
    primaryObjects.z8_add(objectKey, z8_primary_box("wrong"w)); invalid = false;
    try { objects.z8_get(objectKey); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(objects, objectKey, item);
    assert(objects.z8_get(objectKey) is item && objects.opEquals(primaryObjects) && primaryObjects.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-primary-maps.exe" if os.name == "nt" else "primary-primary-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Primary-key maps and primary-valued views share storage")
