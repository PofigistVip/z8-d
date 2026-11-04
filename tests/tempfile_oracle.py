"""Check the lifetime of generated temporary files in an isolated directory."""
from pathlib import Path
import os
import re
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
    auto implicit = new Z8File();
    z8_file_write(implicit, "implicit"w);
    assert(z8_file_read(implicit) == "implicit"w);
    writeln(z8_file_path(implicit).to!string);
    bool repeated;
    foreach (_; 0 .. 20) {
        auto a = z8_file_createTempFile("same-"w, "log"w);
        auto b = z8_file_createTempFile("same-"w, "log"w);
        if (z8_file_path(a) == z8_file_path(b)) { repeated = true; break; }
    }
    assert(repeated);
}
''', encoding="utf-8")
    executable = temp / ("check.exe" if os.name == "nt" else "check")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    environment = os.environ.copy()
    environment.update({"TMP": str(temp), "TEMP": str(temp), "TMPDIR": str(temp), "Z8_WORKING_PATH": str(temp)})
    output = subprocess.check_output([str(executable)], cwd=temp, env=environment, text=True, encoding="utf-8").splitlines()
    assert len(output) == 2, output
    for i, value in enumerate(output):
        path = (temp / value).resolve()
        assert path.parent == (temp / "files" / "temp").resolve(), f"unexpected temp path {path} for {temp}"
        prefix = "prefix-" if i == 0 else ""
        assert re.fullmatch(re.escape(prefix) + r"\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.txt", path.name), path.name
        assert not path.exists(), "temporary file was not removed at process exit"
print("Temporary file metadata and process-exit cleanup verified")
