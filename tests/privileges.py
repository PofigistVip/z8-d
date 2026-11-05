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
}
''', encoding="utf-8")
    executable = temp / ("privileges.exe" if os.name == "nt" else "privileges")
    subprocess.run(["dmd", *import_args(), str(source), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Access union, intersection and table/field/request fallbacks verified")
