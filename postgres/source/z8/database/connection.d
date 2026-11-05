module z8.database.connection;

import std.conv : to;
import z8.runtime;
import z8.database.postgres;
import z8.database.query;

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
    // libpq executes immediately, so there is no pending JDBC batch to flush.
    void flush() { if (connection.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed"); }
    IZ8QueryExecutor queryExecutor(Z8Object query) {
        auto name = z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, query);
        return new Z8PostgresQueryExecutor(connection, schema, name);
    }
}
