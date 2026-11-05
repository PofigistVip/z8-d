"""Check enum instanceof, including null, in generated D."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("ProbeEnum", "ProbeOther", "EnumInstanceOf"):
        shutil.copy2(root / "examples" / "operators" / (name + ".bl"), temp)
    executable = temp / ("enum-case.exe" if os.name == "nt" else "enum-case")
    subprocess.run([str(compiler), "build", str(temp), "EnumInstanceOf.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 221:
        raise SystemExit(f"Enum instanceof failed: {result.returncode}")
print("Enum instanceof verified")
