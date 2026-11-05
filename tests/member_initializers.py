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
    for name in ("NestedBase", "BodyInitBase", "BodyInitCases", "RefInitHolder", "RefInitBase", "RefInitDerived"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    for name, expected in (("BodyInitCases", 219), ("RefInitDerived", 221)):
        executable = temp / (name + (".exe" if os.name == "nt" else ""))
        subprocess.run([str(compiler), "build", str(source), name + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{name} failed: {result.returncode}")
print("Member initializers verified")
