module z8.database.scheduler;

import std.conv : to;
import z8.runtime;
import z8.database.connection : Z8PostgresDatabase;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;
import z8.database.privileges : z8_postgres_read_user;

// A host calls runDue periodically, on a connection owned by the calling
// thread. Session-level advisory locks prevent two hosts running the same
// schedule concurrently. Results are returned even when a BL job fails.
struct Z8ScheduledRun {
    Z8Guid id;
    wstring classId;
    Z8Date started, finished;
    bool success;
    Z8MonitorEntry[] messages;
}

private bool z8_scheduler_running;

class Z8PostgresScheduler {
    private Z8PostgresConnection db;
    private wstring schema;
    private Z8RuntimeRegistry registry;
    private IZ8UserChangeNotifier userNotifier;
    private IZ8RoleChangeNotifier roleNotifier;
    private string ns;
    this(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry,
         IZ8UserChangeNotifier userNotifier = null, IZ8RoleChangeNotifier roleNotifier = null) {
        if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (registry is null) throw new Z8PostgresException("application registry is required");
        this.db = db; this.schema = schema.idup; this.registry = registry;
        this.userNotifier = userNotifier; this.roleNotifier = roleNotifier;
        ns = quoteIdentifier(schema);
    }
    private Z8PostgresParameter guidParameter(Z8Guid id) {
        return Z8PostgresParameter.value(z8_guid_to_string(z8_nonnull(id)).to!string);
    }
    private Z8Date nextDate(Z8Date date, wstring cron) {
        return z8_native_call!Z8Date("org.zenframework.z8.server.utils.Cron.m_nextDate"w, date, cron);
    }
    Z8ScheduledRun[] runDue(Z8Date now = null) {
        if (db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (db.inTransaction()) throw new Z8PostgresException("scheduler requires its own connection transaction");
        if (z8_scheduler_running) throw new Z8PostgresException("scheduler is already running on this thread");
        z8_scheduler_running = true;
        scope(exit) z8_scheduler_running = false;
        if (now is null) now = z8_date_now();
        auto ids = db.execute("SELECT \"RecordId\"::text FROM " ~ ns ~ `."SystemScheduledJobs" ` ~
            `WHERE "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid AND "Active" <> 0 AND "Cron" <> '' ORDER BY "RecordId"`);
        Z8ScheduledRun[] results;
        foreach (row; ids.rows) {
            auto id = z8_guid_literal(row[0].text);
            auto lockName = Z8PostgresParameter.value("z8.schedule." ~ schema.to!string ~ "." ~ row[0].text);
            auto locked = db.execute("SELECT pg_catalog.pg_try_advisory_lock(pg_catalog.hashtextextended($1::text, 0))", [lockName]);
            if (locked.rows[0][0].text != "t") continue;
            scope(exit) if (!db.isClosed()) db.execute("SELECT pg_catalog.pg_advisory_unlock(pg_catalog.hashtextextended($1::text, 0))", [lockName]);
            Z8ScheduledRun result;
            try {
                if (runOne(id, now, result)) results ~= result;
            } catch (Throwable failure) {
                if (db.isClosed() || db.inTransaction()) throw failure;
                result.id = id;
                result.messages = [Z8MonitorEntry(Z8MonitorLevel.error, failure.msg.to!wstring, null, z8_date_now())];
                results ~= result;
            }
        }
        return results;
    }
    private bool runOne(Z8Guid id, Z8Date now, out Z8ScheduledRun result) {
        wstring classId, cron;
        Z8Guid userId;
        bool errorsOnly;
        db.beginTransaction();
        try {
            auto rows = db.execute("SELECT j.\"Class\", s.\"User\"::text, s.\"Cron\", s.\"LastStart\"::text, " ~
                `s."Log errors only"::text FROM ` ~ ns ~ `."SystemScheduledJobs" s JOIN ` ~ ns ~
                `."SystemJobs" j ON j."RecordId" = s."Job" WHERE s."RecordId" = $1::uuid AND s."Active" <> 0 AND s."Cron" <> '' FOR UPDATE OF s`,
                [guidParameter(id)]);
            if (!rows.rows.length) { db.commit(); return false; }
            auto row = rows.rows[0];
            classId = row[0].text.to!wstring; userId = z8_guid_literal(row[1].text); cron = row[2].text.to!wstring;
            errorsOnly = row[4].text != "0";
            auto last = row[3].isNull ? z8_date_min : z8_date_from_ticks(row[3].text.to!long);
            if (z8_date_ticks(nextDate(last, cron)) >= z8_date_ticks(now)) { db.commit(); return false; }
            auto next = nextDate(now, cron);
            db.execute("UPDATE " ~ ns ~ `."SystemScheduledJobs" SET "LastStart" = $2::bigint, "NextStart" = $3::bigint WHERE "RecordId" = $1::uuid`,
                [guidParameter(id), Z8PostgresParameter.value(z8_date_ticks(now).to!string), Z8PostgresParameter.value(z8_date_ticks(next).to!string)]);
            db.commit();
        } catch (Throwable failure) {
            if (db.inTransaction()) db.rollback();
            throw failure;
        }
        auto monitor = new Z8RequestMonitor(classId);
        auto previousRequest = z8_application_request();
        auto previousConnection = z8_connection_current_backend();
        try {
            auto user = z8_postgres_read_user(db, schema, userId, registry);
            auto system = z8_postgres_read_user(db, schema, z8_guid_create(1), registry);
            if (user is null || system is null) throw new Z8PostgresException("scheduled job user does not exist");
            auto request = new Z8ApplicationRequest();
            request.session = new Z8ApplicationSession(""w, user, system); request.monitor = monitor;
            request.userChangeNotifier = userNotifier; request.roleChangeNotifier = roleNotifier;
            request.parameters.z8_add("request"w, classId); request.parameters.z8_add("scheduled"w, "true"w);
            z8_application_set_request(request);
            z8_connection_set_current(new Z8PostgresDatabase(db, schema, registry));
            z8_application_start_response(request, classId);
            z8_application_dispatch_registered_job(registry, classId);
            if (db.inTransaction()) throw new Z8PostgresException("scheduled job left a transaction open");
        } catch (Throwable failure) {
            if (db.inTransaction()) db.rollback();
            monitor.message(Z8MonitorLevel.error, failure.msg.to!wstring);
            monitor.log(Z8MonitorLevel.error, failure.msg.to!wstring);
        } finally {
            z8_application_set_request(previousRequest);
            z8_connection_set_current(previousConnection);
        }
        auto finished = z8_date_now();
        db.beginTransaction();
        try {
            db.execute("UPDATE " ~ ns ~ `."SystemScheduledJobs" SET "LastFinish" = $2::bigint WHERE "RecordId" = $1::uuid`,
                [guidParameter(id), Z8PostgresParameter.value(z8_date_ticks(finished).to!string)]);
            if (!errorsOnly || monitor.hasErrors()) db.execute("INSERT INTO " ~ ns ~
                `."SystemScheduledJobLogs" ("RecordId", "ScheduledJob", "Start", "Finish", "Errors") VALUES ($1::uuid, $2::uuid, $3::bigint, $4::bigint, $5::smallint)`,
                [guidParameter(z8_guid_create_random()), guidParameter(id), Z8PostgresParameter.value(z8_date_ticks(now).to!string),
                 Z8PostgresParameter.value(z8_date_ticks(finished).to!string), Z8PostgresParameter.value(monitor.hasErrors() ? "1" : "0")]);
            db.commit();
        } catch (Throwable failure) {
            if (db.inTransaction()) db.rollback();
            throw failure;
        }
        result = Z8ScheduledRun(id, classId, now, finished, !monitor.hasErrors(), monitor.messages());
        return true;
    }
}
