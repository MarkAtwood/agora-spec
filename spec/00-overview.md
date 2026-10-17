# Agora Protocol: Overview

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1–55 (header, Version Policy, §1).

# Agora Protocol Specification v0.2 (Draft)

**Version:** 0.2 (Draft)
**Date:** 2026-04-21
**Status:** Draft amendment incorporating DM Channel Type and Compliance Logging patch (§9.6, §17.1, §17.2, §17.5, §17.7, §17.8) and Enterprise Identity Provisioning (§2.5)

---

## Version Policy

All versioned protocol surfaces in this specification are at **v1** for the initial release. The version appears as a path prefix on HTTP endpoints (`/v1/agora/...`), as a topic prefix on gossip topics (`v1/agora/...`), in JSON-LD context URLs (`/ns/v1`), and in document `schemaVersion` fields.

A breaking change to any one surface increments only that surface's version; all other surfaces remain at their current version and are unaffected. Clients and relays MUST reject messages or connections whose version they do not support and MUST NOT silently coerce an unknown version to a known one.

Version negotiation is defined per surface:

- **Transport endpoints** — the URL path version is fixed at connection time; a client connects to `/v1/agora/wt` or `/v1/agora/ws` and the relay either accepts or returns HTTP 404/410.
- **Gossip topics** — the version is encoded in the topic string; v1 and v2 topics can coexist on the mesh simultaneously; a relay that supports both subscribes to both topic families.
- **JSON-LD documents** — the `schemaVersion` field carries the document schema version; processors that do not support the declared version MUST reject the document.
- **Client-relay handshake** — version negotiation occurs as part of the `ClientHello`/`RelayChallenge` exchange (§8.6).
- **Relay-to-relay Peer API** — the version is encoded in the URL path; a relay's manifest `capabilities` array declares which versions it supports.

---

## 1. Overview

*Binds: both.*

Agora is a decentralized, end-to-end encrypted, real-time group chat protocol. It is designed to support a user experience comparable to Discord — servers with hierarchical channels, presence indicators, typing notifications, voice/video conferencing — without any central authority owning identity, routing, or message storage. No company holds your keys, your membership lists, or your message history.

### Core Protocol Dependencies

| Dependency | Role |
|---|---|
| **RFC 9420 (MLS)** | Group key agreement and end-to-end encryption |
| **RFC 9750 (MLS Architecture)** | Informational architecture reference for MLS deployment concepts |
| **JSON-LD** | Typed, namespace-aware message framing |
| **libp2p gossipsub v1.1** | Peer discovery, room advertisement, live message fanout |
| **IPLD** | Content-addressed data model (CIDv1 dag-cbor); relay-hosted CAS for blob storage |
| **WebTransport (RFC 9000)** | Primary transport for browsers and native clients |
| **WebSocket (RFC 6455)** | Fallback transport, and the only transport available over Tor |

Agora does **not** define a central server. It defines a protocol that servers — called **Relays** — implement to form a federated, permissionless mesh. Users are not locked to any particular Relay. Relays gossip with each other. Clients may connect to multiple Relays simultaneously and reconcile state across them.

Agora defines no payment layer in this release. Commercial terms between a community and the relays it engages are outside the protocol.

### Design Principles

**Operator separation.** Operating the infrastructure is separate from operating the communications. Relays and other infrastructure services decide nothing about any community and MUST be replaceable without changing its identity, membership, history or policy; every authority over a community is held by the community's own operator and exercised with that operator's keys. This is Agora's first design principle, defined normatively in ARCHITECTURE.md, which governs wherever this specification conflicts with it.

**Relay blindness.** A conformant Relay deliberately cannot read message content, identify senders, or map channel tokens to channel identities or member lists. This is not just policy — it is a structural property of the protocol. A Relay operator served a subpoena should be able to honestly say they hold no useful data. Blindness limits what a Relay can know; operator separation limits what it can decide.

**Federated, not centralized.** Anyone can run a Relay. Any Relay that speaks the protocol can join the mesh. There is no registration, no whitelist, no governing authority over who participates.

**Content addressing.** All persistent state — messages, space definitions, profiles, channel history — is stored in IPFS/IPLD and addressed by content hash (CID). History is tamper-evident by construction. Two Relays storing the same message store the same CID; deduplication is automatic.

**MLS everywhere.** MLS (RFC 9420) is the sole key agreement mechanism. It provides forward secrecy, post-compromise security, and multi-device membership natively. Every channel is an MLS group. Signaling, moderation records, and compliance logs all flow through MLS-authenticated channels.

---

