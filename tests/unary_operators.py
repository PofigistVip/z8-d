"""Compile and run user-defined unary operators."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = [
    (root / "examples" / "project" / "demo" / "cases" / "UnaryOperators.bl", 167),
    (root / "examples" / "project" / "demo" / "cases" / "UnaryComplement.bl", 169),
    (root / "examples" / "project" / "demo" / "cases" / "UnaryPlus.bl", 177),
    # The original Java backend gives these two operators the same method name.
    (root / "examples" / "operators" / "UnaryCombined.bl", 173),
]

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for index, (fixture, expected) in enumerate(fixtures):
        source = temp / f"source{index}"
        source.mkdir()
        shutil.copy2(fixture, source / fixture.name)
        executable = temp / (f"unary_operators{index}.exe" if os.name == "nt" else f"unary_operators{index}")
        subprocess.run([str(compiler), "build", str(source), fixture.stem + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{fixture.name} failed: {result.returncode}")

print("user-defined unary operators verified")
