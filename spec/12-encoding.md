# Agora Protocol: Encoding and Extensions

> Binds: both. Verbatim from `import/agora-protocol-spec-unified.md` lines 3353–3426 (§14–15). Section numbers are the source's and will be renumbered.

## 14. JSON-LD Context and Canonicalization

The canonical Agora JSON-LD context is published at:

```
https://agora.protocol/ns/v1
```

It maps all Agora message types and properties to globally unique IRIs and declares their relationship to relevant external vocabularies (schema.org, W3C DID Core, ActivityStreams where applicable).

All Agora messages MUST include `"@context": "https://agora.protocol/ns/v1"` or an equivalent inline context. Processors that do not perform full JSON-LD expansion MAY treat the context URL as a version tag, but MUST NOT reject messages that include additional `@context` entries for extension vocabularies.

The context URL is versioned: `/ns/v1` is the v1 schema. A breaking change to the type system produces `/ns/v2`. The context URL is frozen once published — `/ns/v1` will always describe the v1 schema without modification.

### 14.1 Canonicalization and Signing Pipeline

All signatures over JSON-LD documents in this specification use the following normative pipeline:

1. **Expand** the document using the Agora JSON-LD context, resolving all terms to absolute IRIs. Use a strict JSON-LD 1.1 processor. Unknown terms MUST be dropped during expansion, not passed through.
2. **Serialize** the expanded document to RDF N-Quads (one quad per line, no trailing blank line).
3. **Canonicalize** the N-Quads dataset using **URDNA2015** (W3C RDF Dataset Normalization Algorithm). This deterministically renames blank nodes and sorts quads, producing a stable byte string regardless of input key ordering or whitespace.
4. **Hash** the canonical N-Quads byte string with **SHA-256**, producing a 32-byte digest.
5. **Sign** the digest with **Ed25519** using the signer's authentication key. The signature is 64 bytes (RFC 8032).

The resulting signature is encoded as **base64url** (no padding) and placed in the document's `proof.signatureValue` field (W3C Data Integrity Proofs format), or carried out-of-band in the enclosing envelope depending on context.

This pipeline is identical to **W3C Data Integrity Proofs** with the `eddsa-rdna-2022` cryptosuite, which is the signing layer used by the W3C Verifiable Credentials ecosystem. Implementations SHOULD use an existing conformant library rather than implementing the pipeline from scratch.

**Reference implementations:**
- TypeScript/JS: [`jsonld`](https://github.com/digitalbazaar/jsonld.js) + [`rdf-canonize`](https://github.com/digitalbazaar/rdf-canonize) (Digital Bazaar — the W3C reference implementations)
- Go: [`go-jsonld-signatures`](https://github.com/go-jsonld-signatures) or FFI binding to the above for correctness during initial development
- Rust: [`json-ld` crate](https://crates.io/crates/json-ld) + [`rdf-types`](https://crates.io/crates/rdf-types) + [`ssi` crate (Spruce Systems)](https://github.com/spruceid/ssi)

**Test vectors:** The Agora repository MUST include a `test-vectors/canonicalization/` directory containing at minimum: (a) five representative Agora document types in their pre-signing JSON-LD form, (b) the expected N-Quads output after expansion and URDNA2015 normalization, and (c) the expected SHA-256 digest. Implementations MUST pass all test vectors before signing or verification code is considered conformant.

### 14.2 Context Document Caching

Because URDNA2015 requires a JSON-LD expansion step, implementations need access to the context document at `https://agora.protocol/ns/v1`. Fetching this document over the network at signing or verification time is unacceptable for latency and offline operation.

Implementations MUST cache the context document locally. The canonical context document for each published version is pinned by its SHA-256 hash, which is included in this specification and in the Agora repository. Implementations MUST verify the cached document against the pinned hash before use.

Implementations MUST NOT fetch the context document from the network during signature verification of an untrusted message — this is a denial-of-service vector (an adversary could stall verification by making the context URL slow or unreachable). The context document MUST be loaded from the local cache only.

---

## 15. Extension Points

The protocol is designed to be extended without breaking existing clients:

- Unknown `@type` values in inner payloads MUST be ignored by clients that do not understand them (forward compatibility).
- Space state documents MAY include extension fields prefixed with a registered namespace.
- New channel types MAY be introduced by extending the channel `type` enum in the JSON-LD context.
- Transport encodings beyond CBOR/JSON MAY be negotiated via WebTransport stream headers.

**Version surface registry.** The following table lists every versioned protocol surface, its current version, and the mechanism by which it is negotiated or detected:

| Surface | Current Version | Location | Negotiation Mechanism |
|---|---|---|---|
| JSON-LD context | v1 | `@context` URL | Static; reject unknown context URLs |
| Canonicalization pipeline | URDNA2015 + Ed25519 | §14.1; `proof.cryptosuite` field | Static for v1; new cryptosuite = new surface version |
| Document schema | 1 | `schemaVersion` field | Field presence; reject unsupported values |
| WebTransport endpoint | v1 | URL path prefix `/v1/agora/wt` | HTTP 404 on unknown version |
| WebSocket endpoint | v1 | URL path prefix `/v1/agora/ws` | HTTP 404 on unknown version |
| Frame format | 0x01 | Frame `version` byte | Discard unknown; may close connection |
| Gossip topics | v1 | Topic string prefix `v1/` | `negotiated.gossipVersion` in RelayChallenge |
| KeyPackage Store API | v1 | URL path prefix `/v1/agora/kp/` | HTTP 404 on unknown version |
| Peer API | v1 | URL path prefix `/v1/agora/peer/` + `peer-api-v1` capability | HTTP 404; capability string |
| Push Proxy API | v1 | URL path prefix `/v1/agora/push/` + `push-proxy-v1` capability | HTTP 404; capability string |
| Relay Manifest schema | 1 | `version` field | Field value; reject unsupported |
| Client-relay handshake | v1 | `supportedTransportVersions` in ClientHello | Negotiated in RelayChallenge |


---

