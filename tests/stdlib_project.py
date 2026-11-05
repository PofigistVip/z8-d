"""Translate and compile the complete original BL standard library.

Usage: python tests/stdlib_project.py <original-z8-root>
This verifies generated D modules; it does not link or run the native platform.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/stdlib_project.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    generated = Path(directory) / "generated"
    subprocess.run([str(compiler), "project", str(language), str(generated)], check=True)
    modules = sorted(generated.rglob("*.d"))
    if not modules:
        raise SystemExit("No D modules generated")
    objects = Path(directory) / "objects"
    objects.mkdir()
    subprocess.run(["dmd", "-c", "-oq", "-od=" + str(objects), "-I" + str(generated), *import_args(), *map(str, modules)],
                   cwd=directory, check=True)
    object_files = list(objects.glob("*.obj" if os.name == "nt" else "*.o"))
    if len(object_files) != len(modules):
        raise SystemExit(f"Expected {len(modules)} object files; got {len(object_files)}")
print(f"Generated and compiled {len(modules)} standard library D modules")
