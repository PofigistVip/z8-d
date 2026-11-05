"""Exercise host-backed native User wrappers through generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/user_binding.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "User.bl").write_text('''
[native "org.zenframework.z8.server.base.security.User"] public class User {
    public guid id; public string login; public string firstName; public string middleName; public string lastName;
    public string description; public string phone; public string email; public primary[string] parameters;
    public bool isAdministrator(); public bool isBuiltinAdministrator(); public bool isBuiltinSystem();
    public string getParameter(string key, string value); public int getParameter(string key, int value);
    public bool getParameter(string key, bool value); public guid getParameter(string key, guid value);
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static User create() { User user; return user; }
    public static bool check(User u) {
        if (u.id != guid.create(42) || u.login != "alice" || u.firstName != "Alice" || u.email != "a@example.org") return false;
        if (!u.isAdministrator() || u.isBuiltinAdministrator() || !u.isBuiltinSystem()) return false;
        if (u.getParameter("text", "fallback") != "value" || u.getParameter("missing", "fallback") != "fallback") return false;
        if (u.getParameter("number", 0) != 7 || !u.getParameter("flag", false) || u.getParameter("id", guid.Null) != guid.create(9)) return false;
        u.login = "changed"; u.parameters.add("new", "shared"); return true;
    }
    public static bool empty(User u) { return u.id == null && u.login == null && !u.isAdministrator(); }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "User.bl").unlink(); shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.security.User;\n" + probe.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    auto data = new Z8UserData(); data.id = z8_guid_create(42); data.login = "alice"w;
    data.firstName = "Alice"w; data.email = "a@example.org"w;
    data.administrator = true; data.builtinSystem = true;
    data.parameters.z8_add("text"w, z8_primary_box("value"w));
    data.parameters.z8_add("number"w, z8_primary_box(7L));
    data.parameters.z8_add("flag"w, z8_primary_box(true));
    data.parameters.z8_add("id"w, z8_primary_box(z8_guid_create(9)));
    auto user = P.m_create(); z8_user_attach(user, data);
    assert(z8_optional_require(P.m_check(user)));
    assert(data.login == "alice"w && z8_primary_cast!wstring(data.parameters.z8_get("new"w)) == "shared"w);
    auto noRoles = new Z8UserData(); noRoles.id = z8_guid_create(1); noRoles.hasRoles = false;
    auto other = P.m_create(); z8_user_attach(other, noRoles);
    assert(z8_optional_require(P.m_empty(other)));
}
''', encoding="utf-8")
    exe = temp / ("user-binding.exe" if os.name == "nt" else "user-binding")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Native User fields, flags and parameters verified")
