"""Reuse an independently compiled BL table library in two applications."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/compiled_library_tables.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    core, catalog = temp / "core", temp / "catalog"
    subprocess.run([str(compiler), "library", str(language), str(core), "core", "--dependency", str(root / "platform/bl")], check=True)
    source = temp / "catalog-source"
    (source / "catalog").mkdir(parents=True)
    (source / "catalog/Product.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[generatable] [name "Library Products"] public class Product extends Table {
    [name "Title"] public StringField title;
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "library", str(source), str(catalog), "catalog", "--library", str(core)], check=True)
    archive = lambda p: p / ("z8-library.lib" if os.name == "nt" else "libz8-library.a")
    for name in ("First", "Second"):
        app, generated = temp / (name + "-source"), temp / (name + "-generated")
        (app / "application").mkdir(parents=True)
        (app / ("application/" + name + ".bl")).write_text('''
import catalog.Product;
[request] [entry] public class %s extends Product { columns = {title}; }
''' % name, encoding="utf-8")
        subprocess.run([str(compiler), "project", str(app), str(generated), "--library", str(core), "--library", str(catalog)], check=True)
        paths = {p.relative_to(generated).as_posix() for p in generated.rglob("*.d")}
        assert paths == {"z8gen/application/" + name + ".d", "z8gen/project_registry.d"}, paths
        harness = temp / (name + ".d")
        harness.write_text('''import z8.runtime; import z8gen.project_registry;
void main() {
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    auto table = registry.newTableByName("Library Products"w);
    assert(table !is null && table.z8_class_id() == "catalog.Product"w);
    auto view = registry.newRequestByClass("application.%s"w);
    assert(view !is null && view.z8_class_id() == "application.%s"w);
    assert(z8_object_new_instance("catalog.Product"w).z8_class_id() == "catalog.Product"w);
    bool title;
    foreach (item; registry.tables()) if (item.name == "Library Products"w)
        foreach (field; item.fields) if (field.name == "Title"w) title = true;
    assert(title);
}''' % (name, name), encoding="utf-8")
        executable = temp / (name + (".exe" if os.name == "nt" else ""))
        args = ["-I" + str(generated), "-I" + str(core / "d"), "-I" + str(catalog / "d"), *import_args(),
                *map(str, generated.rglob("*.d")), str(harness), str(archive(catalog)), str(archive(core)), str(runtime), "-of=" + str(executable)]
        response = temp / (name + ".rsp")
        response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
        subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
        subprocess.run([str(executable)], cwd=temp, check=True)
print("Separate BL table library reused in two applications")
