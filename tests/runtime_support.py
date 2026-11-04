"""Build and link the separate Z8 runtime in generated-code tests."""
from contextlib import contextmanager
from pathlib import Path
import os
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = ROOT / "runtime" / "source"


def import_args():
    return ["-I" + str(RUNTIME_SOURCE), "-J" + str(RUNTIME_SOURCE)]


@contextmanager
def runtime_library():
    directory = ROOT / "runtime" / "lib"
    directory.mkdir(parents=True, exist_ok=True)
    suffix = ".lib" if os.name == "nt" else ".a"
    library = directory / ("z8-runtime-test-" + uuid.uuid4().hex + suffix)
    try:
        subprocess.run(["dmd", "-lib", *import_args(),
                        str(RUNTIME_SOURCE / "z8" / "runtime.d"),
                        str(RUNTIME_SOURCE / "z8" / "runtime_source.d"),
                        "-of=" + str(library)], check=True)
        yield library
    finally:
        library.unlink(missing_ok=True)
