"""Compare common email preview text with the original Java EmlUtils.

Usage: python tests/email_preview_oracle.py <original-z8-root>
Requires the original server JAR and its Gradle-cached mail dependencies.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/email_preview_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jars = sorted((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
for directory in (cache / "org.zenframework.z8.dependencies.commons", cache / "commons-io/commons-io",
                  cache / "jakarta.activation/jakarta.activation-api/1.2.2"):
    if directory.exists():
        jars.extend(p for p in directory.rglob("*.jar") if not p.name.endswith("-sources.jar"))
if not any(p.name.startswith("org.zenframework.z8.server-") for p in jars) or not any(p.name.startswith("mail-1.4.7") for p in jars):
    raise SystemExit("Original server JAR and JavaMail dependency are required")

messages = [
    b'From: sender@example.com\r\nSubject: =?UTF-8?B?0J/RgNC40LLQtdGC?=\r\n'
    b'MIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary="part"\r\n\r\n'
    b'--part\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<b>HTML fallback</b>\r\n'
    b'--part\r\nContent-Type: text/plain; charset=windows-1251\r\n'
    b'Content-Transfer-Encoding: quoted-printable\r\n\r\n=C4=EE=E1=F0=FB=E9 =E4=E5=ED=FC\r\n'
    b'--part--\r\n',
    b'From: plain@example.com\nSubject: =?UTF-8?Q?Hello?=\n =?UTF-8?Q?_world?=\n'
    b'Content-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: base64\n\n'
    b'0J/RgNC40LLQtdGC\n',
    b'From: html@example.com\r\nSubject: HTML\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n'
    b'   <b>Hello</b>   world   ',
    b'From: encoded@example.com\r\nSubject: Encoded\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'
    b'=?UTF-8?B?0J/RgNC40LLQtdGC?=',
    b'From: nested@example.com\r\nSubject: Nested\r\nMIME-Version: 1.0\r\n'
    b'Content-Type: multipart/mixed; boundary=outer\r\n\r\n'
    b'--outer\r\nContent-Type: application/octet-stream\r\n\r\nignored\r\n'
    b'--outer\r\nContent-Type: multipart/alternative; boundary=inner\r\n\r\n'
    b'--inner\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n<b>nested html</b>\r\n'
    b'--inner\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nnested plain\r\n'
    b'--inner--\r\n--outer--\r\n',
    b'From: =?UTF-8?B?0J/RgNC40LLQtdGC?= <sender@example.com>\r\n'
    b'Subject: Named sender\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nBody',
    b'From: "Doe, Jane" <jane@example.com>, other@example.com\r\n'
    b'Subject: Multiple senders\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nBody',
    b'From: html@example.com\r\nSubject: Partial HTML\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n'
    b'First <not closed\r\nline> Second <b>bold</b> End <unfinished',
]
for encoding, value in (("windows-1250", "Žluťoučký"), ("windows-1253", "Καλημέρα"),
                        ("windows-1254", "İstanbul"), ("windows-1257", "Ąžuolas")):
    messages.append(("From: sender@example.com\r\nSubject: " + encoding + "\r\n"
                     "Content-Type: text/plain; charset=" + encoding + "\r\n"
                     "Content-Transfer-Encoding: 8bit\r\n\r\n").encode("ascii") + value.encode(encoding))
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "EmailOracle.java"
    java.write_text('''import java.io.FileInputStream;
import java.io.OutputStreamWriter;
import org.zenframework.z8.server.utils.EmlUtils;
public class EmailOracle {
    public static void main(String[] args) throws Exception {
        OutputStreamWriter out = new OutputStreamWriter(System.out, "UTF-8");
        out.write(EmlUtils.emailToString(new FileInputStream(args[0])));
        out.flush();
    }
}''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [temp, *jars]))
    javac = shutil.which("javac")
    if not javac:
        raise SystemExit("A JDK is required")
    java_runtime = shutil.which("java")
    if not java_runtime:
        raise SystemExit("A Java runtime is required")
    subprocess.run([javac, "--release", "8", "-encoding", "UTF-8", "-cp", classpath, str(java)], check=True)
    source = temp / "main.d"
    source.write_text('''import z8.runtime;
import std.conv : to;
import std.file : write;
void main(string[] args) {
    auto data = z8_binary_from_file(args[1]);
    scope(exit) z8_binary_close(data);
    write(args[2], z8_email_message_text(data).to!string);
}''', encoding="utf-8")
    executable = temp / ("email.exe" if os.name == "nt" else "email")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], check=True)
    for index, contents in enumerate(messages):
        message = temp / (str(index) + ".eml")
        message.write_bytes(contents)
        expected = subprocess.check_output([str(java_runtime), "-cp", classpath, "EmailOracle", str(message)]).decode("utf-8").replace("\r\n", "\n")
        output = temp / "d-output.txt"
        subprocess.run([str(executable), str(message), str(output)], check=True)
        actual = output.read_bytes().decode("utf-8").replace("\r\n", "\n")
        assert actual == expected, (index, expected, actual)
print("Email preview text matches the Java oracle")
