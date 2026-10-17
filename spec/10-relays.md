# 10. Relays, Federation and Discovery

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 584–1065, 2920–2994, 3054–3133, 3188–3207 (§3.4–3.5, §4, §11, §12 intro, §12.2, §12.4).

## 10.1 Deployment Topologies

*Binds: IO.*

Agora is transport-agnostic at the application layer. The following deployment topologies are explicitly supported:

**Public internet (default)** — Relays are clearnet HTTPS/WSS servers with public IPv4 and/or IPv6 addresses. Clients connect over the public internet. This is the baseline configuration assumed throughout this specification unless otherwise noted.

**Tor hidden service** — A Relay MAY operate as a Tor v3 hidden service, publishing a `.onion` address in its `RelayAd` alongside or instead of a clearnet endpoint. Clients connecting via Tor MUST use the WebSocket transport (§11.2); WebTransport requires QUIC over UDP and is unavailable over Tor.

**Private overlay (Tailscale / WireGuard / Headscale)** — A Relay MAY operate exclusively on a WireGuard-based overlay network. The Relay's `RelayAd` lists overlay-internal hostnames or `100.x.x.x` addresses; these are only resolvable inside the overlay. This is the recommended topology for private organizational deployments where all members are already on a common overlay. A fully self-contained deployment — Relay + SFU + TURN + Headscale, all on-premise — has zero dependency on any external infrastructure.

**Dual-stack (clearnet + overlay)** — A Relay MAY publish both clearnet and overlay endpoints. Clients on the overlay prefer the overlay path; external clients use the clearnet path. Both sets of clients share the same space state and message history.

**Managed / SaaS** — A relay operator (the "managed provider") provisions and operates a dedicated Agora relay fleet on behalf of a customer. Each customer receives their own isolated deployment — separate relay processes, separate database, separate blob store — not a shared multi-tenant instance. The customer controls, or delegates control of, the DNS name that roots their deployment; the managed provider's infrastructure hosts it (typically via CNAME or DNS delegation). The managed provider's identity appears as `operatorDID` in each relay manifest (§10.2.1), but `relayDID` is anchored to the customer's DNS domain, not the provider's. This preserves namespace ownership: if the customer migrates to self-hosted, their DNS name and all derived identities (`did:web:<customer-domain>:users:...`) are portable without re-enrollment. `operatorDID` and `relayDID` are IO keys and are distinct principals from every CO key, even where one entity holds both roles (ARCHITECTURE §2.4).

**IPv6** — All Relay endpoints SHOULD support IPv6. Relay URIs MUST use bracket notation for IPv6 address literals (`wss://[2001:db8::1]/v1/agora/ws`). ICE gathers both IPv4 and IPv6 host candidates; dual-stack clients race both address families.

### 10.1.1 Discoverability and DNS Namespace Root

A deployment's ability to participate in the public Agora mesh depends on whether it has a DNS root:

**Discoverable deployments** (public internet, managed/SaaS, dual-stack) SHOULD be anchored to a DNS name. That name is the root of the deployment's identity namespace: relay DIDs are `did:web:<domain>`, organizational user DIDs are `did:web:<domain>:users:...`, and the relay manifest is served at `https://<domain>/.well-known/agora-relay`. Any two deployments with distinct DNS names have non-overlapping identity namespaces by construction; no registry or authority is required to prevent conflicts.

**Non-discoverable deployments** (private overlay, air-gapped, Tor-only) have no DNS root requirement. Relay DIDs are `did:key:...`; user DIDs are `did:key:...` or `did:web` anchored to an internal-only domain. These deployments cannot join the public gossipsub mesh or federate with external organizations. This is an explicit architectural trade-off, not a misconfiguration.

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

The manifest is a signed JSON-LD document that serves as the Relay's authoritative self-declaration. It is the single source of truth for a Relay's identity, capabilities, endpoints, and signing keys. Any Relay that can reach this URL can bootstrap a peering relationship without out-of-band coordination.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RelayManifest",
  "version": "1",
  "relayDID": "did:key:z6MkRelay...",
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
    "keyPackageStore": "https://relay.example.com/v1/agora/kp",
    "peerAPI":         "https://relay.example.com/v1/agora/peer",
    "jmapSync":        "https://relay.example.com/v1/agora/jmap",
    "gossipQuic":      "/ip4/203.0.113.42/udp/9001/quic-v1"
  },
  "keys": [
    {
      "id": "did:key:z6MkRelay...#key-1",
      "type": "Ed25519VerificationKey2020",
      "publicKeyMultibase": "z6MkRelay...",
      "status": "active",
      "activatedAt": "2026-03-12T00:00:00Z",
      "expiresAt": "2027-03-12T00:00:00Z"
    }
  ],
  "capabilities": [
    "gossipsub-v1.1",
    "keypackage-store-v1",
    "keypackage-forwarding-v1",
    "tor-hidden-service-v1",
    "peer-api-v1",
    "jmap-sync-v1"
  ],
  "observationBudget": {
    "connectionLogRetentionDays": 7,
    "extensions": []
  },
  "knownPeers": [
    {
      "relayDID": "did:key:z6MkPeer...",
      "manifestURL": "https://peer.example.net/.well-known/agora-relay",
      "addedAt": "2026-03-12T00:00:00Z"
    }
  ],
  "publishedAt": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

`sig` is the Relay operator's Ed25519 signature over the manifest, excluding the `sig` field, signed per §13.1.1. Peer Relays MUST verify this signature before accepting the manifest.

`observationBudget` declares what the Relay retains beyond transient routing. `connectionLogRetentionDays` is the retention of network-layer connection metadata (ARCHITECTURE §5 item 1), as set by the Relay's `RelayServiceAgreement`s (§10.5.1). `extensions` lists every opt-in extension to the ARCHITECTURE §5 observation budget the Relay has enabled; it MUST be empty unless a CO has opted in (ARCHITECTURE S6). A Relay MUST NOT observe, log or retain anything not covered by ARCHITECTURE §5 or a declared extension.

`knownPeers` is the Relay's current peer list. This serves as a mesh map: a new Relay fetching any existing Relay's manifest obtains a list of further Relays to contact, enabling rapid mesh joining without a central directory server.

**Relay DID and DNS binding.** For relays operating on the public internet (§10.1), `relayDID` SHOULD be a `did:web` anchored to the relay's DNS domain rather than a `did:key`:

```json
"relayDID": "did:web:relay.example.com"
```

The relay MUST serve a conformant DID document at `https://relay.example.com/.well-known/did.json`. This creates a verifiable binding: the manifest at `/.well-known/agora-relay` is signed by the key declared in the DID document, and the DID document SHOULD include a `service` entry pointing back to the manifest URL. Any peer that resolves `did:web:relay.example.com` can verify that the key material and the DNS domain are controlled by the same entity.

For relays operating exclusively on a private overlay, Tor hidden service, or air-gapped network — where no public DNS name exists or is desired — `relayDID` MAY be `did:key:...`. These relays do not participate in the public mesh and do not require DNS binding.

**Operator vs. customer identity.** The `operatorDID` field records the identity of the party that operates the relay infrastructure. For self-hosted deployments, `operatorDID` and the relay's controlling entity are the same. For managed/SaaS deployments (§10.1), they differ: `relayDID` is anchored to the customer's DNS domain; `operatorDID` is the managed provider's DID. This distinction is relevant to legal exposure (§12.3) and compliance logging (§7).

`capabilities` is an array of capability strings declaring what features this Relay supports:

| Capability | Meaning |
|---|---|
| `gossipsub-v1.1` | Participates in libp2p gossipsub v1.1 mesh over TCP |
| `gossipsub-quic-v1` | Participates in libp2p gossipsub v1.1 mesh over QUIC-v1 (preferred) |
| `peer-api-h3` | Peer API is served over HTTP/3 (QUIC); `Alt-Svc: h3` header is present |
| `keypackage-store-v1` | Hosts the KeyPackage Store API (§5.2.1.1) |
| `keypackage-forwarding-v1` | Supports inter-relay KeyPackage forwarding |
| `keypackage-ipfs-supply-v1` | Can replenish the KeyPackage store from a DID's IPFS supply CID (§5.2.1.1) |
| `tor-hidden-service-v1` | Reachable via a `.onion` endpoint |
| `sfu-v1` | Hosts an SFU for voice channel routing |
| `peer-api-v1` | Implements the Peer API v1 (§10.2.2) |
| `jmap-sync-v1` | Exposes the token-keyed JMAP sync API (§11.8.1–§11.8.8) |
| `push-proxy-v1` | Operates a push notification proxy (§11.7) |

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
     Relay-to-relay gossipsub message submission.
     Body: CBOR-encoded gossipsub message batch.
     Authenticated.

GET  /v1/agora/peer/health
     Returns relay health state.
     Response: { "status": "healthy"|"degraded"|"unhealthy"|"maintenance", "since": ISO8601 }
     Unauthenticated.
```

### 10.2.3 Relay-to-Relay Authentication

All relay-to-relay requests (except unauthenticated endpoints) use **RFC 9421 HTTP Message Signatures** with Ed25519. The requesting Relay signs each HTTP request using its active signing key from its manifest. The receiving Relay verifies the signature against the requesting Relay's manifest fetched from `/.well-known/agora-relay`.

**Required signature components** (per RFC 9421 §2.5):

```
"@method"
"@target-uri"
"@authority"
"content-digest"      (POST requests with a body)
"x-agora-relay-did"   (requesting relay's DID)
"x-agora-timestamp"   (Unix timestamp, integer seconds)
"x-agora-nonce"       (random 128-bit value, base64url)
```

**Replay prevention:** `x-agora-timestamp` MUST be within 300 seconds of the receiving Relay's clock. `x-agora-nonce` MUST NOT have been seen in the previous 600 seconds (the receiving Relay maintains a nonce cache with a 600-second TTL). Requests violating either condition MUST be rejected with HTTP 401.

**Manifest caching:** Receiving Relays cache peer manifests for 1 hour. On a cache miss or expiry, the Relay fetches a fresh manifest before verifying the request. If the fetch fails, the Relay retries once after 5 seconds before rejecting the request with HTTP 503.

**Reference implementations for RFC 9421:** [`httpbis-message-signatures`](https://github.com/nicowillis/httpbis-message-signatures) (JS), [`httpsig`](https://github.com/bblfish/httpSig) (Scala/JVM reference), [`go-http-signature`](https://github.com/go-fed/httpsig) (Go).

### 10.2.4 Trust Levels

Relay-to-relay trust is graduated. Trust level determines which Peer API operations a Relay is permitted to invoke and what gossip rate limits apply. Trust level is local state — each Relay maintains its own assessments independently. It is never gossiped or shared. Level 3 is set via local operator configuration and is appropriate for Relays operated by the same organization or well-known partner organizations.

| Level | Name | Criteria | Permissions |
|---|---|---|---|
| 0 | Unknown | No prior contact | Manifest fetch only; `announce` accepted for evaluation |
| 1 | Seen | Valid manifest, valid signature, first contact | `announce`, `health`; gossip rate-limited to 10 msg/s |
| 2 | Known | 7+ days of sustained peering without incident | Full gossip; `peers` accessible; 1000 msg/s |
| 3 | Trusted | Explicitly operator-configured | Full access; relaxed rate limits; no gossip throttling |

**Trust degradation:** A Relay that submits invalid signatures, sends malformed gossip, or repeatedly exceeds rate limits is downgraded to Level 0 and its DID is blocked for 24 hours. Repeated violations (3 or more incidents within 7 days) result in permanent operator-managed blocklisting.

### 10.2.5 Bootstrap: Joining the Mesh

A new Relay with no existing peers joins the gossipsub mesh using any of the following methods, attempted in parallel:

**Method 1 — Known peer URL.** The operator provides one or more peer Relay URLs in the startup configuration. The new Relay fetches `/.well-known/agora-relay` from each, verifies the manifest signature, sends `POST /v1/agora/peer/announce` with its own manifest, and on acceptance fetches `GET /v1/agora/peer/peers` to discover further Relays.

**Method 2 — Directory document.** The Relay fetches any Agora Relay directory document (§10.3.4.1) and contacts each listed Relay using Method 1.

**Method 3 — DNS-SD.** The Relay queries both `_agora-relay._udp.<domain>` (QUIC, preferred) and `_agora-relay._tcp.<domain>` (TCP fallback) SRV records:

```
_agora-relay._udp.example.com. SRV 10 0 9001 relay.example.com.
_agora-relay._tcp.example.com. SRV 20 0 443  relay.example.com.
_agora.relay.example.com.      TXT "did=did:key:z6MkRelay... manifest=https://relay.example.com/.well-known/agora-relay"
```

Lower SRV priority value means higher preference; QUIC (UDP) is preferred. Relays SHOULD publish both records. Relays that cannot expose UDP MUST publish only the TCP record.

**Method 4 — IPNS fallback.** The Relay resolves `/ipns/agora.protocol/relays/v1` for a community-maintained signed bootstrap list. This is the last resort.

A Relay is considered mesh-joined when it has Level 1 or higher trust with at least 3 peers and is participating in gossipsub fanout. It SHOULD continue discovering peers until it has at least 6 active connections (gossipsub's default mesh degree `D`).

### 10.2.6 Mesh Maintenance

**Heartbeat.** Relays MUST poll `GET /v1/agora/peer/health` from each peer every 60 seconds. A peer that returns `unhealthy` or fails to respond for 3 consecutive checks (180 seconds total) is marked unreachable. Its gossipsub connection is dropped; it remains in `knownPeers` for 7 days before removal, in case it recovers.

**Manifest refresh.** Relays re-fetch peer manifests every hour to detect key rotation and endpoint changes. A manifest whose `sig` no longer verifies is treated as a trust failure and the peer is downgraded to Level 0 pending re-verification.

**Key rotation overlap.** When rotating its signing key, a Relay MUST publish both the old and new keys in its manifest with a minimum 48-hour overlap, marking the old key with `"status": "deprecated"`. Peer Relays accept signatures from deprecated keys during this overlap window.

**Peer gossip.** When a Relay discovers a new valid peer, it SHOULD share that peer's `{ relayDID, manifestURL }` with its Level 2+ peers as a `RelayPeerAnnouncement` gossip message:

```json
{
  "@type": "RelayPeerAnnouncement",
  "relayDID": "did:key:z6MkNewRelay...",
  "manifestURL": "https://newrelay.example.com/.well-known/agora-relay",
  "announcedBy": "did:key:z6MkExistingRelay...",
  "ts": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

Receiving Relays verify the signature, independently fetch the new Relay's manifest, and decide whether to initiate peering. The announcement is a hint, not an authorization.

---

## 10.3 Discovery

*Binds: both.*

### 10.3.1 Gossip Protocol

Agora uses **libp2p gossipsub v1.1** for peer discovery, space and channel advertisement, live message delivery, and MLS handshake message delivery (Welcome, Commit, Proposal).

Each gossipsub **topic** maps to a specific scope:

| Topic pattern | Purpose |
|---|---|
| `v1/agora/discovery` | Global space/user advertisements |
| `v1/agora/space/<spaceCID>` | Space-scoped events: joins, state updates, moderation records |
| `v1/agora/channel/<channelToken>` | Per-channel messages and ephemeral presence/typing events |
| `v1/agora/mls/<groupID>` | MLS handshake messages: Welcome, Commit, Proposal |

The `v1/` prefix is the gossip protocol version for that topic family. A future breaking change to message framing on a topic introduces a `v2/` prefix. Relays MUST subscribe to all versions of topics they serve. Clients negotiate which version to publish on via the `negotiated.gossipVersion` field in the `RelayChallenge` (§11.6). During a version transition period, Relays bridge messages between `v1/` and `v2/` topic variants for the same channel.

**Reference implementations for libp2p gossipsub:**
- Go: [`go-libp2p-pubsub`](https://github.com/libp2p/go-libp2p-pubsub)
- Rust: [`libp2p` crate, `gossipsub` module](https://docs.rs/libp2p/latest/libp2p/gossipsub/)
- JS: [`@chainsafe/libp2p-gossipsub`](https://github.com/ChainSafe/js-libp2p-gossipsub)

### 10.3.2 Discovery Advertisements

A **SpaceAd** or **UserAd** message is gossiped periodically (default TTL: 60 seconds; re-advertised at 45 seconds to avoid expiry gaps):

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SpaceAd",
  "spaceCID": "bafyrei...",
  "name": "Example Corp Dev",
  "description": "Example Corp development coordination",
  "memberCount": 12,
  "relayHints": [
    "wss://relay.example.com",
    "wss://relay.example.net"
  ],
  "isPublic": true,
  "advertisedBy": "did:key:z6Mk...",
  "sig": "base64url...",
  "ts": "2026-03-12T00:00:00Z"
}
```

`relayHints` are connection hints only — clients are not required to use them and SHOULD attempt direct peer connections first. `relayHints` MAY include `.onion` addresses, clearnet HTTPS/WSS URIs, overlay-internal hostnames, and IPv6 address literals.

A SpaceAd is a voluntary CO publication; Relays forward it on `v1/agora/discovery` like any other gossip message.

> **Open (agora-pozi.12):** Whether any discovery path (SpaceAd or directory entry) requires an IO to publish CO information on the CO's behalf.

### 10.3.3 Relay Discovery Bootstrap

To bootstrap into the gossip network, a client needs at least one known peer. Agora supports the following bootstrap mechanisms, attempted in order:

1. **Directory sources** — user-configured URLs serving `RelayDirectory` or `SpaceDirectory` documents (§10.3.4); the primary bootstrap mechanism in practice.
2. **Previously cached relay list** — Relays successfully contacted in a prior session, stored locally with a staleness TTL of 7 days.
3. **Mainline DHT** — Relays announce themselves on the BitTorrent Mainline DHT (BEP-5) under a well-known infohash (§10.3.4.6); clients perform a `get_peers` lookup to find announcing relays (§10.3.4.6).
4. **DNS-SD** — `_agora-relay._udp` and `_agora-relay._tcp` mDNS for LAN or overlay discovery (§10.2.5).

### 10.3.4 Directory Documents

A **directory document** is a static JSON-LD file served at any reachable URL. It lists Spaces, Relays, or both, and MAY include references to other directory documents by URL. Users configure one or more directory source URLs in their client. Clients fetch and merge all configured sources on startup and refresh on a configurable interval (default: 1 hour).

Directory documents require no special server infrastructure. A file committed to a public GitHub repository and served via `raw.githubusercontent.com` or GitHub Pages is a valid directory source. So is an IPFS CID, a Cloudflare R2 bucket, a `.onion` URL, or any HTTPS endpoint returning valid JSON.

#### 10.3.4.1 Relay Directory

A `RelayDirectory` lists Relays available for client connection:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RelayDirectory",
  "schemaVersion": "1",
  "id": "https://raw.githubusercontent.com/example/agora-relays/main/relays.json",
  "name": "Community Relay List",
  "maintainer": "did:key:z6MkMaintainer...",
  "published": "2026-03-12T00:00:00Z",
  "ttl": 3600,
  "sig": "base64url...",
  "relays": [
    {
      "@type": "RelayEntry",
      "did": "did:key:z6MkRelay...",
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
      "tiers": [
        { "label": "free",     "maxBandwidthMbps": 1  },
        { "label": "standard", "maxBandwidthMbps": 10 }
      ],
      "note": "Community relay, no logging"
    }
  ],
  "includes": [
    "https://raw.githubusercontent.com/other-org/relays/main/relays.json"
  ]
}
```

`ttl` is the number of seconds before the client should re-fetch the document. `includes` is a list of other directory document URLs whose contents are merged into this one; clients MUST limit include recursion depth to 3 to prevent cycles. `sig` is the maintainer's Ed25519 signature over the document (excluding the `sig` field), signed per §13.1.1. Clients SHOULD verify the signature against the `maintainer` DID but MAY accept unsigned directories with a user-visible warning.

#### 10.3.4.2 Space Directory

A `SpaceDirectory` lists Spaces available for browsing or joining:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SpaceDirectory",
  "schemaVersion": "1",
  "id": "https://raw.githubusercontent.com/example/agora-spaces/main/spaces.json",
  "name": "Open Source Projects",
  "maintainer": "did:key:z6MkMaintainer...",
  "published": "2026-03-12T00:00:00Z",
  "ttl": 3600,
  "sig": "base64url...",
  "spaces": [
    {
      "@type": "SpaceDirectoryEntry",
      "spaceCID": "bafyrei...",
      "name": "Example Corp Community",
      "description": "Example Corp open source project",
      "iconCID": "bafyrei...",
      "memberCount": 340,
      "isPublic": true,
      "inviteURL": "https://invite.example.com/community",
      "relayHints": [
        "wss://relay.example.com"
      ],
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

`inviteURL` is a human-readable join link; the join flow itself is handled by the Space's invite mechanism (§4.3). `spaceCID` is the authoritative space identity — clients verify this against the space's genesis state document when connecting.

#### 10.3.4.3 Combined Directory

A single document MAY contain both `relays` and `spaces` arrays, typed as `AgoraDirectory`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "AgoraDirectory",
  "relays": [ ... ],
  "spaces": [ ... ],
  "includes": [ ... ]
}
```

#### 10.3.4.4 Client Behavior

On startup, the client fetches all configured directory sources in parallel. Results are merged: Relay lists are deduplicated by `did`; Space lists are deduplicated by `spaceCID`. The client attempts connection to the highest-priority available Relay (ordered by user preference). Previously cached Relays from prior sessions are used immediately while directory fetches are in flight.

Failed fetches are retried with exponential backoff (base 30 seconds, maximum 1 hour). A source that consistently fails for 7 days is flagged in the UI as unreachable; it is NOT silently removed from the configured source list. The user decides whether to remove it.

Clients MUST NOT auto-add directory sources from space state documents, relay advertisements, or any other protocol message without explicit user confirmation. Auto-population of directory sources is a privilege escalation vector.

#### 10.3.4.5 Content-Addressed Directories

A directory document MAY be addressed by CID instead of (or in addition to) an HTTPS URL:

```
ipfs://bafyrei.../relays.json
```

Clients resolve `ipfs://` URIs by fetching the blob from any relay's CAS endpoint (`GET /v1/agora/blob/{cid}`) or via their configured relay mesh.

#### 10.3.4.6 Mainline DHT Discovery

Agora uses the BitTorrent Mainline DHT (BEP-5, BEP-44) for two complementary purposes: relay bootstrapping and user endpoint discovery. Both are opportunistic — clients MUST degrade gracefully when UDP is unavailable (corporate firewalls, restrictive NAT) and fall back to other discovery mechanisms.

##### Relay Bootstrapping (BEP-5)

Relay operators announce their relay on Mainline by performing a BEP-5 `announce_peer` for the well-known infohash:

```
infohash = SHA1("agora-relay-v1")
```

> **Open (agora-pozi.20.16):** The infohash value and its derivation are not yet fixed.

The announced port is the relay's WebSocket port. Clients discovering a relay via this mechanism MUST still verify the relay's DID and TLS certificate before use (§10.3.4.7); a Mainline announcement is a hint, not an authorization.

Relay operators SHOULD re-announce every 30 minutes. Clients performing a cold-start bootstrap issue a `get_peers` lookup for this infohash and attempt connection to returned peers.

##### User Endpoint Discovery (BEP-44 / Pkarr)

A `did:key` user MAY publish a BEP-44 mutable item on Mainline to advertise their current relay endpoints, profile CID, and KeyPackage supply CID. This enables contact initiation without requiring a shared directory or prior relay knowledge.

**Key derivation.** The BEP-44 key is the user's raw 32-byte ed25519 authentication public key, extracted directly from their `did:key` identifier. No additional key material is required.

**Record format.** The BEP-44 value is a compact DNS packet (Pkarr format) containing TXT resource records:

```
_agora.             TXT  "v=1"
_relay._agora.      TXT  "wt=https://relay1.example.com/v1/agora/wt"
_relay._agora.      TXT  "wt=https://relay2.example.com/v1/agora/wt"
_profile._agora.    TXT  "cid=bafyrei..."
_kp._agora.         TXT  "cid=ipfs://bafyrei.../keypackages.cbor;n=50"
```

Multiple `_relay._agora` TXT records are permitted; clients treat them as an ordered preference list. All fields are optional except `v`.

| Record | Key | Value | Required |
|---|---|---|---|
| `_agora` | `v` | Schema version (`1`) | Yes |
| `_relay._agora` | `wt` or `ws` | WebTransport or WebSocket relay endpoint URL | No |
| `_profile._agora` | `cid` | `ipfs://` URI of the user's current profile IPLD node | No |
| `_kp._agora` | `cid` | `ipfs://` URI of the user's KeyPackage supply batch; `n` = count | No |

The total DNS packet MUST fit within 1000 bytes (BEP-44 value limit). In practice a record with two relay endpoints, a profile CID, and a KeyPackage CID occupies approximately 350–400 bytes.

**Verification.** BEP-44 mutable items are self-certifying: the DHT node returns the value together with the ed25519 signature, and the lookup key is the public key itself. Clients MUST verify the signature before using any field. A valid signature proves the record was produced by the holder of the DID's authentication key.

**Lookup procedure.**
1. Decode the `did:key` identifier to recover the raw 32-byte ed25519 public key.
2. Issue a BEP-44 `get` query for that key.
3. Verify the returned signature against the key.
4. Parse TXT records and use relay endpoints, profile CID, or KeyPackage supply CID as needed.

**Publication and refresh.** Clients SHOULD publish their record on first login and re-publish every 2 hours. BEP-44 mutable items have no explicit TTL but decay from the DHT within approximately 2 hours without re-announcement. Stale or absent records are not an error — clients fall back to other discovery mechanisms.

**Scope.** This mechanism applies only to `did:key` users. `did:web` users have a domain-anchored DID document served over HTTPS; their relay endpoints are discoverable via standard DID resolution and do not require Mainline publication.

#### 10.3.4.7 Trust Model

Being listed in a directory confers no trust. A Relay in a directory is trusted only to the extent that its DID verifies against its TLS certificate and signed advertisements. A Space in a directory is trusted only to the extent that its `spaceCID` verifies against its genesis state document. A malicious directory entry pointing at a rogue Relay produces a DID mismatch at connection time and is rejected.

Directory maintainers are identified by their `maintainer` DID and signature. There is no global authority over directory content. Multiple competing directories can coexist and are all valid. Clients merge them all.

---

## 10.4 Relay Behavior

*Binds: IO.*

### 10.4.1 Relay Knowledge Constraints

A conformant Relay is explicitly designed to know as little as possible about the traffic it routes. The following is both a design target and a compliance requirement: a Relay operator responding to a legal demand or subpoena MUST be able to honestly testify to all of the following:

- I do not know who my users are (no identity registration, no account system, no persistent user records).

> **Open (agora-pozi.9):** The client-relay handshake (§11.6) authenticates member DIDs, which contradicts this statement; admission without identity is unresolved (ARCHITECTURE §7 item 9, §11 Q2).

- I do not know who is in any group (channel membership is not visible at the relay layer; `channelToken` is epoch-rotating and non-reversible without the epoch secret).
- I do not know who sent any message (sealed sender design; sender DID is inside the MLS ciphertext).
- I store nothing after delivery beyond the configured retention window, and nothing with a message expiry past that expiry — except CIDs pinned under an instruction authorized by the epoch access proof (ARCHITECTURE §6.2), which are retained until unpinned the same way.
- The encrypted blobs I forward and cache are opaque to me.

These statements are the IO side of ARCHITECTURE §4: what a legal demand on a Relay operator yields is bounded by the observation budget in ARCHITECTURE §5.

Any protocol extension or Relay implementation that makes any of these statements false introduces a legal liability surface for operators and a surveillance surface for adversaries. Such extensions MUST be explicitly opt-in and clearly documented as degrading the Relay's metadata-blindness guarantees.

### 10.4.2 Relay-Blind Fan-out

Relays route messages by `channelToken`, not by channel CID or member identity. The routing table maps `channelToken` → set of subscriber connections. Relays MUST NOT:

- Maintain a mapping from `channelToken` to channel CID or Space CID.
- Maintain a mapping from `channelToken` to member DIDs.
- Log sender/recipient pairs for any message.
- Retain message envelopes beyond the configured retention window or message expiry, whichever is sooner.

The `channelToken` rotates with every MLS epoch. A Relay that captures routing tables across epochs cannot correlate them without also capturing the epoch secrets, which it has no access to.

### 10.4.3 Conformance Requirements

A conformant Relay MUST:

- Implement WebSocket transport (§11.2); WebTransport is RECOMMENDED.
- Implement the client-relay authentication handshake (§11.6).
- Implement the KeyPackage Store API (§5.2.1.1).
- Implement the Peer API and relay-to-relay authentication (§10.2).
- Verify the epoch access proof on every envelope before caching or forwarding it, and drop envelopes that fail verification (ARCHITECTURE §6.2).
- Respect `expiryHint` on cached message envelopes (§5.2.4).
- Apply per-`channelToken` rate limits (§12.5).
- Publish a Relay Manifest at `/.well-known/agora-relay` (§10.2.1), declaring its connection-log retention and any observation-budget extensions.
- Maintain heartbeat polling of peer relays (§10.2.6).
- Route messages by `channelToken` only; never attempt to resolve tokens to identities.
- Cache message envelopes up to the lesser of: configured retention window (default 30 days) or the envelope's `expiryHint`.
- Pin IPFS content stored under a `RelayServiceAgreement` within the agreement's retention window.
- Honor pin and unpin instructions authorized by the epoch access proof, retaining pinned CIDs regardless of retention window or `expiryHint` until unpinned (ARCHITECTURE §6.2).
- Enforce the storage and bandwidth quotas set by each `RelayServiceAgreement` (§10.5.1), keyed to the agreement and never to member identity.
- Validate outer envelope structure and `channelToken` format before forwarding; drop malformed envelopes silently.
- Support IPv6 on all endpoints; use bracket notation for IPv6 literals in advertised URIs.
- Enforce per-`channelToken` rate limits as the primary spam control mechanism; per-IP limits MUST NOT be the sole mechanism.

> **Open (agora-pozi.8):** The epoch access proof mechanism is a candidate pending review against MLS security properties (ARCHITECTURE §8 Q1).

> **Open (agora-pozi.10):** Whether a Relay hosts a KeyPackage store at all, or KeyPackages are located through the user's DID document (ARCHITECTURE §8 Q3).

A conformant Relay MUST NOT:

- Attempt to decrypt MLS ciphertext.
- Log or retain sender DIDs (sealed sender design means the Relay never has them).
- Use per-IP rate limiting as the sole spam control mechanism.
- Reuse a consumed KeyPackage.
- Modify gossipsub messages in transit.
- Make or enforce decisions about membership, roles, moderation or content, including bans, timeouts, deletes and pin limits; these are enforced by MLS removal and member clients (ARCHITECTURE S2, §5.2.2).
- Sign Space state, channel state, role assignments, moderation records or retention policy (ARCHITECTURE S4).
- Observe, log or retain anything outside the ARCHITECTURE §5 observation budget, except extensions a CO has opted into and the Relay declares in its manifest (ARCHITECTURE S6).

A conformant Relay SHOULD:

- Announce itself on `v1/agora/discovery` with a signed `RelayAd` including all available endpoint URIs.
- Operate a Tor hidden service endpoint to protect operator IP and support Tor-connected clients.
- Maintain peering connections to at least 3 other known Relays.
- Offer an HTTP API for history fetch: `GET /v1/agora/history/<channelToken>?before=<cid>&limit=50`.
- Implement gossipsub peer scoring to limit amplification attacks.

Relay federation is permissionless. Any Relay that speaks the protocol may join the mesh.

---

## 10.5 Relay Service Agreements and Abuse Control

*Binds: both.*

Agora Relays incur real costs: bandwidth, compute, storage, legal exposure, and abuse handling. This section specifies the `RelayServiceAgreement`, the only binding between a CO and an IO (ARCHITECTURE S7), and proof-of-work as non-monetary abuse control. Commercial terms between CO and IO are agreed out of band and are outside the protocol.

Both mechanisms are **optional extensions** to the core protocol. A Relay that serves only private, trusted traffic requires neither.

### 10.5.1 Relay Service Agreements

A `RelayServiceAgreement` is a bilaterally signed document between a CO billing DID and a Relay DID specifying retention, quotas, SLA terms, and the Relay's observation-budget declaration. It names no Space and no channel (ARCHITECTURE §6.1). Both signatures are made per §13.1.1.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RelayServiceAgreement",
  "id": "urn:agora:rsa:bafyrei...",
  "relay": "did:key:z6MkRelay...",
  "billing": "did:key:z6MkBilling...",
  "retentionDays": 90,
  "bandwidthTierGbPerMonth": 100,
  "storageQuotaGb": 50,
  "observationBudget": {
    "connectionLogRetentionDays": 7,
    "extensions": []
  },
  "validFrom": "2026-03-12T00:00:00Z",
  "validUntil": "2027-03-12T00:00:00Z",
  "keyPackageSLA": {
    "minimumCount": 20,
    "alertThreshold": 5,
    "alertMechanism": "both",
    "guaranteedRetentionDays": 90,
    "replenishFromIPFS": true
  },
  "relaySig": "base64url...",
  "billingSig": "base64url..."
}
```

`billing` is a DID the CO dedicates to agreements. It MUST NOT appear in Space state, SpaceAds, directory documents, or any other record that identifies a Space. A CO MAY use one billing DID for all of its Spaces; doing so is what gives each Space its anonymity set at the Relay (ARCHITECTURE §5 item 6).

The agreement is private between the CO and the Relay. It MUST NOT be gossiped, stored in Space state, or published. Multiple concurrent agreements (multiple Relays serving the same CO) are valid and encouraged for redundancy.

Coverage is registered per MLS group. The CO's registration service submits an `AccessChainRegistration` to the Relay carrying the group's first-epoch access public key (§5.2.2); from then on the Relay follows the chain through `accessKeyAnnouncement`s. Members who create a group request registration from the CO's service; they never hold the billing key.

```json
{
  "@type": "AccessChainRegistration",
  "agreement": "urn:agora:rsa:bafyrei...",
  "epoch": 0,
  "channelToken": "base64url...",
  "accessPublicKey": "z6Mk...",
  "billingSig": "base64url..."
}
```

A registration carries nothing that identifies a Space or channel. The CO's registration service SHOULD batch registrations and add random delay, so that registration timing does not reveal when a particular Space or channel was created.

`storageQuotaGb` and `bandwidthTierGbPerMonth` are the quotas the Relay enforces for this agreement (§10.4.3).

`observationBudget` records the connection-log retention (ARCHITECTURE §5 item 1) and any opt-in observation-budget extensions (ARCHITECTURE S6) the CO has agreed to. The Relay MUST declare the same values in its manifest (§10.2.1) and MUST NOT exceed them.

`keyPackageSLA` is an optional clause that elevates the relay's KeyPackage Store behavior from best-effort to a contractual obligation (§5.2.1.1). When present, all fields are required and the relay's conformance to them is a term of the agreement.

Relays publish their service tiers in their `RelayAd`:

```json
{
  "@type": "RelayAd",
  "did": "did:key:z6MkRelay...",
  "endpoint": "https://relay.example.com",
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
  "sig": "base64url...",
  "ts": "2026-03-12T00:00:00Z"
}
```

### 10.5.2 Proof-of-Work Spam Deterrence

Channels that want spam deterrence MAY require proof-of-work:

```json
{ "@type": "MessageFeePolicy", "scheme": "pow", "difficulty": 18 }
```

`difficulty` is the number of leading zero bits required in the hash of the message envelope. A client sending a message computes a nonce such that `SHA256(envelopeBytes || nonce)` has at least `difficulty` leading zero bits, then includes the nonce in the outer `RoutingEnvelope`:

```json
"powProof": {
  "@type": "PowProof",
  "nonce": "base64url...",
  "difficulty": 18
}
```

The Relay verifies the PoW before forwarding against its own minimum difficulty. The Relay cannot map a `channelToken` to a channel's `MessageFeePolicy` (§10.4.2), so member clients enforce the channel's difficulty and drop envelopes that do not meet it. Difficulty 18 requires ~262,000 SHA-256 hash operations — roughly 10–50ms on a modern CPU, imperceptible to a human sender, but economically prohibitive for bulk message flooding.

