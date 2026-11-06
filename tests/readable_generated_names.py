"""Compile readable, collision-safe generated names and legacy aliases."""
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
    for package in ("alpha", "beta", "demo"):
        (source / package).mkdir(parents=True)
    (source / "alpha/Thing.bl").write_text("public class Thing { public static int value() { return 11; } }", encoding="utf-8")
    (source / "beta/Thing.bl").write_text("public class Thing { public static int value() { return 22; } }", encoding="utf-8")
    (source / "beta/Use.bl").write_text("import beta.Thing; public class Use { public static int value() { return Thing.value(); } }", encoding="utf-8")
    (source / "demo/version.bl").write_text("public class version { public static int value() { return 1; } }", encoding="utf-8")
    (source / "demo/My_Name.bl").write_text("public class My_Name {}", encoding="utf-8")
    (source / "demo/Main.bl").write_text("import alpha.Thing; import beta.Use; import demo.version; public class Main { public static int value() { return Thing.value() + Use.value() + version.value(); } }", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    main = (generated / "z8gen/p_demo/p_Main.d").read_text(encoding="utf-8")
    assert "class Z8_Main" in main and "Z8q_alpha_2EThing.m_value()" in main
    assert "Z8_Use.m_value()" in main and "Z8_version.m_value()" in main
    assert "alias Z8p_64656D6F2E4D61696E = Z8_Main;" in main
    assert "class Z8q_beta_2EThing" in (generated / "z8gen/p_beta/p_Thing.d").read_text(encoding="utf-8")
    harness = temp / "main.d"
    harness.write_text('''
import z8gen.p_demo.p_Main;
import z8gen.p_alpha.p_Thing;
import z8gen.p_beta.p_Thing;
import z8gen.p_demo.p_My_5FName;
import z8.runtime;
void main() {
    assert(Z8_Main.m_value() == 34);
    assert(Z8p_64656D6F2E4D61696E.m_value() == 34);
    assert(Z8p_616C7068612E5468696E67.m_value() == 11);
    assert(Z8p_626574612E5468696E67.m_value() == 22);
    assert(z8_object_new_instance("demo.Main"w).z8_class_id() == "demo.Main"w);
    assert(z8_object_new_instance("alpha.Thing"w).z8_class_id() == "alpha.Thing"w);
    assert(z8_object_new_instance("beta.Thing"w).z8_class_id() == "beta.Thing"w);
    assert(z8_object_new_instance("demo.My_Name"w).z8_class_id() == "demo.My_Name"w);
}
''', encoding="utf-8")
    exe = temp / ("names.exe" if os.name == "nt" else "names")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(exe)], check=True)
print("Readable names, package collisions, D keywords and compatibility aliases verified")
