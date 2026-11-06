module z8.integration.protobuf_postgres_authority;

import std.conv : to;
import z8.runtime : Z8ApplicationSession, Z8Guid;
import z8.authority.messages : Z8AuthorityLogin, Z8AuthorityAuthorize;
import z8.authority.service : IZ8AuthorityEndpoint;
import z8.protobuf.wire : Z8ProtobufException;
import z8.integration.postgres_authority : Z8PostgresHttpAuthority;
import z8.webserver.civetweb : Z8HttpRequest;

// Bridges the single-schema PostgreSQL authority to the transport-neutral
// protobuf service. Incoming notifications are never forwarded back to peers.
class Z8ProtobufPostgresAuthority : IZ8AuthorityEndpoint {
    private Z8PostgresHttpAuthority authority;
    this(Z8PostgresHttpAuthority authority) {
        if (authority is null) throw new Z8ProtobufException("PostgreSQL authority is required");
        this.authority = authority;
    }
    Z8ApplicationSession login(Z8AuthorityLogin request) {
        if (request.schema != authority.databaseSchema()) return null;
        auto context = new Z8HttpRequest();
        if (request.address !is null) context.remoteAddress = request.address.to!string;
        return authority.login(context, request.login, request.password);
    }
    Z8ApplicationSession authorize(Z8AuthorityAuthorize request) {
        if (request.schema != authority.databaseSchema()) return null;
        return authority.authorize(null, request.sessionId, request.serverId);
    }
    void userChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.applyRemoteUserChange(id, schema);
    }
    void roleChanged(Z8Guid id, wstring schema) {
        if (schema != authority.databaseSchema()) throw new Z8ProtobufException("authority schema mismatch");
        authority.applyRemoteRoleChange(id, schema);
    }
}
