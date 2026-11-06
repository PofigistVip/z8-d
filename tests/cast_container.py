"""Compile and execute casts whose operand starts with container."""
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
    (source / "Base.bl").write_text("""
import org.zenframework.z8.lang.sql.sql_string;
public class Base {
    virtual public sql_string value() { return (sql_string) "base"; }
}
""", encoding="utf-8")
    (source / "Probe.bl").write_text("""
import org.zenframework.z8.lang.sql.sql_string;
public class Probe {
    public string[] names = {"first", "second"};
    public Base field = class {
        public sql_string value() { return (sql_string) container.names[1]; }
    };
    public static sql_string run() { Probe owner; return owner.field.value(); }
}
""", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.Probe;
void main() {
    alias Probe = Z8p_50726F6265;
    assert(z8_sql_string_format(Probe.m_run(), Z8SqlVendor.Postgres) == "(('second'))"w);
}
""", encoding="utf-8")
    executable = temp / ("cast-container.exe" if os.name == "nt" else "cast-container")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Casts of container fields and indexed elements verified")
