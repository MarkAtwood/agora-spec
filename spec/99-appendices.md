# Appendices

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 4084–4139 (Appendices A, B).

## Appendix A: Dependency Summary

| Component | Specification | Reference Implementation |
|---|---|---|
| E2EE group key management | RFC 9420 (MLS) | `openmls` (Rust), `mlspp` (C++) |
| Payload envelope | Typed payload envelope (§13.1), CBOR (RFC 8949) | See Wire encoding |
| Identity | W3C DID Core; user DID methods in the rows below; `did:web` for relay DIDs only (§10.2.1) | `ssi` (Rust), `go-did` (Go) |
| Content addressing | IPFS / IPLD (CIDv1, `raw` codec, sha2-256, §13.1) | `go-ipfs`, `helia` (JS), `rust-ipfs` |
| Peer discovery / fanout | libp2p gossipsub v1.1 | `go-libp2p-pubsub`, `libp2p` (Rust) |
| Primary transport | WebTransport (RFC 9000) | Native browser; `webtransport-go`, `wtransport` (Rust) |
| Fallback transport | WebSocket (RFC 6455) | Native in all environments |
| Voice/video media | WebRTC | Native browser; `pion` (Go) |
| SFU | WebRTC SFU | `mediasoup`, `Pion ion-sfu`, `LiveKit` |
| TURN relay | RFC 5766 / RFC 7065 | `coturn` |
| Wire encoding | CBOR (RFC 8949) | `fxamacker/cbor` (Go), `cbor2` (Python) |
| Relay-to-relay auth | RFC 9421 HTTP Message Signatures | `httpsig` (Go), `httpbis-message-signatures` (JS) |
| Ed25519 / X25519 | RFC 8032 / RFC 7748 | Native in all major crypto libraries |
| Argon2id KDF | RFC 9106 | `golang.org/x/crypto/argon2`, `argon2` crate |
| Shamir Secret Sharing | None | `hashicorp/vault` shamir (Go), `sharks` (Rust) |
| Spam deterrence (proof-of-work) | Hashcash-style PoW | SHA-256 (standard library) |
| Native cross-system interop | MIMI (drafts; delivery layer stalled as of 2026-04) | TBD (spec in progress) |
| Matrix gateway | Matrix Application Service API | `mautrix-go`, `mautrix-python` |
| Relay bootstrap DNS | DNS-SD / SRV / TXT records | Standard DNS libraries |
| Object signatures | JWS (RFC 7515), unencoded detached payload (RFC 7797), EdDSA/Ed25519 in JOSE (RFC 8037) | `jose` (JS); any JOSE library supporting RFC 7797 |
| Chat and collaboration data model | JMAP Core (RFC 8620); JMAP Chat (draft-atwood-jmap-chat-00) and companion drafts (chat-did, chat-push, chat-wss, chat-calendars, chat-tasks, chat-filenode, jmap-did, jmap-cid, scene, scene-wss, vtc, vtc-wss) | TBD (drafts in progress) |
| Default user DID method | `did:webvh` (DIF did:webvh specification) | `didwebvh-py`, `didwebvh-ts` |
| Opt-in user DID method | `did:plc` (did:plc specification v0.1) | `did-method-plc` (TS, Bluesky) |
| `did:key` pointer records | Pkarr (BEP-44 mutable items on the Mainline DHT) | `pkarr` (Rust) |

---

## Appendix B: Open Questions

1. **Cross-space identity and reputation**: there is currently no mechanism for carrying moderation history or reputation across Space boundaries. A user banned from one Space can freely join another. Whether this is a feature (clean-slate by design, prevents monoculture moderation) or a gap (enables bad actors to evade consequences) depends on use case. A voluntary cross-space reputation attestation format is worth considering as an optional extension.

---

## Appendix C: Protocol Limits

This table collects the protocol's numeric limits in one place. The defining section governs; if this table and a defining section disagree, the defining section is correct and the table is an erratum. "Example" means the value appears only in an example and is not normative.

| Limit | Value | Strength | Defined in |
|---|---|---|---|
| Members of an `interactive` channel group | 200 | Fixed | §3.2, §5.2.1 |
| Community speaker group (`speakerCap`) | default 200, maximum 500 | Default; maximum MUST NOT be exceeded | §5.2.1.2 |
| Idle speaker eviction (`idleEvictDays`) | default 7 days | Default | §5.2.1.2 |
| Pinned items per channel (`pinLimit`) | default 50 | Default | §5.2.6 |
| Registered devices per employee | default 10 | Org-configured default | §2.5.4 |
| Last-resort KeyPackages | 1 per device | SHOULD | §5.2.1.1 |
| DM member-addition consent | unanimous for 2 to 4 members, majority for 5 or more | Default | §4.6.1 |
| Invite code entropy | at least 128 bits | MUST | §4.3 |
| Custom emoji `name` | 32 characters | MUST | §5.2.8.4 |
| Envelope size (`maxEnvelopeBytes`) | 65536 bytes | Example only | §11.8.3 |
| Attachment size (`maxAttachmentBytes`) | 100 MiB | Example only | §11.8.3 |
| Pkarr record | 1000 bytes | MUST | §10.3.4.6 |
| Directory `includes` depth | 3 | MUST | §10.3.4.1 |
| Messages per `BroadcastKey` | fewer than 2^32 | MUST | §5.2.1.4 |
| `BroadcastKey` rotation | at least every 30 days | SHOULD | §5.2.1.4 |
| MLS epoch lifetime | 7 days maximum | Recommended | §12.2 |
| Presence re-send; offline after silence | 30 s; 60 s | MUST; descriptive | §5.3.1 |
| Typing events; indicator clear | at most 1 per 3 s; 10 s | Descriptive; SHOULD | §5.3.2 |
| `ParticipantState` republish | every `ttl / 2` | MUST | §6.2 |
| Ring duration | 120 s after receipt | MUST NOT exceed | §6.14.1 |
| `RecordingGrant` grace after call end | default 5 min | Default | §6.12.5 |
| Data channel message rate | 10 to 60 per second | See section | §6.13 |
| Mesh call size before SFU | 4 participants | Recommended | §6.5 |
| Relay-to-relay timestamp window; nonce cache | 300 s; 600 s | MUST | §10.2.3 |
| Member authentication `ts` window; replay cache; bearer token lifetime | 300 s; 600 s; at most 1 h | MUST | §3.5 |
| Clock skew tolerance for start times | 300 s | MUST | §12.9 |
| Peer health poll; unreachable after | 60 s; 3 misses | MUST | §10.2.6 |
| Relay key rotation overlap | at least 48 h | MUST | §10.2.6 |
| `SpaceAd` TTL; re-advertise | 60 s; 45 s | Default | §10.3.2 |
| Directory refresh | 1 h | Default | §10.3.4 |
| Relay envelope cache | lesser of `expiryHint` and the retention window (default 30 days) | MUST | §10.4.3 |
| Push registration TTL | default 30 days | Default; renewal MUST | §11.7.3 |
| Push wake-ups per handle | 1 per 5 s, burst 3 | SHOULD (example values) | §11.7.5 |
| Second `RecoveryAssertion` for one DID | not within 24 h without admin review | MUST NOT | §2.4.4 |
| Per-`channelToken` publication rate | Relay local policy, no floor | MUST enforce | §11.6, §12.5 |

This version defines no limit for: DM group size, Space state document size, envelope size on the live stream and gossip, KeyPackage batch size, message body length, channel count per Space, TURN credential lifetime, or a minimum rate that a Relay must admit per `channelToken`.

---

## Appendix D: Registries and Identifiers

This appendix lists the identifiers this specification allocates. "IANA" names the registry in which an entry is required for interoperability outside Agora; "Agora-internal" means this specification is the only allocation authority and no external registration is needed. The `urn:agora:` URN namespace is treated as registered.

**Derivation labels.** §13.3 lists every MLS exporter label, KDF `info` string and AEAD associated-data prefix. The entries of kind "MLS exporter" are MLS exporter labels and need entries in the IANA "MLS Exporter Labels" registry (RFC 9420 §17). The other entries are Agora-internal.

**MLS credential types.** `AgoraMIMICredential` (§9.1) has no MLS credential type codepoint yet. Interoperating with MIMI providers requires one from the IANA "MLS Credential Types" registry, or use of a credential type MIMI defines.

**MLS extension types.** `agora_admission_host` (0xF0A0, GroupContext, §4.6) and `agora_device_binding` (0xF0A1, LeafNode, §5.2.1) use the RFC 9420 private-use range and need no IANA registration.

**URN namespaces.**

| Namespace | Use | Defined in | Registration |
|---|---|---|---|
| `urn:agora:type:` | Payload type URIs | §13.1, §13.2, §5.2.3 | Agora-internal under `urn:agora:` |
| `urn:agora:v1` | JMAP capability | §11.8.3 | IANA "JMAP Capabilities" (RFC 8620 §9.4) |
| `urn:ietf:params:jmap:*` | JMAP family types | External drafts, profiled in §14.6 | Defined by those drafts |

**Capability and model strings** (Agora-internal).

| Strings | Use | Defined in |
|---|---|---|
| `gossipsub-v1.1`, `gossipsub-quic-v1`, `peer-api-h3`, `tor-hidden-service-v1`, `sfu-v1`, `peer-api-v1`, `jmap-sync-v1`, `push-proxy-v1`, `sequencer-v1` | Relay manifest `capabilities` | §10.2.1 |
| `single-author`, `sequenced-v1` | Consistency model identifiers | §14.2.1 |
| `text/markdown;variant=commonmark`, `text/markdown;variant=gfm`, `text/plain`, `application/jmap-chat-rich` | `bodyType` values | §5.2.7.2 |
| `co-issued` | TURN `credentialScheme` | §6.11 |
| `pow` | Proof-of-work scheme | §10.5.2 |

**DID service types.** Entries in the W3C DID Specification Registries are needed for resolvers outside Agora to recognize them.

| `type` | Defined in |
|---|---|
| `AgoraKeyPackageEndpoint` | §2.1, §5.2.1.1 |
| `AgoraProfile` | §2.3 |
| `AgoraSpaceEndpoint` | §3.4 |
| `AgoraComplianceLogger` | §7.3 |
| `AgoraMatrixGateway` | §9.2 |
| `AgoraTextFormatCapabilities` | §5.2.7.4 |

**Web and DNS identifiers.**

| Identifier | Defined in | Registration |
|---|---|---|
| Well-known URI `agora-relay` | §10.2.1 | IANA "Well-Known URIs" (RFC 8615) |
| Service name `agora-relay` (`_agora-relay._udp`, `_agora-relay._tcp`) | §10.2.5, §10.3.3 | IANA "Service Name and Transport Protocol Port Number" (RFC 6335) |
| `_agora` and its children `_kp._agora`, `_profile._agora` | §2.1, §10.3.4.6 | IANA "Underscored and Globally Scoped DNS Node Names" (RFC 8552), for `_agora` |
| HTTP field `Agora-Storage-Auth` | §11.8.2 | IANA "HTTP Field Name" (RFC 9110 §16.3) |
| JWS header parameter `agoraType` | §13.1.1 | IANA "JSON Web Signature and Encryption Header Parameters" (RFC 7515 §4.3) |
| URI scheme `agora` | §3.2 | IANA "Uniform Resource Identifier (URI) Schemes" (RFC 7595) |
| HTTP path prefix `/v1/agora/`, gossip topics `v1/agora/...`, IPNS name `/ipns/agora.protocol/relays/v1` | §1.1, §10.3.1, §10.2.5 | Agora-internal |

---

*End of specification.*
