"""Exercise native Application configuration through generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/application_config.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Application.bl").write_text('''
[native "org.zenframework.z8.server.base.application.Application"] public class Application {
    public static bool isMultitenant(); public static int maxUploadSize(); public static int maxDownloadSize();
    public static string[] supportedFileTypes();
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static bool defaults() {
        string[] types = Application.supportedFileTypes();
        return !Application.isMultitenant() && Application.maxUploadSize() == 5242880 &&
            Application.maxDownloadSize() == 1048576 && types.size() == 31 &&
            types[0] == "pdf" && types[1] == "txt" && types[types.size() - 1] == "vsd";
    }
    public static bool custom() {
        string[] types = Application.supportedFileTypes();
        if (!Application.isMultitenant() || Application.maxUploadSize() != -2147483648 ||
            Application.maxDownloadSize() != 3145728 || types.size() != 4 ||
            types[0] != "pdf" || types[1] != "csv" || types[2] != "png" || types[3] != "custom") return false;
        types.clear(); return Application.supportedFileTypes().size() == 4;
    }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "Application.bl").unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.application.Application;\n" + probe.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.Probe;
import core.thread : Thread;
void main() {
    alias P = Z8p_50726F6265;
    assert(z8_optional_require(P.m_defaults()));
    auto config = new Z8ApplicationConfig();
    config.multitenant = true; config.uploadMaxMiB = 2048; config.downloadMaxMiB = 3;
    config.textExtensions = ["csv"w]; config.imageExtensions = ["png"w];
    config.emailExtensions = []; config.officeExtensions = ["custom"w];
    z8_application_configure(config);
    config.textExtensions[0] = "changed"w;
    auto snapshot = z8_application_configuration(); snapshot.officeExtensions[0] = "changed"w;
    assert(z8_optional_require(P.m_custom()));
    auto thread = new Thread({ assert(z8_optional_require(P.m_custom())); });
    thread.start(); thread.join();
    z8_server_config_replace(["application.multitenancy"w:"TRUE"w, "web.server.upload.max"w:"2048"w,
        "web.client.download.max"w:"3"w, "web.client.hashPassword"w:"false"w,
        "file.converter.text"w:" csv "w, "file.converter.image"w:"png"w,
        "file.converter.email"w:","w, "file.converter.office"w:"custom,"w]);
    z8_application_configure_from_server();
    assert(z8_optional_require(P.m_custom()));
    assert(!z8_application_configuration().clientHashesPasswords);
    z8_server_config_replace(["web.server.upload.max"w:"invalid"w]);
    z8_application_configure_from_server();
    assert(z8_optional_require(P.m_defaults()));
}
''', encoding="utf-8")
    exe = temp / ("application-config.exe" if os.name == "nt" else "application-config")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Application configuration through generated BL verified")
