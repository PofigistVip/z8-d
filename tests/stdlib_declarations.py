"""Compile selected unmodified native declarations from the original Z8 library.

Usage: python tests/stdlib_declarations.py <original-z8-root>
"""
from pathlib import Path
import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/stdlib_declarations.py <original-z8-root>")

root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang" / "src" / "bl"
declarations = (
    "org/zenframework/z8/base/crypto/MD5.bl",
    "org/zenframework/z8/base/crypto/Base34.bl",
    "org/zenframework/z8/base/crypto/Digest.bl",
    "org/zenframework/z8/base/file/FileHandler.bl",
    "org/zenframework/z8/base/security/LoginParameters.bl",
    "org/zenframework/z8/base/table/RecordLock.bl",
)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    for name in declarations:
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(language / name, destination)
    # SHA values with leading zeroes exercise Java BigInteger's formatting.
    input_value = next(str(i) for i in range(100000)
                       if hashlib.sha256(str(i).encode()).digest()[0] == 0)
    (source / "Probe.bl").write_text('''import org.zenframework.z8.base.crypto.MD5;
import org.zenframework.z8.base.crypto.Digest;
public class Probe {
    public static string run() {
        return MD5.hex("hello") + ":" + Digest.md5("Привет 😀") + ":" +
            Digest.sha1("hello") + ":" + Digest.sha256("__INPUT__");
    }
}
'''.replace("__INPUT__", input_value), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    modules = list(generated.rglob("*.d"))
    if len(modules) != len(declarations) + 1:
        raise SystemExit(f"Expected {len(declarations) + 1} D modules; got {len(modules)}")
    subprocess.run(["dmd", "-c", "-o-", "-I" + str(generated), *import_args(),
                    *map(str, modules)], cwd=temp, check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
void main() { writeln(z8_to_utf8(Z8p_50726F6265.m_run())); }
''', encoding="utf-8")
    binary = temp / ("probe.exe" if os.name == "nt" else "probe")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, modules),
                    str(harness), str(runtime), "-of=" + str(binary)], cwd=temp, check=True)
    java = temp / "CryptoOracle.java"
    java.write_text('''import java.math.BigInteger;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
class CryptoOracle {
    static String digest(String value, String algorithm) throws Exception {
        String hex = new BigInteger(1, MessageDigest.getInstance(algorithm).digest(value.getBytes(StandardCharsets.UTF_8))).toString(16);
        while (hex.length() < 32) hex = "0" + hex;
        return hex;
    }
    public static void main(String[] args) throws Exception {
        System.out.println(digest("hello", "MD5") + ":" + digest("Привет 😀", "MD5") + ":" +
            digest("hello", "SHA-1") + ":" + digest(args[0], "SHA-256"));
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", "-encoding", "UTF-8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "CryptoOracle", input_value], text=True, encoding="utf-8").strip()
    actual = subprocess.check_output([str(binary)], cwd=temp, text=True, encoding="utf-8").strip()
    assert actual == expected, (actual, expected)
print(f"Compiled {len(declarations)} original native declarations; crypto results match Java")
