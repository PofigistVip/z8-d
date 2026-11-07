"""Compile typed null casts and verify overload resolution and null results."""
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
    (source / "Flavor.bl").write_text('public enum Flavor { First, Second }', encoding="utf-8")
    (source / "Failure.bl").write_text('public class Failure extends exception { public void operator = (Failure value) {} }', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
        static int calls;
        static bool check() { calls += 1; return true; }
        static int pick(Probe value) { return 1; }
        static int pick(Flavor value) { return 2; }
        static int pick(Failure value) { return 3; }
        public static Probe objectValue() { return (Probe)(null); }
        public static Flavor enumValue() { return (Flavor)(null); }
        public static Failure exceptionValue() { return (Failure)(null); }
        public static int run() {
            if (objectValue() != null || enumValue() != null || exceptionValue() != null) return 1;
            if (pick((Probe)(null)) != 1 || pick((Flavor)(null)) != 2 || pick((Failure)(null)) != 3) return 2;
            if (pick((Probe)(check() ? null : null)) != 1 || pick((Flavor)(false ? null : null)) != 2 || calls != 1) return 3;
            return 0;
        }
    }''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("null-casts.exe" if os.name == "nt" else "null-casts")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static Probe f() { return (Probe)null; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unparenthesized null cast should be rejected")
print("Typed null object casts and overloads verified")
