"""Verify compound assignment with user-defined object operators."""
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
    for name in ("CompoundObject", "CompoundAccumulator", "CompoundObjectHolder", "CompoundObjectCases", "CompoundMember"):
        shutil.copy2(root / "examples" / "operators" / (name + ".bl"), source)
    executable = temp / ("compound.exe" if os.name == "nt" else "compound")
    for name, expected in (("CompoundObjectCases", 205), ("CompoundMember", 223)):
        subprocess.run([str(compiler), "build", str(source), name + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{name} failed: {result.returncode}; expected {expected}")
print("Compound object assignments verified")
