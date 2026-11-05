module z8.database.postgres;

import std.conv : to;
import std.string : fromStringz, toStringz;
import std.utf : validate;

// libpq text-protocol functions from PostgreSQL's public libpq-fe.h.
extern(C) {
    private struct PGconn;
    private struct PGresult;
    private PGconn* PQconnectdb(const(char)* conninfo);
    private int PQstatus(const(PGconn)* connection);
    private int PQtransactionStatus(const(PGconn)* connection);
    private const(char)* PQerrorMessage(const(PGconn)* connection);
    private void PQfinish(PGconn* connection);
    private int PQsetClientEncoding(PGconn* connection, const(char)* encoding);
    private PGresult* PQexecParams(PGconn* connection, const(char)* sql, int count,
        const(uint)* types, const(char)** values, const(int)* lengths, const(int)* formats, int resultFormat);
    private int PQresultStatus(const(PGresult)* result);
    private const(char)* PQresultErrorMessage(const(PGresult)* result);
    private int PQntuples(const(PGresult)* result);
    private int PQnfields(const(PGresult)* result);
    private const(char)* PQfname(const(PGresult)* result, int column);
    private int PQgetisnull(const(PGresult)* result, int row, int column);
    private int PQgetlength(const(PGresult)* result, int row, int column);
    private const(char)* PQgetvalue(const(PGresult)* result, int row, int column);
    private const(char)* PQcmdTuples(PGresult* result);
    private void PQclear(PGresult* result);
}

class Z8PostgresException : Exception {
    this(string message) { super(message); }
}
struct Z8PostgresParameter {
    string text;
    bool isNull;
    static Z8PostgresParameter value(string text) { return Z8PostgresParameter(text, false); }
    static Z8PostgresParameter nullValue() { return Z8PostgresParameter(null, true); }
}
struct Z8PostgresValue {
    string text;
    bool isNull;
}
struct Z8PostgresResult {
    string[] columns;
    Z8PostgresValue[][] rows;
    long affectedRows = -1;
}

private string z8PgCString(const(char)* value) { return value is null ? "" : value.fromStringz.idup; }
private void z8PgValidate(string value) {
    foreach (c; value) if (c == '\0') throw new Z8PostgresException("PostgreSQL text contains a NUL byte");
    try { validate(value); }
    catch (Exception e) { throw new Z8PostgresException("PostgreSQL text is not valid UTF-8"); }
}

// The connection uses libpq's synchronous text protocol. A result owns its
// copied data and remains usable after the connection is closed.
class Z8PostgresConnection {
    private PGconn* connection;
    private uint transactionDepth;
    this(string connectionInfo) {
        z8PgValidate(connectionInfo);
        connection = PQconnectdb(connectionInfo.toStringz);
        if (connection is null) throw new Z8PostgresException("libpq could not allocate a connection");
        if (PQstatus(connection) != 0 || PQsetClientEncoding(connection, "UTF8") != 0) {
            auto message = z8PgCString(PQerrorMessage(connection));
            PQfinish(connection); connection = null;
            throw new Z8PostgresException(message);
        }
    }
    ~this() { if (connection !is null) PQfinish(connection); }

    void close() {
        synchronized (this) {
            if (connection !is null) { PQfinish(connection); connection = null; }
            transactionDepth = 0;
        }
    }
    bool isClosed() { synchronized (this) return connection is null; }
    bool inTransaction() { synchronized (this) return transactionDepth != 0; }
    void beginTransaction() {
        synchronized (this) {
            if (connection is null) throw new Z8PostgresException("PostgreSQL connection is closed");
            if (transactionDepth == uint.max) throw new Z8PostgresException("too many nested PostgreSQL transactions");
            if (!transactionDepth) {
                if (PQtransactionStatus(connection) != 0) throw new Z8PostgresException("PostgreSQL transaction already started outside this connection manager");
                execute("BEGIN");
            }
            ++transactionDepth;
        }
    }
    void commit() {
        synchronized (this) {
            if (connection is null) throw new Z8PostgresException("PostgreSQL connection is closed");
            if (!transactionDepth) throw new Z8PostgresException("Connection.commit() - not in transaction");
            if (transactionDepth > 1) { --transactionDepth; return; }
            auto status = PQtransactionStatus(connection);
            if (status == 3) throw new Z8PostgresException("PostgreSQL transaction is aborted; rollback is required");
            if (status != 2) throw new Z8PostgresException("PostgreSQL transaction state is not active");
            execute("COMMIT"); transactionDepth = 0;
        }
    }
    void rollback() {
        synchronized (this) {
            if (connection is null) throw new Z8PostgresException("PostgreSQL connection is closed");
            if (!transactionDepth) return;
            if (transactionDepth > 1) { --transactionDepth; return; }
            execute("ROLLBACK"); transactionDepth = 0;
        }
    }

    Z8PostgresResult execute(string sql, Z8PostgresParameter[] parameters = null) {
        z8PgValidate(sql);
        if (parameters.length > int.max) throw new Z8PostgresException("too many PostgreSQL parameters");
        string[] storage;
        const(char)*[] values;
        foreach (parameter; parameters) {
            if (parameter.isNull) values ~= null;
            else {
                z8PgValidate(parameter.text);
                // Empty values must still have a non-null pointer for libpq.
                auto terminated = parameter.text ~ '\0';
                storage ~= terminated;
                values ~= terminated.ptr;
            }
        }
        synchronized (this) {
            if (connection is null) throw new Z8PostgresException("PostgreSQL connection is closed");
            auto result = PQexecParams(connection, sql.toStringz, cast(int)parameters.length, null,
                values.length ? values.ptr : null, null, null, 0);
            if (result is null) throw new Z8PostgresException(z8PgCString(PQerrorMessage(connection)));
            scope(exit) PQclear(result);
            auto status = PQresultStatus(result);
            if (status != 1 && status != 2) {
                auto message = z8PgCString(PQresultErrorMessage(result));
                // COPY requires a different libpq protocol; discard the connection
                // instead of leaving it in an unusable copy state.
                if (status == 3 || status == 4 || status == 8) { PQfinish(connection); connection = null; transactionDepth = 0; }
                throw new Z8PostgresException(message.length ? message : "unsupported PostgreSQL result");
            }
            Z8PostgresResult copy;
            foreach (column; 0 .. PQnfields(result)) copy.columns ~= z8PgCString(PQfname(result, column));
            foreach (row; 0 .. PQntuples(result)) {
                Z8PostgresValue[] cells;
                foreach (column; 0 .. PQnfields(result)) {
                    bool isNull = PQgetisnull(result, row, column) != 0;
                    if (isNull) cells ~= Z8PostgresValue(null, true);
                    else {
                        auto length = PQgetlength(result, row, column);
                        auto value = PQgetvalue(result, row, column);
                        cells ~= Z8PostgresValue(value[0 .. length].idup, false);
                    }
                }
                copy.rows ~= cells;
            }
            auto count = z8PgCString(PQcmdTuples(result));
            if (count.length) copy.affectedRows = count.to!long;
            return copy;
        }
    }
}
