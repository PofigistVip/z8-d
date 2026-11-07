"""Execute conditional and instanceof expressions in generated D."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory); source = temp / "src"; generated = temp / "generated"; source.mkdir()
    (source / "Base.bl").write_text("public class Base {}", encoding="utf-8")
    (source / "Child.bl").write_text("public class Child extends Base {}", encoding="utf-8")
    (source / "Color.bl").write_text("public enum Color { Red }", encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    public static bool match(bool flag) {
        Base a = new Child; Base b = new Base;
        return flag ? a : b instanceof Child;
    }
    public static bool nested(bool first, bool second) {
        Base a = new Child; Base b = new Base;
        return first ? a : second ? a : b instanceof Child;
    }
    public static bool branch(bool flag) { return flag ? false : (new Child instanceof Base); }
    public static bool sqlKind(bool flag) {
        sql_int number = 1; sql_string text = "x";
        sql_primary a = number; sql_primary b = text;
        return flag ? a : b instanceof sql_int;
    }
    public static bool exceptionKind(bool flag) {
        exception a = "problem"; exception b = null;
        return flag ? a : b instanceof exception;
    }
    public static bool enumKind(bool flag) {
        Color a = Color.Red; Color b = null;
        return flag ? a : b instanceof Color;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True, cwd=temp)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() {
    alias P = Z8p_50726F6265;
    assert(z8_optional_require(P.m_match(z8_optional_wrap(true))), "true branch must be Child");
    assert(!z8_optional_require(P.m_match(z8_optional_wrap(false))), "false branch must be Base");
    assert(z8_optional_require(P.m_nested(z8_optional_wrap(true), z8_optional_wrap(false))));
    assert(z8_optional_require(P.m_nested(z8_optional_wrap(false), z8_optional_wrap(true))));
    assert(!z8_optional_require(P.m_nested(z8_optional_wrap(false), z8_optional_wrap(false))));
    assert(!z8_optional_require(P.m_branch(z8_optional_wrap(true))));
    assert(z8_optional_require(P.m_branch(z8_optional_wrap(false))));
    assert(z8_optional_require(P.m_sqlKind(z8_optional_wrap(true))));
    assert(!z8_optional_require(P.m_sqlKind(z8_optional_wrap(false))));
    assert(z8_optional_require(P.m_exceptionKind(z8_optional_wrap(true))));
    assert(!z8_optional_require(P.m_exceptionKind(z8_optional_wrap(false))));
    assert(z8_optional_require(P.m_enumKind(z8_optional_wrap(true))));
    assert(!z8_optional_require(P.m_enumKind(z8_optional_wrap(false))));
}''', encoding="utf-8")
    executable = temp / ("probe.exe" if os.name == "nt" else "probe")
    for flags in ([], ["-O"]):
        subprocess.run(["dmd", *flags, "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                        str(harness), str(runtime), "-of=" + str(executable)], check=True, cwd=temp)
        subprocess.run([str(executable)], check=True, cwd=temp)
print("Conditional instanceof grouping and execution verified")
