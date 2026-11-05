"""Check resource diagnostics and shared XML-properties parsing."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source, resources = temp / "bl", temp / "resources"
    source.mkdir()
    resources.mkdir()
    program = source / "Example.bl"
    program.write_text('''// "$comment$" is not a reference
public class Example {
    public static string run() { return "$hello$"; }
    public static string absent() { return "$missing$"; }
}
''', encoding="utf-8")
    (source / "External.bl").write_text('[native "$external$"] public class External { public void run(); }', encoding="utf-8")
    bundle = resources / "bundle_ru.nls"
    bundle.write_text('<properties><entry key="hello">Привет &amp; мир</entry></properties>', encoding="utf-8")
    (resources / "bundle_en.nls").write_text('<properties><entry key="missing">Present</entry></properties>', encoding="utf-8")
    command = [str(compiler), "check-resources", str(source), str(resources), "ru"]
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{program}:4:44: missing resource 'missing'" in result.stderr, result.stderr
    assert "comment" not in result.stderr and "external" not in result.stderr, result.stderr
    bundle.write_text('<properties><entry key="hello">Привет</entry><entry key="missing"/></properties>', encoding="utf-8")
    subprocess.run(command, check=True)
    bundle.write_text('<properties><entry>invalid</entry></properties>', encoding="utf-8")
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 1 and str(bundle) in result.stderr and "missing NLS key" in result.stderr, result.stderr
    result = subprocess.run(command[:-1] + ["fr"], text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 1 and "no resource bundles" in result.stderr, result.stderr
print("Resource checks report missing keys, locations and invalid bundles")
