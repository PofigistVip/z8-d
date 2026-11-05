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
    for name in ("MultipleObjectKeys.bl", "KeyItem.bl", "ValueItem.bl", "MapFlavor.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("multiple_object_keys.exe" if os.name == "nt" else "multiple_object_keys")
    subprocess.run([str(compiler), "build", str(temp), "MultipleObjectKeys.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 127:
        raise SystemExit(f"Multiple object keys failed: {result.returncode}")
    (temp / "MultiKeyValues.bl").write_text("""public class MultiKeyValues {
        public static int run() {
            KeyItem inner = new KeyItem; ValueItem outer = new ValueItem;
            ValueItem[KeyItem][ValueItem] values = {(outer, {(inner, outer)})};
            ValueItem[KeyItem] extracted = values.values().first();
            if (!values.containsValue(extracted) || values.add(outer, extracted)[inner].number != 11) return 1;
            return extracted[inner].number;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "MultiKeyValues.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 11:
        raise SystemExit("Nested map values lost their inner key type")
    bad = temp / "BadMultipleKeys.bl"
    for body in (
        "int[KeyItem][ValueItem] a; int[ValueItem][KeyItem] b; a = b;",
        "int[KeyItem][ValueItem] a; KeyItem wrong; a[wrong];",
        "int[MapFlavor][KeyItem] a; int[KeyItem][MapFlavor] b; a + b;",
        "int[KeyItem][ValueItem] a; int[ValueItem] wrong; ValueItem outer; a.add(outer, wrong);",
    ):
        bad.write_text("public class BadMultipleKeys { public static void run() { " + body + " } }", encoding="utf-8")
        failure = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if failure.returncode == 0:
            raise SystemExit(f"Accepted incompatible nested keys: {body}")
print("Multiple object key types verified")
