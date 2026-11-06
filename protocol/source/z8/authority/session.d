module z8.authority.session;

import std.algorithm.sorting : sort;
import std.conv : to;
import z8.runtime;
import z8.authority.primary;
import z8.authority.privileges;
import z8.authority.custom_primary;
import z8.protobuf.guid;
import z8.protobuf.wire;

// Converting a protobuf message into runtime data intentionally discards its
// unknown fields; the receiving authority is not a wire-message proxy.
struct Z8SessionSnapshot { wstring schema; Z8ApplicationSession session; }
private wstring readText(const(ubyte)[] bytes) {
    try {
        auto text = (cast(const(char)[])bytes).to!wstring;
        if (text !is null) return text;
        auto empty = new wchar[1]; return cast(wstring)empty[0 .. 0];
    } catch (Exception) { throw new Z8ProtobufException("invalid UTF-8 in session"); }
}
private void text(ref ubyte[] output, uint field, wstring value) {
    if (value is null) return;
    if (value.length > 1024 * 1024) throw new Z8ProtobufException("protobuf session exceeds size limit");
    auto encoded = value.to!string;
    if (encoded.length > 1024 * 1024 || output.length > 1024 * 1024 - encoded.length)
        throw new Z8ProtobufException("protobuf session exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, cast(const(ubyte)[])encoded);
}
private void nested(ref ubyte[] output, uint field, const(ubyte)[] value) {
    if (value.length > 1024 * 1024 || output.length > 1024 * 1024 - value.length)
        throw new Z8ProtobufException("protobuf session exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, value);
}
private void guid(ref ubyte[] output, uint field, Z8Guid value) {
    if (value is null) throw new Z8ProtobufException("session GUID is required");
    nested(output, field, z8_proto_encode_guid(Z8ProtobufGuid(value)));
}
private void flag(ref ubyte[] output, uint field, bool value) {
    if (value) { z8_proto_tag(output, field, 0); z8_proto_varint(output, 1); }
}
private ubyte[] encodeUser(Z8UserData user, Z8CustomPrimaryRegistry custom) {
    if (user is null || user.id is null || user.privileges is null || user.parameters is null)
        throw new Z8ProtobufException("session user requires ID, privileges and parameters");
    if (user.roles.length + user.entries.length + cast(size_t)user.parameters.z8_size() > 16384 || user.roleNames.length > user.roles.length)
        throw new Z8ProtobufException("invalid session user collections");
    ubyte[] output;
    guid(output, 1, user.id);
    text(output, 2, user.login); text(output, 3, user.firstName); text(output, 4, user.middleName);
    text(output, 5, user.lastName); text(output, 6, user.description); text(output, 7, user.phone);
    text(output, 8, user.email); text(output, 9, user.settings);
    foreach (i, id; user.roles) {
        ubyte[] role; guid(role, 1, id);
        if (i < user.roleNames.length) text(role, 2, user.roleNames[i]);
        nested(output, 10, role);
    }
    foreach (item; user.entries) {
        ubyte[] entry; guid(entry, 1, item.id); text(entry, 2, item.classId); text(entry, 3, item.title);
        nested(output, 11, entry);
    }
    nested(output, 12, z8_serialize_protobuf_privileges(z8_privileges_to_protobuf(user.privileges)));
    flag(output, 13, user.administrator); flag(output, 14, user.builtinAdministrator);
    flag(output, 15, user.builtinSystem); flag(output, 16, user.changePassword); flag(output, 17, user.hasRoles);
    auto keys = user.parameters.z8_keys();
    wstring[] ordered; bool nullKey;
    for (long i; i < keys.z8_size(); ++i) {
        auto key = keys.z8_get(i);
        if (key is null) nullKey = true; else ordered ~= key;
    }
    sort(ordered);
    void parameter(wstring key) {
        ubyte[] entry;
        if (key is null) { z8_proto_tag(entry, 3, 0); z8_proto_varint(entry, 1); }
        else text(entry, 1, key);
        nested(entry, 2, z8_serialize_protobuf_primary(z8_primary_to_protobuf(user.parameters.z8_get(key), custom)));
        nested(output, 18, entry);
    }
    if (nullKey) parameter(null);
    foreach (key; ordered) parameter(key);
    return output;
}
ubyte[] z8_encode_session(Z8SessionSnapshot value, Z8CustomPrimaryRegistry custom = null) {
    auto session = value.session;
    if (session is null || session.id is null || !session.id.length || value.schema is null || !value.schema.length)
        throw new Z8ProtobufException("session ID and schema are required");
    ubyte[] output;
    text(output, 1, session.id); text(output, 2, value.schema);
    nested(output, 3, encodeUser(session.user, custom)); nested(output, 4, encodeUser(session.system, custom));
    if (output.length > 1024 * 1024) throw new Z8ProtobufException("protobuf session exceeds size limit");
    return output;
}
private struct UserReader {
    Z8UserData value;
    Z8ProtobufGuid id;
    bool privilegesPresent;
    ubyte[] privileges;
    size_t count;
    void initialize() { if (value is null) { value = new Z8UserData(); value.hasRoles = false; } }
}
private void readRole(Z8UserData user, const(ubyte)[] bytes) {
    auto reader = Z8ProtobufReader(bytes); Z8ProtobufGuid id; wstring name;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) z8_proto_merge_guid(id, reader.bytes());
        else if (field == 2 && wire == 2) name = readText(reader.bytes());
        else reader.skip(field, wire);
    }
    if (id.value is null) throw new Z8ProtobufException("session role ID is absent");
    user.roles ~= id.value; user.roleNames ~= name;
}
private void readEntry(Z8UserData user, const(ubyte)[] bytes) {
    auto reader = Z8ProtobufReader(bytes); Z8ProtobufGuid id; wstring classId, title;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) z8_proto_merge_guid(id, reader.bytes());
        else if (field == 2 && wire == 2) classId = readText(reader.bytes());
        else if (field == 3 && wire == 2) title = readText(reader.bytes());
        else reader.skip(field, wire);
    }
    if (id.value is null) throw new Z8ProtobufException("session entry ID is absent");
    user.entries ~= Z8UserEntry(id.value, classId, title);
}
private void readParameter(Z8UserData user, const(ubyte)[] bytes, Z8CustomPrimaryRegistry custom) {
    auto reader = Z8ProtobufReader(bytes); wstring key; bool hasKey, hasValue; ubyte[] primary;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) { key = readText(reader.bytes()); hasKey = true; }
        else if (field == 3 && wire == 0) { reader.varint(); key = null; hasKey = true; }
        else if (field == 2 && wire == 2) { primary ~= reader.bytes(); hasValue = true; }
        else reader.skip(field, wire);
    }
    if (!hasKey || !hasValue || user.parameters.z8_containsKey(key)) throw new Z8ProtobufException("invalid or duplicate session parameter");
    user.parameters.z8_add(key, z8_primary_from_protobuf(z8_parse_protobuf_primary(primary), custom));
}
private void mergeUser(ref UserReader user, const(ubyte)[] bytes, Z8CustomPrimaryRegistry custom) {
    user.initialize(); auto reader = Z8ProtobufReader(bytes);
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) z8_proto_merge_guid(user.id, reader.bytes());
        else if (field >= 2 && field <= 9 && wire == 2) {
            auto value = readText(reader.bytes());
            switch (field) {
                case 2: user.value.login = value; break; case 3: user.value.firstName = value; break;
                case 4: user.value.middleName = value; break; case 5: user.value.lastName = value; break;
                case 6: user.value.description = value; break; case 7: user.value.phone = value; break;
                case 8: user.value.email = value; break; case 9: user.value.settings = value; break;
                default: assert(0);
            }
        } else if ((field == 10 || field == 11 || field == 18) && wire == 2) {
            if (++user.count > 16384) throw new Z8ProtobufException("too many session user entries");
            auto item = reader.bytes();
            if (field == 10) readRole(user.value, item);
            else if (field == 11) readEntry(user.value, item);
            else readParameter(user.value, item, custom);
        } else if (field == 12 && wire == 2) { user.privilegesPresent = true; user.privileges ~= reader.bytes(); }
        else if (field >= 13 && field <= 17 && wire == 0) {
            auto value = reader.varint() != 0;
            switch (field) {
                case 13: user.value.administrator = value; break; case 14: user.value.builtinAdministrator = value; break;
                case 15: user.value.builtinSystem = value; break; case 16: user.value.changePassword = value; break;
                case 17: user.value.hasRoles = value; break; default: assert(0);
            }
        } else reader.skip(field, wire);
    }
}
private Z8UserData finishUser(UserReader user) {
    if (user.value is null || user.id.value is null || !user.privilegesPresent)
        throw new Z8ProtobufException("session user or privileges are absent");
    user.value.id = user.id.value;
    user.value.privileges = z8_privileges_from_protobuf(z8_parse_protobuf_privileges(user.privileges));
    return user.value;
}
Z8SessionSnapshot z8_decode_session(const(ubyte)[] data, Z8CustomPrimaryRegistry custom = null) {
    if (data.length > 1024 * 1024) throw new Z8ProtobufException("protobuf session exceeds size limit");
    auto reader = Z8ProtobufReader(data); wstring id, schema; UserReader user, system;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) id = readText(reader.bytes());
        else if (field == 2 && wire == 2) schema = readText(reader.bytes());
        else if (field == 3 && wire == 2) mergeUser(user, reader.bytes(), custom);
        else if (field == 4 && wire == 2) mergeUser(system, reader.bytes(), custom);
        else reader.skip(field, wire);
    }
    if (id is null || !id.length || schema is null || !schema.length) throw new Z8ProtobufException("session ID and schema are required");
    return Z8SessionSnapshot(schema, new Z8ApplicationSession(id, finishUser(user), finishUser(system)));
}
