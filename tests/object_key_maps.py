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
    for name in ("ObjectKeyMaps.bl", "KeyItem.bl", "ValueItem.bl", "MapFlavor.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("object_key_maps.exe" if os.name == "nt" else "object_key_maps")
    subprocess.run([str(compiler), "build", str(temp), "ObjectKeyMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 107:
        raise SystemExit(f"Object-key map fixture failed: {result.returncode}")

    types = ("int", "decimal", "bool", "string", "guid", "binary", "datespan", "date", "geometry", "file", "exception", "encoding", "primary", "KeyItem", "ValueItem", "MapFlavor", "sql_bool", "sql_int", "sql_decimal", "sql_string", "sql_guid", "sql_date", "sql_datespan", "sql_binary", "sql_geometry", "sql_primary")
    keys = {"KeyItem": "new KeyItem", "MapFlavor": "MapFlavor.First"}
    body = []
    for key_type, initial in keys.items():
        body.append(f"{key_type} k_{key_type} = {initial};")
    for index, value_type in enumerate(types):
        initial = " = null" if value_type == "primary" else " = MapFlavor.First" if value_type == "MapFlavor" else ""
        body.append(f"{value_type} v{index}{initial}; {value_type}[] a{index} = {{}};")
        for key_type in keys:
            name = f"m{index}_{key_type}"
            body.append(f"{value_type}[{key_type}] {name} = {{(k_{key_type}, v{index})}};")
            body.append(f"if (!{name}.containsKey(k_{key_type}) || !{name}.containsValue(v{index}) || {name}.keys().size() != 1) return 1;")
            body.append(f"{value_type}[][{key_type}] n{index}_{key_type} = {{(k_{key_type}, a{index})}};")
            body.append(f"if (n{index}_{key_type}[k_{key_type}].size() != 0) return 2;")
    (temp / "AllObjectKeyMaps.bl").write_text("public class AllObjectKeyMaps { public static int run() { " + " ".join(body) + " return 109; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllObjectKeyMaps.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 109:
        raise SystemExit("Object-key map combinations failed")
    # The Java backend erases these overloads to the same signature.
    (temp / "ObjectKeyOverloads.bl").write_text("""public class ObjectKeyOverloads {
        private static int choose(int[KeyItem] input) { return 1; }
        private static int choose(int[ValueItem] input) { return 2; }
        public static int run() {
            KeyItem key = new KeyItem;
            int[KeyItem] left = int[KeyItem] {(key, 3)};
            int[ValueItem] right;
            int[KeyItem] maybe = true ? left : null;
            int[KeyItem] alternative = maybe ?: left;
            if (alternative[key] != 3) return 1;
            for (KeyItem entry : alternative.keys()) if (entry.number != 7) return 2;
            return choose(left) * 10 + choose(right);
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "ObjectKeyOverloads.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 12:
        raise SystemExit("Object-key overload selection failed")
    bad = temp / "BadObjectKeys.bl"
    for body in (
        "int[KeyItem] left; int[ValueItem] right; left = right;",
        "int[KeyItem] left; ValueItem wrong; left.add(wrong, 1);",
        "int[KeyItem] left; int[ValueItem] right; left + right;",
        "ValueItem[KeyItem] left; KeyItem[KeyItem] right; left = right;",
        "int[UnknownKey] left;",
        "int[KeyItem] left; int[ValueItem] right; int[KeyItem] mixed = true ? left : right;",
    ):
        bad.write_text("public class BadObjectKeys { public static void run() { " + body + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted an incompatible object key: {body}")
    bad.write_text("public class BadObjectKeys { static int[KeyItem] values; }", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
    if result.returncode == 0:
        raise SystemExit("Accepted a static map with reference keys")
print("Object-key maps verified")
