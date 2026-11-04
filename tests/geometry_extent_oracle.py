"""Exercise the nested decimal arrays returned by geometry.extent()."""
from pathlib import Path
import os
import subprocess
import tempfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    source = temp / "Extent.bl"
    source.write_text('''public class Extent {
    public static int run() {
        geometry[] points = {geometry.point(-2, 3, 4326), geometry.point(5, 9, 4326)};
        decimal[][] bounds = geometry.line(points).extent();
        if (bounds.size() != 2) return 1;
        if (bounds[0][0] != -2.0) return 2;
        if (bounds[0][1] != 3.0) return 3;
        if (bounds[1][0] != 5.0) return 4;
        if (bounds[1][1] != 9.0) return 5;
        bounds[0][0] = 8;
        return bounds[0][0] == 8 ? 0 : 3;
    }
}''', encoding="utf-8")
    generated = temp / "generated.d"
    output = subprocess.check_output([str(compiler), "compile", str(source)], text=True, encoding="utf-8")
    generated.write_text(output + '\nimport std.stdio : writeln; void main() { writeln(z8_optional_require(Z8_Extent.m_run())); }\n', encoding="utf-8")
    executable = temp / ("extent.exe" if os.name == "nt" else "extent")
    subprocess.run(["dmd", str(generated), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True).strip()
    assert actual == "0", actual
print("Nested geometry extent values verified")
