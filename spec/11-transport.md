# 11. Transport

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1832–2356 (§8).


*Binds: both.* (§11.1–§11.7 and the relay sync API in §11.8 bind IO; the management API in §11.8.9 binds clients and CO.)

Agora uses two complementary transport surfaces that serve different access patterns:

**Live stream** (§11.1–§11.7) — WebTransport (QUIC) or WebSocket. Optimized for real-time delivery: new message events, MLS handshake messages (Commits, Proposals, Welcomes), presence, and typing indicators. Required for any client that needs low-latency delivery.

**JMAP Sync API** (§11.8) — Standard HTTPS request/response with EventSource push, served by Relays. Optimized for token-keyed envelope history retrieval and state sync. Clients that need only history (bots, compliance tools, search indexers) can use JMAP without opening a live stream connection. The Space, membership, role and invite management API is not served by Relays; it runs in the client or on CO infrastructure (§11.8.9).

A full-featured client uses both. The live stream delivers new events; JMAP fills history on startup and provides a clean sync model for catching up after a disconnect.

## 11.1 Primary Transport: WebTransport

Clients connect to Relays via **WebTransport** (IETF RFC 9000 / HTTP/3 over QUIC). WebTransport provides:

- Multiplexed bidirectional streams over a single QUIC connection
- Reliable ordered streams for MLS handshake messages and persistent message delivery
- Unreliable datagrams for presence and typing events (low-latency, loss-tolerant)

Endpoint: `https://<relay-host>/v1/agora/wt`

WebTransport requires QUIC, which runs over UDP. It is unavailable in any environment that proxies only TCP — including Tor (see §11.3).

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

**Hidden service Relays.** A Relay operating as a Tor v3 hidden service publishes its `.onion` address in its `RelayAd.relayHints`. Clients with Tor available SHOULD prefer `.onion` endpoints when available — they provide end-to-end Tor routing without depending on an exit node.

## 11.4 Frame Format

All frames are CBOR-encoded (compact binary), with a JSON-LD-compatible schema. Clients MAY use JSON encoding for debugging purposes; Relays MUST accept both JSON and CBOR.

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

## 11.6 Client-Relay Authentication

The connection handshake authenticates the Relay to the client and negotiates protocol versions. It does **not** authenticate the client's DID for message routing. Access to publish envelopes and submit MLS operations is granted by the epoch access proof carried on each envelope (ARCHITECTURE §6.2), which shows that the sender is a current member without revealing which member. A Relay MUST NOT require DID authentication to publish, subscribe, fetch history or submit MLS operations, and MUST NOT keep DID ban lists; bans are MLS Removes (ARCHITECTURE §6.2).

> **Open (agora-pozi.9):** how a Relay meters admission and quota before a client has proven membership in any channel, without authenticating its DID.

DID challenge-response (Steps 3–4 below) is used only for KeyPackage Store ownership (§5.2.1.1): a client uploading or deleting its own KeyPackages proves control of the DID. Clients that do not write to the KeyPackage Store omit `did` and `deviceKey` from `ClientHello` and skip Steps 3–4.

> **Open (agora-pozi.10):** whether a KeyPackage Store is IO-hosted at all, and therefore whether a Relay ever performs DID challenge-response.

### Handshake Protocol

Authentication is initiated by the client immediately after transport connection. It uses a `0x04` Control frame.

**Step 1 — Client Hello**

The client sends a `ClientHello` control frame requesting a challenge, optionally declaring its DID for KeyPackage Store access:

```json
{
  "@type": "ClientHello",
  "did": "did:key:z6Mk...",
  "deviceKey": "base64url(Ed25519 pubkey)",
  "clientVersion": "agora/v1",
  "supportedTransportVersions": ["v1"],
  "supportedGossipVersions": ["v1"],
  "supportedFrameVersions": [1],
  "ts": "2026-03-12T12:00:00.000Z"
}
```

`did` and `deviceKey` are OPTIONAL and are present only when the client intends to write to the KeyPackage Store. When present, `deviceKey` is the device's Ed25519 public key, which MUST match a verification method listed in the DID document for the declared DID.

Text format capabilities (§5.2.7) are not declared to the Relay. A Relay that cached them per DID and served them to other clients would learn identity, contrary to ARCHITECTURE S1.

**Step 2 — Relay Challenge**

The Relay responds with a `RelayChallenge`:

```json
{
  "@type": "RelayChallenge",
  "nonce": "base64url(32 random bytes)",
  "relayDID": "did:key:z6MkRelay...",
  "relaySig": "base64url...",
  "ts": "2026-03-12T12:00:00.000Z",
  "expiresIn": 30,
  "negotiated": {
    "transportVersion": "v1",
    "gossipVersion": "v1",
    "frameVersion": 1
  }
}
```

`relaySig` is the Relay's Ed25519 signature over `nonce || relayDID || ts`. This simultaneously authenticates the Relay to the client. `expiresIn` is in seconds; the client must respond within this window.

**Step 3 — Client Response** (KeyPackage Store access only)

```json
{
  "@type": "ClientAuth",
  "did": "did:key:z6Mk...",
  "nonce": "base64url...",
  "sig": "base64url..."
}
```

`sig` is the client's Ed25519 signature over `nonce || clientDID || relayDID || ts` using the `deviceKey` declared in `ClientHello`. The Relay verifies:

1. `sig` is a valid signature by the declared `deviceKey`
2. `deviceKey` is listed as an active verification method in the DID document for `did`
3. `nonce` matches the issued challenge and has not expired

**Step 4 — Session Token** (KeyPackage Store access only)

On successful verification, the Relay issues a `SessionToken`:

```json
{
  "@type": "SessionToken",
  "token": "base64url(32 random bytes)",
  "did": "did:key:z6Mk...",
  "expiresAt": "2026-03-12T20:00:00.000Z",
  "relaySig": "base64url..."
}
```

The token is included as a frame header field in all subsequent KeyPackage Store write operations on this connection. It expires after 8 hours or on disconnection, whichever comes first. Clients reconnecting after expiry repeat the full handshake.

### Connections Without DID Authentication

A connection that does not perform Steps 3–4 MAY:
- Subscribe to gossip topics
- Fetch public space state and history
- Receive messages on subscribed topics
- Publish envelopes and submit MLS operations that carry a valid epoch access proof (ARCHITECTURE §6.2)

It MUST NOT:
- Upload KeyPackages
- Access KeyPackage Store write endpoints

### DID Document Freshness

This subsection applies only to Relays that operate a KeyPackage Store. The Relay caches DID documents to avoid resolving them on every connection. Cached DID documents have a TTL of 1 hour. Clients revoking a device key SHOULD notify their connected Relays via a signed `DeviceRevocation` control frame to accelerate cache invalidation:

```json
{
  "@type": "DeviceRevocation",
  "did": "did:key:z6Mk...",
  "revokedKey": "base64url(Ed25519 pubkey)",
  "sig": "base64url..."
}
```

`sig` is signed by any remaining valid device key for the same DID. Relays MUST process `DeviceRevocation` frames immediately and invalidate any active sessions using the revoked key.

## 11.7 Push Notification Proxy (Optional)

Mobile clients backgrounded by the OS cannot maintain a persistent WebTransport or WebSocket connection. Agora supports an optional **Push Notification Proxy** that enables mobile wake-up notifications without exposing message content, channel identity, or sender identity to the notification infrastructure.

Push proxies are entirely optional. Relays MAY designate one; clients MAY register with one. Clients that maintain persistent connections (desktop clients, server-side bots) do not need them.

### 11.7.1 Privacy Model

The fundamental constraint: APNs (Apple) and FCM (Google) are centralized services that require a server-side component that knows which device token to wake up. The goal is to limit what the proxy learns to the minimum necessary for its function.

**What the push proxy learns** (ARCHITECTURE §5 item 6):
- Opaque device push handles: the client's `pushHandle` (a random token, not linked to any DID or channel), its APNs or FCM device token, and its platform (`apns` or `fcm`)
- Wake-up timing: when a wake-up arrives for each `pushHandle`
- The `relayDID` that signed each wake-up request (an IO-to-IO relationship, ARCHITECTURE §5 item 7)

**What the push proxy does NOT learn:**
- The client's DID
- Which channels the client subscribes to
- Any message content
- The identity of any message sender

> **Open (agora-pozi.11):** whether per-handle wake-up timing is acceptable by default or must be an opt-in budget extension.

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

4. Registers `{ pushHandle, proxyEndpoint, channelTokens }` with their Relay. This registration is not DID-authenticated (§11.6); the Relay keys it by `pushHandle` only:

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

1. Looks up the `{ pushHandle, proxyEndpoint }` registered for that `channelToken`.
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

Both payloads are content-free silent pushes. The OS wakes the app; the app reconnects to its Relay and receives queued messages.

`urgency: "high"` is used for direct messages or @mentions; `urgency: "normal"` is used for general channel traffic. Since the Relay cannot inspect sealed content to determine urgency, the sending client attaches an advisory urgency hint to the outer `RoutingEnvelope`:

```json
"pushUrgency": "high" | "normal"
```

This field is unauthenticated and advisory — Relays use it as-is.

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

- **Relay sync API (IO).** Agora Relays expose a JMAP API limited to blind objects: ciphertext envelopes keyed by `channelToken`, KeyPackages, and blobs (§11.8.1–§11.8.8). It provides history retrieval and state synchronization — state tokens, `/changes` deltas, batched method calls, ResultReferences, and EventSource push — without requiring a persistent connection. A Relay holds no `channelToken`→`channelCID` mapping and serves no Space, Channel, membership, role or invite objects (ARCHITECTURE S1, §5.3 item 4).
- **Management API (client / CO).** The Space, channel, membership, role and invite API runs in the client (a local daemon) or on CO infrastructure, never on a Relay (§11.8.9).

### 11.8.1 Endpoints

A Relay that declares the `jmap-sync-v1` capability MUST expose the following endpoints under the base URL declared in `endpoints.jmapSync` in its manifest:

```
GET  /.well-known/jmap                           Session object (unauthenticated)
POST /jmap/api                                   JMAP request/response
GET  /jmap/events                                EventSource push stream
POST /jmap/upload/{accountId}                    Blob upload
GET  /jmap/download/{accountId}/{blobId}/{name}  Blob download
```

### 11.8.2 Authentication

Relay JMAP requests MUST NOT require DID authentication (§11.6). Envelope history is addressed by `channelToken`; envelopes written through the sync API carry the same epoch access proof as on the live stream (ARCHITECTURE §6.2). `KeyPackage/set` is the only method that requires proof of DID ownership.

> **Open (agora-pozi.9):** how a Relay meters JMAP request admission and quota without identity.

> **Open (agora-pozi.10):** whether `KeyPackage/*` belongs on the Relay at all, and how a KeyPackage owner proves DID control over HTTP.

### 11.8.3 Capability and Session Object

**Capability URI:** `urn:agora:v1`

Every JMAP request MUST include `"urn:ietf:params:jmap:core"` and `"urn:agora:v1"` in the `using` array.

The Session object returned by `GET /.well-known/jmap`:

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
      "maxMessageBodyBytes": 65536,
      "maxAttachmentBytes": 104857600,
      "supportedBodyTypes": ["text/plain", "text/markdown;variant=commonmark"]
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
  "apiUrl": "https://relay.example.com/jmap/api",
  "downloadUrl": "https://relay.example.com/jmap/download/{accountId}/{blobId}/{name}?accept={type}",
  "uploadUrl": "https://relay.example.com/jmap/upload/{accountId}",
  "eventSourceUrl": "https://relay.example.com/jmap/events?types={types}&closeafter={closeafter}&ping={ping}",
  "state": "s-1"
}
```

### 11.8.4 Object Types

#### Message

A single MLS-encrypted message blob as stored by the Relay. **The `encryptedPayload` field is always MLS ciphertext — the Relay cannot read it.** Clients decrypt using their local MLS group state.

```
id              String     ULID (time-sortable, server-assigned)
channelToken    String     Routing token under which the envelope was published
encryptedPayload String    base64url — MLS ciphertext (ApplicationMessage or Proposal/Commit)
mlsEpoch        UInt       MLS epoch in which the message was encrypted
seqNo           UInt       Sequence number within the epoch (for client-side ordering)
receivedAt      UTCDate    Relay's clock — authoritative for stable sort order
expiresAt       UTCDate|null  null = no configured expiry
```

#### KeyPackage

An MLS KeyPackage held in the Relay's KeyPackage Store (§5.2.1.1). Exposed here for CRUD access without using the low-level REST endpoint directly. The same atomic-consumption semantics apply: `KeyPackage/get` with `consume: true` atomically removes the package from the store.

```
id              String     Server-assigned opaque id
ownerDID        String     DID of the user who uploaded this package
packageData     String     base64url — raw MLS KeyPackage bytes
createdAt       UTCDate
expiresAt       UTCDate|null
```

### 11.8.5 Methods

All methods follow RFC 8620 conventions. `/get`, `/set`, `/changes`, and `/query` have their standard semantics. Methods marked **read-only** have no `/set`.

| Method | Notes |
|---|---|
| `Message/get` | Fetch by ids. Returns encrypted blobs. |
| `Message/changes` | State-token delta. Returns added/updated/destroyed ids since a given state. |
| `Message/query` | Filter by `channelToken`; sort by `receivedAt` (default) or `seqNo`. |
| `Message/queryChanges` | RFC 8620 extended query-delta. |
| `KeyPackage/get` | Fetch by ids. Pass `"consume": true` in args to atomically consume (same guarantee as REST `GET /v1/agora/kp/{did}`). |
| `KeyPackage/set` | Upload new packages (`create`); destroy expired ones. `ownerDID` must match the DID whose ownership the client proved (§11.8.2). |
| `KeyPackage/changes` | Delta for the proven owner's own packages. |

**Batching and ResultReferences.** Standard RFC 8620 §4 batching applies. Multiple method calls in a single request execute in order; `#`-prefixed argument keys reference results of prior calls via RFC 6901 JSON Pointers.

Example — query a channel token's envelopes then fetch them in one round-trip:

```json
{
  "using": ["urn:ietf:params:jmap:core", "urn:agora:v1"],
  "methodCalls": [
    ["Message/query", {
      "accountId": "a-relay",
      "filter": {"channelToken": "base64url..."}
    }, "0"],
    ["Message/get", {
      "accountId": "a-relay",
      "#ids": {
        "resultOf": "0",
        "name": "Message/query",
        "path": "/ids"
      }
    }, "1"]
  ]
}
```

### 11.8.6 Relay Blindness Preservation

The Relay's blindness properties (§10.4.1) are fully preserved under the JMAP API:

- **Message content.** `Message/encryptedPayload` is always MLS ciphertext. The Relay stores and serves it without decrypting. A subpoena against the Relay yields only ciphertext.
- **Channel identity.** The Relay keys envelopes by `channelToken` only. It holds no `channelToken`→`channelCID` mapping; that mapping exists only in the management API (§11.8.9).
- **Sender identity.** No sender identity appears in any JMAP object. `encryptedPayload` contains a sealed MLS ApplicationMessage; the sender is sealed inside the ciphertext.
- **Community structure.** The Relay serves no Space, Channel, membership, role or invite objects and no member counts.

### 11.8.7 EventSource Push

The Relay emits `StateChange` events on the EventSource stream when any tracked object type's state advances. Clients use these as a trigger to call the corresponding `/changes` method — they do not carry content.

```
event: state
data: {"changed": {"a-relay": {"Message": "s-43", "KeyPackage": "s-7"}}}
```

Only object types whose state has changed are included in a given event. The live stream (§11.1–§11.2) provides lower-latency delivery for new messages; EventSource is the appropriate trigger for history-sync clients and background processes that do not maintain a live stream connection.

### 11.8.8 Scope: JMAP vs Live Stream

| Operation | JMAP (§11.8) | Live Stream (§11.1–§11.7) |
|---|---|---|
| History retrieval and sync | ✓ | — |
| Space / channel / membership / role / invite management | — (client / CO only, §11.8.9) | — |
| KeyPackage CRUD | ✓ | ✓ (also REST endpoint) |
| Programmatic / bot access | ✓ | — |
| Blob upload / download | ✓ | — |
| New message delivery | — | ✓ |
| MLS handshake (Commit / Proposal / Welcome) | — | ✓ |
| Presence and typing indicators | — | ✓ |
| Push notification registration | — | ✓ |
| DID auth handshake (KeyPackage Store only) | See §11.8.2 | ✓ (control frame) |

### 11.8.9 Management API (Client / CO)

*Binds: CO and clients.*

The Space, channel, membership, role and invite management API is the JMAP Chat specification (draft) (`draft-atwood-jmap-chat-00`, capability `urn:ietf:params:jmap:chat`). This specification does not restate it.

The management API runs in the client (a local daemon serving the user's own devices) or on CO infrastructure. A Relay MUST NOT serve it. Its state is derived from CO-signed Space state (ARCHITECTURE S4) and decrypted MLS application messages, and it is the only place a `channelCID` is mapped to a `channelToken`. Clients use it to resolve a channel to its current `channelToken`, then use the Relay sync API (§11.8.1–§11.8.8) and the live stream to move ciphertext under that token.

---
