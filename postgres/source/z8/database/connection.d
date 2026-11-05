module z8.database.connection;

import std.conv : to;
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8.database.plan : quoteIdentifier;

// Adapter for the request-local BL Connection and Query.setConnection APIs.
class Z8PostgresDatabase : IZ8DatabaseConnection {
    private Z8PostgresConnection connection;
    private wstring schema;
    this(Z8PostgresConnection connection, wstring schema) {
        if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
        this.connection = connection; this.schema = schema.idup;
    }
    void beginTransaction() { connection.beginTransaction(); }
    void commit() { connection.commit(); }
    void rollback() { connection.rollback(); }
    void execute(wstring sql) { connection.execute(sql.to!string); }
    void call(wstring name, Z8Array!Z8Primary values) {
        string sql = "CALL " ~ quoteIdentifier(schema) ~ "." ~ quoteIdentifier(name) ~ "(";
        Z8PostgresParameter[] parameters;
        foreach (index; 0 .. z8_nonnull(values).z8_size()) {
            auto value = values.z8_get(index);
            if (index) sql ~= ", ";
            auto marker = "$" ~ (index + 1).to!string;
            string text;
            if (value is null) {
                sql ~= marker; parameters ~= Z8PostgresParameter.nullValue(); continue;
            }
            final switch (value.kind) {
                case Z8PrimaryKind.integer: sql ~= marker ~ "::bigint"; text = value.integerValue.to!string; break;
                case Z8PrimaryKind.boolean: sql ~= marker ~ "::integer"; text = value.booleanValue ? "1" : "0"; break;
                case Z8PrimaryKind.decimal: sql ~= marker ~ "::numeric"; text = value.decimalValue.z8_string().to!string; break;
                case Z8PrimaryKind.text: sql ~= marker ~ "::text"; text = value.textValue.to!string; break;
                case Z8PrimaryKind.guid: sql ~= marker ~ "::uuid"; text = z8_guid_to_string(value.guidValue).to!string; break;
                case Z8PrimaryKind.date: sql ~= marker ~ "::bigint"; text = z8_date_ticks(value.dateValue).to!string; break;
                case Z8PrimaryKind.datespan: sql ~= marker ~ "::bigint"; text = z8_datespan_milliseconds(value.datespanValue).to!string; break;
                case Z8PrimaryKind.binary: sql ~= "decode(" ~ marker ~ "::text, 'hex')"; text = encodeBinary(value.binaryValue); break;
                case Z8PrimaryKind.geometry:
                    sql ~= "decode(" ~ marker ~ "::text, 'hex')"; text = z8_geometry_to_string(value.geometryValue).to!string;
                    if (!text.length) { parameters ~= Z8PostgresParameter.nullValue(); continue; }
                    break;
                case Z8PrimaryKind.file: case Z8PrimaryKind.user:
                    throw new Z8PostgresException("unsupported PostgreSQL procedure parameter type");
            }
            parameters ~= Z8PostgresParameter.value(text);
        }
        connection.execute(sql ~ ")", parameters);
    }
    // libpq executes immediately, so there is no pending JDBC batch to flush.
    void flush() { if (connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed"); }
    IZ8QueryExecutor queryExecutor(Z8Object query) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, query);
        return new Z8PostgresQueryExecutor(connection, schema, name);
    }
}
