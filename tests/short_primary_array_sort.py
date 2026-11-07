"""Compare short primary-array sorts, nulls and partial failures against Java Z8."""
from pathlib import Path
import os
import random
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

original = os.environ.get("Z8_ORIGINAL_ROOT")
if not original:
    raise SystemExit("Set Z8_ORIGINAL_ROOT to the original Z8 checkout")
server_jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
if not server_jars:
    raise SystemExit("Original Z8 server jars are unavailable")
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars = server_jars + [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
classpath = os.pathsep.join(map(str, jars))
rng = random.Random(1126)
types = {
    "date": ("Z8Date", lambda v: "z8_date_from_ticks(%d)" % v, lambda v: "new date(%dL)" % v),
    "guid": ("Z8Guid", lambda v: "z8_guid_create(0, %d)" % v, lambda v: "new guid(0L, %dL)" % v),
    "binary": ("Z8Binary", lambda v: 'z8_binary_literal("%d")' % (v + 4), lambda v: "new binary(new byte[]{%d})" % v),
    "file": ("Z8File", lambda v: 'z8_file_from_path("%d"w)' % v, lambda v: 'new file("%d")' % v),
    "geometry": ("Z8Geometry", lambda v: "z8_geometry_none(4326)" if v == 0 else 'z8_geometry_fromHexString("%s"w)' % ("A" if v < 0 else "B"),
                 lambda v: "new geometry()" if v == 0 else 'new geometry("%s")' % ("A" if v < 0 else "B")),
}
d_cases, j_cases, descriptions = [], [], []
for name, (d_type, d_make, j_make) in types.items():
    samples = [[None, 1], [1, None], [None, 1, 2], [1, 2, None], [0, 1, 0], [1, 0, 1]]
    samples += [[rng.choice([None, -1, 0, 1]) for _ in range(rng.randrange(2, 32))] for _ in range(50)]
    for sample in samples:
        d_values = ",".join("null" if value is None else d_make(value) for value in sample)
        j_values = ",".join("null" if value is None else j_make(value) for value in sample)
        d_cases.append("run!(%s)([%s]);" % (d_type, d_values))
        j_cases.append("run(new primary[]{%s});" % j_values)
        descriptions.append((name, sample))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "sort.d"
    source.write_text('''import z8.runtime;
import std.stdio : write, writeln;
void run(T)(T[] refs) {
    auto values = new Z8Array!T(refs.dup); auto view = z8_primary_array_view(values);
    bool failed; try values.z8_sort(); catch (Exception) failed = true;
    write(failed ? "E:" : "O:");
    foreach (i; 0 .. values.z8_size()) {
        auto value = values.z8_get(i);
        if (value is null) write("n,");
        else foreach (index, original; refs) if (value is original) { write(index, ","); break; }
        assert((value is null && view.z8_get(i) is null) || z8_primary_cast!T(view.z8_get(i)) is value);
    }
    writeln();
}
void main() {
''' + "\n".join(d_cases) + "\n}\n", encoding="utf-8")
    executable = temp / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    java = temp / "PrimarySortOracle.java"
    java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.*;
class PrimarySortOracle {
  static void run(primary[] refs) {
    RCollection<primary> values = new RCollection<>(refs.clone());
    boolean failed = false; try { values.z8_sort(); } catch (RuntimeException error) { failed = true; }
    System.out.print(failed ? "E:" : "O:");
    for (primary value : values) {
      if (value == null) System.out.print("n,");
      else for (int i = 0; i < refs.length; ++i) if (refs[i] == value) { System.out.print(i + ","); break; }
    }
    System.out.println();
  }
  public static void main(String[] args) throws Exception {
    org.zenframework.z8.server.config.ServerConfig.load(args[0]);
''' + "\n".join(j_cases) + "\n  }\n}\n", encoding="utf-8")
    config = temp / "oracle.properties"
    config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "PrimarySortOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert len(actual) == len(expected) == len(descriptions)
    for index, (left, right) in enumerate(zip(actual, expected)):
        assert left == right, (index, descriptions[index], left, right)
print("Short primary-array sort comparisons and partial failures match Java")
