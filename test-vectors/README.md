# Agora test vectors

Test vectors for the Agora specification. Two independent toolchains compute every value, and a vector is installed only when both agree byte for byte:

| Toolchain | Version | Primitives used |
|---|---|---|
| Python, pyca/cryptography (OpenSSL backend) | cryptography 41.0.7 | Ed25519, AESGCM, HKDF, HMAC, SHA-256, SHA-1 |
| Go standard library | go1.27.1 | `crypto/ed25519`, `crypto/aes` + `crypto/cipher` GCM, `crypto/hkdf`, `crypto/sha256`, `crypto/sha1` |

Each toolchain has its own hand-written base58btc, multibase/CID, CBOR, and protobuf (dag-pb/UnixFS) encoders; the two share no code. As a third check on CBOR, the Python side decodes every CBOR item with `cbor2` 5.9.0 (if installed) and re-encodes it canonically. `cbor2` is never a source of vector values. No dag-pb or UnixFS library was available offline, so the protobuf encoders are instead checked against the published UnixFS CIDs listed below.

## Primitive validation

Before computing any vector, each toolchain checks its primitives against published vectors and aborts on any failure. Both pass all of them:

- SHA-256 and SHA-1 `"abc"` (FIPS 180-2)
- Ed25519 RFC 8032 §7.1 TEST 1 (public key and signature)
- HKDF-SHA256 RFC 5869 A.1 (PRK and OKM) and A.3 (zero-length salt and info)
- AES-128-GCM, McGrew-Viega GCM specification Test Cases 2 and 4
- base58btc, draft-msporny-base58 examples; base32, RFC 4648 §10
- CIDv1 `raw`/sha2-256 of the empty byte string (`bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`)
- dag-pb + UnixFS: the IPFS empty directory (`QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn`, and its CIDv1) and the empty file (`QmbFMke1KXqnYyBBWxB74N4c5SBnJMVAiMNRcGu6x1AwQH`). These cover the PBNode `Data` field and the UnixFS `Type` and `filesize` fields. The `PBLink` and `blocksizes` encodings are checked only by agreement between the two toolchains.

## Files

Fixed inputs named by a label are `SHA-256(UTF-8("agora-test-vectors/" || label))`, truncated to the stated length. Where the spec requires randomness (nonces, content keys, proof-of-work (PoW) and Selective Forwarding Unit (SFU) challenges), the value is fixed for the vector and the file says so. CBOR maps use RFC 8949 §4.2.1 deterministic key order. The spec does not require that order; it is one valid encoding, and receivers use the bytes as received.

| File | Construction | Spec |
|---|---|---|
| `jws.json` | JWS General JSON Serialization, RFC 7797 `b64:false` detached, Ed25519 (16 cases). Valid: `RelayAd` (1 signer); `ServiceAgreement` (2 signers, plus `bodyCidText`, the body CID that `agreement` uses per §10.5.3, and its encoded envelope with `envelopeCidText`); threshold 2-of-3 `SpaceState`; `AdmissionKeyRegistration` with `replaces`; `ChannelAdmissionKey`; `BroadcastKey`. Negative: missing required signer; threshold with duplicated DID; `b64` true; `b64` absent; `b64` and `crit` absent; `crit` absent; `alg` `Ed25519`; `cty` mismatch; `agoraType` mismatch; re-serialized body | §13.1.1, §10.5.1, §10.5.3, §3.4, §4.1 |
| `channel-token.json` | `channelToken` for `keyEpoch` 0, 1, 2^32 | §5.2.2, §13.3 |
| `sealed-envelope.json` | Sealed envelope AES-128-GCM (exporter output given) | §5.2.2 |
| `routing-envelope.json` | `SignedFields`, `admissionSig`, envelope `id`, outer envelope. Chained from the two files above | §5.2.2, §13.1 |
| `broadcast-payload.json` | `BroadcastMessage` signed by its poster, its typed payload envelope, the `agora/broadcast/v1` AEAD, and the routing envelope carrying `broadcastPayload` | §5.2.1.4, §3.4 |
| `chunked-blob.json` | Chunked content-key blob: an empty file, a 14-byte file, and 2-chunk and 3-chunk files (pattern `j mod 251`). Gives each chunk's nonce, AAD, block, and CID; for n > 1, the dag-pb root block, root CID, and `blobId` | §14.3.4, §13.1 |
| `aead-layouts.json` | Group-encrypted blob (`agora/blob/v1`), asset blob (`agora/asset/v1`), history archive blob (`agora/history/v1`), each with the CID of the whole blob | §3.4, §2.6 |
| `derivations.json` | Social recovery seed and public key; WebAuthn PRF input; PRF wrapping key; commit stream name; Mainline DHT infohash | §2.4.2, §12.6, §14.4.2, §10.3.4.6 |
| `sfu-admission.json` | `sfu-admission` CBOR and its `admissionSig` | §6.6 |
| `device-binding.json` | `did:key` identity, leaf `signature_key`, `agora_device_binding` extension data | §5.2.1, §2.1 |
| `http-pow.json` | `Agora-PoW-Challenge` / `Agora-PoW` headers, difficulty 20, smallest 8-byte nonce meeting it, a negative nonce, and a check of the spec's example | §10.5.2, §11.6 |

The header negatives in `jws.json` each carry an Ed25519 signature that is valid over that entry's own signing input, so a verifier must reject them on the header checks.

Blocks larger than 4 KiB in `chunked-blob.json` are stored as length, SHA-256, and first/last 64 bytes; both check scripts recompute each full block and compare its SHA-256.

## Regenerate and verify

```sh
tools/regen.sh                         # Python generates into a staging dir; Go then Python re-check it; only then install
python3 tools/agora_tv.py check        # Python: recompute everything and compare with the JSON files
(cd tools/go && go run . check)        # Go: recompute everything and compare with the JSON files
python3 tools/agora_tv.py primitives   # published-vector checks only
(cd tools/go && go run . primitives)
```

The Go check compares in both directions: every value it computes must match the file, and every non-descriptive value in the file must be one it recomputed. It skips only the keys `construction`, `spec`, `notes`, `reason`, and `pattern`. Go also reaches the `accept`/`reject` verdicts on its own, from the spec §13.1.1 header, signature, and signer-set checks; Python's verdicts are written by hand.

## Not covered

- **MLS exporter labels** (`agora sealed envelope`, `agora blob`, `agora-media-key`, `agora data channel`) need an MLS implementation. The exporter output is taken as a given input. The SFrame per-KID derivation (RFC 9605 §4.4.2) and the KID vectors that spec §6.9 requires are not produced.
- **Hybrid Public Key Encryption (HPKE) labels** (`agora/v1/recovery-share`, `agora-recording-archive-v1`) are not produced. pyca/cryptography 41.0.7 has no HPKE, so there is no second toolchain. The Shamir share encoding of spec §2.4.2 is not covered either.
- **WebAuthn `wrapKey` output** (spec §12.6) is local storage only. These vectors cover the PRF input and the wrapping key, not the wrapped PKCS#8 bytes.
- **`ComplianceRecord`** needs real MLS message, key, and `GroupContext` bytes.

## Spec ambiguities

None open.

Resolved in the current spec and matching these vectors: §5.2.1.4 `message` now references the JMAP Chat `Message` (§5.2.3); §3.4 now gives the group-encrypted blob nonce as 12 bytes; §10.5.1 now identifies an agreement, and its `supersedes` value, by the body CID, matching §10.5.3.
