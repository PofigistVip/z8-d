from pathlib import Path
import os, shutil, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo" / "cases"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("CovariantMaps.bl", "CovariantNestedMaps.bl", "CovariantConditional.bl", "CovariantBase.bl", "CovariantChild.bl", "CovariantMiddle.bl", "CovariantLeaf.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("covariant_maps.exe" if os.name == "nt" else "covariant_maps")
    subprocess.run([str(compiler), "build", str(temp), "CovariantMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 135:
        raise SystemExit(f"Covariant map fixture failed: {result.returncode}")
    (temp / "CovariantMapExpressions.bl").write_text("""public class CovariantMapExpressions {
        private static int size(CovariantBase[string] values, int n) { return values.size() + n; }
        public static int run() {
            CovariantChild[string] children = {("child", new CovariantChild)};
            CovariantBase[string] bases = children;
            int[string] counts = {("count", 2)};
            if (size(children, counts["count"]) != 3) return 1;
            bases.add("bad", new CovariantBase);
            try { CovariantChild removed = children.remove("bad"); return 2; }
            catch (exception expected) {}
            if (children.size() != 1) return 3;
            CovariantChild[][string] childRows = {("first", {new CovariantChild})};
            CovariantBase[][string] baseRows = childRows;
            // The original BL compiler accepts this, but its Java backend does not compile it.
            for (CovariantBase[] row : baseRows.values()) row.add(new CovariantBase);
            try { CovariantChild invalid = childRows["first"][1]; return 4; }
            catch (exception expectedRow) {}
            return 137;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "CovariantMapExpressions.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 137:
        raise SystemExit(f"Covariant map expression fixture failed: {result.returncode}")
    bad = temp / "BadCovariantMaps.bl"
    for body in (
        "CovariantBase[string] a; CovariantChild[string] b; b = a;",
        "int[CovariantBase] a; int[CovariantChild] b; b = a;",
        "CovariantBase[][string] a; CovariantChild[][string] b; b = a;",
        "CovariantBase[][CovariantBase] a; CovariantChild[][CovariantChild] b; b = a;",
        "CovariantBase[int][string] a; CovariantChild[int][string] b; b = a;",
        "int[CovariantBase][string] a; int[CovariantChild][string] b; b = a;",
        "CovariantBase[CovariantBase][] a; CovariantChild[CovariantChild][] b; b = a;",
        "CovariantBase[CovariantChild] a; CovariantChild[CovariantBase] b; CovariantBase[CovariantBase] c = true ? a : b;",
    ):
        bad.write_text("public class BadCovariantMaps { public static void run() { " + body + " } }", encoding="utf-8")
        failure = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if failure.returncode == 0:
            raise SystemExit(f"Accepted invalid implicit map conversion: {body}")
print("Covariant object maps verified")
