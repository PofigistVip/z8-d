"""Exercise the BL LDAP facade through a deterministic host provider."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python tests/ldap_runtime.py [original-z8-root]")
    if len(sys.argv) == 2:
        original_root = Path(sys.argv[1]).resolve()
        jar = next((original_root / "org.zenframework.z8.server/target/libs").glob("*.jar"))
        cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
        deps = [p for p in cache.rglob("*.jar") if p.name.startswith(
            ("commons-logging-", "commons-lang-", "commons-io-", "commons-fileupload-")) and not p.name.endswith("-sources.jar")]
        classpath = os.pathsep.join(map(str, [jar, *deps]))
        config = temp / "server.properties"
        config.write_text("application.language=en\napplication.working.path=" + temp.as_posix() + "\n", encoding="utf-8")
        java = temp / "LdapValuesOracle.java"
        java.write_text('''import org.zenframework.z8.server.config.ServerConfig;
import org.zenframework.z8.server.types.string;
class LdapValuesOracle {
    public static void main(String[] args) throws Exception {
        ServerConfig.load(args[0]);
        org.zenframework.z8.server.ldap.LdapUser user = new org.zenframework.z8.server.ldap.LdapUser();
        user.setDomainName("example"); user.setLogin("alice"); user.setLocked(true);
        user.addMemberOf("admins"); user.addMemberOf("admins"); user.addMemberOf(null); user.addMemberOf(""); user.setParameter("mail", "a@example");
        org.zenframework.z8.server.base.ldap.LdapUser wrapped = org.zenframework.z8.server.base.ldap.LdapUser.newInstance(user).get();
        if (!wrapped.login.get().equals("alice") || !wrapped.domainName.get().equals("example") || !wrapped.locked.get() ||
            wrapped.memberOf.size() != 3 ||
            !wrapped.parameters.z8_get(new string("mail")).get().equals("a@example")) throw new AssertionError("LDAP user");
        int emptyMembers = 0, adminMembers = 0;
        for (string value : wrapped.memberOf) {
            if (value.get().isEmpty()) ++emptyMembers;
            if (value.get().equals("admins")) ++adminMembers;
        }
        if (emptyMembers != 2 || adminMembers != 1) throw new AssertionError("LDAP member normalization");
        org.zenframework.z8.server.ldap.LdapGroup group = new org.zenframework.z8.server.ldap.LdapGroup();
        group.setDomainName("example"); group.setName("admins"); group.addMember("alice"); group.addMember("alice"); group.setParameter("description", "team");
        org.zenframework.z8.server.base.ldap.LdapGroup wrappedGroup = org.zenframework.z8.server.base.ldap.LdapGroup.newInstance(group).get();
        if (!wrappedGroup.name.get().equals("admins") || !wrappedGroup.domainName.get().equals("example") || wrappedGroup.members.size() != 1 ||
            !wrappedGroup.members.get(0).get().equals("alice") || !wrappedGroup.parameters.z8_get(new string("description")).get().equals("team"))
            throw new AssertionError("LDAP group");
        if (org.zenframework.z8.server.base.ldap.LdapUser.newInstance(null) != null ||
            org.zenframework.z8.server.base.ldap.LdapGroup.newInstance(null) != null) throw new AssertionError("LDAP null");
    }
}''', encoding="utf-8")
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
        subprocess.run(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + classpath, "LdapValuesOracle", str(config)], cwd=temp, check=True)
    source, generated = temp / "bl", temp / "generated"
    ldap = source / "org/zenframework/z8/base/ldap"
    lang = source / "org/zenframework/z8/lang"
    ldap.mkdir(parents=True); lang.mkdir(parents=True)
    original = root / "vendor/z8/org.zenframework.z8.lang/src/bl/org/zenframework/z8/base/ldap"
    for name in ("LdapAPI", "LdapUser", "LdapGroup"):
        (ldap / (name + ".bl")).write_bytes((original / (name + ".bl")).read_bytes())
    (lang / "Object.bl").write_text('[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {}', encoding="utf-8")
    (ldap / "Probe.bl").write_text('''public class Probe {
    public static bool unavailable() {
        try { LdapAPI api = LdapAPI.getLdapAPI("ldap://example", "bind", "secret"); return false; }
        catch (exception expected) { return true; }
    }
    public static bool verify() {
        LdapAPI empty; if (empty.isOpened()) return false; empty.close();
        LdapUser freshUser; LdapGroup freshGroup;
        if (freshUser.login == null || freshUser.domainName == null || freshUser.locked ||
            freshUser.memberOf.size() != 0 || freshUser.parameters.size() != 0 ||
            freshGroup.name == null || freshGroup.domainName == null || freshGroup.members.size() != 0 || freshGroup.parameters.size() != 0) return false;
        LdapAPI api = LdapAPI.getLdapAPI("ldap://example", "bind", "secret", "{config}");
        if (!api.isOpened() || api.getUser("missing") != null || api.getGroup("missing") != null) return false;
        LdapUser first = api.getUser("alice");
        if (first.login != "alice" || first.domainName != "example" || !first.locked ||
            first.memberOf.size() != 3 || first.memberOf[0] != "admins" || first.memberOf[1] != "" || first.memberOf[2] != "" ||
            first.parameters.get("mail") != "a@example") return false;
        first.login = "edited"; first.memberOf.add("extra"); first.parameters.add("mail", "changed");
        LdapUser again = api.getUser("ou=users", "(uid=alice)");
        if (again.login != "alice" || again.memberOf.size() != 3 || again.parameters.get("mail") != "a@example") return false;
        LdapUser[] users = api.getUsers(); LdapUser[] filtered = api.getUsers("ou=users", "(uid=alice)");
        if (users.size() != 1 || filtered.size() != 1 || users[0].login != "alice") return false;
        LdapGroup group = api.getGroup("admins");
        if (group.name != "admins" || group.domainName != "example" || group.members[0] != "alice" || group.parameters.get("description") != "team") return false;
        group.name = "changed"; group.members.add("another");
        LdapGroup byFilter = api.getGroup("ou=groups", "(cn=admins)");
        if (byFilter.name != "admins" || byFilter.members.size() != 1) return false;
        if (api.getGroups().size() != 1 || api.getGroups("ou=groups", "(cn=admins)").size() != 1) return false;
        api.close(); if (api.isOpened()) return false;
        LdapAPI defaultConfig = LdapAPI.getLdapAPI("ldap://example", "bind", "secret");
        defaultConfig.close(); return true;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.org.zenframework.z8.base.ldap.Probe;
import core.thread : Thread;
class Session : IZ8LdapSession {
    bool opened = true;
    Z8LdapUserData alice;
    Z8LdapGroupData admins;
    this() {
        alice = new Z8LdapUserData(); alice.domainName = "example"w; alice.login = "alice"w; alice.locked = true;
        alice.memberOf = ["admins"w, "admins"w, null, ""w]; alice.parameters["mail"w] = "a@example"w;
        admins = new Z8LdapGroupData(); admins.domainName = "example"w; admins.name = "admins"w;
        admins.members = ["alice"w, "alice"w]; admins.parameters["description"w] = "team"w;
    }
    bool isOpen() { return opened; }
    void close() { opened = false; }
    Z8LdapUserData user(wstring login) { return login == "alice"w ? alice : null; }
    Z8LdapUserData user(wstring base, wstring filter) { assert(base == "ou=users"w && filter == "(uid=alice)"w); return alice; }
    Z8LdapUserData[] users() { return [alice]; }
    Z8LdapUserData[] users(wstring base, wstring filter) { assert(base == "ou=users"w && filter == "(uid=alice)"w); return [alice]; }
    Z8LdapGroupData group(wstring name) { return name == "admins"w ? admins : null; }
    Z8LdapGroupData group(wstring base, wstring filter) { assert(base == "ou=groups"w && filter == "(cn=admins)"w); return admins; }
    Z8LdapGroupData[] groups() { return [admins]; }
    Z8LdapGroupData[] groups(wstring base, wstring filter) { assert(base == "ou=groups"w && filter == "(cn=admins)"w); return [admins]; }
}
class Provider : IZ8LdapProvider {
    int calls;
    IZ8LdapSession open(wstring url, wstring principal, wstring credentials, wstring config) {
        assert(url == "ldap://example"w && principal == "bind"w && credentials == "secret"w);
        assert(calls == 0 ? config == "{config}"w : config is null); ++calls;
        return new Session();
    }
}
void main() {
    assert(z8_optional_require(Z8p_6F72672E7A656E6672616D65776F726B2E7A382E626173652E6C6461702E50726F6265.m_unavailable()));
    auto provider = new Provider(); auto previous = z8_ldap_set_provider(provider);
    auto worker = new Thread({ assert(z8_optional_require(Z8p_6F72672E7A656E6672616D65776F726B2E7A382E626173652E6C6461702E50726F6265.m_verify())); });
    worker.start(); worker.join(); assert(provider.calls == 2);
    z8_native_clear_bindings(); z8_bind_builtin_ldap(); provider.calls = 0;
    assert(z8_optional_require(Z8p_6F72672E7A656E6672616D65776F726B2E7A382E626173652E6C6461702E50726F6265.m_verify()));
    assert(provider.calls == 2); z8_ldap_set_provider(previous);
}''', encoding="utf-8")
    executable = temp / ("ldap.exe" if os.name == "nt" else "ldap")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("LDAP facade, host provider, snapshots and lifecycle verified")
