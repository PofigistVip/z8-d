"""Verify typed null map entries and rejection of untyped null literals."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "NullMap.bl"
    source.write_text('''public class NullMap {
        public static int run() {
            string key = null; string value = null;
            string[string] strings = {(key, "v"), ("x", value)};
            if (!strings.containsKey(key) || !strings.containsKey("x") || strings["x"] != null || strings[key] != "v") return 1;
            int number = null;
            int[string] numbers = {("x", number)}; string[int] integerKeys = {(number, "v")};
            if (!numbers.containsKey("x") || numbers["x"] != null || !integerKeys.containsKey(number) || integerKeys[number] != "v") return 2;
            primary p = null;
            primary[string] primaries = {("x", p)}; string[primary] primaryKeys = {(p, "v")};
            if (!primaries.containsKey("x") || primaries["x"] != null || !primaryKeys.containsKey(p) || primaryKeys[p] != "v") return 3;
            return 99;
        }
    }''', encoding="utf-8")
    executable = temp / ("null-map.exe" if os.name == "nt" else "null-map")
    subprocess.run([str(compiler), "build", str(temp), "NullMap.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 99:
        raise SystemExit("Typed null map entries did not retain their values")
    for declaration in (
        'string[string] values = {("key", null)};', 'string[string] values = {(null, "value")};',
        'int[string] values = {("key", null)};', 'string[int] values = {(null, "value")};',
        'primary[string] values = {("key", null)};', 'string[primary] values = {(null, "value")};',
        'string[string] values = {(null, null)};',
    ):
        source.write_text('public class NullMap { public static void run() { ' + declaration + ' } }', encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "generated")], capture_output=True)
        if result.returncode == 0:
            raise SystemExit("Unexpectedly accepted untyped null map entry: " + declaration)
print("Typed null map initializers verified")
