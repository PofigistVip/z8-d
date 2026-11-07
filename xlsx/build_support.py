"""Link and deploy the optional OpenXLSX provider in a D host."""
from pathlib import Path
import os
import shutil
import sys


def link_args(root, directory):
    """Return DMD arguments and the shared library to deploy beside the host."""
    root = Path(root).resolve()
    directory = Path(directory).resolve()
    source = root / "xlsx/source"
    if os.name == "nt":
        shared, import_library = directory / "z8_openxlsx.dll", directory / "z8_openxlsx.lib"
        native_args = [str(import_library)]
    elif sys.platform.startswith("linux"):
        shared = directory / "libz8_openxlsx.so"
        import_library = shared
        native_args = ["-L-L" + str(directory), "-L-lz8_openxlsx", "-L-rpath=$ORIGIN"]
    else:
        raise ValueError("OpenXLSX host integration currently supports Windows and Linux")
    for path in (shared, import_library, source / "z8/xlsx/openxlsx.d", source / "z8/xlsx/poi.d"):
        if not path.is_file():
            raise ValueError("OpenXLSX build input not found: " + str(path))
    args = ["-version=Z8OpenXlsx", "-I" + str(source), str(source / "z8/xlsx/openxlsx.d"),
            str(source / "z8/xlsx/poi.d"), *native_args]
    return args, shared


def deploy(shared, executable):
    """Copy the dynamic library beside the executable, unless already there."""
    shared = Path(shared).resolve()
    target = Path(executable).resolve().parent / shared.name
    if shared != target:
        shutil.copy2(shared, target)
