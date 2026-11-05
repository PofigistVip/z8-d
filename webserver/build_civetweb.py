"""Compile the pinned CivetWeb C source for the optional Z8 web server."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/civetweb/src/civetweb.c"
INCLUDE = ROOT / "third_party/civetweb/include"


def build(output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        cl = shutil.which("cl")
        if cl:
            subprocess.run([cl, "/nologo", "/c", "/O2", "/DNO_SSL", "/DNO_CGI", "/DUSE_WEBSOCKET",
                            "/I" + str(INCLUDE), "/Fo" + str(output), str(SOURCE)], check=True)
            return
        vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
        if not vswhere.is_file(): raise RuntimeError("MSVC C compiler or vswhere not found")
        install = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
                                          "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
        vcvars = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
        if not vcvars.is_file(): raise RuntimeError("MSVC x64 build tools not found")
        def batch_path(path): return str(path).replace("%", "%%")
        with tempfile.TemporaryDirectory() as directory:
            bat = Path(directory) / "compile-civetweb.bat"
            bat.write_text(f'@call "{batch_path(vcvars)}" >nul\n@cl /nologo /c /O2 /DNO_SSL /DNO_CGI /DUSE_WEBSOCKET /I"{batch_path(INCLUDE)}" /Fo"{batch_path(output)}" "{batch_path(SOURCE)}"\n', encoding="utf-8")
            subprocess.run(["cmd", "/d", "/c", str(bat)], check=True)
    else:
        cc = shutil.which("cc")
        if not cc: raise RuntimeError("C compiler not found")
        subprocess.run([cc, "-O2", "-fPIC", "-pthread", "-DNO_SSL", "-DNO_CGI", "-DUSE_WEBSOCKET",
                        "-I" + str(INCLUDE), "-c", str(SOURCE), "-o", str(output)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="output object file")
    build(parser.parse_args().output)
