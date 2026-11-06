module z8.authority.privileges;

import z8.runtime : Z8Access, Z8PrivilegeEntry, Z8Privileges, Z8PrivilegesSnapshot, z8_privileges_from_snapshot;
import z8.protobuf.guid;
import z8.protobuf.wire;

struct Z8ProtobufAccess { bool present; Z8Access value; ubyte[] unknownFields; }
struct Z8ProtobufPrivilegeEntry { Z8ProtobufGuid id; Z8ProtobufAccess access; ubyte[] unknownFields; }
struct Z8ProtobufPrivileges {
    Z8ProtobufAccess defaultAccess;
    Z8ProtobufPrivilegeEntry[] tables, fields, requests;
    ubyte[] unknownFields;
}
private void mergeAccess(ref Z8ProtobufAccess access, const(ubyte)[] data) {
    access.present = true;
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (wire == 0 && field >= 1 && field <= 6) {
            auto value = reader.varint() != 0;
            switch (field) {
                case 1: access.value.read = value; break;
                case 2: access.value.write = value; break;
                case 3: access.value.create = value; break;
                case 4: access.value.copy = value; break;
                case 5: access.value.destroy = value; break;
                case 6: access.value.execute = value; break;
                default: assert(0);
            }
        } else { reader.skip(field, wire); access.unknownFields ~= data[start .. reader.position]; }
    }
}
private ubyte[] encodeAccess(Z8ProtobufAccess access) {
    ubyte[] output;
    foreach (i, value; [access.value.read, access.value.write, access.value.create, access.value.copy, access.value.destroy, access.value.execute])
        if (value) { z8_proto_tag(output, cast(uint)i + 1, 0); z8_proto_varint(output, 1); }
    output ~= access.unknownFields;
    return output;
}
private Z8ProtobufPrivilegeEntry parseEntry(const(ubyte)[] data) {
    Z8ProtobufPrivilegeEntry result;
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) z8_proto_merge_guid(result.id, reader.bytes());
        else if (field == 2 && wire == 2) mergeAccess(result.access, reader.bytes());
        else { reader.skip(field, wire); result.unknownFields ~= data[start .. reader.position]; }
    }
    return result;
}
private ubyte[] encodeEntry(Z8ProtobufPrivilegeEntry entry) {
    ubyte[] output;
    if (entry.id.value !is null) { z8_proto_tag(output, 1, 2); z8_proto_bytes(output, z8_proto_encode_guid(entry.id)); }
    if (entry.access.present) { z8_proto_tag(output, 2, 2); z8_proto_bytes(output, encodeAccess(entry.access)); }
    output ~= entry.unknownFields;
    return output;
}
Z8ProtobufPrivileges z8_parse_protobuf_privileges(const(ubyte)[] data) {
    if (data.length > 1024 * 1024) throw new Z8ProtobufException("protobuf privileges exceed size limit");
    Z8ProtobufPrivileges result;
    auto reader = Z8ProtobufReader(data);
    size_t count;
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) mergeAccess(result.defaultAccess, reader.bytes());
        else if (field >= 2 && field <= 4 && wire == 2) {
            if (++count > 16384) throw new Z8ProtobufException("too many privilege entries");
            auto entry = parseEntry(reader.bytes());
            if (field == 2) result.tables ~= entry;
            else if (field == 3) result.fields ~= entry;
            else result.requests ~= entry;
        } else { reader.skip(field, wire); result.unknownFields ~= data[start .. reader.position]; }
    }
    return result;
}
ubyte[] z8_serialize_protobuf_privileges(Z8ProtobufPrivileges value) {
    if (value.tables.length + value.fields.length + value.requests.length > 16384)
        throw new Z8ProtobufException("too many privilege entries");
    ubyte[] output;
    if (value.defaultAccess.present) { z8_proto_tag(output, 1, 2); z8_proto_bytes(output, encodeAccess(value.defaultAccess)); }
    void entries(uint field, Z8ProtobufPrivilegeEntry[] items) {
        foreach (entry; items) { z8_proto_tag(output, field, 2); z8_proto_bytes(output, encodeEntry(entry)); }
    }
    entries(2, value.tables); entries(3, value.fields); entries(4, value.requests);
    output ~= value.unknownFields;
    if (output.length > 1024 * 1024) throw new Z8ProtobufException("protobuf privileges exceed size limit");
    return output;
}
Z8ProtobufPrivileges z8_privileges_to_protobuf(Z8Privileges privileges) {
    if (privileges is null) throw new Z8ProtobufException("privileges are required");
    auto snapshot = privileges.snapshot();
    Z8ProtobufPrivilegeEntry[] entries(Z8PrivilegeEntry[] values) {
        Z8ProtobufPrivilegeEntry[] result;
        foreach (value; values) result ~= Z8ProtobufPrivilegeEntry(Z8ProtobufGuid(value.id), Z8ProtobufAccess(true, value.access));
        return result;
    }
    Z8ProtobufPrivileges result;
    result.defaultAccess = Z8ProtobufAccess(true, snapshot.defaultAccess);
    result.tables = entries(snapshot.tables); result.fields = entries(snapshot.fields); result.requests = entries(snapshot.requests);
    return result;
}
Z8Privileges z8_privileges_from_protobuf(Z8ProtobufPrivileges value) {
    if (value.tables.length + value.fields.length + value.requests.length > 16384)
        throw new Z8ProtobufException("too many privilege entries");
    Z8PrivilegeEntry[] entries(Z8ProtobufPrivilegeEntry[] values) {
        Z8PrivilegeEntry[] result;
        foreach (entry; values) {
            if (entry.id.value is null || !entry.access.present) throw new Z8ProtobufException("privilege entry requires an ID and access");
            result ~= Z8PrivilegeEntry(entry.id.value, entry.access.value);
        }
        return result;
    }
    auto defaults = value.defaultAccess.present ? value.defaultAccess.value : Z8Access.init;
    auto snapshot = Z8PrivilegesSnapshot(defaults, entries(value.tables), entries(value.fields), entries(value.requests));
    try { return z8_privileges_from_snapshot(snapshot); }
    catch (Exception failure) { throw new Z8ProtobufException("invalid privileges: " ~ failure.msg); }
}
