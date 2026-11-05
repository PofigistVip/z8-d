"""Test scalar member initializations in source order."""
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
    for name in ("NestedBase", "BodyInitBase", "BodyInitCases"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    executable = temp / ("member_init.exe" if os.name == "nt" else "member_init")
    subprocess.run([str(compiler), "build", str(source), "BodyInitCases.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 219:
        raise SystemExit(f"BodyInitCases failed: {result.returncode}")
print("Scalar member initializers verified")
