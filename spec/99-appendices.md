# Appendices

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 4084–4139 (Appendices A, B).

## Appendix A: Dependency Summary

| Component | Specification | Reference Implementation |
|---|---|---|
| E2EE group key management | RFC 9420 (MLS) | `openmls` (Rust), `mlspp` (C++) |
| Message framing | JSON-LD (W3C) | `jsonld` + `rdf-canonize` (JS) |
| Identity | W3C DID Core, `did:key`, `did:web` | `ssi` (Rust), `go-did` (Go) |
| Content addressing | IPFS / IPLD (CIDv1, dag-cbor) | `go-ipfs`, `helia` (JS), `rust-ipfs` |
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
| Shamir Secret Sharing | — | `hashicorp/vault` shamir (Go), `sharks` (Rust) |
| Spam deterrence (proof-of-work) | Hashcash-style PoW | SHA-256 (standard library) |
| Native cross-system interop | MIMI (drafts; delivery layer stalled as of 2026-04) | TBD (spec in progress) |
| Matrix gateway | Matrix Application Service API | `mautrix-go`, `mautrix-python` |
| Relay bootstrap DNS | DNS-SD / SRV / TXT records | Standard DNS libraries |
| JSON-LD canonicalization | URDNA2015 | `rdf-canonize` (JS), `ssi` (Rust) |

---

## Appendix B: Open Questions

1. **Cross-space identity and reputation** — there is currently no mechanism for carrying moderation history or reputation across Space boundaries. A user banned from one Space can freely join another. Whether this is a feature (clean-slate by design, prevents monoculture moderation) or a gap (enables bad actors to evade consequences) depends on use case. A voluntary cross-space reputation attestation format is worth considering as an optional extension.

2. **Push notification proxy conformance** — see agora-pozi.11 (push proxy observation budget, ARCHITECTURE.md §8 Q4).

---

*End of specification.*
