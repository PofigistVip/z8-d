"""Check that scalar matrices and primary matrices share both dimensions."""
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
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[][] values) { return values.size(); }
    static int choose(int[][] values) { return 2; }
    static primary[][] choice(bool flag, primary[][] a, int[][] b) { return flag ? a : b; }
    public static int run() {
        int[][] typed = {{1, 2}, {3}}; primary[][] values = typed;
        values.get(0).set(0, 8); typed.get(0).set(1, 9);
        if (typed.get(0).get(0) != 8 || (int)values.get(0).get(1) != 9) return 1;
        primary[] replacement = {5, 6}; values.set(1, replacement);
        if (typed.get(1).get(1) != 6) return 2;
        int[] another = {7}; typed.set(0, another);
        if ((int)values.get(0).get(0) != 7) return 3;
        values.get(0).add("wrong");
        try { int bad = typed.get(0).get(1); return 4; } catch (exception expected) {}
        values.get(0).removeAt(1);
        int count = 0; for (primary[] row : typed) count += row.size();
        if (count != 3 || size(typed) != 2 || choose(typed) != 2) return 5;
        if (choice(false, values, typed).size() != 2) return 6;
        values.add(null); typed.set(2, another);
        if ((int)values.get(2).get(0) != 7) return 7;
        int[][] removals = {{7}}; values.removeAll(removals);
        if (values.size() != 1 || typed.size() != 1 || typed.get(0).get(0) != 5) return 8;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() {
    auto row = new Z8Array!long([1L, 2L]);
    auto typed = new Z8Array!(Z8Array!long)([row, null]);
    auto primary = z8_primary_array_view(typed);
    primary.z8_get(0).z8_set(0, z8_primary_box(8L));
    assert(z8_optional_require(typed.z8_get(0).z8_get(0)) == 8);
    typed.z8_get(0).z8_set(1, 9L);
    assert(z8_optional_require(z8_primary_cast!long(primary.z8_get(0).z8_get(1))) == 9);
    auto other = new Z8Array!Z8Primary([z8_primary_box(3L)]);
    primary.z8_set(1, other);
    assert(z8_optional_require(typed.z8_get(1).z8_get(0)) == 3);
    typed.z8_get(1).z8_set(0, 4L);
    assert(z8_optional_require(z8_primary_cast!long(other.z8_get(0))) == 4);
    other.z8_add(z8_primary_box("bad"w));
    bool rejected; try { typed.z8_get(1).z8_get(1); } catch (Exception) { rejected = true; }
    assert(rejected);
    auto before = typed.z8_version; primary.z8_add(null);
    assert(typed.z8_version == before + 1 && typed.z8_size() == 3 && typed.z8_get(2) is null);
    assert(typed.opEquals(primary) && primary.opEquals(typed));
    auto copy = typed.z8_unique(); assert(copy.z8_size() == 3 && copy.opEquals(typed));
    primary.z8_reverse(); assert(typed.z8_first() is null);
    primary.z8_clear(); assert(typed.z8_isEmpty());
    auto single = new Z8Array!(Z8Array!long)([row]);
    auto singlePrimary = z8_primary_array_view(single); auto oldVersion = single.z8_version;
    single.z8_sort(); assert(singlePrimary.z8_version == oldVersion + 1);
    singlePrimary.z8_add(null); rejected = false;
    try { single.z8_sort(); } catch (Exception) { rejected = true; } assert(rejected);
    auto textRows = new Z8Array!(Z8Array!wstring)([new Z8Array!wstring(["first"w])]);
    auto primaryText = z8_primary_array_view(textRows);
    primaryText.z8_get(0).z8_set(0, z8_primary_box("second"w));
    assert(textRows.z8_get(0).z8_get(0) == "second"w);
    auto dateRows = new Z8Array!(Z8Array!Z8Date)([new Z8Array!Z8Date([z8_date_from_ticks(1)])]);
    auto primaryDates = z8_primary_array_view(dateRows);
    auto next = z8_date_from_ticks(2); primaryDates.z8_get(0).z8_set(0, z8_primary_box(next));
    assert(dateRows.z8_get(0).z8_get(0) is next);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}''', encoding="utf-8")
    executable = temp / ("primary-matrices.exe" if os.name == "nt" else "primary-matrices")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Scalar matrices and primary matrices share storage")
