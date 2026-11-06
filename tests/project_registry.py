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
        "TableFactory": '''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.lang.Object;
public class TableFactory { public static Object find(string name) { return Table.newInstance(name); } }
''',
    }
    for name, code in classes.items():
        (source / (name + ".bl")).write_text(code, encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.project_registry;
import z8gen.p_TableFactory;
import std.json : parseJSON, JSONType;
import std.conv : to;
void main() {
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    auto tables = registry.tables(), requests = registry.requests();
    assert(tables.length == 2 && requests.length == 6 && registry.jobs().length == 1 && registry.entries().length == 1);
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
    z8_register_project(registry); assert(registry.tables().length == 2 && registry.requests().length == 6 && registry.jobs().length == 1 && registry.entries().length == 1);
    assert(registry.newExecutableByName("Nightly"w).z8_class_id() == "DerivedJob"w);
    registry.registerExecutable(z8_object_new_instance("BaseJob"w));
    assert(registry.newExecutableByName("Nightly"w).z8_class_id() == "DerivedJob"w);
    assert(registry.newJobByClass("DailyJob"w).z8_class_id() == "DailyJob"w && registry.jobKeys()[0] == z8_guid_create_name("DailyJob"w));
    assert(registry.newEntryByClass("MenuEntry"w).z8_class_id() == "MenuEntry"w && registry.entryKeys()[0] == z8_guid_create_name("MenuEntry"w));
    auto first = registry.newTableByName("Orders"w), second = registry.newTableByClass("Orders"w);
    assert(first !is null && second !is null && first !is second && first.z8_class_id() == "Orders"w);
    assert(registry.newTableByName("Missing"w) is null && registry.newRequestByClass("Api"w).z8_class_id() == "Api"w);
    assert(registry.newTables().length == 2);
    auto previousRegistry = z8_runtime_set_registry(registry);
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
