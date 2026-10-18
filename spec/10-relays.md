# 10. Relays, Federation, and Discovery

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 584–1065, 2920–2994, 3054–3133, 3188–3207 (§3.4–§3.5, §4, §11, §12 intro, §12.2, §12.4).

## 10.1 Deployment Topologies

*Binds: IO.*

Agora is transport-agnostic at the application layer. The following deployment topologies are explicitly supported:

**Public internet (default).** Relays are clearnet HTTPS/WSS servers with public IPv4 and/or IPv6 addresses. Clients connect over the public internet. This is the baseline configuration assumed throughout this specification unless otherwise noted.

**Tor hidden service.** A relay MAY operate as a Tor v3 hidden service, publishing a `.onion` address in its `RelayAd` alongside or instead of a clearnet endpoint. Clients connecting via Tor MUST use the WebSocket transport (§11.2); WebTransport requires QUIC over UDP and is unavailable over Tor.

**Private overlay (Tailscale / WireGuard / Headscale).** A relay MAY operate exclusively on a WireGuard-based overlay network. The relay's `RelayAd` lists overlay-internal hostnames or `100.x.x.x` addresses; these are only resolvable inside the overlay. This is the recommended topology for private organizational deployments where all members are already on a common overlay. A fully self-contained deployment (relay + Selective Forwarding Unit (SFU) + TURN + Headscale, all on-premise) has zero dependency on any external infrastructure.

**Dual-stack (clearnet + overlay).** A relay MAY publish both clearnet and overlay endpoints. Clients on the overlay prefer the overlay path; external clients use the clearnet path. Both sets of clients share the same Space state and message history.

**Managed / SaaS.** A relay operator (the "managed provider") provisions and operates a dedicated Agora relay fleet on behalf of a customer. Each customer receives their own isolated deployment (separate relay processes, separate database, separate blob store), not a shared multi-tenant instance. The customer controls, or delegates control of, the DNS name that roots their deployment; the managed provider's infrastructure hosts it (typically via CNAME or DNS delegation). The managed provider's identity appears as `operatorDID` in each relay manifest (§10.2.1), but `relayDID` is anchored to the customer's DNS domain, not the provider's. This preserves namespace ownership: if the customer migrates to self-hosted, their DNS name and all derived identities (`did:webvh:<SCID>:<customer-domain>:users:...`) are portable without re-enrollment. A `did:webvh` identity (§2.1) is also portable to a different domain, because its SCID and signed document history move with it. `operatorDID` and `relayDID` are Infrastructure Operator (IO) keys and are distinct principals from every Communications Operator (CO) key, even where one entity holds both roles (ARCHITECTURE §2.4).

**IPv6.** All relay endpoints SHOULD support IPv6. Relay URIs MUST use bracket notation for IPv6 address literals (`wss://[2001:db8::1]/v1/agora/ws`). ICE gathers both IPv4 and IPv6 host candidates; dual-stack clients race both address families.

### 10.1.1 Discoverability and DNS Namespace Root

A deployment's ability to participate in the public Agora mesh depends on whether it has a DNS root:

**Discoverable deployments** (public internet, managed/SaaS, dual-stack) SHOULD be anchored to a DNS name. That name is the root of the deployment's identity namespace: relay DIDs are `did:web:<domain>`, organizational user DIDs are normally `did:webvh:<SCID>:<domain>:users:...`, and the relay manifest is served at `https://<domain>/.well-known/agora-relay`. Any two deployments with distinct DNS names have non-overlapping identity namespaces by construction; no registry or authority is required to prevent conflicts.

**Non-discoverable deployments** (private overlay, air-gapped, Tor-only) have no DNS root requirement. Relay DIDs are `did:key:...`; user DIDs are `did:key:...` or `did:webvh` anchored to an internal-only domain. These deployments cannot join the public gossipsub mesh or federate with external organizations. This is an explicit architectural trade-off.

No registry, whitelist, or certificate authority governs which DNS names may root an Agora deployment. DNS ownership is the sole claim to a namespace.

## 10.2 Relay-to-Relay Peering and Authentication

*Binds: IO.*

Relays form a gossipsub mesh with each other for fan-out. This section specifies how relays discover each other, authenticate, establish trust levels, and maintain the mesh. The model uses a well-known manifest endpoint, RFC 9421 HTTP Message Signatures for relay-to-relay authentication, graduated trust levels, and zero-configuration bootstrap from any single known peer.

**Transport for relay-to-relay communication.** libp2p supports multiple transports. Relays SHOULD prefer **QUIC-v1** (`/ip4/.../udp/.../quic-v1` multiaddr) for gossipsub connections, with TCP (`/ip4/.../tcp/...`) as the fallback for environments where UDP is blocked. QUIC eliminates head-of-line blocking between gossip streams and removes TCP from the relay-to-relay data path entirely.

The Peer API is served over HTTP/3 with an HTTP/1.1 and HTTP/2 fallback (§10.2.2). A relay SHOULD serve everything on port 443: its client endpoints and Peer API over TCP and UDP 443, and libp2p QUIC on UDP 443, sharing one QUIC listener with HTTP/3 and telling connections apart by their TLS ALPN (`h3` or `libp2p`). An operator MAY use other ports; every endpoint, multiaddr, and SRV record carries its port. Relay operators that cannot expose UDP MAY operate TCP-only, but MUST declare this in their manifest `capabilities` by omitting `gossipsub-quic-v1`.

### 10.2.1 Relay Manifest

Every relay MUST publish a **relay manifest** at a well-known URL:

```
GET /.well-known/agora-relay
```

The manifest is a typed payload envelope (§13.1) of type `urn:agora:type:RelayManifest` whose `body` is the JSON object below, served as its encoded envelope with `sig` present and `Content-Type: application/cbor`. It is the relay's authoritative self-declaration and the single source of truth for its identity, capabilities, endpoints, and signing keys. Any relay that can reach this URL can bootstrap a peering relationship without out-of-band coordination.

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
    "gossipQuic":      "/ip4/203.0.113.42/udp/443/quic-v1"
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

The manifest is signed per §13.1.1 by `relayDID`, with a key listed both in `keys` and in the DID document of `relayDID`. Peer relays and clients MUST verify this signature before accepting the manifest.

Each entry in `keys` has a `status` of `active`, `deprecated` (still accepted during a rotation overlap, §10.2.6), or `revoked` (compromised, §12.12). A verifier MUST NOT accept any signature, including the manifest's own, made with a key marked `revoked`.

`endpoints.admissionKeys` is the URL at which the relay accepts admission key registrations from COs (§10.5.3).

`observationBudget` declares what the relay retains beyond transient routing. `connectionLogRetentionDays` is the retention of network-layer connection metadata (ARCHITECTURE §5 item 1), as set by the relay's `ServiceAgreement`s (§10.5.1). `extensions` lists every opt-in extension to the ARCHITECTURE §5 observation budget the relay has enabled; it MUST be empty unless a CO has opted in (ARCHITECTURE S6). A relay MUST NOT observe, log, or retain anything not covered by ARCHITECTURE §5 or a declared extension.

`minPowDifficulty` is the minimum proof-of-work difficulty, in leading zero bits, that the relay requires on each `RoutingEnvelope` (§10.5.2). `0` means the relay requires no proof-of-work, and a relay that omits the member requires none.

`retiresAt` is optional. A relay that will stop serving sets it to the RFC 3339 UTC time at which it stops (§10.4.7); a relay without a planned end omits it.

`knownPeers` lists the relay's peers, including any peer marked unreachable within the last 7 days (§10.2.6). This serves as a mesh map: a new relay fetching any existing relay's manifest obtains a list of further relays to contact, enabling rapid mesh joining without a central directory server.

`capabilities` is an array of capability strings declaring what features this relay supports:

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

**Relay DID and DNS binding.** For relays operating on the public internet (§10.1), `relayDID` SHOULD be a `did:web` anchored to the relay's DNS domain rather than a `did:key`:

```json
"relayDID": "did:web:relay.example.com"
```

The relay MUST serve a conformant DID document at `https://relay.example.com/.well-known/did.json`. This creates a verifiable binding: the manifest at `/.well-known/agora-relay` is signed by `relayDID` with a key declared in that DID document, and the DID document SHOULD include a `service` entry pointing back to the manifest URL. Any peer that resolves `did:web:relay.example.com` can verify that the key material and the DNS domain are controlled by the same entity.

For relays operating exclusively on a private overlay, Tor hidden service, or air-gapped network, where no public DNS name exists or is desired, `relayDID` MAY be `did:key:...`. These relays do not participate in the public mesh and do not require DNS binding.

**Operator vs. customer identity.** The `operatorDID` field records the identity of the party that operates the relay infrastructure. For self-hosted deployments, `operatorDID` and the relay's controlling entity are the same. For managed/SaaS deployments (§10.1), they differ: `relayDID` is anchored to the customer's DNS domain; `operatorDID` is the managed provider's DID. This distinction is relevant to legal exposure (§12.3).

### 10.2.2 Peer API

Relays expose a **Peer API** at the URL declared in `endpoints.peerAPI` for relay-to-relay operations. Every Peer API request except `manifest` and `health` (which are unauthenticated) carries an RFC 9421 HTTP Message Signature (§10.2.3).

Relays SHOULD serve the Peer API over HTTP/3 and advertise this via `Alt-Svc: h3=":443"` (or the appropriate port) on all HTTP responses. A connecting relay that receives an `Alt-Svc` header SHOULD upgrade to HTTP/3 for subsequent requests. Relays MUST continue to accept HTTP/1.1 and HTTP/2 over TLS on the same `peerAPI` URL for peers that cannot use QUIC.

```
GET  /v1/agora/peer/manifest
     Returns this relay's current RelayManifest.
     Unauthenticated.

POST /v1/agora/peer/announce
     A peer relay announces itself, or introduces a third relay.
     Body: the announcing relay's RelayManifest, or a
     RelayPeerAnnouncement (Peer gossip, below).
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

GET  /v1/agora/peer/blob/{cid}?token=<channelToken>
     Pull of one blob (§10.4.4). The requester sets token to the token
     under which it will store the blob; the responder does not check it.
     Response: 200 with the blob bytes, or 404 if this relay does not hold
     the CID. Authenticated.

POST /v1/agora/peer/blob?token=<channelToken>
     Eager replication of one blob held under channelToken (§10.4.4).
     Body: the blob bytes, Content-Type application/octet-stream.
     Header: Agora-Storage-Auth of the original upload, unchanged (§11.8.2).
     The receiving relay verifies admissionSig against the key registered
     for channelToken and sha256 against the body, and does not check
     expires or nonce.
     Response: 201 stored or already held, 403 if the header is missing or
     fails these checks, 404 if channelToken is not registered here, 507 if
     the agreement's storage quota would be exceeded. Authenticated.
```

`<channelToken>` in these paths is the token in base64url without padding (RFC 4648 §5).

A `GossipBatch` carries messages exactly as they travel on the libp2p mesh (§10.3.1). The receiving relay processes each entry as if it had arrived on that topic from the sender, subject to the same rules, including §10.5.4 for channel topics:

```cddl
GossipBatch = [* GossipEntry]
GossipEntry = {
  "topic": tstr,   ; a topic string of §10.3.1
  "data":  bstr    ; the gossip message data of §10.3.1
}
```

### 10.2.3 Relay-to-Relay Authentication

All relay-to-relay requests (except unauthenticated endpoints) use **RFC 9421 HTTP Message Signatures** with Ed25519. The requesting relay signs each HTTP request using an active or deprecated key (§10.2.6) from its manifest. The receiving relay verifies the signature against the requesting relay's manifest fetched from `/.well-known/agora-relay`.

**Profile.** The request carries one signature with label `sig1` in the `Signature-Input` and `Signature` fields. Its signature parameters are:

- `keyid`: the `id` of the signing key in the requesting relay's manifest `keys`, a DID URL whose DID is the requesting relay's `relayDID` (for example `did:web:relay.example.com#key-1`). The receiving relay takes the requester's identity from this DID and fetches its manifest from the DID's domain (`did:web`) or from the peer's known `manifestURL`.
- `alg`: `"ed25519"`.
- `created`: the signing time, integer seconds since the Unix epoch.
- `nonce`: a random 128-bit value, base64url without padding.

**Covered components.** The signature covers these components (RFC 9421 §2):

```
"@method"
"@target-uri"
"@authority"
"content-digest"      (requests with a body; RFC 9530, algorithm sha-256)
```

The receiving relay MUST verify `Content-Digest` against the body before acting on it.

**Replay prevention.** `created` MUST be within 300 seconds of the receiving relay's clock. `nonce` MUST NOT have been seen from the same `keyid` in the previous 600 seconds (the receiving relay maintains a nonce cache with a 600-second TTL). The receiving relay MUST reject a request that violates either condition with HTTP 401.

**Manifest caching.** Receiving relays cache peer manifests for 1 hour. On a cache miss or expiry, the relay fetches a fresh manifest before verifying the request. If the fetch fails, the relay retries once after 5 seconds before rejecting the request with HTTP 503.

**Reference implementations for RFC 9421.** [`httpbis-message-signatures`](https://github.com/nicowillis/httpbis-message-signatures) (JS), [`httpsig`](https://github.com/bblfish/httpSig) (Scala/JVM reference), [`go-http-signature`](https://github.com/go-fed/httpsig) (Go).

### 10.2.4 Trust Levels

Relay-to-relay trust is graduated. Trust level determines which Peer API operations a relay is permitted to invoke and what gossip rate limits apply. Trust level is local state; each relay maintains its own assessments independently. It is never gossiped or shared.

| Level | Name | Criteria | Permissions |
|---|---|---|---|
| 0 | Unknown | No prior contact | Manifest fetch only; `announce` accepted for evaluation |
| 1 | Seen | Valid manifest, valid signature, first contact | `announce`, `health`; gossip rate-limited to 10 msg/s; blob pull, and blob push for tokens registered with the receiving relay (§10.4.4) |
| 2 | Known | 7+ days of sustained peering without incident | Full gossip; `peers` accessible; 1000 msg/s |
| 3 | Trusted | Explicitly operator-configured | Full access; relaxed rate limits; no gossip throttling |

Level 3 is set via local operator configuration and is appropriate for relays operated by the same organization or well-known partner organizations.

**Trust degradation.** A relay downgrades a peer that submits invalid signatures, sends malformed gossip, or repeatedly exceeds rate limits to Level 0 and blocks its DID for 24 hours. Repeated violations (3 or more incidents within 7 days) result in permanent operator-managed blocklisting.

### 10.2.5 Bootstrap: Joining the Mesh

A new relay with no existing peers joins the gossipsub mesh using any of the following methods, attempted in parallel:

**Method 1: Known peer URL.** The operator provides one or more peer relay URLs in the startup configuration. The new relay fetches `/.well-known/agora-relay` from each, verifies the manifest signature, sends `POST /v1/agora/peer/announce` with its own manifest, and on acceptance fetches `GET /v1/agora/peer/peers` to discover further relays.

**Method 2: Directory document.** The relay fetches any Agora relay directory document (§10.3.4.1) and contacts each listed relay using Method 1.

**Method 3: DNS-SD.** The relay queries both `_agora-relay._udp.<domain>` (QUIC, preferred) and `_agora-relay._tcp.<domain>` (TCP fallback) SRV records:

```
_agora-relay._udp.example.com. SRV 10 0 443  relay.example.com.
_agora-relay._tcp.example.com. SRV 20 0 443  relay.example.com.
_agora-relay._udp.example.com. TXT "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"
_agora-relay._tcp.example.com. TXT "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"
```

Each SRV record has a TXT record at the same owner name (RFC 6763 §6) carrying the relay's DID and manifest URL.

Lower SRV priority value means higher preference; QUIC (UDP) is preferred. Relays SHOULD publish both records. Relays that cannot expose UDP MUST publish only the TCP record.

**Method 4: IPNS fallback.** The relay resolves an IPNS name configured by the operator (for example `/ipns/bootstrap.example.com`) for a signed bootstrap list. This is the last resort.

A relay is considered mesh-joined when it has Level 1 or higher trust with at least 3 peers and is participating in gossipsub fan-out. It SHOULD continue discovering peers until it has at least 6 active connections (gossipsub's default mesh degree `D`).

### 10.2.6 Mesh Maintenance

**Heartbeat.** Relays MUST poll `GET /v1/agora/peer/health` from each peer every 60 seconds. A peer that returns `unhealthy` or fails to respond for 3 consecutive checks (180 seconds total) is marked unreachable. Its gossipsub connection is dropped; it remains in `knownPeers` for 7 days before removal, in case it recovers.

**Manifest refresh.** Relays re-fetch peer manifests every hour to detect key rotation and endpoint changes. Relays treat a manifest whose `sig` no longer verifies as a trust failure and downgrade the peer to Level 0 pending re-verification.

**Key rotation overlap.** When rotating its signing key, a relay MUST publish both the old and new keys in its manifest with a minimum 48-hour overlap, marking the old key with `"status": "deprecated"`. Peer relays accept signatures from deprecated keys during this overlap window. A relay instead marks a key whose private half is compromised `"status": "revoked"`, with no overlap; peer relays MUST reject every request signed with a key the manifest marks `revoked` (§12.12).

**Peer gossip.** When a relay discovers a new valid peer, it SHOULD share that peer's `{ relayDID, manifestURL }` with its Level 2+ peers by sending each of them a `RelayPeerAnnouncement` in a `POST /v1/agora/peer/announce` request over the Peer API. The announcement is not carried on any gossip topic (§10.3.1). Its body is:

```json
{
  "@type": "RelayPeerAnnouncement",
  "relayDID": "did:key:z6MkNewRelay...",
  "manifestURL": "https://newrelay.example.com/.well-known/agora-relay",
  "announcedBy": "did:key:z6MkExistingRelay...",
  "ts": "2026-03-12T00:00:00Z"
}
```

The announcement is a typed payload envelope (§13.1) signed per §13.1.1 by `announcedBy`, which is the relay sending the request. Receiving relays verify the signature, independently fetch the new relay's manifest, and decide whether to initiate peering. The announcement is a hint, not an authorization.

---

## 10.3 Discovery

*Binds: both.*

### 10.3.1 Gossip Protocol

Agora uses **libp2p gossipsub v1.1** among relays for peer discovery, voluntary CO and relay advertisements, and live delivery of token-keyed ciphertext envelopes, including MLS Commits and Proposals, which travel in the channel's own envelopes.

Each gossipsub **topic** maps to a specific scope:

| Topic pattern | Purpose | Message data |
|---|---|---|
| `v1/agora/discovery` | SpaceAds (§10.3.2) and RelayAds (§10.5.1) | One encoded typed payload envelope (§13.1) with `sig` present |
| `v1/agora/channel/<channelToken>` | Per-channel envelopes, including ephemeral presence and typing events | One encoded routing envelope (§5.2.2), exactly as the client published it |

`<channelToken>` is the token in base64url without padding (RFC 4648 §5).

**Channel topics.** A relay subscribes to, forwards, and caches `v1/agora/channel/<channelToken>` only for a `channelToken` registered with it under a current `ServiceAgreement` (§10.5.3). It MUST NOT publish to, forward, or cache a channel topic for any other token, and drops envelopes for such tokens whether they arrive from a client or a peer. The mesh for a channel topic therefore consists of the relays the channel's CO has registered the token with; a relay without a registration never sees the channel's traffic or any registration data. Every relay on a channel topic applies the admission rule of §10.5.4 to each envelope.

**Discovery topic.** Every mesh relay MAY carry `v1/agora/discovery`. Only SpaceAds and RelayAds travel on it. Clients do not publish on any gossip topic. They send envelopes to a relay in a live protocol `Publish` (§11.4). Clients MUST NOT send DID-signed records about themselves (profiles, recovery assertions, device revocations, or any other user record) over a relay connection. A user is discovered through the DID document or Pkarr record (§2.1, §10.3.4.6), key recovery is recorded in the DID log (§2.4), and a user tells its groups to re-resolve its DID and profile with an `urn:agora:type:IdentityChanged` MLS application message (§5.2.3).

**Parameters.** Relays MUST use the gossipsub signature policy `StrictNoSign`: messages carry no libp2p author, sequence number, or signature, so no peer ID is attached to an envelope and peers with different policies do not drop each other's messages. The message ID is SHA-256 of the message data. The maximum message data size is 65,536 bytes, the `maxEnvelopeBytes` of §11.8.3. Mesh degree parameters are `D = 6`, `D_low = 4`, `D_high = 12`, and the heartbeat interval is 1 second, the gossipsub v1.1 defaults.

No topic carries a Space CID, MLS group ID, `channelID`, or other Space identifier (ARCHITECTURE S1). Space state, moderation records, and other Space-level records reach members from the CO's Space endpoint and in-band MLS notifications (§3.4); Welcomes go to the invitee's `KeyPackageEndpoint` (§4.6).

The `v1/` prefix is the gossip protocol version for that topic family. A future breaking change to message framing on a topic introduces a `v2/` prefix. Relays MUST subscribe to all versions of topics they serve. Clients never choose a topic version: they send envelopes to a relay in a live protocol `Publish`, whose version is negotiated in the hello exchange (§11.4, §11.6), and the relay publishes them on the topic versions it serves. During a version transition period, relays bridge messages between `v1/` and `v2/` topic variants for the same channel.

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

`spaceEndpoint` lists the CO's Space endpoint URLs (§3.4). `relayHints` lists the client endpoints of the relays that carry the Space's public channels (§10.3.5). Entries MAY be `.onion` addresses, clearnet HTTPS/WSS URIs, overlay-internal hostnames, and IPv6 address literals.

**Signing rule.** Every discovery record is signed by the party it describes: the CO for Space records and the relay for relay records. `advertisedBy` is the CO DID that signs the Space's state (ARCHITECTURE S4), and the SpaceAd is signed per §13.1.1 by `advertisedBy`. Clients MUST discard a SpaceAd whose signature does not verify against `advertisedBy`. There are no user discovery records (§10.3.1).

Only public Spaces advertise. A CO MUST NOT publish a SpaceAd or directory entry for a private Space; private Spaces are reached only by invitation (§4.3).

A SpaceAd is a voluntary CO publication. Relays forward and cache SpaceAds and RelayAds on `v1/agora/discovery` like any other gossip message. A relay MUST NOT author or modify a Space record, MUST NOT forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd, and MUST NOT publish lists of the Spaces it serves.

### 10.3.3 Relay Discovery Bootstrap

To bootstrap into the gossip network, a client needs at least one known peer. Agora supports the following bootstrap mechanisms, attempted in order:

1. **Directory sources.** user-configured URLs serving `RelayDirectory` or `SpaceDirectory` documents (§10.3.4); the primary bootstrap mechanism in practice.
2. **Previously cached relay list.** Relays successfully contacted in a prior session, stored locally with a staleness TTL of 7 days.
3. **Mainline DHT.** Relays announce themselves on the BitTorrent Mainline DHT (BEP-5) under a well-known infohash; clients perform a `get_peers` lookup to find announcing relays (§10.3.4.6).
4. **DNS-SD.** `_agora-relay._udp` and `_agora-relay._tcp` SRV and TXT records under a configured domain, including overlay-internal DNS (§10.2.5).

### 10.3.4 Directory Documents

A **directory document** is a static file served at any reachable URL. It is a typed payload envelope (§13.1) whose `type` is `urn:agora:type:` followed by the document's `@type` (`RelayDirectory`, `SpaceDirectory`, or `AgoraDirectory`) and whose `body` is the JSON object shown below; the file holds the encoded envelope, with `sig` present when the directory is signed. A directory lists Spaces, relays, or both, and MAY include references to other directory documents by URL. Users configure one or more directory source URLs in their client. Clients fetch and merge all configured sources on startup and refresh on a configurable interval (default: 1 hour).

Directory documents require no special server infrastructure. A file committed to a public GitHub repository and served via `raw.githubusercontent.com` or GitHub Pages is a valid directory source. So is an IPFS CID, a Cloudflare R2 bucket, a `.onion` URL, or any HTTPS endpoint returning the encoded envelope.

#### 10.3.4.1 Relay Directory

A `RelayDirectory` lists relays available for client connection:

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

`ttl` is the number of seconds after which the client should re-fetch the document. `includes` is a list of other directory document URLs whose contents are merged into this one; clients MUST limit include recursion depth to 3 to prevent cycles. The document is signed per §13.1.1 by the `maintainer` DID. Clients SHOULD verify the signature against the `maintainer` DID but MAY accept unsigned directories with a user-visible warning. A `RelayEntry` is a connection hint, and its `serviceTiers` have the form of `RelayAd.serviceTiers` (§10.5.1); the relay record that counts is the relay-signed manifest (§10.2.1), which clients MUST verify before use (§10.3.4.7).

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

A directory is an independent publisher and lists only CO-signed Space records. `spaceAd` is the CO-signed SpaceAd (§10.3.2) for the Space: its encoded envelope (§13.1) with `sig`, base64url-encoded without padding (RFC 4648 §5) from the exact bytes and copied unmodified; clients MUST verify its signature and MUST discard an entry whose `spaceAd` is missing, fails verification, or names a different `spaceCID`. Name, description, icon, member count, invite link, and relay hints come only from `spaceAd`; `tags`, `language`, `addedBy`, and `addedAt` are the directory's own annotations, covered by the directory's signature.

The SpaceAd's `inviteURL` is a human-readable join link; the join flow itself is handled by the Space's invite mechanism (§4.3). `spaceCID` is the authoritative Space identity; clients verify it against the Space's genesis state document when connecting.

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

`relays`, `spaces`, and `includes` entries have the forms defined in §10.3.4.1 and §10.3.4.2.

#### 10.3.4.4 Client Behavior

On startup, the client fetches all configured directory sources in parallel. The client merges the results, deduplicating relay lists by `did` and Space lists by `spaceCID`. The client attempts connection to the highest-priority available relay (ordered by user preference). The client uses relays cached from prior sessions immediately while directory fetches are in flight.

The client retries failed fetches with exponential backoff (base 30 seconds, maximum 1 hour). It flags a source that consistently fails for 7 days as unreachable in the UI and does not silently remove it from the configured source list. The user decides whether to remove it.

A client MUST NOT add a directory source because a protocol message names it; sources are added only by the user or by whoever manages the device. Auto-population of directory sources is a privilege escalation vector.

#### 10.3.4.5 Content-Addressed Directories

A directory document MAY be addressed by CID instead of (or in addition to) an HTTPS URL:

```
ipfs://bafkrei.../relays.json
```

Clients resolve `ipfs://` URIs by fetching the blob from the CAS endpoint (`GET /v1/agora/blob/{cid}`, §10.4.4) of a relay that holds it. Relays replicate only blobs held under a channel token (§10.4.4), and a directory document is held under none. A directory publisher therefore stores the document at the relays it names alongside the `ipfs://` URI, and a client tries those relays in turn.

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

**Key derivation.** The BEP-44 key is the user's raw 32-byte Ed25519 authentication public key, extracted directly from their `did:key` identifier. No additional key material is required.

**Record format.** The BEP-44 value is a compact DNS packet (Pkarr format) containing TXT resource records:

```
_agora              TXT  "v=1"
_profile._agora     TXT  "cid=bafkrei..."
_kp._agora          TXT  "url=https://kp.example.net/v1/agora/kp/z6Mk..."
```

`v` and `_kp` are required; `_profile` is optional.

| Record | Key | Value | Required |
|---|---|---|---|
| `_agora` | `v` | Schema version (`1`) | Yes |
| `_profile._agora` | `cid` | Bare CID (no scheme) of the user's current profile node (§2.3) | No |
| `_kp._agora` | `url` | The user's `KeyPackageEndpoint` (§5.2.1.1), an HTTPS URL whose path begins with `/v1/agora/kp/` | Yes |

Only the identity key holder can change the record; any party MAY re-publish the unchanged signed record to keep it alive on the DHT.

The total DNS packet MUST fit within 1000 bytes (BEP-44 value limit). In practice a record with a profile CID and a KeyPackage URL occupies about 200 bytes.

**Verification.** BEP-44 mutable items are self-certifying: the DHT node returns the value together with the Ed25519 signature, and the lookup key is the public key itself. Clients MUST verify the signature before using any field. A valid signature proves the record was produced by the holder of the DID's authentication key.

**Lookup procedure.**
1. Decode the `did:key` identifier to recover the raw 32-byte Ed25519 public key.
2. Issue a BEP-44 `get` query for that key.
3. Verify the returned signature against the key.
4. Parse TXT records and use the profile CID or KeyPackage endpoint as needed.

**Publication and refresh.** Clients SHOULD publish their record on first login and re-publish every 2 hours. BEP-44 mutable items have no explicit TTL but decay from the DHT within about 2 hours without re-announcement. Stale or absent records are not an error; clients fall back to other discovery mechanisms.

**Scope.** This mechanism applies only to `did:key` users. `did:webvh` and `did:plc` users publish their `KeyPackageEndpoint` and profile pointer in their DID document, found by standard DID resolution, and do not require Mainline publication.

#### 10.3.4.7 Trust Model

Being listed in a directory confers no trust. A relay in a directory is trusted only to the extent that its DID verifies against its TLS certificate and signed advertisements. A Space in a directory is trusted only to the extent that its `spaceCID` verifies against its genesis state document. A malicious directory entry pointing at a rogue relay produces a DID mismatch at connection time and is rejected.

Directory maintainers are identified by their `maintainer` DID and signature. There is no global authority over directory content. Multiple competing directories can coexist and are all valid. Clients merge them all.

### 10.3.5 Channel Relay Lists

A relay carries a channel only if the channel's CO has registered the channel's admission key with it (§10.3.1, §10.5.3). A client therefore sends and subscribes to a channel's `channelToken` at one of the relays its CO has engaged, and learns that list from the CO, never from an IO:

- **Channels of a private Space.** From the `relays` member of the channel's `ChannelAdmissionKey`, which the CO's Space endpoint serves only to authenticated members (§3.4). The list appears in no record an IO can read.
- **Channels of a public Space.** From `relayHints` in the CO-signed SpaceAd (§10.3.2), and from the `ChannelAdmissionKey`.
- **Shared channels.** From the `ChannelAdmissionKey` issued by the home Space's CO, which registers the channel's admission key (§8.6).
- **Direct message (DM) groups and self-groups.** From `relays` in the group's `agora_admission` GroupContext extension, which carries the key the group's admission host issues and registers (§4.6, §2.6).

Each entry of a `relays` list is the origin of a relay; the client reads that relay's endpoints from its manifest (§10.2.1).

A client needs a connection to only one listed relay per channel for envelopes: the relays holding a registration for a token exchange its envelopes on the channel topic (§10.3.1). Blobs are uploaded to one listed relay and replicated among the relays carrying the token, and a client fetches a blob from any listed relay, falling back to the channel's `archive` (§10.4.4). Clients SHOULD fall back to another listed relay when one is unreachable or answers `unknown-token` or `token-withdrawn` for a token the client holds in a current `ChannelAdmissionKey` (§11.4).

**Changing relays.** To add a relay, the CO registers every current admission key with it (§10.5.3), then adds it to `relays`; the new relay obtains existing blobs by pull-through or CO seeding (§10.4.4). To remove a relay, the CO removes it from `relays`, then deregisters the keys. Because members' MLS state, Space state, and admission keys do not change, a CO adds, removes, or replaces a relay without touching Space identity or membership (ARCHITECTURE S5). Clients refresh the relay list whenever they fetch the `ChannelAdmissionKey` (§3.4) or, for a DM group or self-group, process a Commit that changes `agora_admission` (§4.6).

For a DM group or a self-group, the relay list is part of MLS state (§4.6). It changes at the next rotation, at most 8 days later while a host's user's client is online. A DM admission host keeps a departing relay registered until every key it issued that lists that relay has been deregistered or until `retiresAt`, whichever is first (§4.6). It therefore engages a replacement at least 14 days before a relay's `retiresAt` (§10.4.7).

---

## 10.4 Relay Behavior

*Binds: IO.*

### 10.4.1 Relay Knowledge Constraints

A conformant relay is designed to know as little as possible about the traffic it routes. The following is both a design target and a compliance requirement: a relay operator responding to a legal demand or subpoena MUST be able to testify truthfully to all of the following:

- I do not know who my users are (no identity registration, no account system, no persistent user records).
- I do not know who is in any group (channel membership is not visible at the relay layer; a `channelToken` is derived from an admission private key I never hold, and an admission signature does not identify its signer). The exception is a DM group or self-group whose admission key an identity host serving one user registers (§10.5.3): the agreement's billing DID then stands for that user's groups (ARCHITECTURE §9).
- I do not know which Space or channel any token belongs to (registrations name only the CO's billing DID, §10.5.3), except the token of a `keyAccess: public` broadcast channel, which the CO publishes with its public Space (§3.4).
- I do not know who sent any message (MLS encrypts the sender data, and the sealed envelope hides the MLS framing, §5.2.2).
- I store nothing after delivery beyond the retention window of the agreement under which a token is registered, and nothing with a message expiry past that expiry, except CIDs pinned under an instruction carrying a valid admission signature (ARCHITECTURE §6.2), which are retained until unpinned the same way.
- The encrypted blobs I forward and cache are opaque to me.

These statements are the IO side of ARCHITECTURE §4: what a legal demand on a relay operator yields is bounded by the observation budget in ARCHITECTURE §5.

Any protocol extension or relay implementation that makes any of these statements false introduces a legal liability surface for operators and a surveillance surface for adversaries. Such extensions MUST be explicitly opt-in and clearly documented as degrading the relay's metadata-blindness guarantees.

### 10.4.2 Relay-Blind Fan-out

Relays route messages by `channelToken`, not by `channelID`, MLS group ID, or member identity. The routing table maps `channelToken` → set of subscriber connections. Relays MUST NOT:

- Maintain a mapping from `channelToken` to `channelID`, MLS group ID, or Space CID.
- Maintain a mapping from `channelToken` to member DIDs.
- Log sender/recipient pairs for any message.
- Retain message envelopes beyond the agreement's retention window or message expiry, whichever is sooner.

A `channelToken` is fixed for one admission key and changes when the CO rotates the key (a new `keyEpoch`, §5.2.2); it does not change on MLS epochs. A relay sees each token's traffic for as long as the key is registered, and it can link a new token to the one it replaces, because the registration of the new key names the token it replaces (§10.5.3), the CO deregisters the old one shortly after, and the same subscribers move across. Subscribers that stay on the old token show the relay that a removal probably occurred and which connections or push handles it affected (ARCHITECTURE §9). The relay cannot map a token to a channel or Space; the set of Spaces it cannot tell apart is every Space the CO serves through it (ARCHITECTURE §5 item 6).

### 10.4.3 Conformance Requirements

A conformant relay MUST:

- Implement WebSocket transport (§11.2); WebTransport is RECOMMENDED.
- Implement the client hello and connection admission controls (§11.6), without authenticating client identity.
- Implement the Peer API and relay-to-relay authentication (§10.2).
- Implement the JMAP sync API (`jmap-sync-v1`, §11.8), which is the only path for envelope history and blob upload.
- Accept `AdmissionKeyRegistration` and `AdmissionKeyDeregistration` requests at its `admissionKeys` endpoint (§10.5.3).
- Carry only `channelToken`s registered with it under a current `ServiceAgreement`, on the live protocol and on the gossip mesh (§10.3.1).
- Verify `admissionSig` on every envelope against the admission public key registered for its `channelToken` before caching or forwarding it, and drop envelopes that fail (§10.5.4, ARCHITECTURE §6.2).
- Respect `expiryHint` on cached message envelopes (§5.2.4).
- Publish a relay manifest at `/.well-known/agora-relay` (§10.2.1), declaring its connection-log retention and any observation-budget extensions.
- Maintain heartbeat polling of peer relays (§10.2.6).
- Route messages by `channelToken` only; never attempt to resolve tokens to identities.
- Hold recent envelopes for each registered `channelToken` up to the lesser of the agreement's `retentionDays` and the envelope's `expiryHint`, and serve them to clients (§10.4.6).
- Retain and serve blobs stored under a `ServiceAgreement` within the agreement's retention window (§10.4.4).
- Replicate each uploaded blob to the agreement's `replicationFloor` of relays carrying its token, and accept replicated blobs and pull requests from them, only for tokens registered with it (§10.4.4).
- Announce on or request from the public IPFS network only public content (§10.4.4).
- Store only ciphertext envelopes, blobs addressed by CID that it cannot interpret (including group-encrypted blobs, §3.4), and records a CO explicitly publishes (such as SpaceAds, directory documents, and public Space state).
- Honor pin and unpin instructions (`PinInstruction`, §11.4) carrying a valid admission signature for a registered `channelToken`, retaining pinned CIDs regardless of retention window or `expiryHint` until unpinned (ARCHITECTURE §6.2).
- Enforce the storage and bandwidth quotas set by each `ServiceAgreement` (§10.5.1), keyed to the agreement and never to member identity.
- Validate envelope structure and `channelToken` format before forwarding; drop malformed envelopes silently.
- Support IPv6 on all endpoints; use bracket notation for IPv6 literals in advertised URIs.
- Enforce per-`channelToken` rate limits (§11.6, §12.5) as the primary spam control mechanism; per-IP limits MUST NOT be the sole mechanism.
- Where it serves push, send every wake-up for a registered `pushHandle` in the same form, with no content and no urgency, whatever envelope triggered it (§11.7).
- Handle takedown requests for CIDs it cannot read as §10.4.5 describes.

A conformant relay MUST NOT:

- Attempt to decrypt MLS ciphertext.
- Log or retain sender DIDs (the relay never has them, §5.2.2).
- Use per-IP rate limiting as the sole spam control mechanism.
- Store or serve MLS KeyPackages; KeyPackages are held at the user's `KeyPackageEndpoint` (§2.1).
- Author or modify Space discovery records, forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd, or publish lists of the Spaces it serves (§10.3.2).
- Accept DID-signed user records from clients or forward them (§10.3.1).
- Gossip, forward or reveal `AdmissionKeyRegistration`s, `AdmissionKeyDeregistration`s, or `ServiceAgreement`s to any party other than the CO that sent them.
- Modify gossipsub messages in transit.
- Make or enforce decisions about membership, roles, moderation, or content, including bans, timeouts, deletes, and pin limits; these are enforced by MLS removal and member clients (ARCHITECTURE S2, §5.2.2).
- Sign Space state, channel state, role assignments, moderation records, or retention policy (ARCHITECTURE S4).
- Observe, log or retain anything outside the ARCHITECTURE §5 observation budget, except extensions a CO has opted into and the relay declares in its manifest (ARCHITECTURE S6).

A conformant relay SHOULD:

- Announce itself on `v1/agora/discovery` with a signed `RelayAd` listing its client-facing endpoints (§10.5.1).
- Operate a Tor hidden service endpoint to protect operator IP and support Tor-connected clients.
- Maintain peering connections to at least 3 other known relays.
- Implement gossipsub peer scoring to limit amplification attacks.

Relay federation is permissionless. Any relay that speaks the protocol can join the mesh and carry the discovery topic; it carries a channel only when that channel's CO registers the channel's admission key with it.

### 10.4.4 Blob Storage and Retrieval

A relay stores blobs in a content-addressed store keyed by the multihash of each block's CID (§13.1), so it serves the same bytes under a `raw` or a `dag-pb` CID with that multihash. Each blob is held under every `channelToken` for which it was uploaded, replicated, pulled, or pinned, and is charged to and retained for the agreement of each such token. "Pin" in this specification means retention in that store under a pin instruction (ARCHITECTURE §6.2); it does not mean pinning on the public IPFS network. A file is stored as several blocks (§14.3.4); each block is a blob for the purposes of this section.

A conformant relay MUST serve every blob it holds over HTTPS at `GET /v1/agora/blob/{cid}` on the origin of its manifest (§10.2.1). The endpoint is unauthenticated and rate-limited per network address (§11.6), and it MUST send `Access-Control-Allow-Origin: *` so that browser clients can fetch from it directly. A request MAY carry the query parameter `token`, a `channelToken` in base64url without padding, which asks for pull-through (below). A relay also serves the same bytes through JMAP download (§11.8.1). These are the fetch paths for blobs, including `ipfs://` URIs (§10.3.4.5); a client needs no IPFS node or public IPFS gateway.

A client MUST verify that the bytes it receives hash to the requested CID and MUST discard them otherwise, whatever the source: a relay, a peer relay, the CO archive, another of the user's devices, or the IPFS network. Because every blob is either ciphertext the relay cannot read or a record a CO chose to publish (§10.4.3), a relay can serve blobs to any requester without learning anything beyond the ARCHITECTURE §5 observation budget.

**Upload admission.** A relay MUST accept a blob upload only when it carries an `Agora-Storage-Auth` authorization (§11.8.2) for a `channelToken` registered with it, signed with that token's registered admission key. It charges the stored bytes to the agreement under which the token is registered and keeps the blob for that agreement's retention window unless it is pinned. This gives blob writes the same member-only admission as envelopes, and the relay learns no uploader identity.

**Upload once.** A client uploads each blob of a channel once, to any one relay in the channel's relay list (§10.3.5), and need not upload it elsewhere. If that relay refuses or fails the upload, the client uploads to another listed relay.

**Replication among a channel's relays.** The relays that carry a channel's `channelToken` are the members of that token's channel topic mesh (§10.3.1), and they replicate the channel's blobs among themselves over the Peer API (§10.2.2):

- *Eager replication.* A relay that accepts an upload MUST copy the blob, with `POST /v1/agora/peer/blob`, forwarding the upload's `Agora-Storage-Auth`, to other relays carrying the token until it is held by at least `replicationFloor` relays including itself, where `replicationFloor` is taken from the agreement under which the token is registered with it (§10.5.1), or by every relay carrying the token if fewer carry it. "Relays carrying the token" means the peers it knows to be subscribed to the token's channel topic. Replication follows the upload response and does not delay it. The relay retries relays that are unreachable or answer `507` with exponential backoff for at least 24 hours, then stops and keeps its own copy. A client that needs the floor met before it posts the Message MAY also upload the blob to a second listed relay.
- *Pull-through.* A relay that receives a fetch, with `token` set, for a CID it does not hold, for a token registered with it under a current agreement, SHOULD fetch the CID from another relay carrying that token with `GET /v1/agora/peer/blob/{cid}`, verify it against the CID, store it under the token, and serve it. Without `token`, or for a token not registered with it, it answers 404 and fetches nothing.
- *Receiving replicas.* A relay that receives a replicated blob accepts it only for a token registered with it under a current agreement, verifies it against its CID, verifies the forwarded `Agora-Storage-Auth` as §10.2.2 describes, charges it to that agreement's storage quota, and keeps it for that agreement's retention window from receipt. A relay MUST NOT pull, push, or cache blobs for a token not registered with it.

Replication adds nothing to what a relay knows: a relay that replicates or pulls a blob already carries the channel's token and its envelopes, the CIDs and sizes it learns are those it stores (ARCHITECTURE §5 item 4), and a peer learns only that the requesting relay carries a token, which the channel topic mesh already shows it.

**Fetching.** A client fetching a blob of a channel asks any relay in the channel's relay list, with `token` set to the channel's current `channelToken`, then other listed relays, then the `archive` named in the channel's `ChannelAdmissionKey` (§3.4), if any. The client MAY fetch the chunks of one file from several of these sources in parallel (§14.3.4).

**Relay replacement.** A relay newly added to a channel's relay list (§10.3.5) obtains the channel's existing blobs by pull-through as clients request them. The CO MAY also seed it with a `seed` pin instruction listing CIDs (§11.4), on which the relay pulls each listed CID it lacks from other relays carrying the token, or, if none holds it, the CO MAY upload it from its archive under an ordinary upload authorization (§11.8.2).

**Pinning.** A pin instruction (§11.4) applies only at the relay that receives it, so a client pinning a blob sends the instruction to each relay in the channel's relay list. A relay that receives a `pin` for a CID it does not hold SHOULD first pull it as above. A `pin` for a CID it holds under another token adds the pin's token as a holder (above). Pinning a `dag-pb` root block (§14.3.4) also pins every block it links to; unpinning it removes that exemption.

**Public IPFS.** Agora is IPFS-compatible, not IPFS-dependent. A relay or client MAY run an IPFS node, and none is required to. Relays, clients, and the CO MUST NOT announce on, provide to, or request from the public IPFS network (its DHT, public Bitswap peers, or public gateways) any blob other than public content: records a CO publishes (§3.4, §10.3.2), and the envelopes and blobs of a broadcast channel whose `keyAccess` is `public` in a public Space (§5.2.1.4). Requesting a CID there discloses interest in it to unknown parties, so private ciphertext is neither announced nor requested. Bitswap MAY be used for private ciphertext only between a user's own devices, which find each other through the self-group (§2.6), and between those devices and the CO archive. Relays exchange blobs only over the Peer API. Public content MAY be published to the public IPFS network by the CO, a member, or a relay holding it (ARCHITECTURE §9).

**No member-to-member exchange.** A client fetches blobs only from relays, the CO archive, and its own user's devices. Devices of different members MUST NOT exchange blobs directly, and clients MUST NOT announce themselves or their content on a local network (for example by mDNS). Disconnected operation is out of scope for this version except through a radio-mesh gateway (profiles/radio-mesh-gateway.md).

### 10.4.5 Takedown Requests

A relay can receive a takedown request (a legal demand, or a report from a third party) naming a CID it stores. The relay cannot read the blob or envelope, so it cannot judge the content, and it MUST NOT attempt to decrypt it.

The relay looks up each `channelToken` under which it holds the CID (§10.4.4) and each agreement under which such a token is registered, and SHOULD forward the request, with the CID, to the CO at each such agreement's `contact` (§10.5.1). The CO identifies the content from its own records and handles it through its moderation process (§4.5). The relay MAY stop serving the CID and delete it, as a storage decision under its own policy and law; doing so removes one copy and is not a moderation decision (ARCHITECTURE S2). The relay MUST NOT disclose to the requester anything beyond the ARCHITECTURE §5 observation budget, and does not learn or reveal which Space or member the content belongs to.

### 10.4.6 Envelope History

A relay holds the recent envelopes of each `channelToken` registered with it, for the `retentionDays` of the agreement under which the token is registered (§10.5.1) or until each envelope's `expiryHint`, whichever is sooner, plus any envelopes pinned under §10.4.3. It indexes, deduplicates, and pins each envelope by its envelope `id`, the CID of its `signed` bytes only (§5.2.2), and stores the complete envelope bytes under that `id`. It serves them to clients through the JMAP sync API (§11.8), keyed by `channelToken` only. Deregistering a key (§10.5.3) stops the relay from accepting new envelopes for its token; envelopes already held under that token remain readable until their retention ends.

Relay-held envelopes are the recent part of a channel's history (§5.2.5). Older history lives in members' stores and in the CO's archive (§7), not at any relay. A relay that drops envelopes early cannot forge or alter any: MLS signatures authenticate every message, and the inner per-sender `seq` (§5.1.1) lets members detect omissions.

### 10.4.7 Token Suspension, Recovery, and Retirement

**Token suspension.** A relay MAY stop admitting envelopes, pin instructions, and blob uploads for one registered `channelToken`, for example when the token carries abusive volume or under a legal demand. This is a carriage decision under the relay's own policy and law, like deleting a copy under §10.4.5, and not a moderation decision (ARCHITECTURE S2). The relay treats a suspended token as withdrawn (§11.4): it sends `token-withdrawn` to the token's subscribers and answers later requests naming the token with `token-withdrawn`. It MUST notify the CO at the `contact` of the agreement under which the token is registered (§10.5.1), naming the token, the time, and the reason. A suspension applies to the token: registering the same token again does not lift it, and the relay admits a new token that the CO registers after rotating the key (§5.2.2), for example after removing the member responsible. The relay lifts a suspension at its discretion. Suspension tells the relay nothing about the channel or its members beyond what it already observes (§10.4.1).

**Recovery from backup.** A relay that restores its state from a backup, or otherwise loses registration state, MUST NOT reinstate admission key registrations from the backup, because a key deregistered after the backup was taken would be admitted again. It starts with no registrations and answers `unknown-token` for every token (§11.4); clients move to another listed relay meanwhile (§10.3.5). It MUST notify the CO at the `contact` of each agreement it holds that its registrations were lost, and the registration service then re-registers every current key under that agreement (§10.5.3). Without that notice the periodic re-registration of §10.5.3 restores them within 24 hours. The relay MAY keep restored envelopes and blobs within their retention and serves them once their token is registered again.

**Retirement.** A relay that will stop serving MUST set `retiresAt` in its manifest (§10.2.1) and MUST notify the CO at the `contact` of each agreement it holds, both at least 30 days before that time, unless the relay and a CO have agreed a different notice period out of band for that CO. A CO removes the relay from its relay lists (§10.3.5) and deregisters its keys there before `retiresAt`. Until `retiresAt` the relay keeps admitting registered tokens.

---

## 10.5 Service Agreements and Abuse Control

*Binds: both.*

IOs incur real costs: bandwidth, compute, storage, legal exposure, and abuse handling. This section specifies the `ServiceAgreement`, the only binding between a CO and an IO (ARCHITECTURE S7), the registration of channel admission keys under it, and proof-of-work as non-monetary abuse control. Commercial terms between CO and IO are agreed out of band and are outside the protocol.

An IO that carries member traffic MUST hold a `ServiceAgreement` for it, because it admits only envelopes whose admission keys a CO has registered under an agreement (§10.5.3, §10.5.4). Proof-of-work is optional (§10.5.2).

### 10.5.1 Service Agreements

A `ServiceAgreement` is a typed payload envelope (§13.1) of type `urn:agora:type:ServiceAgreement` between a CO billing DID and an IO DID, specifying the service, retention, quotas, SLA terms, and the IO's observation-budget declaration. It names no Space and no channel (ARCHITECTURE §6.1). It is signed per §13.1.1 by both the `provider` DID and the `billing` DID: the envelope `sig` carries one entry for each. An agreement is identified by the CID (§13.1) of its body bytes, the exact bytes both parties signed (§13.1.1), not of the encoded envelope.

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
  "replicationFloor": 2,
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

`provider` is the IO's DID; for a relay it is the manifest's `relayDID`. `endpoint` is the URL at which the IO accepts admission key registrations (§10.5.3); for a relay it equals the manifest's `endpoints.admissionKeys`. It is absent for service types that receive no registrations. `contact` is a `mailto:` or `https:` URI at which the IO reaches the CO about abuse and takedown requests (§10.4.5) and about token suspension, lost registrations, and retirement (§10.4.7); it MUST NOT name a Space.

`retentionDays` is how long the IO keeps envelopes and blobs (`relay`) or stamped log entries (`sequencer`) of the tokens registered under the agreement; it is absent for other service types. `storageQuotaGb` and `bandwidthTierGbPerMonth` are the quotas the IO enforces for this agreement (§10.4.3). `replicationFloor`, for `relay` only, is the minimum number of relays carrying a token, including the receiving one, to which a relay eagerly replicates each blob uploaded under that token (§10.4.4); it is an unsigned integer of at least 1, and is 2 when absent. Replicated copies count against the storage quota of each holding relay's own agreement.

`billing` is a DID the CO dedicates to agreements. It MUST NOT appear in Space state, SpaceAds, directory documents, or any other record that identifies a Space. For an identity host acting as the CO (§10.5.3), it also MUST NOT be the DID of a user the host serves and MUST NOT appear in any DID document, Pkarr record, or other record that identifies a user. An identity host that serves one user still discloses, through its agreements, that their tokens belong to that one user's DM groups and self-group (ARCHITECTURE §9). A CO MAY use one billing DID for all of its Spaces; doing so is what gives each Space its anonymity set at the IO (ARCHITECTURE §5 item 6).

The agreement is private between the CO and the IO. It MUST NOT be gossiped, stored in Space state, or published. Both parties keep the fully signed agreement; how they exchange it for signing is out of band. Multiple concurrent agreements (multiple relays serving the same CO) are valid and encouraged for redundancy.

`observationBudget` records the connection-log retention (ARCHITECTURE §5 item 1) and any opt-in observation-budget extensions (ARCHITECTURE S6) the CO has agreed to. A relay holds one manifest and may hold many agreements, so its manifest (§10.2.1) MUST declare a `connectionLogRetentionDays` no lower than the highest value across its agreements and `extensions` listing every extension any of its agreements enables. For the traffic of each agreement the IO MUST NOT exceed that agreement's values.

**Lifecycle.** Admission key registrations (§10.5.3) belong to the agreement under which they were made and lapse with it. To renew an agreement, or to move it to a new billing DID after rotation or suspected compromise of the billing key, the CO and the IO sign a new agreement whose `supersedes` member holds the CID of the agreement it replaces, computed the same way over that agreement's body bytes. `supersedes` is `null` in an agreement that replaces none. From the moment the IO signs a superseding agreement it MUST reject new registrations under the superseded one; keys registered under the superseded agreement remain admitted for one hour, then lapse. Within that hour the CO registers every current admission key under the new agreement. A stolen billing key therefore lets its holder register or deregister keys under the CO's agreement, which spends quota or denies service, only until the CO and IO sign a superseding agreement; it never lets anyone read traffic.

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

A `RelayAd` body carries exactly these members. `did` is the manifest's `relayDID`. `manifestURL` is where the relay manifest (§10.2.1) is served. `endpoints` uses the member names of the manifest's `endpoints` and MUST list every client-facing endpoint the manifest lists (`webTransport`, `webSocket`, `onion`, and `jmapSync`), including overlay-internal URIs (§10.1); relay-to-relay and CO-facing endpoints (`peerAPI`, `gossipQuic`, `admissionKeys`) are left out. `serviceTiers` lists the tiers the relay offers under `ServiceAgreement`s. `ts` is the publication time. Where a `RelayAd` and the manifest disagree, the manifest governs. A `RelayAd` is signed per §13.1.1 by the relay (`did`).

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

`powProof` is not covered by `admissionSig` and need not be: it is bound to the `signed` bytes it was computed over, so it cannot be moved to another envelope. The client computes it after `signed` is fixed. The envelope `id` is the CID of the `signed` bytes only (§5.2.2), so it does not cover `powProof` or the outer encoding: a forwarder that adds, removes, or changes a `powProof` cannot change an envelope's `id`. Connection-level proof-of-work (`AdmissionChallenge`, §11.6) is separate and uses its own challenge.

A relay declares its own minimum difficulty in the `minPowDifficulty` member of its manifest (§10.2.1). The relay verifies the PoW before forwarding against that value and MUST NOT require more than it declares. The relay cannot map a `channelToken` to a channel's `PowPolicy` (§10.4.2), so member clients enforce the channel's difficulty and drop envelopes that do not meet it. Difficulty 18 requires about 262,000 SHA-256 operations, roughly 10 to 50 ms on a modern CPU: imperceptible to a human sender, but economically prohibitive for bulk message flooding.

**HTTP endpoints.** An HTTP endpoint, CO or IO, that requires proof-of-work before serving a request, such as a `KeyPackageEndpoint` host (§4.6.3), an invite endpoint resolving open-link tokens (§4.7), or a sequencer (§14.4), uses the following challenge format. It answers the request with HTTP 429 and an `Agora-PoW-Challenge` response field, a Dictionary structured field (RFC 9651):

```
HTTP/1.1 429 Too Many Requests
Agora-PoW-Challenge: challenge=:RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=:, difficulty=20, expires=30
```

`challenge` is a Byte Sequence of 32 random bytes, `difficulty` an Integer from 0 to 64, the required leading zero bits, and `expires` an Integer, the number of seconds the client has to answer. The client chooses a nonce of 8 to 32 bytes such that SHA-256(`challenge` || nonce) has at least `difficulty` leading zero bits, counted from the most significant bit of the first byte of the hash, as for the connection-level proof of §11.6. It repeats the request with an `Agora-PoW` request field, also a Dictionary structured field:

```
Agora-PoW: challenge=:RvJ4EzqNXWi3jrDXACL8CpIil0hZ96Bfc9ZXG/d3Cuw=:, nonce=:AAAAAAAXBKY=:
```

The endpoint MUST accept each `challenge` at most once and only within `expires` seconds of issuing it, and answers a request whose proof is missing, invalid, expired, or reused with a new challenge as above. The proof carries no identity and is independent of any authentication the endpoint requires (§3.5).

### 10.5.3 Admission Key Registration

A registration service registers each channel admission public key (§5.2.2) with every IO that holds a `ServiceAgreement` with it whose `serviceType` receives registrations (§10.5.1), under that agreement. For channels of a Space the registration service is run by the Space's CO beside its Space endpoint (§3.4), under the CO's agreements; for a shared channel, by the home Space's CO (§8.6); for a DM group or a self-group (§2.6), by the group's admission host, the identity host named in its `agora_admission` extension (§4.6).

A DM group or self-group has no Space state, so its admission host registers its keys only under `relay` agreements. An identity host registers under the agreements of the party that runs it. An employer provisioning service (§2.5) registers under the employer CO's agreements and billing DID. An identity host that an individual chose holds its own `ServiceAgreement`s under its own billing DID and registers under those, acting as the CO for this purpose.

The IOs holding the `relay` agreements a registration service uses are the relays it lists to members (§10.3.5); its `sfu` and `sequencer` agreements are named in Space state (§6.6, §14.4.1). Registrations travel only over HTTPS from the registration service to the IO. They are never gossiped and no client or member sends them.

**Request.** The registration service sends `POST <endpoint>`, where `<endpoint>` is the agreement's `endpoint`, with `Content-Type: application/cbor` and a body that is one encoded typed payload envelope (§13.1) signed per §13.1.1 by the agreement's `billing` DID. The envelope is of one of two types.

`urn:agora:type:AdmissionKeyRegistration` tells the IO to admit envelopes signed by the listed keys:

```json
{
  "agreement": "bafkrei...",
  "ts": "2026-10-16T12:00:00Z",
  "keys": [
    {
      "channelToken": "base64url...",
      "admissionPublicKey": "base64url...",
      "replaces": "base64url..."
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

`agreement` is the CID (§13.1) of the `ServiceAgreement` body bytes, the exact bytes both parties signed (§13.1.1), so it does not depend on how the envelope around them is encoded. `ts` is the sending time, RFC 3339 in UTC. `channelToken` is the 32-byte token (§5.2.2) and `admissionPublicKey` the 32-byte Ed25519 public key (RFC 8032), each in base64url without padding (RFC 4648 §5). `replaces` is present when the key is a rotation (§5.2.2) and holds the `channelToken` of the key it rotates, in the same encoding; the registration service MUST set it in the first registration of each rotated Space channel key with each IO, and MUST omit it for a new channel's first key and for every key of a DM group or self-group (§4.6). An IO ignores a `replaces` that names a token not registered under the agreement. Registrations carry no `keyEpoch`: an IO identifies a key by its `channelToken` alone, and `keyEpoch` stays member-side. A request lists 1 to 1000 keys or tokens. The bodies carry nothing that identifies a Space, channel, DM group, or member.

**Processing.** The IO MUST, before applying a request:

1. verify the signature per §13.1.1 with the agreement's `billing` DID as the required signer;
2. check that it holds the agreement, signed by itself and by `billing`, that the current time is within `validFrom` and `validUntil`, that the agreement is not superseded (§10.5.1), and that its `serviceType` receives registrations;
3. check that `ts` is within 300 seconds of its clock and, for every listed token, later than the `ts` of the last request it accepted that listed the same token under the same agreement, so that a replayed request cannot restore a deregistered key.

The IO applies a valid request entirely or not at all. Registering a token already registered under the same agreement with the same key, and deregistering a token not registered, succeed without change. A token is registered with at most one key; the IO MUST reject a registration that lists a token already registered with a different key.

An IO with a `sequencer` agreement that applies a registration whose key has `replaces` MUST, from that moment, stop stamping Commits on the commit stream of the replaced token (§14.4.3), answering a Commit submitted there with HTTP 409 and `stream-closed` (§11.4). It continues to stamp operations on the replaced token's operation stream until that token is deregistered. A relay uses `replaces` only to send `token-rotated` (§11.4); other IOs ignore it. The field adds no linkage beyond what an IO already observes: an IO can link the key epochs of one channel (§12.3).

**Response.** On success the IO returns HTTP 204. On failure it returns the status below with a JSON body `{ "error": "<code>" }` and changes nothing:

| Status | `error` | Condition |
|---|---|---|
| 400 | `malformed` | Body is not a decodable envelope of one of the two types, a field is missing or badly encoded, or the list is empty or longer than 1000 |
| 401 | `bad-signature` | `sig` is missing or invalid, or its signer is not the agreement's `billing` DID |
| 403 | `agreement-invalid` | Agreement unknown, not yet valid, expired or superseded, or its `serviceType` receives no registrations |
| 409 | `stale` | `ts` outside the 300-second window, or not later than a previous accepted request for a listed token |
| 409 | `token-conflict` | A listed token is already registered with a different key |
| 429 | `rate-limited` | The IO's rate limit for the agreement is exceeded |

**When the registration service registers.** The registration service registers:

- a new channel's or DM group's first admission key before serving it to members;
- each rotated key (§5.2.2) with every IO whose `serviceType` receives registrations (§10.5.1), with `replaces` set, before serving it to members;
- every current key (for a DM group or a self-group, every key of the group that the admission host has not deregistered) with an IO that it engages, and under every renewed or superseding agreement (§10.5.1), before listing that IO to members (§10.3.5);
- every current key (as above) with an IO that reports lost registrations (§10.4.7), without delay.

It MUST also re-send every current key (as above) to each IO at least once every 24 hours. Re-registration of an unchanged key succeeds without change, so the re-send costs the IO nothing when its state is intact and restores a relay that lost its registrations (§10.4.7).

It SHOULD batch registrations for new channels and DM groups and add random delay, so that registration timing does not reveal when a particular Space, channel, or DM group was created. It sends registrations for a rotation that follows a removal without added delay, since a delay would lengthen the removed member's window.

**When the registration service deregisters.** After a rotation, the registration service deregisters the previous key once members have had time to move to the new token, after a grace period RECOMMENDED to be 300 seconds. The grace period applies only to application messages and operations: a sequencer stamps no Commit on the previous key's commit stream once the new key is registered (above), so a member still holding the previous key fetches the new key before it commits. Until the previous key is deregistered, a removed member that held the previous key can still post envelopes the IO admits, though it cannot read the channel (MLS). The registration service also deregisters every key of a channel or DM group that is deleted, and every key at an IO it stops using. If the registration service is unreachable, IOs keep admitting the keys last registered, and members keep using the last key they hold.

For a DM group or a self-group, §4.6 alone governs when the admission host deregisters a key: the 300-second grace period and the deletion rule above do not apply, the host omits `replaces` from every registration, and it completes registration with every IO it lists before it returns the key, with any batching delay applied before that response.

### 10.5.4 Relay Admission

A relay admits an envelope, whether it arrives in a live protocol `Publish` (§11.4), on a channel gossip topic, or in a `GossipBatch` (§10.2.2), only if all of the following hold:

1. the `channelToken` inside the envelope's `signed` bytes is registered with the relay under a current `ServiceAgreement` (§10.5.3);
2. `admissionSig` is a valid Ed25519 signature (RFC 8032) over the exact bytes of the envelope's `signed` field under the admission public key registered for that token; the relay verifies these bytes as received and never re-encodes them;
3. if the relay's `minPowDifficulty` is greater than 0, `powProof` meets it (§10.5.2);
4. the envelope is within the size and rate limits of §11.6;
5. the envelope is not expired as §11.4 defines for `Publish`.

The relay drops an envelope that fails any check; on the live protocol it answers with the `Error` code §11.4 assigns. It reads nothing else from the envelope beyond what routing and retention need (`channelToken` and `expiryHint`). The same registrations admit `PinInstruction`s (§11.4) and blob uploads (§10.4.4), each signed with the token's admission key. Subscribing needs no proof, but a relay delivers nothing on, and sends no push wake-ups for, a token with no registered key (§11.4, §11.7).

Every current member holds the same admission key, so a valid `admissionSig` shows that the sender holds the key registered for the token, that is, it is a current member or was one before the latest rotation, and does not show which member. Removals take effect at the relay when the CO rotates the key and deregisters the old one (§10.5.3); the relay keeps no DID ban list (ARCHITECTURE §6.2).

SFUs (§6.6) and sequencers (§14.4.3) admit traffic by the same rule against the keys registered under their own agreements.
