module z8.database.connection;

import std.conv : to;
import z8.runtime;
import z8.database.postgres;
import z8.database.query;
import z8.database.privileges : z8_postgres_read_user;
import z8.database.plan : quoteIdentifier;

// Adapter for the request-local BL Connection and Query.setConnection APIs.
class Z8PostgresDatabase : IZ8DatabaseConnection, IZ8RawSqlConnection, IZ8SystemInstallation, IZ8SequenceConnection, IZ8BackgroundDatabaseConnection, IZ8JobUserResolver, IZ8UserPasswordVerifier, IZ8UserProfileReader, IZ8DatabaseSchema {
    private Z8PostgresConnection connection;
    private wstring schema;
    private Z8RuntimeRegistry registry;
    private bool systemInstalled;
    this(Z8PostgresConnection connection, wstring schema, Z8RuntimeRegistry registry = null) {
        if (connection is null || connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (schema is null || !schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
        this.connection = connection; this.schema = schema.idup; this.registry = registry;
    }
    void beginTransaction() { connection.beginTransaction(); }
    wstring databaseSchema() { return schema; }
    bool isSystemInstalled() {
        synchronized (connection) {
            if (systemInstalled) return true;
            auto result = connection.execute(`SELECT 1 FROM information_schema.tables WHERE table_schema =
                CASE WHEN $1::text = 'pg_temp' THEN pg_my_temp_schema()::regnamespace::text ELSE $1::text END
                AND table_name = 'SystemUsers' LIMIT 1`, [Z8PostgresParameter.value(schema.to!string)]);
            return systemInstalled = result.rows.length != 0;
        }
    }
    void commit() { connection.commit(); }
    void rollback() { connection.rollback(); }
    void execute(wstring sql) { connection.execute(sql.to!string); }
    IZ8RawSqlCursor openSql(wstring sql) {
        auto result = connection.execute(z8_string_required(sql).to!string);
        if (!result.columns.length) throw new Z8PostgresException("SQL cursor requires a result set");
        return new Z8PostgresRawCursor(result);
    }
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
    Z8UserData resolveJobUser(Z8Guid id) { return z8_postgres_read_user(connection, schema, id, registry); }
    bool readUserProfile(Z8Guid id, out Z8UserProfile profile) {
        auto rows = connection.execute(`SELECT "Email", convert_from("Settings", 'UTF8'), "Change Password" FROM ` ~
            quoteIdentifier(schema) ~ `."SystemUsers" WHERE "RecordId" = $1::uuid`,
            [Z8PostgresParameter.value(z8_guid_to_string(z8_nonnull(id)).to!string)]);
        if (!rows.rows.length) return false;
        if (rows.rows.length != 1) throw new Z8PostgresException("multiple users with the same id");
        auto row = rows.rows[0];
        profile.email = row[0].isNull ? ""w : row[0].text.to!wstring;
        profile.settings = row[1].isNull ? ""w : row[1].text.to!wstring;
        profile.changePassword = !row[2].isNull && row[2].text.to!int != 0;
        return true;
    }
    bool lockMatchingPassword(Z8Guid id, wstring passwordHash) {
        if (!connection.inTransaction()) throw new Z8PostgresException("password verification requires a transaction");
        auto rows = connection.execute("SELECT 1 FROM " ~ quoteIdentifier(schema) ~ `."SystemUsers" WHERE "RecordId" = $1::uuid AND "Password" = $2::text FOR UPDATE`,
            [Z8PostgresParameter.value(z8_guid_to_string(z8_nonnull(id)).to!string), Z8PostgresParameter.value(z8_string_required(passwordHash).to!string)]);
        return rows.rows.length == 1;
    }
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

private class Z8PostgresRawCursor : IZ8RawSqlCursor {
    private Z8PostgresResult result;
    private size_t nextRow, currentRow;
    private bool positioned, closed;
    this(Z8PostgresResult result) { this.result = result; }
    bool next() {
        if (closed) throw new Z8PostgresException("SQL cursor is closed");
        positioned = nextRow < result.rows.length;
        if (positioned) currentRow = nextRow++;
        return positioned;
    }
    Z8RawSqlValue value(long position) {
        if (closed) throw new Z8PostgresException("SQL cursor is closed");
        if (!positioned) throw new Z8PostgresException("SQL cursor is not positioned on a row");
        if (position < 1 || position > result.columns.length) throw new Z8PostgresException("SQL cursor column out of bounds");
        auto index = cast(size_t)(position - 1);
        auto cell = result.rows[currentRow][index];
        if (cell.isNull) return Z8RawSqlValue(null, true);
        auto raw = Z8RawSqlValue(cell.text.to!wstring, false);
        if (result.columnTypes[index] == 17) {
            raw.binary = true;
            raw.bytes = z8_postgres_unescape_bytea(cell.text);
        }
        return raw;
    }
    void close() { closed = true; positioned = false; result = Z8PostgresResult.init; }
}

// The embedding host installs one catalog per thread and closes it after use.
class Z8PostgresDatabaseCatalog : IZ8DatabaseCatalog {
    private struct Entry { Z8DatabaseDescriptor descriptor; Z8PostgresConnection connection; Z8PostgresDatabase backend; }
    private Z8DatabaseDescriptor current;
    private Z8RuntimeRegistry registry;
    private Entry[] entries;
    this(Z8DatabaseDescriptor current, Z8RuntimeRegistry registry = null) {
        this.current = current; this.registry = registry;
    }
    Z8DatabaseDescriptor currentDatabase() { return current; }
    IZ8DatabaseConnection connectionFor(Z8DatabaseDescriptor descriptor) {
        import std.string : indexOf, startsWith;
        if (descriptor.schema is null || !descriptor.schema.length) throw new Z8PostgresException("empty PostgreSQL schema");
        if (descriptor.connection is null || !descriptor.connection.length) throw new Z8PostgresException("empty PostgreSQL connection");
        auto driver = descriptor.driver is null ? "" : z8_str_toLowerCase(descriptor.driver).to!string;
        if (driver.indexOf("oracle") >= 0 || driver.indexOf("sqlserver") >= 0 || driver.indexOf("h2") >= 0)
            throw new Z8PostgresException("database driver is not PostgreSQL");
        foreach (entry; entries)
            if (entry.descriptor == descriptor && !entry.connection.isClosed()) return entry.backend;
        auto info = descriptor.connection.to!string;
        if (info.startsWith("jdbc:postgresql:")) info = info["jdbc:".length .. $];
        auto user = descriptor.user is null ? null : z8_to_utf8(descriptor.user);
        auto password = descriptor.password is null ? null : z8_to_utf8(descriptor.password);
        auto connection = new Z8PostgresConnection(info, user, password);
        scope(failure) connection.close();
        auto backend = new Z8PostgresDatabase(connection, descriptor.schema, registry);
        entries ~= Entry(descriptor, connection, backend);
        return backend;
    }
    void close() {
        foreach (entry; entries) entry.connection.close();
        entries = null;
    }
}
