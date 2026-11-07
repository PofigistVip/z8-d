"""Share nested primary-array values with user-keyed map views."""
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
    (source / "Custom.bl").write_text('''public class Custom extends primary {
        public int number; public void operator = (Custom value) { number = value.number; }
    }''', encoding="utf-8")
    (source / "Plain.bl").write_text('''public class Plain { public operator int() { return 1; } }''', encoding="utf-8")
    (source / "Probe.bl").write_text('''public class Probe {
    static int size(primary[][BaseKey] values) { return values.size(); }
    static primary[][BaseKey] choice(bool flag, primary[][BaseKey] a, int[][ChildKey] b) { return flag ? a : b; }
    public static int run() {
        ChildKey key = new ChildKey; BaseKey base = new BaseKey; int[] row = {1, 2};
        int[][ChildKey] typed = {(key, row)}; primary[][BaseKey] values = typed;
        values.get(key).set(0, 8); typed.get(key).set(1, 9);
        if (typed.get(key).get(0) != 8 || (int)values.get(key).get(1) != 9) return 1;
        primary[] replacement = {5, 6}; values.add(key, replacement);
        if (typed.get(key).get(1) != 6) return 2;
        typed.get(key).set(0, 7); if ((int)replacement.get(0) != 7) return 3;
        replacement.add("wrong"); try { int bad = typed.get(key).get(2); return 4; } catch (exception expected) {}
        replacement.removeAt(2); if (size(typed) != 1 || choice(false, values, typed).size() != 1) return 5;
        values.add(base, replacement); if (typed.size() != 2) return 6;
        try { for (ChildKey item : typed.keys()) {} return 7; } catch (exception expected) {}
        Custom first; first.number = 1; Custom second; second.number = 2;
        Custom[] rowCustom = {first}; Custom[][ChildKey] custom = {(key, rowCustom)}; primary[][BaseKey] pc = custom;
        pc.get(key).set(0, second); if (custom.get(key).get(0).number != 2) return 8;
        primary[] customReplacement = {first}; pc.add(key, customReplacement);
        if (custom.get(key).get(0).number != 1) return 9;
        Custom primaryKey; int[][Custom] primaryKeyMap = {(primaryKey, row)}; primary[][Custom] nested = primaryKeyMap;
        int[][primary] keys = primaryKeyMap; primary[][primary] both = keys;
        both.add("extra", replacement); if (nested.size() != 2 || primaryKeyMap.size() != 2) return 10;
        Custom[][Custom] customMap = {(primaryKey, rowCustom)}; Custom[][primary] customKeysFirst = customMap;
        primary[][Custom] customValuesSecond = customMap; customKeysFirst.add("extra", rowCustom);
        customValuesSecond.get(primaryKey).set(0, first);
        if (customKeysFirst.get("extra").get(0).number != 1 || customMap.size() != 2) return 11;
        return 0;
    }
}''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main() { assert(z8_optional_require(Z8p_50726F6265.m_run()) == 0); }
''', encoding="utf-8")
    executable = temp / ("primary-nested-user-maps.exe" if os.name == "nt" else "primary-nested-user-maps")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
    for declaration in (
        "int[][BaseKey] source; primary[][ChildKey] target = source;",
        "Plain[][ChildKey] source; primary[][BaseKey] target = source;",
    ):
        (source / "Bad.bl").write_text('public class Bad { static void f() { ' + declaration + ' } }', encoding="utf-8")
        if subprocess.run([str(compiler), "project", str(source), str(generated)], capture_output=True).returncode == 0:
            raise SystemExit("Unexpectedly accepted nested map conversion: " + declaration)
print("User-keyed maps of typed arrays share primary array views")
