"""Check JDBC conversions used by grouped Count fields.

Usage: python tests/postgres_count_jdbc_oracle.py <postgres-bin> <postgresql-jdbc.jar>
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from postgres_support import postgres_bin, temporary_postgres

if len(sys.argv) != 3:
    raise SystemExit(__doc__)
bin_dir = postgres_bin(sys.argv[1])
jdbc = Path(sys.argv[2]).resolve()
if not jdbc.is_file():
    raise SystemExit("PostgreSQL JDBC jar not found")

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    source = temp / "CountOracle.java"
    source.write_text('''
import java.sql.*;
import java.nio.charset.StandardCharsets;
public class CountOracle {
    public static void main(String[] args) throws Exception {
        try (Connection db = DriverManager.getConnection("jdbc:postgresql://127.0.0.1:" + args[0] + "/postgres", "postgres", "");
             Statement stmt = db.createStatement()) {
            for (int count = 0; count <= 2; count++) {
                try (ResultSet row = stmt.executeQuery("SELECT count(*) FROM generate_series(1," + count + ")")) {
                    if (!row.next() || row.getLong(1) != count || !row.getString(1).equals(Integer.toString(count)) ||
                        !new String(row.getBytes(1), StandardCharsets.UTF_8).equals(Integer.toString(count)))
                        throw new AssertionError("incorrect JDBC count conversion: " + count);
                    try {
                        boolean result = row.getBoolean(1);
                        if (count == 2 || result != (count == 1)) throw new AssertionError("incorrect boolean: " + count);
                    } catch (SQLException error) {
                        if (count != 2) throw error;
                    }
                }
            }
        }
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", str(source)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        port = next(part.split("=", 1)[1] for part in connection.split() if part.startswith("port="))
        subprocess.run(["java", "-cp", str(temp) + os.pathsep + str(jdbc), "CountOracle", port],
                       cwd=temp, env=environment, check=True)
print("PostgreSQL JDBC count conversions verified")
