"""Compare the standard native Sql functions with the original Java runtime.

Usage: python tests/sql_functions_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/sql_functions_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang" / "src" / "bl"
jars = sorted((original / "org.zenframework.z8.server" / "target" / "libs").glob("*.jar"))
if not any(p.name.startswith("org.zenframework.z8.server-") for p in jars):
    raise SystemExit("Original server JAR not found")
cache = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
for dependency in (cache / "commons-logging" / "commons-logging", cache / "org.zenframework.z8.dependencies.commons", cache / "commons-io" / "commons-io" / "2.7"):
    if dependency.exists():
        jars.extend(p for p in dependency.rglob("*.jar") if not p.name.endswith("-sources.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
types = ["datespan", "date", "decimal", "guid", "int", "string"]
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    declaration = Path("org/zenframework/z8/base/table/Sql.bl")
    destination = source / declaration
    destination.parent.mkdir(parents=True)
    shutil.copy2(language / declaration, destination)
    imports = "\n".join(f"import org.zenframework.z8.lang.sql.sql_{kind};" for kind in ["bool", *types])
    methods = "\n".join(
        f"public static sql_{kind} choose{kind}(sql_bool c, sql_{kind} a, sql_{kind} b) {{ return Sql.IIF(c, a, b); }}"
        for kind in types
    )
    (source / "Probe.bl").write_text(
        imports + "\nimport org.zenframework.z8.base.table.Sql;\npublic class Probe {\n" + methods + "\n}",
        encoding="utf-8",
    )
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    java = temp / "SqlOracle.java"
    java.write_text("""
import org.zenframework.z8.server.db.DatabaseVendor;
import org.zenframework.z8.server.db.sql.functions.Sql;
import org.zenframework.z8.server.types.*;
import org.zenframework.z8.server.types.sql.*;
class SqlOracle {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        for (DatabaseVendor vendor : DatabaseVendor.values()) {
            sql_bool c = new sql_bool(true);
            sql_primary[] values = {
                Sql.z8_IIF(c, new sql_datespan(new datespan(1234L)), new sql_datespan(new datespan(5678L))).operatorPriority(),
                Sql.z8_IIF(c, new sql_date(new date(0L)), new sql_date(new date(100000000L))).operatorPriority(),
                Sql.z8_IIF(c, new sql_decimal(new decimal("1.25")), new sql_decimal(new decimal("-2.5"))).operatorPriority(),
                Sql.z8_IIF(c, new sql_guid("00000000-0000-0000-0000-000000000001"), new sql_guid("00000000-0000-0000-0000-000000000002")).operatorPriority(),
                Sql.z8_IIF(c, new sql_integer(7), new sql_integer(-9)).operatorPriority(),
                Sql.z8_IIF(c, new sql_string("alpha"), new sql_string("beta")).operatorPriority()
            };
            for (int i = 0; i < values.length; i++) {
                try { System.out.println(vendor.name() + ":" + i + ":" + values[i].format(vendor, null)); }
                catch (RuntimeException error) { System.out.println(vendor.name() + ":" + i + ":ERROR"); }
            }
        }
    }
}
""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "SqlOracle", str(config)], cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.p_Probe;
import std.conv : to;
import std.stdio : writeln;
void main() {
    alias P = Z8p_50726F6265;
    foreach (vendor; [Z8SqlVendor.Oracle, Z8SqlVendor.SqlServer, Z8SqlVendor.Postgres, Z8SqlVendor.H2]) {
        auto c = z8_sql_bool_const(true);
        auto span = P.m_choosedatespan(c, z8_sql_datespan_const(new Z8Datespan(1234)), z8_sql_datespan_const(new Z8Datespan(5678)));
        auto date = P.m_choosedate(c, z8_sql_date_const(z8_date_from_ticks(0)), z8_sql_date_const(z8_date_from_ticks(100000000)));
        auto dec = P.m_choosedecimal(c, z8_sql_decimal_const(z8_decimal_parse("1.25"w)), z8_sql_decimal_const(z8_decimal_parse("-2.5"w)));
        auto guid = P.m_chooseguid(c, z8_sql_guid_const(z8_guid_literal("00000000-0000-0000-0000-000000000001")), z8_sql_guid_const(z8_guid_literal("00000000-0000-0000-0000-000000000002")));
        auto number = P.m_chooseint(c, z8_sql_int_const(7), z8_sql_int_const(-9));
        auto text = P.m_choosestring(c, z8_sql_string_const("alpha"w), z8_sql_string_const("beta"w));
        foreach (i; 0 .. 6) {
            try {
                wstring value;
                switch (i) {
                    case 0: value = z8_sql_datespan_format(span, vendor); break;
                    case 1: value = z8_sql_date_format(date, vendor); break;
                    case 2: value = z8_sql_decimal_format(dec, vendor); break;
                    case 3: value = z8_sql_guid_format(guid, vendor); break;
                    case 4: value = z8_sql_int_format(number, vendor); break;
                    case 5: value = z8_sql_string_format(text, vendor); break;
                    default: assert(0);
                }
                writeln(vendor, ":", i, ":", value.to!string);
            } catch (Exception) { writeln(vendor, ":", i, ":ERROR"); }
        }
    }
    z8_native_clear_bindings();
    z8_bind_builtin_sql_functions();
    assert(P.m_chooseint(z8_sql_bool_const(true), z8_sql_int_const(1), z8_sql_int_const(2)) !is null);
}
""", encoding="utf-8")
    executable = temp / ("sql-functions.exe" if os.name == "nt" else "sql-functions")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"Sql functions differ:\nJava={expected!r}\nD={actual!r}")
print("Sql.IIF overloads match Java SQL formatting")
