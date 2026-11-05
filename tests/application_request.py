"""Exercise request-local native Application bindings and response sharing."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python tests/application_request.py [original-z8-root]")
    (source / "Application.bl").write_text('''
[native "org.zenframework.z8.server.base.application.Application"] public class Application {
    public static bool isRequest(); public static int currentTimeMillis();
    public static string[string] requestParameters(); public static file[] requestFiles();
    public static JsonWriter responseWriter();
}
''', encoding="utf-8")
    (source / "JsonWriter.bl").write_text('''
[native "org.zenframework.z8.server.base.json.JsonWriter"] public class JsonWriter {
    public JsonWriter startObject(); public JsonWriter finishObject();
    public JsonWriter writeProperty(string name, primary value); public string toString();
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static bool noRequest() {
        if (Application.isRequest()) return false;
        try { Application.requestParameters(); return false; } catch (exception expected) {}
        try { Application.requestFiles(); return false; } catch (exception expected) {}
        try { Application.responseWriter(); return false; } catch (exception expected) {}
        return true;
    }
    public static string run() {
        if (!Application.isRequest()) return "missing request";
        string[string] parameters = Application.requestParameters();
        if (parameters["incoming"] != "yes") return "missing parameter";
        parameters.add("written", "ok");
        file[] files = Application.requestFiles();
        if (files.size() != 1) return "missing file";
        files.clear();
        JsonWriter first = Application.responseWriter();
        JsonWriter second = Application.responseWriter();
        first.startObject().writeProperty("from", parameters["incoming"]);
        second.writeProperty("count", 3).finishObject();
        return first.toString();
    }
    public static int now() { return Application.currentTimeMillis(); }
}
''', encoding="utf-8")
    if len(sys.argv) == 2:
        original = Path(sys.argv[1]).resolve()
        language = original / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir():
            raise SystemExit("Original BL standard library not found")
        (source / "Application.bl").unlink()
        (source / "JsonWriter.bl").unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.application.Application;\n"
                         "import org.zenframework.z8.base.json.JsonWriter;\n" + probe.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_Probe;
import core.thread : Thread;
void main() {
    alias P = Z8p_50726F6265;
    assert(z8_optional_require(P.m_noRequest()));
    auto request = new Z8ApplicationRequest();
    request.parameters.z8_add("incoming"w, "yes"w);
    request.files.z8_add(z8_file_from_path("one.txt"w));
    assert(z8_application_set_request(request) is null);
    assert(P.m_run() == `{"from":"yes","count":3}`w);
    assert(z8_application_response_text(request) == `{"from":"yes","count":3}`w);
    assert(request.parameters.z8_get("written"w) == "ok"w);
    assert(request.files.z8_size() == 1);
    assert(z8_optional_require(P.m_now()) > 1_600_000_000_000L);
    auto nested = new Z8ApplicationRequest();
    assert(z8_application_set_request(nested) is request);
    assert(z8_application_set_request(request) is nested);
    auto thread = new Thread({
        assert(z8_application_request() is null);
        auto local = new Z8ApplicationRequest();
        z8_application_set_request(local);
        assert(z8_application_request() is local);
    });
    thread.start(); thread.join();
    assert(z8_application_request() is request);
    assert(z8_application_set_request(null) is request);
    assert(z8_optional_require(P.m_noRequest()));
}
''', encoding="utf-8")
    executable = temp / ("application-request.exe" if os.name == "nt" else "application-request")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(executable)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("Thread-local Application request context and shared response writer verified")
