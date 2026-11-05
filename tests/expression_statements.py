"""Compile value expressions discarded as BL statements."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "bl"
    source.mkdir()
    (source / "Discard.bl").write_text('''public class Discard {
        public static int run() { int value = 5; value; 1; true; null; return value; }
    }''', encoding="utf-8")
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''import z8.runtime;
import z8gen.p_Discard;
void main() { assert(z8_optional_require(Z8p_44697363617264.m_run()) == 5); }
''', encoding="utf-8")
    executable = temp / ("discard.exe" if os.name == "nt" else "discard")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("Discarded expression statements verified")
