"""Check resource substitution when creating Z8 strings."""
from pathlib import Path
import os
import subprocess
import tempfile

from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    root = Path(__file__).resolve().parents[1]
    exe = root / ("z8d.exe" if os.name == "nt" else "z8d")
    bl_source = temp / "ResourceLiterals.bl"
    bl_source.write_text(r'''public class ResourceLiterals {
    public static string resource() { return "$nested$"; }
    public static string missing() { return "$missing$"; }
    public static string emptyResource() { return "$$"; }
    public static string empty() { return ""; }
    public static string unicode() { return "Ж😀"; }
    public static string escapes() { return "\b\f\n\r\t\"\\\'"; }
    public static string separators() { return "A__SEPARATORS__D"; }
}
'''.replace("__SEPARATORS__", "\u0085B\u2028C\u2029"), encoding="utf-8")
    generated = subprocess.run([str(exe), "compile", str(bl_source)],
                               capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert 'z8_string_new("$nested$"w)' in generated
    assert 'z8_string_new("Ж😀"w)' in generated
    assert r'''z8_string_new("\b\f\n\r\t\"\\'"w)''' in generated
    assert r'z8_string_new("A\u0085B\u2028C\u2029D"w)' in generated
    source = temp / "string_resources.d"
    source.write_text(generated + r'''
void main() {
    assert(z8_string_new("$missing$"w) == "missing"w);
    assert(z8_string_new("$$"w) == ""w);
    assert(z8_string_new("$"w) == "$"w);
    z8_string_set_resource("greeting"w, "Привет"w);
    z8_string_set_resource("nested"w, "$greeting$"w);
    assert(z8_string_new("$greeting$"w) == "Привет"w);
    assert(z8_string_new("$nested$"w) == "$greeting$"w);
    assert(Z8_ResourceLiterals.m_resource() == "$greeting$"w);
    assert(Z8_ResourceLiterals.m_missing() == "missing"w);
    assert(Z8_ResourceLiterals.m_emptyResource() == ""w);
    assert(Z8_ResourceLiterals.m_unicode() == [cast(wchar)0x0416, cast(wchar)0xD83D, cast(wchar)0xDE00]);
    assert(Z8_ResourceLiterals.m_escapes() == [cast(wchar)8, 12, 10, 13, 9, 34, 92, 39]);
    assert(Z8_ResourceLiterals.m_separators() == [cast(wchar)65, 0x85, 66, 0x2028, 67, 0x2029, 68]);
    assert(Z8_ResourceLiterals.m_empty() !is Z8_ResourceLiterals.m_empty());
    assert(Z8_ResourceLiterals.m_unicode() !is Z8_ResourceLiterals.m_unicode());
    assert(z8_nullable_string_binary!"+"("$"w, "greeting$"w) == "Привет"w);
    auto missingPath = z8_file_parse("[{size:0}]"w).z8_first();
    assert(missingPath.path !is null && missingPath.path.length == 0);
    z8_string_clear_resources();
    assert(z8_string_new("$greeting$"w) == "greeting"w);
}
''', encoding="utf-8")
    executable = temp / ("string_resources.exe" if os.name == "nt" else "string_resources")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("String resource substitution passed")
