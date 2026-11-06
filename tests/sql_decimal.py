"""Check decimal and mixed SQL expression trees independently of a database."""
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
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "SqlDecimalValues.bl", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(temp / "bl"), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''
import z8.runtime;
import z8gen.demo.cases.SqlDecimalValues;
alias Cases = Z8p_64656D6F2E63617365732E53716C446563696D616C56616C756573;
void main() {
    assert(z8_optional_require(Cases.m_run()) == 239);
    auto expression = Cases.m_expression();
    assert(expression.kind == Z8SqlDecimalKind.group);
    auto subtract = cast(Z8SqlDecimal)expression.left;
    assert(subtract.kind == Z8SqlDecimalKind.subtract);
    auto mixed = cast(Z8SqlDecimal)Cases.m_mixed().left;
    assert(mixed.kind == Z8SqlDecimalKind.divide);
    assert((cast(Z8SqlInt)mixed.left).constant == 3);
    auto conversion = cast(Z8SqlDecimal)Cases.m_converted().left;
    assert(conversion.kind == Z8SqlDecimalKind.fromInt);
    auto choice = cast(Z8SqlDecimal)Cases.m_choice().left;
    assert(choice.kind == Z8SqlDecimalKind.choose && choice.condition.constant);
}
''', encoding="utf-8")
    executable = temp / ("sql-decimal.exe" if os.name == "nt" else "sql-decimal")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("SQL decimal expressions verified")
