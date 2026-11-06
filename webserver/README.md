# CivetWeb transport

`z8.webserver.civetweb` is the first HTTP transport layer for z8-d. It embeds the
pinned CivetWeb 1.16 sources in `third_party/civetweb` and invokes a D delegate
for every request. A fresh `Z8ApplicationRequest` is installed for the duration
of that callback, so BL code can use `Application.requestParameters()` and
`Application.responseWriter()`. The prior thread-local context is restored on
success, redirect, or error. Each request also has a `Z8RequestMonitor`, exposed
as `Z8HttpRequest.monitor`, that captures BL messages, log entries and printed
files for the host. The host can serialize its `info` object with
`request.monitor.infoJson(serverId)`, using the same fields as the Java
`JsonWriter.writeInfo`. Its logs remain in memory; log-file persistence and
automatic inclusion of this information in the complete Z8 response protocol
are still pending for raw responses.

Hosts can select `Z8ResponseMode.application` when constructing the server.
It opens the standard `request`/`success` object before calling the handler,
then adds `server` and monitor `info`; BL handlers write properties into that
open object. Handler failures produce the Z8 error envelope and HTTP 200, as
in `RequestDispatcher`. Credential storage, retries, and the rest of the
application-server protocol remain to be implemented.

A handler can use `z8_application_dispatch_object(className, mayExecute)` to
instantiate an ordinary BL `Object`, invoke its virtual `getData`, and write
`data` and `ui`. The host must supply the permission-checking delegate; it
receives the session, class name, and action. For `action=content`, it invokes
`processContentRequest` and the transport streams the binary result with the
original Z8 binary content type (`application/xml`). Query and job requests
need specialized adapters and are not handled by this function.

Alternatively, a handler can call `z8_application_dispatch_request()` in
application response mode. It resolves the `request` parameter, verifies the
session user's request permission, and routes ordinary objects or the supported
table `meta`, `read`, `create`, `copy`, `update`, `destroy`, `attach`, `detach`, `archive`, `action`, `report`
and `content` operations to the corresponding adapter. Before a table action, the
host must install a database backend for the worker thread and restore the
previous backend afterward. The authority is responsible for providing a
current privilege snapshot. The dispatcher also runs executable jobs and handles
their status polling; selecting this handler is explicit rather than automatic.

For database-backed attachments, the optional final `storageDownloads` argument
to `Z8CivetServer` registers `/storage` in application mode. It requires an
authority and a separate application request path. The host's existing handler
must install the database backend, then route requests whose path starts with
`/storage/` to `z8_application_dispatch_file_download(request.path.to!wstring)`;
other requests continue to `z8_application_dispatch_request()`. Downloads use
the original client's `session` and `id` parameters and require the stored
`SystemFiles` path to match the requested path. The authority validates the
session; as with the original converter, the URL does not identify a table or
record for a per-field permission check. Files are returned as attachments with
UTF-8 filenames. Preview conversion and files outside `SystemFiles` are not yet
handled by this route, except short-lived archives created by `action=archive`.
The archive URL is bound to its session, user and database schema; archive data
is retained in the same server process for at most ten minutes, so its download
must be routed to that process. The archive cache has size and count limits.

The initial `meta` adapter writes query attributes, access rights, keys and
metadata for direct and linked fields, including basic presentation, dependencies,
permitted source information and BL `writeMeta` overrides. Nested sections,
fieldsets, field groups, tab controls, action groups, independent forms and forms with a readable Link are also supported.
`Listbox` supports a table query, columns, sorting, actions, a readable Link and
Selector metadata. Tree link metadata is not implemented yet. Table and link
access are checked.
Actions and their parameters are described in metadata and can execute with a
direct or nested query, respecting their `useTransaction` setting. Report metadata
and custom BL report hooks are supported; built-in BIRT and POI engines remain
unimplemented. Fields reached through a custom Join are exposed as read-only
text controls after checking the relation and target permissions. Grouping with
`aggregateBy` is supported by the PostgreSQL executor for its documented subset.
Other control types and unsupported grouping combinations are rejected.
Without an explicit `fields` parameter, configured form controls, names, columns
and extra fields determine the selected fields; if none are configured, z8-d
uses the table's declared fields as a convenience fallback. Field dependencies
are included in the selection, subject to the same access checks.
Read, metadata, create, copy, update and destroy requests can select a nested table using
`query`; the root request, containing tables, their connecting relations and
the selected table are checked. A read can also select the target of a `link`;
as in the original action factory, a nonempty `link` takes precedence over `query`.
With no
`action` parameter, the same metadata is followed by the table read response.

Executable requests with `scheduled` run synchronously; other executable requests
return a job ID and run in a background thread. Poll with the `job` parameter to
receive progress and new messages. The active job monitor is accessible only to the
user that started it and is removed after its completed status is read. Asynchronous
database work requires a backend implementing `IZ8BackgroundDatabaseConnection`;
the PostgreSQL backend opens an independent connection. Job user switching requires
the built-in administrator and an `IZ8JobUserResolver`: the HTTP authority can
implement it, or the PostgreSQL backend can resolve standard users and privileges.

For `request=login`, the dispatcher writes the authenticated session, user
profile, roles, parameters and available entry descriptors. Authentication is
still supplied by `IZ8HttpAuthority`. Login-time email changes and password
changes are supported. The password verifier locks the PostgreSQL user row until
the update commits; `Z8ApplicationConfig.clientHashesPasswords` controls whether
the client supplies the existing Z8 MD5 hashes or the server computes them.
The optional experimental login response includes desktop actions visible to the
current user and omits actions without request permission.
`request=settings` saves `data` to the current session user's `SystemUsers`
record through the active database backend.

An optional `IZ8HttpAuthority` constructor argument connects a host authority
to the transport. With an authority present, each request must have a session
accepted by `authorize`; for `request=login`, the server also tries `login`
using the supplied credentials when no session was accepted. Denied requests
receive the Z8 error envelope with HTTP 401. The authority supplies the
`Z8ApplicationSession` used by `Application.user()` and related methods. With
no authority, the host handler is responsible for access control. Providers
must handle concurrent calls and decide how to synchronize session state.
For a single PostgreSQL schema, the optional integration module
`z8.integration.postgres_authority` supplies `Z8PostgresHttpAuthority`. Add
`integrations/postgres_webserver/source`, `postgres/source` and
`webserver/source` to the D import and build paths. It checks passwords against
PostgreSQL, creates session tokens using the operating system's secure random
generator, enforces the supplied session manager's timeout on requests, and
handles local user and role invalidation. Its source connection must remain
open; each login opens an independent sibling connection. The authority's
password-hashing configuration must match `Z8ApplicationConfig` for login-time
password changes. `logout(sessionId)` revokes a session; an HTTP logout endpoint
and cross-server session synchronization remain to be implemented.
Optional remote user and role notifiers can forward local changes; the protobuf
adapter in `protocol` provides a transport-independent publisher interface.
`integrations/protobuf_postgres_webserver` also exposes that authority through
the transport-neutral protobuf service. A network transport must authenticate
peers and supply the actual RPC delivery.
An authority can implement `IZ8HttpSessionLogout` to support an authenticated
`request=logout` application request. The server revokes the authorized session
and returns the normal success response; subsequent requests using that session
are denied. Both PostgreSQL and protobuf authority adapters support this API.
An authority may also implement `IZ8UserChangeNotifier`. User updates, deletion,
and the BL `Users.notifyUserChange` call then notify it with the user ID and
database schema, so it can invalidate cached sessions for the correct tenant.
The PostgreSQL backend supplies the schema. `Z8SessionManager` implements this
interface and drops that user's session; a host authority can delegate to it.
As in the Java implementation, the callback runs during the database operation,
which can be before an enclosing transaction commits. Changes to the current or
built-in user normally do not notify; setting `changePassword` to true forces it.
An authority can implement `IZ8RoleChangeNotifier` to invalidate sessions when
table, field or request permissions change. `Z8SessionManager` implements this
capability too, preserving administrator sessions as the original manager does.
Updating or deleting a role also invalidates affected non-administrator sessions.
`remoteAddress` is the connection peer; `forwardedAddress` exposes the raw
`X-Real-IP` header for deployments where the host explicitly trusts its proxy.

For a bundled web client, pass a public `documentRoot` and a specific
`requestPath` (normally `/request.json`) to the server constructor. CivetWeb
serves static assets from that directory and dispatches the request path to BL.
Directory listings and server-side includes are disabled, and common servlet
and repository metadata paths are hidden. Use a dedicated public asset directory:
CivetWeb may follow filesystem links, so its contents and links must be trusted.
To prepare the framework client from a checkout of the original Z8 sources:

```sh
python webserver/prepare_client.py path/to/original-z8 path/to/empty-public-dir
```

The script follows the original Gradle `.buildorder` lists and copies the
framework JavaScript, CSS, fonts and images. It fills in the original HTML
template with `revolt`, the bundle name. Application-specific client files and
server endpoints still need to be supplied by the application.

The host owns the server and must call `stop()` from outside a request handler.
Callbacks may run concurrently and must synchronize their own shared state.
`Z8HttpRequest` exposes the HTTP method, decoded path, raw query, content type,
remote address, and body. Query strings and URL-encoded forms populate the
application parameters; for repeated keys the first value is used. Multipart
forms instead use the last value for repeated fields, ignore query parameters,
and expose uploaded files through `Application.requestFiles()`. The `ip`
parameter is set from the connection. The default maximum body is 1 MiB; the
constructor accepts another positive byte limit. Multipart content is buffered
in memory within this limit. Oversized and malformed requests return HTTP 413
and 400 respectively. A `Z8Redirect`
produces a JSON response with status 302. Unexpected errors return HTTP 500.

To compile the CivetWeb object on Windows with MSVC x64 or on Unix with `cc`:

```sh
python webserver/build_civetweb.py path/to/civetweb.o
```

Use `.obj` for the output on Windows. Link that object, the separate z8 runtime,
`webserver/source/z8/webserver/civetweb.d`, and the D modules generated from the
BL project into the host executable. On Unix also link pthread and dl. The test
`python tests/civetweb_server.py [path/to/original-z8]` demonstrates the complete
build and runs concurrent loopback HTTP requests through a BL handler.

The bundled test build enables WebSockets, disables CGI, and does not include
TLS. It is suitable for local integration. Full Z8 response compatibility and
TLS-capable deployment remain to be implemented.
