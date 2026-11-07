"""Check Java-null MessageFormat arguments and custom-primary extraction."""
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
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public void operator = (Custom other) {}
    }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
        public static bool userRejected() {
            Custom item; primary[] values = {item};
            try { string result = "no placeholders".format(values); return false; }
            catch (exception expected) { return true; }
        }
    }''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "FormatNull.java"
    java.write_text('''import java.text.MessageFormat;
class FormatNull {
    public static void main(String[] args) {
        String[] patterns = {"{0}", "{0,number,integer}", "{0,date,short}", "{0,time,short}", "{0,choice,0#zero|1#one}"};
        for (String pattern : patterns) System.out.println(MessageFormat.format(pattern, new Object[] {null}));
    }
}''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "FormatNull"], cwd=temp, text=True).splitlines()
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
import std.conv : to;
void main() {
    auto empty = z8_geometry_none(3857);
    Z8Primary[] inputs = [z8_primary_box(empty), z8_primary_box(z8_decimal_nan()), z8_primary_box(z8_file_from_path("path.txt"w))];
    wstring[] patterns = ["{0}"w, "{0,number,integer}"w, "{0,date,short}"w, "{0,time,short}"w, "{0,choice,0#zero|1#one}"w];
    foreach (input; inputs) foreach (pattern; patterns)
        writeln(z8_string_format(pattern, new Z8Array!Z8Primary([input])).to!string);
    assert(z8_optional_require(Z8p_50726F6265.m_userRejected()));
}''', encoding="utf-8")
    executable = temp / ("format-null.exe" if os.name == "nt" else "format-null")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True).splitlines()
    assert actual == expected * 3, (expected, actual)
print("MessageFormat Java-null and custom-primary extraction verified")

