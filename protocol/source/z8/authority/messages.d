module z8.authority.messages;

import std.conv : to;
import z8.authority.custom_primary;
import z8.authority.session;
import z8.protobuf.wire;
import z8.protobuf.guid;
import z8.runtime : Z8Guid, z8_guid_zero;

struct Z8AuthorityLogin { wstring login, password, schema, address; }
struct Z8AuthorityTrustedLogin { Z8Guid userId; wstring login, schema, address; bool createIfMissing; }
struct Z8AuthorityAuthorize { wstring sessionId, schema, serverId; }
struct Z8AuthorityLogout { wstring sessionId, schema; }
struct Z8AuthoritySessionReply { bool denied; Z8SessionSnapshot session; }

private wstring readText(const(ubyte)[] bytes) {
    try {
        auto value = (cast(const(char)[])bytes).to!wstring;
        if (value !is null) return value;
        auto empty = new wchar[1]; return cast(wstring)empty[0 .. 0];
    } catch (Exception) { throw new Z8ProtobufException("invalid UTF-8 in authority request"); }
}
private void text(ref ubyte[] output, uint field, wstring value) {
    if (value is null) return;
    if (value.length > 1024 * 1024) throw new Z8ProtobufException("authority message exceeds size limit");
    auto encoded = value.to!string;
    if (encoded.length > 1024 * 1024 || output.length > 1024 * 1024 - encoded.length)
        throw new Z8ProtobufException("authority message exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, cast(const(ubyte)[])encoded);
}
private void checkedSize(size_t size) {
    if (size > 1024 * 1024) throw new Z8ProtobufException("authority message exceeds size limit");
}
ubyte[] z8_encode_authority_login(Z8AuthorityLogin value) {
    if (value.login is null || !value.login.length || value.password is null || value.schema is null || !value.schema.length)
        throw new Z8ProtobufException("login, password and schema are required");
    ubyte[] output;
    text(output, 1, value.login); text(output, 2, value.password); text(output, 3, value.schema); text(output, 4, value.address);
    checkedSize(output.length); return output;
}
Z8AuthorityLogin z8_decode_authority_login(const(ubyte)[] data) {
    checkedSize(data.length); auto reader = Z8ProtobufReader(data); Z8AuthorityLogin result;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (wire == 2 && field >= 1 && field <= 4) {
            auto value = readText(reader.bytes());
            switch (field) { case 1: result.login = value; break; case 2: result.password = value; break;
                case 3: result.schema = value; break; case 4: result.address = value; break; default: assert(0); }
        } else reader.skip(field, wire);
    }
    if (result.login is null || !result.login.length || result.password is null || result.schema is null || !result.schema.length)
        throw new Z8ProtobufException("login, password and schema are required");
    return result;
}
private void checkTrustedLogin(Z8AuthorityTrustedLogin value) {
    if (value.schema is null || !value.schema.length || (value.userId is null && (value.login is null || !value.login.length)) ||
        (value.userId !is null && value.userId == z8_guid_zero()))
        throw new Z8ProtobufException("trusted login requires a schema and a nonzero user ID or login");
}
ubyte[] z8_encode_authority_trusted_login(Z8AuthorityTrustedLogin value) {
    checkTrustedLogin(value); ubyte[] output;
    if (value.userId !is null) { z8_proto_tag(output, 1, 2); z8_proto_bytes(output, z8_proto_encode_guid(Z8ProtobufGuid(value.userId))); }
    text(output, 2, value.login); text(output, 3, value.schema); text(output, 4, value.address);
    if (value.createIfMissing) { z8_proto_tag(output, 5, 0); z8_proto_varint(output, 1); }
    checkedSize(output.length); return output;
}
Z8AuthorityTrustedLogin z8_decode_authority_trusted_login(const(ubyte)[] data) {
    checkedSize(data.length); auto reader = Z8ProtobufReader(data); Z8AuthorityTrustedLogin result;
    Z8ProtobufGuid id;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) { z8_proto_merge_guid(id, reader.bytes()); result.userId = id.value; }
        else if (field >= 2 && field <= 4 && wire == 2) {
            auto value = readText(reader.bytes());
            if (field == 2) result.login = value; else if (field == 3) result.schema = value; else result.address = value;
        } else if (field == 5 && wire == 0) result.createIfMissing = reader.varint() != 0;
        else reader.skip(field, wire);
    }
    checkTrustedLogin(result); return result;
}
ubyte[] z8_encode_authority_authorize(Z8AuthorityAuthorize value) {
    if (value.sessionId is null || !value.sessionId.length || value.schema is null || !value.schema.length)
        throw new Z8ProtobufException("session ID and schema are required");
    ubyte[] output; text(output, 1, value.sessionId); text(output, 2, value.schema); text(output, 3, value.serverId);
    checkedSize(output.length); return output;
}
Z8AuthorityAuthorize z8_decode_authority_authorize(const(ubyte)[] data) {
    checkedSize(data.length); auto reader = Z8ProtobufReader(data); Z8AuthorityAuthorize result;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (wire == 2 && field >= 1 && field <= 3) {
            auto value = readText(reader.bytes());
            if (field == 1) result.sessionId = value; else if (field == 2) result.schema = value; else result.serverId = value;
        } else reader.skip(field, wire);
    }
    if (result.sessionId is null || !result.sessionId.length || result.schema is null || !result.schema.length)
        throw new Z8ProtobufException("session ID and schema are required");
    return result;
}
ubyte[] z8_encode_authority_logout(Z8AuthorityLogout value) {
    return z8_encode_authority_authorize(Z8AuthorityAuthorize(value.sessionId, value.schema, null));
}
Z8AuthorityLogout z8_decode_authority_logout(const(ubyte)[] data) {
    checkedSize(data.length); auto reader = Z8ProtobufReader(data); Z8AuthorityLogout result;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (wire == 2 && field >= 1 && field <= 2) {
            auto value = readText(reader.bytes());
            if (field == 1) result.sessionId = value; else result.schema = value;
        } else reader.skip(field, wire);
    }
    if (result.sessionId is null || !result.sessionId.length || result.schema is null || !result.schema.length)
        throw new Z8ProtobufException("session ID and schema are required");
    return result;
}
ubyte[] z8_encode_authority_reply(Z8AuthoritySessionReply value, Z8CustomPrimaryRegistry custom = null) {
    ubyte[] output;
    if (value.denied) {
        if (value.session.session !is null) throw new Z8ProtobufException("ambiguous authority reply");
        z8_proto_tag(output, 2, 0); z8_proto_varint(output, 1);
    } else {
        auto session = z8_encode_session(value.session, custom);
        z8_proto_tag(output, 1, 2); z8_proto_bytes(output, session);
    }
    checkedSize(output.length); return output;
}
Z8AuthoritySessionReply z8_decode_authority_reply(const(ubyte)[] data, Z8CustomPrimaryRegistry custom = null) {
    checkedSize(data.length); auto reader = Z8ProtobufReader(data); bool hasResult, denied; ubyte[] session;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) {
            if (!hasResult || denied) session = null;
            hasResult = true; denied = false; session ~= reader.bytes();
        } else if (field == 2 && wire == 0) {
            reader.varint(); hasResult = true; denied = true; session = null;
        } else reader.skip(field, wire);
    }
    if (!hasResult) throw new Z8ProtobufException("authority reply result is absent");
    Z8AuthoritySessionReply result; result.denied = denied;
    if (!denied) result.session = z8_decode_session(session, custom);
    return result;
}
