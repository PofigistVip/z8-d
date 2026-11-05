"""Compare native Object equality and attributes with the original runtime.

Usage: python tests/object_runtime_oracle.py <original-z8-root>
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/object_runtime_oracle.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
original = Path(sys.argv[1]).resolve()
language = original / "org.zenframework.z8.lang/src/bl"
jars = sorted((original / "org.zenframework.z8.server/target/libs").glob("*.jar"))
if not language.is_dir() or not any(p.name.startswith("org.zenframework.z8.server-") for p in jars):
    raise SystemExit("Original BL library or server JAR not found")
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
for dependency in (cache / "commons-logging/commons-logging", cache / "org.zenframework.z8.dependencies.commons",
                   cache / "commons-io/commons-io/2.7"):
    if dependency.exists():
        jars.extend(p for p in dependency.rglob("*.jar") if not p.name.endswith("-sources.jar"))
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "Probe.bl").write_text("""
import org.zenframework.z8.lang.Object;
public class Probe {
    public static Object create() { return new Object; }
    public static string get(Object value, string name) { return value.getAttribute(name); }
    public static void put(Object value, string name, primary entry) { value.setAttribute(name, entry); }
    public static string display(Object value) { return value.displayName(); }
    public static void setDisplay(Object value, string name) { value.setDisplayName(name); }
    public static string render(Object value) { return value.toString(); }
    public static bool equal(Object left, Object right) { return left == right; }
    public static bool different(Object left, Object right) { return left != right; }
    public static string id(Object value) { return value.id(); }
    public static string index(Object value) { return value.index(); }
    public static string name(Object value) { return value.name(); }
    public static string className(Object value) { return value.className(); }
    public static guid key(Object value) { return value.key(); }
    public static void setId(Object value, string id) { value.setId(id); }
}
""", encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    config = temp / "server.properties"
    config.write_text("application.language=en\n", encoding="utf-8")
    resources = temp / "resources"
    resources.mkdir()
    (resources / "test_en.nls").write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">
<properties><entry key="test.login">Alice localized</entry></properties>''', encoding="utf-8")
    java = temp / "ObjectOracle.java"
    java.write_text("""
import org.zenframework.z8.server.runtime.OBJECT;
import org.zenframework.z8.server.types.*;
class ObjectOracle {
    public static void main(String[] args) throws Exception {
        org.zenframework.z8.server.config.ServerConfig.load(args[0]);
        OBJECT.CLASS<OBJECT> a = new OBJECT.CLASS<OBJECT>(null), b = new OBJECT.CLASS<OBJECT>(null);
        OBJECT value = a.get();
        System.out.println(value.z8_getAttribute(new string("missing")).get());
        System.out.println(value.z8_toString().get());
        System.out.println(value.z8_displayName().get());
        value.z8_setDisplayName(new string("Display"));
        System.out.println(value.z8_displayName().get());
        value.z8_setAttribute(new string("number"), new integer(42));
        value.z8_setAttribute(new string("flag"), new bool(true));
        value.z8_setAttribute(new string("text"), new string("$test.login$"));
        for (String key : new String[] {"number", "flag", "text"})
            System.out.println(value.z8_getAttribute(new string(key)).get());
        value.z8_setAttribute(new string("number"), new integer(-7));
        System.out.println(value.z8_getAttribute(new string("number")).get());
        System.out.println(value.operatorEqu(a).get() + ":" + value.operatorEqu(b).get());
        System.out.println(value.operatorNotEqu(a).get() + ":" + value.operatorNotEqu(b).get());
        try { value.operatorEqu(null); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        try { value.z8_setAttribute(new string("x"), null); System.out.println("bad"); } catch (RuntimeException expected) { System.out.println("error"); }
        OBJECT.CLASS<OBJECT> child = new OBJECT.CLASS<OBJECT>(value);
        child.setIndex("child");
        OBJECT member = child.get();
        System.out.println(value.z8_id().get() + ":" + value.z8_index().get());
        System.out.println(member.z8_id().get() + ":" + member.z8_index().get());
        System.out.println(member.z8_name().get());
        System.out.println(member.z8_className().get());
        System.out.println(member.z8_key().toString());
        member.z8_setAttribute(new string("name"), new string("Changed"));
        System.out.println(member.z8_name().get() + ":" + member.z8_key().toString());
        member.z8_setId(new string("renamed"));
        System.out.println(member.z8_id().get() + ":" + member.z8_index().get());
    }
}
""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp) + os.pathsep + classpath, "ObjectOracle", str(config)],
                                       cwd=temp, text=True, encoding="utf-8").splitlines()
    harness = temp / "main.d"
    harness.write_text("""
import z8.runtime;
import z8gen.p_Probe;
import std.stdio : writeln;
import std.conv : to;
void main() {
    alias P = Z8p_50726F6265;
    z8_string_set_resource("test.login"w, "Alice localized"w);
    auto a = P.m_create(), b = P.m_create();
    writeln(P.m_get(a, "missing"w).to!string);
    writeln(P.m_render(a).to!string);
    writeln(P.m_display(a).to!string);
    P.m_setDisplay(a, "Display"w);
    writeln(P.m_display(a).to!string);
    P.m_put(a, "number"w, z8_primary_box(42L));
    P.m_put(a, "flag"w, z8_primary_box(true));
    P.m_put(a, "text"w, z8_primary_box(z8_string_new("$test.login$"w)));
    foreach (key; ["number"w, "flag"w, "text"w]) writeln(P.m_get(a, key).to!string);
    P.m_put(a, "number"w, z8_primary_box(-7L));
    writeln(P.m_get(a, "number"w).to!string);
    writeln(z8_optional_require(P.m_equal(a, a)), ":", z8_optional_require(P.m_equal(a, b)));
    writeln(z8_optional_require(P.m_different(a, a)), ":", z8_optional_require(P.m_different(a, b)));
    try { P.m_equal(a, null); writeln("bad"); } catch (Exception) { writeln("error"); }
    try { P.m_put(a, "x"w, null); writeln("bad"); } catch (Exception) { writeln("error"); }
    auto child = P.m_create(); child.z8_set_container(a); child.z8_set_index("child"w);
    writeln(P.m_id(a).to!string, ":", P.m_index(a).to!string);
    writeln(P.m_id(child).to!string, ":", P.m_index(child).to!string);
    writeln(P.m_name(child).to!string);
    writeln(P.m_className(child).to!string);
    writeln(z8_guid_to_string(P.m_key(child)).to!string);
    P.m_put(child, "name"w, z8_primary_box("Changed"w));
    writeln(P.m_name(child).to!string, ":", z8_guid_to_string(P.m_key(child)).to!string);
    P.m_setId(child, "renamed"w);
    writeln(P.m_id(child).to!string, ":", P.m_index(child).to!string);
    z8_native_clear_bindings();
    z8_bind_builtin_object();
    assert(P.m_get(P.m_create(), "missing"w) == ""w);
}
""", encoding="utf-8")
    executable = temp / ("object.exe" if os.name == "nt" else "object")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    actual = subprocess.check_output([str(executable)], cwd=temp, text=True, encoding="utf-8").splitlines()
    if actual != expected:
        raise SystemExit(f"Object differs:\nJava={expected!r}\nD={actual!r}")
print("Object attributes and equality match Java")
