from pathlib import Path
import os, shutil, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo" / "cases"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("CovariantArrays.bl", "CovariantBase.bl", "CovariantChild.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("covariant_arrays.exe" if os.name == "nt" else "covariant_arrays")
    subprocess.run([str(compiler), "build", str(temp), "CovariantArrays.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 131:
        raise SystemExit(f"Covariant array fixture failed: {result.returncode}")
    (temp / "CovariantExpressions.bl").write_text("""public class CovariantExpressions {
        private static int check(CovariantBase[] values, int n) { return values.size() + n; }
        public static int run() {
            CovariantChild[] children = {new CovariantChild};
            CovariantBase[] conditional = true ? children : null;
            int[string] numbers = {("x", 2)};
            if (conditional.size() != 1 || check(children, numbers["x"]) != 3) return 1;
            try { for (CovariantChild item : children) conditional.add(new CovariantChild); return 2; }
            catch (exception modified) {}
            return children.size() == 2 ? 133 : 3;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "CovariantExpressions.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 133:
        raise SystemExit(f"Covariant expression fixture failed: {result.returncode}")
print("Covariant object arrays verified")
