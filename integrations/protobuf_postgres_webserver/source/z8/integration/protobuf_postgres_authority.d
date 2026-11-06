module z8.integration.protobuf_postgres_authority;

import std.conv : to;
import z8.runtime : Z8ApplicationSession, Z8Guid;
import z8.authority.messages : Z8AuthorityLogin, Z8AuthorityTrustedLogin, Z8AuthorityAuthorize, Z8AuthorityLogout;
import z8.authority.service : IZ8AuthorityEndpoint, IZ8AuthorityInvalidationSink, IZ8AuthorityLogout, IZ8AuthorityTrustedLogin;
import z8.protobuf.wire : Z8ProtobufException;
import z8.integration.postgres_authority : Z8PostgresHttpAuthority;
import z8.webserver.civetweb : Z8HttpRequest;

// Bridges the single-schema PostgreSQL authority to the transport-neutral
// protobuf service. Peer-application notifications are not rebroadcast.
class Z8ProtobufPostgresAuthority : IZ8AuthorityEndpoint, IZ8AuthorityInvalidationSink, IZ8AuthorityLogout, IZ8AuthorityTrustedLogin {
    private Z8PostgresHttpAuthority authority;
    private bool allowTrustedLogin;
    this(Z8PostgresHttpAuthority authority, bool allowTrustedLogin = false) {
        if (authority is null) throw new Z8ProtobufException("PostgreSQL authority is required");
        this.authority = authority; this.allowTrustedLogin = allowTrustedLogin;
    }
    Z8ApplicationSession login(Z8AuthorityLogin request) {
        if (request.schema != authority.databaseSchema()) return null;
        auto context = new Z8HttpRequest();
        if (request.address !is null) context.remoteAddress = request.address.to!string;
        return authority.login(context, request.login, request.password);
    }
    Z8ApplicationSession trustedLogin(Z8AuthorityTrustedLogin request) {
        if (!allowTrustedLogin) throw new Z8ProtobufException("trusted login is disabled");
        if (request.schema != authority.databaseSchema()) return null;
        return authority.trustedLogin(request.userId, request.login, request.address, request.createIfMissing);
    }
    Z8ApplicationSession authorize(Z8AuthorityAuthorize request) {
        if (request.schema != authority.databaseSchema()) return null;
        return authority.authorize(null, request.sessionId, request.serverId);
    }
    void logout(Z8AuthorityLogout request) {
        if (request.schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.logout(request.sessionId);
    }
    void userChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.userChanged(id, schema);
    }
    void roleChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.roleChanged(id, schema);
    }
    void applyUserChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.applyRemoteUserChange(id, schema);
    }
    void applyRoleChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.applyRemoteRoleChange(id, schema);
    }
}
