"""Check primary values in maps with GUID and reference keys."""
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
    static int size(primary[guid] values) { return values.size(); }
    static primary[guid] choice(bool flag, primary[guid] a, int[guid] b) { return flag ? a : b; }
    public static int run() {
        guid id = guid.create(1); int[guid] typed = {(id, 10)}; primary[guid] values = typed;
        values.add(id, 30); if (typed.get(id) != 30) return 1;
        values.add(id, "wrong"); try { int bad = typed.get(id); return 2; } catch (exception expected) {}
        typed.add(id, 50); if ((int)values.get(id) != 50) return 3;
        if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 4;
        primary[guid] copy = {}; copy.add(typed); if ((int)copy.get(id) != 50) return 5;
        date d = '01/01/2024'; string[date] dm = {(d, "date")}; primary[date] dp = dm;
        dp.add(d, "updated"); if (dm.get(d) != "updated") return 6;
        datespan span = '1 00:00:00'; int[datespan] sm = {(span, 1)}; primary[datespan] sp = sm;
        sp.add(span, 2); if (sm.get(span) != 2) return 7;
        binary b = '65'; int[binary] bm = {(b, 1)}; primary[binary] bp = bm;
        bp.add(b, 2); if (bm.get(b) != 2) return 8;
        geometry g = geometry.point(1, 2, 4326); int[geometry] gm = {(g, 1)}; primary[geometry] gp = gm;
        gp.add(g, 2); if (gm.get(g) != 2) return 9;
        file f = "some.txt"; int[file] fm = {(f, 1)}; primary[file] fp = fm;
        fp.add(f, 2); if (fm.get(f) != 2) return 10;
        Value one; one.number = 1; Value two; two.number = 2;
        Value[guid] objects = {(id, one)}; primary[guid] pv = objects;
        pv.add(id, two); if (objects.get(id).number != 2) return 11;
        pv.add(id, 7); objects.add(id, one); if (((Value)pv.get(id)).number != 1) return 12;
        Value[date] dateObjects = {(d, one)}; primary[date] pd = dateObjects;
        pd.add(d, two); if (dateObjects.get(d).number != 2) return 13;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
class Item : Z8Object {}
void checkKey(K)(K key) {
    auto map = new Z8ReferenceKeyMap!(K, long)();
    map.z8_add(key, z8_optional_wrap(1L)); map.z8_add(null, z8_optional_wrap(2L));
    auto before = map.z8_keys(); auto primary = z8_primary_map_view(map);
    assert(before.opEquals(primary.z8_keys()));
    primary.z8_add(key, z8_primary_box(3L)); assert(z8_optional_require(map.z8_get(key)) == 3);
    primary.z8_add(key, z8_primary_box("wrong"w)); bool invalid;
    try { map.z8_get(key); } catch (Exception) { invalid = true; } assert(invalid);
    auto other = new Z8ReferenceKeyMap!(K, long)();
    auto otherPrimary = z8_primary_map_view(other); otherPrimary.z8_add(key, z8_primary_box("wrong"w));
    otherPrimary.z8_add(null, z8_primary_box(2L)); assert(map.opEquals(other));
    z8_map_add_discard(map, key, z8_optional_wrap(4L));
    assert(map.opEquals(primary) && primary.opEquals(map));
    primary.z8_clear(); assert(map.z8_isEmpty());
}
void main() {
    auto id = z8_guid_create(1, 2); auto map = new Z8GuidMap!long();
    map.z8_add(id, z8_optional_wrap(1L)); auto primary = z8_primary_map_view(map);
    primary.z8_add(id, z8_primary_box(2L)); assert(z8_optional_require(map.z8_get(id)) == 2);
    primary.z8_add(id, z8_primary_box("wrong"w)); bool invalid;
    try { map.z8_get(id); } catch (Exception) { invalid = true; } assert(invalid);
    auto otherGuid = new Z8GuidMap!long(); z8_primary_map_view(otherGuid).z8_add(id, z8_primary_box("wrong"w));
    assert(map.opEquals(otherGuid));
    z8_map_add_discard(map, id, z8_optional_wrap(3L)); assert(map.opEquals(primary) && primary.opEquals(map));
    checkKey(z8_date_from_ticks(1)); checkKey(z8_datespan_literal("1 00:00:00"));
    checkKey(z8_binary_literal("65")); checkKey(z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 4326));
    checkKey(z8_file_from_path("some.txt"w));
    alias ObjectMap = Z8CovariantMap!(Z8Guid, Item, Z8GuidMap!Object, false, true);
    auto objects = new ObjectMap(); auto item = new Item(); objects.z8_add(id, item);
    auto primaryObjects = z8_primary_map_view(objects); primaryObjects.z8_add(id, z8_primary_box("wrong"w)); invalid = false;
    try { objects.z8_get(id); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(objects, id, item);
    assert(objects.z8_get(id) is item && objects.opEquals(primaryObjects) && primaryObjects.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-ref-maps.exe" if os.name == "nt" else "primary-ref-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Reference-key maps and primary-valued views share storage")
