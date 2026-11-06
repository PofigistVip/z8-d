module z8.database.authentication;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;
import z8.database.privileges : z8_postgres_read_user;

// Authentication settings corresponding to ServerConfig's password mode and
// failed-attempt ban. A zero attempt limit disables temporary bans.
struct Z8PostgresAuthenticationConfig {
    bool clientHashesPasswords = true;
    int maxFailedAttempts;
    long banMilliseconds;
}
private bool samePassword(wstring left, wstring right) {
    size_t differences = left.length ^ right.length;
    auto length = left.length > right.length ? left.length : right.length;
    foreach (i; 0 .. length) {
        auto a = i < left.length ? left[i] : 0;
        auto b = i < right.length ? right[i] : 0;
        differences |= cast(size_t)(a ^ b);
    }
    return differences == 0;
}

// Host-facing credential check for the standard SystemUsers table. Null means
// access denied; callers must not distinguish unknown, banned and bad-password
// users in their response. Trusted login and custom BL authentication hooks are
// intentionally separate from this password-based entry point.
class Z8PostgresAuthenticator {
    private Z8PostgresConnection db;
    private wstring schema;
    private string ns;
    private Z8RuntimeRegistry registry;
    private Z8PostgresAuthenticationConfig config;
    this(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry = null,
         Z8PostgresAuthenticationConfig config = Z8PostgresAuthenticationConfig.init) {
        if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (config.maxFailedAttempts < 0 || config.banMilliseconds < 0) throw new Z8PostgresException("invalid authentication configuration");
        this.db = db; this.schema = schema.idup; this.registry = registry; this.config = config;
        ns = quoteIdentifier(schema);
    }
    Z8UserData authenticate(wstring login, wstring password, Z8Date now = null) {
        if (db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (db.inTransaction()) throw new Z8PostgresException("authentication requires its own transaction");
        if (login is null || password is null) return null;
        if (now is null) now = z8_date_now();
        auto ticks = z8_date_ticks(now);
        auto candidate = config.clientHashesPasswords ? password :
            z8_native_call!wstring("org.zenframework.z8.server.crypto.Digest.m_md5"w, password);
        db.beginTransaction();
        try {
            auto rows = db.execute("SELECT \"RecordId\"::text, \"Password\", COALESCE(\"Banned\", 0)::text, " ~
                `COALESCE("Banned Until", 0)::text, COALESCE("Failed Auth Count", 0)::text FROM ` ~ ns ~
                `."SystemUsers" WHERE lower("Name") = lower($1::text) AND "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid FOR UPDATE`,
                [Z8PostgresParameter.value(login.to!string)]);
            if (!rows.rows.length) { db.commit(); return null; }
            if (rows.rows.length != 1) throw new Z8PostgresException("duplicate case-insensitive user login");
            auto row = rows.rows[0];
            if (row[2].text != "0" || row[3].text.to!long > ticks) { db.commit(); return null; }
            auto id = z8_guid_literal(row[0].text);
            auto key = Z8PostgresParameter.value(row[0].text);
            auto failures = row[4].text.to!long;
            if (row[1].isNull || !samePassword(candidate, row[1].text.to!wstring)) {
                if (config.maxFailedAttempts > 0) {
                    if (failures >= config.maxFailedAttempts - 1) {
                        if (ticks > long.max - config.banMilliseconds) throw new Z8PostgresException("authentication ban time overflow");
                        db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = 0, "Banned Until" = $2::bigint WHERE "RecordId" = $1::uuid`,
                            [key, Z8PostgresParameter.value((ticks + config.banMilliseconds).to!string)]);
                    } else db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = $2::bigint WHERE "RecordId" = $1::uuid`,
                        [key, Z8PostgresParameter.value((failures + 1).to!string)]);
                }
                db.commit(); return null;
            }
            if (failures != 0) db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = 0 WHERE "RecordId" = $1::uuid`, [key]);
            auto user = z8_postgres_read_user(db, schema, id, registry);
            db.commit();
            return user;
        } catch (Throwable failure) {
            if (db.inTransaction()) db.rollback();
            throw failure;
        }
    }
}
