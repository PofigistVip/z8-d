"""Test concurrent session lookup, invalidation and expiry."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import core.thread : Thread;
import std.conv : to;
Z8UserData makeUser(long id) {
    auto value = new Z8UserData(); value.id = z8_guid_create(id); return value;
}
void main() {
    auto role = z8_guid_create(8);
    auto user = makeUser(1); user.roles = [role];
    auto system = makeUser(0);
    auto manager = new Z8SessionManager(100);
    auto original = manager.create("first"w, user, system, "a"w);
    auto duplicate = manager.create("unused"w, user, system, "a"w);
    assert(original is duplicate && manager.getSession("unused"w) is null);
    auto copy = manager.getSession("first"w);
    assert(copy !is original && copy.user is user && copy.system is system);
    assert(manager.getSessionInSchema("first"w, "a"w) !is null && manager.getSessionInSchema("first"w, "b"w) is null);
    copy.switchUser(makeUser(2)); copy.restoreUser(); assert(copy.user is user && original.user is user);
    auto administrator = makeUser(3); administrator.administrator = true; administrator.roles = [role];
    auto otherSchema = makeUser(4); otherSchema.roles = [role];
    manager.create("admin"w, administrator, system, "a"w);
    manager.create("other"w, otherSchema, system, "b"w);
    manager.dropRoleSessions(role, "a"w);
    assert(manager.getSession("first"w) is null && manager.getSession("admin"w) !is null && manager.getSession("other"w) !is null);
    manager.dropUserSessions(administrator.id, "a"w);
    assert(manager.getSession("admin"w) is null);
    auto item = manager.create("expire"w, user, system, "a"w);
    item.lastAccessTime = 1000;
    manager.check(1100); assert(manager.getSession("expire"w) !is null);
    item.lastAccessTime = 1000; manager.check(1101); assert(manager.getSession("expire"w) is null);
    auto single = new Z8SessionManager(0, true);
    single.create("old"w, user, system, "a"w);
    single.create("taken"w, administrator, system, "a"w);
    bool rejected; try { single.create("taken"w, user, system, "a"w); } catch (Exception) { rejected = true; }
    assert(rejected && single.getSession("old"w) !is null);
    single.create("new"w, user, system, "a"w);
    assert(single.getSession("old"w) is null && single.getSession("new"w) !is null);
    single.dropSessionInSchema("old"w, "a"w); single.dropSessionInSchema("new"w, "b"w);
    assert(single.getSession("new"w) !is null);
    single.dropSessionInSchema("new"w, "a"w); assert(single.getSession("new"w) is null);
    single.create("new"w, user, system, "a"w);
    single.check(long.max); assert(single.getSession("new"w) !is null);
    auto concurrent = new Z8SessionManager();
    Thread[] threads;
    Thread makeThread(size_t number) {
        return new Thread({
            foreach (j; 0 .. 50) {
                auto id = (number * 50 + j).to!long;
                auto token = id.to!wstring;
                auto u = makeUser(id);
                concurrent.create(token, u, system, "a"w);
                assert(concurrent.getSession(token).user is u);
                concurrent.dropUserSessions(u.id, "a"w);
                assert(concurrent.getSession(token) is null);
            }
        });
    }
    foreach (i; 0 .. 8) threads ~= makeThread(i);
    foreach (thread; threads) thread.start();
    foreach (thread; threads) thread.join();
}
''', encoding="utf-8")
    exe = temp / ("session-manager.exe" if os.name == "nt" else "session-manager")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("Session reuse, expiration, invalidation and concurrency verified")
