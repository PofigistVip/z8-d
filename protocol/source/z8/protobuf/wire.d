module z8.protobuf.wire;

// Small protobuf wire primitives shared by the hand-written protocol adapters.
class Z8ProtobufException : Exception { this(string message) { super(message); } }

void z8_proto_varint(ref ubyte[] output, ulong value) {
    while (value >= 128) { output ~= cast(ubyte)((value & 127) | 128); value >>= 7; }
    output ~= cast(ubyte)value;
}
void z8_proto_tag(ref ubyte[] output, uint field, uint wire) {
    if (!field || field > 0x1fffffff || wire > 5) throw new Z8ProtobufException("invalid protobuf tag");
    z8_proto_varint(output, (cast(ulong)field << 3) | wire);
}
void z8_proto_fixed64(ref ubyte[] output, ulong value) {
    foreach (i; 0 .. 8) output ~= cast(ubyte)(value >> (i * 8));
}
void z8_proto_bytes(ref ubyte[] output, const(ubyte)[] value) {
    z8_proto_varint(output, value.length); output ~= value;
}

struct Z8ProtobufReader {
    const(ubyte)[] data;
    size_t position;
    this(const(ubyte)[] data) { this.data = data; }
    bool empty() const { return position == data.length; }
    ulong varint() {
        ulong value;
        foreach (i; 0 .. 10) {
            if (position == data.length) throw new Z8ProtobufException("truncated protobuf varint");
            auto b = data[position++];
            if (i == 9 && b > 1) throw new Z8ProtobufException("protobuf varint overflow");
            value |= cast(ulong)(b & 127) << (i * 7);
            if (!(b & 128)) return value;
        }
        throw new Z8ProtobufException("protobuf varint overflow");
    }
    void tag(out uint field, out uint wire) {
        auto value = varint();
        if ((value >> 3) == 0 || (value >> 3) > 0x1fffffff || (value & 7) > 5)
            throw new Z8ProtobufException("invalid protobuf tag");
        field = cast(uint)(value >> 3); wire = cast(uint)(value & 7);
    }
    const(ubyte)[] take(size_t count) {
        if (count > data.length - position) throw new Z8ProtobufException("truncated protobuf field");
        auto value = data[position .. position + count]; position += count; return value;
    }
    const(ubyte)[] bytes() {
        auto length = varint();
        if (length > data.length - position) throw new Z8ProtobufException("truncated protobuf bytes");
        return take(cast(size_t)length);
    }
    ulong fixed64() {
        auto value = take(8); ulong result;
        foreach (i, b; value) result |= cast(ulong)b << (i * 8);
        return result;
    }
    void skip(uint field, uint wire, uint depth = 0) {
        final switch (wire) {
            case 0: varint(); return;
            case 1: take(8); return;
            case 2: bytes(); return;
            case 3:
                if (depth >= 100) throw new Z8ProtobufException("protobuf group nesting limit exceeded");
                while (!empty()) {
                    uint nestedField, nestedWire; tag(nestedField, nestedWire);
                    if (nestedWire == 4) {
                        if (nestedField != field) throw new Z8ProtobufException("mismatched protobuf group");
                        return;
                    }
                    skip(nestedField, nestedWire, depth + 1);
                }
                throw new Z8ProtobufException("unterminated protobuf group");
            case 4: throw new Z8ProtobufException("unexpected protobuf end group");
            case 5: take(4); return;
        }
    }
}
