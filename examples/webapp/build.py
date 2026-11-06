"""Build the Tasks example from its BL sources and a Z8 standard-library checkout."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("original_z8", type=Path, help="Original org.zenframework.z8 checkout")
parser.add_argument("output", type=Path, help="Path for the host executable")
parser.add_argument("--postgres-bin", type=Path, help="PostgreSQL bin directory; defaults to Z8_PG_BIN or pg_config")
options = parser.parse_args()
language = options.original_z8.resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
pg_bin = options.postgres_bin or (Path(os.environ["Z8_PG_BIN"]) if os.environ.get("Z8_PG_BIN") else None)
if pg_bin is None and shutil.which("pg_config"):
    pg_bin = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
if pg_bin is None:
    raise SystemExit("Pass --postgres-bin or set Z8_PG_BIN")
pg_bin = pg_bin.resolve()
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if not compiler.is_file():
    raise SystemExit("Build z8d first with dub build --compiler=dmd")
if os.name == "nt" and not (pg_bin.parent / "lib/libpq.lib").is_file():
    raise SystemExit("PostgreSQL libpq.lib was not found")
sys.path.insert(0, str(root / "webserver"))
from build_civetweb import build

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(root / "examples/webapp"), str(generated),
                    "--dependency", str(language), "--dependency", str(root / "platform/bl")], check=True)
    runtime_source = root / "runtime/source"
    runtime = temp / ("z8-runtime.lib" if os.name == "nt" else "libz8-runtime.a")
    subprocess.run(["dmd", "-lib", "-I" + str(runtime_source), "-J" + str(runtime_source),
                    str(runtime_source / "z8/runtime.d"), str(runtime_source / "z8/runtime_source.d"),
                    "-od=" + str(temp), "-of=" + str(runtime)], cwd=temp, check=True)
    civet = temp / ("civetweb.obj" if os.name == "nt" else "civetweb.o")
    build(civet)
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    args = ["-I" + str(generated), "-I" + str(root / "postgres/source"),
            "-I" + str(root / "webserver/source"), "-I" + str(root / "integrations/postgres_webserver/source"),
            "-I" + str(runtime_source), "-J" + str(runtime_source), *map(str, generated.rglob("*.d")),
            *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(root / "webserver/source/z8/webserver/civetweb.d"),
            str(root / "integrations/postgres_webserver/source/z8/integration/postgres_authority.d"),
            str(root / "examples/webapp/host.d"), str(civet), str(runtime), "-of=" + str(output)]
    args += [str(pg_bin.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq", "-L-lpthread", "-L-ldl"]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
print("Built", output)
