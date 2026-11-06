module z8.authority.custom_primary;

import z8.runtime : Z8Object;
import z8.protobuf.wire : Z8ProtobufException;

// Application-provided codecs must validate their inputs and output. Only
// explicitly registered class IDs can be instantiated from a remote message.
interface IZ8CustomPrimaryCodec {
    wstring classId();
    ubyte[] encode(Z8Object value);
    Z8Object decode(const(ubyte)[] data);
}
class Z8CustomPrimaryRegistry {
    private IZ8CustomPrimaryCodec[wstring] codecs;
    private Object mutex;
    this() { mutex = new Object(); }
    void register(IZ8CustomPrimaryCodec codec) {
        if (codec is null) throw new Z8ProtobufException("custom primary codec is required");
        auto id = codec.classId();
        if (id is null || !id.length) throw new Z8ProtobufException("custom primary class ID is required");
        synchronized (mutex) {
            if (id in codecs) throw new Z8ProtobufException("duplicate custom primary codec");
            codecs[id.idup] = codec;
        }
    }
    IZ8CustomPrimaryCodec get(wstring id) {
        if (id is null || !id.length) return null;
        synchronized (mutex) { auto found = id in codecs; return found is null ? null : *found; }
    }
}
