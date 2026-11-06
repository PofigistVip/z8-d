"""Check the Java implementation order of standard native enum arrays."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
language = root / "vendor/z8/org.zenframework.z8.lang/src/bl"
fixture = root / "tests/fixtures/NativeEnumArraySort.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "source"
    source.mkdir()
    shutil.copy2(fixture, source / fixture.name)
    executable = temp / ("native-enum-sort.exe" if os.name == "nt" else "native-enum-sort")
    subprocess.run([str(compiler), "build", str(source), "NativeEnumArraySort.run", str(executable), "--dependency", str(language)], check=True)
    subprocess.run([str(executable)], check=True)
    core = temp / "core"
    subprocess.run([str(compiler), "library", str(language), str(core), "core", "--dependency", str(root / "platform/bl")], check=True)
    subprocess.run([str(compiler), "build", str(source), "NativeEnumArraySort.run", str(executable), "--library", str(core)], check=True)
    subprocess.run([str(executable)], check=True)
    subset = temp / "subset"
    subset.mkdir()
    (subset / "Aggregation.bl").write_text('[native "org.zenframework.z8.server.base.table.value.Aggregation"] public enum Aggregation { Max, Min }', encoding="utf-8")
    (subset / "Subset.bl").write_text('public class Subset { public static int run() { Aggregation[] values = {Aggregation.Max, Aggregation.Min}; values.sort(); if (values[0] != Aggregation.Min) return 1; return 0; } }', encoding="utf-8")
    subprocess.run([str(compiler), "build", str(subset), "Subset.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    (subset / "Aggregation.bl").write_text('[native "org.zenframework.z8.server.base.table.value.Aggregation"] public enum Aggregation { Max, FutureValue }', encoding="utf-8")
    (subset / "Subset.bl").write_text('public class Subset { public static void run() { Aggregation[] values; values.sort(); } }', encoding="utf-8")
    rejected = subprocess.run([str(compiler), "project", str(subset), str(temp / "stale")], capture_output=True, text=True)
    assert rejected.returncode and "native enum sort order is unavailable or stale" in rejected.stderr, rejected.stderr
print("BL native-enum sorting follows Java order, including shared core")
