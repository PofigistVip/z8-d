from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "PrimaryKeyMaps.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("primary_key_maps.exe" if os.name == "nt" else "primary_key_maps")
    subprocess.run([str(compiler), "build", str(temp), "PrimaryKeyMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 97:
        raise SystemExit(f"Primary-key map fixture failed: {result.returncode}")

    types = ("int", "decimal", "bool", "string", "guid", "binary", "datespan", "date", "geometry", "file", "exception", "encoding", "primary", "PrimaryKeyMaps", "MapFlavor", "sql_bool", "sql_int", "sql_decimal", "sql_string", "sql_guid", "sql_date", "sql_datespan", "sql_binary", "sql_geometry", "sql_primary")
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "MapFlavor.bl", temp / "MapFlavor.bl")
    body = []
    for index, value_type in enumerate(types):
        initial = " = null" if value_type == "primary" else " = MapFlavor.First" if value_type == "MapFlavor" else ""
        body.append(f"{value_type} v{index}{initial};")
        body.append(f"{value_type}[primary] m{index} = {{(1, v{index})}};")
        body.append(f"if (!m{index}.containsKey(1) || !m{index}.containsValue(v{index}) || m{index}.values().size() != 1) return 1;")
        body.append(f"{value_type}[] a{index} = {{}}; {value_type}[][primary] n{index} = {{(1, a{index})}};")
        body.append(f"if (n{index}[1].size() != 0 || n{index}.values().size() != 1) return 2;")
    (temp / "AllPrimaryKeyMaps.bl").write_text("public class AllPrimaryKeyMaps { public static int run() { " + " ".join(body) + " return 99; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllPrimaryKeyMaps.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 99:
        raise SystemExit("Primary-key map combinations failed")
print("Primary-key maps verified")
