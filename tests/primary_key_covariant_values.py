"""Widen primary map keys and covariant user values together."""
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
    (source / "BaseKey.bl").write_text('''public class BaseKey {}''', encoding="utf-8")
    (source / "ChildKey.bl").write_text('''public class ChildKey extends BaseKey {}''', encoding="utf-8")
    (source / "Parent.bl").write_text('''public class Parent { public int number; }''', encoding="utf-8")
    (source / "Child.bl").write_text('''public class Child extends Parent { public int extra; }''', encoding="utf-8")
    (source / "Key.bl").write_text('''public class Key extends primary { public void operator = (Key value) {} }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(Parent[primary] values) { return values.size(); }
    static Parent[primary] choice(bool flag, Parent[primary] a, Child[guid] b) { return flag ? a : b; }
    public static int run() {
        guid id = guid.create(1); Child child = new Child; child.number = 3;
        Parent parent = new Parent; parent.number = 7;
        Child[guid] typed = {(id, child)}; Parent[primary] values = typed;
        values.add(id, parent); try { int bad = typed.get(id).number; return 1; } catch (exception expected) {}
        typed.add(id, child); if (values.get(id).number != 3) return 2;
        values.add("extra", parent);
        try { for (Child value : typed.values()) {} return 3; } catch (exception expected) {}
        values.remove("extra"); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 4;
        values.add(id, parent); typed.remove(id); if (values.containsKey(id)) return 5;
        typed.add(id, child);
        Child[] row = {child}; Child[][guid] nested = {(id, row)}; Parent[][primary] wider = nested;
        Parent[] parentRow = {parent}; wider.add(id, parentRow);
        try { int bad = nested.get(id).get(0).number; return 6; } catch (exception expected) {}
        nested.add(id, row); if (wider.get(id).get(0).number != 3) return 7;
        Key key; Child[Key] custom = {(key, child)}; Parent[primary] customValues = custom;
        customValues.add(key, parent); try { int bad = custom.get(key).number; return 8; } catch (exception expected) {}
        custom.add(key, child); if (customValues.get(key).number != 3) return 9;
        ChildKey childKey = new ChildKey; BaseKey baseKey = new BaseKey;
        Child[ChildKey] inner = {(childKey, child)}; Child[ChildKey][guid] outer = {(id, inner)};
        Parent[BaseKey][primary] wideNested = outer; wideNested.get(id).add(baseKey, parent);
        if (outer.get(id).get(childKey).number != 3 || outer.get(id).size() != 2) return 11;
        try { for (ChildKey item : outer.get(id).keys()) {} return 12; } catch (exception expected) {}
        Child[guid] sameKeys = {(id, child)}; Parent[guid] widenedValues = sameKeys;
        widenedValues.add(id, parent); sameKeys.remove(id); if (widenedValues.containsKey(id)) return 10;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("primary-covariant-values.exe" if os.name == "nt" else "primary-covariant-values")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for declaration in ("Parent[guid] source; Child[primary] target = source;", "Parent[][guid] source; Child[][primary] target = source;"):
        (source / "Bad.bl").write_text('public class Bad { static void f() { ' + declaration + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted value downcast: " + declaration)
print("Primary-key maps retain covariant user-value views")
