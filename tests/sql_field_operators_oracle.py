"""Verify SQL field operators and named casts with the original BL compiler.

Usage: python tests/sql_field_operators_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/sql_field_operators_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
compiler = original / "org.zenframework.z8.compiler/src/main/java"
language = original / "org.zenframework.z8.lang/src/bl"
cache = Path.home() / ".gradle/caches/modules-2/files-2.1/org.zenframework.z8.dependencies.eclipse"
jars = sorted(p for p in cache.rglob("*.jar") if "3.4-cert" in p.parts and not p.name.endswith("-sources.jar"))
if not compiler.is_dir() or not language.is_dir() or not jars:
    raise SystemExit("Original compiler, language sources or cached Eclipse dependencies not found")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    classes, project, output = temp / "classes", temp / "project", temp / "output"
    classes.mkdir()
    (project / "src").mkdir(parents=True)
    shutil.copytree(language, project / "src/bl")
    classpath = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                    "-cp", classpath, "-d", str(classes), *map(str, compiler.rglob("*.java"))],
                   cwd=temp, check=True, stdout=subprocess.DEVNULL)
    classpath = str(classes) + os.pathsep + classpath
    for name, kind in (("GuidValue", "guid"), ("DateValue", "date"), ("SpanValue", "datespan"),
                       ("FileValue", "file"), ("IntValue", "int"), ("TextValue", "string")):
        (project / f"src/bl/{name}.bl").write_text(
            f'[native "example.{name}"] public class {name} {{ public operator {kind}(); }}', encoding="utf-8")
    (project / "src/bl/Probe.bl").write_text("""
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
public class Probe {
    public static sql_bool guid(GuidField field, guid value) { return field != value; }
    public static sql_bool fields(GuidField left, GuidField right) { return left == right; }
    public static sql_bool rightSqlGuid(guid left, GuidField right) { return left != right; }
    public static sql_int add(IntField field, int value) { return field + value; }
    public static sql_int rightSqlInt(int value, IntField field) { return value + field; }
    public static sql_bool check(IntField field, int value) { return field > value; }
    public static sql_string named(StringField field) { return field.sql_string(); }
    public static bool sameGuid(GuidValue value, guid other) { return value == other; }
    public static bool bothGuids(GuidValue left, GuidValue right) { return left == right; }
    public static bool rightGuid(guid left, GuidValue right) { return left == right; }
    public static bool earlier(DateValue value, date other) { return value < other; }
    public static bool bothDates(DateValue left, DateValue right) { return left <= right; }
    public static datespan difference(DateValue value, date other) { return value - other; }
    public static date plusDate(SpanValue value, date other) { return value + other; }
    public static bool longer(SpanValue value, datespan other) { return value > other; }
    public static bool sameFile(FileValue value, file other) { return value == other; }
    public static int sum(IntValue left, IntValue right) { return left + right; }
    public static int rightInt(int left, IntValue right) { return left + right; }
    public static bool sameText(TextValue left, TextValue right) { return left == right; }
}
""", encoding="utf-8")
    command = ["java", "-cp", classpath, "org.zenframework.z8.compiler.cmd.Main", str(project),
               "-projectName:verify", "-sources:src/bl", "-output:" + str(output)]
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Original compiler rejected SQL field operators:\n" + result.stdout + result.stderr)
    java = (output / "Probe.java").read_text(encoding="utf-8")
    for marker in ("sql_guid()", "sql_int()", "sql_string()", ".guid()", ".date()", ".datespan()", ".file()"):
        if marker not in java:
            raise SystemExit("Original generated code lacks conversion " + marker)
    (project / "src/bl/Ambiguous.bl").write_text(
        '[native "example.Ambiguous"] public class Ambiguous { public operator guid(); public operator sql_guid(); }',
        encoding="utf-8")
    (project / "src/bl/Bad.bl").write_text(
        'public class Bad { public static void f(Ambiguous value, guid id) { if (value == id) return; } }',
        encoding="utf-8")
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0 or "ambiguous" not in (result.stdout + result.stderr).lower():
        raise SystemExit("Original compiler did not diagnose ambiguous conversions:\n" + result.stdout + result.stderr)
print("SQL and primary value conversions checked against original compiler")
