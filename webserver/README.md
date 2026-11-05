# CivetWeb transport

`z8.webserver.civetweb` is the first HTTP transport layer for z8-d. It embeds the
pinned CivetWeb 1.16 sources in `third_party/civetweb` and invokes a D delegate
for every request. A fresh `Z8ApplicationRequest` is installed for the duration
of that callback, so BL code can use `Application.requestParameters()` and
`Application.responseWriter()`. The prior thread-local context is restored on
success, redirect, or error.

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
application routing, static assets, the full Z8 response
protocol, and TLS-capable deployment remain to be implemented.
