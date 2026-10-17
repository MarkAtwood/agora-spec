# Appendices

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 4084–4139 (Appendices A, B).

## Appendix A: Dependency Summary

| Component | Specification | Reference Implementation |
|---|---|---|
| E2EE group key management | RFC 9420 (MLS) | `openmls` (Rust), `mlspp` (C++) |
| Payload envelope | Typed payload envelope (§13.1), CBOR (RFC 8949) | See Wire encoding |
| Identity | W3C DID Core; user DID methods in the rows below; `did:web` for relay DIDs only (§10.2.1) | `ssi` (Rust), `go-did` (Go) |
| Default user DID method | `did:webvh` (DIF did:webvh specification) | `didwebvh-py`, `didwebvh-ts` |
| Opt-in user DID method | `did:plc` (did:plc specification v0.1) | `did-method-plc` (TS, Bluesky) |
| `did:key` pointer records | Pkarr (BEP-44 mutable items on the Mainline DHT) | `pkarr` (Rust) |
| Content addressing | IPFS / IPLD (CIDv1, `raw` codec, sha2-256, §13.1) | `go-ipfs`, `helia` (JS), `rust-ipfs` |
| Peer discovery / fan-out | libp2p gossipsub v1.1 | `go-libp2p-pubsub`, `libp2p` (Rust) |
| Primary transport | WebTransport (RFC 9000) | Native browser; `webtransport-go`, `wtransport` (Rust) |
| Fallback transport | WebSocket (RFC 6455) | Native in all environments |
| Voice/video media | WebRTC | Native browser; `pion` (Go) |
| SFU | WebRTC Selective Forwarding Unit (SFU) | `mediasoup`, `Pion ion-sfu`, `LiveKit` |
| TURN relay | RFC 5766 / RFC 7065 | `coturn` |
| Wire encoding | CBOR (RFC 8949) | `fxamacker/cbor` (Go), `cbor2` (Python) |
| Relay-to-relay auth | RFC 9421 HTTP Message Signatures | `httpsig` (Go), `httpbis-message-signatures` (JS) |
| Ed25519 / X25519 | RFC 8032 / RFC 7748 | Native in all major crypto libraries |
| Argon2id KDF | RFC 9106 | `golang.org/x/crypto/argon2`, `argon2` crate |
| Shamir Secret Sharing | None | `hashicorp/vault` shamir (Go), `sharks` (Rust) |
| Spam deterrence (proof-of-work) | Hashcash-style PoW | SHA-256 (standard library) |
| Native cross-system interop | MIMI (drafts; future option, not specified, `profiles/gateways.md`) | None |
| Matrix gateway | Matrix Application Service API | `mautrix-go`, `mautrix-python` |
| Relay bootstrap DNS | DNS-SD / SRV / TXT records | Standard DNS libraries |
| Object signatures | JWS (RFC 7515), unencoded detached payload (RFC 7797), EdDSA/Ed25519 in JOSE (RFC 8037) | `jose` (JS); any JOSE library supporting RFC 7797 |
| Chat and collaboration data model | JMAP Core (RFC 8620); JMAP Chat (draft-atwood-jmap-chat-00) and companion drafts (chat-did, chat-push, chat-wss, chat-calendars, chat-tasks, chat-filenode, jmap-did, jmap-cid, scene, scene-wss, vtc, vtc-wss) | TBD (drafts in progress) |

---

## Appendix B: Open Questions

1. **Cross-Space identity and reputation.** There is currently no mechanism for carrying moderation history or reputation across Space boundaries. A user banned from one Space can freely join another. Whether this is a feature (clean-slate by design, prevents monoculture moderation) or a gap (enables bad actors to evade consequences) depends on use case. A voluntary cross-Space reputation attestation format is worth considering as an optional extension.

---

## Appendix C: Protocol Limits

This table collects the protocol's numeric limits in one place. If this table and a defining section disagree, the defining section governs and the table is an erratum. "Example" means the value appears only in an example and is not normative.

| Limit | Value | Strength | Defined in |
|---|---|---|---|
| Leaves in any MLS group, including direct message (DM) groups | 4096 | MUST NOT exceed | §5.2.1 |
| Members of an `interactive` channel group | 200 | Descriptive; the enforced cap is the 4096-leaf limit (§5.2.1) | §3.2, §5.2.1 |
| Community speaker group (`speakerCap`) | default 200, maximum 500 | Default; maximum MUST NOT be exceeded | §5.2.1.2 |
| Idle speaker eviction (`idleEvictDays`) | default 7 days | Default | §5.2.1.2 |
| Pinned items per channel (`pinLimit`) | default 50 | Default | §5.2.6 |
| Registered devices per employee | default 10 | Org-configured default | §2.5.4 |
| Last-resort KeyPackages | 1 per device | SHOULD | §5.2.1.1 |
| KeyPackage `lifetime` | 90 days maximum | MUST | §5.2.1 |
| Envelopes sealed per sending leaf per epoch | 2^20 | MUST NOT exceed | §5.2.2 |
| Invite code entropy | at least 128 bits | MUST | §4.3 |
| Custom emoji `name` | 32 characters | MUST | §5.2.8.4 |
| Routing envelope size, live stream and gossip | 65536 bytes | MUST NOT exceed | §11.4, §10.3.1 |
| Sequencer submission `op` size | 65536 bytes | MUST NOT exceed | §14.4.3 |
| Attachment size (`maxAttachmentBytes`) | 100 MiB | Example only | §11.8.3 |
| File chunk size (chunked content-key blob) | 262,144 bytes (256 KiB); last chunk 1 to 262,144 bytes | Fixed | §14.3.4 |
| File size (chunked content-key blob) | 2^32 bytes, so at most 16,384 chunks | MUST NOT exceed | §14.3.4 |
| Blob replication floor (`replicationFloor`) | default 2, minimum 1 | Default; replication to the floor MUST | §10.4.4, §10.5.1 |
| Pkarr record | 1000 bytes | MUST | §10.3.4.6 |
| Directory `includes` depth | 3 | MUST | §10.3.4.1 |
| Messages per `BroadcastKey` | fewer than 2^32 | MUST | §5.2.1.4 |
| `BroadcastKey` rotation | at least every 30 days | SHOULD | §5.2.1.4 |
| MLS epoch lifetime | 7 days maximum | Recommended | §12.2 |
| Presence re-send; offline after silence | 30 s; 60 s | MUST; descriptive | §5.3.1 |
| Typing events; indicator clear | at most 1 per 3 s; 10 s | Descriptive; SHOULD | §5.3.2 |
| `ParticipantState` republish | every `ttl / 2` | MUST | §6.2 |
| Ring duration | 120 s after receipt | SHOULD NOT exceed | §6.14.1 |
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
| Relay envelope cache | lesser of `expiryHint` and the agreement's `retentionDays` | MUST | §10.4.3, §10.4.6 |
| Publish `ts` ahead of the relay's clock before `expired` | 300 s | MUST | §11.4 |
| Push registration TTL | default 30 days, maximum 30 days | Default; MUST NOT keep longer; renewal MUST | §11.7.3 |
| `PinInstruction`, upload, and sequencer submission `expires` | at most 600 s ahead of the relay's clock | MUST | §11.4, §11.8.2, §14.4.3 |
| Admission key registration request | 1 to 1000 keys or tokens; `ts` within 300 s | MUST | §10.5.3 |
| Full re-registration of current keys | at least every 24 h | MUST | §10.5.3 |
| Grace before deregistering the previous admission key after rotation | 300 s, for application messages and operations only; no Commit is stamped on the previous key's commit stream once the new key is registered | RECOMMENDED; MUST for the sequencer rule | §10.5.3 |
| Canonical-Commit window without a sequencer | 5 s | MUST | §5.1.1 |
| Delay before republishing a winning Commit taken from the sequencer's log | random 10 to 60 s; not published if a copy arrives first | See section | §5.1.1 |
| Retention of the previous epoch's sealing key | 60 s | Descriptive | §5.2.2 |
| Buffering of an envelope that opens under no sealing key, in a group with no sequencer | until the recipient processes its next Commit, at most 24 h; then tried again and dropped if it still does not open; the member then flags itself out of sync and keeps its group state | See section | §5.2.2, §5.1.1 |
| Admission key fetch while connected | at least once an hour | MUST | §5.2.2 |
| MLS generation window per sender | 32 behind; 1000 ahead | Descriptive | §5.2.1 |
| `agora_credentials` entries per leaf; extension data size | 8; 8192 bytes | Over the limit, the extension is ignored | §5.2.1.5 |
| Hold of a Welcome whose authorization cannot yet be decided | 7 days | See section | §4.3 |
| Guardian transfer proposal `ts` window; objection period | 300 s; default 259200 s | MUST; default | §4.1, §3.3 |
| KeyPackage upload `ts` window | 300 s | MUST | §5.2.1.1 |
| BEP-5 re-announce | 30 min | SHOULD | §10.3.4.6 |
| Pkarr re-publish | 2 h | SHOULD | §10.3.4.6 |
| Peer manifest cache; retry on fetch failure | 1 h; once after 5 s | Descriptive | §10.2.3 |
| Peer block after a violation; permanent blocklisting | 24 h; 3 incidents in 7 days | Descriptive | §10.2.4 |
| Unreachable peer kept in `knownPeers` | 7 days | Descriptive | §10.2.6 |
| Directory fetch backoff; unreachable flag | 30 s to 1 h; 7 days | Descriptive | §10.3.4.4 |
| DM admission host handover fallback | any remaining member that may move the group (§4.6.4) after 24 h without a handover Commit | See section | §4.6.4 |
| DM admission key rotation fallback | every host's user's client rotates 24 h after a Commit that removed a leaf, if no Commit has changed `agora_admission` | MUST | §4.6 |
| DM admission host deregisters a group's key | on its issuee's request; 7 days after the issuee of a later key for the group confirms that key; or 30 days after the issuee is offboarded; never sooner than 300 s after the new key's Commit has won and a relay in its `relays` has accepted a Subscribe (§4.6) | See section | §4.6 |
| DM admission key periodic rotation | the client of the host's user with the lowest leaf index rotates 7 days after it processed the Commit that put the current key in `agora_admission`; every host's user's client 24 h later if none has | MUST | §4.6 |
| DM admission host engages a replacement relay | at least 14 days before the departing relay's `retiresAt` | See section | §10.3.5 |
| DM member resolves each other member's DID | at least once every 7 days | See section | §4.6, §2.5.6 |
| Client deletes a DM admission key that a host move replaced | 30 days after the move Commit, and not before a relay admitted the new key | See section | §4.6.4 |
| Client deletes its user's DM admission keys after the user's last leaf is removed | 30 days after that Commit | See section | §4.6.4 |
| Non-member view refetch on a post from an unlisted `senderDID` | at most once a minute per Space | See section | §5.2.1.4 |
| Eager blob replication retry | exponential backoff for at least 24 h, then stop | Descriptive | §10.4.4 |
| SFU `challenge` freshness for a `join` | 30 s | MUST | §6.6 |
| Registrations under a superseded agreement | admitted for 1 h | MUST | §10.5.1 |
| Relay retirement notice (`retiresAt`) | at least 30 days | MUST, unless agreed otherwise out of band | §10.4.7 |
| Proof-of-work difficulty in a challenge | at most 64 bits | Format limit | §11.4, §10.5.2 |
| Push wake-ups per handle | 1 per 5 s, burst 3 | SHOULD (example values) | §11.7.5 |
| Second `RecoveryAssertion` for one DID | not within 24 h without admin review | MUST NOT | §2.4.4 |
| Per-`channelToken` publication rate | Relay local policy, but at least 20 envelopes per second and 256 KiB per second sustained | MUST enforce; MUST admit at least the floor | §11.6, §12.5 |

A direct message (DM) group is bounded only by the 4096-leaf limit, and a message body only by the routing envelope size. This version defines no limit for Space state document size, the number of KeyPackages in one upload, channel count per Space, or TURN credential lifetime.

---

## Appendix D: Registries and Identifiers

This appendix lists the identifiers this specification allocates. "IANA" names the registry in which an entry is required for interoperability outside Agora; "Agora-internal" means this specification is the only allocation authority and no external registration is needed. The `urn:agora:` URN namespace is treated as registered. The prefix `urn:agora:practice:` is reserved for names used by the non-normative guides and profiles in this repository; those names carry no protocol meaning.

**Derivation labels.** §13.3 lists every MLS exporter label, KDF `info` string, and AEAD associated-data prefix. The entries of kind "MLS exporter" are MLS exporter labels and need entries in the IANA "MLS Exporter Labels" registry (RFC 9420 §17). The other entries are Agora-internal.

**MLS extension types.** `agora_admission` (0xF0A0, GroupContext of DM groups and self-groups, §4.6), `agora_device_binding` (0xF0A1, LeafNode, §5.2.1), `agora_space_membership` (0xF0A3, GroupContext of self-groups, §2.6), `agora_compliance` (0xF0A4, GroupContext of DM groups, §7.8.2), and `agora_credentials` (0xF0A5, LeafNode, optional, §5.2.1.5) use the RFC 9420 private-use range and need no IANA registration.

**URN namespaces.**

| Namespace | Use | Defined in | Registration |
|---|---|---|---|
| `urn:agora:type:` | Payload type URIs | §13.1, §13.2, §5.2.3 | Agora-internal under `urn:agora:` |
| `urn:agora:v1` | JMAP capability | §11.8.3 | IANA "JMAP Capabilities" (RFC 8620 §9.4) |
| `urn:ietf:params:jmap:*` | JMAP family types | External drafts, profiled in §14.6 | Defined by those drafts |

**Types, members, and codes.** Payload and record types are registered in the type tables of §5.2.3, which include `KickLift` (§4.5). The following record members, operation values, and codes are Agora-internal.

| Identifier | Kind | Defined in |
|---|---|---|
| `replaces` | `AdmissionKeyRegistration` entry member (rotated token); also a `PushRegister` member (previous handle) | §10.5.3, §11.7.6 |
| `replicationFloor` | `ServiceAgreement` member | §10.5.1, §10.4.4 |
| `archive` | `ChannelAdmissionKey` member | §3.4, §10.4.4 |
| `closingHeads` | Space state member, array of `{channelID, stream, n, hash}` (closing commit-stream heads at a sequencer replacement) | §3.3, §14.4.5 |
| `pushProxy` | Space state member, an object with the members of the relay manifest's `pushProxy` (the push proxy that the Communications Operator, or CO, designates) | §3.3, §11.7.2 |
| `broadcasters` | Non-member view member, array of `{channelID, keyEpoch, dids}` | §3.3, §3.4, §5.2.1.4 |
| `chunkCount`, `thumbnailChunkCount`, `contentKey`, `thumbnailContentKey` | JMAP object extension properties | §14.3.4 |
| `seed` | `pin-op` operation | §11.4, §10.4.4 |
| Error codes of the live protocol, of admission key registration, and of the DM admission-key endpoint | Error codes | §4.6, §11.4, §10.5.3, §14.4.3 |
| `token` | Query parameter of the blob fetch and Peer API blob paths | §10.4.4, §10.2.2 |

**Capability and model strings.** These strings are Agora-internal.

| Strings | Use | Defined in |
|---|---|---|
| `gossipsub-v1.1`, `gossipsub-quic-v1`, `peer-api-h3`, `tor-hidden-service-v1`, `sfu-v1`, `peer-api-v1`, `jmap-sync-v1`, `push-proxy-v1`, `sequencer-v1` | Relay manifest `capabilities` | §10.2.1 |
| `single-author`, `sequenced-v1` | Consistency model identifiers | §14.2.1 |
| `text/markdown;variant=commonmark`, `text/markdown;variant=gfm`, `text/plain`, `application/jmap-chat-rich` | `bodyType` values | §5.2.7.2 |
| `co-issued` | TURN `credentialScheme` | §6.11 |
| `relay`, `sfu`, `sequencer`, `turn`, `push-proxy` | `ServiceAgreement` `serviceType` | §10.5.1 |
| `pow` | Proof-of-work scheme | §10.5.2 |

**DID service types.** Entries in the W3C DID Specification Registries are needed for resolvers outside Agora to recognize them.

| `type` | Defined in |
|---|---|
| `AgoraKeyPackageEndpoint` | §2.1, §5.2.1.1 |
| `AgoraProfile` | §2.3 |
| `AgoraSpaceEndpoint` | §3.4 |
| `AgoraComplianceLogger` | §7.3 |
| `AgoraProvisioning` | §2.5.3 |
| `AgoraMatrixGateway` | `profiles/gateways.md` (non-normative) |
| `AgoraTextFormatCapabilities` | §5.2.7.4 |

**Web and DNS identifiers.**

| Identifier | Defined in | Registration |
|---|---|---|
| Well-known URI `agora-relay` | §10.2.1 | IANA "Well-Known URIs" (RFC 8615) |
| Service name `agora-relay` (`_agora-relay._udp`, `_agora-relay._tcp`) | §10.2.5, §10.3.3 | IANA "Service Name and Transport Protocol Port Number" (RFC 6335) |
| `_agora` and its children `_kp._agora`, `_profile._agora`, `_corundum._agora` | §2.1, §10.3.4.6 | IANA "Underscored and Globally Scoped DNS Node Names" (RFC 8552), for `_agora` |
| HTTP field `Agora-Storage-Auth` | §11.8.2 | IANA "HTTP Field Name" (RFC 9110 §16.3) |
| HTTP fields `Agora-PoW-Challenge`, `Agora-PoW` | §10.5.2 | IANA "HTTP Field Name" (RFC 9110 §16.3) |
| JWS header parameter `agoraType` | §13.1.1 | IANA "JSON Web Signature and Encryption Header Parameters" (RFC 7515 §4.3) |
| WebSocket subprotocol `agora-sfu.v1` | §6.6 | IANA "WebSocket Subprotocol Name Registry" (RFC 6455 §11.5) |
| URI scheme `agora` | §3.2 | IANA "Uniform Resource Identifier (URI) Schemes" (RFC 7595) |
| HTTP path prefix `/v1/agora/`, gossip topics `v1/agora/...` | §1.1, §10.3.1 | Agora-internal |

---

## Appendix E: Acknowledgments

This appendix is non-normative.

Agora's relay peering design (§10.2: signed relay manifest, key lifecycle, request signing, and graduated trust levels) derives from the operator federation design of the CORUNDUM federated social protocol. Agora applies it one layer down, between relays that hold no identity or membership knowledge.

---

*End of specification.*
