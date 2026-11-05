"""Generate PostgreSQL CREATE TABLE DDL from a real BL Table definition."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_schema.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Sample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.BoolField;
import org.zenframework.z8.base.table.value.DecimalField;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.DatetimeField;
import org.zenframework.z8.base.table.value.DatespanField;
import org.zenframework.z8.base.table.value.TextField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.IntExpression;
[name "Sample;--"] public class Sample extends Table {
    [name "Title"] public StringField title; title.defaultValue = "O'Reilly 😀";
    [name "Amount"] public IntField amount; amount.defaultValue = 7;
    [name "Flag"] public BoolField flag; flag.defaultValue = true;
    [name "Price"] public DecimalField price; price.defaultValue = 12.50;
    [name "Reference"] public GuidField reference;
    [name "Moment"] public DatetimeField moment;
    [name "Duration"] public DatespanField duration;
    [name "Details"] public TextField details;
    [name "Blob"] public BinaryField blob;
    public IntExpression computed;
}
''', encoding="utf-8")
    (source / "GeoSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GeometryField;
[name "GeoSample"] public class GeoSample extends Table { [name "Shape"] public GeometryField shape; }
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static Sample make() { Sample value; return value; }
    public static GeoSample geo() { GeoSample value; return value; }
    public static int count(Sample value) { return value.count(); }
    public static void create(Sample value, guid id) { value.create(id); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.schema;
import z8gen.p_Probe;
import std.algorithm.searching : canFind;
void main(string[] args) {
    alias P = Z8p_50726F6265;
    auto db = new Z8PostgresConnection(args[1]);
    db.execute("CREATE TEMP TABLE init_temp (id integer)");
    auto table = P.m_make();
    auto ddl = z8_postgres_create_table_sql("pg_temp"w, table);
    assert(ddl.canFind(`"Sample;--"`) && ddl.canFind(`"Title" character varying DEFAULT 'O''Reilly 😀'`));
    assert(!ddl.canFind("computed") && ddl.canFind(`"Reference" uuid DEFAULT '00000000-0000-0000-0000-000000000000' NOT NULL`));
    assert(ddl.canFind(`PRIMARY KEY ("RecordId")`));
    auto geo = z8_postgres_create_table_sql("pg_temp"w, P.m_geo());
    assert(geo.canFind(`"Shape" geometry(Geometry, 3857) DEFAULT NULL`));
    db.execute(ddl);
    db.execute(`INSERT INTO "Sample;--" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000001')`);
    auto row = db.execute(`SELECT "Title","Amount","Flag","Price","Reference","Moment","Duration","Details","Blob" FROM "Sample;--"`);
    assert(row.rows.length == 1 && row.rows[0][0].text == "O'Reilly 😀" && row.rows[0][1].text == "7" && row.rows[0][2].text == "1");
    assert(row.rows[0][3].text == "12.5" && row.rows[0][4].text == "00000000-0000-0000-0000-000000000000");
    assert(row.rows[0][5].text == "-62135769600000" && row.rows[0][6].text == "0" && row.rows[0][7].isNull && row.rows[0][8].isNull);
    bool notNull; try { db.execute(`INSERT INTO "Sample;--" ("RecordId","Reference") VALUES ('00000000-0000-0000-0000-000000000002',NULL)`); } catch (Z8PostgresException) { notNull = true; }
    assert(notNull);
    bool duplicate; try { db.execute(`INSERT INTO "Sample;--" ("RecordId") VALUES ('00000000-0000-0000-0000-000000000001')`); } catch (Z8PostgresException) { duplicate = true; }
    assert(duplicate);
    auto backend = new Z8PostgresDatabase(db, "pg_temp"w); auto previous = z8_connection_set_current(backend);
    assert(z8_optional_require(P.m_count(table)) == 1); P.m_create(table, z8_guid_create(3));
    assert(z8_optional_require(P.m_count(table)) == 2);
    z8_connection_set_current(previous); db.close();
}
''', encoding="utf-8")
    exe = temp / ("postgres-schema.exe" if os.name == "nt" else "postgres-schema")
    command = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
               *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
               str(harness), str(runtime)]
    command += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    subprocess.run([*command, "-of=" + str(exe)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        result = subprocess.run([str(exe), connection], env=environment, cwd=temp, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise SystemExit(f"Schema fixture failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
print("BL table schema generation, defaults and primary key verified in PostgreSQL")
