from pathlib import Path
import os, shutil, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixture = root / "examples" / "project" / "demo" / "cases" / "NativeKeyMaps.bl"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    shutil.copy2(fixture, temp / fixture.name)
    executable = temp / ("native_key_maps.exe" if os.name == "nt" else "native_key_maps")
    subprocess.run([str(compiler), "build", str(temp), "NativeKeyMaps.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 129:
        raise SystemExit(f"Native key maps failed: {result.returncode}")
    bad = temp / "BadNativeKeys.bl"
    for declaration in ('string[sql_int] values = {(1, "value")};', 'string[exception] values = {("error", "value")};'):
        bad.write_text("public class BadNativeKeys { public static void run() { " + declaration + " } }", encoding="utf-8")
        result = subprocess.run([str(compiler), "project", str(temp), str(temp / "out")], capture_output=True, text=True)
        if result.returncode == 0:
            raise SystemExit(f"Accepted conversion in a map key initializer: {declaration}")
print("Exception, encoding and SQL map keys verified")
