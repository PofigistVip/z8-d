"""Check priority operators in generated D when the Java backend cannot run them."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("PriorityValue", "PriorityCases"):
        shutil.copy2(root / "examples" / "operators" / (name + ".bl"), temp)
    executable = temp / ("priority.exe" if os.name == "nt" else "priority")
    subprocess.run([str(compiler), "build", str(temp), "PriorityCases.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 219:
        raise SystemExit(f"Priority operator failed: {result.returncode}")
print("Priority operator verified")
