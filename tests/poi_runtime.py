"""Read XLSX workbooks through the original BL Workbook/Sheet/Row/Cell declarations."""
from pathlib import Path
import os
import subprocess
import tempfile
import zipfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    poi = source / "org/zenframework/z8/base/poi"
    lang = source / "org/zenframework/z8/lang"
    poi.mkdir(parents=True); lang.mkdir(parents=True)
    declarations = root / "vendor/z8/org.zenframework.z8.lang/src/bl/org/zenframework/z8/base/poi"
    for name in ("Workbook", "Sheet", "Row", "Cell"):
        (poi / (name + ".bl")).write_bytes((declarations / (name + ".bl")).read_bytes())
    (lang / "Object.bl").write_text('[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {}', encoding="utf-8")
    (source / "Probe.bl").write_text('''import org.zenframework.z8.base.poi.Workbook;
import org.zenframework.z8.base.poi.Sheet;
import org.zenframework.z8.base.poi.Row;
import org.zenframework.z8.base.poi.Cell;
public class Probe {
    public static int verify(file input) {
        Workbook book; book = input;
        if (book.getSheetCount() != 2) return 1;
        Sheet sheet = book.getSheet(0); if (sheet.getRowCount() != 3) return 2;
        Row row = sheet.getRow(0); if (row.getCellCount() != 4 || row.getCell(1) != null) return 3;
        if (row.getCell(0).getString() != "Hi & 😀") return 4;
        if (row.getCell(2).getInt() != 42 || row.getCell(2).getDecimal() != 42.25) return 5;
        if (row.getCell(3).getString() != "true") return 6;
        if (row.getCell(4).getString() != "C1*2" || row.getCell(4).getInt() != 84) return 7;
        Row third = sheet.getRow(2); if (third.getCellCount() != 14) return 8;
        if (third.getCell(1).getString() != "Inline Unicode") return 9;
        date day = third.getCell(2).getDate();
        if (day.year() != 2024 || day.month() != 2 || day.day() != 29 || day.hours() != 12) return 10;
        if (third.getCell(5).getString() != "" || third.getCell(5).getInt() != 0) return 11;
        date leap = third.getCell(6).getDate(); date next = third.getCell(7).getDate();
        if (leap.year() != 1900 || leap.month() != 3 || leap.day() != 1 ||
            next.year() != 1900 || next.month() != 3 || next.day() != 1) return 20;
        if (third.getCell(8).getString() != "C3*2" || third.getCell(9).getInt() != 11 ||
            third.getCell(9).getString() != "D3*2") return 21;
        if (third.getCell(11).getString() != "SUM(D3,$C3,D$3,$C$3)+IF(\\\"A1\\\"=\\\"A1\\\",0,0)+SUM(D$1:D$1048576,$D$1:$D$1048576,$A2:$XFD2,$A$3:$XFD$3)+D3+$C3+IFERROR(D3,#REF!)") return 22;
        if (sheet.getRow(3).getCell(12).getString() != "SUM(C4,$C4,C$3,$C$3,$A3:$XFD3,$A$3:$XFD$3)") return 23;
        try { string unsupported = third.getCell(14).getString(); return 24; } catch (exception expected) {}
        if (third.getCell(15).getString() != "XFD1") return 25;
        try { string bad = row.getCell(0).getInt().toString(); return 12; } catch (exception expected) {}
        try { int absent = sheet.getRow(1).getCellCount(); return 13; } catch (exception expected) {}
        if (book.getSheet(1).getRowCount() != 0) return 14;
        if (sheet.getRow(4294967296).getCell(0).getString() != "Hi & 😀" || row.getCell(4294967296).getString() != "Hi & 😀") return 16;
        if (row.getCell(16384) != null) return 17;
        try { int absent = sheet.getRow(-1).getCellCount(); return 18; } catch (exception expected) {}
        try { Cell invalid = row.getCell(-1); return 19; } catch (exception expected) {}
        book.close(); try { int bad = book.getSheetCount(); return 15; } catch (exception expected) {}
        return 0;
    }
    public static bool verify1904(file input) {
        Workbook book; book = input; date day = book.getSheet(0).getRow(2).getCell(2).getDate();
        return day.year() == 2028 && day.month() == 3 && day.day() == 1 && day.hours() == 12;
    }
    public static bool verifyPoi(file input) {
        Workbook book; book = input; Sheet sheet = book.getSheet(0); Row row = sheet.getRow(1);
        return book.getSheetCount() == 1 && sheet.getRowCount() == 1 && row.getCellCount() == 3 &&
            row.getCell(0).getString() == "Generated & 😀" && row.getCell(1).getInt() == 7 &&
            row.getCell(2).getString() == "B2*3" && row.getCell(2).getInt() == 21;
    }
    public static bool failedOpen(file good, file bad) {
        Workbook book; book = good;
        try { book = bad; return false; } catch (exception expected) {}
        try { int count = book.getSheetCount(); return false; } catch (exception expected) {}
        book = good; return book.getSheetCount() == 2;
    }
}''', encoding="utf-8")
    workbook = temp / "fixture.xlsx"
    entries = {
        "[Content_Types].xml": '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>''',
        "_rels/.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="One" sheetId="1" r:id="rId1"/><sheet name="Two" sheetId="2" r:id="rId2"/></sheets></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>''',
        "xl/sharedStrings.xml": '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><r><t>Hi &amp; </t></r><r><t>😀</t></r></si></sst>''',
        "xl/worksheets/sheet1.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>42.25</v></c><c r="D1" t="b"><v>1</v></c><c r="E1"><f>C1*2</f><v>84.5</v></c></row><row r="3"><c r="B3" t="inlineStr"><is><t>Inline Unicode</t></is></c><c r="C3"><v>45351.5</v></c><c r="F3"/><c r="G3"><v>60</v></c><c r="H3"><v>61</v></c><c r="I3"><f t="shared" si="0" ref="I3:J3">C3*2</f><v>10</v></c><c r="J3"><f t="shared" si="0"/><v>11</v></c><c r="K3"><f t="shared" si="1" ref="K3:L3">SUM(C3,$C3,C$3,$C$3)+IF("A1"="A1",0,0)+SUM(C:C,$D:$D,2:2,$3:$3)+Two!C3+'Two'!$C3+IFERROR(C3,#REF!)</f><v>20</v></c><c r="L3"><f t="shared" si="1"/><v>21</v></c><c r="M3"><f t="shared" si="2" ref="M3:M4">SUM(C3,$C3,C$3,$C$3,2:2,$3:$3)</f><v>30</v></c><c r="N3"><f t="shared" si="3" ref="N3:O3">A1 + 1</f><v>31</v></c><c r="O3"><f t="shared" si="3"/><v>32</v></c><c r="P3"><f t="shared" si="4"/><v>34</v></c><c r="Q3"><f t="shared" si="4" ref="P3:Q3">A1</f><v>35</v></c></row><row r="4"><c r="M4"><f t="shared" si="2"/><v>33</v></c></row></sheetData></worksheet>''',
        "xl/worksheets/sheet2.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>''',
    }
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items(): archive.writestr(name, content)
    workbook1904 = temp / "fixture-1904.xlsx"
    workbookPoi = temp / "poi-generated.xlsx"
    workbookMoved = temp / "relocated.xlsx"
    broken = temp / "broken.xlsx"
    broken.write_bytes(b"not a zip file")
    with zipfile.ZipFile(workbook1904, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            if name == "xl/workbook.xml": content = content.replace("<sheets>", '<workbookPr date1904="1"/><sheets>')
            archive.writestr(name, content)
    with zipfile.ZipFile(workbookMoved, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            if name == "[Content_Types].xml":
                content = content.replace("/xl/workbook.xml", "/custom/main.xml").replace("/xl/sharedStrings.xml", "/content/shared.xml")
            elif name == "_rels/.rels":
                content = content.replace('Target="xl/workbook.xml"', 'Target="custom/main.xml"')
            elif name == "xl/workbook.xml":
                name = "custom/main.xml"
            elif name == "xl/_rels/workbook.xml.rels":
                name = "custom/_rels/main.xml.rels"
                content = content.replace('Target="worksheets/sheet1.xml"', 'Target="../xl/worksheets/sheet1.xml"')
                content = content.replace('Target="sharedStrings.xml"', 'Target="../content/shared.xml"')
            elif name == "xl/sharedStrings.xml":
                name = "content/shared.xml"
            archive.writestr(name, content)
    # Compare the same workbook with the POI 3.16 jars used by original Z8.
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
    jars = sorted(p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar")
                  if not p.name.endswith("-sources.jar"))
    if not any("poi-3.16" in p.name for p in jars):
        raise SystemExit("Original Z8 POI dependencies are absent from the Gradle cache")
    java = temp / "PoiOracle.java"
    java.write_text("""import java.io.FileInputStream;
import java.util.TimeZone;
import java.util.Calendar;
import java.io.FileOutputStream;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
class PoiOracle {
  public static void main(String[] args) throws Exception {
    TimeZone.setDefault(TimeZone.getTimeZone("Europe/Moscow"));
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[0]))) {
      Sheet sheet = book.getSheetAt(0); Row first = sheet.getRow(0), third = sheet.getRow(2);
      if (book.getNumberOfSheets() != 2 || sheet.getPhysicalNumberOfRows() != 3 ||
          first.getPhysicalNumberOfCells() != 4 || first.getCell(1) != null ||
          !first.getCell(0).getStringCellValue().equals("Hi & 😀") ||
          first.getCell(2).getNumericCellValue() != 42.25 || !first.getCell(3).getBooleanCellValue() ||
          !first.getCell(4).getCellFormula().equals("C1*2") || first.getCell(4).getNumericCellValue() != 84.5 ||
          third.getPhysicalNumberOfCells() != 14 || !third.getCell(1).getStringCellValue().equals("Inline Unicode") ||
          third.getCell(5).getNumericCellValue() != 0 || book.getSheetAt(1).getPhysicalNumberOfRows() != 0)
        throw new AssertionError("Unexpected POI workbook values");
      if (sheet.getRow(-1) != null || sheet.getRow(1048576) != null || first.getCell(16384) != null)
        throw new AssertionError("Unexpected bounds behavior");
      try { first.getCell(-1); throw new AssertionError("Negative cell accepted"); }
      catch (IllegalArgumentException expected) {}
      if (!third.getCell(8).getCellFormula().equals("C3*2") || !third.getCell(9).getCellFormula().equals("D3*2") || third.getCell(9).getNumericCellValue() != 11)
        throw new AssertionError("Unexpected shared formula");
      if (!third.getCell(11).getCellFormula().equals("SUM(D3,$C3,D$3,$C$3)+IF(\\\"A1\\\"=\\\"A1\\\",0,0)+SUM(D$1:D$1048576,$D$1:$D$1048576,$A2:$XFD2,$A$3:$XFD$3)+D3+$C3+IFERROR(D3,#REF!)"))
        throw new AssertionError("Unexpected complex shared formula: " + third.getCell(11).getCellFormula());
      if (!sheet.getRow(3).getCell(12).getCellFormula().equals("SUM(C4,$C4,C$3,$C$3,$A3:$XFD3,$A$3:$XFD$3)"))
        throw new AssertionError("Unexpected vertically shifted formula");
      if (!third.getCell(15).getCellFormula().equals("XFD1")) throw new AssertionError("Unexpected formula boundary");
      if (!third.getCell(14).getCellFormula().equals("B1+1"))
        throw new AssertionError("Unexpected whitespace normalization");
      Calendar date = Calendar.getInstance(); date.setTime(third.getCell(2).getDateCellValue());
      if (date.get(Calendar.YEAR) != 2024 || date.get(Calendar.MONTH) != 1 || date.get(Calendar.DAY_OF_MONTH) != 29 || date.get(Calendar.HOUR_OF_DAY) != 12)
        throw new AssertionError("Unexpected POI date");
      for (int column = 6; column <= 7; ++column) {
        date.setTime(third.getCell(column).getDateCellValue());
        if (date.get(Calendar.YEAR) != 1900 || date.get(Calendar.MONTH) != 2 || date.get(Calendar.DAY_OF_MONTH) != 1)
          throw new AssertionError("Unexpected POI leap-year date");
      }
    }
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[1]))) {
      Calendar date = Calendar.getInstance(); date.setTime(book.getSheetAt(0).getRow(2).getCell(2).getDateCellValue());
      if (date.get(Calendar.YEAR) != 2028 || date.get(Calendar.MONTH) != 2 || date.get(Calendar.DAY_OF_MONTH) != 1 || date.get(Calendar.HOUR_OF_DAY) != 12)
        throw new AssertionError("Unexpected POI 1904 date");
    }
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[3]))) {
      if (book.getNumberOfSheets() != 2 || !book.getSheetAt(0).getRow(0).getCell(0).getStringCellValue().equals("Hi & 😀"))
        throw new AssertionError("Unexpected relocated workbook");
    }
    try (Workbook book = new XSSFWorkbook()) {
      Row row = book.createSheet("Generated").createRow(1);
      row.createCell(0).setCellValue("Generated & 😀");
      row.createCell(1).setCellValue(7);
      row.createCell(2).setCellFormula("B2*3");
      book.getCreationHelper().createFormulaEvaluator().evaluateFormulaCell(row.getCell(2));
      try (FileOutputStream output = new FileOutputStream(args[2])) { book.write(output); }
    }
  }
}""", encoding="utf-8")
    classpath = os.pathsep.join(map(str, jars))
    subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(java)], cwd=temp, check=True)
    subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "PoiOracle", str(workbook), str(workbook1904), str(workbookPoi), str(workbookMoved)], cwd=temp, check=True)
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''import z8.runtime;
import z8gen.Probe;
void main(string[] args) {
    assert(z8_optional_require(Z8p_50726F6265.m_verify(z8_file_from_path(args[1].to!wstring))) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_verify1904(z8_file_from_path(args[2].to!wstring))));
    assert(z8_optional_require(Z8p_50726F6265.m_verifyPoi(z8_file_from_path(args[3].to!wstring))));
    assert(z8_optional_require(Z8p_50726F6265.m_verify(z8_file_from_path(args[4].to!wstring))) == 0);
    assert(z8_optional_require(Z8p_50726F6265.m_failedOpen(z8_file_from_path(args[1].to!wstring), z8_file_from_path(args[5].to!wstring))));
}
'''.replace('import z8gen.Probe;', 'import z8gen.Probe;\nimport std.conv : to;'), encoding="utf-8")
    executable = temp / ("poi.exe" if os.name == "nt" else "poi")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable), str(workbook), str(workbook1904), str(workbookPoi), str(workbookMoved), str(broken)], cwd=temp, check=True)
print("XLSX workbook, sparse rows, shared strings and cells verified")
