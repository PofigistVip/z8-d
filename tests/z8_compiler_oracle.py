"""Compile the example with the current original Z8 compiler, in a temporary project.

Usage: python tests/z8_compiler_oracle.py <original-z8-root> [eclipse-cache-dir]
Requires JDK and the original project's cached 3.4-cert Eclipse dependencies.
Neither the original sources nor their build outputs are modified.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from runtime_support import runtime_library, import_args

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

with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
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
    file_io_path = temp / "file-io-oracle.txt"
    file_io_dir = temp / "file-io-oracle-dir"
    file_io_child = file_io_dir / "nested" / "unicode.txt"
    (project / "src" / "bl" / "demo" / "cases" / "FileIO.bl").write_text('''public class FileIO {
        public static int run() {
            file value = __FILE__;
            if (value.exists() || !value.isEmpty()) return 1;
            value.write("hello");
            value.append(" world");
            if (!value.exists() || value.isFolder() || value.isEmpty()) return 2;
            if (value.read() != "hello world" || value.size != 11 || value.lastModified().ticks() <= 0) return 3;
            binary bytes = '65, 66';
            value.write(bytes);
            if (value.read() != "AB" || value.size != 2 || bytes.length() != 0) return 4;
            value.delete();
            if (value.exists()) return 5;
            file folder = __DIR__;
            file child = __CHILD__;
            child.write("Привет 😀");
            if (!folder.isFolder() || folder.isEmpty() || child.read() != "Привет 😀" || child.size != 17) return 6;
            folder.delete(true);
            return folder.exists() ? 7 : 223;
        }
    }'''.replace("__FILE__", json.dumps(file_io_path.as_posix()))
       .replace("__DIR__", json.dumps(file_io_dir.as_posix()))
       .replace("__CHILD__", json.dumps(file_io_child.as_posix())), encoding="utf-8")
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
            if file.name in ("Main.java", "Arithmetic.java", "EnumCases.java", "Flavor.java", "NullableObjectField.java", "LifecycleBase.java", "LifecycleChild.java", "LifecycleCases.java", "LifecycleOwner.java", "LifecycleReentrant.java", "LifecycleTrigger.java", "FileValues.java"):
                print(file.read_text(encoding="utf-8"))
    if os.environ.get("Z8_ORACLE_RUN"):
        runtime_lib = stack.enter_context(runtime_library())
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
        System.out.println("RESULT:" + demo.cases.Arithmetic.z8_run().get());
        System.out.println("RESULT:" + demo.cases.Text.z8_run().get());
        System.out.println("RESULT:" + demo.cases.Flow.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DecimalArray.z8_run().get());
        System.out.println("RESULT:" + demo.cases.Overloads.z8_run().get());
        System.out.println("RESULT:" + demo.cases.OverloadUser.z8_run().get());
        System.out.println("RESULT:" + demo.cases.Rounding.z8_run().get());
        System.out.println("RESULT:" + demo.cases.PrimitiveParse.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ArrayOperations.z8_run().get());
        System.out.println("RESULT:" + demo.cases.StaticState.z8_run().get());
        System.out.println("RESULT:" + demo.cases.StaticUser.z8_run().get());
        System.out.println("RESULT:" + demo.cases.InstanceOverloads.z8_run().get());
        System.out.println("RESULT:" + demo.cases.IntegerMethods.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ArrayAdvanced.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ObjectArrays.z8_run().get());
        System.out.println("RESULT:" + demo.cases.InheritedOverloads.z8_run().get());
        System.out.println("RESULT:" + demo.cases.StringMap.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ObjectCasts.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullObjects.z8_run().get());
        System.out.println("RESULT:" + demo.cases.InstanceChecks.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ElvisObjects.z8_run().get());
        System.out.println("RESULT:" + demo.cases.EnumCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullablePrimitives.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableStrings.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableIntegers.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableBooleans.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableDecimals.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableArrays.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NullableObjectField.z8_run().get());
        System.out.println("RESULT:" + demo.cases.LifecycleCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.LifecyclePhases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.PrimaryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.GuidValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BinaryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DatespanValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DateValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BasicArrays.z8_run().get());
        System.out.println("RESULT:" + demo.cases.GeometryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FileValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FileIO.z8_run().get());
    }
}''', encoding="utf-8")
        logging_cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "commons-logging" / "commons-logging"
        logging = [p for p in logging_cache.rglob("*.jar") if not p.name.endswith("-sources.jar")]
        commons_cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "org.zenframework.z8.dependencies.commons"
        commons = [p for p in commons_cache.rglob("*.jar") if "3.4-cert" in p.parts and not p.name.endswith("-sources.jar") and
                   (p.name.startswith("commons-lang-2.6-") or p.name.startswith("commons-fileupload-"))]
        if len(commons) < 2:
            raise SystemExit("Cached Commons Lang and FileUpload dependencies are required to compile the original string runtime")
        io_cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1" / "commons-io" / "commons-io" / "2.7"
        io_jars = [p for p in io_cache.rglob("*.jar") if not p.name.endswith("-sources.jar")]
        if not io_jars:
            raise SystemExit("Cached Commons IO 2.7 is required to compile the original binary runtime")
        commons += io_jars
        run_classpath = os.pathsep.join([str(runtime_jars[0]), str(lang_classes), classpath] + [str(p) for p in logging + commons])
        # The cached runtime JAR can predate the checked-out sources. Override its
        # decimal class with the current source before evaluating decimal results.
        decimal_java = original / "org.zenframework.z8.server" / "src" / "main" / "java" / "org" / "zenframework" / "z8" / "server" / "types" / "decimal.java"
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", run_classpath, "-d", str(generated_classes), str(decimal_java)], cwd=temp, check=True)
        bool_java = decimal_java.with_name("bool.java")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(bool_java)], cwd=temp, check=True)
        collection_java = decimal_java.parent.parent / "runtime" / "RCollection.java"
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(collection_java)], cwd=temp, check=True)
        # Override the cached CLASS implementation so lifecycle comparisons use
        # the checked-out source. Other runtime classes still come from the JAR.
        class_java = collection_java.with_name("CLASS.java")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(class_java)], cwd=temp, check=True)
        map_java = collection_java.with_name("RLinkedHashMap.java")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(map_java)], cwd=temp, check=True)
        string_java = decimal_java.with_name("string.java")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(string_java)], cwd=temp, check=True)
        integer_java = decimal_java.with_name("integer.java")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(integer_java), str(decimal_java.with_name("date.java"))], cwd=temp, check=True)
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(decimal_java.with_name("guid.java"))], cwd=temp, check=True)
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(decimal_java.with_name("datespan.java"))], cwd=temp, check=True)
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(decimal_java.with_name("geometry.java"))], cwd=temp, check=True)
        # The cached file class predates current file.java. Its filename helpers
        # delegate to FilenameUtils in current source, while zip is not exercised
        # by this oracle. Adapt only these dependencies in a temporary copy.
        binary_source = decimal_java.with_name("binary.java").read_text(encoding="utf-8")
        binary_shims = {
            "file.getBaseName(name.get())": "org.apache.commons.io.FilenameUtils.getBaseName(name.get())",
            "file.getExtension(name.get())": "org.apache.commons.io.FilenameUtils.getExtension(name.get()).toLowerCase()",
            "return file.createTempFile().zip(fileOrDirectory).binary();": "throw new UnsupportedOperationException();",
            "return file.createTempFile().zip(binaries).binary();": "throw new UnsupportedOperationException();",
        }
        for old, replacement in binary_shims.items():
            if binary_source.count(old) != 1:
                raise SystemExit("Unexpected binary.java source; cannot apply oracle compatibility shim")
            binary_source = binary_source.replace(old, replacement)
        binary_java = temp / "binary.java"
        binary_java.write_text(binary_source, encoding="utf-8")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes), str(binary_java)], cwd=temp, check=True)
        generated_sources = [str(p) for p in (project / "out" / "demo").rglob("*.java")]
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes)] + generated_sources + [str(runner)], cwd=temp, check=True)
        output = subprocess.check_output(["java", "-cp", str(generated_classes) + os.pathsep + run_classpath, "ProjectRunner", str(config)], cwd=temp, text=True, encoding="utf-8")
        original_results = [line[7:] for line in output.splitlines() if line.startswith("RESULT:")]
        z8d = root / ("z8d.exe" if os.name == "nt" else "z8d")
        d_root = temp / "generated-d"
        subprocess.run([str(z8d), "project", str(project / "src" / "bl"), str(d_root)], cwd=temp, check=True)
        d_modules = sorted(d_root.rglob("*.d"))
        imports = []
        for module_file in d_modules:
            match = re.match(r"module ([A-Za-z0-9_.]+);", module_file.read_text(encoding="utf-8"))
            if not match:
                raise SystemExit(f"Missing module declaration: {module_file}")
            imports.append("import " + match.group(1) + ";\n")
        d_runner = temp / "compare.d"
        d_runner.write_text("module compare;\nimport z8.runtime;\n" + "".join(imports) + '''
import std.stdio : writeln;
void main() {
    writeln(z8_optional_require(Z8p_64656D6F2E4D61696E.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E41726974686D65746963.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E54657874.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E466C6F77.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E446563696D616C4172726179.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4F7665726C6F616473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4F7665726C6F616455736572.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E526F756E64696E67.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5072696D69746976655061727365.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E41727261794F7065726174696F6E73.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5374617469635374617465.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53746174696355736572.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E496E7374616E63654F7665726C6F616473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E496E74656765724D6574686F6473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4172726179416476616E636564.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4F626A656374417272617973.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E496E686572697465644F7665726C6F616473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E537472696E674D6170.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4F626A6563744361737473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C4F626A65637473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E496E7374616E6365436865636B73.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E456C7669734F626A65637473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E456E756D4361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C655072696D697469766573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C65537472696E6773.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C65496E746567657273.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C65426F6F6C65616E73.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C65446563696D616C73.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C65417272617973.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756C6C61626C654F626A6563744669656C64.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4C6966656379636C654361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4C6966656379636C65506861736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5072696D61727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4775696456616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E42696E61727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E446174657370616E56616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4461746556616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4261736963417272617973.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E47656F6D6574727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696C6556616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696C65494F.m_run()));
}
''', encoding="utf-8")
        d_binary = temp / ("compare.exe" if os.name == "nt" else "compare")
        subprocess.run(["dmd", str(d_runner), *map(str, d_modules), "-I" + str(d_root), *import_args(),
                        str(runtime_lib), "-oq", "-od=" + str(temp), "-of=" + str(d_binary)], cwd=temp, check=True)
        d_results = subprocess.check_output([str(d_binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
        if original_results[-9:] != ["173", "179", "181", "191", "193", "197", "199", "211", "223"]:
            raise SystemExit(f"Basic types fixture failed in original Z8: {original_results[-9:]}")
        if original_results != d_results:
            raise SystemExit(f"Original Z8: {original_results!r}; z8-d: {d_results!r}")
        print(f"Matched {len(d_results)} program results against the original compiler and runtime (CLASS from current source)")
        native_enums = [path for path in language.rglob("*.bl")
                        if re.search(r"(?m)^\s*public\s+enum\s+\w+", path.read_text(encoding="utf-8"))]
        if not native_enums:
            raise SystemExit("No enum declarations found in the original standard library")
        for enum_file in native_enums:
            native_source = subprocess.check_output([str(z8d), "compile", str(enum_file)], cwd=temp, text=True, encoding="utf-8")
            native_file = temp / "native_enum.d"
            native_file.write_text(native_source, encoding="utf-8")
            subprocess.run(["dmd", "-c", str(native_file), *import_args(), "-of=" + str(temp / "native_enum.obj")], cwd=temp, check=True)
        print(f"Compiled {len(native_enums)} native enum declarations from the original standard library")
    print(f"Original Z8 compiler accepted the project and generated {len(generated)} Java files")
