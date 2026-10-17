# Agora Protocol: Transport

> Binds: IO. Verbatim from `import/agora-protocol-spec-unified.md` lines 1832–2356 (§8). Section numbers are the source's and will be renumbered.

## 8. Transport

Agora uses two complementary transport surfaces that serve different access patterns:

**Live stream** (§8.1–§8.7) — WebTransport (QUIC) or WebSocket. Optimized for real-time delivery: new message events, MLS handshake messages (Commits, Proposals, Welcomes), presence, and typing indicators. Required for any client that needs low-latency delivery.

**JMAP Management API** (§8.8) — Standard HTTPS request/response with EventSource push. Optimized for history retrieval, state sync, programmatic access, and search. Clients that need only history (bots, compliance tools, search indexers) can use JMAP without opening a live stream connection.

A full-featured client uses both. The live stream delivers new events; JMAP fills history on startup and provides a clean sync model for catching up after a disconnect.

### 8.1 Primary Transport: WebTransport

Clients connect to Relays via **WebTransport** (IETF RFC 9000 / HTTP/3 over QUIC). WebTransport provides:

- Multiplexed bidirectional streams over a single QUIC connection
- Reliable ordered streams for MLS handshake messages and persistent message delivery
- Unreliable datagrams for presence and typing events (low-latency, loss-tolerant)

Endpoint: `https://<relay-host>/v1/agora/wt`

WebTransport requires QUIC, which runs over UDP. It is unavailable in any environment that proxies only TCP — including Tor (see §8.3).

**Reference implementations for WebTransport:** Native browser support in Chromium-based browsers and Firefox 114+. Server-side: [`webtransport-go`](https://github.com/marten-seemann/webtransport-go), [`wtransport`](https://github.com/BiagioFesta/wtransport) (Rust).

### 8.2 Fallback Transport: WebSocket

For environments where QUIC or HTTP/3 is blocked or unavailable:

Endpoint: `wss://<relay-host>/v1/agora/ws`

WebSocket carries the same message framing over a single multiplexed binary stream. Multiplexing is handled by a lightweight channel ID prefix on each frame. WebSocket is the mandatory transport for Tor-connected clients.

### 8.3 Tor Transport Constraints

Tor proxies TCP only. This has the following protocol-level consequences:

**WebTransport unavailable.** Clients connecting via Tor MUST use WebSocket. Clients MUST NOT attempt WebTransport when operating through a SOCKS5 proxy identifiable as Tor. Clients SHOULD detect transport failure and fall back to WebSocket without requiring user intervention.

**VTC severely degraded.** WebRTC ICE relies on UDP for STUN hole-punching and optimal media transport. Over Tor, UDP is unavailable. The only viable VTC path over Tor is TURN-over-TCP through a TURN server reachable via a `.onion` address or a Tor-friendly clearnet endpoint. Media latency over Tor circuits (typically 200–600ms round-trip) renders real-time audio/video unusable for most participants. Clients SHOULD display a warning when VTC is attempted over Tor, and MAY disable VTC participation entirely in Tor-only mode.

**Gossipsub fingerprinting.** Connecting to gossipsub via Tor provides IP-level anonymity but gossipsub peer scoring observes message timing and topic subscription patterns. A sufficiently persistent observer correlating topic subscription events across Tor circuits may be able to fingerprint clients by behavior. Clients requiring strong anonymity SHOULD rotate Tor circuits periodically and SHOULD subscribe to decoy topics (§13.4).

**Rate limiting.** A Relay receiving connections from Tor exit nodes sees the exit node's IP address, not the client's IP. Relays MUST use per-`channelToken` rate limits and PoW/payment requirements as the primary spam control mechanism. Per-IP limits MUST NOT be the sole mechanism.

**Hidden service Relays.** A Relay operating as a Tor v3 hidden service publishes its `.onion` address in its `RelayAd.relayHints`. Clients with Tor available SHOULD prefer `.onion` endpoints when available — they provide end-to-end Tor routing without depending on an exit node.

### 8.4 Frame Format

All frames are CBOR-encoded (compact binary), with a JSON-LD-compatible schema. Clients MAY use JSON encoding for debugging purposes; Relays MUST accept both JSON and CBOR.

Frame structure:

```
[version: u8, type: u8, topic: string, payload: bytes]
```

`version` values: `0x01` = frame format v1 (this specification). A Relay that receives a frame with an unknown `version` byte MUST discard it and MAY close the connection.

`type` values: `0x01` Gossip, `0x02` MLS, `0x03` Ephemeral, `0x04` Control.

**Reference implementations for CBOR:** [`cbor2`](https://pypi.org/project/cbor2/) (Python), [`cbor` crate](https://crates.io/crates/cbor) (Rust), [`cbor-js`](https://github.com/paroga/cbor-js) (JS), [`fxamacker/cbor`](https://github.com/fxamacker/cbor) (Go).

### 8.5 Direct Peer Connections

Clients MAY establish direct WebRTC data channels to each other, bypassing Relays entirely. The `VoiceSignal` mechanism (§10.4) is used for ICE negotiation. Direct peer connections are mandatory for voice and video (media MUST NOT transit Relays) and optional for text messaging (latency optimization).

On WireGuard-based overlays (Tailscale, Headscale), direct peer connections benefit from overlay-managed NAT traversal. Overlay-internal `100.x.x.x` addresses appear as ICE host candidates and are preferred over STUN-discovered public addresses when both peers are on the same overlay network.

### 8.6 Client-Relay Authentication

A Relay needs to know which DID it is talking to for three purposes: ban enforcement (reject connections from banned DIDs), per-DID rate limiting, and KeyPackage Store ownership (§6.1.1). Authentication is performed once per connection via a signed challenge-response handshake that establishes a session token for the lifetime of the connection.

Authentication is **optional for read-only operations** (fetching space state, reading history, subscribing to gossip topics). It is **required for write operations** (publishing messages, uploading KeyPackages, submitting MLS Commits) and for accessing the KeyPackage Store write API.

#### Handshake Protocol

Authentication is initiated by the client immediately after transport connection. It uses a `0x04` Control frame.

**Step 1 — Client Hello**

The client sends a `ClientHello` control frame declaring its DID and requesting a challenge:

```json
{
  "@type": "ClientHello",
  "did": "did:key:z6Mk...",
  "deviceKey": "base64url(Ed25519 pubkey)",
  "clientVersion": "agora/0.1",
  "supportedTransportVersions": ["v1"],
  "supportedGossipVersions": ["v1"],
  "supportedFrameVersions": [1],
  "supportedTextFormats": ["text/markdown;variant=commonmark", "text/markdown;variant=gfm", "text/plain"],
  "ts": "2026-03-12T12:00:00.000Z"
}
```

`deviceKey` is the device's Ed25519 public key, which MUST match a verification method listed in the DID document for the declared DID.

`supportedTextFormats` is an optional array of `TextBody` format strings (§6.7) that this client can render. If absent, the client is assumed to support only `text/markdown;variant=commonmark` and `text/plain`. The Relay does not use this field internally — it is included so that the Relay can make it available to other connected clients composing messages to this DID (see §6.7.4). Clients SHOULD include this field on every connection.

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

**Step 3 — Client Response**

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
4. The DID is not in the Relay's ban list for any space the Relay serves

**Step 4 — Session Token**

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

The token is included as a frame header field in all subsequent write operations on this connection. It expires after 8 hours or on disconnection, whichever comes first. Clients reconnecting after expiry repeat the full handshake.

#### Anonymous Connections

A client that does not perform the authentication handshake is treated as anonymous. Anonymous connections MAY:
- Subscribe to public gossip topics
- Fetch public space state and history
- Receive messages on subscribed topics

Anonymous connections MUST NOT:
- Publish messages to any topic
- Upload KeyPackages
- Submit MLS operations
- Access KeyPackage Store write endpoints

#### DID Document Freshness

The Relay caches DID documents to avoid resolving them on every connection. Cached DID documents have a TTL of 1 hour. Clients revoking a device key SHOULD notify their connected Relays via a signed `DeviceRevocation` control frame to accelerate cache invalidation:

```json
{
  "@type": "DeviceRevocation",
  "did": "did:key:z6Mk...",
  "revokedKey": "base64url(Ed25519 pubkey)",
  "sig": "base64url..."
}
```

`sig` is signed by any remaining valid device key for the same DID. Relays MUST process `DeviceRevocation` frames immediately and invalidate any active sessions using the revoked key.

### 8.7 Push Notification Proxy (Optional)

Mobile clients backgrounded by the OS cannot maintain a persistent WebTransport or WebSocket connection. Agora supports an optional **Push Notification Proxy** that enables mobile wake-up notifications without exposing message content, channel identity, or sender identity to the notification infrastructure.

Push proxies are entirely optional. Relays MAY designate one; clients MAY register with one. Clients that maintain persistent connections (desktop clients, server-side bots) do not need them.

#### 8.7.1 Privacy Model

The fundamental constraint: APNs (Apple) and FCM (Google) are centralized services that require a server-side component that knows which device token to wake up. The goal is to limit what the proxy learns to the minimum necessary for its function.

**What the push proxy learns:**
- A client's opaque `pushHandle` (a random token, not linked to any DID or channel)
- The client's APNs or FCM device token (required to send the push)
- The client's platform (`apns` or `fcm`)
- That *some* Relay sent a wake-up for that `pushHandle` at *some* time

**What the push proxy does NOT learn:**
- The client's DID
- Which Relay the client uses
- Which channels the client subscribes to
- Any message content
- The identity of any message sender

The `pushHandle` is the separation layer: the Relay knows DID → pushHandle; the proxy knows pushHandle → device token. Neither party has both mappings.

#### 8.7.2 Relay Manifest Extension

A Relay that supports push proxy wake-up declares its associated push proxy in the Relay Manifest:

```json
"pushProxy": {
  "endpoint": "https://push.example.com/v1/agora/push",
  "proxyDID": "did:key:z6MkProxy...",
  "platforms": ["apns", "fcm"],
  "registrationEndpoint": "https://push.example.com/v1/agora/push/register"
}
```

#### 8.7.3 Client Registration

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

4. Registers `{ pushHandle, proxyEndpoint }` with their Relay, authenticated via the session token from §8.6:

```
POST /v1/agora/push/register
{
  "pushHandle":    "base64url...",
  "proxyEndpoint": "https://push.example.com/v1/agora/push"
}
```

**Registration renewal:** Push registrations have a TTL (default 30 days). Clients MUST renew before expiry. APNs/FCM device tokens may also change; clients MUST re-register with the proxy when they receive a new device token.

#### 8.7.4 Wake-Up Flow

When a Relay receives a message for a channel and the intended recipient client is not currently connected, the Relay:

1. Looks up the client's `{ pushHandle, proxyEndpoint }` from its registration store.
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

Both payloads are content-free silent pushes. The OS wakes the app; the app reconnects to its Relay and receives queued messages over the authenticated session.

`urgency: "high"` is used for direct messages or @mentions; `urgency: "normal"` is used for general channel traffic. Since the Relay cannot inspect sealed content to determine urgency, the sending client attaches an advisory urgency hint to the outer `RoutingEnvelope`:

```json
"pushUrgency": "high" | "normal"
```

This field is unauthenticated and advisory — Relays use it as-is.

#### 8.7.5 Proxy Authentication and Rate Limiting

The push proxy MUST verify the RFC 9421 signature on all wake-up requests against the sending Relay's manifest. Wake-up requests from unknown or untrusted Relay DIDs MUST be rejected.

Proxies SHOULD rate-limit wake-up requests per `pushHandle` to prevent a rogue Relay from spamming a client device (for example: 1 push per 5 seconds per handle, with a burst allowance of 3).

#### 8.7.6 Handle Rotation

A client MAY rotate its `pushHandle` at any time for privacy or after suspected handle compromise. Rotation procedure:

1. Generate a new `pushHandle`.
2. Register `{ new pushHandle, deviceToken }` with the proxy.
3. Register `{ new pushHandle, proxyEndpoint }` with the Relay (relay atomically replaces old handle).
4. Delete the old `pushHandle` from the proxy: `DELETE /v1/agora/push/register/{pushHandle}`.

### 8.8 JMAP Management and Sync API

Agora Relays expose a [JMAP](https://jmap.io) (RFC 8620) API for history retrieval, state synchronization, and programmatic access. JMAP provides a proven sync model — state tokens, `/changes` deltas, batched method calls, ResultReferences, and EventSource push — without requiring a persistent connection.

#### 8.8.1 Endpoints

A Relay that declares the `jmap-v1` capability MUST expose the following endpoints under the base URL declared in `endpoints.jmap` in its manifest:

```
GET  /.well-known/jmap                           Session object (unauthenticated)
POST /jmap/api                                   JMAP request/response
GET  /jmap/events                                EventSource push stream (authenticated)
POST /jmap/upload/{accountId}                    Blob upload (authenticated)
GET  /jmap/download/{accountId}/{blobId}/{name}  Blob download (authenticated)
POST /jmap/auth                                  Obtain a bearer token (see §8.8.2)
```

#### 8.8.2 Authentication

JMAP requests are authenticated with a **bearer token** obtained via the same DID challenge-response mechanism as the live stream (§8.6), adapted for HTTP:

**Step 1 — POST /jmap/auth** with a `ClientHello` JSON body (identical structure to §8.6).

**Step 2** — The Relay responds with a `RelayChallenge` JSON body.

**Step 3 — POST /jmap/auth** with a `ClientAuth` body (DID signature over the challenge nonce).

**Step 4** — The Relay responds with:
```json
{
  "token": "base64url(32 random bytes)",
  "expiresAt": "2026-04-22T13:00:00Z",
  "accountId": "a-self"
}
```

The token TTL is 24 hours. Clients MUST present it on all subsequent JMAP requests as `Authorization: Bearer <token>`. Token refresh follows the same three-step flow.

Clients that already have an authenticated live stream connection MAY request a JMAP token via a `JmapTokenRequest` control frame (§8.6) to avoid a second round-trip.

**Pay-per-use access via x402.** Relay HTTP endpoints — JMAP, blob download, KeyPackage store, and the Peer API — MAY additionally support the x402 protocol for pay-per-use access without prior DID authentication. Under x402, an unauthenticated request to a gated endpoint returns HTTP 402 with an `X-Payment-Required` header describing the accepted rails and amount. The client pays via any accepted rail and retries with an `X-Payment` proof header. The relay validates the proof and responds with the resource, optionally including a signed bearer token valid for a session or further request quota. x402 access is appropriate for autonomous agents, API integrations, and clients that need programmatic access to relay services without a persistent authenticated session. See also §12.1.

#### 8.8.3 Capability and Session Object

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
    "a-self": {
      "name": "did:key:z6Mk...",
      "isPersonal": true,
      "isReadOnly": false,
      "accountCapabilities": { "urn:agora:v1": {} }
    }
  },
  "primaryAccounts": { "urn:agora:v1": "a-self" },
  "username": "did:key:z6Mk...",
  "apiUrl": "https://relay.example.com/jmap/api",
  "downloadUrl": "https://relay.example.com/jmap/download/{accountId}/{blobId}/{name}?accept={type}",
  "uploadUrl": "https://relay.example.com/jmap/upload/{accountId}",
  "eventSourceUrl": "https://relay.example.com/jmap/events?types={types}&closeafter={closeafter}&ping={ping}",
  "state": "s-1"
}
```

#### 8.8.4 Object Types

##### Message

A single MLS-encrypted message blob as stored by the Relay. **The `encryptedPayload` field is always MLS ciphertext — the Relay cannot read it.** Clients decrypt using their local MLS group state.

```
id              String     ULID (time-sortable, server-assigned)
channelCid      String     Permanent channel identity (IPFS CID)
encryptedPayload String    base64url — MLS ciphertext (ApplicationMessage or Proposal/Commit)
mlsEpoch        UInt       MLS epoch in which the message was encrypted
seqNo           UInt       Sequence number within the epoch (for client-side ordering)
receivedAt      UTCDate    Relay's clock — authoritative for stable sort order
expiresAt       UTCDate|null  null = no configured expiry
```

##### Channel

A space channel as known to the Relay. Channel metadata is derived from the public (unencrypted) space state document (§3.3).

```
id              String     Channel CID (permanent identity)
spaceCid        String     Parent space CID
name            String     Display name from space state
topic           String|null
type            String     "text" | "voice" | "dm"
mode            String     "interactive" | "community" | "broadcast" (§3.2)
channelToken    String     Current gossipsub routing token — use this to subscribe on the live stream
speakerCap      UInt|null  Community channels only: maximum simultaneous MLS group members
idleEvictDays   UInt|null  Community channels only: idle eviction threshold in days
createdAt       UTCDate
lastMessageAt   UTCDate|null
```

##### Space

A space as known to the Relay, derived from the public space state document.

```
id              String     Space CID (permanent identity)
name            String
description     String|null
iconCid         String|null  IPFS CID of space icon blob
channelIds      String[]   Channel ids (ordered by space state)
memberCount     UInt
createdAt       UTCDate
```

##### KeyPackage

An MLS KeyPackage held in the Relay's KeyPackage Store (§6.1.1). Exposed here for CRUD access without using the low-level REST endpoint directly. The same atomic-consumption semantics apply: `KeyPackage/get` with `consume: true` atomically removes the package from the store.

```
id              String     Server-assigned opaque id
ownerDid        String     DID of the user who uploaded this package
packageData     String     base64url — raw MLS KeyPackage bytes
createdAt       UTCDate
expiresAt       UTCDate|null
```

#### 8.8.5 Methods

All methods follow RFC 8620 conventions. `/get`, `/set`, `/changes`, and `/query` have their standard semantics. Methods marked **read-only** have no `/set`.

| Method | Notes |
|---|---|
| `Message/get` | Fetch by ids. Returns encrypted blobs. |
| `Message/changes` | State-token delta. Returns added/updated/destroyed ids since a given state. |
| `Message/query` | Filter by `channelCid`; sort by `receivedAt` (default) or `seqNo`. |
| `Message/queryChanges` | RFC 8620 extended query-delta. |
| `Channel/get` | Fetch by ids. |
| `Channel/changes` | Delta since state token. |
| `Channel/query` | Filter by `spaceCid`; sort by name or `createdAt`. |
| `Space/get` | Fetch by ids. |
| `Space/changes` | Delta since state token. |
| `Space/query` | Filter/sort. |
| `KeyPackage/get` | Fetch by ids. Pass `"consume": true` in args to atomically consume (same guarantee as REST `GET /v1/agora/kp/{did}`). |
| `KeyPackage/set` | Upload new packages (`create`); destroy expired ones. Owner DID must match authenticated session. |
| `KeyPackage/changes` | Delta for the authenticated user's own packages. |

**Batching and ResultReferences.** Standard RFC 8620 §9 batching applies. Multiple method calls in a single request execute in order; `#`-prefixed argument keys reference results of prior calls via RFC 6901 JSON Pointers.

Example — fetch a space then query its channels in one round-trip:

```json
{
  "using": ["urn:ietf:params:jmap:core", "urn:agora:v1"],
  "methodCalls": [
    ["Space/get", {"accountId": "a-self", "ids": ["bafyrei..."]}, "0"],
    ["Channel/query", {
      "accountId": "a-self",
      "#filter": {
        "resultOf": "0",
        "name": "Space/get",
        "path": "/list/0/id"
      }
    }, "1"]
  ]
}
```

#### 8.8.6 Relay Blindness Preservation

The Relay's blindness properties (§11.1) are fully preserved under the JMAP API:

- **Message content.** `Message/encryptedPayload` is always MLS ciphertext. The Relay stores and serves it without decrypting. A subpoena against the Relay yields only ciphertext.
- **Channel identity.** The Relay builds its `channelCid`→`channelToken` mapping from public space state documents. This mapping is already part of normal relay operation (routing requires it); exposing it via JMAP reveals nothing new.
- **Sender identity.** No sender identity appears in any JMAP object. `encryptedPayload` contains a sealed MLS ApplicationMessage; the sender is sealed inside the ciphertext.
- **Space state.** Space and channel metadata is derived from public signed documents — the same documents any gossipsub participant can observe.

#### 8.8.7 EventSource Push

The Relay emits `StateChange` events on the EventSource stream when any tracked object type's state advances. Clients use these as a trigger to call the corresponding `/changes` method — they do not carry content.

```
event: state
data: {"changed": {"a-self": {"Message": "s-43", "Channel": "s-7", "Space": "s-3"}}}
```

Only object types whose state has changed are included in a given event. The live stream (§8.1–§8.2) provides lower-latency delivery for new messages; EventSource is the appropriate trigger for history-sync clients and background processes that do not maintain a live stream connection.

#### 8.8.8 Scope: JMAP vs Live Stream

| Operation | JMAP (§8.8) | Live Stream (§8.1–§8.7) |
|---|---|---|
| History retrieval and sync | ✓ | — |
| Space / channel metadata queries | ✓ | — |
| KeyPackage CRUD | ✓ | ✓ (also REST endpoint) |
| Programmatic / bot access | ✓ | — |
| Blob upload / download | ✓ | — |
| New message delivery | — | ✓ |
| MLS handshake (Commit / Proposal / Welcome) | — | ✓ |
| Presence and typing indicators | — | ✓ |
| Push notification registration | — | ✓ |
| DID auth handshake | ✓ (`/jmap/auth`) | ✓ (control frame) |

---

