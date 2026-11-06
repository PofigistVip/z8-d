"""Check conditional expressions mixing scalar and SQL branch types."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "SqlValue.bl").write_text('''
public class SqlValue {
    static int conversions;
    public operator sql_int() { conversions += 1; return 27; }
    public static int count() { return conversions; }
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    static int effects;
    private static bool effect() { effects += 1; return true; }
    public static sql_bool flag(bool condition, sql_bool value) { return condition ? false : value; }
    public static sql_bool lazy(bool condition, sql_bool value) { return condition ? effect() : value; }
    public static int effectsCount() { return effects; }
    public static sql_int integer(bool condition, sql_int value) { return condition ? value : 42; }
    public static sql_decimal numeric(bool condition, sql_decimal value) { return condition ? 2.5 : value; }
    public static sql_string text(bool condition, sql_string value) { return condition ? "yes" : value; }
    public static sql_guid id(bool condition, sql_guid value) { return condition ? guid.create(7) : value; }
    public static sql_decimal promote(bool condition, sql_int value, sql_decimal decimal) { return condition ? value : decimal; }
    public static sql_int userValue(bool condition, SqlValue value, sql_int fallback) { return condition ? value : fallback; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
import z8gen.SqlValue;
void main() {
    alias P = Z8p_50726F6265;
    auto flag = z8_sql_bool_const(true);
    assert(P.m_flag(true, flag).left.kind == Z8SqlBoolKind.constant);
    assert(!P.m_flag(true, flag).left.constant);
    assert(P.m_flag(false, flag).left is flag);
    assert(z8_optional_require(P.m_effectsCount()) == 0);
    P.m_lazy(false, flag);
    assert(z8_optional_require(P.m_effectsCount()) == 0);
    P.m_lazy(true, flag);
    assert(z8_optional_require(P.m_effectsCount()) == 1);
    auto number = z8_sql_int_const(3);
    assert(P.m_integer(true, number).left is number);
    assert(P.m_integer(false, number).left.constant == 42);
    auto decimal = z8_sql_decimal_const(z8_decimal_parse("9.5"w));
    assert((cast(Z8SqlDecimal)P.m_numeric(false, decimal).left) is decimal);
    assert((cast(Z8SqlDecimal)P.m_numeric(true, decimal).left).constant.z8_string() == "2.5"w);
    auto text = z8_sql_string_const("no"w);
    assert(P.m_text(false, text).left is text);
    assert(P.m_text(true, text).left.constant == "yes"w);
    auto id = z8_sql_guid_const(z8_guid_create(1));
    assert(P.m_id(false, id).left is id);
    assert(P.m_id(true, id).left.constant.minorBits == 7);
    assert((cast(Z8SqlDecimal)P.m_promote(true, number, decimal).left).kind == Z8SqlDecimalKind.fromInt);
    auto value = z8_new!Z8p_53716C56616C7565();
    assert(P.m_userValue(false, value, number).left is number);
    assert(z8_optional_require(Z8p_53716C56616C7565.m_count()) == 0);
    assert(P.m_userValue(true, value, number) !is null);
    assert(z8_optional_require(Z8p_53716C56616C7565.m_count()) == 1);
}
''', encoding="utf-8")
    executable = temp / ("sql-conditional.exe" if os.name == "nt" else "sql-conditional")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Conditional SQL conversions and lazy branch evaluation verified")
