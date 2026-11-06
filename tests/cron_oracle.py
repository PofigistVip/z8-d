"""Compare native Cron expressions and dates against the original Z8 runtime.

Usage: python tests/cron_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/cron_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang" / "src" / "bl"
jars = sorted((original / "org.zenframework.z8.server" / "target" / "libs").glob("org.zenframework.z8.server-*.jar"))
if not jars:
    raise SystemExit("Original server JAR not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    declaration = Path("org/zenframework/z8/utils/Cron.bl")
    destination = source / declaration
    destination.parent.mkdir(parents=True)
    shutil.copy2(language / declaration, destination)
    (source / "Probe.bl").write_text('''import org.zenframework.z8.utils.Cron;
public class Probe {
    public static bool check(string expression) { return Cron.checkExp(expression); }
    public static date next(date value, string expression) { return Cron.nextDate(value, expression); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "CronOracle.java"
    java.write_text('''import org.zenframework.z8.server.utils.Cron;
import org.zenframework.z8.server.types.date;
class CronOracle {
    public static void main(String[] args) {
        String[] syntax = {"* * * * *", "* * * * * *", "*/5 0 1-31 1,3,5 1-5", "99 * * * *", "*/0 * * * *", "  * * * * *", "* * * * *\\n", "* * * *", "* * * * * * *", "* * * * x"};
        for (int i = 0; i < syntax.length; i++) System.out.println("C:" + i + ":" + Cron.checkExp(syntax[i]));
        String[] schedules = {"* * * * *", "*/5 * * * *", "15 14 1 * *", "0 22 * * 1-5", "23 */2 * * *", "5 4 * * 7", "0 0 1 1 *", "* * * * * *", "*/10 * * * * *", "1-59/2 * * * * *", "0 0 31 2 *", "*/0 * * * *", "bad"};
        for (int i = 0; i < schedules.length; i++) {
            try { System.out.println("N:" + i + ":" + Cron.nextDate(new date(946674000123L), schedules[i]).getTicks()); }
            catch (RuntimeException error) { System.out.println("N:" + i + ":ERROR"); }
        }
        int[][] starts = {{2010, 3, 28, 1, 59, 50, 500}, {2010, 10, 31, 1, 59, 50, 500},
                          {2014, 10, 26, 1, 59, 50, 500}, {2024, 2, 28, 23, 59, 50, 500}};
        String[] edges = {"* * * * *", "* * * * * *", "0 3 * * *", "15 2 * * *"};
        for (int i = 0; i < starts.length; i++) for (int j = 0; j < edges.length; j++) {
            int[] v = starts[i];
            try {
                date start = new date(v[0], v[1], v[2], v[3], v[4], v[5]);
                System.out.println("T:" + i + ":" + j + ":" + Cron.nextDate(new date(start.getTicks() + v[6]), edges[j]).getTicks());
            }
            catch (RuntimeException error) { System.out.println("T:" + i + ":" + j + ":ERROR"); }
        }
    }
}
''', encoding="utf-8")
    current_cron = original / "org.zenframework.z8.server" / "src" / "main" / "java" / "org" / "zenframework" / "z8" / "server" / "utils" / "Cron.java"
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", str(jars[0]), "-d", str(temp), str(current_cron)], cwd=temp, check=True)
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", str(temp) + os.pathsep + str(jars[0]), str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + str(jars[0]), "CronOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
void main() {
    alias Probe = Z8p_50726F6265;
    wstring[] syntax = ["* * * * *"w, "* * * * * *"w, "*/5 0 1-31 1,3,5 1-5"w, "99 * * * *"w, "*/0 * * * *"w, "  * * * * *"w, "* * * * *\\n"w, "* * * *"w, "* * * * * * *"w, "* * * * x"w];
    foreach (i, value; syntax) writeln("C:", i, ":", z8_optional_require(Probe.m_check(value)));
    wstring[] schedules = ["* * * * *"w, "*/5 * * * *"w, "15 14 1 * *"w, "0 22 * * 1-5"w, "23 */2 * * *"w, "5 4 * * 7"w, "0 0 1 1 *"w, "* * * * * *"w, "*/10 * * * * *"w, "1-59/2 * * * * *"w, "0 0 31 2 *"w, "*/0 * * * *"w, "bad"w];
    foreach (i, value; schedules) {
        try { writeln("N:", i, ":", z8_date_ticks(Probe.m_next(z8_date_from_ticks(946674000123L), value))); }
        catch (Exception) { writeln("N:", i, ":ERROR"); }
    }
    int[7][] starts = [[2010, 3, 28, 1, 59, 50, 500], [2010, 10, 31, 1, 59, 50, 500],
                       [2014, 10, 26, 1, 59, 50, 500], [2024, 2, 28, 23, 59, 50, 500]];
    wstring[] edges = ["* * * * *"w, "* * * * * *"w, "0 3 * * *"w, "15 2 * * *"w];
    foreach (i, v; starts) foreach (j, expression; edges) {
        try {
            auto start = z8_date_from_ticks(0);
            z8_date_set(start, v[0], v[1], v[2], v[3], v[4], v[5], v[6]);
            writeln("T:", i, ":", j, ":", z8_date_ticks(Probe.m_next(start, expression)));
        } catch (Exception) { writeln("T:", i, ":", j, ":ERROR"); }
    }
    z8_native_clear_bindings();
    z8_bind_builtin_cron();
    assert(z8_optional_require(Probe.m_check("* * * * *"w)));
}
''', encoding="utf-8")
    executable = temp / ("cron.exe" if os.name == "nt" else "cron")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"Cron differs:\nJava={expected!r}\nD={actual!r}")
print("Cron validation and next dates match Java")
