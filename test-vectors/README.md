# Agora test vectors

Vectors for the Agora specification at commit `fd8710f`. Every value is computed by two independent toolchains, and a vector is installed only when both agree byte for byte:

| Toolchain | Version | Primitives used |
|---|---|---|
| Python, pyca/cryptography (OpenSSL backend) | cryptography 41.0.7 | Ed25519, AESGCM, HKDF, HMAC, SHA-256 |
| Go standard library | go1.27.1 | `crypto/ed25519`, `crypto/aes` + `crypto/cipher` GCM, `crypto/hkdf`, `crypto/hmac`, `crypto/sha256` |

The base58btc, multibase/CID and CBOR encoders are written by hand separately in each toolchain; the two share no code.

## Primitive validation

Before computing any vector, each toolchain checks its primitives against published vectors and aborts on any failure. Both pass all of them:

- SHA-256 `"abc"` (FIPS 180-2 B.1)
- Ed25519 RFC 8032 §7.1 TEST 1 (public key and signature)
- HKDF-SHA256 RFC 5869 A.1 (PRK and OKM) and A.3 (zero-length salt and info, as used by `channelToken`)
- AES-128-GCM, McGrew–Viega GCM specification Test Cases 2 and 4
- base58btc, draft-msporny-base58 examples; base32, RFC 4648 §10
- CIDv1 `raw`/sha2-256 of the empty byte string (`bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`)

## Files

Fixed inputs named by a label are `SHA-256(UTF-8("agora-test-vectors/" || label))`, truncated to the stated length. Where the spec requires randomness (nonces, `contentKey`, PoW challenge), the value is fixed for the vector and the file says so.

| File | Construction | Spec |
|---|---|---|
| `jws.json` | JWS General JSON Serialization, RFC 7797 `b64:false` detached, Ed25519. Cases: single signer (`RelayAd`); two signers (`ServiceAgreement`); negative, missing required signer; threshold 2-of-3 valid; negative, threshold with duplicated signer DID. Each case gives protected header JSON and base64url, signing input, signature, and the full `sig` text | §13.1.1, §10.5.1, §4.1 |
| `channel-token.json` | `channelToken` for `keyEpoch` 0, 1, 2^32 | §5.2.2, §13.3 |
| `sealed-envelope.json` | Sealed envelope AES-128-GCM with the given exporter output, AAD, fixed nonce | §5.2.2 |
| `routing-envelope.json` | `SignedFields` CBOR, `admissionSig`, envelope `id` CID, outer routing envelope. Chained: the token comes from `channel-token.json` and the sealed envelope from `sealed-envelope.json` | §5.2.2, §13.1 |
| `chunked-blob.json` | Chunked content-key blob: an empty file, a 14-byte single chunk, and a 263,144-byte two-chunk file (pattern `j mod 251`). Per chunk: nonce, AAD, block, block CID. The root block is not included (see below) | §14.3.4 |
| `device-binding.json` | `did:key` identity, leaf `signature_key`, `agora_device_binding` extension data | §5.2.1, §2.1 |
| `http-pow.json` | `Agora-PoW-Challenge` / `Agora-PoW` headers, difficulty 20, smallest 8-byte nonce meeting it, a negative nonce, and a check of the spec's own example | §10.5.2, §11.6 |

The CBOR encodings use RFC 8949 §4.2.1 deterministic key order. The spec does not require that order; it is one valid encoding, and verifiers work on the received bytes.

## Regenerate and verify

```sh
tools/regen.sh                              # generate in Python to a staging dir, Go checks it, Python re-checks, then install
python3 tools/agora_tv.py check             # Python: recompute everything and compare with the JSON files
(cd tools/go && go run . check)             # Go: recompute everything and compare with the JSON files
python3 tools/agora_tv.py primitives        # published-vector checks only
(cd tools/go && go run . primitives)
```

The Go check compares in both directions: every value it computes must match the file, and every non-descriptive value in the file must be one it recomputed. Only the keys `construction`, `spec`, `notes`, `reason` and `pattern` are skipped.

## Spec ambiguities and gaps

1. **Routing envelope `id` (§13.1 vs §5.2.2).** §13.1 says the `id` is "the CID of the complete encoded routing envelope". §5.2.2 says it is the CID of the `signed` bytes only. These vectors follow §5.2.2.
2. **dag-pb root block (§14.3.4).** The root CID is omitted because the encoding is not fully specified. Open points:
   - Is an "empty `Name`" absent from the PBLink or present with zero length? The two give different bytes.
   - Are UnixFS `blocksizes` packed or unpacked?
   - Is the UnixFS `Data` field absent?
   - What CID version and hash does the root use?
   - §13.1 says every CID uses codec `raw`, which contradicts the `dag-pb` (0x70) root.
3. **Coverage still required by §13.1.1/§13.3 but not produced here:**
   - The JWS negatives for `b64` true or absent, a wrong `alg`, a `cty`/`agoraType` mismatch, and a re-serialized body.
   - At least five signed object types (these vectors have three).
   - The broadcast payload (§5.2.1.4) and group-encrypted blob (§3.4) AEADs.
   - The other §13.3 derivations.
