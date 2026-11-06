"""Exercise named BL conversion operators on the built-in SQL scalar types."""
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
    (source / "Probe.bl").write_text('''
public class Probe {
    static int calls;
    private static guid next() { calls += 1; return guid.create(7); }
    public static int count() { return calls; }
    public static sql_bool flag(bool value) { return value.sql_bool(); }
    public static sql_int integer(int value) { return value.sql_int(); }
    public static sql_decimal number(decimal value) { return value.sql_decimal(); }
    public static sql_string text(string value) { return value.sql_string(); }
    public static sql_guid id(guid value) { return value.sql_guid(); }
    public static sql_guid evaluatedOnce() { return next().sql_guid(); }
    public static sql_date day(date value) { return value.sql_date(); }
    public static sql_datespan span(datespan value) { return value.sql_datespan(); }
    public static sql_geometry shape(geometry value) { return value.sql_geometry(); }
    public static sql_decimal widen(sql_int value) { return value.sql_decimal(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
void main() {
    alias P = Z8p_50726F6265;
    assert(P.m_flag(true).left.constant);
    assert(P.m_integer(42).left.constant == 42);
    assert((cast(Z8SqlDecimal)P.m_number(z8_decimal_parse("2.5"w)).left).constant.z8_string() == "2.5"w);
    assert(P.m_text("test"w).left.constant == "test"w);
    auto id = z8_guid_create(9); assert(P.m_id(id).left.constant is id);
    assert(P.m_evaluatedOnce().left.constant.minorBits == 7 && z8_optional_require(P.m_count()) == 1);
    auto day = z8_date_from_ticks(0); assert(P.m_day(day).left.constant is day);
    auto span = new Z8Datespan(1000); assert(P.m_span(span).left.constant is span);
    auto shape = new Z8Geometry(); assert(P.m_shape(shape).left.constant is shape);
    auto integer = z8_sql_int_const(5);
    assert((cast(Z8SqlDecimal)P.m_widen(integer).left).kind == Z8SqlDecimalKind.fromInt);
    bool failed; try { P.m_id(null); } catch (Exception) { failed = true; } assert(failed);
    failed = false; try { P.m_integer(Z8Optional!long.init); } catch (Exception) { failed = true; } assert(failed);
}
''', encoding="utf-8")
    executable = temp / ("sql-named-conversions.exe" if os.name == "nt" else "sql-named-conversions")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Named scalar-to-SQL conversion operators verified")
