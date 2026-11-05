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
public class Probe {
    public static IntField number() { IntField f; f.defaultValue = 4; return f; }
    public static StringField text() { StringField f; f.defaultValue = "default"; return f; }
    public static IntExpression expression() { IntExpression f; f.setDefault(7); return f; }
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
    bool closed, grouped, nullValue;
    long reads;
    Z8Primary value;
    bool isClosed() { return closed; }
    bool isGrouped() { return grouped; }
    Z8Primary read(Z8Object field, out bool wasNull) {
        ++reads; wasNull = nullValue; return value;
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
}
''', encoding="utf-8")
    exe = temp / ("field-cursor.exe" if os.name == "nt" else "field-cursor")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Field cursor reads, defaults, changes, grouping and null flags verified")
