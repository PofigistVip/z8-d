"""Check SQL integer expression trees independently of a database."""
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
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "SqlIntValues.bl", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(temp / "bl"), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''
import z8.runtime;
import z8gen.demo.cases.SqlIntValues;
alias Cases = Z8p_64656D6F2E63617365732E53716C496E7456616C756573;
void main() {
    assert(z8_optional_require(Cases.m_run()) == 237);
    auto expression = Cases.m_expression();
    assert(expression.kind == Z8SqlIntKind.group);
    auto division = expression.left;
    assert(division.kind == Z8SqlIntKind.divide && division.right.constant == 2);
    assert(division.left.kind == Z8SqlIntKind.multiply);
    assert(division.left.left.kind == Z8SqlIntKind.group);
    assert(division.left.left.left.kind == Z8SqlIntKind.add);
    auto comparison = Cases.m_compare().left;
    assert(comparison.kind == Z8SqlBoolKind.intGreaterEqual);
    auto choice = Cases.m_choice().left;
    assert(choice.kind == Z8SqlIntKind.choose && choice.condition.constant);
    assert(choice.left.constant == 10 && choice.right.constant == 20);
    auto converted = Cases.m_convertedLeft().left;
    assert(converted.kind == Z8SqlIntKind.add && converted.left.constant == 2);
}
''', encoding="utf-8")
    executable = temp / ("sql-int.exe" if os.name == "nt" else "sql-int")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("SQL integer expressions verified")
