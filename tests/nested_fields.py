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
    for name in ("NestedBase", "NestedOwner", "NestedLocalCases", "MemberBase", "MemberMid", "MemberLeaf", "MemberOwn"):
        shutil.copy2(root / "examples" / "project" / "demo" / "cases" / (name + ".bl"), source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    modules = list(generated.rglob("*.d"))
    if len(modules) != 7:
        raise SystemExit(f"Expected one module per source, got {len(modules)}")
    for name, expected in (("NestedOwner", 207), ("NestedLocalCases", 209), ("MemberLeaf", 211), ("MemberOwn", 213)):
        executable = temp / (name + (".exe" if os.name == "nt" else ""))
        subprocess.run([str(compiler), "build", str(source), name + ".run", str(executable)], check=True)
        result = subprocess.run([str(executable)])
        if result.returncode != expected:
            raise SystemExit(f"{name} failed: {result.returncode}")
print("Nested specializations and captures verified")
