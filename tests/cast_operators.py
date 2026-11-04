"""Compile and run user-defined conversion operators."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = [
    (root / "examples" / "project" / "demo" / "cases" / "CastOperators.bl", 179),
    (root / "examples" / "project" / "demo" / "cases" / "CastUnaryInt.bl", 181),
    (root / "examples" / "project" / "demo" / "cases" / "CastUnaryDecimal.bl", 183),
    (root / "examples" / "project" / "demo" / "cases" / "CastBinaryInt.bl", 185),
    (root / "examples" / "project" / "demo" / "cases" / "CastBinaryBool.bl", 187),
    (root / "examples" / "project" / "demo" / "cases" / "CastBinaryString.bl", 189),
    # Direct reference operators are accepted by BL but the Java output does not compile.
    (root / "examples" / "operators" / "BinaryConversionFallback.bl", 191),
]

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for index, (fixture, expected) in enumerate(fixtures):
        source = temp / f"source{index}"
        source.mkdir()
        shutil.copy2(fixture, source / fixture.name)
        executable = temp / (f"cast_operators{index}.exe" if os.name == "nt" else f"cast_operators{index}")
        subprocess.run([str(compiler), "build", str(source), fixture.stem + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{fixture.name} failed: {result.returncode}")

print("user-defined conversion operators verified")
