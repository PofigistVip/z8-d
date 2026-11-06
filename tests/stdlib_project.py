"""Translate, compile and initialize the original BL standard library.

Usage: python tests/stdlib_project.py [z8-source-root]
This starts the generated modules; it does not exercise the native platform.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
if len(sys.argv) > 2:
    raise SystemExit("Usage: python tests/stdlib_project.py [z8-source-root]")
sources = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else root / "vendor/z8"
language = sources / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
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
    harness = Path(directory) / "main.d"
    harness.write_text("import z8.runtime; void main() {}\n", encoding="utf-8")
    executable = Path(directory) / ("stdlib.exe" if os.name == "nt" else "stdlib")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, modules),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=directory, check=True)
    subprocess.run([str(executable)], cwd=directory, check=True)
print(f"Generated, compiled and initialized {len(modules)} standard library D modules")
