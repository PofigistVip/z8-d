"""Check BL ZIP calls against Python's independent ZIP implementation."""
from pathlib import Path
import os
import subprocess
import tempfile
import zipfile
from runtime_support import runtime_library, import_args

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as tmp, runtime_library() as runtime_lib:
    temp = Path(tmp)
    source = temp / "BinaryZip.bl"
    source.write_text('''import org.zenframework.z8.lang.encoding;
public class BinaryZip {
    public static int run(string inputPath, string archivePath, string outputPath, string foreignPath, string foreignOutput, string legacyPath, string legacyOutput) {
        binary value = '65, 66, 67';
        value.setName("nested/data.bin");
        binary[] values = {value};
        binary packed = binary.zip(values);
        if (value.length() != 0) return 1;
        file target = archivePath;
        target.write(packed);
        file input = inputPath;
        binary folder = binary.zip(input);
        file output = outputPath;
        folder.unzip(output);
        file foreign = foreignPath;
        file destination = foreignOutput;
        foreign.unzip(destination);
        file legacy = legacyPath;
        file legacyDestination = legacyOutput;
        legacy.unzip(legacyDestination, encoding.Cp866);
        return 0;
    }
}''', encoding="utf-8")
    generated = temp / "generated.d"
    result = subprocess.run([str(compiler), "compile", str(source)], capture_output=True, text=True, encoding="utf-8", check=True)
    generated.write_text(result.stdout + '''
import std.conv : to;
void main(string[] args) {
    assert(z8_optional_require(Z8_BinaryZip.m_run(args[1].to!wstring, args[2].to!wstring,
        args[3].to!wstring, args[4].to!wstring, args[5].to!wstring, args[8].to!wstring, args[9].to!wstring)) == 0);
    bool rejected;
    try { z8_file_unzip(z8_file_from_path(args[6].to!wstring), z8_file_from_path(args[7].to!wstring)); }
    catch (Exception) { rejected = true; }
    assert(rejected);
}
''', encoding="utf-8")
    executable = temp / ("check.exe" if os.name == "nt" else "check")
    subprocess.run(["dmd", str(generated), *import_args(), str(runtime_lib), "-of=" + str(executable)], cwd=temp, check=True)
    source_dir = temp / "input"
    source_dir.mkdir()
    (source_dir / "данные.txt").write_text("Привет", encoding="utf-8")
    foreign = temp / "foreign.zip"
    with zipfile.ZipFile(foreign, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nested/foreign.txt", "foreign content")
    legacy = temp / "legacy.zip"
    with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("aaaa.txt", "legacy content")
    legacy.write_bytes(legacy.read_bytes().replace(b"aaaa.txt", "тест.txt".encode("cp866")))
    invalid = temp / "invalid.zip"
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("../escaped.txt", "unsafe")
    output, archive_path, foreign_output = temp / "output", temp / "binary.zip", temp / "foreign-output"
    legacy_output = temp / "legacy-output"
    subprocess.run([str(executable), str(source_dir), str(archive_path), str(output), str(foreign),
                    str(foreign_output), str(invalid), str(temp / "unsafe-output"), str(legacy), str(legacy_output)], cwd=temp, check=True)
    assert (output / "данные.txt").read_text(encoding="utf-8") == "Привет"
    assert (foreign_output / "nested" / "foreign.txt").read_text(encoding="utf-8") == "foreign content"
    assert (legacy_output / "тест.txt").read_text(encoding="utf-8") == "legacy content"
    assert not (temp / "escaped.txt").exists()
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["nested/data.bin"]
        assert archive.read("nested/data.bin") == b"ABC"
print("ZIP operations interoperate with Python and reject traversal")
