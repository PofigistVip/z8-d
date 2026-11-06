"""Exercise native Control metadata and Source references from generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/control_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ControlProbe.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.StringField;
public class ControlProbe {
    public static bool verify() {
        StringField field; GuidField key; Table target;
        if (field.colSpan != 1 || field.flex != 0 || field.readOnly || field.required || field.editable || field.important) return false;
        field.colSpan = 3; field.flex = 2; field.height = 45;
        field.readOnly = true; field.required = true; field.editable = true; field.important = true;
        field.dependency = key; field.dependsOn = key; field.dependencies.add(field);
        field.source = target; field.source.valueFrom = key; field.source.filterField = key;
        return field.colSpan == 3 && field.flex == 2 && field.height == 45 && field.readOnly && field.required && field.editable && field.important &&
            field.dependency == key && field.dependsOn == key && field.dependencies.size() == 1 && field.dependencies.first() == field &&
            field.source.query == target && field.source.valueFrom == key && field.source.filterField == key;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_ControlProbe;
void main() { assert(z8_optional_require(Z8p_436F6E74726F6C50726F6265.m_verify())); }
''', encoding="utf-8")
    exe = temp / ("control-runtime.exe" if os.name == "nt" else "control-runtime")
    args = ["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response_file = temp / "dmd.rsp"
    response_file.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response_file)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("BL Control properties, dependencies and Source references verified")
