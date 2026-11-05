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
        (True, {"NameA": 'public class NameA extends primary { public void operator = (NameA value) {} }'}),
        (False, {"NameA": 'public class NameA extends primary { public void operator = (NameA value) {} public string toString() { return "test"; } }'}),
        (False, {"NameA": 'public class NameA extends primary {}'}),
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
    for name in ("OperatorRoot", "OperatorMiddle", "OperatorLeaf", "OperatorDistance", "CompoundObject", "CompoundAccumulator", "CompoundObjectHolder", "CompoundObjectCases", "CompoundMember", "ProbeEnum", "ProbeOther", "ProbeA", "ProbeB", "EnumInstanceOf", "PriorityValue", "PriorityCases"):
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
    priority_java = (operator_project / "out" / "PriorityCases.java").read_text(encoding="utf-8")
    if ".operatorPriority()" not in priority_java:
        raise SystemExit("Original Java backend no longer emits priority operator calls")
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
    reference_map = operator_source / "StaticReferenceMap.bl"
    for declaration in ("StaticReferenceMap[string] value;", "StaticReferenceMap[][primary] value;"):
        reference_map.write_text("public class StaticReferenceMap { public static " + declaration + " }", encoding="utf-8")
        reference_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
        if reference_result.returncode == 0 or "reference type member" not in reference_result.stdout:
            raise SystemExit("Original Z8 did not reject a static reference map:\n" + reference_result.stdout)
    reference_map.unlink()
    native_fixtures = []
    for fixture in (root / "examples" / "native").glob("*.bl"):
        destination = operator_source / fixture.name
        shutil.copy2(fixture, destination)
        native_fixtures.append(destination)
    native_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if native_result.returncode:
        raise SystemExit("Original Z8 rejected native declarations:\n" + native_result.stdout + native_result.stderr)
    bad_native_static = operator_source / "BadNativeStatic.bl"
    for declaration in ("NativeNumber[NativeMath] value;", "int[NativeNumber][NativeMath] value;", "NativeMath[NativeNumber] value;"):
        bad_native_static.write_text("public class BadNativeStatic { public static " + declaration + " }", encoding="utf-8")
        native_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
        if native_result.returncode == 0 or "reference type member" not in native_result.stdout:
            raise SystemExit("Original Z8 did not reject native reference in static collection:\n" + native_result.stdout)
    bad_native_static.unlink()
    bad_primary_attribute = operator_source / "BadPrimaryAttribute.bl"
    bad_primary_attribute.write_text('public class BadPrimaryAttribute { [name "number"] NativeNumber value; }', encoding="utf-8")
    native_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if native_result.returncode == 0 or "Attributes can only be applied to variables of a reference type" not in native_result.stdout:
        raise SystemExit("Original Z8 did not reject attributes on a primary field:\n" + native_result.stdout)
    bad_primary_attribute.unlink()
    for fixture in native_fixtures:
        fixture.unlink()
    sql_map_probe = operator_source / "SqlMapConversion.bl"
    sql_map_probe.write_text('''import org.zenframework.z8.lang.sql.sql_int;
    public class SqlMapConversion { public static void run() { sql_int[string] values = {("x", 1)}; } }''', encoding="utf-8")
    sql_map_result = subprocess.run(operator_command, cwd=temp, capture_output=True, text=True, encoding="utf-8")
    if sql_map_result.returncode == 0 or "Type mismatch" not in sql_map_result.stdout:
        raise SystemExit("Original Z8 did not reject scalar conversion in a SQL map initializer:\n" + sql_map_result.stdout)
    sql_map_probe.unlink()
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
    static org.zenframework.z8.server.types.sql.sql_bool compareDate(int op, org.zenframework.z8.server.types.sql.sql_date left, org.zenframework.z8.server.types.sql.sql_date right) {
        switch (op) {
        case 0: return left.operatorEqu(right); case 1: return left.operatorNotEqu(right);
        case 2: return left.operatorLess(right); case 3: return left.operatorMore(right);
        case 4: return left.operatorLessEqu(right); default: return left.operatorMoreEqu(right);
        }
    }
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        demo.cases.StaticOverloadChild.CLASS<?> metadata = new demo.cases.StaticOverloadChild.CLASS<>(null);
        System.out.println("STATICEXC:" + demo.cases.StaticExceptionValues.z8_run().get());
        System.out.println("SQLARRAY:" + demo.cases.SqlArrays.z8_run().get());
        System.out.println("SQLMAP:" + demo.cases.SqlMaps.z8_run().get());
        System.out.println("OBJECTMAP:" + demo.cases.ObjectMaps.z8_run().get());
        System.out.println("REFMAP:" + demo.cases.ReferenceMaps.z8_run().get());
        System.out.println("NESTEDMAP:" + demo.cases.NestedMapArrays.z8_run().get());
        System.out.println("PRIMARYKEYMAP:" + demo.cases.PrimaryKeyMaps.z8_run().get());
        System.out.println("REFKEYMAP:" + demo.cases.ReferenceKeyMaps.z8_run().get());
        System.out.println("PRIMARYCOLL:" + demo.cases.PrimaryCollectionIdentity.z8_run().get());
        System.out.println("OBJECTKEYMAP:" + demo.cases.ObjectKeyMaps.z8_run().get());
        System.out.println("DEEPARRAY:" + demo.cases.DeepArrays.z8_run().get());
        System.out.println("MATRIXMAP:" + demo.cases.MatrixMaps.z8_run().get());
        System.out.println("MAPEQUALITY:" + demo.cases.ArrayMapEquality.z8_run().get());
        System.out.println("NESTEDMAPS:" + demo.cases.NestedMaps.z8_run().get());
        System.out.println("MULTIKEY:" + demo.cases.MultipleObjectKeys.z8_run().get());
        System.out.println("NATIVEKEY:" + demo.cases.NativeKeyMaps.z8_run().get());
        System.out.println("COVARRAY:" + demo.cases.CovariantArrays.z8_run().get());
        System.out.println("COVMAP:" + demo.cases.CovariantMaps.z8_run().get());
        System.out.println("SQLUSERCONV:" + demo.cases.SqlConversion.z8_run().get());
        System.out.println("EXCEPTIONCONV:" + demo.cases.ExceptionConversion.z8_run().get());
        System.out.println("PRIMARYCONV:" + demo.cases.PrimaryConversion.z8_run().get());
        System.out.println("ENUMCONV:" + demo.cases.EnumConversion.z8_run().get());
        System.out.println("EXPRSTMT:" + demo.cases.ExpressionStatements.z8_run().get());
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
        System.out.println("RESULT:" + demo.cases.StaticInitCases.z8_run().get());
        System.out.println("RESULT:" + demo.cases.FinallyControl.z8_run().get());
        System.out.println("RESULT:" + demo.cases.SqlBoolValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.SqlIntValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.SqlDecimalValues.z8_run().get());
        System.out.println("RESULT:" + demo.cases.SqlStringValues.z8_run().get());
        for (org.zenframework.z8.server.db.DatabaseVendor vendor : org.zenframework.z8.server.db.DatabaseVendor.values()) {
            org.zenframework.z8.server.types.sql.sql_bool[] expressions = {
                demo.cases.SqlBoolValues.z8_expression(), demo.cases.SqlBoolValues.z8_choose(),
                demo.cases.SqlBoolValues.z8_compare(), demo.cases.SqlBoolValues.z8_complex(),
                demo.cases.SqlBoolValues.z8_nested()
            };
            for (org.zenframework.z8.server.types.sql.sql_bool expression : expressions)
                for (boolean logical : new boolean[] {false, true})
                    System.out.println("SQLBOOL:" + vendor.name() + ":" + logical + ":" + expression.format(vendor, null, logical));
            org.zenframework.z8.server.types.sql.sql_integer[] integers = {
                demo.cases.SqlIntValues.z8_expression(), demo.cases.SqlIntValues.z8_remainder(),
                demo.cases.SqlIntValues.z8_bitwise(), demo.cases.SqlIntValues.z8_choice(),
                demo.cases.SqlIntValues.z8_functions(), demo.cases.SqlIntValues.z8_convertedLeft(),
                demo.cases.SqlIntValues.z8_invert(), demo.cases.SqlIntValues.z8_invertTwice(), demo.cases.SqlIntValues.z8_positive()
            };
            for (org.zenframework.z8.server.types.sql.sql_integer value : integers) {
                try { System.out.println("SQLINT:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLINT:" + vendor.name() + ":ERROR"); }
            }
            for (boolean logical : new boolean[] {false, true})
                System.out.println("SQLINTBOOL:" + vendor.name() + ":" + logical + ":" + demo.cases.SqlIntValues.z8_compare().format(vendor, null, logical));
            org.zenframework.z8.server.types.sql.sql_decimal[] decimals = {
                demo.cases.SqlDecimalValues.z8_expression(), demo.cases.SqlDecimalValues.z8_mixed(),
                demo.cases.SqlDecimalValues.z8_converted(), demo.cases.SqlDecimalValues.z8_choice(),
                demo.cases.SqlDecimalValues.z8_remainder(), demo.cases.SqlDecimalValues.z8_convertedLeft(),
                demo.cases.SqlDecimalValues.z8_integerLeft(), demo.cases.SqlDecimalValues.z8_zero(),
                demo.cases.SqlDecimalValues.z8_convertedChoice(), demo.cases.SqlDecimalValues.z8_negative(), demo.cases.SqlDecimalValues.z8_positive()
            };
            for (org.zenframework.z8.server.types.sql.sql_decimal value : decimals) {
                try { System.out.println("SQLDECIMAL:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLDECIMAL:" + vendor.name() + ":ERROR"); }
            }
            org.zenframework.z8.server.types.sql.sql_bool[] decimalComparisons = {
                demo.cases.SqlDecimalValues.z8_compare(), demo.cases.SqlDecimalValues.z8_mixedCompare()
            };
            for (org.zenframework.z8.server.types.sql.sql_bool comparison : decimalComparisons)
                for (boolean logical : new boolean[] {false, true})
                    System.out.println("SQLDECIMALBOOL:" + vendor.name() + ":" + logical + ":" + comparison.format(vendor, null, logical));
            org.zenframework.z8.server.types.sql.sql_decimal[] decimalFunctions = {
                demo.cases.SqlDecimalValues.z8_absolute(), demo.cases.SqlDecimalValues.z8_exponent(),
                demo.cases.SqlDecimalValues.z8_logarithm(), demo.cases.SqlDecimalValues.z8_power(),
                demo.cases.SqlDecimalValues.z8_round(), demo.cases.SqlDecimalValues.z8_truncate()
            };
            for (org.zenframework.z8.server.types.sql.sql_decimal value : decimalFunctions) {
                try { System.out.println("SQLDECFUNC:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLDECFUNC:" + vendor.name() + ":ERROR"); }
            }
            org.zenframework.z8.server.types.sql.sql_integer[] decimalIntegers = {
                demo.cases.SqlDecimalValues.z8_sign(), demo.cases.SqlDecimalValues.z8_ceil(), demo.cases.SqlDecimalValues.z8_floor()
            };
            for (org.zenframework.z8.server.types.sql.sql_integer value : decimalIntegers) {
                try { System.out.println("SQLDECINT:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLDECINT:" + vendor.name() + ":ERROR"); }
            }
            for (boolean logical : new boolean[] {false, true}) {
                try { System.out.println("SQLDECNAN:" + vendor.name() + ":" + logical + ":" + demo.cases.SqlDecimalValues.z8_isNaN().format(vendor, null, logical)); }
                catch (RuntimeException error) { System.out.println("SQLDECNAN:" + vendor.name() + ":" + logical + ":ERROR"); }
            }
            org.zenframework.z8.server.types.sql.sql_string[] strings = {
                demo.cases.SqlStringValues.z8_literal(), demo.cases.SqlStringValues.z8_concatenation(),
                demo.cases.SqlStringValues.z8_convertedLeft(), demo.cases.SqlStringValues.z8_lower(),
                demo.cases.SqlStringValues.z8_trimmed(), demo.cases.SqlStringValues.z8_choice(),
                demo.cases.SqlStringValues.z8_replace(), demo.cases.SqlStringValues.z8_replaceAll(),
                demo.cases.SqlStringValues.z8_substring(), demo.cases.SqlStringValues.z8_remainder(),
                demo.cases.SqlStringValues.z8_reverse(), demo.cases.SqlStringValues.z8_padLeft(), demo.cases.SqlStringValues.z8_padRight()
            };
            for (org.zenframework.z8.server.types.sql.sql_string value : strings) {
                try { System.out.println("SQLSTRING:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLSTRING:" + vendor.name() + ":ERROR"); }
            }
            try { System.out.println("SQLSTRINGLEN:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_length().format(vendor, null)); }
            catch (RuntimeException error) { System.out.println("SQLSTRINGLEN:" + vendor.name() + ":ERROR"); }
            org.zenframework.z8.server.types.sql.sql_bool[] stringPredicates = {
                demo.cases.SqlStringValues.z8_compare(), demo.cases.SqlStringValues.z8_like(), demo.cases.SqlStringValues.z8_regLike()
            };
            for (org.zenframework.z8.server.types.sql.sql_bool predicate : stringPredicates)
                for (boolean logical : new boolean[] {false, true}) {
                    try { System.out.println("SQLSTRINGBOOL:" + vendor.name() + ":" + logical + ":" + predicate.format(vendor, null, logical)); }
                    catch (RuntimeException error) { System.out.println("SQLSTRINGBOOL:" + vendor.name() + ":" + logical + ":ERROR"); }
                }
            for (boolean logical : new boolean[] {false, true}) {
                for (org.zenframework.z8.server.types.sql.sql_bool value : new org.zenframework.z8.server.types.sql.sql_bool[] {demo.cases.SqlStringValues.z8_ftsLike(), demo.cases.SqlStringValues.z8_configuredFtsLike()}) {
                    try { System.out.println("SQLFTSBOOL:" + vendor.name() + ":" + logical + ":" + value.format(vendor, null, logical)); }
                    catch (RuntimeException error) { System.out.println("SQLFTSBOOL:" + vendor.name() + ":" + logical + ":ERROR"); }
                }
            }
            for (org.zenframework.z8.server.types.sql.sql_decimal value : new org.zenframework.z8.server.types.sql.sql_decimal[] {demo.cases.SqlStringValues.z8_ftsRank(), demo.cases.SqlStringValues.z8_configuredFtsRank()}) {
                try { System.out.println("SQLFTSRANK:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLFTSRANK:" + vendor.name() + ":ERROR"); }
            }
            org.zenframework.z8.server.types.sql.sql_integer[] stringSearches = {
                demo.cases.SqlStringValues.z8_findIndex(), demo.cases.SqlStringValues.z8_indexFrom(), demo.cases.SqlStringValues.z8_patternIndex()
            };
            for (org.zenframework.z8.server.types.sql.sql_integer search : stringSearches)
                for (int iteration = 0; iteration < 2; ++iteration) {
                    try { System.out.println("SQLSEARCH:" + vendor.name() + ":" + search.format(vendor, null)); }
                    catch (RuntimeException error) { System.out.println("SQLSEARCH:" + vendor.name() + ":ERROR"); }
                }
            org.zenframework.z8.server.types.sql.sql_bool[] searchPredicates = {
                demo.cases.SqlStringValues.z8_contains(), demo.cases.SqlStringValues.z8_containsFrom(), demo.cases.SqlStringValues.z8_empty()
            };
            for (org.zenframework.z8.server.types.sql.sql_bool predicate : searchPredicates)
                for (boolean logical : new boolean[] {false, true}) {
                    try { System.out.println("SQLSEARCHBOOL:" + vendor.name() + ":" + logical + ":" + predicate.format(vendor, null, logical)); }
                    catch (RuntimeException error) { System.out.println("SQLSEARCHBOOL:" + vendor.name() + ":" + logical + ":ERROR"); }
                }
            try { System.out.println("SQLCONV:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_integer().format(vendor, null)); }
            catch (RuntimeException error) { System.out.println("SQLCONV:" + vendor.name() + ":ERROR"); }
            try { System.out.println("SQLCONV:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_number().format(vendor, null)); }
            catch (RuntimeException error) { System.out.println("SQLCONV:" + vendor.name() + ":ERROR"); }
            System.out.println("SQLUSERCONVSQL:" + vendor.name() + ":" + demo.cases.SqlConversion.z8_convertedNumber().format(vendor, null));
            System.out.println("SQLUSERCONVSQL:" + vendor.name() + ":" + demo.cases.SqlConversion.z8_convertedText().format(vendor, null));
            org.zenframework.z8.server.types.sql.sql_string[] extraStrings = {
                demo.cases.SqlStringValues.z8_quoted(), demo.cases.SqlStringValues.z8_jsonName(),
                demo.cases.SqlStringValues.z8_jsonIndex(), demo.cases.SqlStringValues.z8_identity(),
                demo.cases.SqlStringValues.z8_booleanText(), demo.cases.SqlStringValues.z8_integerText(),
                demo.cases.SqlStringValues.z8_decimalText(), demo.cases.SqlStringValues.z8_regexText(),
                demo.cases.SqlStringValues.z8_notIntegerText(), demo.cases.SqlStringValues.z8_choiceRegexText(), demo.cases.SqlStringValues.z8_guidText(), demo.cases.SqlStringValues.z8_dateText(), demo.cases.SqlStringValues.z8_spanText(), demo.cases.SqlStringValues.z8_binaryText(), demo.cases.SqlStringValues.z8_geometryText()
            };
            for (org.zenframework.z8.server.types.sql.sql_string value : extraStrings) {
                try { System.out.println("SQLTEXTEXTRA:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLTEXTEXTRA:" + vendor.name() + ":ERROR"); }
            }
            for (org.zenframework.z8.server.types.sql.sql_bool predicate : new org.zenframework.z8.server.types.sql.sql_bool[] {
                    demo.cases.SqlStringValues.z8_integerTest(), demo.cases.SqlStringValues.z8_numberTest() })
                for (boolean logical : new boolean[] {false, true}) {
                    try { System.out.println("SQLTEXTTEST:" + vendor.name() + ":" + logical + ":" + predicate.format(vendor, null, logical)); }
                    catch (RuntimeException error) { System.out.println("SQLTEXTTEST:" + vendor.name() + ":" + logical + ":ERROR"); }
                }
            for (org.zenframework.z8.server.types.sql.sql_guid value : new org.zenframework.z8.server.types.sql.sql_guid[] {
                    demo.cases.SqlStringValues.z8_sqlGuid(), demo.cases.SqlStringValues.z8_guidChoice() })
                System.out.println("SQLGUID:" + vendor.name() + ":" + value.format(vendor, null));
            for (boolean logical : new boolean[] {false, true})
                System.out.println("SQLGUIDBOOL:" + vendor.name() + ":" + logical + ":" + demo.cases.SqlStringValues.z8_guidEqual().format(vendor, null, logical));
            for (org.zenframework.z8.server.types.sql.sql_date value : new org.zenframework.z8.server.types.sql.sql_date[] {
                    demo.cases.SqlStringValues.z8_sqlDate(), demo.cases.SqlStringValues.z8_dateChoice(), demo.cases.SqlStringValues.z8_parsedDate() }) {
                try { System.out.println("SQLDATE:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLDATE:" + vendor.name() + ":ERROR"); }
            }
            try { System.out.println("SQLDATETICKS:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_dateTicks().format(vendor, null)); }
            catch (RuntimeException error) { System.out.println("SQLDATETICKS:" + vendor.name() + ":ERROR"); }
            for (org.zenframework.z8.server.types.sql.sql_date value : new org.zenframework.z8.server.types.sql.sql_date[] {
                demo.cases.SqlStringValues.z8_dateTruncDay(), demo.cases.SqlStringValues.z8_dateTruncGroupedDay(),
                demo.cases.SqlStringValues.z8_dateTruncHour(), demo.cases.SqlStringValues.z8_dateTruncMinute(), demo.cases.SqlStringValues.z8_dateTruncSecond(),
                demo.cases.SqlStringValues.z8_dateAddDay(), demo.cases.SqlStringValues.z8_dateAddHour(), demo.cases.SqlStringValues.z8_dateAddMinute(), demo.cases.SqlStringValues.z8_dateAddSecond() })
                System.out.println("SQLDATEFUNC:" + vendor.name() + ":" + value.format(vendor, null));
            for (org.zenframework.z8.server.types.sql.sql_integer value : new org.zenframework.z8.server.types.sql.sql_integer[] {
                demo.cases.SqlStringValues.z8_dateMinute(), demo.cases.SqlStringValues.z8_dateHour(), demo.cases.SqlStringValues.z8_dateDay(),
                demo.cases.SqlStringValues.z8_dateMonth(), demo.cases.SqlStringValues.z8_dateYear() }) {
                try { System.out.println("SQLDATEPART:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLDATEPART:" + vendor.name() + ":ERROR"); }
            }
            for (int mode = 0; mode < 7; ++mode) for (int op = 0; op < 6; ++op) {
                org.zenframework.z8.server.types.sql.sql_date left = new org.zenframework.z8.server.types.sql.sql_date(new org.zenframework.z8.server.types.date(0L));
                org.zenframework.z8.server.types.sql.sql_date right = new org.zenframework.z8.server.types.sql.sql_date(new org.zenframework.z8.server.types.date(100000000L));
                if (mode == 4) { left = new org.zenframework.z8.server.types.sql.sql_date(org.zenframework.z8.server.types.date.Min); right = right.operatorPriority(); }
                else if (mode == 5) { left = left.operatorPriority(); right = new org.zenframework.z8.server.types.sql.sql_date(org.zenframework.z8.server.types.date.Max); }
                else if (mode == 6) right = new org.zenframework.z8.server.types.sql.sql_date(new org.zenframework.z8.server.types.date(3600000L));
                else { if ((mode & 1) != 0) left = left.operatorPriority(); if ((mode & 2) != 0) right = right.operatorPriority(); }
                org.zenframework.z8.server.types.sql.sql_bool result = compareDate(op, left, right);
                for (boolean logical : new boolean[] {false, true})
                    System.out.println("SQLDATECMP:" + vendor.name() + ":" + logical + ":" + result.format(vendor, null, logical));
            }
            for (boolean logical : new boolean[] {false, true})
                System.out.println("SQLDATEBL:" + vendor.name() + ":" + logical + ":" + demo.cases.SqlStringValues.z8_dateCompare().format(vendor, null, logical));
            for (org.zenframework.z8.server.types.sql.sql_datespan value : new org.zenframework.z8.server.types.sql.sql_datespan[] {
                demo.cases.SqlStringValues.z8_sqlSpan(), demo.cases.SqlStringValues.z8_spanChoice(), demo.cases.SqlStringValues.z8_spanSum(),
                demo.cases.SqlStringValues.z8_spanDifference(), demo.cases.SqlStringValues.z8_dateDifference() })
                System.out.println("SQLSPAN:" + vendor.name() + ":" + value.format(vendor, null));
            for (org.zenframework.z8.server.types.sql.sql_date value : new org.zenframework.z8.server.types.sql.sql_date[] {
                demo.cases.SqlStringValues.z8_datePlusSpan(), demo.cases.SqlStringValues.z8_dateMinusSpan(), demo.cases.SqlStringValues.z8_spanPlusDate() })
                System.out.println("SQLSPANARITH:" + vendor.name() + ":" + value.format(vendor, null));
            for (boolean logical : new boolean[] {false, true})
                System.out.println("SQLSPANBOOL:" + vendor.name() + ":" + logical + ":" + demo.cases.SqlStringValues.z8_spanCompare().format(vendor, null, logical));
            for (org.zenframework.z8.server.types.sql.sql_integer value : new org.zenframework.z8.server.types.sql.sql_integer[] {
                demo.cases.SqlStringValues.z8_spanDays(), demo.cases.SqlStringValues.z8_spanHours(), demo.cases.SqlStringValues.z8_spanMinutes(),
                demo.cases.SqlStringValues.z8_spanSeconds(), demo.cases.SqlStringValues.z8_spanTotalHours(), demo.cases.SqlStringValues.z8_spanTotalMinutes(), demo.cases.SqlStringValues.z8_spanTotalSeconds() }) {
                try { System.out.println("SQLSPANPART:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLSPANPART:" + vendor.name() + ":ERROR"); }
            }
            for (org.zenframework.z8.server.types.sql.sql_datespan value : new org.zenframework.z8.server.types.sql.sql_datespan[] {
                demo.cases.SqlStringValues.z8_spanTruncHour(), demo.cases.SqlStringValues.z8_spanTruncMinute(), demo.cases.SqlStringValues.z8_spanTruncSecond(),
                demo.cases.SqlStringValues.z8_spanAddDay(), demo.cases.SqlStringValues.z8_spanAddHour(), demo.cases.SqlStringValues.z8_spanAddMinute(), demo.cases.SqlStringValues.z8_spanAddSecond() }) {
                try { System.out.println("SQLSPANFUNC:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLSPANFUNC:" + vendor.name() + ":ERROR"); }
            }
            System.out.println("SQLBINARY:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_sqlBinary().format(vendor, null));
            for (org.zenframework.z8.server.types.sql.sql_geometry value : new org.zenframework.z8.server.types.sql.sql_geometry[] {
                demo.cases.SqlStringValues.z8_sqlGeometry(), demo.cases.SqlStringValues.z8_geometryPoint(), demo.cases.SqlStringValues.z8_geometryChoice() }) {
                try { System.out.println("SQLGEOM:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLGEOM:" + vendor.name() + ":ERROR"); }
            }
            for (org.zenframework.z8.server.types.sql.sql_bool value : new org.zenframework.z8.server.types.sql.sql_bool[] {
                demo.cases.SqlStringValues.z8_geometryEqual(), demo.cases.SqlStringValues.z8_geometryIntersects(), demo.cases.SqlStringValues.z8_emptyGeometryIntersects() })
                for (boolean logical : new boolean[] {false, true})
                    System.out.println("SQLGEOMBOOL:" + vendor.name() + ":" + logical + ":" + value.format(vendor, null, logical));
            System.out.println("SQLGEOMEMPTY:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_emptyGeometry().format(vendor, null));
            System.out.println("SQLGEOMEMPTY:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_emptyGeometryText().format(vendor, null));
            System.out.println("SQLPRIMARY:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_sqlPrimaryText().format(vendor, null));
            System.out.println("SQLPRIMARYCHECK:" + vendor.name() + ":" + demo.cases.SqlStringValues.z8_sqlPrimaryChecks().get());
            org.zenframework.z8.server.types.sql.sql_geometry geo = demo.cases.SqlStringValues.z8_sqlGeometry();
            for (org.zenframework.z8.server.types.sql.sql_geometry value : new org.zenframework.z8.server.types.sql.sql_geometry[] {
                geo.z8_startPoint(), geo.z8_endPoint(), geo.z8_union(), geo.z8_centroid(), geo.z8_envelope(), geo.z8_homogenize(), geo.z8_makeValid(),
                geo.z8_split(geo), geo.z8_intersect(geo), geo.z8_element(new org.zenframework.z8.server.types.sql.sql_integer(2)),
                geo.z8_extract(new org.zenframework.z8.server.types.sql.sql_integer(2)),
                geo.z8_interpolatePoint(new org.zenframework.z8.server.types.sql.sql_decimal(new org.zenframework.z8.server.types.decimal("0.5"))),
                geo.z8_buffer(new org.zenframework.z8.server.types.sql.sql_decimal(new org.zenframework.z8.server.types.decimal("1.5"))), demo.cases.SqlStringValues.z8_geometryChain() }) {
                try { System.out.println("SQLGEOMFUNC:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLGEOMFUNC:" + vendor.name() + ":ERROR"); }
            }
            for (org.zenframework.z8.server.types.sql.sql_decimal value : new org.zenframework.z8.server.types.sql.sql_decimal[] {
                geo.z8_x(), geo.z8_xMax(), geo.z8_xMin(), geo.z8_y(), geo.z8_yMax(), geo.z8_yMin(), geo.z8_length(), geo.z8_distance(geo) }) {
                try { System.out.println("SQLGEOMMETRIC:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLGEOMMETRIC:" + vendor.name() + ":ERROR"); }
            }
            for (org.zenframework.z8.server.types.sql.sql_bool value : new org.zenframework.z8.server.types.sql.sql_bool[] { geo.z8_isEmpty(), geo.z8_isValid() })
                for (boolean logical : new boolean[] {false, true}) {
                    try { System.out.println("SQLGEOMTEST:" + vendor.name() + ":" + logical + ":" + value.format(vendor, null, logical)); }
                    catch (RuntimeException error) { System.out.println("SQLGEOMTEST:" + vendor.name() + ":" + logical + ":ERROR"); }
                }
            for (org.zenframework.z8.server.types.sql.sql_string value : new org.zenframework.z8.server.types.sql.sql_string[] { geo.z8_strType(), geo.z8_asGeoJSON() }) {
                try { System.out.println("SQLGEOMTEXT:" + vendor.name() + ":" + value.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLGEOMTEXT:" + vendor.name() + ":ERROR"); }
            }
            try { System.out.println("SQLGEOMCOUNT:" + vendor.name() + ":" + geo.z8_collectionSize().format(vendor, null)); }
            catch (RuntimeException error) { System.out.println("SQLGEOMCOUNT:" + vendor.name() + ":ERROR"); }
        }
        org.zenframework.z8.server.types.sql.sql_integer sharedSearch = demo.cases.SqlStringValues.z8_indexFrom();
        for (org.zenframework.z8.server.db.DatabaseVendor vendor : org.zenframework.z8.server.db.DatabaseVendor.values())
            for (int iteration = 0; iteration < 2; ++iteration) {
                try { System.out.println("SQLSEARCHCROSS:" + vendor.name() + ":" + sharedSearch.format(vendor, null)); }
                catch (RuntimeException error) { System.out.println("SQLSEARCHCROSS:" + vendor.name() + ":ERROR"); }
            }
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
        # The cached SQL runtime can predate the checked-out operator methods.
        # Compile the SQL classes exercised here from the current sources.
        server_source = original / "org.zenframework.z8.server" / "src" / "main" / "java" / "org" / "zenframework" / "z8" / "server"
        sql_sources = [server_source / "types" / "sql" / name for name in ("sql_primary.java", "sql_bool.java", "sql_integer.java", "sql_decimal.java", "sql_string.java", "sql_guid.java", "sql_date.java", "sql_datespan.java", "sql_binary.java", "sql_geometry.java")]
        sql_sources += [server_source / "db" / "sql" / name for name in ("SqlConst.java", "SqlStringToken.java")]
        sql_sources += [server_source / "db" / "sql" / "expressions" / name for name in
                        ("Operation.java", "Add.java", "Mul.java", "Group.java", "And.java", "Or.java", "Rel.java", "Equ.java", "Unary.java", "UnaryNot.java", "Bitwise.java")]
        sql_sources += [server_source / "db" / "sql" / "functions" / name for name in ("If.java", "CaseToken.java", "Nvl.java", "IsNull.java")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "numeric" / name for name in
                        ("Floor.java", "Mod.java", "Sign.java", "Abs.java", "Power.java", "IsNaN.java", "Ceil.java", "Exp.java", "Ln.java", "Round.java", "Truncate.java")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "conversion" / name for name in ("IntToDecimal.java", "ToDecimal.java", "ToString.java", "StringToInt.java", "IsIntString.java", "IsNumericString.java", "GuidToString.java", "DateToString.java", "DateToInt.java", "ToDate.java", "DatespanToString.java")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "date" / (name + ".java") for name in
                        ("ExtractDatePart", "ExtractMinute", "ExtractHour", "ExtractDay", "ExtractMonth", "ExtractYear", "TruncDay", "TruncHour", "TruncMinute", "TruncSecond", "AddDay", "AddHour", "AddMinute", "AddSecond")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "datespan" / (name + ".java") for name in
                        ("Days", "Hours", "Minutes", "Seconds", "TotalHours", "TotalMinutes", "TotalSeconds", "TruncHour", "TruncMinute", "TruncSecond", "AddDay", "AddHour", "AddMinute", "AddSecond")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "geometry" / (name + ".java") for name in
                        ("Point", "CollectionSize", "X", "XMax", "XMin", "Y", "YMax", "YMin", "Length", "Element", "Split", "Extract", "GeometryType", "Intersection", "StartPoint", "EndPoint", "Union", "Centroid", "Envelope", "Homogenize", "InterpolatePoint", "Buffer", "IsEmpty", "IsValid", "MakeValid", "AsGeoJson")]
        sql_sources += [server_source / "db" / "sql" / "expressions" / (name + ".java") for name in ("Intersects", "Distance")]
        sql_sources += [server_source / "db" / "sql" / "functions" / "string" / name for name in
                        ("Concat.java", "Lower.java", "Upper.java", "LTrim.java", "RTrim.java", "Length.java", "Quote.java",
                         "Like.java", "RegLike.java", "Replace.java", "RegReplace.java", "Substr.java", "Reverse.java", "LPad.java", "RPad.java",
                         "IndexOf.java", "RegIndexOf.java", "IsEmpty.java", "GetJson.java")]
        sql_sources += [server_source / "db" / "sql" / "fts" / name for name in ("FtsLike.java", "FtsQuery.java", "FtsRank.java", "FtsVector.java")]
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                        "-cp", str(generated_classes) + os.pathsep + run_classpath, "-d", str(generated_classes)] + list(map(str, sql_sources)), cwd=temp, check=True)
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
Z8SqlBool compareDate(int op, Z8SqlDate left, Z8SqlDate right) {
    switch (op) {
    case 0: return z8_sql_date_compare!"=="(left, right); case 1: return z8_sql_date_compare!"!="(left, right);
    case 2: return z8_sql_date_compare!"<"(left, right); case 3: return z8_sql_date_compare!">"(left, right);
    case 4: return z8_sql_date_compare!"<="(left, right); default: return z8_sql_date_compare!">="(left, right);
    }
}
void main() {
    writeln("STATICEXC:", z8_optional_require(Z8p_64656D6F2E63617365732E537461746963457863657074696F6E56616C756573.m_run()));
    writeln("SQLARRAY:", z8_optional_require(Z8p_64656D6F2E63617365732E53716C417272617973.m_run()));
    writeln("SQLMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E53716C4D617073.m_run()));
    writeln("OBJECTMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E4F626A6563744D617073.m_run()));
    writeln("REFMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E5265666572656E63654D617073.m_run()));
    writeln("NESTEDMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E4E65737465644D6170417272617973.m_run()));
    writeln("PRIMARYKEYMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E5072696D6172794B65794D617073.m_run()));
    writeln("REFKEYMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E5265666572656E63654B65794D617073.m_run()));
    writeln("PRIMARYCOLL:", z8_optional_require(Z8p_64656D6F2E63617365732E5072696D617279436F6C6C656374696F6E4964656E74697479.m_run()));
    writeln("OBJECTKEYMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E4F626A6563744B65794D617073.m_run()));
    writeln("DEEPARRAY:", z8_optional_require(Z8p_64656D6F2E63617365732E44656570417272617973.m_run()));
    writeln("MATRIXMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E4D61747269784D617073.m_run()));
    writeln("MAPEQUALITY:", z8_optional_require(Z8p_64656D6F2E63617365732E41727261794D6170457175616C697479.m_run()));
    writeln("NESTEDMAPS:", z8_optional_require(Z8p_64656D6F2E63617365732E4E65737465644D617073.m_run()));
    writeln("MULTIKEY:", z8_optional_require(Z8p_64656D6F2E63617365732E4D756C7469706C654F626A6563744B657973.m_run()));
    writeln("NATIVEKEY:", z8_optional_require(Z8p_64656D6F2E63617365732E4E61746976654B65794D617073.m_run()));
    writeln("COVARRAY:", z8_optional_require(Z8p_64656D6F2E63617365732E436F76617269616E74417272617973.m_run()));
    writeln("COVMAP:", z8_optional_require(Z8p_64656D6F2E63617365732E436F76617269616E744D617073.m_run()));
    writeln("SQLUSERCONV:", z8_optional_require(Z8p_64656D6F2E63617365732E53716C436F6E76657273696F6E.m_run()));
    writeln("EXCEPTIONCONV:", z8_optional_require(Z8p_64656D6F2E63617365732E457863657074696F6E436F6E76657273696F6E.m_run()));
    writeln("PRIMARYCONV:", z8_optional_require(Z8p_64656D6F2E63617365732E5072696D617279436F6E76657273696F6E.m_run()));
    writeln("ENUMCONV:", z8_optional_require(Z8p_64656D6F2E63617365732E456E756D436F6E76657273696F6E.m_run()));
    writeln("EXPRSTMT:", z8_optional_require(Z8p_64656D6F2E63617365732E45787072657373696F6E53746174656D656E7473.m_run()));
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
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E537461746963496E69744361736573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E46696E616C6C79436F6E74726F6C.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_run()));
    writeln(z8_optional_require(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_run()));
    foreach (vendorIndex, vendor; ["Oracle", "SqlServer", "Postgres", "H2"]) {
        auto dialect = [Z8SqlVendor.Oracle, Z8SqlVendor.SqlServer, Z8SqlVendor.Postgres, Z8SqlVendor.H2][vendorIndex];
        auto expressions = [Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_expression(),
            Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_choose(),
            Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_compare(),
            Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_complex(),
            Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573.m_nested()];
        foreach (expression; expressions)
            foreach (logical; [false, true])
                writeln("SQLBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(expression, logical, dialect)));
        auto integers = [Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_expression(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_remainder(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_bitwise(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_choice(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_functions(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_convertedLeft(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_invert(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_invertTwice(),
            Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_positive()];
        foreach (value; integers) {
            try { writeln("SQLINT:", vendor, ":", z8_to_utf8(z8_sql_int_format(value, dialect))); }
            catch (Exception error) { writeln("SQLINT:", vendor, ":ERROR"); }
        }
        foreach (logical; [false, true])
            writeln("SQLINTBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(Z8p_64656D6F2E63617365732E53716C496E7456616C756573.m_compare(), logical, dialect)));
        auto decimals = [Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_expression(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_mixed(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_converted(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_choice(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_remainder(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_convertedLeft(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_integerLeft(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_zero(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_convertedChoice(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_negative(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_positive()];
        foreach (value; decimals) {
            try { writeln("SQLDECIMAL:", vendor, ":", z8_to_utf8(z8_sql_decimal_format(value, dialect))); }
            catch (Exception error) { writeln("SQLDECIMAL:", vendor, ":ERROR"); }
        }
        auto decimalComparisons = [Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_compare(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_mixedCompare()];
        foreach (comparison; decimalComparisons)
            foreach (logical; [false, true])
                writeln("SQLDECIMALBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(comparison, logical, dialect)));
        auto decimalFunctions = [Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_absolute(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_exponent(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_logarithm(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_power(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_round(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_truncate()];
        foreach (value; decimalFunctions) {
            try { writeln("SQLDECFUNC:", vendor, ":", z8_to_utf8(z8_sql_decimal_format(value, dialect))); }
            catch (Exception error) { writeln("SQLDECFUNC:", vendor, ":ERROR"); }
        }
        auto decimalIntegers = [Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_sign(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_ceil(),
            Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_floor()];
        foreach (value; decimalIntegers) {
            try { writeln("SQLDECINT:", vendor, ":", z8_to_utf8(z8_sql_int_format(value, dialect))); }
            catch (Exception error) { writeln("SQLDECINT:", vendor, ":ERROR"); }
        }
        foreach (logical; [false, true]) {
            try { writeln("SQLDECNAN:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573.m_isNaN(), logical, dialect))); }
            catch (Exception error) { writeln("SQLDECNAN:", vendor, ":", logical, ":ERROR"); }
        }
        auto strings = [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_literal(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_concatenation(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_convertedLeft(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_lower(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_trimmed(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_choice(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_replace(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_replaceAll(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_substring(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_remainder(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_reverse(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_padLeft(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_padRight()];
        foreach (value; strings) {
            try { writeln("SQLSTRING:", vendor, ":", z8_to_utf8(z8_sql_string_format(value, dialect))); }
            catch (Exception error) { writeln("SQLSTRING:", vendor, ":ERROR"); }
        }
        try { writeln("SQLSTRINGLEN:", vendor, ":", z8_to_utf8(z8_sql_int_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_length(), dialect))); }
        catch (Exception error) { writeln("SQLSTRINGLEN:", vendor, ":ERROR"); }
        auto stringPredicates = [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_compare(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_like(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_regLike()];
        foreach (predicate; stringPredicates)
            foreach (logical; [false, true]) {
                try { writeln("SQLSTRINGBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(predicate, logical, dialect))); }
                catch (Exception error) { writeln("SQLSTRINGBOOL:", vendor, ":", logical, ":ERROR"); }
            }
        foreach (logical; [false, true]) {
            foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_ftsLike(), Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_configuredFtsLike()]) {
                try { writeln("SQLFTSBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(value, logical, dialect))); }
                catch (Exception error) { writeln("SQLFTSBOOL:", vendor, ":", logical, ":ERROR"); }
            }
        }
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_ftsRank(), Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_configuredFtsRank()]) {
            try { writeln("SQLFTSRANK:", vendor, ":", z8_to_utf8(z8_sql_decimal_format(value, dialect))); }
            catch (Exception error) { writeln("SQLFTSRANK:", vendor, ":ERROR"); }
        }
        auto stringSearches = [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_findIndex(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_indexFrom(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_patternIndex()];
        foreach (search; stringSearches)
            foreach (iteration; 0 .. 2) {
                try { writeln("SQLSEARCH:", vendor, ":", z8_to_utf8(z8_sql_int_format(search, dialect))); }
                catch (Exception error) { writeln("SQLSEARCH:", vendor, ":ERROR"); }
            }
        auto searchPredicates = [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_contains(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_containsFrom(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_empty()];
        foreach (predicate; searchPredicates)
            foreach (logical; [false, true]) {
                try { writeln("SQLSEARCHBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(predicate, logical, dialect))); }
                catch (Exception error) { writeln("SQLSEARCHBOOL:", vendor, ":", logical, ":ERROR"); }
            }
        try { writeln("SQLCONV:", vendor, ":", z8_to_utf8(z8_sql_int_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_integer(), dialect))); }
        catch (Exception error) { writeln("SQLCONV:", vendor, ":ERROR"); }
        try { writeln("SQLCONV:", vendor, ":", z8_to_utf8(z8_sql_decimal_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_number(), dialect))); }
        catch (Exception error) { writeln("SQLCONV:", vendor, ":ERROR"); }
        writeln("SQLUSERCONVSQL:", vendor, ":", z8_to_utf8(z8_sql_int_format(Z8p_64656D6F2E63617365732E53716C436F6E76657273696F6E.m_convertedNumber(), dialect)));
        writeln("SQLUSERCONVSQL:", vendor, ":", z8_to_utf8(z8_sql_string_format(Z8p_64656D6F2E63617365732E53716C436F6E76657273696F6E.m_convertedText(), dialect)));
        auto extraStrings = [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_quoted(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_jsonName(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_jsonIndex(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_identity(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_booleanText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_integerText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_decimalText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_regexText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_notIntegerText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_choiceRegexText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_guidText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_binaryText(),
            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryText()];
        foreach (value; extraStrings) {
            try { writeln("SQLTEXTEXTRA:", vendor, ":", z8_to_utf8(z8_sql_string_format(value, dialect))); }
            catch (Exception error) { writeln("SQLTEXTEXTRA:", vendor, ":ERROR"); }
        }
        foreach (predicate; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_integerTest(),
                            Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_numberTest()])
            foreach (logical; [false, true]) {
                try { writeln("SQLTEXTTEST:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(predicate, logical, dialect))); }
                catch (Exception error) { writeln("SQLTEXTTEST:", vendor, ":", logical, ":ERROR"); }
            }
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlGuid(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_guidChoice()])
            writeln("SQLGUID:", vendor, ":", z8_to_utf8(z8_sql_guid_format(value, dialect)));
        foreach (logical; [false, true])
            writeln("SQLGUIDBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_guidEqual(), logical, dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlDate(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateChoice(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_parsedDate()]) {
            try { writeln("SQLDATE:", vendor, ":", z8_to_utf8(z8_sql_date_format(value, dialect))); }
            catch (Exception error) { writeln("SQLDATE:", vendor, ":ERROR"); }
        }
        try { writeln("SQLDATETICKS:", vendor, ":", z8_to_utf8(z8_sql_int_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTicks(), dialect))); }
        catch (Exception error) { writeln("SQLDATETICKS:", vendor, ":ERROR"); }
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTruncDay(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTruncGroupedDay(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTruncHour(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTruncMinute(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateTruncSecond(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateAddDay(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateAddHour(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateAddMinute(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateAddSecond()])
            writeln("SQLDATEFUNC:", vendor, ":", z8_to_utf8(z8_sql_date_format(value, dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateMinute(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateHour(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateDay(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateMonth(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateYear()]) {
            try { writeln("SQLDATEPART:", vendor, ":", z8_to_utf8(z8_sql_int_format(value, dialect))); }
            catch (Exception error) { writeln("SQLDATEPART:", vendor, ":ERROR"); }
        }
        foreach (mode; 0 .. 7) foreach (op; 0 .. 6) {
            auto left = z8_sql_date_const(z8_date_from_ticks(0)), right = z8_sql_date_const(z8_date_from_ticks(100000000));
            if (mode == 4) { left = z8_sql_date_const(z8_date_min); right = z8_sql_date_group(right); }
            else if (mode == 5) { left = z8_sql_date_group(left); right = z8_sql_date_const(z8_date_max); }
            else if (mode == 6) right = z8_sql_date_const(z8_date_from_ticks(3600000));
            else { if (mode & 1) left = z8_sql_date_group(left); if (mode & 2) right = z8_sql_date_group(right); }
            auto result = compareDate(op, left, right);
            foreach (logical; [false, true])
                writeln("SQLDATECMP:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(result, logical, dialect)));
        }
        foreach (logical; [false, true])
            writeln("SQLDATEBL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateCompare(), logical, dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlSpan(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanChoice(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanSum(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanDifference(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateDifference()])
            writeln("SQLSPAN:", vendor, ":", z8_to_utf8(z8_sql_datespan_format(value, dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_datePlusSpan(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_dateMinusSpan(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanPlusDate()])
            writeln("SQLSPANARITH:", vendor, ":", z8_to_utf8(z8_sql_date_format(value, dialect)));
        foreach (logical; [false, true])
            writeln("SQLSPANBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanCompare(), logical, dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanDays(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanHours(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanMinutes(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanSeconds(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTotalHours(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTotalMinutes(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTotalSeconds()]) {
            try { writeln("SQLSPANPART:", vendor, ":", z8_to_utf8(z8_sql_int_format(value, dialect))); }
            catch (Exception error) { writeln("SQLSPANPART:", vendor, ":ERROR"); }
        }
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTruncHour(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTruncMinute(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanTruncSecond(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanAddDay(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanAddHour(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanAddMinute(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_spanAddSecond()]) {
            try { writeln("SQLSPANFUNC:", vendor, ":", z8_to_utf8(z8_sql_datespan_format(value, dialect))); }
            catch (Exception error) { writeln("SQLSPANFUNC:", vendor, ":ERROR"); }
        }
        writeln("SQLBINARY:", vendor, ":", z8_to_utf8(z8_sql_binary_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlBinary(), dialect)));
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlGeometry(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryPoint(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryChoice()]) {
            try { writeln("SQLGEOM:", vendor, ":", z8_to_utf8(z8_sql_geometry_format(value, dialect))); }
            catch (Exception error) { writeln("SQLGEOM:", vendor, ":ERROR"); }
        }
        foreach (value; [Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryEqual(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryIntersects(),
                        Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_emptyGeometryIntersects()])
            foreach (logical; [false, true])
                writeln("SQLGEOMBOOL:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(value, logical, dialect)));
        auto emptyGeometry = z8_sql_geometry_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_emptyGeometry(), dialect);
        auto emptyGeometryText = z8_sql_string_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_emptyGeometryText(), dialect);
        writeln("SQLGEOMEMPTY:", vendor, ":", emptyGeometry is null ? "null" : z8_to_utf8(emptyGeometry));
        writeln("SQLGEOMEMPTY:", vendor, ":", emptyGeometryText is null ? "null" : z8_to_utf8(emptyGeometryText));
        writeln("SQLPRIMARY:", vendor, ":", z8_to_utf8(z8_sql_string_format(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlPrimaryText(), dialect)));
        writeln("SQLPRIMARYCHECK:", vendor, ":", z8_optional_require(Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlPrimaryChecks()));
        auto geo = Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_sqlGeometry();
        auto half = z8_sql_decimal_const(z8_decimal_parse("0.5"w));
        auto oneHalf = z8_sql_decimal_const(z8_decimal_parse("1.5"w));
        foreach (value; [z8_sql_geometry_startPoint(geo), z8_sql_geometry_endPoint(geo), z8_sql_geometry_union(geo),
                         z8_sql_geometry_centroid(geo), z8_sql_geometry_envelope(geo), z8_sql_geometry_homogenize(geo), z8_sql_geometry_makeValid(geo),
                         z8_sql_geometry_split(geo, geo), z8_sql_geometry_intersect(geo, geo), z8_sql_geometry_element(geo, z8_sql_int_const(2)),
                         z8_sql_geometry_extract(geo, z8_sql_int_const(2)), z8_sql_geometry_interpolatePoint(geo, half),
                         z8_sql_geometry_buffer(geo, oneHalf), Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_geometryChain()]) {
            try { writeln("SQLGEOMFUNC:", vendor, ":", z8_to_utf8(z8_sql_geometry_format(value, dialect))); }
            catch (Exception error) { writeln("SQLGEOMFUNC:", vendor, ":ERROR"); }
        }
        foreach (value; [z8_sql_geometry_x(geo), z8_sql_geometry_xMax(geo), z8_sql_geometry_xMin(geo), z8_sql_geometry_y(geo),
                         z8_sql_geometry_yMax(geo), z8_sql_geometry_yMin(geo), z8_sql_geometry_length(geo), z8_sql_geometry_distance(geo, geo)]) {
            try { writeln("SQLGEOMMETRIC:", vendor, ":", z8_to_utf8(z8_sql_decimal_format(value, dialect))); }
            catch (Exception error) { writeln("SQLGEOMMETRIC:", vendor, ":ERROR"); }
        }
        foreach (value; [z8_sql_geometry_isEmpty(geo), z8_sql_geometry_isValid(geo)])
            foreach (logical; [false, true]) {
                try { writeln("SQLGEOMTEST:", vendor, ":", logical, ":", z8_to_utf8(z8_sql_bool_format(value, logical, dialect))); }
                catch (Exception error) { writeln("SQLGEOMTEST:", vendor, ":", logical, ":ERROR"); }
            }
        foreach (value; [z8_sql_geometry_strType(geo), z8_sql_geometry_asGeoJSON(geo)]) {
            try { writeln("SQLGEOMTEXT:", vendor, ":", z8_to_utf8(z8_sql_string_format(value, dialect))); }
            catch (Exception error) { writeln("SQLGEOMTEXT:", vendor, ":ERROR"); }
        }
        try { writeln("SQLGEOMCOUNT:", vendor, ":", z8_to_utf8(z8_sql_int_format(z8_sql_geometry_collectionSize(geo), dialect))); }
        catch (Exception error) { writeln("SQLGEOMCOUNT:", vendor, ":ERROR"); }
    }
    auto sharedSearch = Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573.m_indexFrom();
    foreach (vendorIndex, vendor; ["Oracle", "SqlServer", "Postgres", "H2"]) {
        auto dialect = [Z8SqlVendor.Oracle, Z8SqlVendor.SqlServer, Z8SqlVendor.Postgres, Z8SqlVendor.H2][vendorIndex];
        foreach (iteration; 0 .. 2) {
            try { writeln("SQLSEARCHCROSS:", vendor, ":", z8_to_utf8(z8_sql_int_format(sharedSearch, dialect))); }
            catch (Exception error) { writeln("SQLSEARCHCROSS:", vendor, ":ERROR"); }
        }
    }
}
''', encoding="utf-8")
        d_binary = temp / ("compare.exe" if os.name == "nt" else "compare")
        subprocess.run(["dmd", str(d_runner), *map(str, d_modules), "-I" + str(d_root), *import_args(),
                        str(runtime_lib), "-oq", "-od=" + str(temp), "-of=" + str(d_binary)], cwd=temp, check=True)
        d_lines = subprocess.check_output([str(d_binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
        d_results = [line for line in d_lines if not line.startswith(("FILEATTR:", "STATICEXC:", "EXCEPTIONCONV:", "PRIMARYCONV:", "ENUMCONV:", "EXPRSTMT:", "SQLARRAY:", "SQLMAP:", "OBJECTMAP:", "REFMAP:", "NESTEDMAP:", "PRIMARYKEYMAP:", "REFKEYMAP:", "PRIMARYCOLL:", "OBJECTKEYMAP:", "DEEPARRAY:", "MATRIXMAP:", "MAPEQUALITY:", "NESTEDMAPS:", "MULTIKEY:", "NATIVEKEY:", "COVARRAY:", "COVMAP:", "SQLUSERCONV:", "SQLUSERCONVSQL:", "SQLBOOL:", "SQLINT:", "SQLINTBOOL:", "SQLDECIMAL:", "SQLDECIMALBOOL:", "SQLDECFUNC:", "SQLDECINT:", "SQLDECNAN:", "SQLSTRING:", "SQLSTRINGLEN:", "SQLSTRINGBOOL:", "SQLSEARCH:", "SQLSEARCHBOOL:", "SQLSEARCHCROSS:", "SQLCONV:", "SQLTEXTEXTRA:", "SQLTEXTTEST:", "SQLGUID:", "SQLGUIDBOOL:", "SQLDATE:", "SQLDATETICKS:", "SQLDATEFUNC:", "SQLDATEPART:", "SQLDATECMP:", "SQLDATEBL:", "SQLSPAN:", "SQLSPANARITH:", "SQLSPANBOOL:", "SQLSPANPART:", "SQLSPANFUNC:", "SQLBINARY:", "SQLGEOM:", "SQLGEOMBOOL:", "SQLGEOMEMPTY:", "SQLGEOMFUNC:", "SQLGEOMMETRIC:", "SQLGEOMTEST:", "SQLGEOMTEXT:", "SQLGEOMCOUNT:", "SQLPRIMARY:", "SQLPRIMARYCHECK:", "SQLFTSBOOL:", "SQLFTSRANK:"))]
        original_static_exception = [line for line in output.splitlines() if line.startswith("STATICEXC:")]
        d_static_exception = [line for line in d_lines if line.startswith("STATICEXC:")]
        if original_static_exception != ["STATICEXC:253"] or d_static_exception != original_static_exception:
            raise SystemExit(f"Static exception behavior differs: original={original_static_exception!r}, D={d_static_exception!r}")
        original_exception_conversion = [line for line in output.splitlines() if line.startswith("EXCEPTIONCONV:")]
        d_exception_conversion = [line for line in d_lines if line.startswith("EXCEPTIONCONV:")]
        if original_exception_conversion != ["EXCEPTIONCONV:271"] or d_exception_conversion != original_exception_conversion:
            raise SystemExit(f"Exception conversion behavior differs: original={original_exception_conversion!r}, D={d_exception_conversion!r}")
        original_primary_conversion = [line for line in output.splitlines() if line.startswith("PRIMARYCONV:")]
        d_primary_conversion = [line for line in d_lines if line.startswith("PRIMARYCONV:")]
        if original_primary_conversion != ["PRIMARYCONV:277"] or d_primary_conversion != original_primary_conversion:
            raise SystemExit(f"Primary conversion behavior differs: original={original_primary_conversion!r}, D={d_primary_conversion!r}")
        original_enum_conversion = [line for line in output.splitlines() if line.startswith("ENUMCONV:")]
        d_enum_conversion = [line for line in d_lines if line.startswith("ENUMCONV:")]
        if original_enum_conversion != ["ENUMCONV:281"] or d_enum_conversion != original_enum_conversion:
            raise SystemExit(f"Enum conversion behavior differs: original={original_enum_conversion!r}, D={d_enum_conversion!r}")
        original_expression_statement = [line for line in output.splitlines() if line.startswith("EXPRSTMT:")]
        d_expression_statement = [line for line in d_lines if line.startswith("EXPRSTMT:")]
        if original_expression_statement != ["EXPRSTMT:283"] or d_expression_statement != original_expression_statement:
            raise SystemExit(f"Expression statement behavior differs: original={original_expression_statement!r}, D={d_expression_statement!r}")
        original_sql_array = [line for line in output.splitlines() if line.startswith("SQLARRAY:")]
        d_sql_array = [line for line in d_lines if line.startswith("SQLARRAY:")]
        if original_sql_array != ["SQLARRAY:257"] or d_sql_array != original_sql_array:
            raise SystemExit(f"SQL array behavior differs: original={original_sql_array!r}, D={d_sql_array!r}")
        original_sql_map = [line for line in output.splitlines() if line.startswith("SQLMAP:")]
        d_sql_map = [line for line in d_lines if line.startswith("SQLMAP:")]
        if original_sql_map != ["SQLMAP:263"] or d_sql_map != original_sql_map:
            raise SystemExit(f"SQL map behavior differs: original={original_sql_map!r}, D={d_sql_map!r}")
        original_object_map = [line for line in output.splitlines() if line.startswith("OBJECTMAP:")]
        d_object_map = [line for line in d_lines if line.startswith("OBJECTMAP:")]
        if original_object_map != ["OBJECTMAP:83"] or d_object_map != original_object_map:
            raise SystemExit(f"Object map behavior differs: original={original_object_map!r}, D={d_object_map!r}")
        original_reference_map = [line for line in output.splitlines() if line.startswith("REFMAP:")]
        d_reference_map = [line for line in d_lines if line.startswith("REFMAP:")]
        if original_reference_map != ["REFMAP:89"] or d_reference_map != original_reference_map:
            raise SystemExit(f"Reference map behavior differs: original={original_reference_map!r}, D={d_reference_map!r}")
        original_nested_map = [line for line in output.splitlines() if line.startswith("NESTEDMAP:")]
        d_nested_map = [line for line in d_lines if line.startswith("NESTEDMAP:")]
        if original_nested_map != ["NESTEDMAP:93"] or d_nested_map != original_nested_map:
            raise SystemExit(f"Nested map behavior differs: original={original_nested_map!r}, D={d_nested_map!r}")
        original_primary_key_map = [line for line in output.splitlines() if line.startswith("PRIMARYKEYMAP:")]
        d_primary_key_map = [line for line in d_lines if line.startswith("PRIMARYKEYMAP:")]
        if original_primary_key_map != ["PRIMARYKEYMAP:97"] or d_primary_key_map != original_primary_key_map:
            raise SystemExit(f"Primary-key map behavior differs: original={original_primary_key_map!r}, D={d_primary_key_map!r}")
        original_reference_key_map = [line for line in output.splitlines() if line.startswith("REFKEYMAP:")]
        d_reference_key_map = [line for line in d_lines if line.startswith("REFKEYMAP:")]
        if original_reference_key_map != ["REFKEYMAP:101"] or d_reference_key_map != original_reference_key_map:
            raise SystemExit(f"Reference-key map behavior differs: original={original_reference_key_map!r}, D={d_reference_key_map!r}")
        original_primary_collection = [line for line in output.splitlines() if line.startswith("PRIMARYCOLL:")]
        d_primary_collection = [line for line in d_lines if line.startswith("PRIMARYCOLL:")]
        if original_primary_collection != ["PRIMARYCOLL:105"] or d_primary_collection != original_primary_collection:
            raise SystemExit(f"Primary collection identity differs: original={original_primary_collection!r}, D={d_primary_collection!r}")
        original_object_key_map = [line for line in output.splitlines() if line.startswith("OBJECTKEYMAP:")]
        d_object_key_map = [line for line in d_lines if line.startswith("OBJECTKEYMAP:")]
        if original_object_key_map != ["OBJECTKEYMAP:107"] or d_object_key_map != original_object_key_map:
            raise SystemExit(f"Object-key map behavior differs: original={original_object_key_map!r}, D={d_object_key_map!r}")
        original_deep_array = [line for line in output.splitlines() if line.startswith("DEEPARRAY:")]
        d_deep_array = [line for line in d_lines if line.startswith("DEEPARRAY:")]
        if original_deep_array != ["DEEPARRAY:111"] or d_deep_array != original_deep_array:
            raise SystemExit(f"Deep array behavior differs: original={original_deep_array!r}, D={d_deep_array!r}")
        original_matrix_map = [line for line in output.splitlines() if line.startswith("MATRIXMAP:")]
        d_matrix_map = [line for line in d_lines if line.startswith("MATRIXMAP:")]
        if original_matrix_map != ["MATRIXMAP:113"] or d_matrix_map != original_matrix_map:
            raise SystemExit(f"Matrix map behavior differs: original={original_matrix_map!r}, D={d_matrix_map!r}")
        original_map_equality = [line for line in output.splitlines() if line.startswith("MAPEQUALITY:")]
        d_map_equality = [line for line in d_lines if line.startswith("MAPEQUALITY:")]
        if original_map_equality != ["MAPEQUALITY:117"] or d_map_equality != original_map_equality:
            raise SystemExit(f"Map equality differs: original={original_map_equality!r}, D={d_map_equality!r}")
        original_nested_maps = [line for line in output.splitlines() if line.startswith("NESTEDMAPS:")]
        d_nested_maps = [line for line in d_lines if line.startswith("NESTEDMAPS:")]
        if original_nested_maps != ["NESTEDMAPS:123"] or d_nested_maps != original_nested_maps:
            raise SystemExit(f"Nested maps differ: original={original_nested_maps!r}, D={d_nested_maps!r}")
        original_multikey = [line for line in output.splitlines() if line.startswith("MULTIKEY:")]
        d_multikey = [line for line in d_lines if line.startswith("MULTIKEY:")]
        if original_multikey != ["MULTIKEY:127"] or d_multikey != original_multikey:
            raise SystemExit(f"Multiple key types differ: original={original_multikey!r}, D={d_multikey!r}")
        original_native_keys = [line for line in output.splitlines() if line.startswith("NATIVEKEY:")]
        d_native_keys = [line for line in d_lines if line.startswith("NATIVEKEY:")]
        if original_native_keys != ["NATIVEKEY:129"] or d_native_keys != original_native_keys:
            raise SystemExit(f"Native map keys differ: original={original_native_keys!r}, D={d_native_keys!r}")
        original_covariant_array = [line for line in output.splitlines() if line.startswith("COVARRAY:")]
        d_covariant_array = [line for line in d_lines if line.startswith("COVARRAY:")]
        if original_covariant_array != ["COVARRAY:131"] or d_covariant_array != original_covariant_array:
            raise SystemExit(f"Covariant arrays differ: original={original_covariant_array!r}, D={d_covariant_array!r}")
        original_covariant_map = [line for line in output.splitlines() if line.startswith("COVMAP:")]
        d_covariant_map = [line for line in d_lines if line.startswith("COVMAP:")]
        if original_covariant_map != ["COVMAP:135"] or d_covariant_map != original_covariant_map:
            raise SystemExit(f"Covariant maps differ: original={original_covariant_map!r}, D={d_covariant_map!r}")
        original_sql_conversion = [line for line in output.splitlines() if line.startswith("SQLUSERCONV:")]
        d_sql_conversion = [line for line in d_lines if line.startswith("SQLUSERCONV:")]
        if original_sql_conversion != ["SQLUSERCONV:269"] or d_sql_conversion != original_sql_conversion:
            raise SystemExit(f"SQL user conversion behavior differs: original={original_sql_conversion!r}, D={d_sql_conversion!r}")
        original_sql = [line for line in output.splitlines() if line.startswith("SQLBOOL:")]
        d_sql = [line for line in d_lines if line.startswith("SQLBOOL:")]
        if original_sql != d_sql or len(d_sql) != 40:
            raise SystemExit(f"SQL boolean formatting differs: original={original_sql!r}, D={d_sql!r}")
        for prefix, count in (("SQLINT:", 36), ("SQLINTBOOL:", 8), ("SQLDECIMAL:", 44), ("SQLDECIMALBOOL:", 16), ("SQLDECFUNC:", 24), ("SQLDECINT:", 12), ("SQLDECNAN:", 8), ("SQLSTRING:", 52), ("SQLSTRINGLEN:", 4), ("SQLSTRINGBOOL:", 24), ("SQLSEARCH:", 24), ("SQLSEARCHBOOL:", 24), ("SQLSEARCHCROSS:", 8), ("SQLCONV:", 8), ("SQLUSERCONVSQL:", 8), ("SQLTEXTEXTRA:", 60), ("SQLTEXTTEST:", 16), ("SQLGUID:", 8), ("SQLGUIDBOOL:", 8), ("SQLDATE:", 12), ("SQLDATETICKS:", 4), ("SQLDATEFUNC:", 36), ("SQLDATEPART:", 20), ("SQLDATECMP:", 336), ("SQLDATEBL:", 8), ("SQLSPAN:", 20), ("SQLSPANARITH:", 12), ("SQLSPANBOOL:", 8), ("SQLSPANPART:", 28), ("SQLSPANFUNC:", 28), ("SQLBINARY:", 4), ("SQLGEOM:", 12), ("SQLGEOMBOOL:", 24), ("SQLGEOMEMPTY:", 8), ("SQLGEOMFUNC:", 56), ("SQLGEOMMETRIC:", 32), ("SQLGEOMTEST:", 16), ("SQLGEOMTEXT:", 8), ("SQLGEOMCOUNT:", 4), ("SQLPRIMARY:", 4), ("SQLPRIMARYCHECK:", 4), ("SQLFTSBOOL:", 16), ("SQLFTSRANK:", 8)):
            original_lines = [line for line in output.splitlines() if line.startswith(prefix)]
            d_formatted = [line for line in d_lines if line.startswith(prefix)]
            if original_lines != d_formatted or len(d_formatted) != count:
                raise SystemExit(f"{prefix} formatting differs: original={original_lines!r}, D={d_formatted!r}")
            if prefix == "SQLPRIMARYCHECK:" and any(not line.endswith(":251") for line in d_formatted):
                raise SystemExit(f"SQL primary type checks failed: {d_formatted!r}")
        original_file_attributes = [line for line in output.splitlines() if line.startswith("FILEATTR:")]
        d_file_attributes = [line for line in d_lines if line.startswith("FILEATTR:")]
        if original_file_attributes != d_file_attributes or len(d_file_attributes) != 1:
            raise SystemExit(f"File attribute differs: original={original_file_attributes!r}, D={d_file_attributes!r}")
        if original_results[-56:-21] != ["221", "219", "217", "215", "211", "213", "209", "207", "203", "201", "197", "195", "193", "185", "187", "189", "181", "183", "179", "177", "171", "169", "167", "165", "163", "159", "155", "153", "151", "149", "167", "171", "251", "28", "241"]:
            raise SystemExit(f"Language fixtures failed in original Z8: {original_results[-56:-21]}")
        if original_results[-21:] != ["173", "179", "181", "191", "193", "197", "199", "211", "223", "227", "229", "233", "239", "223", "227", "229", "231", "235", "237", "239", "241"]:
            raise SystemExit(f"Basic types and control flow failed in original Z8: {original_results[-21:]}")
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
