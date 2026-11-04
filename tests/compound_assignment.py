"""Run compound assignments with side effects through the generated D program."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo" / "cases"

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "source"
    source.mkdir()
    for name in ("CompoundCases.bl", "CompoundNode.bl"):
        shutil.copy2(fixtures / name, source / name)
    executable = temp / ("compound.exe" if os.name == "nt" else "compound")
    subprocess.run([str(compiler), "build", str(source), "CompoundCases.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 251:
        raise SystemExit(f"Compound assignment fixture failed: {result.returncode}")

print("Compound assignment evaluation order verified")
