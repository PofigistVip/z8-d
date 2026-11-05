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
    (project / "src/bl/Probe.bl").write_text("""
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
public class Probe {
    public static sql_bool guid(GuidField field, guid value) { return field != value; }
    public static sql_bool fields(GuidField left, GuidField right) { return left == right; }
    public static sql_int add(IntField field, int value) { return field + value; }
    public static sql_bool check(IntField field, int value) { return field > value; }
    public static sql_string named(StringField field) { return field.sql_string(); }
}
""", encoding="utf-8")
    command = ["java", "-cp", classpath, "org.zenframework.z8.compiler.cmd.Main", str(project),
               "-projectName:verify", "-sources:src/bl", "-output:" + str(output)]
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Original compiler rejected SQL field operators:\n" + result.stdout + result.stderr)
    java = (output / "Probe.java").read_text(encoding="utf-8")
    for marker in ("sql_guid()", "sql_int()", "sql_string()"):
        if marker not in java:
            raise SystemExit("Original generated code lacks conversion " + marker)
print("SQL field expressions and named conversion accepted by original compiler")
