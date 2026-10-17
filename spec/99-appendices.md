# Agora Protocol: Appendices

> Binds: both. Verbatim from `import/agora-protocol-spec-unified.md` lines 4084–4139 (Appendices A, B). Section numbers are the source's and will be renumbered.

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
| Payments | Cashu ecash, Lightning (BOLT12/BOLT11) | `cashu-ts` (JS), `nutshell` (Python), LDK/LND; see §12 |
| Payments (service agreements) | Lightning Network BOLT 12 | Core Lightning, LND |
| Spam deterrence (no payment) | Hashcash-style PoW | SHA-256 (standard library) |
| Native cross-system interop | MIMI (drafts; delivery layer stalled as of 2026-04) | TBD (spec in progress) |
| Matrix gateway | Matrix Application Service API | `mautrix-go`, `mautrix-python` |
| Relay bootstrap DNS | DNS-SD / SRV / TXT records | Standard DNS libraries |
| JSON-LD canonicalization | URDNA2015 | `rdf-canonize` (JS), `ssi` (Rust) |

---

## Appendix B: Open Questions

1. **Cross-space identity and reputation** — there is currently no mechanism for carrying moderation history or reputation across Space boundaries. A user banned from one Space can freely join another. Whether this is a feature (clean-slate by design, prevents monoculture moderation) or a gap (enables bad actors to evade consequences) depends on use case. A voluntary cross-space reputation attestation format is worth considering as an optional extension.

2. **Push notification proxy conformance** — §8.7 specifies the push proxy protocol but does not define conformance requirements for proxy operators (logging policy, data retention, handle-to-token mapping security). A push proxy operator specification analogous to the Relay operator conformance requirements may be warranted for deployments where push proxy trust is a concern.

3. **Transport independence** — IP is the default transport for Agora relay communication, not an architectural requirement. Agora message envelopes are self-authenticating CBOR blobs: content-addressed, MLS-encrypted end-to-end, and verifiable by the recipient without trusting the carrier. A relay that receives a valid envelope over any medium can forward it into the gossipsub mesh; the carrier never has access to useful content and the recipient never has to trust the carrier. This is a first-class property of the design, not an edge case.

   Relay-to-relay synchronization can therefore occur over any medium that can carry bits:

   - **IP internet** — the default; WebTransport (QUIC) and WebSocket as specified
   - **Overlay networks** — WireGuard, Tailscale, Tor; already specified in §3.4
   - **LoRa / Meshtastic** — long-range low-bandwidth radio mesh; viable for text-scale message traffic in areas without IP infrastructure
   - **HF and packet radio** — AX.25, amateur packet networks; applicable for remote, maritime, and disaster deployments
   - **Sneakernet** — physical media (USB, hard drive); content-addressing provides automatic deduplication; a courier syncing two isolated relays daily is a legitimate and complete deployment
   - **Satellite store-and-forward** — non-IP satellite uplinks; batch upload/download on orbital pass
   - **Delay-Tolerant Networking (DTN)** — the Bundle Protocol (RFC 9171) is the IETF standard for store-carry-forward over high-latency or intermittently connected links; Agora envelopes are structurally compatible with DTN bundles and the protocol's tolerance for message reordering makes it a natural fit for deep-space, submarine, and other extreme-latency deployments
   - **Bluetooth mesh / WiFi Direct** — infrastructure-free short-range peer-to-peer
   - **SMS / GSM data** — CBOR envelopes encoded for narrow-band transport

   The practical implications include: disaster-resilient deployments that fall back to radio or mesh when IP infrastructure fails; censorship-resistant relay sync that continues over radio or physical courier when IP is interdicted; and space-capable deployments where relay sync occurs over high-latency deep-space links with the DTN Bundle Protocol as the carrier.

   Two application-layer extensions are specified for non-IP transport contexts: a native email transport profile (AETP; see the community-maintained extension registry) and a batch store-and-forward format for UUCP, rsync, sneakernet, HF radio, and similar carriers. Both apply to application messages only — MLS handshake messages (Welcome, Commit, Proposal) require ordered, timely delivery and MUST use the primary gossipsub path when available. Capability strings: `slow-transport-email-v1`, `slow-transport-batch-v1`.

---

*End of specification.*
