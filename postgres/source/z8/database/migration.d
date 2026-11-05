module z8.database.migration;

import std.conv : to;
import std.string : startsWith;
import z8.runtime;
import z8.database.catalog;
import z8.database.compare;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresException;
import z8.database.schema : fieldType, fieldDefault;

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
