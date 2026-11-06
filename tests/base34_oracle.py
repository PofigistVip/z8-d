"""Run original Base34 declarations through D and compare with the Java runtime.

Usage: python tests/base34_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/base34_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang" / "src" / "bl"
jars = sorted((original / "org.zenframework.z8.server" / "target" / "libs").glob("org.zenframework.z8.server-*.jar"))
if not jars:
    raise SystemExit("Original server JAR not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    declaration = Path("org/zenframework/z8/base/crypto/Base34.bl")
    destination = source / declaration
    destination.parent.mkdir(parents=True)
    shutil.copy2(language / declaration, destination)
    (source / "Probe.bl").write_text('''import org.zenframework.z8.base.crypto.Base34;
public class Probe {
    public static string encode(int value) { return Base34.encode(value); }
    public static int decode(string value) { return Base34.decode(value); }
    public static string random() { return Base34.random(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "Base34Oracle.java"
    java.write_text('''import org.zenframework.z8.server.crypto.Base34;
class Base34Oracle {
    public static void main(String[] args) {
        long[] numbers = {-2147483648L, -1, 0, 1, 33, 34, 123456789, 2147483647L,
                          2147483648L, 4294967296L, Long.MAX_VALUE, Long.MIN_VALUE};
        String[] texts = {"1", "Z", "10", "zzzzz", "O", "0", "", "ß", "ı", "ſ", "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"};
        for (int i = 0; i < numbers.length; i++) {
            try { System.out.println("E:" + i + ":" + Base34.encode(numbers[i])); }
            catch (RuntimeException error) { System.out.println("E:" + i + ":ERROR"); }
        }
        for (int i = 0; i < texts.length; i++) {
            try { System.out.println("D:" + i + ":" + Base34.decode(texts[i])); }
            catch (RuntimeException error) { System.out.println("D:" + i + ":ERROR"); }
        }
        String repeated = "";
        for (int n = 1; n <= 20; n++) {
            repeated += "Z";
            System.out.println("P:" + n + ":" + Base34.decode(repeated));
        }
        String random = Base34.random();
        int decoded = Base34.decode(random);
        System.out.println("R:" + (random.length() == 6 && decoded >= 45435424 && decoded <= 1544804415));
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", "-encoding", "UTF-8", "-cp", str(jars[0]), str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Duser.language=en", "-Duser.country=US", "-cp", str(temp) + os.pathsep + str(jars[0]), "Base34Oracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
import std.stdio : writeln;
void main() {
    alias Probe = Z8p_50726F6265;
    long[] numbers = [long.min / 4294967296L, -1, 0, 1, 33, 34, 123456789, 2147483647L,
                      2147483648L, 4294967296L, long.max, long.min];
    wstring[] texts = ["1"w, "Z"w, "10"w, "zzzzz"w, "O"w, "0"w, ""w, "ß"w, "ı"w, "ſ"w, "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"w];
    foreach (i, value; numbers) {
        try { writeln("E:", i, ":", z8_to_utf8(Probe.m_encode(value))); }
        catch (Exception) { writeln("E:", i, ":ERROR"); }
    }
    foreach (i, value; texts) {
        try { writeln("D:", i, ":", z8_optional_require(Probe.m_decode(value))); }
        catch (Exception) { writeln("D:", i, ":ERROR"); }
    }
    wstring repeated = ""w;
    foreach (n; 1 .. 21) {
        repeated ~= "Z"w;
        writeln("P:", n, ":", z8_optional_require(Probe.m_decode(repeated)));
    }
    auto random = Probe.m_random();
    auto decoded = z8_optional_require(Probe.m_decode(random));
    writeln("R:", random.length == 6 && decoded >= 45435424 && decoded <= 1544804415);
    z8_native_clear_bindings();
    bool missing;
    try { Probe.m_decode("1"w); } catch (Exception) { missing = true; }
    assert(missing);
    z8_bind_builtin_base34();
    assert(z8_optional_require(Probe.m_decode("1"w)) == 0);
}
''', encoding="utf-8")
    executable = temp / ("base34.exe" if os.name == "nt" else "base34")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"Base34 differs:\nJava={expected!r}\nD={actual!r}")
print("Base34 encoding, decoding, errors and random range match Java")
