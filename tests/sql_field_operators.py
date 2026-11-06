"""Run operators that convert native BL fields into SQL expression values."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    declarations = {
        "GuidField": '[native "example.GuidField"] public class GuidField { public operator sql_guid(); }',
        "IntField": '[native "example.IntField"] public class IntField { public operator sql_int(); }',
        "TextField": '[native "example.TextField"] public class TextField { public operator sql_string(); }',
        "BoolField": '[native "example.BoolField"] public class BoolField { public operator sql_bool(); }',
        "DecimalField": '[native "example.DecimalField"] public class DecimalField { public operator sql_decimal(); }',
        "DirectUnary": '[native "example.DirectUnary"] public class DirectUnary { public operator sql_bool(); public bool operator ! (); }',
        "Direct": '[native "example.Direct"] public class Direct { public operator sql_guid(); public bool operator != (guid value); }',
        "Probe": """
public class Probe {
    public static sql_bool guid(GuidField field, guid value) { return field != value; }
    public static sql_bool fields(GuidField left, GuidField right) { return left == right; }
    public static sql_bool rightGuid(guid left, GuidField right) { return left != right; }
    public static sql_int add(IntField field, int value) { return field + value; }
    public static sql_int rightInt(int value, IntField field) { return value + field; }
    public static sql_bool check(IntField field, int value) { return field > value; }
    public static sql_string named(TextField field) { return field.sql_string(); }
    public static bool direct(Direct field, guid value) { return field != value; }
    public static sql_bool negate(BoolField field) { return !field; }
    public static sql_int complement(IntField field) { return ~field; }
    public static sql_int negativeInt(IntField field) { return -field; }
    public static sql_decimal negativeDecimal(DecimalField field) { return -field; }
    public static bool directUnary(DirectUnary field) { return !field; }
    public static sql_string chooseFields(sql_bool condition, TextField yes, TextField no) { return condition.IIF(yes, no); }
}
""",
    }
    for name, code in declarations.items():
        (source / (name + ".bl")).write_text(code, encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    adapter = temp / "adapter.d"
    adapter.write_text("""
module adapter;
import z8.runtime;
__gshared int guidCalls, intCalls, stringCalls, directCalls, boolCalls, decimalCalls, unaryCalls;
Z8SqlGuid asGuid(Z8Object self) {
    ++guidCalls; return z8_sql_guid_const(z8_guid_literal("00000000-0000-0000-0000-000000000001"));
}
Z8SqlInt asInt(Z8Object self) { ++intCalls; return z8_sql_int_const(7); }
Z8SqlString asText(Z8Object self) { ++stringCalls; return z8_sql_string_const("Hello"w); }
Z8SqlBool asBool(Z8Object self) { ++boolCalls; return z8_sql_bool_const(true); }
Z8SqlDecimal asDecimal(Z8Object self) { ++decimalCalls; return z8_sql_decimal_const(z8_decimal_parse("2.5"w)); }
Z8Optional!bool directUnary(Z8Object self) { ++unaryCalls; return z8_optional_wrap(false); }
Z8Optional!bool notEqual(Z8Object self, Z8Guid value) { ++directCalls; return z8_optional_wrap(true); }
void bind() {
    z8_native_bind("example.GuidField.z8cast_sql_guid"w, &asGuid);
    z8_native_bind("example.IntField.z8cast_sql_int"w, &asInt);
    z8_native_bind("example.TextField.z8cast_sql_string"w, &asText);
    z8_native_bind("example.BoolField.z8cast_sql_bool"w, &asBool);
    z8_native_bind("example.DecimalField.z8cast_sql_decimal"w, &asDecimal);
    z8_native_bind("example.DirectUnary.z8cast_sql_bool"w, &asBool);
    z8_native_bind("example.DirectUnary.z8op_not"w, &directUnary);
    z8_native_bind("example.Direct.z8cast_sql_guid"w, &asGuid);
    z8_native_bind("example.Direct.z8op_not_equal"w, &notEqual);
}
""", encoding="utf-8")
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.Probe;
import z8gen.GuidField;
import z8gen.IntField;
import z8gen.TextField;
import z8gen.Direct;
import z8gen.BoolField;
import z8gen.DecimalField;
import z8gen.DirectUnary;
import adapter;
void main() {
    alias P = Z8p_50726F6265;
    auto g = z8_new!Z8p_477569644669656C64();
    auto i = z8_new!Z8p_496E744669656C64();
    auto s = z8_new!Z8p_546578744669656C64();
    auto d = z8_new!Z8p_446972656374();
    auto b = z8_new!Z8p_426F6F6C4669656C64();
    auto decimal = z8_new!Z8p_446563696D616C4669656C64();
    auto directUnary = z8_new!Z8p_446972656374556E617279();
    auto id = z8_guid_literal("00000000-0000-0000-0000-000000000002");
    bind();
    assert(z8_sql_bool_format(P.m_guid(g, id), true) ==
        "'00000000-0000-0000-0000-000000000001'<>'00000000-0000-0000-0000-000000000002'"w);
    assert(z8_sql_bool_format(P.m_fields(g, g), true) ==
        "'00000000-0000-0000-0000-000000000001'='00000000-0000-0000-0000-000000000001'"w);
    assert(z8_sql_bool_format(P.m_rightGuid(id, g), true) ==
        "'00000000-0000-0000-0000-000000000002'<>'00000000-0000-0000-0000-000000000001'"w);
    assert(guidCalls == 4);
    assert(z8_sql_int_format(P.m_add(i, 5)) == "(7 + 5)"w);
    assert(z8_sql_int_format(P.m_rightInt(5, i)) == "(5 + 7)"w);
    assert(z8_sql_bool_format(P.m_check(i, 5), true) == "7>5"w && intCalls == 3);
    assert(z8_sql_string_format(P.m_named(s)) == "('Hello')"w && stringCalls == 1);
    assert(z8_optional_require(P.m_direct(d, id)) && directCalls == 1 && guidCalls == 4);
    assert(P.m_negate(b).left.kind == Z8SqlBoolKind.not && boolCalls == 1);
    assert(P.m_complement(i).left.kind == Z8SqlIntKind.bitNot);
    assert(P.m_negativeInt(i).left.kind == Z8SqlIntKind.negate && intCalls == 5);
    assert((cast(Z8SqlDecimal)P.m_negativeDecimal(decimal).left).kind == Z8SqlDecimalKind.negate && decimalCalls == 1);
    assert(!z8_optional_require(P.m_directUnary(directUnary)) && unaryCalls == 1 && boolCalls == 1);
    assert(P.m_chooseFields(z8_sql_bool_const(true), s, s) !is null && stringCalls == 3);
}
""", encoding="utf-8")
    adapter_object = temp / ("adapter.obj" if os.name == "nt" else "adapter.o")
    subprocess.run(["dmd", "-c", *import_args(), str(adapter), "-of=" + str(adapter_object)], cwd=temp, check=True)
    executable = temp / ("sql-field.exe" if os.name == "nt" else "sql-field")
    subprocess.run(["dmd", "-I" + str(generated), "-I" + str(temp), *import_args(),
                    *map(str, generated.rglob("*.d")), str(harness), str(adapter_object),
                    str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Ambiguous.bl").write_text('''
[native "example.Ambiguous"] public class Ambiguous { public operator bool(); public operator sql_bool(); }
''', encoding="utf-8")
    (source / "Bad.bl").write_text('''
public class Bad { public static void run(Ambiguous value) { !value; } }
''', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0 or "ambiguous unary operator" not in result.stderr:
        raise SystemExit("Missing ambiguity diagnostic for unary conversion: " + result.stderr)
    (source / "Ambiguous.bl").write_text('''
[native "example.Ambiguous"] public class Ambiguous { public operator sql_int(); public operator sql_decimal(); }
''', encoding="utf-8")
    (source / "Bad.bl").write_text('''
public class Bad { public static sql_int run(sql_bool condition, Ambiguous value) { return condition.IIF(value, value); } }
''', encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-iif")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0 or "ambiguous SQL IIF overload" not in result.stderr:
        raise SystemExit("Missing ambiguity diagnostic for SQL IIF: " + result.stderr)
print("SQL field conversions, unary and binary operators, and named casts verified")
