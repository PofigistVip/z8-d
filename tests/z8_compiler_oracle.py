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
    file_io_zip = temp / "file-io-archive.zip"
    file_io_extracted = temp / "file-io-extracted"
    file_io_extracted_child = file_io_extracted / "nested" / "unicode.txt"
    (project / "src" / "bl" / "demo" / "cases" / "FileIO.bl").write_text('''import org.zenframework.z8.lang.encoding;
    public class FileIO {
        public static int run() {
            date timeOnly = '23:59:59';
            if (timeOnly.ticks() < 1600000000000 || date.now().ticks() - timeOnly.ticks() > 600000) return 17;
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
            binary contents = child;
            child.append("!");
            if (contents.length() != 18 || string.fromBinary(contents) != "Привет 😀!") return 11;
            try { int remaining = contents.length(); return 19; } catch (exception expectedClosed) {}
            if (folder.listFiles().size() != 1 || child.parent().parent() != folder) return 8;
            encoding charset = encoding.Windows1251;
            if (charset != encoding.Windows1251 || charset == encoding.UTF8) return 14;
            child.write("Привет", charset);
            child.append("!", charset);
            if (child.size != 7 || child.read(charset) != "Привет!") return 15;
            binary cyrillic = '207, 240, 232, 226, 229, 242';
            if (string.fromBinary(cyrillic, charset) != "Привет") return 16;
            child.write("Привет 😀");
            file archive = __ZIP__;
            file destination = __EXTRACTED__;
            file extracted = __EXTRACTED_CHILD__;
            if (archive.zip(folder) != archive || !archive.exists()) return 9;
            if (archive.unzip(destination) != archive || extracted.read() != "Привет 😀") return 10;
            file temporary = file.createTempFile("z8-test-", "txt");
            if (temporary.exists() || !temporary.fileName().startsWith("z8-test-") || temporary.extension() != "txt") return 12;
            temporary.write("temp");
            if (temporary.read() != "temp") return 13;
            temporary.delete();
            archive.delete();
            destination.delete(true);
            folder.delete(true);
            return folder.exists() ? 7 : 223;
        }
    }'''.replace("__FILE__", json.dumps(file_io_path.as_posix()))
       .replace("__DIR__", json.dumps(file_io_dir.as_posix()))
       .replace("__CHILD__", json.dumps(file_io_child.as_posix()))
       .replace("__ZIP__", json.dumps(file_io_zip.as_posix()))
       .replace("__EXTRACTED__", json.dumps(file_io_extracted.as_posix()))
       .replace("__EXTRACTED_CHILD__", json.dumps(file_io_extracted_child.as_posix())), encoding="utf-8")
    command = ["java", "-cp", str(classes) + os.pathsep + classpath,
               "org.zenframework.z8.compiler.cmd.Main", str(project),
               "-sources:src/bl", "-requires:" + str(lang), "-output:out"]
    result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Original Z8 compiler rejected the example:\n" + result.stdout + result.stderr)
    generated = list((project / "out").rglob("*.java"))
    if not generated:
        raise SystemExit("Original compiler did not produce Java files")
    # Plain record declarations compile in BL, although the original Java
    # backend expects a table superclass for initStaticRecords().
    record_project = temp / "record-project"
    record_source = record_project / "src" / "bl"
    record_source.mkdir(parents=True)
    for path in (root / "examples" / "records").glob("*.bl"):
        shutil.copy2(path, record_source / path.name)
    record_command = ["java", "-cp", str(classes) + os.pathsep + classpath,
                      "org.zenframework.z8.compiler.cmd.Main", str(record_project),
                      "-sources:src/bl", "-requires:" + str(lang), "-output:out"]
    record_result = subprocess.run(record_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if record_result.returncode:
        raise SystemExit("Original Z8 rejected record fixtures:\n" + record_result.stdout + record_result.stderr)
    record_java = (record_project / "out" / "RecordSet.java").read_text(encoding="utf-8")
    if "initStaticRecords()" not in record_java or " First = " not in record_java:
        raise SystemExit("Original Z8 did not generate the expected record declarations")
    default_access = record_source / "DefaultRecord.bl"
    default_access.write_text('''public class DefaultRecord {
        public static guid get() { return RecordSet.Default; }
    }''', encoding="utf-8")
    record_result = subprocess.run(record_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if record_result.returncode:
        raise SystemExit("Original Z8 rejected default-access record:\n" + record_result.stdout)
    inaccessible = record_source / "InaccessibleRecord.bl"
    inaccessible.write_text('''public class InaccessibleRecord {
        public static guid get() { return RecordSet.Hidden; }
    }''', encoding="utf-8")
    record_result = subprocess.run(record_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if record_result.returncode == 0 or "not visible" not in record_result.stdout:
        raise SystemExit("Original Z8 did not reject a non-public record access:\n" + record_result.stdout)
    inaccessible.unlink()
    (record_source / "DuplicateRecord.bl").write_text('''public class DuplicateRecord extends RecordSet {
        records { Other = '00000000-0000-0000-0000-000000000001'; }
    }''', encoding="utf-8")
    record_result = subprocess.run(record_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if record_result.returncode == 0 or "id conflicts" not in record_result.stdout:
        raise SystemExit("Original Z8 did not reject a duplicate inherited record GUID:\n" + record_result.stdout)
    print("Original Z8 verified GUID records, visibility, and inherited duplicate checks")
    # Check name validation and conflicts against the original compiler.
    name_cases = [
        (True, {"NameA": '[name "Имя 1.$"] public class NameA {}'}),
        (True, {"NameA": '[name true] public class NameA {}'}),
        (True, {"NameA": '[title "label"] [native "example.NativeEnum"] public enum NameA { Value }'}),
        (False, {"NameA": '[name "1abc"] public class NameA {}'}),
        (False, {"NameA": '[name "$resource$"] public class NameA {}'}),
        (False, {"NameA": '[name "same"] public class NameA {}',
                 "NameB": '[name "same"] public class NameB {}'}),
        (False, {"NameA": 'public class NameA { [name "same"] NameA first; [name "same"] NameA second; }'}),
        (True, {"NameA": 'public class NameA { [name "same"] void first() {} [name "same"] void second() {} }'}),
        (False, {"NameA": 'public class NameA { [name "same"] NameA field; [name "same"] void method() {} }'}),
        (False, {"NameA": 'public class NameA { [tag value] void method(int value) {} }'}),
        (True, {"NameA": 'public class NameA { int value; [tag value] static void method() {} }'}),
        (False, {"NameA": 'public class NameA { static int f() { return (int)null; } }'}),
        (True, {"NameA": 'public class NameA { static int f() { return (int)(null); } }'}),
        (False, {"NameA": 'public class NameA { static bool f(bool value) { return (bool)!value; } }'}),
        (True, {"NameA": 'public class NameA { static bool f(bool value) { return (bool)(!value); } }'}),
        (False, {"NameA": 'public class NameA { [name "same"] NameA first; }',
                 "NameB": 'public class NameB extends NameA { [name "same"] NameA second; }'}),
        (True, {"NameA": '[name ""] public class NameA {}',
                "NameB": '[name] public class NameB {}'}),
        (False, {"NameA": '[name ""] public class NameA {}',
                 "NameB": '[name ""] public class NameB {}'}),
        (False, {"NameA": 'public class NameA { [name ""] NameA first; [name] NameA second; }'}),
        (False, {"NameA": '[name] public class NameA {}',
                 "NameB": '[name ""] public class NameB {}'}),
    ]
    for case_index, (accepted, files) in enumerate(name_cases):
        names_project = temp / ("name-attribute-project-" + str(case_index))
        names_source = names_project / "src" / "bl"
        names_source.mkdir(parents=True)
        names_command = ["java", "-cp", str(classes) + os.pathsep + classpath,
                         "org.zenframework.z8.compiler.cmd.Main", str(names_project),
                         "-sources:src/bl", "-requires:" + str(lang), "-output:out"]
        for name, content in files.items():
            (names_source / (name + ".bl")).write_text(content, encoding="utf-8")
        checked = subprocess.run(names_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
        if (checked.returncode == 0) != accepted:
            raise SystemExit(f"Original Z8 name attribute result differed for {files}:\n{checked.stdout}{checked.stderr}")
    print("Original Z8 verified name attribute values and conflicts")
    # Binary operators on reference types pass BL but the Java backend emits
    # calls on CLASS wrappers rather than their objects, which javac rejects.
    operator_project = temp / "binary-operator-project"
    operator_source = operator_project / "src" / "bl"
    operator_source.mkdir(parents=True)
    shutil.copy2(root / "examples" / "operators" / "BinaryOperators.bl", operator_source)
    shutil.copy2(root / "examples" / "operators" / "BinaryConversionFallback.bl", operator_source)
    for name in ("OperatorRoot", "OperatorMiddle", "OperatorLeaf", "OperatorDistance", "CompoundObject", "CompoundAccumulator", "CompoundObjectHolder", "CompoundObjectCases", "CompoundMember", "ProbeEnum", "ProbeOther", "ProbeA", "ProbeB", "EnumInstanceOf"):
        shutil.copy2(root / "examples" / "operators" / (name + ".bl"), operator_source)
    operator_command = ["java", "-cp", str(classes) + os.pathsep + classpath,
                        "org.zenframework.z8.compiler.cmd.Main", str(operator_project),
                        "-sources:src/bl", "-requires:" + str(lang), "-output:out"]
    operator_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if operator_result.returncode:
        raise SystemExit("Original Z8 rejected binary operator fixture:\n" + operator_result.stdout + operator_result.stderr)
    operator_java = (operator_project / "out" / "BinaryOperators.java").read_text(encoding="utf-8")
    if "value.operatorAdd(" not in operator_java:
        raise SystemExit("Original Java backend no longer exhibits the expected reference operator call")
    enum_java = (operator_project / "out" / "EnumInstanceOf.java").read_text(encoding="utf-8")
    if "instanceof ProbeEnum.CLASS" not in enum_java:
        raise SystemExit("Original Java backend no longer emits the expected enum CLASS reference")
    ambiguous_operator = operator_source / "AmbiguousConversion.bl"
    ambiguous_operator.write_text('''public class AmbiguousConversion {
        public operator int() { return 1; }
        public operator decimal() { return 1.0; }
        public static int run() { AmbiguousConversion value; return value + 1; }
    }''', encoding="utf-8")
    ambiguous_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if ambiguous_result.returncode == 0 or "ambiguous" not in ambiguous_result.stdout:
        raise SystemExit("Original Z8 did not reject ambiguous binary conversions:\n" + ambiguous_result.stdout)
    ambiguous_operator.unlink()
    tie = operator_source / "AssignmentTie.bl"
    tie.write_text('''public class AssignmentTie {
        public void operator = (AssignmentTie value) {}
        public static void run() { AssignmentTie left; AssignmentTie right; left = right; }
    }''', encoding="utf-8")
    tie_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if tie_result.returncode == 0 or "ambiguous" not in tie_result.stdout:
        raise SystemExit("Original Z8 did not reject an equally ranked assignment:\n" + tie_result.stdout)
    tie.unlink()
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "NestedBase.bl", operator_source)
    static_nested = operator_source / "StaticNestedInit.bl"
    static_nested.write_text('''public class StaticNestedInit {
        public static int run() {
            NestedBase value = class { int number = 100; public int value() { return number; } };
            return value.value();
        }
    }''', encoding="utf-8")
    static_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if static_result.returncode == 0 or "Cannot make a static reference" not in static_result.stdout:
        raise SystemExit("Original Z8 did not reject an initialized field in a static local specialization:\n" + static_result.stdout)
    print("Original Z8 accepted binary operators and rejected ambiguous conversions; direct execution is checked in D")
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
        demo.cases.StaticOverloadChild.CLASS<?> metadata = new demo.cases.StaticOverloadChild.CLASS<>(null);
        if (!"1709199045000L".equals(metadata.getAttribute("dateConstant")) ||
            !"-2134967296L".equals(metadata.getAttribute("spanConstant")) ||
            !"/* 00112233-4455-6677-8899-aabbccddeeff */4822678189205111L, -8603657889541918977L".equals(metadata.getAttribute("guidConstant")) ||
            !"new byte[] {0, -1, -128}".equals(metadata.getAttribute("binaryConstant")) ||
            !"2".equals(metadata.getAttribute("typeCount")) ||
            !"статическое значение".equals(metadata.getAttribute("typeText")) ||
            !"false".equals(metadata.getAttribute("typeFlag")) ||
            !"DfixtureChild".equals(metadata.getAttribute("name")) ||
            !"base".equals(metadata.getAttribute("baseTag")) ||
            !"новое 😀".equals(metadata.getAttribute("sharedTag")) ||
            !"".equals(metadata.getAttribute("flag")) || !"false".equals(metadata.getAttribute("request")) ||
            !"true".equals(metadata.getAttribute("boolTag")) || !"16L".equals(metadata.getAttribute("count")) ||
            !"-16L".equals(metadata.getAttribute("negative")) ||
            !"1.2300".equals(metadata.getAttribute("price")) || !"1E-7".equals(metadata.getAttribute("tiny")) ||
            !"0.00011462".equals(metadata.getAttribute("smallExponent")) ||
            !"1.23001447".equals(metadata.getAttribute("large")) || !"0.00".equals(metadata.getAttribute("zero")) ||
            metadata.getAttribute("absent") != null)
            throw new AssertionError("type attribute metadata differs: " + metadata.getAttributes());
        if (metadata.get().annotated != metadata.get().replacement ||
            !"от родителя".equals(metadata.get().annotated.getAttribute("fieldTag")) ||
            !"специализация".equals(metadata.get().specialized.getAttribute("fieldTag")) ||
            !"существующее".equals(metadata.get().annotated.getAttribute("initTag")) ||
            !"field.impl".equals(metadata.get().annotated.getAttribute("native")) ||
            !"field.primary".equals(metadata.get().annotated.getAttribute("primary")) ||
            !"исходное".equals(metadata.get().annotated.getAttribute("textValue")) ||
            !"исходное".equals(metadata.get().annotated.getAttribute("methodValue")) ||
            !"1".equals(metadata.get().annotated.getAttribute("numericValue")) ||
            !"false".equals(metadata.get().annotated.getAttribute("booleanValue")) ||
            !"12.34".equals(metadata.get().annotated.getAttribute("decimalValue")) ||
            !"00112233-4455-6677-8899-AABBCCDDEEFF".equals(metadata.get().annotated.getAttribute("guidValue")) ||
            !"42".equals(metadata.get().annotated.getAttribute("primaryValue")) ||
            !"2 03:04:05".equals(metadata.get().annotated.getAttribute("spanValue")) ||
            !"2024-02-29T12:30:45+03:00".equals(metadata.get().annotated.getAttribute("dateValue")) ||
            !"0101000020E6100000000000000000F83F00000000000002C0".equals(metadata.get().annotated.getAttribute("geometryValue")) ||
            !"report.bin".equals(metadata.get().annotated.getAttribute("binaryValue")) ||
            !"org.zenframework.z8.server.types.exception: ошибка".equals(metadata.get().annotated.getAttribute("errorValue")) ||
            !"org.zenframework.z8.server.types.exception".equals(metadata.get().annotated.getAttribute("emptyException")) ||
            !"org.zenframework.z8.server.types.exception: ".equals(metadata.get().annotated.getAttribute("emptyMessage")) ||
            !"источник".equals(metadata.get().annotated.getAttribute("copied")) ||
            demo.cases.AttributeSource.calls.get() != 0 ||
            !"false".equals(metadata.get().jobTarget.getAttribute("request")) ||
            !"исходное".equals(metadata.get().jobTarget.getAttribute("job")) ||
            metadata.get().attributeCalls.get() != 1 ||
            !"исходное значение".equals(metadata.get().annotated.getAttribute("joinedValue")) ||
            !"Second Field".equals(metadata.get().annotated.getAttribute("name")) ||
            !"false".equals(metadata.get().annotated.getAttribute("enabled")) ||
            !"-7L".equals(metadata.get().annotated.getAttribute("delta")) ||
            !"-12.340".equals(metadata.get().annotated.getAttribute("decimalDelta")) ||
            !"7L".equals(metadata.get().annotated.getAttribute("count")) ||
            !"*/15 0 1-31 1,3,5 1-5".equals(metadata.get().annotated.getAttribute("job")) ||
            !"true".equals(metadata.get().annotated.getAttribute("selected")) ||
            !"вложенное".equals(metadata.get().annotated.get().annotated.getAttribute("chainTag")) ||
            !"специализация поля".equals(metadata.get().ownSpecial.getAttribute("specialTag")))
            throw new AssertionError("field attribute metadata differs");
        System.out.println("FILEATTR:" + metadata.get().annotated.getAttribute("fileValue"));
        try {
            new demo.cases.AttributeNull.CLASS<>(null).get();
            throw new AssertionError("null string attribute accepted");
        } catch (NullPointerException expectedNullAttribute) { }
        try {
            new demo.cases.AttributeNullNumber.CLASS<>(null).get();
            throw new AssertionError("null numeric attribute accepted");
        } catch (NullPointerException expectedNullNumericAttribute) { }
        try {
            new demo.cases.AttributeMissingReference.CLASS<>(null).get();
            throw new AssertionError("missing source attribute accepted");
        } catch (NullPointerException expectedMissingAttribute) { }
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
        System.out.println("RESULT:" + demo.cases.RefInitDerived.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BodyInitCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ChainOwner.z8_run().get());
        System.out.println("RESULT:" + demo.cases.RemoteMemberDerived.z8_run().get());
        System.out.println("RESULT:" + demo.cases.MemberLeaf.z8_run().get());
        System.out.println("RESULT:" + demo.cases.MemberOwn.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NestedLocalCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NestedOwner.z8_run().get());
        System.out.println("RESULT:" + demo.cases.AssignmentRanking.z8_run().get());
        System.out.println("RESULT:" + demo.cases.AssignmentValue.z8_run().get());
        System.out.println("RESULT:" + demo.cases.SubtypeConversion.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ConversionDerived.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ObjectConversion.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastBinaryInt.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastBinaryBool.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastBinaryString.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastUnaryInt.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastUnaryDecimal.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CastOperators.z8_run().get());
        System.out.println("RESULT:" + demo.cases.UnaryPlus.z8_run().get());
        System.out.println("RESULT:" + demo.cases.UnaryChild.z8_run().get());
        System.out.println("RESULT:" + demo.cases.UnaryComplement.z8_run().get());
        System.out.println("RESULT:" + demo.cases.UnaryOperators.z8_run().get());
        System.out.println("RESULT:" + demo.cases.MixedOverloads.z8_run().get());
        System.out.println("RESULT:" + demo.cases.StaticOverloadChild.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DecimalMaps.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BooleanMaps.z8_run().get());
        System.out.println("RESULT:" + demo.cases.GuidMaps.z8_run().get());
        System.out.println("RESULT:" + demo.cases.PrimitiveMapValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.IntegerMaps.z8_run().get());
        System.out.println("RESULT:" + demo.cases.QualifiedNames.z8_run().get());
        System.out.println("RESULT:" + demo.cases.MapInitializers.z8_run().get());
        System.out.println("RESULT:" + demo.cases.CompoundCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FinalDeclarations.z8_run().get());
        System.out.println("RESULT:" + demo.cases.AutoCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.PrimaryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.GuidValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BinaryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DatespanValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.DateValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.BasicArrays.z8_run().get());
        System.out.println("RESULT:" + demo.cases.GeometryValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FileValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FileIO.z8_run().get());
        System.out.println("RESULT:" + demo.cases.StringExtras.z8_run().get());
        System.out.println("RESULT:" + demo.cases.MathExtras.z8_run().get());
        System.out.println("RESULT:" + demo.cases.NumericConstants.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ExceptionValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.EnumFields.z8_run().get());
        System.out.println("RESULT:" + demo.cases.ArrayMatrices.z8_run().get());
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
    auto metadata = z8_new!Z8p_64656D6F2E63617365732E5374617469634F7665726C6F61644368696C64();
    assert(metadata.z8_get_attribute("dateConstant"w) == "1709199045000L"w);
    assert(metadata.z8_get_attribute("spanConstant"w) == "-2134967296L"w);
    assert(metadata.z8_get_attribute("guidConstant"w) == "/* 00112233-4455-6677-8899-aabbccddeeff */4822678189205111L, -8603657889541918977L"w);
    assert(metadata.z8_get_attribute("binaryConstant"w) == "new byte[] {0, -1, -128}"w);
    assert(metadata.z8_get_attribute("typeCount"w) == "2"w);
    assert(metadata.z8_get_attribute("typeText"w) == "статическое значение"w);
    assert(metadata.z8_get_attribute("typeFlag"w) == "false"w);
    assert(metadata.z8_get_attribute("name"w) == "DfixtureChild"w);
    assert(metadata.z8_get_attribute("baseTag"w) == "base"w);
    assert(metadata.z8_get_attribute("sharedTag"w) == "новое 😀"w);
    assert(metadata.z8_get_attribute("flag"w) == ""w);
    assert(metadata.z8_get_attribute("request"w) == "false"w);
    assert(metadata.z8_get_attribute("boolTag"w) == "true"w);
    assert(metadata.z8_get_attribute("count"w) == "16L"w);
    assert(metadata.z8_get_attribute("negative"w) == "-16L"w);
    assert(metadata.z8_get_attribute("price"w) == "1.2300"w);
    assert(metadata.z8_get_attribute("tiny"w) == "1E-7"w);
    assert(metadata.z8_get_attribute("smallExponent"w) == "0.00011462"w);
    assert(metadata.z8_get_attribute("large"w) == "1.23001447"w);
    assert(metadata.z8_get_attribute("zero"w) == "0.00"w);
    assert(metadata.z8_get_attribute("absent"w) is null);
    z8_nonnull(metadata);
    assert(metadata.f_annotated is metadata.f_replacement);
    assert(metadata.f_annotated.z8_get_attribute("fieldTag"w) == "от родителя"w);
    assert(metadata.f_specialized.z8_get_attribute("fieldTag"w) == "специализация"w);
    assert(metadata.f_annotated.z8_get_attribute("initTag"w) == "существующее"w);
    assert(metadata.f_annotated.z8_get_attribute("native"w) == "field.impl"w);
    assert(metadata.f_annotated.z8_get_attribute("primary"w) == "field.primary"w);
    assert(metadata.f_annotated.z8_get_attribute("textValue"w) == "исходное"w);
    assert(metadata.f_annotated.z8_get_attribute("methodValue"w) == "исходное"w);
    assert(metadata.f_annotated.z8_get_attribute("numericValue"w) == "1"w);
    assert(metadata.f_annotated.z8_get_attribute("booleanValue"w) == "false"w);
    assert(metadata.f_annotated.z8_get_attribute("decimalValue"w) == "12.34"w);
    assert(metadata.f_annotated.z8_get_attribute("guidValue"w) == "00112233-4455-6677-8899-AABBCCDDEEFF"w);
    assert(metadata.f_annotated.z8_get_attribute("primaryValue"w) == "42"w);
    assert(metadata.f_annotated.z8_get_attribute("spanValue"w) == "2 03:04:05"w);
    assert(metadata.f_annotated.z8_get_attribute("dateValue"w) == "2024-02-29T12:30:45+03:00"w);
    assert(metadata.f_annotated.z8_get_attribute("geometryValue"w) == "0101000020E6100000000000000000F83F00000000000002C0"w);
    assert(metadata.f_annotated.z8_get_attribute("binaryValue"w) == "report.bin"w);
    assert(metadata.f_annotated.z8_get_attribute("errorValue"w) == "org.zenframework.z8.server.types.exception: ошибка"w);
    assert(metadata.f_annotated.z8_get_attribute("emptyException"w) == "org.zenframework.z8.server.types.exception"w);
    assert(metadata.f_annotated.z8_get_attribute("emptyMessage"w) == "org.zenframework.z8.server.types.exception: "w);
    writeln("FILEATTR:", z8_to_utf8(metadata.f_annotated.z8_get_attribute("fileValue"w)));
    assert(metadata.f_annotated.z8_get_attribute("copied"w) == "источник"w);
    assert(z8_optional_require(Z8p_64656D6F2E63617365732E417474726962757465536F75726365.f_calls) == 0);
    assert(metadata.f_jobTarget.z8_get_attribute("request"w) == "false"w);
    assert(metadata.f_jobTarget.z8_get_attribute("job"w) == "исходное"w);
    assert(z8_optional_require(metadata.f_attributeCalls) == 1);
    assert(metadata.f_annotated.z8_get_attribute("joinedValue"w) == "исходное значение"w);
    assert(metadata.f_annotated.z8_get_attribute("name"w) == "Second Field"w);
    assert(metadata.f_annotated.z8_get_attribute("enabled"w) == "false"w);
    assert(metadata.f_annotated.z8_get_attribute("delta"w) == "-7L"w);
    assert(metadata.f_annotated.z8_get_attribute("decimalDelta"w) == "-12.340"w);
    assert(metadata.f_annotated.z8_get_attribute("count"w) == "7L"w);
    assert(metadata.f_annotated.z8_get_attribute("job"w) == "*/15 0 1-31 1,3,5 1-5"w);
    assert(metadata.f_annotated.z8_get_attribute("selected"w) == "true"w);
    assert(z8_nonnull(metadata.f_annotated).f_annotated.z8_get_attribute("chainTag"w) == "вложенное"w);
    assert(metadata.f_ownSpecial.z8_get_attribute("specialTag"w) == "специализация поля"w);
    bool nullAttributeRejected;
    try { z8_nonnull(z8_new!Z8p_64656D6F2E63617365732E4174747269627574654E756C6C()); }
    catch (Exception) { nullAttributeRejected = true; }
    assert(nullAttributeRejected);
    nullAttributeRejected = false;
    try { z8_nonnull(z8_new!Z8p_64656D6F2E63617365732E4174747269627574654E756C6C4E756D626572()); }
    catch (Exception) { nullAttributeRejected = true; }
    assert(nullAttributeRejected);
    nullAttributeRejected = false;
    try { z8_nonnull(z8_new!Z8p_64656D6F2E63617365732E4174747269627574654D697373696E675265666572656E6365()); }
    catch (Exception) { nullAttributeRejected = true; }
    assert(nullAttributeRejected);
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
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E526566496E697444657269766564.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E426F6479496E69744361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E436861696E4F776E6572.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E52656D6F74654D656D62657244657269766564.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4D656D6265724C656166.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4D656D6265724F776E.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E65737465644C6F63616C4361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E65737465644F776E6572.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E41737369676E6D656E7452616E6B696E67.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E41737369676E6D656E7456616C7565.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53756274797065436F6E76657273696F6E.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E436F6E76657273696F6E44657269766564.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4F626A656374436F6E76657273696F6E.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4361737442696E617279496E74.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4361737442696E617279426F6F6C.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4361737442696E617279537472696E67.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E43617374556E617279496E74.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E43617374556E617279446563696D616C.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E436173744F70657261746F7273.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E556E617279506C7573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E556E6172794368696C64.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E556E617279436F6D706C656D656E74.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E556E6172794F70657261746F7273.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4D697865644F7665726C6F616473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5374617469634F7665726C6F61644368696C64.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E446563696D616C4D617073.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E426F6F6C65616E4D617073.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E477569644D617073.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5072696D69746976654D617056616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E496E74656765724D617073.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5175616C69666965644E616D6573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4D6170496E697469616C697A657273.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E436F6D706F756E644361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696E616C4465636C61726174696F6E73.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4175746F4361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E5072696D61727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4775696456616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E42696E61727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E446174657370616E56616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4461746556616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4261736963417272617973.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E47656F6D6574727956616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696C6556616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696C65494F.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E537472696E67457874726173.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4D617468457874726173.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E4E756D65726963436F6E7374616E7473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E457863657074696F6E56616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E456E756D4669656C6473.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E41727261794D61747269636573.m_run()));
}
''', encoding="utf-8")
        d_binary = temp / ("compare.exe" if os.name == "nt" else "compare")
        subprocess.run(["dmd", str(d_runner), *map(str, d_modules), "-I" + str(d_root), *import_args(),
                        str(runtime_lib), "-oq", "-od=" + str(temp), "-of=" + str(d_binary)], cwd=temp, check=True)
        d_lines = subprocess.check_output([str(d_binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
        d_results = [line for line in d_lines if not line.startswith("FILEATTR:")]
        original_file_attributes = [line for line in output.splitlines() if line.startswith("FILEATTR:")]
        d_file_attributes = [line for line in d_lines if line.startswith("FILEATTR:")]
        if original_file_attributes != d_file_attributes or len(d_file_attributes) != 1:
            raise SystemExit(f"File attribute differs: original={original_file_attributes!r}, D={d_file_attributes!r}")
        if original_results[-50:-15] != ["221", "219", "217", "215", "211", "213", "209", "207", "203", "201", "197", "195", "193", "185", "187", "189", "181", "183", "179", "177", "171", "169", "167", "165", "163", "159", "155", "153", "151", "149", "167", "171", "251", "28", "241"]:
            raise SystemExit(f"Language fixtures failed in original Z8: {original_results[-50:-15]}")
        if original_results[-15:] != ["173", "179", "181", "191", "193", "197", "199", "211", "223", "227", "229", "233", "239", "223", "227"]:
            raise SystemExit(f"Basic types and composite values failed in original Z8: {original_results[-15:]}")
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
