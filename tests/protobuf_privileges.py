"""Verify protobuf privilege snapshots against Google's protobuf runtime."""
from pathlib import Path
import os
import subprocess
import tempfile
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
schema = (root / "protocol/proto/z8/authority/v1/privileges.proto").read_text(encoding="utf-8")
for declaration in ("Access default_access = 1;", "repeated PrivilegeEntry tables = 2;",
                    "repeated PrivilegeEntry fields = 3;", "repeated PrivilegeEntry requests = 4;"):
    assert declaration in schema
common = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/common.proto", package="z8.authority.v1", syntax="proto3")
guid = common.message_type.add(name="Guid")
for name, number in (("most_significant_bits", 1), ("least_significant_bits", 2)):
    guid.field.add(name=name, number=number, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64)
file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/privileges.proto", package="z8.authority.v1", syntax="proto3")
file.dependency.append(common.name)
access = file.message_type.add(name="Access")
for number, name in enumerate(("read", "write", "create", "copy", "destroy", "execute"), 1):
    access.field.add(name=name, number=number, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_BOOL)
entry = file.message_type.add(name="PrivilegeEntry")
entry.field.add(name="id", number=1, label=1, type=11, type_name=".z8.authority.v1.Guid")
entry.field.add(name="access", number=2, label=1, type=11, type_name=".z8.authority.v1.Access")
privileges = file.message_type.add(name="Privileges")
privileges.field.add(name="default_access", number=1, label=1, type=11, type_name=".z8.authority.v1.Access")
for number, name in enumerate(("tables", "fields", "requests"), 2):
    privileges.field.add(name=name, number=number, label=3, type=11, type_name=".z8.authority.v1.PrivilegeEntry")
pool = descriptor_pool.DescriptorPool(); pool.Add(common); pool.Add(file)
Privileges = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.Privileges"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.privileges;
import z8.protobuf.wire;
import std.file : read, write;
void main(string[] args) {
    auto access = new Z8Privileges(Z8Access(true, true, false, false, false, true));
    access.setTableAccess(z8_guid_create(1), Z8Access.init);
    access.setFieldAccess(z8_guid_create(2), Z8Access(true, true, false, false, false, false));
    access.setRequestAccess(z8_guid_create(3), Z8Access(false, false, false, false, false, true));
    auto wire = z8_privileges_to_protobuf(access);
    write(args[1], z8_serialize_protobuf_privileges(wire));
    auto decoded = z8_parse_protobuf_privileges(cast(const(ubyte)[])read(args[2]));
    auto restored = z8_privileges_from_protobuf(decoded);
    assert(restored.getDefaultAccess().read && restored.getDefaultAccess().write && restored.getDefaultAccess().create);
    assert(!restored.getTableAccess(z8_guid_create(1)).read);
    assert(!restored.getFieldAccess(z8_guid_create(1), z8_guid_create(2)).write);
    assert(restored.getRequestAccess(z8_guid_create(3)).execute);
    write(args[3], z8_serialize_protobuf_privileges(decoded));
    auto malformed = decoded; malformed.tables ~= malformed.tables[0];
    bool rejected; try { z8_privileges_from_protobuf(malformed); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    malformed = decoded; malformed.fields[0].access.present = false;
    rejected = false; try { z8_privileges_from_protobuf(malformed); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    assert(!z8_privileges_from_protobuf(z8_parse_protobuf_privileges([])).getDefaultAccess().execute);
    Z8ProtobufPrivileges absent; absent.defaultAccess.value.execute = true;
    assert(!z8_privileges_from_protobuf(absent).getDefaultAccess().execute);
    rejected = false; try { z8_parse_protobuf_privileges([0x12, 0x01, 0x0A]); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
}
''', encoding="utf-8")
    exe = temp / ("privileges.exe" if os.name == "nt" else "privileges")
    subprocess.run(["dmd", "-I" + str(root / "protocol/source"), *import_args(), str(source),
                    str(root / "protocol/source/z8/protobuf/wire.d"), str(root / "protocol/source/z8/protobuf/guid.d"),
                    str(root / "protocol/source/z8/authority/privileges.d"), str(runtime), "-of=" + str(exe)], check=True)
    message = Privileges()
    message.default_access.read = True; message.default_access.write = True
    table = message.tables.add(); table.id.least_significant_bits = 1; table.access.SetInParent()
    field = message.fields.add(); field.id.least_significant_bits = 2; field.access.read = True; field.access.write = True
    request = message.requests.add(); request.id.least_significant_bits = 3; request.access.execute = True
    message.MergeFromString(b"\x98\x06\x01")
    message.default_access.MergeFromString(b"\x38\x01")
    field.MergeFromString(b"\x18\x09")
    field.id.MergeFromString(b"\x18\x7b")
    field.access.MergeFromString(b"\x38\x01")
    input_file, output_file, roundtrip_file = temp / "input.bin", temp / "d.bin", temp / "roundtrip.bin"
    # Two occurrences of an embedded message merge rather than replacing it.
    encoded = message.SerializeToString() + b"\x0a\x02\x18\x01"
    message.MergeFromString(b"\x0a\x02\x18\x01")
    input_file.write_bytes(encoded)
    subprocess.run([str(exe), str(output_file), str(input_file), str(roundtrip_file)], cwd=temp, check=True)
    generated = Privileges.FromString(output_file.read_bytes())
    assert generated.default_access.read and generated.default_access.write and generated.default_access.execute
    assert len(generated.tables) == 1 and generated.tables[0].HasField("access") and not generated.tables[0].access.read
    assert generated.fields[0].access.read and generated.fields[0].access.write and generated.requests[0].access.execute
    actual = Privileges.FromString(roundtrip_file.read_bytes())
    assert actual == message
    assert b"\x98\x06\x01" in actual.SerializeToString() and b"\x38\x01" in actual.default_access.SerializeToString()
    assert b"\x18\x09" in actual.fields[0].SerializeToString() and b"\x18\x7b" in actual.fields[0].id.SerializeToString()
print("Protobuf privilege snapshots interoperate with Google's runtime")
