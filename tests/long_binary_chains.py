"""Compile long left-associated expressions without overflowing the semantic stack."""
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
    chain = " + ".join(["next()"] * 140)
    string_chain = " + ".join(["part"] * 100)
    (source / "Probe.bl").write_text('''
public class Probe {
    static int calls;
    private static int next() { calls += 1; return calls; }
    public static int run() {
        int sum = CHAIN;
        if (sum != 9870 || calls != 140) return 1;
        string part = "x";
        string text = STRINGS;
        if (text.length() != 100) return 2;
        int grouped = 2 * (3 + 4) - 5 + 6;
        if (grouped != 15) return 3;
        return 0;
    }
}
'''.replace("CHAIN", chain).replace("STRINGS", string_chain), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("long-binary.exe" if os.name == "nt" else "long-binary")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Long binary chains, grouping and evaluation order verified")
