"""Check Java-compatible sorting behaviour for BL object arrays."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples/project/demo/cases/ObjectArraySort.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("object-sort.exe" if os.name == "nt" else "object-sort")
    subprocess.run([str(compiler), "build", str(temp), "ObjectArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("BL object-array sorting behaviour verified")
