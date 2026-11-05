"""Check virtual methods overridden by native classes outside their BL declarations."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    declarations = {
        "Object": '[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object { virtual public string toString(); }',
        "Base": '[native "example.Base"] public class Base extends Object {}',
        "Derived": '[native "example.Derived"] public class Derived extends Base {}',
        "Child": 'public class Child extends Derived { public string toString() { return "child"; } public string parentText() { return super.toString(); } }',
        "Probe": 'public class Probe { public static string text(Object value) { return value.toString(); } public static string parent(Child value) { return value.parentText(); } }',
    }
    for name, content in declarations.items():
        (source / (name + ".bl")).write_text(content, encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.p_Probe;
import z8gen.p_Base;
import z8gen.p_Derived;
import z8gen.p_Child;
wstring baseText(Z8Object self) { return "base"w; }
wstring derivedText(Z8Object self) { return "derived"w; }
void main() {
    alias P = Z8p_50726F6265;
    z8_native_bind("example.Base.m_toString"w, &baseText);
    z8_native_bind("example.Derived.m_toString"w, &derivedText);
    auto base = z8_new!Z8p_42617365();
    auto derived = z8_new!Z8p_44657269766564();
    auto child = z8_new!Z8p_4368696C64();
    assert(P.m_text(base) == "base"w);
    assert(P.m_text(derived) == "derived"w);
    assert(P.m_text(child) == "child"w);
    assert(P.m_parent(child) == "derived"w);
    z8_native_clear_bindings();
    z8_bind_builtin_object();
    z8_native_bind("example.Base.m_toString"w, &baseText);
    assert(P.m_text(derived) == "base"w);
    assert(P.m_parent(child) == "base"w);
}
""", encoding="utf-8")
    executable = temp / ("virtual.exe" if os.name == "nt" else "virtual")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Native virtual overrides dispatch to the most specific implementation")
