"""A specialized field can also receive a member assignment operator."""
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
    (source / "Value.bl").write_text('public class Value {}', encoding="utf-8")
    (source / "Holder.bl").write_text('''
public class Holder {
    public int assigned;
    public void operator = (Value value) { assigned = 42; }
    virtual public int kind() { return 1; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public Value source;
    public Holder item = class { public int kind() { return 7; } };
    item = source;
    public Holder other;
    public Holder replaced = class { public int kind() { return 8; } };
    replaced = other;
    public static int run() {
        Probe value;
        if (value.item.kind() != 7) return 1;
        if (value.item.assigned != 42) return 2;
        if (value.replaced.kind() != 1) return 3;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
void main() {
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
    auto value = z8_nonnull(z8_new!Z8p_50726F6265());
    assert(value.f_replaced is value.f_other);
    auto specialized = z8_object_new_instance(value.f_item.z8_class_id());
    assert(specialized.z8_class_id() == value.f_item.z8_class_id());
}
''', encoding="utf-8")
    executable = temp / ("specialized-field.exe" if os.name == "nt" else "specialized-field")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for code in ("public class Duplicate { int number; number = 1; number = 2; }",
                 "public class Duplicate { int number = 1; number = 2; }"):
        (source / "Duplicate.bl").write_text(code, encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(temp / "invalid")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0 or "duplicate field initialization" not in result.stderr:
            raise SystemExit("Expected duplicate member initializer rejection: " + result.stderr)
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python tests/specialized_field_assignment.py [original-z8-root]")
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
        for name in ("Value", "Holder", "Probe"):
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
print("Member assignment after field specialization verified")
