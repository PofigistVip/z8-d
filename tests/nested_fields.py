"""Compile and run field specializations in one module per BL source."""
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
    for name in ("NestedBase", "NestedOwner"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    modules = list(generated.rglob("*.d"))
    if len(modules) != 2:
        raise SystemExit(f"Expected one module per source, got {len(modules)}")
    executable = temp / ("nested.exe" if os.name == "nt" else "nested")
    subprocess.run([str(compiler), "build", str(source), "NestedOwner.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 207:
        raise SystemExit(f"NestedOwner failed: {result.returncode}")
print("Nested field specializations verified")
