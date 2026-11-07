"""Verify guid.create overload selection and implicit argument conversions."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "TextArg.bl").write_text('public class TextArg { public operator string() { return "custom"; } }', encoding="utf-8")
    (temp / "IntArg.bl").write_text('public class IntArg { public operator int() { return 7; } }', encoding="utf-8")
    (temp / "Probe.bl").write_text('''public class Probe {
        public static int run() {
            if (guid.create(true) != guid.create("true") || guid.create(false) != guid.create("false")) return 1;
            if (guid.create(1.5) != guid.create("1.5")) return 2;
            if (guid.create(7) != guid.create(0, 7) || guid.create(7) == guid.create("7")) return 3;
            date moment = '29/02/2024';
            if (guid.create(moment) != guid.create((string)moment)) return 4;
            datespan span = '1 00:00:00';
            if (guid.create(span) != guid.create((string)span)) return 5;
            guid identity = '00000000-0000-0000-0000-000000000001';
            if (guid.create(identity) != guid.create((string)identity)) return 6;
            file path = "storage/example.txt";
            if (guid.create(path) != guid.create((string)path)) return 7;
            if (guid.create(new TextArg) != guid.create("custom")) return 8;
            if (guid.create(new IntArg) != guid.create(7)) return 9;
            geometry point = geometry.point(1, 2, 4326);
            if (guid.create(point) != guid.create((string)point)) return 10;
            exception error = "problem";
            if (guid.create(error) != guid.create((string)error)) return 11;
            return 99;
        }
    }''', encoding="utf-8")
    executable = temp / ("guid-overloads.exe" if os.name == "nt" else "guid-overloads")
    subprocess.run([str(compiler), "build", str(temp), "Probe.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 99:
        raise SystemExit("guid.create overload returned an unexpected result")
    for declaration in ("guid result = guid.create(null);", "guid result = guid.create('0, 255');",
                        "primary value = 1; guid result = guid.create(value);"):
        (temp / "Bad.bl").write_text("public class Bad { static void f() { " + declaration + " } }", encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted guid.create argument: " + declaration)
    (temp / "Bad.bl").write_text('''public class Bad {
        public operator string() { return "x"; } public operator int() { return 7; }
        static void f() { guid result = guid.create(new Bad); }
    }''', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted ambiguous guid.create argument")
print("guid.create overloads verified")
