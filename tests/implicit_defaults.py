"""Compile and execute nullable implicit defaults for BL enum and primary."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory)
    (source / "Mode.bl").write_text("public enum Mode { First, Second }", encoding="utf-8")
    (source / "Defaults.bl").write_text('''
public class Defaults {
    public primary field;
    public static primary shared;
    public Mode state;
    public static int run() {
        primary value; Mode mode; Defaults object;
        if (value != null || mode != null || object.field != null || Defaults.shared != null || object.state != null) return 1;
        value = 7; mode = Mode.Second; object.field = "ready"; Defaults.shared = value; object.state = mode;
        if ((int)value != 7 || (int)Defaults.shared != 7 || (string)object.field != "ready" || object.state != Mode.Second) return 2;
        value = null; mode = null;
        if (value != null || mode != null) return 3;
        return 0;
    }
}
''', encoding="utf-8")
    executable = source / ("defaults.exe" if os.name == "nt" else "defaults")
    subprocess.run([str(compiler), "build", str(source), "Defaults.run", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("Implicit enum and primary defaults verified")
