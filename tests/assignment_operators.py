"""Compile and execute user-defined assignment operators."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "source"
    source.mkdir()
    for name in ("AssignmentValue", "AssignmentHolder"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    executable = temp / ("assign.exe" if os.name == "nt" else "assign")
    subprocess.run([str(compiler), "build", str(source), "AssignmentValue.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 201:
        raise SystemExit(f"AssignmentValue failed: {result.returncode}")
print("Assignment operators verified")
