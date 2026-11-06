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
import org.zenframework.z8.base.sql.Transaction;
import org.zenframework.z8.base.sql.Database;
import org.zenframework.z8.base.json.JsonObject;
public class Probe {
    public static Connection current() { return Connection.get(); }
    public static Report make() { Report value; return value; }
    public static void attach(Report report, Connection connection) { report.setConnection(connection); }
    public static void begin() { Connection.get().beginTransaction(); }
    public static void commit() { Connection.get().commit(); }
    public static void rollback() { Connection.get().rollback(); }
    public static void flush() { Connection.get().flush(); }
    public static void execute(string sql) { Connection.get().execute(sql); }
    public static void call(string name, primary[] parameters) { Connection.get().call(name, parameters); }
    public static void transactionBegin() { Transaction.begin(); }
    public static void transactionCommit() { Transaction.commit(); }
    public static void transactionRollback() { Transaction.rollback(); }
    public static void transactionFlush() { Transaction.flush(); }
    public static Database database() { return Database.get(); }
    public static Database databaseFromText(string json) { return Database.fromJson(json); }
    public static Database databaseFromObject(JsonObject json) { return Database.fromJson(json); }
    public static JsonObject databaseJson(Database database) { return database.toJson(); }
    public static string databaseSchema(Database database) { return database.schema(); }
    public static Connection databaseConnection(Database database) { return database.connection(); }
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
class Catalog : IZ8DatabaseCatalog {
    IZ8DatabaseConnection target;
    Z8DatabaseDescriptor observed;
    this(IZ8DatabaseConnection target) { this.target = target; }
    Z8DatabaseDescriptor currentDatabase() { return Z8DatabaseDescriptor("pg_temp"w, "user"w, "secret"w, "dsn"w, "postgres"w, "UTF-8"w); }
    IZ8DatabaseConnection connectionFor(Z8DatabaseDescriptor descriptor) { observed = descriptor; return target; }
}
void main(string[] args) {
    alias P = Z8p_50726F6265;
    bool missing; try { P.m_current(); } catch (Exception) { missing = true; } assert(missing);
    missing = false; try { P.m_transactionBegin(); } catch (Exception) { missing = true; } assert(missing);
    auto first = new Z8PostgresConnection(args[1]); auto second = new Z8PostgresConnection(args[1]);
    immutable createSql = `CREATE TEMP TABLE "Reports" ("RecordId" uuid PRIMARY KEY, "CreatedAt" bigint, "ModifiedAt" bigint, "CreatedBy" uuid, "ModifiedBy" uuid, "Lock" bigint, "Amount" bigint)`;
    first.execute(createSql); second.execute(createSql);
    first.execute(`CREATE TEMP TABLE "Calls" ("I" bigint, "B" integer, "N" numeric, "G" uuid, "T" bigint, "S" bigint, "Bytes" bytea, "Text" text, "Null" text, "Geom" bytea)`);
    first.execute(`CREATE PROCEDURE pg_temp."Capture"";quote" (bigint, integer, numeric, uuid, bigint, bigint, bytea, text, text, bytea) LANGUAGE plpgsql AS $$ BEGIN INSERT INTO "Calls" VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10); END $$`);
    first.execute(`CREATE PROCEDURE pg_temp."Noop" () LANGUAGE plpgsql AS $$ BEGIN NULL; END $$`);
    auto db1 = new Z8PostgresDatabase(first, "pg_temp"w), db2 = new Z8PostgresDatabase(second, "pg_temp"w);
    first.execute(`CREATE TABLE public.z8_background_probe (value bigint)`);
    auto background = cast(IZ8BackgroundDatabaseConnection)db1.openBackgroundConnection();
    auto backgroundDb = cast(IZ8DatabaseConnection)background;
    backgroundDb.beginTransaction(); backgroundDb.execute(`INSERT INTO public.z8_background_probe VALUES (3)`w); backgroundDb.rollback();
    assert(first.execute(`SELECT count(*) FROM public.z8_background_probe`).rows[0][0].text == "0");
    backgroundDb.execute(`INSERT INTO public.z8_background_probe VALUES (5)`w); background.closeBackgroundConnection();
    assert(first.execute(`SELECT value FROM public.z8_background_probe`).rows[0][0].text == "5");
    auto previous = z8_connection_set_current(db1);
    auto defaultDatabase = P.m_database();
    assert(P.m_databaseSchema(defaultDatabase) == "pg_temp"w);
    auto catalog = new Catalog(db2);
    auto previousCatalog = z8_database_set_catalog(catalog);
    auto currentDatabase = P.m_database(); auto currentJson = P.m_databaseJson(currentDatabase);
    assert(currentJson.m_getString("user"w) == "user"w && currentJson.m_getString("password"w) == "secret"w);
    auto parsedDatabase = P.m_databaseFromText(`{schema:'other',user:'alice',password:'pw',connection:'dsn2',driver:'postgres',charset:'utf-16le'}`w);
    assert(P.m_databaseSchema(parsedDatabase) == "other"w);
    auto json = P.m_databaseJson(parsedDatabase);
    assert(json.m_getString("charset"w) == "UTF-16LE"w && json.m_getString("connection"w) == "dsn2"w);
    auto copiedDatabase = P.m_databaseFromObject(json);
    assert(P.m_databaseSchema(copiedDatabase) == "other"w);
    auto external = P.m_make(); P.m_attach(external, P.m_databaseConnection(copiedDatabase));
    assert(catalog.observed.schema == "other"w && catalog.observed.user == "alice"w);
    assert(z8_optional_require(P.m_count(external)) == 0);
    z8_database_set_catalog(previousCatalog);
    auto thread = new Thread({ assert(z8_connection_current_backend() is null); z8_connection_set_current(db2); assert(z8_connection_current_backend() is db2); });
    thread.start(); thread.join(); assert(z8_connection_current_backend() is db1);
    auto report = P.m_make(); auto wrapper = P.m_current();
    auto parameters = new Z8Array!Z8Primary([z8_primary_box(42L), z8_primary_box(true), z8_primary_box(z8_decimal_parse("12.30"w)),
        z8_primary_box(z8_guid_create(7)), z8_primary_box(z8_date_from_ticks(1234)), z8_primary_box(new Z8Datespan(7654)),
        z8_primary_box(new Z8Binary([cast(ubyte)0, 1, 255])), z8_primary_box("O'Reilly 😀"w), null,
        z8_primary_box(z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 4326))]);
    P.m_begin(); P.m_call(`Capture";quote`w, parameters); P.m_rollback();
    assert(first.execute(`SELECT count(*) FROM "Calls"`).rows[0][0].text == "0");
    parameters.z8_set(6, z8_primary_box(new Z8Binary([cast(ubyte)0, 1, 255])));
    P.m_call(`Capture";quote`w, parameters); P.m_call("Noop"w, new Z8Array!Z8Primary());
    auto callResult = first.execute(`SELECT "I","B","N","G","T","S",encode("Bytes",'hex'),"Text","Null",octet_length("Geom") FROM "Calls"`);
    assert(callResult.rows.length == 1 && callResult.rows[0][0].text == "42" && callResult.rows[0][1].text == "1" && callResult.rows[0][2].text == "12.30");
    assert(callResult.rows[0][3].text == "00000000-0000-0000-0000-000000000007" && callResult.rows[0][4].text == "1234" && callResult.rows[0][5].text == "7654");
    assert(callResult.rows[0][6].text == "0001ff" && callResult.rows[0][7].text == "O'Reilly 😀" && callResult.rows[0][8].isNull && callResult.rows[0][9].text != "0");
    bool unsupported; try { P.m_call("Noop"w, new Z8Array!Z8Primary([z8_primary_box(report)])); } catch (Z8PostgresException) { unsupported = true; }
    assert(unsupported && first.execute(`SELECT count(*) FROM "Calls"`).rows[0][0].text == "1");
    P.m_begin(); P.m_insert(report, z8_guid_create(1), z8_optional_wrap(12L));
    P.m_begin(); P.m_insert(report, z8_guid_create(2), z8_optional_wrap(25L)); P.m_rollback();
    assert(first.inTransaction() && z8_optional_require(P.m_count(report)) == 2);
    P.m_flush(); P.m_commit(); assert(!first.inTransaction());
    P.m_begin(); P.m_begin(); P.m_insert(report, z8_guid_create(3), z8_optional_wrap(33L));
    P.m_commit(); P.m_rollback(); assert(z8_optional_require(P.m_count(report)) == 2);
    P.m_transactionBegin(); P.m_insert(report, z8_guid_create(4), z8_optional_wrap(44L));
    P.m_transactionBegin(); P.m_insert(report, z8_guid_create(5), z8_optional_wrap(55L));
    P.m_transactionCommit(); P.m_transactionRollback(); assert(z8_optional_require(P.m_count(report)) == 2);
    P.m_transactionBegin(); P.m_insert(report, z8_guid_create(6), z8_optional_wrap(66L));
    P.m_transactionFlush(); P.m_transactionCommit(); assert(z8_optional_require(P.m_count(report)) == 3);
    P.m_execute(`UPDATE "Reports" SET "Amount"=40 WHERE "RecordId"='00000000-0000-0000-0000-000000000001'`w);
    assert(first.execute(`SELECT "Amount" FROM "Reports" WHERE "RecordId"='00000000-0000-0000-0000-000000000001'`).rows[0][0].text == "40");
    P.m_attach(report, wrapper); z8_connection_set_current(db2);
    assert(z8_optional_require(P.m_count(report)) == 3);
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
