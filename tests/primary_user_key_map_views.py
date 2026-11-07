"""Check primary-valued maps with user-defined object keys."""
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
    (source / "Key.bl").write_text('''public class Key {}''', encoding="utf-8")
    (source / "ChildKey.bl").write_text('''public class ChildKey extends Key {}''', encoding="utf-8")
    (source / "Value.bl").write_text('''public class Value extends primary {
        public int number; public void operator = (Value value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[Key] values) { return values.size(); }
    static primary[Key] choice(bool flag, primary[Key] a, int[Key] b) { return flag ? a : b; }
    static primary[Key] childChoice(bool flag, primary[Key] a, int[ChildKey] b) { return flag ? a : b; }
    public static int run() {
        Key key = new Key; int[Key] typed = {(key, 10)}; primary[Key] values = typed;
        values.add(key, 30); if (typed.get(key) != 30) return 1;
        values.add(key, "wrong"); try { int bad = typed.get(key); return 2; } catch (exception expected) {}
        typed.add(key, 50); if ((int)values.get(key) != 50) return 3;
        Key missing = null; values.add(missing, 60); if (typed.get(missing) != 60) return 4;
        if (size(typed) != 2 || choice(false, values, typed).size() != 2) return 5;
        primary[Key] copy = {}; copy.add(typed); if ((int)copy.get(key) != 50) return 6;
        Value one; one.number = 1; Value two; two.number = 2;
        Value[Key] objects = {(key, one)}; primary[Key] primaryObjects = objects;
        primaryObjects.add(key, two); if (objects.get(key).number != 2) return 7;
        primaryObjects.add(key, 3); objects.add(key, one); if (((Value)primaryObjects.get(key)).number != 1) return 8;
        ChildKey child = new ChildKey; int[ChildKey] childMap = {(child, 7)};
        primary[Key] wider = childMap; wider.add(key, 9);
        if (childMap.size() != 2 || childMap.get(child) != 7 || size(childMap) != 2 || childChoice(false, wider, childMap).size() != 2) return 9;
        Value[ChildKey] childObjects = {(child, one)}; primary[Key] widenedObjects = childObjects;
        widenedObjects.add(child, two); if (childObjects.get(child).number != 2) return 11;
        try { for (ChildKey item : childMap.keys()) {} return 10; } catch (exception expected) {}
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Key : Z8Object {}
class Child : Key {}
class Item : Z8Object {}
void main() {
    auto key = new Key();
    alias TypedMap = Z8CovariantMap!(Key, long, Z8ReferenceKeyMap!(Z8Object, long), true, false);
    auto map = new TypedMap(); map.z8_add(key, z8_optional_wrap(1L));
    auto primary = z8_primary_map_view(map); primary.z8_add(key, z8_primary_box(2L));
    assert(z8_optional_require(map.z8_get(key)) == 2);
    primary.z8_add(key, z8_primary_box("wrong"w)); bool invalid;
    try { map.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(map, key, z8_optional_wrap(3L));
    assert(map.opEquals(primary) && primary.opEquals(map));
    alias ObjectMap = Z8CovariantMap!(Key, Item, Z8ReferenceKeyMap!(Z8Object, Object), true, true);
    auto objects = new ObjectMap(); auto item = new Item(); objects.z8_add(key, item);
    auto primaryObjects = z8_primary_map_view(objects);
    primaryObjects.z8_add(key, z8_primary_box("wrong"w)); invalid = false;
    try { objects.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(objects, key, item);
    assert(objects.z8_get(key) is item && objects.opEquals(primaryObjects) && primaryObjects.opEquals(objects));
    auto child = new Child();
    alias ChildMap = Z8CovariantMap!(Child, long, Z8ReferenceKeyMap!(Z8Object, long), true, false);
    auto childMap = new ChildMap(); childMap.z8_add(child, z8_optional_wrap(7L));
    auto wider = z8_primary_object_key_map_view!Key(childMap); wider.z8_add(key, z8_primary_box(9L));
    assert(childMap.z8_size() == 2 && z8_optional_require(childMap.z8_get(child)) == 7);
    auto keys = childMap.z8_keys(); invalid = false;
    foreach (i; 0 .. keys.z8_size()) try { keys.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-object-maps.exe" if os.name == "nt" else "primary-object-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for declaration in ("int[Key] source; primary[ChildKey] target = source;",):
        (source / "Bad.bl").write_text('public class Bad { static void run() { ' + declaration + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted map key downcast: " + declaration)
print("User-key maps and primary-valued views share storage")
