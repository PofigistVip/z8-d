"""Compare file.parse metadata conversion against the original Java file type."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/file_parse_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
jar = next((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
deps = [p for p in cache.rglob("*.jar") if p.name.startswith(
    ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Probe.bl").write_text('''public class Probe {
        public static int size(string json) { file[] files = file.parse(json); return files[0].size; }
        public static string fields(string json) {
            file[] files = file.parse(json); file value = files[0];
            return value.name + "|" + value.author + "|" + value.path + "|" + value.details.get("p") + "|" + value.details.get("q");
        }
    }''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
    java = temp / "FileParseOracle.java"
    java.write_text('''import org.zenframework.z8.server.types.file;
import org.zenframework.z8.server.config.ServerConfig;
import org.zenframework.z8.server.types.string;
class FileParseOracle {
    public static void main(String[] args) throws Exception {
        ServerConfig.load(args[0]);
        String[] values = {"\\\"١٢L\\\"", "\\\"-１２l\\\"", "\\\"+7\\\"", "\\\"7L\\\"", "\\\" 7\\\"",
            "\\\"9223372036854775808\\\"", "\\\"L\\\"", "0", "\\\"\\\"", "null", "1.0", "\\\"-9223372036854775808L\\\""};
        for (String value : values) {
            try { System.out.println("RESULT:" + file.parse("{size:" + value + "}").iterator().next().size.get()); }
            catch (RuntimeException error) { System.out.println("RESULT:error"); }
        }
        String[] documents = {
            "{size:0,name:1.5,author:false,path:[1,2],details:{p:{inner:3},q:[true,5]}}",
            "{size:0,name:1.0,author:12,path:true,details:{p:[1,2],q:{v:false}}}",
            "{size:0,name:null,author:0.000001,path:{x:5},details:{p:[],q:{}}}"
        };
        for (String document : documents) {
            file metadata = file.parse(document).iterator().next();
            System.out.println("FIELDS:" + metadata.name.get() + "|" + metadata.author.get() + "|" + metadata.path.get() + "|" +
                metadata.details.z8_get(new string("p")).get() + "|" + metadata.details.z8_get(new string("q")).get());
        }
    }
}''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [jar, *deps]))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    output = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + classpath,
                                      "FileParseOracle", str(config)], cwd=temp, text=True, encoding="utf-8")
    expected = [line for line in output.splitlines() if line.startswith(("RESULT:", "FIELDS:"))]
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
void main() {
    wstring[] values = ["\\\"١٢L\\\""w, "\\\"-１２l\\\""w, "\\\"+7\\\""w, "\\\"7L\\\""w, "\\\" 7\\\""w,
        "\\\"9223372036854775808\\\""w, "\\\"L\\\""w, "0"w, "\\\"\\\""w, "null"w, "1.0"w, "\\\"-9223372036854775808L\\\""w];
    foreach (value; values) {
        try { writeln("RESULT:", z8_optional_require(Z8p_50726F6265.m_size("{size:"w ~ value ~ "}"w))); }
        catch (Exception) { writeln("RESULT:error"); }
    }
    wstring[] documents = [
        "{size:0,name:1.5,author:false,path:[1,2],details:{p:{inner:3},q:[true,5]}}"w,
        "{size:0,name:1.0,author:12,path:true,details:{p:[1,2],q:{v:false}}}"w,
        "{size:0,name:null,author:0.000001,path:{x:5},details:{p:[],q:{}}}"w
    ];
    foreach (document; documents) writeln("FIELDS:", z8_to_utf8(Z8p_50726F6265.m_fields(document)));
}''', encoding="utf-8")
    executable = temp / ("file-parse.exe" if os.name == "nt" else "file-parse")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, (expected, actual)
print("file.parse metadata conversion matches original Z8")
