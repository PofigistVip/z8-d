"""Compile and run user-defined binary operators."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = [
    (root / "examples" / "operators" / "BinaryOperators.bl", 175),
]

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for index, (fixture, expected) in enumerate(fixtures):
        source = temp / f"source{index}"
        source.mkdir()
        shutil.copy2(fixture, source / fixture.name)
        executable = temp / (f"binary_operators{index}.exe" if os.name == "nt" else f"binary_operators{index}")
        subprocess.run([str(compiler), "build", str(source), fixture.stem + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{fixture.name} failed: {result.returncode}")

print("user-defined binary operators verified")
