"""Compare SQL field references with Java when query aggregation is disabled."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2: raise SystemExit("Usage: python tests/sql_field_reference_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
if not language.is_dir(): raise SystemExit("Original BL standard library not found")
jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.value.Field;
import org.zenframework.z8.base.table.value.IntField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.table.value.BoolField;
import org.zenframework.z8.base.table.value.DecimalField;
import org.zenframework.z8.base.table.value.GuidField;
public class Probe {
    public static IntField number() { IntField value; return value; }
    public static StringField text() { StringField value; return value; }
    public static BoolField flag() { BoolField value; return value; }
    public static DecimalField amount() { DecimalField value; return value; }
    public static GuidField id() { GuidField value; return value; }
    public static sql_int numberSql(IntField value) { return value.sql_int(); }
    public static sql_string textSql(StringField value) { return value.sql_string(); }
    public static sql_bool flagSql(BoolField value) { return value.sql_bool(); }
    public static sql_decimal amountSql(DecimalField value) { return value.sql_decimal(); }
    public static sql_guid idSql(GuidField value) { return value.sql_guid(); }
    public static sql_bool isNull(Field value) { return value.sqlIsNull(); }
    public static sql_bool greater(IntField value) { return value > 5; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "SqlFieldOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.value.*;
import org.zenframework.z8.server.db.DatabaseVendor;
import org.zenframework.z8.server.db.sql.*;
import org.zenframework.z8.server.types.sql.*;
public class SqlFieldOracle {
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        IntegerField number = new IntegerField(null); StringField text = new StringField(null);
        BoolField flag = new BoolField(null); DecimalField amount = new DecimalField(null); GuidField id = new GuidField(null);
        FormatOptions options = new FormatOptions(); options.disableAggregation();
        for (Field f : new Field[] {number, text, flag, amount, id}) options.setFieldAlias(f, "T.col");
        SqlToken[] values = {number.sql_int().operatorPriority(), text.sql_string().operatorPriority(),
                             flag.sql_bool().operatorPriority(), amount.sql_decimal().operatorPriority(), id.sql_guid().operatorPriority(),
                             number.z8_sqlIsNull().operatorPriority(), number.sql_int().operatorMore(new sql_integer(5))};
        for (DatabaseVendor vendor : new DatabaseVendor[] {DatabaseVendor.Oracle, DatabaseVendor.SqlServer, DatabaseVendor.Postgres, DatabaseVendor.H2})
            for (int i = 0; i < values.length; i++) for (boolean logical : new boolean[] {false, true})
                System.out.println(vendor + ":" + i + ":" + logical + ":" + values[i].format(vendor, options, logical));
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", cp, str(java)], check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "SqlFieldOracle"], text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
void main() {
    alias P = Z8p_50726F6265;
    auto number = P.m_number(); auto text = P.m_text(); auto flag = P.m_flag();
    auto amount = P.m_amount(); auto id = P.m_id();
    auto intSql = P.m_numberSql(number); bool missing;
    try { z8_sql_int_format(intSql); } catch (Exception) { missing = true; }
    assert(missing);
    foreach (field; [cast(Z8Object)number, cast(Z8Object)text, cast(Z8Object)flag, cast(Z8Object)amount, cast(Z8Object)id])
        z8_field_bind_sql(field, null, null, "T.col"w);
    auto stringSql = P.m_textSql(text); auto boolSql = P.m_flagSql(flag);
    auto decimalSql = P.m_amountSql(amount); auto guidSql = P.m_idSql(id);
    auto nullSql = P.m_isNull(number); auto greater = P.m_greater(number);
    foreach (vendor; [Z8SqlVendor.Oracle, Z8SqlVendor.SqlServer, Z8SqlVendor.Postgres, Z8SqlVendor.H2])
        foreach (i; 0 .. 7) foreach (logical; [false, true]) {
            wstring result;
            switch (i) {
                case 0: result = z8_sql_int_format(intSql, vendor, logical); break;
                case 1: result = z8_sql_string_format(stringSql, vendor); break;
                case 2: result = z8_sql_bool_format(boolSql, logical, vendor); break;
                case 3: result = z8_sql_decimal_format(decimalSql, vendor, logical); break;
                case 4: result = z8_sql_guid_format(guidSql, vendor); break;
                case 5: result = z8_sql_bool_format(nullSql, logical, vendor); break;
                case 6: result = z8_sql_bool_format(greater, logical, vendor); break;
                default: assert(0);
            }
            writeln(vendor, ":", i, ":", logical, ":", result.to!string);
        }
    z8_field_bind_sql(number, "t"w, `a"b`w);
    assert(z8_sql_int_format(intSql, Z8SqlVendor.Postgres) == `(t."a""b")`w);
    assert(z8_sql_int_format(intSql, Z8SqlVendor.SqlServer) == `(t.[a"b])`w);
}
''', encoding="utf-8")
    exe = temp / ("sql-field.exe" if os.name == "nt" else "sql-field")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    actual = subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()
    if actual != expected: raise SystemExit(f"SQL field formatting differs:\nD: {actual}\nJava: {expected}")
print("SQL field references match Java Z8 without aggregation")
