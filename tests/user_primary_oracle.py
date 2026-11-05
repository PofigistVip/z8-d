"""Compare custom primary boxing, casts and identity with the Java runtime.

Usage: python tests/user_primary_oracle.py <original-z8-root>
Requires the original server JAR under org.zenframework.z8.server/target/libs.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/user_primary_oracle.py <original-z8-root>")
jars = sorted((Path(sys.argv[1]).resolve() / "org.zenframework.z8.server" / "target" / "libs").glob("org.zenframework.z8.server-*.jar"))
if not jars:
    raise SystemExit("Original server JAR not found")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "UserPrimaryOracle.java"
    java.write_text('''import java.util.HashMap;
import org.zenframework.z8.server.types.primary;
import org.zenframework.z8.server.types.integer;
class UserPrimaryOracle {
    static class Number extends primary {
        public int compareTo(primary value) { return this == value ? 0 : 1; }
        public String toString() { return "native:9"; }
        public int hashCode() { return 37; }
    }
    public static void main(String[] args) {
        Number number = new Number();
        primary boxed = number;
        System.out.println(boxed instanceof Number);
        System.out.println(((Number)boxed) == number);
        System.out.println(boxed.toString());
        System.out.println(boxed.z8_hashCode().get());
        System.out.println(new integer(1) instanceof Number);
        try { Number wrong = (Number)(primary)new integer(1); System.out.println(false); }
        catch (ClassCastException expected) { System.out.println(true); }
        HashMap<primary, Long> values = new HashMap<primary, Long>();
        values.put(boxed, 4L);
        System.out.println(values.get(number));
    }
}
'''.replace('new integer(1) instanceof Number', '((primary)new integer(1)) instanceof Number'), encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", str(jars[0]), str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + str(jars[0]), "UserPrimaryOracle"], text=True).splitlines()
    source = temp / "oracle.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
class Number : Z8Object {
    override wstring z8_user_primary_string_impl() { return "native:9"w; }
    override long z8_user_primary_hash_impl() { return 37; }
}
void main() {
    auto number = new Number();
    auto boxed = z8_primary_box(number);
    writeln(z8_primary_is!Number(boxed));
    writeln(z8_primary_cast!Number(boxed) is number);
    writeln(z8_to_utf8(z8_primary_to_string(boxed)));
    writeln(z8_primary_hash(boxed));
    writeln(z8_primary_is!Number(z8_primary_box(1L)));
    try { z8_primary_cast!Number(z8_primary_box(1L)); writeln(false); }
    catch (Exception) { writeln(true); }
    auto values = new Z8PrimaryKeyMap!long();
    values.z8_add(boxed, z8_optional_wrap(4L));
    writeln(z8_optional_require(values.z8_get(z8_primary_box(number))));
}
''', encoding="utf-8")
    binary = temp / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(binary)], cwd=temp, check=True)
    actual = subprocess.check_output([str(binary)], cwd=temp, text=True).splitlines()
    assert actual == expected, (actual, expected)
print("User primary casts and identity match Java")
