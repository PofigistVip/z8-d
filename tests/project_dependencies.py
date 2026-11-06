"""Compile and build BL projects with ordered source-root dependencies."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    main, first, second = (temp / name for name in ("application", "first", "second"))
    for source in (main, first, second):
        (source / "app").mkdir(parents=True)
        (source / "lib").mkdir()
    (main / "app/Main.bl").write_text('''
import lib.Value;
public class Main { public static int run() { Value v; return v.get(); } }
''', encoding="utf-8")
    (first / "lib/Value.bl").write_text('''
import lib.Base;
public class Value { public int get() { Base b; return b.get(); } }
''', encoding="utf-8")
    (second / "lib/Base.bl").write_text('public class Base { public int get() { string s = "$base$"; return 42; } }', encoding="utf-8")
    (second / "lib/Value.bl").write_text('public class Value { public int get() { return 11; } }', encoding="utf-8")
    generated = temp / "generated"
    dependencies = ["--dependency", str(first), "--dependency", str(second)]
    subprocess.run([str(compiler), "project", str(main), str(generated), *dependencies], check=True)
    assert (generated / "z8gen/p_lib/p_Value.d").is_file()
    assert (generated / "z8gen/p_lib/p_Base.d").is_file()
    exe = temp / ("project.exe" if os.name == "nt" else "project")
    subprocess.run([str(compiler), "build", str(main), "app.Main.run", str(exe), *dependencies], check=True)
    assert subprocess.run([str(exe)]).returncode == 42
    (main / "lib/Value.bl").write_text('public class Value { public int get() { return 7; } }', encoding="utf-8")
    subprocess.run([str(compiler), "build", str(main), "app.Main.run", str(exe), *dependencies], check=True)
    assert subprocess.run([str(exe)]).returncode == 7
    resources = temp / "resources"; resources.mkdir()
    bundle = resources / "strings_ru.nls"
    bundle.write_text('<properties><entry key="other">Other</entry></properties>', encoding="utf-8")
    command = [str(compiler), "check-resources", str(main), str(resources), "ru", *dependencies]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1 and "base" in result.stderr and "Base.bl" in result.stderr
    bundle.write_text('<properties><entry key="base">Base</entry></properties>', encoding="utf-8")
    subprocess.run(command, check=True)
    result = subprocess.run([str(compiler), "project", str(main), str(generated), "--dependency"], capture_output=True)
    assert result.returncode == 2
print("Ordered project source dependencies and shadowing verified")
