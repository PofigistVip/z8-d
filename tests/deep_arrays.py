from pathlib import Path
import os
import shutil
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo" / "cases"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("DeepArrays.bl", "KeyItem.bl", "ValueItem.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("deep_arrays.exe" if os.name == "nt" else "deep_arrays")
    subprocess.run([str(compiler), "build", str(temp), "DeepArrays.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 111:
        raise SystemExit(f"Deep-array fixture failed: {result.returncode}")
    (temp / "ExtraDeepArrays.bl").write_text("""public class ExtraDeepArrays {
        private static int[KeyItem][] identity(int[KeyItem][] input) { return input; }
        public static int run() {
            KeyItem key = new KeyItem;
            int[KeyItem][] one = {{(key, 5)}};
            int[KeyItem][] doubled = one + identity(one);
            int result = 0;
            for (int[KeyItem] entry : doubled) result += entry[key];
            return result;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "ExtraDeepArrays.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 10:
        raise SystemExit("Deep array map typing failed")
    bad = temp / "BadDeepArrays.bl"
    for body in (
        "int[KeyItem][] a; int[ValueItem][] b; a + b;",
        "int[KeyItem][] a; int[ValueItem][] b; a = b;",
        'int[][][] numbers = {{{"wrong"}}};',
    ):
        bad.write_text("public class BadDeepArrays { public static void run() { " + body + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted an invalid deep array: {body}")
    bad.write_text("public class BadDeepArrays { static int[KeyItem][] values; }", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
    if result.returncode == 0:
        raise SystemExit("Accepted a static array with object keys")
print("Deep arrays and arrays of maps verified")
