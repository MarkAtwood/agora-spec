# 13. Encoding and Extensions

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 3353–3426 (§14–15).

## 13.1 Typed Payload Envelope

*Binds: both.*

Every Agora payload is carried in a **typed payload envelope**. The envelope names what the payload is, says how its bytes are encoded, and carries those bytes unchanged. Agora computes no canonical form of any payload.

The routing envelope that Relays carry is not a typed payload envelope and is defined in §5.2.2. It follows the same exact-bytes rule: its `signed` field is a CBOR byte string holding the encoded routing fields that `admissionSig` covers, and its `id` is the CID of the complete encoded routing envelope. Neither is computed over a re-encoding.

**Fields.**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `type` | text | yes | Absolute URI naming the object type (see "Type URIs" below). |
| `contentType` | text | yes | Media type of `body` (RFC 6838), with parameters if any, e.g. `application/json`, `application/ld+json`, `application/cbor`. |
| `body` | bytes | yes | The exact bytes of the object, encoded as `contentType` says. |
| `sig` | text | no | JWS General JSON Serialization over `body`, one entry per required signer (§13.1.1). REQUIRED where §13.1.1 or the section defining the object requires an object-level signature; otherwise absent. |
| `seq` | unsigned integer | MLS only | The sending device's sequence number in the group, counted per MLS leaf (§5.1.1). Present only when the envelope is the `application_data` of an MLS application message; covered by the MLS signature. |

**Encoding.** An envelope is encoded as a CBOR map (RFC 8949) with the text-string keys `type`, `contentType`, `body`, `sig` and, inside MLS only, `seq`. `type`, `contentType` and `sig` are CBOR text strings; `body` is a CBOR byte string holding the object bytes verbatim, never a nested CBOR or JSON value. Receivers MUST ignore map keys they do not recognize. The map itself is not signed, so its key order and integer widths carry no meaning.

**Inside an MLS application message.** The `application_data` of every MLS application message (§5.2.3) is exactly one encoded envelope. The MLS sender signature authenticates the sender and the envelope, so `sig` is absent unless the object is one that is also verified outside the group (below), in which case it is carried with its `sig` so that it can be forwarded or archived byte-for-byte.

**Inside a broadcast payload.** The `plaintext` sealed into a routing envelope's `broadcastPayload` (§5.2.1.4) is exactly one encoded envelope. No MLS sender signature covers it, so its `sig` MUST be present and recipients MUST verify it per §13.1.1 before acting on the payload. The binding of the signer to the channel, key epoch and broadcaster roles is defined in §5.2.1.4.

**Stored and published objects.** An object verified outside an MLS group (for example Space state, compliance records, `ServiceAgreement`, `AdmissionKeyRegistration`, `AdmissionKeyDeregistration`, `ChannelAdmissionKey` other than a DM group's (§3.4), `BroadcastKey`, discovery records and `ChannelShareAgreement`) is stored, served and forwarded as its encoded envelope with `sig` present. Where such an object is content-addressed, its CID is computed over the encoded envelope bytes as stored.

**Content identifiers.** Every CID this specification computes, whether of an encoded envelope, a routing envelope or a blob, is a CIDv1 with multicodec `raw` (0x55) and multihash `sha2-256` (0x12, 32-byte digest), computed over exactly those bytes. A CID carried in CBOR or used as input to a derivation is in binary form. A CID written in text, JSON or a URI is in multibase base32 lower-case form (prefix `b`), its CID text form.

**Type URIs.** `type` values are compared as exact, case-sensitive strings. No normalization is applied.

- A JMAP data type is named by the URN of the capability that defines it, a `#`, and the data type name as the defining specification spells it. For example, the `Message` type of the JMAP Chat specification (draft-atwood-jmap-chat-00) is `urn:ietf:params:jmap:chat#Message`. The `body` of a JMAP object is its JSON representation as defined by that specification and RFC 8620, with `contentType` `application/json`.
- An Agora protocol type is named `urn:agora:type:` followed by the type name, for example `urn:agora:type:SpaceState`, `urn:agora:type:SpeakRequest`, `urn:agora:type:IdentityChanged`, `urn:agora:type:AbuseReport` or `urn:agora:type:ChannelAdmissionKey`. The `urn:agora:type:` namespace is reserved for types defined by this specification. A type name is never reused for an incompatible definition; a breaking change defines a new name. Unless its defining section states otherwise, an Agora type has `contentType` `application/json` and its `body` is the JSON object shown in that section. A `@context` or `@type` member in such a body is ordinary JSON and carries no meaning for Agora processing.
- Any other type is named by an absolute URI under the control of whoever defines it, such as an HTTPS IRI or a URN in a namespace they control (§13.2).

**JSON-LD.** JSON-LD remains usable: a body MAY have `contentType` `application/ld+json`, with `type` set to the JSON-LD type IRI of the object. Such bodies are carried and signed as bytes like any other. Agora performs no JSON-LD expansion, RDF conversion or canonicalization, and no Agora processing step dereferences a body's `@context`.

**Example.** A chat message (a JMAP Chat `Message`) inside an MLS application message, in CBOR diagnostic notation with `body` shown as hex:

```
{
  "type": "urn:ietf:params:jmap:chat#Message",
  "contentType": "application/json",
  "body": h'7b2273656e6465724d73674964223a...'      / the exact JSON bytes of the Message /
}
```

### 13.1.1 Signing

This is the single normative object-signing procedure of this specification. Wherever another section says an object is "signed", "signed per §13.1.1", or signed over its "canonical" form, this procedure is meant. It applies to every content type: signatures cover the exact `body` bytes, and no canonical CBOR, JCS (RFC 8785) or RDF form is computed. Objects exchanged only inside an MLS group need no object-level signature; the MLS sender signature suffices.

**Format.** An object-level signature is a JWS (RFC 7515) in the General JSON Serialization (RFC 7515 §7.2.1) with a detached payload, using the unencoded payload option (RFC 7797) and the EdDSA algorithm with Ed25519 (RFC 8037). The envelope's `sig` field holds the UTF-8 JSON text of a JSON object with exactly one member, `signatures`: an array with one entry per signer, each entry a JSON object with exactly the members `protected` and `signature`. The `payload` member is omitted (detached), and the unprotected `header` member MUST NOT be used. Every entry signs the same exact `body` bytes. A signature is never embedded in the `body` it signs.

**Required signers.** The section defining each object states its required signer or signers. An object with one required signer has one entry; a multi-signer object (for example `ServiceAgreement` or `ChannelShareAgreement`) has one entry per required signer. Signing order is irrelevant: each signer computes its entry independently over the same `body`, and entries MAY appear in any order.

**Protected header.** Each entry's JWS Protected Header MUST be a JSON object containing exactly these members:

| Member | Value |
|---|---|
| `alg` | `"EdDSA"` |
| `b64` | `false` |
| `crit` | `["b64"]` |
| `kid` | DID URL of the signing verification method, e.g. `did:webvh:QmSCID...:example.com:alice#keys-1` or `did:key:z6Mk...#z6Mk...` |
| `cty` | The envelope's `contentType`, exactly |
| `agoraType` | The envelope's `type`, exactly |

`cty` and `agoraType` bind the signature to the declared encoding and type, so a signed body cannot be presented as another type.

**Signing.** The signer computes the JWS Signing Input as `ASCII(BASE64URL(UTF8(protected header))) || "." || body`, where `body` is the exact byte string placed in the envelope, signs it with the Ed25519 private key of the verification method named by `kid` (RFC 8032), and adds the entry `{"protected": BASE64URL(UTF8(protected header)), "signature": BASE64URL(signature)}` to the `signatures` array.

**Byte-for-byte rule.** A signed `body` MUST be stored, forwarded, archived and re-published as the exact bytes that were signed. Parties MUST NOT substitute a parsed and re-serialized body for the original bytes, including to change whitespace, key order, number formatting or character escaping. An implementation that needs a modified object creates a new object and, if required, a new signature.

**Verification.** A verifier MUST reject the object unless `sig` parses as the JSON object described under Format, it contains an entry for every required signer that the section defining the object names, and every such entry satisfies all of the following:

1. The entry has exactly the members `protected` and `signature`, each a base64url string.
2. The protected header decodes to a JSON object with exactly the members above; `alg` is `"EdDSA"`, `b64` is `false`, `crit` is `["b64"]`, `cty` equals the envelope's `contentType` and `agoraType` equals the envelope's `type`.
3. `kid` is a DID URL whose DID resolves (§2.1; a `did:web` IO principal such as a Relay, §10.2.1, per the `did:web` method specification) to a DID document containing a verification method whose `id` equals `kid`, holding an Ed25519 public key, and referenced from the document's `authentication` relationship unless the section defining the object names another relationship. For an object being received, the verifier uses the DID's current document. For an object it accepted earlier and stored, it uses the document version in effect when it accepted the object, which it records with the object (`versionId` for `did:webvh`, the operation CID for `did:plc`). A later key revocation does not invalidate an object accepted before it.
4. The DID in `kid` is the signer that the section defining the object requires (for example the Space's CO DID, or the message's `senderDID`).
5. The Ed25519 signature verifies over the JWS Signing Input built from the entry's received `protected` value and the `body` bytes exactly as received.

A verifier MUST reject the object if any entry fails these checks, including an entry from a signer that is not required.

Verification MUST NOT fetch any resource named inside `body`.

**Admission signatures.** `admissionSig` is not an object-level signature. The channel admission key is a key the CO shares with current members, not a DID verification method, so no `kid` can name it (ARCHITECTURE §6.2). An `admissionSig` is a raw 64-byte Ed25519 signature (RFC 8032) under the channel admission private key over the exact bytes of a CBOR byte string named `signed`: the routing envelope's `signed` field (§5.2.2), or the `signed` member of a `PinInstruction` or blob upload authorization (§11.4, §11.8.2). The verifier checks it over those bytes as received, under the admission public key registered for the `channelToken` they contain, and never re-encodes them. The `AdmissionKeyRegistration` that tells an IO which public key to use is an object signed per this section by the CO's billing DID (§10.5.1).

**Test vectors.** A JWS signing test-vector set MUST be published containing at minimum: (a) at least five representative signed object types, including at least one multi-signer object, each with its envelope fields, `body` bytes in hex, the Ed25519 test private key, and the expected `sig`; and (b) negative cases that a verifier MUST reject, including `b64` set to `true` or absent, an `alg` other than `EdDSA`, `cty` or `agoraType` not matching the envelope, a body that was re-serialized after signing, and a multi-signer object missing one required signer's entry. Because Ed25519 signatures are deterministic, expected `sig` values are byte-exact. Implementations MUST pass all test vectors before signing or verification code is considered conformant.

> **Open (agora-pozi.31.69):** The JWS test-vector set does not exist yet; no `test-vectors/` directory is present in the repository.

### 13.1.2 Context Document Caching

Retired. Signatures are computed over exact `body` bytes (§13.1.1) and involve no JSON-LD expansion, so implementations fetch and cache no JSON-LD context document for signing or verification. A body with `contentType` `application/ld+json` MAY be processed by an application that understands its type, and that processing is outside this specification.

---

## 13.2 Extension Points

*Binds: both.*

The protocol is designed to be extended without breaking existing clients:

- **Types are extensible by URI.** New payload types are added by defining a new `type` URI (§13.1). Types defined outside this specification MUST use a URI under the definer's control; the `urn:agora:type:` namespace is reserved for this specification. No registry is needed.
- **Unknown types are ignored.** A recipient that does not understand an envelope's `type` MUST ignore the payload: it MUST NOT display it, MUST NOT treat it as an error, and MUST continue processing the MLS group or channel normally. A recipient that keeps such a payload (for example in history storage or a compliance archive) MUST keep the encoded envelope byte-for-byte. A recipient that understands the `type` but not the `contentType` MUST treat the payload as an unknown type.
- Space state documents MAY include extension fields whose names are URIs under the definer's control; recipients MUST ignore extension fields they do not understand. A field that a CO enforcement point (ARCHITECTURE §6.3) depends on MUST NOT be added as such an extension. It requires a new `schemaVersion`, so that a client that does not understand it rejects the document instead of ignoring the field.
- New channel types MAY be introduced by defining new values of the channel `type` field.
- The live client-relay protocol is versioned and negotiated in the hello exchange (§11.6).

**Version surface registry.** The following table lists every versioned protocol surface, its current version, and the mechanism by which it is negotiated or detected. URL-versioned surfaces answer a request under an unknown version prefix with HTTP 404.

| Surface | Current Version | Location | Negotiation Mechanism |
|---|---|---|---|
| Payload type | per type | Envelope `type` URI (§13.1) | New type = new URI; unknown types ignored (§13.2) |
| Object signature | JWS, EdDSA/Ed25519, `b64` false | §13.1.1; JWS `alg` and `crit` header members | Static for v1; new algorithm = new surface version |
| Document schema | 1 | `schemaVersion` field | Field presence; reject unsupported values |
| WebTransport endpoint | v1 | URL path prefix `/v1/agora/wt` | HTTP 404 on unknown version |
| WebSocket endpoint | v1 | URL path prefix `/v1/agora/ws` | HTTP 404 on unknown version |
| Live protocol | 1 | `v` member of every live-stream message; `versions` in `ClientHello` (§11.4, §11.6) | Negotiated in `RelayHello`; unknown `v` discarded |
| Gossip topics | v1 | Topic string prefix `v1/` (§10.3.1) | Relays subscribe to every version they serve |
| KeyPackage Store API | v1 | URL path prefix `/v1/agora/kp/` (§5.2.1.1) | HTTP 404 on unknown version |
| Peer API | v1 | URL path prefix `/v1/agora/peer/` + `peer-api-v1` capability | HTTP 404; capability string |
| Push Proxy API | v1 | URL path prefix `/v1/agora/push/` + `push-proxy-v1` capability | HTTP 404; capability string |
| Relay Manifest schema | 1 | `version` field | Field value; reject unsupported |
| Relay Manifest location | 1 | `GET /.well-known/agora-relay` (§10.2.1) | Manifest `version` field |
| JMAP sync API | v1 | Base URL `endpoints.jmapSync`, conventionally `/v1/agora/jmap` + capability `urn:agora:v1` + `jmap-sync-v1` capability string (§11.8) | JMAP `using`; capability string |
| Relay blob API | v1 | URL path prefix `/v1/agora/blob/` (§10.4.4) | HTTP 404 on unknown version |
| Space endpoint | v1 | URL from `spaceEndpoint`, conventionally under `/v1/agora/space/` (§3.4) | HTTP 404 on unknown version |
| Sequencer API | v1 | Sequencer `endpoint`, conventionally `/v1/agora/seq` (§14.4) | HTTP 404 on unknown version |
| SFU signaling | v1 | `SFUDescriptor.endpoint`, conventionally `/v1/agora/sfu` (§6.6) | HTTP 404 on unknown version |
| TURN credential service | v1 | `TURNDescriptor.credentialEndpoint`, conventionally `/v1/agora/turn` (§6.11) | HTTP 404 on unknown version |

## 13.3 Derivation Label Registry

*Binds: both.*

Every MLS exporter label, KDF and HPKE `info` string, AEAD associated-data prefix, signature context string and hash-input prefix that this specification defines is listed below. A new label MUST NOT equal a label in this table, and a section that defines a new label MUST add it here. The labels are opaque byte strings (UTF-8, no terminator); their spelling style carries no meaning. Every Agora MLS exporter call other than the SFrame ones (RFC 9605 §5.2) uses the group's MLS `group_id` as its context, for channels and DM groups alike. Every channel and DM group, broadcast channels included, derives its `channelToken` from its admission key with `agora channel token`; no other token label exists.

The test-vector set of §13.1.1 MUST also cover each derivation in this table, the `admissionSig` input, and CID computation.

| Label | Kind | Context or input | Defined in |
|---|---|---|---|
| `agora channel token` | HKDF-SHA256 `info`, followed by `keyEpoch` as uint64 big-endian | IKM: channel admission private key seed; output `channelToken`, 32 bytes | §5.2.2, ARCHITECTURE §6.2 |
| `agora sealed envelope` | MLS exporter | MLS `group_id`, `Nk` bytes | §5.2.2 |
| `agora blob` | MLS exporter | MLS `group_id`, `Nk` bytes | §3.4 |
| `agora-media-key` | MLS exporter (SFrame, RFC 9605 §5.2) | media keys | §6.9 |
| `agora data channel` | MLS exporter (SFrame, RFC 9605 §5.2) | data channel keys | §6.13 |
| `agora/v1/social-recovery-key` | HKDF-SHA256 `info` | social recovery key seed | §2.4.2 |
| `agora/v1/recovery-share` | HPKE `info` prefix, followed by the owner's DID | guardian share encryption | §2.4.2 |
| `agora/v1/webauthn-prf` | SHA-256 input; the digest is the WebAuthn PRF input `first` | browser device key wrapping | §12.6 |
| `agora/v1/webauthn-prf-wrap` | HKDF-SHA256 `info` | IKM: WebAuthn PRF output; output AES-GCM wrapping key, 32 bytes | §12.6 |
| `agora/sealed/v1` | AEAD associated-data prefix | sealed envelope | §5.2.2 |
| `agora/blob/v1` | AEAD associated-data prefix | group-encrypted blob | §3.4 |
| `agora/broadcast/v1` | AEAD associated-data prefix | broadcast payload | §5.2.1.4 |
| `agora/asset/v1` | AEAD associated data | Space icon and custom emoji under `assetKey` | §3.4 |
| `agora/history/v1` | AEAD associated data | history transfer archive blob | §2.6 |
| `agora/envelope/v1` | Signature context (`ctx` of the routing envelope's `signed` map) | `admissionSig` over routing envelopes | §5.2.2 |
| `agora/v1/device-binding` | Ed25519 signed-message prefix, followed by the leaf `signature_key` | `did:key` device binding in the `agora_device_binding` leaf extension | §5.2.1, §2.1 |
| `agora sfu admission` | Signature context (`ctx` of `sfu-admission`) | `admissionSig` in an SFU `join` | §6.6 |
| `agora/commits/v1` | SHA-256 input prefix, followed by `channelToken` | commit stream name | §5.1.1, §14.4 |
| `agora-recording-archive-v1` | HPKE `info` prefix | recording archive | §6.12.4 |
| `agora-relay-v1` | SHA-1 input | Mainline DHT infohash | §10.3.4.6 |

---
