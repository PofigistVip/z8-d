"""Compare typed value-array sorts and partial errors with original Java Z8."""
from pathlib import Path
import os
import random
import shutil
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/ValueArraySort.bl"
rng = random.Random(793)
types = {
    "int": ("long", [None, -(1 << 63) + 1, -2, 0, 1, (1 << 63) - 1]),
    "bool": ("bool", [None, False, True]),
    "decimal": ("Z8Decimal", [None, "-1.5", "0", "2.5", "NaN"]),
    "string": ("wstring", [None, "", "A", "B", "😀"]),
}
cases = []
for name, (_, options) in types.items():
    samples = [[None, options[-1]], [options[-1], None], [None, options[-1], options[1]]]
    samples += [[rng.choice(options) for _ in range(rng.randrange(2, 32))] for _ in range(60)]
    # Large arrays are compared only when integer subtraction cannot overflow.
    stable = [x for x in options if x is not None and (name != "int" or -2 <= x <= 1)]
    samples += [[rng.choice(stable) for _ in range(length)] for length in (32, 33, 64)]
    cases += [(name, sample) for sample in samples]

def make(name, value):
    if value is None:
        return ("null" if name == "string" else "Z8Optional!(%s).init" % types[name][0]), "null"
    if name == "int":
        literal = "long.min + 1" if value == -(1 << 63) + 1 else "long.max" if value == (1 << 63) - 1 else "%dL" % value
        return "z8_optional_wrap(%s)" % literal, "new integer(%dL)" % value
    if name == "bool":
        literal = str(value).lower(); return "z8_optional_wrap(%s)" % literal, "new bool(%s)" % literal
    if name == "decimal":
        return ("z8_optional_wrap(z8_decimal_nan())", "new decimal(Double.NaN)") if value == "NaN" else (
            'z8_optional_wrap(z8_decimal_parse("%s"w))' % value, 'new decimal("%s")' % value)
    return '"%s"w' % value, 'new string("%s")' % value

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("sort.exe" if os.name == "nt" else "sort")
    subprocess.run([str(compiler), "build", str(temp), "ValueArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    d_cases, j_cases = [], []
    for name, sample in cases:
        converted = [make(name, item) for item in sample]
        d_type = types[name][0]
        constructor = "new Z8Array!%s([%s]%s)" % (d_type, ",".join(item[0] for item in converted), "" if name == "string" else ", true")
        d_cases.append("run!(%s)(%s);" % (d_type, constructor))
        j_cases.append("run(new primary[]{%s});" % ",".join(item[1] for item in converted))
    source = temp / "sort.d"
    source.write_text('''import z8.runtime;
import std.stdio : write, writeln;
import std.conv : to;
void run(T)(Z8Array!T values) {
    auto view = z8_primary_array_view(values);
    bool failed; try values.z8_sort(); catch (Exception) failed = true;
    write(failed ? "E:" : "O:");
    foreach (i; 0 .. values.z8_size()) {
        auto value = values.z8_get(i);
        assert(z8_primary_collection_equals(view.z8_get(i), z8_array_box(value)));
        static if (is(T == wstring)) { if (value is null) write("n|"); else write(value.to!string, "|"); }
        else if (!value.present) write("n|");
        else static if (is(T == Z8Decimal)) write(value.value.z8_string().to!string, "|");
        else write(value.value, "|");
    }
    writeln();
}
Z8Primary z8_array_box(T)(T value) { return z8_primary_box(value); }
void main() {
''' + "\n".join(d_cases) + '''
    auto large = new Z8Array!long(); foreach (_; 0 .. 30) large.z8_add(0L);
    large.z8_add(long.min); large.z8_add(long.max);
    bool failed; try large.z8_sort(); catch (Exception) failed = true; assert(failed);
}''', encoding="utf-8")
    executable = temp / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    original = os.environ.get("Z8_ORIGINAL_ROOT")
    if original:
        jars = list((Path(original) / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        jars += [p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar") if not p.name.endswith("-sources.jar")]
        if not jars: raise SystemExit("Original Z8 server jars are unavailable")
        java = temp / "ValueSortOracle.java"
        groups = [j_cases[index:index + 10] for index in range(0, len(j_cases), 10)]
        methods = "\n".join("  static void group%d() {\n%s\n  }" % (index, "\n".join(group)) for index, group in enumerate(groups))
        calls = "\n".join("    group%d();" % index for index in range(len(groups)))
        java.write_text('''import org.zenframework.z8.server.runtime.RCollection;
import org.zenframework.z8.server.types.*;
class ValueSortOracle {
  static void run(primary[] refs) {
    RCollection<primary> values = new RCollection<>(refs.clone());
    boolean failed = false; try { values.z8_sort(); } catch (RuntimeException error) { failed = true; }
    System.out.print(failed ? "E:" : "O:");
    for (primary value : values) System.out.print(value == null ? "n|" : value.toString() + "|");
    System.out.println();
  }
''' + methods + '''
  public static void main(String[] args) throws Exception {
    org.zenframework.z8.server.config.ServerConfig.load(args[0]);
''' + calls + "\n  }\n}\n", encoding="utf-8")
        config = temp / "oracle.properties"
        config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "ValueSortOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
        assert len(actual) == len(expected) == len(cases)
        for index, (left, right) in enumerate(zip(actual, expected)):
            assert left == right, (index, cases[index], left, right)
print("Typed value-array sorting and partial errors verified")
