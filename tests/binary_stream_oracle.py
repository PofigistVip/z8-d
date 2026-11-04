"""Compare file-backed binary stream behavior with the original Java runtime."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/binary_stream_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jar = next((original / "org.zenframework.z8.server" / "target" / "libs").glob("*.jar"))
cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
deps = [p for p in cache.rglob("*.jar") if p.name.startswith(
    ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java_dir, d_dir = temp / "java", temp / "d"
    java_dir.mkdir(); d_dir.mkdir()
    config = temp / "server.properties"
    config.write_text("application.language=en\napplication.working.path=" + java_dir.as_posix() + "\n", encoding="utf-8")
    source = temp / "BinaryStreamOracle.java"
    source.write_text('''import org.zenframework.z8.server.config.ServerConfig;
import org.zenframework.z8.server.types.binary;
import org.zenframework.z8.server.types.file;
import org.zenframework.z8.server.types.string;
class BinaryStreamOracle {
    public static void main(String[] args) throws Exception {
        ServerConfig.load(args[0]);
        file source = new file("source.txt"); source.z8_write(new string("hello"));
        binary stream = source.binary(); source.z8_append(new string("!"));
        System.out.println("RESULT:" + stream.length() + " " + string.z8_fromBinary(stream).get());
        try { stream.length(); System.out.println("RESULT:open"); } catch (RuntimeException e) { System.out.println("RESULT:closed"); }
        binary copy = source.binary(); file target = new file("copy.txt"); target.z8_write(copy);
        System.out.println("RESULT:" + target.z8_read().get());
        try { copy.length(); System.out.println("RESULT:open"); } catch (RuntimeException e) { System.out.println("RESULT:closed"); }
        binary memory = new binary(new byte[]{65,66});
        System.out.println("RESULT:" + string.z8_fromBinary(memory).get() + " " + memory.length());
        binary same = source.binary(); source.z8_write(same);
        System.out.println("RESULT:" + source.z8_read().get().length());
    }
}
''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [jar, *deps]))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(source)], cwd=temp, check=True)
    java = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + classpath,
        "BinaryStreamOracle", str(config)], cwd=temp, text=True, encoding="utf-8")
    expected = [line[7:] for line in java.splitlines() if line.startswith("RESULT:")]
    d_source = temp / "binary_stream.d"
    d_source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
void main(string[] args) {
    z8_file_set_roots(args[1]);
    auto source = z8_file_from_path("source.txt"w); z8_file_write(source, "hello"w);
    auto stream = z8_file_to_binary(source); z8_file_append(source, "!"w);
    writeln(z8_binary_length(stream), " ", z8_string_fromBinary(stream, z8_encoding_by_id(4)).to!string);
    try { z8_binary_length(stream); writeln("open"); } catch (Exception) { writeln("closed"); }
    auto copy = z8_file_to_binary(source); auto target = z8_file_from_path("copy.txt"w); z8_file_write(target, copy);
    writeln(z8_file_read(target).to!string);
    try { z8_binary_length(copy); writeln("open"); } catch (Exception) { writeln("closed"); }
    auto memory = new Z8Binary([cast(ubyte)65, 66]);
    writeln(z8_string_fromBinary(memory, z8_encoding_by_id(4)).to!string, " ", z8_binary_length(memory));
    auto same = z8_file_to_binary(source); z8_file_write(source, same);
    writeln(z8_file_read(source).length);
}
''', encoding="utf-8")
    executable = temp / ("binary_stream.exe" if os.name == "nt" else "binary_stream")
    subprocess.run(["dmd", str(d_source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable), str(d_dir)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert expected == actual, (expected, actual)
print("File-backed binary streams match the original Z8 runtime")
