"""Locate the pinned DUB ldap package for hosts built directly with DMD."""
from pathlib import Path
import subprocess

VERSION = "0.4.0"


def source(root):
    root = Path(root).resolve()
    source_file = root / ".dub/packages/ldap" / VERSION / "ldap/source/ldap.d"
    if not source_file.is_file():
        subprocess.run(["dub", "fetch", "ldap@" + VERSION, "--cache=local"], cwd=root, check=True)
    if not source_file.is_file():
        raise RuntimeError("DUB did not provide the pinned ldap package: " + str(source_file))
    return source_file
