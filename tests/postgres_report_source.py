"""Verify query-backed report sources preserve active PostgreSQL cursors."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_report_source.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ReportRows.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.form.report.DataSource;
public class ReportRows extends Table {
    [name "Amount"] public IntField amount;
    sortFields = {amount};
    public void start() { Field[] fields = {amount}; read(fields); }
    public bool advance() { return next(); }
    public int value() { return amount.get(); }
    public void change(int value) { amount = value; }
    public DataSource source() { DataSource result; result = this; return result; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.schema;
import z8.database.query;
import z8gen.p_ReportRows;
class FailingExecutor : IZ8QueryExecutor {
    IZ8QueryCursor read(Z8Object query, Z8QueryReadRequest request) { throw new Exception("report query failed"); }
}
void main(string[] args) {
    auto db = new Z8PostgresConnection(args[1]); scope(exit) db.close();
    db.execute("CREATE SCHEMA report_test");
    auto table = z8_new!Z8p_5265706F7274526F7773(); z8_nonnull(table);
    z8_postgres_create_tables(db, "report_test"w, [table]);
    db.execute(`INSERT INTO "report_test"."ReportRows" ("RecordId", "Amount") VALUES
        ('00000000-0000-0000-0000-000000000011', 5), ('00000000-0000-0000-0000-000000000012', 7)`);
    auto executor = new Z8PostgresQueryExecutor(db, "report_test"w, "ReportRows"w);
    z8_query_set_executor(table, executor);
    table.m_start(); assert(z8_optional_require(table.m_advance()) && z8_optional_require(table.m_value()) == 5);
    auto source = table.m_source(); auto fields = [cast(Z8Object)table.f_amount];
    z8_report_source_open(source, 0, fields);
    assert(z8_report_source_count(source) == 2);
    assert(z8_report_source_next(source) && z8_optional_require(table.m_value()) == 5);
    assert(z8_report_source_next(source) && z8_optional_require(table.m_value()) == 7);
    assert(!z8_report_source_next(source)); z8_report_source_close(source);
    assert(z8_optional_require(source.m_getIndex()) == 2);
    assert(z8_optional_require(table.m_value()) == 5);
    bool failed;
    try { z8_report_source_open(source, 0, [cast(Z8Object)table]); } catch (Exception) { failed = true; }
    assert(failed && z8_optional_require(table.m_value()) == 5);
    z8_query_set_executor(table, new FailingExecutor()); failed = false;
    try { z8_report_source_open(source, 0, fields); } catch (Exception) { failed = true; }
    z8_query_set_executor(table, executor);
    assert(failed && z8_optional_require(table.m_value()) == 5);
    assert(z8_optional_require(table.m_advance()) && z8_optional_require(table.m_value()) == 7);
    table.m_change(99);
    z8_report_source_open(source, 0, fields, true);
    assert(z8_report_source_next(source) && z8_optional_require(table.m_value()) == 12);
    assert(!z8_report_source_next(source)); z8_report_source_close(source);
    assert(z8_optional_require(table.m_value()) == 99);
}
''', encoding="utf-8")
    executable = temp / ("postgres-report-source.exe" if os.name == "nt" else "postgres-report-source")
    args = ["-I" + str(generated), "-I" + str(root / "postgres/source"), *import_args(),
            *map(str, generated.rglob("*.d")), *map(str, (root / "postgres/source/z8/database").glob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    args += [str(bin_dir.parent / "lib/libpq.lib")] if os.name == "nt" else ["-L-lpq"]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    with temporary_postgres(bin_dir) as (connection, environment):
        run = subprocess.run([str(executable), connection], env=environment, cwd=temp, capture_output=True, text=True,
                             encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if run.returncode:
            raise RuntimeError(f"PostgreSQL report source fixture failed ({run.returncode}):\n{run.stdout}\n{run.stderr}")
print("PostgreSQL report source reads, aggregation and cursor restoration verified")
