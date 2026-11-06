// A small single-process host for a generated BL project and PostgreSQL.
module webapp_host;

import std.conv : to;
import std.file : exists;
import std.stdio : readln, stdout, stderr, writeln;
import std.string : startsWith, replace;
import z8.runtime;
import z8.database.authentication;
import z8.database.bootstrap;
import z8.database.connection;
import z8.database.postgres;
import z8.database.scheduler : Z8ScheduledRun;
import z8.database.scheduler_service;
import z8.integration.postgres_authority;
import z8.webserver.civetweb;
import z8gen.project_registry;

class SchedulerObserver : IZ8SchedulerObserver {
    void onRuns(Z8ScheduledRun[] runs) { }
    void onError(wstring message) { stderr.writeln("Scheduler: ", message.to!string); }
}

void main(string[] args) {
    if (args.length < 3) throw new Exception("usage: webapp-host <postgres-connection> <schema> [--initialize] [--public-dir <path>] [--config <path>]");
    bool initialize; string publicDirectory, configPath;
    for (size_t i = 3; i < args.length; ++i) {
        if (args[i] == "--initialize" && !initialize) initialize = true;
        else if (args[i] == "--public-dir" && !publicDirectory.length && i + 1 < args.length) publicDirectory = args[++i];
        else if (args[i] == "--config" && !configPath.length && i + 1 < args.length) configPath = args[++i];
        else throw new Exception("invalid option");
    }
    if (!configPath.length && exists("server.properties")) configPath = "server.properties";
    if (configPath.length) z8_server_configure_from_file(configPath);
    auto db = new Z8PostgresConnection(args[1]); scope(exit) db.close();
    auto schema = args[2].to!wstring;
    auto registry = new Z8RuntimeRegistry(); z8_register_project(registry);
    auto previousRegistry = z8_runtime_set_registry(registry);
    scope(exit) z8_runtime_set_registry(previousRegistry);
    enum prefix = "org.zenframework.z8.server.base.table.system."w;
    Z8Object[] systemTables;
    foreach (name; ["Users"w, "Roles"w, "UserRoles"w, "Entries"w, "UserEntries"w, "Sequences"w,
        "Tables"w, "Fields"w, "Requests"w, "RoleTableAccess"w, "RoleFieldAccess"w, "RoleRequestAccess"w, "Files"w, "Settings"w,
        "Jobs"w, "ScheduledJobs"w, "ScheduledJobLogs"w]) {
        auto table = z8_native_new(prefix ~ name); table.z8_ensure(); systemTables ~= table;
    }
    z8_postgres_reconcile_registered(db, schema, registry, systemTables);
    if (initialize) {
        // Give the example administrator its demo entry without changing an
        // existing assignment or other users' menus.
        auto ns = `"` ~ args[2].replace(`"`, `""`) ~ `"`;
        auto id = z8_guid_to_string(z8_guid_create_name("example.Tasks.Administrator"w)).to!string;
        auto entry = z8_guid_to_string(z8_guid_create_name("Tasks"w)).to!string;
        db.execute("INSERT INTO " ~ ns ~ `."SystemUserEntries" ("RecordId", "UserId", "EntryId", "Position") ` ~
            `SELECT $1::uuid, '00000000-0000-0000-0000-000000000002'::uuid, $2::uuid, 1 ` ~
            `WHERE NOT EXISTS (SELECT 1 FROM ` ~ ns ~ `."SystemUserEntries" WHERE "UserId" = '00000000-0000-0000-0000-000000000002'::uuid AND "EntryId" = $2::uuid) ON CONFLICT DO NOTHING`,
            [Z8PostgresParameter.value(id), Z8PostgresParameter.value(entry)]);
        writeln("initialized"); return;
    }
    Z8PostgresAuthenticationConfig config;
    auto applicationConfig = z8_application_configuration();
    config.clientHashesPasswords = applicationConfig.clientHashesPasswords;
    config.maxFailedAttempts = applicationConfig.authFailsLimit;
    config.banMilliseconds = cast(long)applicationConfig.authFailsBanSeconds * 1000;
    if (applicationConfig.uploadMaxMiB <= 0 || cast(ulong)applicationConfig.uploadMaxMiB * 1_048_576UL > size_t.max)
        throw new Exception("invalid upload limit");
    auto bodyLimit = cast(size_t)applicationConfig.uploadMaxMiB * 1_048_576;
    auto securityLog = z8_security_log_file_from_config();
    auto sessions = new Z8SessionManager(cast(long)applicationConfig.sessionTimeoutMinutes * 60_000, applicationConfig.oneSessionPerUser);
    auto authority = new Z8PostgresHttpAuthority(db, schema, registry, config, sessions, "example"w);
    auto scheduler = new Z8PostgresSchedulerService(db, schema, registry, 1000, new SchedulerObserver(), authority, authority);
    scheduler.start(); scope(exit) scheduler.stop();
    auto server = new Z8CivetServer("127.0.0.1:0", (Z8HttpRequest request) {
        auto connection = db.openSibling(); scope(exit) connection.close();
        auto previous = z8_connection_set_current(new Z8PostgresDatabase(connection, schema, registry));
        scope(exit) z8_connection_set_current(previous);
        if (request.path.startsWith("/storage/")) z8_application_dispatch_file_download(request.path.to!wstring);
        else z8_application_dispatch_request();
    }, bodyLimit, Z8ResponseMode.application, "example"w, authority, "Access denied"w, publicDirectory, "/request.json", true, securityLog);
    scope(exit) server.stop();
    writeln(server.port()); stdout.flush(); readln();
}
