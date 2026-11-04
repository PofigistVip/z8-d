"""Compile and run collection initializers, including map evaluation order."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "MapInitializers.bl"

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "source"
    source.mkdir()
    shutil.copy2(fixture, source / fixture.name)
    executable = temp / ("map_initializers.exe" if os.name == "nt" else "map_initializers")
    subprocess.run([str(compiler), "build", str(source), "MapInitializers.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 171:
        raise SystemExit(f"Map initializer fixture failed: {result.returncode}")

print("Map and nested collection initializers verified")
