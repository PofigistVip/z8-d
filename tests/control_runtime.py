"""Exercise native Control metadata and Source references from generated BL."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/control_runtime.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomField.bl").write_text('''
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.json.JsonWriter;
import org.zenframework.z8.base.query.Query;
public class CustomField extends StringField {
    virtual protected void writeMeta(JsonWriter writer, Query query, Query context) { writer.writeProperty("custom", "enabled"); writer.writeProperty("customReadOnly", readOnly); }
}
''', encoding="utf-8")
    (source / "CustomTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.form.Fieldset;
import org.zenframework.z8.base.form.Section;
import org.zenframework.z8.base.form.Tab;
import org.zenframework.z8.base.form.TabControl;
public class CustomTable extends Table {
    [name "Label"] CustomField label;
    label.required = true; label.width = 120; label.colSpan = 2;
    Table destination;
    label.source = destination; label.source.valueFrom = recordId; label.source.filterField = destination.recordId;
    label.dependency = recordId; label.dependsOn = recordId; label.dependencies = {recordId};
    Fieldset panel; Section nested; TabControl tabControl; Tab tab;
    panel.controls = {nested}; nested.controls = {label};
    tabControl.tabs = {tab}; tab.controls = {label}; controls = {panel, tabControl};
}
''', encoding="utf-8")
    (source / "CyclicTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.form.Section;
public class CyclicTable extends Table { Section section; section.controls = {section}; controls = {section}; }
''', encoding="utf-8")
    (source / "ControlProbe.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.table.value.GuidField;
import org.zenframework.z8.base.table.value.StringField;
import org.zenframework.z8.base.form.Section;
public class ControlProbe {
    public static CustomField makeCustom() { CustomField value; return value; }
    public static CustomTable makeTable() { CustomTable value; return value; }
    public static bool verify() {
        StringField field; GuidField key; Table target; Section section;
        if (field.colSpan != 1 || field.flex != 0 || field.readOnly || field.required || field.editable || field.important) return false;
        field.colSpan = 3; field.flex = 2; field.height = 45;
        field.readOnly = true; field.required = true; field.editable = true; field.important = true;
        field.dependency = key; field.dependsOn = key; field.dependencies.add(field);
        field.source = target; field.source.valueFrom = key; field.source.filterField = key;
        if (section.colCount != 3) return false;
        section.colCount = 2; section.controls.add(field);
        return field.colSpan == 3 && field.flex == 2 && field.height == 45 && field.readOnly && field.required && field.editable && field.important &&
            field.dependency == key && field.dependsOn == key && field.dependencies.size() == 1 && field.dependencies.first() == field &&
            field.source.query == target && field.source.valueFrom == key && field.source.filterField == key &&
            section.colCount == 2 && section.controls.size() == 1 && section.controls.first() == field;
    }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import z8gen.p_ControlProbe;
import std.json : parseJSON;
import std.conv : to;
void main() {
    alias P = Z8p_436F6E74726F6C50726F6265;
    assert(z8_optional_require(P.m_verify()));
    auto request = new Z8ApplicationRequest(); auto monitor = new Z8RequestMonitor(); request.monitor = monitor;
    z8_application_set_request(request); z8_application_start_response(request, "meta"w);
    z8_control_write_custom_meta(P.m_makeCustom(), null, null);
    z8_application_finish_response(request, monitor);
    assert(parseJSON(z8_application_response_text(request).to!string)["custom"].str == "enabled");
    request = new Z8ApplicationRequest(); monitor = new Z8RequestMonitor(); request.monitor = monitor;
    z8_application_set_request(request); z8_application_start_response(request, "meta"w);
    auto table = z8_nonnull(P.m_makeTable()); auto privileges = new Z8Privileges(Z8Access(true, false, false, false, false, true));
    z8_control_write_field_meta(table.f_label, table, table, privileges);
    z8_application_finish_response(request, monitor);
    auto meta = parseJSON(z8_application_response_text(request).to!string);
    assert(meta["type"].str == "string" && meta["name"].str == "label" && meta["header"].str == "Label");
    assert(meta["length"].integer == 30 && meta["width"].integer == 120 && meta["colSpan"].integer == 2);
    assert(meta["readOnly"].boolean && !meta["required"].boolean && meta["custom"].str == "enabled");
    assert(meta["customReadOnly"].boolean && !z8_optional_require(table.f_label.f_readOnly));
    assert(meta["source"]["field"].str == "recordId" && meta["source"]["link"].str == "recordId");
    assert(meta["dependency"].str == "recordId" && meta["dependencies"][0].str == "recordId");
    privileges.setRequestAccess(z8_guid_create_name(table.f_destination.z8_class_id()), Z8Access.init);
    request = new Z8ApplicationRequest(); monitor = new Z8RequestMonitor(); request.monitor = monitor;
    z8_application_set_request(request); z8_application_start_response(request, "meta"w);
    z8_control_write_field_meta(table.f_label, table, table, privileges); z8_application_finish_response(request, monitor);
    assert("source" !in parseJSON(z8_application_response_text(request).to!string).object);
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, false, false, false, false, true));
    request = new Z8ApplicationRequest(); monitor = new Z8RequestMonitor(); request.monitor = monitor;
    request.session = new Z8ApplicationSession("test"w, user, user);
    request.parameters.z8_add("request"w, "CustomTable"w); request.parameters.z8_add("action"w, "meta"w);
    request.parameters.z8_add("fields"w, `["label"]`w);
    z8_application_set_request(request); z8_application_start_response(request, "CustomTable"w);
    z8_application_dispatch_request(); z8_application_finish_response(request, monitor);
    meta = parseJSON(z8_application_response_text(request).to!string);
    assert(meta["isQuery"].boolean && meta["fields"].array.length == 3 && meta["primaryKey"].str == "recordId" && meta["lockKey"].str == "lock");
    assert(meta["fields"][0]["name"].str == "label" && meta["fields"][0]["custom"].str == "enabled" && meta["access"]["read"].boolean && !meta["access"]["write"].boolean);
    assert(meta["limit"].integer == 200 && meta["colCount"].integer == 4 && "data" !in meta.object);
    assert(meta["controls"][0]["isFieldset"].boolean && meta["controls"][0]["isSection"].boolean);
    assert(meta["controls"][0]["controls"][0]["isSection"].boolean && meta["controls"][0]["controls"][0]["controls"][0]["name"].str == "label");
    assert(meta["controls"][1]["isTabControl"].boolean && meta["controls"][1]["tabs"][0]["isTab"].boolean);
    assert(meta["controls"][1]["tabs"][0]["colCount"].integer == 1 && meta["controls"][1]["tabs"][0]["controls"][0]["name"].str == "label");
    user.privileges.setFieldAccess(z8_guid_create_name("CustomTable.Label"w), Z8Access.init);
    request = new Z8ApplicationRequest(); monitor = new Z8RequestMonitor(); request.monitor = monitor;
    request.session = new Z8ApplicationSession("test"w, user, user); request.parameters.z8_add("request"w, "CustomTable"w);
    request.parameters.z8_add("action"w, "meta"w); request.parameters.z8_add("fields"w, `["label"]`w);
    z8_application_set_request(request); z8_application_start_response(request, "CustomTable"w); z8_application_dispatch_request();
    z8_application_finish_response(request, monitor); meta = parseJSON(z8_application_response_text(request).to!string);
    assert("controls" !in meta["controls"][0]["controls"][0].object);
    assert("controls" !in meta["controls"][1]["tabs"][0].object);
    request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    request.parameters.z8_add("request"w, "CyclicTable"w); request.parameters.z8_add("action"w, "meta"w);
    z8_application_set_request(request); z8_application_start_response(request, "CyclicTable"w);
    bool cyclic; try { z8_application_dispatch_request(); } catch (Exception error) { cyclic = error.msg == "cyclic section controls"; } assert(cyclic);
    user.privileges.setTableAccess(z8_guid_create_name("CustomTable"w), Z8Access.init);
    request = new Z8ApplicationRequest(); request.session = new Z8ApplicationSession("test"w, user, user);
    request.parameters.z8_add("request"w, "CustomTable"w); request.parameters.z8_add("action"w, "meta"w);
    z8_application_set_request(request); z8_application_start_response(request, "CustomTable"w);
    bool denied; try { z8_application_dispatch_request(); } catch (Exception) { denied = true; } assert(denied);
    z8_application_set_request(null);
}
''', encoding="utf-8")
    exe = temp / ("control-runtime.exe" if os.name == "nt" else "control-runtime")
    args = ["dmd", "-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")), str(harness), str(runtime), "-of=" + str(exe)]
    response_file = temp / "dmd.rsp"
    response_file.write_text("\n".join('"' + arg.replace('"', r'\"') + '"' for arg in args[1:]) + "\n", encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response_file)], cwd=temp, check=True)
    subprocess.run([str(exe)], cwd=temp, check=True)
print("BL Control properties, dependencies and Source references verified")
