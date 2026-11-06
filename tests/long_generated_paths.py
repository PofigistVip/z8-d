"""Write generated modules beyond the Windows MAX_PATH limit."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
temp = Path(tempfile.mkdtemp())
def io_path(path):
    text = str(path.absolute())
    return "\\\\?\\" + text if os.name == "nt" else text
try:
    source, output = temp / "bl", temp / ("g" * 95) / ("h" * 95) / "generated"
    source.mkdir()
    name = "Т" * 32
    (source / (name + ".bl")).write_text("public class " + name + " { public static int run() { return 7; } }", encoding="utf-8")
    encoded = name
    module = output / "z8gen" / (encoded + ".d")
    assert os.name != "nt" or len(str(module)) > 260
    subprocess.run([str(compiler), "project", str(source), str(output)], check=True)
    with open(io_path(module), encoding="utf-8") as generated:
        assert ("module z8gen." + encoded + ";") in generated.read()
    executable = temp / ("program.exe" if os.name == "nt" else "program")
    build_temp = temp / "build-temp"
    build_temp.mkdir()
    env = dict(os.environ, TMP=str(build_temp), TEMP=str(build_temp), TMPDIR=str(build_temp))
    subprocess.run([str(compiler), "build", str(source), name + ".run", str(executable)], check=True, env=env)
    assert not list(build_temp.glob("z8d-*")), "Temporary build directory was not cleaned"
    if subprocess.run([str(executable)]).returncode != 7:
        raise SystemExit("Long-path executable returned an unexpected result")
    deep = temp / ("a" * 120) / ("b" * 120)
    os.makedirs(io_path(deep))
    with open(io_path(deep / "Other.bl"), "w", encoding="utf-8") as other:
        other.write("public class Other { public static int run() { return 8; } }")
    assert os.name != "nt" or len(str(deep / "Other.bl")) > 260
    subprocess.run([str(compiler), "project", str(deep), str(temp / "deep-output")], check=True)
    assert (temp / "deep-output" / "z8gen" / "Other.d").is_file()
    deep_executable = deep / ("program.exe" if os.name == "nt" else "program")
    subprocess.run([str(compiler), "build", str(deep), "Other.run", str(deep_executable)], check=True)
    copied_executable = temp / ("copied.exe" if os.name == "nt" else "copied")
    shutil.copyfile(io_path(deep_executable), copied_executable)
    if subprocess.run([str(copied_executable)]).returncode != 8:
        raise SystemExit("Long-path output executable returned an unexpected result")
    subprocess.run([str(compiler), "compile", str(deep / "Other.bl")], check=True, capture_output=True)
    subprocess.run([str(compiler), "lex", str(deep / "Other.bl")], check=True, capture_output=True)
finally:
    shutil.rmtree(io_path(temp))
print("Long source and generated paths and build verified")
