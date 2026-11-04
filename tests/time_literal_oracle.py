"""Time-only literals capture the compiler's current instant, as in Z8."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / "TimeOnly.bl"
    source.write_text("public class TimeOnly { public static date run() { return '23:59:59'; } }", encoding="utf-8")
    before = time.time_ns() // 1_000_000
    generated = subprocess.check_output([str(compiler), "compile", str(source)], text=True, encoding="utf-8")
    after = time.time_ns() // 1_000_000
    match = re.search(r"z8_date_from_ticks\((\d+)L\)", generated)
    assert match, "generated D code did not capture the instant"
    assert before - 1000 <= int(match.group(1)) <= after + 1000
print("Time-only literal captures the compiler's current instant")
