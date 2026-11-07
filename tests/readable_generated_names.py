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
    for package in ("alpha", "beta", "demo", "p_pkg", "Names"):
        (source / package).mkdir(parents=True)
    other = temp / "dependency"
    (other / "names").mkdir(parents=True)
    (other / "demo").mkdir()
    (source / "alpha/Thing.bl").write_text("public class Thing { public static int value() { return 11; } }", encoding="utf-8")
    (source / "beta/Thing.bl").write_text("public class Thing { public static int value() { return 22; } }", encoding="utf-8")
    (source / "beta/Use.bl").write_text("import beta.Thing; public class Use { public static int value() { return Thing.value(); } }", encoding="utf-8")
    (source / "demo/version.bl").write_text("public class version { public static int value() { return 1; } }", encoding="utf-8")
    (source / "demo/version_.bl").write_text("public class version_ {}", encoding="utf-8")
    (source / "demo/version__.bl").write_text("public class version__ {}", encoding="utf-8")
    (source / "demo/My_Name.bl").write_text("public class My_Name {}", encoding="utf-8")
    (source / "demo/Документ.bl").write_text("public class Документ {}", encoding="utf-8")
    (source / "demo/\u0301Start.bl").write_text(
        "public class \u0301Start { public static int e\u0301() { int a\u203Fb = 42; return a\u203Fb; } }", encoding="utf-8")
    (source / "demo/€Rates.bl").write_text(
        'public class €Rates { public static int €value() { int fee\u200C = 42; int hidden\u0085part = 0; return fee\u200C + hidden\u0085part; } public static int _z8id_6D5FE282AC76616C7565() { return 9; } }', encoding="utf-8")
    (source / "demo/__Hidden.bl").write_text("public class __Hidden {}", encoding="utf-8")
    (source / "demo/_z8_Probe.bl").write_text("public class _z8_Probe {}", encoding="utf-8")
    (source / "demo/p_Thing.bl").write_text("public class p_Thing {}", encoding="utf-8")
    (source / "p_pkg/p_Item.bl").write_text("public class p_Item {}", encoding="utf-8")
    (source / "Names/First.bl").write_text("public class First {}", encoding="utf-8")
    (other / "names/Second.bl").write_text("public class Second {}", encoding="utf-8")
    (source / "demo/Upper.bl").write_text("public class Upper {}", encoding="utf-8")
    (other / "demo/upper.bl").write_text("public class upper {}", encoding="utf-8")
    (source / "native_registry.bl").write_text("public class native_registry {}", encoding="utf-8")
    (source / "project_registry.bl").write_text("public class project_registry {}", encoding="utf-8")
    (source / "entry.bl").write_text("public class entry {}", encoding="utf-8")
    (source / "NativeProbe.bl").write_text('[native "test.Native"] public class NativeProbe {}', encoding="utf-8")
    (source / "Registered.bl").write_text('[entry] public class Registered {}', encoding="utf-8")
    (source / "demo/Main.bl").write_text("import alpha.Thing; import beta.Use; import demo.version; import demo.Документ; import demo.€Rates; public class Main { public static int value() { return Thing.value() + Use.value() + version.value(); } public static int extra() { return €Rates.€value() + €Rates._z8id_6D5FE282AC76616C7565() - 9; } public static Документ create() { return new Документ; } }", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated), "--dependency", str(other)], check=True)
    main = (generated / "z8gen/demo/Main.d").read_text(encoding="utf-8")
    assert "class Z8_Main" in main and "Z8q_alpha_2EThing.m_value()" in main
    assert "Z8_Use.m_value()" in main and "Z8_version.m_value()" in main
    assert "import z8gen.demo.Документ;" in main
    assert "alias Z8p_64656D6F2E4D61696E = Z8_Main;" in main
    assert "class Z8q_beta_2EThing" in (generated / "z8gen/beta/Thing.d").read_text(encoding="utf-8")
    assert (generated / "z8gen/_z8_4E616D6573/First.d").is_file()
    assert (generated / "z8gen/_z8_6E616D6573/Second.d").is_file()
    assert (generated / "z8gen/demo/_z8_5570706572.d").is_file()
    assert (generated / "z8gen/demo/_z8_7570706572.d").is_file()
    assert (generated / "z8gen/demo/_z8_CC815374617274.d").is_file()
    assert (generated / "z8gen/demo/_z8_E282AC5261746573.d").is_file()
    assert (generated / "z8gen/native_registry.d").is_file()
    assert (generated / "z8gen/project_registry.d").is_file()
    for name in ("native_registry", "project_registry", "entry"):
        assert (generated / "z8gen" / ("_z8_" + name.encode().hex().upper() + ".d")).is_file()
    # A separately compiled old-style module remains discoverable alongside
    # new BL package names that themselves begin with p_.
    legacy = generated / "z8gen/p_legacy/p_Old_5FName.d"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('''module z8gen.p_legacy.p_Old_5FName;
import z8.runtime;
class Z8_Old_5FName : Z8Object { override wstring z8_class_id() { return "legacy.Old_Name"w; } }
''', encoding="utf-8")
    for name in ("version_.d", "version__.d", "version___.d", "My_Name.d", "Документ.d", "p_Thing.d", "_z8_5F5F48696464656E.d", "_z8_5F7A385F50726F6265.d"):
        assert (generated / "z8gen/demo" / name).is_file(), name
    harness = temp / "main.d"
    harness.write_text('''
import z8gen.demo.Main;
import z8gen.alpha.Thing;
import z8gen.beta.Thing;
import z8gen.demo.My_Name;
import z8gen.demo.Документ;
import z8gen.demo._z8_CC815374617274;
import z8gen.demo.version__;
import z8gen.demo.version___;
import z8gen.demo._z8_5F5F48696464656E;
import z8gen.demo._z8_5F7A385F50726F6265;
import z8gen.demo.p_Thing;
import z8gen.p_pkg.p_Item;
import z8gen.p_legacy.p_Old_5FName;
import z8gen._z8_4E616D6573.First;
import z8gen._z8_6E616D6573.Second;
import z8gen.demo._z8_5570706572;
import z8gen.demo._z8_7570706572;
import z8gen._z8_6E61746976655F7265676973747279;
import z8gen._z8_70726F6A6563745F7265676973747279;
import z8gen._z8_656E747279;
import z8.runtime;
void main() {
    assert(Z8_Main.m_value() == 34);
    assert(Z8_Main.m_extra() == 42);
    assert(Z8_\u0301Start.m_e\u0301() == 42);
    assert(Z8_Main.m_create().z8_class_id() == "demo.Документ"w);
    assert(Z8p_64656D6F2E4D61696E.m_value() == 34);
    assert(Z8p_616C7068612E5468696E67.m_value() == 11);
    assert(Z8p_626574612E5468696E67.m_value() == 22);
    assert(z8_object_new_instance("demo.Main"w).z8_class_id() == "demo.Main"w);
    assert(z8_object_new_instance("alpha.Thing"w).z8_class_id() == "alpha.Thing"w);
    assert(z8_object_new_instance("beta.Thing"w).z8_class_id() == "beta.Thing"w);
    assert(z8_object_new_instance("demo.My_Name"w).z8_class_id() == "demo.My_Name"w);
    assert(z8_object_new_instance("demo.Документ"w).z8_class_id() == "demo.Документ"w);
    assert(z8_object_new_instance("demo.€Rates"w).z8_class_id() == "demo.€Rates"w);
    assert(z8_object_new_instance("demo.version_"w).z8_class_id() == "demo.version_"w);
    assert(z8_object_new_instance("demo.version__"w).z8_class_id() == "demo.version__"w);
    assert(z8_object_new_instance("demo.__Hidden"w).z8_class_id() == "demo.__Hidden"w);
    assert(z8_object_new_instance("demo._z8_Probe"w).z8_class_id() == "demo._z8_Probe"w);
    assert(z8_object_new_instance("demo.p_Thing"w).z8_class_id() == "demo.p_Thing"w);
    assert(z8_object_new_instance("p_pkg.p_Item"w).z8_class_id() == "p_pkg.p_Item"w);
    assert(z8_object_new_instance("legacy.Old_Name"w).z8_class_id() == "legacy.Old_Name"w);
    assert(z8_object_new_instance("Names.First"w).z8_class_id() == "Names.First"w);
    assert(z8_object_new_instance("names.Second"w).z8_class_id() == "names.Second"w);
    assert(z8_object_new_instance("demo.Upper"w).z8_class_id() == "demo.Upper"w);
    assert(z8_object_new_instance("demo.upper"w).z8_class_id() == "demo.upper"w);
    assert(z8_object_new_instance("native_registry"w).z8_class_id() == "native_registry"w);
    assert(z8_object_new_instance("project_registry"w).z8_class_id() == "project_registry"w);
    assert(z8_object_new_instance("entry"w).z8_class_id() == "entry"w);
}
''', encoding="utf-8")
    exe = temp / ("names.exe" if os.name == "nt" else "names")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(exe)], check=True)
print("Readable names, package collisions, D keywords and compatibility aliases verified")
