// Command agoratv is the Go-standard-library toolchain for the Agora test vectors.
//
//	go run . primitives    validate primitives against published vectors
//	go run . check [DIR]   recompute every vector and compare with the JSON files in DIR
//
// It shares no code with tools/agora_tv.py; agreement between the two is the oracle.
package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ed25519"
	"crypto/hkdf"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/base32"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"math/bits"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}

func h(s string) []byte {
	b, err := hex.DecodeString(s)
	must(err)
	return b
}

func hx(b []byte) string { return hex.EncodeToString(b) }

func sum(b []byte) []byte { s := sha256.Sum256(b); return s[:] }

func cat(parts ...[]byte) []byte { return bytes.Join(parts, nil) }

func hkdfKey(ikm, salt []byte, info string, n int) []byte {
	k, err := hkdf.Key(sha256.New, ikm, salt, info, n)
	must(err)
	return k
}

func edPriv(seed []byte) ed25519.PrivateKey { return ed25519.NewKeyFromSeed(seed) }

func edPub(seed []byte) []byte { return []byte(edPriv(seed).Public().(ed25519.PublicKey)) }

func edSign(seed, msg []byte) []byte {
	sig := ed25519.Sign(edPriv(seed), msg)
	if !ed25519.Verify(edPub(seed), msg, sig) {
		panic("ed25519 self-verify")
	}
	return sig
}

func gcm(key []byte) cipher.AEAD {
	blk, err := aes.NewCipher(key)
	must(err)
	g, err := cipher.NewGCM(blk)
	must(err)
	return g
}

func gcmSeal(key, nonce, pt, aad []byte) []byte {
	ct := gcm(key).Seal(nil, nonce, pt, aad)
	back, err := gcm(key).Open(nil, nonce, ct, aad)
	if err != nil || !bytes.Equal(back, pt) {
		panic("gcm round trip")
	}
	return ct
}

const b58Alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

func b58(data []byte) string {
	n := new(big.Int).SetBytes(data)
	r := new(big.Int)
	base := big.NewInt(58)
	var out []byte
	for n.Sign() > 0 {
		n.DivMod(n, base, r)
		out = append(out, b58Alphabet[r.Int64()])
	}
	for _, c := range data {
		if c != 0 {
			break
		}
		out = append(out, '1')
	}
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	return string(out)
}

func b64url(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }
func b64std(b []byte) string { return base64.StdEncoding.EncodeToString(b) }

func cidOf(codec byte, data []byte) []byte {
	return append([]byte{0x01, codec, 0x12, 0x20}, sum(data)...)
}
func cidRaw(data []byte) []byte { return cidOf(0x55, data) }

func cidText(c []byte) string {
	return "b" + strings.ToLower(base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString(c))
}

func cidV0(data []byte) string { return b58(append([]byte{0x12, 0x20}, sum(data)...)) }

func didKey(pub []byte) string { return "did:key:z" + b58(append([]byte{0xed, 0x01}, pub...)) }

func u64(n uint64) []byte { return binary.BigEndian.AppendUint64(nil, n) }

func lzBits(b []byte) int {
	n := 0
	for _, c := range b {
		if c == 0 {
			n += 8
			continue
		}
		return n + bits.LeadingZeros8(c)
	}
	return n
}

// Hand-written CBOR (RFC 8949), independent of the Python encoder.
func cborHead(major byte, n uint64) []byte {
	m := major << 5
	switch {
	case n < 24:
		return []byte{m | byte(n)}
	case n <= 0xff:
		return []byte{m | 24, byte(n)}
	case n <= 0xffff:
		return binary.BigEndian.AppendUint16([]byte{m | 25}, uint16(n))
	case n <= 0xffffffff:
		return binary.BigEndian.AppendUint32([]byte{m | 26}, uint32(n))
	}
	return binary.BigEndian.AppendUint64([]byte{m | 27}, n)
}

func cUint(n uint64) []byte { return cborHead(0, n) }
func cBstr(b []byte) []byte { return append(cborHead(2, uint64(len(b))), b...) }
func cTstr(s string) []byte { return append(cborHead(3, uint64(len(s))), s...) }

type kv struct {
	k string
	v []byte
}

// cMap sorts entries by encoded key bytes (RFC 8949 section 4.2.1).
func cMap(entries ...kv) []byte {
	type ek struct{ k, v []byte }
	var es []ek
	for _, e := range entries {
		es = append(es, ek{cTstr(e.k), e.v})
	}
	sort.Slice(es, func(i, j int) bool { return bytes.Compare(es[i].k, es[j].k) < 0 })
	out := cborHead(5, uint64(len(es)))
	for _, e := range es {
		out = append(append(out, e.k...), e.v...)
	}
	return out
}

func typedEnvelope(typ, cty string, body []byte, sig string) []byte {
	return cMap(kv{"type", cTstr(typ)}, kv{"contentType", cTstr(cty)}, kv{"body", cBstr(body)}, kv{"sig", cTstr(sig)})
}

// Hand-written protobuf for dag-pb and UnixFS, independent of the Python encoder.
func pbVarint(field int, n uint64) []byte {
	return binary.AppendUvarint(binary.AppendUvarint(nil, uint64(field)<<3), n)
}

func pbBytes(field int, b []byte) []byte {
	out := binary.AppendUvarint(nil, uint64(field)<<3|2)
	return append(binary.AppendUvarint(out, uint64(len(b))), b...)
}

func unixfsFile(sizes []uint64) []byte {
	var total uint64
	for _, s := range sizes {
		total += s
	}
	out := cat(pbVarint(1, 2), pbVarint(3, total))
	for _, s := range sizes {
		out = append(out, pbVarint(4, s)...)
	}
	return out
}

type link struct {
	cid   []byte
	tsize uint64
}

func dagpbNode(links []link, data []byte) []byte {
	var out []byte
	for _, l := range links {
		out = append(out, pbBytes(2, cat(pbBytes(1, l.cid), pbBytes(2, nil), pbVarint(3, l.tsize)))...)
	}
	return append(out, pbBytes(1, data)...)
}

// ------------------------------------------------------- published vectors

func primitives() bool {
	ok := true
	check := func(name, got, want string) {
		good := got == want
		ok = ok && good
		if good {
			fmt.Println("PASS", name)
		} else {
			fmt.Println("FAIL", name, got)
		}
	}
	check("SHA-256 abc", hx(sum([]byte("abc"))),
		"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
	s1 := sha1.Sum([]byte("abc"))
	check("SHA-1 abc", hx(s1[:]), "a9993e364706816aba3e25717850c26c9cd0d89d")
	sk := h("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
	check("Ed25519 RFC8032 T1 pub", hx(edPub(sk)),
		"d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
	check("Ed25519 RFC8032 T1 sig", hx(ed25519.Sign(edPriv(sk), nil)),
		"e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065"+
			"224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
	ikm := bytes.Repeat([]byte{0x0b}, 22)
	prk, err := hkdf.Extract(sha256.New, ikm, h("000102030405060708090a0b0c"))
	must(err)
	check("HKDF RFC5869 A.1 PRK", hx(prk),
		"077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5")
	check("HKDF RFC5869 A.1 OKM", hx(hkdfKey(ikm, h("000102030405060708090a0b0c"), string(h("f0f1f2f3f4f5f6f7f8f9")), 42)),
		"3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")
	check("HKDF RFC5869 A.3 OKM", hx(hkdfKey(ikm, nil, "", 42)),
		"8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8")
	check("AES-GCM MV TC2", hx(gcmSeal(make([]byte, 16), make([]byte, 12), make([]byte, 16), nil)),
		"0388dace60b6a392f328c2b971b2fe78"+"ab6e47d42cec13bdf53a67b21257bddf")
	check("AES-GCM MV TC4", hx(gcmSeal(h("feffe9928665731c6d6a8f9467308308"), h("cafebabefacedbaddecaf888"),
		h("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"+
			"1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39"),
		h("feedfacedeadbeeffeedfacedeadbeefabaddad2"))),
		"42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e"+
			"21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091"+
			"5bc94fbc3221a5db94fae95ae7121a47")
	check("base58 Hello World!", b58([]byte("Hello World!")), "2NEpo7TZRRrLZSi2U")
	check("base58 leading zeros", b58(h("0000287fb4cd")), "11233QC4")
	check("base32 foobar", base32.StdEncoding.EncodeToString([]byte("foobar")), "MZXW6YTBOI======")
	check("CID empty raw", cidText(cidRaw(nil)), "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku")
	emptyDir := dagpbNode(nil, pbVarint(1, 1))
	check("UnixFS empty directory CIDv0", cidV0(emptyDir), "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
	check("UnixFS empty directory CIDv1", cidText(cidOf(0x70, emptyDir)),
		"bafybeiczsscdsbs7ffqz55asqdf3smv6klcw3gofszvwlyarci47bgf354")
	check("UnixFS empty file CIDv0", cidV0(dagpbNode(nil, unixfsFile(nil))), "QmbFMke1KXqnYyBBWxB74N4c5SBnJMVAiMNRcGu6x1AwQH")
	fmt.Println("toolchain:", runtime.Version())
	return ok
}

// ----------------------------------------------------------------- vectors

func fixed(label string, n int) []byte { return sum([]byte("agora-test-vectors/" + label))[:n] }

func token(seed []byte, epoch uint64) []byte {
	return hkdfKey(seed, nil, string(cat([]byte("agora channel token"), u64(epoch))), 32)
}

type flat map[string]string

func (f flat) put(k string, v any) {
	switch t := v.(type) {
	case string:
		f[k] = t
	case []byte:
		f[k] = hx(t)
	case int:
		f[k] = strconv.Itoa(t)
	case uint64:
		f[k] = strconv.FormatUint(t, 10)
	case bool:
		f[k] = strconv.FormatBool(t)
	default:
		panic(fmt.Sprintf("put %s: %T", k, v))
	}
}

func (f flat) key(p, label string) []byte {
	seed := fixed(label, 32)
	f.put(p+".seedLabel", label)
	f.put(p+".seedHex", seed)
	f.put(p+".publicKeyHex", edPub(seed))
	return seed
}

func channelToken(f flat) []byte {
	seed := fixed("admission-key", 32)
	for i, ep := range []uint64{0, 1, 4294967296} {
		p := fmt.Sprintf("vectors.%d.", i)
		prk, err := hkdf.Extract(sha256.New, seed, nil)
		must(err)
		f.put(p+"inputs.seedLabel", "admission-key")
		f.put(p+"inputs.seedHex", seed)
		f.put(p+"inputs.keyEpoch", ep)
		f.put(p+"inputs.saltHex", "")
		f.put(p+"intermediates.infoHex", cat([]byte("agora channel token"), u64(ep)))
		f.put(p+"intermediates.prkHex", prk)
		f.put(p+"outputs.channelTokenHex", token(seed, ep))
	}
	return token(seed, 0)
}

func sealedEnvelope(f flat, tok []byte) []byte {
	k := fixed("sealed-envelope-exporter-output", 16)
	nonce := fixed("sealed-envelope-nonce", 12)
	pt := []byte("agora test vector: stand-in bytes for a serialized MLSMessage (not valid MLS)")
	aad := cat([]byte("agora/sealed/v1"), tok, u64(7))
	ct := gcmSeal(k, nonce, pt, aad)
	p := "vectors.0."
	f.put(p+"inputs.exporterOutputLabel", "sealed-envelope-exporter-output")
	f.put(p+"inputs.keyHex", k)
	f.put(p+"inputs.channelTokenHex", tok)
	f.put(p+"inputs.epoch", 7)
	f.put(p+"inputs.nonceLabel", "sealed-envelope-nonce")
	f.put(p+"inputs.nonceHex", nonce)
	f.put(p+"inputs.plaintextHex", pt)
	f.put(p+"intermediates.aadHex", aad)
	f.put(p+"outputs.ciphertextAndTagHex", ct)
	f.put(p+"outputs.tagHex", ct[len(ct)-16:])
	sealed := cat(nonce, ct)
	f.put(p+"outputs.sealedEnvelopeHex", sealed)
	return sealed
}

func routingEnvelope(f flat, tok, sealed []byte) {
	p := "vectors.0."
	seed := f.key(p+"inputs.admissionKey", "admission-key")
	ts, exp := uint64(1792195200000), uint64(1792800000000)
	signed := cMap(
		kv{"ctx", cTstr("agora/envelope/v1")},
		kv{"channelToken", cBstr(tok)},
		kv{"ts", cUint(ts)},
		kv{"expiryHint", cUint(exp)},
		kv{"sealedEnvelope", cBstr(sealed)},
	)
	sig := edSign(seed, signed)
	env := cMap(kv{"signed", cBstr(signed)}, kv{"admissionSig", cBstr(sig)})
	f.put(p+"inputs.channelTokenHex", tok)
	f.put(p+"inputs.ts", ts)
	f.put(p+"inputs.expiryHint", exp)
	f.put(p+"inputs.sealedEnvelopeHex", sealed)
	f.put(p+"intermediates.signedHex", signed)
	f.put(p+"outputs.admissionSigHex", sig)
	f.put(p+"outputs.idCidBytesHex", cidRaw(signed))
	f.put(p+"outputs.idCidText", cidText(cidRaw(signed)))
	f.put(p+"outputs.routingEnvelopeHex", env)
}

const chunkSize = 262144

// putBlock stores a block inline up to 4096 bytes, else as length, SHA-256 and first/last 64 bytes.
// The full block is always recomputed; the SHA-256 compares all of it.
func putBlock(f flat, q string, blk []byte) {
	f.put(q+"blockLength", len(blk))
	f.put(q+"blockSha256Hex", sum(blk))
	if len(blk) <= 4096 {
		f.put(q+"blockHex", blk)
	} else {
		f.put(q+"blockFirst64Hex", blk[:64])
		f.put(q+"blockLast64Hex", blk[len(blk)-64:])
	}
}

func chunkCase(f flat, p, name string, data, key []byte) {
	n := (len(data) + chunkSize - 1) / chunkSize
	if n == 0 {
		n = 1
	}
	f.put(p+"name", name)
	f.put(p+"plaintextSize", len(data))
	f.put(p+"plaintextSha256Hex", sum(data))
	f.put(p+"chunkCount", n)
	var links []link
	for i := 0; i < n; i++ {
		q := fmt.Sprintf("%sblocks.%d.", p, i)
		chunk := data[i*chunkSize : min((i+1)*chunkSize, len(data))]
		nonce := make([]byte, 12)
		binary.BigEndian.PutUint64(nonce[4:], uint64(i))
		final := byte(0)
		if i == n-1 {
			final = 1
		}
		aad := cat([]byte("agora/chunk/v1"), u64(uint64(i)), u64(uint64(n)), []byte{final})
		blk := gcmSeal(key, nonce, chunk, aad)
		links = append(links, link{cidRaw(blk), uint64(len(blk))})
		f.put(q+"index", i)
		f.put(q+"plaintextLength", len(chunk))
		f.put(q+"nonceHex", nonce)
		f.put(q+"aadHex", aad)
		putBlock(f, q, blk)
		f.put(q+"blockCidText", cidText(cidRaw(blk)))
	}
	if n == 1 {
		f.put(p+"blobIdText", cidText(links[0].cid))
		return
	}
	var sizes []uint64
	for _, l := range links {
		sizes = append(sizes, l.tsize)
	}
	data2 := unixfsFile(sizes)
	root := dagpbNode(links, data2)
	rc := cidOf(0x70, root)
	f.put(p+"rootBlock.unixfsDataHex", data2)
	f.put(p+"rootBlock.rootBlockHex", root)
	f.put(p+"rootBlock.rootCidBytesHex", rc)
	f.put(p+"rootBlock.rootCidText", cidText(rc))
	f.put(p+"blobIdText", cidText(rc))
}

func patternFile(size int) []byte {
	b := make([]byte, size)
	for j := range b {
		b[j] = byte(j % 251)
	}
	return b
}

func chunked(f flat) {
	k := fixed("chunk-content-key", 16)
	f.put("contentKeyLabel", "chunk-content-key")
	f.put("contentKeyHex", k)
	f.put("contentKeyBase64url", b64url(k))
	small := []byte("Hello, Agora!\n")
	chunkCase(f, "vectors.0.", "empty-file", nil, k)
	chunkCase(f, "vectors.1.", "single-chunk", small, k)
	f.put("vectors.1.plaintextHex", small)
	chunkCase(f, "vectors.2.", "two-chunk", patternFile(chunkSize+1000), k)
	chunkCase(f, "vectors.3.", "three-chunk", patternFile(2*chunkSize+5), k)
}

func deviceBinding(f flat) {
	p := "vectors.0."
	id := f.key(p+"inputs.identityKey", "did-key-identity")
	leaf := f.key(p+"inputs.leafSignatureKey", "device-leaf-signature-key")
	msg := cat([]byte("agora/v1/device-binding"), edPub(leaf))
	f.put(p+"intermediates.didKey", didKey(edPub(id)))
	f.put(p+"intermediates.signedMessageHex", msg)
	f.put(p+"outputs.extensionDataHex", edSign(id, msg))
}

const relayAdBody = `{"did":"did:web:relay.example.com","manifestURL":"https://relay.example.com/.well-known/agora-relay",` +
	`"endpoints":{"webTransport":"https://relay.example.com/v1/agora/wt","webSocket":"wss://relay.example.com/v1/agora/ws",` +
	`"onion":"ws://examplerelay3xyzabc.onion/v1/agora/ws","jmapSync":"https://relay.example.com/v1/agora/jmap"},` +
	`"serviceTiers":[{"id":"standard","retentionDays":30,"bandwidthTierGbPerMonth":100}],"ts":"2026-03-12T00:00:00Z"}`

const serviceAgreementBody = `{"serviceType":"relay","provider":"did:web:relay.example.com","billing":"BILLING",` +
	`"endpoint":"https://relay.example.com/v1/agora/admission-keys","contact":"mailto:io-liaison@co.example.com",` +
	`"retentionDays":90,"bandwidthTierGbPerMonth":100,"storageQuotaGb":50,"replicationFloor":2,` +
	`"observationBudget":{"connectionLogRetentionDays":7,"extensions":[]},"supersedes":null,` +
	`"validFrom":"2026-03-12T00:00:00Z","validUntil":"2027-03-12T00:00:00Z"}`

const guardianBody = `{"schemaVersion":1,"seq":42,"prevStateCID":"PREV","owner":"did:web:owner.example.com",` +
	`"guardian":{"dids":["did:web:g1.example.com","did:web:g2.example.com","did:web:g3.example.com"],` +
	`"threshold":2,"delaySeconds":259200},` +
	`"pendingTransfer":{"newOwner":"did:web:newowner.example.com","ts":"2026-10-17T00:00:00Z"}}`

func akrBody(agreement, tok, pub, replaces string) string {
	return `{"agreement":` + jsonStr(agreement) + `,"ts":"2026-10-16T12:00:00Z","keys":[{"channelToken":` + jsonStr(tok) +
		`,"admissionPublicKey":` + jsonStr(pub) + `,"replaces":` + jsonStr(replaces) + `}]}`
}

func cakBody(chanID, seed string) string {
	return `{"@type":"ChannelAdmissionKey","channelID":` + jsonStr(chanID) + `,"keyEpoch":1,"seed":` + jsonStr(seed) +
		`,"relays":["https://relay.example.net","https://relay2.example.org"],"archive":"https://archive.co.example.com"}`
}

func bkBody(chanID, key string) string {
	return `{"@type":"BroadcastKey","channelID":` + jsonStr(chanID) + `,"keyEpoch":7,"key":` + jsonStr(key) +
		`,"notBefore":"2026-10-16T00:00:00Z"}`
}

func bmBody(chanID, sender, device string) string {
	return `{"channelID":` + jsonStr(chanID) + `,"keyEpoch":7,"senderDID":` + jsonStr(sender) + `,"device":` + jsonStr(device) +
		`,"seq":311,"message":{"senderMsgId":"01J3XM2C4V0Q6R9T8Y7W5E3B1A",` +
		`"body":"v2.1.0 released; see release notes for details.","bodyType":"text/markdown;variant=commonmark",` +
		`"sentAt":"2026-04-22T09:00:00Z"}}`
}

const cty = "application/json"

type signer struct{ did, kid, label string }

func didKeySigner(label string) signer {
	d := didKey(edPub(fixed(label, 32)))
	return signer{d, d + "#" + strings.TrimPrefix(d, "did:key:"), label}
}

func jsonStr(s string) string { b, err := json.Marshal(s); must(err); return string(b) }

// hdr builds a protected header; a member whose raw value is "" is omitted.
func hdr(kid, typ, alg, b64, crit, ctyv string) string {
	var parts []string
	for _, m := range [][2]string{{"alg", alg}, {"b64", b64}, {"crit", crit}, {"kid", jsonStr(kid)},
		{"cty", ctyv}, {"agoraType", jsonStr(typ)}} {
		if m[1] != "" {
			parts = append(parts, jsonStr(m[0])+":"+m[1])
		}
	}
	return "{" + strings.Join(parts, ",") + "}"
}

func defHdr(kid, typ string) string {
	return hdr(kid, typ, `"EdDSA"`, "false", `["b64"]`, jsonStr(cty))
}

type entry struct{ protected, signature string }

// verifyEntry applies §13.1.1 checks 1, 2 and 5 and returns the DID named by kid.
func verifyEntry(e entry, envType, envCty string, body []byte, pubs map[string][]byte) (string, bool) {
	raw, err := base64.RawURLEncoding.DecodeString(e.protected)
	if err != nil {
		return "", false
	}
	var m map[string]json.RawMessage
	if json.Unmarshal(raw, &m) != nil || len(m) != 6 {
		return "", false
	}
	str := func(k string) (string, bool) {
		var s string
		v, ok := m[k]
		return s, ok && json.Unmarshal(v, &s) == nil
	}
	alg, ok1 := str("alg")
	kid, ok2 := str("kid")
	c, ok3 := str("cty")
	at, ok4 := str("agoraType")
	var b64 bool
	var crit []string
	b64raw, ok5 := m["b64"]
	critraw, ok6 := m["crit"]
	if !(ok1 && ok2 && ok3 && ok4 && ok5 && ok6) || json.Unmarshal(b64raw, &b64) != nil ||
		json.Unmarshal(critraw, &crit) != nil {
		return "", false
	}
	if alg != "EdDSA" || b64 || len(crit) != 1 || crit[0] != "b64" || c != envCty || at != envType {
		return "", false
	}
	sig, err := base64.RawURLEncoding.DecodeString(e.signature)
	if err != nil || !ed25519.Verify(pubs[kid], cat([]byte(e.protected+"."), body), sig) {
		return "", false
	}
	did, _, _ := strings.Cut(kid, "#")
	return did, true
}

// verdict applies §13.1.1 to the envelope as received.
func verdict(es []entry, envType string, body []byte, pubs map[string][]byte, required, candidates []string, k int) string {
	seen := map[string]bool{}
	for _, e := range es {
		did, ok := verifyEntry(e, envType, cty, body, pubs)
		if !ok || seen[did] {
			return "reject"
		}
		seen[did] = true
	}
	if candidates != nil {
		for d := range seen {
			if !contains(candidates, d) {
				return "reject"
			}
		}
		if len(seen) < k {
			return "reject"
		}
		return "accept"
	}
	if len(seen) != len(required) {
		return "reject"
	}
	for _, d := range required {
		if !seen[d] {
			return "reject"
		}
	}
	return "accept"
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

// signEntry fills the per-signer keys under q and returns the entry.
func signEntry(f flat, q string, s signer, ph string, body []byte, withID bool) entry {
	seed := fixed(s.label, 32)
	if withID {
		f.key(q+"key", s.label)
		f.put(q+"did", s.did)
		f.put(q+"kid", s.kid)
	}
	pb := b64url([]byte(ph))
	input := cat([]byte(pb+"."), body)
	sig := edSign(seed, input)
	f.put(q+"protectedHeaderJson", ph)
	f.put(q+"protectedB64", pb)
	f.put(q+"signingInputHex", input)
	f.put(q+"signatureHex", sig)
	if withID {
		f.put(q+"signatureB64", b64url(sig))
	}
	return entry{pb, b64url(sig)}
}

func sigJSON(es []entry) string {
	var parts []string
	for _, e := range es {
		parts = append(parts, `{"protected":`+jsonStr(e.protected)+`,"signature":`+jsonStr(e.signature)+`}`)
	}
	return `{"signatures":[` + strings.Join(parts, ",") + `]}`
}

func putEnvelope(f flat, p, typ string, body []byte, sig string) {
	f.put(p+"type", typ)
	f.put(p+"contentType", cty)
	f.put(p+"bodyText", string(body))
	f.put(p+"bodyHex", body)
	f.put(p+"sig", sig)
}

type jcase struct {
	name, typ            string
	body, envBody        []byte
	signers              []signer
	headers              []string
	required, candidates []string
	k                    int
}

func jwsCase(f flat, p string, c jcase) string {
	var es []entry
	pubs := map[string][]byte{}
	for j, s := range c.signers {
		ph := defHdr(s.kid, c.typ)
		if c.headers != nil {
			ph = c.headers[j]
		}
		es = append(es, signEntry(f, fmt.Sprintf("%ssigners.%d.", p, j), s, ph, c.body, true))
		pubs[s.kid] = edPub(fixed(s.label, 32))
	}
	env := c.body
	if c.envBody != nil {
		env = c.envBody
		f.put(p+"signedBodyHex", c.body)
	}
	sig := sigJSON(es)
	f.put(p+"name", c.name)
	putEnvelope(f, p+"envelope.", c.typ, env, sig)
	f.put(p+"expected", verdict(es, c.typ, env, pubs, c.required, c.candidates, c.k))
	for j, d := range c.required {
		f.put(fmt.Sprintf("%srequiredSigners.%d", p, j), d)
	}
	if c.candidates != nil {
		for j, d := range c.candidates {
			f.put(fmt.Sprintf("%scandidateDids.%d", p, j), d)
		}
		f.put(p+"threshold", c.k)
	}
	return sig
}

func jws(f flat) {
	const T = "urn:agora:type:"
	relay := signer{"did:web:relay.example.com", "did:web:relay.example.com#key-1", "relay-provider"}
	billing := didKeySigner("billing")
	owner := didKeySigner("space-owner")
	sa := []byte(strings.Replace(serviceAgreementBody, "BILLING", billing.did, 1))
	gb := []byte(strings.Replace(guardianBody, "PREV", cidText(cidRaw([]byte("agora-test-vectors/previous-space-state"))), 1))
	g1a := signer{"did:web:g1.example.com", "did:web:g1.example.com#key-1", "guardian-1-key-1"}
	g1b := signer{"did:web:g1.example.com", "did:web:g1.example.com#key-2", "guardian-1-key-2"}
	g2 := signer{"did:web:g2.example.com", "did:web:g2.example.com#key-1", "guardian-2"}
	cands := []string{"did:web:g1.example.com", "did:web:g2.example.com", "did:web:g3.example.com"}
	rad := []byte(relayAdBody)
	rt := T + "RelayAd"
	one := []string{relay.did}
	rk := relay.kid

	jwsCase(f, "vectors.0.", jcase{name: "single-signer-relayad", typ: rt, body: rad, signers: []signer{relay}, required: one})
	saSig := jwsCase(f, "vectors.1.", jcase{name: "two-signer-serviceagreement", typ: T + "ServiceAgreement", body: sa,
		signers: []signer{relay, billing}, required: []string{relay.did, billing.did}})
	saEnv := typedEnvelope(T+"ServiceAgreement", cty, sa, saSig)
	f.put("vectors.1.encodedEnvelopeHex", saEnv)
	f.put("vectors.1.envelopeCidText", cidText(cidRaw(saEnv)))
	agreement := cidText(cidRaw(sa)) // §10.5.3: CID of the signed ServiceAgreement body bytes
	f.put("vectors.1.bodyCidText", agreement)
	jwsCase(f, "vectors.2.", jcase{name: "negative-missing-required-signer", typ: T + "ServiceAgreement", body: sa,
		signers: []signer{billing}, required: []string{relay.did, billing.did}})
	jwsCase(f, "vectors.3.", jcase{name: "threshold-2-of-3-valid", typ: T + "SpaceState", body: gb,
		signers: []signer{g1a, g2}, candidates: cands, k: 2})
	jwsCase(f, "vectors.4.", jcase{name: "negative-threshold-duplicate-did", typ: T + "SpaceState", body: gb,
		signers: []signer{g1a, g1b}, candidates: cands, k: 2})

	oldTok := token(fixed("admission-key", 32), 0)
	newSeed := fixed("admission-key-rotated", 32)
	akr := akrBody(agreement, b64url(token(newSeed, 1)), b64url(edPub(newSeed)), b64url(oldTok))
	jwsCase(f, "vectors.5.", jcase{name: "admission-key-registration", typ: T + "AdmissionKeyRegistration",
		body: []byte(akr), signers: []signer{billing}, required: []string{billing.did}})
	jwsCase(f, "vectors.6.", jcase{name: "channel-admission-key", typ: T + "ChannelAdmissionKey",
		body: []byte(cakBody(b64url(fixed("channel-id", 16)), b64url(newSeed))), signers: []signer{owner},
		required: []string{owner.did}})
	jwsCase(f, "vectors.7.", jcase{name: "broadcast-key", typ: T + "BroadcastKey",
		body:    []byte(bkBody(b64url(fixed("broadcast-channel-id", 16)), b64url(fixed("broadcast-content-key", 16)))),
		signers: []signer{owner}, required: []string{owner.did}})

	ok := jsonStr(cty)
	negs := []struct{ name, ph string }{
		{"negative-b64-true", hdr(rk, rt, `"EdDSA"`, "true", `["b64"]`, ok)},
		{"negative-b64-absent", hdr(rk, rt, `"EdDSA"`, "", `["b64"]`, ok)},
		{"negative-b64-and-crit-absent", hdr(rk, rt, `"EdDSA"`, "", "", ok)},
		{"negative-crit-absent", hdr(rk, rt, `"EdDSA"`, "false", "", ok)},
		{"negative-alg-not-eddsa", hdr(rk, rt, `"Ed25519"`, "false", `["b64"]`, ok)},
		{"negative-cty-mismatch", hdr(rk, rt, `"EdDSA"`, "false", `["b64"]`, jsonStr("application/cbor"))},
		{"negative-agoratype-mismatch", hdr(rk, T+"ServiceAgreement", `"EdDSA"`, "false", `["b64"]`, ok)},
	}
	for i, n := range negs {
		jwsCase(f, fmt.Sprintf("vectors.%d.", 8+i), jcase{name: n.name, typ: rt, body: rad, signers: []signer{relay},
			headers: []string{n.ph}, required: one})
	}
	var pretty bytes.Buffer
	must(json.Indent(&pretty, rad, "", "  "))
	jwsCase(f, "vectors.15.", jcase{name: "negative-reserialized-body", typ: rt, body: rad, envBody: pretty.Bytes(),
		signers: []signer{relay}, required: one})
}

func broadcast(f flat) {
	p := "vectors.0."
	adm := f.key(p+"inputs.admissionKey", "broadcast-admission-key")
	tok := token(adm, 7)
	chanID := fixed("broadcast-channel-id", 16)
	ckey := fixed("broadcast-content-key", 16)
	device := fixed("broadcast-device", 16)
	nonce := fixed("broadcast-nonce", 12)
	poster := didKeySigner("broadcast-poster")
	f.key(p+"inputs.posterKey", "broadcast-poster")
	typ := "urn:agora:type:BroadcastMessage"
	body := []byte(bmBody(b64url(chanID), poster.did, b64url(device)))
	e := signEntry(f, p+"intermediates.jws.", poster, defHdr(poster.kid, typ), body, false)
	sig := sigJSON([]entry{e})
	if verdict([]entry{e}, typ, body, map[string][]byte{poster.kid: edPub(fixed(poster.label, 32))},
		[]string{poster.did}, nil, 0) != "accept" {
		panic("broadcast message signature")
	}
	putEnvelope(f, p+"intermediates.envelope.", typ, body, sig)
	pt := typedEnvelope(typ, cty, body, sig)
	aad := cat([]byte("agora/broadcast/v1"), tok)
	payload := cat(nonce, gcmSeal(ckey, nonce, pt, aad))
	ts := uint64(1792195200000)
	signed := cMap(kv{"ctx", cTstr("agora/envelope/v1")}, kv{"channelToken", cBstr(tok)}, kv{"ts", cUint(ts)},
		kv{"broadcastPayload", cBstr(payload)})
	asig := edSign(adm, signed)
	f.put(p+"inputs.keyEpoch", 7)
	f.put(p+"inputs.channelIdLabel", "broadcast-channel-id")
	f.put(p+"inputs.channelIdHex", chanID)
	f.put(p+"inputs.contentKeyLabel", "broadcast-content-key")
	f.put(p+"inputs.contentKeyHex", ckey)
	f.put(p+"inputs.deviceLabel", "broadcast-device")
	f.put(p+"inputs.deviceHex", device)
	f.put(p+"inputs.nonceLabel", "broadcast-nonce")
	f.put(p+"inputs.nonceHex", nonce)
	f.put(p+"inputs.ts", ts)
	f.put(p+"intermediates.channelTokenHex", tok)
	f.put(p+"intermediates.posterDid", poster.did)
	f.put(p+"intermediates.posterKid", poster.kid)
	f.put(p+"intermediates.plaintextEnvelopeHex", pt)
	f.put(p+"intermediates.aadHex", aad)
	f.put(p+"intermediates.signedHex", signed)
	f.put(p+"outputs.broadcastPayloadHex", payload)
	f.put(p+"outputs.admissionSigHex", asig)
	f.put(p+"outputs.idCidText", cidText(cidRaw(signed)))
	f.put(p+"outputs.routingEnvelopeHex", cMap(kv{"signed", cBstr(signed)}, kv{"admissionSig", cBstr(asig)}))
}

func aeadLayouts(f flat) {
	gk := fixed("group-blob-exporter-output", 16)
	gn := fixed("group-blob-nonce", 12)
	gpt := []byte("agora test vector: stand-in bytes for a CO record")
	gaad := cat([]byte("agora/blob/v1"), u64(17))
	gblob := cat(u64(17), gn, gcmSeal(gk, gn, gpt, gaad))
	p := "groupEncryptedBlob."
	f.put(p+"inputs.exporterOutputLabel", "group-blob-exporter-output")
	f.put(p+"inputs.keyHex", gk)
	f.put(p+"inputs.epoch", 17)
	f.put(p+"inputs.nonceLabel", "group-blob-nonce")
	f.put(p+"inputs.nonceHex", gn)
	f.put(p+"inputs.plaintextHex", gpt)
	f.put(p+"intermediates.aadHex", gaad)
	f.put(p+"outputs.blobHex", gblob)
	f.put(p+"outputs.cidText", cidText(cidRaw(gblob)))
	for _, c := range []struct{ p, kl, nl, pt, aad string }{
		{"assetBlob.", "asset-key", "asset-nonce", "agora test vector: stand-in bytes for an icon image", "agora/asset/v1"},
		{"historyBlob.", "history-key", "history-nonce", "agora test vector: stand-in bytes for a CBOR HistoryArchive", "agora/history/v1"},
	} {
		k, n := fixed(c.kl, 16), fixed(c.nl, 12)
		blob := cat(n, gcmSeal(k, n, []byte(c.pt), []byte(c.aad)))
		f.put(c.p+"inputs.keyLabel", c.kl)
		f.put(c.p+"inputs.keyHex", k)
		f.put(c.p+"inputs.nonceLabel", c.nl)
		f.put(c.p+"inputs.nonceHex", n)
		f.put(c.p+"inputs.plaintextHex", []byte(c.pt))
		f.put(c.p+"intermediates.aadHex", []byte(c.aad))
		f.put(c.p+"outputs.blobHex", blob)
		f.put(c.p+"outputs.cidText", cidText(cidRaw(blob)))
	}
}

func derivations(f flat, tok0 []byte) {
	s := fixed("social-recovery-secret", 32)
	seed := hkdfKey(s, nil, "agora/v1/social-recovery-key", 32)
	f.put("socialRecoveryKey.inputs.secretLabel", "social-recovery-secret")
	f.put("socialRecoveryKey.inputs.secretHex", s)
	f.put("socialRecoveryKey.intermediates.infoHex", []byte("agora/v1/social-recovery-key"))
	f.put("socialRecoveryKey.outputs.seedHex", seed)
	f.put("socialRecoveryKey.outputs.publicKeyHex", edPub(seed))
	f.put("webauthnPrf.outputs.prfFirstHex", sum([]byte("agora/v1/webauthn-prf")))
	prf := fixed("webauthn-prf-output", 32)
	f.put("webauthnPrfWrap.inputs.prfOutputLabel", "webauthn-prf-output")
	f.put("webauthnPrfWrap.inputs.prfOutputHex", prf)
	f.put("webauthnPrfWrap.intermediates.infoHex", []byte("agora/v1/webauthn-prf-wrap"))
	f.put("webauthnPrfWrap.outputs.wrapKeyHex", hkdfKey(prf, nil, "agora/v1/webauthn-prf-wrap", 32))
	in := cat([]byte("agora/commits/v1"), tok0)
	f.put("commitStream.inputs.channelTokenHex", tok0)
	f.put("commitStream.intermediates.inputHex", in)
	f.put("commitStream.outputs.streamNameHex", sum(in))
	ih := sha1.Sum([]byte("agora-relay-v1"))
	f.put("relayInfohash.outputs.infohashHex", ih[:])
}

func sfuAdmission(f flat, tok0 []byte) {
	p := "vectors.0."
	seed := f.key(p+"inputs.admissionKey", "admission-key")
	nonce := fixed("sfu-challenge-nonce", 32)
	sfu := "did:web:sfu.example.com"
	signed := cMap(kv{"ctx", cTstr("agora sfu admission")}, kv{"sfu", cTstr(sfu)}, kv{"nonce", cBstr(nonce)},
		kv{"channelToken", cBstr(tok0)})
	f.put(p+"inputs.channelTokenHex", tok0)
	f.put(p+"inputs.sfu", sfu)
	f.put(p+"inputs.nonceLabel", "sfu-challenge-nonce")
	f.put(p+"inputs.nonceHex", nonce)
	f.put(p+"intermediates.signedHex", signed)
	f.put(p+"outputs.admissionSigHex", edSign(seed, signed))
}

func httpPow(f flat) {
	ch := fixed("pow-challenge", 32)
	diff, exp := 20, 30
	var n uint64
	for lzBits(sum(cat(ch, u64(n)))) < diff {
		n++
	}
	nonce := u64(n)
	hash := sum(cat(ch, nonce))
	bad := u64(0)
	hb := sum(cat(ch, bad))
	p := "vectors.0."
	f.put(p+"inputs.challengeLabel", "pow-challenge")
	f.put(p+"inputs.challengeHex", ch)
	f.put(p+"inputs.difficulty", diff)
	f.put(p+"inputs.expires", exp)
	f.put(p+"outputs.challengeHeader", fmt.Sprintf("Agora-PoW-Challenge: challenge=:%s:, difficulty=%d, expires=%d", b64std(ch), diff, exp))
	f.put(p+"outputs.nonceHex", nonce)
	f.put(p+"outputs.hashHex", hash)
	f.put(p+"outputs.leadingZeroBits", lzBits(hash))
	f.put(p+"outputs.powHeader", fmt.Sprintf("Agora-PoW: challenge=:%s:, nonce=:%s:", b64std(ch), b64std(nonce)))
	f.put(p+"negative.nonceHex", bad)
	f.put(p+"negative.hashHex", hb)
	f.put(p+"negative.leadingZeroBits", lzBits(hb))
	v := "accept"
	if lzBits(hb) < diff {
		v = "reject"
	}
	f.put(p+"negative.expected", v)
	exC, err := base64.StdEncoding.DecodeString("RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=")
	must(err)
	exN, err := base64.StdEncoding.DecodeString("AAAAAAAXBKY=")
	must(err)
	exH := sum(cat(exC, exN))
	f.put("specExample.challengeHex", exC)
	f.put("specExample.nonceHex", exN)
	f.put("specExample.hashHex", exH)
	f.put("specExample.leadingZeroBits", lzBits(exH))
	f.put("specExample.meetsDifficulty20", lzBits(exH) >= 20)
}

func computeAll() map[string]flat {
	all := map[string]flat{}
	for _, n := range []string{"channel-token.json", "sealed-envelope.json", "routing-envelope.json",
		"chunked-blob.json", "device-binding.json", "jws.json", "broadcast-payload.json", "aead-layouts.json",
		"derivations.json", "sfu-admission.json", "http-pow.json"} {
		all[n] = flat{}
	}
	tok := channelToken(all["channel-token.json"])
	sealed := sealedEnvelope(all["sealed-envelope.json"], tok)
	routingEnvelope(all["routing-envelope.json"], tok, sealed)
	chunked(all["chunked-blob.json"])
	deviceBinding(all["device-binding.json"])
	jws(all["jws.json"])
	broadcast(all["broadcast-payload.json"])
	aeadLayouts(all["aead-layouts.json"])
	derivations(all["derivations.json"], tok)
	sfuAdmission(all["sfu-admission.json"], tok)
	httpPow(all["http-pow.json"])
	return all
}

var descriptive = map[string]bool{"construction": true, "spec": true, "notes": true, "reason": true,
	"pattern": true, "toolchain": true}

func flatten(v any, prefix string, out flat) {
	switch t := v.(type) {
	case map[string]any:
		for k, x := range t {
			if !descriptive[k] {
				flatten(x, prefix+k+".", out)
			}
		}
	case []any:
		for i, x := range t {
			flatten(x, prefix+strconv.Itoa(i)+".", out)
		}
	case string:
		out[strings.TrimSuffix(prefix, ".")] = t
	case json.Number:
		out[strings.TrimSuffix(prefix, ".")] = t.String()
	case bool:
		out[strings.TrimSuffix(prefix, ".")] = strconv.FormatBool(t)
	case nil:
		out[strings.TrimSuffix(prefix, ".")] = "null"
	}
}

func check(dir string) bool {
	ok := true
	all := computeAll()
	names := make([]string, 0, len(all))
	for n := range all {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, name := range names {
		raw, err := os.ReadFile(filepath.Join(dir, name))
		must(err)
		dec := json.NewDecoder(bytes.NewReader(raw))
		dec.UseNumber()
		var doc any
		must(dec.Decode(&doc))
		stored := flat{}
		flatten(doc, "", stored)
		computed := all[name]
		bad := 0
		for k, v := range computed {
			if sv, present := stored[k]; !present || sv != v {
				fmt.Println("MISMATCH", name, k)
				bad++
			}
		}
		for k := range stored {
			if _, present := computed[k]; !present {
				fmt.Println("UNCHECKED (not recomputed by Go)", name, k)
				bad++
			}
		}
		if bad == 0 {
			fmt.Println("OK", name, len(computed), "values")
		}
		ok = ok && bad == 0
	}
	return ok
}

func main() {
	cmd := ""
	if len(os.Args) > 1 {
		cmd = os.Args[1]
	}
	switch cmd {
	case "primitives":
		if !primitives() {
			os.Exit(1)
		}
	case "check":
		if !primitives() {
			fmt.Println("primitive validation failed")
			os.Exit(1)
		}
		dir := "../.."
		if len(os.Args) > 2 {
			dir = os.Args[2]
		}
		if !check(dir) {
			os.Exit(1)
		}
	default:
		fmt.Println("usage: agoratv primitives | check [DIR]")
		os.Exit(2)
	}
}
