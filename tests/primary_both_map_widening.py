"""Widen both keys and values to primary with shared BL map storage."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public int number; public void operator = (Custom value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Plain.bl").write_text('''public class Plain { public operator int() { return 1; } }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[primary] values) { return values.size(); }
    static primary[primary] choice(bool flag, primary[primary] a, int[int] b) { return flag ? a : b; }
    public static int run() {
        int[int] typed = {(1, 10)}; primary[primary] values = typed;
        values.add(1, "wrong"); try { int bad = typed.get(1); return 1; } catch (exception expected) {}
        typed.add(1, 20); values.add("wrong", 30);
        try { for (int key : typed.keys()) {} return 2; } catch (exception expected) {}
        values.remove("wrong"); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 3;
        primary[primary] copy = {}; copy.add(typed); if ((int)copy.get(1) != 20) return 4;
        string[string] texts = {("a", "text")}; primary[primary] primaryTexts = texts;
        primaryTexts.add("a", "changed"); if (texts.get("a") != "changed") return 5;
        bool[bool] flags = {(true, true)}; primary[primary] primaryFlags = flags;
        primaryFlags.add(true, false); if (flags.get(true)) return 6;
        decimal[decimal] decimals = {(1.5, 2.5)}; primary[primary] primaryDecimals = decimals;
        primaryDecimals.add(1.5, 3.5); if (decimals.get(1.5) != 3.5) return 7;
        guid id = guid.create(1); date d = '01/01/2024'; date[guid] dates = {(id, d)}; primary[primary] primaryDates = dates;
        primaryDates.add(id, d); if (dates.get(id) != d) return 8;
        datespan span = '1 00:00:00'; int[datespan] spans = {(span, 1)}; primary[primary] primarySpans = spans;
        primarySpans.add(span, 2); if (spans.get(span) != 2) return 9;
        binary b = '65'; int[binary] binaries = {(b, 1)}; primary[primary] primaryBinaries = binaries;
        primaryBinaries.add(b, 2); if (binaries.get(b) != 2) return 10;
        geometry g = geometry.point(1, 2, 4326); int[geometry] points = {(g, 1)}; primary[primary] primaryPoints = points;
        primaryPoints.add(g, 2); if (points.get(g) != 2) return 11;
        file f = "some.txt"; int[file] files = {(f, 1)}; primary[primary] primaryFiles = files;
        primaryFiles.add(f, 2); if (files.get(f) != 2) return 12;
        Custom key; Custom first; first.number = 1; Custom second; second.number = 2;
        Custom[Custom] custom = {(key, first)}; primary[primary] primaryCustom = custom;
        primaryCustom.add(key, second); if (custom.get(key).number != 2) return 13;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("primary-both-map-views.exe" if os.name == "nt" else "primary-both-map-views")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for declaration in (
        "int[int] source; primary[primary] target = source;",
        "int[guid] source; primary[primary] target = source;",
        "Custom[Custom] source; primary[primary] target = source;",
    ):
        (source / "Check.bl").write_text('public class Check { static void f() { ' + declaration + ' } }', encoding="utf-8")
        subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, check=True)
    for declaration in ("Plain[int] source; primary[primary] target = source;", "int[Plain] source; primary[primary] target = source;"):
        (source / "Check.bl").write_text('public class Check { static void f() { ' + declaration + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted non-primary map type: " + declaration)
    (source / "Check.bl").write_text('public class Check { static void choose(int[int] v) {} static void choose(primary[primary] v) {} static void f() { int[int] v; choose(v); } }', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True, text=True)
    if result.returncode == 0 or "ambiguous" not in result.stderr:
        raise SystemExit("Expected ambiguous map overloads: " + result.stderr)
print("Map keys and values widen together while retaining shared storage")
