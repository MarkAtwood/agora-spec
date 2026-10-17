# 11. Transport

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1832–2356 (§8).


*Binds: both.* (§11.1–§11.7 and the relay sync API in §11.8 bind IO; the management API in §11.8.9 binds clients and CO.)

Agora uses two complementary transport surfaces that serve different access patterns:

**Live stream** (§11.1–§11.7): WebTransport (QUIC) or WebSocket. Optimized for real-time delivery: new message events, MLS handshake messages (Commits, Proposals, Welcomes), presence, and typing indicators. Required for any client that needs low-latency delivery.

**JMAP Sync API** (§11.8): Standard HTTPS request/response with EventSource push, served by Relays. Optimized for token-keyed envelope history retrieval and state sync. Clients that need only history (bots, compliance tools, search indexers) can use JMAP without opening a live stream connection. The Space, membership, role and invite management API is not served by Relays; it runs in the client or on CO infrastructure (§11.8.9).

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

WebSocket carries the same message framing over a single multiplexed binary stream. Multiplexing is handled by a lightweight channel ID prefix on each frame. WebSocket is the mandatory transport for Tor-connected clients.

## 11.3 Tor Transport Constraints

Tor proxies TCP only. This has the following protocol-level consequences:

**WebTransport unavailable.** Clients connecting via Tor MUST use WebSocket. Clients MUST NOT attempt WebTransport when operating through a SOCKS5 proxy identifiable as Tor. Clients SHOULD detect transport failure and fall back to WebSocket without requiring user intervention.

**VTC severely degraded.** WebRTC ICE relies on UDP for STUN hole-punching and optimal media transport. Over Tor, UDP is unavailable. The only viable VTC path over Tor is TURN-over-TCP through a TURN server reachable via a `.onion` address or a Tor-friendly clearnet endpoint. Media latency over Tor circuits (typically 200–600ms round-trip) renders real-time audio/video unusable for most participants. Clients SHOULD display a warning when VTC is attempted over Tor, and MAY disable VTC participation entirely in Tor-only mode.

**Gossipsub fingerprinting.** Connecting to gossipsub via Tor provides IP-level anonymity but gossipsub peer scoring observes message timing and topic subscription patterns. A sufficiently persistent observer correlating topic subscription events across Tor circuits may be able to fingerprint clients by behavior. Clients requiring strong anonymity SHOULD rotate Tor circuits periodically and SHOULD subscribe to decoy topics (§12.4).

**Rate limiting.** A Relay receiving connections from Tor exit nodes sees the exit node's IP address, not the client's IP. Relays MUST use per-`channelToken` rate limits and PoW requirements as the primary spam control mechanism. Per-IP limits MUST NOT be the sole mechanism.

**Hidden service Relays.** A Relay operating as a Tor v3 hidden service publishes its `.onion` address in its manifest and `RelayAd` as `endpoints.onion` (§10.2.1, §10.5.1). Clients with Tor available SHOULD prefer `.onion` endpoints when available; they provide end-to-end Tor routing without depending on an exit node.

## 11.4 Frame Format

All frames are CBOR-encoded (compact binary). Every Agora object carried in a frame's `payload` is a typed payload envelope (§13.1), carried as its exact encoded bytes. Clients MAY use JSON encoding for debugging purposes; Relays MUST accept both JSON and CBOR.

Frame structure:

```
[version: u8, type: u8, topic: string, payload: bytes]
```

`version` values: `0x01` = frame format v1 (this specification). A Relay that receives a frame with an unknown `version` byte MUST discard it and MAY close the connection.

`type` values: `0x01` Gossip, `0x02` MLS, `0x03` Ephemeral, `0x04` Control.

**Reference implementations for CBOR:** [`cbor2`](https://pypi.org/project/cbor2/) (Python), [`cbor` crate](https://crates.io/crates/cbor) (Rust), [`cbor-js`](https://github.com/paroga/cbor-js) (JS), [`fxamacker/cbor`](https://github.com/fxamacker/cbor) (Go).

## 11.5 Direct Peer Connections

Clients MAY establish direct WebRTC data channels to each other, bypassing Relays entirely. The `VoiceSignal` mechanism (§6.4) is used for ICE negotiation. Direct peer connections are mandatory for voice and video (media MUST NOT transit Relays) and optional for text messaging (latency optimization).

On WireGuard-based overlays (Tailscale, Headscale), direct peer connections benefit from overlay-managed NAT traversal. Overlay-internal `100.x.x.x` addresses appear as ICE host candidates and are preferred over STUN-discovered public addresses when both peers are on the same overlay network.

## 11.6 Client Hello and Connection Admission

Relays never authenticate client identity. Writes are gated by the epoch access proof carried on each envelope (ARCHITECTURE §6.2), which shows that the sender is a current member without revealing which member. Group registration is gated by the CO billing key (§10.5.1), and storage and bandwidth by the quotas of the `RelayServiceAgreement` (§10.5.1). A Relay MUST NOT request or accept DID authentication from a client, and MUST NOT keep DID ban lists; bans are MLS Removes (ARCHITECTURE §6.2).

### Client Hello

Immediately after transport connection the client sends a `ClientHello` in a `0x04` Control frame. It is unauthenticated and carries only version information:

```json
{
  "@type": "ClientHello",
  "clientVersion": "agora/v1",
  "supportedTransportVersions": ["v1"],
  "supportedGossipVersions": ["v1"],
  "supportedFrameVersions": [1]
}
```

The Relay answers with a `RelayHello`:

```json
{
  "@type": "RelayHello",
  "relayDID": "did:web:relay.example.com",
  "negotiated": {
    "transportVersion": "v1",
    "gossipVersion": "v1",
    "frameVersion": 1
  }
}
```

`negotiated` holds the highest version of each kind supported by both sides. If there is no common version of any kind, the Relay closes the connection. The client MUST check `relayDID` against the Relay's manifest (§10.2.1); the Relay itself is authenticated by its TLS certificate or `.onion` address (§10.3.4.7).

Text format capabilities (§5.2.7) are not declared to the Relay. A Relay that cached them per client and served them to other clients would learn identity, contrary to ARCHITECTURE S1.

### Connection Admission

A Relay rate-limits connections, subscriptions, history reads (live stream and JMAP, §11.8) and push registrations (§11.7.3) per network address and per `channelToken`. Limit values are local Relay policy. Per-address limits MUST NOT be the sole control, because many clients can share one address (Tor exits, carrier NAT).

Under load, a Relay MAY require a proof-of-work challenge before accepting a connection. It then answers the `ClientHello` with an `AdmissionChallenge` instead of a `RelayHello`:

```json
{
  "@type": "AdmissionChallenge",
  "challenge": "base64url(32 random bytes)",
  "difficulty": 20,
  "expiresIn": 30
}
```

The client computes `powNonce` such that `SHA256(challenge || powNonce)` has at least `difficulty` leading zero bits, the same construction as §10.5.2, and replies within `expiresIn` seconds:

```json
{
  "@type": "AdmissionProof",
  "challenge": "base64url...",
  "powNonce": "base64url..."
}
```

On a valid proof the Relay sends the `RelayHello`; otherwise it closes the connection. A Relay MUST accept each `challenge` at most once. A proof-of-work challenge lets a client whose address has hit its per-address limit still connect, so clients behind shared addresses are not locked out.

Privacy Pass tokens are a possible future admission extension and are not part of this version.

## 11.7 Push Notification Proxy (Optional)

Mobile clients backgrounded by the OS cannot maintain a persistent WebTransport or WebSocket connection. Agora supports an optional **Push Notification Proxy** that enables mobile wake-up notifications without exposing message content, channel identity, or sender identity to the notification infrastructure.

Push is enabled by default on mobile clients, and the push proxy's observations are within the observation budget (ARCHITECTURE §5 item 7). Users MAY disable push; a client with push disabled makes no registration. A Relay MAY designate a push proxy in its manifest (§11.7.2), and a CO MAY designate its own push proxy for its members. Clients that maintain persistent connections (desktop clients, server-side bots) do not need one.

### 11.7.1 Privacy Model

The fundamental constraint: APNs (Apple) and FCM (Google) are centralized services that require a server-side component that knows which device token to wake up. The goal is to limit what the proxy learns to the minimum necessary for its function.

**What the push proxy learns** (ARCHITECTURE §5 item 7):
- Opaque device push handles: the client's `pushHandle` (a random token, not linked to any DID or channel), its APNs or FCM device token, and its platform (`apns` or `fcm`)
- Wake-up timing: when a wake-up arrives for each `pushHandle`
- The `relayDID` that signed each wake-up request (an IO-to-IO relationship, ARCHITECTURE §5 item 8)

**What the push proxy does NOT learn:**
- The client's DID
- Which channels the client subscribes to
- Any message content
- The identity of any message sender

The `pushHandle` is the separation layer: the Relay knows `channelToken` → pushHandle and never the client's DID; the proxy knows pushHandle → device token. Neither party links a device to a DID or a channel.

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
  "pushHandle":  "base64url(32 random bytes)",
  "deviceToken": "hex or base64 APNs/FCM token",
  "platform":    "apns" | "fcm",
  "appBundleID": "com.example.agora"
}
Response: 200 { "registered": true, "ttl": 2592000 }
```

4. Registers `{ pushHandle, proxyEndpoint, channelTokens }` with their Relay. This registration carries no identity and is rate-limited per address and per `channelToken` (§11.6); the Relay keys it by `pushHandle` only:

```
POST /v1/agora/push/register
{
  "pushHandle":    "base64url...",
  "proxyEndpoint": "https://push.example.com/v1/agora/push",
  "channelTokens": ["base64url...", "..."]
}
```

**Registration renewal:** Push registrations have a TTL (default 30 days). Clients MUST renew before expiry. APNs/FCM device tokens may also change; clients MUST re-register with the proxy when they receive a new device token.

### 11.7.4 Wake-Up Flow

When a Relay receives an envelope on a `channelToken` for which a `pushHandle` is registered and that handle's client is not currently connected, the Relay:

1. Looks up the `{ pushHandle, proxyEndpoint }` registered for that `channelToken`. The Relay sends the wake-up to whichever proxy the client registered, its own or one designated by the client's CO.
2. Sends a signed wake-up request to the proxy:

```
POST https://push.example.com/v1/agora/push/wake
x-agora-relay-did: did:key:z6MkRelay...
x-agora-timestamp: 1741780800
x-agora-nonce: base64url...
signature: sig1=:base64url...:

{
  "pushHandle": "base64url...",
  "urgency":    "normal" | "high"
}
```

3. The proxy maps `pushHandle → deviceToken` and sends a zero-content push notification to APNs or FCM.

Wake-ups carry no content. Both payloads are content-free silent pushes. The OS wakes the app; the app reconnects to its Relay and receives queued messages.

To blur timing, Relays SHOULD add random jitter before sending a wake-up and SHOULD coalesce wake-ups for the same `pushHandle` that fall within the jitter window into one request.

`urgency: "high"` is used for direct messages or @mentions; `urgency: "normal"` is used for general channel traffic. Since the Relay cannot inspect sealed content to determine urgency, the sending client attaches an advisory urgency hint to the outer `RoutingEnvelope`:

```json
"pushUrgency": "high" | "normal"
```

This field is unauthenticated and advisory; Relays use it as-is.

### 11.7.5 Proxy Authentication and Rate Limiting

The push proxy MUST verify the RFC 9421 signature on all wake-up requests against the sending Relay's manifest. Wake-up requests from unknown or untrusted Relay DIDs MUST be rejected.

Proxies SHOULD rate-limit wake-up requests per `pushHandle` to prevent a rogue Relay from spamming a client device (for example: 1 push per 5 seconds per handle, with a burst allowance of 3).

### 11.7.6 Handle Rotation

A client MAY rotate its `pushHandle` at any time for privacy or after suspected handle compromise. Rotation procedure:

1. Generate a new `pushHandle`.
2. Register `{ new pushHandle, deviceToken }` with the proxy.
3. Register `{ new pushHandle, proxyEndpoint, channelTokens }` with the Relay, including the old `pushHandle` so the Relay atomically replaces it.
4. Delete the old `pushHandle` from the proxy: `DELETE /v1/agora/push/register/{pushHandle}`.

## 11.8 JMAP Management and Sync API

JMAP ([RFC 8620](https://jmap.io)) is used at two layers that run on different operators:

- **Relay sync API (IO).** Agora Relays expose a JMAP API limited to blind objects: ciphertext envelopes keyed by `channelToken`, and blobs (§11.8.1–§11.8.8). It provides history retrieval and state synchronization (state tokens, `/changes` deltas, batched method calls, ResultReferences, and EventSource push) without requiring a persistent connection. A Relay holds no `channelToken`→`channelCID` mapping and serves no Space, Channel, membership, role or invite objects (ARCHITECTURE S1, §5.3 item 4).
- **Management API (client / CO).** The Space, channel, membership, role and invite API runs in the client (a local daemon) or on CO infrastructure, never on a Relay (§11.8.9).

### 11.8.1 Endpoints

A Relay that declares the `jmap-sync-v1` capability MUST expose the following endpoints under the base URL declared in `endpoints.jmapSync` in its manifest. Paths are relative to that base; with the base `https://relay.example.com/v1/agora/jmap`, the Session object is at `https://relay.example.com/v1/agora/jmap/.well-known/jmap`.

```
GET  {base}/.well-known/jmap                      Session object (unauthenticated)
POST {base}/api                                   JMAP request/response
GET  {base}/events                                EventSource push stream
POST {base}/upload/{accountId}                    Blob upload
GET  {base}/download/{accountId}/{blobId}/{name}  Blob download
```

Clients locate the Session object from `endpoints.jmapSync`, not by RFC 8620 autodiscovery at the origin's `/.well-known/jmap`.

### 11.8.2 Authentication

Relays never authenticate client identity on JMAP requests (§11.6). Envelope history is addressed by `channelToken`; envelopes written through the sync API carry the same epoch access proof as on the live stream (ARCHITECTURE §6.2). Requests are rate-limited per network address and per `channelToken` (§11.6).

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

A single MLS-encrypted envelope as stored by the Relay. The name `Envelope` avoids a collision with the `Message` type of the JMAP Chat specification (draft-atwood-jmap-chat-00). **The `encryptedPayload` field is always MLS ciphertext; the Relay cannot read it.** Clients decrypt using their local MLS group state.

```
id              String     ULID (time-sortable, server-assigned)
channelToken    String     Routing token under which the envelope was published
encryptedPayload String    base64url: MLS ciphertext (ApplicationMessage or Proposal/Commit)
mlsEpoch        UInt       MLS epoch in which the envelope was encrypted
seqNo           UInt       Sequence number within the epoch (for client-side ordering)
receivedAt      UTCDate    Relay's clock; authoritative for stable sort order
expiresAt       UTCDate|null  null = no configured expiry
```

### 11.8.5 Methods

All methods follow RFC 8620 conventions. `/get`, `/set`, `/changes`, and `/query` have their standard semantics. Methods marked **read-only** have no `/set`.

| Method | Notes |
|---|---|
| `Envelope/get` | Fetch by ids. Returns encrypted blobs. |
| `Envelope/changes` | State-token delta. Returns added/updated/destroyed ids since a given state. |
| `Envelope/query` | Filter by `channelToken`; sort by `receivedAt` (default) or `seqNo`. |
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

- **Envelope content.** `Envelope/encryptedPayload` is always MLS ciphertext. The Relay stores and serves it without decrypting. A subpoena against the Relay yields only ciphertext.
- **Channel identity.** The Relay keys envelopes by `channelToken` only. It holds no `channelToken`→`channelCID` mapping; that mapping exists only in the management API (§11.8.9).
- **Sender identity.** No sender identity appears in any JMAP object. `encryptedPayload` contains a sealed MLS ApplicationMessage; the sender is sealed inside the ciphertext.
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
| New message delivery | ✗ | ✓ |
| MLS handshake (Commit / Proposal / Welcome) | ✗ | ✓ |
| Presence and typing indicators | ✗ | ✓ |
| Push notification registration | ✗ | ✓ |

### 11.8.9 Management API (Client / CO)

*Binds: CO and clients.*

The Space, channel, membership, role and invite management API is the JMAP Chat specification family (draft-atwood-jmap-chat-00, capability `urn:ietf:params:jmap:chat`, and its companion drafts), as profiled and carried by Agora per §14. This specification does not restate it.

The management API runs in the client (a local daemon serving the user's own devices) or on CO infrastructure. A Relay MUST NOT serve it. Its state is derived from CO-signed Space state (ARCHITECTURE S4) and decrypted MLS application messages, and it is the only place a `channelCID` is mapped to a `channelToken`. Clients use it to resolve a channel to its current `channelToken`, then use the Relay sync API (§11.8.1–§11.8.8) and the live stream to move ciphertext under that token.

---
