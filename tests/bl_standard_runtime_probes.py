"""Run the executable integer probes from bl-standard against generated D.

Usage: python tests/bl_standard_runtime_probes.py <bl-standard-root>
Standard-library imports use the vendored BL sources; cases ending in Java
generation errors are skipped.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/bl_standard_runtime_probes.py <bl-standard-root>")
root = Path(__file__).resolve().parents[1]
corpus = Path(sys.argv[1]).resolve() / "tests/runtime_probes.py"
if not corpus.is_file():
    raise SystemExit("bl-standard runtime probe corpus not found")
spec = importlib.util.spec_from_file_location("bl_standard_runtime_probes", corpus)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "src"
    source.mkdir()
    (source / "Child.bl").write_text("public class Child extends Value {}", encoding="utf-8")
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.SpecProbe;
import std.stdio : writeln;
void main() {
    alias Probe = Z8p_5370656350726F6265;
    try {
        auto result = z8_nonnull(z8_new!Probe()).m_f();
        static if (is(typeof(result) == Z8Optional!long)) {
            if (result.present) writeln(result.value);
            else writeln("<null>");
        } else static assert(0, "probe has an unsupported result type");
    } catch (Exception) { writeln("<exception>"); }
}
""", encoding="utf-8")
    count = 0
    rejected = 0
    for name, value, code, stage, expected in module.CASES:
        if stage not in ("run", "run-error", "bl-error"):
            continue
        (source / "Value.bl").write_text(value or module.DEFAULT_VALUE, encoding="utf-8")
        (source / "SpecProbe.bl").write_text(code, encoding="utf-8")
        generated = temp / f"generated-{count}"
        dependency = ["--dependency", str(root / "vendor/z8/org.zenframework.z8.lang/src/bl")] if (
            "import org." in (value or "") or "import org." in code) else []
        result = subprocess.run([str(compiler), "project", str(source), str(generated), *dependency],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if stage == "bl-error":
            if result.returncode == 0:
                raise SystemExit(f"Probe {name!r} should have failed BL compilation")
            if dependency and expected.lower() not in result.stderr.lower():
                raise SystemExit(f"Probe {name!r} failed for the wrong reason:\n{result.stderr}")
            rejected += 1
            continue
        if result.returncode:
            raise SystemExit(f"Probe {name!r} failed BL compilation:\n{result.stderr}")
        executable = temp / ("probe.exe" if os.name == "nt" else "probe")
        command = ["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                   str(harness), str(runtime), "-of=" + str(executable)]
        result = subprocess.run(command, cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise SystemExit(f"Probe {name!r} failed D compilation:\n{result.stderr}")
        result = subprocess.run([str(executable)], cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace")
        expected_output = "<exception>" if stage == "run-error" else expected
        if result.returncode or result.stdout.strip() != expected_output:
            raise SystemExit(f"Probe {name!r}: expected {expected_output!r}, got {result.stdout.strip()!r}\n{result.stderr}")
        count += 1
print(f"{count} executable bl-standard probes and {rejected} rejection probes matched")
