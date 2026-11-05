"""Start a temporary PostgreSQL cluster and exercise the optional libpq client."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres

root = Path(__file__).resolve().parents[1]
if len(sys.argv) > 2:
    raise SystemExit("Usage: python tests/postgres_client.py [postgres-bin-directory]")
bin_dir = postgres_bin(sys.argv[1] if len(sys.argv) == 2 else None)
libpq = bin_dir.parent / "lib/libpq.lib"

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
    db.beginTransaction(); assert(db.inTransaction());
    db.execute("INSERT INTO sample VALUES (9,'outer',NULL)");
    db.beginTransaction(); db.execute("INSERT INTO sample VALUES (10,'inner',NULL)");
    db.rollback(); assert(db.inTransaction()); db.commit(); assert(!db.inTransaction());
    assert(db.execute("SELECT count(*) FROM sample").rows[0][0].text == "4");
    db.beginTransaction(); db.execute("INSERT INTO sample VALUES (11,'rollback outer',NULL)");
    db.beginTransaction(); db.execute("INSERT INTO sample VALUES (12,'commit inner',NULL)");
    db.commit(); assert(db.inTransaction()); db.rollback(); assert(!db.inTransaction());
    assert(db.execute("SELECT count(*) FROM sample").rows[0][0].text == "4");
    db.rollback(); bool noTransaction;
    try { db.commit(); } catch (Z8PostgresException) { noTransaction = true; } assert(noTransaction);
    db.beginTransaction(); bool failedInTransaction;
    try { db.execute("SELECT missing FROM sample"); } catch (Z8PostgresException) { failedInTransaction = true; }
    bool abortedCommit; try { db.commit(); } catch (Z8PostgresException) { abortedCommit = true; }
    assert(failedInTransaction && abortedCommit && db.inTransaction());
    db.rollback(); assert(!db.inTransaction() && db.execute("SELECT 1").rows[0][0].text == "1");
    db.execute("BEGIN"); bool externalTransaction;
    try { db.beginTransaction(); } catch (Z8PostgresException) { externalTransaction = true; }
    assert(externalTransaction); db.execute("ROLLBACK");
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
    with temporary_postgres(bin_dir) as (connection, environment):
        subprocess.run([str(executable), connection], env=environment, cwd=temp, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
print("PostgreSQL client verified against a temporary local cluster")
