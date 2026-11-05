"""Check record attribute acceptance and generated registration against Z8.

Usage: python tests/record_attributes_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/record_attributes_oracle.py <original-z8-root>")
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
    base = project / "src/bl/RecordBase.bl"
    base.write_text("""
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
public class RecordBase extends Table {
    public StringField title;
    records { [title "Base"] Base = '00000000-0000-0000-0000-000000000004'; }
}
""", encoding="utf-8")
    probe = project / "src/bl/RecordProbe.bl"
    imports = "import org.zenframework.z8.base.table.value.IntField;\n"
    good = """
public class RecordProbe extends RecordBase {
    public IntField count;
    public string label = "Prefix";
    public string makeTitle() { return label + "!"; }
    records {
        [title "42 value"] [count -7] First = '00000000-0000-0000-0000-000000000001';
        [title makeTitle()] public Second = '00000000-0000-0000-0000-000000000002';
        Bare = '00000000-0000-0000-0000-000000000003';
    }
}
"""
    command = ["java", "-cp", classpath, "org.zenframework.z8.compiler.cmd.Main", str(project),
               "-projectName:verify", "-sources:src/bl", "-output:" + str(output)]
    probe.write_text(imports + good, encoding="utf-8")
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Original compiler rejected valid records:\n" + result.stdout + result.stderr)
    java = (output / "RecordProbe.java").read_text(encoding="utf-8")
    for marker in ("super.initStaticRecords()", "title.get()", "count.get()", "z8_makeTitle()", "internalAddRecord"):
        if marker not in java:
            raise SystemExit("Original record generation missing " + marker)
    for attributes in ('[missing "x"]', '[title]', '[title 123]', '[count "x"]', '[title "x"] [title "y"]'):
        code = ("public class RecordProbe extends RecordBase { public IntField count; records { " + attributes +
                " A = '00000000-0000-0000-0000-000000000005'; } }")
        probe.write_text(imports + code, encoding="utf-8")
        result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            raise SystemExit("Original compiler accepted invalid record attribute " + attributes)
print("Record attribute acceptance and registration checked against original compiler")
