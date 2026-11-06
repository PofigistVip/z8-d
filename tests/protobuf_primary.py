"""Cross-check typed BL primary values with Google's protobuf runtime."""
from pathlib import Path
import os
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
file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/primary.proto", package="z8.authority.v1", syntax="proto3")
file.dependency.append(common.name)
decimal = file.message_type.add(name="Decimal")
decimal.field.add(name="coefficient", number=1, label=1, type=9)
decimal.field.add(name="scale", number=2, label=1, type=17)
decimal.field.add(name="nan", number=3, label=1, type=8)
primary = file.message_type.add(name="Primary"); primary.oneof_decl.add(name="value")
for number, (name, kind, type_name) in enumerate((
    ("null_value", 8, None), ("integer_value", 18, None), ("boolean_value", 8, None),
    ("decimal_value", 11, ".z8.authority.v1.Decimal"), ("text_value", 9, None),
    ("guid_value", 11, ".z8.authority.v1.Guid"), ("date_ticks", 18, None),
    ("datespan_milliseconds", 18, None)), 1):
    field = primary.field.add(name=name, number=number, label=1, type=kind, oneof_index=0)
    if type_name: field.type_name = type_name
pool = descriptor_pool.DescriptorPool(); pool.Add(common); pool.Add(file)
Primary = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.Primary"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory)
    source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.primary;
import z8.protobuf.wire;
import std.file : read, write;
import std.path : buildPath;
import std.bigint : BigInt;
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
    auto parsed = z8_parse_protobuf_primary(cast(const(ubyte)[])read(buildPath(dir, "decimal.bin")));
    write(buildPath(dir, "decimal-roundtrip.bin"), z8_serialize_protobuf_primary(parsed));
    emit("null", null); emit("integer", z8_primary_box(long.min)); emit("boolean", z8_primary_box(false));
    emit("decimal", z8_primary_box(decimal)); emit("text", z8_primary_box("Строка 🐘"w));
    emit("nan", z8_primary_box(z8_decimal_nan())); emit("empty", z8_primary_box(z8_string_new(""w)));
    emit("guid", z8_primary_box(new Z8Guid(0xFEDCBA9876543210UL, 0x8877665544332211UL)));
    emit("date", z8_primary_box(z8_date_from_ticks(1700000000123L))); emit("span", z8_primary_box(new Z8Datespan(long.min)));
    auto overridden = z8_parse_protobuf_primary([0x18, 0x01, 0x10, 0x00]);
    assert(overridden.kind == Z8ProtobufPrimaryKind.integer && overridden.integerValue == 0);
    bool rejected; try { z8_primary_from_protobuf(z8_parse_protobuf_primary([])); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    rejected = false; try { z8_primary_to_protobuf(z8_primary_box(new Z8Binary())); } catch (Z8ProtobufException) { rejected = true; }
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
                    str(root / "protocol/source/z8/authority/primary.d"), str(runtime), "-of=" + str(exe)], check=True)
    values = {
        "null": Primary(null_value=False), "integer": Primary(integer_value=-(1 << 63)),
        "boolean": Primary(boolean_value=False), "text": Primary(text_value="Строка 🐘"),
        "date": Primary(date_ticks=1700000000123), "span": Primary(datespan_milliseconds=-(1 << 63)),
        "decimal": Primary(), "guid": Primary(), "nan": Primary(), "empty": Primary(text_value=""),
    }
    values["decimal"].decimal_value.coefficient = "-1234500"; values["decimal"].decimal_value.scale = 6
    values["decimal"].decimal_value.MergeFromString(b"\x20\x01")
    values["nan"].decimal_value.nan = True
    values["decimal"].MergeFromString(b"\x98\x06\x01")
    values["guid"].guid_value.most_significant_bits = 0xFEDCBA9876543210
    values["guid"].guid_value.least_significant_bits = 0x8877665544332211
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
print("Protobuf primary values interoperate with Google's runtime")
