"""Exercise native query Period fields, JSON parsing and SQL predicates."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/period_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "PeriodTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.DatetimeField;
public class PeriodTable extends Table { public DatetimeField moment; }
''', encoding="utf-8")
    (source / "PeriodProbe.bl").write_text('''
import org.zenframework.z8.base.query.Period;
public class PeriodProbe {
    public static PeriodTable table() { PeriodTable table; return table; }
    public static Period empty() { Period period; return period; }
    public static Period parse(PeriodTable table, string json) { return Period.getPeriod(table.moment, json); }
    public static Period configured(PeriodTable table) {
        Period period; period.field = table.moment; period.start = date.parse("1000"); period.finish = date.parse("2000"); return period;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.PeriodProbe;
void main() {
    alias P = Z8p_506572696F6450726F6265;
    auto table = P.m_table();
    auto empty = P.m_empty();
    assert(z8_date_ticks(empty.f_start) == z8_date_ticks(z8_date_min));
    assert(z8_date_ticks(empty.f_finish) == z8_date_ticks(z8_date_max));
    assert(empty.m_where().kind == Z8SqlBoolKind.constant && empty.m_where().constant);
    auto configured = P.m_configured(table);
    auto where = configured.m_where();
    assert(where.kind == Z8SqlBoolKind.and && where.left.dateOperator == "<=" && where.right.dateOperator == "<=");
    assert(z8_date_ticks(where.left.dateLeft.constant) == 1000 && where.left.dateRight.field is table.f_moment);
    assert(z8_date_ticks(where.right.dateRight.constant) == 2000 && where.right.dateLeft.field is table.f_moment);
    auto parsed = P.m_parse(table, "{active:true,start:'1000',finish:'2000'}"w);
    assert(z8_date_ticks(parsed.f_start) == 1000 && z8_date_ticks(parsed.f_finish) == 2000);
    assert(parsed.m_where().kind == Z8SqlBoolKind.and);
    parsed = P.m_parse(table, "{active:false,start:'bad'}"w);
    assert(parsed.m_where().kind == Z8SqlBoolKind.constant && parsed.m_where().constant);
    parsed = P.m_parse(table, "{active:true,finish:'2000'}"w);
    assert(parsed.m_where().kind == Z8SqlBoolKind.dateCompare);
    assert(z8_date_ticks(parsed.m_where().dateRight.constant) == 2000);
    bool invalid; try { P.m_parse(table, "{active:true,start:'bad'}"w); } catch (Exception) { invalid = true; }
    assert(invalid);
}
''', encoding="utf-8")
    executable = temp / ("period.exe" if os.name == "nt" else "period")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Period defaults, JSON and inclusive SQL bounds passed")
