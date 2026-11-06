module z8.authority.client;

import z8.runtime : Z8ApplicationSession, Z8Guid, IZ8UserChangeNotifier, IZ8RoleChangeNotifier;
import z8.authority.custom_primary;
import z8.authority.messages;
import z8.authority.notifications;
import z8.authority.service : IZ8AuthorityEndpoint, IZ8AuthorityInvalidationSink;
import z8.authority.transport;
import z8.protobuf.wire;

class Z8ProtobufAuthorityClient : IZ8AuthorityEndpoint, IZ8AuthorityInvalidationSink, IZ8UserChangeNotifier, IZ8RoleChangeNotifier {
    private IZ8AuthorityRpcTransport transport;
    private Z8CustomPrimaryRegistry custom;
    this(IZ8AuthorityRpcTransport transport, Z8CustomPrimaryRegistry custom = null) {
        if (transport is null) throw new Z8ProtobufException("authority transport is required");
        this.transport = transport; this.custom = custom;
    }
    private Z8ApplicationSession sessionReply(ubyte[] payload, wstring schema, wstring expectedId = null) {
        auto reply = z8_decode_authority_reply(payload, custom);
        if (reply.denied) return null;
        if (reply.session.schema != schema) throw new Z8ProtobufException("authority returned a different schema");
        auto session = reply.session.session;
        if (expectedId !is null && session.id != expectedId) throw new Z8ProtobufException("authority returned a different session ID");
        return session;
    }
    Z8ApplicationSession login(Z8AuthorityLogin request) {
        return sessionReply(transport.call(Z8AuthorityMethod.login, z8_encode_authority_login(request)), request.schema);
    }
    Z8ApplicationSession authorize(Z8AuthorityAuthorize request) {
        return sessionReply(transport.call(Z8AuthorityMethod.authorize, z8_encode_authority_authorize(request)), request.schema, request.sessionId);
    }
    private void changed(Z8AuthorityMethod method, Z8Guid id, wstring schema) {
        if (id is null || schema is null || !schema.length) throw new Z8ProtobufException("notification requires an ID and schema");
        Z8AuthorityChange change; change.id = id; change.schema = schema;
        auto reply = transport.call(method, z8_encode_authority_change(change));
        if (reply.length > 1024 * 1024) throw new Z8ProtobufException("authority response exceeds size limit");
        // Empty messages may carry unknown fields and must still be well formed.
        auto reader = Z8ProtobufReader(reply);
        while (!reader.empty()) { uint field, wire; reader.tag(field, wire); reader.skip(field, wire); }
    }
    void userChanged(Z8Guid id, wstring schema) { changed(Z8AuthorityMethod.userChanged, id, schema); }
    void roleChanged(Z8Guid id, wstring schema) { changed(Z8AuthorityMethod.roleChanged, id, schema); }
    void applyUserChanged(Z8Guid id, wstring schema) { changed(Z8AuthorityMethod.applyUserChanged, id, schema); }
    void applyRoleChanged(Z8Guid id, wstring schema) { changed(Z8AuthorityMethod.applyRoleChanged, id, schema); }
}
// Attach this to a broadcasting authority when delivering to another peer.
class Z8ProtobufAuthorityPeerNotifier : IZ8UserChangeNotifier, IZ8RoleChangeNotifier {
    private Z8ProtobufAuthorityClient peer;
    this(Z8ProtobufAuthorityClient peer) {
        if (peer is null) throw new Z8ProtobufException("authority peer is required");
        this.peer = peer;
    }
    void userChanged(Z8Guid id, wstring schema) { peer.applyUserChanged(id, schema); }
    void roleChanged(Z8Guid id, wstring schema) { peer.applyRoleChanged(id, schema); }
}
