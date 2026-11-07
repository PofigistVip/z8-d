"""Exercise the D/OpenXLSX bridge against an XLSX generated without extra packages."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("library_dir", type=Path, help="directory containing z8_openxlsx and its import library")
args = parser.parse_args()
library_dir = args.library_dir.resolve()

entries = {
    "[Content_Types].xml": '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="txt" ContentType="text/plain"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''',
    "_rels/.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
    "xl/workbook.xml": '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Данные 😀" sheetId="1" r:id="rId1"/><sheet name="Second" sheetId="2" r:id="rId2"/><sheet name="Empty" sheetId="3" r:id="rId3"/></sheets></workbook>''',
    "xl/_rels/workbook.xml.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/></Relationships>''',
    "xl/worksheets/sheet1.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Привет 😀 &amp; text</t></is></c><c r="B1" s="0"><v>42</v></c><c r="D1"/><c r="E1" t="b"><v>1</v></c><c r="F1"><v>42.25</v></c><c r="G1"><f>B1*2</f><v>84</v></c><c r="H1"><f t="shared" si="0" ref="H1:H2">B1+1</f><v>43</v></c><c r="I1"><f t="array" ref="I1">B1+2</f><v>44</v></c><c r="J1" t="inlineStr"><is><r><t>First </t></r><r><t>_x0041_</t></r></is></c><c r="K1"><f>1+1</f><v>2</v></c></row><row r="2"><c r="H2"><f t="shared" si="0"/><v>45</v></c></row></sheetData></worksheet>''',
    "xl/worksheets/sheet2.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="C2" t="inlineStr"><is><t>other</t></is></c></row><row r="4"/></sheetData></worksheet>''',
    "xl/worksheets/sheet3.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>''',
    "custom/preserved.txt": "An unrelated package entry",
}

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    workbook = temp / "Книга.xlsx"
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents.encode("utf-8"))
    styled = temp / "styled.xlsx"
    with zipfile.ZipFile(styled, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries.items():
            if name == "xl/worksheets/sheet1.xml":
                contents = contents.replace("<sheetData>", '<cols><col min="1" max="4" width="12" customWidth="1" outlineLevel="2" collapsed="0"/></cols><sheetData>')
            archive.writestr(name, contents.encode("utf-8"))
    executable = temp / ("probe.exe" if os.name == "nt" else "probe")
    command = ["dmd", "-I" + str(ROOT / "xlsx/source"), str(ROOT / "tests/openxlsx_bridge.d"),
               str(ROOT / "xlsx/source/z8/xlsx/openxlsx.d"), "-of=" + str(executable)]
    if os.name == "nt":
        command.append(str(library_dir / "z8_openxlsx.lib"))
        shutil.copy2(library_dir / "z8_openxlsx.dll", temp)
    else:
        command.extend(["-L-L" + str(library_dir), "-L-lz8_openxlsx"])
    subprocess.run(command, check=True)
    environment = os.environ.copy()
    if os.name != "nt":
        environment["LD_LIBRARY_PATH"] = str(library_dir) + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
    saved = temp / "saved.xlsx"
    saved_again = temp / "saved-again.xlsx"
    styled_saved = temp / "styled-saved.xlsx"
    removed_saved = temp / "removed.xlsx"
    cloned_saved = temp / "cloned.xlsx"
    subprocess.run([str(executable), str(workbook), str(saved), str(saved_again), str(styled), str(styled_saved), str(removed_saved), str(cloned_saved)], check=True, env=environment)
    with zipfile.ZipFile(saved) as archive:
        assert archive.testzip() is None
        assert archive.read("custom/preserved.txt") == b"An unrelated package entry"
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        columns = [item.attrib for item in sheet.findall("x:cols/x:col", namespace)]
        assert columns == [{"min": "2", "max": "2", "hidden": "1"},
                           {"min": "4", "max": "4", "hidden": "1"}], columns
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
    jars = sorted(p for p in cache.glob("org.zenframework.z8.dependencies.*/*/3.4-cert/**/*.jar")
                  if not p.name.endswith("-sources.jar"))
    if any("poi-3.16" in p.name for p in jars) and shutil.which("javac") and shutil.which("java"):
        oracle = temp / "SavedWorkbookOracle.java"
        oracle.write_text('''import java.io.FileInputStream;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
class SavedWorkbookOracle {
  public static void main(String[] args) throws Exception {
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[0]))) {
      Row row = book.getSheetAt(0).getRow(0);
      if (book.getNumberOfSheets() != 3 || !book.getSheetName(1).equals("Второй лист") ||
          !book.getSheetAt(0).isColumnHidden(1) || !book.getSheetAt(0).isColumnHidden(3) ||
          book.getSheetAt(0).isColumnHidden(0) || book.getSheetAt(0).getPhysicalNumberOfRows() != 2 ||
          row.getPhysicalNumberOfCells() != 10 || !row.getCell(0).getStringCellValue().equals("Привет 😀 & text") ||
          !row.getCell(10).getStringCellValue().equals("replaced") ||
          !row.getCell(6).getCellFormula().equals("B1*2") || row.getCell(6).getNumericCellValue() != 84)
        throw new AssertionError("OpenXLSX output differs from the original POI API");
      Row written = book.getSheetAt(2).getRow(2);
      if (!written.getCell(0).getStringCellValue().equals("Русский 😀 _x0041_ _x005F_x0041_ \\u0001\\u0000\\r\\n & < >") ||
          written.getCell(1).getNumericCellValue() != 42.25 || !written.getCell(2).getBooleanCellValue() ||
          !written.getCell(3).getStringCellValue().equals("") ||
          !written.getCell(4).getStringCellValue().equals("_x00G0_ _X0041_") ||
          !written.getCell(5).getStringCellValue().equals("\\uFFFE\\uFFFF") ||
          !written.getCell(6).getStringCellValue().equals("A _x0041_"))
        throw new AssertionError("OpenXLSX written values differ from the original POI API");
    }
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[1]))) {
      if (!book.getSheetAt(0).isColumnHidden(1) || book.getSheetAt(0).isColumnHidden(3))
        throw new AssertionError("Repeated save did not retain column changes");
    }
    try (Workbook before = new XSSFWorkbook(new FileInputStream(args[2]));
         Workbook after = new XSSFWorkbook(new FileInputStream(args[0]))) {
      for (int col : new int[]{0, 1, 2, 3})
        if (before.getSheetAt(0).getColumnWidth(col) != after.getSheetAt(0).getColumnWidth(col))
          throw new AssertionError("Column width changed at " + col + ": " + before.getSheetAt(0).getColumnWidth(col) + " != " + after.getSheetAt(0).getColumnWidth(col));
    }
    try (Workbook before = new XSSFWorkbook(new FileInputStream(args[3]));
         Workbook after = new XSSFWorkbook(new FileInputStream(args[4]))) {
      Sheet expected = before.getSheetAt(0), actual = after.getSheetAt(0);
      expected.setColumnHidden(1, true); expected.setColumnHidden(3, true);
      for (int col = 0; col < 6; ++col)
        if (expected.getColumnWidth(col) != actual.getColumnWidth(col) || expected.isColumnHidden(col) != actual.isColumnHidden(col))
          throw new AssertionError("Styled column differs at " + col);
    }
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[5]))) {
      Row row = book.getSheetAt(0).getRow(3);
      if (row == null || row.getPhysicalNumberOfCells() != 1 || row.getCell(1) != null ||
          row.getCell(3) != null || row.getCell(9) != null || !row.getCell(6).getCellFormula().equals("B1*2"))
        throw new AssertionError("Removed cells or retained row differ from POI");
      if (book.getSheetAt(0).getRow(9) != null) throw new AssertionError("Missing row was created");
    }
    try (Workbook book = new XSSFWorkbook(new FileInputStream(args[6]))) {
      if (book.getNumberOfSheets() != 4 || !book.getSheetName(3).equals("Копия") ||
          book.getSheetAt(0).getRow(5).getCell(0).getNumericCellValue() != 7 ||
          book.getSheetAt(3).getRow(5).getCell(0).getNumericCellValue() != 9 ||
          !book.getSheetAt(3).getRow(0).getCell(6).getCellFormula().equals("B1*2") ||
          book.getSheetAt(3).getRow(0).getCell(6).getNumericCellValue() != 84)
        throw new AssertionError("Cloned sheet differs from the original");
    }
  }
}''', encoding="utf-8")
        classpath = os.pathsep.join(map(str, jars))
        subprocess.run(["javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-cp", classpath, str(oracle)], cwd=temp, check=True)
        subprocess.run(["java", "-cp", str(temp) + os.pathsep + classpath, "SavedWorkbookOracle", str(saved), str(saved_again), str(workbook), str(styled), str(styled_saved), str(removed_saved), str(cloned_saved)], cwd=temp, check=True)
    else:
        print("POI output verification skipped: original POI jars or Java unavailable")
print("OpenXLSX bridge: OK")
