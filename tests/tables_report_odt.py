"""Compare rendering of the original system Tables.odt with JOODoc.

Usage: python tests/tables_report_odt.py <original-z8-root>
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/tables_report_odt.py <original-z8-root>")
original = Path(sys.argv[1]).resolve()
template = original / "org.zenframework.z8.server/WEB-INF/reports/system/Tables.odt"
bundled = Path(__file__).resolve().parents[1] / "runtime/source/z8_tables_report_template.odt"
cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
libre = cache / "org.zenframework.z8.dependencies.libreoffice"
jars = [p for name in ("jodreports-2.4.0", "freemarker-2.3.32", "xom-1.3.8")
        for p in (libre / name / "3.4-cert").rglob("*.jar") if not p.name.endswith("-sources.jar")]
jars += [p for name in ("commons-io/commons-io/2.7", "org.slf4j/slf4j-api/1.7.36")
         for p in (cache / name).rglob("*.jar") if not p.name.endswith("-sources.jar")]
if not template.is_file() or len(jars) < 5:
    raise SystemExit("Original Tables.odt or cached JOODoc dependencies not found")
assert bundled.read_bytes() == template.read_bytes(), "Bundled Tables.odt differs from the original"

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    java = temp / "TablesOdtOracle.java"
    java.write_text('''import java.io.*;
import java.util.*;
import net.sf.jooreports.templates.*;
class TablesOdtOracle {
  static Map<String,Object> field(String name, String type, String description, int sequence) {
    Map<String,Object> value = new HashMap<>();
    value.put("name", name); value.put("type", type); value.put("description", description);
    value.put("sequence", String.valueOf(sequence)); return value;
  }
  static Map<String,Object> table(String name, String id, String description, List<Object> fields) {
    Map<String,Object> value = new HashMap<>();
    value.put("name", name); value.put("classId", id); value.put("description", description);
    value.put("fields", fields); return value;
  }
  public static void main(String[] args) throws Exception {
    int mode = Integer.parseInt(args[2]); List<Object> tables = new ArrayList<>();
    if (mode == 1) tables.add(table("Таблица & <имя>", "demo.Table", "Описание ${field.name}  два", Arrays.asList(
      field("Имя & <поле>", "String", "Первая строка\\nВторая", 1), field("${table.name}", "Integer", "a > b\\tend\\rnext\\r\\nlast", 2))));
    if (mode == 2) {
      tables.add(table("Пустая", "demo.Empty", "", Collections.emptyList()));
      tables.add(table("Вторая", "demo.Second", "Описание", Arrays.asList(field("Код", "Guid", "id", 1))));
    }
    if (mode == 3) for (int i = 0; i < 40; i++) {
      List<Object> fields = new ArrayList<>();
      for (int j = 0; j < 5; j++) fields.add(field("Field" + j, "String", "description", j + 1));
      tables.add(table("Table" + i, "demo.Table" + i, "description", fields));
    }
    Map<String,Object> data = new HashMap<>(); data.put("tables", tables);
    DocumentTemplate document = new DocumentTemplateFactory().getTemplate(new FileInputStream(args[0]));
    try (OutputStream output = new FileOutputStream(args[1])) { document.createDocument(data, output); }
  }
}''', encoding="utf-8")
    classpath = os.pathsep.join(map(str, [temp, *jars]))
    subprocess.run(["javac", "-source", "8", "-target", "8", "-encoding", "UTF-8", "-cp", classpath, str(java)], cwd=temp, check=True)
    source = temp / "main.d"
    source.write_text('''import z8.runtime;
import std.file : read, write;
import std.conv : to;
void main(string[] args) {
    Z8TablesReportTable[] tables;
    if (args[3] == "1") tables ~= Z8TablesReportTable("Таблица & <имя>"w, "demo.Table"w,
        "Описание ${field.name}  два"w, [Z8TablesReportField("Имя & <поле>"w, "String"w, "Первая строка\\nВторая"w),
                                        Z8TablesReportField("${table.name}"w, "Integer"w, "a > b\\tend\\rnext\\r\\nlast"w)]);
    if (args[3] == "2") {
        tables ~= Z8TablesReportTable("Пустая"w, "demo.Empty"w, ""w, null);
        tables ~= Z8TablesReportTable("Вторая"w, "demo.Second"w, "Описание"w,
            [Z8TablesReportField("Код"w, "Guid"w, "id"w)]);
    }
    if (args[3] == "3") foreach (i; 0 .. 40) {
        Z8TablesReportField[] fields;
        foreach (j; 0 .. 5) fields ~= Z8TablesReportField("Field"w ~ j.to!wstring, "String"w, "description"w);
        tables ~= Z8TablesReportTable("Table"w ~ i.to!wstring, "demo.Table"w ~ i.to!wstring, "description"w, fields);
    }
    write(args[2], z8_tables_report_render(cast(ubyte[])read(args[1]), tables));
}''', encoding="utf-8")
    executable = temp / ("tables-odt.exe" if os.name == "nt" else "tables-odt")
    subprocess.run(["dmd", str(source), *import_args(), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)

    def structure(path):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert archive.infolist()[0].filename == "mimetype" and archive.infolist()[0].compress_type == zipfile.ZIP_STORED
            root = ET.fromstring(archive.read("content.xml"))
            text = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
            row = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row"
            text_ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
            def visible(item):
                value = item.text or ""
                for child in item:
                    if child.tag == text_ns + "line-break": value += "\n"
                    elif child.tag == text_ns + "tab": value += "\t"
                    elif child.tag == text_ns + "s": value += " " * int(child.get(text_ns + "c", "1"))
                    else: value += visible(child)
                    value += child.tail or ""
                return value
            return ([visible(item) for item in root.iter(text)], len(list(root.iter(row))))

    for mode in range(4):
        expected, actual = temp / f"java-{mode}.odt", temp / f"d-{mode}.odt"
        subprocess.run(["java", "-cp", classpath, "TablesOdtOracle", str(template), str(expected), str(mode)], cwd=temp, check=True)
        subprocess.run([str(executable), str(template), str(actual), str(mode)], cwd=temp, check=True)
        if structure(actual) != structure(expected):
            with zipfile.ZipFile(expected) as archive:
                xml = archive.read("content.xml").decode("utf-8")
                marker = xml.find("Первая")
                print("Original field XML:", repr(xml[max(0, marker - 100):marker + 300]))
                marker = xml.find("a &gt; b")
                print("Original whitespace XML:", repr(xml[max(0, marker - 50):marker + 180]))
            raise AssertionError((mode, structure(expected), structure(actual)))
        with zipfile.ZipFile(template) as source_zip, zipfile.ZipFile(actual) as actual_zip:
            for name in source_zip.namelist():
                if name != "content.xml":
                    assert source_zip.read(name) == actual_zip.read(name), name
    invalid = temp / "unsupported.odt"
    with zipfile.ZipFile(template) as source_zip, zipfile.ZipFile(invalid, "w") as output:
        for member in source_zip.infolist():
            data = source_zip.read(member.filename)
            if member.filename == "content.xml":
                data = data.replace(b"${table.name}", b"${table.unknown}")
            output.writestr(member, data)
    rejected = subprocess.run([str(executable), str(invalid), str(temp / "invalid-output.odt"), "1"], cwd=temp, capture_output=True)
    assert rejected.returncode and b"unsupported TablesReport template expression" in rejected.stderr
print("System Tables.odt content and layout match the original JOODoc engine")
