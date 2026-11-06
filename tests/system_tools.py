"""Exercise the local system views under different request users."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/system_tools.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Probe.bl").write_text("public class Probe {}", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated), "--dependency", str(language),
                    "--dependency", str(root / "platform/bl")], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
void main() {
    enum name = "org.zenframework.z8.server.base.table.system.view.SequencesView"w;
    auto user = new Z8UserData(); user.id = z8_guid_create(3);
    auto request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    auto previous = z8_application_set_request(request); scope(exit) z8_application_set_request(previous);
    auto view = z8_object_new_instance(name);
    assert(z8_optional_require(z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, view)));
    auto controls = z8_query_array(view, "controls"w); auto sort = z8_query_array(view, "sortFields"w);
    assert(controls.length == 3 && controls[0].z8_index() == "key"w && controls[1].z8_index() == "value"w && controls[2].z8_index() == "description"w);
    assert(sort.length == 1 && sort[0] is controls[2]);
    assert(z8_optional_require(z8_native_field!(Z8Optional!long)("org.zenframework.z8.server.base.form.Control.f_colSpan"w, controls[2])) == 4);
    user.administrator = true; view = z8_object_new_instance(name);
    assert(!z8_optional_require(z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, view)));
}
''', encoding="utf-8")
    executable = temp / ("system-tools.exe" if os.name == "nt" else "system-tools")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("System tool controls and administrator access verified")
