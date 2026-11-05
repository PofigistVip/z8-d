"""Run the BL Connection API and Query.setConnection against PostgreSQL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_connection.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Report.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
[name "Reports"] public class Report extends Table { [name "Amount"] public IntField amount; }
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.sql.Connection;
public class Probe {
    public static Connection current() { return Connection.get(); }
    public static Report make() { Report value; return value; }
    public static void attach(Report report, Connection connection) { report.setConnection(connection); }
    public static void begin() { Connection.get().beginTransaction(); }
    public static void commit() { Connection.get().commit(); }
    public static void rollback() { Connection.get().rollback(); }
    public static void flush() { Connection.get().flush(); }
    public static void execute(string sql) { Connection.get().execute(sql); }
    public static void insert(Report report, guid id, int amount) { report.amount = amount; report.create(id); }
    public static int count(Report report) { return report.count(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8gen.p_Probe;
import core.thread : Thread;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    bool missing; try { P.m_current(); } catch (Exception) { missing = true; } assert(missing);
    auto first = new Z8PostgresConnection(args[1]); auto second = new Z8PostgresConnection(args[1]);
    immutable createSql = `CREATE TEMP TABLE "Reports" ("RecordId" uuid PRIMARY KEY, "CreatedAt" bigint, "ModifiedAt" bigint, "CreatedBy" uuid, "ModifiedBy" uuid, "Lock" bigint, "Amount" bigint)`;
    first.execute(createSql); second.execute(createSql);
    auto db1 = new Z8PostgresDatabase(first, "pg_temp"w), db2 = new Z8PostgresDatabase(second, "pg_temp"w);
    auto previous = z8_connection_set_current(db1);
    auto thread = new Thread({ assert(z8_connection_current_backend() is null); z8_connection_set_current(db2); assert(z8_connection_current_backend() is db2); });
    thread.start(); thread.join(); assert(z8_connection_current_backend() is db1);
    auto report = P.m_make(); auto wrapper = P.m_current();
    P.m_begin(); P.m_insert(report, z8_guid_create(1), z8_optional_wrap(12L));
    P.m_begin(); P.m_insert(report, z8_guid_create(2), z8_optional_wrap(25L)); P.m_rollback();
    assert(first.inTransaction() && z8_optional_require(P.m_count(report)) == 2);
    P.m_flush(); P.m_commit(); assert(!first.inTransaction());
    P.m_begin(); P.m_begin(); P.m_insert(report, z8_guid_create(3), z8_optional_wrap(33L));
    P.m_commit(); P.m_rollback(); assert(z8_optional_require(P.m_count(report)) == 2);
    P.m_execute(`UPDATE "Reports" SET "Amount"=40 WHERE "RecordId"='00000000-0000-0000-0000-000000000001'`w);
    assert(first.execute(`SELECT "Amount" FROM "Reports" WHERE "RecordId"='00000000-0000-0000-0000-000000000001'`).rows[0][0].text == "40");
    P.m_attach(report, wrapper); z8_connection_set_current(db2);
    assert(z8_optional_require(P.m_count(report)) == 2);
    auto other = P.m_make(); assert(z8_optional_require(P.m_count(other)) == 0);
    z8_connection_set_current(previous); first.close(); second.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-connection.exe" if os.name == "nt" else "postgres-connection")
    command = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
               *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
               str(harness), str(runtime)]
    command += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    subprocess.run([*command, "-of=" + str(exe)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        result = subprocess.run([str(exe), connection], env=environment, cwd=temp, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise SystemExit(f"Connection fixture failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
print("BL Connection and request-local PostgreSQL transactions verified")
