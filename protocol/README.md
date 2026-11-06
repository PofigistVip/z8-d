# Interserver protocol

The Z8 authority's `userChanged` and `roleChanged` events have transport-neutral
Protocol Buffers messages in `proto/z8/authority/v1/notifications.proto`.
`Guid` stores the most and least significant 64-bit UUID words, independently
of a language's signed integer representation. The two event types have the
same wire layout but must be routed to their respective handlers.

`z8.authority.notifications` provides D encoding, decoding and application to a
`Z8SessionManager`; `z8.protobuf.wire` contains the necessary wire primitives.
`privileges.proto` and `z8.authority.privileges` represent default access and
the original, uncombined table, field and request overrides. Explicit denies
remain present. Conversion into runtime privileges rejects duplicate IDs and
entries without an ID or access; an omitted default grants nothing. The wire
representation preserves unknown fields and limits the number of entries.
`primary.proto` and `z8.authority.primary` encode null, integers, booleans,
decimals, strings, GUIDs, dates, durations, geometries, binary values and files. The `oneof` preserves the
difference between null and default scalar values. Decimal coefficient and
scale are preserved separately. Geometry carries EWKB and SRID. Binary values
copy the unread stream without advancing it, subject to the message size limit.
File metadata, details and in-memory upload contents are transferred; a file
path remains metadata and does not cause the sender to read that path.
User-defined primary values require an explicitly registered
`IZ8CustomPrimaryCodec` in a `Z8CustomPrimaryRegistry` supplied to the encoder
and decoder. The registry selects only approved class IDs and checks the class
returned by a codec. Codecs must validate their payloads and be thread-safe.
`session.proto` and `z8.authority.session` serialize a session ID, schema,
user and system identities, roles, entry points, privilege snapshots and typed
parameters. Optional identity strings distinguish null from empty; parameters
also distinguish null and empty keys and values. Decoding requires both users,
their IDs and privileges, and rejects duplicate parameter keys. Conversion to
runtime objects intentionally discards unknown fields; it is not a wire-message
proxy. A user-defined parameter without its registered codec causes the
operation to fail.
`service.proto` describes transport-independent login, authorization and change
notification operations. `z8.authority.messages` encodes and decodes the login,
authorization and session reply envelopes, including explicit empty passwords
and denied replies. It does not open sockets or choose an RPC implementation.
`Z8ProtobufAuthorityNotifier` implements the runtime's user and role notifier
interfaces and forwards encoded events to a host-provided
`IZ8AuthorityChangePublisher`. A receiving host dispatches them with
`z8_apply_authority_change` and the matching event kind.
`Z8PostgresHttpAuthority` accepts optional remote user and role notifiers, so
the protobuf notifier can forward local changes. Apply received messages to the
session manager directly to avoid sending the same event back to its origin.
Application rejects missing identifiers or empty schemas. The decoder accepts
and retains unknown fields, checks UTF-8, limits messages to 1 MiB, and handles
deprecated groups for forward compatibility. The wire representation follows
the [Protocol Buffers encoding guide](https://protobuf.dev/programming-guides/encoding/).

This is a serialization contract and local handler, not a network service.
Transport, endpoint authentication, delivery guarantees and the rest of the
original RMI interfaces remain to be implemented. Do not accept these messages
from an untrusted peer without an authenticated transport.

Run `python tests/protobuf_notifications.py`, `python tests/protobuf_privileges.py`,
`python tests/protobuf_primary.py` and `python tests/protobuf_session.py` to
cross-check serialization with Google's Python protobuf runtime; the tests require
the `protobuf` Python package. `python tests/protobuf_authority_messages.py`
checks the request/reply envelopes. `python tests/protobuf_schemas.py [protoc]`
compiles every `.proto` file and inspects the resulting descriptors.
