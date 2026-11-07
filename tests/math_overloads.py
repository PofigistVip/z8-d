"""Verify Math min/max overload selection and implicit conversions."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "IntArg.bl").write_text('public class IntArg { public operator int() { return 4; } }', encoding="utf-8")
    (temp / "DecimalArg.bl").write_text('public class DecimalArg { public operator decimal() { return 4.5; } }', encoding="utf-8")
    (temp / "Probe.bl").write_text('''import org.zenframework.z8.lang.Math;
    public class Probe {
        public static int run() {
            if (Math.min(new IntArg, 3) != 3 || Math.max(3, new IntArg) != 4) return 1;
            if (Math.min(new DecimalArg, 5) != 4.5 || Math.max(3.5, new DecimalArg) != 4.5) return 2;
            if (Math.min(1, 2.5).toString() != "1" || Math.max(1.5, 2).toString() != "2") return 3;
            date moment = '29/02/2024';
            if (Math.min(moment, 0).ticks() != 0 || Math.max(0, moment) != moment) return 4;
            if (false) { date a = Math.min(moment, null); date b = Math.max(null, moment); }
            return 99;
        }
    }''', encoding="utf-8")
    executable = temp / ("math-overloads.exe" if os.name == "nt" else "math-overloads")
    subprocess.run([str(compiler), "build", str(temp), "Probe.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 99:
        raise SystemExit(f"Math overload returned an unexpected result: {result.returncode}")
    bad = temp / "Bad.bl"
    for expression in ("Math.min(null, 3)", "Math.max(3, null)", "Math.min(null, null)"):
        bad.write_text('import org.zenframework.z8.lang.Math; public class Bad { static void f() { ' + expression + '; } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted ambiguous Math overload: " + expression)
    bad.write_text('''import org.zenframework.z8.lang.Math; public class Bad {
        public operator int() { return 4; } public operator decimal() { return 4.5; }
        static void f() { Math.min(new Bad, 3); }
    }''', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted ambiguous user conversion")
print("Math min/max overloads verified")
