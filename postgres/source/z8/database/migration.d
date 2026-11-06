module z8.database.migration;

import std.conv : to;
import std.string : startsWith;
import z8.runtime;
import z8.database.catalog;
import z8.database.compare;
import z8.database.metadata : z8_postgres_sync_registry;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresConnection, Z8PostgresException;
import z8.database.schema : fieldType, fieldDefault, foreignKeyTarget, z8_postgres_create_table_sql,
    z8_postgres_ensure_null_record, z8_postgres_apply_static_records, z8_postgres_lock_schema;

// Plan missing columns without executing them or changing existing columns.
string[] z8_postgres_plan_add_columns(wstring schema, Z8Object table, Z8PostgresTableDescription actual) {
    if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
    if (actual is null) throw new Z8PostgresException("cannot add columns to a missing PostgreSQL table");
    if (schema.to!string != actual.schema && !(schema == "pg_temp"w && actual.schema.startsWith("pg_temp_")))
        throw new Z8PostgresException("PostgreSQL table description does not match schema");
    auto differences = z8_postgres_compare_table(table, actual);
    auto key = z8_query_primary_key(table);
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    string[] result;
    foreach (field; z8_query_declared_fields(table, true)) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
        bool missing;
        foreach (difference; differences)
            if (difference.kind == Z8SchemaDifferenceKind.missingColumn && difference.column == name.to!string) { missing = true; break; }
        if (!missing) continue;
        if (field is key) throw new Z8PostgresException("cannot add a missing primary key as an ordinary column");
        auto sql = "ALTER TABLE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~
            " ADD COLUMN " ~ quoteIdentifier(name) ~ " " ~ fieldType(field) ~ " DEFAULT " ~ fieldDefault(field);
        if (z8_native_is_instance("org.zenframework.z8.server.base.table.value.GuidField"w, field)) sql ~= " NOT NULL";
        result ~= sql;
    }
    return result;
}

// Add missing single-column BL foreign keys without modifying existing keys.
// Conflicting constraints are reported rather than silently combined.
string[] z8_postgres_plan_add_foreign_keys(wstring schema, Z8Object table, Z8PostgresTableDescription actual) {
    if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
    if (actual is null) throw new Z8PostgresException("cannot add foreign keys to a missing PostgreSQL table");
    if (schema.to!string != actual.schema && !(schema == "pg_temp"w && actual.schema.startsWith("pg_temp_")))
        throw new Z8PostgresException("PostgreSQL table description does not match schema");
    auto differences = z8_postgres_compare_table(table, actual);
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    auto names = actual.constraintNames.dup;
    string[] result;
    foreach (field; z8_query_declared_fields(table, true)) {
        auto target = foreignKeyTarget(table, field);
        if (target is null) continue;
        auto fieldName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
        bool missing;
        foreach (difference; differences)
            if (difference.kind == Z8SchemaDifferenceKind.missingForeignKey && difference.column == fieldName.to!string) { missing = true; break; }
        if (!missing) continue;
        bool exists;
        foreach (column; actual.columns) if (column.name == fieldName.to!string) { exists = true; break; }
        if (!exists) throw new Z8PostgresException("foreign key source column is missing");
        foreach (key; actual.foreignKeys) foreach (column; key.columns)
            if (column == fieldName.to!string) throw new Z8PostgresException("conflicting foreign key on source column");
        auto targetKey = z8_query_primary_key(target);
        if (targetKey is null) throw new Z8PostgresException("foreign key target has no primary key");
        auto targetName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, target);
        auto targetKeyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, targetKey);
        size_t suffix; string name;
        while (true) {
            name = "z8_fk_" ~ suffix.to!string; ++suffix;
            bool taken; foreach (existing; names) if (existing == name) { taken = true; break; }
            if (!taken) break;
        }
        names ~= name;
        result ~= "ALTER TABLE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~
            " ADD CONSTRAINT " ~ quoteIdentifier(name.to!wstring) ~ " FOREIGN KEY (" ~ quoteIdentifier(fieldName) ~
            ") REFERENCES " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(targetName) ~ " (" ~ quoteIdentifier(targetKeyName) ~ ")";
    }
    return result;
}

// Plan absent single-column indexes, including the standard lower(...) expression.
string[] z8_postgres_plan_add_indexes(wstring schema, Z8Object table, Z8PostgresTableDescription actual) {
    if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
    if (actual is null) throw new Z8PostgresException("cannot add indexes to a missing PostgreSQL table");
    if (schema.to!string != actual.schema && !(schema == "pg_temp"w && actual.schema.startsWith("pg_temp_")))
        throw new Z8PostgresException("PostgreSQL table description does not match schema");
    auto indexDifferences = z8_postgres_compare_indexes(table, actual);
    auto tableDifferences = z8_postgres_compare_table(table, actual);
    auto names = actual.schemaIndexNames.dup;
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    string[] result;
    foreach (expected; z8_postgres_expected_indexes(table)) {
        bool missing;
        foreach (difference; indexDifferences)
            if (difference.kind == Z8SchemaIndexDifferenceKind.missingIndex && difference.column == expected.column) { missing = true; break; }
        if (!missing) continue;
        foreach (difference; tableDifferences)
            if (difference.column == expected.column && (difference.kind == Z8SchemaDifferenceKind.missingColumn || difference.kind == Z8SchemaDifferenceKind.columnType))
                throw new Z8PostgresException("index source column is missing or has an incompatible type");
        size_t suffix; string name;
        while (true) {
            name = "z8_idx_" ~ suffix.to!string; ++suffix;
            bool taken; foreach (existing; names) if (existing == name) { taken = true; break; }
            if (!taken) break;
        }
        names ~= name;
        auto expression = quoteIdentifier(expected.column.to!wstring);
        if (expected.lowerExpression) expression = "pg_catalog.lower(" ~ expression ~ ")";
        if (expected.operatorClass !is null) expression ~= " " ~ expected.operatorClass;
        result ~= "CREATE " ~ (expected.unique ? "UNIQUE " : "") ~ "INDEX " ~ quoteIdentifier(name.to!wstring) ~
            " ON " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~ " USING " ~ expected.method ~ " (" ~ expression ~ ")";
    }
    return result;
}

// These PostgreSQL conversions preserve all existing values. More complex
// conversions still require an explicit migration rather than an implicit cast.
private bool safeWidening(Z8SchemaDifference difference) {
    import std.algorithm.searching : startsWith;
    if (difference.kind != Z8SchemaDifferenceKind.columnType) return false;
    if (difference.expected == "bigint" && (difference.actual == "integer" || difference.actual == "smallint")) return true;
    if (difference.expected != "character varying") return false;
    if (difference.actual == "text") return true;
    enum prefix = "character varying(";
    if (!difference.actual.startsWith(prefix) || difference.actual.length <= prefix.length + 1 || difference.actual[$ - 1] != ')') return false;
    foreach (ch; difference.actual[prefix.length .. $ - 1]) if (ch < '0' || ch > '9') return false;
    return true;
}
private string[] applyAdditiveSchema(Z8PostgresConnection db, wstring schema, Z8Object[] tables,
                                      bool createMissing, Z8RuntimeRegistry registry, bool syncRegistry) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (db.inTransaction()) throw new Z8PostgresException("additive migration requires its own transaction");
    quoteIdentifier(schema);
    wstring[] names;
    foreach (table; tables) {
        if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
            throw new Z8PostgresException("PostgreSQL schema requires a Table");
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
        quoteIdentifier(name);
        foreach (existing; names) if (existing == name) throw new Z8PostgresException("duplicate PostgreSQL table name");
        names ~= name;
    }
    db.beginTransaction();
    try {
        z8_postgres_lock_schema(db, schema);
        string[] applied;
        Z8Object[] created;
        foreach (index, table; tables) {
            if (z8_postgres_describe_table(db, schema, names[index]) !is null) continue;
            if (!createMissing) throw new Z8PostgresException("additive migration requires existing tables");
            auto sql = z8_postgres_create_table_sql(schema, table);
            db.execute(sql); applied ~= sql; created ~= table;
        }
        // Reject incompatible tables before altering any existing columns.
        // Full registry reconciliation also widens a small set of lossless types.
        string[] widenings;
        foreach (index, table; tables) {
            auto actual = z8_postgres_describe_table(db, schema, names[index]);
            foreach (difference; z8_postgres_compare_table(table, actual)) {
                if (syncRegistry && safeWidening(difference)) {
                    widenings ~= "ALTER TABLE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(names[index]) ~
                        " ALTER COLUMN " ~ quoteIdentifier(difference.column.to!wstring) ~ " TYPE " ~ difference.expected;
                    continue;
                }
                if (difference.kind == Z8SchemaDifferenceKind.columnType || difference.kind == Z8SchemaDifferenceKind.nullability ||
                    difference.kind == Z8SchemaDifferenceKind.primaryKey)
                    throw new Z8PostgresException("additive migration found an incompatible existing table");
            }
        }
        foreach (sql; widenings) { db.execute(sql); applied ~= sql; }
        // Re-read catalog state between stages, including index names used by
        // other tables in this same migration.
        foreach (index, table; tables) {
            auto actual = z8_postgres_describe_table(db, schema, names[index]);
            foreach (sql; z8_postgres_plan_add_columns(schema, table, actual)) { db.execute(sql); applied ~= sql; }
        }
        // A complete registry reconciliation refreshes records for every table,
        // as TableGenerator does, including tables whose schema did not change.
        // The lower-level additive APIs seed only newly created tables.
        auto recordsTables = syncRegistry ? tables : created;
        foreach (table; recordsTables) z8_postgres_ensure_null_record(db, schema, table);
        foreach (table; recordsTables) z8_postgres_apply_static_records(db, schema, table, registry);
        if (syncRegistry) z8_postgres_sync_registry(db, schema, registry);
        foreach (index, table; tables) {
            auto actual = z8_postgres_describe_table(db, schema, names[index]);
            foreach (sql; z8_postgres_plan_add_indexes(schema, table, actual)) { db.execute(sql); applied ~= sql; }
        }
        foreach (index, table; tables) {
            auto actual = z8_postgres_describe_table(db, schema, names[index]);
            foreach (sql; z8_postgres_plan_add_foreign_keys(schema, table, actual)) { db.execute(sql); applied ~= sql; }
        }
        db.commit(); return applied;
    } catch (Throwable failure) {
        try { if (db.inTransaction()) db.rollback(); } catch (Throwable ignored) { }
        throw failure;
    }
}

// Apply only additive changes to existing tables. Statements are returned
// after a successful transaction; incompatible schemas cause a full rollback.
string[] z8_postgres_apply_additive_migration(Z8PostgresConnection db, wstring schema, Z8Object[] tables) {
    return applyAdditiveSchema(db, schema, tables, false, null, false);
}

// Also create missing tables and seed their null/static records. Roles require
// the same application registry and access tables as ordinary bootstrap.
string[] z8_postgres_ensure_additive_schema(Z8PostgresConnection db, wstring schema, Z8Object[] tables, Z8RuntimeRegistry registry = null) {
    return applyAdditiveSchema(db, schema, tables, true, registry, false);
}

package string[] z8_postgres_reconcile_schema(Z8PostgresConnection db, wstring schema, Z8Object[] tables, Z8RuntimeRegistry registry) {
    if (registry is null) throw new Z8PostgresException("application registry is required");
    return applyAdditiveSchema(db, schema, tables, true, registry, true);
}
