module z8.database.authentication;

import std.conv : to;
import z8.runtime;
import z8.database.plan : quoteIdentifier;
import z8.database.postgres;
import z8.database.connection : Z8PostgresDatabase;
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
    private IZ8UserChangeNotifier userNotifier;
    private IZ8RoleChangeNotifier roleNotifier;
    private void notifyAuthenticationChange(Z8Guid id) {
        // Users.notifyUserChange excludes built-in system and administrator users.
        if (userNotifier !is null && id != z8_guid_create(1) && id != z8_guid_create(2))
            userNotifier.userChanged(id, schema);
    }
    this(Z8PostgresConnection db, wstring schema, Z8RuntimeRegistry registry = null,
         Z8PostgresAuthenticationConfig config = Z8PostgresAuthenticationConfig.init,
         IZ8UserChangeNotifier userNotifier = null, IZ8RoleChangeNotifier roleNotifier = null) {
        if (db is null || db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (config.maxFailedAttempts < 0 || config.banMilliseconds < 0) throw new Z8PostgresException("invalid authentication configuration");
        this.db = db; this.schema = schema.idup; this.registry = registry; this.config = config;
        this.userNotifier = userNotifier; this.roleNotifier = roleNotifier;
        ns = quoteIdentifier(schema);
    }
    Z8UserData authenticate(wstring login, wstring password, Z8Date now = null, wstring address = null) {
        if (login is null || password is null) return null;
        return authenticateIdentity(null, login, password, false, now, address, false, null);
    }
    // Only a host that has already authenticated the caller may use this API.
    // Existing users are resolved by ID when supplied, otherwise by login.
    Z8UserData authenticateTrusted(Z8Guid userId, wstring login = null, Z8Date now = null, wstring address = null,
                                   bool createIfMissing = false, wstring oneTimePassword = null) {
        if (userId !is null && userId == z8_guid_zero()) return null;
        if (userId is null && (login is null || !login.length)) return null;
        if (createIfMissing && (oneTimePassword is null || !oneTimePassword.length))
            throw new Z8PostgresException("trusted user creation requires a one-time password");
        return authenticateIdentity(userId, login, null, true, now, address, createIfMissing, oneTimePassword);
    }
    private Z8UserData authenticateIdentity(Z8Guid userId, wstring login, wstring password, bool trusted, Z8Date now, wstring address,
                                            bool createIfMissing, wstring oneTimePassword) {
        if (db.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (db.inTransaction()) throw new Z8PostgresException("authentication requires its own transaction");
        if (now is null) now = z8_date_now();
        auto ticks = z8_date_ticks(now);
        Z8Object customUser;
        bool needsHookContext;
        if (registry !is null) foreach (entry; registry.named()) if (entry.name == "User"w) {
            customUser = z8_user_wrap_with_registry(new Z8UserData(), registry);
            break;
        }
        needsHookContext = customUser !is null || createIfMissing;
        if (registry !is null && !needsHookContext) {
            foreach (entry; registry.named()) if (entry.name == "SystemUsers"w) { needsHookContext = true; break; }
            if (!needsHookContext) foreach (entry; registry.tables()) if (entry.name == "SystemUsers"w) { needsHookContext = true; break; }
        }
        auto previousRequest = z8_application_request();
        auto previousConnection = z8_connection_current_backend();
        scope(exit) if (needsHookContext) {
            z8_application_set_request(previousRequest);
            z8_connection_set_current(previousConnection);
        }
        if (needsHookContext) {
            auto system = z8_postgres_read_user(db, schema, z8_guid_create(1), registry, null, false);
            if (system is null) throw new Z8PostgresException("system user is missing");
            auto request = new Z8ApplicationRequest();
            request.session = new Z8ApplicationSession("system"w, system, system);
            request.monitor = new Z8RequestMonitor();
            request.userChangeNotifier = userNotifier; request.roleChangeNotifier = roleNotifier;
            request.parameters.z8_add("login"w, login); request.parameters.z8_add("schema"w, schema);
            if (address !is null) request.parameters.z8_add("address"w, address);
            z8_application_set_request(request);
            z8_connection_set_current(new Z8PostgresDatabase(db, schema, registry));
            if (customUser !is null) {
                try { z8_user_before_load(customUser, login); }
                catch (Throwable failure) { request.monitor.log(Z8MonitorLevel.error, failure.msg.to!wstring); }
            }
        }
        db.beginTransaction();
        try {
            if (createIfMissing && userId is null) db.execute("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('z8.trusted.' || $1::text || '.' || lower($2::text), 0))",
                [Z8PostgresParameter.value(schema.to!string), Z8PostgresParameter.value(login.to!string)]);
            auto lookup = userId is null ? `lower("Name") = lower($1::text)` : `"RecordId" = $1::uuid`;
            auto lookupValue = userId is null ? login.to!string : z8_guid_to_string(userId).to!string;
            auto selectUser = "SELECT \"RecordId\"::text, \"Password\", COALESCE(\"Banned\", 0)::text, " ~
                `COALESCE("Banned Until", 0)::text, COALESCE("Failed Auth Count", 0)::text FROM ` ~ ns ~
                `."SystemUsers" WHERE `;
            auto suffix = ` AND "RecordId" <> '00000000-0000-0000-0000-000000000000'::uuid FOR UPDATE`;
            auto rows = db.execute(selectUser ~ lookup ~ suffix, [Z8PostgresParameter.value(lookupValue)]);
            bool created;
            if (!rows.rows.length && createIfMissing) {
                if (userId !is null) throw new Z8PostgresException("cannot provision a missing user by explicit ID");
                auto users = registry is null ? null : registry.newNamedByName("SystemUsers"w);
                if (users is null && registry !is null) users = registry.newTableByName("SystemUsers"w);
                if (users is null) users = z8_native_new("org.zenframework.z8.server.base.table.system.Users"w);
                users.z8_ensure();
                if (!z8_native_is_instance("org.zenframework.z8.server.base.table.system.Users"w, users))
                    throw new Z8PostgresException("SystemUsers is not a Users table");
                Z8Object nameField, passwordField;
                foreach (field; z8_query_declared_fields(users, true)) {
                    if (field.z8_index() == "name"w) nameField = field;
                    else if (field.z8_index() == "password"w) passwordField = field;
                }
                if (nameField is null || passwordField is null) throw new Z8PostgresException("SystemUsers fields are missing");
                z8_field_set(nameField, z8_primary_box(login));
                z8_field_set(passwordField, z8_primary_box(z8_native_call!wstring("org.zenframework.z8.server.crypto.Digest.m_md5"w, oneTimePassword)));
                auto request = z8_application_request();
                Z8Guid newId;
                {
                    request.parameters.z8_add("plainPassword"w, oneTimePassword);
                    scope(exit) request.parameters.z8_remove("plainPassword"w);
                    newId = z8_native_call!Z8Guid("org.zenframework.z8.server.base.query.Query.m_create"w, users);
                }
                if (newId is null || newId == z8_guid_zero()) throw new Z8PostgresException("trusted user creation returned an invalid ID");
                rows = db.execute(selectUser ~ `"RecordId" = $1::uuid` ~ suffix, [Z8PostgresParameter.value(z8_guid_to_string(newId).to!string)]);
                if (!rows.rows.length) throw new Z8PostgresException("created user was not found");
                created = true;
                if (customUser !is null) {
                    try { z8_user_before_load(customUser, login); }
                    catch (Throwable failure) { request.monitor.log(Z8MonitorLevel.error, failure.msg.to!wstring); }
                }
            }
            if (!rows.rows.length) { db.commit(); return null; }
            if (rows.rows.length != 1) throw new Z8PostgresException("duplicate case-insensitive user login");
            auto row = rows.rows[0];
            auto id = z8_guid_literal(row[0].text);
            auto key = Z8PostgresParameter.value(row[0].text);
            auto failures = row[4].text.to!long;
            auto loginData = new Z8LoginParametersData(id, login, address, schema);
            auto user = z8_postgres_read_user(db, schema, id, registry, loginData);
            if (user is null || row[2].text != "0" || row[3].text.to!long > ticks) {
                if (created) db.rollback(); else db.commit(); return null;
            }
            bool accepted;
            if (customUser !is null) {
                z8_user_attach(customUser, user);
                try { accepted = z8_user_authenticate(customUser, password); }
                catch (Throwable failure) { z8_application_request().monitor.log(Z8MonitorLevel.error, failure.msg.to!wstring); }
            }
            if (trusted) accepted = true;
            auto candidate = password;
            if (!accepted && !config.clientHashesPasswords)
                candidate = z8_native_call!wstring("org.zenframework.z8.server.crypto.Digest.m_md5"w, password);
            if (!accepted && (row[1].isNull || !samePassword(candidate, row[1].text.to!wstring))) {
                if (config.maxFailedAttempts > 0) {
                    if (failures >= config.maxFailedAttempts - 1) {
                        if (ticks > long.max - config.banMilliseconds) throw new Z8PostgresException("authentication ban time overflow");
                        db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = 0, "Banned Until" = $2::bigint WHERE "RecordId" = $1::uuid`,
                            [key, Z8PostgresParameter.value((ticks + config.banMilliseconds).to!string)]);
                    } else db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = $2::bigint WHERE "RecordId" = $1::uuid`,
                        [key, Z8PostgresParameter.value((failures + 1).to!string)]);
                }
                db.commit();
                if (config.maxFailedAttempts > 0) notifyAuthenticationChange(id);
                return null;
            }
            if (failures != 0) db.execute("UPDATE " ~ ns ~ `."SystemUsers" SET "Failed Auth Count" = 0 WHERE "RecordId" = $1::uuid`, [key]);
            db.commit();
            if (failures != 0) notifyAuthenticationChange(id);
            if (customUser !is null) {
                z8_user_attach(customUser, user);
                try { z8_user_on_load(customUser); }
                catch (Throwable failure) { z8_application_request().monitor.log(Z8MonitorLevel.error, failure.msg.to!wstring); }
            }
            return user;
        } catch (Throwable failure) {
            if (db.inTransaction()) db.rollback();
            throw failure;
        }
    }
}
