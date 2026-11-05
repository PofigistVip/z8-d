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
    for name in ("NestedMapArrays.bl", "MapFlavor.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("nested_maps.exe" if os.name == "nt" else "nested_maps")
    subprocess.run([str(compiler), "build", str(temp), "NestedMapArrays.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 93:
        raise SystemExit(f"Nested map fixture failed: {result.returncode}")

    # Cover every supported element type and key in a nested array map.
    values = ("int", "decimal", "bool", "string", "guid", "binary", "datespan", "date", "geometry", "file", "exception", "encoding", "primary", "NestedMapArrays", "MapFlavor", "sql_bool", "sql_int", "sql_decimal", "sql_string", "sql_guid", "sql_date", "sql_datespan", "sql_binary", "sql_geometry", "sql_primary")
    keys = {"string": '"key"', "int": "1", "guid": "'00000000-0000-0000-0000-000000000001'", "bool": "true", "decimal": "1.5"}
    body = []
    for index, value_type in enumerate(values):
        body.append(f"{value_type}[] a{index} = {{}};")
        for key_type, key in keys.items():
            name = f"m{index}_{key_type}"
            body.append(f"{value_type}[][{key_type}] {name} = {{({key}, a{index})}};")
            body.append(f"if (!{name}.containsValue(a{index}) || {name}[{key}].size() != 0 || {name}.values().first().size() != 0) return 1;")
    (temp / "AllNestedMaps.bl").write_text("public class AllNestedMaps { public static int run() { " + " ".join(body) + " return 95; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllNestedMaps.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 95:
        raise SystemExit("Nested map combinations failed")
    bad = temp / "BadNestedMap.bl"
    for body in ('int[][string] values = {("x", {"wrong"})};', 'NestedMapArrays[][string] values = {("x", {MapFlavor.First})};'):
        bad.write_text("public class BadNestedMap { public static void run() { " + body + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted an invalid nested map: {body}")
print("Maps of arrays verified")
