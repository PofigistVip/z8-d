"""Check the lifetime of generated temporary files in an isolated directory."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    source = temp / "tempfile.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
void main() {
    auto value = z8_file_createTempFile("prefix-"w, "txt"w);
    assert(!z8_file_exists(value));
    z8_file_write(value, "content"w);
    assert(z8_file_exists(value));
    writeln(z8_file_path(value).to!string);
}
''', encoding="utf-8")
    executable = temp / ("check.exe" if os.name == "nt" else "check")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    environment = os.environ.copy()
    environment.update({"TMP": str(temp), "TEMP": str(temp), "TMPDIR": str(temp)})
    output = subprocess.check_output([str(executable)], cwd=temp, env=environment, text=True, encoding="utf-8").strip()
    path = (temp / output).resolve()
    assert path.parent == (temp / "z8-d").resolve(), f"unexpected temp path {path} for {temp}"
    assert path.name.startswith("prefix-") and path.suffix == ".txt"
    assert not path.exists(), "temporary file was not removed at process exit"
print("Temporary file metadata and process-exit cleanup verified")
