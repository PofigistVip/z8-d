"""Round-trip BL geometry through request actions and PostGIS."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_geometry.py <original-z8-root> [postgres-bin-directory]")
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
    (source / "GeoSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GeometryField;
public class GeoSample extends Table { [name "Shape"] public GeometryField shape; }
''', encoding="utf-8")
    (source / "GeoCountBucket.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "GeoCountBuckets"] public class GeoCountBucket extends Table { [name "Label"] public StringField label; }
''', encoding="utf-8")
    (source / "GeoCountSample.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Link;
import org.zenframework.z8.base.table.value.GeometryField;
import org.zenframework.z8.base.table.value.Aggregation;
[name "GeoCountSamples"] public class GeoCountSample extends Table {
    public GeoCountBucket bucket; [name "BucketId"] public Link bucketId = bucket;
    [name "Shape"] public GeometryField shape; shape.aggregation = Aggregation.Count;
    aggregateBy = {bucketId};
}
''', encoding="utf-8")
    (source / "GeoCountProbe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.Aggregation;
public class GeoCountProbe {
    public static GeoCountSample make() { GeoCountSample value; return value; }
    public static void read(GeoCountSample value) { Field[] fields = {value.bucketId, value.shape}; value.read(fields); }
    public static void readLinked(GeoCountSample value) { Field[] fields = {value.bucket.label, value.shape}; value.read(fields); }
    public static void groupLinked(GeoCountSample value) { value.bucket.label.aggregation = Aggregation.None; value.groupBy = {value.bucket.label}; }
    public static void groupDirect(GeoCountSample value) { value.aggregateBy.clear(); value.groupBy = {value.bucketId}; }
    public static bool next(GeoCountSample value) { return value.next(); }
    public static guid bucket(GeoCountSample value) { return value.bucketId.get(); }
    public static string label(GeoCountSample value) { return value.bucket.label.get(); }
    public static string count(GeoCountSample value) { return value.shape.get().toString(); }
    public static int countShape(GeoCountSample value) { return value.shape.get().shape(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.connection;
import z8.database.schema;
import z8.database.query;
import z8gen.GeoCountProbe;
import std.json : parseJSON, JSONType, JSONValue;
import std.conv : to;

void main(string[] args) {
    auto db = new Z8PostgresConnection(args[1]);
    db.execute("CREATE EXTENSION IF NOT EXISTS postgis");
    db.execute("CREATE SCHEMA geo_test");
    db.execute(`CREATE TABLE geo_test."GeoCountBuckets" ("RecordId" uuid PRIMARY KEY, "Label" text)`);
    db.execute(`CREATE TABLE geo_test."GeoCountSamples" ("RecordId" uuid PRIMARY KEY, "BucketId" uuid, "Shape" geometry)`);
    db.execute(`INSERT INTO geo_test."GeoCountBuckets" VALUES ('00000000-0000-0000-0000-000000000021','A'), ('00000000-0000-0000-0000-000000000022','B')`);
    db.execute(`INSERT INTO geo_test."GeoCountSamples" VALUES
        ('00000000-0000-0000-0000-000000000031','00000000-0000-0000-0000-000000000021',ST_GeomFromText('POINT(1 2)',3857)),
        ('00000000-0000-0000-0000-000000000032','00000000-0000-0000-0000-000000000021',ST_GeomFromText('POINT(3 4)',3857)),
        ('00000000-0000-0000-0000-000000000033','00000000-0000-0000-0000-000000000022',NULL)`);
    alias P = Z8p_47656F436F756E7450726F6265;
    auto count = P.m_make();
    z8_query_set_executor(count, new Z8PostgresQueryExecutor(db, "geo_test"w, "GeoCountSamples"w));
    P.m_read(count); int countRows;
    while (z8_optional_require(P.m_next(count))) {
        assert(P.m_count(count) == (P.m_bucket(count) == z8_guid_create(0x21) ? "2"w : "0"w)); ++countRows;
        bool invalidShape; try { P.m_countShape(count); } catch (Exception) { invalidShape = true; } assert(invalidShape);
    }
    assert(countRows == 2);
    P.m_readLinked(count); countRows = 0;
    while (z8_optional_require(P.m_next(count))) {
        assert(P.m_count(count) == (P.m_label(count) == "A"w ? "2"w : "0"w)); ++countRows;
    }
    assert(countRows == 2);
    P.m_groupLinked(count); P.m_readLinked(count); countRows = 0;
    while (z8_optional_require(P.m_next(count))) { assert(P.m_count(count) == "1"w); ++countRows; }
    assert(countRows == 2);
    P.m_groupDirect(count); P.m_read(count); countRows = 0;
    while (z8_optional_require(P.m_next(count))) {
        assert(P.m_count(count) == (P.m_bucket(count) == z8_guid_create(0x21) ? "2"w : "0"w)); ++countRows;
    }
    assert(countRows == 2);
    auto table = z8_object_new_instance("GeoSample"w);
    z8_postgres_create_tables(db, "geo_test"w, [table]);
    auto previous = z8_connection_set_current(new Z8PostgresDatabase(db, "geo_test"w));
    scope(exit) { z8_connection_set_current(previous); db.close(); }
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto session = new Z8ApplicationSession("geo"w, user, user);
    wstring invoke(wstring action, wstring data, wstring ids = null, wstring filter = null) {
        auto request = new Z8ApplicationRequest(); request.session = session; request.monitor = new Z8RequestMonitor();
        request.parameters.z8_add("request"w, "GeoSample"w); request.parameters.z8_add("action"w, action);
        request.parameters.z8_add("fields"w, `["shape"]`w);
        if (data !is null) request.parameters.z8_add("data"w, data);
        if (ids !is null) request.parameters.z8_add("recordId"w, ids);
        if (filter !is null) request.parameters.z8_add("filter"w, filter);
        auto prior = z8_application_set_request(request); scope(exit) z8_application_set_request(prior);
        z8_application_start_response(request, "GeoSample"w); z8_application_dispatch_request();
        z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor);
        return z8_application_response_text(request);
    }
    auto created = parseJSON(invoke("create"w, `[{"recordId":"00000000-0000-0000-0000-000000000011","shape":{"type":"Point","coordinates":[1.25,2.5]}}]`w).to!string);
    assert(created["data"].array.length == 1 && created["data"][0]["shape"]["type"].str == "Point");
    assert(created["data"][0]["shape"]["coordinates"][0].floating == 1.25);
    auto dbPoint = db.execute(`SELECT ST_AsEWKT("Shape") FROM "geo_test"."GeoSample" WHERE "RecordId"='00000000-0000-0000-0000-000000000011'`);
    assert(dbPoint.rows[0][0].text == "SRID=3857;POINT(1.25 2.5)");
    invoke("create"w, `[{"recordId":"00000000-0000-0000-0000-000000000013","shape":{"type":"Point","coordinates":[9,9]}}]`w);
    auto point = JSONValue(`{"type":"Point","coordinates":[1.25,2.5]}`).toString();
    auto filter = (`{"property":"shape","value":` ~ point ~ `}`).to!wstring;
    auto matching = parseJSON(invoke("read"w, null, null, filter).to!string);
    assert(matching["success"].boolean && matching["data"].array.length == 1);
    assert(matching["data"][0]["shape"]["coordinates"][0].floating == 1.25);
    auto updated = parseJSON(invoke("update"w, `[{"recordId":"00000000-0000-0000-0000-000000000011","shape":{"type":"LineString","coordinates":[[0,0],[3,4]]}}]`w).to!string);
    assert(updated["data"][0]["shape"]["type"].str == "LineString");
    auto copied = parseJSON(invoke("copy"w, `[{"recordId":"00000000-0000-0000-0000-000000000012"}]`w, "00000000-0000-0000-0000-000000000011"w).to!string);
    assert(copied["data"][0]["shape"]["type"].str == "LineString");
    assert(db.execute(`SELECT ST_AsEWKT("Shape") FROM "geo_test"."GeoSample" WHERE "RecordId"='00000000-0000-0000-0000-000000000012'`).rows[0][0].text == "SRID=3857;LINESTRING(0 0,3 4)");
    auto cleared = parseJSON(invoke("update"w, `[{"recordId":"00000000-0000-0000-0000-000000000011","shape":null}]`w).to!string);
    assert(cleared["data"][0]["shape"].type == JSONType.null_);
    assert(db.execute(`SELECT "Shape" IS NULL FROM "geo_test"."GeoSample" WHERE "RecordId"='00000000-0000-0000-0000-000000000011'`).rows[0][0].text == "t");
}
''', encoding="utf-8")
    exe = temp / ("postgres-geometry.exe" if os.name == "nt" else "postgres-geometry")
    args = ["dmd", "-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
            *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(harness), str(runtime), "-of=" + str(exe)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    response_file = temp / "dmd.rsp"
    response_file.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response_file)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        run = subprocess.run([str(exe), connection], env=environment, cwd=temp, capture_output=True, text=True, encoding="utf-8",
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if run.returncode:
            raise RuntimeError(f"PostGIS fixture failed ({run.returncode}):\n{run.stdout}\n{run.stderr}")
print("GeoJSON request actions round-trip through PostgreSQL PostGIS")
