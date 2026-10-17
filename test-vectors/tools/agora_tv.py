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

try:  # optional third cross-check of the hand-written CBOR; never a source of values
    import cbor2
except ImportError:
    cbor2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.dirname(HERE)

# Descriptive keys are not computed values; both checkers skip them.
DESCRIPTIVE = {"construction", "spec", "notes", "reason", "pattern", "toolchain"}

# Ciphertexts longer than this are stored as length, SHA-256 and first/last 64 bytes.
INLINE_MAX = 4096

CBOR_ITEMS = []  # (encoded bytes, expected Python value) for the cbor2 cross-check


# ---------------------------------------------------------------- primitives

def digest(alg, data):
    h = hashes.Hash(alg)
    h.update(data)
    return h.finalize()


def sha256(data):
    return digest(hashes.SHA256(), data)


def sha1(data):
    return digest(hashes.SHA1(), data)


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
    ct = AESGCM(key).encrypt(nonce, pt, aad)
    assert AESGCM(key).decrypt(nonce, ct, aad) == pt
    return ct


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


def cid(codec, data):
    return bytes([0x01, codec, 0x12, 0x20]) + sha256(data)


def cid_raw(data):
    return cid(0x55, data)


def cid_text(c):
    return "b" + base64.b32encode(c).decode().rstrip("=").lower()


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


def cbor_map(pairs, expected):
    """pairs: list of (text key, encoded value); sorted per RFC 8949 4.2.1."""
    enc = sorted(((cbor_tstr(k), v) for k, v in pairs), key=lambda kv: kv[0])
    out = cbor_head(5, len(enc)) + b"".join(k + v for k, v in enc)
    CBOR_ITEMS.append((out, expected))
    return out


def typed_envelope(typ, cty, body, sig):
    return cbor_map([("type", cbor_tstr(typ)), ("contentType", cbor_tstr(cty)),
                     ("body", cbor_bstr(body)), ("sig", cbor_tstr(sig))],
                    {"type": typ, "contentType": cty, "body": body, "sig": sig})


# Hand-written protobuf for dag-pb and UnixFS.
def varint(n):
    out = b""
    while n >= 0x80:
        out += bytes([(n & 0x7F) | 0x80])
        n >>= 7
    return out + bytes([n])


def pb_varint(field, n):
    return varint(field << 3) + varint(n)


def pb_bytes(field, b):
    return varint((field << 3) | 2) + varint(len(b)) + b


def unixfs_file(sizes):
    return pb_varint(1, 2) + pb_varint(3, sum(sizes)) + b"".join(pb_varint(4, s) for s in sizes)


def dagpb_node(links, data):
    """links: list of (binary CID, Tsize); Links before Data, Name present and empty."""
    return b"".join(pb_bytes(2, pb_bytes(1, c) + pb_bytes(2, b"") + pb_varint(3, t)) for c, t in links) \
        + pb_bytes(1, data)


def cidv0(data):
    return b58encode(bytes([0x12, 0x20]) + sha256(data))


# ------------------------------------------------------ published vectors

def primitives():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(("PASS" if good else "FAIL"), name)

    # SHA-256 and SHA-1 "abc" (FIPS 180-2 Appendix B.1 and A.1)
    check("SHA-256 abc", sha256(b"abc").hex(),
          "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    check("SHA-1 abc", sha1(b"abc").hex(), "a9993e364706816aba3e25717850c26c9cd0d89d")
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
    # dag-pb + UnixFS: the well-known IPFS empty directory and empty file nodes
    empty_dir = dagpb_node([], pb_varint(1, 1))
    check("UnixFS empty directory CIDv0", cidv0(empty_dir), "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
    check("UnixFS empty directory CIDv1", cid_text(cid(0x70, empty_dir)),
          "bafybeiczsscdsbs7ffqz55asqdf3smv6klcw3gofszvwlyarci47bgf354")
    check("UnixFS empty file CIDv0", cidv0(dagpb_node([], unixfs_file([]))),
          "QmbFMke1KXqnYyBBWxB74N4c5SBnJMVAiMNRcGu6x1AwQH")
    print("toolchain: pyca/cryptography", cryptography.__version__)
    return ok


# ------------------------------------------------------------ vectors

def fixed(label, n=32):
    return sha256(("agora-test-vectors/" + label).encode())[:n]


FIXED_NOTE = ("Fixed inputs named by a label are SHA-256(UTF-8(\"agora-test-vectors/\" || label)), "
              "truncated to the stated length.")
CBOR_NOTE = ("CBOR maps are encoded with RFC 8949 section 4.2.1 core deterministic key order and preferred "
             "integer widths. The spec does not require this order; it is one valid encoding, and receivers "
             "use the bytes as received.")


def key(label):
    seed = fixed(label)
    return {"seedLabel": label, "seedHex": seed.hex(), "publicKeyHex": ed_pub(seed).hex()}


def token(seed, epoch):
    return hkdf_sha256(seed, b"", b"agora channel token" + u64(epoch), 32)


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
    return {
        "inputs": {"exporterOutputLabel": "sealed-envelope-exporter-output",
                   "keyHex": k.hex(), "channelTokenHex": channel_token.hex(),
                   "epoch": epoch, "nonceLabel": "sealed-envelope-nonce",
                   "nonceHex": nonce.hex(), "plaintextHex": SEALED_PLAINTEXT.hex()},
        "intermediates": {"aadHex": aad.hex()},
        "outputs": {"ciphertextAndTagHex": ct.hex(), "tagHex": ct[-16:].hex(),
                    "sealedEnvelopeHex": (nonce + ct).hex()},
    }, nonce + ct


def routing_signed(channel_token, ts, payload_key, payload, expiry=None):
    pairs = [("ctx", cbor_tstr("agora/envelope/v1")), ("channelToken", cbor_bstr(channel_token)),
             ("ts", cbor_uint(ts)), (payload_key, cbor_bstr(payload))]
    exp = {"ctx": "agora/envelope/v1", "channelToken": channel_token, "ts": ts, payload_key: payload}
    if expiry is not None:
        pairs.append(("expiryHint", cbor_uint(expiry)))
        exp["expiryHint"] = expiry
    return cbor_map(pairs, exp)


def routing_envelope(signed, sig):
    return cbor_map([("signed", cbor_bstr(signed)), ("admissionSig", cbor_bstr(sig))],
                    {"signed": signed, "admissionSig": sig})


def routing_vector(channel_token, sealed):
    seed = fixed("admission-key")
    ts, expiry = 1792195200000, 1792800000000
    signed = routing_signed(channel_token, ts, "sealedEnvelope", sealed, expiry)
    sig = ed_sign(seed, signed)
    assert ed_verify(ed_pub(seed), sig, signed)
    env = routing_envelope(signed, sig)
    c = cid_raw(signed)
    return {
        "construction": "Routing envelope: admissionSig and envelope id",
        "spec": "§5.2.2 Outer Routing Envelope; §13.1.1 Admission signatures; §13.1 Content identifiers",
        "notes": [FIXED_NOTE, CBOR_NOTE,
                  "The admission key is the keyEpoch 0 key of channel-token.json; channelToken is its epoch 0 token.",
                  "sealedEnvelope is sealedEnvelopeHex from sealed-envelope.json.",
                  "admissionSig = Ed25519(admission seed, signed bytes). id = CIDv1(raw 0x55, sha2-256) "
                  "of the signed bytes only (§5.2.2)."],
        "vectors": [{
            "inputs": {"admissionKey": key("admission-key"),
                       "channelTokenHex": channel_token.hex(), "ts": ts, "expiryHint": expiry,
                       "sealedEnvelopeHex": sealed.hex()},
            "intermediates": {"signedHex": signed.hex()},
            "outputs": {"admissionSigHex": sig.hex(), "idCidBytesHex": c.hex(),
                        "idCidText": cid_text(c), "routingEnvelopeHex": env.hex()},
        }],
    }


CHUNK = 262144


def blob_fields(blk):
    """Inline hex up to INLINE_MAX bytes; otherwise length, SHA-256 and first/last 64 bytes."""
    f = {"blockLength": len(blk), "blockSha256Hex": sha256(blk).hex()}
    if len(blk) <= INLINE_MAX:
        f["blockHex"] = blk.hex()
    else:
        f["blockFirst64Hex"] = blk[:64].hex()
        f["blockLast64Hex"] = blk[-64:].hex()
    return f


def chunk_case(label, data, key_bytes):
    n = max(1, -(-len(data) // CHUNK))
    blocks, links = [], []
    for i in range(n):
        chunk = data[i * CHUNK:min((i + 1) * CHUNK, len(data))]
        nonce = i.to_bytes(12, "big")
        aad = b"agora/chunk/v1" + u64(i) + u64(n) + bytes([1 if i == n - 1 else 0])
        blk = gcm_seal(key_bytes, nonce, chunk, aad)
        c = cid_raw(blk)
        links.append((c, len(blk)))
        b = {"index": i, "plaintextLength": len(chunk), "nonceHex": nonce.hex(), "aadHex": aad.hex()}
        b.update(blob_fields(blk))
        b["blockCidText"] = cid_text(c)
        blocks.append(b)
    case = {"name": label, "plaintextSize": len(data), "plaintextSha256Hex": sha256(data).hex(),
            "chunkCount": n, "blocks": blocks}
    if n == 1:
        case["blobIdText"] = blocks[0]["blockCidText"]
    else:
        data_field = unixfs_file([t for _, t in links])
        root = dagpb_node(links, data_field)
        rc = cid(0x70, root)
        case["rootBlock"] = {"unixfsDataHex": data_field.hex(), "rootBlockHex": root.hex(),
                             "rootCidBytesHex": rc.hex(), "rootCidText": cid_text(rc)}
        case["blobIdText"] = cid_text(rc)
    return case


def pattern_file(size):
    return bytes(j % 251 for j in range(size))


def chunked_vectors():
    k = fixed("chunk-content-key", 16)
    small = b"Hello, Agora!\n"
    cases = [chunk_case("empty-file", b"", k), chunk_case("single-chunk", small, k),
             chunk_case("two-chunk", pattern_file(CHUNK + 1000), k),
             chunk_case("three-chunk", pattern_file(2 * CHUNK + 5), k)]
    cases[1]["plaintextHex"] = small.hex()
    cases[2]["pattern"] = "byte j of the file = j mod 251, for j in 0 .. 263143 (262144 + 1000 bytes)"
    cases[3]["pattern"] = "byte j of the file = j mod 251, for j in 0 .. 524292 (2 * 262144 + 5 bytes)"
    return {
        "construction": "Chunked content-key blob encryption and dag-pb root block",
        "spec": "§14.3.4 Blobs; §13.3 label 'agora/chunk/v1'; §13.1 Content identifiers",
        "notes": [FIXED_NOTE,
                  "contentKey is fixed here; the spec requires a fresh random key per file.",
                  "Chunk size is fixed at 262,144 bytes by the spec (Appendix C), so the multi-chunk cases "
                  "use 263,144-byte (2 chunks) and 524,293-byte (3 chunks) files.",
                  "nonce[i] = i as 96-bit big-endian; aad[i] = \"agora/chunk/v1\" || uint64be(i) || "
                  "uint64be(n) || uint8(final). block = ciphertext || 16-byte tag.",
                  "Blocks longer than 4096 bytes are given as blockLength, blockSha256Hex and their first "
                  "and last 64 bytes; the check scripts recompute each full block and compare its SHA-256.",
                  "Root block (n > 1): dag-pb PBNode with Links before Data; each PBLink = Hash (binary chunk "
                  "CID), Name (present, zero length), Tsize (block length). Data = UnixFS Type=File(2), "
                  "filesize = sum of block lengths, one non-packed blocksizes entry per block. Root CID = "
                  "CIDv1 dag-pb (0x70) sha2-256. blobIdText is the root CID for n > 1, else the chunk CID."],
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

AKR_BODY = ('{"agreement":"%s","ts":"2026-10-16T12:00:00Z","keys":[{"channelToken":"%s",'
            '"admissionPublicKey":"%s","replaces":"%s"}]}')

CAK_BODY = ('{"@type":"ChannelAdmissionKey","channelID":"%s","keyEpoch":1,"seed":"%s",'
            '"relays":["https://relay.example.net","https://relay2.example.org"],'
            '"archive":"https://archive.co.example.com"}')

BK_BODY = '{"@type":"BroadcastKey","channelID":"%s","keyEpoch":7,"key":"%s","notBefore":"2026-10-16T00:00:00Z"}'

BM_BODY = ('{"channelID":"%s","keyEpoch":7,"senderDID":"%s","device":"%s","seq":311,"message":{'
           '"senderMsgId":"01J3XM2C4V0Q6R9T8Y7W5E3B1A","body":"v2.1.0 released; see release notes for details.",'
           '"bodyType":"text/markdown;variant=commonmark","sentAt":"2026-04-22T09:00:00Z"}}')

CTY = "application/json"


def header(kid, typ, alg='"EdDSA"', b64="false", crit='["b64"]', cty=CTY):
    members = [("alg", alg), ("b64", b64), ("crit", crit), ("kid", '"%s"' % kid), ("cty", '"%s"' % cty),
               ("agoraType", '"%s"' % typ)]
    return "{" + ",".join('"%s":%s' % (k, v) for k, v in members if v is not None) + "}"


def jws_entry(signer, typ, body, ph=None):
    did, kid, label = signer
    seed = fixed(label)
    ph = ph or header(kid, typ)
    pb64 = b64url(ph.encode())
    si = pb64.encode() + b"." + body
    sig = ed_sign(seed, si)
    assert ed_verify(ed_pub(seed), sig, si)
    return {"did": did, "kid": kid, "key": key(label), "protectedHeaderJson": ph,
            "protectedB64": pb64, "signingInputHex": si.hex(),
            "signatureHex": sig.hex(), "signatureB64": b64url(sig)}


def sig_json(entries):
    return '{"signatures":[%s]}' % ",".join(
        '{"protected":"%s","signature":"%s"}' % (e["protectedB64"], e["signatureB64"]) for e in entries)


def envelope_doc(typ, body, entries):
    return {"type": typ, "contentType": CTY, "bodyText": body.decode(), "bodyHex": body.hex(),
            "sig": sig_json(entries)}


def jws_case(name, typ, body, signers, expected, reason, extra, headers=None, env_body=None):
    headers = headers or [None] * len(signers)
    entries = [jws_entry(s, typ, body, h) for s, h in zip(signers, headers)]
    case = {"name": name, "envelope": envelope_doc(typ, env_body or body, entries),
            "signers": entries, "expected": expected, "reason": reason}
    case.update(extra)
    if env_body is not None:
        case["signedBodyHex"] = body.hex()
    return case


def did_key_signer(label):
    d = did_key(ed_pub(fixed(label)))
    return (d, d + "#" + d[len("did:key:"):], label)


def jws_vectors():
    relay = ("did:web:relay.example.com", "did:web:relay.example.com#key-1", "relay-provider")
    billing = did_key_signer("billing")
    owner = did_key_signer("space-owner")
    sa_body = (SERVICE_AGREEMENT_BODY % billing[0]).encode()
    g_body = (GUARDIAN_BODY % cid_text(cid_raw(b"agora-test-vectors/previous-space-state"))).encode()
    g1a = ("did:web:g1.example.com", "did:web:g1.example.com#key-1", "guardian-1-key-1")
    g1b = ("did:web:g1.example.com", "did:web:g1.example.com#key-2", "guardian-1-key-2")
    g2 = ("did:web:g2.example.com", "did:web:g2.example.com#key-1", "guardian-2")
    thr = {"candidateDids": ["did:web:g1.example.com", "did:web:g2.example.com",
                             "did:web:g3.example.com"], "threshold": 2}
    req = lambda *dids: {"requiredSigners": list(dids)}
    T = "urn:agora:type:"
    rad = RELAY_AD_BODY.encode()

    sa_case = jws_case("two-signer-serviceagreement", T + "ServiceAgreement", sa_body, [relay, billing],
                       "accept", "both required signers (provider and billing) present, §10.5.1",
                       req(relay[0], billing[0]))
    sa_env = typed_envelope(T + "ServiceAgreement", CTY, sa_body, sa_case["envelope"]["sig"])
    sa_case["encodedEnvelopeHex"] = sa_env.hex()
    sa_case["envelopeCidText"] = cid_text(cid_raw(sa_env))
    sa_cid = cid_raw(sa_body)  # §10.5.3: agreement = CID of the signed body bytes
    sa_case["bodyCidText"] = cid_text(sa_cid)

    old_tok = token(fixed("admission-key"), 0)
    new_seed = fixed("admission-key-rotated")
    new_tok = token(new_seed, 1)
    akr_body = (AKR_BODY % (cid_text(sa_cid), b64url(new_tok), b64url(ed_pub(new_seed)), b64url(old_tok))).encode()
    cak_body = (CAK_BODY % (b64url(fixed("channel-id", 16)), b64url(new_seed))).encode()
    bk_body = (BK_BODY % (b64url(fixed("broadcast-channel-id", 16)),
                          b64url(fixed("broadcast-content-key", 16)))).encode()

    rk = relay[1]
    rt = T + "RelayAd"
    cases = [
        jws_case("single-signer-relayad", rt, rad, [relay], "accept",
                 "one required signer (the Relay, `did`), §10.5.1", req(relay[0])),
        sa_case,
        jws_case("negative-missing-required-signer", T + "ServiceAgreement", sa_body, [billing], "reject",
                 "ServiceAgreement requires provider and billing entries; provider entry missing. "
                 "The billing entry itself is cryptographically valid.", req(relay[0], billing[0])),
        jws_case("threshold-2-of-3-valid", T + "SpaceState", g_body, [g1a, g2], "accept",
                 "entries from 2 distinct candidate DIDs, threshold 2, §4.1 / §13.1.1", thr),
        jws_case("negative-threshold-duplicate-did", T + "SpaceState", g_body, [g1a, g1b], "reject",
                 "two entries whose kids name the same DID (g1, two different keys); both signatures are "
                 "cryptographically valid, but only 1 distinct DID < threshold 2 and duplicate DIDs MUST "
                 "be rejected, §13.1.1", thr),
        jws_case("admission-key-registration", T + "AdmissionKeyRegistration", akr_body, [billing], "accept",
                 "signed by the agreement's billing DID, §10.5.3; agreement = bodyCidText (CID of the "
                 "ServiceAgreement body bytes) of two-signer-serviceagreement; keys[0] is a rotation with replaces = the keyEpoch 0 token",
                 req(billing[0])),
        jws_case("channel-admission-key", T + "ChannelAdmissionKey", cak_body, [owner], "accept",
                 "signed by the Space owner, §3.4; seed is the rotated admission key of "
                 "admission-key-registration (keyEpoch 1)", req(owner[0])),
        jws_case("broadcast-key", T + "BroadcastKey", bk_body, [owner], "accept",
                 "signed by the Space owner, §3.4; used by broadcast-payload.json", req(owner[0])),
        jws_case("negative-b64-true", rt, rad, [relay], "reject", "b64 is true (§13.1.1 check 2)",
                 req(relay[0]), [header(rk, rt, b64="true")]),
        jws_case("negative-b64-absent", rt, rad, [relay], "reject",
                 "b64 member absent while crit still lists it (§13.1.1 check 2)",
                 req(relay[0]), [header(rk, rt, b64=None)]),
        jws_case("negative-b64-and-crit-absent", rt, rad, [relay], "reject",
                 "b64 and crit absent: an ordinary b64=true JWS header (§13.1.1 check 2)",
                 req(relay[0]), [header(rk, rt, b64=None, crit=None)]),
        jws_case("negative-crit-absent", rt, rad, [relay], "reject",
                 "b64 false but crit absent (§13.1.1 check 2; RFC 7797 section 6)",
                 req(relay[0]), [header(rk, rt, crit=None)]),
        jws_case("negative-alg-not-eddsa", rt, rad, [relay], "reject",
                 "alg is \"Ed25519\" rather than \"EdDSA\" (§13.1.1 check 2)",
                 req(relay[0]), [header(rk, rt, alg='"Ed25519"')]),
        jws_case("negative-cty-mismatch", rt, rad, [relay], "reject",
                 "header cty application/cbor, envelope contentType application/json (§13.1.1 check 2)",
                 req(relay[0]), [header(rk, rt, cty="application/cbor")]),
        jws_case("negative-agoratype-mismatch", rt, rad, [relay], "reject",
                 "header agoraType urn:agora:type:ServiceAgreement, envelope type urn:agora:type:RelayAd "
                 "(§13.1.1 check 2)", req(relay[0]), [header(rk, T + "ServiceAgreement")]),
        jws_case("negative-reserialized-body", rt, rad, [relay], "reject",
                 "signature made over the compact body (signedBodyHex); the envelope carries the same JSON "
                 "re-serialized with 2-space indentation, so check 5 fails (§13.1.1 byte-for-byte rule)",
                 req(relay[0]), None, json.dumps(json.loads(RELAY_AD_BODY), indent=2).encode()),
    ]
    return {
        "construction": "JWS General JSON Serialization, RFC 7797 unencoded detached payload, EdDSA/Ed25519",
        "spec": "§13.1.1 Signing; §10.5.1, §10.5.3, §3.4 (signers); §4.1 (guardian threshold)",
        "notes": [FIXED_NOTE, CBOR_NOTE,
                  "Protected header member order and the JSON text of `sig` are as shown; the spec fixes "
                  "neither, and verifiers use the received `protected` value. All JSON is compact.",
                  "signingInput = ASCII(BASE64URL(UTF8(protected header))) || \".\" || body.",
                  "Header negatives: the signature is a valid Ed25519 signature over that entry's own "
                  "signingInput, so rejection must come from the header checks, not the signature check.",
                  "The guardian body is an abbreviated Space state proposal, not a complete Space state "
                  "document; it exercises the signature-set rules only.",
                  "DID resolution is out of scope: each entry gives the public key its kid resolves to."],
        "vectors": cases,
    }


def broadcast_vector():
    adm_seed = fixed("broadcast-admission-key")
    epoch = 7
    tok = token(adm_seed, epoch)
    chan = fixed("broadcast-channel-id", 16)
    ckey = fixed("broadcast-content-key", 16)
    device = fixed("broadcast-device", 16)
    nonce = fixed("broadcast-nonce", 12)
    poster = did_key_signer("broadcast-poster")
    typ = "urn:agora:type:BroadcastMessage"
    body = (BM_BODY % (b64url(chan), poster[0], b64url(device))).encode()
    entry = jws_entry(poster, typ, body)
    env = envelope_doc(typ, body, [entry])
    plaintext = typed_envelope(typ, CTY, body, env["sig"])
    aad = b"agora/broadcast/v1" + tok
    payload = nonce + gcm_seal(ckey, nonce, plaintext, aad)
    ts = 1792195200000
    signed = routing_signed(tok, ts, "broadcastPayload", payload)
    sig = ed_sign(adm_seed, signed)
    renv = routing_envelope(signed, sig)
    return {
        "construction": "Broadcast payload AEAD inside a routing envelope",
        "spec": "§5.2.1.4 Message structure; §13.3 label 'agora/broadcast/v1'; §3.4 BroadcastKey; §13.1.1",
        "notes": [FIXED_NOTE, CBOR_NOTE,
                  "nonce is FIXED for the vector; the spec requires a fresh random 12-byte nonce per message.",
                  "contentKey and channelID equal the key and channelID of the broadcast-key vector in jws.json.",
                  "plaintext = encoded typed payload envelope {type, contentType, body, sig} of type "
                  "urn:agora:type:BroadcastMessage, sig by the poster's did:key.",
                  "broadcastPayload = nonce || AES-128-GCM(contentKey, nonce, plaintext, "
                  "\"agora/broadcast/v1\" || channelToken). channelToken is derived from the broadcast "
                  "admission key at keyEpoch 7, which signs the routing envelope."],
        "vectors": [{
            "inputs": {"admissionKey": key("broadcast-admission-key"), "keyEpoch": epoch,
                       "channelIdLabel": "broadcast-channel-id", "channelIdHex": chan.hex(),
                       "contentKeyLabel": "broadcast-content-key", "contentKeyHex": ckey.hex(),
                       "deviceLabel": "broadcast-device", "deviceHex": device.hex(),
                       "posterKey": key("broadcast-poster"), "nonceLabel": "broadcast-nonce",
                       "nonceHex": nonce.hex(), "ts": ts},
            "intermediates": {"channelTokenHex": tok.hex(), "posterDid": poster[0], "posterKid": poster[1],
                              "jws": {k: entry[k] for k in ("protectedHeaderJson", "protectedB64",
                                                            "signingInputHex", "signatureHex")},
                              "envelope": env, "plaintextEnvelopeHex": plaintext.hex(),
                              "aadHex": aad.hex(), "signedHex": signed.hex()},
            "outputs": {"broadcastPayloadHex": payload.hex(), "admissionSigHex": sig.hex(),
                        "idCidText": cid_text(cid_raw(signed)), "routingEnvelopeHex": renv.hex()},
        }],
    }


def aead_layouts():
    gk = fixed("group-blob-exporter-output", 16)
    gn = fixed("group-blob-nonce", 12)
    gpt = b"agora test vector: stand-in bytes for a CO record"
    epoch = 17
    gaad = b"agora/blob/v1" + u64(epoch)
    gblob = u64(epoch) + gn + gcm_seal(gk, gn, gpt, gaad)
    ak = fixed("asset-key", 16)
    an = fixed("asset-nonce", 12)
    apt = b"agora test vector: stand-in bytes for an icon image"
    ablob = an + gcm_seal(ak, an, apt, b"agora/asset/v1")
    hk = fixed("history-key", 16)
    hn = fixed("history-nonce", 12)
    hpt = b"agora test vector: stand-in bytes for a CBOR HistoryArchive"
    hblob = hn + gcm_seal(hk, hn, hpt, b"agora/history/v1")
    return {
        "construction": "AEAD layouts: group-encrypted blob, asset blob, history archive blob",
        "spec": "§3.4 (group-encrypted blob, 'agora/blob/v1'; assets, 'agora/asset/v1'); "
                "§2.6 (history, 'agora/history/v1'); §13.3",
        "notes": [FIXED_NOTE,
                  "All nonces and keys are FIXED for the vectors; the spec requires fresh random nonces "
                  "and, for the history blob, a fresh random key.",
                  "Group-encrypted blob: key is the given MLS-Exporter(\"agora blob\", group_id, 16) output; "
                  "blob = uint64be(epoch) || nonce || AES-128-GCM(key, nonce, record, \"agora/blob/v1\" || "
                  "uint64be(epoch)).",
                  "Asset blob = nonce || AES-128-GCM(assetKey, nonce, image, \"agora/asset/v1\").",
                  "History blob = nonce || AES-128-GCM(key, nonce, archive, \"agora/history/v1\").",
                  "Plaintexts are opaque stand-in bytes. cidText is the raw CID of the whole blob."],
        "groupEncryptedBlob": {
            "inputs": {"exporterOutputLabel": "group-blob-exporter-output", "keyHex": gk.hex(),
                       "epoch": epoch, "nonceLabel": "group-blob-nonce", "nonceHex": gn.hex(),
                       "plaintextHex": gpt.hex()},
            "intermediates": {"aadHex": gaad.hex()},
            "outputs": {"blobHex": gblob.hex(), "cidText": cid_text(cid_raw(gblob))}},
        "assetBlob": {
            "inputs": {"keyLabel": "asset-key", "keyHex": ak.hex(), "nonceLabel": "asset-nonce",
                       "nonceHex": an.hex(), "plaintextHex": apt.hex()},
            "intermediates": {"aadHex": b"agora/asset/v1".hex()},
            "outputs": {"blobHex": ablob.hex(), "cidText": cid_text(cid_raw(ablob))}},
        "historyBlob": {
            "inputs": {"keyLabel": "history-key", "keyHex": hk.hex(), "nonceLabel": "history-nonce",
                       "nonceHex": hn.hex(), "plaintextHex": hpt.hex()},
            "intermediates": {"aadHex": b"agora/history/v1".hex()},
            "outputs": {"blobHex": hblob.hex(), "cidText": cid_text(cid_raw(hblob))}},
    }


def derivations(token0):
    s = fixed("social-recovery-secret")
    sinfo = b"agora/v1/social-recovery-key"
    sseed = hkdf_sha256(s, b"", sinfo, 32)
    prf_out = fixed("webauthn-prf-output")
    winfo = b"agora/v1/webauthn-prf-wrap"
    cin = b"agora/commits/v1" + token0
    return {
        "construction": "Hash and KDF derivations of the §13.3 label registry",
        "spec": "§2.4.2 (social recovery key), §12.6 (WebAuthn PRF), §5.1.1 / §14.4.2 (commit stream), "
                "§10.3.4.6 (Mainline DHT infohash), §13.3",
        "notes": [FIXED_NOTE,
                  "socialRecoveryKey: seed = HKDF-SHA256(IKM = S, salt = zero-length, info = "
                  "\"agora/v1/social-recovery-key\", L = 32), used as an Ed25519 seed. S is fixed here.",
                  "webauthnPrf: PRF input first = SHA-256(UTF-8 \"agora/v1/webauthn-prf\").",
                  "webauthnPrfWrap: wrapping key = HKDF-SHA256(IKM = PRF output, salt = zero-length, info = "
                  "\"agora/v1/webauthn-prf-wrap\", L = 32). The PRF output is fixed here.",
                  "commitStream: SHA-256(\"agora/commits/v1\" || channelToken), channelToken = keyEpoch 0 "
                  "token of channel-token.json.",
                  "relayInfohash: SHA-1 of the 14 ASCII bytes \"agora-relay-v1\"."],
        "socialRecoveryKey": {
            "inputs": {"secretLabel": "social-recovery-secret", "secretHex": s.hex()},
            "intermediates": {"infoHex": sinfo.hex()},
            "outputs": {"seedHex": sseed.hex(), "publicKeyHex": ed_pub(sseed).hex()}},
        "webauthnPrf": {"outputs": {"prfFirstHex": sha256(b"agora/v1/webauthn-prf").hex()}},
        "webauthnPrfWrap": {
            "inputs": {"prfOutputLabel": "webauthn-prf-output", "prfOutputHex": prf_out.hex()},
            "intermediates": {"infoHex": winfo.hex()},
            "outputs": {"wrapKeyHex": hkdf_sha256(prf_out, b"", winfo, 32).hex()}},
        "commitStream": {
            "inputs": {"channelTokenHex": token0.hex()},
            "intermediates": {"inputHex": cin.hex()},
            "outputs": {"streamNameHex": sha256(cin).hex()}},
        "relayInfohash": {"outputs": {"infohashHex": sha1(b"agora-relay-v1").hex()}},
    }


def sfu_admission(token0):
    seed = fixed("admission-key")
    nonce = fixed("sfu-challenge-nonce", 32)
    sfu = "did:web:sfu.example.com"
    signed = cbor_map([("ctx", cbor_tstr("agora sfu admission")), ("sfu", cbor_tstr(sfu)),
                       ("nonce", cbor_bstr(nonce)), ("channelToken", cbor_bstr(token0))],
                      {"ctx": "agora sfu admission", "sfu": sfu, "nonce": nonce, "channelToken": token0})
    sig = ed_sign(seed, signed)
    assert ed_verify(ed_pub(seed), sig, signed)
    return {
        "construction": "SFU join admission signature",
        "spec": "§6.6 Admission; §13.3 label 'agora sfu admission'",
        "notes": [FIXED_NOTE, CBOR_NOTE,
                  "signed = CBOR sfu-admission {ctx, sfu, nonce, channelToken}; admissionSig = Ed25519(admission "
                  "seed, signed). The admission key and channelToken are the keyEpoch 0 values of "
                  "channel-token.json. The challenge nonce is fixed here; the SFU sends a fresh random one."],
        "vectors": [{
            "inputs": {"admissionKey": key("admission-key"), "channelTokenHex": token0.hex(), "sfu": sfu,
                       "nonceLabel": "sfu-challenge-nonce", "nonceHex": nonce.hex()},
            "intermediates": {"signedHex": signed.hex()},
            "outputs": {"admissionSigHex": sig.hex()},
        }],
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
    CBOR_ITEMS.clear()
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
        "broadcast-payload.json": broadcast_vector(),
        "aead-layouts.json": aead_layouts(),
        "derivations.json": derivations(token0),
        "sfu-admission.json": sfu_admission(token0),
        "http-pow.json": pow_vectors(),
    }


def cbor2_crosscheck():
    """Third check: decode each hand-encoded CBOR item with cbor2 and re-encode canonically."""
    if cbor2 is None:
        print("cbor2 not installed: CBOR third cross-check skipped")
        return True
    bad = [enc.hex()[:40] for enc, exp in CBOR_ITEMS
           if cbor2.loads(enc) != exp or cbor2.dumps(exp, canonical=True) != enc]
    for b in bad:
        print("FAIL cbor2 cross-check", b)
    print("cbor2 cross-check:", len(CBOR_ITEMS) - len(bad), "of", len(CBOR_ITEMS), "CBOR items agree")
    return not bad


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
    if cmd not in ("generate", "check"):
        sys.exit(__doc__)
    if not primitives():
        sys.exit("primitive validation failed")
    docs = build_all()
    if not cbor2_crosscheck():
        sys.exit("cbor2 cross-check failed")
    if cmd == "generate":
        for name, doc in docs.items():
            with open(os.path.join(sys.argv[2], name), "w") as f:
                json.dump(doc, f, indent=1)
                f.write("\n")
        return
    d = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DIR
    bad = 0
    for name, doc in docs.items():
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


if __name__ == "__main__":
    main()
