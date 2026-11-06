# Tasks example

This example compiles `Tasks.bl` against the original Z8 BL library and runs
the generated project in a single D process with PostgreSQL and CivetWeb. It
demonstrates registry generation, additive schema initialization, local
authentication, table actions and database- or disk-backed attachments. The host is a
small local example: it listens on a dynamically assigned loopback port and
exits when a line is entered on stdin. It can optionally serve the original
JavaScript client from a separately prepared public directory.

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
python webserver/prepare_client.py C:/path/to/org.zenframework.z8 C:/path/to/empty-public-dir
C:/path/to/tasks.exe $connection public --public-dir C:/path/to/empty-public-dir
```

The example uses the original client-hashed password mode; an HTTP login sends
the MD5 hash. The built-in administrator initially has the framework's empty
password default. Configure the credential before making the example reachable.
`--initialize` assigns the example Tasks entry to the administrator if it is
not already assigned. The host prints the assigned port; open
`http://127.0.0.1:<port>/index.html` for the prepared client. Its application
endpoint is `/request.json`, and authenticated file downloads use
`/storage/...`. Restarting the host reconciles additive schema changes and
refreshes declared static records while preserving ordinary data. The automated test checks delivery of the original
client files and the client's login request, not the entire browser UI.

Optionally add `--config C:/path/to/server.properties` to initialization and
server commands. The example applies the configured working and storage paths,
upload limit, password hashing mode, login-failure limits, session timeout and
single-session policy, disk storage mode, language and supported file extensions. Setting
`security.log.file` also enables a rotating request and login security log.
The properties file's directory is used as the application root. Without
`--config`, the host uses `server.properties` in its working directory if present.

Run the full automated example, including a temporary PostgreSQL instance and
two server runs, with:

```powershell
python tests/webapp_end_to_end.py C:/path/to/org.zenframework.z8 "C:/Program Files/PostgreSQL/15/bin"
```
