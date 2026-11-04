"""Compile and run unannotated GUID records."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")

with tempfile.TemporaryDirectory() as directory:
    executable = Path(directory) / ("records.exe" if os.name == "nt" else "records")
    subprocess.run([str(compiler), "build", str(root / "examples" / "records"),
                    "RecordUse.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 163:
        raise SystemExit(f"Record fixture failed: {result.returncode}")

print("Unannotated GUID records verified")
