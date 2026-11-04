"""Build a generated D program and check its observable results and diagnostics."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
exe = root / ("z8d.exe" if os.name == "nt" else "z8d")
source = root / "examples" / "math.bl"
result = subprocess.run([str(exe), "compile", str(source)], capture_output=True, text=True, encoding="utf-8", check=True)

assert "import z8.runtime;" in result.stdout
assert "class Z8Object {" not in result.stdout
assert "\n    override void z8_allocate_fields() {\n        super.z8_allocate_fields();\n    }" in result.stdout
assert "\n        if (" in result.stdout and "\n            v_result =" in result.stdout

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime_lib:
    directory = Path(directory)
    generated = directory / "generated.d"
    generated.write_text(result.stdout + """
void main() {
    assert(Z8_Math.m_add(2, 3) == 5);
    assert(Z8_Math.m_calculate(3) == 15);
    assert(Z8_Math.m_calculate(-4) == -2);
    assert(Z8_Math.m_positive(0) == false);
    assert(Z8_Math.m_divide(long.min, -1) == long.min);
    assert(Z8_Math.m_remainder(long.min, -1) == 0);
    assert(Z8_Math.m_divide(-7, 3) == -2);
    assert(Z8_Math.m_remainder(-7, 3) == -1);
    assert(Z8_Math.m_minimum() == long.min);
    assert(Z8_Math.m_sumOddUntilSeven(100) == 16);
    assert(Z8_Math.m_sumOddUntilSeven(0) == 0);
    assert(Z8_Math.m_countDown(0) == 1);
    assert(Z8_Math.m_countDown(4) == 4);
    assert(Z8_Math.m_halve(16) == 4);
    assert(Z8_Math.m_incrementInLoop(0) == 3);
    assert(Z8_Math.m_divideInPlace(long.min, -1) == long.min);
    assert(Z8_Math.m_defaultValues());
    assert(Z8_Math.m_greeting("world"w) == "Hello, world!\\n"w);
    assert(Z8_Math.m_emptyString());
    assert(Z8_Math.m_unicodeLiteral() == [cast(wchar)0x0416, cast(wchar)0xD83D, cast(wchar)0xDE00]);
    assert(Z8_Math.m_unicodeLength() == 3);
    assert(Z8_Math.m_stringIsEmpty(""w));
    assert(!Z8_Math.m_stringIsEmpty("x"w));
    assert(Z8_Math.m_escapedLiteral() == [cast(wchar)65, 9, 34, 92, 39, 90]);
    assert(Z8_Math.m_nestedLoops() == 3);
    assert(Z8_Math.m_sum(Z8_Math.m_makeValues()) == 12);
    assert(Z8_Math.m_updateArray() == 22);
    assert(Z8_Math.m_literalArgument() == 8);
    assert(Z8_Math.m_emptyArray());
    assert(Z8_Math.m_mixedArrays());
    assert(Z8_Math.m_indexEvaluatedOnce() == 24);
    auto numbers = new Z8Array!long([cast(long)42]);
    assert(Z8_Math.m_elementAt(numbers, 4294967296L) == 42);
    bool badIndex;
    try { Z8_Math.m_elementAt(numbers, -1); } catch (Exception) { badIndex = true; }
    assert(badIndex);
    auto forEachValues = new Z8Array!long([cast(long)1, -5, 2, 11, 3]);
    assert(Z8_Math.m_sumWithForeach(forEachValues) == 3);
    assert(Z8_Math.m_choose(true, 0) == 1);
    assert(Z8_Math.m_choose(false, 0) == 7);
    assert(Z8_Math.m_choose(false, 2) == 5);
    bool modified;
    try { Z8_Math.m_modifyDuringIteration(); } catch (Exception) { modified = true; }
    assert(modified);
    assert(Z8_Math.m_caughtMessageLength() == 5);
    assert(Z8_Math.m_divisionOrFallback(10, 0) == 77);
    assert(Z8_Math.m_divisionOrFallback(10, 2) == 5);
    auto cleanup = new Z8Array!long();
    assert(Z8_Math.m_cleanupOnReturn(cleanup) == 1);
    assert(cleanup.z8_size() == 1 && cleanup.z8_get(0) == 5);
    assert(Z8_Math.m_caughtEmptyMessage());
    assert(Z8_Math.m_price(z8_decimal("0.10"), 2).z8_string() == "0.30"w);
    assert(Z8_Math.m_decimalRules());
    assert(Z8_Math.m_decimalText() == "12345678901234567890123456789012345679"w);
    assert(Z8_Math.m_decimalDivision() == "0.333333"w);
    assert(Z8_Math.m_mixedDecimalComparison());
    assert(Z8_Math.m_stringOperations());
    assert(Z8_Math.m_primitiveText());
    assert(Z8_Math.m_parsePrimitives());
    assert(Z8_Math.m_conversions() == "42:true:2:7"w);
    assert(z8_decimal("1.20").z8_round(1, 7).z8_string() == "1.2"w);
    bool roundingFailed;
    try { z8_decimal("1.25").z8_round(1, 7); } catch (Exception) { roundingFailed = true; }
    assert(roundingFailed);
    auto astral = [cast(wchar)0xD83D, cast(wchar)0xDE00].idup;
    auto bmp = [cast(wchar)0xE000].idup;
    assert(Z8_Math.m_compareStrings(astral, bmp));
    assert(!Z8_Math.m_nonzeroAndPositive(0));
    bool threw;
    try { Z8_Math.m_divide(1, 0); } catch (Exception) { threw = true; }
    assert(threw);
}
""", encoding="utf-8")
    binary = directory / ("check.exe" if os.name == "nt" else "check")
    subprocess.run(["dmd", str(generated), *import_args(), str(runtime_lib), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)
    bad = directory / "bad.bl"
    bad.write_text("class Bad { static int f() { return true; } }", encoding="utf-8")
    rejected = subprocess.run([str(exe), "compile", str(bad)], capture_output=True, text=True, encoding="utf-8")
    assert rejected.returncode == 1 and "return type mismatch" in rejected.stderr
    assert not rejected.stdout

    map_file = directory / "MapCheck.bl"
    map_file.write_text('''class MapCheck {
        static bool run() {
            string[string] value;
            string[string] alias = value;
            value["key"] = "first";
            alias["key"] = "second";
            if (value["key"] != "second" || value.size() != 1) return false;
            string absent = value["missing"];
            return absent == null;
        }
    }''', encoding="utf-8")
    map_source = subprocess.check_output([str(exe), "compile", str(map_file)], text=True, encoding="utf-8")
    generated.write_text(map_source + "\nvoid main() { assert(Z8_MapCheck.m_run()); }\n", encoding="utf-8")
    subprocess.run(["dmd", str(generated), *import_args(), str(runtime_lib), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)

    index_file = directory / "NullableIndex.bl"
    index_file.write_text("""class NullableIndex { static bool run() {
        int[] values = {null}; values[0] = 3; values[0] += 2;
        decimal[] decimals = {null}; decimals[0] = 1.5; decimals[0] += 2;
        return values[0] == 5 && decimals[0].toString() == "3.5";
    } }""", encoding="utf-8")
    index_source = subprocess.check_output([str(exe), "compile", str(index_file)], text=True, encoding="utf-8")
    generated.write_text(index_source + "\nvoid main() { assert(Z8_NullableIndex.m_run()); }\n", encoding="utf-8")
    subprocess.run(["dmd", str(generated), *import_args(), str(runtime_lib), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)

    generated_root = directory / "generated project"
    project = subprocess.run(
        [str(exe), "project", str(root / "examples" / "project"), str(generated_root)],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    modules = sorted(generated_root.rglob("*.d"))
    assert len(modules) == len(list((root / "examples" / "project").rglob("*.bl")))
    main_source = (generated_root / "z8gen" / "p_demo" / "p_Main.d").read_text(encoding="utf-8")
    assert "module z8gen.p_demo.p_Main;" in main_source
    assert "import z8.runtime;" in main_source and "class Z8Object {" not in main_source
    assert "import z8gen.p_demo.p_Counter;" in main_source
    assert "\n    override void z8_allocate_fields() {\n        super.z8_allocate_fields();" in main_source
    relative_root = directory / "relative project"
    subprocess.run(
        [str(exe), "project", "examples/project", str(relative_root)], cwd=root,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert {p.relative_to(generated_root): p.read_bytes() for p in modules} == {
        p.relative_to(relative_root): p.read_bytes() for p in relative_root.rglob("*.d")}
    project_class = "Z8p_" + "demo.Main".encode("utf-8").hex().upper()
    static_class = "Z8p_" + "demo.cases.StaticState".encode("utf-8").hex().upper()
    runner = directory / "project_runner.d"
    runner.write_text("module project_runner;\nimport z8gen.p_demo.p_Main;\n" +
                      "import z8gen.p_demo.p_cases.p_StaticState;\nimport core.thread : Thread;\n" +
                      "void main() { assert(" + project_class +
                      ".m_run() == 59); auto worker = new Thread({ " + static_class +
                      ".f_count = 123; }); worker.start(); worker.join(); assert(" + static_class +
                      ".f_count == 123); }\n", encoding="utf-8")
    subprocess.run(["dmd", str(runner), *map(str, modules), "-I" + str(generated_root),
                    *import_args(), str(runtime_lib), "-oq", "-od=" + str(directory),
                    "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)

    # Exercise cyclic imports and modules with the same filename in different packages.
    cycle_root = directory / "cycle project"
    (cycle_root / "pkg").mkdir(parents=True)
    (cycle_root / "pkg" / "A.bl").write_text(
        "public class A { public B next; public int value; public static int run() { A a; a.next.next.value = 4; return a.next.next.value; } }", encoding="utf-8")
    (cycle_root / "pkg" / "B.bl").write_text(
        "public class B { public A next; }", encoding="utf-8")
    (cycle_root / "pkg" / "Node.bl").write_text("public class Node {}", encoding="utf-8")
    (cycle_root / "other").mkdir()
    (cycle_root / "other" / "Node.bl").write_text("public class Node {}", encoding="utf-8")
    cycle_exe = directory / ("cycle.exe" if os.name == "nt" else "cycle")
    with_prebuilt_runtime = dict(os.environ, Z8_RUNTIME_LIB=str(runtime_lib))
    subprocess.run([str(exe), "build", str(cycle_root), "pkg.A.run", str(cycle_exe)],
                   env=with_prebuilt_runtime, check=True)
    assert runtime_lib.exists()
    assert subprocess.run([str(cycle_exe)], cwd=directory).returncode == 4

    bad_root = directory / "bad_project"
    bad_root.mkdir()
    (bad_root / "Broken.bl").write_text("import missing.Type; class Broken {}", encoding="utf-8")
    rejected = subprocess.run([str(exe), "project", str(bad_root), str(directory / "bad-output")], capture_output=True, text=True, encoding="utf-8")
    assert rejected.returncode == 1 and "Broken.bl:1:1" in rejected.stderr and "unresolved import" in rejected.stderr
    assert not rejected.stdout

    executable = directory / ("app.exe" if os.name == "nt" else "app")
    built = subprocess.run(
        [str(exe), "build", str(root / "examples" / "project"), "demo.Main.run", str(executable)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert built.returncode == 0, built.stderr
    assert subprocess.run([str(executable)], cwd=directory).returncode == 59
    for entry, expected in [("demo.cases.Arithmetic.run", 37), ("demo.cases.Text.run", 41), ("demo.cases.Flow.run", 11), ("demo.cases.DecimalArray.run", 47), ("demo.cases.Overloads.run", 53), ("demo.cases.OverloadUser.run", 53), ("demo.cases.Rounding.run", 61), ("demo.cases.PrimitiveParse.run", 67), ("demo.cases.ArrayOperations.run", 54), ("demo.cases.StaticState.run", 70), ("demo.cases.StaticUser.run", 71), ("demo.cases.InstanceOverloads.run", 81), ("demo.cases.IntegerMethods.run", 89), ("demo.cases.ArrayAdvanced.run", 97), ("demo.cases.ObjectArrays.run", 13), ("demo.cases.InheritedOverloads.run", 99), ("demo.cases.StringMap.run", 103), ("demo.cases.ObjectCasts.run", 14), ("demo.cases.NullObjects.run", 107), ("demo.cases.InstanceChecks.run", 109), ("demo.cases.ElvisObjects.run", 113), ("demo.cases.EnumCases.run", 127), ("demo.cases.NullablePrimitives.run", 131), ("demo.cases.NullableStrings.run", 137), ("demo.cases.NullableIntegers.run", 139), ("demo.cases.NullableBooleans.run", 149), ("demo.cases.NullableDecimals.run", 151), ("demo.cases.NullableArrays.run", 157), ("demo.cases.NullableObjectField.run", 163), ("demo.cases.LifecycleCases.run", 167), ("demo.cases.LifecyclePhases.run", 169)]:
        built = subprocess.run([str(exe), "build", str(root / "examples" / "project"), entry, str(executable)],
                               capture_output=True, text=True, encoding="utf-8")
        assert built.returncode == 0, built.stderr
        assert subprocess.run([str(executable)], cwd=directory).returncode == expected
    invalid_entry = subprocess.run(
        [str(exe), "build", str(root / "examples" / "project"), "demo.Twice.apply", str(executable)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert invalid_entry.returncode == 1 and "entry must be" in invalid_entry.stderr

print("Generated D programs and diagnostics verified")
