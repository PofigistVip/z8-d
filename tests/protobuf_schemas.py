"""Compile all protocol schemas with protoc and inspect their descriptors."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from google.protobuf import descriptor_pb2, descriptor_pool

if len(sys.argv) > 2:
    raise SystemExit("Usage: python tests/protobuf_schemas.py [protoc-path]")
protoc = sys.argv[1] if len(sys.argv) == 2 else shutil.which("protoc")
if not protoc:
    raise SystemExit("protoc not found; pass its path explicitly")
root = Path(__file__).resolve().parents[1] / "protocol/proto"
files = sorted(root.rglob("*.proto"))
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "schemas.pb"
    subprocess.run([protoc, "--experimental_allow_proto3_optional", "--include_imports", "--proto_path=" + str(root),
                    "--descriptor_set_out=" + str(output), *map(str, files)], check=True)
    descriptors = descriptor_pb2.FileDescriptorSet.FromString(output.read_bytes())
    pool = descriptor_pool.DescriptorPool()
    for file in descriptors.file: pool.AddSerializedFile(file.SerializeToString())
    service = pool.FindServiceByName("z8.authority.v1.Authority")
    assert [(m.name, m.input_type.name, m.output_type.name) for m in service.methods] == [
        ("Login", "LoginRequest", "SessionReply"), ("Authorize", "AuthorizeRequest", "SessionReply"),
        ("UserChanged", "UserChanged", "Empty"), ("RoleChanged", "RoleChanged", "Empty")]
    login = pool.FindMessageTypeByName("z8.authority.v1.LoginRequest")
    assert login.fields_by_name["password"].has_presence and login.fields_by_name["password"].number == 2
    session = pool.FindMessageTypeByName("z8.authority.v1.SessionSnapshot")
    assert session.fields_by_name["user"].number == 3 and session.fields_by_name["system"].number == 4
    primary = pool.FindMessageTypeByName("z8.authority.v1.Primary")
    assert [(f.name, f.number) for f in primary.oneofs_by_name["value"].fields][-4:] == [
        ("geometry_value", 9), ("binary_value", 10), ("file_value", 11), ("custom_value", 12)]
print(f"Compiled {len(descriptors.file)} protobuf schemas")
