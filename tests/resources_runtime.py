"""Exercise Resources.loadResource with a host-configured application root."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/resources_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "ResourceProbe.bl").write_text('''
import org.zenframework.z8.base.application.Resources;
import org.zenframework.z8.base.file.FileConverter;
public class ResourceProbe {
    public static file load(string path) { return Resources.loadResource(path); }
    public static string extension(string path) { return FileConverter.getExtension(path); }
    public static string fileExtension(file value) { return FileConverter.getExtension(value); }
    public static bool pdf(string value) { return FileConverter.isPdfExtension(value); }
    public static bool text(string value) { return FileConverter.isTextExtension(value); }
    public static bool image(string value) { return FileConverter.isImageExtension(value); }
    public static bool email(string value) { return FileConverter.isEmailExtension(value); }
    public static bool office(string value) { return FileConverter.isOfficeExtension(value); }
    public static bool convertible(string value) { return FileConverter.isConvertableToPdf(value); }
    public static file convert(file source, file target) { return FileConverter.convert(source, target); }
    public static file convertOptions(file source, file target, string[string] options) { return FileConverter.convert(source, target, options); }
    public static file convertBinary(binary source, string type, file target) { return FileConverter.convert(source, type, target); }
    public static file convertBinaryOptions(binary source, file target, string[string] options) { return FileConverter.convert(source, target, options); }
    public static file convertBinaryTypeOptions(binary source, string type, file target, string[string] options) { return FileConverter.convert(source, type, target, options); }
}
''', encoding="utf-8")
    application, working = temp / "application", temp / "working"
    (application / "data").mkdir(parents=True)
    working.mkdir()
    (application / "data" / "resource.txt").write_bytes(b"hello resource")
    (application / "data" / "sample.pdf").write_bytes(b"%PDF-test")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.ResourceProbe;
import std.conv : to;
import std.path : buildPath;
void main(string[] args) {
    alias P = Z8p_5265736F7572636550726F6265;
    z8_file_set_roots(args[2]);
    z8_resources_set_application_root(args[1]);
    auto file = P.m_load("data/resource.txt"w);
    assert(z8_file_exists(file) && file.name == "resource.txt"w);
    assert(z8_optional_require(file.size) == 14 && z8_file_read(file) == "hello resource"w);
    assert(file.time !is null && z8_date_ticks(file.time) == z8_date_ticks(z8_file_lastModified(file)));
    auto leading = P.m_load("/data/resource.txt"w);
    assert(z8_file_exists(leading) && z8_file_read(leading) == "hello resource"w);
    auto missing = P.m_load("data/missing.txt"w);
    assert(!z8_file_exists(missing) && z8_optional_require(missing.size) == 0);
    assert(z8_date_ticks(missing.time) == 0);
    assert(P.m_extension("A.B/тест.TxT"w) == "txt"w && P.m_fileExtension(file) == "txt"w);
    assert(P.m_extension("file"w) == ""w);
    assert(z8_optional_require(P.m_pdf("pdf"w)) && !z8_optional_require(P.m_pdf("PDF"w)));
    assert(z8_optional_require(P.m_text("XML"w)) && z8_optional_require(P.m_image("JpG"w)));
    assert(z8_optional_require(P.m_email("EML"w)) && z8_optional_require(P.m_office("DOCX"w)));
    assert(z8_optional_require(P.m_convertible("docx"w)) && !z8_optional_require(P.m_convertible("zip"w)));
    z8_server_config_replace(["file.converter.text"w:" md, csv "w]);
    z8_application_configure_from_server();
    assert(z8_optional_require(P.m_text("MD"w)) && z8_optional_require(P.m_convertible("csv"w)));
    assert(!z8_optional_require(P.m_text("txt"w)));
    auto source = z8_file_from_path(buildPath(args[1], "data", "sample.pdf").to!wstring);
    auto target = z8_file_from_path(buildPath(args[2], "out", "copy.pdf").to!wstring);
    auto converted = P.m_convert(source, target);
    assert(z8_file_read(converted) == "%PDF-test"w && z8_optional_require(converted.size) == 9);
    z8_file_write(target, "existing"w);
    assert(z8_file_read(P.m_convert(source, target)) == "existing"w);
    auto options = new Z8StringMap(); options.z8_add("reset"w, "true"w);
    assert(z8_file_read(P.m_convertOptions(source, target, options)) == "%PDF-test"w);
    auto binaryTarget = z8_file_from_path(buildPath(args[2], "out", "binary.pdf").to!wstring);
    assert(z8_file_read(P.m_convertBinary(z8_binary_from_string("%PDF-binary"w), "pdf"w, binaryTarget)) == "%PDF-binary"w);
    auto binaryOptions = new Z8StringMap(); binaryOptions.z8_add("reset"w, "true"w);
    assert(z8_file_read(P.m_convertBinaryOptions(z8_binary_from_string("%PDF-new"w), binaryTarget, binaryOptions)) == "%PDF-binary"w);
    assert(z8_file_read(P.m_convertBinaryTypeOptions(z8_binary_from_string("%PDF-new"w), "pdf"w, binaryTarget, binaryOptions)) == "%PDF-new"w);
    bool unsupported; try { P.m_convertOptions(z8_file_from_path(buildPath(args[1], "data", "resource.txt").to!wstring), target, options); }
    catch (Exception) { unsupported = true; }
    assert(unsupported && z8_file_read(target) == "%PDF-test"w);
    bool same; try { P.m_convertOptions(source, source, options); } catch (Exception) { same = true; }
    assert(same && z8_file_read(source) == "%PDF-test"w);
}
''', encoding="utf-8")
    executable = temp / ("resources.exe" if os.name == "nt" else "resources")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(application), str(working)], cwd=temp, check=True)
print("Application resource loading and file metadata passed")
