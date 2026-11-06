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
decimals, strings, GUIDs, dates and durations. The `oneof` preserves the
difference between null and default scalar values. Decimal coefficient and
scale are preserved separately. Binary, geometry, file and user-defined primary
values are currently rejected instead of being silently dropped.
`session.proto` and `z8.authority.session` serialize a session ID, schema,
user and system identities, roles, entry points, privilege snapshots and typed
parameters. Optional identity strings distinguish null from empty; parameters
also distinguish null and empty keys and values. Decoding requires both users,
their IDs and privileges, and rejects duplicate parameter keys. Conversion to
runtime objects intentionally discards unknown fields; it is not a wire-message
proxy. Parameters using the primary types listed above as unsupported cause the
operation to fail.
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
the `protobuf` Python package.
