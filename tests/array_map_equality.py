from pathlib import Path
import os
import shutil
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
fixtures = root / "examples" / "project" / "demo" / "cases"
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    for name in ("ArrayMapEquality.bl", "KeyItem.bl"):
        shutil.copy2(fixtures / name, temp / name)
    executable = temp / ("array_map_equality.exe" if os.name == "nt" else "array_map_equality")
    subprocess.run([str(compiler), "build", str(temp), "ArrayMapEquality.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 117:
        raise SystemExit(f"Map equality in arrays failed: {result.returncode}")
    (temp / "NullableMapEquality.bl").write_text("""public class NullableMapEquality {
        public static int run() {
            int[string] a; int[string] b;
            a.add("x", null); b.add("x", null);
            int[string][] numbers = {a};
            if (!numbers.contains(b)) return 1;
            b.clear(); b.add("y", null);
            if (numbers.contains(b)) return 2;
            string[string] c; string[string] d;
            c.add("x", null); d.add("x", null);
            string[string][] strings = {c};
            if (!strings.contains(d)) return 3;
            decimal[int] e; decimal[int] f;
            e.add(1, null); f.add(1, null);
            decimal[int][] decimals = {e};
            if (!decimals.contains(f)) return 4;
            return 119;
        }
    }""", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "NullableMapEquality.run", str(executable)], check=True)
    result = subprocess.run([str(executable)])
    if result.returncode != 119:
        raise SystemExit(f"Nullable map equality failed: {result.returncode}")
    shutil.copy2(fixtures / "MapFlavor.bl", temp / "MapFlavor.bl")
    keys = {
        "string": '"key"', "int": "1", "guid": "'00000000-0000-0000-0000-000000000001'",
        "bool": "true", "decimal": "1.5", "primary": "1", "date": "day", "datespan": "span",
        "binary": "bytes", "geometry": "shape", "file": "path", "KeyItem": "item", "MapFlavor": "MapFlavor.First",
    }
    body = ["date day = '01/01/2024';", "datespan span = '1 02:03:04';", "binary bytes = '1, 2';", "geometry shape;", 'file path = "sample.txt";', "KeyItem item = new KeyItem;"]
    for key_type, key in keys.items():
        body.append(f"int[{key_type}] a_{key_type} = {{({key}, 4)}}; int[{key_type}] b_{key_type} = {{({key}, 4)}};")
        body.append(f"int[{key_type}][] c_{key_type} = {{a_{key_type}}}; if (!c_{key_type}.contains(b_{key_type})) return 1;")
    (temp / "AllMapEqualities.bl").write_text("public class AllMapEqualities { public static int run() { " + " ".join(body) + " return 121; } }", encoding="utf-8")
    subprocess.run([str(compiler), "build", str(temp), "AllMapEqualities.run", str(executable)], check=True)
    if subprocess.run([str(executable)]).returncode != 121:
        raise SystemExit("Map equality combinations failed")
print("Map equality in arrays verified")
