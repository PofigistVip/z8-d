"""Compile and run object conversion operators in a multi-file project."""
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
    for name in ("ConversionTarget", "ObjectConversion", "ConversionDerived"):
        shutil.copy2(fixtures / (name + ".bl"), source)
    for name, expected in (("ObjectConversion", 193), ("ConversionDerived", 195)):
        executable = temp / (name + (".exe" if os.name == "nt" else ""))
        subprocess.run([str(compiler), "build", str(source), name + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{name} failed: {result.returncode}")
print("Object conversion operators verified")
