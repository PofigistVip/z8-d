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
samples += ["0." + "0" * 29 + "1", "-0." + "0" * 29 + "1"]
for _ in range(300):
    digits = str(rng.randrange(1, 10)) + "".join(str(rng.randrange(10)) for _ in range(rng.randrange(15, 26)))
    value = Decimal(digits).scaleb(rng.randrange(-30, -15) - len(digits) + 1)
    samples.append(format(value, "f"))
samples += ["0." + "0" * 299 + "1", "-0." + "0" * 299 + "1"]
for _ in range(200):
    digits = str(rng.randrange(1, 10)) + "".join(str(rng.randrange(10)) for _ in range(rng.randrange(15, 26)))
    value = Decimal(digits).scaleb(rng.randrange(-300, -30) - len(digits) + 1)
    samples.append(format(value, "f"))
samples += ["1000000000000000.0", "4503599627370495.0", "4503599627370496.0",
            "9007199254740991.0", "9007199254740992.0", "-9007199254740992.0",
            "9007199254740994.0", "26919713289647808.0", "63456623512116783.0",
            "-44628848587899182.0", "99999999999999984.0", "2935601023316268.750052482272"]
for _ in range(200):
    integer = rng.randrange(10**15, 2**53 + 1)
    samples.append(("-" if rng.randrange(2) else "") + str(integer) + ".0")
for _ in range(300):
    integer = rng.randrange(10**16, 10**17 - 16)
    samples.append(("-" if rng.randrange(2) else "") + str(integer) + ".0")
for _ in range(50):
    # Some fractional spellings round to an integer double at this magnitude.
    text = str(rng.randrange(10**15, 2**53)) + ".49"
    if float(text).is_integer():
        samples.append(text)
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    methods = "\n".join(f"public static decimal value{i}() {{ return {value}; }}" for i, value in enumerate(samples))
    (source / "Probe.bl").write_text("public class Probe {\n" + methods + "\n}", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    for rejected in ("100000000000000000.0", "1000000000000000.125", "0." + "0" * 300 + "1",
                     "4012161563682237.749685808834", "1582087371762615.874997622157",
                     "3258245237057377.250097458906"):
        probe = temp / "Rejected.bl"
        probe.write_text("public class Rejected { public static decimal value() { return " + rejected + "; } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "compile", str(probe)], capture_output=True, text=True, encoding="utf-8")
        assert result.returncode and "decimal literal cannot yet be converted reliably" in result.stderr, (rejected, result.stderr)
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
    # Check a larger sample of the newly accepted integral-double range
    # without generating thousands of separate BL methods.
    random_values = [str(rng.randrange(10**15, 2**53 + 1)) + ".0" for _ in range(4096)]
    random_values += [("-" if rng.randrange(2) else "") + str(rng.randrange(10**16, 10**17 - 16)) + ".0" for _ in range(8192)]
    random_values += [f"{rng.randrange(10**15, 10**16)}e{e-15}" for e in range(-30, -15) for _ in range(500)]
    random_values += [f"{rng.randrange(10**15, 10**16)}e{e-15}" for e in range(-300, -30) for _ in range(40)]
    input_text = "\n".join(random_values) + "\n"
    java_batch = temp / "DecimalDoubleBatch.java"
    java_batch.write_text('''import java.io.*;
class DecimalDoubleBatch {
  public static void main(String[] args) throws Exception {
    BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
    for (String line; (line = input.readLine()) != null;)
      System.out.println(java.math.BigDecimal.valueOf(Double.parseDouble(line)).toPlainString());
  }
}''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java_batch)], cwd=temp, check=True)
    batch_source = temp / "batch.d"
    batch_source.write_text('''import z8.runtime;
import std.stdio : stdin, writeln;
void main() { foreach (line; stdin.byLine) writeln(z8_decimal_literal(line.idup).z8_string()); }
''', encoding="utf-8")
    batch_exe = temp / ("batch.exe" if os.name == "nt" else "batch")
    subprocess.run(["dmd", str(batch_source), *import_args(), str(runtime), "-of=" + str(batch_exe)], cwd=temp, check=True)
    expected_batch = subprocess.check_output(["java", "-cp", str(temp), "DecimalDoubleBatch"], input=input_text, text=True, encoding="utf-8").splitlines()
    actual_batch = subprocess.check_output([str(batch_exe)], input=input_text, text=True, encoding="utf-8").splitlines()
    if expected_batch != actual_batch:
        mismatch = next((i for i, (a, b) in enumerate(zip(actual_batch, expected_batch)) if a != b), None)
        raise SystemExit(f"Integral double mismatch at {mismatch}: D={actual_batch[mismatch]!r}, Java={expected_batch[mismatch]!r}" if mismatch is not None else "Integral double result count differs")
print(f"{len(samples)} BL literals and {len(random_values)} double values match Java")
