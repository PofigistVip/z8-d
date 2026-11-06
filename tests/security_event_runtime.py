"""Exercise SecurityObject and host-created SecurityEvent values through BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/security_event_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomSecurityObject.bl").write_text('''
import org.zenframework.z8.base.security.SecurityObject;
public class CustomSecurityObject extends SecurityObject {
    virtual public string getType() { return "custom"; }
    virtual public string getName() { return "Special"; }
    virtual public guid getId() { return guid.Null; }
}
''', encoding="utf-8")
    (source / "CustomSecurityLog.bl").write_text('''
import org.zenframework.z8.base.security.SecurityLog;
import org.zenframework.z8.base.security.SecurityEvent;
import org.zenframework.z8.base.security.SecurityObject;
import org.zenframework.z8.base.security.User;
public class CustomSecurityLog extends SecurityLog {
    public int count = 0; public string last = "";
    virtual protected bool acceptEvent(SecurityEvent event) { return event.getAction() != "skip"; }
    virtual protected void writeEvent(SecurityEvent event) { count = count + 1; last = event.getAction() + ":" + event.getMessage(); }
    public string formatObject(SecurityObject object) { return super.format(object); }
    public string formatUser(User user) { return super.format(user); }
    public string[string] filtered(string[string] params) { return super.filterParameters(params); }
}
''', encoding="utf-8")
    (source / "SecurityEndpoint.bl").write_text('''
import org.zenframework.z8.lang.Object;
import org.zenframework.z8.base.json.JsonArray;
import org.zenframework.z8.base.application.Application;
import org.zenframework.z8.base.security.User;
public class SecurityEndpoint extends Object {
    virtual protected JsonArray getData(string[string] parameters) {
        Application.logSecurityEvent("table", guid.Null, "Orders", "change"); return null;
    }
}
''', encoding="utf-8")
    (source / "SecurityProbe.bl").write_text('''
import org.zenframework.z8.base.security.SecurityObject;
import org.zenframework.z8.base.security.SecurityEvent;
import org.zenframework.z8.base.security.User;
import org.zenframework.z8.base.application.Application;
public class SecurityProbe {
    public static SecurityObject make(guid id) { return SecurityObject.object("table", id, "Orders"); }
    public static SecurityObject custom() { CustomSecurityObject value; return value; }
    public static SecurityEvent eventType() { SecurityEvent value; return value; }
    public static bool check(SecurityEvent event, guid id) {
        return event.getObject().getType() == "table" && event.getObject().getId() == id && event.getObject().getName() == "Orders" &&
            event.getAction() == "update" && !event.isSuccess() && event.getMessage() == "denied";
    }
    public static bool customType(SecurityObject object) { return object.getType() == "custom"; }
    public static CustomSecurityLog log() { CustomSecurityLog value; return value; }
    public static User userType() { User value; return value; }
    public static void add(guid id) {
        Application.logSecurityEvent("table", id, "Orders", "skip");
        Application.logSecurityEvent(SecurityObject.object("table", id, "Orders"), "update");
    }
    public static bool logCheck(CustomSecurityLog log) { return log.count == 1 && log.last == "update:denied"; }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_SecurityProbe;
class Sink : IZ8SecurityLogSink {
    long count; bool failed, leaked; wstring action;
    void write(Z8Object event, Z8StringMap parameters) {
        ++count;
        action = z8_native_call!wstring("org.zenframework.z8.server.base.security.SecurityEvent.m_getAction"w, event);
        failed = !z8_optional_require(z8_native_call!(Z8Optional!bool)("org.zenframework.z8.server.base.security.SecurityEvent.m_isSuccess"w, event));
        leaked = parameters.z8_containsKey("password"w) || parameters.z8_containsKey("token"w);
        assert(parameters.z8_get("ip"w) == "127.0.0.1"w);
    }
}
void main() {
    alias P = Z8p_536563757269747950726F6265;
    auto id = z8_guid_create(7); auto object = P.m_make(id);
    auto event = z8_security_event_new(object, "update"w);
    z8_security_event_set_result(event, false, "denied"w);
    assert(z8_optional_require(P.m_check(cast(typeof(P.m_eventType()))event, id)));
    assert(z8_optional_require(P.m_customType(P.m_custom())));
    auto formatLog = P.m_log();
    assert(formatLog.m_formatObject(P.m_make(id)) == "table:Orders"w);
    assert(formatLog.m_formatObject(P.m_custom()) == "custom:00000000-0000-0000-0000-000000000000:Special"w);
    auto person = new Z8UserData(); person.id = id; person.login = "alice"w; person.firstName = "Alice"w; person.lastName = "Smith"w;
    assert(formatLog.m_formatUser(cast(typeof(P.m_userType()))z8_user_wrap(person)) == "Alice Smith (alice)"w);
    auto parameters = new Z8StringMap(); parameters.z8_add("password"w, "secret"w); parameters.z8_add("ip"w, "127.0.0.1"w);
    auto filtered = formatLog.m_filtered(parameters);
    assert(filtered.z8_size() == 1 && filtered.z8_get("ip"w) == "127.0.0.1"w && !filtered.z8_containsKey("password"w));
    auto request = new Z8ApplicationRequest(); request.securityLog = P.m_log();
    auto previous = z8_application_set_request(request);
    P.m_add(id); z8_security_events_set_result(request, false, "denied"w);
    z8_security_events_commit(request);
    assert(z8_optional_require(P.m_logCheck(cast(typeof(P.m_log()))request.securityLog)));
    z8_security_events_commit(request);
    assert(z8_optional_require(P.m_logCheck(cast(typeof(P.m_log()))request.securityLog)));
    z8_application_set_request(previous);
    auto sink = new Sink(); request = new Z8ApplicationRequest(); request.securityLogSink = sink;
    request.parameters.z8_add("ip"w, "127.0.0.1"w); request.parameters.z8_add("password"w, "secret"w);
    request.parameters.z8_add("token"w, "secret"w); request.parameters.z8_add("action"w, "read"w);
    request.parameters.z8_add("request"w, "missing"w);
    previous = z8_application_set_request(request);
    bool rejected; try { z8_application_dispatch_request(); } catch (Exception) { rejected = true; }
    assert(rejected && sink.count == 1 && sink.failed && sink.action == "read"w && !sink.leaked);
    z8_application_set_request(previous);
    sink = new Sink(); request = new Z8ApplicationRequest(); request.securityLogSink = sink;
    request.monitor = new Z8RequestMonitor();
    auto user = new Z8UserData(); user.id = id; user.privileges = new Z8Privileges(Z8Access(false, false, false, false, false, true));
    request.session = new Z8ApplicationSession("test"w, user, user);
    request.parameters.z8_add("ip"w, "127.0.0.1"w); request.parameters.z8_add("request"w, "SecurityEndpoint"w);
    request.parameters.z8_add("action"w, "read"w); request.parameters.z8_add("password"w, "secret"w);
    previous = z8_application_set_request(request); z8_application_start_response(request, "SecurityEndpoint"w);
    z8_application_dispatch_request();
    assert(sink.count == 2 && !sink.failed && sink.action == "change"w && !sink.leaked);
    z8_application_set_request(previous);
}
''', encoding="utf-8")
    executable = temp / ("security-event.exe" if os.name == "nt" else "security-event")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable)], cwd=temp, check=True)
print("SecurityObject and SecurityEvent BL values passed")
