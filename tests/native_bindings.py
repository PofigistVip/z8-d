"""Exercise native declarations with callbacks in a separately linked D runtime."""
from pathlib import Path
import os, shutil, subprocess, tempfile
from runtime_support import import_args, runtime_library
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "bl"
    shutil.copytree(root / "examples" / "native", source)
    generated = temp / "generated"
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.p_NativeMath;
import z8gen.p_NativeNumber;
import z8gen.p_NativeConsumer;
alias Math = Z8p_4E61746976654D617468;
alias Number = Z8p_4E61746976654E756D626572;
alias Consumer = Z8p_4E6174697665436F6E73756D6572;
Z8Optional!long add(Z8Optional!long a, Z8Optional!long b) { return z8_optional_wrap(z8_optional_require(a) + z8_optional_require(b)); }
wstring addText(wstring a, wstring b) { return a ~ b; }
Z8Optional!long scale(Math self, Z8Optional!long value) { return z8_optional_wrap(z8_optional_require(value) * 3); }
Z8Optional!long read(Number self) { return z8_optional_wrap(9L); }
Z8Optional!long convertNumber(Number self) { return z8_optional_wrap(2L); }
Z8Optional!long ignored(Math self) { return z8_optional_wrap(10L); }
__gshared Z8Optional!long nativeFactor, nativeTotal;
Z8Optional!long* factor(Math self) { assert(self !is null); return &nativeFactor; }
Z8Optional!long* total() { return &nativeTotal; }
Z8Optional!long* badField() { return null; }
void reset() {}
void main() {
    bool missing;
    try { Consumer.m_run(); } catch (Exception e) { missing = e.msg.indexOf("native binding not found") >= 0; }
    assert(missing);
    z8_native_bind_field("example.bad.f_field"w, &badField);
    bool badPointer;
    try { z8_native_field!(Z8Optional!long)("example.bad.f_field"w) = z8_optional_wrap(1L); }
    catch (Exception e) { badPointer = e.msg.indexOf("native field binding returned null") >= 0; }
    assert(badPointer);
    nativeFactor = z8_optional_wrap(3L);
    nativeTotal = z8_optional_wrap(7L);
    z8_native_bind("example.NativeMath.m_add"w, &add);
    z8_native_bind("example.NativeMath.m_add"w, &addText);
    z8_native_bind("example.NativeMath.m_scale"w, &scale);
    z8_native_bind("example.NativeMath.m_reset"w, &reset);
    z8_native_bind("example.NativeNumber.m_read"w, &read);
    z8_native_bind("example.NativeNumber.z8cast_int"w, &convertNumber);
    z8_native_bind("example.NativeMath.m_ignored"w, &ignored);
    bool missingField;
    try { Consumer.m_run(); } catch (Exception e) { missingField = e.msg.indexOf("example.NativeMath.f_factor") >= 0; }
    assert(missingField);
    z8_native_bind_field("example.NativeMath.f_factor"w, &factor);
    bool missingStaticField;
    try { Consumer.m_run(); } catch (Exception e) { missingStaticField = e.msg.indexOf("example.NativeMath.f_total") >= 0; }
    assert(missingStaticField);
    z8_native_bind_field("example.NativeMath.f_total"w, &total);
    assert(z8_optional_require(Consumer.m_run()) == 54);
    assert(z8_optional_require(nativeFactor) == 4 && z8_optional_require(nativeTotal) == 12);
    z8_native_clear_bindings();
}
'''.replace('import z8.runtime;', 'import z8.runtime;\nimport std.string : indexOf;'), encoding="utf-8")
    executable = temp / ("native.exe" if os.name == "nt" else "native")
    modules = [str(p) for p in generated.rglob("*.d")]
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *modules, str(harness), str(runtime), "-of=" + str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    (source / "Bad.bl").write_text("class Bad { public void f(); }", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad")], capture_output=True, text=True)
    if result.returncode == 0 or "requires a native type" not in result.stderr:
        raise SystemExit("A bodyless method was accepted on an ordinary class")
    (source / "Bad.bl").write_text("class Bad extends primary {}", encoding="utf-8")
    result = subprocess.run([str(compiler), "project", str(source), str(temp / "bad-primary")], capture_output=True, text=True)
    if result.returncode == 0 or "must implement assignment from itself" not in result.stderr:
        raise SystemExit("A non-native primary subclass without assignment was accepted")
    (source / "Bad.bl").write_text("class Bad extends primary { public void operator = (Bad value) {} }", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(temp / "good-primary")], check=True)
print("Native and primary declarations bound through the separate runtime")
