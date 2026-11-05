"""Verify specialization of an imported inherited field."""
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
    for relative in ("demo/cases/NestedBase.bl", "demo/cases/RemoteMemberDerived.bl", "demo/util/RemoteMemberBase.bl"):
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / "examples" / "project" / relative, destination)
    executable = temp / ("nested.exe" if os.name == "nt" else "nested")
    subprocess.run([str(compiler), "build", str(source), "demo.cases.RemoteMemberDerived.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 215:
        raise SystemExit(f"RemoteMemberDerived failed: {result.returncode}")
print("Cross-package field specializations verified")
