# Tasks example

This example compiles `Tasks.bl` against the original Z8 BL library and runs
the generated project in a single D process with PostgreSQL and CivetWeb. It
demonstrates registry generation, additive schema initialization, local
authentication, table actions and database-backed attachments. The host is a
small local example: it listens on a dynamically assigned loopback port, exits
when a line is entered on stdin, and does not serve the JavaScript client.

Build it with DMD, DUB, Python, a C compiler supported by
`webserver/build_civetweb.py`, and PostgreSQL client development libraries:

```powershell
dub build --compiler=dmd
python examples/webapp/build.py C:/path/to/org.zenframework.z8 C:/path/to/tasks.exe --postgres-bin "C:/Program Files/PostgreSQL/15/bin"
```

On Unix the PostgreSQL bin directory is normally discovered through
`pg_config`; `Z8_PG_BIN` or `--postgres-bin` can override it. On Windows,
`libpq.dll` and its dependencies must be available on `PATH` at runtime.

The target schema must already exist and the connection user must be allowed to
create its tables and indexes. Initialize it once, configure an administrator
password in `SystemUsers` using the original Z8 MD5 password representation,
then start the host:

```powershell
$connection = 'host=127.0.0.1 dbname=example user=example'
C:/path/to/tasks.exe $connection public --initialize
# Set the Admin user's Password in public."SystemUsers" before serving requests.
C:/path/to/tasks.exe $connection public
```

The example uses the original client-hashed password mode; an HTTP login sends
the MD5 hash. The built-in administrator initially has the framework's empty
password default. Configure the credential before making the example reachable.
The host prints the assigned port; its application endpoint is `/request.json`
and authenticated file downloads use `/storage/...`. Restarting the host
reconciles additive schema changes and preserves existing records.

Run the full automated example, including a temporary PostgreSQL instance and
two server runs, with:

```powershell
python tests/webapp_end_to_end.py C:/path/to/org.zenframework.z8 "C:/Program Files/PostgreSQL/15/bin"
```
