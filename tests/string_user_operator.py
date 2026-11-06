"""Resolve direct string operators for values with multiple conversion operators."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Mixed.bl").write_text('''
public class Mixed {
    public operator string() { return "text"; }
    public operator int() { return 99; }
    public operator bool() { return false; }
    public operator guid() { return guid.Null; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static int run() {
        Mixed value = new Mixed;
        if ("prefix " + value + " suffix" != "prefix text suffix") return 1;
        if ("text" != value || !("text" == value) || !("z" > value)) return 2;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("string-operators.exe" if os.name == "nt" else "string-operators")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python tests/string_user_operator.py [original-z8-root]")
    if len(sys.argv) == 2:
        original = Path(sys.argv[1]).resolve()
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        eclipse = [p for p in (cache / "org.zenframework.z8.dependencies.eclipse").rglob("*.jar")
                   if "3.4-cert" in p.parts and not p.name.endswith("-sources.jar")]
        compiler_source = original / "org.zenframework.z8.compiler/src/main/java"
        language = original / "org.zenframework.z8.lang/src/bl"
        server_jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        if not compiler_source.is_dir() or not language.is_dir() or not eclipse or not server_jars:
            raise SystemExit("Original compiler, standard library, server JAR or Eclipse dependencies not found")
        compiler_classes = temp / "java-compiler"
        compiler_classes.mkdir()
        eclipse_cp = os.pathsep.join(map(str, eclipse))
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", eclipse_cp,
                        "-d", str(compiler_classes), *map(str, compiler_source.rglob("*.java"))], cwd=temp, check=True)
        lang = temp / "lang"
        (lang / "src").mkdir(parents=True)
        shutil.copytree(language, lang / "src/bl")
        (lang / "z8.project").write_text("sourcePaths=src/bl\n", encoding="utf-8")
        project = temp / "java-project"
        java_source = project / "src/bl/p"
        java_source.mkdir(parents=True)
        for name in ("Mixed", "Probe"):
            shutil.copy2(source / (name + ".bl"), java_source)
        subprocess.run(["java", "-cp", str(compiler_classes) + os.pathsep + eclipse_cp,
                        "org.zenframework.z8.compiler.cmd.Main", str(project), "-sources:src/bl",
                        "-requires:" + str(lang), "-output:out"], cwd=temp, check=True)
        runner = temp / "Runner.java"
        runner.write_text('''
public class Runner {
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        System.out.println(p.Probe.z8_run().get());
    }
}
''', encoding="utf-8")
        dependencies = [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar")
                        if not p.name.endswith("-sources.jar")]
        dependencies += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
        java_cp = os.pathsep.join(map(str, [*server_jars, *dependencies]))
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", java_cp,
                        "-d", str(temp), *map(str, (project / "out").rglob("*.java")), str(runner)], cwd=temp, check=True)
        result = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + java_cp, "Runner"],
                                         cwd=temp, text=True, encoding="utf-8")
        if result.strip() != "0":
            raise SystemExit("Original Java result differs: " + result)
print("String operators select the direct user conversion")
