"""Compile the example with the current original Z8 compiler, in a temporary project.

Usage: python tests/z8_compiler_oracle.py <original-z8-root> [eclipse-cache-dir]
Requires JDK and the original project's cached 3.4-cert Eclipse dependencies.
Neither the original sources nor their build outputs are modified.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/z8_compiler_oracle.py <original-z8-root> [eclipse-cache-dir]")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
compiler = original / "org.zenframework.z8.compiler" / "src" / "main" / "java"
language = original / "org.zenframework.z8.lang" / "src" / "bl"
cache = Path(sys.argv[2]) if len(sys.argv) == 3 else Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "org.zenframework.z8.dependencies.eclipse"
jars = [p for p in cache.rglob("*.jar") if "3.4-cert" in p.parts and not p.name.endswith("-sources.jar")]
if not compiler.is_dir() or not language.is_dir() or len(jars) < 3:
    raise SystemExit("Original compiler, language sources or cached Eclipse dependencies not found")

with tempfile.TemporaryDirectory() as temporary:
    temp = Path(temporary)
    classes = temp / "compiler"
    classes.mkdir()
    classpath = os.pathsep.join(map(str, jars))
    java_files = [str(p) for p in compiler.rglob("*.java")]
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                    "-cp", classpath, "-d", str(classes)] + java_files,
                   cwd=temp, check=True)
    lang = temp / "lang"
    (lang / "src").mkdir(parents=True)
    shutil.copytree(language, lang / "src" / "bl")
    (lang / "z8.project").write_text("sourcePaths=src/bl\n", encoding="utf-8")
    project = temp / "project"
    (project / "src").mkdir(parents=True)
    shutil.copytree(root / "examples" / "project", project / "src" / "bl")
    shutil.copy2(root / "examples" / "math.bl", project / "src" / "bl" / "Math.bl")
    command = ["java", "-cp", str(classes) + os.pathsep + classpath,
               "org.zenframework.z8.compiler.cmd.Main", str(project),
               "-sources:src/bl", "-requires:" + str(lang), "-output:out"]
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Original Z8 compiler rejected the example:\n" + result.stdout + result.stderr)
    generated = list((project / "out").rglob("*.java"))
    if not generated:
        raise SystemExit("Original compiler did not produce Java files")
    if os.environ.get("Z8_ORACLE_INSPECT"):
        for file in generated:
            if file.name == "Main.java":
                print(file.read_text(encoding="utf-8"))
    if os.environ.get("Z8_ORACLE_RUN"):
        runtime_jars = list((original / "org.zenframework.z8.server" / "target" / "libs").glob("*.jar"))
        lang_classes = original / "org.zenframework.z8.lang" / "target" / "classes" / "main"
        if not runtime_jars or not lang_classes.is_dir():
            raise SystemExit("Prebuilt original runtime and language classes are required")
        generated_classes = temp / "generated-classes"
        generated_classes.mkdir()
        config = temp / "server.properties"
        config.write_text("application.language=en\n", encoding="utf-8")
        runner = temp / "ProjectRunner.java"
        runner.write_text('''public class ProjectRunner {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        System.out.println("RESULT:" + demo.Main.z8_run().get());
    }
}''', encoding="utf-8")
        logging_cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "commons-logging" / "commons-logging"
        logging = [p for p in logging_cache.rglob("*.jar") if not p.name.endswith("-sources.jar")]
        run_classpath = os.pathsep.join([str(runtime_jars[0]), str(lang_classes), classpath] + [str(p) for p in logging])
        generated_sources = [str(p) for p in (project / "out" / "demo").rglob("*.java")]
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", run_classpath, "-d", str(generated_classes)] + generated_sources + [str(runner)], cwd=temp, check=True)
        output = subprocess.check_output(["java", "-cp", str(generated_classes) + os.pathsep + run_classpath, "ProjectRunner", str(config)], cwd=temp, text=True, encoding="utf-8")
        original_results = [line[7:] for line in output.splitlines() if line.startswith("RESULT:")]
        z8d = root / ("z8d.exe" if os.name == "nt" else "z8d")
        d_source = subprocess.check_output([str(z8d), "project", str(project / "src" / "bl")], cwd=temp, text=True, encoding="utf-8")
        d_runner = temp / "compare.d"
        d_runner.write_text(d_source + '''
import std.stdio : writeln;
void main() {
    writeln(Z8p_64656D6F2E4D61696E.m_run());
}
''', encoding="utf-8")
        d_binary = temp / ("compare.exe" if os.name == "nt" else "compare")
        subprocess.run(["dmd", str(d_runner), "-of=" + str(d_binary)], cwd=temp, check=True)
        d_results = subprocess.check_output([str(d_binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
        if original_results != d_results:
            raise SystemExit(f"Original Z8: {original_results!r}; z8-d: {d_results!r}")
        print(f"Matched {len(d_results)} program results against the original compiler and prebuilt runtime")
    print(f"Original Z8 compiler accepted the project and generated {len(generated)} Java files")
