# Interserver protocol

The Z8 authority's `userChanged` and `roleChanged` events have transport-neutral
Protocol Buffers messages in `proto/z8/authority/v1/notifications.proto`.
`Guid` stores the most and least significant 64-bit UUID words, independently
of a language's signed integer representation. The two event types have the
same wire layout but must be routed to their respective handlers.

`z8.authority.notifications` provides D encoding, decoding and application to a
`Z8SessionManager`; `z8.protobuf.wire` contains the necessary wire primitives.
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

Run `python tests/protobuf_notifications.py` to cross-check serialization with
Google's Python protobuf runtime; the test requires the `protobuf` Python package.
