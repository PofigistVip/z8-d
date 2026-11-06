module z8.authority.service;

import z8.runtime : Z8ApplicationSession, Z8Guid;
import z8.authority.custom_primary;
import z8.authority.messages;
import z8.authority.notifications;
import z8.authority.session;
import z8.protobuf.wire : Z8ProtobufException;
import z8.authority.transport : Z8AuthorityMethod;

// Transport-neutral authority operations. Implementations must be thread-safe.
interface IZ8AuthorityEndpoint {
    Z8ApplicationSession login(Z8AuthorityLogin request);
    Z8ApplicationSession authorize(Z8AuthorityAuthorize request);
    void userChanged(Z8Guid id, wstring schema);
    void roleChanged(Z8Guid id, wstring schema);
}

// A transport authenticates the peer and maps its RPC methods to these calls.
// A null session is an ordinary denial; malformed messages throw.
class Z8ProtobufAuthorityService {
    private IZ8AuthorityEndpoint endpoint;
    private Z8CustomPrimaryRegistry custom;
    this(IZ8AuthorityEndpoint endpoint, Z8CustomPrimaryRegistry custom = null) {
        if (endpoint is null) throw new Z8ProtobufException("authority endpoint is required");
        this.endpoint = endpoint; this.custom = custom;
    }
    private ubyte[] reply(Z8ApplicationSession session, wstring schema) {
        Z8AuthoritySessionReply result;
        if (session is null) result.denied = true;
        else result.session = Z8SessionSnapshot(schema, session);
        return z8_encode_authority_reply(result, custom);
    }
    ubyte[] login(const(ubyte)[] payload) {
        auto request = z8_decode_authority_login(payload);
        return reply(endpoint.login(request), request.schema);
    }
    ubyte[] authorize(const(ubyte)[] payload) {
        auto request = z8_decode_authority_authorize(payload);
        auto session = endpoint.authorize(request);
        if (session !is null && session.id != request.sessionId) throw new Z8ProtobufException("authority returned a different session ID");
        return reply(session, request.schema);
    }
    ubyte[] userChanged(const(ubyte)[] payload) {
        auto value = z8_decode_authority_change(payload);
        if (value.id is null || value.schema is null || !value.schema.length) throw new Z8ProtobufException("notification requires an ID and schema");
        endpoint.userChanged(value.id, value.schema); return [];
    }
    ubyte[] roleChanged(const(ubyte)[] payload) {
        auto value = z8_decode_authority_change(payload);
        if (value.id is null || value.schema is null || !value.schema.length) throw new Z8ProtobufException("notification requires an ID and schema");
        endpoint.roleChanged(value.id, value.schema); return [];
    }
    ubyte[] dispatch(Z8AuthorityMethod method, const(ubyte)[] payload) {
        switch (method) {
            case Z8AuthorityMethod.login: return login(payload);
            case Z8AuthorityMethod.authorize: return authorize(payload);
            case Z8AuthorityMethod.userChanged: return userChanged(payload);
            case Z8AuthorityMethod.roleChanged: return roleChanged(payload);
            default: throw new Z8ProtobufException("unknown authority method");
        }
    }
}
