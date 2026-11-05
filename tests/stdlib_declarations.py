"""Compile selected unmodified native declarations from the original Z8 library.

Usage: python tests/stdlib_declarations.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/stdlib_declarations.py <original-z8-root>")

root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang" / "src" / "bl"
declarations = (
    "org/zenframework/z8/base/crypto/MD5.bl",
    "org/zenframework/z8/base/crypto/Base34.bl",
    "org/zenframework/z8/base/crypto/Digest.bl",
    "org/zenframework/z8/base/file/FileHandler.bl",
    "org/zenframework/z8/base/security/LoginParameters.bl",
    "org/zenframework/z8/base/table/RecordLock.bl",
)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    for name in declarations:
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(language / name, destination)
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    modules = list(generated.rglob("*.d"))
    if len(modules) != len(declarations):
        raise SystemExit(f"Expected {len(declarations)} D modules; got {len(modules)}")
    subprocess.run(["dmd", "-c", "-o-", "-I" + str(generated), *import_args(),
                    *map(str, modules)], cwd=temp, check=True)
print(f"Compiled {len(declarations)} unmodified native standard-library declarations to D")
