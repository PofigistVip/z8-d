"""Run generated BL Query reads against an isolated PostgreSQL cluster."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_query.py <original-z8-root> [postgres-bin-directory]")
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
    (source / "Sales.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.BoolField;
import org.zenframework.z8.base.table.value.TextField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.DatetimeField;
public class Sales extends Table {
    [name "Amount"] public IntField amount;
    [name "Title"] public StringField title;
    [name "Flag"] public BoolField flag;
    [name "Info"] public TextField info;
    [name "Blob"] public BinaryField blob;
    [name "When"] public DatetimeField instant;
    public string events = "";
    public bool copying = false;
    public bool observeRead = false; public int observedRead;
    virtual protected sql_bool scope() { return amount >= 0; }
    virtual protected void onNew() { events += "N"; if (copying) flag = false; }
    virtual protected void beforeRead() { if (observeRead) observedRead = amount.get(); }
    virtual protected void onCopy(guid id) { events += "O"; }
    virtual protected void beforeCreate(guid id) { super.beforeCreate(id); events += "C"; }
    virtual protected void afterCreate(guid id) { events += "A"; }
    virtual protected void beforeUpdate(guid id) { super.beforeUpdate(id); events += "U"; }
    virtual protected void afterUpdate(guid id) { events += "V"; }
    virtual protected void beforeDestroy(guid id) { events += "D"; }
    virtual protected void afterDestroy(guid id) { events += "E"; }
}
''', encoding="utf-8")
    (source / "Plain.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.NowField;
public class Plain extends Table { [name "When"] public NowField moment; }
''', encoding="utf-8")
    (source / "Quiet.bl").write_text('''
public class Quiet extends Plain {
    virtual protected void beforeCreate(guid id) {}
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.SortDirection;
import org.zenframework.z8.base.table.value.Aggregation;
public class Probe {
    public static Sales make() { Sales table; return table; }
    public static Plain makePlain() { Plain table; return table; }
    public static Quiet makeQuiet() { Quiet table; return table; }
    public static guid createPlain(Plain table, guid id) { return table.create(id); }
    public static void read(Sales table) {
        Field[] fields = {table.amount, table.title, table.flag, table.info, table.blob, table.instant};
        Field[] sort = {table.amount}; table.amount.sortDirection = SortDirection.Desc;
        table.read(fields, sort, table.amount >= 0);
    }
    public static void page(Sales table) {
        Field[] fields = {table.amount, table.title}; Field[] sort = {table.amount};
        table.amount.sortDirection = SortDirection.Desc; table.read(fields, sort, table.amount >= 0, 1, 1);
    }
    public static void readDefault(Sales table) {
        table.controls = {table.title}; table.names = {table.amount}; table.columns = {table.title};
        Field[] fields = {}; table.read(fields);
    }
    public static void readKeyOnly(Sales table) {
        table.controls.clear(); table.names.clear(); table.columns.clear();
        Field[] fields = {}; table.read(fields);
    }
    public static bool record(Sales table, guid id) { Field[] fields = {table.amount}; return table.readRecord(id, fields); }
    public static int count(Sales table) { return table.count(); }
    public static int countWhere(Sales table) { return table.count(table.amount > 10); }
    public static bool hasId(Sales table, guid id) { return table.hasRecord(id); }
    public static bool hasWhere(Sales table) { return table.hasRecord(table.amount > 10); }
    public static guid[] find(Sales table) { return table.findRecords(table.amount >= 0); }
    public static bool next(Sales table) { return table.next(); }
    public static void close(Sales table) { table.close(); }
    public static bool firstRow(Sales table) {
        if (table.amount.get() != 20 || table.recordId() != guid.create(2)) return false;
        if (table.title.get() != "" || !table.title.wasNull()) return false;
        if (table.flag.get() || !table.flag.wasNull()) return false;
        if (table.info.get() != "" || !table.info.wasNull()) return false;
        if (table.blob.get().length() != 0 || !table.blob.wasNull()) return false;
        return table.instant.get() == date.Min && table.instant.wasNull();
    }
    public static bool secondRow(Sales table) {
        return table.amount.get() == 10 && table.recordId() == guid.create(1) &&
            table.title.get() == "O'Reilly" && !table.title.wasNull() && table.flag.get() &&
            table.info.get() == "Русский 😀" && table.blob.get().length() == 3 && table.instant.get().ticks() == 1234;
    }
    public static int amount(Sales table) { return table.amount.get(); }
    public static void groupSum(Sales table) {
        table.title.aggregation = Aggregation.None; table.amount.aggregation = Aggregation.Sum;
        Field[] groups = {table.title}; Field[] fields = {table.amount, table.title};
        table.group(groups, fields, table.amount >= 0, table.amount > 5);
    }
    public static void groupArray(Sales table) {
        table.flag.aggregation = Aggregation.None; table.amount.aggregation = Aggregation.Array;
        table.amount.arrayOrderBy.add(table.amount); table.amount.sortDirection = SortDirection.Desc;
        Field[] groups = {table.flag}; Field[] fields = {table.flag, table.amount};
        table.group(groups, fields);
    }
    public static void groupConfigured(Sales table) {
        table.flag.aggregation = Aggregation.None; table.amount.aggregation = Aggregation.Sum;
        table.groupBy = {table.flag}; Field[] fields = {table.flag, table.amount}; table.read(fields);
    }
    public static void clearGroup(Sales table) { table.groupBy.clear(); }
    public static void setGroup(Sales table) { table.groupBy = {table.flag}; }
    public static bool hasGroup(Sales table) { return table.groupBy.size() == 1; }
    public static int[] groupValues(Sales table) { return table.amount.array(); }
    public static bool groupFlag(Sales table) { return table.flag.get(); }
    public static void prepareCreate(Sales table) {
        table.amount = 33; table.title = "New O'Reilly"; table.flag = true;
        table.info = "Данные 😀"; table.blob = '1, 2, 255'; table.instant = 1234;
    }
    public static guid create(Sales table, guid id) { return table.create(id); }
    public static guid copy(Sales table, guid id) { return table.copy(id); }
    public static void prepareCopy(Sales table) { table.amount = 88; table.title.unique = true; table.copying = true; }
    public static void finishCopy(Sales table) { table.copying = false; }
    public static void observeRead(Sales table) { table.observeRead = true; }
    public static int observedRead(Sales table) { return table.observedRead; }
    public static void prepareUpdate(Sales table) {
        table.amount = 40; table.title = "Changed"; table.info = "Обновлено"; table.blob = '9, 8';
    }
    public static void prepareBulk(Sales table) { table.amount = 77; }
    public static int update(Sales table, guid id) { return table.update(id); }
    public static int updateWhere(Sales table) { return table.update(table.amount >= 10); }
    public static int updateNoMatch(Sales table) { return table.update(table.amount > 1000); }
    public static int destroy(Sales table, guid id) { return table.destroy(id); }
    public static int destroyWhere(Sales table) { return table.destroy(table.amount >= 10); }
    public static string events(Sales table) { return table.events; }
    public static void clearEvents(Sales table) { table.events = ""; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8gen.p_Probe;
import std.conv : to;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute(`CREATE TEMP TABLE "Sales""Quote" ("RecordId" uuid PRIMARY KEY, "CreatedAt" bigint, "ModifiedAt" bigint, "CreatedBy" uuid, "ModifiedBy" uuid, "Lock" bigint, "Amount" bigint, "Title" varchar(30), "Flag" smallint, "Info" bytea, "Blob" bytea, "When" bigint)`);
    db.execute(`INSERT INTO "Sales""Quote" ("RecordId","Amount","Title","Flag","Info","Blob","When") VALUES ('00000000-0000-0000-0000-000000000001',10,'O''Reilly',1,convert_to('Русский 😀','UTF8'),decode('0001ff','hex'),1234)`);
    db.execute(`INSERT INTO "Sales""Quote" ("RecordId","Amount","Title","Flag","Info","Blob","When") VALUES ('00000000-0000-0000-0000-000000000002',20,NULL,NULL,NULL,NULL,NULL)`);
    db.execute(`INSERT INTO "Sales""Quote" ("RecordId","Amount","Title","Flag","Info","Blob","When") VALUES ('00000000-0000-0000-0000-000000000003',-1,'hidden',1,NULL,NULL,NULL)`);
    auto table = P.m_make();
    z8_query_set_executor(table, new Z8PostgresQueryExecutor(db, "pg_temp"w, `Sales"Quote`w));
    P.m_read(table);
    assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_firstRow(table)));
    assert(z8_optional_require(P.m_count(table)) == 2 && z8_optional_require(P.m_countWhere(table)) == 1);
    assert(z8_optional_require(P.m_hasId(table, z8_guid_create(3))));
    assert(!z8_optional_require(P.m_hasId(table, z8_guid_create(999))));
    assert(z8_optional_require(P.m_firstRow(table)));
    assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_secondRow(table)));
    assert(!z8_optional_require(P.m_next(table)));
    assert(z8_optional_require(P.m_hasWhere(table)) && table.m_recordId() == z8_guid_create(2));
    P.m_close(table);
    auto found = P.m_find(table);
    assert(found.z8_size() == 2 && found.z8_contains(z8_guid_create(1)) && found.z8_contains(z8_guid_create(2)));
    P.m_page(table); assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_amount(table)) == 10);
    assert(!z8_optional_require(P.m_next(table)));
    P.m_readDefault(table); long defaultRows;
    while (z8_optional_require(P.m_next(table))) { assert(z8_optional_require(P.m_amount(table)) > 0); ++defaultRows; }
    assert(defaultRows == 2);
    P.m_readKeyOnly(table); long keys;
    while (z8_optional_require(P.m_next(table))) { assert(table.m_recordId() != z8_guid_zero()); ++keys; }
    assert(keys == 2);
    assert(z8_optional_require(P.m_record(table, z8_guid_create(3))) && z8_optional_require(P.m_amount(table)) == -1);
    P.m_close(table);
    db.execute(`INSERT INTO "Sales""Quote" ("RecordId","Amount","Title","Flag","Info","Blob","When") VALUES ('00000000-0000-0000-0000-000000000004',5,'O''Reilly',1,NULL,NULL,NULL)`);
    P.m_groupSum(table);
    long sum, groups;
    while (z8_optional_require(P.m_next(table))) { sum += z8_optional_require(P.m_amount(table)); ++groups; }
    assert(groups == 2 && sum == 35);
    P.m_clearGroup(table);
    db.execute(`INSERT INTO "Sales""Quote" ("RecordId","Amount","Title") VALUES ('00000000-0000-0000-0000-000000000000',99,'sentinel')`);
    assert(z8_optional_require(P.m_count(table)) == 3 && !z8_optional_require(P.m_hasId(table, z8_guid_zero())));
    auto ids = P.m_find(table); assert(ids.z8_size() == 3 && !ids.z8_contains(z8_guid_zero()));
    P.m_groupSum(table); long sentinelGroups, sentinelSum;
    while (z8_optional_require(P.m_next(table))) { sentinelSum += z8_optional_require(P.m_amount(table)); ++sentinelGroups; }
    assert(sentinelGroups == 3 && sentinelSum == 134);
    db.execute(`DELETE FROM "Sales""Quote" WHERE "RecordId" = '00000000-0000-0000-0000-000000000000'`);
    P.m_groupArray(table); groups = 0; sum = 0;
    while (z8_optional_require(P.m_next(table))) {
        auto values = P.m_groupValues(table);
        if (values.z8_size() == 2) assert(values.z8_get(0) == 10 && values.z8_get(1) == 5);
        else assert(values.z8_size() == 1 && values.z8_get(0) == 20);
        for (long i; i < values.z8_size(); ++i) sum += z8_optional_require(values.z8_get(i));
        ++groups;
    }
    assert(groups == 2 && sum == 35);
    P.m_groupConfigured(table); groups = 0; sum = 0;
    assert(z8_optional_require(P.m_count(table)) == 2);
    while (z8_optional_require(P.m_next(table))) { sum += z8_optional_require(P.m_amount(table)); ++groups; }
    assert(groups == 2 && sum == 35);
    P.m_clearGroup(table);
    db.execute("BEGIN"); P.m_prepareBulk(table);
    assert(z8_optional_require(P.m_updateWhere(table)) == 2 && P.m_events(table) == "UVUV"w);
    assert(db.execute(`SELECT count(*) FROM "Sales""Quote" WHERE "Amount"=77`).rows[0][0].text == "2");
    assert(!z8_field_is_changed(table.f_amount));
    db.execute("ROLLBACK"); P.m_clearEvents(table);
    P.m_prepareBulk(table);
    assert(z8_optional_require(P.m_updateNoMatch(table)) == 0 && !z8_field_is_changed(table.f_amount));
    db.execute("BEGIN"); P.m_setGroup(table);
    assert(z8_optional_require(P.m_destroyWhere(table)) == 2 && P.m_events(table) == "DEDE"w);
    assert(z8_optional_require(P.m_hasGroup(table)));
    assert(db.execute(`SELECT count(*) FROM "Sales""Quote"`).rows[0][0].text == "2");
    db.execute("ROLLBACK"); P.m_clearGroup(table); P.m_clearEvents(table);
    db.execute("BEGIN");
    P.m_read(table); assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_amount(table)) == 20);
    P.m_prepareCopy(table); P.m_observeRead(table);
    assert(z8_optional_require(P.m_hasId(table, z8_guid_create(2))));
    assert(z8_optional_require(P.m_observedRead(table)) == 0 && z8_optional_require(P.m_amount(table)) == 88);
    auto copied = P.m_copy(table, z8_guid_create(1));
    assert(z8_optional_require(P.m_observedRead(table)) == 0);
    assert(copied != z8_guid_create(1) && copied != z8_guid_zero() && P.m_events(table) == "NOCA"w);
    auto copyRow = db.execute(`SELECT "Amount", "Title", "Flag", convert_from("Info",'UTF8') FROM "Sales""Quote" WHERE "RecordId"=$1::uuid`, [Z8PostgresParameter.value(z8_guid_to_string(copied).to!string)]);
    assert(copyRow.rows.length == 1 && copyRow.rows[0][0].text == "88" && copyRow.rows[0][1].text == "");
    assert(copyRow.rows[0][2].text == "1" && copyRow.rows[0][3].text == "Русский 😀");
    assert(z8_optional_require(P.m_amount(table)) == 20 && z8_optional_require(P.m_next(table)));
    P.m_close(table);
    auto missingCopy = P.m_copy(table, z8_guid_create(999));
    auto missingRow = db.execute(`SELECT "Amount", "Flag" FROM "Sales""Quote" WHERE "RecordId"=$1::uuid`, [Z8PostgresParameter.value(z8_guid_to_string(missingCopy).to!string)]);
    assert(missingRow.rows.length == 1 && missingRow.rows[0][0].text == "0" && missingRow.rows[0][1].text == "0");
    assert(P.m_events(table) == "NOCANOCA"w);
    db.execute("ROLLBACK"); P.m_finishCopy(table); P.m_clearEvents(table);
    db.execute("BEGIN");
    auto request = new Z8ApplicationRequest();
    auto creator = new Z8UserData(); creator.id = z8_guid_create(101);
    auto editor = new Z8UserData(); editor.id = z8_guid_create(102);
    request.session = new Z8ApplicationSession("test"w, creator, creator);
    auto previousRequest = z8_application_set_request(request);
    auto beforeAudit = z8_date_ticks(z8_date_now());
    P.m_prepareCreate(table); P.m_create(table, z8_guid_create(43));
    request.session.switchUser(editor); P.m_prepareUpdate(table);
    assert(z8_optional_require(P.m_update(table, z8_guid_create(43))) == 1);
    auto audit = db.execute(`SELECT "CreatedAt", "CreatedBy", "ModifiedAt", "ModifiedBy" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002b'`);
    assert(audit.rows[0][0].text.to!long >= beforeAudit && audit.rows[0][2].text.to!long >= beforeAudit);
    assert(audit.rows[0][1].text == "00000000-0000-0000-0000-000000000065" && audit.rows[0][3].text == "00000000-0000-0000-0000-000000000066");
    auto plain = P.m_makePlain(); auto quiet = P.m_makeQuiet();
    z8_query_set_executor(plain, new Z8PostgresQueryExecutor(db, "pg_temp"w, `Sales"Quote`w));
    z8_query_set_executor(quiet, new Z8PostgresQueryExecutor(db, "pg_temp"w, `Sales"Quote`w));
    P.m_createPlain(plain, z8_guid_create(45)); P.m_createPlain(quiet, z8_guid_create(46));
    auto inherited = db.execute(`SELECT "RecordId", "CreatedBy", "When" FROM "Sales""Quote" WHERE "RecordId" IN ('00000000-0000-0000-0000-00000000002d','00000000-0000-0000-0000-00000000002e') ORDER BY "RecordId"`);
    assert(inherited.rows[0][1].text == "00000000-0000-0000-0000-000000000066");
    assert(inherited.rows[1][1].text == "00000000-0000-0000-0000-000000000066");
    assert(inherited.rows[0][2].text.to!long >= beforeAudit && inherited.rows[1][2].text.to!long >= beforeAudit);
    auto eventsBeforeSuppression = P.m_events(table);
    request.setEventsLevel(Z8EventsLevel.system); P.m_prepareCreate(table); P.m_create(table, z8_guid_create(47));
    P.m_createPlain(plain, z8_guid_create(48));
    auto defaultSuppressed = db.execute(`SELECT "When" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-000000000030'`);
    assert(defaultSuppressed.rows[0][0].text.to!long < beforeAudit);
    auto systemOnly = db.execute(`SELECT "CreatedBy" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002f'`);
    assert(systemOnly.rows[0][0].text == "00000000-0000-0000-0000-000000000066" && P.m_events(table) == eventsBeforeSuppression);
    request.setEventsLevel(Z8EventsLevel.none); P.m_prepareCreate(table); P.m_create(table, z8_guid_create(44));
    auto noAudit = db.execute(`SELECT "CreatedBy" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002c'`);
    assert(noAudit.rows[0][0].isNull || noAudit.rows[0][0].text != "00000000-0000-0000-0000-000000000066");
    assert(P.m_events(table) == eventsBeforeSuppression);
    request.restoreEventsLevel(); assert(request.eventsLevel() == Z8EventsLevel.system);
    request.restoreEventsLevel(); assert(request.eventsLevel() == Z8EventsLevel.all);
    z8_application_set_request(previousRequest); db.execute("ROLLBACK"); P.m_clearEvents(table);
    P.m_prepareCreate(table);
    assert(P.m_create(table, z8_guid_create(42)) == z8_guid_create(42) && P.m_events(table) == "NCA"w);
    auto inserted = db.execute(`SELECT "Amount", "Title", "Flag", convert_from("Info",'UTF8'), encode("Blob",'hex'), "When" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002a'`);
    assert(inserted.rows.length == 1 && inserted.rows[0][0].text == "33" && inserted.rows[0][1].text == "New O'Reilly");
    assert(inserted.rows[0][2].text == "1" && inserted.rows[0][3].text == "Данные 😀" && inserted.rows[0][4].text == "0102ff" && inserted.rows[0][5].text == "1234");
    P.m_prepareUpdate(table);
    assert(z8_optional_require(P.m_update(table, z8_guid_create(42))) == 1 && P.m_events(table) == "NCAUV"w);
    auto updated = db.execute(`SELECT "Amount", "Title", convert_from("Info",'UTF8'), encode("Blob",'hex') FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002a'`);
    assert(updated.rows[0][0].text == "40" && updated.rows[0][1].text == "Changed" && updated.rows[0][2].text == "Обновлено" && updated.rows[0][3].text == "0908");
    z8_field_set(table.f_title, null); z8_field_set(table.f_info, null); z8_field_set(table.f_blob, null);
    assert(z8_optional_require(P.m_update(table, z8_guid_create(42))) == 1);
    auto nulls = db.execute(`SELECT "Title", "Info", "Blob" FROM "Sales""Quote" WHERE "RecordId"='00000000-0000-0000-0000-00000000002a'`);
    assert(nulls.rows[0][0].isNull && nulls.rows[0][1].isNull && nulls.rows[0][2].isNull);
    db.execute("BEGIN"); P.m_prepareBulk(table);
    assert(z8_optional_require(P.m_update(table, null)) == 5);
    assert(db.execute(`SELECT count(*) FROM "Sales""Quote" WHERE "Amount"=77`).rows[0][0].text == "5");
    db.execute("ROLLBACK");
    assert(z8_optional_require(P.m_destroy(table, z8_guid_create(42))) == 1 && P.m_events(table) == "NCAUVUVDE"w);
    assert(!z8_optional_require(P.m_hasId(table, z8_guid_create(42))));
    assert(z8_optional_require(P.m_destroy(table, z8_guid_zero())) == 0 && P.m_events(table) == "NCAUVUVDE"w);
    assert(z8_optional_require(P.m_destroy(table, null)) == 0 && P.m_events(table) == "NCAUVUVDEDE"w);
    P.m_prepareCreate(table); bool duplicate;
    try { P.m_create(table, z8_guid_create(1)); } catch (Z8PostgresException) { duplicate = true; }
    assert(duplicate && P.m_events(table) == "NCAUVUVDEDENC"w && z8_field_is_changed(table.f_amount));
    assert(z8_optional_require(P.m_amount(table)) == 33);
    db.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-query.exe" if os.name == "nt" else "postgres-query")
    command = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
               *map(str, generated.rglob("*.d")), str(root / "postgres/source/z8/database/postgres.d"),
               str(root / "postgres/source/z8/database/query.d"), str(harness), str(runtime)]
    command += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    subprocess.run([*command, "-of=" + str(exe)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        subprocess.run([str(exe), connection], env=environment, cwd=temp, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
print("Generated BL table reads match the PostgreSQL integration fixture")
