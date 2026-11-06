"""A shared transitive library is registered once per application traversal."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    shared_source = temp / "shared-src/shared"
    shared_source.mkdir(parents=True)
    (shared_source / "Marker.bl").write_text('''
[request] public class Marker {
    private static int count;
    private static int next() { count = count + 1; return count; }
    public int marker = next();
    public static int total() { return count; }
}''', encoding="utf-8")
    shared = temp / "shared-lib"
    subprocess.run([str(compiler), "library", str(shared_source.parent), str(shared), "shared"], check=True)
    libraries = [shared]
    for name in ("left", "right"):
        source = temp / (name + "-src") / name
        source.mkdir(parents=True)
        (source / "Item.bl").write_text("public class Item {}", encoding="utf-8")
        library = temp / (name + "-lib")
        subprocess.run([str(compiler), "library", str(source.parent), str(library), name, "--library", str(shared)], check=True)
        libraries.append(library)
    app = temp / "app-src/app"
    app.mkdir(parents=True)
    (app / "Main.bl").write_text("public class Main {}", encoding="utf-8")
    generated = temp / "generated"
    flags = [part for library in libraries for part in ("--library", str(library))]
    subprocess.run([str(compiler), "project", str(app.parent), str(generated), *flags], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.project_registry;
import z8lib.l_shared.shared_.Marker;
void main() {
    assert(Z8_Marker.m_total() == 0);
    auto first = new Z8RuntimeRegistry();
    z8_register_project(first);
    assert(Z8_Marker.m_total() == 1);
    assert(first.requests().length == 1);
    z8_register_project(first);
    assert(Z8_Marker.m_total() == 2);
    auto second = new Z8RuntimeRegistry();
    z8_register_project(second);
    assert(Z8_Marker.m_total() == 3);
    assert(second.requests().length == 1);
}''', encoding="utf-8")
    executable = temp / ("probe.exe" if os.name == "nt" else "probe")
    archive = "z8-library.lib" if os.name == "nt" else "libz8-library.a"
    args = ["-I" + str(generated), *("-I" + str(library / "d") for library in libraries), *import_args(),
            *map(str, generated.rglob("*.d")), str(harness),
            *map(lambda library: str(library / archive), reversed(libraries)), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Diamond BL library dependency registered once per traversal")
