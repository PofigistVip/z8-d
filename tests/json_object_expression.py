"""Exercise JsonObjectExpression SQL generation and cursor-value decoding."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/json_object_expression.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "JsonExpressionTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.JsonObjectExpression;
public class JsonExpressionTable extends Table {
    [name "Amount"] public IntField amount;
    [name "Title"] public StringField title;
    public JsonObjectExpression data;
}
''', encoding="utf-8")
    (source / "JsonExpressionProbe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.JsonObjectExpression;
import org.zenframework.z8.base.json.JsonObject;
public class JsonExpressionProbe {
    public static JsonExpressionTable make() { JsonExpressionTable table; return table; }
    public static void fields(JsonExpressionTable table) {
        Field[] values = {table.amount, table.title}; table.data = values;
    }
    public static void named(JsonExpressionTable table) {
        sql_int count = 7; sql_string text = "Ada";
        sql_primary[string] values = {("count", count), ("name", text)};
        table.data = values;
    }
    public static string title(JsonExpressionTable table) { return table.data.get().getString("title"); }
    public static JsonObject[] array(JsonExpressionTable table) { return table.data.array(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_JsonExpressionProbe;
import std.algorithm.searching : canFind;
void main() {
    alias P = Z8p_4A736F6E45787072657373696F6E50726F6265;
    auto table = P.m_make(); z8_nonnull(table); auto expression = table.f_data;
    z8_field_bind_sql(table.f_amount, "t"w, "Amount"w);
    z8_field_bind_sql(table.f_title, "t"w, "Title"w);
    assert(z8_field_aggregation(expression) == Z8FieldAggregation.array);
    P.m_fields(table);
    assert(z8_field_sql_format(expression, Z8SqlVendor.Postgres) ==
        `json_strip_nulls(json_build_object('amount', t."Amount", 'title', t."Title"))`w);
    auto dependencies = z8_field_query_dependencies(expression);
    assert(dependencies.length == 3 && dependencies.canFind(table.f_amount) && dependencies.canFind(table.f_title));
    P.m_named(table);
    auto sql = z8_field_sql_format(expression, Z8SqlVendor.Postgres);
    assert(sql.canFind("'count', 7"w) && sql.canFind("'name', 'Ada'"w));
    assert(z8_field_query_dependencies(expression).length == 1);
    z8_field_set(expression, z8_primary_box(`{"title":"hello"}`w));
    assert(P.m_title(table) == "hello"w);
    z8_field_set(expression, z8_primary_box(`[{"title":"one"},{"title":"two"}]`w));
    auto values = P.m_array(table);
    assert(values.z8_size() == 2 && values.z8_get(1).m_getString("title"w) == "two"w);
    z8_field_set(expression, z8_primary_box(`[null]`w));
    bool rejected; try { P.m_array(table); } catch (Exception) { rejected = true; } assert(rejected);
}
''', encoding="utf-8")
    executable = temp / ("json-expression.exe" if os.name == "nt" else "json-expression")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("JsonObjectExpression SQL, dependencies and values verified")
