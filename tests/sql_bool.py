"""Check SQL boolean expression trees and eager BL operand evaluation."""
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
    shutil.copy2(root / "examples" / "project" / "demo" / "cases" / "SqlBoolValues.bl", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(temp / "bl"), str(generated)], check=True)
    runner = temp / "main.d"
    runner.write_text('''
import z8.runtime;
import z8gen.p_demo.p_cases.p_SqlBoolValues;
alias Cases = Z8p_64656D6F2E63617365732E53716C426F6F6C56616C756573;
void main() {
    assert(z8_optional_require(Cases.m_run()) == 235);
    auto value = Cases.m_expression();
    assert(value.kind == Z8SqlBoolKind.group);
    assert(value.left.kind == Z8SqlBoolKind.group);
    auto conjunction = value.left.left;
    assert(conjunction.kind == Z8SqlBoolKind.and);
    assert(conjunction.left.kind == Z8SqlBoolKind.constant && !conjunction.left.constant);
    assert(conjunction.right.kind == Z8SqlBoolKind.group);
    assert(conjunction.right.left.kind == Z8SqlBoolKind.constant && conjunction.right.left.constant);
    auto choice = Cases.m_choose().left;
    assert(choice.kind == Z8SqlBoolKind.choose);
    assert(choice.left.constant && choice.right.constant && !choice.alternative.constant);
    auto comparison = Cases.m_compare().left;
    assert(comparison.kind == Z8SqlBoolKind.notEqual);
    assert(comparison.left.constant && !comparison.right.constant);
}
''', encoding="utf-8")
    executable = temp / ("sql-bool.exe" if os.name == "nt" else "sql-bool")
    subprocess.run(["dmd", str(runner), *map(str, generated.rglob("*.d")), "-I" + str(generated),
                    *import_args(), str(runtime), "-oq", "-od=" + str(temp), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("SQL boolean expressions verified")
