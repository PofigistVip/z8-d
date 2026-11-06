"""Exercise headless LibreOffice conversion via the BL FileConverter API.

Usage: python tests/file_converter_office.py <original-z8-root> <libreoffice-home>
"""
from pathlib import Path
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from runtime_support import import_args, runtime_library

if len(sys.argv) != 3:
    raise SystemExit("Usage: python tests/file_converter_office.py <original-z8-root> <libreoffice-home>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
office = Path(sys.argv[2]).resolve()
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if not language.is_dir() or not (office / "program" / ("soffice.com" if os.name == "nt" else "soffice")).is_file():
    raise SystemExit("Original BL library or LibreOffice executable not found")

with tempfile.TemporaryDirectory(prefix="z8 office ") as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "OfficeProbe.bl").write_text('''
import org.zenframework.z8.base.file.FileConverter;
public class OfficeProbe {
    public static file convert(file source, file target) { return FileConverter.convert(source, target); }
    public static file convertWithOptions(file source, file target, string[string] options) { return FileConverter.convert(source, target, options); }
    public static file convertBinary(binary source, string extension, file target) { return FileConverter.convert(source, extension, target); }
    public static file convertUnknown(binary source, file target) { return FileConverter.convert(source, target); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    (temp / "source.txt").write_text("Hello from Z8. Привет!", encoding="utf-8")
    def png_chunk(kind, contents):
        return struct.pack("!I", len(contents)) + kind + contents + struct.pack("!I", zlib.crc32(kind + contents) & 0xffffffff)
    pixels = b"\0" + b"\xff\0\0" * 2 + b"\0" + b"\0\xff\0" * 2
    png = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack("!IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
           png_chunk(b"IDAT", zlib.compress(pixels)) + png_chunk(b"IEND", b""))
    (temp / "image.png").write_bytes(png)
    # Keep the header readable but corrupt the compressed pixels; LibreOffice
    # may otherwise report success and emit a blank PDF.
    (temp / "invalid.png").write_bytes(png[:-16] + b"\0" * 16)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.OfficeProbe;
import std.conv : to;
import std.path : buildPath;
void main(string[] args) {
    alias P = Z8p_4F666669636550726F6265;
    z8_server_config_replace(["office.home"w: args[2].to!wstring]);
    auto input = z8_file_from_path(buildPath(args[1], "source.txt").to!wstring);
    auto document = z8_file_from_path(buildPath(args[1], "result", "документ.docx").to!wstring);
    auto output = P.m_convert(input, document);
    assert(z8_file_exists(output) && z8_optional_require(output.size) > 100);
    auto pdf = z8_file_from_path(buildPath(args[1], "result", "report.pdf").to!wstring);
    assert(z8_file_exists(P.m_convert(document, pdf)));
    auto archive = z8_file_from_path(buildPath(args[1], "result", "archive.pdf").to!wstring);
    auto pdfOptions = new Z8StringMap(); pdfOptions.z8_add("format"w, "PDF/A-1b"w);
    assert(z8_file_exists(P.m_convertWithOptions(document, archive, pdfOptions)));
    auto binaryOutput = z8_file_from_path(buildPath(args[1], "result", "binary.odt").to!wstring);
    auto rtf = z8_binary_from_string(`{\\rtf1\\ansi Z8 binary}`w);
    assert(z8_file_exists(P.m_convertBinary(rtf, "rtf"w, binaryOutput)));
    auto inferred = z8_file_from_path(buildPath(args[1], "result", "inferred.odt").to!wstring);
    assert(z8_file_exists(P.m_convertUnknown(z8_file_to_binary(document), inferred)));
    auto image = z8_file_from_path(buildPath(args[1], "image.png").to!wstring);
    auto imagePdf = z8_file_from_path(buildPath(args[1], "result", "image.pdf").to!wstring);
    assert(z8_file_exists(P.m_convert(image, imagePdf)));
    auto invalidImage = z8_file_from_path(buildPath(args[1], "invalid.png").to!wstring);
    auto invalidPdf = z8_file_from_path(buildPath(args[1], "result", "invalid.pdf").to!wstring);
    bool invalidFailed;
    try { P.m_convert(invalidImage, invalidPdf); } catch (Exception) { invalidFailed = true; }
    assert(invalidFailed && !z8_file_exists(invalidPdf));
    auto unsupported = z8_file_from_path(buildPath(args[1], "result", "unsupported.pdf").to!wstring);
    auto unsupportedOptions = new Z8StringMap(); unsupportedOptions.z8_add("format"w, "PDF/X-3:2002"w);
    bool unsupportedFailed;
    try { P.m_convertWithOptions(document, unsupported, unsupportedOptions); } catch (Exception) { unsupportedFailed = true; }
    assert(unsupportedFailed && !z8_file_exists(unsupported));
    // A failed reset must not replace an already generated document.
    z8_server_config_replace(["office.home"w: buildPath(args[1], "missing").to!wstring]);
    auto options = new Z8StringMap(); options.z8_add("reset"w, "true"w);
    bool failed;
    try { P.m_convertWithOptions(input, document, options); } catch (Exception) { failed = true; }
    assert(failed && z8_file_exists(document));
}
''', encoding="utf-8")
    executable = temp / ("office.exe" if os.name == "nt" else "office")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(temp), str(office)], cwd=temp, check=True, timeout=90)
    with zipfile.ZipFile(temp / "result" / "документ.docx") as document:
        assert b"Hello from Z8" in document.read("word/document.xml")
    assert (temp / "result" / "report.pdf").read_bytes().startswith(b"%PDF-")
    archive = (temp / "result" / "archive.pdf").read_bytes()
    assert archive.startswith(b"%PDF-") and b"pdfaid:part" in archive
    with zipfile.ZipFile(temp / "result" / "binary.odt") as document:
        assert b"Z8 binary" in document.read("content.xml")
    with zipfile.ZipFile(temp / "result" / "inferred.odt") as document:
        assert b"Hello from Z8" in document.read("content.xml")
    image_pdf = (temp / "result" / "image.pdf").read_bytes()
    assert image_pdf.startswith(b"%PDF-") and b"/Subtype/Image" in image_pdf
print("FileConverter office and PDF conversion passed")
