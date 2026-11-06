module z8.database.schema;

import std.conv : to;
import std.string : icmp;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresConnection, Z8PostgresException, Z8PostgresParameter;
import z8.database.connection : Z8PostgresDatabase;

// Serialize schema creation, additive migration and metadata sync per schema.
// PostgreSQL releases transaction-level advisory locks on commit or rollback.
package void z8_postgres_lock_schema(Z8PostgresConnection db, wstring schema) {
    if (db is null || db.isClosed() || !db.inTransaction()) throw new Z8PostgresException("schema lock requires a transaction");
    quoteIdentifier(schema);
    db.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext($1), pg_catalog.hashtext($2))",
        [Z8PostgresParameter.value("z8.schema"), Z8PostgresParameter.value(schema.to!string)]);
}

package string fieldType(Z8Object field) {
    switch (z8_field_type_id(field)) {
        case "int"w: case "date"w: case "datetime"w: case "datespan"w: return "bigint";
        case "boolean"w: return "smallint";
        case "float"w: return "numeric";
        case "string"w: return "character varying";
        case "guid"w: return "uuid";
        case "binary"w: case "text"w: case "file"w: case "attachments"w: return "bytea";
        case "geometry"w: return "geometry(Geometry, " ~ z8_optional_require(z8_field_srs(field)).to!string ~ ")";
        default: throw new Z8PostgresException("unsupported PostgreSQL schema field type");
    }
}
package string fieldDefault(Z8Object field) {
    auto kind = z8_field_type_id(field);
    // Z8 formats byte-backed defaults as SQL NULL in the PostgreSQL dialect.
    if (kind == "binary"w || kind == "text"w || kind == "file"w || kind == "attachments"w) return "NULL";
    auto value = z8_field_default_value(field);
    if (value is null) return "NULL";
    switch (kind) {
        case "int"w: return z8_sql_int_format(z8_sql_int_const(value.integerValue), Z8SqlVendor.Postgres).to!string;
        case "boolean"w: return z8_sql_bool_format(z8_sql_bool_const(value.booleanValue), false, Z8SqlVendor.Postgres).to!string;
        case "float"w: return z8_sql_decimal_format(z8_sql_decimal_const(value.decimalValue), Z8SqlVendor.Postgres).to!string;
        case "string"w: return z8_sql_string_format(z8_sql_string_const(value.textValue), Z8SqlVendor.Postgres).to!string;
        case "guid"w: return z8_sql_guid_format(z8_sql_guid_const(value.guidValue), Z8SqlVendor.Postgres).to!string;
        case "date"w: case "datetime"w: return z8_date_ticks(value.dateValue).to!string;
        case "datespan"w: return z8_datespan_milliseconds(value.datespanValue).to!string;
        case "geometry"w:
            auto sql = z8_sql_geometry_format(z8_sql_geometry_const(value.geometryValue), Z8SqlVendor.Postgres);
            return sql is null ? "NULL" : sql.to!string;
        default: throw new Z8PostgresException("unsupported PostgreSQL schema default");
    }
}
// Return DDL without executing or modifying existing database objects.
string z8_postgres_create_table_sql(wstring schema, Z8Object table) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    auto fields = z8_query_declared_fields(table, true);
    auto key = z8_query_primary_key(table);
    if (key is null) throw new Z8PostgresException("PostgreSQL table has no primary key");
    string sql = "CREATE TABLE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~ " (";
    wstring[] names;
    bool foundKey;
    foreach (index, field; fields) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
        foreach (existing; names) if (existing == name) throw new Z8PostgresException("duplicate PostgreSQL column name");
        names ~= name;
        if (index) sql ~= ", ";
        sql ~= quoteIdentifier(name) ~ " " ~ fieldType(field) ~ " DEFAULT " ~ fieldDefault(field);
        if (field is key || z8_native_is_instance("org.zenframework.z8.server.base.table.value.GuidField"w, field)) sql ~= " NOT NULL";
        if (field is key) foundKey = true;
    }
    if (!foundKey) throw new Z8PostgresException("PostgreSQL primary key is not a table field");
    auto keyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, key);
    return sql ~ ", PRIMARY KEY (" ~ quoteIdentifier(keyName) ~ "))";
}

// Indexes are separate so callers can create records and extensions first.
string[] z8_postgres_create_indexes_sql(wstring schema, Z8Object table) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    string[] result;
    foreach (field; z8_query_declared_fields(table, true)) {
        auto options = z8_field_index_options(field);
        auto kind = z8_field_type_id(field);
        if (!options.indexed && !options.unique && !(kind == "string"w && options.trigram)) continue;
        auto fieldName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
        auto indexName = (options.unique ? "Unq" : "Idx") ~ result.length.to!string ~ tableName.to!string;
        if (options.unique && (kind == "geometry"w || (kind == "string"w && options.trigram)))
            throw new Z8PostgresException("PostgreSQL GIN and GiST indexes cannot be unique");
        string sql = "CREATE " ~ (options.unique ? "UNIQUE " : "") ~ "INDEX " ~
            quoteIdentifier(indexName.to!wstring) ~ " ON " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~ " ";
        if (kind == "geometry"w) sql ~= "USING gist ";
        if (kind == "string"w && options.trigram) sql ~= "USING gin ";
        auto expression = quoteIdentifier(fieldName);
        if (kind == "string"w && options.caseInsensitive) expression = "LOWER(" ~ expression ~ ")";
        if (kind == "string"w && options.trigram) expression ~= " gin_trgm_ops";
        result ~= sql ~ "(" ~ expression ~ ")";
    }
    return result;
}

package Z8Object foreignKeyTarget(Z8Object table, Z8Object field) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.value.Link"w, field)) return null;
    auto enabled = field.z8_get_attribute("foreignKey"w);
    if (enabled !is null && icmp(enabled.to!string, "true") != 0) return null;
    auto target = z8_link_query(field);
    auto parent = field.z8_get_attribute("parentKey"w);
    if (target is null && parent !is null && icmp(parent.to!string, "false") != 0) target = table;
    if (target is null || !z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, target))
        throw new Z8PostgresException("foreign key Link target is not a Table");
    return target;
}
// Targets are in the same schema, as with the PostgreSQL query executor.
string[] z8_postgres_create_foreign_keys_sql(wstring schema, Z8Object table) {
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    string[] result;
    foreach (field; z8_query_declared_fields(table, true)) {
        auto target = foreignKeyTarget(table, field);
        if (target is null) continue;
        auto targetKey = z8_query_primary_key(target);
        if (targetKey is null) throw new Z8PostgresException("foreign key target has no primary key");
        auto targetName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, target);
        auto fieldName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field);
        auto targetKeyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, targetKey);
        auto name = ("FK" ~ result.length.to!string ~ "_" ~ tableName.to!string).to!wstring;
        result ~= "ALTER TABLE " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~
            " ADD CONSTRAINT " ~ quoteIdentifier(name) ~ " FOREIGN KEY (" ~ quoteIdentifier(fieldName) ~
            ") REFERENCES " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(targetName) ~ " (" ~ quoteIdentifier(targetKeyName) ~ ")";
    }
    return result;
}

// Like TableGenerator.createNullRecord, preserve an existing row and invoke
// Table.create for a missing one, including the BL lifecycle hooks.
bool z8_postgres_ensure_null_record(Z8PostgresConnection connection, wstring schema, Z8Object table) {
    if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto key = z8_query_primary_key(table);
    if (key is null) throw new Z8PostgresException("PostgreSQL table has no primary key");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    auto keyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, key);
    auto sql = "SELECT 1 FROM " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~
        " WHERE " ~ quoteIdentifier(keyName) ~ " = '00000000-0000-0000-0000-000000000000'::uuid";
    if (connection.execute(sql).rows.length) return false;
    auto backend = new Z8PostgresDatabase(connection, schema);
    auto previousExecutor = z8_query_swap_executor(table, backend.queryExecutor(table));
    auto previousConnection = z8_connection_set_current(backend);
    scope(exit) {
        z8_query_set_executor(table, previousExecutor);
        z8_connection_set_current(previousConnection);
    }
    z8_native_call!Z8Guid("org.zenframework.z8.server.base.query.Query.m_create"w, table, z8_guid_zero());
    return true;
}

// Apply declared records using the same create/update events as TableGenerator.
// Roles require the application registry and initialized access tables.
void z8_postgres_apply_static_records(Z8PostgresConnection connection, wstring schema, Z8Object table, Z8RuntimeRegistry registry = null) {
    if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (!z8_native_is_instance("org.zenframework.z8.server.base.table.Table"w, z8_nonnull(table)))
        throw new Z8PostgresException("PostgreSQL schema requires a Table");
    auto users = z8_native_is_instance("org.zenframework.z8.server.base.table.system.Users"w, table);
    auto roles = z8_native_is_instance("org.zenframework.z8.server.base.table.system.Roles"w, table);
    if (roles && registry is null) throw new Z8PostgresException("static role records require an application registry");
    auto key = z8_query_primary_key(table);
    if (key is null) throw new Z8PostgresException("PostgreSQL table has no primary key");
    auto tableName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
    auto keyName = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, key);
    auto sql = "SELECT 1 FROM " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(tableName) ~
        " WHERE " ~ quoteIdentifier(keyName) ~ " = $1::uuid";
    z8_initialize_static_records(table);
    auto records = table.z8_static_records();
    auto fields = z8_query_declared_fields(table, true);
    foreach (record; records) {
        if (record.key is null) throw new Z8PostgresException("static record has no GUID");
        foreach (item; record.values) {
            bool found;
            foreach (field; fields) if (item.field is field && field !is key) { found = true; break; }
            if (!found) throw new Z8PostgresException("static record field is not a table data field");
        }
    }
    auto backend = new Z8PostgresDatabase(connection, schema, registry);
    auto previousExecutor = z8_query_swap_executor(table, backend.queryExecutor(table));
    auto previousConnection = z8_connection_set_current(backend);
    scope(exit) {
        z8_query_set_executor(table, previousExecutor);
        z8_connection_set_current(previousConnection);
    }
    foreach (record; records) {
        auto exists = connection.execute(sql, [Z8PostgresParameter.value(z8_guid_to_string(record.key).to!string)]).rows.length != 0;
        auto protectedUser = users && exists && (record.key == z8_guid_create(1) || record.key == z8_guid_create(2));
        auto protectedRole = roles && exists && (record.key == z8_guid_literal("DC08CA72-C668-412F-91B7-022F1C82AC09") ||
            record.key == z8_guid_literal("421A8413-A8EC-4DAB-9235-9A5FF83341C5") || record.key == z8_guid_literal("BE41CEB5-02DF-44EE-885F-B82DDEDCAA08"));
        foreach (item; record.values) {
            auto index = item.field.z8_index();
            if (protectedUser && (index == "name"w || index == "password"w || index == "description"w)) continue;
            if (protectedRole && (index == "name"w || index == "description"w || index == "read"w || index == "write"w ||
                index == "create"w || index == "copy"w || index == "destroy"w || index == "execute"w)) continue;
            z8_field_set(item.field, item.value);
        }
        if (exists)
            z8_native_call!(Z8Optional!long)("org.zenframework.z8.server.base.query.Query.m_update"w, table, record.key);
        else
            z8_native_call!Z8Guid("org.zenframework.z8.server.base.query.Query.m_create"w, table, record.key);
    }
}

// Create a new set of tables atomically. Existing schemas are not migrated.
// Each phase runs for all tables before foreign keys are installed, permitting
// mutually referencing tables and their zero-GUID records.
void z8_postgres_create_tables(Z8PostgresConnection connection, wstring schema, Z8Object[] tables) {
    if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (connection.inTransaction()) throw new Z8PostgresException("schema creation requires its own transaction");
    string[] definitions, indexes, foreignKeys;
    wstring[] names;
    foreach (table; tables) {
        if (z8_native_is_instance("org.zenframework.z8.server.base.table.system.Roles"w, table))
            throw new Z8PostgresException("static role records require access-table lifecycle handling");
        definitions ~= z8_postgres_create_table_sql(schema, table);
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, table);
        foreach (existing; names) if (existing == name) throw new Z8PostgresException("duplicate PostgreSQL table name");
        names ~= name;
        indexes ~= z8_postgres_create_indexes_sql(schema, table);
        foreignKeys ~= z8_postgres_create_foreign_keys_sql(schema, table);
    }
    connection.beginTransaction();
    try {
        z8_postgres_lock_schema(connection, schema);
        foreach (sql; definitions) connection.execute(sql);
        foreach (table; tables) z8_postgres_ensure_null_record(connection, schema, table);
        foreach (table; tables) z8_postgres_apply_static_records(connection, schema, table);
        foreach (sql; indexes) connection.execute(sql);
        foreach (sql; foreignKeys) connection.execute(sql);
        connection.commit();
    } catch (Throwable failure) {
        try { connection.rollback(); } catch (Throwable ignored) { }
        throw failure;
    }
}
