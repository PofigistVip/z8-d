"""Exercise BL Sorter overrides, stable ordering and shared array storage."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/sorter_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "SortItem.bl").write_text('''
import org.zenframework.z8.lang.Object;
public class SortItem extends Object { public int key; public int serial; }
''', encoding="utf-8")
    (source / "KeySorter.bl").write_text('''
import org.zenframework.z8.utils.Sorter;
import org.zenframework.z8.lang.Object;
public class KeySorter extends Sorter {
    virtual public int compare(Object a, Object b) {
        SortItem x = (SortItem)a; SortItem y = (SortItem)b;
        return x.key - y.key;
    }
}
''', encoding="utf-8")
    (source / "OverflowSorter.bl").write_text('''
import org.zenframework.z8.utils.Sorter;
import org.zenframework.z8.lang.Object;
public class OverflowSorter extends Sorter {
    virtual public int compare(Object a, Object b) {
        SortItem x = (SortItem)a; SortItem y = (SortItem)b;
        if (x.key < y.key) return 4294967295;
        if (x.key > y.key) return -4294967295;
        return 0;
    }
}
''', encoding="utf-8")
    (source / "SortProbe.bl").write_text('''
import org.zenframework.z8.utils.Sorter;
public class SortProbe {
    public static bool verify() {
        SortItem a; a.key = 2; a.serial = 1;
        SortItem b; b.key = 1; b.serial = 2;
        SortItem c; c.key = 2; c.serial = 3;
        SortItem d; d.key = 1; d.serial = 4;
        SortItem[] values = {a, b, c, d};
        SortItem[] alias = values;
        KeySorter sorter; sorter.sort(values);
        if (alias[0] != b || alias[1] != d || alias[2] != a || alias[3] != c) return false;
        Sorter equal; equal.sort(values);
        if (values[0] != b || values[1] != d || values[2] != a || values[3] != c) return false;
        OverflowSorter overflow; overflow.sort(values);
        return values[0] == b && values[1] == d && values[2] == a && values[3] == c;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_SortProbe;
void main() { assert(z8_optional_require(Z8p_536F727450726F6265.m_verify())); }
''', encoding="utf-8")
    executable = temp / ("sorter.exe" if os.name == "nt" else "sorter")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Sorter overrides, stability and shared storage passed")
