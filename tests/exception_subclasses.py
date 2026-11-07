"""Exercise native and generated classes derived from the BL exception type."""
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
    (source / "UserError.bl").write_text('''
[native "example.UserError"] public class UserError extends exception {
    public static UserError error(string message);
}
''', encoding="utf-8")
    (source / "ExtendedError.bl").write_text('''
public class ExtendedError extends UserError {}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static string direct() { UserError error = UserError.error("failure"); return error.getMessage(); }
    public static string thrown() {
        try { throw UserError.error("failure"); }
        catch (exception caught) { return caught.getMessage(); }
    }
    private static string message(exception error) { return error.getMessage(); }
    public static string argument() { return message(UserError.error("argument")); }
    public static string assignment() { UserError value = UserError.error("assigned"); exception error = value; return error.getMessage(); }
    private static int choose(UserError error) { return 1; }
    private static int choose(exception error) { return 2; }
    public static int overload() { return choose(UserError.error("choice")); }
    public static bool descendant() { ExtendedError value; try { throw value; } catch (exception caught) { return true; } }
    public static bool identity() {
        UserError value = UserError.error("identity"); exception asException = value;
        if (!(value instanceof exception) || !(asException instanceof UserError)) return false;
        UserError restored = (UserError) asException;
        if (restored.getMessage() != "identity") return false;
        try { throw value; } catch (exception caught) { return !(caught instanceof UserError); }
    }
    public static UserError roundtrip(UserError value) { exception converted = value; return (UserError) converted; }
    public static bool nullIdentity(UserError value) {
        if (value instanceof exception) return false;
        exception converted = value;
        return converted == null;
    }
    public static bool typedCatch() {
        UserError value = UserError.error("typed");
        try { throw value; }
        catch (ExtendedError other) { return false; }
        catch (UserError caught) { return caught.getMessage() == "typed"; }
        catch (exception other) { return false; }
    }
    public static UserError caughtIdentity(UserError value) {
        try { throw value; } catch (UserError caught) { return caught; }
    }
    public static bool descendantCatch() {
        ExtendedError value; try { throw value; } catch (UserError caught) { return caught instanceof ExtendedError; }
    }
    public static bool catchRethrow() {
        try { try { throw UserError.error("pass"); } catch (ExtendedError other) { return false; } }
        catch (UserError caught) { return caught.getMessage() == "pass"; }
    }
    public static int catchFinally() {
        int number = 0;
        try { throw UserError.error("finally"); }
        catch (UserError caught) { number = 1; }
        finally { number = number + 2; }
        return number;
    }
    public static int returnFinally() {
        try { throw UserError.error("finally"); }
        catch (UserError caught) { return 3; }
        finally { int value = 1; }
    }
    public static bool invalidCast() {
        exception value = "plain";
        if (value instanceof UserError) return false;
        try { UserError result = (UserError) value; return false; } catch (exception caught) { return true; }
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    adapter = temp / "adapter.d"
    adapter.write_text('''module adapter;
import z8.runtime;
Z8Object userError(wstring message) {
    auto result = z8_native_new("example.UserError"w);
    auto error = cast(Z8ExceptionObject)result;
    assert(error !is null);
    error.z8_set_exception_message(message);
    return error;
}
void bindError() { z8_native_bind("example.UserError.m_error"w, &userError); }
''', encoding="utf-8")
    adapter_object = temp / ("adapter.obj" if os.name == "nt" else "adapter.o")
    subprocess.run(["dmd", "-c", *import_args(), str(adapter), "-of=" + str(adapter_object)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
import z8gen.UserError;
import adapter;
void main() {
    alias P = Z8p_50726F6265;
    bindError();
    assert(P.m_direct() == "failure"w);
    assert(P.m_thrown() == "failure"w);
    assert(P.m_argument() == "argument"w);
    assert(P.m_assignment() == "assigned"w);
    assert(z8_optional_require(P.m_overload()) == 1);
    assert(z8_optional_require(P.m_descendant()));
    assert(z8_optional_require(P.m_identity()));
    assert(z8_optional_require(P.m_invalidCast()));
    assert(z8_optional_require(P.m_typedCatch()));
    assert(z8_optional_require(P.m_descendantCatch()));
    assert(z8_optional_require(P.m_catchRethrow()));
    assert(z8_optional_require(P.m_catchFinally()) == 3);
    assert(z8_optional_require(P.m_returnFinally()) == 3);
    auto original = cast(Z8p_557365724572726F72)userError("identity"w);
    assert(P.m_roundtrip(original) is original);
    assert(P.m_caughtIdentity(original) is original);
    assert(P.m_roundtrip(null) is null);
    assert(z8_optional_require(P.m_nullIdentity(null)));
}
''', encoding="utf-8")
    executable = temp / ("exception-subclasses.exe" if os.name == "nt" else "exception-subclasses")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(adapter_object), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for declaration in (
        'try {} catch (int value) {}',
        'try {} catch (Probe value) {}',
        'try {} catch (UserError first) {} catch (UserError second) {}',
        'try {} catch (exception first) {} catch (exception second) {}',
        'try {} catch (exception first) {} catch (UserError second) {}',
    ):
        (source / "Bad.bl").write_text('public class Bad { static void f() { ' + declaration + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted invalid catch: " + declaration)
print("Native exception subclasses, implicit conversions and throw verified")
