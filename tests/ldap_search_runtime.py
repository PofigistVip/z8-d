"""Verify LDAP configuration, extraction, caching and search parameters."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "ldap_search.d"
    source.write_text('''import z8.runtime;
import std.algorithm.searching : canFind;
struct Search { wstring base, filter; int page; }
class Directory : IZ8LdapDirectory {
    bool opened = true, duplicateUsers, extraLogins;
    Search[] calls;
    Z8LdapDirectoryEntry alice, groupEntry;
    this() {
        alice = new Z8LdapDirectoryEntry(); alice.distinguishedName = "CN=Alice,ou=users,dc=example"w;
        alice.attributes["UID"w] = ["alice"w]; alice.attributes["memberOf"w] = ["CN=Admins,ou=groups,dc=example"w, "CN=Admins,ou=groups,dc=example"w];
        alice.attributes["accountExpires"w] = ["1"w]; alice.attributes["mail"w] = ["a@example"w]; alice.attributes["multi"w] = ["one"w, "two"w];
        groupEntry = new Z8LdapDirectoryEntry(); groupEntry.distinguishedName = "CN=Admins,ou=groups,dc=example"w;
        groupEntry.attributes["CN"w] = ["admins"w]; groupEntry.attributes["member"w] = [alice.distinguishedName, alice.distinguishedName];
        groupEntry.attributes["description"w] = ["team"w];
    }
    bool isOpen() { return opened; }
    void close() { opened = false; }
    Z8LdapDirectoryEntry[] search(wstring base, wstring filter, int page) {
        if (!opened) throw new Exception("closed");
        calls ~= Search(base, filter, page);
        if (base == "ou=users,dc=example"w) {
            if (duplicateUsers) return [alice, alice];
            if (extraLogins && filter == "(objectCategory=Person)"w) {
                auto noName = new Z8LdapDirectoryEntry(); noName.distinguishedName = "CN=Missing"w; noName.attributes["memberOf"w] = [];
                auto blank = new Z8LdapDirectoryEntry(); blank.distinguishedName = "CN=Blank"w; blank.attributes["uid"w] = [""w]; blank.attributes["memberOf"w] = [];
                return [alice, noName, blank];
            }
            return [alice];
        }
        if (base == "ou=groups,dc=example"w) return [groupEntry];
        return [];
    }
}
class Transport : IZ8LdapTransport {
    Directory directory;
    IZ8LdapDirectory connect(wstring url, wstring principal, wstring credentials) {
        assert(url == "ldap://test"w && principal == "bind"w && credentials == "secret"w);
        directory = new Directory(); return directory;
    }
}
void main() {
    z8_server_config_replace(null); auto options = z8_ldap_server_options();
    assert(options.connectTimeoutMilliseconds == 3000 && options.pageSize == 500 && !options.sslTrusted);
    z8_server_config_replace(["ldap.connect.timeout"w: "2500"w, "ldap.read.pageSize"w: "17"w, "ldap.ssl.trusted"w: "TrUe"w]);
    options = z8_ldap_server_options();
    assert(options.connectTimeoutMilliseconds == 2500 && options.pageSize == 17 && options.sslTrusted);
    z8_server_config_replace(["ldap.connect.timeout"w: "bad"w, "ldap.read.pageSize"w: "2147483648"w, "ldap.ssl.trusted"w: "yes"w]);
    options = z8_ldap_server_options();
    assert(options.connectTimeoutMilliseconds == 3000 && options.pageSize == 500 && !options.sslTrusted);
    z8_server_config_replace(null);
    auto transport = new Transport(); auto provider = new Z8LdapConfiguredProvider(transport, 500);
    auto config = `{baseDn:"dc=example",users:{baseDn:"ou=users",loginField:"uid",groupField:"memberOf",expiresField:"accountExpires",fields:{mail:"mail",multi:"multi"}},groups:{baseDn:"ou=groups",nameField:"cn",memberField:"member",fields:{label:"description"}}}`w;
    auto session = provider.open("ldap://test"w, "bind"w, "secret"w, config); auto directory = transport.directory;
    assert(session.isOpen()); auto alice = session.user("alice"w);
    assert(alice.login == "alice"w && alice.domainName == "CN=Alice,ou=users,dc=example"w && alice.locked);
    assert(alice.memberOf.length == 1 && alice.parameters["mail"w] == "a@example"w && ("multi"w in alice.parameters) is null);
    assert(directory.calls.length == 1 && directory.calls[0].base == "ou=users,dc=example"w &&
           directory.calls[0].filter == "(&(objectCategory=Person)(uid=alice))"w && directory.calls[0].page == 0);
    assert(session.users().length == 1); auto count = directory.calls.length;
    assert(directory.calls[$-1].filter == "(objectCategory=Person)"w && directory.calls[$-1].page == 500);
    assert(session.user("alice"w) !is null && directory.calls.length == count);
    assert(session.groups().length == 1); count = directory.calls.length;
    auto group = session.group("admins"w);
    assert(group !is null && group.members.length == 1 && group.parameters["label"w] == "team"w && directory.calls.length == count);
    assert(session.user("ou=users,dc=example"w, "(uid=alice)"w) !is null && directory.calls[$-1].page == 0);
    assert(session.group("ou=groups,dc=example"w, "(cn=admins)"w) !is null && directory.calls[$-1].page == 500);
    directory.duplicateUsers = true; bool failed;
    try { session.user("ou=users,dc=example"w, "(uid=*)"w); } catch (Exception) { failed = true; }
    assert(failed); directory.duplicateUsers = false;
    directory.alice.attributes["accountExpires"w] = ["1L"w]; failed = false;
    try { session.user("ou=users,dc=example"w, "(uid=alice)"w); } catch (Exception) { failed = true; } assert(failed);
    session.close(); assert(!session.isOpen());

    auto fallbackConfig = `{baseDn:"dc=example",users:{baseDn:"ou=users",loginField:"uid"},groups:{baseDn:"ou=groups",nameField:"cn",memberField:"member"}}`w;
    session = provider.open("ldap://test"w, "bind"w, "secret"w, fallbackConfig); directory = transport.directory;
    alice = session.user("alice"w);
    assert(alice.memberOf.length == 1 && alice.memberOf[0] == "CN=Admins,ou=groups,dc=example"w);
    assert(directory.calls.length == 2 && directory.calls[1].base == "ou=groups,dc=example"w && directory.calls[1].page == 500);
    session.close();

    session = provider.open("ldap://test"w, "bind"w, "secret"w, config); directory = transport.directory;
    directory.alice.attributes["memberOf"w] = []; alice = session.user("alice"w);
    assert(alice.memberOf.length == 0 && directory.calls.length == 1);
    directory.extraLogins = true; assert(session.users().length == 3); session.close();

    session = provider.open("ldap://test"w, "bind"w, "secret"w, "{}"w); directory = transport.directory;
    assert(session.users().length == 0 && session.groups().length == 0 && directory.calls.length == 0);
    failed = false; try { session.user("alice"w); } catch (Exception) { failed = true; } assert(failed); session.close();
    session = provider.open("ldap://test"w, "bind"w, "secret"w,
        `{baseDn:"dc=example",users:{baseDn:"ou=users",loginField:"uid",groupField:"memberOf",fields:{bad:1}}}`w);
    failed = false; try { session.user("alice"w); } catch (Exception) { failed = true; }
    assert(failed && session.isOpen()); session.close();
    failed = false; try { provider.open("ldap://test"w, "bind"w, "secret"w, `{users:{loginField:3}}`w); } catch (Exception) { failed = true; }
    assert(failed && !transport.directory.isOpen());
}
''', encoding="utf-8")
    executable = temp / ("ldap-search.exe" if os.name == "nt" else "ldap-search")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("LDAP search configuration, membership and caching verified")
