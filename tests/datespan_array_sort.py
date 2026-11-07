"""Compare short datespan-array sorting, including comparator mutations, with Java."""
from pathlib import Path
import os
import random
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/DatespanArraySort.bl"
rng = random.Random(381)
cases = [[], [None], [1000, 2000], [-1000, 2000], [None, 1000], [1000, None],
         [1000, -1000, 0], [None, 3, 1], [4, None, 2], [-(1 << 63), 1]]
cases += [[rng.choice([None, -3000, -1000, 0, 1000, 2000, 3000]) for _ in range(rng.randrange(2, 32))]
          for _ in range(100)]
cases += [[rng.choice([-3000, -1000, 0, 1000, 2000, 3000]) for _ in range(rng.randrange(2, 32))]
          for _ in range(100)]

def d_number(value):
    return "long.min" if value == -(1 << 63) else str(value) + "L"

def j_number(value):
    return "Long.MIN_VALUE" if value == -(1 << 63) else str(value) + "L"

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("sort.exe" if os.name == "nt" else "sort")
    subprocess.run([str(compiler), "build", str(temp), "DatespanArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    d_cases = []
    j_cases = []
    for case in cases:
        d_values = ", ".join("null" if value is None else "new Z8Datespan(" + d_number(value) + ")" for value in case)
        j_values = ", ".join("null" if value is None else "new datespan(" + j_number(value) + ")" for value in case)
        d_cases.append("run([" + d_values + "]);" if case else "run(cast(Z8Datespan[])[]);")
        j_cases.append("run(new datespan[]{" + j_values + "});")
    source = temp / "sort.d"
    source.write_text('''import z8.runtime;
import std.stdio : write, writeln;
void run(Z8Datespan[] refs) {
    auto values = new Z8Array!Z8Datespan(refs.dup);
    auto view = z8_primary_array_view(values);
    bool failed; try values.z8_sort(); catch (Exception) failed = true;
    write(failed ? "E:" : "O:");
    foreach (i; 0 .. values.z8_size()) {
        auto value = values.z8_get(i); if (value is null) write("n,");
        else foreach (index, original; refs) if (value is original) { write(index, ","); break; }
        assert((value is null && view.z8_get(i) is null) || z8_primary_cast!Z8Datespan(view.z8_get(i)) is value);
    }
    write(":"); foreach (value; refs) if (value is null) write("n,"); else write(value.ticks, ","); writeln();
}
void main() {
''' + "\n".join(d_cases) + '''
    auto large = new Z8Array!Z8Datespan(); foreach (_; 0 .. 32) large.z8_add(new Z8Datespan(1));
    bool failed; try large.z8_sort(); catch (Exception) failed = true; assert(failed);
}''', encoding="utf-8")
    executable = temp / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        if not jars:
            raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "DatespanSortOracle.java"
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.datespan;
class DatespanSortOracle {
  static void run(datespan[] refs) {
    RCollection<datespan> values = new RCollection<>(refs.clone());
    boolean failed = false; try { values.z8_sort(); } catch (RuntimeException error) { failed = true; }
    System.out.print(failed ? "E:" : "O:");
    for (datespan value : values) {
      if (value == null) System.out.print("n,");
      else for (int i = 0; i < refs.length; ++i) if (refs[i] == value) { System.out.print(i + ","); break; }
    }
    System.out.print(":"); for (datespan value : refs) System.out.print(value == null ? "n," : value.milliseconds() + ",");
    System.out.println();
  }
  public static void main(String[] args) {
''' + "\n".join(j_cases) + '''
  }
}''', encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "DatespanSortOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
        assert actual == expected, next((i, cases[i], left, right) for i, (left, right) in enumerate(zip(actual, expected)) if left != right)
print("Short datespan-array sorting and comparator mutations verified")
