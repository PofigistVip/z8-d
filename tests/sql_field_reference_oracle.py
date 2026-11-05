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
import org.zenframework.z8.base.table.value.DateField;
import org.zenframework.z8.base.table.value.DatespanField;
import org.zenframework.z8.base.table.value.BinaryField;
import org.zenframework.z8.base.table.value.GeometryField;
import org.zenframework.z8.base.table.value.TextField;
import org.zenframework.z8.base.table.value.FileField;
public class Probe {
    public static IntField number() { IntField value; return value; }
    public static StringField text() { StringField value; return value; }
    public static BoolField flag() { BoolField value; return value; }
    public static DecimalField amount() { DecimalField value; return value; }
    public static GuidField id() { GuidField value; return value; }
    public static DateField dateField() { DateField value; return value; }
    public static DatespanField duration() { DatespanField value; return value; }
    public static BinaryField bytes() { BinaryField value; return value; }
    public static GeometryField geometryField() { GeometryField value; return value; }
    public static TextField longText() { TextField value; return value; }
    public static FileField file() { FileField value; return value; }
    public static sql_int numberSql(IntField value) { return value.sql_int(); }
    public static sql_string textSql(StringField value) { return value.sql_string(); }
    public static sql_bool flagSql(BoolField value) { return value.sql_bool(); }
    public static sql_decimal amountSql(DecimalField value) { return value.sql_decimal(); }
    public static sql_guid idSql(GuidField value) { return value.sql_guid(); }
    public static sql_bool isNull(Field value) { return value.sqlIsNull(); }
    public static sql_bool greater(IntField value) { return value > 5; }
    public static sql_date dateSql(DateField value) { return value.sql_date(); }
    public static sql_datespan spanSql(DatespanField value) { return value.sql_datespan(); }
    public static sql_binary binarySql(BinaryField value) { return value.sql_binary(); }
    public static sql_geometry geometrySql(GeometryField value) { return value.sql_geometry(); }
    public static sql_string longTextSql(TextField value) { return value.sql_string(); }
    public static sql_string fileSql(FileField value) { return value.sql_string(); }
    public static sql_bool inVector(Field value, primary[] values) { return value.inVector(values); }
    public static sql_bool notInVector(Field value, primary[] values) { return value.notInVector(values); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    java = temp / "SqlFieldOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.value.*;
import org.zenframework.z8.server.db.DatabaseVendor;
import org.zenframework.z8.server.db.sql.*;
import org.zenframework.z8.server.types.sql.*;
import org.zenframework.z8.server.types.*;
import org.zenframework.z8.server.runtime.RCollection;
import java.util.Arrays;
public class SqlFieldOracle {
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        IntegerField number = new IntegerField(null); StringField text = new StringField(null);
        BoolField flag = new BoolField(null); DecimalField amount = new DecimalField(null); GuidField id = new GuidField(null);
        DateField dateField = new DateField(null); DatespanField duration = new DatespanField(null);
        BinaryField bytes = new BinaryField(null); GeometryField geometryField = new GeometryField(null);
        TextField longText = new TextField(null); FileField file = new FileField(null);
        FormatOptions options = new FormatOptions(); options.disableAggregation();
        for (Field f : new Field[] {number, text, flag, amount, id, dateField, duration, bytes, geometryField, longText, file}) options.setFieldAlias(f, "T.col");
        RCollection<primary> items = new RCollection<primary>(Arrays.asList(new integer(1), new string("O'Reilly"), new bool(true)));
        RCollection<primary> empty = new RCollection<primary>();
        RCollection<primary> mixed = new RCollection<primary>(Arrays.asList(new date(0), new datespan(1234), guid.create(5), new decimal("1.25"), new binary()));
        SqlToken[] values = {number.sql_int().operatorPriority(), text.sql_string().operatorPriority(),
                             flag.sql_bool().operatorPriority(), amount.sql_decimal().operatorPriority(), id.sql_guid().operatorPriority(),
                             number.z8_sqlIsNull().operatorPriority(), number.sql_int().operatorMore(new sql_integer(5)),
                             dateField.sql_date().operatorPriority(), duration.sql_datespan().operatorPriority(), bytes.sql_binary(),
                             geometryField.sql_geometry().operatorPriority(), longText.sql_string().operatorPriority(), file.sql_string().operatorPriority(),
                             number.z8_inVector(items).operatorPriority(), number.z8_notInVector(items).operatorPriority(),
                             number.z8_inVector(empty).operatorPriority(), number.z8_inVector(mixed).operatorPriority()};
        for (DatabaseVendor vendor : new DatabaseVendor[] {DatabaseVendor.Oracle, DatabaseVendor.SqlServer, DatabaseVendor.Postgres, DatabaseVendor.H2})
            for (int i = 0; i < values.length; i++) for (boolean logical : new boolean[] {false, true})
                System.out.println(vendor + ":" + i + ":" + logical + ":" + values[i].format(vendor, options, logical));
        options.enableAggregation();
        Aggregation[] aggregations = {Aggregation.None, Aggregation.Sum, Aggregation.Max, Aggregation.Min, Aggregation.Average,
            Aggregation.Count, Aggregation.Array, Aggregation.Distinct, Aggregation.Concat, Aggregation.BitwiseOr, Aggregation.BitwiseAnd};
        Field[] fields = {number, text, flag, amount, id, dateField, duration, bytes, geometryField, longText, file};
        for (boolean order : new boolean[] {false, true}) {
            options.setOrderBy(order);
            for (int a = 0; a < aggregations.length; a++) {
                for (Field f : fields) f.aggregation = aggregations[a];
                for (DatabaseVendor vendor : new DatabaseVendor[] {DatabaseVendor.Oracle, DatabaseVendor.SqlServer, DatabaseVendor.Postgres, DatabaseVendor.H2})
                    for (int i = 0; i < 13; i++) for (boolean logical : new boolean[] {false, true}) {
                        String result;
                        try { result = values[i].format(vendor, options, logical); } catch (RuntimeException error) { result = "ERROR"; }
                        System.out.println("A:" + order + ":" + a + ":" + vendor + ":" + i + ":" + logical + ":" + result);
                    }
            }
        }
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    aggregation_java = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/base/table/value/Aggregation.java"
    functions_java = original / "org.zenframework.z8.server/src/main/java/org/zenframework/z8/server/db/sql/functions"
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", cp, "-d", str(temp), str(aggregation_java),
                    str(functions_java / "Array.java"), str(functions_java / "Distinct.java"), str(java)], check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + cp, "SqlFieldOracle"], text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
import core.thread : Thread;
void main() {
    alias P = Z8p_50726F6265;
    auto number = P.m_number(); auto text = P.m_text(); auto flag = P.m_flag();
    auto amount = P.m_amount(); auto id = P.m_id();
    auto dateField = P.m_dateField(); auto duration = P.m_duration(); auto bytes = P.m_bytes();
    auto geometryField = P.m_geometryField(); auto longText = P.m_longText(); auto file = P.m_file();
    auto intSql = P.m_numberSql(number); bool missing;
    try { z8_sql_int_format(intSql); } catch (Exception) { missing = true; }
    assert(missing);
    auto fields = [cast(Z8Object)number, cast(Z8Object)text, cast(Z8Object)flag, cast(Z8Object)amount, cast(Z8Object)id,
                   cast(Z8Object)dateField, cast(Z8Object)duration, cast(Z8Object)bytes, cast(Z8Object)geometryField,
                   cast(Z8Object)longText, cast(Z8Object)file];
    foreach (field; fields)
        z8_field_bind_sql(field, null, null, "T.col"w);
    auto stringSql = P.m_textSql(text); auto boolSql = P.m_flagSql(flag);
    auto decimalSql = P.m_amountSql(amount); auto guidSql = P.m_idSql(id);
    auto nullSql = P.m_isNull(number); auto greater = P.m_greater(number);
    auto dateSql = P.m_dateSql(dateField); auto spanSql = P.m_spanSql(duration); auto binarySql = P.m_binarySql(bytes);
    auto geometrySql = P.m_geometrySql(geometryField); auto longTextSql = P.m_longTextSql(longText); auto fileSql = P.m_fileSql(file);
    auto items = new Z8Array!Z8Primary([z8_primary_box(1L), z8_primary_box("O'Reilly"w), z8_primary_box(true)]);
    auto inVector = P.m_inVector(number, items); auto notInVector = P.m_notInVector(number, items);
    auto empty = P.m_inVector(number, new Z8Array!Z8Primary());
    auto mixed = P.m_inVector(number, new Z8Array!Z8Primary([z8_primary_box(z8_date_from_ticks(0)),
        z8_primary_box(new Z8Datespan(1234)), z8_primary_box(z8_guid_create(5)),
        z8_primary_box(z8_decimal_parse("1.25"w)), z8_primary_box(new Z8Binary())]));
    items.z8_set(0, z8_primary_box(99L));
    wstring formatSql(int i, Z8SqlVendor vendor, bool logical) {
        switch (i) {
            case 0: return z8_sql_int_format(intSql, vendor, logical);
            case 1: return z8_sql_string_format(stringSql, vendor);
            case 2: return z8_sql_bool_format(boolSql, logical, vendor);
            case 3: return z8_sql_decimal_format(decimalSql, vendor, logical);
            case 4: return z8_sql_guid_format(guidSql, vendor);
            case 5: return z8_sql_bool_format(nullSql, logical, vendor);
            case 6: return z8_sql_bool_format(greater, logical, vendor);
            case 7: return z8_sql_date_format(dateSql, vendor);
            case 8: return z8_sql_datespan_format(spanSql, vendor);
            case 9: return z8_sql_binary_format(binarySql, vendor);
            case 10: return z8_sql_geometry_format(geometrySql, vendor);
            case 11: return z8_sql_string_format(longTextSql, vendor);
            case 12: return z8_sql_string_format(fileSql, vendor);
            case 13: return z8_sql_bool_format(inVector, logical, vendor);
            case 14: return z8_sql_bool_format(notInVector, logical, vendor);
            case 15: return z8_sql_bool_format(empty, logical, vendor);
            case 16: return z8_sql_bool_format(mixed, logical, vendor);
            default: assert(0);
        }
    }
    auto vendors = [Z8SqlVendor.Oracle, Z8SqlVendor.SqlServer, Z8SqlVendor.Postgres, Z8SqlVendor.H2];
    foreach (vendor; vendors) foreach (i; 0 .. 17) foreach (logical; [false, true])
        writeln(vendor, ":", i, ":", logical, ":", formatSql(i, vendor, logical).to!string);
    auto aggregations = [Z8FieldAggregation.none, Z8FieldAggregation.sum, Z8FieldAggregation.max, Z8FieldAggregation.min,
        Z8FieldAggregation.average, Z8FieldAggregation.count, Z8FieldAggregation.array, Z8FieldAggregation.distinct,
        Z8FieldAggregation.concat, Z8FieldAggregation.bitwiseOr, Z8FieldAggregation.bitwiseAnd];
    foreach (order; [false, true]) {
        z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, order));
        foreach (a, aggregation; aggregations) {
            foreach (field; fields) z8_field_set_aggregation(field, aggregation);
            foreach (vendor; vendors) foreach (i; 0 .. 13) foreach (logical; [false, true]) {
                string result;
                try { result = formatSql(i, vendor, logical).to!string; } catch (Exception) { result = "ERROR"; }
                writeln("A:", order, ":", a, ":", vendor, ":", i, ":", logical, ":", result);
            }
        }
    }
    z8_field_set_aggregation(number, Z8FieldAggregation.sum);
    z8_sql_set_field_options(Z8SqlFieldFormatOptions(true, false));
    auto thread = new Thread({ assert(z8_sql_int_format(intSql) == "(T.col)"w); });
    thread.start(); thread.join();
    assert(z8_sql_int_format(intSql) == "(sum(T.col))"w);
    z8_sql_set_field_options(Z8SqlFieldFormatOptions.init);
    z8_field_bind_sql(number, "t"w, `a"b`w);
    assert(z8_sql_int_format(intSql, Z8SqlVendor.Postgres) == `(t."a""b")`w);
    assert(z8_sql_int_format(intSql, Z8SqlVendor.SqlServer) == `(t.[a"b])`w);
    bool badValues; try { P.m_inVector(number, null); } catch (Exception) { badValues = true; }
    assert(badValues);
    auto withNull = P.m_inVector(number, new Z8Array!Z8Primary([null]));
    bool badElement; try { z8_sql_bool_format(withNull); } catch (Exception) { badElement = true; }
    assert(badElement);
}
''', encoding="utf-8")
    exe = temp / ("sql-field.exe" if os.name == "nt" else "sql-field")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    actual = subprocess.check_output([str(exe)], text=True, encoding="utf-8").splitlines()
    if actual != expected:
        differences = [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
        raise SystemExit(f"SQL field formatting differs ({len(actual)} D lines, {len(expected)} Java lines):\n" +
                         "\n".join(f"{i}: D={a!r} Java={b!r}" for i, a, b in differences[:20]))
print("SQL field references and aggregation match Java Z8")
