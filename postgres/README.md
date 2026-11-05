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
to the caller. Existing built-in user names, passwords and descriptions are
preserved on reapplication. Built-in roles can be applied separately when an
application registry and initialized access tables are supplied; their names,
descriptions and permissions are preserved on reapplication. The combined
`z8_postgres_create_tables` bootstrap still rejects Roles because it does not
yet populate the application metadata needed by the role lifecycle.
Users' and Roles' native fields, built-in identifiers and Java-defined static
record metadata are available. Built-in user deletion is rejected, while the
built-in role deletion and user-ban checks follow Z8's user-event setting.
General authorization and cross-server user-change notifications are still
pending.
Physical fields of the system `Tables`, `Fields` and `Requests` metadata tables
are available, including the `Fields` link to `Tables`. Registry-based localized
display values remain unimplemented.
The native `RoleTableAccess`, `RoleFieldAccess` and `RoleRequestAccess` fields
and their table links are available. `RoleFieldAccess` keeps read and write
permissions consistent during user-level updates. `RoleTableAccess` also
normalizes table permissions and propagates read/write changes to matching field
access rows using the same database connection. Role-change notifications and
the remaining authorization lifecycle are not yet implemented. When a
`Z8RuntimeRegistry` is supplied as the third argument to `Z8PostgresDatabase`,
creating a role also creates access rows for its registered table keys and the
existing field and request records; deleting a role removes those access rows.
Without a registry these role lifecycle operations do not run. The metadata
tables and their referenced records must already exist, and callers should use
a transaction to group the role and access-row changes.

`z8_postgres_bootstrap` in `z8.database.bootstrap` initializes a new schema's
supplied tables, zero-GUID rows, built-in records, registered metadata, initial
access rows, indexes and foreign keys in one transaction. The caller must
provide the complete table list and registry, create the schema and extensions
first, and call it outside an existing transaction. Like the Java schema
generator it suppresses user-level events during initialization; an existing
request's event level is restored afterward. Existing tables are not migrated.
`UserRoles` provides links to users and roles, built-in administrator
assignments, a read-only flag based on the current user and protection against
removing the built-in assignments. The flag is metadata; general access
enforcement is not yet implemented.
`z8_postgres_load_privileges` in `z8.database.privileges` loads a user's roles
and effective table, field and request permissions. It combines grants across
roles, falls back to their default permissions and intersects field access
with table access. `z8_postgres_refresh_user_privileges` installs the snapshot
on a host user only after a successful load. The host can pass that user to
`z8_application_dispatch_authorized_object`, which checks request execution
permission before dispatch. Refresh after changes and authorization of query
and job adapters remain separate work, except for the limited table-read
adapter described below.
`z8_application_dispatch_query_read` reads a table using the current database
connection and the session's privilege snapshot. It requires request execute
and table read permissions, omits fields without read permission, and always
includes the primary key. It supports `action=read`, a JSON `fields` array,
non-negative `start` and `limit`, and JSON `filter`, `where` and `quickFilter`
conditions. Filter fields must be readable; malformed or empty filter
expressions are rejected rather than ignored, while `[]` means no filter.
Linked and computed fields,
sorting, other read options and custom request parameters are rejected. The host must
open the application response before calling it; the CivetWeb transport does
not select this adapter automatically. Other query actions are not implemented.
The native `Users.onNew` defaults mirror the Java implementation, including its
default password value and `changePassword` flag; explicitly supplied values
are preserved even when user-level events are disabled. With user events enabled,
unnamed nonzero user records receive a sequence-based name. The prefix can be
provided through the `Users.name.default` resource; it defaults to `User`.
`Sequencer.next` and `Field.getSequencer` allocate values from the native
`SystemSequences` table. Allocation uses atomic database updates. When the
first call for a key occurs in a transaction, the initial row is created using
a separate connection, while increments participate in the caller's transaction.
The `SystemSequences` table must already be committed and visible to that
connection. The extra connection uses the original connection string and does
not inherit session-local settings; temporary schemas cannot be used for this
case. Duplicate existing keys are rejected. PostgreSQL reports bigint overflow.
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
`z8_postgres_compare_table` in `z8.database.compare` reports missing or extra
columns, mismatched types and nullability, primary-key differences, and missing
or extra foreign keys. Foreign keys are compared by their columns, target and
PostgreSQL constraint behavior. It does not yet compare defaults or indexes,
and never changes the schema.
`z8_postgres_plan_add_columns` in `z8.database.migration` returns SQL for
missing non-primary columns with their BL defaults and nullability. The caller
can review and execute the statements; other differences, indexes and foreign
keys require separate handling.

`z8_postgres_sync_registry` in `z8.database.metadata` inserts or updates the
registered table, field and request metadata and creates initial access rows
for existing roles when metadata is new. Existing permissions and unregistered
rows are preserved. It uses the caller's transaction if present, otherwise it
creates one; concurrent synchronizations of the same schema are serialized.
This is the additive part of `AccessRightsGenerator`: it does not remove stale
metadata, emit cross-server notifications or populate audit fields through BL
table events.

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
