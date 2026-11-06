module z8.database.privileges;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;

struct Z8LoadedPrivileges {
    Z8Privileges privileges;
    Z8Guid[] roleIds;
    wstring[] roleNames;
}
private bool permission(Z8PostgresValue value) { return !value.isNull && value.text.to!int != 0; }
private bool sameTablePermissions(Z8Access a, Z8Access b) {
    return a.read == b.read && a.write == b.write && a.create == b.create && a.copy == b.copy && a.destroy == b.destroy;
}

// Read User.loadRoles/load*Access semantics: OR each grant across assigned
// roles, use the roles' union as the fallback, and intersect field restrictions
// with their owning table's access.
Z8LoadedPrivileges z8_postgres_load_privileges(Z8PostgresConnection db, wstring schema, Z8Guid userId) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (userId is null) throw new Z8PostgresException("user GUID is required");
    auto ns = quoteIdentifier(schema);
    auto params = [Z8PostgresParameter.value(z8_guid_to_string(userId).to!string)];
    enum nonzero = "'00000000-0000-0000-0000-000000000000'::uuid";
    auto roles = db.execute(`SELECT DISTINCT r."RecordId"::text, r."Read", r."Write", r."Create", r."Copy", r."Destroy", r."Execute", r."Name" FROM ` ~
        ns ~ `."SystemUserRoles" ur JOIN ` ~ ns ~ `."SystemRoles" r ON r."RecordId" = ur."Role" ` ~
        `WHERE ur."User" = $1::uuid AND ur."RecordId" <> ` ~ nonzero ~ ` AND r."RecordId" <> ` ~ nonzero, params);
    Z8LoadedPrivileges result; Z8Access defaults;
    foreach (row; roles.rows) {
        result.roleIds ~= z8_guid_literal(row[0].text);
        result.roleNames ~= row[7].isNull ? ""w : row[7].text.to!wstring;
        defaults = defaults.orAccess(Z8Access(permission(row[1]), permission(row[2]), permission(row[3]), permission(row[4]), permission(row[5]), permission(row[6])));
    }
    result.privileges = new Z8Privileges(defaults);
    auto tables = db.execute(`SELECT a."Table"::text, MAX(COALESCE(a."Read",0)), MAX(COALESCE(a."Write",0)), ` ~
        `MAX(COALESCE(a."Create",0)), MAX(COALESCE(a."Copy",0)), MAX(COALESCE(a."Destroy",0)) FROM ` ~
        ns ~ `."SystemRoleTableAccess" a JOIN ` ~ ns ~ `."SystemUserRoles" ur ON ur."Role" = a."Role" JOIN ` ~
        ns ~ `."SystemRoles" r ON r."RecordId" = ur."Role" ` ~
        `WHERE ur."User" = $1::uuid AND ur."RecordId" <> ` ~ nonzero ~ ` AND r."RecordId" <> ` ~ nonzero ~ ` AND a."RecordId" <> ` ~ nonzero ~ ` GROUP BY a."Table"`, params);
    foreach (row; tables.rows) {
        auto access = Z8Access(permission(row[1]), permission(row[2]), permission(row[3]), permission(row[4]), permission(row[5]), false);
        if (!sameTablePermissions(access, defaults)) result.privileges.setTableAccess(z8_guid_literal(row[0].text), access);
    }
    auto fields = db.execute(`SELECT a."Field"::text, f."Table"::text, MAX(COALESCE(a."Read",0)), MAX(COALESCE(a."Write",0)) FROM ` ~
        ns ~ `."SystemRoleFieldAccess" a JOIN ` ~ ns ~ `."SystemUserRoles" ur ON ur."Role" = a."Role" JOIN ` ~
        ns ~ `."SystemRoles" r ON r."RecordId" = ur."Role" JOIN ` ~
        ns ~ `."SystemFields" f ON f."RecordId" = a."Field" ` ~
        `WHERE ur."User" = $1::uuid AND ur."RecordId" <> ` ~ nonzero ~ ` AND r."RecordId" <> ` ~ nonzero ~ ` AND a."RecordId" <> ` ~ nonzero ~
        ` AND f."RecordId" <> ` ~ nonzero ~ ` GROUP BY a."Field", f."Table"`, params);
    foreach (row; fields.rows) {
        auto tableAccess = result.privileges.getTableAccess(z8_guid_literal(row[1].text));
        auto read = permission(row[2]), write = permission(row[3]);
        if (tableAccess.read != read || tableAccess.write != write)
            result.privileges.setFieldAccess(z8_guid_literal(row[0].text), Z8Access(read, write, false, false, false, false));
    }
    auto requests = db.execute(`SELECT a."Request"::text, MAX(COALESCE(a."Execute",0)) FROM ` ~
        ns ~ `."SystemRoleRequestAccess" a JOIN ` ~ ns ~ `."SystemUserRoles" ur ON ur."Role" = a."Role" JOIN ` ~
        ns ~ `."SystemRoles" r ON r."RecordId" = ur."Role" ` ~
        `WHERE ur."User" = $1::uuid AND ur."RecordId" <> ` ~ nonzero ~ ` AND r."RecordId" <> ` ~ nonzero ~ ` AND a."RecordId" <> ` ~ nonzero ~ ` GROUP BY a."Request"`, params);
    foreach (row; requests.rows) {
        auto execute = permission(row[1]);
        if (execute != defaults.execute) result.privileges.setRequestAccess(z8_guid_literal(row[0].text), Z8Access(false, false, false, false, false, execute));
    }
    return result;
}
// Replace the user's snapshot only after every database query succeeds.
void z8_postgres_refresh_user_privileges(Z8PostgresConnection db, wstring schema, Z8UserData user) {
    if (user is null) throw new Z8PostgresException("user is required");
    auto loaded = z8_postgres_load_privileges(db, schema, user.id);
    user.roles = loaded.roleIds; user.roleNames = loaded.roleNames; user.privileges = loaded.privileges;
}
// Resolve the standard Users record together with its current role grants.
// A host can supply its own resolver for project-specific user parameters.
Z8UserEntry[] z8_postgres_load_user_entries(Z8PostgresConnection db, wstring schema, Z8Guid id, Z8RuntimeRegistry registry = null) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (id is null) throw new Z8PostgresException("user GUID is required");
    if (registry is null) registry = z8_runtime_get_registry();
    auto ns = quoteIdentifier(schema);
    auto rows = db.execute(`SELECT e."RecordId"::text, e."Class" FROM ` ~ ns ~ `."SystemUserEntries" ue JOIN ` ~
        ns ~ `."SystemEntries" e ON e."RecordId" = ue."EntryId" WHERE ue."UserId" = $1::uuid ` ~
        `AND ue."RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid ` ~
        `AND e."RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid ORDER BY ue."Position" ASC`,
        [Z8PostgresParameter.value(z8_guid_to_string(id).to!string)]);
    auto descriptors = registry is null ? null : registry.entries();
    Z8UserEntry[] result;
    foreach (row; rows.rows) {
        auto classId = row[1].isNull ? ""w : row[1].text.to!wstring;
        auto title = "<entry removed>"w;
        foreach (entry; descriptors) if (entry.classId == classId) { title = entry.displayName; break; }
        result ~= Z8UserEntry(z8_guid_literal(row[0].text), classId, title);
    }
    if (id == z8_guid_create(2)) {
        enum systemTools = "org.zenframework.z8.server.base.table.system.SystemTools"w;
        auto systemId = z8_guid_create_name(systemTools);
        bool present;
        foreach (entry; result) if (entry.id == systemId) { present = true; break; }
        if (!present) result ~= Z8UserEntry(systemId, systemTools, z8_string_new("$SystemTools.title$"w));
    }
    return result;
}
Z8UserData z8_postgres_read_user(Z8PostgresConnection db, wstring schema, Z8Guid id, Z8RuntimeRegistry registry = null) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (id is null || id == z8_guid_zero()) return null;
    auto rows = db.execute(`SELECT "Name", "First Name", "Middle Name", "Last Name", "Phone", "Email", ` ~
        `convert_from("Description", 'UTF8'), "Change Password", convert_from("Settings", 'UTF8') FROM ` ~ quoteIdentifier(schema) ~ `."SystemUsers" WHERE "RecordId" = $1::uuid`,
        [Z8PostgresParameter.value(z8_guid_to_string(id).to!string)]);
    if (!rows.rows.length) return null;
    if (rows.rows.length != 1) throw new Z8PostgresException("multiple users with the same id");
    auto user = new Z8UserData(); user.id = id;
    auto row = rows.rows[0];
    wstring text(size_t index) { return row[index].isNull ? ""w : row[index].text.to!wstring; }
    user.login = text(0); user.firstName = text(1); user.middleName = text(2); user.lastName = text(3);
    user.phone = text(4); user.email = text(5); user.description = text(6);
    user.changePassword = !row[7].isNull && row[7].text.to!int != 0; user.settings = text(8);
    user.builtinAdministrator = id == z8_guid_create(2); user.builtinSystem = id == z8_guid_create(1);
    z8_postgres_refresh_user_privileges(db, schema, user);
    user.entries = z8_postgres_load_user_entries(db, schema, id, registry);
    user.administrator = user.builtinAdministrator;
    foreach (role; user.roles) if (role == z8_guid_literal("DC08CA72-C668-412F-91B7-022F1C82AC09")) user.administrator = true;
    return user;
}
