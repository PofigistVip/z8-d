"""Compare BL comparison grouping against the original Z8 compiler.

Usage: python tests/comparison_grammar_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/comparison_grammar_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
compiler_sources = original / "org.zenframework.z8.compiler/src/main/java"
language = original / "org.zenframework.z8.lang/src/bl"
cache = Path.home() / ".gradle/caches/modules-2/files-2.1/org.zenframework.z8.dependencies.eclipse"
jars = [p for p in cache.rglob("*.jar") if "3.4-cert" in p.parts and not p.name.endswith("-sources.jar")]
if not compiler_sources.is_dir() or not language.is_dir() or len(jars) < 3:
    raise SystemExit("Original compiler, BL library or cached Eclipse dependencies not found")

cases = (
    ("true == false == true", False),
    ("true != false == true", False),
    ("1 < 2 < 3", False),
    ("1 < 2 >= 3", False),
    ("(true == false) == true", True),
    ("true == (false == true)", True),
    ("(1 < 2) == (3 < 4)", True),
    ("1 < 2 == 3 < 4", True),
    ("1 < 2 && 3 < 4", True),
)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    classes = temp / "classes"; classes.mkdir()
    classpath = os.pathsep.join(map(str, jars))
    sources = list(compiler_sources.rglob("*.java"))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath,
                    "-d", str(classes), *map(str, sources)], cwd=temp, check=True, capture_output=True)
    project = temp / "project"; (project / "src").mkdir(parents=True)
    shutil.copytree(language, project / "src/bl")
    output = temp / "output"; output.mkdir()
    java_command = ["java", "-cp", os.pathsep.join([str(classes), classpath]),
                    "org.zenframework.z8.compiler.cmd.Main", str(project), "-projectName:verify",
                    "-sources:src/bl", "-output:" + str(output)]
    probe = project / "src/bl/SpecProbe.bl"
    compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
    for expression, expected in cases:
        probe.write_text("public class SpecProbe { public bool f() { return " + expression + "; } }", encoding="utf-8")
        java = subprocess.run(java_command, cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
        d = subprocess.run([str(compiler), "compile", str(probe)], cwd=temp, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        java_accepts = java.returncode == 0 and "Error(s) 0" in java.stdout
        d_accepts = d.returncode == 0
        if java_accepts != expected or d_accepts != expected:
            raise AssertionError((expression, expected, java_accepts, d_accepts, java.stdout, java.stderr, d.stderr))
print(f"{len(cases)} comparison grammar probes matched original Z8")
