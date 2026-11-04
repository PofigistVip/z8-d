"""Compare working/storage path resolution against the original Z8 runtime."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/file_roots_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
runtime_jar = next((original / "org.zenframework.z8.server" / "target" / "libs").glob("*.jar"))
cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
dependencies = [p for p in cache.rglob("*.jar") if p.name.startswith(
    ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java_root, d_root = temp / "java", temp / "d"
    env_root = temp / "environment"
    for root in (java_root, d_root, env_root):
        (root / "working").mkdir(parents=True)
        (root / "vault").mkdir()
    config = temp / "server.properties"
    config.write_text("application.language=en\napplication.working.path=" + (java_root / "working").as_posix() +
                      "\nstorage.path=" + (java_root / "vault").as_posix() + "\n", encoding="utf-8")
    source = temp / "FileRootsOracle.java"
    source.write_text('''import org.zenframework.z8.server.config.ServerConfig;
import org.zenframework.z8.server.types.file;
import org.zenframework.z8.server.types.string;
class FileRootsOracle {
    public static void main(String[] args) throws Exception {
        ServerConfig.load(args[0]);
        String[] paths = {"docs/normal.txt", "storage/a.txt", "storage_backup/b.txt", "./storage/local.txt",
                          "storage/../outside.txt", args[1]};
        for (String path : paths) {
            System.out.println("PATH:" + file.getAbsolutePath(path).getPath());
            System.out.println("PARENT:" + new file(path).z8_parent().path.get());
        }
        file temporary = file.z8_createTempFile(new string("prefix-"), new string("txt"));
        System.out.println("TEMP:" + temporary.path.get());
        file implicit = new file();
        implicit.z8_write(new string("implicit"));
        System.out.println("IMPLICIT:" + implicit.path.get());
    }
}
''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [runtime_jar, *dependencies]))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(source)], cwd=temp, check=True)
    output = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + classpath,
        "FileRootsOracle", str(config), str(java_root / "absolute.txt")], cwd=temp, text=True, encoding="utf-8")
    expected = [Path(line[5:]).resolve().relative_to(java_root.resolve()) for line in output.splitlines() if line.startswith("PATH:")]
    expected_parents = [line[7:] for line in output.splitlines() if line.startswith("PARENT:")]
    temporary = next(line[5:] for line in output.splitlines() if line.startswith("TEMP:"))
    implicit = next(line[9:] for line in output.splitlines() if line.startswith("IMPLICIT:"))
    for prefix, value in (("prefix-", temporary), ("", implicit)):
        path = Path(value)
        assert path.parent == Path("files") / "temp", path
        assert re.fullmatch(re.escape(prefix) + r"\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.txt", path.name), path
        assert not (java_root / "working" / path).exists(), "Java temporary file was not removed at exit"
    assert len(expected) == 6, output
    d_source = temp / "file_roots.d"
    d_source.write_text('''import z8.runtime;
import std.conv : to;
import std.stdio : writeln;
void main(string[] args) {
    if (args[1] != "--environment") z8_file_set_roots(args[1], args[2]);
    string[] paths = ["docs/normal.txt", "storage/a.txt", "storage_backup/b.txt", "./storage/local.txt",
                      "storage/../outside.txt", args[3]];
    foreach (i, path; paths) {
        auto file = z8_file_from_path(path.to!wstring);
        z8_file_write(file, i.to!string.to!wstring);
        assert(z8_file_read(file) == i.to!string.to!wstring);
        writeln("PARENT:", z8_file_parent(file).path.to!string);
    }
}
''', encoding="utf-8")
    executable = temp / ("file_roots.exe" if os.name == "nt" else "file_roots")
    subprocess.run(["dmd", str(d_source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    result = subprocess.check_output([str(executable), str(d_root / "working"), str(d_root / "vault"), str(d_root / "absolute.txt")], cwd=temp, text=True, encoding="utf-8")
    actual_parents = [line[7:] for line in result.splitlines() if line.startswith("PARENT:")]
    def normalized_parent(value, root):
        path = Path(value)
        return ("absolute", path.resolve().relative_to(root.resolve())) if path.is_absolute() else ("relative", path)
    for i in (0, 1):
        assert normalized_parent(expected_parents[i], java_root) == normalized_parent(actual_parents[i], d_root)
    for i, path in enumerate(expected):
        assert (d_root / path).read_text(encoding="utf-8") == str(i), (i, path)
    environment = dict(os.environ, Z8_WORKING_PATH=str(env_root / "working"), Z8_STORAGE_PATH=str(env_root / "vault"))
    subprocess.run([str(executable), "--environment", "", str(env_root / "absolute.txt")], cwd=temp, env=environment, check=True, capture_output=True)
    for i, path in enumerate(expected):
        assert (env_root / path).read_text(encoding="utf-8") == str(i), (i, path)
print("File working and storage paths match the original Z8 runtime")
