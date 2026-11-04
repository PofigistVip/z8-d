"""Test binary operator selection by inheritance distance."""
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
    for name in ("OperatorRoot", "OperatorMiddle", "OperatorLeaf", "OperatorDistance"):
        shutil.copy2(root / "examples" / "operators" / (name + ".bl"), source)
    executable = temp / ("operator_distance.exe" if os.name == "nt" else "operator_distance")
    subprocess.run([str(compiler), "build", str(source), "OperatorDistance.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 199:
        raise SystemExit(f"OperatorDistance failed: {result.returncode}")
print("Binary operator inheritance distance verified")
