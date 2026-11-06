"""Compare high-precision BL decimal literals with Java double conversion."""
from decimal import Decimal
from pathlib import Path
import os
import random
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
samples = [
    "0.12345678901234567890",
    "0.0000000000093974433296972762664",
    "7413.04345526901443",
    "64061528025.674158375",
    "0.000000004442825982198500806623058",
    "0.0048567173794069742213338242",
    "0.3629450702930574757126",
]
rng = random.Random(9012)
for _ in range(300):
    digits = str(rng.randrange(1, 10)) + "".join(str(rng.randrange(10)) for _ in range(rng.randrange(15, 26)))
    value = Decimal(digits).scaleb(rng.randrange(-14, 14) - len(digits) + 1)
    text = format(value, "f")
    samples.append(text if "." in text else text + ".0")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    methods = "\n".join(f"public static decimal value{i}() {{ return {value}; }}" for i, value in enumerate(samples))
    (source / "Probe.bl").write_text("public class Probe {\n" + methods + "\n}", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "DecimalLiteralOracle.java"
    java_lines = "\n".join(f"System.out.println(java.math.BigDecimal.valueOf({value}).toPlainString());" for value in samples)
    java.write_text("class DecimalLiteralOracle { public static void main(String[] args) {\n" + java_lines + "\n}}", encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "DecimalLiteralOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    d_lines = "\n".join(f"writeln(z8_optional_require(P.m_value{i}()).z8_string());" for i in range(len(samples)))
    harness.write_text("""
import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
import core.stdc.locale : setlocale, LC_NUMERIC;
void main() {
    alias P = Z8p_50726F6265;
    version (Windows) setlocale(LC_NUMERIC, "Russian_Russia.1251");
    else setlocale(LC_NUMERIC, "de_DE.UTF-8");
""" + d_lines + "\n}", encoding="utf-8")
    executable = temp / ("decimal-literals.exe" if os.name == "nt" else "decimal-literals")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    for i, (observed, reference) in enumerate(zip(actual, expected)):
        if observed != reference:
            raise SystemExit(f"Literal {samples[i]}: D={observed!r}, Java={reference!r}")
    if len(actual) != len(expected):
        raise SystemExit(f"Expected {len(expected)} values, got {len(actual)}")
print(f"{len(samples)} high-precision BL decimal literals match Java")
