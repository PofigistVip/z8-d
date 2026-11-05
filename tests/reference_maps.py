from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "ReferenceMaps.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("reference_maps.exe" if os.name == "nt" else "reference_maps")
    subprocess.run([str(compiler), "build", str(temp), "ReferenceMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 89:
        raise SystemExit(f"Reference map fixture failed: {result.returncode}")

    # Instantiate every supported reference-value/key combination in generated D.
    keys = {"string": '"key"', "int": "1", "guid": "'00000000-0000-0000-0000-000000000001'", "bool": "true", "decimal": "1.5"}
    values = {"binary": "'1, 2'", "datespan": "'1 02:03:04'", "date": "'29/02/2024'", "geometry": None, "file": '"sample.txt"', "exception": '"message"', "encoding": "encoding.UTF8"}
    body = []
    for value_type, initial in values.items():
        body.append(f"{value_type} v_{value_type}" + (f" = {initial};" if initial else ";"))
        for key_type, key in keys.items():
            name = f"m_{value_type}_{key_type}"
            body.append(f"{value_type}[{key_type}] {name} = {{({key}, v_{value_type})}};")
            body.append(f"if (!{name}.containsKey({key}) || {name}.values().size() != 1 || !{name}.containsValue(v_{value_type})) return 1;")
            body.append(f"{name}.remove({key}); if (!{name}.isEmpty()) return 2;")
    (temp / "AllReferenceMaps.bl").write_text('import org.zenframework.z8.lang.encoding; public class AllReferenceMaps { public static int run() { ' + " ".join(body) + ' return 91; } }', encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllReferenceMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 91:
        raise SystemExit(f"Reference map combinations failed: {result.returncode}")
    bad = temp / "BadReferenceMap.bl"
    for declaration in ('date[string] values = {("x", 1)};', 'file[string] values = {("x", "path")};', 'exception[string] values = {("x", "message")};'):
        bad.write_text("public class BadReferenceMap { public static void run() { " + declaration + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted a conversion in a map initializer: {declaration}")
print("Reference-type maps verified")
