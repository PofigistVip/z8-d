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
    # Indexed assignment is a z8-d extension; the Java backend does not compile it.
    (temp / "NestedArrayAssignment.bl").write_text("""public class NestedArrayAssignment {
        public static int run() {
            CovariantChild[][] children = {{new CovariantChild}};
            CovariantBase[][] bases = children;
            CovariantBase[] replacement = {new CovariantBase};
            bases[0] = replacement;
            if (bases[0].size() != 1 || children[0].size() != 1) return 1;
            try { CovariantChild invalid = children[0][0]; return 2; }
            catch (exception expected) {}
            CovariantChild[] valid = {new CovariantChild};
            children[0] = valid;
            if (bases[0][0].value != 11 || children[0][0].extra != 7) return 3;
            return 139;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "NestedArrayAssignment.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 139:
        raise SystemExit(f"Nested array assignment failed: {result.returncode}")
    bad = temp / "BadCovariantArrays.bl"
    for body in (
        "CovariantBase[][] a; CovariantChild[][] b; b = a;",
        "CovariantBase[][][] a; CovariantChild[][] b; a = b;",
    ):
        bad.write_text("public class BadCovariantArrays { public static void run() { " + body + " } }", encoding="utf-8")
        failure = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if failure.returncode == 0:
            raise SystemExit(f"Accepted invalid array conversion: {body}")
print("Covariant object arrays verified")
