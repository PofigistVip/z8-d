"""Verify Z8 Access and Privileges composition and fallback rules."""
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
void main() {
    auto user = Z8Access(true, false, false, false, false, false);
    auto writer = Z8Access(false, true, true, false, false, true);
    auto merged = user.orAccess(writer);
    assert(merged.read && merged.write && merged.create && merged.execute && !merged.destroy);
    auto privileges = new Z8Privileges(merged);
    auto table = z8_guid_create(1), field = z8_guid_create(2), request = z8_guid_create(3);
    assert(privileges.getTableAccess(null) == merged && privileges.getRequestAccess(request) == merged);
    privileges.setTableAccess(table, Z8Access(true, false, false, false, false, false));
    assert(privileges.getTableAccess(z8_guid_create(1)).read && !privileges.getTableAccess(table).write);
    assert(privileges.getFieldAccess(table, field).read && !privileges.getFieldAccess(table, field).write);
    privileges.setFieldAccess(field, Z8Access(true, true, false, false, false, false));
    auto restricted = privileges.getFieldAccess(table, z8_guid_create(2));
    assert(restricted.read && !restricted.write && !restricted.execute);
    privileges.setFieldAccess(field, Z8Access(false, true, false, false, false, false));
    restricted = privileges.getFieldAccess(table, field);
    assert(!restricted.read && !restricted.write);
    privileges.setRequestAccess(request, Z8Access(false, false, false, false, false, true));
    assert(privileges.getRequestAccess(z8_guid_create(3)).execute && !privileges.getRequestAccess(request).read);
    privileges.setDefaultAccess(Z8Access.init);
    assert(!privileges.getTableAccess(z8_guid_create(9)).read && privileges.getTableAccess(table).read);
    auto snapshot = privileges.snapshot();
    assert(snapshot.tables.length == 1 && snapshot.fields.length == 1 && snapshot.requests.length == 1);
    assert(!snapshot.fields[0].access.read && snapshot.fields[0].access.write);
    auto restored = z8_privileges_from_snapshot(snapshot);
    assert(restored.getTableAccess(table) == privileges.getTableAccess(table));
    assert(restored.getFieldAccess(table, field) == privileges.getFieldAccess(table, field));
    assert(restored.getRequestAccess(request) == privileges.getRequestAccess(request));
    snapshot.tables[0].id.minorBits = 99;
    assert(restored.getTableAccess(table).read && privileges.getTableAccess(table).read);
    auto bad = privileges.snapshot(); bad.fields ~= bad.fields[0];
    bool rejected; try { z8_privileges_from_snapshot(bad); } catch (Exception) { rejected = true; }
    assert(rejected);
    bad = privileges.snapshot(); bad.tables[0].id = null;
    rejected = false; try { z8_privileges_from_snapshot(bad); } catch (Exception) { rejected = true; }
    assert(rejected);
    privileges.setTableAccess(z8_guid_create(7), merged);
    privileges.setTableAccess(z8_guid_create(5), Z8Access.init);
    auto ordered = privileges.snapshot();
    assert(ordered.tables.length == 3 && ordered.tables[0].id == z8_guid_create(1) && ordered.tables[1].id == z8_guid_create(5) && ordered.tables[2].id == z8_guid_create(7));
}
''', encoding="utf-8")
    executable = temp / ("privileges.exe" if os.name == "nt" else "privileges")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Access union, intersection and table/field/request fallbacks verified")
