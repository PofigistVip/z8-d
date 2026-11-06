"""Cross-check Z8 authority notifications with Google's protobuf runtime."""
from pathlib import Path
import os
import subprocess
import tempfile

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
schema = (root / "protocol/proto/z8/authority/v1/notifications.proto").read_text(encoding="utf-8")
for declaration in ("fixed64 most_significant_bits = 1;", "fixed64 least_significant_bits = 2;",
                    "Guid user_id = 1;", "Guid role_id = 1;", "string schema = 2;"):
    assert declaration in schema

file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/notifications.proto", package="z8.authority.v1", syntax="proto3")
guid = file.message_type.add(name="Guid")
for name, number in (("most_significant_bits", 1), ("least_significant_bits", 2)):
    guid.field.add(name=name, number=number, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64)
for name, field in (("UserChanged", "user_id"), ("RoleChanged", "role_id")):
    message = file.message_type.add(name=name)
    message.field.add(name=field, number=1, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".z8.authority.v1.Guid")
    message.field.add(name="schema", number=2, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
pool = descriptor_pool.DescriptorPool()
pool.Add(file)
Guid = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.Guid"))
UserChanged = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.UserChanged"))
RoleChanged = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.RoleChanged"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.notifications;
import z8.protobuf.wire;
import std.file : read, write;
class LoopbackPublisher : IZ8AuthorityChangePublisher {
    Z8SessionManager sessions;
    Z8AuthorityChangeKind[] calls;
    this(Z8SessionManager sessions) { this.sessions = sessions; }
    void publish(Z8AuthorityChangeKind kind, const(ubyte)[] payload) {
        calls ~= kind; z8_apply_authority_change(sessions, kind, payload);
    }
}
void main(string[] args) {
    Z8AuthorityChange change;
    change.id = new Z8Guid(0xFEDCBA9876543210UL, 0x8877665544332211UL);
    change.schema = "Схема 🐘"w;
    write(args[1], z8_encode_authority_change(change));
    auto input = cast(const(ubyte)[])read(args[2]);
    auto decoded = z8_decode_authority_change(input);
    assert(decoded.id.majorBits == 0xFEDCBA9876543210UL && decoded.id.minorBits == 0x8877665544332211UL);
    assert(decoded.schema == "Схема 🐘"w && decoded.unknownFields.length && decoded.unknownGuidFields.length);
    write(args[3], z8_encode_authority_change(decoded));
    ubyte[][] malformed = [[0], [0x0A, 0x80], [0x12, 0x01, 0xFF], [0x0A, 0x01, 0x09],
                    [0x08, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x02],
                    [0x5B, 0x64], [0x5C], [0x0E]];
    foreach (bad; malformed) {
        bool rejected; try { z8_decode_authority_change(bad); } catch (Z8ProtobufException) { rejected = true; }
        assert(rejected);
    }
    auto manager = new Z8SessionManager();
    auto system = new Z8UserData(); system.id = z8_guid_create(1);
    auto user = new Z8UserData(); user.id = z8_guid_create(42); user.roles = [z8_guid_create(8)];
    auto admin = new Z8UserData(); admin.id = z8_guid_create(43); admin.roles = user.roles; admin.administrator = true;
    manager.create("user"w, user, system, "schema"w);
    manager.create("other"w, user, system, "other"w);
    change.id = user.id; change.schema = "schema"w; change.unknownFields = null; change.unknownGuidFields = null;
    z8_apply_user_changed(manager, z8_encode_authority_change(change));
    assert(manager.getSession("user"w) is null && manager.getSession("other"w) !is null);
    manager.create("user"w, user, system, "schema"w);
    manager.create("admin"w, admin, system, "schema"w);
    change.id = z8_guid_create(8);
    z8_apply_role_changed(manager, z8_encode_authority_change(change));
    assert(manager.getSession("user"w) is null && manager.getSession("admin"w) !is null && manager.getSession("other"w) !is null);
    change.schema = ""w;
    bool rejected; try { z8_apply_user_changed(manager, z8_encode_authority_change(change)); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected && manager.getSession("other"w) !is null);
    auto publisher = new LoopbackPublisher(manager);
    auto notifier = new Z8ProtobufAuthorityNotifier(publisher);
    manager.create("loopback"w, user, system, "schema"w);
    (cast(IZ8UserChangeNotifier)notifier).userChanged(user.id, "schema"w);
    assert(manager.getSession("loopback"w) is null && publisher.calls.length == 1 && publisher.calls[0] == Z8AuthorityChangeKind.user);
    manager.create("loopback-role"w, user, system, "schema"w);
    (cast(IZ8RoleChangeNotifier)notifier).roleChanged(z8_guid_create(8), "schema"w);
    assert(manager.getSession("loopback-role"w) is null && publisher.calls.length == 2 && publisher.calls[1] == Z8AuthorityChangeKind.role);
    rejected = false; try { notifier.userChanged(user.id, ""w); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected && publisher.calls.length == 2);
    rejected = false; try { z8_apply_authority_change(manager, cast(Z8AuthorityChangeKind)42, []); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
}
''', encoding="utf-8")
    exe = temp / ("protobuf.exe" if os.name == "nt" else "protobuf")
    subprocess.run(["dmd", "-I" + str(root / "protocol/source"), *import_args(), str(source),
                    str(root / "protocol/source/z8/protobuf/wire.d"),
                    str(root / "protocol/source/z8/authority/notifications.d"), str(runtime), "-of=" + str(exe)], check=True)

    first = Guid(most_significant_bits=0xFEDCBA9876543210).SerializeToString() + b"\x18\x7b"
    second = Guid(least_significant_bits=0x8877665544332211).SerializeToString()
    encoded = b"\x0a" + bytes([len(first)]) + first + b"\x0a" + bytes([len(second)]) + second
    text = "Схема 🐘".encode("utf-8")
    encoded += b"\x12" + bytes([len(text)]) + text + b"\x98\x06\x96\x01\x5b\x65\x01\x02\x03\x04\x5c"
    input_file, output_file, roundtrip_file = temp / "input.bin", temp / "d.bin", temp / "roundtrip.bin"
    input_file.write_bytes(encoded)
    subprocess.run([str(exe), str(output_file), str(input_file), str(roundtrip_file)], cwd=temp, check=True)
    decoded = UserChanged.FromString(output_file.read_bytes())
    assert decoded.user_id.most_significant_bits == 0xFEDCBA9876543210
    assert decoded.user_id.least_significant_bits == 0x8877665544332211 and decoded.schema == "Схема 🐘"
    expected = UserChanged.FromString(encoded)
    actual = UserChanged.FromString(roundtrip_file.read_bytes())
    assert actual == expected and b"\x98\x06\x96\x01" in actual.SerializeToString()
    assert b"\x18\x7b" in actual.user_id.SerializeToString() and b"\x5b\x65\x01\x02\x03\x04\x5c" in actual.SerializeToString()
    role = RoleChanged.FromString(output_file.read_bytes())
    assert role.role_id.most_significant_bits == decoded.user_id.most_significant_bits and role.schema == decoded.schema
print("Protobuf authority notifications interoperate with Google's runtime")
