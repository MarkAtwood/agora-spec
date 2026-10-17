# 1. Overview

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1–55 (header, Version Policy, §1).

**Agora Protocol Specification v0.2 (Draft)**

**Version:** 0.2 (Draft)
**Date:** 2026-04-21
**Status:** Draft amendment incorporating DM Channel Type and Compliance Logging patch (§4.6, §7.1, §7.2, §7.5, §7.7, §7.8) and Enterprise Identity Provisioning (§2.5)

---

## 1.1 Version Policy

All versioned protocol surfaces in this specification are at **v1** for the initial release. The version appears as a path prefix on HTTP endpoints (`/v1/agora/...`), as a topic prefix on gossip topics (`v1/agora/...`), and in document `schemaVersion` fields.

A breaking change to any one surface increments only that surface's version; all other surfaces remain at their current version and are unaffected. Clients and relays MUST reject messages or connections whose version they do not support and MUST NOT silently coerce an unknown version to a known one.

Version negotiation is defined per surface:

- **Transport endpoints:** the URL path version is fixed at connection time; a client connects to `/v1/agora/wt` or `/v1/agora/ws` and the relay either accepts or returns HTTP 404 (§13.2).
- **Gossip topics:** the version is encoded in the topic string; v1 and v2 topics can coexist on the mesh simultaneously; a relay that supports both subscribes to both topic families.
- **Documents:** the `schemaVersion` field carries the document schema version; processors that do not support the declared version MUST reject the document.
- **Client-relay handshake:** version negotiation occurs as part of the `ClientHello`/`RelayHello` exchange (§11.6).
- **Relay-to-relay Peer API:** the version is encoded in the URL path; a relay's manifest `capabilities` array declares which versions it supports.

---

## 1.2 Introduction

*Binds: both.*

Agora is a decentralized, end-to-end encrypted, real-time group chat protocol. It is designed to support a user experience comparable to Discord (servers with hierarchical channels, presence indicators, typing notifications, voice/video conferencing) without any central authority owning identity, routing, or message storage. No company holds your keys, your membership lists, or your message history.

### 1.2.1 Core Protocol Dependencies

| Dependency | Role |
|---|---|
| **RFC 9420 (MLS)** | Group key agreement and end-to-end encryption |
| **RFC 9750 (MLS Architecture)** | Informational architecture reference for MLS deployment concepts |
| **JSON (RFC 8259)** | Payload bodies in the typed envelope (§13.1); JSON-LD is an optional content type |
| **libp2p gossipsub v1.1** | Peer discovery, room advertisement, live message fanout |
| **IPLD** | Content-addressed data model (CIDv1 dag-cbor); relay-hosted CAS for blob storage |
| **WebTransport (RFC 9000)** | Primary transport for browsers and native clients |
| **WebSocket (RFC 6455)** | Fallback transport, and the only transport available over Tor |

Agora does **not** define a central server. It defines a protocol that servers, called **Relays**, implement to form a federated, permissionless mesh. Users are not locked to any particular Relay. Relays gossip with each other. Clients may connect to multiple Relays simultaneously and reconcile state across them.

Agora defines no payment layer in this release. Commercial terms between a community and the relays it engages are outside the protocol.

### 1.2.2 Design Principles

**Operator separation.** Operating the infrastructure is separate from operating the communications. Relays and other infrastructure services decide nothing about any community and MUST be replaceable without changing its identity, membership, history or policy; every authority over a community is held by the community's own operator and exercised with that operator's keys. This is Agora's first design principle, defined normatively in ARCHITECTURE.md, which governs wherever this specification conflicts with it.

**Relay blindness.** A conformant Relay deliberately cannot read message content, identify senders, or map channel tokens to channel identities or member lists. This is a structural property of the protocol. A Relay operator served a subpoena should be able to say truthfully that they hold no useful data. Blindness limits what a Relay can know; operator separation limits what it can decide.

**Federation.** Anyone can run a Relay. Any Relay that speaks the protocol can join the mesh. There is no registration, no whitelist, no governing authority over who participates.

**Content addressing.** All persistent state (messages, space definitions, profiles, channel history) is stored in IPFS/IPLD and addressed by content hash (CID). History is therefore tamper-evident. Two Relays storing the same message store the same CID; deduplication is automatic.

**MLS everywhere.** MLS (RFC 9420) is the sole key agreement mechanism. It provides forward secrecy, post-compromise security, and multi-device membership natively. Every channel is an MLS group. Signaling, moderation records, and compliance logs all flow through MLS-authenticated channels.

---

## 1.3 Requirements Language

*Binds: both.*

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY and OPTIONAL in this specification are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

## 1.4 Conformance Classes

*Binds: both.*

An implementation claims conformance to one or more of the classes below. A conformant implementation of a class MUST implement every requirement that the listed sections place on that class, and MUST also meet §1.1, §12.9 and §13.1. "Conformant client" and "conformant Relay" elsewhere in this specification mean the Client and Relay classes defined here. The IO or CO role of each class follows ARCHITECTURE.md §2.3.

| Class | Role | MUST implement |
|---|---|---|
| Client | Member endpoint | §2.1, §2.2 (DID resolution, device keys); §3.3 to §3.5 (Space state validation and retrieval, member authentication); §4 (authority checks, invites, moderation, DMs); §5.1, §5.2.1 to §5.2.8, §5.3 (MLS groups in every channel mode, envelopes, message types, expiry, history, pins, text, reactions, presence); §7.2, §7.5, §7.7 (adding the logger, expiry under logging, member disclosure); §8.4, §8.8 (guest admission and retention notice); §9.3 (gateway indicators); §11.1 or §11.2, §11.4, §11.6 (transport and hello); §12.6 (key storage); §12.10 (disclosure accessibility); §14.2 to §14.4 (consistency models and validation) |
| Calls profile | Member endpoint | Client, plus §6 except the recorder-side formats of §6.12.4 and §6.12.6 |
| Regulated-member profile | Member endpoint, CO enforcement point | Client, plus every row of the §7.8 Conformance Summary that applies to the regulated member's client or the committing client; with the Calls profile, also §6.12.5 and §6.12.7 |
| Relay | IO | §10.4.3 and the sections it cites, §10.4.4 |
| Registration service | CO | §5.2.2 (Epoch Access Proof), §10.5.1, §12.8 |
| Space endpoint | CO | §3.4, §3.5, §4.3 (invite checks), §4.4 (public view), §5.2.1.4 (`BroadcastKey` service), §12.8 |
| KeyPackage host | CO | §2.1 (endpoint publication), §4.6 (Welcome intake), §5.2.1.1, §12.8 |
| Provisioning service | CO | §2.5, the KeyPackage host class for the identities it runs (§5.2.1.1), §12.8 |
| Compliance logger | CO | §5.2.1.3, §7.3, §7.4, §7.5, §7.8.2, §7.8.8, §7.8.9, the KeyPackage host class for its own DID, §12.8 |
| Compliance recorder | CO | §6.12.1 to §6.12.6, §12.8 |
| TURN credential service | CO | §6.11 (TURN Credentials), §3.5, §12.8 |
| Sequencer | IO | §14.4 |
| SFU | IO | §6.6, §6.9, §6.10 |
| Push proxy | IO | §11.7 |

The Calls and Regulated-member profiles are client classes: a client claims them in addition to Client. A component that is not listed has no conformance definition in this version. A deployment MAY implement several classes; it then meets each class's requirements separately, and ARCHITECTURE.md §2.4 still applies.

**Enforcement-relevant fields.** Recipients ignore Space state extension fields they do not understand (§13.2). A field on which a CO enforcement point (ARCHITECTURE.md §6.3) depends, such as a new retention or capture rule, therefore MUST NOT be introduced as an extension field. It is introduced only with a new Space state `schemaVersion`, which clients that do not support it reject (§1.1).

---

