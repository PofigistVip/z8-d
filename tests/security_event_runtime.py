"""Exercise SecurityObject and host-created SecurityEvent values through BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/security_event_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomSecurityObject.bl").write_text('''
import org.zenframework.z8.base.security.SecurityObject;
public class CustomSecurityObject extends SecurityObject {
    virtual public string getType() { return "custom"; }
}
''', encoding="utf-8")
    (source / "SecurityProbe.bl").write_text('''
import org.zenframework.z8.base.security.SecurityObject;
import org.zenframework.z8.base.security.SecurityEvent;
public class SecurityProbe {
    public static SecurityObject make(guid id) { return SecurityObject.object("table", id, "Orders"); }
    public static SecurityObject custom() { CustomSecurityObject value; return value; }
    public static SecurityEvent eventType() { SecurityEvent value; return value; }
    public static bool check(SecurityEvent event, guid id) {
        return event.getObject().getType() == "table" && event.getObject().getId() == id && event.getObject().getName() == "Orders" &&
            event.getAction() == "update" && !event.isSuccess() && event.getMessage() == "denied";
    }
    public static bool customType(SecurityObject object) { return object.getType() == "custom"; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_SecurityProbe;
void main() {
    alias P = Z8p_536563757269747950726F6265;
    auto id = z8_guid_create(7); auto object = P.m_make(id);
    auto event = z8_security_event_new(object, "update"w);
    z8_security_event_set_result(event, false, "denied"w);
    assert(z8_optional_require(P.m_check(cast(typeof(P.m_eventType()))event, id)));
    assert(z8_optional_require(P.m_customType(P.m_custom())));
}
''', encoding="utf-8")
    executable = temp / ("security-event.exe" if os.name == "nt" else "security-event")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("SecurityObject and SecurityEvent BL values passed")
