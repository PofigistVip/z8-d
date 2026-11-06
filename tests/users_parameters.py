"""Exercise the original Users.getParameters overloads through generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/users_parameters.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir(): raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory); source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "LegacyUsers.bl").write_text('''
import org.zenframework.z8.base.table.system.Users;
public class LegacyUsers extends Users {
    virtual protected bool getParameters(guid id, string login, primary[string] parameters) {
        parameters.add("legacy", login); return id == guid.create(42);
    }
}
''', encoding="utf-8")
    (source / "ModernUsers.bl").write_text('''
import org.zenframework.z8.base.table.system.Users;
import org.zenframework.z8.base.security.LoginParameters;
public class ModernUsers extends Users {
    virtual protected bool getParameters(LoginParameters login, primary[string] parameters) {
        parameters.add("schema", login.schema()); return false;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.LegacyUsers;
import z8gen.ModernUsers;
void main() {
    auto login = new Z8LoginParametersData(z8_guid_create(42), "alice"w, "127.0.0.1"w, "tenant"w);
    auto values = new Z8PrimaryMap();
    auto legacy = z8_object_new_instance("LegacyUsers"w);
    assert(z8_users_extra_parameters(legacy, login, values));
    assert(z8_primary_cast!wstring(values.z8_get("legacy"w)) == "alice"w);
    values.z8_clear(); auto modern = z8_object_new_instance("ModernUsers"w);
    assert(!z8_users_extra_parameters(modern, login, values));
    assert(z8_primary_cast!wstring(values.z8_get("schema"w)) == "tenant"w);
    auto base = z8_native_new("org.zenframework.z8.server.base.table.system.Users"w);
    assert(z8_users_extra_parameters(base, login, new Z8PrimaryMap()));
}
''', encoding="utf-8")
    exe = temp / ("users-parameters.exe" if os.name == "nt" else "users-parameters")
    args = ["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Users.getParameters virtual overloads verified")
