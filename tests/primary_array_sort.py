"""Compare short mixed primary[] sorting and side effects with Java Z8."""
from pathlib import Path
import os
import random
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/PrimaryArraySort.bl"
rng = random.Random(357)
values = [None, ("i", -3), ("i", 0), ("i", 2), ("d", "-1.5"), ("d", "2.5"), ("d", "NaN"),
          ("b", False), ("b", True), ("s", "A"), ("s", "B"), ("g", -1), ("g", 2),
          ("date", 0), ("date", 1000), ("span", -1000), ("span", 2000),
          ("binary", 1), ("file", 1), ("geometry", ""), ("geometry", "A"), ("geometry", "B")]
cases = [[("i", 3), ("i", 1), ("i", 2)], [("i", 1), ("d", "NaN")],
         [("span", 1000), ("span", 2000)], [None, ("i", 1)], [("i", 1), None]]
cases += [[rng.choice(values) for _ in range(rng.randrange(2, 32))] for _ in range(200)]
cases += [[rng.choice(values[1:]) for _ in range(rng.randrange(2, 32))] for _ in range(100)]
for kind in ("i", "d", "b", "s", "g", "date", "binary", "file", "geometry"):
    candidates = [item for item in values if item is not None and item[0] == kind and item != ("geometry", "")]
    for length in (32, 33, 64, 100):
        cases.append([rng.choice(candidates) for _ in range(length)])
for length in (32, 33, 64, 100):
    cases.append([rng.choice([("i", -3), ("i", 2), ("d", "-1"), ("d", "2")]) for _ in range(length)])
    cases.append([rng.choice([("binary", 1), ("file", 1)]) for _ in range(length)])
    cases.append([None] + [rng.choice([("binary", 1), ("file", 1)]) for _ in range(length - 1)])

def make(value):
    if value is None:
        return "null", "null"
    kind, data = value
    if kind == "i": return "z8_primary_box(%dL)" % data, "new integer(%dL)" % data
    if kind == "d":
        return ("z8_primary_box(z8_decimal_nan())", "new decimal(Double.NaN)") if data == "NaN" else (
            'z8_primary_box(z8_decimal_parse("%s"w))' % data, 'new decimal("%s")' % data)
    if kind == "b": return "z8_primary_box(%s)" % str(data).lower(), "new bool(%s)" % str(data).lower()
    if kind == "s": return 'z8_primary_box("%s"w)' % data, 'new string("%s")' % data
    if kind == "g": return "z8_primary_box(z8_guid_create(0, %d))" % data, "new guid(0L, %dL)" % data
    if kind == "date": return "z8_primary_box(z8_date_from_ticks(%d))" % data, "new date(%dL)" % data
    if kind == "span": return "z8_primary_box(new Z8Datespan(%d))" % data, "new datespan(%dL)" % data
    if kind == "binary": return 'z8_primary_box(z8_binary_literal("%d"))' % data, "new binary(new byte[]{%d})" % data
    if kind == "file": return 'z8_primary_box(z8_file_from_path("%d"w))' % data, 'new file("%d")' % data
    return ('z8_primary_box(z8_geometry_fromHexString("%s"w))' % data, 'new geometry("%s")' % data)

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("sort.exe" if os.name == "nt" else "sort")
    subprocess.run([str(compiler), "build", str(temp), "PrimaryArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    d_cases, j_cases = [], []
    for case in cases:
        converted = [make(item) for item in case]
        d_cases.append("run([%s]);" % ",".join(item[0] for item in converted))
        j_cases.append("run(new primary[]{%s});" % ",".join(item[1] for item in converted))
    source = temp / "sort.d"
    source.write_text('''import z8.runtime;
import std.stdio : write, writeln;
void run(Z8Primary[] refs) {
    auto values = new Z8Array!Z8Primary(refs.dup);
    bool failed; try values.z8_sort(); catch (Exception) failed = true;
    write(failed ? "E:" : "O:");
    foreach (i; 0 .. values.z8_size()) {
        auto value = values.z8_get(i);
        if (value is null) write("n,");
        else foreach (index, original; refs) if (value is original) { write(index, ","); break; }
    }
    write(":"); foreach (value; refs) if (value !is null && value.kind == Z8PrimaryKind.datespan) write(value.datespanValue.ticks, ",");
    writeln();
}
void main() {
''' + "\n".join(d_cases) + '''
    auto first = z8_date_from_ticks(2000), earlier = z8_date_from_ticks(1000);
    auto typed = new Z8Array!Z8Date([first, earlier]); auto view = z8_primary_array_view(typed);
    view.z8_sort(); assert(typed.z8_get(0) is earlier && typed.z8_get(1) is first);
    auto one = new Z8Datespan(1000), two = new Z8Datespan(2000);
    auto spans = new Z8Array!Z8Datespan([one, two]); z8_primary_array_view(spans).z8_sort();
    assert(two.ticks == -1000 && spans.z8_get(0) is two);
    auto large = new Z8Array!Z8Primary(); foreach (_; 0 .. 32) large.z8_add(z8_primary_box(1L));
    assert(large.z8_sort() is large);
    large.z8_add(z8_primary_box("mixed"w));
    bool failed; try large.z8_sort(); catch (Exception) failed = true; assert(failed);
    auto fractional = new Z8Array!Z8Primary(); foreach (_; 0 .. 31) fractional.z8_add(z8_primary_box(1L));
    fractional.z8_add(z8_primary_box(z8_decimal_parse("1.5"w)));
    failed = false; try fractional.z8_sort(); catch (Exception) failed = true; assert(failed);
    auto overflow = new Z8Array!Z8Primary(); foreach (_; 0 .. 30) overflow.z8_add(z8_primary_box(0L));
    overflow.z8_add(z8_primary_box(long.min)); overflow.z8_add(z8_primary_box(long.max));
    failed = false; try overflow.z8_sort(); catch (Exception) failed = true; assert(failed);
}''', encoding="utf-8")
    executable = temp / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        jars += [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
        if not jars:
            raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "MixedPrimarySortOracle.java"
        groups = [j_cases[index:index + 10] for index in range(0, len(j_cases), 10)]
        methods = "\n".join("  static void group%d() {\n%s\n  }" % (index, "\n".join(group)) for index, group in enumerate(groups))
        calls = "\n".join("    group%d();" % index for index in range(len(groups)))
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.*;
class MixedPrimarySortOracle {
  static void run(primary[] refs) {
    RCollection<primary> values = new RCollection<>(refs.clone());
    boolean failed = false; try { values.z8_sort(); } catch (RuntimeException error) { failed = true; }
    System.out.print(failed ? "E:" : "O:");
    for (primary value : values) {
      if (value == null) System.out.print("n,");
      else for (int i = 0; i < refs.length; ++i) if (refs[i] == value) { System.out.print(i + ","); break; }
    }
    System.out.print(":"); for (primary value : refs) if (value instanceof datespan) System.out.print(((datespan)value).milliseconds() + ",");
    System.out.println();
  }
''' + methods + '''
  public static void main(String[] args) throws Exception {
    org.zenframework.z8.server.config.ServerConfig.load(args[0]);
''' + calls + "\n  }\n}\n", encoding="utf-8")
        config = temp / "oracle.properties"
        config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "MixedPrimarySortOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
        assert len(actual) == len(expected) == len(cases)
        for index, (left, right) in enumerate(zip(actual, expected)):
            assert left == right, (index, cases[index], left, right)
print("Mixed primary-array sorting and comparator effects verified")
