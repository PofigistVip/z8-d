module z8.authority.primary;

import std.bigint : BigInt;
import std.conv : to;
import z8.runtime;
import z8.protobuf.guid;
import z8.protobuf.wire;
import z8.authority.file;

enum Z8ProtobufPrimaryKind { none, nullValue, integer, boolean, decimal, text, guid, date, datespan, geometry, binary, file }
struct Z8ProtobufDecimal { wstring coefficient; int scale; bool nan; ubyte[] unknownFields; }
struct Z8ProtobufGeometry { wstring ewkbHex; int srid; ubyte[] unknownFields; }
struct Z8ProtobufBinary { ubyte[] data; wstring name; bool hasName; ubyte[] unknownFields; }
struct Z8ProtobufPrimary {
    Z8ProtobufPrimaryKind kind;
    bool nullValue, booleanValue;
    long integerValue;
    wstring textValue;
    Z8ProtobufDecimal decimalValue;
    Z8ProtobufGuid guidValue;
    Z8ProtobufGeometry geometryValue;
    Z8ProtobufBinary binaryValue;
    ubyte[] fileValue;
    ubyte[] unknownFields;
}
private wstring utf8(const(ubyte)[] bytes) {
    try { return (cast(const(char)[])bytes).to!wstring; }
    catch (Exception) { throw new Z8ProtobufException("invalid UTF-8 in protobuf primary"); }
}
private void putText(ref ubyte[] output, uint field, wstring value) {
    if (value.length > 1024 * 1024) throw new Z8ProtobufException("protobuf primary exceeds size limit");
    auto text = value.to!string;
    if (text.length > 1024 * 1024 || output.length > 1024 * 1024 - text.length)
        throw new Z8ProtobufException("protobuf primary exceeds size limit");
    z8_proto_tag(output, field, 2); z8_proto_bytes(output, cast(const(ubyte)[])text);
}
private void mergeDecimal(ref Z8ProtobufDecimal value, const(ubyte)[] data) {
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) value.coefficient = utf8(reader.bytes());
        else if (field == 2 && wire == 0) {
            auto raw = reader.varint();
            if (raw > uint.max) throw new Z8ProtobufException("decimal scale overflow");
            value.scale = cast(int)z8_proto_unzigzag(raw);
        } else if (field == 3 && wire == 0) value.nan = reader.varint() != 0;
        else { reader.skip(field, wire); value.unknownFields ~= data[start .. reader.position]; }
    }
}
private ubyte[] encodeDecimal(Z8ProtobufDecimal value) {
    ubyte[] output;
    if (value.coefficient.length) putText(output, 1, value.coefficient);
    if (value.scale) { z8_proto_tag(output, 2, 0); z8_proto_varint(output, z8_proto_zigzag(value.scale)); }
    if (value.nan) { z8_proto_tag(output, 3, 0); z8_proto_varint(output, 1); }
    output ~= value.unknownFields;
    return output;
}
private void mergeGeometry(ref Z8ProtobufGeometry value, const(ubyte)[] data) {
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position; uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) value.ewkbHex = utf8(reader.bytes());
        else if (field == 2 && wire == 0) {
            auto raw = reader.varint();
            if (raw > uint.max) throw new Z8ProtobufException("geometry SRID overflow");
            value.srid = cast(int)z8_proto_unzigzag(raw);
        } else { reader.skip(field, wire); value.unknownFields ~= data[start .. reader.position]; }
    }
}
private ubyte[] encodeGeometry(Z8ProtobufGeometry value) {
    ubyte[] output;
    if (value.ewkbHex.length) putText(output, 1, value.ewkbHex);
    if (value.srid) { z8_proto_tag(output, 2, 0); z8_proto_varint(output, z8_proto_zigzag(value.srid)); }
    output ~= value.unknownFields;
    return output;
}
private void mergeBinary(ref Z8ProtobufBinary value, const(ubyte)[] data) {
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position; uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 2) value.data = reader.bytes().dup;
        else if (field == 2 && wire == 2) { value.name = utf8(reader.bytes()); value.hasName = true; }
        else { reader.skip(field, wire); value.unknownFields ~= data[start .. reader.position]; }
    }
}
private ubyte[] encodeBinary(Z8ProtobufBinary value) {
    ubyte[] output;
    if (value.data.length) { z8_proto_tag(output, 1, 2); z8_proto_bytes(output, value.data); }
    if (value.hasName) putText(output, 2, value.name);
    output ~= value.unknownFields;
    return output;
}
Z8ProtobufPrimary z8_parse_protobuf_primary(const(ubyte)[] data) {
    if (data.length > 1024 * 1024) throw new Z8ProtobufException("protobuf primary exceeds size limit");
    Z8ProtobufPrimary result;
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (wire == 0 && (field == 1 || field == 2 || field == 3 || field == 7 || field == 8)) {
            auto value = reader.varint();
            if (field == 1) { result.kind = Z8ProtobufPrimaryKind.nullValue; result.nullValue = value != 0; }
            else if (field == 3) { result.kind = Z8ProtobufPrimaryKind.boolean; result.booleanValue = value != 0; }
            else {
                result.kind = field == 2 ? Z8ProtobufPrimaryKind.integer : field == 7 ? Z8ProtobufPrimaryKind.date : Z8ProtobufPrimaryKind.datespan;
                result.integerValue = z8_proto_unzigzag(value);
            }
        } else if (field == 4 && wire == 2) {
            if (result.kind != Z8ProtobufPrimaryKind.decimal) result.decimalValue = Z8ProtobufDecimal.init;
            result.kind = Z8ProtobufPrimaryKind.decimal; mergeDecimal(result.decimalValue, reader.bytes());
        } else if (field == 5 && wire == 2) {
            result.kind = Z8ProtobufPrimaryKind.text; result.textValue = utf8(reader.bytes());
        } else if (field == 6 && wire == 2) {
            if (result.kind != Z8ProtobufPrimaryKind.guid) result.guidValue = Z8ProtobufGuid.init;
            result.kind = Z8ProtobufPrimaryKind.guid; z8_proto_merge_guid(result.guidValue, reader.bytes());
        } else if (field == 9 && wire == 2) {
            if (result.kind != Z8ProtobufPrimaryKind.geometry) result.geometryValue = Z8ProtobufGeometry.init;
            result.kind = Z8ProtobufPrimaryKind.geometry; mergeGeometry(result.geometryValue, reader.bytes());
        } else if (field == 10 && wire == 2) {
            if (result.kind != Z8ProtobufPrimaryKind.binary) result.binaryValue = Z8ProtobufBinary.init;
            result.kind = Z8ProtobufPrimaryKind.binary; mergeBinary(result.binaryValue, reader.bytes());
        } else if (field == 11 && wire == 2) {
            if (result.kind != Z8ProtobufPrimaryKind.file) result.fileValue = null;
            result.kind = Z8ProtobufPrimaryKind.file; result.fileValue ~= reader.bytes();
        } else { reader.skip(field, wire); result.unknownFields ~= data[start .. reader.position]; }
    }
    return result;
}
ubyte[] z8_serialize_protobuf_primary(Z8ProtobufPrimary value) {
    ubyte[] output;
    switch (value.kind) {
        case Z8ProtobufPrimaryKind.none: break;
        case Z8ProtobufPrimaryKind.nullValue: z8_proto_tag(output, 1, 0); z8_proto_varint(output, value.nullValue ? 1 : 0); break;
        case Z8ProtobufPrimaryKind.boolean: z8_proto_tag(output, 3, 0); z8_proto_varint(output, value.booleanValue ? 1 : 0); break;
        case Z8ProtobufPrimaryKind.integer:
        case Z8ProtobufPrimaryKind.date:
        case Z8ProtobufPrimaryKind.datespan:
            auto field = value.kind == Z8ProtobufPrimaryKind.integer ? 2 : value.kind == Z8ProtobufPrimaryKind.date ? 7 : 8;
            z8_proto_tag(output, field, 0); z8_proto_varint(output, z8_proto_zigzag(value.integerValue)); break;
        case Z8ProtobufPrimaryKind.decimal:
            z8_proto_tag(output, 4, 2); z8_proto_bytes(output, encodeDecimal(value.decimalValue)); break;
        case Z8ProtobufPrimaryKind.text: putText(output, 5, value.textValue); break;
        case Z8ProtobufPrimaryKind.guid:
            z8_proto_tag(output, 6, 2); z8_proto_bytes(output, z8_proto_encode_guid(value.guidValue)); break;
        case Z8ProtobufPrimaryKind.geometry:
            z8_proto_tag(output, 9, 2); z8_proto_bytes(output, encodeGeometry(value.geometryValue)); break;
        case Z8ProtobufPrimaryKind.binary:
            z8_proto_tag(output, 10, 2); z8_proto_bytes(output, encodeBinary(value.binaryValue)); break;
        case Z8ProtobufPrimaryKind.file:
            z8_proto_tag(output, 11, 2); z8_proto_bytes(output, value.fileValue); break;
        default: throw new Z8ProtobufException("invalid protobuf primary kind");
    }
    output ~= value.unknownFields;
    if (output.length > 1024 * 1024) throw new Z8ProtobufException("protobuf primary exceeds size limit");
    return output;
}
Z8ProtobufPrimary z8_primary_to_protobuf(Z8Primary value) {
    Z8ProtobufPrimary result;
    if (value is null) { result.kind = Z8ProtobufPrimaryKind.nullValue; return result; }
    switch (value.kind) {
        case Z8PrimaryKind.integer: result.kind = Z8ProtobufPrimaryKind.integer; result.integerValue = value.integerValue; break;
        case Z8PrimaryKind.boolean: result.kind = Z8ProtobufPrimaryKind.boolean; result.booleanValue = value.booleanValue; break;
        case Z8PrimaryKind.decimal:
            result.kind = Z8ProtobufPrimaryKind.decimal; result.decimalValue.nan = value.decimalValue.nan;
            if (!value.decimalValue.nan) { result.decimalValue.coefficient = value.decimalValue.coefficient.to!string.to!wstring; result.decimalValue.scale = value.decimalValue.scale; }
            break;
        case Z8PrimaryKind.text:
            if (value.textValue is null) throw new Z8ProtobufException("invalid text primary");
            result.kind = Z8ProtobufPrimaryKind.text; result.textValue = value.textValue; break;
        case Z8PrimaryKind.guid:
            if (value.guidValue is null) throw new Z8ProtobufException("invalid GUID primary");
            result.kind = Z8ProtobufPrimaryKind.guid; result.guidValue.value = value.guidValue; break;
        case Z8PrimaryKind.date:
            result.kind = Z8ProtobufPrimaryKind.date; result.integerValue = z8_date_ticks(value.dateValue); break;
        case Z8PrimaryKind.datespan:
            if (value.datespanValue is null) throw new Z8ProtobufException("invalid datespan primary");
            result.kind = Z8ProtobufPrimaryKind.datespan; result.integerValue = value.datespanValue.ticks; break;
        case Z8PrimaryKind.geometry:
            if (value.geometryValue is null) throw new Z8ProtobufException("invalid geometry primary");
            result.kind = Z8ProtobufPrimaryKind.geometry;
            try {
                result.geometryValue.srid = cast(int)z8_geometry_srs(value.geometryValue);
                result.geometryValue.ewkbHex = z8_geometry_to_string(value.geometryValue);
                if (result.geometryValue.srid < 0 && result.geometryValue.ewkbHex.length)
                    throw new Z8ProtobufException("negative SRID is not supported for nonempty geometry");
            } catch (Z8ProtobufException failure) { throw failure; }
            catch (Exception failure) { throw new Z8ProtobufException("invalid geometry: " ~ failure.msg); }
            break;
        case Z8PrimaryKind.binary:
            if (value.binaryValue is null) throw new Z8ProtobufException("invalid binary primary");
            result.kind = Z8ProtobufPrimaryKind.binary;
            try { result.binaryValue.data = z8_binary_snapshot(value.binaryValue, 1024 * 1024); }
            catch (Exception failure) { throw new Z8ProtobufException("invalid binary: " ~ failure.msg); }
            result.binaryValue.name = value.binaryValue.name; result.binaryValue.hasName = value.binaryValue.name !is null;
            break;
        case Z8PrimaryKind.file:
            if (value.fileValue is null) throw new Z8ProtobufException("invalid file primary");
            result.kind = Z8ProtobufPrimaryKind.file; result.fileValue = z8_encode_file_metadata(value.fileValue); break;
        default: throw new Z8ProtobufException("primary type is not supported by protobuf");
    }
    return result;
}
Z8Primary z8_primary_from_protobuf(Z8ProtobufPrimary value) {
    switch (value.kind) {
        case Z8ProtobufPrimaryKind.nullValue: return null;
        case Z8ProtobufPrimaryKind.integer: return z8_primary_box(value.integerValue);
        case Z8ProtobufPrimaryKind.boolean: return z8_primary_box(value.booleanValue);
        case Z8ProtobufPrimaryKind.text: return z8_primary_box(value.textValue is null ? ""w : value.textValue);
        case Z8ProtobufPrimaryKind.guid:
            if (value.guidValue.value is null) throw new Z8ProtobufException("primary GUID is absent");
            return z8_primary_box(value.guidValue.value);
        case Z8ProtobufPrimaryKind.date:
            try {
                auto date = z8_date_from_ticks(value.integerValue);
                if (z8_date_ticks(date) != value.integerValue) throw new Z8ProtobufException("date ticks out of range");
                return z8_primary_box(date);
            } catch (Z8ProtobufException failure) { throw failure; }
            catch (Exception) { throw new Z8ProtobufException("date ticks out of range"); }
        case Z8ProtobufPrimaryKind.datespan: return z8_primary_box(new Z8Datespan(value.integerValue));
        case Z8ProtobufPrimaryKind.geometry:
            try {
                if (!value.geometryValue.ewkbHex.length) return z8_primary_box(z8_geometry_none(value.geometryValue.srid));
                auto geometry = z8_geometry_fromHexString(value.geometryValue.ewkbHex);
                if (z8_geometry_srs(geometry) != value.geometryValue.srid) throw new Z8ProtobufException("geometry SRID does not match EWKB");
                return z8_primary_box(geometry);
            } catch (Z8ProtobufException failure) { throw failure; }
            catch (Exception failure) { throw new Z8ProtobufException("invalid geometry: " ~ failure.msg); }
        case Z8ProtobufPrimaryKind.binary:
            auto binary = new Z8Binary(value.binaryValue.data.dup);
            binary.name = value.binaryValue.hasName ? (value.binaryValue.name is null ? ""w : value.binaryValue.name) : null;
            return z8_primary_box(binary);
        case Z8ProtobufPrimaryKind.file: return z8_primary_box(z8_decode_file_metadata(value.fileValue));
        case Z8ProtobufPrimaryKind.decimal:
            if (value.decimalValue.nan) return z8_primary_box(z8_decimal_nan());
            auto text = value.decimalValue.coefficient;
            auto start = text.length && text[0] == '-' ? 1 : 0;
            if (text.length <= start || text.length - start > 38) throw new Z8ProtobufException("invalid decimal coefficient");
            foreach (c; text[start .. $]) if (c < '0' || c > '9') throw new Z8ProtobufException("invalid decimal coefficient");
            Z8Decimal decimal;
            decimal.coefficient = BigInt(text.to!string); decimal.scale = value.decimalValue.scale;
            return z8_primary_box(decimal);
        default: throw new Z8ProtobufException("protobuf primary value is absent or unsupported");
    }
}
