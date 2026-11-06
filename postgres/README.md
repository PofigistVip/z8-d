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
`z8_postgres_bootstrap_registered` obtains fresh table instances from the registry
and accepts additional framework tables separately; the host must still supply
any required system tables that were not registered by the generated project.
Registered entry points are inserted or refreshed in `SystemEntries` when that
table is present; existing user assignments are retained and obsolete entries
are not deleted by the additive synchronizer.
`SystemEntries.Name` and `SystemRequests.Name` resolve their display names through
the active runtime registry, with `Class` included as a field dependency.
`z8_postgres_read_user` loads the user's ordered entry assignments as well as
role privileges, and supplies the built-in system-tools entry for an administrator
when it has not been assigned explicitly.
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
non-negative `start` and `limit`, `recordId` (one GUID or a JSON array), JSON `sort`, and `filter`, `where` and
`quickFilter` conditions. Sort and filter fields must be readable; malformed or empty filter
expressions are rejected rather than ignored, while `[]` means no filter.
With `count=true`, it returns `total`; if the requested offset is past the
last record, it also returns the final page, matching Java `ReadAction`.
The optional `values` object (or the first object of an array) initializes
readable direct scalar fields before `onReadAction` and `beforeRead` run.
`lookup` and `lookupFields` support case-insensitive matching across readable
text fields; multiple fields are combined with OR.
An active JSON `period` filters a readable direct `period` date field between
the optional inclusive `start` and `finish` boundaries.
BL-defined direct `groupBy` fields and JSON `having` conditions are supported;
all participating fields must be readable. Array and distinct aggregations are
accepted; the serialized value follows the original field's `get()` and
`wasNull()` semantics, and BL code can retrieve elements with `array()`.
Linked groups are allowed through readable Link paths. Changes to `groupBy` from
`beforeRead` are not supported.
The client `group` parameter places its fields first in the sort order; it
does not turn ordinary rows into SQL aggregates.
`totals=true` returns a `data` object with supported sum and average totals over
readable fields, including totals of grouped and `aggregateBy` results. Filters,
HAVING, linked fields and the query scope still apply.
As in the Java `ReadAction`, a nonempty `recordId` list replaces the request
filters and query scope; an empty list keeps the normal filters and scope.
Direct Link paths may be selected, filtered, searched and sorted when every
intermediate link and target table is readable; selected linked fields include
their link fields in the response. Context `values` may also reference readable
linked and computed fields; supplied values are detached while serializing rows.
Custom Join paths, other read options and custom request parameters are rejected. The host must open the
application response before calling it.
Ordinary computed fields can be selected, filtered and sorted only when all
their declared and SQL expression dependencies are readable.
`z8_application_dispatch_request` selects this adapter for a table request;
the CivetWeb host must explicitly call the dispatcher and install a backend for
the worker thread. The separately supported write actions are described below.
The initial `meta` action describes table fields, authorized Link paths, query
access and nested sections, fieldsets, field groups, tab controls, independent
forms and forms with a readable Link. Action parameters, their query-backed
sources, and report definitions are included. `aggregateBy` metadata marks the
query read-only. Other controls and custom Join metadata are rejected. Actions can execute with `action=action`,
`name`, `records`, `selection` and a JSON `parameters` array; `query` or `link`
selects the query passed to the action, and `useTransaction` controls the transaction.
Custom BL reports can run through `action=report`, while the BIRT and POI engines
remain unimplemented. `action=content` runs the selected query's binary callback
inside a transaction.
An omitted action combines this metadata with the corresponding table read.
Executable jobs support synchronous `scheduled` requests and asynchronous jobs
with `job` status polling. Their JSON `parameters` are an object keyed by parameter
ID. An asynchronous job uses an independent PostgreSQL connection, and only its
owner can poll its active monitor. Hosts can implement `IZ8JobUserResolver` for
custom identity parameters; otherwise the PostgreSQL backend resolves the standard
user fields and role privileges from the system tables.
The direct-table `create` action accepts a nonempty `data` array of objects,
checks table create access, and inserts the records in a transaction with the
BL creation hooks. Missing or zero primary keys receive random GUIDs. As in
Java `CreateAction`, create permission governs the supplied values; individual
field write permissions are enforced by `update`, not by `create`. After
commit, the action returns the readable requested fields of created records.
The direct-table `update` action accepts a nonempty `data` array of objects
containing the primary key and fields to change. It requires table and field
write access, runs the BL update hooks in a transaction, and returns the
readable requested fields of the affected records after commit. String, text,
integer, decimal, boolean, GUID, date, datetime and datespan values are
supported by both write actions, as are GeoJSON geometry values when PostGIS
is installed in the database. File and attachment field values are stored
as text metadata; binary fields accept an index into the request's uploaded
files. Linked or computed fields and additional write options are rejected.
Persisting attachment files separately is not implemented.
Optional `values` are checked before a create, update or copy transaction and
applied as readable context fields when selecting its response.
The direct-table `copy` action accepts source GUIDs in `recordId` and one
override object per source in `data`. It requires copy access and write access
to every primary field, invokes the BL copy hooks, and returns the copied
records after commit. Overrides use the same supported scalar types as create
and update. A missing or empty source list is rejected.
The direct-table `destroy` action accepts a nonempty `data` array of GUID
strings or objects containing the primary-key field. It checks request execute
and table destroy access, invokes the BL destroy hooks, and processes all records
in a transaction. Linked-query deletion and additional options are not supported.
As with the Java connection manager, nested transactions share the outer
transaction; callers must propagate failures to the outermost rollback.
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

`Z8PostgresScheduler` in `z8.database.scheduler` provides a synchronous
`runDue()` step for a host-owned timer. It loads active schedules, claims each
with a PostgreSQL advisory lock, checks its CRON against the last start, and
runs the registered executable as the configured user with request permission
checks. It records start, next start and finish times; a log row is written on
errors or when `Log errors only` is disabled. Results and captured messages are
returned to the caller. The scheduler needs an open connection with no active
transaction and the Jobs, ScheduledJobs, ScheduledJobLogs and security tables.
The caller supplies periodic calls and connection lifetime. Alternatively,
`Z8PostgresSchedulerService` in `z8.database.scheduler_service` starts a timer
thread with its own sibling connection. `start()` and `stop()` are idempotent;
`stop()` waits for a running job to finish. An optional thread-safe observer
receives run results and service errors on the scheduler thread. Neither API
persists monitor text unless an `IZ8SchedulerLogStore` is supplied.
`Z8FileSchedulerLogStore` stores logs under an explicitly configured directory;
the scheduler records their file metadata and size in `SystemScheduledJobLogs`.
Filesystem writes are outside the PostgreSQL transaction. Start time is committed
before execution, so a process crash after claiming a run does not retry that
occurrence automatically.
Both scheduler APIs accept optional user and role change notifiers, allowing
jobs that modify security records to invalidate the authority's sessions.

`Z8PostgresAuthenticator` in `z8.database.authentication` checks a login and
password against `SystemUsers`, returning a user and privilege snapshot or null
for denied credentials. It supports the original client-hashed and server-MD5
password modes, case-insensitive login lookup, permanent and timed bans, and
optional failed-attempt limits. Concurrent attempts lock the user row; failed
attempts and timed bans commit even when access is denied. It requires a
connection without an active transaction. When supplied, the user-change notifier
invalidates non-built-in users' sessions after a failed-attempt counter or ban
update commits, including a successful login that resets the counter. A notifier
failure is reported to the caller; the committed database update is retained.
A registered named `User` subclass
can implement the original `onBeforeLoad`, `authenticate` and `onLoad` hooks;
if custom authentication returns false or throws, password verification remains
the fallback. Hook execution uses a system-user request and the current schema.
The registered `SystemUsers` specialization can also populate or reject a
user through either `getParameters` overload. If that hook throws, the built-in
system and administrator accounts retain the original fallback behavior.
Trusted login and a network transport for cross-server notifications are still pending.
The optional `z8.integration.postgres_authority`
module connects it to CivetWeb.

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

The executor supports `aggregateBy` grouping over root Link fields with numeric
sum, average, minimum and maximum. Filters can reference linked tables, and a
subselect joins target fields, including chained links and computed fields, after
grouping. Expressions and joins requiring unprojected root fields are rejected, as are
a second grouping and row locks on these queries. Numeric sum and average totals
retain linked fields' joins and apply after grouping. `HAVING` filters over
projected root aggregates and linked fields run after the initial grouping;
HAVING defined by a linked query itself is not yet supported.
Nontrivial HAVING without grouping is also rejected. Filter-based updates and deletes select
matching records and invoke the BL events for each record. Record copying reads
the source through the executor and preserves an active query cursor. Table audit
values use the active request's session and event level; standalone use without
an active request does not populate them. Z8 table and field
privilege checks are not implemented by this executor; the host must enforce them.
