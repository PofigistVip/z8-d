// A small single-process host for a generated BL project and PostgreSQL.
module webapp_host;

import std.conv : to;
import std.stdio : readln, stdout, writeln;
import std.string : startsWith;
import z8.runtime;
import z8.database.authentication;
import z8.database.bootstrap;
import z8.database.connection;
import z8.database.postgres;
import z8.integration.postgres_authority;
import z8.webserver.civetweb;
import z8gen.project_registry;

void main(string[] args) {
    if (args.length < 3 || args.length > 4) throw new Exception("usage: webapp-host <postgres-connection> <schema> [--initialize]");
    if (args.length == 4 && args[3] != "--initialize") throw new Exception("unknown option");
    auto db = new Z8PostgresConnection(args[1]); scope(exit) db.close();
    auto schema = args[2].to!wstring;
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    auto previousRegistry = z8_runtime_set_registry(registry);
    scope(exit) z8_runtime_set_registry(previousRegistry);
    enum prefix = "org.zenframework.z8.server.base.table.system."w;
    Z8Object[] systemTables;
    foreach (name; ["Users"w, "Roles"w, "UserRoles"w, "Entries"w, "UserEntries"w, "Sequences"w,
        "Tables"w, "Fields"w, "Requests"w, "RoleTableAccess"w, "RoleFieldAccess"w, "RoleRequestAccess"w, "Files"w]) {
        auto table = z8_native_new(prefix ~ name); table.z8_ensure(); systemTables ~= table;
    }
    z8_postgres_reconcile_registered(db, schema, registry, systemTables);
    if (args.length == 4) { writeln("initialized"); return; }
    Z8PostgresAuthenticationConfig config;
    auto authority = new Z8PostgresHttpAuthority(db, schema, registry, config, null, "example"w);
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto connection = db.openSibling(); scope(exit) connection.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(connection, schema, registry));
        scope(exit) z8_connection_set_current(previous);
        if (request.path.startsWith("/storage/")) z8_application_dispatch_file_download(request.path.to!wstring);
        else z8_application_dispatch_request();
    }, 5 * 1024 * 1024, Z8ResponseMode.application, "example"w, authority, "Access denied"w, null, "/request.json", true);
    scope(exit) server.stop();
    writeln(server.port()); stdout.flush(); readln();
}
