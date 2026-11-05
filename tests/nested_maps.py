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
    for name in ("NestedMaps.bl", "KeyItem.bl", "ValueItem.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("nested_maps.exe" if os.name == "nt" else "nested_maps")
    subprocess.run([str(compiler), "build", str(temp), "NestedMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 123:
        raise SystemExit(f"Nested map fixture failed: {result.returncode}")
    (temp / "AlternatingCollections.bl").write_text("""public class AlternatingCollections {
        public static int run() {
            int[string][][int] arrays = {(1, {{("value", 4)}})};
            if (arrays[1][0]["value"] != 4) return 1;
            int[string][int][][bool] maps = {(true, {{(2, {("value", 5)})}})};
            if (maps[true][0][2]["value"] != 5) return 2;
            KeyItem key = new KeyItem;
            ValueItem value = new ValueItem;
            ValueItem[KeyItem][int] objects = {(1, {(key, value)})};
            if (objects.values().first()[key].number != 11) return 3;
            ValueItem[KeyItem] second = objects[1];
            if (second.keys().first().number != 7) return 4;
            return 125;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AlternatingCollections.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 125:
        raise SystemExit("Alternating collections failed")
    bad = temp / "BadNestedMaps.bl"
    for body in (
        "int[string][int] a; int[string][bool] b; a = b;",
        "ValueItem[KeyItem][int] a; KeyItem[KeyItem][int] b; a = b;",
        "int[KeyItem][ValueItem] values;",
    ):
        bad.write_text("public class BadNestedMaps { public static void run() { " + body + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted an invalid or unsupported nested map: {body}")
print("Nested maps verified")
