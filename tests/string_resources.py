"""Check resource substitution when creating Z8 strings."""
from pathlib import Path
import os
import subprocess
import tempfile

from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    source = temp / "string_resources.d"
    source.write_text('''import z8.runtime;
void main() {
    assert(z8_string_new("$missing$"w) == "missing"w);
    assert(z8_string_new("$$"w) == ""w);
    assert(z8_string_new("$"w) == "$"w);
    z8_string_set_resource("greeting"w, "Привет"w);
    z8_string_set_resource("nested"w, "$greeting$"w);
    assert(z8_string_new("$greeting$"w) == "Привет"w);
    assert(z8_string_new("$nested$"w) == "$greeting$"w);
    assert(z8_nullable_string_binary!"+"("$"w, "greeting$"w) == "Привет"w);
    z8_string_clear_resources();
    assert(z8_string_new("$greeting$"w) == "greeting"w);
}
''', encoding="utf-8")
    executable = temp / ("string_resources.exe" if os.name == "nt" else "string_resources")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("String resource substitution passed")
