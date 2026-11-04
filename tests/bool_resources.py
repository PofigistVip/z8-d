"""Check bool resource labels and defaults in the standalone runtime."""
from pathlib import Path
import os
import subprocess
import tempfile

from runtime_support import runtime_library, import_args


with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    source = temp / "bool_resources.d"
    source.write_text('''import z8.runtime;
void main() {
    assert(z8_bool_parse("BOOL.TRUE"w));
    assert(!z8_bool_parse("bool.false"w));
    assert(!z8_bool_parse(null));
    z8_bool_set_resource_strings("да"w, "нет"w);
    assert(z8_bool_parse("ДА"w));
    assert(!z8_bool_parse("Нет"w));
    assert(z8_bool_parse("YES"w));
    assert(!z8_bool_parse("No"w));
    bool rejected;
    try { z8_bool_parse("bool.true"w); } catch (Exception) { rejected = true; }
    assert(rejected);
    z8_bool_set_resource_strings("same"w, "same"w);
    assert(!z8_bool_parse("same"w));
}
''', encoding="utf-8")
    executable = temp / ("bool_resources.exe" if os.name == "nt" else "bool_resources")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Boolean resource labels and defaults passed")
