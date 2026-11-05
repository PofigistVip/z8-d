"""Exercise Query write lifecycle with a host-provided writer."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/query_write.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Report.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
public class Report extends Table {
    public IntField amount;
    public string events = "";
    virtual protected void onNew() { events += "N"; amount = 5; }
    virtual protected void beforeCreate(guid id) { events += "C"; amount = 6; }
    virtual protected void afterCreate(guid id) { events += "A"; }
    virtual protected void beforeUpdate(guid id) { events += "U"; }
    virtual protected void afterUpdate(guid id) { events += "V"; }
    virtual protected void beforeDestroy(guid id) { events += "D"; }
    virtual protected void afterDestroy(guid id) { events += "E"; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static Report make() { Report table; return table; }
    public static guid create(Report table, guid id) { return table.create(id); }
    public static guid createRandom(Report table) { return table.create(); }
    public static int update(Report table, guid id) { return table.update(id); }
    public static int destroy(Report table, guid id) { return table.destroy(id); }
    public static void set(Report table, int value) { table.amount = value; }
    public static int get(Report table) { return table.amount.get(); }
    public static string events(Report table) { return table.events; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
class Writer : IZ8QueryExecutor, IZ8QueryWriter {
    Z8Object amount, key;
    long inserted, updated, deleted, lastAmount;
    Z8Guid lastId;
    bool fail;
    this(Z8Object amount, Z8Object key) { this.amount = amount; this.key = key; }
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) { return null; }
    void insert(Z8Object query, Z8Object[] fields) {
        ++inserted; assert(fields.length == 7);
        lastAmount = z8_optional_require(z8_primary_cast!long(z8_field_default_value(amount)));
        lastId = z8_primary_cast!Z8Guid(z8_field_default_value(key));
        if (fail) throw new Exception("write failure");
    }
    long update(Z8Object query, Z8Guid id, Z8Object[] fields) {
        ++updated; assert(fields.length == 1 && fields[0] is amount);
        lastAmount = z8_optional_require(z8_primary_cast!long(z8_field_default_value(amount))); lastId = id;
        if (fail) throw new Exception("write failure");
        return 1;
    }
    long destroy(Z8Object query, Z8Guid id) { ++deleted; lastId = id; return 1; }
}
void main() {
    alias P = Z8p_50726F6265;
    auto table = P.m_make(); z8_nonnull(table);
    auto writer = new Writer(table.f_amount, table.f_recordId()); z8_query_set_executor(table, writer);
    assert(P.m_create(table, z8_guid_create(9)) == z8_guid_create(9));
    assert(P.m_events(table) == "NCA"w && writer.inserted == 1 && writer.lastAmount == 6 && writer.lastId == z8_guid_create(9));
    assert(z8_optional_require(P.m_get(table)) == 0 && !z8_field_is_changed(table.f_amount));
    P.m_set(table, z8_optional_wrap(31L));
    assert(z8_optional_require(P.m_update(table, z8_guid_create(9))) == 1 && writer.lastAmount == 31);
    assert(P.m_events(table) == "NCAUV"w && z8_optional_require(P.m_get(table)) == 0);
    assert(z8_optional_require(P.m_update(table, z8_guid_create(9))) == 0 && writer.updated == 1);
    assert(P.m_events(table) == "NCAUVUV"w);
    assert(z8_optional_require(P.m_update(table, z8_guid_zero())) == 0 && P.m_events(table) == "NCAUVUV"w);
    assert(z8_optional_require(P.m_destroy(table, z8_guid_create(9))) == 1 && writer.deleted == 1);
    assert(P.m_events(table) == "NCAUVUVDE"w);
    assert(z8_optional_require(P.m_destroy(table, z8_guid_zero())) == 0 && writer.deleted == 1);
    writer.fail = true; bool failed;
    try { P.m_create(table, z8_guid_create(10)); } catch (Exception) { failed = true; }
    assert(failed && P.m_events(table) == "NCAUVUVDENC"w && z8_field_is_changed(table.f_amount));
    z8_field_reset(table.f_amount); z8_field_reset(table.f_recordId()); writer.fail = false;
    auto random = P.m_createRandom(table); assert(random !is null && random != z8_guid_zero());
}
''', encoding="utf-8")
    exe = temp / ("query-write.exe" if os.name == "nt" else "query-write")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Query write lifecycle, defaults, changes and failures verified")
