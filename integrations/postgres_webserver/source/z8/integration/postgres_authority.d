module z8.integration.postgres_authority;

import z8.runtime;
import z8.database.authentication;
import z8.database.postgres;
import z8.database.privileges : z8_postgres_read_user;
import z8.webserver.civetweb : IZ8HttpAuthority, Z8HttpRequest;

version (Windows) {
    pragma(lib, "bcrypt.lib");
    private extern(Windows) int BCryptGenRandom(void* algorithm, ubyte* buffer, uint length, uint flags);
}

// Session IDs must come directly from an operating-system CSPRNG; the D
// standard library's randomUUID explicitly does not guarantee this property.
private wstring newSessionToken() {
    ubyte[32] bytes;
    version (Windows) {
        if (BCryptGenRandom(null, bytes.ptr, cast(uint)bytes.length, 2) != 0)
            throw new Z8PostgresException("cannot generate session token");
    } else version (Posix) {
        import std.stdio : File;
        auto file = File("/dev/urandom", "rb");
        size_t offset;
        while (offset < bytes.length) {
            auto read = file.rawRead(bytes[offset .. $]);
            if (!read.length) throw new Z8PostgresException("cannot generate session token");
            offset += read.length;
        }
    } else static assert(0, "secure session token generation is unavailable on this platform");
    enum wstring digits = "0123456789abcdef"w;
    wchar[64] token;
    foreach (i, b; bytes) { token[2 * i] = digits[b >> 4]; token[2 * i + 1] = digits[b & 15]; }
    return token[].idup;
}

// Single-schema authority. Each login uses an independent connection; the
// synchronized session manager owns and invalidates the issued session IDs.
class Z8PostgresHttpAuthority : IZ8HttpAuthority, IZ8UserChangeNotifier, IZ8RoleChangeNotifier {
    private Z8PostgresConnection source;
    private wstring schema, serverId;
    private Z8RuntimeRegistry registry;
    private Z8PostgresAuthenticationConfig config;
    private Z8SessionManager sessions;

    this(Z8PostgresConnection source, wstring schema, Z8RuntimeRegistry registry,
         Z8PostgresAuthenticationConfig config = Z8PostgresAuthenticationConfig.init,
         Z8SessionManager sessions = null, wstring serverId = null) {
        if (source is null || source.isClosed()) throw new Z8PostgresException("PostgreSQL connection is closed");
        if (schema is null || !schema.length || registry is null) throw new Z8PostgresException("authority schema and registry are required");
        new Z8PostgresAuthenticator(source, schema, registry, config);
        this.source = source; this.schema = schema.idup; this.registry = registry; this.config = config;
        this.sessions = sessions is null ? new Z8SessionManager() : sessions; this.serverId = serverId;
    }
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring id, wstring server) {
        if (serverId !is null && server !is null && server.length && server != serverId) return null;
        sessions.check(z8_date_ticks(z8_date_now()));
        return sessions.getSessionInSchema(id, schema);
    }
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password) {
        sessions.check(z8_date_ticks(z8_date_now()));
        auto connection = source.openSibling();
        scope(exit) connection.close();
        auto user = new Z8PostgresAuthenticator(connection, schema, registry, config, this, this).authenticate(login, password);
        if (user is null) return null;
        auto system = z8_postgres_read_user(connection, schema, z8_guid_create(1), registry);
        if (system is null) throw new Z8PostgresException("system user is missing");
        return sessions.create(newSessionToken(), user, system, schema);
    }
    void userChanged(Z8Guid id, wstring schema) { sessions.dropUserSessions(id, schema); }
    void roleChanged(Z8Guid id, wstring schema) { sessions.dropRoleSessions(id, schema); }
    void logout(wstring id) {
        sessions.dropSessionInSchema(id, schema);
    }
}
