module z8.database.metadata;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;

private Z8PostgresParameter textParameter(wstring value) {
    return value is null ? Z8PostgresParameter.nullValue() : Z8PostgresParameter.value(value.to!string);
}
private Z8PostgresParameter guidParameter(Z8Guid value) { return Z8PostgresParameter.value(z8_guid_to_string(value).to!string); }

// Synchronize additions and metadata updates from the host registry. Existing
// role permissions are preserved; removal of obsolete entries is not performed.
void z8_postgres_sync_registry(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry) {
    if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
    if (registry is null) throw new Z8PostgresException("application registry is required");
    auto ns = quoteIdentifier(schema);
    auto ownsTransaction = !db.inTransaction();
    if (ownsTransaction) db.beginTransaction();
    try {
        db.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext($1)::bigint)",
            [Z8PostgresParameter.value("z8.registry." ~ schema.to!string)]);
        auto roles = db.execute("SELECT \"RecordId\"::text, COALESCE(\"Read\",0)::text, COALESCE(\"Write\",0)::text, " ~
            `COALESCE("Create",0)::text, COALESCE("Copy",0)::text, COALESCE("Destroy",0)::text, COALESCE("Execute",0)::text FROM ` ~
            ns ~ `."SystemRoles" WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid`);
        foreach (table; registry.tables()) {
            auto tableId = guidParameter(table.key);
            auto params = [tableId, textParameter(table.name), textParameter(table.description), textParameter(table.classId), textParameter(table.displayName)];
            auto inserted = db.execute("INSERT INTO " ~ ns ~ `."SystemTables" ("RecordId", "Name", "Description", "Class", "Display Name", "Lock") ` ~
                `VALUES ($1::uuid, $2::text, convert_to($3::text,'UTF8'), $4::text, $5::text, 1) ON CONFLICT ("RecordId") DO NOTHING RETURNING "RecordId"`, params);
            if (inserted.rows.length) {
                foreach (role; roles.rows) {
                    auto roleParams = [guidParameter(z8_guid_create_random()), Z8PostgresParameter.value(role[0].text), tableId,
                        Z8PostgresParameter.value(role[1].text), Z8PostgresParameter.value(role[2].text), Z8PostgresParameter.value(role[3].text),
                        Z8PostgresParameter.value(role[4].text), Z8PostgresParameter.value(role[5].text)];
                    db.execute("INSERT INTO " ~ ns ~ `."SystemRoleTableAccess" ("RecordId", "Role", "Table", "Read", "Write", "Create", "Copy", "Destroy") ` ~
                        `VALUES ($1::uuid, $2::uuid, $3::uuid, $4::smallint, $5::smallint, $6::smallint, $7::smallint, $8::smallint)`, roleParams);
                }
            } else {
                db.execute("UPDATE " ~ ns ~ `."SystemTables" SET "Name" = $2::text, "Description" = convert_to($3::text,'UTF8'), "Class" = $4::text, "Display Name" = $5::text, "Lock" = 1 WHERE "RecordId" = $1::uuid`, params);
            }
            foreach (field; table.fields) {
                auto fieldId = guidParameter(field.key);
                auto fieldParams = [fieldId, tableId, textParameter(field.name), textParameter(field.displayName), textParameter(field.description),
                    textParameter(field.type), Z8PostgresParameter.value(field.ordinal.to!string)];
                auto created = db.execute("INSERT INTO " ~ ns ~ `."SystemFields" ("RecordId", "Table", "Name", "Display Name", "Description", "Type", "Position", "Lock") ` ~
                    `VALUES ($1::uuid, $2::uuid, $3::text, $4::text, convert_to($5::text,'UTF8'), $6::text, $7::bigint, 1) ON CONFLICT ("RecordId") DO NOTHING RETURNING "RecordId"`, fieldParams);
                if (created.rows.length) {
                    foreach (role; roles.rows) {
                        auto roleParams = [guidParameter(z8_guid_create_random()), Z8PostgresParameter.value(role[0].text), fieldId,
                            Z8PostgresParameter.value(role[1].text), Z8PostgresParameter.value(role[2].text)];
                        db.execute("INSERT INTO " ~ ns ~ `."SystemRoleFieldAccess" ("RecordId", "Role", "Field", "Read", "Write") ` ~
                            `VALUES ($1::uuid, $2::uuid, $3::uuid, $4::smallint, $5::smallint)`, roleParams);
                    }
                } else {
                    auto updated = db.execute("UPDATE " ~ ns ~ `."SystemFields" SET "Name" = $3::text, "Display Name" = $4::text, "Description" = convert_to($5::text,'UTF8'), "Type" = $6::text, "Position" = $7::bigint, "Lock" = 1 WHERE "RecordId" = $1::uuid AND "Table" = $2::uuid`, fieldParams);
                    if (updated.affectedRows != 1) throw new Z8PostgresException("registered field key belongs to another table");
                }
            }
        }
        foreach (request; registry.requests()) {
            auto requestId = guidParameter(request.key);
            auto params = [requestId, textParameter(request.displayName), textParameter(request.classId)];
            auto inserted = db.execute("INSERT INTO " ~ ns ~ `."SystemRequests" ("RecordId", "Name", "Class", "Lock") ` ~
                `VALUES ($1::uuid, $2::text, $3::text, 1) ON CONFLICT ("RecordId") DO NOTHING RETURNING "RecordId"`, params);
            if (inserted.rows.length) {
                foreach (role; roles.rows) {
                    auto roleParams = [guidParameter(z8_guid_create_random()), Z8PostgresParameter.value(role[0].text), requestId, Z8PostgresParameter.value(role[6].text)];
                    db.execute("INSERT INTO " ~ ns ~ `."SystemRoleRequestAccess" ("RecordId", "Role", "Request", "Execute") ` ~
                        `VALUES ($1::uuid, $2::uuid, $3::uuid, $4::smallint)`, roleParams);
                }
            } else {
                db.execute("UPDATE " ~ ns ~ `."SystemRequests" SET "Name" = $2::text, "Class" = $3::text, "Lock" = 1 WHERE "RecordId" = $1::uuid`, params);
            }
        }
        // EntriesGenerator preserves user-to-entry assignments while refreshing
        // metadata; obsolete entries are deliberately not removed here.
        foreach (entry; registry.entries()) {
            auto params = [guidParameter(entry.key), textParameter(entry.displayName), textParameter(entry.classId)];
            db.execute("INSERT INTO " ~ ns ~ `."SystemEntries" ("RecordId", "Name", "Class", "Lock") ` ~
                `VALUES ($1::uuid, $2::text, $3::text, 3) ON CONFLICT ("RecordId") DO UPDATE ` ~
                `SET "Name" = EXCLUDED."Name", "Class" = EXCLUDED."Class", "Lock" = 3`, params);
        }
        // Jobs.java is optional until its framework table is included in the
        // bootstrap. Preserve obsolete rows until scheduled jobs and logs can
        // be migrated together, rather than orphaning user configuration.
        auto jobTables = db.execute("SELECT pg_catalog.to_regclass($1::text) IS NOT NULL, pg_catalog.to_regclass($2::text) IS NOT NULL",
            [Z8PostgresParameter.value(ns ~ `."SystemJobs"`), Z8PostgresParameter.value(ns ~ `."SystemScheduledJobs"`)]);
        if (jobTables.rows[0][0].text == "t") foreach (job; registry.jobs()) {
            auto params = [guidParameter(job.key), textParameter(job.displayName), textParameter(job.classId)];
            db.execute("INSERT INTO " ~ ns ~ `."SystemJobs" ("RecordId", "Name", "Class", "Lock") ` ~
                `VALUES ($1::uuid, $2::text, $3::text, 3) ON CONFLICT ("RecordId") DO UPDATE ` ~
                `SET "Name" = EXCLUDED."Name", "Class" = EXCLUDED."Class", "Lock" = 3`, params);
            if (job.hasSchedule && jobTables.rows[0][1].text == "t") {
                auto schedule = [guidParameter(z8_guid_create_random()), guidParameter(job.key), textParameter(job.cron),
                    Z8PostgresParameter.value(job.cron.length ? "1" : "0")];
                db.execute("INSERT INTO " ~ ns ~ `."SystemScheduledJobs" ("RecordId", "Job", "Cron", "Active") ` ~
                    `SELECT $1::uuid, $2::uuid, $3::text, $4::smallint WHERE NOT EXISTS ` ~
                    `(SELECT 1 FROM ` ~ ns ~ `."SystemScheduledJobs" WHERE "Job" = $2::uuid)`, schedule);
            }
        }
        if (ownsTransaction) db.commit();
    } catch (Throwable failure) {
        if (ownsTransaction) { try { db.rollback(); } catch (Throwable ignored) { } }
        throw failure;
    }
}
