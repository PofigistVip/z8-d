"""Start a generated project whose native classes import each other."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "First.bl").write_text(
        '[native "example.First"] public class First { public Second other(); public Mode kind(); }', encoding="utf-8")
    (source / "Second.bl").write_text(
        '[native "example.Second"] public class Second { public First other(); }', encoding="utf-8")
    (source / "Mode.bl").write_text('public enum Mode { One, Two }', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.p_First;
import z8gen.p_Second;
import z8gen.p_Mode;
void main() {
    assert(cast(Z8p_4669727374)z8_native_new("example.First"w) !is null);
    assert(cast(Z8p_5365636F6E64)z8_native_new("example.Second"w) !is null);
    assert(Z8p_4D6F6465.e_One is Z8p_4D6F6465.e_One);
    assert(Z8p_4D6F6465.e_One !is Z8p_4D6F6465.e_Two);
    z8_native_clear_bindings();
    assert(z8_native_new("example.First"w) !is null);
}
""", encoding="utf-8")
    executable = temp / ("cyclic-native.exe" if os.name == "nt" else "cyclic-native")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Cyclic native modules start and register their factories")
