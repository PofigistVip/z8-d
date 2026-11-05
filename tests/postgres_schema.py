"""Generate PostgreSQL CREATE TABLE DDL from a real BL Table definition."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_schema.py <original-z8-root> [postgres-bin-directory]")
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
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.BoolField;
import org.zenframework.z8.base.table.value.DecimalField;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.DatetimeField;
import org.zenframework.z8.base.table.value.DatespanField;
import org.zenframework.z8.base.table.value.TextField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.IntExpression;
[name "Sample;--"] public class Sample extends Table {
    [name "Title"] public StringField title; title.defaultValue = "O'Reilly 😀";
    [name "Amount"] public IntField amount; amount.defaultValue = 7;
    [name "Flag"] public BoolField flag; flag.defaultValue = true;
    [name "Price"] public DecimalField price; price.defaultValue = 12.50;
    [name "Reference"] public GuidField reference;
    [name "Moment"] public DatetimeField moment;
    [name "Duration"] public DatespanField duration;
    [name "Details"] public TextField details;
    [name "Blob"] public BinaryField blob;
    public IntExpression computed;
}
''', encoding="utf-8")
    (source / "GeoSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GeometryField;
[name "GeoSample"] public class GeoSample extends Table { [name "Shape"] public GeometryField shape; shape.indexed = true; }
''', encoding="utf-8")
    (source / "IndexSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
[name "IndexSample"] public class IndexSample extends Table {
    [name "Title"] public StringField title; title.unique = true; title.caseInsensitive = true;
    [name "Search"] public StringField search; search.trigram = true; search.caseInsensitive = true;
    [name "Amount"] public IntField amount; amount.indexed = true;
    [name "Ignored"] public StringField ignored;
}
''', encoding="utf-8")
    (source / "ReferenceTarget.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "Target;--"] public class ReferenceTarget extends Table {
    [name "Label"] public StringField label;
    virtual protected void onNew() { label = "created by hook"; }
}
''', encoding="utf-8")
    (source / "ReferenceSource.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
[name "Source"] public class ReferenceSource extends Table {
    public ReferenceTarget target;
    [name "TargetId"] public Link targetId = target;
    [name "UncheckedId"] [foreignKey false] public Link unchecked = target;
    [name "ParentId"] [parentKey true] public Link parent;
}
''', encoding="utf-8")
    (source / "StaticSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
[name "StaticSample"] public class StaticSample extends Table {
    [name "Label"] public StringField label;
    [name "Counter"] public IntField counter;
    [name "Other"] public StringField other;
    virtual protected void beforeUpdate(guid id) { counter = 55; }
    records {
        [label "Seed"] [counter 12] First = '00000000-0000-0000-0000-000000000031';
        [label "Second"] Second = '00000000-0000-0000-0000-000000000032';
    }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static Sample make() { Sample value; return value; }
    public static GeoSample geo() { GeoSample value; return value; }
    public static IndexSample indexes() { IndexSample value; return value; }
    public static ReferenceSource references() { ReferenceSource value; return value; }
    public static ReferenceTarget target() { ReferenceTarget value; return value; }
    public static StaticSample statics() { StaticSample value; return value; }
    public static int count(Sample value) { return value.count(); }
    public static void create(Sample value, guid id) { value.create(id); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.schema;
import z8.database.catalog;
import z8.database.compare;
import z8.database.migration;
import z8gen.p_Probe;
import std.algorithm.searching : canFind;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute("CREATE TEMP TABLE init_temp (id integer)");
    auto table = P.m_make();
    auto ddl = z8_postgres_create_table_sql("pg_temp"w, table);
    assert(ddl.canFind(`"Sample;--"`) && ddl.canFind(`"Title" character varying DEFAULT 'O''Reilly 😀'`));
    assert(!ddl.canFind("computed") && ddl.canFind(`"Reference" uuid DEFAULT '00000000-0000-0000-0000-000000000000' NOT NULL`));
    assert(ddl.canFind(`PRIMARY KEY ("RecordId")`));
    auto geo = z8_postgres_create_table_sql("pg_temp"w, P.m_geo());
    assert(geo.canFind(`"Shape" geometry(Geometry, 3857) DEFAULT NULL`));
    bool geometryIndex;
    foreach (index; z8_postgres_create_indexes_sql("pg_temp"w, P.m_geo()))
        if (index.canFind(`USING gist ("Shape")`)) geometryIndex = true;
    assert(geometryIndex);
    auto indexedTable = P.m_indexes();
    db.execute(z8_postgres_create_table_sql("pg_temp"w, indexedTable));
    db.execute("CREATE EXTENSION pg_trgm");
    bool uniqueIndex, trigramIndex, amountIndex;
    foreach (index; z8_postgres_create_indexes_sql("pg_temp"w, indexedTable)) {
        assert(!index.canFind(`"Ignored"`));
        if (index.canFind(`LOWER("Title")`)) uniqueIndex = index.canFind("CREATE UNIQUE INDEX");
        if (index.canFind(`USING gin (LOWER("Search") gin_trgm_ops)`)) trigramIndex = true;
        if (index.canFind(`("Amount")`)) amountIndex = true;
        db.execute(index);
    }
    assert(uniqueIndex && trigramIndex && amountIndex);
    db.execute(`INSERT INTO "IndexSample" ("RecordId", "Title") VALUES ('00000000-0000-0000-0000-000000000011', 'Alice')`);
    bool insensitiveDuplicate;
    try { db.execute(`INSERT INTO "IndexSample" ("RecordId", "Title") VALUES ('00000000-0000-0000-0000-000000000012', 'ALICE')`); }
    catch (Z8PostgresException) { insensitiveDuplicate = true; }
    assert(insensitiveDuplicate);
    auto referenced = P.m_target(); auto referencing = P.m_references();
    db.execute(z8_postgres_create_table_sql("pg_temp"w, referenced));
    db.execute(z8_postgres_create_table_sql("pg_temp"w, referencing));
    auto priorBackend = new Z8PostgresDatabase(db, "pg_temp"w);
    auto priorConnection = z8_connection_set_current(priorBackend);
    auto priorExecutor = priorBackend.queryExecutor(referenced);
    z8_query_set_executor(referenced, priorExecutor);
    assert(z8_postgres_ensure_null_record(db, "pg_temp"w, referenced));
    assert(z8_connection_current_backend() is priorBackend);
    assert(z8_query_swap_executor(referenced, null) is priorExecutor);
    z8_connection_set_current(priorConnection);
    assert(!z8_postgres_ensure_null_record(db, "pg_temp"w, referenced));
    assert(db.execute(`SELECT "Label" FROM "Target;--"`).rows[0][0].text == "created by hook");
    assert(z8_postgres_ensure_null_record(db, "pg_temp"w, referencing));
    assert(!z8_postgres_ensure_null_record(db, "pg_temp"w, referencing));
    auto foreignKeys = z8_postgres_create_foreign_keys_sql("pg_temp"w, referencing);
    assert(foreignKeys.length == 2);
    bool targetKey, parentKey;
    foreach (sql; foreignKeys) {
        assert(!sql.canFind("UncheckedId"));
        if (sql.canFind(`FOREIGN KEY ("TargetId") REFERENCES "pg_temp"."Target;--" ("RecordId")`)) targetKey = true;
        if (sql.canFind(`FOREIGN KEY ("ParentId") REFERENCES "pg_temp"."Source" ("RecordId")`)) parentKey = true;
        db.execute(sql);
    }
    assert(targetKey && parentKey);
    db.execute(`INSERT INTO "Source" ("RecordId", "UncheckedId") VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000099')`);
    bool invalidReference;
    try { db.execute(`INSERT INTO "Source" ("RecordId", "TargetId") VALUES ('00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000099')`); }
    catch (Z8PostgresException) { invalidReference = true; }
    assert(invalidReference);
    auto statics = P.m_statics();
    db.execute(z8_postgres_create_table_sql("pg_temp"w, statics));
    z8_postgres_apply_static_records(db, "pg_temp"w, statics);
    auto seeded = db.execute(`SELECT "Label", "Counter" FROM "StaticSample" ORDER BY "RecordId"`);
    assert(seeded.rows.length == 2 && seeded.rows[0][0].text == "Seed" && seeded.rows[0][1].text == "12");
    assert(seeded.rows[1][0].text == "Second" && seeded.rows[1][1].text == "0");
    db.execute(`UPDATE "StaticSample" SET "Label" = 'Changed', "Counter" = 99, "Other" = 'Preserved' WHERE "RecordId" = '00000000-0000-0000-0000-000000000031'`);
    z8_postgres_apply_static_records(db, "pg_temp"w, statics);
    seeded = db.execute(`SELECT "Label", "Counter", "Other" FROM "StaticSample" ORDER BY "RecordId"`);
    assert(seeded.rows.length == 2 && seeded.rows[0][0].text == "Seed" && seeded.rows[0][1].text == "55" && seeded.rows[0][2].text == "Preserved");
    db.execute(`CREATE SCHEMA "z8_test"`);
    z8_postgres_create_tables(db, "z8_test"w, [P.m_references(), P.m_target(), P.m_statics()]);
    assert(db.execute(`SELECT count(*) FROM "z8_test"."Source"`).rows[0][0].text == "1");
    assert(db.execute(`SELECT count(*) FROM "z8_test"."StaticSample"`).rows[0][0].text == "3");
    db.execute(`INSERT INTO "z8_test"."Source" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000041')`);
    bool missingReference;
    try { db.execute(`INSERT INTO "z8_test"."Source" ("RecordId", "TargetId") VALUES ('00000000-0000-0000-0000-000000000042', '00000000-0000-0000-0000-000000000099')`); }
    catch (Z8PostgresException) { missingReference = true; }
    assert(missingReference);
    db.execute(`CREATE SCHEMA "z8_rollback"`);
    bool rolledBack;
    try { z8_postgres_create_tables(db, "z8_rollback"w, [P.m_references()]); }
    catch (Z8PostgresException) { rolledBack = true; }
    assert(rolledBack && db.execute(`SELECT to_regclass('"z8_rollback"."Source"') IS NULL`).rows[0][0].text == "t");
    assert(!db.inTransaction());
    db.beginTransaction(); bool nestedRejected;
    try { z8_postgres_create_tables(db, "z8_test"w, [P.m_statics()]); }
    catch (Z8PostgresException) { nestedRejected = true; }
    assert(nestedRejected && db.inTransaction()); db.rollback();
    auto sourceInfo = z8_postgres_describe_table(db, "z8_test"w, "Source"w);
    assert(sourceInfo !is null && sourceInfo.schema == "z8_test" && sourceInfo.primaryKeyColumns == ["RecordId"]);
    assert(sourceInfo.foreignKeys.length == 2 && sourceInfo.indexes.length >= 2);
    bool primaryIndex, linkIndex, linkColumn;
    foreach (idx; sourceInfo.indexes) {
        if (idx.primary) primaryIndex = idx.unique && idx.definition.canFind("RecordId");
        if (idx.definition.canFind("TargetId")) linkIndex = true;
    }
    foreach (column; sourceInfo.columns) if (column.name == "TargetId")
        linkColumn = column.type == "uuid" && !column.nullable && column.hasDefault;
    assert(primaryIndex && linkIndex && linkColumn);
    auto targetInfo = z8_postgres_describe_table(db, "pg_temp"w, "Target;--"w);
    assert(targetInfo !is null && targetInfo.schema.canFind("pg_temp_") && targetInfo.name == "Target;--");
    assert(z8_postgres_describe_table(db, "z8_test"w, "Source' OR true --"w) is null);
    assert(z8_postgres_describe_table(db, "does_not_exist"w, "Source"w) is null);
    db.execute(`CREATE TABLE "z8_test"."Composite" ("B" integer, "A" integer, PRIMARY KEY ("A", "B"))`);
    auto composite = z8_postgres_describe_table(db, "z8_test"w, "Composite"w);
    assert(composite.primaryKeyColumns == ["A", "B"] && composite.columns[0].name == "B");
    db.execute(`CREATE SCHEMA "dot.name"`);
    db.execute(`CREATE TABLE "dot.name"."quoted""table" ("a" integer)`);
    auto quoted = z8_postgres_describe_table(db, "dot.name"w, `quoted"table`w);
    assert(quoted !is null && quoted.schema == "dot.name" && quoted.columns[0].name == "a");
    auto expectedStatic = P.m_statics();
    assert(z8_postgres_compare_table(expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w)).length == 0);
    assert(z8_postgres_compare_table(expectedStatic, null)[0].kind == Z8SchemaDifferenceKind.missingTable);
    db.execute(`ALTER TABLE "z8_test"."StaticSample" ALTER COLUMN "Label" TYPE text, DROP COLUMN "Counter", ADD COLUMN "Extra" integer, ALTER COLUMN "Other" SET NOT NULL`);
    auto differences = z8_postgres_compare_table(expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w));
    bool changedType, missingColumn, extraColumn, changedNullability;
    foreach (difference; differences) {
        if (difference.kind == Z8SchemaDifferenceKind.columnType && difference.column == "Label") changedType = true;
        if (difference.kind == Z8SchemaDifferenceKind.missingColumn && difference.column == "Counter") missingColumn = true;
        if (difference.kind == Z8SchemaDifferenceKind.extraColumn && difference.column == "Extra") extraColumn = true;
        if (difference.kind == Z8SchemaDifferenceKind.nullability && difference.column == "Other") changedNullability = true;
    }
    assert(changedType && missingColumn && extraColumn && changedNullability && differences.length == 4);
    auto additions = z8_postgres_plan_add_columns("z8_test"w, expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w));
    assert(additions.length == 1 && additions[0] == `ALTER TABLE "z8_test"."StaticSample" ADD COLUMN "Counter" bigint DEFAULT 0`);
    db.execute(additions[0]);
    assert(db.execute(`SELECT count(*) FROM "z8_test"."StaticSample" WHERE "Counter" = 0`).rows[0][0].text == "3");
    assert(z8_postgres_plan_add_columns("z8_test"w, expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w)).length == 0);
    bool wrongSchema;
    try { z8_postgres_plan_add_columns("other"w, expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w)); }
    catch (Z8PostgresException) { wrongSchema = true; }
    assert(wrongSchema);
    auto noKey = new Z8PostgresTableDescription(); noKey.schema = "z8_test"; noKey.name = "StaticSample";
    bool missingKeyRejected;
    try { z8_postgres_plan_add_columns("z8_test"w, expectedStatic, noKey); }
    catch (Z8PostgresException) { missingKeyRejected = true; }
    assert(missingKeyRejected);
    db.execute(`ALTER TABLE "z8_test"."StaticSample" DROP CONSTRAINT "StaticSample_pkey", ADD PRIMARY KEY ("Label")`);
    differences = z8_postgres_compare_table(expectedStatic, z8_postgres_describe_table(db, "z8_test"w, "StaticSample"w));
    bool changedKey;
    foreach (difference; differences) if (difference.kind == Z8SchemaDifferenceKind.primaryKey && difference.expected == "RecordId" && difference.actual == "Label") changedKey = true;
    assert(changedKey);
    db.execute(ddl);
    db.execute(`INSERT INTO "Sample;--" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000001')`);
    auto row = db.execute(`SELECT "Title","Amount","Flag","Price","Reference","Moment","Duration","Details","Blob" FROM "Sample;--"`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "O'Reilly 😀" && row.rows[0][1].text == "7" && row.rows[0][2].text == "1");
    assert(row.rows[0][3].text == "12.5" && row.rows[0][4].text == "00000000-0000-0000-0000-000000000000");
    assert(row.rows[0][5].text == "-62135769600000" && row.rows[0][6].text == "0" && row.rows[0][7].isNull && row.rows[0][8].isNull);
    bool notNull; try { db.execute(`INSERT INTO "Sample;--" ("RecordId","Reference") VALUES ('00000000-0000-0000-0000-000000000002',NULL)`); } catch (Z8PostgresException) { notNull = true; }
    assert(notNull);
    bool duplicate; try { db.execute(`INSERT INTO "Sample;--" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000001')`); } catch (Z8PostgresException) { duplicate = true; }
    assert(duplicate);
    auto backend = new Z8PostgresDatabase(db, "pg_temp"w); auto previous = z8_connection_set_current(backend);
    assert(z8_optional_require(P.m_count(table)) == 1); P.m_create(table, z8_guid_create(3));
    assert(z8_optional_require(P.m_count(table)) == 2);
    z8_connection_set_current(previous); db.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-schema.exe" if os.name == "nt" else "postgres-schema")
    command = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
               *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
               str(harness), str(runtime)]
    command += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    subprocess.run([*command, "-of=" + str(exe)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        result = subprocess.run([str(exe), connection], env=environment, cwd=temp, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise SystemExit(f"Schema fixture failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
print("BL table schema generation, defaults and primary key verified in PostgreSQL")
