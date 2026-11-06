module z8.protobuf.guid;

import z8.runtime : Z8Guid;
import z8.protobuf.wire;

struct Z8ProtobufGuid { Z8Guid value; ubyte[] unknownFields; }

// Merge multiple occurrences of an embedded message, as required by protobuf.
void z8_proto_merge_guid(ref Z8ProtobufGuid guid, const(ubyte)[] data) {
    if (guid.value is null) guid.value = new Z8Guid();
    auto reader = Z8ProtobufReader(data);
    while (!reader.empty()) {
        auto start = reader.position;
        uint field, wire; reader.tag(field, wire);
        if (field == 1 && wire == 1) guid.value.majorBits = reader.fixed64();
        else if (field == 2 && wire == 1) guid.value.minorBits = reader.fixed64();
        else { reader.skip(field, wire); guid.unknownFields ~= data[start .. reader.position]; }
    }
}
ubyte[] z8_proto_encode_guid(Z8ProtobufGuid guid) {
    if (guid.value is null) throw new Z8ProtobufException("protobuf GUID is absent");
    ubyte[] output;
    if (guid.value.majorBits) { z8_proto_tag(output, 1, 1); z8_proto_fixed64(output, guid.value.majorBits); }
    if (guid.value.minorBits) { z8_proto_tag(output, 2, 1); z8_proto_fixed64(output, guid.value.minorBits); }
    output ~= guid.unknownFields;
    return output;
}
