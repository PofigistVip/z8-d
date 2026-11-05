module z8.database.schema;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres : Z8PostgresException;

private string fieldType(Z8Object field) {
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
private string fieldDefault(Z8Object field) {
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
