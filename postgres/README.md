# PostgreSQL client

`z8.database.postgres` is an optional synchronous client using PostgreSQL's
`libpq` text protocol. The generated application and the core Z8 runtime do
not require this module unless PostgreSQL is used.

Install PostgreSQL's client development files and make `libpq` available to
the linker and loader. On Windows, add PostgreSQL's `lib` directory to `LIB`
and its `bin` directory to `PATH`. On Linux, install the distribution's libpq
development package. Build the module with `dub build` in this directory and
link the application with `libpq` (for example, pass the path to `libpq.lib` to
DMD on Windows, or `-L-lpq` on Linux).

`Z8PostgresConnection.execute` accepts a SQL statement and optional
`Z8PostgresParameter` values. Null parameters and empty strings are distinct;
results are copied and remain usable after closing the connection. Close each
connection explicitly when it is no longer needed.

`Z8PostgresQueryExecutor` connects BL `Query` reads to a single PostgreSQL
table. Construct it with a connection, schema and table name, then attach it to
the generated query with `z8_query_set_executor`. It supports explicit selected
fields, SQL filters and scope, sort direction, pagination, read locks and GUID
record lookup. It reads integer, boolean, decimal, string, text, file, binary,
GUID and date/duration fields. It also selects the table's primary key.

The executor currently rejects linked queries, grouping, nontrivial HAVING,
geometry and reads without an explicit field list. Query write operations and
schema generation are not yet implemented. Z8 table and field privilege checks
are not implemented by this executor; the host must enforce them.
