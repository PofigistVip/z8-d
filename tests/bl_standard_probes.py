"""Check compiler acceptance against the bl-standard compile probe corpus.

Usage: python tests/bl_standard_probes.py <bl-standard-root>
The corpus records whether BL compilation should succeed; Java generation and
execution are checked separately by the original bl-standard test suite.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/bl_standard_probes.py <bl-standard-root>")
root = Path(__file__).resolve().parents[1]
corpus = Path(sys.argv[1]).resolve() / "tests/compile_probes.py"
if not corpus.is_file():
    raise SystemExit("bl-standard compile probe corpus not found")
spec = importlib.util.spec_from_file_location("bl_standard_probes", corpus)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "src"
    source.mkdir()
    (source / "Value.bl").write_text(
        "public class Value { public int field; virtual public int get(){return 0;} }",
        encoding="utf-8",
    )
    for name, code, expected_error in module.CASES:
        (source / "SpecProbe.bl").write_text(code, encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(temp / "generated")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if (result.returncode == 0) != (expected_error is None):
            raise SystemExit(f"Probe {name!r} differs from bl-standard:\n{result.stdout}{result.stderr}")
    access_count = 0
    for access in ("", "public", "protected", "private"):
        for kind in ("field", "method"):
            for relation in ("unrelated", "subclass"):
                (source / "Value.bl").write_text(
                    "public class Value {" + access + " int field=4;" + access + " int method(){return 4;}}", encoding="utf-8")
                member = "field" if kind == "field" else "method()"
                code = ("public class SpecProbe {public int f(){Value x;return x." + member + ";}}"
                        if relation == "unrelated" else
                        "public class SpecProbe extends Value {public int f(){return " + member + ";}}")
                (source / "SpecProbe.bl").write_text(code, encoding="utf-8")
                result = subprocess.run([str(compiler), "project", str(source), str(temp / "generated")],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace")
                allowed = access in ("", "public") or (access == "protected" and relation == "subclass")
                if (result.returncode == 0) != allowed:
                    raise SystemExit(f"Access probe {access or 'default'} {kind} {relation} differs:\n{result.stdout}{result.stderr}")
                access_count += 1
    (source / "Value.bl").unlink(); (source / "SpecProbe.bl").unlink()
    (source / "p").mkdir(); (source / "q").mkdir()
    (source / "q/SpecProbe.bl").write_text(
        "import p.Value;public class SpecProbe {public int f(){Value v;return v.field;}}", encoding="utf-8")
    for modifier in ("private", "protected", "public", "static", "auto", "virtual"):
        (source / "p/Value.bl").write_text(modifier + " class Value {public int field=7;}", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(source), str(temp / "generated")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise SystemExit(f"Type modifier probe {modifier!r} differs:\n{result.stdout}{result.stderr}")
        access_count += 1
    # Confirm that the accepted cross-package declarations also produce valid D.
    modules = list((temp / "generated").rglob("*.d"))
    result = subprocess.run(["dmd", "-c", "-o-", "-I" + str(temp / "generated"), *import_args(), *map(str, modules)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise SystemExit(f"Cross-package D compilation failed:\n{result.stdout}{result.stderr}")
print(f"{len(module.CASES)} bl-standard compiler acceptance probes and {access_count} access probes passed")
