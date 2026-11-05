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
    public static string[string] requestParameters(); public static file[] requestFiles(); public static JsonWriter responseWriter();
    public static User user(); public static guid userId();
    public static void redirect(string url);
    public static void info(string text); public static void warning(string text); public static void error(string text);
    public static void logInfo(string text); public static void logWarning(string text); public static void logError(string text);
    public static void print(file value);
}
''', encoding="utf-8")
    (source / "User.bl").write_text('''
[native "org.zenframework.z8.server.base.security.User"] public class User { public string login; }
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
        if (p.containsKey("mode") && p["mode"] == "protocol") {
            Application.info("notice");
            Application.responseWriter().writeProperty("answer", 42);
            return;
        }
        if (p.containsKey("mode") && p["mode"] == "auth") {
            Application.responseWriter().writeProperty("login", Application.user().login)
                .writeProperty("userId", Application.userId());
            return;
        }
        if (p.containsKey("mode") && p["mode"] == "unbalanced") {
            Application.responseWriter().startObject();
            return;
        }
        if (p.containsKey("mode") && p["mode"] == "monitor") {
            Application.info("info"); Application.warning("warn"); Application.error("error");
            Application.logInfo("log info"); Application.logWarning("log warn"); Application.logError("log error");
            file output; Application.print(output);
        }
        JsonWriter writer = Application.responseWriter().startObject().writeProperty("name", p["name"])
            .writeProperty("value", p["value"]).writeProperty("ip", p["ip"]);
        file[] files = Application.requestFiles();
        if (files.size() > 0) {
            file uploaded = files.first();
            writer.writeProperty("filename", uploaded.name).writeProperty("content", uploaded.read())
                .writeProperty("path", uploaded.path).writeProperty("size", uploaded.size)
                .writeProperty("count", files.size());
        }
        writer.finishObject();
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
        (source / "User.bl").unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        probe = source / "Probe.bl"
        probe.write_text("import org.zenframework.z8.base.application.Application;\nimport org.zenframework.z8.base.json.JsonWriter;\n" +
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
import core.memory : GC;
import std.string : indexOf;
class Authority : IZ8HttpAuthority {
    Z8SessionManager sessions;
    this() {
        sessions = new Z8SessionManager();
        makeSession("valid"w, "session-user"w);
    }
    Z8ApplicationSession makeSession(wstring token, wstring login) {
        auto user = new Z8UserData(); user.id = z8_guid_create(42); user.login = login;
        auto system = new Z8UserData(); system.id = z8_guid_create(1);
        return sessions.create(token, user, system, "default"w);
    }
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring id, wstring serverId) {
        if (request.remoteAddress != "127.0.0.1") return null;
        return serverId == "shard"w ? sessions.getSession(id) : null;
    }
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password) {
        return login == "alice"w && password == "secret"w ? makeSession("new"w, login) : null;
    }
}
void runRequest(Z8HttpRequest request) {
    if (request.query.indexOf("collect=1") >= 0) GC.collect();
    Z8p_50726F6265.m_run();
    if (request.query.indexOf("mode=monitor") >= 0) {
        auto m = request.monitor;
        assert(m.messages().length == 3 && m.logs().length == 3 && m.files().length == 1);
        assert(m.messages()[0].text == "info"w && m.messages()[1].level == Z8MonitorLevel.warning);
        assert(m.logs()[2].level == Z8MonitorLevel.error && m.hasErrors());
        auto entries = m.messages(); entries[0].text = "changed"w;
        assert(m.messages()[0].text == "info"w && m.messages()[0].time !is null);
    }
}
void main() {
    auto server = new Z8CivetServer("127.0.0.1:0", &runRequest, 2048);
    auto protocol = new Z8CivetServer("127.0.0.1:0", &runRequest, 2048, Z8ResponseMode.application, "server-1"w);
    auto auth = new Z8CivetServer("127.0.0.1:0", &runRequest, 2048, Z8ResponseMode.application, "server-1"w, new Authority());
    scope(exit) server.stop();
    scope(exit) protocol.stop();
    scope(exit) auth.stop();
    writeln(server.port(), " ", protocol.port(), " ", auth.port()); stdout.flush();
    readln();
    server.stop(); server.stop();
    bool stopped; try { server.port(); } catch (Exception) { stopped = true; }
    assert(stopped);
}
''', encoding="utf-8")
    # A delegate carries the handler context and remains valid for the server lifetime.
    text = harness.read_text(encoding="utf-8").replace("&runRequest, 2048", "(Z8HttpRequest request) { runRequest(request); }, 2048")
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
        ports = line.split()
        if len(ports) != 3 or not all(p.isdigit() for p in ports): raise RuntimeError("Server did not start: " + line + process.stderr.read())
        port, protocol_port, auth_port = map(int, ports)
        def request(path, body=None, headers=None, target=None):
            conn = http.client.HTTPConnection("127.0.0.1", target or port, timeout=10)
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
            status, body = request("/api?collect=1&name=user" + str(i) + "&value=" + str(i))
            return status, json.loads(body)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for i, (status, data) in enumerate(pool.map(one, range(64))):
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
        status, body = request("/api?mode=monitor&name=x&value=y")
        assert status == 200 and json.loads(body)["name"] == "x", (status, body)
        status, body = request("/api?mode=protocol&request=demo", target=protocol_port)
        result = json.loads(body)
        assert status == 200 and result["request"] == "demo" and result["success"] is True and result["answer"] == 42, result
        assert result["server"] == "server-1" and result["info"]["messages"][0]["text"] == "notice", result
        status, body = request("/api?mode=fail&request=broken", target=protocol_port)
        result = json.loads(body)
        assert status == 200 and result["request"] == "broken" and result["success"] is False and result["data"] == [], result
        assert result["info"]["messages"][-1]["type"] == "error" and result["info"]["messages"][-1]["text"] == "failed", result
        status, body = request("/api?mode=unbalanced", target=protocol_port)
        result = json.loads(body)
        assert status == 200 and result["request"] is None and result["success"] is False, result
        assert result["info"]["messages"][-1]["text"] == "unbalanced response writer", result
        status, body = request("/api?mode=auth&request=read", target=auth_port)
        result = json.loads(body)
        assert status == 401 and result["status"] == 401 and result["success"] is False and result["data"] == [], result
        assert result["info"]["messages"][0]["type"] == "error", result
        status, body = request("/api?mode=auth&request=read&session=invalid&server=shard", target=auth_port)
        assert status == 401, (status, body)
        status, body = request("/api?mode=auth&request=read&session=valid&server=other", target=auth_port)
        assert status == 401, (status, body)
        status, body = request("/api?mode=auth&request=read&session=valid&server=shard", target=auth_port)
        result = json.loads(body)
        assert status == 200 and result["success"] and result["login"] == "session-user", result
        status, body = request("/api?mode=auth&request=login&login=alice&password=wrong", target=auth_port)
        assert status == 401, (status, body)
        status, body = request("/api?mode=auth&request=login&login=alice&password=secret", target=auth_port)
        result = json.loads(body)
        assert status == 200 and result["success"] and result["login"] == "alice", result
        status, body = request("/api?mode=auth&request=login&session=invalid&login=alice&password=secret", target=auth_port)
        result = json.loads(body)
        assert status == 200 and result["login"] == "alice", result
        status, body = request("/api?name=after&value=error")
        assert status == 200 and json.loads(body)["name"] == "after", (status, body)
        status, body = request("/api?name=x", "x" * 2049)
        assert status == 413
        status, body = request("/api", "--boundary", {"Content-Type":"multipart/form-data; boundary=boundary"})
        assert status == 400
        boundary = "z8-boundary"
        multipart = (b'--z8-boundary\r\nContent-Disposition: form-data; name="name"\r\n\r\nfirst\r\n'
                     b'--z8-boundary\r\nContent-Disposition: form-data; name="name"\r\n\r\nlast\r\n'
                     b'--z8-boundary\r\nContent-Disposition: form-data; name="value"\r\n\r\nvalue\r\n'
                     b'--z8-boundary\r\nContent-Disposition: form-data; name="file"; filename="a+%20.txt"\r\n\r\n'
                     b'hello\x00\r\n--z8-boundaryXinside\r\n'
                     b'--z8-boundary\r\nContent-Disposition: form-data; name="file2"; filename="another"\r\n\r\nx\r\n'
                     b'--z8-boundary--\r\n')
        status, body = request("/api?name=ignored", multipart, {"Content-Type":'multipart/form-data; boundary="' + boundary + '"'})
        assert status == 200, (status, body)
        data = json.loads(body)
        content = "hello\0\r\n--z8-boundaryXinside"
        assert data == {"name":"last", "value":"value", "ip":"127.0.0.1", "filename":"a+%20.txt", "path":"", "content":content, "size":len(content), "count":2}, data
        empty = (b'--z8-boundary\r\nContent-Disposition: form-data; name="file"; filename=""\r\n\r\n'
                 b'\r\n--z8-boundary--\r\n')
        status, body = request("/api", empty, {"Content-Type":"multipart/form-data; boundary=z8-boundary"})
        assert status == 200 and json.loads(body)["filename"] == "" and json.loads(body)["size"] == 0, (status, body)
        status, body = request("/api", multipart[:-10], {"Content-Type":"multipart/form-data; boundary=z8-boundary"})
        assert status == 400, (status, body)
        invalid = (b'--z8-boundary\r\nContent-Disposition: form-data; name="name"\r\n\r\n\xff\r\n'
                   b'--z8-boundary--\r\n')
        status, body = request("/api", invalid, {"Content-Type":"multipart/form-data; boundary=z8-boundary"})
        assert status == 400, (status, body)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request("POST", "/api", body=iter([multipart[:35], multipart[35:]]),
                               headers={"Content-Type":"multipart/form-data; boundary=z8-boundary", "Transfer-Encoding":"chunked"}, encode_chunked=True)
            response = connection.getresponse()
            chunked_status, chunked_body = response.status, response.read().decode("utf-8")
            assert chunked_status == 200 and json.loads(chunked_body)["content"] == content, (chunked_status, chunked_body)
        finally: connection.close()
    finally:
        if process.poll() is None:
            try: process.stdin.write("\n"); process.stdin.flush()
            except OSError: pass
        process.wait(timeout=15)
        stderr = process.stderr.read()
        if process.returncode: raise RuntimeError("Server exited with code " + str(process.returncode) + ": " + stderr)
print("CivetWeb loopback requests, request isolation and limits verified")
