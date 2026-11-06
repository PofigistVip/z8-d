module z8.database.migration;

import std.conv : to;
import std.string : startsWith;
import z8.runtime;
import z8.database.catalog;
import z8.database.compare;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresException;
import z8.database.schema : fieldType, fieldDefault, foreignKeyTarget;

// Plan additive changes only; never execute them or change existing columns.
// The caller must separately handle indexes, foreign keys and other differences.
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

// Plan only supported, absent single-column indexes; expression indexes are
// reported by z8_postgres_compare_indexes and left for separate handling.
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
        if (expected.operatorClass !is null) expression ~= " " ~ expected.operatorClass;
        result ~= "CREATE " ~ (expected.unique ? "UNIQUE " : "") ~ "INDEX " ~ quoteIdentifier(name.to!wstring) ~
            " ON " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~ " USING " ~ expected.method ~ " (" ~ expression ~ ")";
    }
    return result;
}
