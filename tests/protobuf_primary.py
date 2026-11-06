"""Cross-check typed BL primary values with Google's protobuf runtime."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
schema = (root / "protocol/proto/z8/authority/v1/primary.proto").read_text(encoding="utf-8")
for line in ("bool null_value = 1;", "sint64 integer_value = 2;", "Decimal decimal_value = 4;",
             "Guid guid_value = 6;", "sint64 date_ticks = 7;", "sint64 datespan_milliseconds = 8;"):
    assert line in schema
common = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/common.proto", package="z8.authority.v1", syntax="proto3")
guid = common.message_type.add(name="Guid")
for number, name in enumerate(("most_significant_bits", "least_significant_bits"), 1):
    guid.field.add(name=name, number=number, label=1, type=descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64)
file_descriptor = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/file.proto", package="z8.authority.v1", syntax="proto3")
file_descriptor.dependency.append(common.name)
detail = file_descriptor.message_type.add(name="StringEntry"); detail.oneof_decl.add(name="key_kind"); detail.oneof_decl.add(name="value_kind")
for name, number, kind, oneof in (("key", 1, 9, 0), ("null_key", 2, 8, 0), ("value", 3, 9, 1), ("null_value", 4, 8, 1)):
    detail.field.add(name=name, number=number, label=1, type=kind, oneof_index=oneof)
details = file_descriptor.message_type.add(name="FileDetails")
details.field.add(name="entries", number=1, label=3, type=11, type_name=".z8.authority.v1.StringEntry")
metadata = file_descriptor.message_type.add(name="FileMetadata")
for name, number in (("id", 1), ("user", 2)):
    metadata.field.add(name=name, number=number, label=1, type=11, type_name=".z8.authority.v1.Guid")
for name, number, kind in (("name", 3, 9), ("path", 4, 9), ("author", 5, 9), ("time_ticks", 6, 18), ("size", 7, 18), ("upload", 9, 12)):
    oneof = len(metadata.oneof_decl); metadata.oneof_decl.add(name="_" + name)
    metadata.field.add(name=name, number=number, label=1, type=kind, proto3_optional=True, oneof_index=oneof)
metadata.field.add(name="details", number=8, label=1, type=11, type_name=".z8.authority.v1.FileDetails")
file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/primary.proto", package="z8.authority.v1", syntax="proto3")
file.dependency.extend((common.name, file_descriptor.name))
decimal = file.message_type.add(name="Decimal")
decimal.field.add(name="coefficient", number=1, label=1, type=9)
decimal.field.add(name="scale", number=2, label=1, type=17)
decimal.field.add(name="nan", number=3, label=1, type=8)
geometry = file.message_type.add(name="Geometry")
geometry.field.add(name="ewkb_hex", number=1, label=1, type=9); geometry.field.add(name="srid", number=2, label=1, type=17)
binary = file.message_type.add(name="Binary"); binary.oneof_decl.add(name="_name")
binary.field.add(name="data", number=1, label=1, type=12)
binary.field.add(name="name", number=2, label=1, type=9, proto3_optional=True, oneof_index=0)
custom = file.message_type.add(name="CustomPrimary")
custom.field.add(name="class_id", number=1, label=1, type=9); custom.field.add(name="payload", number=2, label=1, type=12)
primary = file.message_type.add(name="Primary"); primary.oneof_decl.add(name="value")
for number, (name, kind, type_name) in enumerate((
    ("null_value", 8, None), ("integer_value", 18, None), ("boolean_value", 8, None),
    ("decimal_value", 11, ".z8.authority.v1.Decimal"), ("text_value", 9, None),
    ("guid_value", 11, ".z8.authority.v1.Guid"), ("date_ticks", 18, None),
    ("datespan_milliseconds", 18, None), ("geometry_value", 11, ".z8.authority.v1.Geometry"),
    ("binary_value", 11, ".z8.authority.v1.Binary"), ("file_value", 11, ".z8.authority.v1.FileMetadata"),
    ("custom_value", 11, ".z8.authority.v1.CustomPrimary")), 1):
    field = primary.field.add(name=name, number=number, label=1, type=kind, oneof_index=0)
    if type_name: field.type_name = type_name
pool = descriptor_pool.DescriptorPool(); pool.Add(common); pool.Add(file_descriptor); pool.Add(file)
Primary = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.Primary"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.primary;
import z8.authority.custom_primary;
import z8.protobuf.wire;
import std.file : read, write;
import std.path : buildPath;
import std.bigint : BigInt;
class Demo : Z8Object { ubyte number; override wstring z8_class_id() { return "example.Demo"w; } }
class Codec : IZ8CustomPrimaryCodec {
    wstring classId() { return "example.Demo"w; }
    ubyte[] encode(Z8Object value) { auto item = cast(Demo)value; if (item is null) throw new Exception("wrong type"); return [item.number]; }
    Z8Object decode(const(ubyte)[] data) { if (data.length != 1) throw new Exception("invalid data"); auto item = new Demo(); item.number = data[0]; return item; }
}
class BadCodec : IZ8CustomPrimaryCodec {
    wstring classId() { return "example.Bad"w; }
    ubyte[] encode(Z8Object value) { return []; }
    Z8Object decode(const(ubyte)[] data) { return new Demo(); }
}
void main(string[] args) {
    auto dir = args[1];
    Z8Primary readValue(string name) {
        return z8_primary_from_protobuf(z8_parse_protobuf_primary(cast(const(ubyte)[])read(buildPath(dir, name ~ ".bin"))));
    }
    void emit(string name, Z8Primary value) { write(buildPath(dir, name ~ "-d.bin"), z8_serialize_protobuf_primary(z8_primary_to_protobuf(value))); }
    assert(readValue("null") is null);
    assert(z8_optional_require(z8_primary_cast!long(readValue("integer"))) == long.min);
    assert(!z8_optional_require(z8_primary_cast!bool(readValue("boolean"))));
    auto decimal = z8_optional_require(z8_primary_cast!Z8Decimal(readValue("decimal")));
    assert(decimal.coefficient == BigInt("-1234500") && decimal.scale == 6 && !decimal.nan);
    assert(z8_optional_require(z8_primary_cast!Z8Decimal(readValue("nan"))).nan);
    assert(z8_primary_cast!wstring(readValue("text")) == "Строка 🐘"w);
    auto empty = readValue("empty"); assert(empty !is null && empty.textValue !is null && empty.textValue.length == 0);
    assert(z8_primary_cast!Z8Guid(readValue("guid")) == new Z8Guid(0xFEDCBA9876543210UL, 0x8877665544332211UL));
    assert(z8_date_ticks(z8_primary_cast!Z8Date(readValue("date"))) == 1700000000123L);
    assert(z8_primary_cast!Z8Datespan(readValue("span")).ticks == long.min);
    auto geometry = z8_primary_cast!Z8Geometry(readValue("geometry"));
    assert(z8_geometry_srs(geometry) == 4326 && z8_geometry_x(geometry) == z8_decimal_literal("1.5"));
    auto none = z8_primary_cast!Z8Geometry(readValue("empty-geometry")); assert(z8_geometry_srs(none) == 3857 && !z8_geometry_to_string(none).length);
    auto binary = z8_primary_cast!Z8Binary(readValue("binary"));
    assert(binary.data == [cast(ubyte)1, 2, 255] && binary.name !is null && !binary.name.length);
    auto metadata = z8_primary_cast!Z8File(readValue("file"));
    assert(metadata.id == z8_guid_create(7) && metadata.user == z8_guid_create(8));
    assert(metadata.name !is null && !metadata.name.length && metadata.path == "folder/a.txt"w && metadata.author is null);
    assert(z8_date_ticks(metadata.time) == 1700000000123L && z8_optional_require(metadata.size) == 2);
    assert(metadata.details.z8_get("charset"w) == "utf-8"w && metadata.details.z8_containsKey(null) && metadata.details.z8_get(null) is null);
    assert(z8_file_has_upload(metadata) && z8_file_upload_snapshot(metadata, 10) == [cast(ubyte)0, 255]);
    auto missingFile = new Z8File(); missingFile.id = null; missingFile.user = null; missingFile.name = null;
    missingFile.path = null; missingFile.author = null; missingFile.time = null; missingFile.size = Z8Optional!long.init; missingFile.details = null;
    auto copiedMissing = z8_primary_cast!Z8File(z8_primary_from_protobuf(z8_parse_protobuf_primary(z8_serialize_protobuf_primary(z8_primary_to_protobuf(z8_primary_box(missingFile))))));
    assert(copiedMissing.id is null && copiedMissing.name is null && copiedMissing.time is null && !copiedMissing.size.present && copiedMissing.details is null && !z8_file_has_upload(copiedMissing));
    auto emptyUpload = z8_file_from_upload(""w, []);
    auto copiedEmpty = z8_primary_cast!Z8File(z8_primary_from_protobuf(z8_parse_protobuf_primary(z8_serialize_protobuf_primary(z8_primary_to_protobuf(z8_primary_box(emptyUpload))))));
    assert(z8_file_has_upload(copiedEmpty) && z8_file_upload_snapshot(copiedEmpty, 0).length == 0);
    auto customRegistry = new Z8CustomPrimaryRegistry(); customRegistry.register(new Codec()); customRegistry.register(new BadCodec());
    auto customWire = z8_parse_protobuf_primary(cast(const(ubyte)[])read(buildPath(dir, "custom.bin")));
    auto customValue = cast(Demo)z8_primary_from_protobuf(customWire, customRegistry).userValue;
    assert(customValue !is null && customValue.number == 42);
    write(buildPath(dir, "custom-d.bin"), z8_serialize_protobuf_primary(z8_primary_to_protobuf(z8_primary_box(customValue), customRegistry)));
    auto parsed = z8_parse_protobuf_primary(cast(const(ubyte)[])read(buildPath(dir, "decimal.bin")));
    write(buildPath(dir, "decimal-roundtrip.bin"), z8_serialize_protobuf_primary(parsed));
    emit("null", null); emit("integer", z8_primary_box(long.min)); emit("boolean", z8_primary_box(false));
    emit("decimal", z8_primary_box(decimal)); emit("text", z8_primary_box("Строка 🐘"w));
    emit("nan", z8_primary_box(z8_decimal_nan())); emit("empty", z8_primary_box(z8_string_new(""w)));
    emit("guid", z8_primary_box(new Z8Guid(0xFEDCBA9876543210UL, 0x8877665544332211UL)));
    emit("date", z8_primary_box(z8_date_from_ticks(1700000000123L))); emit("span", z8_primary_box(new Z8Datespan(long.min)));
    emit("geometry", z8_primary_box(geometry)); emit("empty-geometry", z8_primary_box(none));
    emit("file", z8_primary_box(metadata));
    auto memory = new Z8Binary([cast(ubyte)0, 1, 2, 255]); memory.name = z8_string_new(""w);
    ubyte[2] buffer; assert(z8_binary_read_chunk(memory, buffer[0 .. 1]) == [cast(ubyte)0]);
    emit("binary", z8_primary_box(memory)); assert(memory.position == 1);
    bool tooLarge; try { z8_binary_snapshot(memory, 2); } catch (Exception) { tooLarge = true; }
    assert(tooLarge && memory.position == 1);
    auto file = z8_binary_from_file(buildPath(dir, "stream.bin"));
    assert(z8_binary_read_chunk(file, buffer[]) == [cast(ubyte)10, 11]);
    emit("file-stream", z8_primary_box(file)); assert(z8_binary_remaining(file) == 2);
    assert(z8_binary_read_chunk(file, buffer[]) == [cast(ubyte)12, 13]); z8_binary_close(file);
    bool closed; try { z8_binary_snapshot(file, 100); } catch (Exception) { closed = true; } assert(closed);
    auto overridden = z8_parse_protobuf_primary([0x18, 0x01, 0x10, 0x00]);
    assert(overridden.kind == Z8ProtobufPrimaryKind.integer && overridden.integerValue == 0);
    bool rejected; try { z8_primary_from_protobuf(z8_parse_protobuf_primary([])); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    rejected = false; try { z8_primary_to_protobuf(z8_primary_box(new Z8Object())); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    rejected = false; try { z8_primary_from_protobuf(customWire); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
    rejected = false; try { customRegistry.register(new Codec()); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
    auto wrong = z8_parse_protobuf_primary([0x62, 0x0D, 0x0A, 0x0B, 'e', 'x', 'a', 'm', 'p', 'l', 'e', '.', 'B', 'a', 'd']);
    rejected = false; try { z8_primary_from_protobuf(wrong, customRegistry); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
    rejected = false; try { readValue("bad-file"); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
    auto invalidGeometry = z8_primary_to_protobuf(z8_primary_box(geometry)); invalidGeometry.geometryValue.srid = 3857;
    rejected = false; try { z8_primary_from_protobuf(invalidGeometry); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    Z8ProtobufPrimary invalidDate; invalidDate.kind = Z8ProtobufPrimaryKind.date; invalidDate.integerValue = long.max;
    rejected = false; try { z8_primary_from_protobuf(invalidDate); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    auto invalidDecimal = z8_primary_to_protobuf(z8_primary_box(decimal)); invalidDecimal.decimalValue.coefficient = "1e999999"w;
    rejected = false; try { z8_primary_from_protobuf(invalidDecimal); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
}
''', encoding="utf-8")
    exe = temp / ("primary.exe" if os.name == "nt" else "primary")
    subprocess.run(["dmd", "-I" + str(root / "protocol/source"), *import_args(), str(source),
                    str(root / "protocol/source/z8/protobuf/wire.d"), str(root / "protocol/source/z8/protobuf/guid.d"),
                    str(root / "protocol/source/z8/authority/file.d"), str(root / "protocol/source/z8/authority/custom_primary.d"),
                    str(root / "protocol/source/z8/authority/primary.d"), str(runtime), "-of=" + str(exe)], check=True)
    values = {
        "null": Primary(null_value=False), "integer": Primary(integer_value=-(1 << 63)),
        "boolean": Primary(boolean_value=False), "text": Primary(text_value="Строка 🐘"),
        "date": Primary(date_ticks=1700000000123), "span": Primary(datespan_milliseconds=-(1 << 63)),
        "decimal": Primary(), "guid": Primary(), "nan": Primary(), "empty": Primary(text_value=""),
        "geometry": Primary(), "empty-geometry": Primary(), "binary": Primary(), "file": Primary(), "custom": Primary(),
    }
    values["decimal"].decimal_value.coefficient = "-1234500"; values["decimal"].decimal_value.scale = 6
    values["decimal"].decimal_value.MergeFromString(b"\x20\x01")
    values["nan"].decimal_value.nan = True
    values["decimal"].MergeFromString(b"\x98\x06\x01")
    values["guid"].guid_value.most_significant_bits = 0xFEDCBA9876543210
    values["guid"].guid_value.least_significant_bits = 0x8877665544332211
    values["geometry"].geometry_value.ewkb_hex = (struct.pack("<BII", 1, 0x20000001, 4326) + struct.pack("<dd", 1.5, -2.5)).hex().upper()
    values["geometry"].geometry_value.srid = 4326
    values["empty-geometry"].geometry_value.srid = 3857
    values["binary"].binary_value.data = b"\x01\x02\xff"; values["binary"].binary_value.name = ""
    metadata = values["file"].file_value
    metadata.id.least_significant_bits = 7; metadata.user.least_significant_bits = 8
    metadata.name = ""; metadata.path = "folder/a.txt"; metadata.time_ticks = 1700000000123; metadata.size = 2
    detail = metadata.details.entries.add(); detail.key = "charset"; detail.value = "utf-8"
    detail = metadata.details.entries.add(); detail.null_key = True; detail.null_value = True
    metadata.upload = b"\x00\xff"
    values["custom"].custom_value.class_id = "example.Demo"; values["custom"].custom_value.payload = b"\x2a"
    bad_file = Primary(); bad_file.CopyFrom(values["file"]); bad_file.file_value.details.entries.add().CopyFrom(bad_file.file_value.details.entries[0])
    (temp / "bad-file.bin").write_bytes(bad_file.SerializeToString())
    (temp / "stream.bin").write_bytes(bytes([10, 11, 12, 13]))
    for name, value in values.items(): (temp / (name + ".bin")).write_bytes(value.SerializeToString())
    first, second = Primary(), Primary()
    first.decimal_value.coefficient = "-1234500"; first.decimal_value.MergeFromString(b"\x20\x01")
    second.decimal_value.scale = 6
    encoded_decimal = first.SerializeToString() + second.SerializeToString() + b"\x98\x06\x01"
    values["decimal"] = Primary.FromString(encoded_decimal)
    (temp / "decimal.bin").write_bytes(encoded_decimal)
    subprocess.run([str(exe), str(temp)], cwd=temp, check=True)
    for name, expected in values.items():
        actual = Primary.FromString((temp / (name + "-d.bin")).read_bytes())
        if name == "decimal":
            assert actual.decimal_value.coefficient == "-1234500" and actual.decimal_value.scale == 6
        else:
            assert actual == expected
    assert Primary.FromString((temp / "decimal-roundtrip.bin").read_bytes()) == values["decimal"]
    assert Primary.FromString((temp / "file-stream-d.bin").read_bytes()).binary_value.data == bytes([12, 13])
print("Protobuf primary values interoperate with Google's runtime")
