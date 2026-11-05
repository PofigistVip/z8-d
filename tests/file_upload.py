"""Exercise request-upload files without relying on a filesystem path."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import std.conv : to;
void main(string[] args) {
    z8_file_set_roots(args[1]);
    ubyte[] bytes = cast(ubyte[]) "Привет".dup;
    auto file = z8_file_from_upload("имя.txt"w, bytes);
    bytes[0] = 0;
    assert(file.name == "имя.txt"w && file.path == ""w);
    assert(file.size.present && file.size.value == "Привет".length);
    assert(z8_file_read(file) == "Привет"w);
    auto first = z8_file_to_binary(file);
    auto second = z8_file_to_binary(file);
    assert(first.data == second.data && first.data.ptr != second.data.ptr);
    first.data[0] = 0;
    assert(z8_file_read(file) == "Привет"w);
    auto empty = z8_file_from_upload("empty"w, null);
    assert(z8_file_read(empty) == ""w && empty.size.value == 0);
    assert(z8_file_to_binary(empty).data.length == 0);
    z8_file_assign(file, "other.txt"w);
    assert(z8_file_read(file) == "Привет"w);
    z8_file_write(empty, "written"w);
    assert(empty.path.length && z8_file_read(empty) == "written"w);
}
''', encoding="utf-8")
    executable = temp / ("test.exe" if os.name == "nt" else "test")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable), str(temp)], check=True)
