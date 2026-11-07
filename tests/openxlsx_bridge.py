"""Exercise the D/OpenXLSX bridge against an XLSX generated without extra packages."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("library_dir", type=Path, help="directory containing z8_openxlsx and its import library")
args = parser.parse_args()
library_dir = args.library_dir.resolve()

entries = {
    "[Content_Types].xml": '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''',
    "_rels/.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
    "xl/workbook.xml": '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Данные 😀" sheetId="1" r:id="rId1"/><sheet name="Second" sheetId="2" r:id="rId2"/><sheet name="Empty" sheetId="3" r:id="rId3"/></sheets></workbook>''',
    "xl/_rels/workbook.xml.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/></Relationships>''',
    "xl/worksheets/sheet1.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Привет 😀 &amp; text</t></is></c><c r="B1"><v>42</v></c><c r="D1"/><c r="E1" t="b"><v>1</v></c><c r="F1"><v>42.25</v></c><c r="G1"><f>B1*2</f><v>84</v></c><c r="H1"><f t="shared" si="0" ref="H1:H2">B1+1</f><v>43</v></c><c r="I1"><f t="array" ref="I1">B1+2</f><v>44</v></c><c r="J1" t="inlineStr"><is><r><t>First </t></r><r><t>_x0041_</t></r></is></c></row><row r="2"><c r="H2"><f t="shared" si="0"/><v>45</v></c></row></sheetData></worksheet>''',
    "xl/worksheets/sheet2.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="C2" t="inlineStr"><is><t>other</t></is></c></row><row r="4"/></sheetData></worksheet>''',
    "xl/worksheets/sheet3.xml": '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>''',
}

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    workbook = temp / "Книга.xlsx"
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries.items():
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
    subprocess.run([str(executable), str(workbook)], check=True, env=environment)
print("OpenXLSX bridge: OK")
