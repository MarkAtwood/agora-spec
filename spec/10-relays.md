# 10. Relays, Federation and Discovery

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 584–1065, 2920–2994, 3054–3133, 3188–3207 (§3.4–3.5, §4, §11, §12 intro, §12.2, §12.4).

## 10.1 Deployment Topologies

*Binds: IO.*

Agora is transport-agnostic at the application layer. The following deployment topologies are explicitly supported:

**Public internet (default)**: Relays are clearnet HTTPS/WSS servers with public IPv4 and/or IPv6 addresses. Clients connect over the public internet. This is the baseline configuration assumed throughout this specification unless otherwise noted.

**Tor hidden service**: A Relay MAY operate as a Tor v3 hidden service, publishing a `.onion` address in its `RelayAd` alongside or instead of a clearnet endpoint. Clients connecting via Tor MUST use the WebSocket transport (§11.2); WebTransport requires QUIC over UDP and is unavailable over Tor.

**Private overlay (Tailscale / WireGuard / Headscale)**: A Relay MAY operate exclusively on a WireGuard-based overlay network. The Relay's `RelayAd` lists overlay-internal hostnames or `100.x.x.x` addresses; these are only resolvable inside the overlay. This is the recommended topology for private organizational deployments where all members are already on a common overlay. A fully self-contained deployment (Relay + SFU + TURN + Headscale, all on-premise) has zero dependency on any external infrastructure.

**Dual-stack (clearnet + overlay)**: A Relay MAY publish both clearnet and overlay endpoints. Clients on the overlay prefer the overlay path; external clients use the clearnet path. Both sets of clients share the same space state and message history.

**Managed / SaaS**: A relay operator (the "managed provider") provisions and operates a dedicated Agora relay fleet on behalf of a customer. Each customer receives their own isolated deployment (separate relay processes, separate database, separate blob store), not a shared multi-tenant instance. The customer controls, or delegates control of, the DNS name that roots their deployment; the managed provider's infrastructure hosts it (typically via CNAME or DNS delegation). The managed provider's identity appears as `operatorDID` in each relay manifest (§10.2.1), but `relayDID` is anchored to the customer's DNS domain, not the provider's. This preserves namespace ownership: if the customer migrates to self-hosted, their DNS name and all derived identities (`did:webvh:<SCID>:<customer-domain>:users:...`) are portable without re-enrollment. A did:webvh identity (§2.1) is also portable to a different domain, because its SCID and signed document history move with it. `operatorDID` and `relayDID` are IO keys and are distinct principals from every CO key, even where one entity holds both roles (ARCHITECTURE §2.4).

**IPv6**: All Relay endpoints SHOULD support IPv6. Relay URIs MUST use bracket notation for IPv6 address literals (`wss://[2001:db8::1]/v1/agora/ws`). ICE gathers both IPv4 and IPv6 host candidates; dual-stack clients race both address families.

### 10.1.1 Discoverability and DNS Namespace Root

A deployment's ability to participate in the public Agora mesh depends on whether it has a DNS root:

**Discoverable deployments** (public internet, managed/SaaS, dual-stack) SHOULD be anchored to a DNS name. That name is the root of the deployment's identity namespace: relay DIDs are `did:web:<domain>`, organizational user DIDs are normally `did:webvh:<SCID>:<domain>:users:...`, and the relay manifest is served at `https://<domain>/.well-known/agora-relay`. Any two deployments with distinct DNS names have non-overlapping identity namespaces by construction; no registry or authority is required to prevent conflicts.

**Non-discoverable deployments** (private overlay, air-gapped, Tor-only) have no DNS root requirement. Relay DIDs are `did:key:...`; user DIDs are `did:key:...` or `did:webvh` anchored to an internal-only domain. These deployments cannot join the public gossipsub mesh or federate with external organizations. This is an explicit architectural trade-off.

No registry, whitelist, or certificate authority governs which DNS names may root an Agora deployment. DNS ownership is the sole claim to a namespace.

## 10.2 Relay-to-Relay Peering and Authentication

*Binds: IO.*

Relays form a gossipsub mesh with each other for fanout. This section specifies how Relays discover each other, authenticate, establish trust levels, and maintain the mesh. The model follows a well-known manifest endpoint, RFC 9421 HTTP Message Signatures for relay-to-relay authentication, graduated trust levels, and zero-configuration bootstrap from any single known peer.

**Transport for relay-to-relay communication.** libp2p supports multiple transports; Relays SHOULD prefer **QUIC-v1** (`/ip4/.../udp/.../quic-v1` multiaddr) for gossipsub connections, with TCP (`/ip4/.../tcp/...`) as the fallback for environments where UDP is blocked. QUIC eliminates head-of-line blocking between gossip streams and removes TCP from the relay-to-relay data path entirely. The Peer API (§10.2.2) SHOULD be served over **HTTP/3** (QUIC); Relays MUST also support HTTP/1.1 or HTTP/2 over TLS as a fallback and SHOULD advertise HTTP/3 availability via `Alt-Svc: h3="<port>"` response headers. Relay operators that cannot expose UDP MAY operate TCP-only, but MUST declare this in their manifest `capabilities` by omitting `gossipsub-quic-v1`.

### 10.2.1 Relay Manifest

Every Relay MUST publish a **Relay Manifest** at a well-known URL:

```
GET /.well-known/agora-relay
```

The manifest is a typed payload envelope (§13.1) of type `urn:agora:type:RelayManifest` whose `body` is the JSON object below, served as its encoded envelope with `sig` present and `Content-Type: application/cbor`. It is the Relay's authoritative self-declaration. It is the single source of truth for a Relay's identity, capabilities, endpoints, and signing keys. Any Relay that can reach this URL can bootstrap a peering relationship without out-of-band coordination.

```json
{
  "version": "1",
  "relayDID": "did:web:relay.example.com",
  "operator": "Example Relay Co.",
  "operatorDID": "did:key:z6MkOperator...",
  "adminContact": "relay-admin@example.com",
  "abuseContact": "abuse@example.com",
  "description": "Public community relay, US-West",
  "region": "us-west",
  "endpoints": {
    "webTransport":    "https://relay.example.com/v1/agora/wt",
    "webSocket":       "wss://relay.example.com/v1/agora/ws",
    "onion":           "ws://examplerelay3xyzabc.onion/v1/agora/ws",
    "peerAPI":         "https://relay.example.com/v1/agora/peer",
    "jmapSync":        "https://relay.example.com/v1/agora/jmap",
    "admissionKeys":   "https://relay.example.com/v1/agora/admission-keys",
    "gossipQuic":      "/ip4/203.0.113.42/udp/9001/quic-v1"
  },
  "keys": [
    {
      "id": "did:web:relay.example.com#key-1",
      "type": "Ed25519VerificationKey2020",
      "publicKeyMultibase": "z6MkRelay...",
      "status": "active",
      "activatedAt": "2026-03-12T00:00:00Z",
      "expiresAt": "2027-03-12T00:00:00Z"
    }
  ],
  "capabilities": [
    "gossipsub-v1.1",
    "tor-hidden-service-v1",
    "peer-api-v1",
    "jmap-sync-v1"
  ],
  "minPowDifficulty": 0,
  "observationBudget": {
    "connectionLogRetentionDays": 7,
    "extensions": []
  },
  "knownPeers": [
    {
      "relayDID": "did:web:peer.example.net",
      "manifestURL": "https://peer.example.net/.well-known/agora-relay",
      "addedAt": "2026-03-12T00:00:00Z"
    }
  ],
  "publishedAt": "2026-03-12T00:00:00Z"
}
```

The manifest is signed per §13.1.1 by `relayDID`, with a key listed both in `keys` and in the DID document of `relayDID`. Peer Relays and clients MUST verify this signature before accepting the manifest.

Each entry in `keys` has a `status` of `active`, `deprecated` (still accepted during a rotation overlap, §10.2.6) or `revoked` (compromised, §12.12). A verifier MUST NOT accept any signature, including the manifest's own, made with a key marked `revoked`.

`endpoints.admissionKeys` is the URL at which the Relay accepts admission key registrations from COs (§10.5.3).

`observationBudget` declares what the Relay retains beyond transient routing. `connectionLogRetentionDays` is the retention of network-layer connection metadata (ARCHITECTURE §5 item 1), as set by the Relay's `ServiceAgreement`s (§10.5.1). `extensions` lists every opt-in extension to the ARCHITECTURE §5 observation budget the Relay has enabled; it MUST be empty unless a CO has opted in (ARCHITECTURE S6). A Relay MUST NOT observe, log or retain anything not covered by ARCHITECTURE §5 or a declared extension.

`minPowDifficulty` is the minimum proof-of-work difficulty, in leading zero bits, that the Relay requires on each `RoutingEnvelope` (§10.5.2). `0` means the Relay requires no proof-of-work, and a Relay that omits the member requires none.

`retiresAt` is optional. A Relay that will stop serving sets it to the RFC 3339 UTC time at which it stops (§10.4.7); a Relay without a planned end omits it.

`knownPeers` is the Relay's current peer list. This serves as a mesh map: a new Relay fetching any existing Relay's manifest obtains a list of further Relays to contact, enabling rapid mesh joining without a central directory server.

**Relay DID and DNS binding.** For relays operating on the public internet (§10.1), `relayDID` SHOULD be a `did:web` anchored to the relay's DNS domain rather than a `did:key`:

```json
"relayDID": "did:web:relay.example.com"
```

The relay MUST serve a conformant DID document at `https://relay.example.com/.well-known/did.json`. This creates a verifiable binding: the manifest at `/.well-known/agora-relay` is signed by `relayDID` with a key declared in that DID document, and the DID document SHOULD include a `service` entry pointing back to the manifest URL. Any peer that resolves `did:web:relay.example.com` can verify that the key material and the DNS domain are controlled by the same entity.

For relays operating exclusively on a private overlay, Tor hidden service, or air-gapped network, where no public DNS name exists or is desired, `relayDID` MAY be `did:key:...`. These relays do not participate in the public mesh and do not require DNS binding.

**Operator vs. customer identity.** The `operatorDID` field records the identity of the party that operates the relay infrastructure. For self-hosted deployments, `operatorDID` and the relay's controlling entity are the same. For managed/SaaS deployments (§10.1), they differ: `relayDID` is anchored to the customer's DNS domain; `operatorDID` is the managed provider's DID. This distinction is relevant to legal exposure (§12.3).

`capabilities` is an array of capability strings declaring what features this Relay supports:

| Capability | Meaning |
|---|---|
| `gossipsub-v1.1` | Participates in libp2p gossipsub v1.1 mesh over TCP |
| `gossipsub-quic-v1` | Participates in libp2p gossipsub v1.1 mesh over QUIC-v1 (preferred) |
| `peer-api-h3` | Peer API is served over HTTP/3 (QUIC); `Alt-Svc: h3` header is present |
| `tor-hidden-service-v1` | Reachable via a `.onion` endpoint |
| `sfu-v1` | Hosts an SFU for voice channel routing |
| `peer-api-v1` | Implements the Peer API v1 (§10.2.2) |
| `jmap-sync-v1` | Exposes the token-keyed JMAP sync API (§11.8.1–§11.8.8) |
| `push-proxy-v1` | Operates a push notification proxy (§11.7) |
| `sequencer-v1` | Operates a blind sequencer (§14.4) |

### 10.2.2 Peer API

Relays expose a **Peer API** at the URL declared in `endpoints.peerAPI` for relay-to-relay operations. All Peer API requests (except `manifest` and `health`, which are unauthenticated) are signed using RFC 9421 HTTP Message Signatures (§10.2.3).

Relays SHOULD serve the Peer API over HTTP/3 and advertise this via `Alt-Svc: h3="9001"` (or the appropriate port) on all HTTP responses. A connecting Relay that receives an `Alt-Svc` header SHOULD upgrade to HTTP/3 for subsequent requests. Relays MUST continue to accept HTTP/1.1 and HTTP/2 over TLS on the same `peerAPI` URL for peers that cannot use QUIC.

```
GET  /v1/agora/peer/manifest
     Returns this relay's current RelayManifest.
     Unauthenticated.

POST /v1/agora/peer/announce
     A peer relay announces itself. Body: the announcing relay's RelayManifest.
     Response: 200 { "status": "accepted"|"known"|"rejected", "trustLevel": N }

GET  /v1/agora/peer/peers
     Returns the relay's known peer list: array of { relayDID, manifestURL }.
     Authenticated. Rate-limited to 1 request/hour per peer.

POST /v1/agora/peer/gossip
     Relay-to-relay gossip message submission, for peers that cannot hold a
     libp2p connection. Body: GossipBatch (below), Content-Type application/cbor.
     Response: 204. Authenticated.

GET  /v1/agora/peer/health
     Returns relay health state.
     Response: { "status": "healthy"|"degraded"|"unhealthy"|"maintenance", "since": <RFC 3339 UTC> }
     Unauthenticated.
```

A `GossipBatch` carries messages exactly as they travel on the libp2p mesh (§10.3.1). The receiving Relay processes each entry as if it had arrived on that topic from the sender, subject to the same rules, including §10.5.4 for channel topics:

```cddl
GossipBatch = [* GossipEntry]
GossipEntry = {
  "topic": tstr,   ; a topic string of §10.3.1
  "data":  bstr    ; the gossip message data of §10.3.1
}
```

### 10.2.3 Relay-to-Relay Authentication

All relay-to-relay requests (except unauthenticated endpoints) use **RFC 9421 HTTP Message Signatures** with Ed25519. The requesting Relay signs each HTTP request using an active or deprecated key (§10.2.6) from its manifest. The receiving Relay verifies the signature against the requesting Relay's manifest fetched from `/.well-known/agora-relay`.

**Profile.** The request carries one signature with label `sig1` in the `Signature-Input` and `Signature` fields. Its signature parameters are:

- `keyid`: the `id` of the signing key in the requesting Relay's manifest `keys`, a DID URL whose DID is the requesting Relay's `relayDID` (for example `did:web:relay.example.com#key-1`). The receiving Relay takes the requester's identity from this DID and fetches its manifest from the DID's domain (`did:web`) or from the peer's known `manifestURL`.
- `alg`: `"ed25519"`.
- `created`: the signing time, integer seconds since the Unix epoch.
- `nonce`: a random 128-bit value, base64url without padding.

**Covered components** (RFC 9421 §2):

```
"@method"
"@target-uri"
"@authority"
"content-digest"      (requests with a body; RFC 9530, algorithm sha-256)
```

The receiving Relay MUST verify `Content-Digest` against the body before acting on it.

**Replay prevention:** `created` MUST be within 300 seconds of the receiving Relay's clock. `nonce` MUST NOT have been seen from the same `keyid` in the previous 600 seconds (the receiving Relay maintains a nonce cache with a 600-second TTL). Requests violating either condition MUST be rejected with HTTP 401.

**Manifest caching:** Receiving Relays cache peer manifests for 1 hour. On a cache miss or expiry, the Relay fetches a fresh manifest before verifying the request. If the fetch fails, the Relay retries once after 5 seconds before rejecting the request with HTTP 503.

**Reference implementations for RFC 9421:** [`httpbis-message-signatures`](https://github.com/nicowillis/httpbis-message-signatures) (JS), [`httpsig`](https://github.com/bblfish/httpSig) (Scala/JVM reference), [`go-http-signature`](https://github.com/go-fed/httpsig) (Go).

### 10.2.4 Trust Levels

Relay-to-relay trust is graduated. Trust level determines which Peer API operations a Relay is permitted to invoke and what gossip rate limits apply. Trust level is local state; each Relay maintains its own assessments independently. It is never gossiped or shared. Level 3 is set via local operator configuration and is appropriate for Relays operated by the same organization or well-known partner organizations.

| Level | Name | Criteria | Permissions |
|---|---|---|---|
| 0 | Unknown | No prior contact | Manifest fetch only; `announce` accepted for evaluation |
| 1 | Seen | Valid manifest, valid signature, first contact | `announce`, `health`; gossip rate-limited to 10 msg/s |
| 2 | Known | 7+ days of sustained peering without incident | Full gossip; `peers` accessible; 1000 msg/s |
| 3 | Trusted | Explicitly operator-configured | Full access; relaxed rate limits; no gossip throttling |

**Trust degradation:** A Relay that submits invalid signatures, sends malformed gossip, or repeatedly exceeds rate limits is downgraded to Level 0 and its DID is blocked for 24 hours. Repeated violations (3 or more incidents within 7 days) result in permanent operator-managed blocklisting.

### 10.2.5 Bootstrap: Joining the Mesh

A new Relay with no existing peers joins the gossipsub mesh using any of the following methods, attempted in parallel:

**Method 1: Known peer URL.** The operator provides one or more peer Relay URLs in the startup configuration. The new Relay fetches `/.well-known/agora-relay` from each, verifies the manifest signature, sends `POST /v1/agora/peer/announce` with its own manifest, and on acceptance fetches `GET /v1/agora/peer/peers` to discover further Relays.

**Method 2: Directory document.** The Relay fetches any Agora Relay directory document (§10.3.4.1) and contacts each listed Relay using Method 1.

**Method 3: DNS-SD.** The Relay queries both `_agora-relay._udp.<domain>` (QUIC, preferred) and `_agora-relay._tcp.<domain>` (TCP fallback) SRV records:

```
_agora-relay._udp.example.com. SRV 10 0 9001 relay.example.com.
_agora-relay._tcp.example.com. SRV 20 0 443  relay.example.com.
_agora-relay._udp.example.com. TXT "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"
_agora-relay._tcp.example.com. TXT "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"
```

Each SRV record has a TXT record at the same owner name (RFC 6763 §6) carrying the Relay's DID and manifest URL.

Lower SRV priority value means higher preference; QUIC (UDP) is preferred. Relays SHOULD publish both records. Relays that cannot expose UDP MUST publish only the TCP record.

**Method 4: IPNS fallback.** The Relay resolves an IPNS name configured by the operator (e.g. `/ipns/bootstrap.example.com`) for a signed bootstrap list. This is the last resort.

A Relay is considered mesh-joined when it has Level 1 or higher trust with at least 3 peers and is participating in gossipsub fanout. It SHOULD continue discovering peers until it has at least 6 active connections (gossipsub's default mesh degree `D`).

### 10.2.6 Mesh Maintenance

**Heartbeat.** Relays MUST poll `GET /v1/agora/peer/health` from each peer every 60 seconds. A peer that returns `unhealthy` or fails to respond for 3 consecutive checks (180 seconds total) is marked unreachable. Its gossipsub connection is dropped; it remains in `knownPeers` for 7 days before removal, in case it recovers.

**Manifest refresh.** Relays re-fetch peer manifests every hour to detect key rotation and endpoint changes. A manifest whose `sig` no longer verifies is treated as a trust failure and the peer is downgraded to Level 0 pending re-verification.

**Key rotation overlap.** When rotating its signing key, a Relay MUST publish both the old and new keys in its manifest with a minimum 48-hour overlap, marking the old key with `"status": "deprecated"`. Peer Relays accept signatures from deprecated keys during this overlap window. A key whose private half is compromised is instead marked `"status": "revoked"`, with no overlap; peer Relays MUST reject every request signed with a key the manifest marks `revoked` (§12.12).

**Peer gossip.** When a Relay discovers a new valid peer, it SHOULD share that peer's `{ relayDID, manifestURL }` with its Level 2+ peers as a `RelayPeerAnnouncement` gossip message:

```json
{
  "@type": "RelayPeerAnnouncement",
  "relayDID": "did:key:z6MkNewRelay...",
  "manifestURL": "https://newrelay.example.com/.well-known/agora-relay",
  "announcedBy": "did:key:z6MkExistingRelay...",
  "ts": "2026-03-12T00:00:00Z"
}
```

The announcement is signed per §13.1.1 by `announcedBy`. Receiving Relays verify the signature, independently fetch the new Relay's manifest, and decide whether to initiate peering. The announcement is a hint, not an authorization.

---

## 10.3 Discovery

*Binds: both.*

### 10.3.1 Gossip Protocol

Agora uses **libp2p gossipsub v1.1** among Relays for peer discovery, voluntary CO and Relay advertisements, and live delivery of token-keyed ciphertext envelopes, including MLS Commits and Proposals, which travel in the channel's own envelopes.

Each gossipsub **topic** maps to a specific scope:

| Topic pattern | Purpose | Message data |
|---|---|---|
| `v1/agora/discovery` | SpaceAds (§10.3.2) and RelayAds (§10.5.1) | One encoded typed payload envelope (§13.1) with `sig` present |
| `v1/agora/channel/<channelToken>` | Per-channel envelopes, including ephemeral presence and typing events | One encoded routing envelope (§5.2.2), exactly as the client published it |

`<channelToken>` is the token in base64url without padding (RFC 4648 §5).

**Channel topics.** A Relay subscribes to, forwards and caches `v1/agora/channel/<channelToken>` only for a `channelToken` registered with it under a current `ServiceAgreement` (§10.5.3). It MUST NOT publish to, forward or cache a channel topic for any other token, and drops envelopes for such tokens whether they arrive from a client or a peer. The mesh for a channel topic therefore consists of the Relays the channel's CO has registered the token with; a Relay without a registration never sees the channel's traffic or any registration data. Every Relay on a channel topic applies the admission rule of §10.5.4 to each envelope.

**Discovery topic.** Every mesh Relay MAY carry `v1/agora/discovery`. Only SpaceAds and RelayAds travel on it. Clients do not publish on any gossip topic; they send envelopes to a Relay in a live protocol `Publish` (§11.4), and MUST NOT send DID-signed records about themselves (profiles, recovery assertions, device revocations or any other user record) over a Relay connection. A user is discovered through the DID document or Pkarr record (§2.1, §10.3.4.6), key recovery is recorded in the DID log (§2.4), and a user tells its groups to re-resolve its DID and profile with an `urn:agora:type:IdentityChanged` MLS application message (§5.2.3).

**Parameters.** Relays MUST use the gossipsub signature policy `StrictNoSign`: messages carry no libp2p author, sequence number or signature, so no peer ID is attached to an envelope and peers with different policies do not drop each other's messages. The message ID is SHA-256 of the message data. The maximum message data size is 65536 bytes, the `maxEnvelopeBytes` of §11.8.3. Mesh degree parameters are `D = 6`, `D_low = 4`, `D_high = 12` and the heartbeat interval is 1 second, the gossipsub v1.1 defaults.

No topic carries a Space CID, MLS group ID, `channelID` or other Space identifier (ARCHITECTURE S1). Space state, moderation records and other Space-level records reach members from the CO's Space endpoint and in-band MLS notifications (§3.4); Welcomes go to the invitee's `KeyPackageEndpoint` (§4.6).

The `v1/` prefix is the gossip protocol version for that topic family. A future breaking change to message framing on a topic introduces a `v2/` prefix. Relays MUST subscribe to all versions of topics they serve. Clients never choose a topic version: they send envelopes to a Relay in a live protocol `Publish`, whose version is negotiated in the hello exchange (§11.4, §11.6), and the Relay publishes them on the topic versions it serves. During a version transition period, Relays bridge messages between `v1/` and `v2/` topic variants for the same channel.

**Reference implementations for libp2p gossipsub:**
- Go: [`go-libp2p-pubsub`](https://github.com/libp2p/go-libp2p-pubsub)
- Rust: [`libp2p` crate, `gossipsub` module](https://docs.rs/libp2p/latest/libp2p/gossipsub/)
- JS: [`@chainsafe/libp2p-gossipsub`](https://github.com/ChainSafe/js-libp2p-gossipsub)

### 10.3.2 Discovery Advertisements

A **SpaceAd** is a typed payload envelope (§13.1) of type `urn:agora:type:SpaceAd`, gossiped periodically on `v1/agora/discovery` by a mesh node its CO operates (default TTL: 60 seconds; re-advertised at 45 seconds to avoid expiry gaps). Its body is:

```json
{
  "spaceCID": "bafkrei...",
  "name": "Example Corp Dev",
  "description": "Example Corp development coordination",
  "memberCount": 12,
  "relayHints": [
    "wss://relay.example.com",
    "wss://relay.example.net"
  ],
  "iconCID": "bafkrei...",
  "inviteURL": "https://invite.example.com/dev",
  "spaceEndpoint": ["https://spaces.example.com/v1/agora/space/1f3a..."],
  "advertisedBy": "did:webvh:QmSCID...:example.com:co",
  "ts": "2026-03-12T00:00:00Z"
}
```

`spaceEndpoint` lists the CO's Space endpoint URLs (§3.4). `relayHints` lists the client endpoints of the Relays that carry the Space's public channels (§10.3.5). Entries MAY be `.onion` addresses, clearnet HTTPS/WSS URIs, overlay-internal hostnames, and IPv6 address literals.

**Signing rule.** Every discovery record is signed by the party it describes: the CO for Space records and the Relay for relay records. `advertisedBy` is the CO DID that signs the Space's state (ARCHITECTURE S4), and the SpaceAd is signed per §13.1.1 by `advertisedBy`. Clients MUST discard a SpaceAd whose signature does not verify against `advertisedBy`. There are no user discovery records (§10.3.1).

Only public Spaces advertise. A CO MUST NOT publish a SpaceAd or directory entry for a private Space; private Spaces are reached only by invitation (§4.3).

A SpaceAd is a voluntary CO publication. Relays forward and cache SpaceAds and RelayAds on `v1/agora/discovery` like any other gossip message. A Relay MUST NOT author or modify a Space record, MUST NOT forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd, and MUST NOT publish lists of the Spaces it serves.

### 10.3.3 Relay Discovery Bootstrap

To bootstrap into the gossip network, a client needs at least one known peer. Agora supports the following bootstrap mechanisms, attempted in order:

1. **Directory sources**: user-configured URLs serving `RelayDirectory` or `SpaceDirectory` documents (§10.3.4); the primary bootstrap mechanism in practice.
2. **Previously cached relay list**: Relays successfully contacted in a prior session, stored locally with a staleness TTL of 7 days.
3. **Mainline DHT**: Relays announce themselves on the BitTorrent Mainline DHT (BEP-5) under a well-known infohash (§10.3.4.6); clients perform a `get_peers` lookup to find announcing relays (§10.3.4.6).
4. **DNS-SD**: `_agora-relay._udp` and `_agora-relay._tcp` mDNS for LAN or overlay discovery (§10.2.5).

### 10.3.4 Directory Documents

A **directory document** is a static file served at any reachable URL. It is a typed payload envelope (§13.1) whose `type` is `urn:agora:type:` followed by the document's `@type` (`RelayDirectory`, `SpaceDirectory` or `AgoraDirectory`) and whose `body` is the JSON object shown below; the file holds the encoded envelope, with `sig` present when the directory is signed. A directory lists Spaces, Relays, or both, and MAY include references to other directory documents by URL. Users configure one or more directory source URLs in their client. Clients fetch and merge all configured sources on startup and refresh on a configurable interval (default: 1 hour).

Directory documents require no special server infrastructure. A file committed to a public GitHub repository and served via `raw.githubusercontent.com` or GitHub Pages is a valid directory source. So is an IPFS CID, a Cloudflare R2 bucket, a `.onion` URL, or any HTTPS endpoint returning the encoded envelope.

#### 10.3.4.1 Relay Directory

A `RelayDirectory` lists Relays available for client connection:

```json
{
  "@type": "RelayDirectory",
  "schemaVersion": "1",
  "id": "https://raw.githubusercontent.com/example/agora-relays/main/relays.json",
  "name": "Community Relay List",
  "maintainer": "did:key:z6MkMaintainer...",
  "published": "2026-03-12T00:00:00Z",
  "ttl": 3600,
  "relays": [
    {
      "@type": "RelayEntry",
      "did": "did:web:relay.example.com",
      "endpoints": [
        "wss://relay.example.com",
        "wss://relay2.example.com"
      ],
      "onionEndpoints": [
        "ws://examplerelay.onion"
      ],
      "regions": ["us-west", "eu-central"],
      "operator": "Example Relay Operator",
      "operatorDID": "did:key:z6MkOperator...",
      "serviceTiers": [
        { "id": "hobbyist", "retentionDays": 7,  "bandwidthTierGbPerMonth": 10  },
        { "id": "standard", "retentionDays": 30, "bandwidthTierGbPerMonth": 100 }
      ],
      "note": "Community relay, no logging"
    }
  ],
  "includes": [
    "https://raw.githubusercontent.com/other-org/relays/main/relays.json"
  ]
}
```

`ttl` is the number of seconds before the client should re-fetch the document. `includes` is a list of other directory document URLs whose contents are merged into this one; clients MUST limit include recursion depth to 3 to prevent cycles. The document is signed per §13.1.1 by the `maintainer` DID. Clients SHOULD verify the signature against the `maintainer` DID but MAY accept unsigned directories with a user-visible warning. A `RelayEntry` is a connection hint, and its `serviceTiers` have the form of `RelayAd.serviceTiers` (§10.5.1); the relay record that counts is the Relay-signed manifest (§10.2.1), which clients MUST verify before use (§10.3.4.7).

#### 10.3.4.2 Space Directory

A `SpaceDirectory` lists Spaces available for browsing or joining:

```json
{
  "@type": "SpaceDirectory",
  "schemaVersion": "1",
  "id": "https://raw.githubusercontent.com/example/agora-spaces/main/spaces.json",
  "name": "Open Source Projects",
  "maintainer": "did:key:z6MkMaintainer...",
  "published": "2026-03-12T00:00:00Z",
  "ttl": 3600,
  "spaces": [
    {
      "@type": "SpaceDirectoryEntry",
      "spaceCID": "bafkrei...",
      "spaceAd": "base64url...",
      "tags": ["cryptography", "embedded", "fips", "open-source"],
      "language": "en",
      "addedBy": "did:key:z6MkMaintainer...",
      "addedAt": "2026-03-12T00:00:00Z"
    }
  ],
  "includes": [
    "https://raw.githubusercontent.com/other-org/spaces/main/spaces.json"
  ]
}
```

A directory is an independent publisher and lists only CO-signed Space records. `spaceAd` is the CO-signed SpaceAd (§10.3.2) for the Space: its encoded envelope (§13.1) with `sig`, base64url-encoded without padding (RFC 4648 §5) from the exact bytes and copied unmodified; clients MUST verify its signature and MUST discard an entry whose `spaceAd` is missing, fails verification, or names a different `spaceCID`. Name, description, icon, member count, invite link and relay hints come only from `spaceAd`; `tags`, `language`, `addedBy` and `addedAt` are the directory's own annotations, covered by the directory's signature.

The SpaceAd's `inviteURL` is a human-readable join link; the join flow itself is handled by the Space's invite mechanism (§4.3). `spaceCID` is the authoritative space identity; clients verify this against the space's genesis state document when connecting.

#### 10.3.4.3 Combined Directory

A single document MAY contain both `relays` and `spaces` arrays, typed as `AgoraDirectory`:

```json
{
  "@type": "AgoraDirectory",
  "relays": [],
  "spaces": [],
  "includes": []
}
```

`relays`, `spaces` and `includes` entries have the forms defined in §10.3.4.1 and §10.3.4.2.

#### 10.3.4.4 Client Behavior

On startup, the client fetches all configured directory sources in parallel. Results are merged: Relay lists are deduplicated by `did`; Space lists are deduplicated by `spaceCID`. The client attempts connection to the highest-priority available Relay (ordered by user preference). Previously cached Relays from prior sessions are used immediately while directory fetches are in flight.

Failed fetches are retried with exponential backoff (base 30 seconds, maximum 1 hour). A source that consistently fails for 7 days is flagged in the UI as unreachable; it is NOT silently removed from the configured source list. The user decides whether to remove it.

Clients MUST NOT auto-add directory sources from space state documents, relay advertisements, or any other protocol message without explicit user confirmation. Auto-population of directory sources is a privilege escalation vector.

#### 10.3.4.5 Content-Addressed Directories

A directory document MAY be addressed by CID instead of (or in addition to) an HTTPS URL:

```
ipfs://bafkrei.../relays.json
```

Clients resolve `ipfs://` URIs by fetching the blob from the CAS endpoint (`GET /v1/agora/blob/{cid}`, §10.4.4) of a Relay that holds it. Relays do not exchange blobs, so a Relay holds a blob only if it was uploaded there (§10.4.4); a directory publisher stores the document at the Relays it names alongside the `ipfs://` URI, and a client tries those Relays in turn.

#### 10.3.4.6 Mainline DHT Discovery

Agora uses the BitTorrent Mainline DHT (BEP-5, BEP-44) for two complementary purposes: relay bootstrapping and user endpoint discovery. Both are opportunistic: clients MUST degrade gracefully when UDP is unavailable (corporate firewalls, restrictive NAT) and fall back to other discovery mechanisms.

##### Relay Bootstrapping (BEP-5)

Relay operators announce their relay on Mainline by performing a BEP-5 `announce_peer` for the well-known infohash:

```
infohash = SHA1("agora-relay-v1")
```

The infohash is the 20-byte SHA-1 digest of the 14 ASCII bytes `agora-relay-v1`, with no terminator. SHA-1 serves here only as the BEP-5 naming function; nothing depends on its collision resistance, since every result is verified as below. A future incompatible relay protocol announces under a new string.

The announced port is the relay's WebSocket port. Clients discovering a relay via this mechanism MUST still verify the relay's DID and TLS certificate before use (§10.3.4.7); a Mainline announcement is a hint, not an authorization.

Relay operators SHOULD re-announce every 30 minutes. Clients performing a cold-start bootstrap issue a `get_peers` lookup for this infohash and attempt connection to returned peers.

##### User Endpoint Discovery (BEP-44 / Pkarr)

A `did:key` user has no DID document, so it publishes its Pkarr pointer record here (§2.1): a BEP-44 mutable item on Mainline, signed by the identity key, carrying its KeyPackage pointer and profile pointer. It names no relay or other IO (ARCHITECTURE §2). A `did:key` user MUST publish this record to be reachable for invitations. This enables contact initiation without requiring a shared directory or prior relay knowledge.

**Key derivation.** The BEP-44 key is the user's raw 32-byte ed25519 authentication public key, extracted directly from their `did:key` identifier. No additional key material is required.

**Record format.** The BEP-44 value is a compact DNS packet (Pkarr format) containing TXT resource records:

```
_agora.             TXT  "v=1"
_profile._agora.    TXT  "cid=bafkrei..."
_kp._agora.         TXT  "url=https://kp.example.net/v1/agora/kp/z6Mk..."
```

`v` and `_kp` are required; `_profile` and the optional service records below are optional. No record names a relay or other IO.

| Record | Key | Value | Required |
|---|---|---|---|
| `_agora` | `v` | Schema version (`1`) | Yes |
| `_profile._agora` | `cid` | Bare CID (no scheme) of the user's current profile node (§2.3) | No |
| `_kp._agora` | `url` | The user's `KeyPackageEndpoint` (§5.2.1.1), an HTTPS URL whose path begins with `/v1/agora/kp/` | Yes |
| `_corundum._agora` | `url`, `key` | Optional service record for the CORUNDUM social protocol: the operator's content endpoint (`url`) and the multibase Ed25519 posting key (`key`) that signs the user's content index (profiles/corundum.md) | No |

**Service records.** Beyond `_profile` and `_kp`, a Pkarr record MAY carry the optional service records listed in the table above, each the `did:key` equivalent of a DID document `service` entry. Only the identity key holder can change the record; any party MAY re-publish the unchanged signed record to keep it alive on the DHT.

The total DNS packet MUST fit within 1000 bytes (BEP-44 value limit). In practice a record with a profile CID and a KeyPackage URL occupies about 200 bytes.

**Verification.** BEP-44 mutable items are self-certifying: the DHT node returns the value together with the ed25519 signature, and the lookup key is the public key itself. Clients MUST verify the signature before using any field. A valid signature proves the record was produced by the holder of the DID's authentication key.

**Lookup procedure.**
1. Decode the `did:key` identifier to recover the raw 32-byte ed25519 public key.
2. Issue a BEP-44 `get` query for that key.
3. Verify the returned signature against the key.
4. Parse TXT records and use the profile CID or KeyPackage endpoint as needed.

**Publication and refresh.** Clients SHOULD publish their record on first login and re-publish every 2 hours. BEP-44 mutable items have no explicit TTL but decay from the DHT within approximately 2 hours without re-announcement. Stale or absent records are not an error; clients fall back to other discovery mechanisms.

**Scope.** This mechanism applies only to `did:key` users. `did:webvh` and `did:plc` users publish their `KeyPackageEndpoint` and profile pointer in their DID document, found by standard DID resolution, and do not require Mainline publication.

#### 10.3.4.7 Trust Model

Being listed in a directory confers no trust. A Relay in a directory is trusted only to the extent that its DID verifies against its TLS certificate and signed advertisements. A Space in a directory is trusted only to the extent that its `spaceCID` verifies against its genesis state document. A malicious directory entry pointing at a rogue Relay produces a DID mismatch at connection time and is rejected.

Directory maintainers are identified by their `maintainer` DID and signature. There is no global authority over directory content. Multiple competing directories can coexist and are all valid. Clients merge them all.

### 10.3.5 Channel Relay Lists

A Relay carries a channel only if the channel's CO has registered the channel's admission key with it (§10.3.1, §10.5.3). A client therefore sends and subscribes to a channel's `channelToken` at one of the Relays its CO has engaged, and learns that list from the CO, never from an IO:

- **Channels of a private Space.** From the `relays` member of the channel's `ChannelAdmissionKey`, which the CO's Space endpoint serves only to authenticated members (§3.4). The list appears in no record an IO can read.
- **Channels of a public Space.** From `relayHints` in the CO-signed SpaceAd (§10.3.2), and from the `ChannelAdmissionKey`.
- **Shared channels.** From the `ChannelAdmissionKey` issued by the home Space's CO, which registers the channel's admission key (§8.6).
- **DM groups.** From the `ChannelAdmissionKey` served by the identity host of the DM's initiator, which issues and registers the group's admission key (§4.6).

A client needs a connection to only one listed Relay per channel for envelopes: the Relays holding a registration for a token exchange its envelopes on the channel topic (§10.3.1). Blobs are not exchanged: a blob is held only by the Relays it was uploaded to (§10.4.4). Clients SHOULD fall back to another listed Relay when one is unreachable or answers `unknown-token` or `token-withdrawn` for a token the client holds in a current `ChannelAdmissionKey` (§11.4).

**Changing Relays.** To add a Relay, the CO registers every current admission key with it (§10.5.3), then adds it to `relays`. To remove a Relay, the CO removes it from `relays`, then deregisters the keys. Because members' MLS state, Space state and admission keys do not change, a CO adds, removes or replaces a Relay without touching Space identity or membership (ARCHITECTURE S5). Clients refresh the relay list whenever they fetch the `ChannelAdmissionKey` (§3.4).

---

## 10.4 Relay Behavior

*Binds: IO.*

### 10.4.1 Relay Knowledge Constraints

A conformant Relay is designed to know as little as possible about the traffic it routes. The following is both a design target and a compliance requirement: a Relay operator responding to a legal demand or subpoena MUST be able to testify truthfully to all of the following:

- I do not know who my users are (no identity registration, no account system, no persistent user records).
- I do not know who is in any group (channel membership is not visible at the relay layer; a `channelToken` is derived from an admission private key I never hold, and an admission signature does not identify its signer).
- I do not know which Space or channel any token belongs to (registrations name only the CO's billing DID, §10.5.3).
- I do not know who sent any message (MLS encrypts the sender data, and the sealed envelope hides the MLS framing, §5.2.2).
- I store nothing after delivery beyond the retention window of the agreement under which a token is registered, and nothing with a message expiry past that expiry, except CIDs pinned under an instruction carrying a valid admission signature (ARCHITECTURE §6.2), which are retained until unpinned the same way.
- The encrypted blobs I forward and cache are opaque to me.

These statements are the IO side of ARCHITECTURE §4: what a legal demand on a Relay operator yields is bounded by the observation budget in ARCHITECTURE §5.

Any protocol extension or Relay implementation that makes any of these statements false introduces a legal liability surface for operators and a surveillance surface for adversaries. Such extensions MUST be explicitly opt-in and clearly documented as degrading the Relay's metadata-blindness guarantees.

### 10.4.2 Relay-Blind Fan-out

Relays route messages by `channelToken`, not by `channelID`, MLS group ID or member identity. The routing table maps `channelToken` → set of subscriber connections. Relays MUST NOT:

- Maintain a mapping from `channelToken` to `channelID`, MLS group ID or Space CID.
- Maintain a mapping from `channelToken` to member DIDs.
- Log sender/recipient pairs for any message.
- Retain message envelopes beyond the agreement's retention window or message expiry, whichever is sooner.

A `channelToken` is fixed for one admission key and changes when the CO rotates the key (a new `keyEpoch`, §5.2.2); it does not change on MLS epochs. A Relay sees each token's traffic for as long as the key is registered, and it can usually link a new token to the one it replaces, because the CO registers the new key and deregisters the old one close together and the same subscribers move across. It cannot map a token to a channel or Space; the set of Spaces it cannot tell apart is every Space the CO serves through it (ARCHITECTURE §5 item 6).

### 10.4.3 Conformance Requirements

A conformant Relay MUST:

- Implement WebSocket transport (§11.2); WebTransport is RECOMMENDED.
- Implement the client hello and connection admission controls (§11.6), without authenticating client identity.
- Implement the Peer API and relay-to-relay authentication (§10.2).
- Accept `AdmissionKeyRegistration` and `AdmissionKeyDeregistration` requests at its `admissionKeys` endpoint (§10.5.3).
- Carry only `channelToken`s registered with it under a current `ServiceAgreement`, on the live protocol and on the gossip mesh (§10.3.1).
- Verify `admissionSig` on every envelope against the admission public key registered for its `channelToken` before caching or forwarding it, and drop envelopes that fail (§10.5.4, ARCHITECTURE §6.2).
- Respect `expiryHint` on cached message envelopes (§5.2.4).
- Publish a Relay Manifest at `/.well-known/agora-relay` (§10.2.1), declaring its connection-log retention and any observation-budget extensions.
- Maintain heartbeat polling of peer relays (§10.2.6).
- Route messages by `channelToken` only; never attempt to resolve tokens to identities.
- Hold recent envelopes for each registered `channelToken` up to the lesser of the agreement's `retentionDays` and the envelope's `expiryHint`, and serve them to clients (§10.4.6).
- Retain and serve blobs stored under a `ServiceAgreement` within the agreement's retention window (§10.4.4).
- Store only ciphertext envelopes, blobs addressed by CID that it cannot interpret (including group-encrypted blobs, §3.4), and records a CO explicitly publishes (such as SpaceAds, directory documents and public Space state).
- Honor pin and unpin instructions (`PinInstruction`, §11.4) carrying a valid admission signature for a registered `channelToken`, retaining pinned CIDs regardless of retention window or `expiryHint` until unpinned (ARCHITECTURE §6.2).
- Enforce the storage and bandwidth quotas set by each `ServiceAgreement` (§10.5.1), keyed to the agreement and never to member identity.
- Validate envelope structure and `channelToken` format before forwarding; drop malformed envelopes silently.
- Support IPv6 on all endpoints; use bracket notation for IPv6 literals in advertised URIs.
- Enforce per-`channelToken` rate limits (§11.6, §12.5) as the primary spam control mechanism; per-IP limits MUST NOT be the sole mechanism.
- Where it serves push, send every wake-up for a registered `pushHandle` in the same form, with no content and no urgency, whatever envelope triggered it (§11.7).
- Handle takedown requests for CIDs it cannot read as §10.4.5 describes.

A conformant Relay MUST NOT:

- Attempt to decrypt MLS ciphertext.
- Log or retain sender DIDs (the Relay never has them, §5.2.2).
- Use per-IP rate limiting as the sole spam control mechanism.
- Store or serve MLS KeyPackages; KeyPackages are held at the user's `KeyPackageEndpoint` (§2.1).
- Author or modify Space discovery records, forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd, or publish lists of the Spaces it serves (§10.3.2).
- Accept DID-signed user records from clients or forward them (§10.3.1).
- Gossip, forward or reveal `AdmissionKeyRegistration`s, `AdmissionKeyDeregistration`s or `ServiceAgreement`s to any party other than the CO that sent them.
- Modify gossipsub messages in transit.
- Make or enforce decisions about membership, roles, moderation or content, including bans, timeouts, deletes and pin limits; these are enforced by MLS removal and member clients (ARCHITECTURE S2, §5.2.2).
- Sign Space state, channel state, role assignments, moderation records or retention policy (ARCHITECTURE S4).
- Observe, log or retain anything outside the ARCHITECTURE §5 observation budget, except extensions a CO has opted into and the Relay declares in its manifest (ARCHITECTURE S6).

A conformant Relay SHOULD:

- Announce itself on `v1/agora/discovery` with a signed `RelayAd` including all available endpoint URIs.
- Operate a Tor hidden service endpoint to protect operator IP and support Tor-connected clients.
- Maintain peering connections to at least 3 other known Relays.
- Implement gossipsub peer scoring to limit amplification attacks.

Relay federation is permissionless. Any Relay that speaks the protocol may join the mesh and carry the discovery topic; it carries a channel only when that channel's CO registers the channel's admission key with it.

### 10.4.4 Blob Storage and Retrieval

A Relay stores blobs in a content-addressed store keyed by CID (§13.1). "Pin" in this specification means retention in that store under a pin instruction (ARCHITECTURE §6.2); it does not mean pinning on the public IPFS network.

A conformant Relay MUST serve every blob it holds over HTTPS at `GET /v1/agora/blob/{cid}` on the origin of its manifest (§10.2.1). The endpoint is unauthenticated and rate-limited per network address (§11.6), and it MUST send `Access-Control-Allow-Origin: *` so that browser clients can fetch from it directly. A Relay that declares `jmap-sync-v1` also serves the same bytes through JMAP download (§11.8.1). These are the fetch paths for blobs, including `ipfs://` URIs (§10.3.4.5); a client needs no IPFS node or public IPFS gateway.

A client MUST verify that the bytes it receives hash to the requested CID and MUST discard them otherwise. Because every blob is either ciphertext the Relay cannot read or a record a CO chose to publish (§10.4.3), a Relay can serve blobs to any requester without learning anything beyond the ARCHITECTURE §5 observation budget.

A Relay is not required to run an IPFS node, join the IPFS DHT or speak Bitswap. A Relay MAY mirror to the public IPFS network only records a CO has chosen to publish (§10.3.2); it MUST NOT publish other blobs there.

**Upload admission.** A Relay MUST accept a blob upload only when it carries an `Agora-Storage-Auth` authorization (§11.8.2) for a `channelToken` registered with it, signed with that token's registered admission key. It charges the stored bytes to the agreement under which the token is registered and keeps the blob for that agreement's retention window unless it is pinned. This gives blob writes the same member-only admission as envelopes, and the Relay learns no uploader identity.

**Where blobs live.** Relays do not forward, gossip or replicate blobs to each other; a Relay holds only the blobs uploaded to it. A client uploading a blob for a channel SHOULD upload it to every Relay in the channel's relay list (§10.3.5) and MUST upload it to at least one. A client fetching a blob tries the Relays of the channel's relay list in turn. A pin instruction (§11.4) applies only at the Relay that receives it, so a client pinning a blob sends the instruction to each Relay it uploaded to.

### 10.4.5 Takedown Requests

A Relay may receive a takedown request (a legal demand, or a report from a third party) naming a CID it stores. The Relay cannot read the blob or envelope, so it cannot judge the content, and it MUST NOT attempt to decrypt it.

The Relay looks up the `channelToken` under which the CID was stored or pinned and the agreement under which that token is registered, and SHOULD forward the request, with the CID, to the CO at the agreement's `contact` (§10.5.1). The CO identifies the content from its own records and handles it through its moderation process (§4.5). The Relay MAY stop serving the CID and delete it, as a storage decision under its own policy and law; doing so removes one copy and is not a moderation decision (ARCHITECTURE S2). The Relay MUST NOT disclose to the requester anything beyond the ARCHITECTURE §5 observation budget, and does not learn or reveal which Space or member the content belongs to.

### 10.4.6 Envelope History

A Relay holds the recent envelopes of each `channelToken` registered with it, for the `retentionDays` of the agreement under which the token is registered (§10.5.1) or until each envelope's `expiryHint`, whichever is sooner, plus any envelopes pinned under §10.4.3. It serves them to clients through the live protocol and the JMAP sync API (§11.8), keyed by `channelToken` only. Deregistering a key (§10.5.3) stops the Relay from accepting new envelopes for its token; envelopes already held under that token remain readable until their retention ends.

Relay-held envelopes are the recent part of a channel's history (§5.2.5). Older history lives in members' stores and in the CO's archive (§7), not at any Relay. A Relay that drops envelopes early cannot forge or alter any: MLS signatures authenticate every message, and the inner per-sender `seq` (§5.1.1) lets members detect omissions.

### 10.4.7 Token Suspension, Recovery and Retirement

**Token suspension.** A Relay MAY stop admitting envelopes, pin instructions and blob uploads for one registered `channelToken`, for example when the token carries abusive volume or under a legal demand. This is a carriage decision under the Relay's own policy and law, like deleting a copy under §10.4.5, and not a moderation decision (ARCHITECTURE S2). The Relay treats a suspended token as withdrawn (§11.4): it sends `token-withdrawn` to the token's subscribers and answers later requests naming the token with `token-withdrawn`. It MUST notify the CO at the `contact` of the agreement under which the token is registered (§10.5.1), naming the token, the time and the reason. A suspension applies to the token: registering the same token again does not lift it, and the Relay admits a new token that the CO registers after rotating the key (§5.2.2), for example after removing the member responsible. The Relay lifts a suspension at its discretion. Suspension tells the Relay nothing about the channel or its members beyond what it already observes (§10.4.1).

**Recovery from backup.** A Relay that restores its state from a backup, or otherwise loses registration state, MUST NOT reinstate admission key registrations from the backup, because a key deregistered after the backup was taken would be admitted again. It starts with no registrations and answers `unknown-token` for every token (§11.4); clients move to another listed Relay meanwhile (§10.3.5). It MUST notify the CO at the `contact` of each agreement it holds that its registrations were lost, and the registration service then re-registers every current key under that agreement (§10.5.3). Without that notice the periodic re-registration of §10.5.3 restores them within 24 hours. The Relay MAY keep restored envelopes and blobs within their retention and serves them once their token is registered again.

**Retirement.** A Relay that will stop serving MUST set `retiresAt` in its manifest (§10.2.1) and MUST notify the CO at the `contact` of each agreement it holds, both at least 30 days before that time, unless the Relay and a CO have agreed a different notice period out of band for that CO. A CO removes the Relay from its relay lists (§10.3.5) and deregisters its keys there before `retiresAt`. Until `retiresAt` the Relay keeps admitting registered tokens.

---

## 10.5 Service Agreements and Abuse Control

*Binds: both.*

IOs incur real costs: bandwidth, compute, storage, legal exposure, and abuse handling. This section specifies the `ServiceAgreement`, the only binding between a CO and an IO (ARCHITECTURE S7), the registration of channel admission keys under it, and proof-of-work as non-monetary abuse control. Commercial terms between CO and IO are agreed out of band and are outside the protocol.

An IO that carries member traffic MUST hold a `ServiceAgreement` for it, because it admits only envelopes whose admission keys a CO has registered under an agreement (§10.5.3, §10.5.4). Proof-of-work is optional (§10.5.2).

### 10.5.1 Service Agreements

A `ServiceAgreement` is a typed payload envelope (§13.1) of type `urn:agora:type:ServiceAgreement` between a CO billing DID and an IO DID, specifying the service, retention, quotas, SLA terms, and the IO's observation-budget declaration. It names no Space and no channel (ARCHITECTURE §6.1). It is signed per §13.1.1 by both the `provider` DID and the `billing` DID: the envelope `sig` carries one entry for each. An agreement is identified by the CID of its encoded envelope (§13.1).

```json
{
  "serviceType": "relay",
  "provider": "did:web:relay.example.com",
  "billing": "did:key:z6MkBilling...",
  "endpoint": "https://relay.example.com/v1/agora/admission-keys",
  "contact": "mailto:io-liaison@co.example.com",
  "retentionDays": 90,
  "bandwidthTierGbPerMonth": 100,
  "storageQuotaGb": 50,
  "observationBudget": {
    "connectionLogRetentionDays": 7,
    "extensions": []
  },
  "supersedes": null,
  "validFrom": "2026-03-12T00:00:00Z",
  "validUntil": "2027-03-12T00:00:00Z"
}
```

`serviceType` is one of the following. An IO that provides several services to the same CO holds one agreement per service.

| `serviceType` | IO | Receives admission key registrations |
|---|---|---|
| `relay` | Relay (§10) | Yes |
| `sfu` | SFU (§6.6) | Yes |
| `sequencer` | Sequencer (§14.4) | Yes |
| `turn` | TURN server (§6.11) | No |
| `push-proxy` | Push notification proxy (§11.7) | No |

`provider` is the IO's DID; for a Relay it is the manifest's `relayDID`. `endpoint` is the URL at which the IO accepts admission key registrations (§10.5.3); for a Relay it equals the manifest's `endpoints.admissionKeys`. It is absent for service types that receive no registrations. `contact` is a `mailto:` or `https:` URI at which the IO reaches the CO about abuse and takedown requests (§10.4.5) and about token suspension, lost registrations and retirement (§10.4.7); it MUST NOT name a Space.

`retentionDays` is how long the IO keeps envelopes and blobs (`relay`) or stamped log entries (`sequencer`) of the tokens registered under the agreement; it is absent for other service types. `storageQuotaGb` and `bandwidthTierGbPerMonth` are the quotas the IO enforces for this agreement (§10.4.3).

`billing` is a DID the CO dedicates to agreements. It MUST NOT appear in Space state, SpaceAds, directory documents, or any other record that identifies a Space. A CO MAY use one billing DID for all of its Spaces; doing so is what gives each Space its anonymity set at the IO (ARCHITECTURE §5 item 6).

The agreement is private between the CO and the IO. It MUST NOT be gossiped, stored in Space state, or published. Both parties keep the fully signed agreement; how they exchange it for signing is out of band. Multiple concurrent agreements (multiple Relays serving the same CO) are valid and encouraged for redundancy.

`observationBudget` records the connection-log retention (ARCHITECTURE §5 item 1) and any opt-in observation-budget extensions (ARCHITECTURE S6) the CO has agreed to. A Relay holds one manifest and may hold many agreements, so its manifest (§10.2.1) MUST declare a `connectionLogRetentionDays` no lower than the highest value across its agreements and `extensions` listing every extension any of its agreements enables. For the traffic of each agreement the IO MUST NOT exceed that agreement's values.

**Lifecycle.** Admission key registrations (§10.5.3) belong to the agreement under which they were made and lapse with it. To renew an agreement, or to move it to a new billing DID after rotation or suspected compromise of the billing key, the CO and the IO sign a new agreement whose `supersedes` member holds the CID of the agreement it replaces (`null` otherwise). From the moment the IO signs a superseding agreement it MUST reject new registrations under the superseded one; keys registered under the superseded agreement remain admitted for one hour, then lapse. Within that hour the CO registers every current admission key under the new agreement. A stolen billing key therefore lets its holder register or deregister keys under the CO's agreement, which spends quota or denies service, only until the CO and IO sign a superseding agreement; it never lets anyone read traffic.

Relays publish their service tiers in their `RelayAd`, a typed payload envelope of type `urn:agora:type:RelayAd` gossiped on `v1/agora/discovery` (§10.3.1). Its body is:

```json
{
  "did": "did:web:relay.example.com",
  "manifestURL": "https://relay.example.com/.well-known/agora-relay",
  "endpoints": {
    "webTransport": "https://relay.example.com/v1/agora/wt",
    "webSocket":    "wss://relay.example.com/v1/agora/ws",
    "onion":        "ws://examplerelay3xyzabc.onion/v1/agora/ws",
    "jmapSync":     "https://relay.example.com/v1/agora/jmap"
  },
  "serviceTiers": [
    {
      "id": "hobbyist",
      "retentionDays": 7,
      "bandwidthTierGbPerMonth": 10
    },
    {
      "id": "standard",
      "retentionDays": 30,
      "bandwidthTierGbPerMonth": 100
    },
    {
      "id": "enterprise",
      "retentionDays": 365,
      "bandwidthTierGbPerMonth": 1000
    }
  ],
  "ts": "2026-03-12T00:00:00Z"
}
```

A `RelayAd` body carries exactly these members. `did` is the manifest's `relayDID`. `manifestURL` is where the Relay Manifest (§10.2.1) is served. `endpoints` uses the member names of the manifest's `endpoints` and MUST list every client-facing endpoint the manifest lists (`webTransport`, `webSocket`, `onion` and `jmapSync`), including overlay-internal URIs (§10.1); relay-to-relay and CO-facing endpoints (`peerAPI`, `gossipQuic`, `admissionKeys`) are left out. `serviceTiers` lists the tiers the Relay offers under `ServiceAgreement`s. `ts` is the publication time. Where a `RelayAd` and the manifest disagree, the manifest governs. A `RelayAd` is signed per §13.1.1 by the Relay (`did`).

### 10.5.2 Proof-of-Work Spam Deterrence

Channels that want spam deterrence MAY require proof-of-work. A channel declares this with an optional `powPolicy` member of its entry in Space state (§3.3):

```json
"powPolicy": { "@type": "PowPolicy", "scheme": "pow", "difficulty": 18 }
```

`difficulty` is the number of leading zero bits required. A client sending a message computes a `nonce` of 8 to 32 bytes such that `SHA256(signed || nonce)` has at least `difficulty` leading zero bits, where `signed` is the exact byte string held in the envelope's `signed` field (§5.2.2), and places the result in the `powProof` member of the routing envelope, outside `signed`:

```cddl
PowProof = {
  "nonce":      bstr .size (8..32),
  "difficulty": uint
}
```

`powProof` is not covered by `admissionSig` and need not be: it is bound to the `signed` bytes it was computed over, so it cannot be moved to another envelope. The client computes it after `signed` is fixed; the envelope `id`, the CID of the complete encoded envelope (§5.2.2), covers it. Connection-level proof-of-work (`AdmissionChallenge`, §11.6) is separate and uses its own challenge.

A Relay declares its own minimum difficulty in the `minPowDifficulty` member of its manifest (§10.2.1). The Relay verifies the PoW before forwarding against that value and MUST NOT require more than it declares. The Relay cannot map a `channelToken` to a channel's `PowPolicy` (§10.4.2), so member clients enforce the channel's difficulty and drop envelopes that do not meet it. Difficulty 18 requires about 262,000 SHA-256 operations, roughly 10 to 50 ms on a modern CPU: imperceptible to a human sender, but economically prohibitive for bulk message flooding.

**HTTP endpoints.** A CO HTTP endpoint that requires proof of work before serving a request, such as a `KeyPackageEndpoint` host (§4.6.3), an invite endpoint resolving open-link tokens (§4.7) or a sequencer (§14.4), uses the following challenge format. It answers the request with HTTP 429 and an `Agora-PoW-Challenge` response field, a Dictionary structured field (RFC 9651):

```
HTTP/1.1 429 Too Many Requests
Agora-PoW-Challenge: challenge=:RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=:, difficulty=20, expires=30
```

`challenge` is a Byte Sequence of 32 random bytes, `difficulty` an Integer from 0 to 64, the required leading zero bits, and `expires` an Integer, the seconds within which the client must answer. The client chooses a nonce of 8 to 32 bytes such that SHA-256(`challenge` || nonce) has at least `difficulty` leading zero bits, counted from the most significant bit of the first byte of the hash, as for the connection-level proof of §11.6. It repeats the request with an `Agora-PoW` request field, also a Dictionary structured field:

```
Agora-PoW: challenge=:RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=:, nonce=:AAAAAAAXBKY=:
```

The endpoint MUST accept each `challenge` at most once and only within `expires` seconds of issuing it, and answers a request whose proof is missing, invalid, expired or reused with a new challenge as above. The proof carries no identity and is independent of any authentication the endpoint requires (§3.5).

### 10.5.3 Admission Key Registration

A registration service registers each channel admission public key (§5.2.2) with every IO that holds a `ServiceAgreement` with it whose `serviceType` receives registrations (§10.5.1), under that agreement. For channels of a Space the registration service is run by the Space's CO beside its Space endpoint (§3.4), under the CO's agreements; for a shared channel, by the home Space's CO (§8.6); for a DM group or a self-group (§2.6), by the initiator's identity host (§4.6). An identity host registers under the agreements of the party that runs it. An employer provisioning service (§2.5) registers under the employer CO's agreements and billing DID. An identity host that an individual chose holds its own `ServiceAgreement`s under its own billing DID and registers under those, acting as the CO for this purpose. The IOs holding the agreements a registration service uses are the relays it lists to members (§10.3.5). Registrations travel only over HTTPS from the registration service to the IO. They are never gossiped and no client or member sends them.

**Request.** The registration service sends `POST <endpoint>`, where `<endpoint>` is the agreement's `endpoint`, with `Content-Type: application/cbor` and a body that is one encoded typed payload envelope (§13.1) signed per §13.1.1 by the agreement's `billing` DID. The envelope is of one of two types.

`urn:agora:type:AdmissionKeyRegistration` tells the IO to admit envelopes signed by the listed keys:

```json
{
  "agreement": "bafkrei...",
  "ts": "2026-10-16T12:00:00Z",
  "keys": [
    {
      "channelToken": "base64url...",
      "keyEpoch": 3,
      "admissionPublicKey": "base64url..."
    }
  ]
}
```

`urn:agora:type:AdmissionKeyDeregistration` tells the IO to stop admitting envelopes for the listed tokens:

```json
{
  "agreement": "bafkrei...",
  "ts": "2026-10-16T12:05:00Z",
  "channelTokens": ["base64url..."]
}
```

`agreement` is the CID of the `ServiceAgreement` (§10.5.1). `ts` is the sending time, RFC 3339 in UTC. `channelToken` is the 32-byte token (§5.2.2) and `admissionPublicKey` the 32-byte Ed25519 public key (RFC 8032), each in base64url without padding (RFC 4648 §5). `keyEpoch` is the key's rotation counter (§5.2.2); an IO whose signed admission messages carry `keyEpoch` (for example an SFU, §6.6) checks it against the registered value. A request lists 1 to 1000 keys or tokens. The bodies carry nothing that identifies a Space, channel, DM group or member.

**Processing.** The IO MUST, before applying a request:

1. verify the signature per §13.1.1 with the agreement's `billing` DID as the required signer;
2. check that it holds the agreement, signed by itself and by `billing`, that the current time is within `validFrom` and `validUntil`, that the agreement is not superseded (§10.5.1), and that its `serviceType` receives registrations;
3. check that `ts` is within 300 seconds of its clock and, for every listed token, later than the `ts` of the last request it accepted that listed the same token under the same agreement, so that a replayed request cannot restore a deregistered key.

The IO applies a valid request entirely or not at all. Registering a token already registered under the same agreement with the same key, and deregistering a token not registered, succeed without change. A token is registered with at most one key; the IO MUST reject a registration that lists a token already registered with a different key.

**Response.** On success the IO returns HTTP 204. On failure it returns the status below with a JSON body `{ "error": "<code>" }` and changes nothing:

| Status | `error` | Condition |
|---|---|---|
| 400 | `malformed` | Body is not a decodable envelope of one of the two types, a field is missing or badly encoded, or the list is empty or longer than 1000 |
| 401 | `bad-signature` | `sig` is missing or invalid, or its signer is not the agreement's `billing` DID |
| 403 | `agreement-invalid` | Agreement unknown, not yet valid, expired or superseded, or its `serviceType` receives no registrations |
| 409 | `stale` | `ts` outside the 300-second window, or not later than a previous accepted request for a listed token |
| 409 | `token-conflict` | A listed token is already registered with a different key |
| 429 | `rate-limited` | The IO's rate limit for the agreement is exceeded |

**When the CO registers.** The registration service registers:

- a new channel's or DM group's first admission key before serving it to members;
- each rotated key (a new `keyEpoch`, §5.2.2) with every IO, before serving it to members;
- every current key with an IO that it engages, and under every renewed or superseding agreement (§10.5.1), before listing that IO to members (§10.3.5);
- every current key with an IO that reports lost registrations (§10.4.7), without delay.

It MUST also re-send every current key to each IO at least once every 24 hours. Re-registration of an unchanged key succeeds without change, so the re-send costs the IO nothing when its state is intact and restores a Relay that lost its registrations (§10.4.7).

It SHOULD batch registrations for new channels and DM groups and add random delay, so that registration timing does not reveal when a particular Space, channel or DM group was created. It sends registrations for a rotation that follows a removal without added delay, since a delay would lengthen the removed member's window.

**When the CO deregisters.** After a rotation, the registration service deregisters the previous key once members have had time to move to the new token, after a grace period RECOMMENDED to be 300 seconds. Until then a removed member that held the previous key can still post envelopes the IO admits, though it cannot read the channel (MLS). The registration service also deregisters every key of a channel or DM group that is deleted, and every key at an IO it stops using. If the registration service is unreachable, IOs keep admitting the keys last registered, and members keep using the last key they hold.

### 10.5.4 Relay Admission

A Relay admits an envelope, whether it arrives in a live protocol `Publish` (§11.4), on a channel gossip topic or in a `GossipBatch` (§10.2.2), only if all of the following hold:

1. the `channelToken` inside the envelope's `signed` bytes is registered with the Relay under a current `ServiceAgreement` (§10.5.3);
2. `admissionSig` is a valid Ed25519 signature (RFC 8032) over the exact bytes of the envelope's `signed` field under the admission public key registered for that token; the Relay verifies these bytes as received and never re-encodes them;
3. if the Relay's `minPowDifficulty` is greater than 0, `powProof` meets it (§10.5.2);
4. the envelope is within the size and rate limits of §11.6.

The Relay drops an envelope that fails any check; on the live protocol it answers with the `Error` code §11.4 assigns. It reads nothing else from the envelope beyond what routing and retention need (`channelToken` and `expiryHint`). The same registrations admit `PinInstruction`s (§11.4) and blob uploads (§10.4.4), each signed with the token's admission key. Subscribing needs no proof, but a Relay delivers nothing on, and sends no push wake-ups for, a token with no registered key (§11.4, §11.7).

Every current member holds the same admission key, so a valid `admissionSig` shows that the sender holds the key registered for the token, that is, it is a current member or was one before the latest rotation, and does not show which member. Removals take effect at the Relay when the CO rotates the key and deregisters the old one (§10.5.3); the Relay keeps no DID ban list (ARCHITECTURE §6.2).

SFUs (§6.6) and sequencers (§14.4.3) admit traffic by the same rule against the keys registered under their own agreements.
