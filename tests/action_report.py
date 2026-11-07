"""Exercise ActionReport metadata, parameters and custom report execution."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from runtime_support import import_args, runtime_library

if len(sys.argv) != 2:
    raise SystemExit("Usage: python tests/action_report.py <original-z8-root>")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
compiler = root / ("z8d.exe" if os.name == "nt" else "z8d")
with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source, generated = temp / "bl", temp / "generated"
    shutil.copytree(language, source)
    (source / "CustomReport.bl").write_text('''
import org.zenframework.z8.base.form.report.Report;
import org.zenframework.z8.base.application.Application;
public class CustomReport extends Report {
    virtual protected file execute(guid recordId) {
        file result = format + "-" + recordId.toString() + "-" + Application.requestParameters()["clientContext"];
        result.write("report content"); return result;
    }
}
''', encoding="utf-8")
    (source / "ReportActionTable.bl").write_text('''
import org.zenframework.z8.base.table.Table;
import org.zenframework.z8.base.form.action.ActionReport;
[request] public class ReportActionTable extends Table {
    CustomReport report;
    public ActionReport exportAction;
    exportAction.report = report;
    actions = {exportAction};
    public int parameterCount() { return exportAction.parameters.size(); }
}
''', encoding="utf-8")
    (source / "PrintProbe.bl").write_text('''
import org.zenframework.z8.base.application.Application;
public class PrintProbe {
    public static void emit() {
        file output = "result.txt";
        output.write("report content");
        Application.print(output);
    }
    public static void printFile(file value) { Application.print(value); }
}
''', encoding="utf-8")
    subprocess.run([str(compiler), "project", str(source), str(generated)], check=True)
    harness = temp / "main.d"
    harness.write_text('''
import z8.runtime;
import std.json : parseJSON;
import std.conv : to;
import std.string : startsWith;
import z8gen.ReportActionTable;
import z8gen.PrintProbe;
class Database : IZ8DatabaseConnection, IZ8DatabaseSchema {
    void beginTransaction() {} void commit() {} void rollback() {} void execute(wstring sql) {}
    void call(wstring name, Z8Array!Z8Primary args) {} void flush() {}
    IZ8QueryExecutor queryExecutor(Z8Object query) { return null; }
    wstring databaseSchema() { return "test"w; }
}
void checkFile(Z8File file, wstring name, Z8ApplicationSession session) {
    assert(file.id is null && file.name == name && file.path.startsWith("storage/z8-generated/"w));
    auto download = new Z8ApplicationRequest(); download.session = session;
    auto previous = z8_application_set_request(download); scope(exit) z8_application_set_request(previous);
    z8_application_dispatch_file_download("/"w ~ file.path);
    auto data = z8_application_response_binary(download); scope(exit) z8_binary_close(data);
    assert(cast(string)z8_binary_snapshot(data, 1024) == "report content");
    download.session = new Z8ApplicationSession("different"w, session.user, session.system);
    bool denied; try { z8_application_dispatch_file_download("/"w ~ file.path); } catch (Exception) { denied = true; }
    assert(denied);
}
void main(string[] args) {
    z8_file_set_roots(args[1]);
    auto previousDb = z8_connection_set_current(new Database()); scope(exit) z8_connection_set_current(previousDb);
    auto sample = z8_new!Z8p_5265706F7274416374696F6E5461626C65(); z8_nonnull(sample);
    assert(z8_optional_require(sample.m_parameterCount()) == 1);
    auto user = new Z8UserData(); user.id = z8_guid_create(1);
    user.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto session = new Z8ApplicationSession("test"w, user, user);
    auto request = new Z8ApplicationRequest(); request.session = session; request.monitor = new Z8RequestMonitor();
    request.parameters.z8_add("request"w, "ReportActionTable"w); request.parameters.z8_add("action"w, "meta"w);
    auto previous = z8_application_set_request(request); scope(exit) z8_application_set_request(previous);
    z8_application_start_response(request, "ReportActionTable"w); z8_application_dispatch_request();
    z8_application_finish_response(request, cast(Z8RequestMonitor)request.monitor);
    auto meta = parseJSON(z8_application_response_text(request).to!string);
    assert(meta["actions"].array.length == 1 && meta["actions"][0]["isReport"].boolean);
    assert(meta["actions"][0]["parameters"].array.length == 1);
    assert(meta["actions"][0]["parameters"][0]["id"].str == "format" && meta["actions"][0]["parameters"][0]["value"].str == "pdf");
    request = new Z8ApplicationRequest(); request.session = session; auto monitor = new Z8RequestMonitor(); request.monitor = monitor;
    request.parameters.z8_add("request"w, "ReportActionTable"w); request.parameters.z8_add("action"w, "action"w);
    request.parameters.z8_add("name"w, "exportAction"w);
    request.parameters.z8_add("clientContext"w, "custom"w);
    request.parameters.z8_add("records"w, `["00000000-0000-0000-0000-000000000011","00000000-0000-0000-0000-000000000012"]`w);
    request.parameters.z8_add("parameters"w, `[{"id":"format","value":"xls"}]`w);
    z8_application_set_request(request); z8_application_start_response(request, "ReportActionTable"w);
    z8_application_dispatch_request(); z8_application_finish_response(request, monitor);
    auto response = parseJSON(z8_application_response_text(request).to!string);
    assert(response["success"].boolean && monitor.files().length == 2);
    checkFile(monitor.files()[0], "xls-00000000-0000-0000-0000-000000000011-custom"w, session);
    checkFile(monitor.files()[1], "xls-00000000-0000-0000-0000-000000000012-custom"w, session);
    request = new Z8ApplicationRequest(); request.session = session; monitor = new Z8RequestMonitor(); request.monitor = monitor;
    request.parameters.z8_add("request"w, "ReportActionTable"w); request.parameters.z8_add("action"w, "action"w);
    request.parameters.z8_add("name"w, "exportAction"w);
    request.parameters.z8_add("clientContext"w, "second"w);
    request.parameters.z8_add("records"w, `["00000000-0000-0000-0000-000000000011"]`w);
    z8_application_set_request(request); z8_application_start_response(request, "ReportActionTable"w);
    z8_application_dispatch_request(); z8_application_finish_response(request, monitor);
    assert(monitor.files().length == 1);
    checkFile(monitor.files()[0], "pdf-00000000-0000-0000-0000-000000000011-second"w, session);
    request = new Z8ApplicationRequest(); request.session = session; monitor = new Z8RequestMonitor(); request.monitor = monitor;
    z8_application_set_request(request);
    Z8p_5072696E7450726F6265.m_emit();
    assert(monitor.files().length == 1);
    checkFile(monitor.files()[0], "result.txt"w, session);
    auto upload = z8_file_from_upload("uploaded.txt"w, cast(const(ubyte)[])"report content");
    Z8p_5072696E7450726F6265.m_printFile(upload);
    checkFile(monitor.files()[1], "uploaded.txt"w, session);
    auto stored = z8_file_from_path("storage/retained.txt"w); stored.id = z8_guid_create(10);
    Z8p_5072696E7450726F6265.m_printFile(stored);
    assert(monitor.files()[2] is stored);
    auto published = monitor.files()[0];
    Z8p_5072696E7450726F6265.m_printFile(published);
    assert(monitor.files()[3] is published);
}
''', encoding="utf-8")
    executable = temp / ("action-report.exe" if os.name == "nt" else "action-report")
    args = ["-I" + str(generated), *import_args(), *map(str, generated.rglob("*.d")),
            str(harness), str(runtime), "-of=" + str(executable)]
    response = temp / "dmd.rsp"
    response.write_text("\n".join('"' + arg.replace('\\', '/') + '"' for arg in args), encoding="utf-8")
    subprocess.run(["dmd", "@" + str(response)], cwd=temp, check=True)
    subprocess.run([str(executable), str(temp)], cwd=temp, check=True)
print("ActionReport metadata, format and selected records verified")
