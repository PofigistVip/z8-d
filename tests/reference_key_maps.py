from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "ReferenceKeyMaps.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("reference_key_maps.exe" if os.name == "nt" else "reference_key_maps")
    subprocess.run([str(compiler), "build", str(temp), "ReferenceKeyMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 101:
        raise SystemExit(f"Reference-key map fixture failed: {result.returncode}")

    types = ("int", "decimal", "bool", "string", "guid", "binary", "datespan", "date", "geometry", "file", "exception", "encoding", "primary", "ReferenceKeyMaps", "MapFlavor", "sql_bool", "sql_int", "sql_decimal", "sql_string", "sql_guid", "sql_date", "sql_datespan", "sql_binary", "sql_geometry", "sql_primary")
    keys = {"date": "'29/02/2024'", "datespan": "'1 02:03:04'", "binary": "'1, 2'", "geometry": None, "file": '"sample.txt"'}
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "MapFlavor.bl", temp / "MapFlavor.bl")
    body = []
    for key_type, initial in keys.items():
        body.append(f"{key_type} k_{key_type}" + (f" = {initial};" if initial else ";"))
    for index, value_type in enumerate(types):
        initial = " = null" if value_type == "primary" else " = MapFlavor.First" if value_type == "MapFlavor" else ""
        body.append(f"{value_type} v{index}{initial}; {value_type}[] a{index} = {{}};")
        for key_type in keys:
            name = f"m{index}_{key_type}"
            body.append(f"{value_type}[{key_type}] {name} = {{(k_{key_type}, v{index})}};")
            body.append(f"if (!{name}.containsKey(k_{key_type}) || !{name}.containsValue(v{index}) || {name}.keys().size() != 1) return 1;")
            body.append(f"{value_type}[][{key_type}] n{index}_{key_type} = {{(k_{key_type}, a{index})}};")
            body.append(f"if (n{index}_{key_type}[k_{key_type}].size() != 0) return 2;")
    (temp / "AllReferenceKeyMaps.bl").write_text("public class AllReferenceKeyMaps { public static int run() { " + " ".join(body) + " return 103; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllReferenceKeyMaps.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 103:
        raise SystemExit("Reference-key map combinations failed")
    bad = temp / "BadReferenceKeyMap.bl"
    for declaration in ('string[date] values = {(1, "value")};', 'string[file] values = {("path", "value")};'):
        bad.write_text("public class BadReferenceKeyMap { public static void run() { " + declaration + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted a conversion in a map key initializer: {declaration}")
print("Reference-key maps verified")
