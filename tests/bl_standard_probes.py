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
print(f"{len(module.CASES)} bl-standard compiler acceptance probes passed")
