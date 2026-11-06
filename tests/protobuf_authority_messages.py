"""Check authority request/reply envelopes with Google's protobuf runtime."""
from pathlib import Path
import os
import subprocess
import tempfile
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from runtime_support import import_args, runtime_library

root = Path(__file__).resolve().parents[1]
schema = (root / "protocol/proto/z8/authority/v1/service.proto").read_text(encoding="utf-8")
for declaration in ("optional string password = 2;", "SessionSnapshot session = 1;", "bool access_denied = 2;",
                    "rpc Login(LoginRequest) returns (SessionReply);", "rpc Authorize(AuthorizeRequest) returns (SessionReply);"):
    assert declaration in schema
session_file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/session.proto", package="z8.authority.v1", syntax="proto3")
session = session_file.message_type.add(name="SessionSnapshot")
session.field.add(name="session_id", number=1, label=1, type=9); session.field.add(name="schema", number=2, label=1, type=9)
file = descriptor_pb2.FileDescriptorProto(name="z8/authority/v1/service.proto", package="z8.authority.v1", syntax="proto3")
file.dependency.append(session_file.name)
login = file.message_type.add(name="LoginRequest")
login.field.add(name="login", number=1, label=1, type=9)
for name, number in (("password", 2), ("address", 4)):
    index = len(login.oneof_decl); login.oneof_decl.add(name="_" + name)
    login.field.add(name=name, number=number, label=1, type=9, proto3_optional=True, oneof_index=index)
login.field.add(name="schema", number=3, label=1, type=9)
authorize = file.message_type.add(name="AuthorizeRequest")
authorize.field.add(name="session_id", number=1, label=1, type=9); authorize.field.add(name="schema", number=2, label=1, type=9)
authorize.oneof_decl.add(name="_server_id")
authorize.field.add(name="server_id", number=3, label=1, type=9, proto3_optional=True, oneof_index=0)
reply = file.message_type.add(name="SessionReply"); reply.oneof_decl.add(name="result")
reply.field.add(name="session", number=1, label=1, type=11, type_name=".z8.authority.v1.SessionSnapshot", oneof_index=0)
reply.field.add(name="access_denied", number=2, label=1, type=8, oneof_index=0)
pool = descriptor_pool.DescriptorPool(); pool.Add(session_file); pool.Add(file)
Login = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.LoginRequest"))
Authorize = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.AuthorizeRequest"))
Reply = message_factory.GetMessageClass(pool.FindMessageTypeByName("z8.authority.v1.SessionReply"))

with tempfile.TemporaryDirectory() as directory, runtime_library() as runtime:
    temp = Path(directory); source = temp / "main.d"
    source.write_text('''
import z8.runtime;
import z8.authority.messages;
import z8.authority.session;
import z8.protobuf.wire;
import std.file : read, write;
import std.path : buildPath;
void main(string[] args) {
    auto dir = args[1];
    if (args[2] == "generate") {
        write(buildPath(dir, "d-login.bin"), z8_encode_authority_login(Z8AuthorityLogin("Alice"w, ""w, "схема"w, "127.0.0.1"w)));
        write(buildPath(dir, "d-authorize.bin"), z8_encode_authority_authorize(Z8AuthorityAuthorize("token"w, "схема"w, ""w)));
        auto user = new Z8UserData(); user.id = z8_guid_create(42); user.privileges = new Z8Privileges();
        auto system = new Z8UserData(); system.id = z8_guid_create(1); system.privileges = new Z8Privileges();
        Z8AuthoritySessionReply reply; reply.session = Z8SessionSnapshot("схема"w, new Z8ApplicationSession("token"w, user, system));
        write(buildPath(dir, "d-reply.bin"), z8_encode_authority_reply(reply));
        Z8AuthoritySessionReply denied; denied.denied = true;
        write(buildPath(dir, "d-denied.bin"), z8_encode_authority_reply(denied));
        return;
    }
    auto login = z8_decode_authority_login(cast(const(ubyte)[])read(buildPath(dir, "login.bin")));
    assert(login.login == "Alice"w && login.schema == "схема"w && login.password !is null && !login.password.length && login.address is null);
    auto request = z8_decode_authority_authorize(cast(const(ubyte)[])read(buildPath(dir, "authorize.bin")));
    assert(request.sessionId == "token"w && request.schema == "схема"w && request.serverId !is null && !request.serverId.length);
    auto reply = z8_decode_authority_reply(cast(const(ubyte)[])read(buildPath(dir, "reply.bin")));
    assert(!reply.denied && reply.session.session.id == "token"w && reply.session.session.user.id == z8_guid_create(42));
    assert(z8_decode_authority_reply(cast(const(ubyte)[])read(buildPath(dir, "denied.bin"))).denied);
    bool rejected;
    try { z8_decode_authority_login(cast(const(ubyte)[])read(buildPath(dir, "missing-password.bin"))); } catch (Z8ProtobufException) { rejected = true; }
    assert(rejected);
    rejected = false; try { z8_decode_authority_reply([]); } catch (Z8ProtobufException) { rejected = true; } assert(rejected);
}
''', encoding="utf-8")
    exe = temp / ("messages.exe" if os.name == "nt" else "messages")
    modules = ("z8/protobuf/wire.d", "z8/protobuf/guid.d", "z8/authority/file.d", "z8/authority/custom_primary.d",
               "z8/authority/primary.d", "z8/authority/privileges.d", "z8/authority/session.d", "z8/authority/messages.d")
    subprocess.run(["dmd", "-I" + str(root / "protocol/source"), *import_args(), str(source),
                    *[str(root / "protocol/source" / module) for module in modules], str(runtime), "-of=" + str(exe)], check=True)
    subprocess.run([str(exe), str(temp), "generate"], cwd=temp, check=True)
    decoded_login = Login.FromString((temp / "d-login.bin").read_bytes())
    assert decoded_login.login == "Alice" and decoded_login.schema == "схема" and decoded_login.HasField("password") and decoded_login.password == ""
    decoded_authorize = Authorize.FromString((temp / "d-authorize.bin").read_bytes())
    assert decoded_authorize.session_id == "token" and decoded_authorize.HasField("server_id") and decoded_authorize.server_id == ""
    decoded_reply = Reply.FromString((temp / "d-reply.bin").read_bytes())
    assert decoded_reply.WhichOneof("result") == "session" and decoded_reply.session.session_id == "token"
    assert Reply.FromString((temp / "d-denied.bin").read_bytes()).access_denied
    (temp / "login.bin").write_bytes(Login(login="Alice", password="", schema="схема").SerializeToString())
    (temp / "missing-password.bin").write_bytes(Login(login="Alice", schema="схема").SerializeToString())
    (temp / "authorize.bin").write_bytes(Authorize(session_id="token", schema="схема", server_id="").SerializeToString())
    # A later oneof member overrides an earlier one; preserve unknown session fields.
    (temp / "reply.bin").write_bytes(Reply(access_denied=False).SerializeToString() + decoded_reply.SerializeToString())
    (temp / "denied.bin").write_bytes(Reply(access_denied=False).SerializeToString())
    subprocess.run([str(exe), str(temp), "verify"], cwd=temp, check=True)
print("Protobuf authority messages interoperate with Google's runtime")
