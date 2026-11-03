"""Build a generated D program and check its observable results and diagnostics."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
exe = root / ("z8d.exe" if __import__("os").name == "nt" else "z8d")
source = root / "examples" / "math.bl"
result = subprocess.run([str(exe), "compile", str(source)], capture_output=True, text=True, encoding="utf-8", check=True)

with tempfile.TemporaryDirectory() as directory:
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
    assert(!Z8_Math.m_nonzeroAndPositive(0));
    bool threw;
    try { Z8_Math.m_divide(1, 0); } catch (Exception) { threw = true; }
    assert(threw);
}
""", encoding="utf-8")
    binary = directory / ("check.exe" if __import__("os").name == "nt" else "check")
    subprocess.run(["dmd", str(generated), "-of=" + str(binary)], cwd=directory, check=True)
    subprocess.run([str(binary)], cwd=directory, check=True)
    bad = directory / "bad.bl"
    bad.write_text("class Bad { static int f() { return true; } }", encoding="utf-8")
    rejected = subprocess.run([str(exe), "compile", str(bad)], capture_output=True, text=True, encoding="utf-8")
    assert rejected.returncode == 1 and "return type mismatch" in rejected.stderr
    assert not rejected.stdout

print("Generated D program and diagnostics verified")
