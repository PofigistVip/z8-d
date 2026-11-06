"""Compile BL GUID-array sorting and check signed UUID order and aliasing."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/GuidArraySort.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("guid-sort.exe" if os.name == "nt" else "guid-sort")
    subprocess.run([str(compiler), "build", str(temp), "GuidArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("BL GUID-array sorting and aliasing verified")
