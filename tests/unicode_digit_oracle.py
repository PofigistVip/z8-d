"""Compare the BMP digit table with the Java 8 Character implementation."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    java = temp / "DigitOracle.java"
    java.write_text('''class DigitOracle {
    public static void main(String[] args) {
        System.out.println(System.getProperty("java.specification.version"));
        int hash = 0;
        for (int c = 0; c < 65536; c++) hash = 31 * hash + Character.digit((char)c, 36) + 1;
        System.out.printf("%08X\\n", hash);
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    version, expected = subprocess.check_output(["java", "-cp", str(temp), "DigitOracle"], cwd=temp, text=True).splitlines()
    if version != "1.8":
        print(f"Skipped exhaustive digit comparison: Java {version} uses a different Unicode table")
    else:
        source = temp / "digit.d"
        source.write_text('''import z8.runtime;
import std.stdio : writefln;
void main() {
    uint hash;
    foreach (c; 0 .. 65536) hash = 31u * hash + cast(uint)(z8_java_digit(cast(wchar)c) + 1);
    writefln("%08X", hash);
}
''', encoding="utf-8")
        executable = temp / ("digit.exe" if os.name == "nt" else "digit")
        subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
        actual = subprocess.check_output([str(executable)], cwd=temp, text=True).strip()
        assert actual == expected, f"Java={expected}, D={actual}"
        print("Unicode digit table matches Java 8 across the BMP")
