"""Compile and run references using fully qualified BL type names."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo"

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    demo = temp / "source" / "demo"
    cases = demo / "cases"
    cases.mkdir(parents=True)
    shutil.copy2(fixtures / "Counter.bl", demo / "Counter.bl")
    for name in ("QualifiedBase.bl", "QualifiedChild.bl", "QualifiedNames.bl"):
        shutil.copy2(fixtures / "cases" / name, cases / name)
    executable = temp / ("qualified.exe" if os.name == "nt" else "qualified")
    subprocess.run([str(compiler), "build", str(temp / "source"),
                    "demo.cases.QualifiedNames.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 167:
        raise SystemExit(f"Qualified type fixture failed: {result.returncode}")

print("Qualified type references verified")
