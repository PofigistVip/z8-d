"""Execute JsonObjectExpression reads and aggregation against PostgreSQL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from postgres_support import postgres_bin, temporary_postgres
from runtime_support import import_args, runtime_library

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/postgres_json_expression.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "JsonRows.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.JsonObjectExpression;
import org.zenframework.z8.base.json.JsonObject;
public class JsonRows extends Table {
    [name "Amount"] public IntField amount;
    [name "Title"] public StringField title;
    [name "Category"] public StringField category;
    public JsonObjectExpression data;
    public int verify() {
        Field[] members = {amount, title}; data = members;
        Field[] selected = {data}; read(selected);
        int total = 0; int count = 0;
        while (next()) { JsonObject object = data.get(); total += object.getInt("amount"); count += 1; }
        close();
        if (total != 12 || count != 2) return 1;
        Field[] groups = {category}; group(groups, selected);
        if (!next()) return 2;
        JsonObject[] rows = data.array();
        if (rows.size() != 2) return 3;
        if (rows[0].getInt("amount") + rows[1].getInt("amount") != 12) return 4;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.database.postgres;
import z8.database.schema;
import z8.database.query;
import z8gen.JsonRows;
import std.conv : to;
void main(string[] args) {
    auto db = new Z8PostgresConnection(args[1]); scope(exit) db.close();
    db.execute("CREATE SCHEMA json_test");
    auto table = z8_new!Z8p_4A736F6E526F7773(); z8_nonnull(table);
    z8_postgres_create_tables(db, "json_test"w, [table]);
    db.execute(`INSERT INTO "json_test"."JsonRows" ("RecordId", "Amount", "Title", "Category") VALUES
        ('00000000-0000-0000-0000-000000000011', 5, 'first', 'same'),
        ('00000000-0000-0000-0000-000000000012', 7, 'second', 'same')`);
    z8_query_set_executor(table, new Z8PostgresQueryExecutor(db, "json_test"w, "JsonRows"w));
    auto result = z8_optional_require(table.m_verify()); assert(result == 0, result.to!string);
}
''', encoding="utf-8")
    executable = temp / ("postgres-json-expression.exe" if os.name == "nt" else "postgres-json-expression")
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
            raise RuntimeError(f"PostgreSQL JSON expression fixture failed ({run.returncode}):\n{run.stdout}\n{run.stderr}")
print("PostgreSQL JSON expressions and aggregation verified")
