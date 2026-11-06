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
import org.zenframework.z8.base.table.RecordLock;
public class Probe {
    public static string recordLock() {
        string before = "" + RecordLock.None + ":" + RecordLock.Full + ":" + RecordLock.Edit + ":" + RecordLock.Destroy;
        RecordLock.Edit = 9;
        return before + ":" + RecordLock.Edit;
    }
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
import z8gen.Probe;
import std.stdio : writeln;
void main() {
    writeln(z8_to_utf8(Z8p_50726F6265.m_recordLock()));
    writeln(z8_to_utf8(Z8p_50726F6265.m_run()));
}
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
    actual = subprocess.check_output([str(binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert len(actual) == 2 and actual[1] == expected, (actual, expected)
    record_expected = "0:1:2:3:9"
    server_jars = list((Path(sys.argv[1]).resolve() / "org.zenframework.z8.server" / "target" / "libs").glob("org.zenframework.z8.server-*.jar"))
    if server_jars:
        server = str(server_jars[0])
        record_java = temp / "RecordLockOracle.java"
        record_java.write_text('''import org.zenframework.z8.server.base.query.RecordLock;
import org.zenframework.z8.server.types.integer;
class RecordLockOracle {
    public static void main(String[] args) {
        String before = RecordLock.None.get() + ":" + RecordLock.Full.get() + ":" + RecordLock.Edit.get() + ":" + RecordLock.Destroy.get();
        RecordLock.Edit = new integer(9);
        System.out.println(before + ":" + RecordLock.Edit.get());
    }
}
''', encoding="utf-8")
        subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", server, str(record_java)], cwd=temp, check=True)
        record_expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + server, "RecordLockOracle"], text=True, encoding="utf-8").strip()
    assert actual[0] == record_expected, (actual[0], record_expected)
print(f"Compiled {len(declarations)} original native declarations; RecordLock fields work and crypto results match Java")
