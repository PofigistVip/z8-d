"""Exercise typed Expression fields using the original BL declarations."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/typed_expressions.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomText.bl").write_text('''
import org.zenframework.z8.base.table.value.StringExpression;
public class CustomText extends StringExpression {
    public int calls = 0;
    virtual protected sql_string expression() { calls += 1; return "derived"; }
    virtual public string get() { return "override"; }
}
''', encoding="utf-8")
    types = ("BoolExpression", "DecimalExpression", "StringExpression", "TextExpression", "FileExpression",
             "GuidExpression", "DatetimeExpression", "DateExpression", "DatespanExpression", "GeometryExpression")
    imports = "".join(f"import org.zenframework.z8.base.table.value.{name};\n" for name in types)
    factories = "\n".join(f"public static {name} make{name}() {{ {name} value; return value; }}" for name in types)
    (source / "Probe.bl").write_text(imports + '''
public class Probe {
''' + factories + '''
    public static CustomText custom() { CustomText value; return value; }
    public static bool check() {
        BoolExpression b; DecimalExpression d; StringExpression s; TextExpression t; FileExpression f;
        GuidExpression g; DatetimeExpression dt; DateExpression day; DatespanExpression span; GeometryExpression shape;
        if (b.get() || b.width != 5 || b.wasNull()) return false;
        b.setDefault(true); if (!b.get()) return false;
        if (d.get() != 0 || d.format != "0,000.00") return false;
        d.setDefault(1.25); if (d.get() != 1.25) return false;
        if (s.get() != "" || t.get() != "" || f.get() != "") return false;
        s.setDefault("s"); t.setDefault("t"); f.setDefault("f");
        if (s.get() != "s" || t.get() != "t" || f.get() != "f") return false;
        if (g.get() != guid.Null || dt.get() != date.Min || day.get() != date.Min) return false;
        if (dt.format != "d.m.Y H:i" || day.format != "d.m.Y") return false;
        if (span.get() != '0 00:00:00' || shape.get().srs() != geometry.DefaultSRS) return false;
        day = '01/01/2024'; span = '1 00:00:00';
        if (day.get().year() != 2024 || span.get() != '1 00:00:00') return false;
        CustomText custom; StringExpression base = custom;
        return base.string() == "override" && !base.wasNull();
    }
    public static sql_string customSql(CustomText value) { return value.sql_string(); }
    public static void boolAssign(BoolExpression value, sql_bool sql) { value = sql; }
    public static void textAssign(TextExpression value, sql_string sql) { value = sql; }
    public static int calls(CustomText value) { return value.calls; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
void main() {
    alias P = Z8p_50726F6265;
    assert(z8_optional_require(P.m_check()));
    auto b = P.m_makeBoolExpression(); auto d = P.m_makeDecimalExpression();
    auto s = P.m_makeStringExpression(); auto t = P.m_makeTextExpression(); auto f = P.m_makeFileExpression();
    auto g = P.m_makeGuidExpression(); auto dt = P.m_makeDatetimeExpression(); auto day = P.m_makeDateExpression();
    auto span = P.m_makeDatespanExpression(); auto shape = P.m_makeGeometryExpression();
    assert(z8_field_sql_format(b, Z8SqlVendor.Postgres) == "0"w);
    assert(z8_field_sql_format(d, Z8SqlVendor.Postgres) == "0"w);
    assert(z8_field_sql_format(s, Z8SqlVendor.Postgres) == "''"w);
    assert(z8_field_sql_format(t, Z8SqlVendor.Postgres) == "''"w);
    assert(z8_field_sql_format(f, Z8SqlVendor.Postgres) == "''"w);
    assert(z8_field_sql_format(g, Z8SqlVendor.Postgres) == "'00000000-0000-0000-0000-000000000000'"w);
    assert(z8_field_sql_format(dt, Z8SqlVendor.Postgres) == z8_field_sql_format(day, Z8SqlVendor.Postgres));
    assert(z8_field_sql_format(span, Z8SqlVendor.Postgres) == "0"w);
    P.m_boolAssign(b, z8_sql_bool_const(true));
    d.m_setExpression(z8_sql_decimal_const(z8_decimal_parse("12.5"w)));
    s.m_setExpression(z8_sql_string_const("alpha"w)); P.m_textAssign(t, z8_sql_string_const("beta"w));
    f.m_setExpression(z8_sql_string_const("file"w)); g.m_setExpression(z8_sql_guid_const(z8_guid_create(5)));
    dt.m_setExpression(z8_sql_date_const(z8_date_from_ticks(1234))); day.m_setExpression(z8_sql_date_const(z8_date_from_ticks(1234)));
    span.m_setExpression(z8_sql_datespan_const(new Z8Datespan(1234)));
    shape.m_setExpression(z8_sql_geometry_const(z8_geometry_point(z8_decimal_from_int(1), z8_decimal_from_int(2), 4326)));
    assert(z8_field_sql_format(b, Z8SqlVendor.Postgres) == "1"w);
    assert(z8_field_sql_format(b, Z8SqlVendor.Postgres, true) == "1=1"w);
    assert(z8_field_sql_format(d, Z8SqlVendor.Postgres) == "12.5"w);
    assert(z8_field_sql_format(s, Z8SqlVendor.Postgres) == "'alpha'"w);
    assert(z8_field_sql_format(t, Z8SqlVendor.Postgres) == "'beta'"w);
    assert(z8_field_sql_format(f, Z8SqlVendor.Postgres) == "'file'"w);
    assert(z8_field_sql_format(g, Z8SqlVendor.Postgres) == "'00000000-0000-0000-0000-000000000005'"w);
    assert(z8_field_sql_format(dt, Z8SqlVendor.Postgres) == "1234"w);
    assert(z8_field_sql_format(day, Z8SqlVendor.Postgres) == "1234"w);
    assert(z8_field_sql_format(span, Z8SqlVendor.Postgres) == "1234"w);
    assert(z8_field_sql_format(shape, Z8SqlVendor.Postgres).length != 0);
    z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
    assert(z8_field_sql_format(b, Z8SqlVendor.Postgres, true) == "max(1=1)"w);
    assert(z8_field_sql_format(t, Z8SqlVendor.Postgres) == "max(CONVERT_FROM('beta', 'UTF8'))"w);
    assert(z8_field_sql_format(g, Z8SqlVendor.Postgres) == "max('00000000-0000-0000-0000-000000000005'::text)::uuid"w);
    z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
    auto custom = P.m_custom(); auto sql = P.m_customSql(custom);
    assert(z8_sql_string_format(sql) == "(('derived'))"w);
    assert(z8_sql_string_format(sql) == "(('derived'))"w && z8_optional_require(P.m_calls(custom)) == 1);
}
''', encoding="utf-8")
    exe = temp / ("typed-expressions.exe" if os.name == "nt" else "typed-expressions")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Typed expression defaults, overrides and SQL verified")
