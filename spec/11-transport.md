# 11. Transport

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1832–2356 (§8).


*Binds: both.* (§11.1–§11.7 and the relay sync API in §11.8 bind IO; the management API in §11.8.9 binds clients and CO.)

Agora uses two complementary transport surfaces that serve different access patterns:

**Live stream** (§11.1–§11.7): WebTransport (QUIC) or WebSocket. Optimized for real-time delivery: new message events, MLS handshake messages (Commits and Proposals), presence, and typing indicators. Welcomes do not travel on the live stream; they are delivered to the new member's `KeyPackageEndpoint` (§4.6, §5.2.1.1). Required for any client that needs low-latency delivery.

**JMAP Sync API** (§11.8): Standard HTTPS request/response with EventSource push, served by Relays. Optimized for token-keyed envelope history retrieval and state sync. JMAP is used only for history and blobs; envelopes are written only on the live stream (§11.4). Clients that need only history (bots, compliance tools, search indexers) can use JMAP without opening a live stream connection. The Space, membership, role and invite management API is not served by Relays; it runs in the client or on CO infrastructure (§11.8.9).

A full-featured client uses both. The live stream delivers new events; JMAP fills history on startup and provides a clean sync model for catching up after a disconnect.

## 11.1 Primary Transport: WebTransport

Clients connect to Relays via **WebTransport** (IETF RFC 9000 / HTTP/3 over QUIC). WebTransport provides:

- Multiplexed bidirectional streams over a single QUIC connection
- Reliable ordered streams for MLS handshake messages and persistent message delivery
- Unreliable datagrams for presence and typing events (low-latency, loss-tolerant)

Endpoint: `https://<relay-host>/v1/agora/wt`

WebTransport requires QUIC, which runs over UDP. It is unavailable in any environment that proxies only TCP, including Tor (see §11.3).

**Reference implementations for WebTransport:** Native browser support in Chromium-based browsers and Firefox 114+. Server-side: [`webtransport-go`](https://github.com/marten-seemann/webtransport-go), [`wtransport`](https://github.com/BiagioFesta/wtransport) (Rust).

## 11.2 Fallback Transport: WebSocket

For environments where QUIC or HTTP/3 is blocked or unavailable:

Endpoint: `wss://<relay-host>/v1/agora/ws`

WebSocket carries the same message set as WebTransport (§11.4). Each WebSocket binary message carries exactly one message, and there is no multiplexing prefix. Messages that a WebTransport peer would send as datagrams are sent as ordinary binary messages. WebSocket is the mandatory transport for Tor-connected clients.

## 11.3 Tor Transport Constraints

Tor proxies TCP only. This has the following protocol-level consequences:

**WebTransport unavailable.** Clients connecting via Tor MUST use WebSocket. Clients MUST NOT attempt WebTransport when operating through a SOCKS5 proxy identifiable as Tor. Clients SHOULD detect transport failure and fall back to WebSocket without requiring user intervention.

**VTC severely degraded.** WebRTC ICE relies on UDP for STUN hole-punching and optimal media transport. Over Tor, UDP is unavailable. The only viable VTC path over Tor is TURN-over-TCP through a TURN server reachable via a `.onion` address or a Tor-friendly clearnet endpoint. Media latency over Tor circuits (typically 200–600ms round-trip) renders real-time audio/video unusable for most participants. Clients SHOULD display a warning when VTC is attempted over Tor, and MAY disable VTC participation entirely in Tor-only mode.

**Subscription fingerprinting.** Tor hides the client's address from the Relay, but the Relay still sees which `channelToken`s a connection subscribes to and when. A Relay that correlates subscription sets across Tor circuits may be able to recognize a client by them. Clients requiring strong anonymity SHOULD rotate Tor circuits periodically and SHOULD spread their subscriptions across several Relays (§12.4); decoy subscriptions do not help, because a Relay knows which tokens are registered with it.

**Rate limiting.** A Relay receiving connections from Tor exit nodes sees the exit node's IP address, not the client's IP. Relays MUST use per-`channelToken` rate limits (and proof-of-work where the Relay requires it, §11.6) as the primary spam control mechanism. Per-IP limits MUST NOT be the sole mechanism.

**Hidden service Relays.** A Relay operating as a Tor v3 hidden service publishes its `.onion` address in its manifest and `RelayAd` as `endpoints.onion` (§10.2.1, §10.5.1). Clients with Tor available SHOULD prefer `.onion` endpoints when available; they provide end-to-end Tor routing without depending on an exit node.

## 11.4 Frame Format and Message Set

The live stream carries the fixed message set defined below, identically over WebTransport and WebSocket. Each message is one CBOR data item (RFC 8949) that matches the CDDL (RFC 8610) in this section. JSON is not used on the live stream. Routing envelopes are CBOR only and have no JSON form (§5.2.2). A routing envelope travels inside a message as the exact bytes its sender encoded; a Relay MUST NOT re-encode or otherwise alter those bytes.

**Framing.**

- *WebTransport.* After the session is established, the client opens one bidirectional stream. Both sides send messages on it as a CBOR sequence (RFC 8742): each message is one complete CBOR data item, with no other framing. A `Publish` or `Deliver` MAY instead travel in a WebTransport datagram, one message per datagram. The Relay sends no `Ack` or `Error` for a `Publish` received in a datagram, and datagrams may be lost, so clients use them only for loss-tolerant traffic such as presence and typing (§5.3). A message too large for a datagram goes on the stream. A Relay sends an envelope that arrived in a datagram as a datagram to WebTransport subscribers and as an ordinary message to WebSocket subscribers.
- *WebSocket.* Each binary WebSocket message carries exactly one message. A Relay that receives a text WebSocket message MUST close the connection.

**Common members.** Every message is a CBOR map with text-string keys. `v` is the live protocol version negotiated in the hello exchange (§11.6); this specification defines version 1. `t` names the message. A receiver MUST discard a message with an unknown `v` and MAY close the connection. A receiver MUST ignore map keys it does not recognize. A Relay answers a message with an unknown `t` with an `Error` of code `bad-message`; a client ignores such a message. Client requests carry `id`, an unsigned integer chosen by the client and unique among its outstanding requests on the connection. The Relay answers each request with exactly one `Ack` or `Error` carrying the same `id`, except a `Publish` received in a datagram.

**Size.** A routing envelope in a `Publish` or `Deliver` MUST NOT exceed 65,536 bytes, the `maxEnvelopeBytes` of the Relay's JMAP session (§11.8.3). Larger content travels as a blob (§10.4.4). A Relay answers an oversized `Publish` with `Error` code `too-large`.

```cddl
message    = client-msg / relay-msg
client-msg = ClientHello / AdmissionProof / Subscribe / Unsubscribe
           / Publish / PinInstruction / PushRegister
relay-msg  = RelayHello / AdmissionChallenge / Deliver / Ack / Error

channel-token  = bstr .size 32   ; routing token, §5.2.2
envelope-bytes = bstr            ; exact bytes of one routing envelope, §5.2.2
cid            = bstr            ; CID in binary form, §13.1
req-id         = uint
handle         = bstr .size 32   ; pushHandle, §11.7.3

ClientHello = {
  "v": 1, "t": "ClientHello",
  "versions": [+ uint]           ; live protocol versions the client supports
}

RelayHello = {
  "v": 1, "t": "RelayHello",
  "relayDID": tstr,              ; the Relay's DID, §10.2.1
  "version": uint                ; negotiated live protocol version
}

AdmissionChallenge = {
  "v": 1, "t": "AdmissionChallenge",
  "challenge": bstr .size 32,
  "difficulty": uint .le 64,     ; required leading zero bits
  "expiresIn": uint              ; seconds
}

AdmissionProof = {
  "v": 1, "t": "AdmissionProof",
  "challenge": bstr .size 32,
  "powNonce": bstr .size (8..32)
}

Subscribe = {
  "v": 1, "t": "Subscribe", "id": req-id,
  "tokens": [+ channel-token]
}

Unsubscribe = {
  "v": 1, "t": "Unsubscribe", "id": req-id,
  "tokens": [+ channel-token]
}

Publish = {
  "v": 1, "t": "Publish", "id": req-id,
  "envelope": envelope-bytes
}

Deliver = {
  "v": 1, "t": "Deliver",
  "envelope": envelope-bytes
}

Ack = {
  "v": 1, "t": "Ack", "id": req-id,
  ? "cid": cid                   ; the envelope id (CID of the signed
                                 ; bytes only), in answer to Publish
}

Error = {
  "v": 1, "t": "Error",
  ? "id": req-id,                ; absent for a connection-level error
  "code": error-code,
  ? "token": channel-token,      ; the token concerned, for unknown-token,
                                 ; or token-withdrawn or token-rotated
                                 ; without "id"
  ? "detail": tstr               ; diagnostic text, not for display
}

error-code = "bad-message" / "unsupported-version" / "unknown-token"
           / "token-withdrawn" / "bad-admission-sig" / "insufficient-pow"
           / "expired" / "replayed" / "too-large" / "rate-limited"
           / "quota-exceeded" / "unknown-cid" / "stream-closed"
           / "token-rotated" / "internal"

PinInstruction = {
  "v": 1, "t": "PinInstruction", "id": req-id,
  "signed": bstr .cbor pin-op,
  "admissionSig": bstr .size 64  ; Ed25519 over the exact bytes of "signed"
}

pin-op = {
  "op": "pin" / "unpin" / "seed",
  "channelToken": channel-token,
  "cids": [+ cid],
  "nonce": bstr .size 16,
  "expires": uint                ; seconds since the Unix epoch
}

upload-op = {                    ; blob upload authorization, §11.8.2
  "op": "upload",
  "channelToken": channel-token,
  "sha256": bstr .size 32,       ; SHA-256 of the uploaded bytes
  "nonce": bstr .size 16,
  "expires": uint
}

PushRegister = {
  "v": 1, "t": "PushRegister", "id": req-id,
  "pushHandle": handle,
  "proxyEndpoint": tstr,         ; the push proxy's endpoint, §11.7.2
  "tokens": [* channel-token],   ; empty array deletes the registration
  ? "replaces": handle,          ; previous pushHandle, §11.7.6
  "ttl": uint                    ; seconds
}
```

**Hello and admission.** `ClientHello`, `RelayHello`, `AdmissionChallenge` and `AdmissionProof` are defined in §11.6. Every other message carries the negotiated version as `v`.

**Subscribe and Unsubscribe.** A Relay MUST NOT require any proof to subscribe; subscriptions are rate-limited (§11.6). After answering a `Subscribe` with `Ack`, the Relay sends a `Deliver` for each envelope it accepts on any subscribed token until the client unsubscribes from that token or the connection closes. A subscription delivers only envelopes accepted after it; earlier envelopes come from the JMAP sync API (§11.8). A Relay delivers nothing for a token that has no registered admission key. It answers a `Subscribe` with one `Ack` for the request, subscribing the tokens that are registered, and sends, for each listed token that is not registered, an `Error` without `id` with code `unknown-token` and `token` set to that token (or `token-withdrawn`, as below). A client fails over for those tokens as §10.3.5 describes.

**Publish.** On a `Publish` the Relay:

1. decodes the routing envelope and its `signed` field (§5.2.2), without re-encoding either;
2. looks up the admission public key registered for the `channelToken` in `signed` (§10.5.3), and answers `unknown-token` if there is none;
3. verifies `admissionSig` over the exact bytes of `signed` under that key, and answers `bad-admission-sig` if it fails;
4. checks `powProof` against its `minPowDifficulty` (§10.5.2), and answers `insufficient-pow` if it falls short;
5. applies the remaining acceptance checks of §10.5.4 and §10.4.3, answering `expired`, `rate-limited` or `quota-exceeded` as they apply. An envelope is `expired` if its `ts` is more than 300 seconds ahead of the Relay's clock or older than the `retentionDays` of the agreement under which the key is registered, or if it carries an `expiryHint` that has already passed;
6. stores the envelope under its `channelToken` for the retention of the agreement under which the key is registered, answers `Ack` with `cid` set to the envelope `id` (§5.2.2), sends a `Deliver` with the same envelope bytes to every other connection subscribed to the token, and fans the envelope out as §10.4.2 describes.

If the Relay already holds an envelope with the same `id` under the token, it answers `Ack` with that `cid` and neither stores nor delivers the envelope again.

**Deliver.** A client processes a delivered envelope as §5.2.2 describes.

**Error.** An `Error` without `id` reports a problem with the connection as a whole; the Relay MAY close the connection after sending it. The exceptions are `unknown-token`, `token-withdrawn` and `token-rotated` carrying `token`, which concern one token and leave the connection open.

**Stream closed.** `stream-closed` is not sent on the live protocol. It is the code a sequencer returns for a Commit submitted on the commit stream of a token whose key has been replaced (§10.5.3, §14.4.3).

**Withdrawn tokens.** `unknown-token` means that no admission key is registered for the token. `token-withdrawn` means that the token's key was registered and is no longer admitted: the CO deregistered it (§10.5.3), the agreement under which it was registered has ended (§10.5.1, §10.5.3), or the Relay suspended the token (§10.4.7). When a key stops being admitted, the Relay sends each connection subscribed to its token an `Error` without `id`, with code `token-withdrawn` and `token` set to that token, and ends those subscriptions without closing the connection. It answers a later `Subscribe`, `Publish` or `PinInstruction` naming that token with `token-withdrawn` for as long as it still holds envelopes under the token, and with `unknown-token` after that. On either code the client fetches the current `ChannelAdmissionKey` (§5.2.2). In a DM group or a self-group, the client instead fetches that token's history (§11.8), processes the Commits in it, and uses the key in `agora_admission` (§4.6). If its token is the one refused, the client uses another Relay in the key's relay list (§10.3.5). When a Relay applies a registration whose key has `replaces` (§10.5.3), it sends each connection subscribed to the replaced token an `Error` without `id`, with code `token-rotated` and `token` set to the replaced token, and keeps those subscriptions open. On `token-rotated` the client fetches the current `ChannelAdmissionKey` (§5.2.2).

**PinInstruction.** A pin instruction asks the Relay to keep, or stop keeping, envelopes and blobs past retention (§5.2.6). The Relay MUST reject an instruction, with code `bad-message`, whose `signed` value does not decode to a `pin-op`. A routing envelope's `signed` map (§5.2.2) has no `op` member, so a signature made for one is never accepted as the other. The Relay then looks up the key registered for `channelToken` and verifies `admissionSig` over the exact bytes of `signed`, answering as for `Publish`. It answers `expired` if `expires` has passed or is more than 600 seconds ahead of its clock, and `replayed` if it has already accepted the same `nonce` for that token. For `pin`, it adds the pin's token as a holder of each listed CID that it holds (§10.4.4), exempts those CIDs from retention expiry and charges the storage to the agreement under which the key is registered, answering `quota-exceeded` if the agreement's quota would be exceeded and `unknown-cid` if it holds none of the CIDs after attempting to pull them (§10.4.4). For `unpin`, it removes the exemption. For `seed`, it fetches each listed CID it does not hold from other Relays carrying the token, as for pull-through (§10.4.4), and keeps what it obtains for the ordinary retention window without a pin exemption; it answers `Ack` once it has accepted the instruction, before the fetches finish. A CO sends `seed` to a Relay newly added to a channel's relay list, signing with the channel's admission key, which its registration service holds. Envelope CIDs in a `pin-op` are envelope `id`s, the CIDs of the envelopes' `signed` bytes (§5.2.2). The role check that decides whether a member may pin is made by clients against Space state (ARCHITECTURE §6.2), never by the Relay.

**PushRegister.** Defined in §11.7.3.

**Reference implementations for CBOR:** [`cbor2`](https://pypi.org/project/cbor2/) (Python), [`cbor` crate](https://crates.io/crates/cbor) (Rust), [`cbor-js`](https://github.com/paroga/cbor-js) (JS), [`fxamacker/cbor`](https://github.com/fxamacker/cbor) (Go).

## 11.5 Direct Peer Connections

Clients MAY establish direct WebRTC data channels to each other, bypassing Relays entirely. The `VoiceSignal` mechanism (§6.4) is used for ICE negotiation. Direct peer connections are mandatory for voice and video (media MUST NOT transit Relays) and optional for text messaging (latency optimization).

On WireGuard-based overlays (Tailscale, Headscale), direct peer connections benefit from overlay-managed NAT traversal. Overlay-internal `100.x.x.x` addresses appear as ICE host candidates and are preferred over STUN-discovered public addresses when both peers are on the same overlay network.

## 11.6 Client Hello and Connection Admission

Relays never authenticate client identity. Writes are gated by the `admissionSig` on each envelope (§5.2.2, ARCHITECTURE §6.2), which shows that the sender holds the channel's current admission key without revealing which member sent it. Admission key registration is gated by the CO billing DID (§10.5.1), and storage and bandwidth by the quotas of the `ServiceAgreement` (§10.5.1). A Relay MUST NOT request or accept DID authentication from a client, and MUST NOT keep DID ban lists; bans are MLS Removes followed by an admission key rotation (ARCHITECTURE §6.2).

### Client Hello

Immediately after the transport connection opens, the client sends a `ClientHello` (§11.4). It is unauthenticated and carries only the live protocol versions the client supports. In CBOR diagnostic notation:

```
{"v": 1, "t": "ClientHello", "versions": [1]}
```

The Relay answers with a `RelayHello`:

```
{"v": 1, "t": "RelayHello", "relayDID": "did:web:relay.example.com", "version": 1}
```

`version` is the highest version in `versions` that the Relay supports, and every later message on the connection carries it as `v`. If there is no common version, the Relay sends an `Error` with code `unsupported-version` and closes the connection. The four hello and admission messages keep their version 1 form in every protocol version, so any two versions can negotiate. The version in the transport endpoint's URL path (§11.1, §11.2) is fixed at connection time and is separate from this negotiation. The Relay MUST NOT process any other client message before it has sent `RelayHello`, and a client sends none before receiving it.

The client MUST check `relayDID` against the Relay's manifest (§10.2.1); the Relay itself is authenticated by its TLS certificate or `.onion` address (§10.3.4.7).

Text format capabilities (§5.2.7) are not declared to the Relay. A Relay that cached them per client and served them to other clients would learn identity, contrary to ARCHITECTURE S1.

### Connection Admission

A Relay rate-limits connections, subscriptions, publications, history reads (live stream and JMAP, §11.8) and push registrations (§11.7.3) per network address and per `channelToken`. Limit values are local Relay policy, with one floor: a Relay MUST admit at least 20 envelopes per second and 256 KiB per second, sustained, on each `channelToken` before rate-limiting it, so that the presence, typing and Commit traffic a channel generates (§5.3) is never throttled. Per-address limits MUST NOT be the sole control, because many clients can share one address (Tor exits, carrier NAT).

Under load, a Relay MAY require a proof-of-work challenge before accepting a connection. It then answers the `ClientHello` with an `AdmissionChallenge` instead of a `RelayHello`:

```
{"v": 1, "t": "AdmissionChallenge",
 "challenge": h'46f278133a8d5d68b78eb0d70022fc0a9222974859f7a05f73d6571bf7770aec',
 "difficulty": 20, "expiresIn": 30}
```

The client chooses a `powNonce` of 8 to 32 bytes such that SHA-256(`challenge` || `powNonce`) has at least `difficulty` leading zero bits, counted from the most significant bit of the first byte of the hash, and replies within `expiresIn` seconds:

```
{"v": 1, "t": "AdmissionProof",
 "challenge": h'46f278133a8d5d68b78eb0d70022fc0a9222974859f7a05f73d6571bf7770aec',
 "powNonce": h'00000000001704a6'}
```

On a valid proof the Relay sends the `RelayHello`; otherwise it closes the connection. A Relay MUST accept each `challenge` at most once. A proof-of-work challenge lets a client whose address has hit its per-address limit still connect, so clients behind shared addresses are not locked out. This connection-level proof is separate from the per-envelope `powProof` of §10.5.2, which a Relay with a nonzero `minPowDifficulty` requires on every routing envelope whatever happened at connection time.

Privacy Pass tokens are a possible future admission extension and are not part of this version.

## 11.7 Push Notification Proxy (Optional)

Mobile clients backgrounded by the OS cannot maintain a persistent WebTransport or WebSocket connection. Agora supports an optional **Push Notification Proxy** that enables mobile wake-up notifications without exposing message content, channel identity, or sender identity to the notification infrastructure.

Push is enabled by default on mobile clients, and what the push proxy and the Relay observe for push is within the observation budget (ARCHITECTURE §5 item 7). Users MAY disable push; a client with push disabled makes no registration with either. A Relay MAY designate a push proxy in its manifest (§11.7.2), and a CO MAY designate its own push proxy for its members. Clients that maintain persistent connections (desktop clients, server-side bots) do not need one.

### 11.7.1 Privacy Model

The fundamental constraint: APNs (Apple) and FCM (Google) are centralized services that require a server-side component that knows which device token to wake up. The goal is to limit what the proxy and the Relay learn to the minimum necessary for their function.

**What the push proxy learns** (ARCHITECTURE §5 item 7):
- Opaque device push handles: the client's `pushHandle` (a random token, not linked to any DID or channel), its APNs or FCM device token, and its platform (`apns` or `fcm`)
- Wake-up timing: when a wake-up arrives for each `pushHandle`
- The `relayDID` that signed each wake-up request (an IO-to-IO relationship, ARCHITECTURE §5 item 8)

**What the Relay learns** (ARCHITECTURE §5 item 7):
- Each registered `pushHandle`, its proxy endpoint, and the set of `channelToken`s registered to it. The Relay therefore learns which routing tokens wake the same device, across sessions and network addresses.

**What neither learns:**
- The client's DID
- The channel or Space behind any `channelToken`, except the token of a `keyAccess: public` broadcast channel, which the CO publishes with its public Space (§3.4)
- Any message content
- The identity of any message sender

The `pushHandle` is the separation layer: the Relay knows `channelToken`s → `pushHandle` and never the client's DID or device token; the proxy knows `pushHandle` → device token and never a `channelToken`. Neither party links a device to a DID or to a channel identity.

### 11.7.2 Relay Manifest Extension

A Relay that supports push proxy wake-up declares its associated push proxy in the Relay Manifest:

```json
"pushProxy": {
  "endpoint": "https://push.example.com/v1/agora/push",
  "proxyDID": "did:key:z6MkProxy...",
  "platforms": ["apns", "fcm"],
  "registrationEndpoint": "https://push.example.com/v1/agora/push/register"
}
```

### 11.7.3 Client Registration

On first launch on a mobile device, a client wishing to receive push notifications:

1. Generates a random 256-bit `pushHandle` and stores it locally.
2. Obtains a platform device token from APNs or FCM via the OS push notification API.
3. Registers `{ pushHandle, deviceToken, platform }` with the push proxy:

```
POST /v1/agora/push/register
{
  "pushHandle":  "_8eP_Gb8wAi_Qlsoi2d0YT_nKN3GY0sy5sgel3C1u-A",
  "deviceToken": "740f4707bebcf74f9b7c25d48e3358945f6aa01da5ddb387462c7eaf61bb78ad",
  "platform":    "apns",
  "appBundleID": "com.example.agora"
}
Response: 200 { "registered": true, "ttl": 2592000 }
```

`pushHandle` is the 32-byte handle in base64url without padding (RFC 4648 §5). `deviceToken` is the device token as the platform's API supplies it: for APNs the token bytes in lower-case hexadecimal, for FCM the registration token string. `platform` is `"apns"` or `"fcm"`.

4. Sends a `PushRegister` (§11.4) on its live stream connection to each Relay it uses, with the `pushHandle`, the proxy's `endpoint` (§11.7.2) and the `channelToken`s it wants wake-ups for. The registration carries no identity and is rate-limited per address and per `channelToken` (§11.6). The Relay keys it by `pushHandle` only and answers with `Ack`:

```
{"v": 1, "t": "PushRegister", "id": 7,
 "pushHandle": h'ffc78ffc66fcc008bf425b288b6774613fe728ddc6634b32e6c81e9770b5bbe0',
 "proxyEndpoint": "https://push.example.com/v1/agora/push",
 "tokens": [h'c62684507f1a9865dabfd9823d1775e9e7b67807d39d25e5a6e0d609853617b1',
            h'a9fb192f6b985a1299167790744493bb80d46b3c9b70526ca773fdb75953807b'],
 "ttl": 2592000}
```

A `PushRegister` replaces the whole token set registered for its `pushHandle`; an empty `tokens` array deletes the registration. A Relay MUST drop a registration when its `ttl` expires and MUST NOT keep one longer than 30 days (2,592,000 seconds), whatever `ttl` asks for.

**Token rotation.** A `channelToken` changes whenever the channel's admission key rotates (§5.2.2). When the client obtains a new `ChannelAdmissionKey`, it sends a new `PushRegister` with the updated token set. When a Relay processes an `AdmissionKeyDeregistration` (§10.5.3), it removes that key's token from every push registration.

**Registration renewal:** Push registrations have a TTL (default 30 days). Clients MUST renew with the proxy and with each Relay before expiry. APNs/FCM device tokens may also change; clients MUST re-register with the proxy when they receive a new device token.

### 11.7.4 Wake-Up Flow

When a Relay accepts an envelope on a `channelToken` that is registered to a `pushHandle` whose client has no live stream connection to the Relay, the Relay:

1. Looks up the `{ pushHandle, proxyEndpoint }` registered for that `channelToken`. The Relay sends the wake-up to whichever proxy the client registered, its own or one designated by the client's CO.
2. Sends a wake-up request to `<proxyEndpoint>/wake`, signed with RFC 9421 HTTP Message Signatures as profiled in §10.2.3:

```
POST https://push.example.com/v1/agora/push/wake
Content-Type: application/json

{"pushHandle": "_8eP_Gb8wAi_Qlsoi2d0YT_nKN3GY0sy5sgel3C1u-A"}
```

`pushHandle` is in base64url without padding, as at registration (§11.7.3).

3. The proxy maps `pushHandle → deviceToken` and sends a push notification with no content to APNs or FCM.

Wake-ups carry no content and no urgency. Relays send every wake-up the same way, and the proxy sends every wake-up to APNs or FCM with the same platform priority and the same empty payload. The OS wakes the app; the app reconnects to its Relay, subscribes, and fetches what it missed through the JMAP sync API (§11.8). The device decides how to notify the user after it has decrypted the messages.

To blur timing, Relays SHOULD add random jitter before sending a wake-up and SHOULD coalesce wake-ups for the same `pushHandle` that fall within the jitter window into one request.

### 11.7.5 Proxy Authentication and Rate Limiting

The push proxy MUST verify the RFC 9421 signature on every wake-up request, per §10.2.3, against the sending Relay's manifest. Wake-up requests from unknown or untrusted Relay DIDs MUST be rejected.

Proxies SHOULD rate-limit wake-up requests per `pushHandle` to prevent a rogue Relay from spamming a client device (for example: 1 push per 5 seconds per handle, with a burst allowance of 3).

### 11.7.6 Handle Rotation

A client MAY rotate its `pushHandle` at any time for privacy or after suspected handle compromise. Rotation procedure:

1. Generate a new `pushHandle`.
2. Register `{ new pushHandle, deviceToken }` with the proxy.
3. Send each Relay a `PushRegister` with the new `pushHandle`, its `channelToken`s, and `replaces` set to the old `pushHandle`. The Relay atomically replaces the old registration with the new one.
4. Delete the old `pushHandle` from the proxy: `DELETE /v1/agora/push/register/{pushHandle}`.

## 11.8 JMAP Management and Sync API

JMAP ([RFC 8620](https://jmap.io)) is used at two layers that run on different operators:

- **Relay sync API (IO).** Agora Relays expose a JMAP API limited to blind objects: ciphertext envelopes keyed by `channelToken`, and blobs (§11.8.1–§11.8.8). It provides history retrieval and state synchronization (state tokens, `/changes` deltas, batched method calls, ResultReferences, and EventSource push) without requiring a persistent connection. A Relay serves the recent envelopes it holds for each `channelToken`, for the retention set by the `ServiceAgreement` under which the token's admission key is registered (§10.5.1); older history comes from members' stores and the CO archive (§5.2.5). A Relay holds no mapping from `channelToken` to `channelID` or MLS group ID, and serves no Space, Channel, membership, role or invite objects (ARCHITECTURE S1, §7 item 4).
- **Management API (client / CO).** The Space, channel, membership, role and invite API runs in the client (a local daemon) or on CO infrastructure, never on a Relay (§11.8.9).

### 11.8.1 Endpoints

Every Relay declares the `jmap-sync-v1` capability (§10.4.3) and MUST expose the following endpoints under the base URL declared in `endpoints.jmapSync` in its manifest. Paths are relative to that base; with the base `https://relay.example.com/v1/agora/jmap`, the Session object is at `https://relay.example.com/v1/agora/jmap/.well-known/jmap`.

```
GET  {base}/.well-known/jmap                      Session object (unauthenticated)
POST {base}/api                                   JMAP request/response
GET  {base}/events                                EventSource push stream
POST {base}/upload/{accountId}                    Blob upload
GET  {base}/download/{accountId}/{blobId}/{name}  Blob download
```

Clients locate the Session object from `endpoints.jmapSync`, not by RFC 8620 autodiscovery at the origin's `/.well-known/jmap`.

### 11.8.2 Authentication

Relays never authenticate client identity on JMAP requests (§11.6). Envelope history is addressed by `channelToken`. The sync API is read-only for envelopes: envelopes are written only by `Publish` on the live stream (§11.4), where the Relay verifies `admissionSig` (ARCHITECTURE §6.2). Requests are rate-limited per network address and per `channelToken` (§11.6).

**Blob upload.** A blob upload (`POST {base}/upload/{accountId}`) MUST carry an `Agora-Storage-Auth` header whose value is the base64url encoding (no padding) of the CBOR map `{"signed": bstr .cbor upload-op, "admissionSig": bstr .size 64}`, where `upload-op` is defined in §11.4 and `admissionSig` is an Ed25519 signature under the admission key of `channelToken` over the exact bytes of `signed`. The Relay verifies the signature, `expires` and `nonce` as for a `PinInstruction` (§11.4), checks that `sha256` equals the SHA-256 of the uploaded bytes, and charges the blob to the storage quota of the agreement under which that key is registered (§10.5.1). It rejects the upload with HTTP 403 if the header is missing or fails any check, and with HTTP 507 if the agreement's storage quota would be exceeded. On success, the `blobId` of the RFC 8620 upload response is the CID (§13.1) of the uploaded bytes in its text form, with codec `raw`; the Relay serves the same bytes under the `dag-pb` CID with the same multihash (§10.4.4). The Relay then replicates the blob to other Relays carrying the token (§10.4.4), so a client uploads each blob to one Relay only. A file is uploaded as its chunk blocks and, for more than one chunk, its root block, each in its own upload (§14.3.4). Blob downloads need no authorization; blobs are encrypted (§3.4).

### 11.8.3 Capability and Session Object

**Capability URI:** `urn:agora:v1`

Every JMAP request MUST include `"urn:ietf:params:jmap:core"` and `"urn:agora:v1"` in the `using` array.

The Session object returned by `GET {base}/.well-known/jmap`:

```json
{
  "capabilities": {
    "urn:ietf:params:jmap:core": {
      "maxSizeUpload": 104857600,
      "maxConcurrentUpload": 4,
      "maxSizeRequest": 10485760,
      "maxConcurrentRequests": 4,
      "maxCallsInRequest": 16,
      "maxObjectsInGet": 500,
      "maxObjectsInSet": 500,
      "collationAlgorithms": ["i;unicode-casemap"]
    },
    "urn:agora:v1": {
      "maxEnvelopeBytes": 65536,
      "maxAttachmentBytes": 104857600
    }
  },
  "accounts": {
    "a-relay": {
      "name": "relay.example.com",
      "isPersonal": false,
      "isReadOnly": false,
      "accountCapabilities": { "urn:agora:v1": {} }
    }
  },
  "primaryAccounts": { "urn:agora:v1": "a-relay" },
  "username": "",
  "apiUrl": "https://relay.example.com/v1/agora/jmap/api",
  "downloadUrl": "https://relay.example.com/v1/agora/jmap/download/{accountId}/{blobId}/{name}?accept={type}",
  "uploadUrl": "https://relay.example.com/v1/agora/jmap/upload/{accountId}",
  "eventSourceUrl": "https://relay.example.com/v1/agora/jmap/events?types={types}&closeafter={closeafter}&ping={ping}",
  "state": "s-1"
}
```

### 11.8.4 Object Types

#### Envelope

A single routing envelope (§5.2.2) as stored by the Relay. The name `Envelope` avoids a collision with the `Message` type of the JMAP Chat specification (draft-atwood-jmap-chat-00). **The `envelope` field holds the routing envelope exactly as the Relay received it; its sealed or broadcast payload is ciphertext the Relay cannot read.** Clients verify and decrypt it as they would on the live stream, using their local MLS group state.

```
id              String     The envelope id (§5.2.2): the CID of the envelope's signed bytes only, in CID text form (§13.1)
channelToken    String     Routing token under which the envelope was published, base64url without padding (RFC 4648 §5)
envelope        String     base64url without padding: the exact bytes of the routing envelope as received
receivedAt      UTCDate    Relay's clock; authoritative for stable sort order
expiresAt       UTCDate|null  Time the Relay will drop the envelope; null = no configured expiry
```

`Envelope` is read-only: there is no `Envelope/set`.

### 11.8.5 Methods

All methods follow RFC 8620 conventions. `/get`, `/set`, `/changes`, and `/query` have their standard semantics. Methods marked **read-only** have no `/set`.

| Method | Notes |
|---|---|
| `Envelope/get` | Fetch by ids. Returns encrypted blobs. |
| `Envelope/changes` | State-token delta. Returns added/updated/destroyed ids since a given state. |
| `Envelope/query` | Filter by `channelToken`; sort by `receivedAt`. |
| `Envelope/queryChanges` | RFC 8620 extended query-delta. |

**Batching and ResultReferences.** Standard RFC 8620 §4 batching applies. Multiple method calls in a single request execute in order; `#`-prefixed argument keys reference results of prior calls via RFC 6901 JSON Pointers.

Example: query a channel token's envelopes then fetch them in one round-trip:

```json
{
  "using": ["urn:ietf:params:jmap:core", "urn:agora:v1"],
  "methodCalls": [
    ["Envelope/query", {
      "accountId": "a-relay",
      "filter": {"channelToken": "base64url..."}
    }, "0"],
    ["Envelope/get", {
      "accountId": "a-relay",
      "#ids": {
        "resultOf": "0",
        "name": "Envelope/query",
        "path": "/ids"
      }
    }, "1"]
  ]
}
```

### 11.8.6 Relay Blindness Preservation

The Relay's blindness properties (§10.4.1) are fully preserved under the JMAP API:

- **Envelope content.** The payload inside `Envelope/envelope` is always ciphertext. The Relay stores and serves it without decrypting. A subpoena against the Relay yields only ciphertext.
- **Channel identity.** The Relay keys envelopes by `channelToken` only. It holds no mapping from `channelToken` to `channelID` or MLS group ID; that mapping exists only in the management API (§11.8.9).
- **Sender identity.** No sender identity appears in any JMAP object. The routing envelope carries no sender (§5.2.2); the sender is sealed inside the ciphertext.
- **Community structure.** The Relay serves no Space, Channel, membership, role or invite objects and no member counts.

### 11.8.7 EventSource Push

The Relay emits `StateChange` events on the EventSource stream when any tracked object type's state advances. Clients use these as a trigger to call the corresponding `/changes` method; they do not carry content.

```
event: state
data: {"changed": {"a-relay": {"Envelope": "s-43"}}}
```

Only object types whose state has changed are included in a given event. The live stream (§11.1–§11.2) provides lower-latency delivery for new messages; EventSource is the appropriate trigger for history-sync clients and background processes that do not maintain a live stream connection.

### 11.8.8 Scope: JMAP vs Live Stream

| Operation | JMAP (§11.8) | Live Stream (§11.1–§11.7) |
|---|---|---|
| History retrieval and sync | ✓ | ✗ |
| Space / channel / membership / role / invite management | ✗ (client / CO only, §11.8.9) | ✗ |
| Programmatic / bot access | ✓ | ✗ |
| Blob upload / download | ✓ | ✗ |
| Envelope publication (`Publish`) | ✗ | ✓ |
| New message delivery | ✗ | ✓ |
| Pin / unpin instruction (`PinInstruction`) | ✗ | ✓ |
| MLS handshake (Commit / Proposal); Welcomes go to the `KeyPackageEndpoint` (§5.2.1.1) | ✗ | ✓ |
| Presence and typing indicators | ✗ | ✓ |
| Push notification registration (`PushRegister`) | ✗ | ✓ |

### 11.8.9 Management API (Client / CO)

*Binds: CO and clients.*

The Space, channel, membership, role and invite management API is the JMAP Chat specification family (draft-atwood-jmap-chat-00, capability `urn:ietf:params:jmap:chat`, and its companion drafts), as profiled and carried by Agora per §14. This specification does not restate it.

The management API runs in the client (a local daemon serving the user's own devices) or on CO infrastructure. A Relay MUST NOT serve it. Its state is derived from CO-signed Space state (ARCHITECTURE S4) and decrypted MLS application messages, and it is the only place a `channelID` (or a DM's MLS group ID) is mapped to a `channelToken`. Clients use it to resolve a channel to its current `channelToken`, which they derive from the channel's current `ChannelAdmissionKey` (ARCHITECTURE §6.2), then use the Relay sync API (§11.8.1–§11.8.8) and the live stream to move ciphertext under that token.

---
