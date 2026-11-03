"""Compare implemented decimal operations with the original Java BigDecimal rules."""
from pathlib import Path
import os
import random
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
exe = root / ("z8d.exe" if os.name == "nt" else "z8d")
generated = subprocess.run(
    [str(exe), "compile", str(root / "examples" / "math.bl")],
    capture_output=True, text=True, encoding="utf-8", check=True,
).stdout

d_main = r'''
import std.stdio : writeln;
void main() {
    writeln(z8_decimal("0.09").z8_string());
    writeln(z8_decimal("1.20e+3").z8_string());
    writeln(z8_decimal("0.000").z8_string());
    writeln(z8_decimal("0.0e+5").z8_string());
    writeln(z8_decimal("12345678901234567890123456789012345678.91").z8_string());
    writeln(z8_decimal("-12345678901234567890123456789012345678.91").z8_string());
    writeln((z8_decimal("0.10") + z8_decimal("0.20")).z8_string());
    writeln((z8_decimal("100.0") - z8_decimal("0.009")).z8_string());
    writeln((z8_decimal("12345678901234567890.12") * z8_decimal("9876543210.9")).z8_string());
    writeln((z8_decimal("1.0") / z8_decimal("3.0")).z8_string());
    writeln((z8_decimal("1.00") / z8_decimal("2.0")).z8_string());
    writeln((z8_decimal("-2.0") / z8_decimal("3.0")).z8_string());
    writeln((z8_decimal("12.5") / z8_decimal("0.3")).z8_string());
    writeln((z8_decimal("0.00") / z8_decimal("2.0")).z8_string());
    writeln((z8_decimal("5.00") % z8_decimal("2.0")).z8_string());
    writeln(z8_decimal("1.0") == z8_decimal("1.00"));
    writeln(z8_decimal("1.0") <= z8_decimal("1.00"));
    writeln(Z8_Math.m_mixedDecimalComparison());
    // RANDOM_CASES
}
'''
java_main = r'''
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.math.MathContext;
public class DecimalOracle {
    static BigDecimal cap(BigDecimal n) {
        return n.precision() > 38 ? n.setScale(n.scale() - (n.precision() - 38), RoundingMode.CEILING) : n;
    }
    static BigDecimal n(String text) { return cap(new BigDecimal(text)); }
    static BigDecimal div(BigDecimal a, BigDecimal b) {
        return cap(a.divide(b, new MathContext(a.precision() + (int)Math.ceil(10.0 * b.precision() / 3.0))));
    }
    public static void main(String[] args) {
        System.out.println(n("0.09").toPlainString());
        System.out.println(n("1.20e+3").toPlainString());
        System.out.println(n("0.000").toPlainString());
        System.out.println(n("0.0e+5").toPlainString());
        System.out.println(n("12345678901234567890123456789012345678.91").toPlainString());
        System.out.println(n("-12345678901234567890123456789012345678.91").toPlainString());
        System.out.println(cap(n("0.10").add(n("0.20"))).toPlainString());
        System.out.println(cap(n("100.0").subtract(n("0.009"))).toPlainString());
        System.out.println(cap(n("12345678901234567890.12").multiply(n("9876543210.9"))).toPlainString());
        System.out.println(div(n("1.0"), n("3.0")).toPlainString());
        System.out.println(div(n("1.00"), n("2.0")).toPlainString());
        System.out.println(div(n("-2.0"), n("3.0")).toPlainString());
        System.out.println(div(n("12.5"), n("0.3")).toPlainString());
        System.out.println(div(n("0.00"), n("2.0")).toPlainString());
        System.out.println(cap(n("5.00").remainder(n("2.0"))).toPlainString());
        System.out.println(n("1.0").equals(n("1.00")));
        System.out.println(n("1.0").compareTo(n("1.00")) <= 0);
        System.out.println(n("1.0").compareTo(BigDecimal.ONE) >= 0 && !(n("1.0").compareTo(BigDecimal.ONE) > 0)
            && n("1.0").compareTo(BigDecimal.ONE) <= 0 && !(n("1.0").compareTo(BigDecimal.ONE) < 0));
        // RANDOM_CASES
    }
}
'''

rng = random.Random(1701)
def number():
    integer_digits = rng.randrange(1, 42)
    fraction_digits = rng.randrange(1, 13)
    integer = "".join(str(rng.randrange(10)) for _ in range(integer_digits))
    fraction = "".join(str(rng.randrange(10)) for _ in range(fraction_digits))
    return ("-" if rng.randrange(2) else "") + integer + "." + fraction

d_lines, java_lines, cases = [], [], []
for _ in range(80):
    a, b = number(), number()
    if not any(c in "123456789" for c in b):
        b = "1.0"
    for symbol, method in [("+", "add"), ("-", "subtract"), ("*", "multiply"), ("%", "remainder")]:
        cases.append((a, symbol, b))
        d_lines.append(f'writeln((z8_decimal("{a}") {symbol} z8_decimal("{b}")).z8_string());')
        java_lines.append(f'System.out.println(cap(n("{a}").{method}(n("{b}"))).toPlainString());')
    d_lines.append(f'writeln((z8_decimal("{a}") / z8_decimal("{b}")).z8_string());')
    cases.append((a, "/", b))
    java_lines.append(f'System.out.println(div(n("{a}"), n("{b}")).toPlainString());')
def safe_literal():
    integer = str(rng.randrange(0, 10**9))
    fraction = f"{rng.randrange(0, 100000):05d}"
    return ("-" if rng.randrange(2) else "") + integer + "." + fraction

for literal in ["1.00", "0.10", "0.0001", "1.0e+10", "0.0"] + [safe_literal() for _ in range(80)]:
    cases.append((literal, "literal", ""))
    d_lines.append(f'writeln(z8_decimal_literal("{literal}").z8_string());')
    java_lines.append(f'System.out.println(cap(BigDecimal.valueOf(Double.parseDouble("{literal}"))).toPlainString());')
d_main = d_main.replace("// RANDOM_CASES", "\n".join(d_lines))
java_main = java_main.replace("// RANDOM_CASES", "\n".join(java_lines))

with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    dfile = directory / "decimal_check.d"
    jfile = directory / "DecimalOracle.java"
    binary = directory / ("decimal_check.exe" if os.name == "nt" else "decimal_check")
    dfile.write_text(generated + d_main, encoding="utf-8")
    jfile.write_text(java_main, encoding="utf-8")
    subprocess.run(["dmd", str(dfile), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run(["javac", "-source", "8", "-target", "8", str(jfile)], cwd=directory, check=True)
    d_output = subprocess.check_output([str(binary)], cwd=directory, text=True, encoding="utf-8")
    java_output = subprocess.check_output(["java", "-cp", str(directory), "DecimalOracle"], cwd=directory, text=True, encoding="utf-8")
    d_results, java_results = d_output.splitlines(), java_output.splitlines()
    assert len(d_results) == len(java_results)
    for i, (actual, expected) in enumerate(zip(d_results, java_results)):
        detail = cases[i - 18] if i >= 18 else "fixed"
        assert actual == expected, f"case {i} {detail}: D={actual}, Java={expected}"

print("Decimal results match Java BigDecimal reference")
