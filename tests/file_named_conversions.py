"""Run the named file conversion operators through generated BL code."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Probe.bl").write_text('''
public class Probe {
    public static string path(file value) { return value.string(); }
    public static binary open(file value) { return value.binary(); }
    public static int run() {
        file source = "source.txt";
        source.write("hello");
        binary stream = source.binary();
        source.append("!");
        if (string.fromBinary(stream) != "hello!") return 1;
        try { int length = stream.length(); return 2; } catch (exception expected) {}
        if (source.string() != "source.txt") return 3;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main(string[] args) {
    z8_file_set_roots(args[1]);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
    bool failed;
    try { Z8p_50726F6265.m_open(null); } catch (Exception) { failed = true; }
    assert(failed);
}
''', encoding="utf-8")
    executable = temp / ("file-conversions.exe" if os.name == "nt" else "file-conversions")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable), str(temp)], cwd=temp, check=True)
print("Named file conversion operators and file-backed streams verified")
