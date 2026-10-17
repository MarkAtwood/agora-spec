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
	"crypto/hmac"
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

func hmacSHA256(key, data []byte) []byte {
	m := hmac.New(sha256.New, key)
	m.Write(data)
	return m.Sum(nil)
}

func hkdfKey(ikm, salt []byte, info string, n int) []byte {
	k, err := hkdf.Key(sha256.New, ikm, salt, info, n)
	must(err)
	return k
}

func edPriv(seed []byte) ed25519.PrivateKey { return ed25519.NewKeyFromSeed(seed) }

func edPub(seed []byte) []byte { return []byte(edPriv(seed).Public().(ed25519.PublicKey)) }

func gcmSeal(key, nonce, pt, aad []byte) []byte {
	blk, err := aes.NewCipher(key)
	must(err)
	g, err := cipher.NewGCM(blk)
	must(err)
	return g.Seal(nil, nonce, pt, aad)
}

func gcmOpenOK(key, nonce, ct, aad, want []byte) bool {
	blk, err := aes.NewCipher(key)
	must(err)
	g, err := cipher.NewGCM(blk)
	must(err)
	pt, err := g.Open(nil, nonce, ct, aad)
	return err == nil && bytes.Equal(pt, want)
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

func cidRaw(data []byte) []byte { return append([]byte{0x01, 0x55, 0x12, 0x20}, sum(data)...) }

func cidText(c []byte) string {
	return "b" + strings.ToLower(base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString(c))
}

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
func cMap(entries []kv) []byte {
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
	fmt.Println("toolchain:", runtime.Version())
	return ok
}

// ----------------------------------------------------------------- vectors

func fixed(label string, n int) []byte { return sum([]byte("agora-test-vectors/" + label))[:n] }

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
	var tok0 []byte
	for i, ep := range []uint64{0, 1, 4294967296} {
		p := fmt.Sprintf("vectors.%d.", i)
		info := append([]byte("agora channel token"), u64(ep)...)
		tok := hkdfKey(seed, nil, string(info), 32)
		prk, err := hkdf.Extract(sha256.New, seed, nil)
		must(err)
		f.put(p+"inputs.seedLabel", "admission-key")
		f.put(p+"inputs.seedHex", seed)
		f.put(p+"inputs.keyEpoch", ep)
		f.put(p+"inputs.saltHex", "")
		f.put(p+"intermediates.infoHex", info)
		f.put(p+"intermediates.prkHex", prk)
		f.put(p+"outputs.channelTokenHex", tok)
		if ep == 0 {
			tok0 = tok
		}
	}
	return tok0
}

func sealedEnvelope(f flat, tok []byte) []byte {
	k := fixed("sealed-envelope-exporter-output", 16)
	nonce := fixed("sealed-envelope-nonce", 12)
	pt := []byte("agora test vector: stand-in bytes for a serialized MLSMessage (not valid MLS)")
	aad := append(append([]byte("agora/sealed/v1"), tok...), u64(7)...)
	ct := gcmSeal(k, nonce, pt, aad)
	if !gcmOpenOK(k, nonce, ct, aad, pt) {
		panic("sealed envelope does not open")
	}
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
	sealed := append(append([]byte{}, nonce...), ct...)
	f.put(p+"outputs.sealedEnvelopeHex", sealed)
	return sealed
}

func routingEnvelope(f flat, tok, sealed []byte) {
	p := "vectors.0."
	seed := f.key(p+"inputs.admissionKey", "admission-key")
	ts, exp := uint64(1792195200000), uint64(1792800000000)
	signed := cMap([]kv{
		{"ctx", cTstr("agora/envelope/v1")},
		{"channelToken", cBstr(tok)},
		{"ts", cUint(ts)},
		{"expiryHint", cUint(exp)},
		{"sealedEnvelope", cBstr(sealed)},
	})
	sig := ed25519.Sign(edPriv(seed), signed)
	if !ed25519.Verify(edPub(seed), signed, sig) {
		panic("admissionSig")
	}
	env := cMap([]kv{{"signed", cBstr(signed)}, {"admissionSig", cBstr(sig)}})
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

func chunkCase(f flat, p, name string, data, key []byte) {
	n := (len(data) + chunkSize - 1) / chunkSize
	if n == 0 {
		n = 1
	}
	f.put(p+"name", name)
	f.put(p+"plaintextSize", len(data))
	f.put(p+"plaintextSha256Hex", sum(data))
	f.put(p+"chunkCount", n)
	for i := 0; i < n; i++ {
		q := fmt.Sprintf("%sblocks.%d.", p, i)
		chunk := data[i*chunkSize : min((i+1)*chunkSize, len(data))]
		nonce := make([]byte, 12)
		binary.BigEndian.PutUint64(nonce[4:], uint64(i))
		final := byte(0)
		if i == n-1 {
			final = 1
		}
		aad := append(append(append([]byte("agora/chunk/v1"), u64(uint64(i))...), u64(uint64(n))...), final)
		blk := gcmSeal(key, nonce, chunk, aad)
		if !gcmOpenOK(key, nonce, blk, aad, chunk) {
			panic("chunk does not open")
		}
		f.put(q+"index", i)
		f.put(q+"plaintextLength", len(chunk))
		f.put(q+"nonceHex", nonce)
		f.put(q+"aadHex", aad)
		f.put(q+"blockLength", len(blk))
		f.put(q+"blockSha256Hex", sum(blk))
		f.put(q+"blockHex", blk)
		f.put(q+"blockCidText", cidText(cidRaw(blk)))
	}
}

func chunked(f flat) {
	k := fixed("chunk-content-key", 16)
	f.put("contentKeyLabel", "chunk-content-key")
	f.put("contentKeyHex", k)
	f.put("contentKeyBase64url", b64url(k))
	small := []byte("Hello, Agora!\n")
	big := make([]byte, chunkSize+1000)
	for j := range big {
		big[j] = byte(j % 251)
	}
	chunkCase(f, "vectors.0.", "empty-file", nil, k)
	chunkCase(f, "vectors.1.", "single-chunk", small, k)
	f.put("vectors.1.plaintextHex", small)
	chunkCase(f, "vectors.2.", "two-chunk", big, k)
}

func deviceBinding(f flat) {
	p := "vectors.0."
	id := f.key(p+"inputs.identityKey", "did-key-identity")
	leaf := f.key(p+"inputs.leafSignatureKey", "device-leaf-signature-key")
	msg := append([]byte("agora/v1/device-binding"), edPub(leaf)...)
	sig := ed25519.Sign(edPriv(id), msg)
	if !ed25519.Verify(edPub(id), msg, sig) {
		panic("device binding")
	}
	f.put(p+"intermediates.didKey", didKey(edPub(id)))
	f.put(p+"intermediates.signedMessageHex", msg)
	f.put(p+"outputs.extensionDataHex", sig)
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

type signer struct{ did, kid, label string }

type entry struct {
	did, protected, signature string
	pub, input, sig           []byte
}

func jsonStr(s string) string { b, err := json.Marshal(s); must(err); return string(b) }

// verdict applies the §13.1.1 signer-set rules to entries whose signatures already verified.
func verdict(es []entry, required []string, candidates []string, k int) string {
	seen := map[string]bool{}
	for _, e := range es {
		if !ed25519.Verify(e.pub, e.input, e.sig) {
			return "reject"
		}
		if seen[e.did] {
			return "reject"
		}
		seen[e.did] = true
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

func jwsCase(f flat, p, name, typ string, body []byte, signers []signer, required, candidates []string, k int) {
	cty := "application/json"
	var es []entry
	var parts []string
	for j, s := range signers {
		q := fmt.Sprintf("%ssigners.%d.", p, j)
		seed := f.key(q+"key", s.label)
		ph := `{"alg":"EdDSA","b64":false,"crit":["b64"],"kid":` + jsonStr(s.kid) +
			`,"cty":` + jsonStr(cty) + `,"agoraType":` + jsonStr(typ) + `}`
		pb := b64url([]byte(ph))
		input := append([]byte(pb+"."), body...)
		sig := ed25519.Sign(edPriv(seed), input)
		es = append(es, entry{s.did, pb, b64url(sig), edPub(seed), input, sig})
		parts = append(parts, `{"protected":`+jsonStr(pb)+`,"signature":`+jsonStr(b64url(sig))+`}`)
		f.put(q+"did", s.did)
		f.put(q+"kid", s.kid)
		f.put(q+"protectedHeaderJson", ph)
		f.put(q+"protectedB64", pb)
		f.put(q+"signingInputHex", input)
		f.put(q+"signatureHex", sig)
		f.put(q+"signatureB64", b64url(sig))
	}
	f.put(p+"name", name)
	f.put(p+"envelope.type", typ)
	f.put(p+"envelope.contentType", cty)
	f.put(p+"envelope.bodyText", string(body))
	f.put(p+"envelope.bodyHex", body)
	f.put(p+"envelope.sig", `{"signatures":[`+strings.Join(parts, ",")+`]}`)
	f.put(p+"expected", verdict(es, required, candidates, k))
	for j, d := range required {
		f.put(fmt.Sprintf("%srequiredSigners.%d", p, j), d)
	}
	if candidates != nil {
		for j, d := range candidates {
			f.put(fmt.Sprintf("%scandidateDids.%d", p, j), d)
		}
		f.put(p+"threshold", k)
	}
}

func jws(f flat) {
	billingDID := didKey(edPub(fixed("billing", 32)))
	relay := signer{"did:web:relay.example.com", "did:web:relay.example.com#key-1", "relay-provider"}
	billing := signer{billingDID, billingDID + "#" + strings.TrimPrefix(billingDID, "did:key:"), "billing"}
	sa := []byte(strings.Replace(serviceAgreementBody, "BILLING", billingDID, 1))
	gb := []byte(strings.Replace(guardianBody, "PREV", cidText(cidRaw([]byte("agora-test-vectors/previous-space-state"))), 1))
	g1a := signer{"did:web:g1.example.com", "did:web:g1.example.com#key-1", "guardian-1-key-1"}
	g1b := signer{"did:web:g1.example.com", "did:web:g1.example.com#key-2", "guardian-1-key-2"}
	g2 := signer{"did:web:g2.example.com", "did:web:g2.example.com#key-1", "guardian-2"}
	cands := []string{"did:web:g1.example.com", "did:web:g2.example.com", "did:web:g3.example.com"}
	both := []string{"did:web:relay.example.com", billingDID}
	jwsCase(f, "vectors.0.", "single-signer-relayad", "urn:agora:type:RelayAd", []byte(relayAdBody),
		[]signer{relay}, []string{"did:web:relay.example.com"}, nil, 0)
	jwsCase(f, "vectors.1.", "two-signer-serviceagreement", "urn:agora:type:ServiceAgreement", sa,
		[]signer{relay, billing}, both, nil, 0)
	jwsCase(f, "vectors.2.", "negative-missing-required-signer", "urn:agora:type:ServiceAgreement", sa,
		[]signer{billing}, both, nil, 0)
	jwsCase(f, "vectors.3.", "threshold-2-of-3-valid", "urn:agora:type:SpaceState", gb,
		[]signer{g1a, g2}, nil, cands, 2)
	jwsCase(f, "vectors.4.", "negative-threshold-duplicate-did", "urn:agora:type:SpaceState", gb,
		[]signer{g1a, g1b}, nil, cands, 2)
}

func httpPow(f flat) {
	ch := fixed("pow-challenge", 32)
	diff, exp := 20, 30
	var n uint64
	for lzBits(sum(append(append([]byte{}, ch...), u64(n)...))) < diff {
		n++
	}
	nonce := u64(n)
	hash := sum(append(append([]byte{}, ch...), nonce...))
	bad := u64(0)
	hb := sum(append(append([]byte{}, ch...), bad...))
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
	verdict := "accept"
	if lzBits(hb) < diff {
		verdict = "reject"
	}
	f.put(p+"negative.expected", verdict)
	exC, err := base64.StdEncoding.DecodeString("RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=")
	must(err)
	exN, err := base64.StdEncoding.DecodeString("AAAAAAAXBKY=")
	must(err)
	exH := sum(append(append([]byte{}, exC...), exN...))
	f.put("specExample.challengeHex", exC)
	f.put("specExample.nonceHex", exN)
	f.put("specExample.hashHex", exH)
	f.put("specExample.leadingZeroBits", lzBits(exH))
	f.put("specExample.meetsDifficulty20", lzBits(exH) >= 20)
}

func computeAll() map[string]flat {
	all := map[string]flat{}
	for _, n := range []string{"channel-token.json", "sealed-envelope.json", "routing-envelope.json",
		"chunked-blob.json", "device-binding.json", "jws.json", "http-pow.json"} {
		all[n] = flat{}
	}
	tok := channelToken(all["channel-token.json"])
	sealed := sealedEnvelope(all["sealed-envelope.json"], tok)
	routingEnvelope(all["routing-envelope.json"], tok, sealed)
	chunked(all["chunked-blob.json"])
	deviceBinding(all["device-binding.json"])
	jws(all["jws.json"])
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
