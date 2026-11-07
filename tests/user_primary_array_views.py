"""User primary arrays and primary[] retain the same mutable storage."""
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
    (source / "Value.bl").write_text('''
public class Value extends primary {
    public int number;
    public void operator = (Value value) { number = value.number; }
}
''', encoding="utf-8")
    (source / "Child.bl").write_text('''public class Child extends Value { public void operator = (Child value) {} }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static primary[] choice(bool b, primary[] left, Value[] right) { return b ? left : right; }
    public static int size(primary[] values) { return values.size(); }
    public static int choose(primary[] values) { return 1; }
    public static int choose(Value[] values) { return 2; }
    public static int run() {
        Value first; first.number = 1;
        Value second; second.number = 2;
        Value[] typed = {first, null};
        primary[] values = typed;
        values.set(1, second); if (typed[1].number != 2) return 1;
        typed.set(0, second); if (((Value)values[0]).number != 2) return 2;
        values.add(null); typed.set(2, first); if (((Value)values[2]).number != 1) return 3;
        values.add("wrong");
        try { int bad = typed[3].number; return 4; } catch (exception expected) {}
        values.removeAt(3);
        int count = 0; for (primary item : typed) count += 1;
        if (count != 3 || size(typed) != 3 || choose(typed) != 2) return 5;
        if (choice(false, values, typed).size() != 3) return 6;
        Value[] remove = {first}; values.removeAll(remove);
        if (values.size() != 2) return 7;
        Child[] children = null; primary[] parents = children;
        if (parents != null) return 8;
        return 0;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
class Base : Z8Object {}
class Derived : Base {}
void main() {
    auto one = new Derived(), two = new Derived();
    auto typed = new Z8ObjectArray!Derived([one, null]);
    auto baseView = z8_object_array_view!(Base, Derived)(typed);
    auto values = z8_primary_array_view(typed);
    assert(z8_primary_array_view(baseView) is values);
    values.z8_set(1, z8_primary_box(two)); assert(typed.z8_get(1) is two);
    typed.z8_set(0, two); assert(z8_primary_cast!Derived(values.z8_get(0)) is two);
    values.z8_add(null); z8_object_array_assign(typed, 2, one);
    assert(z8_primary_cast!Derived(values.z8_get(2)) is one);
    values.z8_add(z8_primary_box(42L));
    bool invalid; try { typed.z8_get(3); } catch (Exception) { invalid = true; }
    assert(invalid); values.z8_removeAt(3);
    auto prior = values.z8_version; baseView.z8_add(one);
    assert(values.z8_version == prior + 1 && typed.z8_size() == 4);
    assert(values.opEquals(typed) && typed.opEquals(values));
    assert(z8_primary_array_view(cast(Z8ObjectArray!Derived)null) is null);
    assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0);
}
''', encoding="utf-8")
    executable = temp / ("user-primary-arrays.exe" if os.name == "nt" else "user-primary-arrays")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    # Indexed assignment of ordinary object arrays continues to accept derived values and null.
    (source / "Objects.bl").write_text('''public class Objects {
        public static int run() {
            Objects[] values = {new Objects};
            values[0] = null;
            if (values[0] != null) return 1;
            values[0] = new Objects;
            return values[0] == null ? 2 : 0;
        }
    }''', encoding="utf-8")
    subprocess.run([str(compiler), "build", str(source), "Objects.run", str(executable)], check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    (source / "Bad.bl").write_text('public class Bad { static void f() { Bad[] items; primary[] values = items; } }', encoding="utf-8")
    if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
        raise SystemExit("Unexpectedly accepted non-primary object array")
print("User primary and object arrays share storage")

