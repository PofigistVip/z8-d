"""Verify generated startup registration against standard BL declarations."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/project_registry.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    classes = {
        "Orders": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.StringField;
[name "Orders"] [generatable] [request true] public class Orders extends Table { [name "Title"] StringField title; }
''',
        "BaseTable": '''
import org.zenframework.z8.base.table.Table;
[name "Inherited"] [generatable] public class BaseTable extends Table {}
''',
        "DerivedTable": '[generatable] public class DerivedTable extends BaseTable {}',
        "Api": '[request] public class Api {}',
        "ApiChild": 'public class ApiChild extends Api {}',
        "PrivateApi": '[request false] public class PrivateApi extends Api {}',
        "UnnamedTable": '''
import org.zenframework.z8.base.table.Table;
[generatable] public class UnnamedTable extends Table {}
''',
        "Other": 'public class Other {}',
        "DailyJob": '''
import org.zenframework.z8.base.Executable;
[job] [request] public class DailyJob extends Executable {}
''',
        "ScheduledJob": '''
import org.zenframework.z8.base.Executable;
[job "*/5 * * * *"] public class ScheduledJob extends Executable {}
''',
        "MenuEntry": '[entry] public class MenuEntry {}',
        "BaseJob": '''
import org.zenframework.z8.base.Executable;
[name "Nightly"] [request] public class BaseJob extends Executable {
    useTransaction = false;
    virtual protected void execute() { info("base"); }
}
''',
        "DerivedJob": '''
public class DerivedJob extends BaseJob { virtual protected void execute() { info("derived"); } }
''',
        "BaseThing": '''
import org.zenframework.z8.lang.Object;
[name "Thing"] public class BaseThing extends Object {}
''',
        "DerivedThing": 'public class DerivedThing extends BaseThing {}',
        "NamedFactory": '''
import org.zenframework.z8.lang.Object;
public class NamedFactory {
    public static Object fresh() { return Object.newNamedInstance("Thing"); }
    public static Object singleton() { return Object.getNamedSingleton("Thing"); }
}
''',
        "TableFactory": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.lang.Object;
public class TableFactory { public static Object find(string name) { return Table.newInstance(name); } }
''',
    }
    for name, code in classes.items():
        (source / (name + ".bl")).write_text(code, encoding="utf-8")
    system_tools = source / "org/zenframework/z8/server/base/table/system/SystemTools.bl"
    system_tools.parent.mkdir(parents=True, exist_ok=True)
    system_tools.write_text("public class SystemTools {}", encoding="utf-8")
    (source / "DerivedTools.bl").write_text('''
import org.zenframework.z8.server.base.table.system.SystemTools;
public class DerivedTools extends SystemTools {}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.project_registry;
import z8gen.TableFactory;
import z8gen.NamedFactory;
import std.json : parseJSON, JSONType;
import std.conv : to;
import core.thread : Thread;
void main() {
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    auto tables = registry.tables(), requests = registry.requests();
    assert(tables.length == 2 && requests.length == 6 && registry.jobs().length == 2 && registry.entries().length == 1);
    auto revision = z8_runtime_version(registry);
    assert(revision.details.length == 6 && revision.details[0].classId == "Version"w && revision.details[0].controlSum == revision.number);
    assert(revision.details[0].id == z8_guid_create_name("system.version"w));
    assert(revision.details[1].classId == "DailyJob"w && revision.details[2].classId == "DerivedTable"w &&
           revision.details[3].classId == "MenuEntry"w && revision.details[4].classId == "Orders"w && revision.details[5].classId == "ScheduledJob"w);
    foreach (record; revision.details[1 .. $]) {
        auto object = z8_object_new_instance(record.classId);
        assert(record.controlSum == z8_object_control_sum(object).to!wstring);
        assert(record.id == z8_native_call!Z8Guid("org.zenframework.z8.server.runtime.OBJECT.m_key"w, object));
    }
    auto excluded = new Z8RuntimeRegistry(); excluded.registerEntry(z8_object_new_instance("DerivedTools"w));
    assert(z8_runtime_version(excluded).details.length == 1 && z8_runtime_version(excluded).number == "0.000.000.000"w);
    Z8RuntimeVersion changedRevision;
    changedRevision.details = [Z8VersionRecord(z8_guid_create(1), "A"w, "new A"w, "new display"w, "10"w),
        Z8VersionRecord(z8_guid_create(2), "B"w, "new B"w, "display B"w, "20"w),
        Z8VersionRecord(z8_guid_create(3), "C"w, "new C"w, "display C"w, "30"w)];
    auto diff = parseJSON(z8_runtime_version_diff(`[{'className':'A','name':'old A','displayName':'old display','controlSum':'10','extra':'kept'},
        {'className':'B','name':'old B','controlSum':'19'}, {'className':'Removed','name':'old'}]`w, changedRevision).to!string).array;
    assert(diff.length == 4 && diff[0].object["extra"].str == "kept" && diff[0].object["changed"].type == JSONType.false_);
    assert(diff[0].object["newName"].str == "new A" && diff[1].object["changed"].type == JSONType.true_);
    assert(diff[1].object["newControlSum"].str == "20" && !("changed" in diff[2].object));
    assert(diff[3].object["className"].str == "C" && diff[3].object["name"].str == "" &&
           diff[3].object["newName"].str == "new C" && diff[3].object["changed"].type == JSONType.true_);
    assert(parseJSON(z8_runtime_version_diff("[]"w, changedRevision).to!string).array.length == 3);
    bool invalidRevision;
    try { z8_runtime_version_diff("[{}]"w, changedRevision); } catch (Exception) { invalidRevision = true; }
    assert(invalidRevision);
    bool disabledSchedule, activeSchedule;
    foreach (job; registry.jobs()) {
        if (job.classId == "DailyJob"w) disabledSchedule = job.hasSchedule && job.cron !is null && job.cron.length == 0;
        if (job.classId == "ScheduledJob"w) activeSchedule = job.hasSchedule && job.cron == "*/5 * * * *"w;
    }
    assert(disabledSchedule && activeSchedule);
    bool dailyKey, scheduledKey;
    foreach (key; registry.jobKeys()) {
        dailyKey |= key == z8_guid_create_name("DailyJob"w);
        scheduledKey |= key == z8_guid_create_name("ScheduledJob"w);
    }
    assert(dailyKey && scheduledKey);
    auto manual = new Z8RuntimeRegistry(); manual.registerJob(z8_object_new_instance("DerivedJob"w));
    assert(manual.jobs().length == 1 && !manual.jobs()[0].hasSchedule && manual.jobs()[0].cron is null);
    bool orders, inherited, api, child, orderRequest;
    foreach (table; tables) {
        if (table.name == "Orders"w) orders = table.classId == "Orders"w && table.fields.length == 7;
        if (table.name == "Inherited"w) inherited = table.classId == "DerivedTable"w;
    }
    foreach (request; requests) {
        if (request.classId == "Api"w) api = true;
        if (request.classId == "ApiChild"w) child = true;
        if (request.classId == "Orders"w) orderRequest = true;
        assert(request.classId != "PrivateApi"w);
    }
    assert(orders && inherited && api && child && orderRequest);
    registry.registerTable(z8_object_new_instance("BaseTable"w));
    assert(registry.newTableByName("Inherited"w).z8_class_id() == "DerivedTable"w);
    z8_register_project(registry); assert(registry.tables().length == 2 && registry.requests().length == 6 && registry.jobs().length == 2 && registry.entries().length == 1);
    assert(registry.newExecutableByName("Nightly"w).z8_class_id() == "DerivedJob"w);
    registry.registerExecutable(z8_object_new_instance("BaseJob"w));
    assert(registry.newExecutableByName("Nightly"w).z8_class_id() == "DerivedJob"w);
    assert(registry.newJobByClass("DailyJob"w).z8_class_id() == "DailyJob"w);
    assert(registry.newEntryByClass("MenuEntry"w).z8_class_id() == "MenuEntry"w && registry.entryKeys()[0] == z8_guid_create_name("MenuEntry"w));
    auto first = registry.newTableByName("Orders"w), second = registry.newTableByClass("Orders"w);
    assert(first !is null && second !is null && first !is second && first.z8_class_id() == "Orders"w);
    assert(registry.newTableByName("Missing"w) is null && registry.newRequestByClass("Api"w).z8_class_id() == "Api"w);
    assert(registry.newTables().length == 2);
    auto previousRegistry = z8_runtime_set_registry(registry);
    alias NamedFactory = Z8p_4E616D6564466163746F7279;
    auto named = NamedFactory.m_fresh(), another = NamedFactory.m_fresh(), singleton = NamedFactory.m_singleton();
    assert(named.z8_class_id() == "DerivedThing"w && another !is named && singleton !is named);
    assert(singleton is NamedFactory.m_singleton());
    z8_register_project(registry); assert(singleton is NamedFactory.m_singleton());
    assert(registry.newNamedByName("missing"w) is null);
    assert(z8_native_is_instance("org.zenframework.z8.server.base.table.system.Users"w, registry.newNamedByName("SystemUsers"w)));
    Z8Object[8] values; Thread[] workers;
    Thread makeWorker(size_t index) { return new Thread({ values[index] = registry.namedSingleton("Thing"w); }); }
    foreach (i; 0 .. values.length) workers ~= makeWorker(i);
    foreach (worker; workers) worker.start();
    foreach (worker; workers) worker.join();
    foreach (value; values) assert(value is singleton);
    auto factoryValue = Z8p_5461626C65466163746F7279.m_find("Orders"w);
    assert(factoryValue !is null && factoryValue.z8_class_id() == "Orders"w && factoryValue !is first);
    bool missing; try { Z8p_5461626C65466163746F7279.m_find("Missing"w); } catch (Exception) { missing = true; }
    assert(missing);
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    request.monitor = new Z8RequestMonitor(); request.parameters.z8_add("request"w, "Api"w);
    z8_application_set_request(request); z8_application_start_response(request, "Api"w); z8_application_dispatch_request();
    z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor);
    assert(parseJSON(z8_application_response_text(request).to!string)["data"].type == JSONType.null_);
    request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    auto monitor = new Z8RequestMonitor(); request.monitor = monitor;
    request.parameters.z8_add("request"w, "BaseJob"w); request.parameters.z8_add("scheduled"w, "true"w);
    z8_application_set_request(request); z8_application_start_response(request, "BaseJob"w); z8_application_dispatch_request();
    assert(monitor.messages().length == 1 && monitor.messages()[0].text == "derived"w);
    z8_runtime_set_registry(previousRegistry);
}
''', encoding="utf-8")
    exe = temp / ("registry.exe" if os.name == "nt" else "registry")
    args = ["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("Generated project registration for tables and requests verified")
