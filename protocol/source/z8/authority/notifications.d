module z8.authority.notifications;

import std.conv : to;
import z8.runtime : Z8Guid, Z8SessionManager, IZ8UserChangeNotifier, IZ8RoleChangeNotifier;
import z8.protobuf.wire;

// UserChanged and RoleChanged share a wire layout, but are separate message
// types in the schema and must be routed to the appropriate handler.
struct Z8AuthorityChange {
    Z8Guid id;
    wstring schema;
    ubyte[] unknownFields, unknownGuidFields;
}
private void parseGuid(ref Z8AuthorityChange result, const(ubyte)[] data) {
    if (result.id is null) result.id = new Z8Guid();
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 1) result.id.majorBits = reader.fixed64();
        else if (field == 2 && wire == 1) result.id.minorBits = reader.fixed64();
        else { reader.skip(field, wire); result.unknownGuidFields ~= data[start .. reader.position]; }
    }
}
Z8AuthorityChange z8_decode_authority_change(const(ubyte)[] data) {
    if (data.length > 1024 * 1024) throw new Z8ProtobufException("protobuf notification exceeds size limit");
    Z8AuthorityChange result; result.schema = ""w;
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) parseGuid(result, reader.bytes());
        else if (field == 2 && wire == 2) {
            auto bytes = reader.bytes();
            try { result.schema = (cast(const(char)[])bytes).to!wstring; }
            catch (Exception) { throw new Z8ProtobufException("invalid UTF-8 in protobuf schema"); }
        } else { reader.skip(field, wire); result.unknownFields ~= data[start .. reader.position]; }
    }
    return result;
}
ubyte[] z8_encode_authority_change(Z8AuthorityChange value) {
    ubyte[] output;
    if (value.id !is null) {
        ubyte[] id;
        if (value.id.majorBits) { z8_proto_tag(id, 1, 1); z8_proto_fixed64(id, value.id.majorBits); }
        if (value.id.minorBits) { z8_proto_tag(id, 2, 1); z8_proto_fixed64(id, value.id.minorBits); }
        id ~= value.unknownGuidFields;
        z8_proto_tag(output, 1, 2); z8_proto_bytes(output, id);
    }
    if (value.schema.length) {
        auto schema = value.schema.to!string;
        z8_proto_tag(output, 2, 2); z8_proto_bytes(output, cast(const(ubyte)[])schema);
    }
    output ~= value.unknownFields;
    if (output.length > 1024 * 1024) throw new Z8ProtobufException("protobuf notification exceeds size limit");
    return output;
}
private Z8AuthorityChange checked(const(ubyte)[] payload) {
    auto value = z8_decode_authority_change(payload);
    if (value.id is null || value.schema is null || !value.schema.length) throw new Z8ProtobufException("notification requires an ID and schema");
    return value;
}
void z8_apply_user_changed(Z8SessionManager sessions, const(ubyte)[] payload) {
    if (sessions is null) throw new Z8ProtobufException("session manager is required");
    auto change = checked(payload); sessions.dropUserSessions(change.id, change.schema);
}
void z8_apply_role_changed(Z8SessionManager sessions, const(ubyte)[] payload) {
    if (sessions is null) throw new Z8ProtobufException("session manager is required");
    auto change = checked(payload); sessions.dropRoleSessions(change.id, change.schema);
}

enum Z8AuthorityChangeKind { user, role }
// The host chooses transport, delivery and authentication. Calls may occur
// concurrently and, as in Java Z8, before the originating transaction commits.
interface IZ8AuthorityChangePublisher {
    void publish(Z8AuthorityChangeKind kind, const(ubyte)[] payload);
}
class Z8ProtobufAuthorityNotifier : IZ8UserChangeNotifier, IZ8RoleChangeNotifier {
    private IZ8AuthorityChangePublisher publisher;
    this(IZ8AuthorityChangePublisher publisher) {
        if (publisher is null) throw new Z8ProtobufException("notification publisher is required");
        this.publisher = publisher;
    }
    private void send(Z8AuthorityChangeKind kind, Z8Guid id, wstring schema) {
        if (id is null || schema is null || !schema.length) throw new Z8ProtobufException("notification requires an ID and schema");
        Z8AuthorityChange value; value.id = id; value.schema = schema;
        publisher.publish(kind, z8_encode_authority_change(value));
    }
    void userChanged(Z8Guid id, wstring schema) { send(Z8AuthorityChangeKind.user, id, schema); }
    void roleChanged(Z8Guid id, wstring schema) { send(Z8AuthorityChangeKind.role, id, schema); }
}
void z8_apply_authority_change(Z8SessionManager sessions, Z8AuthorityChangeKind kind, const(ubyte)[] payload) {
    switch (kind) {
        case Z8AuthorityChangeKind.user: z8_apply_user_changed(sessions, payload); return;
        case Z8AuthorityChangeKind.role: z8_apply_role_changed(sessions, payload); return;
        default: throw new Z8ProtobufException("unknown authority notification kind");
    }
}
