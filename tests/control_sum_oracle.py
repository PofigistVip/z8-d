"""Compare control sums with the checked-out Java source's algorithm."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/control_sum_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
jars = list((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
jars += list((original / "org.zenframework.z8.boot/target/libs").glob("*.jar"))
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
jars += [p for p in (cache / "org.zenframework.z8.dependencies.commons").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += list((cache / "commons-logging/commons-logging").rglob("*.jar"))
if not jars:
    raise SystemExit("Original server JAR not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "ControlSumOracle.java"
    java.write_text('''
import org.zenframework.z8.server.base.table.Table;
import org.zenframework.z8.server.base.table.system.Roles;
import org.zenframework.z8.server.base.table.value.Field;
class ControlSumOracle {
    // The available server JAR predates the source checkout: it does not
    // cache control sums and formats varchar lengths differently. Use its
    // object model with the current source's PostgreSQL formats and algorithm.
    static int fieldSum(Field field) {
        String type;
        switch (field.type()) {
            case Guid: type = "uuid"; break;
            case Date: case Datetime: case Datespan: case Integer: type = "bigint"; break;
            case Boolean: type = "smallint"; break;
            case Decimal: type = "numeric"; break;
            case String: type = "character varying"; break;
            case Binary: case Text: case File: case Attachments: type = "bytea"; break;
            default: throw new IllegalArgumentException(field.type().toString());
        }
        return Math.abs((field.name() + " " + type).hashCode());
    }
    static int tableSum(Table table) {
        int sum = 0;
        for (Field field : table.getPrimaryFields()) sum += fieldSum(field);
        return Math.abs(Integer.toString(sum).hashCode());
    }
    static void show(Table table) {
        int sum = 0;
        for (Field field : table.getPrimaryFields()) { int value = fieldSum(field); sum += value; System.out.println(field.name() + ":" + value); }
        int tableSum = Math.abs(Integer.toString(sum).hashCode());
        System.out.println("table:" + tableSum);
        Field field = table.getPrimaryFields().iterator().next();
        int cachedField = fieldSum(field);
        field.getCLASS().setName("changed");
        System.out.println("cached:" + cachedField + ":" + tableSum);
    }
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Field language = org.zenframework.z8.server.config.ServerConfig.class.getDeclaredField("language");
        language.setAccessible(true); language.set(null, "ru");
        show(new Table.CLASS<Table>(null).get());
        show(new Roles.CLASS<Roles>(null).get());
        Table unicodeTable = new Table.CLASS<Table>(null).get();
        Field unicodeField = unicodeTable.getPrimaryFields().iterator().next();
        unicodeField.getCLASS().setName("Поле 😀");
        System.out.println("unicode:" + fieldSum(unicodeField));
        System.out.println("object:" + Math.abs("Класс 😀".hashCode()));
        int sum = tableSum(new Table.CLASS<Table>(null).get()) + tableSum(new Roles.CLASS<Roles>(null).get());
        String number = String.format("%010d", Math.abs(sum));
        System.out.println("version:" + number.substring(0, 1) + "." + number.substring(1, 4) + "." + number.substring(4, 7) + "." + number.substring(7));
    }
}
''', encoding="utf-8")
    cp = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", cp, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp) + os.pathsep + cp, "ControlSumOracle"], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "bl"
    source.mkdir()
    (source / "Probe.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.system.Roles;
public class Probe {
    public static Table table() { Table value; return value; }
    public static Roles roles() { Roles value; return value; }
}
''', encoding="utf-8")
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated), "--dependency", str(language)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
class UnicodeObject : Z8Object { override wstring z8_class_id() { return "Класс 😀"w; } }
void show(Z8Object table) {
    auto fields = z8_query_declared_fields(table, true);
    foreach (field; fields) writeln(z8_native_call!wstring("org.zenframework.z8.server.runtime.OBJECT.m_name"w, field).to!string, ":", z8_object_control_sum(field));
    writeln("table:", z8_object_control_sum(table));
    fields[0].z8_set_attribute("name"w, "changed"w);
    writeln("cached:", z8_object_control_sum(fields[0]), ":", z8_object_control_sum(table));
}
void main() {
    alias P = Z8p_50726F6265; show(P.m_table()); show(P.m_roles());
    auto unicodeTable = P.m_table(); auto field = z8_query_declared_fields(unicodeTable, true)[0];
    field.z8_set_attribute("name"w, "Поле 😀"w);
    writeln("unicode:", z8_object_control_sum(field));
    writeln("object:", z8_object_control_sum(new UnicodeObject()));
    auto registry = new Z8RuntimeRegistry(); registry.registerTable(P.m_table()); registry.registerTable(P.m_roles());
    writeln("version:", z8_runtime_version(registry).number.to!string);
}
''', encoding="utf-8")
    exe = temp / ("control-sum.exe" if os.name == "nt" else "control-sum")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace("\\", "/") + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    actual = subprocess.check_output([str(exe)], cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, (expected, actual)
print("Field and table control sums match the current Java source algorithm")
