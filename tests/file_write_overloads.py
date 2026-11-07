"""Exercise file.write/append overloads and implicit conversions."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "BinaryArg.bl").write_text("public class BinaryArg { public operator binary() { return '65, 66'; } }", encoding="utf-8")
    (temp / "TextArg.bl").write_text('public class TextArg { public operator string() { return " CD"; } }', encoding="utf-8")
    probe = '''public class Probe {
        public static int run() {
            file target = __PATH__;
            target.write(new BinaryArg); target.append(new TextArg);
            if (target.read() != "AB CD") return 1;
            target.write(true); target.append(1.5);
            if (target.read() != "true1.5") return 2;
            target.write("Привет", encoding.UTF8); target.append("!", encoding.UTF8);
            if (target.read(encoding.UTF8) != "Привет!") return 3;
            if (false) { file other; target.write(null, encoding.UTF8); target.write(other, encoding.UTF8); }
            target.delete(); return 99;
        }
    }'''
    (temp / "Probe.bl").write_text(probe.replace("__PATH__", json.dumps((temp / "output.txt").as_posix(), ensure_ascii=False)), encoding="utf-8")
    executable = temp / ("file-overloads.exe" if os.name == "nt" else "file-overloads")
    subprocess.run([str(compiler), "build", str(temp), "Probe.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 99:
        raise SystemExit("file write/append overload returned an unexpected result")
    bad = temp / "Bad.bl"
    for method in ("write", "append"):
        for declaration in ("destination." + method + "(null);", "file other; destination." + method + "(other);",
                            "primary value = 1; destination." + method + "(value);",
                            "destination." + method + "('65, 66', encoding.UTF8);"):
            bad.write_text("public class Bad { static void f() { file destination; " + declaration + " } }", encoding="utf-8")
            if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
                raise SystemExit("Unexpectedly accepted file content argument: " + declaration)
        bad.write_text('''public class Bad {
            public operator binary() { return '65, 66'; } public operator string() { return "text"; }
            static void f() { file destination; destination.''' + method + '''(new Bad); }
        }''', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted ambiguous file content argument")
print("file.write and file.append overloads verified")
