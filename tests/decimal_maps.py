"""Compile and run decimal-keyed maps and indexed assignments."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = [
    (root / "examples" / "project" / "demo" / "cases" / "DecimalMaps.bl", 159),
    # Indexed assignment is accepted by BL but the original Java output is invalid.
    (root / "examples" / "maps" / "DecimalMapIndex.bl", 161),
]

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for index, (fixture, expected) in enumerate(fixtures):
        source = temp / f"source{index}"
        source.mkdir()
        shutil.copy2(fixture, source / fixture.name)
        executable = temp / (f"decimal_maps{index}.exe" if os.name == "nt" else f"decimal_maps{index}")
        subprocess.run([str(compiler), "build", str(source), fixture.stem + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{fixture.name} failed: {result.returncode}")

print("decimal-keyed maps verified")
