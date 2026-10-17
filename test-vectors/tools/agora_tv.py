#!/usr/bin/env python3
"""Agora test vectors, Python toolchain (pyca/cryptography).

  agora_tv.py primitives        validate primitives against published vectors
  agora_tv.py generate OUTDIR   compute all vectors and write JSON files
  agora_tv.py check [DIR]       recompute all vectors and compare with JSON files

The Go program in tools/go performs the same computations independently.
"""
import base64
import json
import os
import sys

import cryptography
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.dirname(HERE)

# Descriptive keys are not computed values; both checkers skip them.
DESCRIPTIVE = {"construction", "spec", "notes", "reason", "pattern", "toolchain"}


# ---------------------------------------------------------------- primitives

def sha256(data):
    h = hashes.Hash(hashes.SHA256())
    h.update(data)
    return h.finalize()


def hmac_sha256(key, data):
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def hkdf_sha256(ikm, salt, info, length):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def ed_pub(seed):
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw)


def ed_sign(seed, msg):
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)


def ed_verify(pub, sig, msg):
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except InvalidSignature:
        return False


def gcm_seal(key, nonce, pt, aad):
    return AESGCM(key).encrypt(nonce, pt, aad)


def gcm_open(key, nonce, ct, aad):
    return AESGCM(key).decrypt(nonce, ct, aad)


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data):
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * zeros + out


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64std(data):
    return base64.b64encode(data).decode()


def cid_raw(data):
    return bytes([0x01, 0x55, 0x12, 0x20]) + sha256(data)


def cid_text(cid):
    return "b" + base64.b32encode(cid).decode().rstrip("=").lower()


def did_key(pub):
    return "did:key:z" + b58encode(bytes([0xED, 0x01]) + pub)


def u64(n):
    return n.to_bytes(8, "big")


def leading_zero_bits(h):
    bits = 0
    for b in h:
        if b == 0:
            bits += 8
            continue
        bits += 8 - b.bit_length()
        break
    return bits


# Hand-written CBOR (RFC 8949) for the few shapes needed.
def cbor_head(major, n):
    if n < 24:
        return bytes([(major << 5) | n])
    for ai, width in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if n < (1 << (8 * width)):
            return bytes([(major << 5) | ai]) + n.to_bytes(width, "big")
    raise ValueError("too large")


def cbor_uint(n):
    return cbor_head(0, n)


def cbor_bstr(b):
    return cbor_head(2, len(b)) + b


def cbor_tstr(s):
    b = s.encode()
    return cbor_head(3, len(b)) + b


def cbor_map(pairs):
    """pairs: list of (text key, encoded value); sorted per RFC 8949 4.2.1."""
    enc = sorted(((cbor_tstr(k), v) for k, v in pairs), key=lambda kv: kv[0])
    return cbor_head(5, len(enc)) + b"".join(k + v for k, v in enc)


# ------------------------------------------------------ published vectors

def primitives():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(("PASS" if good else "FAIL"), name)

    # SHA-256 "abc" (FIPS 180-2 Appendix B.1)
    check("SHA-256 abc", sha256(b"abc").hex(),
          "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    # Ed25519 RFC 8032 section 7.1 TEST 1
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    check("Ed25519 RFC8032 T1 pub", ed_pub(sk).hex(),
          "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    check("Ed25519 RFC8032 T1 sig", ed_sign(sk, b"").hex(),
          "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065"
          "224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    # HKDF RFC 5869 A.1 and A.3 (A.3: zero-length salt and info)
    ikm = bytes([0x0B] * 22)
    check("HKDF RFC5869 A.1 PRK",
          hmac_sha256(bytes.fromhex("000102030405060708090a0b0c"), ikm).hex(),
          "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5")
    check("HKDF RFC5869 A.1 OKM",
          hkdf_sha256(ikm, bytes.fromhex("000102030405060708090a0b0c"),
                      bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42).hex(),
          "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")
    check("HKDF RFC5869 A.3 OKM", hkdf_sha256(ikm, b"", b"", 42).hex(),
          "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8")
    # AES-128-GCM, McGrew-Viega GCM spec Test Case 2 and Test Case 4
    check("AES-GCM MV TC2", gcm_seal(bytes(16), bytes(12), bytes(16), b"").hex(),
          "0388dace60b6a392f328c2b971b2fe78" "ab6e47d42cec13bdf53a67b21257bddf")
    k = bytes.fromhex("feffe9928665731c6d6a8f9467308308")
    p = bytes.fromhex("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
                      "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39")
    a = bytes.fromhex("feedfacedeadbeeffeedfacedeadbeefabaddad2")
    iv = bytes.fromhex("cafebabefacedbaddecaf888")
    check("AES-GCM MV TC4", gcm_seal(k, iv, p, a).hex(),
          "42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e"
          "21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091"
          "5bc94fbc3221a5db94fae95ae7121a47")
    # base58btc, draft-msporny-base58-03 section 5
    check("base58 Hello World!", b58encode(b"Hello World!"), "2NEpo7TZRRrLZSi2U")
    check("base58 leading zeros", b58encode(bytes.fromhex("0000287fb4cd")), "11233QC4")
    # base32, RFC 4648 section 10
    check("base32 foobar", base64.b32encode(b"foobar").decode(), "MZXW6YTBOI======")
    # CIDv1 raw sha2-256 of the empty byte string (well-known IPFS identity of an empty raw block)
    check("CID empty raw", cid_text(cid_raw(b"")),
          "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku")
    print("toolchain: pyca/cryptography", cryptography.__version__)
    return ok


# ------------------------------------------------------------ vectors

def fixed(label, n=32):
    return sha256(("agora-test-vectors/" + label).encode())[:n]


FIXED_NOTE = ("Fixed inputs named by a label are SHA-256(UTF-8(\"agora-test-vectors/\" || label)), "
              "truncated to the stated length.")


def key(label):
    seed = fixed(label)
    return {"seedLabel": label, "seedHex": seed.hex(), "publicKeyHex": ed_pub(seed).hex()}


def channel_token_vectors():
    seed = fixed("admission-key")
    out = []
    for epoch in (0, 1, 4294967296):
        info = b"agora channel token" + u64(epoch)
        out.append({
            "inputs": {"seedLabel": "admission-key", "seedHex": seed.hex(),
                       "keyEpoch": epoch, "saltHex": ""},
            "intermediates": {"infoHex": info.hex(),
                              "prkHex": hmac_sha256(bytes(32), seed).hex()},
            "outputs": {"channelTokenHex": hkdf_sha256(seed, b"", info, 32).hex()},
        })
    return {
        "construction": "channelToken derivation",
        "spec": "§5.2.2 Channel Admission; §13.3 label 'agora channel token'",
        "notes": [FIXED_NOTE,
                  "channelToken = HKDF-SHA256(IKM = seed, salt = zero-length, "
                  "info = \"agora channel token\" || uint64be(keyEpoch), L = 32).",
                  "prkHex is the RFC 5869 extract output; a zero-length salt is HashLen zero bytes."],
        "vectors": out,
    }


SEALED_PLAINTEXT = b"agora test vector: stand-in bytes for a serialized MLSMessage (not valid MLS)"


def sealed_vector(channel_token):
    k = fixed("sealed-envelope-exporter-output", 16)
    nonce = fixed("sealed-envelope-nonce", 12)
    epoch = 7
    aad = b"agora/sealed/v1" + channel_token + u64(epoch)
    ct = gcm_seal(k, nonce, SEALED_PLAINTEXT, aad)
    assert gcm_open(k, nonce, ct, aad) == SEALED_PLAINTEXT
    return {
        "inputs": {"exporterOutputLabel": "sealed-envelope-exporter-output",
                   "keyHex": k.hex(), "channelTokenHex": channel_token.hex(),
                   "epoch": epoch, "nonceLabel": "sealed-envelope-nonce",
                   "nonceHex": nonce.hex(), "plaintextHex": SEALED_PLAINTEXT.hex()},
        "intermediates": {"aadHex": aad.hex()},
        "outputs": {"ciphertextAndTagHex": ct.hex(), "tagHex": ct[-16:].hex(),
                    "sealedEnvelopeHex": (nonce + ct).hex()},
    }, nonce + ct


def routing_vector(channel_token, sealed):
    seed = fixed("admission-key")
    ts, expiry = 1792195200000, 1792800000000
    signed = cbor_map([("ctx", cbor_tstr("agora/envelope/v1")),
                       ("channelToken", cbor_bstr(channel_token)),
                       ("ts", cbor_uint(ts)),
                       ("expiryHint", cbor_uint(expiry)),
                       ("sealedEnvelope", cbor_bstr(sealed))])
    sig = ed_sign(seed, signed)
    assert ed_verify(ed_pub(seed), sig, signed)
    env = cbor_map([("signed", cbor_bstr(signed)), ("admissionSig", cbor_bstr(sig))])
    cid = cid_raw(signed)
    return {
        "construction": "Routing envelope: admissionSig and envelope id",
        "spec": "§5.2.2 Outer Routing Envelope; §13.1.1 Admission signatures; §13.1 Content identifiers",
        "notes": [FIXED_NOTE,
                  "The admission key is the keyEpoch 0 key of channel-token.json; channelToken is its epoch 0 token.",
                  "sealedEnvelope is sealedEnvelopeHex from sealed-envelope.json.",
                  "SignedFields and the outer map are encoded with RFC 8949 section 4.2.1 core deterministic "
                  "key order and preferred integer widths. The spec does not require this order; it is one "
                  "valid encoding, and verifiers MUST use the signed bytes as received.",
                  "admissionSig = Ed25519(admission seed, signed bytes). id = CIDv1(raw 0x55, sha2-256) "
                  "of the signed bytes only (§5.2.2)."],
        "vectors": [{
            "inputs": {"admissionKey": key("admission-key"),
                       "channelTokenHex": channel_token.hex(), "ts": ts, "expiryHint": expiry,
                       "sealedEnvelopeHex": sealed.hex()},
            "intermediates": {"signedHex": signed.hex()},
            "outputs": {"admissionSigHex": sig.hex(), "idCidBytesHex": cid.hex(),
                        "idCidText": cid_text(cid), "routingEnvelopeHex": env.hex()},
        }],
    }


CHUNK = 262144


def chunk_case(label, data, key_bytes):
    n = max(1, -(-len(data) // CHUNK))
    blocks = []
    for i in range(n):
        chunk = data[i * CHUNK:min((i + 1) * CHUNK, len(data))]
        nonce = i.to_bytes(12, "big")
        aad = b"agora/chunk/v1" + u64(i) + u64(n) + bytes([1 if i == n - 1 else 0])
        blk = gcm_seal(key_bytes, nonce, chunk, aad)
        assert gcm_open(key_bytes, nonce, blk, aad) == chunk
        cid = cid_raw(blk)
        blocks.append({"index": i, "plaintextLength": len(chunk), "nonceHex": nonce.hex(),
                       "aadHex": aad.hex(), "blockLength": len(blk), "blockSha256Hex": sha256(blk).hex(),
                       "blockHex": blk.hex(), "blockCidText": cid_text(cid)})
    return {"name": label, "plaintextSize": len(data), "plaintextSha256Hex": sha256(data).hex(),
            "chunkCount": n, "blocks": blocks}


def big_file():
    return bytes(j % 251 for j in range(CHUNK + 1000))


def chunked_vectors():
    k = fixed("chunk-content-key", 16)
    small = b"Hello, Agora!\n"
    cases = [chunk_case("empty-file", b"", k), chunk_case("single-chunk", small, k),
             chunk_case("two-chunk", big_file(), k)]
    cases[1]["plaintextHex"] = small.hex()
    cases[2]["pattern"] = "byte j of the file = j mod 251, for j in 0 .. 263143 (262144 + 1000 bytes)"
    return {
        "construction": "Chunked content-key blob encryption",
        "spec": "§14.3.4 Blobs; §13.3 label 'agora/chunk/v1'; §13.1 Content identifiers",
        "notes": [FIXED_NOTE,
                  "contentKey is fixed here; the spec requires a fresh random key per file.",
                  "Chunk size is fixed at 262,144 bytes by the spec (Appendix C), so the multi-chunk case "
                  "uses a 263,144-byte file (2 chunks).",
                  "nonce[i] = i as 96-bit big-endian; aad[i] = \"agora/chunk/v1\" || uint64be(i) || "
                  "uint64be(n) || uint8(final). block = ciphertext || 16-byte tag.",
                  "The dag-pb root block and its CID are NOT included: the root block encoding is "
                  "underspecified (see README, ambiguities)."],
        "contentKeyLabel": "chunk-content-key", "contentKeyHex": k.hex(),
        "contentKeyBase64url": b64url(k),
        "vectors": cases,
    }


def device_binding_vectors():
    ident = fixed("did-key-identity")
    leaf = fixed("device-leaf-signature-key")
    leaf_pub = ed_pub(leaf)
    msg = "agora/v1/device-binding".encode() + leaf_pub
    sig = ed_sign(ident, msg)
    assert ed_verify(ed_pub(ident), sig, msg)
    return {
        "construction": "did:key device binding (agora_device_binding, 0xF0A1)",
        "spec": "§5.2.1 (definition), §2.1, §13.3 label 'agora/v1/device-binding'",
        "notes": [FIXED_NOTE,
                  "extensionData = Ed25519(identity seed, UTF-8(\"agora/v1/device-binding\") || signature_key). "
                  "did:key = \"did:key:z\" || base58btc(0xed 0x01 || identity public key)."],
        "vectors": [{
            "inputs": {"identityKey": key("did-key-identity"),
                       "leafSignatureKey": key("device-leaf-signature-key")},
            "intermediates": {"didKey": did_key(ed_pub(ident)), "signedMessageHex": msg.hex()},
            "outputs": {"extensionDataHex": sig.hex()},
        }],
    }


# --- JWS

RELAY_AD_BODY = ('{"did":"did:web:relay.example.com","manifestURL":"https://relay.example.com/'
                 '.well-known/agora-relay","endpoints":{"webTransport":"https://relay.example.com/v1/'
                 'agora/wt","webSocket":"wss://relay.example.com/v1/agora/ws","onion":"ws://examplerelay3'
                 'xyzabc.onion/v1/agora/ws","jmapSync":"https://relay.example.com/v1/agora/jmap"},'
                 '"serviceTiers":[{"id":"standard","retentionDays":30,"bandwidthTierGbPerMonth":100}],'
                 '"ts":"2026-03-12T00:00:00Z"}')

SERVICE_AGREEMENT_BODY = ('{"serviceType":"relay","provider":"did:web:relay.example.com","billing":"%s",'
                          '"endpoint":"https://relay.example.com/v1/agora/admission-keys",'
                          '"contact":"mailto:io-liaison@co.example.com","retentionDays":90,'
                          '"bandwidthTierGbPerMonth":100,"storageQuotaGb":50,"replicationFloor":2,'
                          '"observationBudget":{"connectionLogRetentionDays":7,"extensions":[]},'
                          '"supersedes":null,"validFrom":"2026-03-12T00:00:00Z",'
                          '"validUntil":"2027-03-12T00:00:00Z"}')

GUARDIAN_BODY = ('{"schemaVersion":1,"seq":42,"prevStateCID":"%s","owner":"did:web:owner.example.com",'
                 '"guardian":{"dids":["did:web:g1.example.com","did:web:g2.example.com",'
                 '"did:web:g3.example.com"],"threshold":2,"delaySeconds":259200},'
                 '"pendingTransfer":{"newOwner":"did:web:newowner.example.com","ts":"2026-10-17T00:00:00Z"}}')


def protected_header(kid, cty, typ):
    return ('{"alg":"EdDSA","b64":false,"crit":["b64"],"kid":"%s","cty":"%s","agoraType":"%s"}'
            % (kid, cty, typ))


def jws_entry(did, kid, label, cty, typ, body):
    seed = fixed(label)
    ph = protected_header(kid, cty, typ)
    pb64 = b64url(ph.encode())
    si = pb64.encode() + b"." + body
    sig = ed_sign(seed, si)
    return {"did": did, "kid": kid, "key": key(label), "protectedHeaderJson": ph,
            "protectedB64": pb64, "signingInputHex": si.hex(),
            "signatureHex": sig.hex(), "signatureB64": b64url(sig)}


def sig_json(entries):
    return '{"signatures":[%s]}' % ",".join(
        '{"protected":"%s","signature":"%s"}' % (e["protectedB64"], e["signatureB64"]) for e in entries)


def jws_case(name, typ, body, signers, expected, reason, extra=None):
    cty = "application/json"
    entries = [jws_entry(d, k, lbl, cty, typ, body) for d, k, lbl in signers]
    for e in entries:
        assert ed_verify(bytes.fromhex(e["key"]["publicKeyHex"]), bytes.fromhex(e["signatureHex"]),
                         bytes.fromhex(e["signingInputHex"]))
    case = {"name": name, "envelope": {"type": typ, "contentType": cty, "bodyText": body.decode(),
                                       "bodyHex": body.hex(), "sig": sig_json(entries)},
            "signers": entries, "expected": expected, "reason": reason}
    case.update(extra or {})
    return case


def jws_vectors():
    billing_did = did_key(ed_pub(fixed("billing")))
    billing_kid = billing_did + "#" + billing_did[len("did:key:"):]
    relay = ("did:web:relay.example.com", "did:web:relay.example.com#key-1", "relay-provider")
    billing = (billing_did, billing_kid, "billing")
    sa_body = (SERVICE_AGREEMENT_BODY % billing_did).encode()
    g_body = (GUARDIAN_BODY % cid_text(cid_raw(b"agora-test-vectors/previous-space-state"))).encode()
    g1a = ("did:web:g1.example.com", "did:web:g1.example.com#key-1", "guardian-1-key-1")
    g1b = ("did:web:g1.example.com", "did:web:g1.example.com#key-2", "guardian-1-key-2")
    g2 = ("did:web:g2.example.com", "did:web:g2.example.com#key-1", "guardian-2")
    thr = {"candidateDids": ["did:web:g1.example.com", "did:web:g2.example.com",
                             "did:web:g3.example.com"], "threshold": 2}
    sa_t, rad_t, ss_t = ("urn:agora:type:ServiceAgreement", "urn:agora:type:RelayAd",
                         "urn:agora:type:SpaceState")
    cases = [
        jws_case("single-signer-relayad", rad_t, RELAY_AD_BODY.encode(), [relay], "accept",
                 "one required signer (the Relay, `did`), §10.5.1",
                 {"requiredSigners": ["did:web:relay.example.com"]}),
        jws_case("two-signer-serviceagreement", sa_t, sa_body, [relay, billing], "accept",
                 "both required signers (provider and billing) present, §10.5.1",
                 {"requiredSigners": ["did:web:relay.example.com", billing_did]}),
        jws_case("negative-missing-required-signer", sa_t, sa_body, [billing], "reject",
                 "ServiceAgreement requires provider and billing entries; provider entry missing. "
                 "The billing entry itself is cryptographically valid.",
                 {"requiredSigners": ["did:web:relay.example.com", billing_did]}),
        jws_case("threshold-2-of-3-valid", ss_t, g_body, [g1a, g2], "accept",
                 "entries from 2 distinct candidate DIDs, threshold 2, §4.1 / §13.1.1", thr),
        jws_case("negative-threshold-duplicate-did", ss_t, g_body, [g1a, g1b], "reject",
                 "two entries whose kids name the same DID (g1, two different keys); both signatures are "
                 "cryptographically valid, but only 1 distinct DID < threshold 2 and duplicate DIDs MUST "
                 "be rejected, §13.1.1", thr),
    ]
    return {
        "construction": "JWS General JSON Serialization, RFC 7797 unencoded detached payload, EdDSA/Ed25519",
        "spec": "§13.1.1 Signing; §10.5.1 (ServiceAgreement, RelayAd signers); §4.1 (guardian threshold)",
        "notes": [FIXED_NOTE,
                  "Protected header member order and the JSON text of `sig` are as shown; the spec fixes "
                  "neither, and verifiers use the received `protected` value. All JSON is compact.",
                  "signingInput = ASCII(BASE64URL(UTF8(protected header))) || \".\" || body.",
                  "The guardian body is an abbreviated Space state proposal, not a complete Space state "
                  "document; it exercises the signature-set rules only.",
                  "DID resolution is out of scope: each entry gives the public key its kid resolves to."],
        "vectors": cases,
    }


def pow_vectors():
    challenge = fixed("pow-challenge", 32)
    difficulty, expires = 20, 30
    n = 0
    while leading_zero_bits(sha256(challenge + u64(n))) < difficulty:
        n += 1
    nonce = u64(n)
    h = sha256(challenge + nonce)
    bad = u64(0)
    hb = sha256(challenge + bad)
    ex_c = base64.b64decode("RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=")
    ex_n = base64.b64decode("AAAAAAAXBKY=")
    ex_h = sha256(ex_c + ex_n)
    return {
        "construction": "HTTP proof-of-work challenge and response",
        "spec": "§10.5.2 HTTP endpoints; leading-zero-bit count as §11.6",
        "notes": [FIXED_NOTE,
                  "challenge is fixed here; the spec requires 32 random bytes per challenge.",
                  "nonce is the smallest 8-byte big-endian counter meeting difficulty, so both toolchains "
                  "find it independently.",
                  "Header values are RFC 9651 Dictionaries; Byte Sequences are standard base64 with padding."],
        "vectors": [{
            "inputs": {"challengeLabel": "pow-challenge", "challengeHex": challenge.hex(),
                       "difficulty": difficulty, "expires": expires},
            "outputs": {"challengeHeader": "Agora-PoW-Challenge: challenge=:%s:, difficulty=%d, expires=%d"
                        % (b64std(challenge), difficulty, expires),
                        "nonceHex": nonce.hex(), "hashHex": h.hex(), "leadingZeroBits": leading_zero_bits(h),
                        "powHeader": "Agora-PoW: challenge=:%s:, nonce=:%s:" % (b64std(challenge), b64std(nonce))},
            "negative": {"nonceHex": bad.hex(), "hashHex": hb.hex(), "leadingZeroBits": leading_zero_bits(hb),
                         "expected": "reject"},
        }],
        "specExample": {"challengeHex": ex_c.hex(), "nonceHex": ex_n.hex(), "hashHex": ex_h.hex(),
                        "leadingZeroBits": leading_zero_bits(ex_h),
                        "meetsDifficulty20": leading_zero_bits(ex_h) >= 20},
    }


def build_all():
    ct = channel_token_vectors()
    token0 = bytes.fromhex(ct["vectors"][0]["outputs"]["channelTokenHex"])
    sv, sealed = sealed_vector(token0)
    sealed_doc = {
        "construction": "Sealed envelope AEAD",
        "spec": "§5.2.2 Sealed Envelope; §13.3 labels 'agora sealed envelope', 'agora/sealed/v1'",
        "notes": [FIXED_NOTE,
                  "key is the given MLS-Exporter(\"agora sealed envelope\", group_id, 16) output; MLS is not "
                  "implemented here.",
                  "nonce is FIXED for the vector; the spec requires a fresh random 12-byte nonce per envelope.",
                  "plaintext is opaque stand-in bytes, not a valid MLSMessage.",
                  "channelToken is the keyEpoch 0 token of channel-token.json.",
                  "aad = \"agora/sealed/v1\" || channelToken || uint64be(epoch); sealedEnvelope = nonce || "
                  "ciphertext || tag (AES-128-GCM)."],
        "vectors": [sv],
    }
    return {
        "channel-token.json": ct,
        "sealed-envelope.json": sealed_doc,
        "routing-envelope.json": routing_vector(token0, sealed),
        "chunked-blob.json": chunked_vectors(),
        "device-binding.json": device_binding_vectors(),
        "jws.json": jws_vectors(),
        "http-pow.json": pow_vectors(),
    }


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in DESCRIPTIVE:
                continue
            out.update(flatten(v, prefix + k + "."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, prefix + str(i) + "."))
    else:
        out[prefix[:-1]] = obj
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "primitives":
        sys.exit(0 if primitives() else 1)
    if cmd == "generate":
        if not primitives():
            sys.exit("primitive validation failed")
        outdir = sys.argv[2]
        for name, doc in build_all().items():
            with open(os.path.join(outdir, name), "w") as f:
                json.dump(doc, f, indent=1)
                f.write("\n")
        return
    if cmd == "check":
        if not primitives():
            sys.exit("primitive validation failed")
        d = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DIR
        bad = 0
        for name, doc in build_all().items():
            with open(os.path.join(d, name)) as f:
                stored = flatten(json.load(f))
            computed = flatten(doc)
            if stored != computed:
                bad += 1
                for k in sorted(set(stored) | set(computed)):
                    if stored.get(k) != computed.get(k):
                        print("MISMATCH", name, k)
            else:
                print("OK", name, len(computed), "values")
        sys.exit(1 if bad else 0)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
