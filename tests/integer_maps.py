"""Compile and execute maps with integer keys and nullable entries."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = [
    (root / "examples" / "project" / "demo" / "cases" / "IntegerMaps.bl", 149),
    (root / "examples" / "project" / "demo" / "cases" / "PrimitiveMapValues.bl", 151),
    # The original BL compiler accepts indexed assignment but emits invalid Java.
    (root / "examples" / "maps" / "IntegerMapIndex.bl", 143),
    (root / "examples" / "maps" / "MapCompound.bl", 191),
]

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for index, (fixture, expected) in enumerate(fixtures):
        source = temp / f"source{index}"
        source.mkdir()
        shutil.copy2(fixture, source / fixture.name)
        executable = temp / (f"integer_maps{index}.exe" if os.name == "nt" else f"integer_maps{index}")
        subprocess.run([str(compiler), "build", str(source), fixture.stem + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{fixture.name} failed: {result.returncode}")

print("Integer-key maps verified")
