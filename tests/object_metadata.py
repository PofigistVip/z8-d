"""Exercise OBJECT metadata for generated classes and member references."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/object_metadata.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Object.bl").write_text('''
[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {
    public string id(); public void setId(string id); public string index(); public string className();
    public string name(); public guid key();
    auto public Object[] objects;
}
''', encoding="utf-8")
    (source / "Leaf.bl").write_text('public class Leaf extends Object {}', encoding="utf-8")
    (source / "Child.bl").write_text('[name "Widget"] public class Child extends Object { public Leaf leaf; }', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe extends Object {
    public Child child;
    public Child alias = child;
    public static bool run() {
        Probe root;
        if (root.id() != "" || root.index() != "" || root.className() != "Probe" || root.name() != "Probe") return false;
        if (root.child.index() != "child" || root.child.id() != "child") return false;
        if (root.alias.index() != "child" || root.alias.id() != "child") return false;
        if (root.objects.size() != 2 || root.child.objects.size() != 1) return false;
        if (root.child.className() != "Child" || root.child.name() != "Widget" || root.child.key() != guid.create("Widget")) return false;
        if (root.child.leaf.index() != "leaf" || root.child.leaf.id() != "child.leaf") return false;
        root.child.setId("renamed");
        return root.child.id() == "child" && root.child.index() == "child";
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "Object.bl").unlink(); shutil.copytree(language, source, dirs_exist_ok=True)
        for name in ("Leaf", "Child", "Probe"):
            path = source / (name + ".bl")
            path.write_text("import org.zenframework.z8.lang.Object;\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import z8gen.p_Leaf;
void main() {
    assert(z8_optional_require(Z8p_50726F6265.m_run()));
    auto root = z8_new!Z8p_50726F6265(); root.z8_ensure();
    assert(root.f_child.z8_get_owner() is root && root.f_child.z8_get_ordinal() == 1);
    auto child = z8_nonnull(root.f_child);
    assert(child.f_leaf.z8_get_owner() is child && child.f_leaf.z8_get_ordinal() == 0);
    auto view = z8_object_array_view!Z8Object(root.f_objects());
    auto appended = z8_new!Z8p_4C656166(); view.z8_add(appended);
    assert(appended.z8_get_owner() is root && appended.z8_get_ordinal() == 2);
    auto inserted = z8_new!Z8p_4C656166(); view.z8_add(0, inserted);
    assert(inserted.z8_get_owner() is root && inserted.z8_get_ordinal() == 0);
}
''', encoding="utf-8")
    exe = temp / ("object-metadata.exe" if os.name == "nt" else "object-metadata")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("OBJECT class, name, key and member metadata verified")
