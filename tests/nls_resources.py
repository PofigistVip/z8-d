"""Compare loading Java XML-properties resources with the original format."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from runtime_support import runtime_library, import_args

with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    nls = temp / "sample_ru.nls"
    nls.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">
<properties><comment>Test resources</comment>
<entry key="bool.true">да</entry><entry key="bool.false">нет</entry>
<entry key="hello">Привет &amp; &#x1F600;</entry>
<entry key="empty"/><entry key="escaped&amp;key">&lt;tag&gt; &quot;x&quot;</entry>
<entry key="duplicate">old</entry><entry key="duplicate"><![CDATA[new]]></entry>
</properties>''', encoding="utf-8")
    bad = temp / "bad.nls"
    bad.write_text('<properties><entry key="hello">changed</entry><entry>invalid</entry></properties>', encoding="utf-8")
    java = temp / "NlsOracle.java"
    java.write_text('''import java.io.FileInputStream;
import java.util.Properties;
class NlsOracle {
    public static void main(String[] args) throws Exception {
        Properties p = new Properties();
        try (FileInputStream in = new FileInputStream(args[0])) { p.loadFromXML(in); }
        for (String key : new String[]{"bool.true", "bool.false", "hello", "empty", "escaped&key", "duplicate"})
            System.out.println(p.getProperty(key));
    }
}
''', encoding="utf-8")
    subprocess.run(["javac", "-source", "8", "-target", "8", str(java)], cwd=temp, check=True)
    expected = subprocess.check_output(["java", "-Dfile.encoding=UTF-8", "-cp", str(temp), "NlsOracle", str(nls)], cwd=temp, text=True, encoding="utf-8").splitlines()
    source = temp / "nls.d"
    source.write_text('''import z8.runtime;
import std.stdio : writeln;
import std.conv : to;
void main(string[] args) {
    assert(z8_string_load_nls(args[1]) == 6);
    foreach (key; ["bool.true"w, "bool.false"w, "hello"w, "empty"w, "escaped&key"w, "duplicate"w])
        writeln(z8_string_new("$"w ~ key ~ "$"w).to!string);
    assert(z8_bool_parse("ДА"w));
    assert(!z8_bool_parse("нет"w));
    bool rejected;
    try { z8_string_load_nls(args[2]); } catch (Exception) { rejected = true; }
    assert(rejected);
    assert(z8_string_new("$hello$"w) == "Привет & 😀"w);
    if (args.length > 3) {
        z8_string_clear_resources();
        assert(z8_string_load_nls(args[3]) > 2);
        assert(z8_string_new("$bool.true$"w) == "да"w);
        assert(z8_bool_parse("ДА"w));
    }
}
''', encoding="utf-8")
    executable = temp / ("nls.exe" if os.name == "nt" else "nls")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    command = [str(executable), str(nls), str(bad)]
    if len(sys.argv) > 1:
        command.append(str(Path(sys.argv[1]).resolve()))
    actual = subprocess.check_output(command, cwd=temp, text=True, encoding="utf-8").splitlines()
    assert actual == expected, (expected, actual)
print("NLS resources match Java XML properties")
