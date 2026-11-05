"""Exercise runtime access to virtual BL object request hooks."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
if len(sys.argv) > 2: raise SystemExit("Usage: python tests/object_dispatch_hooks.py [original-z8-root]")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    source.mkdir()
    (source / "JsonArray.bl").write_text('''
[native "org.zenframework.z8.server.base.json.parser.JsonArray"] public class JsonArray {
    public static JsonArray parse(string text); public string toString();
}
''', encoding="utf-8")
    (source / "Object.bl").write_text('''
[native "org.zenframework.z8.server.runtime.OBJECT"] public class Object {
    virtual protected JsonArray getData(string[string] parameters);
    virtual protected binary processContentRequest(string[string] parameters, file[] files);
}
''', encoding="utf-8")
    (source / "Endpoint.bl").write_text('''
[ui "Grid"] [displayName "Demo"] public class Endpoint extends Object {
    virtual protected JsonArray getData(string[string] parameters) { return JsonArray.parse(parameters["data"]); }
    virtual protected binary processContentRequest(string[string] parameters, file[] files) {
        binary result = parameters["content"]; return result;
    }
}
''', encoding="utf-8")
    (source / "Child.bl").write_text('public class Child extends Endpoint {}', encoding="utf-8")
    if len(sys.argv) == 2:
        language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
        if not language.is_dir(): raise SystemExit("Original BL standard library not found")
        (source / "Object.bl").unlink(); (source / "JsonArray.bl").unlink()
        shutil.copytree(language, source, dirs_exist_ok=True)
        path = source / "Endpoint.bl"
        path.write_text("import org.zenframework.z8.lang.Object;\nimport org.zenframework.z8.base.json.JsonArray;\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import std.json : parseJSON;
import std.conv : to;
void main() {
    auto params = new Z8StringMap();
    params.z8_add("data"w, `[1,"text"]`w); params.z8_add("content"w, "payload"w);
    auto files = new Z8Array!Z8File();
    auto target = z8_object_new_instance("Child"w);
    auto data = target.z8_object_get_data(params);
    assert(z8_native_call!wstring("org.zenframework.z8.server.base.json.parser.JsonArray.m_toString"w, data) == `[1,"text"]`w);
    auto content = target.z8_object_process_content(params, files);
    assert(cast(string)content.data == "payload");
    auto object = z8_object_new_instance("org.zenframework.z8.server.runtime.OBJECT"w);
    assert(object.z8_object_get_data(params) is null && object.z8_object_process_content(params, files) is null);
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    auto request = new Z8ApplicationRequest(); request.parameters = params;
    request.session = new Z8ApplicationSession("session"w, user, user);
    auto monitor = new Z8RequestMonitor(); request.monitor = monitor;
    z8_application_set_request(request);
    z8_application_start_response(request, "Child"w);
    bool denied;
    try { z8_application_dispatch_object("Child"w, null); } catch (Exception) { denied = true; }
    assert(denied && z8_application_response_text(request) == `{"request":"Child","success":true`w);
    bool checked;
    z8_application_dispatch_object("Child"w, (Z8ApplicationSession session, wstring name, wstring action) {
        checked = session is request.session && name == "Child"w && action is null; return checked;
    });
    z8_application_finish_response(request, monitor, "server"w);
    auto result = parseJSON(z8_application_response_text(request).to!string);
    assert(checked && result["data"].array.length == 2 && result["data"][1].str == "text" && result["ui"].str == "Grid");
    assert(monitor.source == "Demo"w);
    auto binaryRequest = new Z8ApplicationRequest(); binaryRequest.parameters = params;
    binaryRequest.session = request.session; binaryRequest.monitor = new Z8RequestMonitor();
    params.z8_add("action"w, "content"w);
    z8_application_set_request(binaryRequest); z8_application_start_response(binaryRequest, "Child"w);
    z8_application_dispatch_object("Child"w, (Z8ApplicationSession session, wstring name, wstring action) { return action == "content"w; });
    assert(z8_application_has_binary_response(binaryRequest));
    assert(cast(string)z8_application_response_binary(binaryRequest).data == "payload");
    auto authorized = new Z8ApplicationRequest(); authorized.session = request.session;
    authorized.parameters.z8_add("data"w, `["allowed"]`w); authorized.monitor = new Z8RequestMonitor();
    z8_application_set_request(authorized); z8_application_start_response(authorized, "Child"w);
    assert(!z8_application_may_execute(null, "Child"w, null));
    denied = false; try { z8_application_dispatch_authorized_object("Child"w); } catch (Exception) { denied = true; }
    assert(denied);
    user.privileges = new Z8Privileges(Z8Access(false, false, false, false, false, true));
    user.privileges.setRequestAccess(z8_guid_create_name("Child"w), Z8Access.init);
    denied = false; try { z8_application_dispatch_authorized_object("Child"w); } catch (Exception) { denied = true; }
    assert(denied);
    user.privileges.setRequestAccess(z8_guid_create_name("Child"w), Z8Access(false, false, false, false, false, true));
    z8_application_dispatch_authorized_object("Child"w);
    z8_application_finish_response(authorized, cast(Z8RequestMonitor)authorized.monitor);
    assert(parseJSON(z8_application_response_text(authorized).to!string)["data"][0].str == "allowed");
    auto unified = new Z8ApplicationRequest(); unified.session = request.session; unified.monitor = new Z8RequestMonitor();
    unified.parameters.z8_add("request"w, "Child"w); unified.parameters.z8_add("data"w, `["unified"]`w);
    z8_application_set_request(unified); z8_application_start_response(unified, "Child"w);
    z8_application_dispatch_request(); z8_application_finish_response(unified, cast(Z8RequestMonitor)unified.monitor);
    assert(parseJSON(z8_application_response_text(unified).to!string)["data"][0].str == "unified");
    z8_application_set_request(null);
}
''', encoding="utf-8")
    exe = temp / ("object-dispatch.exe" if os.name == "nt" else "object-dispatch")
    subprocess.run(["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
                    str(harness), str(runtime), "-of=" + str(exe)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Virtual OBJECT request hooks and inheritance verified")
