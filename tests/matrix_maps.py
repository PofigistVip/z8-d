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
    for name in ("MatrixMaps.bl", "KeyItem.bl", "ValueItem.bl", "MapFlavor.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("matrix_maps.exe" if os.name == "nt" else "matrix_maps")
    subprocess.run([str(compiler), "build", str(temp), "MatrixMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 113:
        raise SystemExit(f"Matrix map fixture failed: {result.returncode}")
    types = ("int", "decimal", "bool", "string", "guid", "binary", "datespan", "date", "geometry", "file", "exception", "encoding", "primary", "KeyItem", "ValueItem", "MapFlavor", "sql_bool", "sql_int", "sql_decimal", "sql_string", "sql_guid", "sql_date", "sql_datespan", "sql_binary", "sql_geometry", "sql_primary")
    keys = {"string": '"key"', "int": "1", "KeyItem": "k", "MapFlavor": "MapFlavor.First"}
    body = ["KeyItem k = new KeyItem;"]
    for index, value_type in enumerate(types):
        body.append(f"{value_type}[][] a{index} = {{}};")
        for key_type, key in keys.items():
            name = f"m{index}_{key_type}"
            body.append(f"{value_type}[][][{key_type}] {name} = {{({key}, a{index})}};")
            body.append(f"if (!{name}.containsKey({key}) || !{name}.containsValue(a{index}) || {name}.values().first().size() != 0) return 1;")
    (temp / "AllMatrixMaps.bl").write_text("public class AllMatrixMaps { public static int run() { " + " ".join(body) + " return 115; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllMatrixMaps.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 115:
        raise SystemExit("Matrix map combinations failed")
    bad = temp / "BadMatrixMaps.bl"
    for body in (
        "ValueItem[][][KeyItem] a; KeyItem[][][KeyItem] b; a = b;",
        "ValueItem[][][KeyItem] a; ValueItem[][][ValueItem] b; a = b;",
        'int[][][string] values = {("x", {{"wrong"}})};',
    ):
        bad.write_text("public class BadMatrixMaps { public static void run() { " + body + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted an invalid matrix map: {body}")
print("Maps of matrices verified")
