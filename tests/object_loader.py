"""Exercise BL class lookup and Object.newInstance on linked D modules."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/object_loader.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir(); (source / "pkg").mkdir()
    (source / "Object.bl").write_text('''
[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {
    public static Object newInstance(string className); public string className();
}
''', encoding="utf-8")
    (source / "pkg/Thing.bl").write_text('public class Thing extends Object { public int value = 9; }', encoding="utf-8")
    (source / "pkg/Hidden.bl").write_text('[name "Hidden Name"] public class Hidden extends Object {}', encoding="utf-8")
    (source / "Plain.bl").write_text('public class Plain {}', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import pkg.Thing;
public class Probe {
    public static bool run() {
        Object value = Object.newInstance("pkg.Thing");
        if (!(value instanceof Thing) || ((Thing)value).value != 9 || value.className() != "pkg.Thing") return false;
        Object nativeValue = Object.newInstance("org.zenframework.z8.server.runtime.OBJECT");
        if (nativeValue.className() != "org.zenframework.z8.server.runtime.OBJECT") return false;
        try { Object.newInstance("missing.Class"); return false; } catch (exception expected) {}
        try { Object.newInstance("Plain"); return false; } catch (exception expected) {}
        return true;
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "Object.bl").unlink(); shutil.copytree(language, source, dirs_exist_ok=True)
        for name in ("pkg/Thing", "pkg/Hidden", "Probe"):
            path = source / (name + ".bl")
            path.write_text("import org.zenframework.z8.lang.Object;\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        for name in ("pkg/Thing", "pkg/Hidden"):
            path = source / (name + ".bl")
            path.write_text("import Object;\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    assert(z8_optional_require(Z8p_50726F6265.m_run()));
    auto hidden = z8_object_new_instance("pkg.Hidden"w);
    assert(hidden.z8_class_id() == "pkg.Hidden"w && hidden.z8_get_attribute("name"w) == "Hidden Name"w);
}
''', encoding="utf-8")
    exe = temp / ("object-loader.exe" if os.name == "nt" else "object-loader")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Dynamic BL class lookup and instantiation verified")
