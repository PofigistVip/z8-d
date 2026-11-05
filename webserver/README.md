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
receives the session, class name, and action. Query, job, and binary-content
requests need specialized adapters and are not handled by this function.

An optional `IZ8HttpAuthority` constructor argument connects a host authority
to the transport. With an authority present, each request must have a session
accepted by `authorize`; for `request=login`, the server also tries `login`
using the supplied credentials when no session was accepted. Denied requests
receive the Z8 error envelope with HTTP 401. The authority supplies the
`Z8ApplicationSession` used by `Application.user()` and related methods. With
no authority, the host handler is responsible for access control. Providers
must handle concurrent calls and decide how to synchronize session state.
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
TLS. It is suitable for local integration. Session handling, authorization,
application routing, the full Z8 response
protocol, and TLS-capable deployment remain to be implemented.
