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
    for name in ("ObjectMaps.bl", "MapFlavor.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("object_maps.exe" if os.name == "nt" else "object_maps")
    subprocess.run([str(compiler), "build", str(temp), "ObjectMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 83:
        raise SystemExit(f"Object map fixture failed: {result.returncode}")
    bad = temp / "BadMaps.bl"
    invalid = (
        'ObjectMaps[string] objects; MapFlavor[string] colors; objects + colors;',
        'ObjectMaps[string] objects = {("x", MapFlavor.First)};',
        'MapFlavor[string] colors = {("x", new ObjectMaps)};',
        'ObjectMaps[string] objects; MapFlavor[string] colors; objects.add(colors);',
        'ObjectMaps[string] objects; objects.add("x", MapFlavor.First);',
    )
    for body in invalid:
        bad.write_text('public class BadMaps { public static void run() { ' + body + ' } }', encoding="utf-8")
        failure = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if failure.returncode == 0:
            raise SystemExit(f"Accepted an incompatible map: {body}")
print("Object and enum maps verified")
