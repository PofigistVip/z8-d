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
    virtual protected sql_bool scope() { return amount >= 0; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.SortDirection;
import org.zenframework.z8.base.table.value.Aggregation;
public class Probe {
    public static Sales make() { Sales table; return table; }
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
    public static int[] groupValues(Sales table) { return table.amount.array(); }
    public static bool groupFlag(Sales table) { return table.flag.get(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8gen.p_Probe;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute(`CREATE TEMP TABLE "Sales""Quote" ("RecordId" uuid, "Amount" bigint, "Title" varchar(30), "Flag" smallint, "Info" bytea, "Blob" bytea, "When" bigint)`);
    db.execute(`INSERT INTO "Sales""Quote" VALUES ('00000000-0000-0000-0000-000000000001',10,'O''Reilly',1,convert_to('Русский 😀','UTF8'),decode('0001ff','hex'),1234)`);
    db.execute(`INSERT INTO "Sales""Quote" VALUES ('00000000-0000-0000-0000-000000000002',20,NULL,NULL,NULL,NULL,NULL)`);
    db.execute(`INSERT INTO "Sales""Quote" VALUES ('00000000-0000-0000-0000-000000000003',-1,'hidden',1,NULL,NULL,NULL)`);
    auto table = P.m_make();
    z8_query_set_executor(table, new Z8PostgresQueryExecutor(db, "pg_temp"w, `Sales"Quote`w));
    P.m_read(table);
    assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_firstRow(table)));
    assert(z8_optional_require(P.m_count(table)) == 2 && z8_optional_require(P.m_countWhere(table)) == 1);
    assert(z8_optional_require(P.m_firstRow(table)));
    assert(z8_optional_require(P.m_next(table)) && z8_optional_require(P.m_secondRow(table)));
    assert(!z8_optional_require(P.m_next(table)));
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
    db.execute(`INSERT INTO "Sales""Quote" VALUES ('00000000-0000-0000-0000-000000000004',5,'O''Reilly',1,NULL,NULL,NULL)`);
    P.m_groupSum(table);
    long sum, groups;
    while (z8_optional_require(P.m_next(table))) { sum += z8_optional_require(P.m_amount(table)); ++groups; }
    assert(groups == 2 && sum == 35);
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
