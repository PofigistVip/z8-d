"""Check shared string/primary array storage and checked typed reads."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
void main() {
    auto strings = new Z8Array!wstring(["one"w, "two"w]);
    auto before = strings.z8_version;
    auto values = z8_primary_array_view(strings);
    assert(values is z8_primary_array_view(strings));
    assert(strings.z8_version == before && values.z8_size() == 2);
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "one"w);
    strings.z8_set(0, "changed"w);
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "changed"w);
    values.z8_set(1, z8_primary_box("other"w));
    assert(strings.z8_get(1) == "other"w);
    values.z8_add(null);
    assert(strings.z8_size() == 3 && strings.z8_get(2) is null);
    strings.z8_set(2, "last"w);
    assert(z8_primary_cast!wstring(values.z8_get(2)) == "last"w);
    values.z8_add(z8_primary_box(7L));
    bool invalid;
    try { strings.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid && strings.z8_size() == 4);
    invalid = false;
    try { strings.z8_removeAt(3); } catch (Exception) { invalid = true; }
    assert(invalid && values.z8_size() == 3);
    auto same = new Z8Array!wstring(["changed"w, "other"w, "last"w]);
    assert(strings == same && values.opEquals(strings) && strings.opEquals(values));
    auto saved = values.z8_version;
    strings.z8_add("more"w);
    assert(values.z8_version == saved + 1 && strings.z8_version == values.z8_version);
    strings.z8_reverse();
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "more"w);
    strings.z8_sort();
    assert(z8_primary_cast!wstring(values.z8_get(0)) == "changed"w);
    auto extra = new Z8Array!wstring(["x"w]);
    extra.z8_addAll(strings);
    assert(extra.z8_size() == 5 && extra.z8_get(1) == "changed"w);
    values.z8_clear();
    assert(strings.z8_isEmpty());
    assert(z8_primary_array_view(cast(Z8Array!wstring)null) is null);
}
''', encoding="utf-8")
    executable = temp / ("primary-array-views.exe" if os.name == "nt" else "primary-array-views")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)],
                   cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    bl, generated = temp / "bl", temp / "generated"
    bl.mkdir()
    (bl / "Input.bl").write_text('''
[native "example.Input"] public class Input { public static int size(primary[] values); }
''', encoding="utf-8")
    (bl / "Probe.bl").write_text('''
public class Probe {
    public static primary[] asPrimary(string[] values) { return values; }
    public static primary[] choice(bool first, primary[] left, string[] right) { return first ? left : right; }
    public static int count(string[] values) { int result = 0; for (primary part : values) { result += 1; } return result; }
    public static int run() {
        string[] words = {"one", "two"};
        primary[] values = words;
        values.set(0, "north"); words.set(1, "south");
        if (words[0] != "north" || (string) values[1] != "south") return 1;
        words[0] = "fresh"; words[0] += "!";
        if ((string) values[0] != "fresh!") return 2;
        values.add(7);
        try { string wrong = words[2]; return 3; } catch (exception expected) {}
        values.set(2, "fixed"); values.add(null); words[3] = "last";
        if (words[2] != "fixed" || (string) values[3] != "last") return 4;
        if (count(words) != 4 || Input.size(words) != 4) return 5;
        if (choice(false, values, words).size() != 4) return 6;
        try { for (primary part : words) { words.add("more"); } return 7; } catch (exception expected) {}
        if (values.size() != 5) return 8;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(bl), str(generated)], check=True)
    harness = temp / "bl_main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
Z8Optional!long count(Z8Array!Z8Primary values) { return z8_optional_wrap(z8_nonnull(values).z8_size()); }
void main() {
    z8_native_bind("example.Input.m_size"w, &count);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}
''', encoding="utf-8")
    executable = temp / ("primary-array-bl.exe" if os.name == "nt" else "primary-array-bl")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("String and primary array views share storage")
