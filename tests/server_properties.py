"""Compare server.properties parsing with java.util.Properties.load."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/server_properties.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "PropertiesProbe.bl").write_text('''
import org.zenframework.z8.base.application.ServerConfig;
public class PropertiesProbe { public static string get(string key) { return ServerConfig.get(key); } }
''', encoding="utf-8")
    properties = temp / "server.properties"
    properties.write_bytes(
        b"  # comment\r\n! comment\nalpha=old\nalpha:updated\n"
        b"spaces\\ key\\:  =  spaced value  \r\nempty=\r\n=empty key\n"
        b"lines=first\\\r\n  second\\\n \t!not-a-comment\n"
        b"latin=caf\xe9\nunicode=\\u041f\\u0440\\u0438\\u0432\\u0435\\u0442 \\uD83D\\uDE00\n"
        b"escaped=one\\ttwo\\nthree\\\\four\\:five\\=six\\q\nnoSep\n"
        b"trailing=pair\\\\\napplication.working.path=work\nstorage.path=files\n"
        b"application.language=en\nresource=$hello$\n"
    )
    resources = temp / "resources"
    resources.mkdir()
    (resources / "sample_ru.nls").write_text('<properties><entry key="hello">Russian</entry><entry key="only.ru">yes</entry></properties>', encoding="utf-8")
    (resources / "sample_en.nls").write_text('<properties><entry key="hello">English</entry><entry key="bool.true">certainly</entry></properties>', encoding="utf-8")
    (resources / "bad_zz.nls").write_text('<properties><entry key="broken">', encoding="utf-8")
    resource_override = temp / "override.nls"
    resource_override.write_text('<properties><entry key="hello">Override</entry></properties>', encoding="utf-8")
    other_resources = temp / "other-resources"
    other_resources.mkdir()
    (other_resources / "sample_en.xml").write_text('<properties><entry key="hello">Other directory</entry></properties>', encoding="utf-8")
    malformed = temp / "bad.properties"
    malformed.write_bytes(b"alpha=replace\nbad=\\uZZZZ\n")
    java = temp / "PropertiesOracle.java"
    java.write_text('''
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
public class PropertiesOracle {
    public static void main(String[] args) throws Exception {
        Properties properties = new Properties();
        try (InputStream input = new FileInputStream(args[0])) { properties.load(input); }
        for (String key : new String[] {"alpha", "spaces key:", "empty", "", "lines", "latin", "unicode", "escaped", "noSep", "trailing", "missing"}) {
            String value = properties.getProperty(key);
            System.out.println(value == null ? "<null>" : Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));
        }
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "--release", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-cp", str(temp), "PropertiesOracle", str(properties)], cwd=temp, text=True).splitlines()
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_PropertiesProbe;
import std.base64 : Base64;
import std.conv : to;
import std.stdio : writeln;
import std.file : exists;
import std.path : buildPath, dirName;
void main(string[] args) {
    alias P = Z8p_50726F7065727469657350726F6265;
    z8_server_config_load_file(args[1]);
    foreach (key; ["alpha"w, "spaces key:"w, "empty"w, ""w, "lines"w, "latin"w, "unicode"w, "escaped"w, "noSep"w, "trailing"w, "missing"w]) {
        auto value = P.m_get(key);
        if (value is null) writeln("<null>");
        else writeln(Base64.encode(cast(const(ubyte)[])z8_to_utf8(value)));
    }
    bool failed; try { z8_server_config_load_file(args[2]); } catch (Exception) { failed = true; }
    assert(failed && P.m_get("alpha"w) == "updated"w);
    z8_server_config_load_file(args[1], ["alpha"w:"override"w]);
    assert(P.m_get("alpha"w) == "override"w);
    auto dangling = z8_properties_parse([cast(ubyte)92]);
    assert(dangling.length == 1 && (""w in dangling) !is null && dangling[""w] == ""w);
    z8_server_configure_from_file(args[1]);
    assert(P.m_get("resource"w) == args[3].to!wstring);
    if (args[3] == "English") {
        assert(z8_string_new("$only.ru$"w) == "only.ru"w && z8_bool_parse("certainly"w));
        bool invalidResources;
        try { z8_string_configure_nls(dirName(args[1]), "zz"w); } catch (Exception) { invalidResources = true; }
        assert(invalidResources && P.m_get("resource"w) == "English"w);
    }
    z8_file_write(z8_file_from_path("probe.txt"w), "data"w);
    assert(exists(buildPath(dirName(args[1]), "work", "probe.txt")));
    z8_file_write(z8_file_from_path("storage/probe.txt"w), "data"w);
    assert(exists(buildPath(dirName(args[1]), "work", "files", "probe.txt")));
    auto resource = z8_native_call!Z8File("org.zenframework.z8.server.base.application.Resources.m_loadResource"w, "server.properties"w);
    assert(z8_file_exists(resource));
}
''', encoding="utf-8")
    executable = temp / ("properties.exe" if os.name == "nt" else "properties")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    environment = dict(os.environ)
    for key in ("Z8_LANGUAGE", "Z8_NLS_DIR", "Z8_NLS_FILES"):
        environment.pop(key, None)
    for selected, overrides in (("English", {}), ("Russian", {"Z8_LANGUAGE": "ru"}),
                                ("Other directory", {"Z8_NLS_DIR": str(other_resources)}),
                                ("Override", {"Z8_NLS_FILES": str(resource_override)})):
        actual = subprocess.check_output([str(executable), str(properties), str(malformed), selected], cwd=temp,
                                         env=environment | overrides, text=True).splitlines()
        if actual != expected:
            raise SystemExit(f"Properties differ:\nJava={expected!r}\nD={actual!r}")
print("Server properties match java.util.Properties for tested cases")
