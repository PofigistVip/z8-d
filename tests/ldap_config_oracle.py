"""Compare LDAP configuration and generated search filters with original Z8."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/ldap_config_oracle.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
jar = next((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
deps = [p for p in cache.rglob("*.jar") if p.name.startswith(
    ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "LdapConfigOracle.java"
    java.write_text('''import java.lang.reflect.Field;
import java.text.MessageFormat;
import sun.misc.Unsafe;
import org.zenframework.z8.server.ldap.LdapAPI;
class LdapConfigOracle {
    static Object get(LdapAPI api, String name) throws Exception {
        Field field = LdapAPI.class.getDeclaredField(name); field.setAccessible(true); return field.get(api);
    }
    static void value(Object base, Object filter, int page) {
        if (base != null) System.out.println("RESULT:" + base + "|" + filter + "|" + page);
    }
    public static void main(String[] args) throws Exception {
        Field field = Unsafe.class.getDeclaredField("theUnsafe"); field.setAccessible(true);
        Unsafe unsafe = (Unsafe)field.get(null);
        String[] configs = {
            "{baseDn:'dc=example',users:{baseDn:'ou=users',loginField:'uid'},groups:{baseDn:'ou=groups',nameField:'cn'}}",
            "{baseDn:'dc=example'}",
            "{baseDn:'dc=example',users:{baseDn:'ou=users',loginField:'uid',fields:{bad:1}}}"
        };
        for (String config : configs) {
            LdapAPI api = (LdapAPI)unsafe.allocateInstance(LdapAPI.class); api.setConfig(config);
            Object usersBase = get(api, "usersBaseDn"), groupsBase = get(api, "groupsBaseDn");
            value(usersBase, MessageFormat.format((String)get(api, "userFilter"), "O'Brien"), 0);
            value(usersBase, get(api, "usersFilter"), 500);
            value(groupsBase, MessageFormat.format((String)get(api, "groupFilter"), "staff"), 500);
            value(groupsBase, get(api, "groupsFilter"), 500);
        }
    }
}''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [jar, *deps]))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    output = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + classpath,
                                      "LdapConfigOracle"], cwd=temp, text=True, encoding="utf-8")
    expected = [line for line in output.splitlines() if line.startswith("RESULT:")]
    source = temp / "ldap_config.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
class Directory : IZ8LdapDirectory {
    bool isOpen() { return true; }
    void close() {}
    Z8LdapDirectoryEntry[] search(wstring base, wstring filter, int page) {
        writeln("RESULT:", base.to!string, "|", filter.to!string, "|", page); return [];
    }
}
class Transport : IZ8LdapTransport {
    IZ8LdapDirectory connect(wstring url, wstring principal, wstring credentials) { return new Directory(); }
}
void main() {
    wstring[] configs = [
        `{baseDn:'dc=example',users:{baseDn:'ou=users',loginField:'uid'},groups:{baseDn:'ou=groups',nameField:'cn'}}`w,
        `{baseDn:'dc=example'}`w,
        `{baseDn:'dc=example',users:{baseDn:'ou=users',loginField:'uid',fields:{bad:1}}}`w
    ];
    auto provider = new Z8LdapConfiguredProvider(new Transport());
    foreach (config; configs) {
        auto session = provider.open("ldap://test"w, "bind"w, "secret"w, config);
        session.user("O'Brien"w); session.users(); session.group("staff"w); session.groups(); session.close();
    }
}''', encoding="utf-8")
    executable = temp / ("ldap-config.exe" if os.name == "nt" else "ldap-config")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, (expected, actual)
print("LDAP bases and filters match original Z8")
