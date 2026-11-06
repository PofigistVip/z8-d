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
import org.zenframework.z8.base.table.value.Aggregation;
import org.zenframework.z8.base.table.SortDirection;
import org.zenframework.z8.base.application.Application;
[name "Sample;--"] public class Sample extends Table {
    [name "Title"] public StringField title; title.defaultValue = "O'Reilly 😀";
    [name "Amount"] public IntField amount; amount.defaultValue = 7;
    [name "Flag"] public BoolField flag; flag.defaultValue = true;
    [name "Price"] public DecimalField price; price.defaultValue = 12.50;
    [name "Reference"] public GuidField reference;
    [name "Moment"] public DatetimeField moment;
    period = moment;
    [name "Duration"] public DatespanField duration;
    [name "Details"] public TextField details;
    [name "Blob"] public BinaryField blob;
    public IntExpression computed; computed = amount + 1;
    public string actionEvents = "";
    public string getActionEvents() { return actionEvents; }
    virtual protected void onCopyAction(guid id) { actionEvents = "C"; }
    virtual protected void onCreateAction(guid id) { actionEvents = "N"; }
    virtual protected void onUpdateAction(guid id) { actionEvents = "U"; }
    virtual protected void onDestroyAction(guid id) { actionEvents = "D"; }
    virtual protected sql_bool scope() {
        if (Application.isRequest() && Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "write-values") return amount >= amount.get();
        if (Application.isRequest() && Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "default-events") return amount >= amount.get();
        return amount >= 0;
    }
    virtual protected void onReadAction() {
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-hook") { amount = 999; addWhere(amount >= 40); }
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-values") addWhere(amount >= amount.get());
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-group") { groupBy = {flag}; amount.aggregation = Aggregation.Sum; }
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-group-average") { groupBy = {flag}; amount.aggregation = Aggregation.Average; }
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-group-arrays") { groupBy = {flag}; amount.aggregation = Aggregation.Array; title.aggregation = Aggregation.Distinct; }
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-computed-group") { computed.aggregation = Aggregation.None; groupBy = {computed}; }
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "with-average") amount.aggregation = Aggregation.Average;
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "default-events") amount = amount.get() + 1;
        if (Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "default-order") { groupFields = {flag}; sortFields = {amount}; amount.sortDirection = SortDirection.Desc; }
    }
    virtual protected void beforeRead() {
        if (Application.isRequest() && Application.requestParameters().containsKey("session") && Application.requestParameters()["session"] == "default-events") amount = amount.get() + 1;
    }
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
import org.zenframework.z8.base.table.system.Roles;
import org.zenframework.z8.base.table.system.Users;
import org.zenframework.z8.base.table.system.Sequences;
import org.zenframework.z8.base.table.Sequencer;
import org.zenframework.z8.base.table.system.Tables;
import org.zenframework.z8.base.table.system.Requests;
import org.zenframework.z8.base.table.system.Fields;
import org.zenframework.z8.base.table.system.RoleTableAccess;
import org.zenframework.z8.base.table.system.RoleFieldAccess;
import org.zenframework.z8.base.table.system.RoleRequestAccess;
import org.zenframework.z8.base.table.system.UserRoles;
import org.zenframework.z8.base.table.system.Entries;
import org.zenframework.z8.base.table.system.UserEntries;
import org.zenframework.z8.base.security.User;
import org.zenframework.z8.base.table.value.Field;
public class Probe {
    public static bool lookupSystemUser() {
        User user = User.get(guid.create(1));
        return user != null && user.login == "System" && user.isBuiltinSystem()
            && User.get(guid.create(999999)) == null;
    }
    public static Sample make() { Sample value; return value; }
    public static GeoSample geo() { GeoSample value; return value; }
    public static IndexSample indexes() { IndexSample value; return value; }
    public static ReferenceSource references() { ReferenceSource value; return value; }
    public static ReferenceTarget target() { ReferenceTarget value; return value; }
    public static StaticSample statics() { StaticSample value; return value; }
    public static Roles roles() { Roles value; return value; }
    public static Users users() { Users value; return value; }
    public static Sequences sequences() { Sequences value; return value; }
    public static Tables systemTables() { Tables value; return value; }
    public static Requests systemRequests() { Requests value; return value; }
    public static Fields systemFields() { Fields value; return value; }
    public static RoleTableAccess roleTableAccess() { RoleTableAccess value; return value; }
    public static RoleFieldAccess roleFieldAccess() { RoleFieldAccess value; return value; }
    public static RoleRequestAccess roleRequestAccess() { RoleRequestAccess value; return value; }
    public static UserRoles userRoles() { UserRoles value; return value; }
    public static Entries entries() { Entries value; return value; }
    public static UserEntries userEntries() { UserEntries value; return value; }
    public static void deleteEntry(Entries value, guid id) { value.destroy(id); }
    public static string entryName(Entries value, guid id) { Field[] fields = {value.name}; if (value.readRecord(id, fields)) return value.name.get(); return "missing"; }
    public static string requestName(Requests value, guid id) { Field[] fields = {value.name}; if (value.readRecord(id, fields)) return value.name.get(); return "missing"; }
    public static int entryNameDependencies(Entries value) { return value.name.usedFields.size(); }
    public static void clearEntryNameDependencies(Entries value) { value.name.usedFields.clear(); }
    public static void deleteUserRole(UserRoles value, guid id) { value.destroy(id); }
    public static void createUserRole(UserRoles value, guid id, guid user, guid role) { value.user = user; value.role = role; value.create(id); }
    public static string accessRoleName(RoleTableAccess value) { Field[] fields = {value.roles.name}; value.read(fields); if (value.next()) return value.roles.name.get(); return "missing"; }
    public static void setFieldRead(RoleFieldAccess value, guid id, bool flag) { value.read = flag; value.update(id); }
    public static void setRequestExecute(RoleRequestAccess value, guid id, bool flag) { value.execute = flag; value.update(id); }
    public static void setFieldWrite(RoleFieldAccess value, guid id, bool flag) { value.write = flag; value.update(id); }
    public static void setFieldBoth(RoleFieldAccess value, guid id) { value.read = false; value.write = true; value.update(id); }
    public static void setTableRead(RoleTableAccess value, guid id, bool flag) { value.read = flag; value.update(id); }
    public static void setTableWrite(RoleTableAccess value, guid id, bool flag) { value.write = flag; value.update(id); }
    public static void setTableCreate(RoleTableAccess value, guid id, bool flag) { value.create = flag; value.update(id); }
    public static void setTableCopy(RoleTableAccess value, guid id, bool flag) { value.copy = flag; value.update(id); }
    public static void setTableDestroy(RoleTableAccess value, guid id, bool flag) { value.destroy = flag; value.update(id); }
    public static string fieldTableName(Fields value) { Field[] fields = {value.tables.name}; value.read(fields); if (value.next()) return value.tables.name.get(); return "missing"; }
    public static guid systemUser() { return Users.System; }
    public static guid administratorUser() { return Users.Administrator; }
    public static void createUser(Users value, guid id) { value.create(id); }
    public static void createCustomUser(Users value, guid id) { value.password = "custom"; value.changePassword = false; value.create(id); }
    public static void createNamedUser(Users value, guid id, string name) { value.name = name; value.create(id); }
    public static void banUser(Users value, guid id, bool banned) { value.banned = banned; value.update(id); }
    public static void forcePasswordChange(Users value, guid id) { value.changePassword = true; value.update(id); }
    public static void notifyUserChange(guid id) { Users.notifyUserChange(id); }
    public static void deleteUser(Users value, guid id) { value.destroy(id); }
    public static void deleteRole(Roles value, guid id) { value.destroy(id); }
    public static void createRole(Roles value, guid id) { value.name = "Custom"; value.create(id); }
    public static void renameRole(Roles value, guid id) { value.name = "Renamed"; value.update(id); }
    public static guid administratorRole() { return Roles.Administrator; }
    public static guid userRole() { return Roles.User; }
    public static guid guestRole() { return Roles.Guest; }
    public static int nextSequence(string key, int increment, int initial) { return Sequencer.next(key, increment, initial); }
    public static int nextNamed(string key) { return Sequencer.next(key); }
    public static int nextIncrement(string key, int increment) { return Sequencer.next(key, increment); }
    public static int nextField(Sample value) { return value.title.getSequencer().next(); }
    public static guid fieldKey(Sample value) { return value.title.key(); }
    public static int nextFieldAdvanced(Sample value, int increment, int initial) { return value.title.getSequencer().next(increment, initial); }
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
import z8.database.query;
import z8.database.schema;
import z8.database.catalog;
import z8.database.compare;
import z8.database.migration;
import z8.database.metadata;
import z8.database.bootstrap;
import z8.database.privileges;
import z8gen.p_Probe;
import std.algorithm.searching : canFind;
import std.conv : to;
import std.json : parseJSON;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    if (args.length > 2) {
        import std.stdio : writeln;
        if (args[2] == "metadata_worker") {
            auto registry = new Z8RuntimeRegistry(); registry.registerTable(P.m_statics());
            z8_postgres_sync_registry(db, "z8_access"w, registry); db.close(); return;
        }
        if (args[2] == "metadata_count") {
            auto key = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("StaticSample"w)).to!string);
            auto counts = db.execute(`SELECT (SELECT count(*) FROM "z8_access"."SystemTables" WHERE "RecordId" = $1::uuid), (SELECT count(*) FROM "z8_access"."SystemFields" WHERE "Table" = $1::uuid), (SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Table" = $1::uuid), (SELECT count(*) FROM "z8_access"."SystemRoleFieldAccess" a JOIN "z8_access"."SystemFields" f ON a."Field" = f."RecordId" WHERE f."Table" = $1::uuid)`, [key]);
            writeln(counts.rows[0][0].text, " ", counts.rows[0][1].text, " ", counts.rows[0][2].text, " ", counts.rows[0][3].text);
            db.close(); return;
        }
        auto backend = new Z8PostgresDatabase(db, "z8_test"w); z8_connection_set_current(backend);
        auto transactional = args[2] == "worker_tx";
        foreach (i; 0 .. (transactional ? 20 : 30)) {
            if (transactional) db.beginTransaction();
            auto value = P.m_nextSequence(transactional ? "parallel_tx"w : "parallel"w, z8_optional_wrap(1L), z8_optional_wrap(1L));
            if (transactional) db.commit();
            writeln(z8_optional_require(value));
        }
        db.close(); return;
    }
    db.execute("CREATE TEMP TABLE init_temp (id integer)");
    auto table = P.m_make();
    auto eventTarget = P.m_make();
    eventTarget.z8_query_virtual_onCopyAction(z8_guid_create(1)); eventTarget.z8_query_virtual_onCreateAction(z8_guid_create(1));
    assert(eventTarget.m_getActionEvents() == "N"w);
    eventTarget.z8_query_virtual_onUpdateAction(z8_guid_create(1)); assert(eventTarget.m_getActionEvents() == "U"w);
    eventTarget.z8_query_virtual_onDestroyAction(z8_guid_create(1)); assert(eventTarget.m_getActionEvents() == "D"w);
    assert(P.m_fieldKey(table) == z8_guid_create_name("Sample;--.Title"w));
    auto registry = new Z8RuntimeRegistry(); registry.registerTable(table); registry.registerTable(P.m_make());
    registry.registerTable(P.m_indexes()); registry.registerRequest(table);
    auto registeredTables = registry.tables(); auto registeredRequests = registry.requests();
    assert(registeredTables.length == 2 && registeredRequests.length == 1);
    assert(registeredTables[0].key == z8_guid_create_name("Sample;--"w));
    assert(registeredRequests[0].key == z8_guid_create_name(registeredRequests[0].classId));
    bool titleMetadata;
    foreach (field; registeredTables[0].fields) if (field.index == "title"w) {
        titleMetadata = field.name == "Title"w && field.displayName == "Title"w && field.type == "string(30)"w && field.ordinal == 6 && field.key == z8_guid_create_name("Sample;--.Title"w);
        field.key.minorBits = 0;
    }
    assert(titleMetadata);
    bool titleKeyIntact;
    foreach (field; registry.tables()[0].fields) if (field.index == "title"w) titleKeyIntact = field.key == z8_guid_create_name("Sample;--.Title"w);
    assert(titleKeyIntact && registeredRequests[0].fields.length == 0);
    registeredTables[0].key.minorBits = 0; assert(registry.tableKeys()[0] == z8_guid_create_name("Sample;--"w));
    auto conflict = P.m_indexes(); conflict.z8_set_attribute("name"w, "Sample;--"w);
    bool duplicateRegistration; try { registry.registerTable(conflict); } catch (Exception) { duplicateRegistration = true; }
    assert(duplicateRegistration && registry.tables().length == 2);
    Z8Object sampleTitle, indexTitle;
    foreach (field; z8_query_declared_fields(table, true)) if (field.z8_index() == "title"w) sampleTitle = field;
    auto otherTable = P.m_indexes();
    foreach (field; z8_query_declared_fields(otherTable, true)) if (field.z8_index() == "title"w) indexTitle = field;
    auto sampleFieldKey = z8_native_call!Z8Guid("org.zenframework.z8.server.runtime.OBJECT.m_key"w, sampleTitle);
    auto indexFieldKey = z8_native_call!Z8Guid("org.zenframework.z8.server.runtime.OBJECT.m_key"w, indexTitle);
    assert(sampleFieldKey == z8_guid_create_name("Sample;--.Title"w) && indexFieldKey == z8_guid_create_name("IndexSample.Title"w));
    assert(sampleFieldKey != indexFieldKey);
    auto detached = z8_native_new("org.zenframework.z8.server.base.table.value.StringField"w);
    detached.z8_set_attribute("name"w, "Detached"w);
    assert(z8_native_call!Z8Guid("org.zenframework.z8.server.runtime.OBJECT.m_key"w, detached) == z8_guid_create_name("Detached"w));
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
    auto expectedSource = P.m_references();
    assert(z8_postgres_compare_table(expectedSource, sourceInfo).length == 0);
    db.execute(`ALTER TABLE "z8_test"."Source" DROP CONSTRAINT "FK0_Source"`);
    db.execute(`ALTER TABLE "z8_test"."Source" ADD CONSTRAINT "WrongAction" FOREIGN KEY ("TargetId") REFERENCES "z8_test"."Target;--" ("RecordId") ON DELETE CASCADE`);
    auto foreignDifferences = z8_postgres_compare_table(expectedSource, z8_postgres_describe_table(db, "z8_test"w, "Source"w));
    bool missingForeign, extraForeign;
    foreach (difference; foreignDifferences) {
        if (difference.kind == Z8SchemaDifferenceKind.missingForeignKey && difference.column == "TargetId") missingForeign = true;
        if (difference.kind == Z8SchemaDifferenceKind.extraForeignKey && difference.actual.canFind("WrongAction")) extraForeign = true;
    }
    assert(missingForeign && extraForeign && foreignDifferences.length == 2);
    auto targetInfo = z8_postgres_describe_table(db, "pg_temp"w, "Target;--"w);
    assert(targetInfo !is null && targetInfo.schema.canFind("pg_temp_") && targetInfo.name == "Target;--");
    assert(z8_postgres_describe_table(db, "z8_test"w, "Source' OR true --"w) is null);
    assert(z8_postgres_describe_table(db, "does_not_exist"w, "Source"w) is null);
    db.execute(`CREATE TABLE "z8_test"."Composite" ("B" integer, "A" integer, PRIMARY KEY ("A", "B"))`);
    auto composite = z8_postgres_describe_table(db, "z8_test"w, "Composite"w);
    assert(composite.primaryKeyColumns == ["A", "B"] && composite.columns[0].name == "B");
    db.execute(`CREATE TABLE "z8_test"."CompositeRef" ("X" integer, "Y" integer, FOREIGN KEY ("X", "Y") REFERENCES "z8_test"."Composite" ("A", "B"))`);
    auto compositeRef = z8_postgres_describe_table(db, "z8_test"w, "CompositeRef"w);
    assert(compositeRef.foreignKeys.length == 1 && compositeRef.foreignKeys[0].columns == ["X", "Y"] && compositeRef.foreignKeys[0].targetColumns == ["A", "B"]);
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
    auto roleTable = P.m_roles();
    auto roleDDL = z8_postgres_create_table_sql("z8_test"w, roleTable);
    assert(roleDDL.canFind(`"Name" character varying`) && roleDDL.canFind(`"Description" bytea`) && roleDDL.canFind(`"Read" smallint`));
    assert(z8_guid_to_string(P.m_administratorRole()) == "DC08CA72-C668-412F-91B7-022F1C82AC09"w);
    assert(z8_guid_to_string(P.m_userRole()) == "421A8413-A8EC-4DAB-9235-9A5FF83341C5"w);
    assert(z8_guid_to_string(P.m_guestRole()) == "BE41CEB5-02DF-44EE-885F-B82DDEDCAA08"w);
    z8_initialize_static_records(roleTable);
    auto roleRecords = roleTable.z8_static_records();
    assert(roleRecords.length == 3 && roleRecords[0].values.length == 9);
    assert(roleRecords[0].values[0].value.textValue == "Administrator"w && roleRecords[0].values[2].value.booleanValue);
    assert(roleRecords[1].values[2].value.booleanValue && !roleRecords[1].values[3].value.booleanValue);
    assert(!roleRecords[2].values[2].value.booleanValue && roleRecords[2].values[8].value.integerValue == 3);
    auto sequences = P.m_sequences();
    auto sequenceDDL = z8_postgres_create_table_sql("z8_test"w, sequences);
    assert(sequenceDDL.canFind(`"Description" bytea`) && sequenceDDL.canFind(`"Key" character varying`) && sequenceDDL.canFind(`"Value" bigint`));
    bool sequenceIndex;
    foreach (sql; z8_postgres_create_indexes_sql("z8_test"w, sequences)) if (sql.canFind(`("Key")`)) sequenceIndex = true;
    assert(sequenceIndex);
    foreach (field; z8_query_declared_fields(sequences, true)) if (field.z8_index() == "key"w) {
        auto length = z8_native_field!(Z8Optional!long)("org.zenframework.z8.server.base.table.value.StringField.f_length"w, field);
        assert(z8_optional_require(length) == 256);
    }
    z8_postgres_create_tables(db, "z8_test"w, [sequences]);
    auto sequenceBackend = new Z8PostgresDatabase(db, "z8_test"w);
    auto savedSequenceBackend = z8_connection_set_current(sequenceBackend);
    assert(z8_optional_require(P.m_nextSequence("Тест 😀"w, z8_optional_wrap(2L), z8_optional_wrap(5L))) == 7);
    assert(z8_optional_require(P.m_nextSequence("Тест 😀"w, z8_optional_wrap(3L), z8_optional_wrap(100L))) == 10);
    assert(z8_optional_require(P.m_nextNamed("named"w)) == 2);
    assert(z8_optional_require(P.m_nextIncrement("named"w, z8_optional_wrap(4L))) == 6);
    assert(z8_optional_require(P.m_nextField(P.m_make())) == 2);
    assert(z8_optional_require(P.m_nextField(P.m_make())) == 3);
    assert(z8_optional_require(P.m_nextFieldAdvanced(P.m_make(), z8_optional_wrap(4L), z8_optional_wrap(99L))) == 7);
    db.beginTransaction();
    assert(z8_optional_require(P.m_nextSequence("rollback"w, z8_optional_wrap(2L), z8_optional_wrap(10L))) == 12);
    assert(z8_optional_require(P.m_nextSequence("rollback"w, z8_optional_wrap(2L), z8_optional_wrap(10L))) == 14);
    db.rollback();
    assert(z8_optional_require(P.m_nextSequence("rollback"w, z8_optional_wrap(2L), z8_optional_wrap(99L))) == 12);
    db.beginTransaction();
    assert(z8_optional_require(P.m_nextSequence("rollback"w, z8_optional_wrap(2L), z8_optional_wrap(1L))) == 14);
    db.rollback();
    assert(z8_optional_require(P.m_nextSequence("rollback"w, z8_optional_wrap(2L), z8_optional_wrap(1L))) == 14);
    db.execute(`INSERT INTO "z8_test"."SystemSequences" ("RecordId", "Key", "Value") VALUES ('00000000-0000-0000-0000-000000000099', 'legacy', 40)`);
    assert(z8_optional_require(P.m_nextSequence("legacy"w, z8_optional_wrap(2L), z8_optional_wrap(1L))) == 42);
    db.execute(`INSERT INTO "z8_test"."SystemSequences" ("RecordId", "Key", "Value") VALUES ('00000000-0000-0000-0000-000000000098', 'legacy', 50)`);
    bool ambiguousSequence;
    try { P.m_nextNamed("legacy"w); } catch (Z8PostgresException) { ambiguousSequence = true; }
    assert(ambiguousSequence);
    z8_connection_set_current(savedSequenceBackend);
    auto userTable = P.m_users();
    auto userDDL = z8_postgres_create_table_sql("z8_test"w, userTable);
    assert(userDDL.canFind(`"Name" character varying`) && userDDL.canFind(`"Password" character varying DEFAULT 'd41d8cd98f00b204e9800998ecf8427e'`));
    assert(userDDL.canFind(`"Verification" character varying`) && userDDL.canFind(`"Verification Modified At" bigint`));
    foreach (field; z8_query_declared_fields(userTable, true)) {
        if (field.z8_index() == "name"w) {
            auto length = z8_native_field!(Z8Optional!long)("org.zenframework.z8.server.base.table.value.StringField.f_length"w, field);
            assert(z8_optional_require(length) == 128);
        }
        if (field.z8_index() == "password"w)
            assert(field.z8_get_attribute("system"w) == "true"w && field.z8_get_attribute("exportable"w) == "false"w);
    }
    auto userIndexes = z8_postgres_create_indexes_sql("z8_test"w, userTable);
    bool uniqueLogin;
    foreach (index; userIndexes) if (index.canFind(`LOWER("Name")`)) uniqueLogin = index.canFind("CREATE UNIQUE INDEX");
    assert(uniqueLogin);
    assert(z8_guid_to_string(P.m_systemUser()) == "00000000-0000-0000-0000-000000000001"w);
    assert(z8_guid_to_string(P.m_administratorUser()) == "00000000-0000-0000-0000-000000000002"w);
    z8_initialize_static_records(userTable);
    auto userRecords = userTable.z8_static_records();
    assert(userRecords.length == 2 && userRecords[0].values[0].value.textValue == "Admin"w);
    assert(userRecords[0].values[1].value.integerValue == 3 && userRecords[1].values[0].value.textValue == "System"w);
    db.execute(userDDL);
    auto userBackend = new Z8PostgresDatabase(db, "z8_test"w);
    auto savedBackend = z8_connection_set_current(userBackend);
    assert(z8_postgres_ensure_null_record(db, "z8_test"w, P.m_users()));
    assert(db.execute(`SELECT count(*) FROM "z8_test"."SystemSequences" WHERE "Key" = 'SystemUsers.Name'`).rows[0][0].text == "0");
    z8_string_set_resource("Users.name.default"w, "Имя "w);
    P.m_createUser(userTable, z8_guid_create(70));
    P.m_createCustomUser(userTable, z8_guid_create(71));
    P.m_createNamedUser(P.m_users(), z8_guid_create(74), "Alice"w);
    auto suppressed = new Z8ApplicationRequest(); suppressed.setEventsLevel(Z8EventsLevel.none);
    auto savedRequest = z8_application_set_request(suppressed);
    P.m_createUser(P.m_users(), z8_guid_create(72));
    bool cannotDeleteSystem;
    try { P.m_deleteUser(P.m_users(), P.m_systemUser()); } catch (Exception) { cannotDeleteSystem = true; }
    assert(cannotDeleteSystem);
    z8_application_set_request(savedRequest);
    auto createdUsers = db.execute(`SELECT "Password", "Change Password", "Name" FROM "z8_test"."SystemUsers" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000' ORDER BY "RecordId"`);
    assert(createdUsers.rows.length == 4 && createdUsers.rows[0][0].text == "d41d8cd98f00b204e9800998ecf8427e" && createdUsers.rows[0][1].text == "1" && createdUsers.rows[0][2].text == "Имя 2");
    assert(createdUsers.rows[1][0].text == "custom" && createdUsers.rows[1][1].text == "0");
    assert(createdUsers.rows[1][2].text == "Имя 3" && createdUsers.rows[2][0].text == "d41d8cd98f00b204e9800998ecf8427e" && createdUsers.rows[2][1].text == "1" && createdUsers.rows[2][2].text == "");
    assert(createdUsers.rows[3][2].text == "Alice"); z8_string_clear_resources();
    db.execute(`INSERT INTO "z8_test"."SystemUsers" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000001')`);
    bool cannotBanSystem;
    try { P.m_banUser(P.m_users(), P.m_systemUser(), z8_optional_wrap(true)); } catch (Exception) { cannotBanSystem = true; }
    assert(cannotBanSystem && db.execute(`SELECT "Banned" FROM "z8_test"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000001'`).rows[0][0].text == "0");
    P.m_banUser(P.m_users(), P.m_systemUser(), z8_optional_wrap(false));
    P.m_banUser(P.m_users(), z8_guid_create(70), z8_optional_wrap(true));
    assert(db.execute(`SELECT "Banned" FROM "z8_test"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000046'`).rows[0][0].text == "1");
    auto verifiedUser = P.m_users();
    foreach (field; z8_query_declared_fields(verifiedUser, true))
        if (field.z8_index() == "verification"w) z8_field_set(field, z8_primary_box("token"w));
    P.m_createUser(verifiedUser, z8_guid_create(73));
    assert(db.execute(`SELECT "Verification Modified At" > 0 FROM "z8_test"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000049'`).rows[0][0].text == "t");
    assert(db.execute(`SELECT "Name" FROM "z8_test"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000049'`).rows[0][0].text == "User4");
    P.m_createNamedUser(P.m_users(), z8_guid_create(75), ""w);
    assert(db.execute(`SELECT "Name" FROM "z8_test"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-00000000004B'`).rows[0][0].text == "User5");
    db.execute(roleDDL);
    db.execute(`INSERT INTO "z8_test"."SystemRoles" ("RecordId") VALUES ('DC08CA72-C668-412F-91B7-022F1C82AC09')`);
    bool cannotDeleteRole;
    try { P.m_deleteRole(roleTable, P.m_administratorRole()); } catch (Exception) { cannotDeleteRole = true; }
    assert(cannotDeleteRole);
    auto disabled = new Z8ApplicationRequest(); disabled.setEventsLevel(Z8EventsLevel.none);
    savedRequest = z8_application_set_request(disabled);
    P.m_deleteRole(roleTable, P.m_administratorRole());
    z8_application_set_request(savedRequest);
    assert(db.execute(`SELECT count(*) FROM "z8_test"."SystemRoles"`).rows[0][0].text == "0");
    z8_connection_set_current(savedBackend);
    db.execute(`CREATE SCHEMA "z8_security"`);
    z8_postgres_create_tables(db, "z8_security"w, [P.m_users(), P.m_sequences()]);
    auto builtin = db.execute(`SELECT "Name", "Lock", "Change Password" FROM "z8_security"."SystemUsers" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000' ORDER BY "RecordId"`);
    assert(builtin.rows.length == 2 && builtin.rows[0][0].text == "System" && builtin.rows[1][0].text == "Admin");
    assert(builtin.rows[0][1].text == "3" && builtin.rows[1][1].text == "3" && builtin.rows[1][2].text == "1");
    db.execute(`UPDATE "z8_security"."SystemUsers" SET "Name" = 'Custom admin', "Password" = 'Secret', "Description" = convert_to('Kept', 'UTF8'), "Lock" = 0 WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    z8_postgres_apply_static_records(db, "z8_security"w, P.m_users());
    auto retainedUser = db.execute(`SELECT "Name", "Password", convert_from("Description", 'UTF8'), "Lock" FROM "z8_security"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`);
    assert(retainedUser.rows[0][0].text == "Custom admin" && retainedUser.rows[0][1].text == "Secret" && retainedUser.rows[0][2].text == "Kept" && retainedUser.rows[0][3].text == "3");
    bool rolesUnavailable;
    try { z8_postgres_apply_static_records(db, "z8_security"w, P.m_roles()); } catch (Z8PostgresException) { rolesUnavailable = true; }
    assert(rolesUnavailable);
    auto bootstrapRegistry = new Z8RuntimeRegistry(); auto bootstrapSample = P.m_make();
    bootstrapRegistry.registerTable(bootstrapSample); bootstrapRegistry.registerRequest(bootstrapSample); bootstrapRegistry.registerEntry(bootstrapSample);
    Z8Object[] bootstrapTables = [P.m_userRoles(), P.m_userEntries(), P.m_entries(), P.m_roles(), P.m_users(), P.m_sequences(), P.m_systemTables(), P.m_systemFields(),
        P.m_systemRequests(), P.m_roleTableAccess(), P.m_roleFieldAccess(), P.m_roleRequestAccess(), P.m_target()];
    db.execute(`CREATE SCHEMA "z8_bootstrap"`);
    auto bootstrapUser = new Z8UserData(); bootstrapUser.id = z8_guid_create(777); bootstrapUser.administrator = true;
    auto bootstrapRequest = new Z8ApplicationRequest(); bootstrapRequest.session = new Z8ApplicationSession("bootstrap"w, bootstrapUser, bootstrapUser);
    bootstrapRequest.setEventsLevel(Z8EventsLevel.user);
    auto savedBootstrapRequest = z8_application_set_request(bootstrapRequest);
    z8_postgres_bootstrap_registered(db, "z8_bootstrap"w, bootstrapRegistry, bootstrapTables);
    assert(z8_application_request() is bootstrapRequest && bootstrapRequest.eventsLevel() == Z8EventsLevel.user);
    z8_application_set_request(savedBootstrapRequest);
    auto initialUsers = db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemUsers" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`);
    assert(initialUsers.rows[0][0].text == "2");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemRoles" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "3");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemUserRoles" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "2");
    auto entry = db.execute(`SELECT "Class" FROM "z8_bootstrap"."SystemEntries" WHERE "Class" = 'org.zenframework.z8.server.base.table.system.SystemTools'`);
    assert(entry.rows.length == 1 && entry.rows[0][0].text == "org.zenframework.z8.server.base.table.system.SystemTools");
    assert(db.execute(`SELECT "Lock" FROM "z8_bootstrap"."SystemEntries" WHERE "Class" = 'Sample'`).rows[0][0].text == "3");
    auto userEntries = db.execute(`SELECT "UserId"::text, "EntryId"::text, "Lock" FROM "z8_bootstrap"."SystemUserEntries" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000' ORDER BY "UserId"`);
    assert(userEntries.rows.length == 2 && userEntries.rows[0][0].text == "00000000-0000-0000-0000-000000000001" && userEntries.rows[1][0].text == "00000000-0000-0000-0000-000000000002");
    assert(z8_guid_literal(userEntries.rows[0][1].text) == z8_guid_create_name("org.zenframework.z8.server.base.table.system.SystemTools"w) && userEntries.rows[0][2].text == "3");
    bootstrapSample.z8_set_attribute("displayName"w, "Renamed entry"w); bootstrapRegistry.registerEntry(bootstrapSample);
    z8_postgres_sync_registry(db, "z8_bootstrap"w, bootstrapRegistry);
    assert(db.execute(`SELECT "Name" FROM "z8_bootstrap"."SystemEntries" WHERE "Class" = 'Sample'`).rows[0][0].text == "Renamed entry");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemUserEntries" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "2");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemRoleTableAccess" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "3");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemRoleRequestAccess" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "3");
    assert(db.execute(`SELECT "Read"::text || "Write"::text || "Create"::text || "Copy"::text || "Destroy"::text FROM "z8_bootstrap"."SystemRoleTableAccess" WHERE "Role" = 'DC08CA72-C668-412F-91B7-022F1C82AC09'`).rows[0][0].text == "11111");
    assert(db.execute(`SELECT "Read"::text || "Write"::text FROM "z8_bootstrap"."SystemRoleTableAccess" WHERE "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'`).rows[0][0].text == "10");
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."SystemRoleFieldAccess" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "45");
    assert(db.execute(`SELECT "Execute" FROM "z8_bootstrap"."SystemRoleRequestAccess" WHERE "Role" = 'DC08CA72-C668-412F-91B7-022F1C82AC09'`).rows[0][0].text == "1");
    auto bootTableKey = z8_guid_create_name("Sample;--"w);
    auto bootFieldKey = z8_guid_create_name("Sample;--.Title"w);
    auto bootRequestKey = z8_guid_create_name("Sample"w);
    auto adminPrivileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2));
    db.execute(`INSERT INTO "z8_bootstrap"."SystemUserEntries" ("RecordId", "UserId", "EntryId", "Position") VALUES ($1::uuid, $2::uuid, $3::uuid, 5)`,
        [Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create(0x555)).to!string),
         Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create(2)).to!string),
         Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("Sample"w)).to!string)]);
    auto loadedAdmin = z8_postgres_read_user(db, "z8_bootstrap"w, z8_guid_create(2), bootstrapRegistry);
    assert(loadedAdmin !is null && loadedAdmin.login == "Admin"w && loadedAdmin.builtinAdministrator && loadedAdmin.administrator);
    assert(loadedAdmin.privileges.getRequestAccess(bootRequestKey).execute && loadedAdmin.roles.length == 1);
    assert(loadedAdmin.roleNames.length == 1 && loadedAdmin.roleNames[0] == "Administrator"w && loadedAdmin.changePassword);
    assert(loadedAdmin.entries.length == 2 && loadedAdmin.entries[1].classId == "Sample"w && loadedAdmin.entries[1].title == "Renamed entry"w);
    db.beginTransaction();
    db.execute(`DELETE FROM "z8_bootstrap"."SystemUserEntries" WHERE "RecordId" = 'D53F3EBE-4D11-4ACE-99D7-07608B68B6C2'`);
    auto fallbackAdmin = z8_postgres_read_user(db, "z8_bootstrap"w, z8_guid_create(2), bootstrapRegistry);
    assert(fallbackAdmin.entries.length == 2 && fallbackAdmin.entries[1].classId == "org.zenframework.z8.server.base.table.system.SystemTools"w);
    db.rollback();
    auto loadedSystem = (cast(IZ8JobUserResolver)new Z8PostgresDatabase(db, "z8_bootstrap"w)).resolveJobUser(z8_guid_create(1));
    assert(loadedSystem !is null && loadedSystem.login == "System"w && loadedSystem.builtinSystem);
    auto previousConnection = z8_connection_set_current(new Z8PostgresDatabase(db, "z8_bootstrap"w, bootstrapRegistry));
    assert(z8_optional_require(P.m_lookupSystemUser()));
    auto manager = new Z8SessionManager();
    auto notificationUser = new Z8UserData(); notificationUser.id = z8_guid_create(0x12345);
    manager.create("victim"w, notificationUser, loadedSystem, "z8_bootstrap"w);
    manager.create("other-schema"w, notificationUser, loadedSystem, "other"w);
    manager.create("admin-session"w, loadedAdmin, loadedSystem, "z8_bootstrap"w);
    auto notificationRequest = new Z8ApplicationRequest();
    notificationRequest.session = new Z8ApplicationSession("admin-session"w, loadedAdmin, loadedSystem);
    notificationRequest.userChangeNotifier = manager;
    auto previousRequest = z8_application_set_request(notificationRequest);
    P.m_createNamedUser(P.m_users(), notificationUser.id, "Notification User"w);
    auto explicitUsers = P.m_users();
    z8_query_set_executor(explicitUsers, new Z8PostgresQueryExecutor(db, "z8_bootstrap"w, "SystemUsers"w));
    z8_connection_set_current(new Z8PostgresDatabase(db, "other"w));
    P.m_banUser(explicitUsers, notificationUser.id, z8_optional_wrap(true));
    z8_connection_set_current(new Z8PostgresDatabase(db, "z8_bootstrap"w, bootstrapRegistry));
    assert(manager.getSession("victim"w) is null && manager.getSession("other-schema"w) !is null);
    manager.create("role-add"w, notificationUser, loadedSystem, "z8_bootstrap"w);
    auto assignmentId = z8_guid_create(0x12346);
    P.m_createUserRole(P.m_userRoles(), assignmentId, notificationUser.id, P.m_userRole());
    assert(manager.getSession("role-add"w) is null);
    manager.create("role-remove"w, notificationUser, loadedSystem, "z8_bootstrap"w);
    P.m_deleteUserRole(P.m_userRoles(), assignmentId);
    assert(manager.getSession("role-remove"w) is null && manager.getSession("other-schema"w) !is null);
    P.m_notifyUserChange(loadedAdmin.id);
    assert(manager.getSession("admin-session"w) !is null);
    P.m_forcePasswordChange(P.m_users(), loadedAdmin.id);
    assert(manager.getSession("admin-session"w) is null);
    manager.create("victim-delete"w, notificationUser, loadedSystem, "z8_bootstrap"w);
    P.m_deleteUser(P.m_users(), notificationUser.id);
    assert(manager.getSession("victim-delete"w) is null && manager.getSession("other-schema"w) !is null);
    z8_application_set_request(previousRequest);
    z8_connection_set_current(previousConnection);
    assert(z8_postgres_read_user(db, "z8_bootstrap"w, z8_guid_create(999999)) is null);
    assert(adminPrivileges.roleIds.length == 1 && adminPrivileges.privileges.getDefaultAccess().execute);
    assert(adminPrivileges.privileges.getTableAccess(bootTableKey).write && adminPrivileges.privileges.getFieldAccess(bootTableKey, bootFieldKey).read);
    assert(adminPrivileges.privileges.getRequestAccess(bootRequestKey).execute);
    db.execute(`INSERT INTO "z8_bootstrap"."Sample;--" ("RecordId", "Title", "Amount", "Moment") VALUES ('00000000-0000-0000-0000-00000000012D', 'Visible', 42, 1000)`);
    auto queryUser = new Z8UserData(); queryUser.id = z8_guid_create(2); queryUser.privileges = adminPrivileges.privileges;
    auto querySession = new Z8ApplicationSession("query"w, queryUser, queryUser);
    auto readRequest = new Z8ApplicationRequest(); readRequest.session = querySession; readRequest.monitor = new Z8RequestMonitor();
    readRequest.parameters.z8_add("request"w, "Sample"w); readRequest.parameters.z8_add("server"w, "shard"w); readRequest.parameters.z8_add("ip"w, "127.0.0.1"w);
    readRequest.parameters.z8_add("action"w, "read"w); readRequest.parameters.z8_add("fields"w, `["title",{"id":"amount"}]`w);
    readRequest.parameters.z8_add("limit"w, "1"w);
    auto priorReadRequest = z8_application_set_request(readRequest);
    auto priorReadBackend = z8_connection_set_current(new Z8PostgresDatabase(db, "z8_bootstrap"w));
    auto previousRegistry = z8_runtime_set_registry(bootstrapRegistry);
    bootstrapSample.z8_set_attribute("displayName"w, "Localized request"w); bootstrapRegistry.registerRequest(bootstrapSample);
    auto dynamicEntries = P.m_entries(), dynamicRequests = P.m_systemRequests();
    assert(z8_field_fields(dynamicEntries.f_name).length == 2 && z8_field_fields(dynamicRequests.f_name).length == 2);
    auto mutableDependencies = P.m_entries();
    assert(z8_optional_require(P.m_entryNameDependencies(mutableDependencies)) == 1);
    P.m_clearEntryNameDependencies(mutableDependencies); assert(z8_field_fields(mutableDependencies.f_name).length == 1);
    assert(P.m_entryName(dynamicEntries, z8_guid_create_name("Sample"w)) == "Renamed entry"w);
    assert(P.m_requestName(dynamicRequests, z8_guid_create_name("Sample"w)) == "Localized request"w);
    db.execute(`INSERT INTO "z8_bootstrap"."SystemEntries" ("RecordId", "Name", "Class") VALUES ('00000000-0000-0000-0000-000000000444', 'stale', 'Missing.Entry')`);
    assert(P.m_entryName(P.m_entries(), z8_guid_create(0x444)) == "<entry removed>"w);
    z8_runtime_set_registry(previousRegistry);
    z8_application_start_response(readRequest, "Sample"w); z8_application_dispatch_request();
    z8_application_finish_response(readRequest, cast(Z8RequestMonitor)readRequest.monitor);
    auto readJson = parseJSON(z8_application_response_text(readRequest).to!string);
    assert(readJson["data"].array.length == 1 && readJson["data"][0]["title"].str == "Visible" && readJson["data"][0]["amount"].integer == 42);
    assert(readJson["data"][0]["recordId"].str == "00000000-0000-0000-0000-00000000012D");
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access.init);
    auto masked = new Z8ApplicationRequest(); masked.session = querySession; masked.monitor = new Z8RequestMonitor();
    masked.parameters.z8_add("action"w, "read"w); masked.parameters.z8_add("fields"w, `["title","amount"]`w);
    z8_application_set_request(masked); z8_application_start_response(masked, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(masked, cast(Z8RequestMonitor)masked.monitor);
    auto maskedJson = parseJSON(z8_application_response_text(masked).to!string);
    assert("title" !in maskedJson["data"][0].object && maskedJson["data"][0]["amount"].integer == 42);
    queryUser.privileges.setTableAccess(bootTableKey, Z8Access.init);
    auto deniedRead = new Z8ApplicationRequest(); deniedRead.session = querySession; deniedRead.parameters.z8_add("action"w, "read"w);
    z8_application_set_request(deniedRead); z8_application_start_response(deniedRead, "Sample"w);
    bool noTableRead; try { z8_application_dispatch_query_read("Sample"w); } catch (Exception) { noTableRead = true; }
    assert(noTableRead);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    auto unsupportedRead = new Z8ApplicationRequest(); unsupportedRead.session = querySession;
    unsupportedRead.parameters.z8_add("action"w, "read"w); unsupportedRead.parameters.z8_add("filter"w, "{}"w);
    z8_application_set_request(unsupportedRead); z8_application_start_response(unsupportedRead, "Sample"w);
    bool unsupportedFilter; try { z8_application_dispatch_query_read("Sample"w); } catch (Exception) { unsupportedFilter = true; }
    assert(unsupportedFilter);
    bool rejectedRead(wstring parameter, wstring value) {
        auto bad = new Z8ApplicationRequest(); bad.session = querySession;
        bad.parameters.z8_add("action"w, "read"w); bad.parameters.z8_add(parameter, value);
        if (parameter != "fields"w) bad.parameters.z8_add("fields"w, `["amount"]`w);
        z8_application_set_request(bad); z8_application_start_response(bad, "Sample"w);
        try { z8_application_dispatch_query_read("Sample"w); } catch (Exception) { return true; }
        return false;
    }
    assert(rejectedRead("otherOption"w, "true"w));
    assert(rejectedRead("action"w, "write"w));
    assert(rejectedRead("fields"w, `{"id":"title"}`w));
    assert(!rejectedRead("fields"w, `["computed"]`w));
    assert(rejectedRead("start"w, "-1"w));
    assert(rejectedRead("filter"w, `{"logical":"or","expressions":[{"property":"title","value":"Visible"},{}]}`w));
    assert(rejectedRead("filter"w, `{"logical":"bad","expressions":[{"property":"title","value":"Visible"}]}`w));
    auto filtered = new Z8ApplicationRequest(); filtered.session = querySession; filtered.monitor = new Z8RequestMonitor();
    filtered.parameters.z8_add("action"w, "read"w); filtered.parameters.z8_add("fields"w, `["title","amount"]`w);
    filtered.parameters.z8_add("filter"w, `{"logical":"or","expressions":[{"property":"amount","operator":"gt","value":"40"},{"property":"title","value":"No match"}]}`w);
    filtered.parameters.z8_add("where"w, `{"property":"title","value":"Visible"}`w);
    filtered.parameters.z8_add("quickFilter"w, `{"property":"amount","operator":"lt","value":"50"}`w);
    z8_application_set_request(filtered); z8_application_start_response(filtered, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(filtered, cast(Z8RequestMonitor)filtered.monitor);
    assert(parseJSON(z8_application_response_text(filtered).to!string)["data"].array.length == 1);
    filtered = new Z8ApplicationRequest(); filtered.session = querySession; filtered.monitor = new Z8RequestMonitor();
    filtered.parameters.z8_add("action"w, "read"w); filtered.parameters.z8_add("fields"w, `["amount"]`w);
    filtered.parameters.z8_add("filter"w, `[]`w);
    filtered.parameters.z8_add("where"w, `{"property":"amount","operator":"lt","value":"40"}`w);
    z8_application_set_request(filtered); z8_application_start_response(filtered, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(filtered, cast(Z8RequestMonitor)filtered.monitor);
    assert(parseJSON(z8_application_response_text(filtered).to!string)["data"].array.length == 0);
    long lookup(wstring fields, wstring text) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("fields"w, `["amount"]`w);
        request.parameters.z8_add("lookupFields"w, fields); request.parameters.z8_add("lookup"w, text);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor);
        return cast(long)parseJSON(z8_application_response_text(request).to!string)["data"].array.length;
    }
    assert(lookup(`["title","details"]`w, "VIS"w) == 1);
    assert(lookup(`["title","details"]`w, "absent"w) == 0);
    long periodRows(wstring period) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("fields"w, `["amount"]`w); request.parameters.z8_add("period"w, period);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor);
        return cast(long)parseJSON(z8_application_response_text(request).to!string)["data"].array.length;
    }
    assert(periodRows(`{"active":true,"start":"1000","finish":"1000"}`w) == 1);
    assert(periodRows(`{"active":true,"start":"1001"}`w) == 0);
    assert(periodRows(`{"active":false,"start":"1001"}`w) == 1);
    queryUser.privileges.setFieldAccess(z8_guid_create_name("Sample;--.Moment"w), Z8Access.init);
    bool periodDenied;
    try { periodRows(`{"active":true,"start":"1000"}`w); } catch (Exception) { periodDenied = true; }
    assert(periodDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access.init);
    assert(rejectedRead("filter"w, `{"property":"title","value":"Visible"}`w));
    bool lookupDenied;
    try { lookup(`["title"]`w, "Visible"w); } catch (Exception) { lookupDenied = true; }
    assert(lookupDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    queryUser.privileges.setRequestAccess(bootRequestKey, Z8Access.init);
    assert(rejectedRead("fields"w, `["title"]`w));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    db.execute(`INSERT INTO "z8_bootstrap"."Sample;--" ("RecordId", "Title", "Amount") VALUES ('00000000-0000-0000-0000-00000000012E', 'Second', 10)`);
    wstring totalRead(wstring fields, wstring filter = null, wstring session = null, wstring having = null) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("fields"w, fields); request.parameters.z8_add("totals"w, "true"w);
        if (filter !is null) request.parameters.z8_add("filter"w, filter);
        if (session !is null) request.parameters.z8_add("session"w, session);
        if (having !is null) request.parameters.z8_add("having"w, having);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); return z8_application_response_text(request);
    }
    auto totalsJson = parseJSON(totalRead(`["amount","title"]`w).to!string);
    assert(totalsJson["data"]["amount"].integer == 52 && "title" !in totalsJson["data"].object);
    totalsJson = parseJSON(totalRead(`["computed"]`w).to!string);
    assert(totalsJson["data"]["computed"].integer == 54, totalsJson.toString());
    totalsJson = parseJSON(totalRead(`["amount"]`w, `{"property":"amount","operator":"gt","value":"20"}`w).to!string);
    assert(totalsJson["data"]["amount"].integer == 42);
    totalsJson = parseJSON(totalRead(`["amount"]`w, `{"property":"amount","operator":"gt","value":"100"}`w).to!string);
    assert(totalsJson["data"]["amount"].integer == 0);
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Amount" = 11 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    totalsJson = parseJSON(totalRead(`["amount"]`w, null, "with-average"w).to!string);
    assert(totalsJson["data"]["amount"].integer == 26);
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Amount" = 10 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Flag" = 0 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    totalsJson = parseJSON(totalRead(`["amount"]`w, null, "with-group"w).to!string);
    assert(totalsJson["data"]["amount"].integer == 52);
    totalsJson = parseJSON(totalRead(`["computed"]`w, null, "with-group"w).to!string);
    assert(totalsJson["data"]["computed"].integer == 54, totalsJson.toString());
    totalsJson = parseJSON(totalRead(`["amount"]`w, null, "with-group"w, `{"property":"amount","operator":"gt","value":"20"}`w).to!string);
    assert(totalsJson["data"]["amount"].integer == 42);
    totalsJson = parseJSON(totalRead(`["amount"]`w, null, "with-group"w, `{"property":"amount","operator":"gt","value":"100"}`w).to!string);
    assert(totalsJson["data"]["amount"].integer == 0);
    db.execute(`INSERT INTO "z8_bootstrap"."Sample;--" ("RecordId", "Title", "Amount", "Flag") VALUES ('00000000-0000-0000-0000-000000000140', 'Average 1', 11, 1), ('00000000-0000-0000-0000-000000000141', 'Average 2', 13, 0)`);
    totalsJson = parseJSON(totalRead(`["amount"]`w, null, "with-group-average"w).to!string);
    assert(totalsJson["data"]["amount"].integer == 19);
    db.execute(`DELETE FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" IN ('00000000-0000-0000-0000-000000000140', '00000000-0000-0000-0000-000000000141')`);
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Flag" = 1 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    auto amountKey = z8_guid_create_name("Sample;--.Amount"w);
    queryUser.privileges.setFieldAccess(amountKey, Z8Access.init);
    totalsJson = parseJSON(totalRead(`["amount"]`w).to!string);
    assert("amount" !in totalsJson["data"].object);
    totalsJson = parseJSON(totalRead(`["computed"]`w).to!string);
    assert("computed" !in totalsJson["data"].object);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    wstring groupedRead(wstring having, bool count = false) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("session"w, "with-group"w);
        request.parameters.z8_add("fields"w, `["flag","amount"]`w); request.parameters.z8_add("having"w, having);
        if (count) request.parameters.z8_add("count"w, "true"w);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); return z8_application_response_text(request);
    }
    auto groupJson = parseJSON(groupedRead(`{"property":"amount","operator":"ge","value":"50"}`w).to!string);
    assert(groupJson["data"].array.length == 1 && groupJson["data"][0]["flag"].boolean && groupJson["data"][0]["amount"].integer == 52, groupJson.toString());
    assert("recordId" !in groupJson["data"][0].object && "lock" !in groupJson["data"][0].object);
    assert(parseJSON(groupedRead(`{"property":"amount","operator":"gt","value":"60"}`w).to!string)["data"].array.length == 0);
    assert(parseJSON(groupedRead(`{"property":"amount","operator":"ge","value":"50"}`w, true).to!string)["total"].integer == 1);
    assert(parseJSON(groupedRead(`{"property":"amount","operator":"gt","value":"60"}`w, true).to!string)["total"].integer == 0);
    auto arrayRequest = new Z8ApplicationRequest(); arrayRequest.session = querySession; arrayRequest.monitor = new Z8RequestMonitor();
    arrayRequest.parameters.z8_add("action"w, "read"w); arrayRequest.parameters.z8_add("session"w, "with-group-arrays"w);
    arrayRequest.parameters.z8_add("fields"w, `["flag","amount","title"]`w);
    z8_application_set_request(arrayRequest); z8_application_start_response(arrayRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(arrayRequest, cast(Z8RequestMonitor)arrayRequest.monitor);
    auto arrayJson = parseJSON(z8_application_response_text(arrayRequest).to!string);
    // IntegerField.get() returns null for arrays; its initially true wasNull flag
    // makes Field.writeData emit the Java null replacement, zero.
    assert(arrayJson["data"].array.length == 1 && arrayJson["data"][0]["amount"].integer == 0, arrayJson.toString());
    auto titles = parseJSON(arrayJson["data"][0]["title"].str).array;
    assert(titles.length == 2 && titles[0].str == "Second" && titles[1].str == "Visible");
    auto computedRequest = new Z8ApplicationRequest(); computedRequest.session = querySession; computedRequest.monitor = new Z8RequestMonitor();
    computedRequest.parameters.z8_add("action"w, "read"w); computedRequest.parameters.z8_add("session"w, "with-group"w);
    computedRequest.parameters.z8_add("fields"w, `["flag","computed"]`w);
    computedRequest.parameters.z8_add("having"w, `{"property":"computed","operator":"ge","value":"54"}`w);
    z8_application_set_request(computedRequest); z8_application_start_response(computedRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(computedRequest, cast(Z8RequestMonitor)computedRequest.monitor);
    auto computedJson = parseJSON(z8_application_response_text(computedRequest).to!string);
    assert(computedJson["data"].array.length == 1 && computedJson["data"][0]["computed"].integer == 54, computedJson.toString());
    computedRequest = new Z8ApplicationRequest(); computedRequest.session = querySession; computedRequest.monitor = new Z8RequestMonitor();
    computedRequest.parameters.z8_add("action"w, "read"w); computedRequest.parameters.z8_add("session"w, "with-group"w);
    computedRequest.parameters.z8_add("fields"w, `["flag","computed"]`w);
    computedRequest.parameters.z8_add("having"w, `{"property":"computed","operator":"ge","value":"55"}`w);
    z8_application_set_request(computedRequest); z8_application_start_response(computedRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(computedRequest, cast(Z8RequestMonitor)computedRequest.monitor);
    assert(parseJSON(z8_application_response_text(computedRequest).to!string)["data"].array.length == 0);
    queryUser.privileges.setFieldAccess(amountKey, Z8Access.init);
    computedRequest = new Z8ApplicationRequest(); computedRequest.session = querySession; computedRequest.monitor = new Z8RequestMonitor();
    computedRequest.parameters.z8_add("action"w, "read"w); computedRequest.parameters.z8_add("session"w, "with-group"w);
    computedRequest.parameters.z8_add("fields"w, `["flag","computed"]`w);
    z8_application_set_request(computedRequest); z8_application_start_response(computedRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(computedRequest, cast(Z8RequestMonitor)computedRequest.monitor);
    computedJson = parseJSON(z8_application_response_text(computedRequest).to!string);
    assert("computed" !in computedJson["data"][0].object);
    computedRequest = new Z8ApplicationRequest(); computedRequest.session = querySession; computedRequest.monitor = new Z8RequestMonitor();
    computedRequest.parameters.z8_add("action"w, "read"w); computedRequest.parameters.z8_add("session"w, "with-group"w);
    computedRequest.parameters.z8_add("fields"w, `["flag"]`w);
    computedRequest.parameters.z8_add("having"w, `{"property":"computed","operator":"ge","value":"54"}`w);
    z8_application_set_request(computedRequest); z8_application_start_response(computedRequest, "Sample"w);
    bool havingDenied; try { z8_application_dispatch_query_read("Sample"w); } catch (Exception) { havingDenied = true; }
    assert(havingDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    auto groupByExpression = new Z8ApplicationRequest(); groupByExpression.session = querySession; groupByExpression.monitor = new Z8RequestMonitor();
    groupByExpression.parameters.z8_add("action"w, "read"w); groupByExpression.parameters.z8_add("session"w, "with-computed-group"w);
    groupByExpression.parameters.z8_add("fields"w, `["computed","amount"]`w);
    groupByExpression.parameters.z8_add("sort"w, `[{"property":"computed"}]`w);
    z8_application_set_request(groupByExpression); z8_application_start_response(groupByExpression, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(groupByExpression, cast(Z8RequestMonitor)groupByExpression.monitor);
    auto computedGroups = parseJSON(z8_application_response_text(groupByExpression).to!string)["data"].array;
    assert(computedGroups.length == 2 && computedGroups[0]["computed"].integer == 11 && computedGroups[0]["amount"].integer == 10);
    assert(computedGroups[1]["computed"].integer == 43 && computedGroups[1]["amount"].integer == 42);
    queryUser.privileges.setFieldAccess(amountKey, Z8Access.init);
    groupByExpression = new Z8ApplicationRequest(); groupByExpression.session = querySession; groupByExpression.monitor = new Z8RequestMonitor();
    groupByExpression.parameters.z8_add("action"w, "read"w); groupByExpression.parameters.z8_add("session"w, "with-computed-group"w);
    groupByExpression.parameters.z8_add("fields"w, `["computed"]`w);
    z8_application_set_request(groupByExpression); z8_application_start_response(groupByExpression, "Sample"w);
    bool computedGroupDenied; try { z8_application_dispatch_query_read("Sample"w); } catch (Exception) { computedGroupDenied = true; }
    assert(computedGroupDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    queryUser.privileges.setFieldAccess(z8_guid_create_name("Sample;--.Flag"w), Z8Access.init);
    bool groupDenied;
    try { groupedRead(`{"property":"amount","operator":"ge","value":"50"}`w); } catch (Exception) { groupDenied = true; }
    assert(groupDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Flag" = 0 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    wstring orderedGroup(wstring group, wstring sort) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("fields"w, `["flag","amount"]`w);
        request.parameters.z8_add("group"w, group); request.parameters.z8_add("sort"w, sort);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); return z8_application_response_text(request);
    }
    auto orderedJson = parseJSON(orderedGroup(`{"property":"flag"}`w, `[{"property":"amount","direction":"DESC"}]`w).to!string);
    assert(orderedJson["data"].array.length == 2 && orderedJson["data"][0]["amount"].integer == 10 && orderedJson["data"][1]["amount"].integer == 42);
    orderedJson = parseJSON(orderedGroup(`[{"property":"flag"}]`w, `[{"property":"flag","direction":"DESC"}]`w).to!string);
    assert(orderedJson["data"][0]["amount"].integer == 42 && orderedJson["data"][1]["amount"].integer == 10);
    auto defaultOrder = new Z8ApplicationRequest(); defaultOrder.session = querySession; defaultOrder.monitor = new Z8RequestMonitor();
    defaultOrder.parameters.z8_add("request"w, "Sample"w); defaultOrder.parameters.z8_add("session"w, "default-order"w);
    defaultOrder.parameters.z8_add("fields"w, `["flag","amount"]`w);
    z8_application_set_request(defaultOrder); z8_application_start_response(defaultOrder, "Sample"w); z8_application_dispatch_request();
    z8_application_finish_response(defaultOrder, cast(Z8RequestMonitor)defaultOrder.monitor);
    auto defaultOrderJson = parseJSON(z8_application_response_text(defaultOrder).to!string);
    assert(defaultOrderJson["group"][0].str == "flag" && defaultOrderJson["sort"].array.length == 2);
    assert(defaultOrderJson["sort"][0]["property"].str == "flag" && defaultOrderJson["sort"][1]["direction"].str == "desc");
    assert(defaultOrderJson["data"][0]["amount"].integer == 10 && defaultOrderJson["data"][1]["amount"].integer == 42);
    queryUser.privileges.setFieldAccess(z8_guid_create_name("Sample;--.Flag"w), Z8Access.init);
    groupDenied = false;
    try { orderedGroup(`{"property":"flag"}`w, `[]`w); } catch (Exception) { groupDenied = true; }
    assert(groupDenied);
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    db.execute(`UPDATE "z8_bootstrap"."Sample;--" SET "Flag" = 1 WHERE "RecordId" = '00000000-0000-0000-0000-00000000012E'`);
    long sortedAmount(wstring sorting, wstring start = "0"w) {
        auto sorted = new Z8ApplicationRequest(); sorted.session = querySession; sorted.monitor = new Z8RequestMonitor();
        sorted.parameters.z8_add("action"w, "read"w); sorted.parameters.z8_add("fields"w, `["amount"]`w);
        sorted.parameters.z8_add("sort"w, sorting); sorted.parameters.z8_add("start"w, start); sorted.parameters.z8_add("limit"w, "1"w);
        z8_application_set_request(sorted); z8_application_start_response(sorted, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(sorted, cast(Z8RequestMonitor)sorted.monitor);
        return parseJSON(z8_application_response_text(sorted).to!string)["data"][0]["amount"].integer;
    }
    assert(sortedAmount(`[{"property":"amount"}]`w) == 10);
    assert(sortedAmount(`[{"property":"amount","direction":"DESC"}]`w) == 42);
    assert(sortedAmount(`[{"property":"amount","direction":"DESC"}]`w, "1"w) == 10);
    assert(rejectedRead("sort"w, `[{"property":"amount","direction":"invalid"}]`w));
    assert(!rejectedRead("sort"w, `[{"property":"computed"}]`w));
    long recordCount(wstring ids, wstring filter = null) {
        auto byId = new Z8ApplicationRequest(); byId.session = querySession; byId.monitor = new Z8RequestMonitor();
        byId.parameters.z8_add("action"w, "read"w); byId.parameters.z8_add("fields"w, `["amount"]`w);
        byId.parameters.z8_add("recordId"w, ids); if (filter !is null) byId.parameters.z8_add("filter"w, filter);
        z8_application_set_request(byId); z8_application_start_response(byId, "Sample"w); z8_application_dispatch_query_read("Sample"w);
        z8_application_finish_response(byId, cast(Z8RequestMonitor)byId.monitor);
        return cast(long)parseJSON(z8_application_response_text(byId).to!string)["data"].array.length;
    }
    assert(recordCount("00000000-0000-0000-0000-00000000012D"w) == 1);
    assert(recordCount(`["00000000-0000-0000-0000-00000000012D","00000000-0000-0000-0000-00000000012E"]`w) == 2);
    assert(recordCount(`["00000000-0000-0000-0000-00000000012D"]`w, `{"property":"amount","operator":"lt","value":"0"}`w) == 1);
    assert(recordCount(`[]`w, `{"property":"amount","operator":"lt","value":"0"}`w) == 0);
    assert(recordCount("00000000-0000-0000-0000-000000000000"w) == 0);
    db.execute(`INSERT INTO "z8_bootstrap"."Sample;--" ("RecordId", "Title", "Amount") VALUES ('00000000-0000-0000-0000-00000000012F', 'Outside scope', -10)`);
    assert(recordCount(`[]`w) == 2);
    assert(recordCount("00000000-0000-0000-0000-00000000012F"w) == 1);
    auto countRequest = new Z8ApplicationRequest(); countRequest.session = querySession; countRequest.monitor = new Z8RequestMonitor();
    countRequest.parameters.z8_add("action"w, "read"w); countRequest.parameters.z8_add("fields"w, `["amount"]`w);
    countRequest.parameters.z8_add("count"w, "true"w); countRequest.parameters.z8_add("filter"w, `{"property":"amount","operator":"gt","value":"20"}`w);
    z8_application_set_request(countRequest); z8_application_start_response(countRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(countRequest, cast(Z8RequestMonitor)countRequest.monitor);
    auto countJson = parseJSON(z8_application_response_text(countRequest).to!string);
    assert(countJson["total"].integer == 1 && "data" !in countJson.object);
    countRequest = new Z8ApplicationRequest(); countRequest.session = querySession; countRequest.monitor = new Z8RequestMonitor();
    countRequest.parameters.z8_add("action"w, "read"w); countRequest.parameters.z8_add("fields"w, `["amount"]`w);
    countRequest.parameters.z8_add("count"w, "true"w); countRequest.parameters.z8_add("filter"w, `{"property":"amount","operator":"gt","value":"100"}`w);
    z8_application_set_request(countRequest); z8_application_start_response(countRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(countRequest, cast(Z8RequestMonitor)countRequest.monitor);
    countJson = parseJSON(z8_application_response_text(countRequest).to!string);
    assert(countJson["total"].integer == 0 && "data" !in countJson.object);
    countRequest = new Z8ApplicationRequest(); countRequest.session = querySession; countRequest.monitor = new Z8RequestMonitor();
    countRequest.parameters.z8_add("action"w, "read"w); countRequest.parameters.z8_add("fields"w, `["amount"]`w);
    countRequest.parameters.z8_add("count"w, "true"w); countRequest.parameters.z8_add("start"w, "9"w); countRequest.parameters.z8_add("limit"w, "1"w);
    countRequest.parameters.z8_add("sort"w, `[{"property":"amount","direction":"asc"}]`w);
    z8_application_set_request(countRequest); z8_application_start_response(countRequest, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(countRequest, cast(Z8RequestMonitor)countRequest.monitor);
    countJson = parseJSON(z8_application_response_text(countRequest).to!string);
    assert(countJson["total"].integer == 2 && countJson["data"].array.length == 1 && countJson["data"][0]["amount"].integer == 42);
    auto hooked = new Z8ApplicationRequest(); hooked.session = querySession; hooked.monitor = new Z8RequestMonitor();
    hooked.parameters.z8_add("action"w, "read"w); hooked.parameters.z8_add("fields"w, `["amount"]`w); hooked.parameters.z8_add("session"w, "with-hook"w);
    z8_application_set_request(hooked); z8_application_start_response(hooked, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(hooked, cast(Z8RequestMonitor)hooked.monitor);
    auto hookedJson = parseJSON(z8_application_response_text(hooked).to!string);
    assert(hookedJson["data"].array.length == 1 && hookedJson["data"][0]["amount"].integer == 42);
    auto defaultRead = new Z8ApplicationRequest(); defaultRead.session = querySession; defaultRead.monitor = new Z8RequestMonitor();
    defaultRead.parameters.z8_add("request"w, "Sample"w); defaultRead.parameters.z8_add("fields"w, `["amount"]`w);
    defaultRead.parameters.z8_add("session"w, "default-events"w); defaultRead.parameters.z8_add("values"w, `{"amount":40}`w);
    z8_application_set_request(defaultRead); z8_application_start_response(defaultRead, "Sample"w); z8_application_dispatch_request();
    z8_application_finish_response(defaultRead, cast(Z8RequestMonitor)defaultRead.monitor);
    auto defaultJson = parseJSON(z8_application_response_text(defaultRead).to!string);
    assert(defaultJson["isQuery"].boolean && defaultJson["data"].array.length == 1 && defaultJson["data"][0]["amount"].integer == 42);
    auto contextRead = new Z8ApplicationRequest(); contextRead.session = querySession; contextRead.monitor = new Z8RequestMonitor();
    contextRead.parameters.z8_add("action"w, "read"w); contextRead.parameters.z8_add("fields"w, `["amount"]`w);
    contextRead.parameters.z8_add("session"w, "with-values"w); contextRead.parameters.z8_add("values"w, `[{"amount":40}]`w);
    z8_application_set_request(contextRead); z8_application_start_response(contextRead, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(contextRead, cast(Z8RequestMonitor)contextRead.monitor);
    auto contextJson = parseJSON(z8_application_response_text(contextRead).to!string);
    assert(contextJson["data"].array.length == 1 && contextJson["data"][0]["amount"].integer == 42);
    assert(!rejectedRead("values"w, `[]`w));
    assert(rejectedRead("values"w, `[42]`w));
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access.init);
    assert(rejectedRead("values"w, `{"title":"Hidden"}`w));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    bool update(wstring data, out wstring output, wstring values = null, wstring sessionId = null) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, "Sample"w); request.parameters.z8_add("action"w, "update"w);
        request.parameters.z8_add("fields"w, `["title","amount"]`w); request.parameters.z8_add("data"w, data);
        if (values !is null) request.parameters.z8_add("values"w, values);
        if (sessionId !is null) request.parameters.z8_add("session"w, sessionId);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w);
        try { z8_application_dispatch_request(); } catch (Exception) { return false; }
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); output = z8_application_response_text(request); return true;
    }
    wstring updateResult;
    assert(update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","title":"Updated","amount":44}]`w, updateResult));
    auto updatedJson = parseJSON(updateResult.to!string);
    assert(updatedJson["data"].array.length == 1 && updatedJson["data"][0]["title"].str == "Updated" && updatedJson["data"][0]["amount"].integer == 44);
    assert(update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","flag":false,"price":"17.25","reference":"00000000-0000-0000-0000-000000000063","moment":"2024-01-02T03:04:05Z","duration":"01:02:03","details":"Данные"}]`w, updateResult));
    auto scalars = db.execute(`SELECT "Flag", "Price", "Reference", "Moment", "Duration", convert_from("Details", 'UTF8') FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-00000000012D'`);
    assert(scalars.rows[0][0].text == "0" && scalars.rows[0][1].text == "17.25" && scalars.rows[0][2].text == "00000000-0000-0000-0000-000000000063");
    assert(scalars.rows[0][3].text.to!long == z8_date_ticks(z8_date_parse("2024-01-02T03:04:05Z"w)) && scalars.rows[0][4].text == "3723000" && scalars.rows[0][5].text == "Данные");
    auto upload = new Z8ApplicationRequest(); upload.session = querySession; upload.monitor = new Z8RequestMonitor();
    upload.parameters.z8_add("request"w, "Sample"w); upload.parameters.z8_add("action"w, "update"w);
    upload.parameters.z8_add("fields"w, `["title"]`w); upload.parameters.z8_add("data"w, `[{"recordId":"00000000-0000-0000-0000-00000000012D","blob":0}]`w);
    upload.files.z8_add(z8_file_from_upload("data.bin"w, cast(const(ubyte)[])[0, 255, 65]));
    z8_application_set_request(upload); z8_application_start_response(upload, "Sample"w); z8_application_dispatch_request();
    assert(db.execute(`SELECT encode("Blob", 'hex') FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-00000000012D'`).rows[0][0].text == "00ff41");
    assert(!update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","blob":0}]`w, updateResult));
    assert(!update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","amount":55},{"recordId":"00000000-0000-0000-0000-00000000012E","amount":"invalid"}]`w, updateResult));
    assert(db.execute(`SELECT "Amount" FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-00000000012D'`).rows[0][0].text == "44");
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access(true, false, false, false, false, false));
    assert(!update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","title":"Denied"}]`w, updateResult));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    assert(!update(`[{"title":"Missing id"}]`w, updateResult));
    assert(update(`[{"recordId":"00000000-0000-0000-0000-00000000012D","amount":44}]`w, updateResult, `{"amount":100}`w, "write-values"w));
    assert(parseJSON(updateResult.to!string)["data"].array.length == 0);
    bool create(wstring data, out wstring output, wstring values = null, wstring sessionId = null) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, "Sample"w); request.parameters.z8_add("action"w, "create"w);
        request.parameters.z8_add("fields"w, `["title","amount"]`w); request.parameters.z8_add("data"w, data);
        if (values !is null) request.parameters.z8_add("values"w, values);
        if (sessionId !is null) request.parameters.z8_add("session"w, sessionId);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w);
        try { z8_application_dispatch_request(); } catch (Exception) { return false; }
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); output = z8_application_response_text(request); return true;
    }
    wstring createResult;
    assert(create(`[{"recordId":"00000000-0000-0000-0000-000000000133","title":"Created","amount":88}]`w, createResult));
    auto createdJson = parseJSON(createResult.to!string);
    assert(createdJson["data"].array.length == 1 && createdJson["data"][0]["recordId"].str == "00000000-0000-0000-0000-000000000133");
    assert(createdJson["data"][0]["title"].str == "Created" && createdJson["data"][0]["amount"].integer == 88);
    assert(create(`[{"recordId":"00000000-0000-0000-0000-000000000136","title":"Context","amount":88}]`w, createResult, `{"amount":100}`w, "write-values"w));
    assert(parseJSON(createResult.to!string)["data"].array.length == 0);
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-000000000136'`).rows[0][0].text == "1");
    assert(!create(`[{"recordId":"00000000-0000-0000-0000-000000000137"}]`w, createResult, `{"amount":[]}`w));
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-000000000137'`).rows[0][0].text == "0");
    auto createUpload = new Z8ApplicationRequest(); createUpload.session = querySession; createUpload.monitor = new Z8RequestMonitor();
    createUpload.parameters.z8_add("request"w, "Sample"w); createUpload.parameters.z8_add("action"w, "create"w); createUpload.parameters.z8_add("fields"w, `["title"]`w);
    createUpload.parameters.z8_add("data"w, `[{"recordId":"00000000-0000-0000-0000-000000000135","title":"Upload","blob":0}]`w);
    createUpload.files.z8_add(z8_file_from_upload("data.bin"w, cast(const(ubyte)[])[7, 8, 255]));
    z8_application_set_request(createUpload); z8_application_start_response(createUpload, "Sample"w); z8_application_dispatch_request();
    assert(db.execute(`SELECT encode("Blob", 'hex') FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-000000000135'`).rows[0][0].text == "0708ff");
    assert(!create(`[{"recordId":"00000000-0000-0000-0000-000000000134","title":"Rollback"},{"recordId":"00000000-0000-0000-0000-000000000133"}]`w, createResult));
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-000000000134'`).rows[0][0].text == "0");
    queryUser.privileges.setTableAccess(bootTableKey, Z8Access(true, false, false, false, false, true));
    assert(!create(`[{"title":"Denied"}]`w, createResult));
    queryUser.privileges.setTableAccess(bootTableKey, Z8Access(true, false, true, false, false, true));
    assert(create(`[{"recordId":"00000000-0000-0000-0000-000000000000","title":"Generated","amount":66}]`w, createResult));
    createdJson = parseJSON(createResult.to!string);
    assert(createdJson["data"].array.length == 1 && createdJson["data"][0]["recordId"].str != "00000000-0000-0000-0000-000000000000");
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    bool copy(wstring sourceIds, wstring data, out wstring output, wstring values = null, wstring sessionId = null) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, "Sample"w); request.parameters.z8_add("action"w, "copy"w);
        request.parameters.z8_add("fields"w, `["title","amount"]`w); request.parameters.z8_add("data"w, data); request.parameters.z8_add("recordId"w, sourceIds);
        if (values !is null) request.parameters.z8_add("values"w, values);
        if (sessionId !is null) request.parameters.z8_add("session"w, sessionId);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w);
        try { z8_application_dispatch_request(); } catch (Exception) { return false; }
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); output = z8_application_response_text(request); return true;
    }
    wstring copyResult;
    assert(copy("00000000-0000-0000-0000-000000000133"w, `[{"title":"Copy","amount":99}]`w, copyResult));
    auto copyJson = parseJSON(copyResult.to!string);
    assert(copyJson["data"].array.length == 1 && copyJson["data"][0]["title"].str == "Copy" && copyJson["data"][0]["amount"].integer == 99);
    assert(copyJson["data"][0]["recordId"].str != "00000000-0000-0000-0000-000000000133");
    assert(copy("00000000-0000-0000-0000-000000000133"w, `[{"recordId":"00000000-0000-0000-0000-000000000138","amount":88}]`w, copyResult, `{"amount":100}`w, "write-values"w));
    assert(parseJSON(copyResult.to!string)["data"].array.length == 0);
    auto countBeforeFailedCopy = db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--"`).rows[0][0].text;
    assert(!copy(`["00000000-0000-0000-0000-000000000133","invalid"]`w, `[{},{}]`w, copyResult));
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--"`).rows[0][0].text == countBeforeFailedCopy);
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access(true, false, false, false, false, false));
    assert(!copy("00000000-0000-0000-0000-000000000133"w, `[{}]`w, copyResult));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    db.execute(`INSERT INTO "z8_bootstrap"."Sample;--" ("RecordId", "Title", "Amount", "Flag", "Price") VALUES ('00000000-0000-0000-0000-000000000130', NULL, NULL, NULL, NULL)`);
    auto nullRead = new Z8ApplicationRequest(); nullRead.session = querySession; nullRead.monitor = new Z8RequestMonitor();
    nullRead.parameters.z8_add("action"w, "read"w); nullRead.parameters.z8_add("fields"w, `["title","amount","flag","price"]`w);
    nullRead.parameters.z8_add("recordId"w, "00000000-0000-0000-0000-000000000130"w);
    z8_application_set_request(nullRead); z8_application_start_response(nullRead, "Sample"w); z8_application_dispatch_query_read("Sample"w);
    z8_application_finish_response(nullRead, cast(Z8RequestMonitor)nullRead.monitor);
    auto nullJson = parseJSON(z8_application_response_text(nullRead).to!string);
    assert(nullJson["data"].array.length == 1 && nullJson["data"][0]["title"].str == "" && nullJson["data"][0]["amount"].integer == 0);
    assert(nullJson["data"][0]["flag"].boolean && nullJson["data"][0]["price"].integer == 0);
    db.execute(`CREATE TABLE "z8_bootstrap"."DeleteRef" ("Target" uuid REFERENCES "z8_bootstrap"."Sample;--" ("RecordId"))`);
    db.execute(`INSERT INTO "z8_bootstrap"."DeleteRef" VALUES ('00000000-0000-0000-0000-00000000012E')`);
    bool destroy(wstring data) {
        auto request = new Z8ApplicationRequest(); request.session = querySession; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, "Sample"w); request.parameters.z8_add("action"w, "destroy"w); request.parameters.z8_add("data"w, data);
        z8_application_set_request(request); z8_application_start_response(request, "Sample"w);
        try { z8_application_dispatch_request(); } catch (Exception) { return false; }
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor); return true;
    }
    assert(!destroy(`[]`w));
    assert(!destroy(`[{"recordId":"bad"}]`w));
    queryUser.privileges.setTableAccess(bootTableKey, Z8Access(true, false, false, false, false, true));
    assert(!destroy(`["00000000-0000-0000-0000-00000000012D"]`w));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    assert(!destroy(`["00000000-0000-0000-0000-00000000012D",{"recordId":"00000000-0000-0000-0000-00000000012E"}]`w));
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" = '00000000-0000-0000-0000-00000000012D'`).rows[0][0].text == "1");
    db.execute(`DELETE FROM "z8_bootstrap"."DeleteRef"`);
    assert(destroy(`["00000000-0000-0000-0000-00000000012D",{"recordId":"00000000-0000-0000-0000-00000000012E"},"00000000-0000-0000-0000-000000000000"]`w));
    assert(db.execute(`SELECT count(*) FROM "z8_bootstrap"."Sample;--" WHERE "RecordId" IN ('00000000-0000-0000-0000-00000000012D', '00000000-0000-0000-0000-00000000012E')`).rows[0][0].text == "0");
    assert(rejectedRead("recordId"w, `["invalid"]`w));
    queryUser.privileges.setFieldAccess(bootFieldKey, Z8Access.init);
    assert(rejectedRead("sort"w, `[{"property":"title"}]`w));
    queryUser.privileges = adminPrivileges.privileges = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(2)).privileges;
    z8_application_set_request(priorReadRequest); z8_connection_set_current(priorReadBackend);
    auto noRoles = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(999));
    assert(noRoles.roleIds.length == 0 && !noRoles.privileges.getTableAccess(bootTableKey).read && !noRoles.privileges.getRequestAccess(bootRequestKey).execute);
    db.execute(`INSERT INTO "z8_bootstrap"."SystemUsers" ("RecordId", "Name") VALUES ('00000000-0000-0000-0000-0000000000DE', 'Multiple roles')`);
    db.execute(`INSERT INTO "z8_bootstrap"."SystemUserRoles" ("RecordId", "User", "Role") VALUES ('00000000-0000-0000-0000-0000000000DF', '00000000-0000-0000-0000-0000000000DE', '421A8413-A8EC-4DAB-9235-9A5FF83341C5'), ('00000000-0000-0000-0000-0000000000E0', '00000000-0000-0000-0000-0000000000DE', 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08')`);
    db.execute(`UPDATE "z8_bootstrap"."SystemRoleTableAccess" SET "Write" = 1 WHERE "Role" = 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08'`);
    db.execute(`UPDATE "z8_bootstrap"."SystemRoleFieldAccess" SET "Read" = 0, "Write" = 0 WHERE "Field" = $1::uuid AND "Role" IN ('421A8413-A8EC-4DAB-9235-9A5FF83341C5', 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08')`, [Z8PostgresParameter.value(z8_guid_to_string(bootFieldKey).to!string)]);
    db.execute(`UPDATE "z8_bootstrap"."SystemRoleRequestAccess" SET "Execute" = 1 WHERE "Role" = 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08'`);
    auto combined = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(222));
    assert(combined.roleIds.length == 2 && combined.privileges.getDefaultAccess().read && !combined.privileges.getDefaultAccess().write);
    assert(combined.privileges.getTableAccess(bootTableKey).read && combined.privileges.getTableAccess(bootTableKey).write);
    assert(!combined.privileges.getFieldAccess(bootTableKey, bootFieldKey).read && !combined.privileges.getFieldAccess(bootTableKey, bootFieldKey).write);
    assert(combined.privileges.getRequestAccess(bootRequestKey).execute);
    auto refreshed = new Z8UserData(); refreshed.id = z8_guid_create(222);
    z8_postgres_refresh_user_privileges(db, "z8_bootstrap"w, refreshed);
    assert(refreshed.roles.length == 2 && refreshed.privileges.getRequestAccess(bootRequestKey).execute);
    auto refreshedSession = new Z8ApplicationSession("privileges"w, refreshed, refreshed);
    assert(z8_application_may_execute(refreshedSession, "Sample"w, null));
    assert(!z8_application_may_execute(refreshedSession, "Unknown"w, null));
    auto previousPrivileges = refreshed.privileges; auto previousRoles = refreshed.roles.dup;
    bool refreshFailed;
    try { z8_postgres_refresh_user_privileges(db, "missing_schema"w, refreshed); } catch (Z8PostgresException) { refreshFailed = true; }
    assert(refreshFailed && refreshed.privileges is previousPrivileges && refreshed.roles == previousRoles);
    db.execute(`UPDATE "z8_bootstrap"."SystemRoleTableAccess" SET "Read" = 0, "Write" = 0 WHERE "Role" IN ('421A8413-A8EC-4DAB-9235-9A5FF83341C5', 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08')`);
    db.execute(`UPDATE "z8_bootstrap"."SystemRoleFieldAccess" SET "Read" = 1, "Write" = 1 WHERE "Field" = $1::uuid AND "Role" IN ('421A8413-A8EC-4DAB-9235-9A5FF83341C5', 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08')`, [Z8PostgresParameter.value(z8_guid_to_string(bootFieldKey).to!string)]);
    combined = z8_postgres_load_privileges(db, "z8_bootstrap"w, z8_guid_create(222));
    assert(!combined.privileges.getTableAccess(bootTableKey).read && !combined.privileges.getFieldAccess(bootTableKey, bootFieldKey).read && !combined.privileges.getFieldAccess(bootTableKey, bootFieldKey).write);
    assert(db.execute(`SELECT "CreatedBy" FROM "z8_bootstrap"."SystemUsers" WHERE "RecordId" = '00000000-0000-0000-0000-000000000002'`).rows[0][0].text == "00000000-0000-0000-0000-000000000309");
    assert(db.execute(`SELECT "Label" FROM "z8_bootstrap"."Target;--" WHERE "RecordId" = '00000000-0000-0000-0000-000000000000'`).rows[0][0].text == "");
    db.execute(`CREATE SCHEMA "z8_bootfail"`);
    Z8Object[] failingBootstrapTables = [P.m_userRoles(), P.m_roles(), P.m_users(), P.m_sequences(), P.m_systemTables(), P.m_systemFields(),
        P.m_systemRequests(), P.m_roleTableAccess(), P.m_roleFieldAccess(), P.m_roleRequestAccess(), P.m_references()];
    bool bootstrapRolledBack;
    try { z8_postgres_bootstrap(db, "z8_bootfail"w, failingBootstrapTables, bootstrapRegistry); }
    catch (Z8PostgresException) { bootstrapRolledBack = true; }
    assert(bootstrapRolledBack && !db.inTransaction() && z8_application_request() is null);
    assert(db.execute(`SELECT to_regclass('"z8_bootfail"."SystemRoles"') IS NULL`).rows[0][0].text == "t");
    savedBootstrapRequest = z8_application_set_request(bootstrapRequest);
    bool duplicateBootstrap;
    try { z8_postgres_bootstrap(db, "z8_bootfail"w, [P.m_make(), P.m_make()], bootstrapRegistry); }
    catch (Z8PostgresException) { duplicateBootstrap = true; }
    assert(duplicateBootstrap && bootstrapRequest.eventsLevel() == Z8EventsLevel.user && z8_application_request() is bootstrapRequest);
    z8_application_set_request(savedBootstrapRequest);
    auto securityRoles = P.m_roles(); db.execute(z8_postgres_create_table_sql("z8_security"w, securityRoles));
    z8_postgres_ensure_null_record(db, "z8_security"w, securityRoles);
    db.execute(`INSERT INTO "z8_security"."SystemRoles" ("RecordId", "Name") VALUES ('DC08CA72-C668-412F-91B7-022F1C82AC09', 'Administrator')`);
    auto userRoles = P.m_userRoles();
    assert(z8_postgres_create_foreign_keys_sql("z8_security"w, userRoles).length == 2);
    z8_postgres_create_tables(db, "z8_security"w, [userRoles]);
    auto assignments = db.execute(`SELECT "User"::text, "Role"::text, "Lock" FROM "z8_security"."SystemUserRoles" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000' ORDER BY "User"`);
    assert(assignments.rows.length == 2 && assignments.rows[0][0].text == "00000000-0000-0000-0000-000000000001" && assignments.rows[1][0].text == "00000000-0000-0000-0000-000000000002");
    assert(assignments.rows[0][1].text == "dc08ca72-c668-412f-91b7-022f1c82ac09" && assignments.rows[0][2].text == "1" && assignments.rows[1][2].text == "1");
    auto securityBackend = new Z8PostgresDatabase(db, "z8_security"w); auto savedSecurityBackend = z8_connection_set_current(securityBackend);
    auto disabledEvents = new Z8ApplicationRequest(); disabledEvents.setEventsLevel(Z8EventsLevel.none);
    auto securityRequest = z8_application_set_request(disabledEvents);
    bool builtinAssignmentProtected;
    try { P.m_deleteUserRole(userRoles, z8_guid_literal("8D05DB1E-1A17-4E19-949C-F2894920261E")); } catch (Exception) { builtinAssignmentProtected = true; }
    assert(builtinAssignmentProtected);
    bool systemEntryProtected;
    try { P.m_deleteEntry(P.m_entries(), z8_guid_create_name("org.zenframework.z8.server.base.table.system.SystemTools"w)); } catch (Exception) { systemEntryProtected = true; }
    assert(systemEntryProtected); z8_application_set_request(securityRequest); z8_connection_set_current(savedSecurityBackend);
    auto principal = new Z8UserData(); auto session = new Z8ApplicationSession("test"w, principal, principal);
    auto accessRequest = new Z8ApplicationRequest(); accessRequest.session = session;
    securityRequest = z8_application_set_request(accessRequest);
    auto readonlyRoles = P.m_userRoles();
    auto readonly = z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, readonlyRoles);
    assert(z8_optional_require(readonly));
    auto readonlyEntries = P.m_userEntries();
    readonly = z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, readonlyEntries);
    assert(z8_optional_require(readonly));
    principal.administrator = true; auto writableRoles = P.m_userRoles();
    readonly = z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, writableRoles);
    assert(!z8_optional_require(readonly));
    auto writableEntries = P.m_userEntries();
    readonly = z8_native_field!(Z8Optional!bool)("org.zenframework.z8.server.base.query.Query.f_readOnly"w, writableEntries);
    assert(!z8_optional_require(readonly)); z8_application_set_request(securityRequest);
    auto systemTables = P.m_systemTables(); auto systemRequests = P.m_systemRequests();
    auto tablesDDL = z8_postgres_create_table_sql("z8_security"w, systemTables);
    auto requestsDDL = z8_postgres_create_table_sql("z8_security"w, systemRequests);
    assert(tablesDDL.canFind(`"Name" character varying`) && tablesDDL.canFind(`"Description" bytea`) && tablesDDL.canFind(`"Class" character varying`) && tablesDDL.canFind(`"Display Name" character varying`));
    assert(requestsDDL.canFind(`"Name" character varying`) && requestsDDL.canFind(`"Class" character varying`));
    foreach (field; z8_query_declared_fields(systemRequests, true)) if (field.z8_index() == "classId"w) {
        auto length = z8_native_field!(Z8Optional!long)("org.zenframework.z8.server.base.table.value.StringField.f_length"w, field);
        assert(z8_optional_require(length) == 1024);
    }
    z8_postgres_create_tables(db, "z8_security"w, [systemTables, systemRequests]);
    assert(db.execute(`SELECT count(*) FROM "z8_security"."SystemTables"`).rows[0][0].text == "1");
    assert(db.execute(`SELECT count(*) FROM "z8_security"."SystemRequests"`).rows[0][0].text == "1");
    auto systemFields = P.m_systemFields();
    auto fieldsDDL = z8_postgres_create_table_sql("z8_fields"w, systemFields);
    assert(fieldsDDL.canFind(`"Table" uuid`) && fieldsDDL.canFind(`"Class" character varying`) && fieldsDDL.canFind(`"Position" bigint`));
    auto fieldsKeys = z8_postgres_create_foreign_keys_sql("z8_fields"w, systemFields);
    assert(fieldsKeys.length == 1 && fieldsKeys[0].canFind(`FOREIGN KEY ("Table") REFERENCES "z8_fields"."SystemTables" ("RecordId")`));
    bool fieldsTableIndexed;
    foreach (sql; z8_postgres_create_indexes_sql("z8_fields"w, systemFields)) if (sql.canFind(`("Table")`)) fieldsTableIndexed = true;
    assert(fieldsTableIndexed);
    db.execute(`CREATE SCHEMA "z8_fields"`);
    z8_postgres_create_tables(db, "z8_fields"w, [systemFields, P.m_systemTables()]);
    bool invalidTableReference;
    try { db.execute(`INSERT INTO "z8_fields"."SystemFields" ("RecordId", "Table") VALUES ('00000000-0000-0000-0000-000000000051', '00000000-0000-0000-0000-000000000099')`); }
    catch (Z8PostgresException) { invalidTableReference = true; }
    assert(invalidTableReference);
    db.execute(`INSERT INTO "z8_fields"."SystemTables" ("RecordId", "Name") VALUES ('00000000-0000-0000-0000-000000000052', 'Customers')`);
    db.execute(`INSERT INTO "z8_fields"."SystemFields" ("RecordId", "Table") VALUES ('00000000-0000-0000-0000-000000000053', '00000000-0000-0000-0000-000000000052')`);
    auto fieldsBackend = new Z8PostgresDatabase(db, "z8_fields"w); auto savedFieldsBackend = z8_connection_set_current(fieldsBackend);
    assert(P.m_fieldTableName(systemFields) == "Customers"w); z8_connection_set_current(savedFieldsBackend);
    auto roleTableAccess = P.m_roleTableAccess(); auto roleFieldAccess = P.m_roleFieldAccess(); auto roleRequestAccess = P.m_roleRequestAccess();
    auto tableAccessDDL = z8_postgres_create_table_sql("z8_access"w, roleTableAccess);
    auto fieldAccessDDL = z8_postgres_create_table_sql("z8_access"w, roleFieldAccess);
    auto requestAccessDDL = z8_postgres_create_table_sql("z8_access"w, roleRequestAccess);
    assert(tableAccessDDL.canFind(`"Role" uuid`) && tableAccessDDL.canFind(`"Table" uuid`) && tableAccessDDL.canFind(`"Lock" bigint DEFAULT 3`));
    assert(fieldAccessDDL.canFind(`"Field" uuid`) && fieldAccessDDL.canFind(`"Read" smallint`) && fieldAccessDDL.canFind(`"Write" smallint`));
    assert(requestAccessDDL.canFind(`"Request" uuid`) && requestAccessDDL.canFind(`"Execute" smallint`));
    assert(z8_postgres_create_foreign_keys_sql("z8_access"w, roleTableAccess).length == 2);
    assert(z8_postgres_create_foreign_keys_sql("z8_access"w, roleFieldAccess).length == 2);
    assert(z8_postgres_create_foreign_keys_sql("z8_access"w, roleRequestAccess).length == 2);
    db.execute(`CREATE SCHEMA "z8_access"`);
    auto accessRoles = P.m_roles(); db.execute(z8_postgres_create_table_sql("z8_access"w, accessRoles));
    z8_postgres_ensure_null_record(db, "z8_access"w, accessRoles);
    z8_postgres_create_tables(db, "z8_access"w, [roleTableAccess, roleFieldAccess, roleRequestAccess, P.m_systemFields(), P.m_systemRequests(), P.m_systemTables()]);
    bool invalidRole;
    try { db.execute(`INSERT INTO "z8_access"."SystemRoleTableAccess" ("RecordId", "Role") VALUES ('00000000-0000-0000-0000-000000000061', '00000000-0000-0000-0000-000000000099')`); }
    catch (Z8PostgresException) { invalidRole = true; }
    assert(invalidRole);
    db.execute(`INSERT INTO "z8_access"."SystemRoles" ("RecordId", "Name") VALUES ('DC08CA72-C668-412F-91B7-022F1C82AC09', 'Admins')`);
    db.execute(`INSERT INTO "z8_access"."SystemTables" ("RecordId", "Name") VALUES ('00000000-0000-0000-0000-000000000062', 'Orders')`);
    db.execute(`INSERT INTO "z8_access"."SystemRoleTableAccess" ("RecordId", "Role", "Table") VALUES ('00000000-0000-0000-0000-000000000063', 'DC08CA72-C668-412F-91B7-022F1C82AC09', '00000000-0000-0000-0000-000000000062')`);
    auto accessBackend = new Z8PostgresDatabase(db, "z8_access"w); auto savedAccessBackend = z8_connection_set_current(accessBackend);
    assert(P.m_accessRoleName(roleTableAccess) == "Admins"w);
    db.execute(`INSERT INTO "z8_access"."SystemFields" ("RecordId", "Table") VALUES ('00000000-0000-0000-0000-000000000064', '00000000-0000-0000-0000-000000000062')`);
    db.execute(`INSERT INTO "z8_access"."SystemRoleFieldAccess" ("RecordId", "Role", "Field") VALUES ('00000000-0000-0000-0000-000000000065', 'DC08CA72-C668-412F-91B7-022F1C82AC09', '00000000-0000-0000-0000-000000000064')`);
    db.execute(`INSERT INTO "z8_access"."SystemRoles" ("RecordId", "Name") VALUES ('BE41CEB5-02DF-44EE-885F-B82DDEDCAA08', 'Guests')`);
    db.execute(`INSERT INTO "z8_access"."SystemTables" ("RecordId", "Name") VALUES ('00000000-0000-0000-0000-000000000066', 'Other')`);
    db.execute(`INSERT INTO "z8_access"."SystemFields" ("RecordId", "Table") VALUES ('00000000-0000-0000-0000-000000000067', '00000000-0000-0000-0000-000000000066')`);
    db.execute(`INSERT INTO "z8_access"."SystemRoleFieldAccess" ("RecordId", "Role", "Field", "Read", "Write") VALUES ('00000000-0000-0000-0000-000000000068', 'DC08CA72-C668-412F-91B7-022F1C82AC09', '00000000-0000-0000-0000-000000000067', 1, 1), ('00000000-0000-0000-0000-000000000069', 'BE41CEB5-02DF-44EE-885F-B82DDEDCAA08', '00000000-0000-0000-0000-000000000064', 1, 1)`);
    db.execute(`INSERT INTO "z8_access"."SystemRequests" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000071')`);
    db.execute(`INSERT INTO "z8_access"."SystemRoleRequestAccess" ("RecordId", "Role", "Request") VALUES ('00000000-0000-0000-0000-000000000070', 'DC08CA72-C668-412F-91B7-022F1C82AC09', '00000000-0000-0000-0000-000000000071')`);
    auto roleSessions = new Z8SessionManager();
    auto roleMember = new Z8UserData(); roleMember.id = z8_guid_create(333); roleMember.roles = [P.m_administratorRole()];
    auto roleAdmin = new Z8UserData(); roleAdmin.id = z8_guid_create(334); roleAdmin.roles = roleMember.roles; roleAdmin.administrator = true;
    roleSessions.create("other-tenant"w, roleMember, roleAdmin, "other"w);
    roleSessions.create("admin"w, roleAdmin, roleAdmin, "z8_access"w);
    auto roleRequest = new Z8ApplicationRequest(); roleRequest.roleChangeNotifier = roleSessions;
    roleRequest.session = new Z8ApplicationSession("admin"w, roleAdmin, roleAdmin);
    auto oldRoleRequest = z8_application_set_request(roleRequest);
    roleSessions.create("field"w, roleMember, roleAdmin, "z8_access"w);
    P.m_setFieldRead(roleFieldAccess, z8_guid_create(101), z8_optional_wrap(true));
    assert(roleSessions.getSession("field"w) is null);
    roleSessions.create("table"w, roleMember, roleAdmin, "z8_access"w);
    P.m_setTableRead(roleTableAccess, z8_guid_create(99), z8_optional_wrap(true));
    assert(roleSessions.getSession("table"w) is null);
    roleSessions.create("request"w, roleMember, roleAdmin, "z8_access"w);
    P.m_setRequestExecute(roleRequestAccess, z8_guid_create(112), z8_optional_wrap(true));
    assert(roleSessions.getSession("request"w) is null && roleSessions.getSession("other-tenant"w) !is null && roleSessions.getSession("admin"w) !is null);
    z8_application_set_request(oldRoleRequest);
    db.execute(`DELETE FROM "z8_access"."SystemRoleRequestAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000070'`);
    db.execute(`DELETE FROM "z8_access"."SystemRequests" WHERE "RecordId" = '00000000-0000-0000-0000-000000000071'`);
    auto accessId = z8_guid_create(101);
    P.m_setFieldWrite(roleFieldAccess, accessId, z8_optional_wrap(true));
    auto accessRow = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`);
    assert(accessRow.rows[0][0].text == "1" && accessRow.rows[0][1].text == "1");
    P.m_setFieldRead(roleFieldAccess, accessId, z8_optional_wrap(false));
    accessRow = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`);
    assert(accessRow.rows[0][0].text == "0" && accessRow.rows[0][1].text == "0");
    P.m_setFieldBoth(roleFieldAccess, accessId);
    accessRow = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`);
    assert(accessRow.rows[0][0].text == "0" && accessRow.rows[0][1].text == "0");
    auto skipAccessEvents = new Z8ApplicationRequest(); skipAccessEvents.setEventsLevel(Z8EventsLevel.none);
    auto previousAccessRequest = z8_application_set_request(skipAccessEvents);
    P.m_setFieldWrite(roleFieldAccess, accessId, z8_optional_wrap(true));
    z8_application_set_request(previousAccessRequest);
    accessRow = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`);
    assert(accessRow.rows[0][0].text == "0" && accessRow.rows[0][1].text == "1");
    string tableRights() { return db.execute(`SELECT "Read"::text || "Write"::text || "Create"::text || "Copy"::text || "Destroy"::text FROM "z8_access"."SystemRoleTableAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000063'`).rows[0][0].text; }
    string fieldRights() { return db.execute(`SELECT "Read"::text || "Write"::text FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`).rows[0][0].text; }
    auto tableAccessId = z8_guid_create(99);
    P.m_setTableWrite(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "11000" && fieldRights() == "11");
    P.m_setTableRead(roleTableAccess, tableAccessId, z8_optional_wrap(false)); assert(tableRights() == "00000" && fieldRights() == "00");
    P.m_setTableRead(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "10000" && fieldRights() == "10");
    P.m_setTableCreate(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "11100" && fieldRights() == "11");
    P.m_setTableCopy(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "11110" && fieldRights() == "11");
    P.m_setTableCreate(roleTableAccess, tableAccessId, z8_optional_wrap(false)); assert(tableRights() == "11000" && fieldRights() == "11");
    P.m_setTableCopy(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "11110" && fieldRights() == "11");
    P.m_setTableWrite(roleTableAccess, tableAccessId, z8_optional_wrap(false)); assert(tableRights() == "10000" && fieldRights() == "10");
    P.m_setTableDestroy(roleTableAccess, tableAccessId, z8_optional_wrap(true)); assert(tableRights() == "10001" && fieldRights() == "10");
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoleFieldAccess" WHERE "RecordId" IN ('00000000-0000-0000-0000-000000000068', '00000000-0000-0000-0000-000000000069') AND "Read" = 1 AND "Write" = 1`).rows[0][0].text == "2");
    db.beginTransaction(); P.m_setTableRead(roleTableAccess, tableAccessId, z8_optional_wrap(false));
    assert(tableRights() == "00000" && fieldRights() == "00"); db.rollback();
    assert(tableRights() == "10001" && fieldRights() == "10");
    db.execute(`UPDATE "z8_access"."SystemRoleTableAccess" SET "Read" = 0, "Write" = 0, "Create" = 0, "Copy" = 0, "Destroy" = 0 WHERE "RecordId" = '00000000-0000-0000-0000-000000000063'`);
    db.execute(`UPDATE "z8_access"."SystemRoleFieldAccess" SET "Read" = 0, "Write" = 0 WHERE "RecordId" = '00000000-0000-0000-0000-000000000065'`);
    previousAccessRequest = z8_application_set_request(skipAccessEvents);
    P.m_setTableWrite(P.m_roleTableAccess(), tableAccessId, z8_optional_wrap(true));
    z8_application_set_request(previousAccessRequest);
    assert(tableRights() == "01000" && fieldRights() == "00");
    auto roleRegistry = new Z8RuntimeRegistry(); roleRegistry.registerTable(P.m_make()); roleRegistry.registerTable(P.m_indexes());
    foreach (key; roleRegistry.tableKeys())
        db.execute(`INSERT INTO "z8_access"."SystemTables" ("RecordId", "Name") VALUES ($1::uuid, 'Registered')`, [Z8PostgresParameter.value(z8_guid_to_string(key).to!string)]);
    db.execute(`INSERT INTO "z8_access"."SystemRequests" ("RecordId", "Name") VALUES ('00000000-0000-0000-0000-00000000006A', 'Request')`);
    auto lifecycleBackend = new Z8PostgresDatabase(db, "z8_access"w, roleRegistry);
    z8_connection_set_current(lifecycleBackend);
    auto roleId = z8_guid_create(111);
    db.beginTransaction(); P.m_createRole(P.m_roles(), roleId);
    auto createdAccessCounts = db.execute(`SELECT (SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F'), (SELECT count(*) FROM "z8_access"."SystemRoleFieldAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F'), (SELECT count(*) FROM "z8_access"."SystemRoleRequestAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F')`);
    assert(createdAccessCounts.rows[0][0].text == "2" && createdAccessCounts.rows[0][1].text == "2" && createdAccessCounts.rows[0][2].text == "1");
    db.rollback();
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F'`).rows[0][0].text == "0");
    P.m_createRole(P.m_roles(), roleId);
    P.m_deleteRole(P.m_roles(), roleId);
    createdAccessCounts = db.execute(`SELECT (SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F'), (SELECT count(*) FROM "z8_access"."SystemRoleFieldAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F'), (SELECT count(*) FROM "z8_access"."SystemRoleRequestAccess" WHERE "Role" = '00000000-0000-0000-0000-00000000006F')`);
    assert(createdAccessCounts.rows[0][0].text == "0" && createdAccessCounts.rows[0][1].text == "0" && createdAccessCounts.rows[0][2].text == "0");
    P.m_createRole(P.m_roles(), roleId);
    roleMember.roles = [roleId];
    roleSessions.create("rename-role"w, roleMember, roleAdmin, "z8_access"w);
    oldRoleRequest = z8_application_set_request(roleRequest);
    P.m_renameRole(P.m_roles(), roleId);
    assert(roleSessions.getSession("rename-role"w) is null);
    roleSessions.create("delete-role"w, roleMember, roleAdmin, "z8_access"w);
    P.m_deleteRole(P.m_roles(), roleId);
    assert(roleSessions.getSession("delete-role"w) is null);
    z8_application_set_request(oldRoleRequest);
    auto missingRegistry = new Z8RuntimeRegistry(); missingRegistry.registerTable(P.m_geo());
    z8_connection_set_current(new Z8PostgresDatabase(db, "z8_access"w, missingRegistry));
    db.beginTransaction(); bool missingRegisteredTable;
    try { P.m_createRole(P.m_roles(), z8_guid_create(112)); } catch (Z8PostgresException) { missingRegisteredTable = true; }
    assert(missingRegisteredTable); db.rollback();
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoles" WHERE "RecordId" = '00000000-0000-0000-0000-000000000070'`).rows[0][0].text == "0");
    z8_connection_set_current(lifecycleBackend);
    previousAccessRequest = z8_application_set_request(skipAccessEvents);
    P.m_createRole(P.m_roles(), z8_guid_create(113));
    z8_application_set_request(previousAccessRequest);
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Role" = '00000000-0000-0000-0000-000000000071'`).rows[0][0].text == "0");
    P.m_deleteRole(P.m_roles(), z8_guid_create(113));
    db.execute(`UPDATE "z8_access"."SystemRoles" SET "Name" = 'Preserved admin', "Description" = convert_to('Keep', 'UTF8'), "Read" = 0, "Lock" = 0 WHERE "RecordId" = 'DC08CA72-C668-412F-91B7-022F1C82AC09'`);
    db.beginTransaction();
    z8_postgres_apply_static_records(db, "z8_access"w, P.m_roles(), roleRegistry);
    db.commit();
    auto retainedRole = db.execute(`SELECT "Name", convert_from("Description", 'UTF8'), "Read", "Lock" FROM "z8_access"."SystemRoles" WHERE "RecordId" = 'DC08CA72-C668-412F-91B7-022F1C82AC09'`);
    assert(retainedRole.rows[0][0].text == "Preserved admin" && retainedRole.rows[0][1].text == "Keep" && retainedRole.rows[0][2].text == "0" && retainedRole.rows[0][3].text == "3");
    auto builtInRoleAccess = db.execute(`SELECT (SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'), (SELECT count(*) FROM "z8_access"."SystemRoleFieldAccess" WHERE "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'), (SELECT count(*) FROM "z8_access"."SystemRoleRequestAccess" WHERE "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5')`);
    assert(builtInRoleAccess.rows[0][0].text == "2" && builtInRoleAccess.rows[0][1].text == "2" && builtInRoleAccess.rows[0][2].text == "1");
    auto registeredSample = P.m_make(); registeredSample.z8_set_attribute("displayName"w, "Пример"w);
    roleRegistry.registerTable(registeredSample); roleRegistry.registerTable(P.m_geo()); roleRegistry.registerRequest(registeredSample);
    z8_postgres_sync_registry(db, "z8_access"w, roleRegistry);
    auto sampleKey = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("Sample;--"w)).to!string);
    auto sampleMetadata = db.execute(`SELECT "Name", "Class", "Display Name", "Lock" FROM "z8_access"."SystemTables" WHERE "RecordId" = $1::uuid`, [sampleKey]);
    assert(sampleMetadata.rows[0][0].text == "Sample;--" && sampleMetadata.rows[0][1].text == "Sample" && sampleMetadata.rows[0][2].text == "Пример" && sampleMetadata.rows[0][3].text == "1");
    auto titleKey = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("Sample;--.Title"w)).to!string);
    auto titleMetadataRow = db.execute(`SELECT "Name", "Type", "Position", "Table"::text FROM "z8_access"."SystemFields" WHERE "RecordId" = $1::uuid`, [titleKey]);
    assert(titleMetadataRow.rows[0][0].text == "Title" && titleMetadataRow.rows[0][1].text == "string(30)" && titleMetadataRow.rows[0][2].text == "6" && z8_guid_literal(titleMetadataRow.rows[0][3].text) == z8_guid_create_name("Sample;--"w));
    auto geoKey = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("GeoSample"w)).to!string);
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoleTableAccess" WHERE "Table" = $1::uuid`, [geoKey]).rows[0][0].text == "3");
    auto userFieldRights = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "Field" = $1::uuid AND "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'`, [titleKey]);
    assert(userFieldRights.rows.length == 1 && userFieldRights.rows[0][0].text == "1" && userFieldRights.rows[0][1].text == "0");
    auto requestKey = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("Sample"w)).to!string);
    auto requestMetadata = db.execute(`SELECT "Name", "Class" FROM "z8_access"."SystemRequests" WHERE "RecordId" = $1::uuid`, [requestKey]);
    assert(requestMetadata.rows[0][0].text == "Пример" && requestMetadata.rows[0][1].text == "Sample");
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRoleRequestAccess" WHERE "Request" = $1::uuid`, [requestKey]).rows[0][0].text == "3");
    db.execute(`UPDATE "z8_access"."SystemRoleFieldAccess" SET "Read" = 0, "Write" = 1 WHERE "Field" = $1::uuid AND "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'`, [titleKey]);
    auto beforeFields = db.execute(`SELECT count(*) FROM "z8_access"."SystemFields"`).rows[0][0].text;
    z8_postgres_sync_registry(db, "z8_access"w, roleRegistry);
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemFields"`).rows[0][0].text == beforeFields);
    userFieldRights = db.execute(`SELECT "Read", "Write" FROM "z8_access"."SystemRoleFieldAccess" WHERE "Field" = $1::uuid AND "Role" = '421A8413-A8EC-4DAB-9235-9A5FF83341C5'`, [titleKey]);
    assert(userFieldRights.rows.length == 1 && userFieldRights.rows[0][0].text == "0" && userFieldRights.rows[0][1].text == "1");
    roleRegistry.registerRequest(P.m_geo());
    auto rolledBackRequest = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("GeoSample"w)).to!string);
    db.beginTransaction(); z8_postgres_sync_registry(db, "z8_access"w, roleRegistry);
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRequests" WHERE "RecordId" = $1::uuid`, [rolledBackRequest]).rows[0][0].text == "1");
    db.rollback();
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemRequests" WHERE "RecordId" = $1::uuid`, [rolledBackRequest]).rows[0][0].text == "0");
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemTables" WHERE "RecordId" = '00000000-0000-0000-0000-000000000066'`).rows[0][0].text == "1");
    auto newMetadataTable = P.m_systemTables(); roleRegistry.registerTable(newMetadataTable);
    auto newMetadataKey = Z8PostgresParameter.value(z8_guid_to_string(z8_guid_create_name("SystemTables"w)).to!string);
    db.execute(`ALTER TABLE "z8_access"."SystemRoleFieldAccess" ADD CONSTRAINT "reject_new" CHECK ("Read" = -1) NOT VALID`);
    bool metadataRolledBack;
    try { z8_postgres_sync_registry(db, "z8_access"w, roleRegistry); } catch (Z8PostgresException) { metadataRolledBack = true; }
    assert(metadataRolledBack && !db.inTransaction());
    assert(db.execute(`SELECT count(*) FROM "z8_access"."SystemTables" WHERE "RecordId" = $1::uuid`, [newMetadataKey]).rows[0][0].text == "0");
    db.execute(`ALTER TABLE "z8_access"."SystemRoleFieldAccess" DROP CONSTRAINT "reject_new"`);
    z8_connection_set_current(accessBackend);
    z8_connection_set_current(savedAccessBackend);
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
        workers = [subprocess.Popen([str(exe), connection, "worker"], env=environment, cwd=temp, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) for _ in range(4)]
        values = []
        for worker in workers:
            stdout, stderr = worker.communicate(timeout=30)
            if worker.returncode:
                raise SystemExit(f"Sequence worker failed ({worker.returncode}):\n{stdout}\n{stderr}")
            values.extend(map(int, stdout.splitlines()))
        assert sorted(values) == list(range(2, 122)), values
        workers = [subprocess.Popen([str(exe), connection, "worker_tx"], env=environment, cwd=temp, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) for _ in range(4)]
        values = []
        for worker in workers:
            stdout, stderr = worker.communicate(timeout=30)
            if worker.returncode:
                raise SystemExit(f"Transactional sequence worker failed ({worker.returncode}):\n{stdout}\n{stderr}")
            values.extend(map(int, stdout.splitlines()))
        assert sorted(values) == list(range(2, 82)), values
        workers = [subprocess.Popen([str(exe), connection, "metadata_worker"], env=environment, cwd=temp, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) for _ in range(3)]
        for worker in workers:
            stdout, stderr = worker.communicate(timeout=30)
            if worker.returncode:
                raise SystemExit(f"Metadata worker failed ({worker.returncode}):\n{stdout}\n{stderr}")
        check = subprocess.run([str(exe), connection, "metadata_count"], env=environment, cwd=temp, capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, check=True)
        assert check.stdout.strip() == "1 9 3 27", check.stdout
print("BL table schema generation, defaults and primary key verified in PostgreSQL")
