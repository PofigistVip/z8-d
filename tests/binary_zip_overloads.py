"""Exercise binary.zip overload selection with file conversions."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source_dir = temp / "input"
    source_dir.mkdir()
    (source_dir / "sample.txt").write_text("ZIP content", encoding="utf-8")
    (temp / "FileArg.bl").write_text('''public class FileArg {
        public string path; public operator file() { file value = path; return value; }
    }''', encoding="utf-8")
    program = '''public class Probe {
        public static int run() {
            binary fromString = binary.zip(__INPUT__); fromString.unzip(__OUTPUT1__);
            FileArg converted; converted.path = __INPUT__;
            binary fromObject = binary.zip(converted); fromObject.unzip(__OUTPUT2__);
            binary item = '65, 66'; item.setName("array.bin"); binary[] values = {item};
            binary fromArray = binary.zip(values); fromArray.unzip(__OUTPUT3__);
            return 99;
        }
    }'''
    for name, path in (("__INPUT__", source_dir), ("__OUTPUT1__", temp / "out1"),
                       ("__OUTPUT2__", temp / "out2"), ("__OUTPUT3__", temp / "out3")):
        program = program.replace(name, json.dumps(path.as_posix(), ensure_ascii=False))
    (temp / "Probe.bl").write_text(program, encoding="utf-8")
    executable = temp / ("zip-overloads.exe" if os.name == "nt" else "zip-overloads")
    subprocess.run([str(compiler), "build", str(temp), "Probe.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 99:
        raise SystemExit("binary.zip overload failed")
    assert (temp / "out1/sample.txt").read_text(encoding="utf-8") == "ZIP content"
    assert (temp / "out2/sample.txt").read_text(encoding="utf-8") == "ZIP content"
    assert (temp / "out3/array.bin").read_bytes() == b"AB"
    bad = temp / "Bad.bl"
    for expression in ("null", "1"):
        bad.write_text("public class Bad { static void f() { binary result = binary.zip(" + expression + "); } }", encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted binary.zip argument: " + expression)
print("binary.zip overloads verified")
