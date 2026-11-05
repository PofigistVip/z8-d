"""Compare LoginParameters with the original Z8 runtime.

Usage: python tests/login_parameters_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/login_parameters_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang" / "src" / "bl"
jars = sorted((original / "org.zenframework.z8.server" / "target" / "libs").glob("*.jar"))
if not any(p.name.startswith("org.zenframework.z8.server-") for p in jars):
    raise SystemExit("Original server runtime JAR not found")
cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
for dependency in (cache / "commons-logging" / "commons-logging", cache / "org.zenframework.z8.dependencies.commons", cache / "commons-io" / "commons-io" / "2.7"):
    if dependency.exists():
        jars.extend(p for p in dependency.rglob("*.jar") if not p.name.endswith("-sources.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
qualified = "org.zenframework.z8.base.security.LoginParameters"
module = "z8gen." + ".".join("p_" + part for part in qualified.split("."))
typename = "Z8p_" + qualified.encode().hex().upper()
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    declaration = Path("org/zenframework/z8/base/security/LoginParameters.bl")
    destination = source / declaration
    destination.parent.mkdir(parents=True)
    shutil.copy2(language / declaration, destination)
    (source / "Probe.bl").write_text('''import org.zenframework.z8.base.security.LoginParameters;
public class Probe {
    public static string describe(LoginParameters value) {
        if (value.login() == null) return "absent";
        return value.login() + "|" + value.address() + "|" + value.schema();
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    resources = temp / "resources"
    resources.mkdir()
    (resources / "test_en.nls").write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">
<properties><entry key="test.login">Alice localized</entry></properties>''', encoding="utf-8")
    java = temp / "LoginOracle.java"
    java.write_text('''import org.zenframework.z8.server.base.security.LoginParameters;
import org.zenframework.z8.server.types.guid;
class LoginOracle {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        LoginParameters blank = new LoginParameters.CLASS<LoginParameters>().get();
        System.out.println(blank.z8_login() == null && blank.z8_address() == null && blank.z8_schema() == null && blank.z8_userId() == null);
        guid id = new guid("00112233-4455-6677-8899-aabbccddeeff");
        org.zenframework.z8.server.security.LoginParameters source = new org.zenframework.z8.server.security.LoginParameters("alice");
        source.setUserId(id).setAddress("127.0.0.1").setSchema("tenant");
        LoginParameters configured = LoginParameters.newInstance(source).get();
        System.out.println(configured.z8_login().get() + "|" + configured.z8_address().get() + "|" + configured.z8_schema().get());
        System.out.println(configured.z8_userId() == id);
        source.setAddress("changed").setLogin("$test.login$");
        System.out.println(configured.z8_login().get() + "|" + configured.z8_address().get());
        LoginParameters empty = LoginParameters.newInstance(new org.zenframework.z8.server.security.LoginParameters((String)null)).get();
        System.out.println(empty.z8_login() != null && empty.z8_address() != null && empty.z8_schema() != null);
        System.out.println(empty.z8_login().get() + "|" + empty.z8_address().get() + "|" + empty.z8_schema().get());
    }
}
''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "LoginOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import __MODULE__;
import z8gen.p_Probe;
import std.stdio : writeln;
alias Login = __TYPE__;
alias Probe = Z8p_50726F6265;
void main() {
    auto blank = z8_new!Login();
    writeln(Probe.m_describe(blank) == "absent"w && z8_nonnull(blank).m_address() is null && z8_nonnull(blank).m_schema() is null && z8_nonnull(blank).m_userId() is null);
    auto id = z8_guid_literal("00112233-4455-6677-8899-aabbccddeeff");
    auto source = new Z8LoginParametersData(id, "alice"w, "127.0.0.1"w, "tenant"w);
    auto configured = cast(Login)z8_login_parameters_from_data(source);
    assert(configured !is null);
    bool invalidType;
    try { z8_login_parameters_set(new Z8Object(), null, null, null, null); } catch (Exception) { invalidType = true; }
    assert(invalidType);
    writeln(z8_to_utf8(Probe.m_describe(configured)));
    writeln(z8_nonnull(configured).m_userId() is id);
    source.address = "changed"w;
    source.login = "$test.login$"w;
    z8_string_set_resource("test.login"w, "Alice localized"w);
    writeln(z8_to_utf8(z8_nonnull(configured).m_login() ~ "|"w ~ z8_nonnull(configured).m_address()));
    auto empty = cast(Login)z8_login_parameters_new(null, null, null, null);
    writeln(z8_nonnull(empty).m_login() !is null && z8_nonnull(empty).m_address() !is null && z8_nonnull(empty).m_schema() !is null);
    writeln(z8_to_utf8(Probe.m_describe(empty)));
    z8_native_clear_bindings();
    z8_bind_builtin_login_parameters();
    assert(z8_nonnull(configured).m_login() == "Alice localized"w);
}
'''.replace("__MODULE__", module).replace("__TYPE__", typename), encoding="utf-8")
    binary = temp / ("login.exe" if os.name == "nt" else "login")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(binary)], cwd=temp, check=True)
    actual = subprocess.check_output([str(binary)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, (actual, expected)
print("LoginParameters state and null handling match Java")
