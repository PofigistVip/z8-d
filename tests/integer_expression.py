"""Exercise BL integer expression fields and lazy SQL expressions."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/integer_expression.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Custom.bl").write_text('''
import org.zenframework.z8.base.table.value.IntExpression;
public class Custom extends IntExpression {
    public int calls = 0;
    virtual protected sql_int expression() { calls += 1; return 42; }
    virtual public int get() { return 99; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.IntExpression;
import org.zenframework.z8.base.table.value.Aggregation;
public class Probe {
    public static IntExpression make() { IntExpression result; return result; }
    public static Custom custom() { Custom result; return result; }
    public static IntField input() { IntField result; return result; }
    public static sql_int asSql(IntExpression value) { return value.sql_int(); }
    public static void setDefault(IntExpression value, int v) { value.setDefault(v); }
    public static void setExpression(IntExpression value, IntField field) { value.setExpression(field + 3); }
    public static void assign(IntExpression value, IntField field) { value = field + 5; }
    public static void reset(IntExpression value) { value.setExpression(null); }
    public static bool values(IntExpression value) { return value.get() == 0 && !value.wasNull() && value.aggregation == Aggregation.Sum && value.format == "0,000"; }
    public static int dynamicValue(IntExpression value) { return value.int(); }
    public static int calls(Custom value) { return value.calls; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
void main() {
    alias P = Z8p_50726F6265;
    auto value = P.m_make(); auto input = P.m_input(); auto custom = P.m_custom();
    assert(z8_optional_require(P.m_values(value)));
    assert(z8_optional_require(P.m_dynamicValue(custom)) == 99);
    z8_field_bind_sql(input, null, null, "T.amount"w);
    auto sql = P.m_asSql(value); auto customSql = P.m_asSql(custom);
    P.m_setDefault(value, z8_optional_wrap(8L));
    assert(z8_sql_int_format(sql) == "(8)"w);
    P.m_setDefault(value, z8_optional_wrap(9L));
    assert(z8_sql_int_format(sql) == "(8)"w); // expression is cached
    P.m_setExpression(value, input);
    assert(z8_sql_int_format(sql) == "(T.amount + 3)"w);
    P.m_assign(value, input);
    assert(z8_sql_int_format(sql) == "(T.amount + 5)"w);
    P.m_reset(value);
    assert(z8_sql_int_format(sql) == "(9)"w);
    assert(z8_sql_int_format(customSql) == "((42))"w);
    assert(z8_sql_int_format(customSql) == "((42))"w && z8_optional_require(P.m_calls(custom)) == 1);
    z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
    P.m_setExpression(value, input);
    assert(z8_sql_int_format(sql) == "(sum(T.amount + 3))"w);
    z8_field_bind_sql(value, null, null, "Q.alias"w);
    assert(z8_sql_int_format(sql) == "(sum(Q.alias))"w);
    z8_field_bind_sql(value, null, null);
    value.m_setExpression(P.m_asSql(value));
    bool recursive;
    try { z8_sql_int_format(sql); } catch (Exception) { recursive = true; }
    assert(recursive);
    P.m_reset(value);
    assert(z8_sql_int_format(sql) == "(sum(9))"w);
}
''', encoding="utf-8")
    exe = temp / ("integer-expression.exe" if os.name == "nt" else "integer-expression")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Integer expression defaults, overrides, SQL and caching verified")
