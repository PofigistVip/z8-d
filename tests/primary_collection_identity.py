from pathlib import Path
import os
import shutil
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "PrimaryCollectionIdentity.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("primary_identity.exe" if os.name == "nt" else "primary_identity")
    subprocess.run([str(compiler), "build", str(temp), "PrimaryCollectionIdentity.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 105:
        raise SystemExit(f"Primary collection identity failed: {result.returncode}")
print("Primary collection identity verified")
