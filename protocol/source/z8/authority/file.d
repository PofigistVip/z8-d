module z8.authority.file;

import std.conv : to;
import z8.runtime;
import z8.protobuf.guid;
import z8.protobuf.wire;

private wstring readText(const(ubyte)[] bytes) {
    try {
        auto value = (cast(const(char)[])bytes).to!wstring;
        if (value !is null) return value;
        auto empty = new wchar[1]; return cast(wstring)empty[0 .. 0];
    } catch (Exception) { throw new Z8ProtobufException("invalid UTF-8 in file metadata"); }
}
private void text(ref ubyte[] output, uint field, wstring value) {
    if (value is null) return;
    if (value.length > 1024 * 1024) throw new Z8ProtobufException("protobuf file exceeds size limit");
    auto encoded = value.to!string;
    if (encoded.length > 1024 * 1024 || output.length > 1024 * 1024 - encoded.length)
        throw new Z8ProtobufException("protobuf file exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, cast(const(ubyte)[])encoded);
}
private void nested(ref ubyte[] output, uint field, const(ubyte)[] value) {
    if (value.length > 1024 * 1024 || output.length > 1024 * 1024 - value.length)
        throw new Z8ProtobufException("protobuf file exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, value);
}
private ubyte[] encodeDetails(Z8StringMap details) {
    if (details.z8_size() > 16384) throw new Z8ProtobufException("too many file details");
    ubyte[] output;
    auto keys = details.z8_insertion_keys();
    for (long i; i < keys.z8_size(); ++i) {
        auto key = keys.z8_get(i), value = details.z8_get(key);
        ubyte[] entry;
        if (key is null) { z8_proto_tag(entry, 2, 0); z8_proto_varint(entry, 1); } else text(entry, 1, key);
        if (value is null) { z8_proto_tag(entry, 4, 0); z8_proto_varint(entry, 1); } else text(entry, 3, value);
        nested(output, 1, entry);
    }
    return output;
}
ubyte[] z8_encode_file_metadata(Z8File value) {
    if (value is null) throw new Z8ProtobufException("file is required");
    ubyte[] output;
    if (value.id !is null) nested(output, 1, z8_proto_encode_guid(Z8ProtobufGuid(value.id)));
    if (value.user !is null) nested(output, 2, z8_proto_encode_guid(Z8ProtobufGuid(value.user)));
    text(output, 3, value.name); text(output, 4, value.path); text(output, 5, value.author);
    if (value.time !is null) { z8_proto_tag(output, 6, 0); z8_proto_varint(output, z8_proto_zigzag(z8_date_ticks(value.time))); }
    if (value.size.present) { z8_proto_tag(output, 7, 0); z8_proto_varint(output, z8_proto_zigzag(value.size.value)); }
    if (value.details !is null) nested(output, 8, encodeDetails(value.details));
    if (z8_file_has_upload(value)) {
        ubyte[] bytes;
        try { bytes = z8_file_upload_snapshot(value, 1024 * 1024); }
        catch (Exception failure) { throw new Z8ProtobufException("invalid file upload: " ~ failure.msg); }
        nested(output, 9, bytes);
    }
    if (output.length > 1024 * 1024) throw new Z8ProtobufException("protobuf file exceeds size limit");
    return output;
}
private void readDetail(Z8StringMap details, const(ubyte)[] data) {
    auto reader = Z8ProtobufReader(data); wstring key, value; bool hasKey, hasValue;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) { key = readText(reader.bytes()); hasKey = true; }
        else if (field == 2 && wire == 0) { reader.varint(); key = null; hasKey = true; }
        else if (field == 3 && wire == 2) { value = readText(reader.bytes()); hasValue = true; }
        else if (field == 4 && wire == 0) { reader.varint(); value = null; hasValue = true; }
        else reader.skip(field, wire);
    }
    if (!hasKey || !hasValue || details.z8_containsKey(key)) throw new Z8ProtobufException("invalid or duplicate file detail");
    details.z8_add(key, value);
}
private void readDetails(Z8StringMap details, const(ubyte)[] data, ref size_t count) {
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) {
            if (++count > 16384) throw new Z8ProtobufException("too many file details");
            readDetail(details, reader.bytes());
        } else reader.skip(field, wire);
    }
}
Z8File z8_decode_file_metadata(const(ubyte)[] data) {
    if (data.length > 1024 * 1024) throw new Z8ProtobufException("protobuf file exceeds size limit");
    auto reader = Z8ProtobufReader(data); Z8ProtobufGuid id, user;
    wstring name, path, author; Z8Date time; Z8Optional!long size;
    Z8StringMap details; size_t count; ubyte[] upload; bool hasUpload;
    while (!reader.empty()) {
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) z8_proto_merge_guid(id, reader.bytes());
        else if (field == 2 && wire == 2) z8_proto_merge_guid(user, reader.bytes());
        else if (field == 3 && wire == 2) name = readText(reader.bytes());
        else if (field == 4 && wire == 2) path = readText(reader.bytes());
        else if (field == 5 && wire == 2) author = readText(reader.bytes());
        else if (field == 6 && wire == 0) {
            auto ticks = z8_proto_unzigzag(reader.varint());
            try {
                time = z8_date_from_ticks(ticks);
                if (z8_date_ticks(time) != ticks) throw new Z8ProtobufException("file time out of range");
            } catch (Z8ProtobufException failure) { throw failure; }
            catch (Exception) { throw new Z8ProtobufException("file time out of range"); }
        } else if (field == 7 && wire == 0) size = z8_optional_wrap(z8_proto_unzigzag(reader.varint()));
        else if (field == 8 && wire == 2) {
            if (details is null) details = new Z8StringMap();
            readDetails(details, reader.bytes(), count);
        } else if (field == 9 && wire == 2) { upload = reader.bytes().dup; hasUpload = true; }
        else reader.skip(field, wire);
    }
    auto result = hasUpload ? z8_file_from_upload(name is null ? ""w : name, upload) : new Z8File();
    result.id = id.value; result.user = user.value; result.name = name; result.path = path; result.author = author;
    result.time = time; result.size = size; result.details = details;
    return result;
}
