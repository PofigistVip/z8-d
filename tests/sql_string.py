"""Check string SQL expression trees independently of a database."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "bl" / "demo" / "cases"
    source.mkdir(parents=True)
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "SqlStringValues.bl", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(temp / "bl"), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''
import z8.runtime;
import z8gen.p_demo.p_cases.p_SqlStringValues;
alias Cases = Z8p_64656D6F2E63617365732E53716C537472696E6756616C756573;
void main() {
    assert(z8_optional_require(Cases.m_run()) == 241);
    auto text = Cases.m_concatenation();
    assert(text.kind == Z8SqlStringKind.group && text.left.kind == Z8SqlStringKind.upper);
    assert(text.left.left.kind == Z8SqlStringKind.group);
    assert(text.left.left.left.kind == Z8SqlStringKind.concat);
    auto choice = Cases.m_choice().left;
    assert(choice.kind == Z8SqlStringKind.choose && choice.condition.constant);
    auto length = Cases.m_length().left;
    assert(length.kind == Z8SqlIntKind.textLength);
    auto comparison = Cases.m_compare().left;
    assert(comparison.kind == Z8SqlBoolKind.textGreaterEqual);
    assert(z8_sql_string_format(Cases.m_literal(), Z8SqlVendor.Postgres) == "('O''Reilly 😀')"w);
    auto instant = z8_date_from_ticks(100000000);
    auto date = z8_sql_date_const(instant);
    auto truncated = z8_sql_date_truncDay(date);
    assert(z8_date_ticks(instant) == 100000000);
    auto first = z8_sql_date_format(truncated);
    assert(z8_date_ticks(instant) != 100000000);
    assert(z8_sql_date_format(truncated) == first);
    assert(z8_optional_require(Cases.m_sqlPrimaryChecks()) == 251);
    Z8SqlPrimary primary = z8_sql_string_const("value"w);
    assert(z8_sql_primary_toString(primary) is cast(Z8SqlString)primary);
    primary = z8_sql_decimal_const(z8_decimal_parse("1.5"w));
    assert(z8_sql_string_format(z8_sql_primary_toString(primary), Z8SqlVendor.Postgres) == "(1.5)::text"w);
}
''', encoding="utf-8")
    executable = temp / ("sql-string.exe" if os.name == "nt" else "sql-string")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("SQL string expressions verified")
