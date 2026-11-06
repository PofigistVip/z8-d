"""Exercise Resources.loadResource with a host-configured application root."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/resources_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ResourceProbe.bl").write_text('''
import org.zenframework.z8.base.application.Resources;
public class ResourceProbe {
    public static file load(string path) { return Resources.loadResource(path); }
}
''', encoding="utf-8")
    application, working = temp / "application", temp / "working"
    (application / "data").mkdir(parents=True)
    working.mkdir()
    (application / "data" / "resource.txt").write_bytes(b"hello resource")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_ResourceProbe;
void main(string[] args) {
    alias P = Z8p_5265736F7572636550726F6265;
    z8_file_set_roots(args[2]);
    z8_resources_set_application_root(args[1]);
    auto file = P.m_load("data/resource.txt"w);
    assert(z8_file_exists(file) && file.name == "resource.txt"w);
    assert(z8_optional_require(file.size) == 14 && z8_file_read(file) == "hello resource"w);
    assert(file.time !is null && z8_date_ticks(file.time) == z8_date_ticks(z8_file_lastModified(file)));
    auto leading = P.m_load("/data/resource.txt"w);
    assert(z8_file_exists(leading) && z8_file_read(leading) == "hello resource"w);
    auto missing = P.m_load("data/missing.txt"w);
    assert(!z8_file_exists(missing) && z8_optional_require(missing.size) == 0);
    assert(z8_date_ticks(missing.time) == 0);
}
''', encoding="utf-8")
    executable = temp / ("resources.exe" if os.name == "nt" else "resources")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(application), str(working)], cwd=temp, check=True)
print("Application resource loading and file metadata passed")
