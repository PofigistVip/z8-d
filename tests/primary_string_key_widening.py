"""Widen string map keys to primary while retaining shared state and order."""
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
    static string[primary] choice(bool flag, string[primary] a, string[string] b) { return flag ? a : b; }
    public static int run() {
        string[string] typed = {("one", "first")}; string[primary] values = typed;
        values.add("one", "second"); if (typed.get("one") != "second") return 1;
        values.add(7, "bad"); try { for (string key : typed.keys()) {} return 2; } catch (exception expected) {}
        values.remove(7); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 3;
        int[string] both = {("x", 10)}; int[primary] keysFirst = both; primary[string] valuesSecond = both;
        keysFirst.add(7, 30); valuesSecond.add("x", "text");
        try { int bad = both.get("x"); return 4; } catch (exception expected) {}
        both.add("x", 40); if ((int)valuesSecond.get("x") != 40 || keysFirst.get(7) != 30) return 5;
        int[string] other = {("x", 20)}; primary[string] valuesFirst = other; int[primary] keysSecond = other;
        valuesFirst.add("x", "text"); try { int bad = keysSecond.get("x"); return 6; } catch (exception expected) {}
        other.add("x", 25); keysSecond.add(7, 35);
        if ((int)valuesFirst.get("x") != 25 || keysSecond.get(7) != 35) return 7;
        string[string] texts = {("x", "text")}; string[primary] textKeys = texts; primary[string] textValues = texts;
        textKeys.add(7, "extra"); textValues.add("x", 9);
        try { string bad = texts.get("x"); return 8; } catch (exception expected) {}
        texts.add("x", "fixed"); if ((string)textValues.get("x") != "fixed" || textKeys.get(7) != "extra") return 9;
        Item item = new Item; item.number = 5; Item[string] objects = {("x", item)}; Item[primary] all = objects;
        all.add(7, item); if (objects.size() != 2 || all.get("x").number != 5) return 10;
        try { for (string key : objects.keys()) {} return 11; } catch (exception expected) {}
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
import std.conv : to;
class Item : Z8Object {}
void main() {
    auto map = new Z8StringMap();
    foreach (i; 0 .. 160) map.z8_add(("key" ~ i.to!string).to!wstring, "v"w);
    foreach (i; 0 .. 110) map.z8_remove(("key" ~ i.to!string).to!wstring);
    map.z8_add(null, "null"w);
    auto before = z8_primary_array_view(map.z8_keys());
    auto insertion = z8_primary_array_view(map.z8_insertion_keys());
    auto primary = z8_primary_key_map_view(map);
    assert(before.opEquals(primary.z8_keys()) && insertion.opEquals(primary.z8_insertion_keys()));
    primary.z8_add(z8_primary_box("key111"w), "changed"w); assert(map.z8_get("key111"w) == "changed"w);
    primary.z8_add(z8_primary_box(7L), "wrong"w); auto keys = map.z8_keys(); bool invalid;
    foreach (i; 0 .. keys.z8_size()) try { keys.z8_get(i); } catch (Exception) { invalid = true; }
    assert(invalid); primary.z8_remove(z8_primary_box(7L)); assert(map.opEquals(primary) && primary.opEquals(map));
    auto values = z8_primary_map_view(map); values.z8_add("key111"w, z8_primary_box(7L)); invalid = false;
    try { map.z8_get("key111"w); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(map, "key111"w, "fixed"w); assert(primary.z8_get(z8_primary_box("key111"w)) == "fixed"w);
    auto numeric = new Z8StringValueMap!long(); numeric.z8_add("x"w, z8_optional_wrap(1L));
    auto valueFirst = z8_primary_map_view(numeric); auto keySecond = z8_primary_key_map_view(numeric);
    valueFirst.z8_add("x"w, z8_primary_box("wrong"w)); invalid = false;
    try { keySecond.z8_get(z8_primary_box("x"w)); } catch (Exception) { invalid = true; } assert(invalid);
    z8_map_add_discard(numeric, "x"w, z8_optional_wrap(8L)); assert(z8_optional_require(keySecond.z8_get(z8_primary_box("x"w))) == 8);
    alias ObjectMap = Z8CovariantMap!(wstring, Item, Z8StringValueMap!Object, false, true);
    auto objects = new ObjectMap(); auto item = new Item(); objects.z8_add("x"w, item);
    auto all = z8_primary_key_map_view(objects); all.z8_add(z8_primary_box(7L), item);
    assert(objects.z8_size() == 2 && objects.opEquals(all) && all.opEquals(objects));
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-string-key-views.exe" if os.name == "nt" else "primary-string-key-views")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("String map keys share storage with primary keys")
