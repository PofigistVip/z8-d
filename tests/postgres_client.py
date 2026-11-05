"""Start a temporary PostgreSQL cluster and exercise the optional libpq client."""
from pathlib import Path
import os
import shutil
import socket
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
if len(sys.argv) > 2:
    raise SystemExit("Usage: python tests/postgres_client.py [postgres-bin-directory]")
if len(sys.argv) == 2:
    bin_dir = Path(sys.argv[1]).resolve()
elif os.environ.get("Z8_PG_BIN"):
    bin_dir = Path(os.environ["Z8_PG_BIN"]).resolve()
elif shutil.which("pg_config"):
    bin_dir = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
else:
    raise SystemExit("Pass the PostgreSQL bin directory or set Z8_PG_BIN")
suffix = ".exe" if os.name == "nt" else ""
initdb, pg_ctl = bin_dir / ("initdb" + suffix), bin_dir / ("pg_ctl" + suffix)
if not initdb.is_file() or not pg_ctl.is_file():
    raise SystemExit("PostgreSQL initdb and pg_ctl were not found")
libpq = bin_dir.parent / "lib/libpq.lib"
if os.name == "nt" and not libpq.is_file():
    raise SystemExit("PostgreSQL libpq.lib was not found")

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.database.postgres;
import std.conv : to;
void main(string[] args) {
    auto db = new Z8PostgresConnection(args[1]);
    assert(!db.isClosed());
    auto create = db.execute("CREATE TEMP TABLE sample (id integer, name text, note text)");
    assert(create.rows.length == 0 && create.affectedRows == -1);
    auto inserted = db.execute("INSERT INTO sample VALUES ($1::integer, $2::text, $3::text)",
        [Z8PostgresParameter.value("7"), Z8PostgresParameter.value("Ж😀 O'Reilly"), Z8PostgresParameter.nullValue()]);
    assert(inserted.affectedRows == 1);
    db.execute("INSERT INTO sample VALUES ($1::integer, $2::text, $3::text)",
        [Z8PostgresParameter.value("8"), Z8PostgresParameter.value(""), Z8PostgresParameter.value("literal NULL")]);
    auto result = db.execute("SELECT id, name, note FROM sample ORDER BY id");
    assert(result.columns == ["id", "name", "note"] && result.rows.length == 2);
    assert(result.rows[0][0].text == "7" && result.rows[0][1].text == "Ж😀 O'Reilly" && result.rows[0][2].isNull);
    assert(result.rows[1][1].text == "" && !result.rows[1][1].isNull && result.rows[1][2].text == "literal NULL");
    auto literal = db.execute("SELECT $1::text", [Z8PostgresParameter.value("'; DROP TABLE sample; --")]);
    assert(literal.rows[0][0].text == "'; DROP TABLE sample; --");
    db.execute("BEGIN"); db.execute("DELETE FROM sample"); db.execute("ROLLBACK");
    assert(db.execute("SELECT count(*) FROM sample").rows[0][0].text == "2");
    bool sqlError; try { db.execute("SELECT missing FROM sample"); } catch (Z8PostgresException) { sqlError = true; }
    assert(sqlError && db.execute("SELECT 1").rows[0][0].text == "1");
    bool nul; try { db.execute("SELECT $1::text", [Z8PostgresParameter.value("x\\0y")]); } catch (Z8PostgresException) { nul = true; }
    assert(nul);
    bool invalidUtf; try { db.execute("SELECT $1::text", [Z8PostgresParameter.value("\\xFF")]); } catch (Z8PostgresException) { invalidUtf = true; }
    assert(invalidUtf);
    db.close(); db.close(); assert(db.isClosed() && result.rows[0][1].text == "Ж😀 O'Reilly");
    bool closed; try { db.execute("SELECT 1"); } catch (Z8PostgresException) { closed = true; } assert(closed);
    auto copy = new Z8PostgresConnection(args[1]);
    bool unsupported; try { copy.execute("COPY (SELECT 1) TO STDOUT"); } catch (Z8PostgresException) { unsupported = true; }
    assert(unsupported && copy.isClosed());
}
''', encoding="utf-8")
    executable = temp / ("postgres-client.exe" if os.name == "nt" else "postgres-client")
    command = ["dmd", "-I" + str(root / "postgres/source"), str(root / "postgres/source/z8/database/postgres.d"), str(source)]
    command += [str(libpq)] if os.name == "nt" else ["-L-lpq"]
    command += ["-of=" + str(executable)]
    subprocess.run(command, cwd=temp, check=True)
    environment = os.environ.copy()
    environment["PATH"] = str(bin_dir) + os.pathsep + environment.get("PATH", "")
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    data = temp / "data"
    subprocess.run([str(initdb), "-D", str(data), "-A", "trust", "-U", "postgres", "--no-locale", "-E", "UTF8", "--no-sync"],
                   env=environment, stdout=subprocess.DEVNULL, check=True, creationflags=creation_flags)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    try:
        options = f"-h 127.0.0.1 -p {port} -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
        subprocess.run([str(pg_ctl), "-D", str(data), "-l", str(temp / "postgres.log"), "-o", options, "-w", "start"],
                       env=environment, stdout=subprocess.DEVNULL, check=True, creationflags=creation_flags)
        subprocess.run([str(executable), f"host=127.0.0.1 port={port} dbname=postgres user=postgres connect_timeout=5"],
                       env=environment, cwd=temp, check=True, creationflags=creation_flags)
    finally:
        if (data / "postmaster.pid").exists():
            subprocess.run([str(pg_ctl), "-D", str(data), "-m", "immediate", "-w", "stop"],
                           env=environment, stdout=subprocess.DEVNULL, check=True, creationflags=creation_flags)
print("PostgreSQL client verified against a temporary local cluster")
