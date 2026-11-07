"""Compare z8d tokens with the current original Java lexer, compiled read-only.

Usage: python tests/lexer_oracle.py <original-z8-root> [--corpus]
Only the original lexer's source files are compiled. Minimal stubs stand in for
workspace and type metadata that the standalone in-memory lexer does not use.
"""
from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--corpus"):
    raise SystemExit("Usage: python tests/lexer_oracle.py <original-z8-root> [--corpus]")

root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
java_root = original / "org.zenframework.z8.compiler" / "src" / "main" / "java"
base = java_root / "org" / "zenframework" / "z8" / "compiler"
lexer = base / "parser" / "grammar" / "lexer"
exe = root / ("z8d.exe" if os.name == "nt" else "z8d")
if not (lexer / "Lexer.java").is_file():
    raise SystemExit("Original compiler sources not found")

with tempfile.TemporaryDirectory() as temporary:
    temp = Path(temporary)
    stub = temp / "stubs" / "org" / "zenframework" / "z8" / "compiler"
    (stub / "workspace").mkdir(parents=True)
    (stub / "file").mkdir()
    (stub / "parser" / "type").mkdir(parents=True)
    (stub / "workspace" / "CompilationUnit.java").write_text(
        "package org.zenframework.z8.compiler.workspace; public class CompilationUnit { public Object getAbsolutePath() { return null; } }", encoding="utf-8")
    (stub / "file" / "FileException.java").write_text(
        "package org.zenframework.z8.compiler.file; public class FileException extends Exception {}", encoding="utf-8")
    (stub / "file" / "File.java").write_text(
        "package org.zenframework.z8.compiler.file; public class File { public static File fromPath(Object p) { return new File(); } public char[] read() { return null; } }", encoding="utf-8")
    names = "Binary SqlBinary Boolean SqlBoolean Datespan SqlDatespan Date SqlDate Decimal SqlDecimal Guid SqlGuid Integer SqlInteger String SqlString".split()
    constants = " ".join(f'public static final String {name} = "{name}";' for name in names)
    (stub / "parser" / "type" / "Primary.java").write_text(
        "package org.zenframework.z8.compiler.parser.type; public class Primary { " + constants + " }", encoding="utf-8")
    sources = [base / "core" / "IPosition.java", base / "core" / "IToken.java"]
    sources += [base / "util" / (name + ".java") for name in ("Binary", "Date", "Datespan", "Set")]
    sources += list(lexer.glob("*.java")) + list((lexer / "token").glob("*.java"))
    sources += list((temp / "stubs").rglob("*.java")) + [root / "tests" / "OriginalLexerOracle.java"]
    subprocess.run(["javac", "-source", "8", "-target", "8", "-encoding", "UTF-8",
                    "-sourcepath", str(temp / "stubs"), "-d", str(temp)] + [str(p) for p in sources],
                   check=True, cwd=temp)
    edge = temp / "edge.bl"
    edge.write_bytes(('class Edge { // line\r\n\t/* outer /* nested */ done */\n'
                    'string x = "a\\n\\\"b"; int n = 0x7f; decimal d = .5e+2;\n'
                    "date a = '29/02/2024'; datespan b = '2 03:04:05'; "
                    "guid c = '00112233-4455-6677-8899-aabbccddeeff'; binary x = '0, 0xFF';\n"
                    'bool ok = true && false || a != b; return - 12; }').encode("utf-8"))
    files = [root / "examples" / "math.bl", edge] + sorted((root / "examples" / "project").rglob("*.bl"))
    unicode_edge = temp / "unicode-identifiers.bl"
    unicode_edge.write_text("class e\u0301 { int a\u203Fb; int \u0301mark; int \u0661digit; }", encoding="utf-8")
    files.append(unicode_edge)
    if len(sys.argv) == 3:
        files += sorted((original / "org.zenframework.z8.lang" / "src" / "bl").rglob("*.bl"))
    total = 0
    for file in files:
        java = subprocess.run(["java", "-cp", str(temp), "OriginalLexerOracle", str(file)],
                              capture_output=True, text=True, encoding="utf-8", check=True)
        d = subprocess.run([str(exe), "lex", str(file)], capture_output=True, text=True, encoding="utf-8", check=True)
        expected = []
        for line in java.stdout.splitlines():
            kind, offset, length, row, column, encoded = line.split("\t")
            expected.append(dict(kind=kind, offset=int(offset), length=int(length), line=int(row),
                                 column=int(column), text=base64.b64decode(encoded).decode("utf-8")))
        # JSON may contain U+2028/U+2029 inside a token; splitlines() treats
        # these valid characters as record separators.
        actual = [json.loads(line) for line in d.stdout.split("\n") if line]
        if len(actual) != len(expected):
            raise AssertionError(f"{file}: token counts differ: D={len(actual)}, Java={len(expected)}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            if left != right:
                raise AssertionError(f"{file}: token {index}: D={left!r}, Java={right!r}")
        total += len(actual)
    print(f"Matched {total} tokens in {len(files)} files against the original Java lexer")
