"""Verify protobuf session snapshots against Google's protobuf runtime."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
schema = (root / "protocol/proto/z8/authority/v1/session.proto").read_text(encoding="utf-8")
for declaration in ("UserSnapshot user = 3;", "UserSnapshot system = 4;", "Privileges privileges = 12;",
                    "repeated Parameter parameters = 18;", "bool null_key = 3;"):
    assert declaration in schema

def proto(name):
    return descriptor_pb2.FileDescriptorProto(name=f"z8/authority/v1/{name}.proto", package="z8.authority.v1", syntax="proto3")

def field(message, name, number, kind, label=1, type_name=None, oneof=None, optional=False):
    item = message.field.add(name=name, number=number, label=label, type=kind)
    if type_name: item.type_name = ".z8.authority.v1." + type_name
    if optional:
        oneof = len(message.oneof_decl); message.oneof_decl.add(name="_" + name); item.proto3_optional = True
    if oneof is not None: item.oneof_index = oneof
    return item

common = proto("common"); guid = common.message_type.add(name="Guid")
field(guid, "most_significant_bits", 1, 6); field(guid, "least_significant_bits", 2, 6)
file_descriptor = proto("file"); file_descriptor.dependency.append(common.name)
detail = file_descriptor.message_type.add(name="StringEntry"); detail.oneof_decl.add(name="key_kind"); detail.oneof_decl.add(name="value_kind")
for name, number, kind, oneof in (("key", 1, 9, 0), ("null_key", 2, 8, 0), ("value", 3, 9, 1), ("null_value", 4, 8, 1)):
    field(detail, name, number, kind, oneof=oneof)
details = file_descriptor.message_type.add(name="FileDetails"); field(details, "entries", 1, 11, label=3, type_name="StringEntry")
metadata = file_descriptor.message_type.add(name="FileMetadata")
field(metadata, "id", 1, 11, type_name="Guid"); field(metadata, "user", 2, 11, type_name="Guid")
for name, number, kind in (("name", 3, 9), ("path", 4, 9), ("author", 5, 9), ("time_ticks", 6, 18), ("size", 7, 18), ("upload", 9, 12)):
    field(metadata, name, number, kind, optional=True)
field(metadata, "details", 8, 11, type_name="FileDetails")
primary_file = proto("primary"); primary_file.dependency.extend((common.name, file_descriptor.name))
decimal = primary_file.message_type.add(name="Decimal")
field(decimal, "coefficient", 1, 9); field(decimal, "scale", 2, 17); field(decimal, "nan", 3, 8)
geometry = primary_file.message_type.add(name="Geometry"); field(geometry, "ewkb_hex", 1, 9); field(geometry, "srid", 2, 17)
binary = primary_file.message_type.add(name="Binary"); field(binary, "data", 1, 12); field(binary, "name", 2, 9, optional=True)
primary = primary_file.message_type.add(name="Primary"); primary.oneof_decl.add(name="value")
for number, (name, kind, type_name) in enumerate((("null_value", 8, None), ("integer_value", 18, None),
    ("boolean_value", 8, None), ("decimal_value", 11, "Decimal"), ("text_value", 9, None),
    ("guid_value", 11, "Guid"), ("date_ticks", 18, None), ("datespan_milliseconds", 18, None),
    ("geometry_value", 11, "Geometry"), ("binary_value", 11, "Binary"), ("file_value", 11, "FileMetadata")), 1):
    field(primary, name, number, kind, type_name=type_name, oneof=0)
priv_file = proto("privileges"); priv_file.dependency.append(common.name)
access = priv_file.message_type.add(name="Access")
for number, name in enumerate(("read", "write", "create", "copy", "destroy", "execute"), 1): field(access, name, number, 8)
priv_entry = priv_file.message_type.add(name="PrivilegeEntry")
field(priv_entry, "id", 1, 11, type_name="Guid"); field(priv_entry, "access", 2, 11, type_name="Access")
privileges = priv_file.message_type.add(name="Privileges"); field(privileges, "default_access", 1, 11, type_name="Access")
for number, name in enumerate(("tables", "fields", "requests"), 2): field(privileges, name, number, 11, label=3, type_name="PrivilegeEntry")
file = proto("session"); file.dependency.extend((common.name, primary_file.name, priv_file.name))
role = file.message_type.add(name="Role"); field(role, "id", 1, 11, type_name="Guid"); field(role, "name", 2, 9, optional=True)
entry = file.message_type.add(name="Entry"); field(entry, "id", 1, 11, type_name="Guid")
field(entry, "class_id", 2, 9, optional=True); field(entry, "title", 3, 9, optional=True)
param = file.message_type.add(name="Parameter"); param.oneof_decl.add(name="key_kind")
field(param, "key", 1, 9, oneof=0); field(param, "null_key", 3, 8, oneof=0); field(param, "value", 2, 11, type_name="Primary")
user = file.message_type.add(name="UserSnapshot"); field(user, "id", 1, 11, type_name="Guid")
for number, name in enumerate(("login", "first_name", "middle_name", "last_name", "description", "phone", "email", "settings"), 2):
    field(user, name, number, 9, optional=True)
field(user, "roles", 10, 11, label=3, type_name="Role"); field(user, "entries", 11, 11, label=3, type_name="Entry")
field(user, "privileges", 12, 11, type_name="Privileges")
for number, name in enumerate(("administrator", "builtin_administrator", "builtin_system", "change_password", "has_roles"), 13): field(user, name, number, 8)
field(user, "parameters", 18, 11, label=3, type_name="Parameter")
session = file.message_type.add(name="SessionSnapshot")
field(session, "session_id", 1, 9); field(session, "schema", 2, 9)
field(session, "user", 3, 11, type_name="UserSnapshot"); field(session, "system", 4, 11, type_name="UserSnapshot")
pool = descriptor_pool.DescriptorPool()
for descriptor in (common, file_descriptor, primary_file, priv_file, file): pool.Add(descriptor)
Session = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.SessionSnapshot"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory); source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.session;
import z8.protobuf.wire;
import std.file : read, write;
import std.path : dirName, buildPath;
void main(string[] args) {
    auto user = new Z8UserData(); user.id = z8_guid_create(42); user.login = "$literal$"w;
    user.middleName = z8_string_new(""w); user.roles = [z8_guid_create(5)]; user.roleNames = ["Operators"w];
    user.entries = [Z8UserEntry(z8_guid_create(9), "Sample"w, "Заголовок"w)];
    user.privileges = new Z8Privileges(Z8Access(true, true, false, false, false, true));
    user.privileges.setTableAccess(z8_guid_create(7), Z8Access.init);
    user.parameters.z8_add(null, z8_primary_box(7L));
    user.parameters.z8_add(z8_string_new(""w), null);
    user.parameters.z8_add("flag"w, z8_primary_box(false));
    user.parameters.z8_add("text"w, z8_primary_box("текст 🐘"w));
    auto binaryValue = new Z8Binary([cast(ubyte)0, 255]); binaryValue.name = "data.bin"w;
    user.parameters.z8_add("binary"w, z8_primary_box(binaryValue));
    auto file = z8_file_from_upload("photo.bin"w, [cast(ubyte)4, 5]); file.id = z8_guid_create(7); file.time = z8_date_from_ticks(1700000000123L);
    file.details.z8_add("kind"w, "photo"w); user.parameters.z8_add("file"w, z8_primary_box(file));
    user.parameters.z8_add("geometry"w, z8_primary_box(z8_geometry_point(z8_decimal_literal("1.5"), z8_decimal_literal("-2.5"), 4326)));
    auto system = new Z8UserData(); system.id = z8_guid_create(1); system.builtinSystem = true;
    system.privileges = new Z8Privileges(Z8Access(true, true, true, true, true, true));
    auto session = new Z8ApplicationSession("token"w, user, system);
    write(args[1], z8_encode_session(Z8SessionSnapshot("схема"w, session)));
    auto decoded = z8_decode_session(cast(const(ubyte)[])read(args[2]));
    assert(decoded.schema == "схема"w && decoded.session.id == "token"w && decoded.session.user.id == z8_guid_create(42));
    auto copy = decoded.session.user;
    assert(copy.login == "$literal$"w && copy.firstName is null && copy.middleName !is null && !copy.middleName.length);
    assert(copy.roles.length == 1 && copy.roles[0] == z8_guid_create(5) && copy.roleNames[0] == "Operators"w);
    assert(copy.entries.length == 1 && copy.entries[0].id == z8_guid_create(9) && copy.entries[0].title == "Заголовок"w);
    assert(copy.privileges.getDefaultAccess().execute && !copy.privileges.getTableAccess(z8_guid_create(7)).read);
    assert(copy.parameters.z8_containsKey(null) && z8_optional_require(z8_primary_cast!long(copy.parameters.z8_get(null))) == 7);
    assert(copy.parameters.z8_containsKey(""w) && copy.parameters.z8_get(""w) is null);
    assert(!z8_optional_require(z8_primary_cast!bool(copy.parameters.z8_get("flag"w))));
    assert(z8_primary_cast!wstring(copy.parameters.z8_get("text"w)) == "текст 🐘"w);
    assert(z8_primary_cast!Z8Binary(copy.parameters.z8_get("binary"w)).data == [cast(ubyte)0, 255]);
    auto copiedFile = z8_primary_cast!Z8File(copy.parameters.z8_get("file"w));
    assert(copiedFile.id == z8_guid_create(7) && z8_file_has_upload(copiedFile) && z8_file_upload_snapshot(copiedFile, 10) == [cast(ubyte)4, 5]);
    assert(z8_geometry_srs(z8_primary_cast!Z8Geometry(copy.parameters.z8_get("geometry"w))) == 4326);
    assert(decoded.session.system.builtinSystem && decoded.session.system.privileges.getDefaultAccess().destroy);
    write(args[3], z8_encode_session(decoded));
    bool rejected; try { z8_decode_session([]); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
    foreach (name; ["duplicate.bin", "missing-privileges.bin", "missing-system.bin"]) {
        rejected = false;
        try { z8_decode_session(cast(const(ubyte)[])read(buildPath(dirName(args[2]), name))); }
        catch (Z8ProtobufException) { rejected = true; }
        assert(rejected);
    }
    user.parameters.z8_add("unsupported"w, z8_primary_box(new Z8Object()));
    rejected = false; try { z8_encode_session(Z8SessionSnapshot("schema"w, session)); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
}
''', encoding="utf-8")
    exe = temp / ("session.exe" if os.name == "nt" else "session")
    modules = ("z8/protobuf/wire.d", "z8/protobuf/guid.d", "z8/authority/file.d", "z8/authority/primary.d", "z8/authority/privileges.d", "z8/authority/session.d")
    subprocess.run(["dmd", "-I" + str(root / "protocol/source"), *import_args(), str(source),
                    *[str(root / "protocol/source" / module) for module in modules], str(runtime), "-of=" + str(exe)], check=True)
    message = Session(session_id="token", schema="схема")
    user = message.user; user.id.least_significant_bits = 42; user.login = "$literal$"; user.middle_name = ""; user.has_roles = True
    item = user.roles.add(); item.id.least_significant_bits = 5; item.name = "Operators"
    item = user.entries.add(); item.id.least_significant_bits = 9; item.class_id = "Sample"; item.title = "Заголовок"
    user.privileges.default_access.read = True; user.privileges.default_access.write = True; user.privileges.default_access.execute = True
    item = user.privileges.tables.add(); item.id.least_significant_bits = 7; item.access.SetInParent()
    item = user.parameters.add(); item.null_key = True; item.value.integer_value = 7
    item = user.parameters.add(); item.key = ""; item.value.null_value = False
    item = user.parameters.add(); item.key = "binary"; item.value.binary_value.data = b"\x00\xff"; item.value.binary_value.name = "data.bin"
    item = user.parameters.add(); item.key = "file"; metadata = item.value.file_value
    metadata.id.least_significant_bits = 7; metadata.user.SetInParent(); metadata.name = "photo.bin"; metadata.path = ""; metadata.author = ""
    metadata.time_ticks = 1700000000123; metadata.size = 2; metadata.upload = b"\x04\x05"
    detail = metadata.details.entries.add(); detail.key = "kind"; detail.value = "photo"
    item = user.parameters.add(); item.key = "flag"; item.value.boolean_value = False
    item = user.parameters.add(); item.key = "geometry"; item.value.geometry_value.srid = 4326
    item.value.geometry_value.ewkb_hex = (struct.pack("<BII", 1, 0x20000001, 4326) + struct.pack("<dd", 1.5, -2.5)).hex().upper()
    item = user.parameters.add(); item.key = "text"; item.value.text_value = "текст 🐘"
    system = message.system; system.id.least_significant_bits = 1; system.builtin_system = True; system.has_roles = True
    for name in ("read", "write", "create", "copy", "destroy", "execute"): setattr(system.privileges.default_access, name, True)
    # Split the same embedded user across two occurrences to test protobuf merge.
    first, second = Session(session_id="token", schema="схема"), Session()
    first.user.id.least_significant_bits = 42; first.system.CopyFrom(system)
    second.user.CopyFrom(user); second.user.ClearField("id")
    encoded = first.SerializeToString() + second.SerializeToString() + b"\x98\x06\x01"
    expected = Session.FromString(encoded); expected.DiscardUnknownFields()
    bad = Session(); bad.CopyFrom(expected); bad.user.parameters.add().CopyFrom(bad.user.parameters[0])
    (temp / "duplicate.bin").write_bytes(bad.SerializeToString())
    bad.CopyFrom(expected); bad.user.ClearField("privileges")
    (temp / "missing-privileges.bin").write_bytes(bad.SerializeToString())
    bad.CopyFrom(expected); bad.ClearField("system")
    (temp / "missing-system.bin").write_bytes(bad.SerializeToString())
    input_file, output_file, roundtrip_file = temp / "input.bin", temp / "d.bin", temp / "roundtrip.bin"
    input_file.write_bytes(encoded)
    subprocess.run([str(exe), str(output_file), str(input_file), str(roundtrip_file)], cwd=temp, check=True)
    generated = Session.FromString(output_file.read_bytes())
    assert generated.session_id == "token" and generated.user.login == "$literal$" and not generated.user.HasField("first_name")
    assert generated.user.HasField("middle_name") and generated.user.middle_name == ""
    assert len(generated.user.parameters) == 7 and generated.user.privileges.tables[0].HasField("access")
    assert Session.FromString(roundtrip_file.read_bytes()) == expected
print("Protobuf session snapshots interoperate with Google's runtime")
