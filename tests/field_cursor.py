"""Exercise the host cursor contract and Field value precedence."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/field_cursor.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.IntExpression;
import org.zenframework.z8.base.table.value.BoolField;
import org.zenframework.z8.base.table.value.DecimalField;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.DateField;
public class Probe {
    public static IntField number() { IntField f; f.defaultValue = 4; return f; }
    public static StringField text() { StringField f; f.defaultValue = "default"; return f; }
    public static IntExpression expression() { IntExpression f; f.setDefault(7); return f; }
    public static BoolField flagField() { BoolField f; return f; }
    public static DecimalField decimalField() { DecimalField f; return f; }
    public static GuidField guidField() { GuidField f; return f; }
    public static DateField dateField() { DateField f; return f; }
    public static void assign(IntField f, int value) { f = value; }
    public static int primary(IntField f) { return f.int(); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
class Cursor : IZ8FieldCursor {
    bool closed, grouped, nullValue, lastArray;
    long reads;
    Z8Primary value;
    bool isClosed() { return closed; }
    bool isGrouped() { return grouped; }
    Z8Primary read(Z8Object field, bool asArray, out bool wasNull) {
        ++reads; wasNull = nullValue; lastArray = asArray; return value;
    }
}
void main() {
    alias P = Z8p_50726F6265;
    auto number = P.m_number(); auto text = P.m_text(); auto expression = P.m_expression();
    auto cursor = new Cursor(); cursor.value = z8_primary_box(23L);
    z8_field_set_cursor(number, cursor);
    assert(z8_optional_require(number.m_get()) == 23 && cursor.reads == 1);
    assert(z8_optional_require(number.m_getDefault()) == 4 && cursor.reads == 1);
    assert(!z8_optional_require(number.m_wasNull()));
    assert(z8_optional_require(P.m_primary(number)) == 23 && cursor.reads == 2);
    cursor.nullValue = true; cursor.value = z8_primary_box(0L);
    assert(z8_optional_require(number.m_get()) == 0 && z8_optional_require(number.m_wasNull()));
    P.m_assign(number, z8_optional_wrap(99L));
    auto previous = cursor.reads;
    assert(z8_optional_require(number.m_get()) == 99 && cursor.reads == previous);
    z8_field_reset(number); cursor.nullValue = false; cursor.value = z8_primary_box(31L);
    assert(z8_optional_require(number.m_get()) == 31 && !z8_optional_require(number.m_wasNull()));
    cursor.closed = true; previous = cursor.reads;
    assert(z8_optional_require(number.m_get()) == 4 && cursor.reads == previous);
    cursor.closed = false; cursor.grouped = true; z8_field_set_aggregation(number, Z8FieldAggregation.array);
    assert(!number.m_get().present && cursor.reads == previous);
    assert(!P.m_primary(number).present);
    cursor.grouped = false;
    z8_field_set_cursor(number, null);
    assert(z8_optional_require(number.m_get()) == 4);
    cursor.value = z8_primary_box("row"w); cursor.nullValue = false;
    z8_field_set_cursor(text, cursor);
    assert(text.m_get() == "row"w && text.m_getDefault() == "default"w);
    cursor.value = z8_primary_box(77L); cursor.nullValue = true;
    z8_field_set_cursor(expression, cursor);
    assert(z8_optional_require(expression.m_get()) == 77 && !z8_optional_require(expression.m_wasNull()));
    cursor.nullValue = false; cursor.grouped = true;
    z8_field_set_cursor(number, cursor); z8_field_set_aggregation(number, Z8FieldAggregation.array);
    cursor.value = z8_primary_box(`[1,2,"3L"]`w);
    auto numbers = number.m_array();
    assert(cursor.lastArray && numbers.z8_size() == 3 && numbers.z8_get(0) == 1 && numbers.z8_get(2) == 3);
    assert(!number.m_get().present);
    z8_field_set_cursor(expression, cursor); z8_field_set_aggregation(expression, Z8FieldAggregation.distinct);
    auto values = expression.m_array(); assert(values.z8_size() == 3 && values.z8_get(1) == 2);
    z8_field_set_aggregation(text, Z8FieldAggregation.array); cursor.value = z8_primary_box(`["first",null,42]`w);
    assert(text.m_get() == `["first",null,42]`w && cursor.lastArray);
    auto strings = text.m_array();
    assert(strings.z8_size() == 3 && strings.z8_get(0) == "first"w && strings.z8_get(1) is null && strings.z8_get(2) == "42"w);
    auto flag = P.m_flagField(); z8_field_set_cursor(flag, cursor); z8_field_set_aggregation(flag, Z8FieldAggregation.array);
    cursor.value = z8_primary_box(`[true,false,null,"yes"]`w);
    auto bools = flag.m_array(); assert(bools.z8_size() == 4 && bools.z8_get(0) && !bools.z8_get(1) && !bools.z8_get(2) && bools.z8_get(3));
    auto amount = P.m_decimalField(); z8_field_set_cursor(amount, cursor); z8_field_set_aggregation(amount, Z8FieldAggregation.array);
    cursor.value = z8_primary_box(`[1.25,"2",""]`w);
    auto decimals = amount.m_array(); assert(decimals.z8_size() == 3 && decimals.z8_get(0) == z8_decimal_parse("1.25"w) && decimals.z8_get(2) == z8_decimal_from_int(0));
    auto id = P.m_guidField(); z8_field_set_cursor(id, cursor); z8_field_set_aggregation(id, Z8FieldAggregation.array);
    cursor.value = z8_primary_box(`[null,"00000000-0000-0000-0000-000000000005"]`w);
    auto ids = id.m_array(); assert(ids.z8_size() == 2 && ids.z8_get(0) == z8_guid_zero() && ids.z8_get(1) == z8_guid_create(5));
    auto day = P.m_dateField(); z8_field_set_cursor(day, cursor); z8_field_set_aggregation(day, Z8FieldAggregation.array);
    cursor.value = z8_primary_box(`[0,1234]`w);
    auto dates = day.m_array(); assert(dates.z8_size() == 2 && z8_date_ticks(dates.z8_get(1)) == 1234);
}
''', encoding="utf-8")
    exe = temp / ("field-cursor.exe" if os.name == "nt" else "field-cursor")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Field cursor reads, defaults, changes, grouping and null flags verified")
