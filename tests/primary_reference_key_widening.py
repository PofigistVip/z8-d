"""Widen GUID, reference and user-primary map keys without copying."""
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
    (source / "Key.bl").write_text('''public class Key extends primary { public void operator = (Key value) {} }''', encoding="utf-8")
    (source / "ObjectValue.bl").write_text('''public class ObjectValue { public int number; }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(string[primary] values) { return values.size(); }
    static string[primary] choice(bool flag, string[primary] a, string[guid] b) { return flag ? a : b; }
    public static int run() {
        guid id = guid.create(1); string[guid] typed = {(id, "one")}; string[primary] values = typed;
        values.add(id, "two"); if (typed.get(id) != "two") return 1;
        typed.add(id, "three"); if (values.get(id) != "three") return 2;
        values.add("wrong", "bad");
        try { for (guid item : typed.keys()) {} return 3; } catch (exception expected) {}
        values.remove("wrong"); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 4;
        date d = '01/01/2024'; int[date] dates = {(d, 1)}; int[primary] primaryDates = dates;
        primaryDates.add(d, 2); if (dates.get(d) != 2) return 5;
        datespan span = '1 00:00:00'; int[datespan] spans = {(span, 1)}; int[primary] primarySpans = spans;
        primarySpans.add(span, 2); if (spans.get(span) != 2) return 6;
        binary b = '65'; int[binary] binaries = {(b, 1)}; int[primary] primaryBinaries = binaries;
        primaryBinaries.add(b, 2); if (binaries.get(b) != 2) return 7;
        geometry g = geometry.point(1, 2, 4326); int[geometry] points = {(g, 1)}; int[primary] primaryPoints = points;
        primaryPoints.add(g, 2); if (points.get(g) != 2) return 8;
        file f = "some.txt"; int[file] files = {(f, 1)}; int[primary] primaryFiles = files;
        primaryFiles.add(f, 2); if (files.get(f) != 2) return 9;
        Key key; int[Key] custom = {(key, 1)}; int[primary] customPrimary = custom;
        customPrimary.add(key, 2); if (custom.get(key) != 2) return 10;
        ObjectValue value = new ObjectValue; value.number = 3;
        ObjectValue[guid] objects = {(id, value)}; ObjectValue[primary] primaryObjects = objects;
        primaryObjects.add("extra", value); if (objects.size() != 2 || primaryObjects.get(id).number != 3) return 11;
        try { for (guid item : objects.keys()) {} return 12; } catch (exception expected) {}
        int[] row = {1, 2}; int[][guid] matrix = {(id, row)}; int[][primary] primaryMatrix = matrix;
        primaryMatrix.add("extra", row); if (matrix.size() != 2 || primaryMatrix.get(id).get(1) != 2) return 14;
        ObjectValue[] objectRow = {value}; ObjectValue[][guid] objectArrays = {(id, objectRow)};
        ObjectValue[][primary] allObjectArrays = objectArrays;
        allObjectArrays.add("extra", objectRow); if (objectArrays.size() != 2 || allObjectArrays.get(id).get(0).number != 3) return 15;
        ObjectValue[Key] customObjects = {(key, value)}; ObjectValue[primary] allObjects = customObjects;
        allObjects.add("extra", value); if (customObjects.size() != 2 || allObjects.get(key).number != 3) return 13;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Item : Z8Object {}
class UserKey : Z8Object {}
void main() {
    auto id = z8_guid_create(1, 2); auto typed = new Z8GuidMap!long();
    typed.z8_add(id, z8_optional_wrap(1L)); auto primary = z8_primary_key_map_view(typed);
    primary.z8_add(z8_primary_box(id), z8_optional_wrap(2L)); assert(z8_optional_require(typed.z8_get(id)) == 2);
    primary.z8_add(z8_primary_box("wrong"w), z8_optional_wrap(3L));
    auto keys = typed.z8_keys(); bool invalid;
    foreach (i; 0 .. keys.z8_size()) try { keys.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); primary.z8_remove(z8_primary_box("wrong"w));
    assert(typed.opEquals(primary) && primary.opEquals(typed));
    assert(z8_primary_key_map_view(cast(Z8GuidMap!long)null) is null);
    auto item = new Item();
    alias GuidObjects = Z8CovariantMap!(Z8Guid, Item, Z8GuidMap!Object, false, true);
    auto guidObjects = new GuidObjects(); guidObjects.z8_add(id, item);
    auto allGuidObjects = z8_primary_key_map_view(guidObjects);
    assert(guidObjects.opEquals(allGuidObjects) && allGuidObjects.opEquals(guidObjects));
    alias UserKeys = Z8CovariantMap!(UserKey, long, Z8ReferenceKeyMap!(Z8Object, long), true, false);
    auto userKeys = new UserKeys(); auto userKey = new UserKey(); userKeys.z8_add(userKey, z8_optional_wrap(1L));
    auto allUserKeys = z8_primary_key_map_view(userKeys);
    assert(userKeys.opEquals(allUserKeys) && allUserKeys.opEquals(userKeys));
    alias UserObjects = Z8CovariantMap!(UserKey, Item, Z8ReferenceKeyMap!(Z8Object, Object), true, true);
    auto userObjects = new UserObjects(); userObjects.z8_add(userKey, item);
    auto allUserObjects = z8_primary_key_map_view(userObjects);
    assert(userObjects.opEquals(allUserObjects) && allUserObjects.opEquals(userObjects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-key-views.exe" if os.name == "nt" else "primary-key-views")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void run() { int[Bad] source; int[primary] target = source; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted a non-primary user key")
print("Reference and user-primary map keys share storage with primary keys")
