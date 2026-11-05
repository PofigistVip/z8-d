"""Build CivetWeb and exercise BL Application requests over loopback HTTP."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import http.client
import json
import os
import shutil
import subprocess
import tempfile
from runtime_support import import_args, runtime_library
import sys

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "Application.bl").write_text('''
[native "org.zenframework.z8.server.base.application.Application"] public class Application {
    public static string[string] requestParameters(); public static JsonWriter responseWriter();
    public static void redirect(string url);
}
''', encoding="utf-8")
    (source / "JsonWriter.bl").write_text('''
[native "org.zenframework.z8.server.base.json.JsonWriter"] public class JsonWriter {
    public JsonWriter startObject(); public JsonWriter finishObject();
    public JsonWriter writeProperty(string name, primary value);
}
''', encoding="utf-8")
    (source / "Probe.bl").write_text('''
public class Probe {
    public static void run() {
        string[string] p = Application.requestParameters();
        if (p.containsKey("mode") && p["mode"] == "fail") throw "failed";
        if (p.containsKey("mode") && p["mode"] == "redirect") Application.redirect("/next");
        Application.responseWriter().startObject().writeProperty("name", p["name"])
            .writeProperty("value", p["value"]).writeProperty("ip", p["ip"]).finishObject();
    }
}
''', encoding="utf-8")
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python tests/civetweb_server.py [original-z8-root]")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "Application.bl").unlink()
        (source / "JsonWriter.bl").unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.application.Application;\n" +
                         probe.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    sys.path.insert(0, str(root / "webserver"))
    from build_civetweb import build
    obj = temp / ("civetweb.obj" if os.name == "nt" else "civetweb.o")
    build(obj)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8.webserver.civetweb;
import z8gen.p_Probe;
import std.stdio : writeln, stdout, readln;
void runRequest(Z8HttpRequest request) { Z8p_50726F6265.m_run(); }
void main() {
    auto server = new Z8CivetServer("127.0.0.1:0", &runRequest, 128);
    scope(exit) server.stop();
    writeln(server.port()); stdout.flush();
    readln();
    server.stop(); server.stop();
    bool stopped; try { server.port(); } catch (Exception) { stopped = true; }
    assert(stopped);
}
''', encoding="utf-8")
    # A delegate carries the handler context and remains valid for the server lifetime.
    text = harness.read_text(encoding="utf-8").replace("&runRequest, 128", "(Z8HttpRequest request) { runRequest(request); }, 128")
    harness.write_text(text, encoding="utf-8")
    executable = temp / ("civetweb-server.exe" if os.name == "nt" else "civetweb-server")
    args = ["dmd", "-I" + str(generated), "-I" + str(root / "webserver/source"), *import_args(),
            *map(str, generated.rglob("*.d")), str(root / "webserver/source/z8/webserver/civetweb.d"),
            str(harness), str(obj), str(runtime), "-of=" + str(executable)]
    if os.name != "nt": args += ["-L-lpthread", "-L-ldl"]
    response_file = temp / "dmd.rsp"
    response_file.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response_file)], cwd=temp, check=True)
    process = subprocess.Popen([str(executable)], cwd=temp, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        line = process.stdout.readline().strip()
        if not line.isdigit(): raise RuntimeError("Server did not start: " + line + process.stderr.read())
        port = int(line)
        def request(path, body=None, headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                conn.request("POST" if body is not None else "GET", path, body=body, headers=headers or {})
                response = conn.getresponse()
                data = response.read()
                assert response.getheader("Content-Type") == "application/json; charset=UTF-8"
                assert int(response.getheader("Content-Length")) == len(data)
                return response.status, data.decode("utf-8")
            finally: conn.close()
        status, body = request("/api?name=%D0%BC%D0%B8%D1%80&value=query", "value=body", {"Content-Type":"application/x-www-form-urlencoded"})
        assert status == 200 and json.loads(body) == {"name":"мир", "value":"query", "ip":"127.0.0.1"}, (status, body)
        def one(i):
            status, body = request("/api?name=user" + str(i) + "&value=" + str(i))
            return status, json.loads(body)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for i, (status, data) in enumerate(pool.map(one, range(16))):
                assert status == 200 and data["name"] == "user" + str(i) and data["value"] == str(i), (status, data)
        status, body = request("/api?name=&value=")
        assert status == 200 and json.loads(body)["name"] == "" and json.loads(body)["value"] == "", (status, body)
        status, body = request("/api", "name=hello+world&value=%D1%82%D0%B5%D1%81%D1%82", {"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"})
        assert status == 200 and json.loads(body)["name"] == "hello world" and json.loads(body)["value"] == "тест", (status, body)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request("POST", "/api", body=iter([b"name=chunk", b"&value=ok"]),
                               headers={"Content-Type": "application/x-www-form-urlencoded", "Transfer-Encoding": "chunked"},
                               encode_chunked=True)
            response = connection.getresponse()
            chunked_status, chunked_body = response.status, response.read().decode("utf-8")
            assert chunked_status == 200 and json.loads(chunked_body)["name"] == "chunk", (chunked_status, chunked_body)
        finally: connection.close()
        status, body = request("/api?name=%FF&value=1")
        assert status == 400, (status, body)
        status, body = request("/api?mode=redirect")
        assert status == 302 and json.loads(body)["redirect"] == "/next", (status, body)
        status, body = request("/api?mode=fail")
        assert status == 500 and json.loads(body)["error"] == "internal server error"
        status, body = request("/api?name=after&value=error")
        assert status == 200 and json.loads(body)["name"] == "after", (status, body)
        status, body = request("/api?name=x", "x" * 129)
        assert status == 413
        status, body = request("/api", "--boundary", {"Content-Type":"multipart/form-data; boundary=boundary"})
        assert status == 415
    finally:
        if process.poll() is None:
            process.stdin.write("\n"); process.stdin.flush()
        process.wait(timeout=15)
        stderr = process.stderr.read()
        if process.returncode: raise RuntimeError("Server exited with code " + str(process.returncode) + ": " + stderr)
print("CivetWeb loopback requests, request isolation and limits verified")
