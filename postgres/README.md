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

`beginTransaction`, `commit` and `rollback` maintain a nesting counter like the
original Z8 connection: only the outermost commit or rollback issues SQL; an
inner rollback is not a savepoint and does not undo changes by itself. If a SQL
error aborts the transaction, an outer commit reports an error and the caller
must roll back. Do not mix these methods with raw `BEGIN`/`COMMIT`/`ROLLBACK`.

`Z8PostgresDatabase` from `z8.database.connection` connects this client to the
BL `Connection` API. Install it for the current thread with
`z8_connection_set_current`, and restore the returned previous backend when the
request ends. `Connection.get()` uses that backend; queries without an explicit
executor use it and derive the table name from the BL query's `name` attribute.
`Query.setConnection` binds a query to a specific connection. `flush()` is a
no-op because this client executes statements immediately. `Connection.call`
invokes a procedure in the configured schema with parameterized scalar, GUID,
date, duration, binary and geometry values; file and user-defined primary
parameters are not yet supported.

`z8_postgres_create_table_sql(schema, table)` in `z8.database.schema` generates
`CREATE TABLE` SQL for a BL `Table`, including physical fields, PostgreSQL types,
defaults and the primary key. `z8_postgres_create_indexes_sql(schema, table)`
returns separate index statements, including case-insensitive and trigram
indexes. Both functions only return SQL; the host chooses when to run it.
Geometry columns and indexes require PostGIS; trigram indexes require `pg_trgm`.
Unique GIN and GiST indexes are rejected because PostgreSQL does not support
them. `z8_postgres_create_foreign_keys_sql(schema, table)` returns constraints
for enabled BL `Link` fields, including self-referencing parent keys. Create
referenced tables and use `z8_postgres_ensure_null_record` for their zero-GUID
records before applying constraints. The helper invokes BL creation hooks for
missing records and preserves existing ones; callers must serialize concurrent
schema generation. The schema lifecycle does not yet call it automatically.
`z8_postgres_apply_static_records` creates or updates declared BL records using
table events; it expects a clean table instance and leaves transaction control
to the caller. Built-in Users and Roles tables are rejected until their special
rules for preserving credentials and permissions are implemented.
`z8_postgres_create_tables` runs these operations, index creation and foreign
keys in phases inside one transaction for a new set of tables. The schema and
required extensions must already exist. It rejects an existing transaction and
does not migrate existing tables. Database changes roll back on failure; side
effects performed by BL event handlers outside the database do not. The full
original schema lifecycle is not yet implemented.

`z8_postgres_describe_table` in `z8.database.catalog` reads a table's columns,
default expressions, ordered primary key, indexes and foreign-key definitions
from PostgreSQL catalogs. It returns null for a missing table and accepts
`pg_temp` as the current connection's temporary schema. The result is a
read-only snapshot, not an automatic migration plan.

`Z8PostgresQueryExecutor` connects BL `Query` reads to PostgreSQL tables.
Construct it with a connection, schema and root table name, then attach it to
the generated query with `z8_query_set_executor`. It supports explicit selected
fields, SQL filters and scope, sort direction, pagination, read locks and GUID
record lookup. Nested `Link` targets use their Z8 table names in the same schema;
only links needed by selected fields, filters, sorting, grouping and expression
dependencies are joined. `Join` supports a BL SQL boolean condition; its dependent
tables are joined first, and cyclic join dependencies are rejected. Inner, left, right and full joins are supported, as
are target-query filters and chained links. `GROUP BY`, `HAVING` and array aggregations are
supported. `Query.count()` preserves an active cursor and counts groups when
the query is grouped; `hasRecord` and `findRecords` are also available. It reads integer, boolean, decimal, string, text, file, binary, GUID
and date/duration fields. Ungrouped reads also select the table's primary key.
As in Z8, ungrouped reads exclude the all-zero primary-key sentinel.
`create`, `update(guid)` and `destroy(guid)` use parameterized statements for
the same single-table field types. As in Z8, `update(null)` updates every row;
the SQL transaction is controlled by the connection's caller.

An empty field list selects the query's direct field controls, names, columns
and extra fields; nested form controls are not yet supported.

The executor currently rejects `aggregateBy` links, geometry, and nontrivial
HAVING without grouping. Filter-based updates and deletes select
matching records and invoke the BL events for each record. Record copying reads
the source through the executor and preserves an active query cursor. Table audit
values use the active request's session and event level; standalone use without
an active request does not populate them. Z8 table and field
privilege checks are not implemented by this executor; the host must enforce them.
