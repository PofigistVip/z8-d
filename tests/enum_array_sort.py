"""Compile BL user-defined enum sorting, including null and alias semantics."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples/project/demo/cases"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("SortColor.bl", "EnumArraySort.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("enum-sort.exe" if os.name == "nt" else "enum-sort")
    subprocess.run([str(compiler), "build", str(temp), "EnumArraySort.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    enum_source, app_source, library = temp / "enum-source", temp / "app-source", temp / "palette"
    enum_source.mkdir(); app_source.mkdir()
    shutil.copy2(fixtures / "SortColor.bl", enum_source / "SortColor.bl")
    shutil.copy2(fixtures / "EnumArraySort.bl", app_source / "EnumArraySort.bl")
    subprocess.run([str(compiler), "library", str(enum_source), str(library), "palette"], check=True)
    subprocess.run([str(compiler), "build", str(app_source), "EnumArraySort.run", str(executable), "--library", str(library)], check=True)
    subprocess.run([str(executable)], check=True)
    native = temp / "native-source"
    native.mkdir()
    (native / "NativeColor.bl").write_text('[native "example.NativeColor"] public enum NativeColor { Red, Blue }', encoding="utf-8")
    (native / "NativeSort.bl").write_text('public class NativeSort { public static void run() { NativeColor[] values; values.sort(); } }', encoding="utf-8")
    rejected = subprocess.run([str(compiler), "project", str(native), str(temp / "native-output")], capture_output=True, text=True)
    assert rejected.returncode and "not yet supported" in rejected.stderr, rejected.stderr
print("BL enum-array sorting, null and aliasing verified")
