module z8.database.connection;

import std.conv : to;
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8.database.plan : quoteIdentifier;

// Adapter for the request-local BL Connection and Query.setConnection APIs.
class Z8PostgresDatabase : IZ8DatabaseConnection, IZ8SequenceConnection, IZ8BackgroundDatabaseConnection {
    private Z8PostgresConnection connection;
    private wstring schema;
    private Z8RuntimeRegistry registry;
    this(Z8PostgresConnection connection, wstring schema, Z8RuntimeRegistry registry = null) {
        if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
        this.connection = connection; this.schema = schema.idup; this.registry = registry;
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
    IZ8DatabaseConnection openBackgroundConnection() { return new Z8PostgresDatabase(connection.openSibling(), schema, registry); }
    void closeBackgroundConnection() { connection.close(); }
    long nextSequence(wstring key, long increment, long defaultValue) {
        key = z8_string_required(key);
        synchronized (connection) {
            auto table = quoteIdentifier(schema) ~ `."SystemSequences"`;
            auto keyParameter = Z8PostgresParameter.value(key.to!string);
            auto rows = connection.execute("SELECT \"RecordId\"::text FROM " ~ table ~
                ` WHERE "Key" = $1::text AND "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid LIMIT 2`, [keyParameter]);
            if (rows.rows.length > 1) throw new Z8PostgresException("multiple records for a sequence key");
            auto id = rows.rows.length ? rows.rows[0][0].text : z8_guid_to_string(z8_guid_create_name(key)).to!string;
            auto idParameter = Z8PostgresParameter.value(id);
            auto initial = Z8PostgresParameter.value(defaultValue.to!string);
            auto step = Z8PostgresParameter.value(increment.to!string);
            Z8PostgresResult result;
            if (!rows.rows.length && connection.inTransaction()) {
                auto sibling = connection.openSibling();
                scope(exit) sibling.close();
                sibling.execute("INSERT INTO " ~ table ~ ` ("RecordId", "Key", "Value") VALUES ($1::uuid, $2::text, $3::bigint) ON CONFLICT ("RecordId") DO NOTHING`,
                    [idParameter, keyParameter, initial]);
            }
            if (!rows.rows.length && !connection.inTransaction()) {
                result = connection.execute("INSERT INTO " ~ table ~ ` AS seq ("RecordId", "Key", "Value") VALUES ($1::uuid, $2::text, $3::bigint + $4::bigint)
                    ON CONFLICT ("RecordId") DO UPDATE SET "Value" = seq."Value" + $4::bigint WHERE seq."Key" = $2::text RETURNING "Value"`,
                    [idParameter, keyParameter, initial, step]);
            } else {
                result = connection.execute("UPDATE " ~ table ~ ` SET "Value" = "Value" + $3::bigint WHERE "RecordId" = $1::uuid AND "Key" = $2::text RETURNING "Value"`,
                    [idParameter, keyParameter, step]);
            }
            if (result.rows.length != 1 || result.rows[0][0].isNull) throw new Z8PostgresException("sequence record is missing or has a conflicting key");
            return result.rows[0][0].text.to!long;
        }
    }
    IZ8QueryExecutor queryExecutor(Z8Object query) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, query);
        return new Z8PostgresQueryExecutor(connection, schema, name, registry);
    }
}
