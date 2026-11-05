module z8.database.privileges;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;

struct Z8LoadedPrivileges {
    Z8Privileges privileges;
    Z8Guid[] roleIds;
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
    auto roles = db.execute(`SELECT DISTINCT r."RecordId"::text, r."Read", r."Write", r."Create", r."Copy", r."Destroy", r."Execute" FROM ` ~
        ns ~ `."SystemUserRoles" ur JOIN ` ~ ns ~ `."SystemRoles" r ON r."RecordId" = ur."Role" ` ~
        `WHERE ur."User" = $1::uuid AND ur."RecordId" <> ` ~ nonzero ~ ` AND r."RecordId" <> ` ~ nonzero, params);
    Z8LoadedPrivileges result; Z8Access defaults;
    foreach (row; roles.rows) {
        result.roleIds ~= z8_guid_literal(row[0].text);
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
