# Agora Relay Operations Guide

**Version:** 0.1 (Draft)
**Date:** 2026-10-16
**Status:** Draft, non-normative. ARCHITECTURE.md and the protocol specification in `spec/` govern on conflict.
**Companion to:** the current Agora Protocol Specification draft in `spec/` (v0.2 draft; every protocol surface at v1, spec §1.1)

---

## Abstract

This document is the operational companion to the Agora Protocol Specification. It covers how an infrastructure engineer deploys, configures, operates, monitors, upgrades, and decommissions an Agora relay in production. The protocol spec defines protocol behavior.

A relay is an Infrastructure Operator (IO) component (ARCHITECTURE §2.1). It carries ciphertext and decides nothing about any community. It never knows membership, senders, or which Space or channel a routing token belongs to. Everything that requires that knowledge (identity provisioning, KeyPackage hosting, compliance logging, archives, gateways, bridges) is a Communications Operator (CO) component and runs on CO infrastructure, not in the relay.

The audience is infrastructure engineers, platform teams, and site reliability engineers (SREs) at enterprises or service providers running an Agora relay. It assumes familiarity with Linux systems administration, container orchestration (Docker/Kubernetes), and basic distributed systems concepts. It assumes no deep knowledge of MLS or DIDs and cites protocol concepts by section number where relevant.

---

## Key Words

This guide is non-normative and uses no BCP 14 key words. Where it restates a requirement of the protocol specification or ARCHITECTURE.md, it cites the section that states it. Everywhere else, "must" and "should" describe how this relay implementation behaves or what this guide advises.

---

## Table of Contents

1. Overview
2. Deployment Architecture
3. Configuration
4. Deployment Packaging
5. Relay Admin API
6. Observability
7. Alerting
8. Backup and Restore
9. Upgrade Procedure
10. Key Management
11. Network Requirements
12. Capacity Planning
13. Security Hardening
14. Enterprise Integration Deployment
15. Multi-Relay HA Deployment
16. Decommissioning
17. Abuse Handling

---

## 1. Overview

### 1.1 Purpose and Scope

This document describes how to run an Agora relay across its lifecycle: initial deployment, day-to-day operations, observability, upgrading, and decommissioning. It also describes this implementation's Admin API (§5), which the protocol spec does not cover.

**Section references.** Three kinds of reference appear in this document, always written distinctly:

- "spec §N.N" is a section of the Agora Protocol Specification in `spec/` (referred to throughout as "the protocol spec"), for example spec §10.4.3.
- "ARCHITECTURE §N" and "ARCHITECTURE S1" through "S8" are sections and rules of ARCHITECTURE.md.
- A bare "§N.N" is a section of this document.

Where this document and the protocol spec or ARCHITECTURE.md disagree, those documents govern.

### 1.2 Relationship to the Protocol Specification

The protocol spec lists what a conformant relay must and must not do (spec §10.4.3). In summary, a relay:

- speaks the live CBOR message set over WebSocket, and preferably WebTransport (spec §11.1, spec §11.2, spec §11.4)
- runs the unauthenticated client hello and connection admission controls (spec §11.6)
- implements the Peer API and relay-to-relay authentication (spec §10.2)
- accepts `AdmissionKeyRegistration` and `AdmissionKeyDeregistration` requests from COs at its `admissionKeys` endpoint (spec §10.5.3)
- carries only the `channelToken`s registered with it under a current `ServiceAgreement` (spec §10.3.1)
- verifies `admissionSig` on every envelope against the registered admission public key (spec §10.5.4)
- holds recent envelopes and blobs for each agreement's retention (spec §10.4.4, spec §10.4.6)
- enforces each agreement's quotas (spec §10.5.1)
- publishes a relay manifest with its observation-budget declaration (spec §10.2.1)

A relay stores no KeyPackages, authenticates no client identity, accepts no DID-signed user records from clients, and signs no community state. This document covers how to deploy and operate that relay: config file format, packaging, observability, backup procedures, network requirements, and operational runbooks.

The binding between a relay operator and each CO it serves is a `ServiceAgreement` with `serviceType` `relay` (ARCHITECTURE S7, spec §10.5.1). It is signed by the relay (`provider`) and by the CO's billing DID (`billing`), names no Space or channel, and is private between the two parties. It sets retention (`retentionDays`), quotas, the CO's abuse and takedown `contact`, and the connection-log retention the relay declares in its manifest. Under it the CO's registration service registers the channel admission public keys whose envelopes the relay admits (spec §10.5.3). Commercial terms are agreed out of band and are outside the protocol and this document.

Enterprise components such as the employer DID provisioning service and the Purview bridge are CO components. They are not deployed as part of a relay and need no relay configuration. §14 explains the boundary.

### 1.3 Who This Document Is For

- **Infrastructure engineers** provisioning relay infrastructure on cloud or on-premises hardware.
- **Platform teams** integrating the relay into an existing Kubernetes or ECS environment.
- **SREs** responsible for relay availability, monitoring, and incident response.
- **Security engineers** reviewing the relay's security posture.

This document is not aimed at end users, Space owners, or Agora client developers.

---

## 2. Deployment Architecture

### 2.1 Component Overview

A production Agora relay deployment has these components:

```
┌──────────────────────────────────────────────────────────────┐
│  Internet-facing                                              │
│                                                               │
│  ┌─────────────────┐   ┌─────────────────┐                   │
│  │  Load Balancer  │   │  Tor Hidden Svc │ (optional)         │
│  │  (QUIC + TCP)   │   │  (WebSocket)    │                    │
│  └────────┬────────┘   └────────┬────────┘                   │
└───────────┼─────────────────────┼──────────────────────────── ┘
            │                     │
┌───────────┼─────────────────────┼──────────────────────────── ┐
│  Relay tier                     │                              │
│           ▼                     ▼                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  agora-relay process                                   │  │
│  │                                                        │  │
│  │  • WebTransport (QUIC/HTTP3)  /v1/agora/wt             │  │
│  │  • WebSocket                  /v1/agora/ws             │  │
│  │  • Peer API                   /v1/agora/peer           │  │
│  │  • JMAP Envelope sync         /v1/agora/jmap           │  │
│  │  • Blob CAS (public read)     /v1/agora/blob/{cid}     │  │
│  │  • Admission key registration /v1/agora/admission-keys │  │
│  │  • Push proxy client          (outbound)               │  │
│  │  • Gossipsub peer             (QUIC UDP)               │  │
│  │  • Admin API                  /admin  (internal only)  │  │
│  │  • Prometheus metrics         /metrics (internal only) │  │
│  └───────────┬────────────────────────────────────────────┘  │
│              │                                                 │
│    ┌─────────┼──────────┐                                     │
│    ▼         ▼          ▼                                      │
│  ┌──────┐ ┌──────┐ ┌────────┐                                 │
│  │  DB  │ │ Blob │ │  SFU   │ (optional)                     │
│  │(PG / │ │store │ │        │                                 │
│  │SQLite│ │(CAS) │ │        │                                 │
│  └──────┘ └──────┘ └────────┘                                 │
└──────────────────────────────────────────────────────────────┘
```

**Required components:**
- `agora-relay`: the relay process. Implements all protocol-level behavior.
- Database: SQLite for development/small deployments; PostgreSQL for production. Stores held ciphertext envelopes keyed by `channelToken`, the peer table, loaded agreements, registered admission public keys with their tokens and the `ts` of the last accepted registration request per token (spec §10.5.3), pin state, quota counters, and push registrations.
- Blob store: content-addressed storage (CAS) for opaque blobs: the root and chunk blocks of encrypted files (spec §14.3.4), group-encrypted blobs (spec §3.4), pinned CIDs, and records a CO explicitly publishes, such as public Space state and directory documents (spec §10.4.3). Each blob is held under every `channelToken` for which it was uploaded, replicated, pulled or pinned, and is charged to and retained for the agreement of each such token (spec §10.4.4). Blocks are keyed by multihash, so one stored block answers to both its `raw` and its `dag-pb` CID (spec §10.4.4). Backed by the local filesystem (`blob_backend = "local"`) or an S3-compatible object store (`blob_backend = "s3"`) for high-availability (HA) deployments.

**Blob access.** Blobs are reachable through exactly two public interfaces, both on the client-facing port:

- `GET /v1/agora/blob/{cid}`: the CAS read endpoint (spec §10.4.4). Unauthenticated, rate-limited per network address (spec §11.6), and served with `Access-Control-Allow-Origin: *` so browser clients can fetch directly. The content is either ciphertext that only group members can decrypt or a record the CO chose to publish. A request may carry `?token=<channelToken>`, which asks for pull-through (below).
- JMAP upload and download (`/v1/agora/jmap/upload/{accountId}`, `/v1/agora/jmap/download/{accountId}/{blobId}/{name}`, paths under `endpoints.jmapSync`, spec §11.8.1). Downloads follow the same rules as the CAS endpoint. An upload is accepted only with an `Agora-Storage-Auth` header signed with the admission key registered for a `channelToken` (spec §10.4.4, spec §11.8.2). It counts against the storage quota of the agreement under which that key is registered and is kept for that agreement's retention, or longer if a `PinInstruction` signed with the same key pins it (spec §11.4).

These two HTTPS interfaces are the client fetch path for every blob, including `ipfs://` URIs (spec §10.4.4). "Pinning" means retention in the local blob store under a pin instruction, not pinning on the public IPFS network. Pinning a `dag-pb` root block also pins every chunk block it links to (spec §10.4.4).

There is no admin read endpoint for blob or envelope bytes. The Admin API has two content operations, both for takedown handling (§17): `GET /admin/content/{cid}` returns the agreement and contact for a CID, and `DELETE /admin/content/{cid}` deletes it (§5.2). Both sit behind the same bearer-token authentication as every other admin endpoint.

**Blob replication.** A client uploads each blob once, to any one relay in the channel's relay list, and the relays carrying that token replicate it among themselves over the Peer API (spec §10.2.2, spec §10.4.4). A file of up to 2^32 bytes arrives as a root block plus up to 16,384 chunk blocks of 256 KiB each, every one a separate upload and a separate CID (spec §14.3.4).

- *Eager replication.* After answering the upload, the relay pushes the blob to other relays carrying the token (the peers it knows to be subscribed to the token's channel topic) with `POST /v1/agora/peer/blob?token=<channelToken>`, forwarding the upload's `Agora-Storage-Auth` header unchanged. It pushes until at least `replicationFloor` relays, counting itself, hold the blob. If fewer relays carry the token, it pushes to every one of them. `replicationFloor` comes from the agreement under which the token is registered here; it defaults to 2 and is not a relay setting (spec §10.5.1). A peer answers 201 (stored or already held), 403 (header missing or failing its checks), 404 (token not registered there) or 507 (that agreement's storage quota is full). The relay retries peers that are unreachable or answer 507 with exponential backoff for at least 24 hours, then stops and keeps its own copy (spec §10.4.4).
- *Pull-through.* When a client fetch with `token` names a CID this relay lacks, and the token is registered here under a current agreement, the relay fetches it from a relay carrying the token with `GET /v1/agora/peer/blob/{cid}?token=<channelToken>`, checks it against the CID, stores it under the token and serves it. The `token` on a peer pull names the token under which the requester will store the blob; the responding relay does not check it and serves any blob it holds (spec §10.2.2). A fetch without `token`, or for a token not registered here, gets 404 and triggers nothing.
- *Inbound.* The relay accepts pushed blobs only for tokens registered with it under a current agreement. For each push it verifies the forwarded `Agora-Storage-Auth` header: `admissionSig` against the key registered for the push's token, and `sha256` against the body. It does not check `expires` or `nonce`. It answers 403 if the header is missing or fails these checks (spec §10.2.2). It verifies each blob against its CID, charges it to that agreement's storage quota and keeps it for that agreement's `retentionDays` from receipt. It never pushes, pulls or caches blobs for any other token. A blob already held under another token gains the new token as a holder and is charged to that token's agreement as well; a `pin` for a held CID does the same (spec §10.4.4).
- *Seeding.* A CO that adds this relay to a channel's relay list may send a `seed` pin instruction listing CIDs, signed with the channel's admission key (spec §11.4). The relay acknowledges at once, then pulls each listed CID it lacks from other relays carrying the token and keeps it for the ordinary retention window, without a pin exemption.

Peer API blob requests are authenticated with HTTP Message Signatures like the rest of the Peer API (spec §10.2.3) and travel on port 443 with the relay's other traffic (§11.1). Replication tells a relay nothing new: a peer that pushes or pulls a token's blob already carries that token, which the channel topic mesh shows anyway, and blobs are ciphertext or published records that any requester may fetch (spec §10.4.4). A Level 1 peer may pull blobs and push blobs for tokens registered here (spec §10.2.4).

**Public IPFS.** Spec §10.4.4 forbids announcing on, providing to or requesting from the public IPFS network (its DHT, public Bitswap peers or public gateways) any blob that is not public content, and permits Bitswap for private ciphertext only among a user's own devices and between those devices and the CO archive. Relays exchange blobs only over the Peer API, never by Bitswap, and this relay runs no IPFS node. It also never publishes public content to IPFS, because it cannot tell public content from ciphertext by looking at the bytes. A CO that wants its published records, or the blobs of a public broadcast channel, on the public IPFS network publishes them from its own node.

**Admission key registration.** COs send `AdmissionKeyRegistration` and `AdmissionKeyDeregistration` requests to `POST /v1/agora/admission-keys` on the client-facing port. The URL is published as `endpoints.admissionKeys` in the manifest and equals the `endpoint` of each relay agreement (spec §10.2.1, spec §10.5.1). Each request is one CBOR-encoded typed payload envelope signed by the agreement's billing DID. The relay verifies it, applies it entirely or not at all, and answers 204 or one of the error codes of spec §10.5.3. When it applies a registration whose key names a token in `replaces`, it sends each connection subscribed to that token an `Error` with code `token-rotated` and keeps those subscriptions open (spec §11.4). Registrations are never gossiped and the relay reveals them to no one but the CO that sent them (spec §10.4.3).

**Optional components:**
- SFU (Selective Forwarding Unit): voice/video channel routing (spec §6.6). An IO component that is never an MLS member. Can be a separate process or a separate host.
- Sequencer: stamps an order on encrypted operations for `sequenced-v1` JMAP types and on concurrent Commits (spec §14.4.1). A CO engages a sequencer under a separate `ServiceAgreement` with `serviceType` `sequencer` and registers its channels' admission keys there as with a relay. Spec §14.4.1 advises a CO to designate a relay it already holds an agreement with. A relay operator asked to do this runs the sequencer service beside the relay under the same `relayDID`, declares `sequencer-v1` in the manifest (spec §10.2.1), and serves it at the endpoint the CO names in its designation (conventionally `/v1/agora/seq`). The sequencer is not part of the relay process described here. It learns what a relay holding the same registrations learns (spec §14.4.6).
- Push proxy: mobile push notification wake-ups (spec §11.7). Can be co-located or externally hosted; a CO may run its own instead (spec §11.7).

CO components (employer DID provisioning service and KeyPackage host, compliance logger, Purview bridge, gateways) are not part of a relay deployment. See §14.

### 2.2 Single-Node Deployment

Single-node deployment is appropriate for:
- Development and testing environments.
- Small organizations with fewer than about 200 active users.
- Enterprise deployments where the relay serves only internal users on a reliable LAN.

In a single-node deployment, all components run on one host or in one Docker Compose stack. SQLite is acceptable as the database backend. The local filesystem blob store (`blob_backend = "local"`) is sufficient. No load balancer is required; the relay process handles TLS directly.

### 2.3 Multi-Node HA Deployment

Multi-node HA deployment is required when:
- The relay must survive single-node failure.
- Active user count exceeds about 500.
- The relay serves public community traffic where downtime causes user-visible disruption.

§15 covers multi-node HA in detail. In short: PostgreSQL with streaming replication replaces SQLite; multiple relay instances share the database and an S3-compatible blob store backend (AWS S3, MinIO, Backblaze B2, or equivalent); a load balancer with QUIC affinity fronts the relay instances.

### 2.4 External Dependencies

| Dependency | Role | Required |
|---|---|---|
| PostgreSQL 15+ or SQLite 3.40+ | Held envelopes, peer table, agreements, registered admission keys, pin state, quota counters, push registrations | Yes |
| Blob store (local filesystem or S3-compatible) | Content-addressed storage for opaque blobs and CO-published records | Yes |
| Let's Encrypt / ACME CA | TLS certificate provisioning | Yes (or bring your own cert) |
| DNS provider | A/AAAA records, SRV records for DNS-SD discovery | Yes |
| APNs / FCM credentials | Push notification delivery | Only if running push proxy |
| AWS Secrets Manager / Vault | Secrets management | Recommended |
| Prometheus + Grafana | Metrics and dashboards | Recommended |

### 2.5 Network Topology Requirements

The relay requires these network interfaces:

- **Public interface.** Handles WebTransport (QUIC/UDP), WebSocket (TCP), JMAP HTTPS, the blob CAS endpoint, the admission key registration endpoint, and the well-known relay manifest endpoint. Must be reachable from the internet, or at least from the COs' registration services for the registration endpoint.
- **Peer gossip interface.** Handles libp2p gossipsub QUIC connections from peer relays. It may be the same public interface or a separate interface. It must not be firewalled from peer relay IP ranges.
- **Internal/management interface.** Handles the Admin API, Prometheus metrics, and database connections. It must not be reachable from the internet.

---

## 3. Configuration

### 3.1 Config File Location and Format

The relay reads configuration from a TOML file. The default path is `/etc/agora-relay/relay.toml`. Override with the `--config` flag or the `AGORA_CONFIG` environment variable.

Secrets (signing keys, database passwords, admin tokens) must not be placed in the config file. Use environment variable overrides (§3.3) or a secrets manager integration (§3.4).

### 3.2 Full Configuration Reference

```toml
# /etc/agora-relay/relay.toml
# All fields shown. Defaults annotated with "# default: <value>".

# ─────────────────────────────────────────────
# [server]: network and TLS configuration
# ─────────────────────────────────────────────
[server]

# Hostname at which this relay is publicly reachable.
# Used to construct endpoint URLs in the relay manifest.
hostname = "relay.example.com"

# WebTransport (QUIC/HTTP3) listen address.
# default: "0.0.0.0:443"
webtransport_addr = "0.0.0.0:443"

# WebSocket (WSS) listen address.
# If webtransport and websocket share port 443, the relay
# distinguishes them by ALPN ("h3" vs "http/1.1"/"h2").
# default: "0.0.0.0:443"
websocket_addr = "0.0.0.0:443"

# Peer API and libp2p (gossipsub) listen address.
# This port must be reachable from peer relays. On 443 the relay
# shares one QUIC listener with HTTP/3 and tells connections apart
# by ALPN ("h3" vs "libp2p"), per spec §10.2. An operator who cannot
# share 443 may pick another port; the manifest endpoints, multiaddrs
# and SRV records then carry that port.
# default: "0.0.0.0:443"
peer_addr = "0.0.0.0:443"

# Admin API listen address. must be bound to a non-public interface.
# default: "127.0.0.1:9099"
admin_addr = "127.0.0.1:9099"

# Prometheus metrics listen address.
# default: "127.0.0.1:9100"
metrics_addr = "127.0.0.1:9100"

# TLS certificate and private key paths.
# For Let's Encrypt automation, set tls_acme = true instead.
tls_cert = "/etc/agora-relay/tls/fullchain.pem"
tls_key  = "/etc/agora-relay/tls/privkey.pem"

# Let's Encrypt / ACME automatic certificate management.
# When true, tls_cert and tls_key are managed automatically.
# default: false
tls_acme = false

# ACME email address (required when tls_acme = true).
tls_acme_email = "relay-admin@example.com"

# ACME directory URL. Default is Let's Encrypt production.
# Use "https://acme-staging-v02.api.letsencrypt.org/directory" for testing.
# default: "https://acme-v02.api.letsencrypt.org/directory"
tls_acme_directory = "https://acme-v02.api.letsencrypt.org/directory"

# Maximum number of concurrent client connections.
# default: 10000
max_connections = 10000

# Accept new client connections. Set false to drain before
# decommissioning (§16.3). default: true
accepting_new_connections = true

# Maximum number of concurrent JMAP requests.
# default: 200
max_jmap_concurrent = 200

# Minimum TLS version. must be "1.3" for WebTransport.
# WebSocket may fall back to 1.2 for compatibility with older clients.
# default: "1.3"
tls_min_version = "1.3"

# Enable Tor hidden service (optional).
# Requires a local Tor daemon with control port access.
# default: false
tor_enabled = false

# Tor control port address (required when tor_enabled = true).
tor_control_addr = "127.0.0.1:9051"

# Path to the Tor hidden service key directory.
tor_hidden_service_dir = "/var/lib/tor/agora-relay"

# Plaintext WebSocket listener for onion traffic (used when
# tor_enabled = true). Must be bound to loopback; Tor forwards onion
# port 80 here, and the onion service provides the encryption (§11.5).
# default: "127.0.0.1:8080"
tor_ws_listen = "127.0.0.1:8080"

# ─────────────────────────────────────────────
# [identity]: relay DID and signing key
# ─────────────────────────────────────────────
[identity]

# Relay DID. A relay with a public DNS name uses did:web anchored to
# that name, so that key rotation keeps the DID (spec §10.2.1). A relay
# on a private overlay, Tor-only or air-gapped network may use did:key.
# This value is public. The signing key is a secret; see §3.3.
relay_did = "did:web:relay.example.com"

# Operator DID (the organization or person operating this relay).
operator_did = "did:web:example.com:agora:relay-operator"

# Human-readable operator name, appears in relay manifest.
operator_name = "Example Corp Relay"

# Admin contact email, appears in relay manifest.
admin_contact = "relay-admin@example.com"

# Abuse contact email, appears in relay manifest.
abuse_contact = "abuse@example.com"

# Relay description, appears in relay manifest.
description = "Example Corp internal relay, US-East"

# Geographic region hint, appears in relay manifest.
region = "us-east"

# Path to the relay signing key (Ed25519 private key, PEM format).
# STRONGLY prefer setting via AGORA_SIGNING_KEY_PATH env var or
# a secrets manager. If set here, file permissions must be 0600.
# default: "/etc/agora-relay/keys/relay-signing.key"
signing_key_path = "/etc/agora-relay/keys/relay-signing.key"

# Previous signing key, published as "deprecated" during a key rotation
# overlap window (spec §10.2.6; procedure in §10.1).
# default: "" (no rotation in progress)
signing_key_deprecated_path = ""

# Manifest key ids published with "status": "revoked" after a key
# compromise (spec §10.2.6, spec §12.12). Peers reject every signature
# made with a revoked key. Procedure in §10.1.
# default: []
revoked_key_ids = []

# PKCS#11 provider library for HSM-backed signing key.
# When set, signing_key_path is the PKCS#11 key label, not a file path.
# default: "" (disabled; use software key)
pkcs11_provider = ""

# Key expiry duration. The relay manifest key entry will have
# expiresAt = now() + key_expiry_days at manifest publication time.
# default: 365
key_expiry_days = 365

# ─────────────────────────────────────────────
# [storage]: database and blob store configuration
# ─────────────────────────────────────────────
[storage]

# Database backend: "sqlite" or "postgres".
# default: "sqlite"
db_backend = "postgres"

# SQLite database file path (used when db_backend = "sqlite").
# default: "/var/lib/agora-relay/relay.db"
sqlite_path = "/var/lib/agora-relay/relay.db"

# PostgreSQL connection string (used when db_backend = "postgres").
# Set via AGORA_DB_URL environment variable; do not put credentials here.
# default: "" (must be set via env var if using postgres)
postgres_url = ""

# PostgreSQL connection pool size.
# default: 20
postgres_pool_size = 20

# There is no relay-wide retention setting. The relay carries only
# tokens registered under an agreement, and holds each envelope and
# blob for the retentionDays of that agreement or until the envelope's
# expiryHint, whichever is sooner (spec §10.4.4, spec §10.4.6).
# Pinned CIDs are kept until unpinned (spec §10.4.3, spec §11.4).

# Blob store backend: "local" or "s3".
# "local" stores blobs on the local filesystem, indexed by CIDv1.
# "s3" stores blobs in an S3-compatible object store; required for HA deployments.
# default: "local"
blob_backend = "local"

# Local filesystem path for blob store (used when blob_backend = "local").
# default: "/var/lib/agora-relay/blobs"
blob_local_path = "/var/lib/agora-relay/blobs"

# S3-compatible object store configuration (used when blob_backend = "s3").
# Enables shared blob store for HA deployments and off-site archival.
# Compatible with AWS S3, MinIO, Backblaze B2, Cloudflare R2, and any S3-compatible API.
# Set credentials via AGORA_BLOB_S3_ACCESS_KEY and AGORA_BLOB_S3_SECRET_KEY env vars.
# default: "" (disabled)
blob_s3_endpoint   = ""   # e.g. "https://s3.us-east-1.amazonaws.com"
blob_s3_bucket     = ""   # e.g. "agora-relay-blobs-prod"
blob_s3_region     = ""   # e.g. "us-east-1"
blob_s3_access_key = ""   # set via AGORA_BLOB_S3_ACCESS_KEY env var
blob_s3_secret_key = ""   # set via AGORA_BLOB_S3_SECRET_KEY env var

# Blob replication among the relays carrying a token (spec §10.4.4).
# The replication floor is not set here: it is the replicationFloor of
# the agreement under which each token is registered (default 2,
# spec §10.5.1). Replicated copies count against the storage quota of
# this relay's own agreement for the token.

# Concurrent outbound Peer API blob transfers (eager replication,
# pull-through and seed fetches). default: 16
blob_peer_transfer_concurrency = 16

# Seconds to wait for peers during a pull-through before answering the
# client 404. default: 10
blob_pull_through_timeout_seconds = 10

# ─────────────────────────────────────────────
# [agreements]: ServiceAgreements (spec §10.5.1)
# ─────────────────────────────────────────────
[agreements]

# Directory of fully signed ServiceAgreement envelopes, one encoded
# envelope per file, each signed by this relay (provider) and by the
# CO billing DID. An agreement is identified by the CID of its body
# bytes (spec §10.5.1). The relay loads only agreements whose serviceType is
# "relay", whose provider is identity.relay_did, and whose endpoint
# equals this relay's admission key registration URL,
# https://<server.hostname>/v1/agora/admission-keys, which is also
# published as endpoints.admissionKeys (spec §10.2.1). It accepts
# AdmissionKeyRegistration and AdmissionKeyDeregistration requests only
# under a loaded, current, unsuperseded agreement, and enforces each
# agreement's retentionDays, storageQuotaGb and bandwidthTierGbPerMonth,
# and replicates blobs to its replicationFloor (spec §10.4.4).
# When a superseding agreement is loaded, keys registered under the
# superseded one stay admitted for one hour and then lapse; that hour
# is fixed by spec §10.5.1 and is not configurable.
# Agreements are private: never gossip, publish, or log their contents.
# default: "/etc/agora-relay/agreements"
agreements_dir = "/etc/agora-relay/agreements"

# Registration requests accepted per minute per agreement. Excess
# requests are answered 429 rate-limited (spec §10.5.3). default: 60
registrations_per_agreement_per_minute = 60

# ─────────────────────────────────────────────
# [observation]: observation budget (ARCHITECTURE §5, spec §10.2.1)
# ─────────────────────────────────────────────
[observation]

# Retention of network-layer connection metadata (source address,
# timing, volume, transport) in days. This covers access logs and any
# log line carrying a remote address. Published in the manifest as
# observationBudget.connectionLogRetentionDays. The relay refuses to
# load an agreement whose observationBudget differs from this section,
# so the one published value is true for every agreement.
# default: 7
connection_log_retention_days = 7

# Opt-in observation-budget extensions (ARCHITECTURE S6). must stay
# empty unless every CO served has agreed to the extension in its
# agreement. Published in the manifest as observationBudget.extensions.
# default: []
extensions = []

# ─────────────────────────────────────────────
# [peering]: relay-to-relay mesh configuration
# ─────────────────────────────────────────────
[peering]

# Bootstrap peer manifest URLs. The relay contacts these on startup
# to join the gossipsub mesh (spec §10.2.5, Method 1).
bootstrap_peers = [
  "https://peer1.example.net/.well-known/agora-relay",
  "https://peer2.example.org/.well-known/agora-relay",
]

# Target mesh degree: number of active peer connections to maintain.
# Corresponds to gossipsub D parameter. default: 6
mesh_degree = 6

# Peer manifest cache TTL in seconds. default: 3600
peer_manifest_cache_ttl = 3600

# Peer heartbeat interval in seconds (spec §10.2.6). default: 60
peer_heartbeat_interval = 60

# Number of missed heartbeats before marking a peer unreachable. default: 3
peer_heartbeat_miss_threshold = 3

# Days to retain an unreachable peer in knownPeers before removal. default: 7
peer_retention_days = 7

# Blocklisted peer DIDs (permanently refused). Array of DID strings.
blocked_peers = []

# Explicitly trusted peer DIDs (trust level 3). Array of DID strings.
# These peers bypass gossip rate limiting entirely (spec §10.2.4).
trusted_peers = []

# ─────────────────────────────────────────────
# [push_proxy]: push notification proxy (spec §11.7)
# ─────────────────────────────────────────────
[push_proxy]

# Whether this relay operates a co-located push proxy. default: false
enabled = false

# Push proxy endpoint URL (if operating a push proxy, this is the
# locally-served URL; if using an external proxy, this is its URL).
endpoint = "https://push.relay.example.com/v1/agora/push"

# Push proxy DID (required if enabled = true).
proxy_did = ""

# APNs key ID, team ID, bundle ID (required for APNs support).
apns_key_id   = ""
apns_team_id  = ""
apns_bundle_id = ""
# APNs private key path (PKCS#8 .p8 file). Set via env var AGORA_APNS_KEY.
apns_key_path = ""

# FCM server key. Set via AGORA_FCM_SERVER_KEY env var.
fcm_server_key = ""

# Push registration TTL in days. The relay drops a registration when
# its ttl expires and never keeps one past 30 days (spec §11.7.3).
# default: 30
registration_ttl_days = 30

# Maximum random delay added before sending a wake-up, in milliseconds.
# Wake-ups for the same pushHandle within this window are coalesced
# into one request (spec §11.7.4). Every wake-up has the same form,
# with no content and no urgency; there is no priority setting.
# default: 2000
wake_jitter_max_ms = 2000

# A push registration tells the relay which channelTokens wake the
# same device (pushHandle). That linkage is within the observation
# budget (ARCHITECTURE §5 item 7) and is held only as long as the
# registration. It is never logged.

# ─────────────────────────────────────────────
# [jmap]: JMAP sync API, token-keyed Envelopes and blobs (spec §11.8)
# ─────────────────────────────────────────────
# Every relay serves this API and declares jmap-sync-v1; it is the only
# path for envelope history and blob upload and cannot be disabled
# (spec §10.4.3). The relay serves only Envelope sync and blob
# upload/download. It serves no Space, channel, membership, role or
# invite objects; that
# management API runs in the client or on CO infrastructure
# (spec §11.8.9). JMAP requests are unauthenticated and rate-limited
# like the live stream (spec §11.8.2).
[jmap]

# JMAP base URL (published as endpoints.jmapSync in the manifest).
base_url = "https://relay.example.com/v1/agora/jmap"

# Maximum envelope bytes (session object maxEnvelopeBytes). default: 65536
max_envelope_bytes = 65536

# Maximum blob upload bytes (session object maxAttachmentBytes).
# default: 104857600 (100 MB)
max_attachment_bytes = 104857600

# EventSource ping interval in seconds. default: 30
eventsource_ping_interval = 30

# There is no [compliance] or [enterprise] section. The compliance
# logger is a CO component and never runs on a relay (ARCHITECTURE S8;
# ARCHITECTURE §7 item 8), and the relay authenticates no client
# identity, so it has
# no provisioner, OIDC or SAML settings (spec §11.6). See §14.

# ─────────────────────────────────────────────
# [rate_limits]: admission and abuse controls (spec §11.6, spec §12.5)
# ─────────────────────────────────────────────
[rate_limits]

# Maximum envelopes per second per channelToken (spec §12.5). spec §11.6
# sets a floor: a relay admits at least 20 envelopes per second on each
# token before limiting it, so do not set this below 20. default: 50
channel_msg_per_second = 50

# Maximum envelope bytes per second per channelToken. spec §11.6 sets a
# floor of 256 KiB per second, so do not set this below 262144.
# default: 524288
channel_bytes_per_second = 524288

# Burst allowance per channelToken. default: 200
channel_msg_burst = 200

# New connections per second per network address. default: 10
connections_per_address_per_second = 10

# Concurrent channelToken subscriptions per connection. default: 500
subscriptions_per_connection = 500

# History reads (live stream and JMAP) per minute per channelToken.
# default: 120
history_reads_per_token_per_minute = 120

# Push registrations per hour per network address. default: 20
push_registrations_per_address_per_hour = 20

# Require an AdmissionChallenge proof of work before RelayHello once
# active connections exceed this fraction of server.max_connections,
# and for any address over its per-address limit (spec §11.6).
# default: 0.8
admission_pow_load_threshold = 0.8

# Leading zero bits required in an admission proof. default: 20
admission_pow_difficulty = 20

# Relay's own minimum envelope PoW difficulty (spec §10.5.2). 0 accepts
# envelopes without a powProof. A channel's own PowPolicy is
# enforced by member clients, since the relay cannot map a
# channelToken to a channel. Published in the manifest as
# `minPowDifficulty` (spec §10.2.1). default: 0
envelope_pow_min_difficulty = 0

# ─────────────────────────────────────────────
# [logging]: structured log output
# ─────────────────────────────────────────────
# Any log line that carries a remote address is connection metadata
# and is deleted after observation.connection_log_retention_days.
[logging]

# Log level: "error", "warn", "info", "debug", "trace". default: "info"
level = "info"

# Log output: "stdout", "stderr", or a file path. default: "stdout"
output = "stdout"

# Log format: "json" (production) or "text" (development). default: "json"
format = "json"
```

### 3.3 Environment Variable Overrides

All configuration values can be overridden via environment variables using the pattern `AGORA_<SECTION>_<KEY>` in SCREAMING_SNAKE_CASE. Section separators become underscores. These secrets must be set via environment variables and must not appear in the config file:

| Environment Variable | Config Equivalent | Description |
|---|---|---|
| `AGORA_SIGNING_KEY_PATH` | `identity.signing_key_path` | Path to relay Ed25519 signing key |
| `AGORA_DB_URL` | `storage.postgres_url` | PostgreSQL connection string including password |
| `AGORA_ADMIN_TOKEN` | (no config equivalent) | Admin API bearer token (see §5.1) |
| `AGORA_BLOB_S3_ACCESS_KEY` | `storage.blob_s3_access_key` | S3-compatible blob store access key |
| `AGORA_BLOB_S3_SECRET_KEY` | `storage.blob_s3_secret_key` | S3-compatible blob store secret key |
| `AGORA_APNS_KEY` | `push_proxy.apns_key_path` | APNs private key path |
| `AGORA_FCM_SERVER_KEY` | `push_proxy.fcm_server_key` | FCM server key |

### 3.4 Secrets Management

The approach depends on the deployment environment:

**AWS Secrets Manager.** Store each secret as a separate secret. Use the AWS SDK to fetch secrets at startup. The relay process must have an IAM role with `secretsmanager:GetSecretValue` permission for the relevant secret ARNs. Inject secret values as environment variables via the ECS task definition `secrets` field or Kubernetes external-secrets operator.

**HashiCorp Vault.** Use the Vault agent sidecar injector for Kubernetes, or the Vault AWS auth method for ECS. The relay process should not contain Vault credentials; authentication should use the platform identity (EC2 instance profile, Kubernetes service account).

**Kubernetes Secrets.** Acceptable for internal/development deployments. For production, use a secrets operator (External Secrets Operator, Sealed Secrets) that syncs from a trusted secrets store rather than committing plaintext secrets to etcd.

The relay signing key requires special handling; see §10.1.

---

## 4. Deployment Packaging

### 4.1 Docker

The official relay image follows this structure:

```dockerfile
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -r -s /bin/false -u 1000 agora

# Copy relay binary (statically linked or with bundled deps)
COPY --chown=agora:agora agora-relay /usr/local/bin/agora-relay

# Config and key directories
RUN mkdir -p /etc/agora-relay/keys /var/lib/agora-relay \
    && chown -R agora:agora /etc/agora-relay /var/lib/agora-relay

VOLUME ["/etc/agora-relay", "/var/lib/agora-relay"]

USER agora

EXPOSE 443/udp 443/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fk https://localhost:443/v1/agora/peer/health || exit 1

ENTRYPOINT ["/usr/local/bin/agora-relay"]
CMD ["--config", "/etc/agora-relay/relay.toml"]
```

**Image tags.** Use digest-pinned references in production. Do not use the `:latest` tag in production deployments. Use immutable tags of the form `agora-relay:0.2.1` and pin to the image digest in your deployment manifests:

```
ghcr.io/agora-protocol/relay:0.2.1@sha256:<digest>
```

**Volume mounts:**
- `/etc/agora-relay`: config file, signed agreements, and TLS certificates (read-only at runtime after startup)
- `/var/lib/agora-relay`: database (SQLite) and blob store (if using local backend)

### 4.2 Docker Compose: Single-Node Stack

```yaml
# docker-compose.yml: single-node Agora relay stack
version: "3.9"

services:
  relay:
    image: ghcr.io/agora-protocol/relay:0.2.1@sha256:<digest>
    restart: unless-stopped
    ports:
      - "443:443/tcp"
      - "443:443/udp"
    volumes:
      - ./config:/etc/agora-relay:ro
      - relay-data:/var/lib/agora-relay
    environment:
      AGORA_SIGNING_KEY_PATH: /etc/agora-relay/keys/relay-signing.key
      AGORA_DB_URL: "postgresql://agora:${DB_PASSWORD}@postgres:5432/agora"
      AGORA_ADMIN_TOKEN: "${ADMIN_TOKEN}"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - relay-internal
      - relay-public

  postgres:
    image: postgres:16-alpine@sha256:<digest>
    restart: unless-stopped
    environment:
      POSTGRES_DB: agora
      POSTGRES_USER: agora
      POSTGRES_PASSWORD: "${DB_PASSWORD}"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agora"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - relay-internal

volumes:
  relay-data:
  postgres-data:

networks:
  relay-internal:
    internal: true
  relay-public:
```

Do not commit the `.env` file to version control. It must contain at least:

```
DB_PASSWORD=<strong-random-password>
ADMIN_TOKEN=<strong-random-token>
```

### 4.3 Helm Chart: Kubernetes Deployment

Excerpt of `values.yaml` for the Agora relay Helm chart:

```yaml
# values.yaml

image:
  repository: ghcr.io/agora-protocol/relay
  tag: "0.2.1"
  digest: "sha256:<digest>"
  pullPolicy: IfNotPresent

replicaCount: 2  # For HA; see §15

service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
  ports:
    webtransport:
      port: 443
      protocol: UDP
    websocket:
      port: 443
      protocol: TCP

config:
  hostname: "relay.example.com"
  server:
    tls_acme: true
    tls_acme_email: "relay-admin@example.com"
  storage:
    db_backend: "postgres"
  peering:
    mesh_degree: 6
    bootstrap_peers: []
  logging:
    level: "info"
    format: "json"

secrets:
  # Reference to a Kubernetes Secret containing:
  #   AGORA_SIGNING_KEY_PATH, AGORA_DB_URL, AGORA_ADMIN_TOKEN
  existingSecret: "agora-relay-secrets"

persistence:
  enabled: true
  storageClass: "gp3"
  relayData:
    size: "50Gi"

postgresql:
  enabled: true          # Deploy bundled PostgreSQL; set false to use external
  auth:
    database: agora
    username: agora
    existingSecret: "agora-pg-credentials"
  primary:
    persistence:
      size: "100Gi"
      storageClass: "gp3"

blobStore:
  backend: "local"        # "local" or "s3"
  persistence:
    size: "200Gi"
    storageClass: "gp3"
  # For s3 backend, set blob_s3_* values in relay config and
  # provide credentials via AGORA_BLOB_S3_ACCESS_KEY / AGORA_BLOB_S3_SECRET_KEY.

resources:
  relay:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "4"
      memory: "8Gi"

serviceMonitor:
  enabled: true           # Create Prometheus ServiceMonitor
  namespace: "monitoring"

adminIngress:
  enabled: false          # Admin API must not be exposed externally
```

### 4.4 AWS Deployment (Terraform Out of Scope)

This guide does not provide a Terraform module; a sketch would be mistaken for a tested one. An AWS deployment, in ECS Fargate or EKS, needs these resources, which map directly onto the components in §2:

| Resource | Purpose | Notes |
|---|---|---|
| ECS service or EKS deployment | Runs `agora-relay` | Inject `AGORA_DB_URL`, `AGORA_ADMIN_TOKEN` and the signing key from Secrets Manager (§3.4) |
| Aurora PostgreSQL or RDS PostgreSQL | Database | Automated backup retention no longer than the shortest agreement retention (§8.1) |
| S3 bucket | Blob store (`blob_backend = "s3"`) | No transition to archive storage classes (CAS reads must be immediate); noncurrent-version expiration within the retention window (§8.4) |
| Network Load Balancer | UDP 443 (QUIC) and TCP 443 | Requirements in §11.4 and §15.5 |
| Security groups | Port policy | Rules in §11.1 and §11.3; admin and metrics ports never public |

---

## 5. Relay Admin API

The Relay Admin API is an HTTP API served on the admin listen address (default `127.0.0.1:9099`). It must not be exposed to the public internet. All endpoints require authentication via a static bearer token (see §5.1). The Admin API is an operator interface defined in this document, outside the Agora protocol.

The Admin API reports per-token and per-agreement counters only. It never reports Space or channel names, types, Space CIDs, channel IDs, or member counts (ARCHITECTURE §7 item 7); the relay does not have them (spec §10.4.1). Agreements are identified by their `id`, the CID of the agreement body bytes both parties signed (spec §10.5.1), and their billing DID, which is what the relay holds (ARCHITECTURE §5 item 6). The Admin API never returns registered admission keys or agreement documents to anyone; they stay private between the relay and each CO (spec §10.4.3).

### 5.1 Authentication

All Admin API requests must include an `Authorization: Bearer <token>` header. The token is configured via the `AGORA_ADMIN_TOKEN` environment variable. The relay must reject any request without a valid token with HTTP 401.

The admin token must be a cryptographically random value of at least 32 bytes, base64url-encoded. Generate with:

```bash
openssl rand -base64 32
```

The admin token provides full control over the relay. It must be treated as a high-value secret: stored in a secrets manager, rotated via `POST /admin/reload` after updating the environment variable, and never logged.

Every Admin API call is recorded in the relay's audit log (retrievable via `GET /admin/audit`).

### 5.2 Endpoint Reference

#### `GET /admin/status`

Returns full relay status. No request body.

**Response 200:**
```json
{
  "version": "0.2.1",
  "relay_did": "did:web:relay.example.com",
  "uptime_seconds": 1209600,
  "started_at": "2026-04-08T00:00:00Z",
  "health": "healthy",
  "peer_count": 8,
  "active_connections": 1247,
  "admission_pow_active": false,
  "message_rate_per_second": 342.7,
  "messages_forwarded_total": 187423901,
  "agreements_loaded": 12,
  "admission_keys_registered": 4318,
  "storage": {
    "db_size_bytes": 42949672960,
    "blob_store_size_bytes": 214748364800,
    "retention_queue_depth": 29183
  },
  "observation_budget": {
    "connection_log_retention_days": 7,
    "extensions": []
  }
}
```

#### `GET /admin/peers`

Lists all known peers with current trust level, reachability, and traffic statistics.

**Response 200:**
```json
{
  "peers": [
    {
      "relay_did": "did:web:peer.example.net",
      "manifest_url": "https://peer.example.net/.well-known/agora-relay",
      "trust_level": 2,
      "reachable": true,
      "last_seen_at": "2026-04-22T14:00:01Z",
      "last_heartbeat_at": "2026-04-22T14:00:01Z",
      "peered_since": "2026-04-01T00:00:00Z",
      "gossip_msg_rate_per_second": 12.4,
      "gossip_msg_total": 9827341,
      "region": "eu-west",
      "capabilities": ["gossipsub-v1.1", "gossipsub-quic-v1", "peer-api-v1"]
    }
  ]
}
```

#### `POST /admin/peers/{did}/trust`

Sets the trust level for a peer manually. Trust level 3 is the maximum; level 0 effectively blocks the peer from gossiping (manifest fetch only).

**Request body:**
```json
{
  "trust_level": 3,
  "reason": "same-org relay"
}
```

**Response 200:**
```json
{ "relay_did": "did:web:peer.example.net", "trust_level": 3, "updated_at": "2026-04-22T14:00:00Z" }
```

**Response 404:** Peer DID not found in the peer table.

#### `DELETE /admin/peers/{did}`

Removes a peer and adds it to the permanent blocklist. This action is irreversible via the API; to unblock, restart the relay with the peer removed from `peering.blocked_peers`.

**Request body:**
```json
{
  "reason": "repeated invalid signatures",
  "confirm": "REMOVE_AND_BLOCK"
}
```

The `confirm` field must equal the string `"REMOVE_AND_BLOCK"`. Requests without this field return HTTP 400.

**Response 200:**
```json
{ "relay_did": "did:web:peer.example.net", "blocked": true }
```

#### `GET /admin/agreements`

Lists loaded `ServiceAgreement`s with their quota counters.

**Response 200:**
```json
{
  "agreements": [
    {
      "id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
      "service_type": "relay",
      "billing_did": "did:key:z6MkBilling...",
      "valid_from": "2026-03-12T00:00:00Z",
      "valid_until": "2027-03-12T00:00:00Z",
      "superseded_by": null,
      "retention_days": 90,
      "admission_keys_registered": 361,
      "last_registration_at": "2026-10-16T11:58:02Z",
      "storage_bytes": 1073741824,
      "storage_quota_bytes": 53687091200,
      "bandwidth_bytes_this_month": 21474836480,
      "bandwidth_quota_bytes_per_month": 107374182400,
      "terminated": false
    }
  ]
}
```

`superseded_by` is the `id` of a loaded agreement whose `supersedes` names this one; keys registered under a superseded agreement lapse one hour after the relay signed the new one (spec §10.5.1).

#### `GET /admin/agreements/{id}`

Returns the same counters for one agreement, plus the envelope and blob counts stored under it and recent registration results by `error` code (spec §10.5.3). Does not return the agreement document or the registered keys.

#### `GET /admin/agreements/{id}/cids`

Streams the CIDs stored or pinned under the agreement, one per line. Used to hand a CO the list of its content before decommissioning or termination (§16.4, §17.2).

#### `POST /admin/agreements/{id}/terminate`

Ends service under the agreement before its `validUntil`, for example when the CO and operator end the contract early. The relay treats the agreement as ended: it rejects new registrations under it (`agreement-invalid`), stops admitting envelopes, pin instructions and uploads for every token registered under it, and sends each subscribed connection an `Error` with code `token-withdrawn` for those tokens (spec §11.4). Held envelopes stay readable until their retention ends (spec §10.4.6). Stored data is deleted after `grace_days`, which should follow the agreement's notice terms. An agreement that reaches `validUntil` lapses the same way without this call (spec §10.5.1).

**Request body:**
```json
{
  "confirm_agreement_id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "grace_days": 30,
  "reason": "contract ended by mutual notice"
}
```

`confirm_agreement_id` must exactly match `{id}`. Requests where these do not match return HTTP 400.

**Response 200:**
```json
{
  "id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "terminated_at": "2026-10-16T14:00:00Z",
  "data_deletion_at": "2026-11-15T14:00:00Z"
}
```

#### `GET /admin/tokens`

Lists the busiest `channelToken`s by traffic over a window, for capacity and abuse triage.

**Query parameters:**
- `window`: `1h`, `24h` (default) or `7d`.
- `limit`: maximum entries. Default 50, maximum 1000.

**Response 200:**
```json
{
  "tokens": [
    {
      "channel_token": "base64url...",
      "agreement_id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
      "key_status": "registered",
      "envelopes": 128440,
      "bytes": 734003200,
      "subscribers_now": 41,
      "push_registrations": 17,
      "rate_limited": 312,
      "admission_sig_failures": 0
    }
  ]
}
```

`agreement_id` is the agreement under which the token's admission key is registered. `key_status` is one of `registered`; `suspended`, for a token this relay has suspended (spec §10.4.7); or `withdrawn`, for a token whose key was deregistered or whose agreement ended while the relay still holds envelopes under it (spec §11.4). Counters are per token. A token changes only when the CO rotates the channel's admission key, not on MLS epochs (spec §10.4.2). The relay uses a registration's `replaces` only to send `token-rotated` to the old token's subscribers (spec §10.5.3, spec §11.4) and keeps no link between a token and the one that replaces it.

The CO's registrations normally decide admission: to cut a token off, the CO deregisters its key (spec §10.5.3). The relay may also suspend one token under its own policy and law (spec §10.4.7); see the next two operations.

#### `POST /admin/tokens/{token}/suspend`

Stops admitting envelopes, pin instructions and blob uploads for one registered `channelToken`, for example when it carries abusive volume or under a legal demand (spec §10.4.7). This is a carriage decision, not a moderation decision (ARCHITECTURE S2). The relay treats the token as withdrawn: it sends `token-withdrawn` to the token's subscribers and answers later requests naming the token with `token-withdrawn` (spec §11.4). The suspension applies to the token itself: a re-registration of the same token does not lift it, and a new token the CO registers after rotating the key is admitted normally.

Spec §10.4.7 requires a notice to the CO at the `contact` of the agreement under which the token is registered, naming the token, the time and the reason. The relay sends it when the suspension takes effect and records the delivery result in the audit log. Suspension tells the relay nothing about the channel or its members beyond what it already observes (spec §10.4.1).

**Request body:**
```json
{
  "confirm_token": "base64url...",
  "reason": "sustained abusive volume"
}
```

`confirm_token` must exactly match `{token}`, and the token must be registered; otherwise the request returns HTTP 400.

**Response 200:**
```json
{
  "channel_token": "base64url...",
  "agreement_id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "suspended_at": "2026-10-16T14:00:00Z",
  "contact_notified": true
}
```

#### `DELETE /admin/tokens/{token}/suspend`

Lifts a suspension, at the operator's discretion (spec §10.4.7). The relay admits the token again if its key is still registered. Returns HTTP 404 if the token is not suspended.

#### `GET /admin/content/{cid}`

Looks up a CID named in a takedown request (spec §10.4.5). Returns what the relay holds about it and nothing else: whether it is a blob or an envelope, its size, whether it is pinned, the `channelToken` under which it was stored or pinned, the agreement under which that token is registered, and that agreement's `contact`. The bytes are never returned.

**Response 200:**
```json
{
  "cid": "bafkreie5cvv4h45feklmhv2qnkcoyyb3eslkvu4tk4uvzjiyaq5qxvklie",
  "kind": "blob",
  "size": 482113,
  "pinned": false,
  "channel_token": "base64url...",
  "agreement_id": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "contact": "mailto:io-liaison@co.example.com"
}
```

**Response 404:** The relay holds nothing under this CID.

#### `DELETE /admin/content/{cid}`

Stops serving a blob or envelope, deletes it, and adds the CID to a deny list so that the relay refuses a re-upload of the same bytes. Spec §10.4.5 allows this as a storage decision under the operator's own policy and law; it removes this relay's copy only and is not a moderation decision. Copies on other relays and in members' stores are unaffected; because blobs are replicated, other relays carrying the token usually hold a copy. The deny list also refuses the CID in replication pushes, pull-through and `seed` fetches. If `{cid}` is a `dag-pb` root block (spec §14.3.4), the relay also deletes and deny-lists the chunk blocks it links to, as pinning a root covers its chunks (spec §10.4.4).

**Request body:**
```json
{
  "confirm_cid": "bafkreie5cvv4h45feklmhv2qnkcoyyb3eslkvu4tk4uvzjiyaq5qxvklie",
  "reason": "court order 2026-CV-1234"
}
```

`confirm_cid` must exactly match `{cid}`.

**Response 200:**
```json
{ "cid": "bafkreie5cvv4h45feklmhv2qnkcoyyb3eslkvu4tk4uvzjiyaq5qxvklie", "deleted": true, "denylisted": true }
```

#### `GET /admin/metrics`

Returns a redirect to the Prometheus metrics endpoint.

**Response 302:** `Location: http://127.0.0.1:9100/metrics`

#### `POST /admin/reload`

Reloads non-breaking configuration changes without restarting the relay process. Reloadable fields: `peering.bootstrap_peers`, `peering.blocked_peers`, `peering.trusted_peers`, `rate_limits.*`, `logging.level`, `identity.signing_key_path`, `identity.signing_key_deprecated_path`, `identity.revoked_key_ids`, `agreements.registrations_per_agreement_per_minute`, `server.tls_cert`, `server.tls_key`, `server.accepting_new_connections`, and the contents of `agreements.agreements_dir`. Non-reloadable fields (require restart): all other `server.*` and `identity.*` fields, `storage.*`, and `observation.*`.

**Response 200:**
```json
{
  "reloaded_at": "2026-04-22T14:00:00Z",
  "fields_reloaded": ["peering.blocked_peers", "logging.level"],
  "fields_skipped_require_restart": []
}
```

**Response 400:** If the updated config file contains syntax errors or invalid values, the reload is rejected and the running configuration is unchanged.

#### `GET /admin/audit`

Returns the relay operator audit log: all Admin API calls with timestamp, endpoint, caller IP, and HTTP status code.

**Query parameters:**
- `since`: ISO 8601 datetime; return only entries after this time. Default: 24 hours ago.
- `limit`: maximum entries to return. Default: 1000, maximum: 10000.

**Response 200:**
```json
{
  "entries": [
    {
      "ts": "2026-04-22T14:00:00Z",
      "method": "POST",
      "path": "/admin/peers/did:web:peer.example.net/trust",
      "remote_addr": "10.0.1.5",
      "http_status": 200,
      "duration_ms": 3
    }
  ]
}
```

---

## 6. Observability

### 6.1 Prometheus Metrics

The relay must expose Prometheus metrics at `GET /metrics` on the metrics listen address (default `127.0.0.1:9100`). The metrics endpoint must not require authentication. It must not be publicly reachable.

All metric names are prefixed `agora_relay_`.

#### Connection Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_connections_active` | Gauge | `transport` (`webtransport`, `websocket`) | Currently active client connections |
| `agora_relay_connections_total` | Counter | `transport` | Total connections accepted since start |
| `agora_relay_connections_rejected_total` | Counter | `reason` (`rate_limit`, `admission_pow_failed`, `unsupported_version`, `text_frame`, `tls_error`) | Connections rejected |
| `agora_relay_connection_duration_seconds` | Histogram | `transport` | Connection lifetime in seconds |
| `agora_relay_admission_challenges_total` | Counter | `result` (`passed`, `failed`, `expired`) | AdmissionChallenge proofs of work issued under load (spec §11.6) |
| `agora_relay_admin_api_requests_total` | Counter | `endpoint` | Admin API requests (§5) |

Example exposition:
```
# HELP agora_relay_connections_active Currently active client connections
# TYPE agora_relay_connections_active gauge
agora_relay_connections_active{transport="webtransport"} 1103
agora_relay_connections_active{transport="websocket"} 144
```

#### Message Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_live_messages_received_total` | Counter | `t` (`ClientHello`, `AdmissionProof`, `Subscribe`, `Unsubscribe`, `Publish`, `PinInstruction`, `PushRegister`), `path` (`stream`, `datagram`) | Live protocol messages received from clients (spec §11.4) |
| `agora_relay_envelopes_delivered_total` | Counter | `path` (`stream`, `datagram`) | `Deliver` messages sent to subscribers |
| `agora_relay_live_errors_total` | Counter | `code` (the `error-code` values of spec §11.4: `bad-message`, `unsupported-version`, `unknown-token`, `token-withdrawn`, `token-rotated`, `bad-admission-sig`, `insufficient-pow`, `expired`, `replayed`, `too-large`, `rate-limited`, `quota-exceeded`, `unknown-cid`, `internal`) | `Error` messages sent, by code |
| `agora_relay_envelope_bytes_received_total` | Counter | none | Total routing envelope bytes received in `Publish` and on the mesh |
| `agora_relay_envelope_bytes_delivered_total` | Counter | none | Total routing envelope bytes sent in `Deliver` |
| `agora_relay_channel_token_active` | Gauge | none | Number of distinct channelTokens with active subscribers |
| `agora_relay_message_retention_queue_depth` | Gauge | none | Number of held envelopes pending retention GC |

#### Admission Metrics

The relay cannot see MLS framing inside the sealed envelope (spec §5.2.2), so it cannot count Commits, Proposals or application messages separately, except that an envelope in a sequenced channel that carries a `commitStamp` is a Commit (spec §12.3). It counts what it verifies: `admissionSig` on each envelope, pin instruction and upload authorization against the registered admission public key (spec §10.5.4), and the CO's registration requests (spec §10.5.3).

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_admission_sig_verifications_total` | Counter | `source` (`publish`, `mesh`, `pin`, `upload`), `result` (`valid`, `bad_admission_sig`, `unknown_token`, `token_withdrawn`) | `admissionSig` checks over the exact `signed` bytes |
| `agora_relay_admission_key_requests_total` | Counter | `type` (`registration`, `deregistration`), `result` (`accepted`, `malformed`, `bad-signature`, `agreement-invalid`, `stale`, `token-conflict`, `rate-limited`) | Requests to the `admissionKeys` endpoint, by spec §10.5.3 outcome |
| `agora_relay_admission_keys_registered` | Gauge | `agreement` | Admission keys currently registered under each agreement |
| `agora_relay_tokens_withdrawn_total` | Counter | `cause` (`deregistered`, `agreement_ended`, `superseded`, `suspended`) | Tokens whose key stopped being admitted (spec §11.4) |
| `agora_relay_envelope_validation_failures_total` | Counter | `reason` (`cbor_decode`, `signed_decode`, `token_format`, `too_large`) | Routing envelope structure failures |
| `agora_relay_pin_instructions_total` | Counter | `op` (`pin`, `unpin`), `result` (`accepted`, `expired`, `replayed`, `unknown-cid`, `quota-exceeded`, `rejected`) | `PinInstruction`s processed (spec §11.4) |

#### Push Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_push_registrations_active` | Gauge | none | Push registrations held (spec §11.7.3) |
| `agora_relay_push_wakeups_sent_total` | Counter | `result` (`sent`, `coalesced`, `proxy_error`) | Wake-up requests sent to push proxies (spec §11.7.4) |

No push metric carries a `pushHandle`, a token or a proxy endpoint as a label.

#### Agreement Metrics

Label cardinality is bounded by the number of loaded agreements.

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_agreement_storage_bytes` | Gauge | `agreement` | Storage used under the agreement |
| `agora_relay_agreement_storage_quota_bytes` | Gauge | `agreement` | `storageQuotaGb` of the agreement, in bytes |
| `agora_relay_agreement_bandwidth_bytes_total` | Counter | `agreement` | Bytes served under the agreement |
| `agora_relay_agreement_quota_rejections_total` | Counter | `agreement`, `kind` (`storage`, `bandwidth`) | Writes or reads refused for quota |

#### JMAP Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_jmap_requests_total` | Counter | `method` | JMAP method calls by method name |
| `agora_relay_jmap_request_duration_seconds` | Histogram | `method` | JMAP request latency; expose p50/p95/p99 |
| `agora_relay_jmap_errors_total` | Counter | `method`, `error_type` | JMAP errors by method and error type |
| `agora_relay_jmap_eventsource_connections_active` | Gauge | none | Active EventSource push connections |

Histogram buckets for `agora_relay_jmap_request_duration_seconds`: `0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0`.

#### Peer Mesh Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_peer_count` | Gauge | `trust_level` (`0`, `1`, `2`, `3`) | Known peers by trust level |
| `agora_relay_peer_reachable` | Gauge | `trust_level` | Reachable peers by trust level |
| `agora_relay_gossip_messages_received_total` | Counter | none | Gossip messages received from peer relays |
| `agora_relay_gossip_messages_sent_total` | Counter | none | Gossip messages sent to peer relays |
| `agora_relay_peer_heartbeat_failures_total` | Counter | none | Heartbeat check failures across all peers |
| `agora_relay_peer_manifest_refresh_failures_total` | Counter | none | Peer manifest fetch failures |
| `agora_relay_peer_trust_downgrades_total` | Counter | `reason` (`invalid_sig`, `malformed_gossip`, `rate_exceeded`) | Peer trust level downgrades |

#### Storage Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_db_size_bytes` | Gauge | none | Database file/tablespace size in bytes |
| `agora_relay_blob_store_size_bytes` | Gauge | none | Blob store size in bytes |
| `agora_relay_blob_store_cid_count` | Gauge | none | Number of CIDs held in the blob store |
| `agora_relay_storage_retention_gc_duration_seconds` | Histogram | none | Time taken per retention GC pass |
| `agora_relay_storage_retention_deleted_total` | Counter | `kind` (`envelope`, `blob`) | Envelopes and blobs deleted by retention GC at the end of their agreement's `retentionDays` or `expiryHint` |

#### Blob Replication Metrics

No metric carries a `channelToken` or CID label; per-token series would build a record of which tokens are active that the relay does not otherwise keep.

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_blob_replication_pushes_total` | Counter | `result` (`stored`, `not_registered`, `quota`, `error`) | Outbound `POST /v1/agora/peer/blob` requests by peer answer (201, 404, 507, other) |
| `agora_relay_blob_replication_received_total` | Counter | `result` (`stored`, `rejected_token`, `rejected_cid`, `quota`) | Inbound replicated blobs by outcome |
| `agora_relay_blob_below_floor` | Gauge | none | Blobs held by fewer relays than their agreement's `replicationFloor` because no further peer accepted them |
| `agora_relay_blob_pull_through_total` | Counter | `result` (`fetched`, `not_found`, `no_token`) | Client fetches for a CID not held here, by outcome |
| `agora_relay_blob_seed_cids_total` | Counter | `result` (`held`, `fetched`, `not_found`) | CIDs listed in accepted `seed` instructions, by outcome |
| `agora_relay_blob_peer_bytes_total` | Counter | `direction` (`in`, `out`) | Blob bytes moved over the Peer API |

#### Compliance Metrics

None. Compliance logging is a CO function on CO infrastructure (ARCHITECTURE S8); the relay has no compliance subsystem to monitor. A CO monitors its own logger, including the capture gaps it detects (spec §7.8.9).

#### Abuse Control Metrics

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `agora_relay_pow_verifications_total` | Counter | `result` (`accepted`, `rejected`) | Envelope `powProof` checks against `minPowDifficulty` (spec §10.5.2) |
| `agora_relay_rate_limited_requests_total` | Counter | `type` (`channel`, `connection`, `subscription`, `history`, `push_registration`, `registration`) | Requests rejected by rate limiter |
| `agora_relay_content_denylist_size` | Gauge | none | CIDs on the takedown deny list (§17) |

### 6.2 Log Format

The relay must emit structured JSON logs when `logging.format = "json"`. Each log line is a single JSON object. Fields:

| Field | Type | Always present | Description |
|---|---|---|---|
| `ts` | ISO 8601 string | Yes | Event timestamp with millisecond precision |
| `level` | string | Yes | `error`, `warn`, `info`, `debug`, `trace` |
| `component` | string | Yes | Internal component: `transport`, `connection` (hello and admission challenge), `admission` (`admissionSig` checks), `registration`, `peer`, `jmap`, `blob`, `agreement`, `push`, `admin`, `gossip` |
| `event` | string | Yes | Short machine-readable event name (see below) |
| `msg` | string | Yes | Human-readable description |
| `duration_ms` | number | No | Duration of the operation in milliseconds |
| `peer_did` | string | No | Peer relay DID involved in this event |
| `agreement_id` | string | No | Agreement involved in this event (agreement, quota and admin events only) |
| `error` | string | No | Error message for `level=error` or `level=warn` events |
| `remote_addr` | string | No | Client IP address. Connection metadata: subject to `observation.connection_log_retention_days` |
| `trace_id` | string | No | Request trace ID for correlation |

Example log line:
```json
{"ts":"2026-10-16T14:00:01.234Z","level":"info","component":"connection","event":"connection_admitted","msg":"RelayHello sent","duration_ms":3,"trace_id":"abc123"}
```

**Log levels and what goes at each level:**

- `error`: conditions that require operator attention: failed TLS handshake, database write failure, blob store write failure, agreement file that fails signature verification or names another provider or endpoint.
- `warn`: conditions that are notable but not immediately actionable: peer heartbeat miss (first occurrence), agreement above 90% of a quota, rate limit triggered for the first time on a `channelToken`, admission proof of work switched on.
- `info`: normal operational events: relay startup and shutdown, peer connect/disconnect, TLS cert renewal, GC completed, config reload.
- `debug`: per-request events useful for troubleshooting: individual client hellos, `admissionSig` failures, registration request outcomes, JMAP method calls, gossip message receipt/forward.
- `trace`: verbose internal state: frame parsing, gossipsub scoring events, blob store write operations. Not for production use.

**Relay blindness in logs.** Logs hold only what the observation budget allows (ARCHITECTURE §5, spec §10.4.1). They never contain sender DIDs, member DIDs, Space CIDs, channel IDs or MLS group IDs; the relay does not have them. They never contain registered admission keys, agreement contents or push registrations. Logs that carry `remote_addr` are connection metadata. ARCHITECTURE §5 item 1 limits their retention to the value the relay declares in its manifest, here `observation.connection_log_retention_days` (see also ARCHITECTURE §7 item 11). Ship logs only to a collector that enforces the same retention; a log pipeline that keeps them longer puts the relay outside its declared budget.

---

## 7. Alerting

Configure at least these alert rules for a production relay. The rules use Prometheus alerting rule format.

```yaml
# agora-relay-alerts.yaml
groups:
  - name: agora_relay
    rules:

    # ── Availability ──────────────────────────────────────────────────────

    - alert: AgoraRelayDown
      expr: up{job="agora-relay"} == 0
      for: 1m
      labels:
        severity: critical
        team: infra
      annotations:
        summary: "Agora relay is down"
        description: >
          Relay {{ $labels.instance }} has been unreachable for over 1 minute.
          Clients cannot connect. Check process health and logs.

    - alert: AgoraRelayHealthDegraded
      expr: >
        agora_relay_connections_active{transport="webtransport"}
        + agora_relay_connections_active{transport="websocket"} == 0
        and up{job="agora-relay"} == 1
      for: 5m
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Agora relay has no active client connections"
        description: >
          Relay is up but has accepted no client connections for 5 minutes.
          Possible network, TLS, or routing issue.

    # ── Peer Mesh ─────────────────────────────────────────────────────────

    - alert: AgoraPeerMeshDegraded
      expr: sum(agora_relay_peer_reachable) < 3
      for: 10m
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Agora peer mesh degraded"
        description: >
          Relay has fewer than 3 reachable peers for over 10 minutes.
          Envelope fanout and discovery gossip may be impaired.
          Current reachable peers: {{ $value }}

    - alert: AgoraPeerMeshCritical
      expr: sum(agora_relay_peer_reachable) == 0
      for: 5m
      labels:
        severity: critical
        team: infra
      annotations:
        summary: "Agora relay is isolated from peer mesh"
        description: >
          Relay has zero reachable peers. It is isolated from the gossipsub mesh.
          Envelopes and discovery records from other relays are not being received.

    # ── Agreements ────────────────────────────────────────────────────────

    - alert: AgoraAgreementStorageQuotaHigh
      expr: >
        agora_relay_agreement_storage_bytes
        / agora_relay_agreement_storage_quota_bytes > 0.90
      for: 30m
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Agreement {{ $labels.agreement }} above 90% of storage quota"
        description: >
          Writes under this agreement will be refused at 100%. Contact the
          CO at the agreement's contact address.

    # ── Storage ───────────────────────────────────────────────────────────

    - alert: AgoraDatabaseStorageHigh
      expr: >
        agora_relay_db_size_bytes / (1024^3)
        > (node_filesystem_size_bytes{mountpoint="/var/lib/agora-relay"}
           / (1024^3)) * 0.80
      for: 30m
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Agora relay database storage above 80% capacity"
        description: >
          The relay database is using more than 80% of available storage.
          Increase storage, or check that the sum of agreement quotas
          (storageQuotaGb) fits the host.

    - alert: AgoraBlobStoreStorageHigh
      expr: >
        agora_relay_blob_store_size_bytes
        > 200 * (1024^3)
      for: 1h
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Blob store exceeds 200 GB"
        description: >
          Blob store is {{ $value | humanize1024 }}B. Review retention policy and
          consider switching to an S3-compatible backend for archival.

    # ── Security / Anomaly ────────────────────────────────────────────────

    - alert: AgoraAdmissionSigFailureSpike
      expr: >
        sum(rate(agora_relay_admission_sig_verifications_total{result!="valid"}[5m])) > 10
      for: 2m
      labels:
        severity: warning
        team: security
      annotations:
        summary: "Elevated admission signature failures"
        description: >
          Envelopes failing admissionSig verification at {{ $value }}/s.
          May indicate a flood from non-members, clients still using a
          deregistered key, or a misbehaving client.
          Consider the admission controls in §13.3. Threshold: 10/s for 2 minutes.

    - alert: AgoraRegistrationRejections
      expr: >
        sum(rate(agora_relay_admission_key_requests_total{result!="accepted"}[15m])) > 0.1
      for: 15m
      labels:
        severity: warning
        team: infra
      annotations:
        summary: "Admission key registrations are being rejected"
        description: >
          A CO's registration service is getting errors from this relay.
          Check the result label: stale points at clock skew (300-second
          window, spec §10.5.3), agreement-invalid at an expired or
          superseded agreement. Members of that CO's channels cannot post
          here until it is fixed.

    - alert: AgoraEnvelopeValidationFailureSpike
      expr: sum(rate(agora_relay_envelope_validation_failures_total[5m])) > 5
      for: 2m
      labels:
        severity: warning
        team: security
      annotations:
        summary: "Elevated routing envelope validation failures"
        description: >
          Routing envelope structure failures at {{ $value }}/s for 2 minutes.
          May indicate malformed clients or an active protocol attack.

    - alert: AgoraAdminAPIAccessed
      expr: increase(agora_relay_admin_api_requests_total[1m]) > 0
      labels:
        severity: info
        team: security
      annotations:
        summary: "Admin API accessed"
        description: >
          The relay Admin API was accessed. This alert fires on every access
          as an audit trigger. Review /admin/audit for details.
```

---

## 8. Backup and Restore

### 8.1 What Must Be Backed Up

| Item | Criticality | Notes |
|---|---|---|
| Relay signing key | **CRITICAL** | For a `did:key` relay, losing the key loses the relay DID permanently, and all peer relationships must be re-established with a new DID. For a `did:web` relay, the DID survives: publish a new key in `did.json` and the manifest (§10.1); the DID and its agreements are kept. |
| Database | High | Held envelopes, peer table, pin state, quota counters, push registrations. It also holds registered admission keys and per-token registration `ts` state; these are backed up for audit only and never restored (§8.5, spec §10.4.7). |
| Blob store | High | Opaque blobs and CO-published records. Content is content-addressed; deduplication is automatic. Back up the full blob store directory (local backend) or enable S3 bucket versioning (S3 backend, §8.4). |
| Signed agreements | High | The `agreements.agreements_dir` files. Without them the relay cannot verify registration requests or enforce quotas. Store as securely as the database: they are private between the relay and each CO. |
| Config file | Medium | Reconstructible, but restoring it avoids reconfiguring from scratch. |
| TLS private key | Medium | Loss requires certificate reissuance (fast with ACME, but causes a brief outage). |

**Backups and retention.** Backups of the database and blob store hold envelopes and blobs, and they hold access logs too if you back those up, so they fall under the same retention limits as the live relay (spec §10.4.1, spec §10.4.2). Expire database and blob backups within the shortest `retentionDays` among loaded agreements, because a backup holds every agreement's data. Back up access logs, if at all, only within `observation.connection_log_retention_days`. Pinned CIDs are the exception: they are kept until unpinned. The relay is never the authoritative record for a community. Older history lives in members' stores and the CO's archive (spec §5.2.5, ARCHITECTURE §4).

The relay holds no secret admission material. It stores only admission public keys and tokens, so a backup leaks no key that lets anyone post or read. It does reveal which tokens each agreement registered, so protect it like the database.

### 8.2 Relay Signing Key Backup

Back up the relay signing key before you first deploy the relay. For a `did:key` relay there is no recovery path if it is lost, because the DID is the key. A `did:web` relay that loses its key keeps its DID and recovers by publishing a new key in `did.json` and the manifest (§10.1, spec §10.2.1). Procedure:

1. Generate the key using the relay CLI:
   ```bash
   agora-relay keygen --output /etc/agora-relay/keys/relay-signing.key
   ```
   This generates an Ed25519 private key in PEM format.

2. Encrypt the key with a strong passphrase before backup:
   ```bash
   openssl enc -aes-256-cbc -pbkdf2 -in relay-signing.key \
       -out relay-signing.key.enc
   ```

3. Store the encrypted key in at least two physically separate locations:
   - Primary: your secrets manager (AWS Secrets Manager, HashiCorp Vault) as a binary secret.
   - Secondary: offline, air-gapped storage (encrypted USB, HSM backup key, printed QR code in a physical safe).

4. Record the relay DID in your CMDB. A `did:key` DID is derived from the public key and cannot be reconstructed without it.

5. Test the backup by decrypting the backup copy and verifying the DID:
   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -in relay-signing.key.enc \
       -out relay-signing.key.restored
   agora-relay did-from-key --key relay-signing.key.restored
   # Output must match the relay DID in your config.
   ```

### 8.3 Database Backup

**PostgreSQL:**

Use `pg_dump` for logical backups or continuous WAL archiving for point-in-time recovery:

```bash
# Daily logical backup (run from a backup host or as a cron job)
pg_dump -h $POSTGRES_HOST -U agora -d agora -Fc \
    -f /backup/agora-relay-$(date +%Y%m%d).dump

# Verify backup integrity
pg_restore --list /backup/agora-relay-$(date +%Y%m%d).dump > /dev/null
echo "Backup exit code: $?"

# Keep backups only within the retention limit in §8.1
# (BACKUP_RETENTION_DAYS = shortest agreement retentionDays)
find /backup -name "agora-relay-*.dump" -mtime +"$BACKUP_RETENTION_DAYS" -delete
```

For production, enable WAL archiving to S3 with `wal_level = replica` and `archive_mode = on`. Use `pgBackRest` or `barman` for managed WAL archiving.

**SQLite** (single-node only):

```bash
# Use SQLite's online backup API; never copy the .db file while the relay is running
sqlite3 /var/lib/agora-relay/relay.db ".backup /backup/relay-$(date +%Y%m%d).db"
```

**RPO/RTO guidance:**
- RPO (Recovery Point Objective): 1 hour maximum. WAL archiving provides near-zero RPO.
- RTO (Recovery Time Objective): 30 minutes for a warm standby (§15), 2 hours for a cold restore from backup.

### 8.4 Blob Store Backup

**Local backend (`blob_backend = "local"`):**

The blob store directory is a flat content-addressed filesystem. Back it up with any standard tool:

```bash
# Incremental rsync to a backup destination
rsync -av --checksum /var/lib/agora-relay/blobs/ \
    backup-host:/backup/agora-blobs/

# Or archive to a tarball
tar -czf /backup/agora-blobs-$(date +%Y%m%d).tar.gz \
    -C /var/lib/agora-relay blobs/
```

Because blobs are content-addressed, incremental backups are efficient: unchanged blobs have unchanged filenames and rsync skips them automatically.

**S3 backend (`blob_backend = "s3"`):**

Enable S3 bucket versioning and cross-region replication in your S3 provider. No additional backup tooling is required; the object store is the durable store. Add a lifecycle rule that expires noncurrent versions within the retention limit in §8.1; otherwise a deleted or taken-down blob survives as an old version. Verify versioning is enabled:

```bash
aws s3api get-bucket-versioning --bucket agora-relay-blobs-prod
# Expected: { "Status": "Enabled" }
```

### 8.5 Database Restore Procedure

1. Stop the relay process:
   ```bash
   systemctl stop agora-relay
   # or: docker compose stop relay
   ```

2. Restore the database:
   ```bash
   # PostgreSQL
   createdb -h $POSTGRES_HOST -U postgres agora_restored
   pg_restore -h $POSTGRES_HOST -U postgres -d agora_restored \
       /backup/agora-relay-20260422.dump

   # Verify row counts
   psql -h $POSTGRES_HOST -U agora -d agora_restored \
       -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"
   ```

3. Discard every admission key registration. Before the relay admits any traffic, delete every registered admission key and every per-token registration `ts` record from the restored database. The relay must not reinstate registrations from a backup, because a key the CO deregistered after the backup was taken would be admitted again (spec §10.4.7). It starts with no registrations and answers `unknown-token` for every token (spec §11.4); clients use another relay in the channel's relay list meanwhile (spec §10.3.5). Dropping the `ts` records is safe, because the CO re-registers with fresh requests.

4. Update the config to point at the restored database (if database name changed).

5. Restart the relay:
   ```bash
   systemctl start agora-relay
   ```

6. Verify recovery via the Admin API:
   ```bash
   curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
       http://localhost:9099/admin/status | jq .
   ```

7. Check that peer connections are re-established within 5 minutes. If not, check `GET /admin/peers` for peer reachability.

8. Notify every CO. Send each loaded agreement's `contact` a notice that this relay lost its registrations and the time of the restore. The CO's registration service then re-registers every current key under that agreement (spec §10.5.3). Without the notice, the CO's periodic re-registration restores them within 24 hours. Restored envelopes and blobs may be kept within their retention; the relay serves them again once their token is registered again.

---

## 9. Upgrade Procedure

### 9.1 Pre-Upgrade Checklist

Before upgrading any relay component:

- [ ] Read the release notes for the new version. Identify breaking vs non-breaking changes (§9.6).
- [ ] Verify the new image digest matches the published digest in the release notes.
- [ ] Back up the database (§8.3).
- [ ] Note the current relay version: `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/status | jq .version`
- [ ] Verify peer count is at expected baseline: `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/peers | jq '.peers | length'`
- [ ] Note the loaded agreement count: `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/status | jq .agreements_loaded`
- [ ] Confirm a rollback path exists (rollback image tag and database rollback script if schema changes are involved).

### 9.2 Single-Node Upgrade

A single-node upgrade is a rolling restart with minimal downtime (typically under 30 seconds, limited by QUIC connection migration):

```bash
# 1. Pull the new image
docker pull ghcr.io/agora-protocol/relay:0.2.2@sha256:<new-digest>

# 2. Update the image tag in docker-compose.yml or your deployment config

# 3. Run database migrations before starting the new relay version
docker run --rm \
    -e AGORA_DB_URL=$AGORA_DB_URL \
    ghcr.io/agora-protocol/relay:0.2.2@sha256:<new-digest> \
    migrate --up

# 4. Perform a graceful reload (zero-downtime for non-breaking upgrades)
docker compose up -d --no-deps relay

# 5. Verify the new version is running
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/status | jq .version
# Should return "0.2.2"

# 6. Verify peer connections recovered
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/peers | jq '[.peers[] | select(.reachable == true)] | length'
```

### 9.3 Multi-Node Rolling Upgrade

For multi-node HA deployments (§15), upgrade one node at a time:

1. Remove one relay node from the load balancer target group (mark as unhealthy or detach).
2. Wait for in-flight WebTransport/WebSocket connections to drain. Clients reconnect to surviving nodes. Allow 60 seconds for drain.
3. Run database migrations on the removed node (safe: migrations must be backward-compatible, see §9.4).
4. Upgrade the node to the new image.
5. Restart the node and verify it connects to peers and passes health checks.
6. Return the node to the load balancer.
7. Repeat for remaining nodes.

Never upgrade all nodes simultaneously. At minimum, keep one node on the old version until the first upgraded node has been verified healthy.

### 9.4 Database Migration Procedure

Database migrations are managed by the relay binary's built-in migration tool:

```bash
# Check pending migrations
agora-relay migrate --status

# Apply pending migrations (run before starting the new relay version)
agora-relay migrate --up

# Rollback the last migration (only if the upgrade is being aborted)
agora-relay migrate --down --steps 1
```

Migrations are versioned and tracked in the `schema_migrations` table. All migrations must be:
- **Backward-compatible for one version.** A migration that adds a column must have a default value so the old relay binary can continue to read the table. Dropping columns requires a two-version process (deprecate in v0.2, remove in v0.3).
- **Idempotent.** Running the same migration twice must produce the same result.

### 9.5 Post-Upgrade Verification

After upgrading:

1. Confirm version: `GET /admin/status` returns the expected version string.
2. Confirm peer mesh: `GET /admin/peers` shows expected peer count and all previously reachable peers are still reachable.
3. Confirm client admission: connect a test client and complete the `ClientHello`/`RelayHello` exchange (spec §11.6).
4. Confirm JMAP: `curl -s https://<relay-hostname>/v1/agora/jmap/.well-known/jmap` returns a valid session object (paths are relative to `endpoints.jmapSync`, spec §11.8.1).
5. Confirm agreements: `GET /admin/status` shows the same `agreements_loaded` and `admission_keys_registered` as before the upgrade, and `agora_relay_admission_sig_verifications_total{result="valid"}` is increasing.
6. Confirm metrics: check the Prometheus dashboard for any anomalous spikes.

### 9.6 Breaking vs Non-Breaking Changes

A relay upgrade is **non-breaking** if:
- It adds new optional config fields or Admin API endpoints.
- It adds new optional capabilities to the relay manifest.
- Database migrations only add columns with defaults (backward-compatible).
- The protocol spec version is unchanged.

A relay upgrade is **breaking** if:
- It changes the wire format of any protocol message.
- It removes or renames config fields that were previously set.
- Database migrations drop or rename columns.
- The relay manifest declares a new required capability that peer relays must support.
- The protocol spec version increments on any transport surface.

Release notes must call out breaking changes explicitly. A breaking change must not be deployed by rolling upgrade without coordination across all relay nodes sharing the same relay DID.

### 9.7 Rollback Procedure

If a post-upgrade verification fails:

1. Stop the new relay version.
2. If a database migration was applied, roll it back:
   ```bash
   agora-relay migrate --down --steps 1
   ```
3. Start the previous relay version.
4. Verify the relay is healthy via `GET /admin/status`.
5. File an incident report documenting what failed and why.

---

## 10. Key Management

### 10.1 Relay Signing Key

The relay signing key is an Ed25519 private key and the relay's cryptographic identity. It is listed in the manifest `keys` and in the DID document of `relayDID`, and the relay signs its manifest, its `RelayAd`, relay-to-relay requests (spec §10.2.3) and push wake-up requests (spec §11.7.4) with it. For a `did:key` relay the DID is derived from it.

**Generation:**
```bash
agora-relay keygen --output /etc/agora-relay/keys/relay-signing.key
# This produces a PEM-encoded Ed25519 private key.
# The corresponding relay DID is printed to stdout.
```

**File permissions.** The key file must have permissions `0600` and be owned by the relay process user. The relay must reject any other permissions at startup.

**HSM storage (recommended for production).** Store the key in a hardware security module or cloud HSM. Options are below. Validation levels, product names, Ed25519 support and pricing change; verify each against current vendor documentation (table written 2026-10, not re-verified).

| Option | Notes |
|---|---|
| PKCS#11 + SoftHSM2 | Development/testing only. Software HSM; no hardware protection. |
| PKCS#11 + YubiHSM 2 | Affordable hardware HSM. Supports Ed25519. Network-attached or USB. |
| AWS CloudHSM | FIPS 140 Level 3 validated (140-2 or 140-3 depending on HSM type). Billed hourly per HSM. Use PKCS#11 or JCE provider. |
| GCP Cloud HSM | FIPS 140 Level 3 validated. Use via Cloud KMS API. |
| Azure Dedicated HSM or Azure Cloud HSM | FIPS 140 Level 3 validated. Use PKCS#11 provider. Check which offering Microsoft currently sells. |
| TPM 2.0 | Available on most server hardware. Ed25519 support varies by TPM firmware. |

Configure PKCS#11 in the relay config:
```toml
[identity]
pkcs11_provider = "/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so"
signing_key_path = "label=agora-relay-signing"
```

**Key rotation:**

Key rotation uses the overlap window of spec §10.2.6, which requires the relay to publish both the old and new keys in its manifest for at least 48 hours, the old one marked `deprecated`. Rotate before `key_expiry_days` elapses:

1. Generate a new signing key:
   ```bash
   agora-relay keygen --output /etc/agora-relay/keys/relay-signing-new.key
   ```

2. Update the relay config to reference the new key as `signing_key_path`, and set `signing_key_deprecated_path` to the old key.

3. Reload the config:
   ```bash
   curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/reload
   ```
   The relay immediately publishes a new manifest with both keys listed: the new key with `"status": "active"` and the old key with `"status": "deprecated"`.

4. Wait the full 48-hour overlap window. During this period, peer relays accept signatures from either key.

5. After 48 hours, set `signing_key_deprecated_path = ""` and reload again. The relay publishes a manifest with only the new active key.

If `relayDID` is a `did:key`, the DID is the key, so a new key is a new relay identity: peers treat it as a new relay, and each CO must sign a new agreement naming it as `provider`. Where the relay has a DNS name, use `did:web` (spec §10.2.1) so that rotation keeps the DID and the agreements. For `did:web`, update the DID document at `/.well-known/did.json` to list both keys during the overlap.

**Emergency key rotation.** If you believe the signing key is compromised, do not use the overlap. Spec §12.12 has the relay publish its manifest with the compromised key's `status` set to `revoked`, and peers reject every request signed with a revoked key:

1. Generate a new key and set it as `signing_key_path`.
2. Add the compromised key's manifest `id` to `identity.revoked_key_ids` and leave `signing_key_deprecated_path` empty.
3. Remove the compromised key from the `did:web` DID document.
4. Reload. The relay publishes a manifest listing the new key as `active` and the old one as `revoked`.
5. Notify each CO you hold a `ServiceAgreement` with through the agreement's `contact` (spec §12.12), and notify Level 3 peer operators.

Peers that still hold the old manifest may reject requests until they refetch it; spec §12.12 asks them to refetch when a signature fails, and their cache lasts at most one hour (spec §10.2.3). The relay key signs no member-visible content and is not an admission key, so members need to do nothing.

### 10.2 TLS Certificates

**Let's Encrypt (recommended).** Set `tls_acme = true` in the config. The relay handles ACME certificate negotiation, renewal, and reload automatically. No operator action is required for normal renewals.

**Manual certificate management:**
```bash
# Renew a certificate using certbot
certbot renew --cert-name relay.example.com

# After renewal, reload the relay to pick up the new cert
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/reload
```

TLS certificates are independent of the relay's protocol identity and do not need the relay DID rotation procedure.

### 10.3 Admin API Token

Generate a new token:
```bash
openssl rand -base64 32
```

Rotation procedure:
1. Generate a new token.
2. Update `AGORA_ADMIN_TOKEN` in your secrets manager.
3. Restart the relay (the admin token cannot be reloaded live because that would create a TOCTOU window).

### 10.4 Compliance Logger Signing Key

Not applicable. A relay operates no compliance logger and holds no logger key. The logger is a CO principal on CO infrastructure with its own DID and keys (ARCHITECTURE S8, spec §7.3).

---

## 11. Network Requirements

### 11.1 Required Open Ports

| Port | Protocol | Direction | Purpose | Access |
|---|---|---|---|---|
| 443 | UDP (QUIC) | Inbound + Outbound | WebTransport (primary client transport); Peer API over HTTP/3 and libp2p gossipsub QUIC, on one QUIC listener split by ALPN (`h3` or `libp2p`) | Public internet |
| 443 | TCP (TLS) | Inbound + Outbound | WebSocket (fallback client transport), JMAP sync API, blob CAS, admission key registration, `/.well-known/agora-relay`; Peer API over HTTP/1.1 or HTTP/2, gossipsub TCP fallback, including blob replication and pull-through (spec §10.2.2) | Public internet |
| 9099 | TCP | Inbound | Admin API | Internal only (loopback or management VLAN) |
| 9100 | TCP | Inbound | Prometheus metrics scrape | Internal only (monitoring system) |

### 11.2 Required DNS Records

```dns
; A/AAAA records for the relay hostname
relay.example.com.      IN  A      203.0.113.1
relay.example.com.      IN  AAAA   2001:db8::1

; SRV records for DNS-SD discovery (spec §10.2.5, Method 3)
; QUIC (preferred, lower priority number = higher preference)
_agora-relay._udp.example.com.  IN  SRV  10 0 443   relay.example.com.
; TCP fallback
_agora-relay._tcp.example.com.  IN  SRV  20 0 443   relay.example.com.

; TXT records with relay DID and manifest URL, at the same owner names as the
; SRV records (spec §10.2.5, Method 3)
_agora-relay._udp.example.com.  IN  TXT  "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"
_agora-relay._tcp.example.com.  IN  TXT  "did=did:web:relay.example.com manifest=https://relay.example.com/.well-known/agora-relay"

; Optional: separate subdomain for push proxy
push.relay.example.com.  IN  A  203.0.113.1
```

Spec §10.2.5 asks relays to publish both SRV records, and asks a relay that cannot expose UDP to publish only the `_agora-relay._tcp` record. Spec §10.2 has such a relay omit `gossipsub-quic-v1` from its manifest capabilities.

### 11.3 Firewall Rules

**Public interface (internet-facing):**
- ALLOW UDP 443 from anywhere (WebTransport, Peer API over HTTP/3, gossipsub QUIC)
- ALLOW TCP 443 from anywhere (WebSocket, JMAP, blob CAS, admission key registration, well-known, Peer API, gossipsub TCP fallback)
- ALLOW UDP 443 and TCP 443 outbound (connections to peer relays)
- DENY all other inbound

Peer traffic shares 443 with client traffic, so a public relay cannot restrict peers by source IP at the firewall. Peer authentication happens at the Peer API (spec §10.2.3). A relay that peers only with known relays and serves peers on a separate port may firewall that port to their address ranges.

**Management interface (internal):**
- ALLOW TCP 9099 from monitoring/ops CIDR only (Admin API)
- ALLOW TCP 9100 from Prometheus scrape CIDR only (metrics)
- DENY all other inbound on management interface

**Blob store (S3 backend only):**
- ALLOW TCP 443 outbound to S3-compatible endpoint (blob store API)
- No additional inbound ports required; the local blob store serves via the relay process on existing ports

### 11.4 Load Balancer Considerations

WebTransport (QUIC) connections are stateful: a client maintains a QUIC connection to a specific relay instance. Standard round-robin load balancing breaks QUIC connections by routing packets to different backends.

**QUIC load balancing requirements:**
- Use a Network Load Balancer (NLB, Layer 4) with UDP support, not an Application Load Balancer (which does not support QUIC for WebTransport).
- Configure the NLB with **connection tracking** so that UDP flows from the same source IP:port are consistently forwarded to the same backend. AWS NLB does this automatically for UDP.
- For Kubernetes, use a Service of type `LoadBalancer` with `externalTrafficPolicy: Local` to prevent SNAT from breaking connection tracking.

**WebSocket sticky sessions.** WebSocket connections are long-lived TCP connections. Any TLS-terminating load balancer works, but it must be configured for **sticky sessions** (source IP or cookie-based affinity). Without sticky sessions, WebSocket upgrade attempts may be routed to a different backend than the original HTTP request.

### 11.5 Tor Hidden Service (Optional)

To expose the relay as a Tor v3 hidden service:

1. Install and configure Tor:
   ```
   # /etc/tor/torrc additions
   HiddenServiceDir /var/lib/tor/agora-relay/
   HiddenServicePort 80 127.0.0.1:8080
   HiddenServiceVersion 3
   ```

2. Start Tor. The `.onion` address is in `/var/lib/tor/agora-relay/hostname`.

3. Configure the relay with `tor_enabled = true`, the control port address, and `tor_ws_listen` set to the loopback address that `HiddenServicePort` forwards to. That listener speaks plaintext WebSocket, not TLS: forwarding onion port 80 to the TLS listener on 443 would break the advertised `ws://` endpoint.

4. The relay publishes the `.onion` address in its manifest under `endpoints.onion` as `ws://examplerelay3xyz.onion/v1/agora/ws`.

Back up the `.onion` key file at `/var/lib/tor/agora-relay/hs_ed25519_secret_key` with the same rigor as the relay signing key. If it is lost, the hidden service address changes permanently.

---

## 12. Capacity Planning

### 12.1 Storage

**Message store (database).** Each held routing envelope is approximately 2 to 10 KB (sealed MLS ciphertext plus the CBOR routing fields and the 64-byte `admissionSig`), and never more than 65,536 bytes (spec §11.4). For a typical text message:

- Average encrypted message size: about 2 KB (short messages) to about 8 KB (rich text + reactions)
- Routing envelope overhead per message: about 150 bytes (`signed` fields and `admissionSig`)
- Effective planning estimate: **4 KB per message**

Storage growth formula:
```
daily_storage_growth_GB = active_users × messages_per_user_per_day × 4KB / (1024^3)
```

For 500 active users sending 50 messages/day each:
```
500 × 50 × 4096 = 102,400,000 bytes ≈ 98 MB/day
```

At 30-day retention: about 2.9 GB. At 90-day retention: about 8.8 GB. Retention is set per agreement (`retentionDays`). Relay-held envelopes are only the recent part of a channel's history; older history lives in members' stores and the CO's archive (spec §5.2.5). Regulatory retention periods are met by the CO's archive, not by relay retention (ARCHITECTURE §4); a CO that asks for multi-year relay retention is asking for storage, and the agreement's `storageQuotaGb` should reflect it.

The relay sees users only as connections, so size from the storage quotas in your agreements rather than from user counts where you can: the sum of `storageQuotaGb` across agreements is the upper bound on agreement-covered storage.

**Blob store.** Blobs are content-addressed, but expect little deduplication: files are encrypted under a fresh key per upload, so the same file uploaded twice is two sets of blocks (spec §14.3.4). Each file costs its size plus 16 bytes per 256 KiB chunk and a small root block. Replicated and pulled copies count against your agreement for the token, so with the default `replicationFloor` of 2 each uploaded blob sits on at least two relays. Plan for the sum of agreement storage quotas, less what the database already holds, plus CO-published records (public Space state and directory documents, typically tens of KB each).

### 12.2 Memory

| Component | Memory estimate |
|---|---|
| Base relay process | ~100 MB |
| Per active WebTransport connection | ~200 KB (QUIC state, per-connection buffers) |
| Per active WebSocket connection | ~50 KB |
| Per active channelToken (routing table entry, registered admission public key) | ~10 KB |
| Peer manifest cache | ~10 KB per cached manifest |

For 1,000 active WebTransport connections and 200 WebSocket connections:
```
100 MB base
+ 1000 × 200 KB = 200 MB
+ 200 × 50 KB  = 10 MB
≈ 310 MB minimum
```

Plan for 2× headroom: **2 GB RAM** for up to 1,000 concurrent connections. Scale to 8 GB for up to 5,000 connections.

### 12.3 CPU

| Operation | CPU cost |
|---|---|
| `admissionSig` Ed25519 verification (per envelope) | ~0.1 ms |
| Outer envelope validation (per message) | ~0.05 ms |
| PoW verification, any difficulty | ~0.01 ms (one SHA-256) |
| JMAP history query (50 messages) | ~2–10 ms (database query + serialization) |
| Gossipsub message routing | ~0.1 ms per subscriber |

Message fan-out is the dominant CPU workload. For 500 active users in 50 active channels with average 10 subscribers per channel:
- 50 messages/second total × 10 subscribers × 0.05 ms routing = 25 ms CPU/second (~2.5%)
- 50 messages/second × 0.1 ms `admissionSig` verification = 5 ms CPU/second (~0.5%)

TLS is offloaded by the kernel or hardware in modern Linux systems and is not a significant CPU consumer.

**Baseline recommendation.** 2 vCPU for up to 1,000 concurrent connections, 4 vCPU for up to 5,000. Gossipsub fan-out scales linearly with subscriber count; scale horizontally before vertically when fan-out is the bottleneck.

### 12.4 Network Bandwidth

| Direction | Estimate |
|---|---|
| Per active user ingress | ~5–20 KB/s (sending messages) |
| Per active user egress | ~20–100 KB/s (receiving from subscribed channels) |
| Gossipsub peer mesh | ~100–500 KB/s per peer at mesh degree 6 |
| Blob store (S3 backend) | ~1–10 MB/s during active CID fetches from S3 |
| Eager replication egress | Up to (`replicationFloor` - 1) × blob upload ingress; 1× at the default floor of 2 |
| Replication, pull-through and seed ingress | Blob bytes that peers push to you plus what you pull on clients' behalf; a newly seeded relay can pull a channel's whole blob set in a burst |

Cap peer blob traffic with `storage.blob_peer_transfer_concurrency` if seeding or pull-through bursts compete with client traffic.

For 500 active users:
- Client traffic: 500 × 100 KB/s = 50 MB/s peak egress
- Peer mesh: 6 peers × 500 KB/s = 3 MB/s
- Total estimated peak: ~55 MB/s ≈ 440 Mbps

A 1 Gbps uplink is sufficient for up to about 1,000 concurrent active users. For larger deployments, scale horizontally.

### 12.5 Vertical vs Horizontal Scaling

Scale **vertically** (larger instance) when:
- CPU is the bottleneck (per-message processing, PoW verification at high volume).
- Single-node latency is acceptable and operational complexity matters more than raw capacity.

Scale **horizontally** (add relay nodes, see §15) when:
- Connection count exceeds about 5,000 (QUIC connection table becomes a bottleneck).
- Network bandwidth approaches 1 Gbps.
- Geographic diversity is needed (deploy in multiple regions).
- HA without a maintenance window is required.

---

## 13. Security Hardening

### 13.1 TLS Configuration

The relay must be configured with the following TLS parameters:

```toml
[server]
tls_min_version = "1.3"
```

TLS 1.2 is permitted only for WebSocket connections to accommodate legacy clients; WebTransport (QUIC) requires TLS 1.3 by protocol definition.

For TLS 1.3, cipher suites are not configurable (the protocol mandates a fixed set). For TLS 1.2 fallback (WebSocket only), the relay must not negotiate:
- `TLS_RSA_*` (no forward secrecy)
- `*_RC4_*` (broken cipher)
- `*_3DES_*` (broken cipher)
- `*_CBC_SHA` without `*_SHA256` or stronger HMAC

The acceptable TLS 1.2 cipher list (in priority order):
```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
```

### 13.2 Network Segmentation

The Admin API (`/admin`) and Prometheus metrics (`/metrics`) must be bound to a non-public interface. Default configuration (`admin_addr = "127.0.0.1:9099"`, `metrics_addr = "127.0.0.1:9100"`) is correct for single-node deployments. For multi-node deployments, bind to an internal management VLAN address, not `0.0.0.0`.

Blobs are served publicly only through the CAS and JMAP endpoints on the client-facing port (§2.1). The admin content operations (`GET` and `DELETE /admin/content/{cid}`) are on the admin interface with the rest of the Admin API.

The PostgreSQL port must not be exposed outside the relay's private network.

### 13.3 Rate Limiting

The relay knows no user identities, so its controls key on what it can see: network address, `channelToken`, and agreement (spec §11.6, ARCHITECTURE §9). The default limits in §3.2 (`[rate_limits]`) are conservative starting points. Tune based on observed traffic:

- If legitimate high-volume bot traffic hits `channel_msg_per_second`, raise it globally. The relay cannot scope a limit to a channel, because it cannot map a token to a channel, and a channel's token changes whenever its CO rotates the admission key. Never set the per-token limits below the floor of spec §11.6 (20 envelopes and 256 KiB per second).
- If the relay serves Tor clients or carrier NAT, do not rely on per-address limits (spec §11.3). Many clients share one address. Lower `admission_pow_load_threshold` so that clients over their per-address limit can still connect by solving an admission challenge.
- Writes need a valid `admissionSig` under an admission key registered under an agreement (spec §10.5.4), so non-members cannot write at all. A member removed since the CO's last key rotation can still post until the CO deregisters the old key (spec §10.5.3); that is the CO's window to close, not the relay's. Floods of invalid envelopes cost one signature check each; watch `AgoraAdmissionSigFailureSpike` (§7).
- Storage and bandwidth are bounded per agreement by its quotas (spec §10.5.1), not by rate limits.

### 13.4 PoW Difficulty Tuning

Two proofs of work apply at a relay, both non-monetary abuse controls:

- **Admission proof (spec §11.6).** The relay asks for it before `RelayHello` under load or for addresses over their limit. `admission_pow_difficulty` sets its difficulty.
- **Envelope proof (spec §10.5.2).** A channel's `PowPolicy` sets the difficulty its members' clients require. The relay cannot see that policy, so it enforces only its own floor, `envelope_pow_min_difficulty`, published as manifest `minPowDifficulty`. Spec §10.5.2 forbids it to require more than it declares.

| Context | Admission difficulty | Envelope floor | Rationale |
|---|---|---|---|
| Private relay serving one CO's agreements | 16 | 0 | Writes already need an admission signature; admission PoW only absorbs connection floods |
| Public relay, light abuse | 18–20 | 0 | ~262,000–1M hash ops per connection under load; imperceptible to a human |
| Public relay, heavy abuse | 22 | 16 | ~4M hash ops per connection; envelope floor makes bulk flooding expensive |

Difficulty above 24 is not recommended for either proof because it begins to degrade legitimate user experience on low-end hardware. An envelope floor above the difficulty a channel sets would make the relay drop that channel's valid traffic, so keep the floor at or below 18 unless every CO served agrees.

### 13.5 OS Hardening

Minimal practical checklist for the relay host:

- **Minimal OS install.** Do not install unnecessary packages. Use a minimal container base image (Debian slim or distroless).
- **Non-root process.** Run the relay as a non-root user (uid 1000 in the reference Dockerfile). Never run as uid 0.
- **No SSH access in containers.** Use `kubectl exec` or `docker exec` for debugging. Remove SSH daemon from container images.
- **Read-only filesystem where possible.** Mount `/etc/agora-relay/keys` and `/etc/agora-relay/relay.toml` as read-only. Only `/var/lib/agora-relay` needs write access.
- **Seccomp profile.** Apply a restrictive seccomp profile to the relay container. The relay requires a limited syscall set (network I/O, file I/O, time); deny the rest.
- **No capability escalation.** Run containers with `--no-new-privileges` and `CAP_DROP ALL`, adding back only `CAP_NET_BIND_SERVICE` if binding to port 443 directly.
- **Automatic security updates.** Enable unattended upgrades for the OS. Relay binary upgrades follow the procedure in §9.

### 13.6 Dependency Supply Chain

- Pin all Docker images to digests as well as tags (§4.1).
- Verify image signatures before deployment (use `cosign` or Docker Content Trust).
- Pin the relay binary image to a specific version and digest.
- Pin PostgreSQL to a specific minor version.
- Do not pull `:latest` in production.
- Review the relay binary's software bill of materials (SBOM) on each release. The relay publishes SBOM artifacts in SPDX format alongside each release image.

---

## 14. Enterprise Integration Deployment

Enterprise integrations are CO components (ARCHITECTURE §2.3). They hold identity keys, membership knowledge or plaintext, so they run under the CO's control on CO infrastructure, never inside a relay (ARCHITECTURE S8). A relay needs no configuration for any of them and treats an enterprise CO like any other: one or more `ServiceAgreement`s signed by the CO's billing DID, and the admission keys its registration service registers under them. An organization that runs both its own relays and its own CO components is acting in two roles and keeps the keys distinct (ARCHITECTURE §2.4).

### 14.1 DID Sidecar (O365/Entra ID)

The employer DID provisioning service (spec §2.5) is a CO component. It serves the organization's `did:webvh` user documents, registers device keys, and hosts its users' KeyPackages at the `KeyPackageEndpoint` named in each DID document, where Welcomes are delivered (spec §2.5.3). The relay never resolves member DIDs, never authenticates clients by DID, and stores no KeyPackages (spec §10.4.3, spec §11.6). No relay-side setting restricts a relay to an organization's members. MLS enforces membership, and the CO-issued admission key that only current members hold enforces relay admission (ARCHITECTURE §6.2). The same holds for direct message (DM) groups: the initiator's identity host, often the employer's provisioning service, issues and registers a DM group's admission key (spec §10.5.3).

Deployment guidance: `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`, and `profiles/universal-idp-did.md`.

### 14.2 Purview Bridge

The Purview bridge and the compliance logger it reads from are CO components that hold plaintext (ARCHITECTURE S8, spec §7.3). Neither runs on a relay, and the relay has no compliance configuration, queue or log store. Where an IO hosts them on its hardware, that is a separate contract with the IO acting as the CO's processor; they remain CO principals with their own DIDs and keys and are outside the relay's configuration (ARCHITECTURE §7 item 8).

Deployment guidance: `profiles/purview-bridge.md`.

### 14.3 SAML/OIDC Configuration

None on the relay. SAML and OIDC are consumed by the CO's provisioning service during onboarding and device registration (spec §2.5.3, spec §2.5.4). The relay processes no identity provider (IdP) tokens and no assertions.

---

## 15. Multi-Relay HA Deployment

### 15.1 Architecture

A multi-relay HA deployment runs two or more relay instances sharing a common database and blob store. The goal is to survive a single relay instance failure without client-visible disruption.

```
                  ┌─────────────────────────────────────┐
                  │   Network Load Balancer              │
                  │   UDP 443 (QUIC) + TCP 443 (WS)      │
                  └───────┬──────────────┬──────────────┘
                          │              │
               ┌──────────▼──┐      ┌───▼──────────┐
               │  relay-1    │      │  relay-2     │
               │  (primary)  │      │  (replica)   │
               └──────┬──────┘      └──────┬───────┘
                      │                    │
               ┌──────▼────────────────────▼──────┐
               │      PostgreSQL Primary           │
               │      + Streaming Replication      │
               └──────────────┬───────────────────┘
                              │
               ┌──────────────▼───────────────────┐
               │     Shared Blob Store             │
               │  (S3-compatible object store)     │
               └──────────────────────────────────┘
```

### 15.2 Active-Active vs Active-Passive

**Active-active (recommended).** Both relay instances accept connections simultaneously. The load balancer distributes connections across instances. The database is the shared state layer; both instances read and write to it. This configuration requires the load balancer to provide QUIC affinity (§11.4), so that packets from the same QUIC connection go to the same backend.

**Active-passive.** One relay handles all traffic; the second is a hot standby that becomes active only when the primary fails. It is simpler to reason about but wastes the capacity of the standby. Use only when active-active QUIC affinity is not available in the load balancer.

### 15.3 Database: PostgreSQL HA

For multi-relay HA, use PostgreSQL with streaming replication:

- **Primary** handles reads and writes.
- **Replica(s)** receive streaming WAL replication and handle read-only queries.
- Use Patroni or pg_auto_failover for automatic primary election on failure.
- Connection pooling via PgBouncer in front of each relay's database connection.

Alternatively, use **CockroachDB** for a distributed-by-default PostgreSQL-compatible database. CockroachDB handles its own replication and failover with no external HA tooling needed. It is appropriate for multi-region deployments but adds operational complexity for single-region.

### 15.4 Blob Store: Shared Backend

All relay instances must share the same blob store so that any instance can serve any CID. Use `blob_backend = "s3"` and configure all instances to point at the same bucket:

- **AWS S3.** Set `blob_s3_endpoint`, `blob_s3_bucket`, and `blob_s3_region` identically across all relay instances. Use an IAM role or access key with `s3:GetObject` and `s3:PutObject` on the bucket.
- **MinIO (self-hosted).** Deploy a MinIO cluster with erasure coding for durability. All relay instances connect to the same MinIO endpoint. Simpler to control than AWS; requires operating the MinIO cluster.
- **Cloudflare R2 / Backblaze B2.** S3-compatible APIs; configure `blob_s3_endpoint` to the provider's S3-compatible URL. Zero egress cost (R2) or very low cost (B2) makes these attractive for read-heavy relay workloads.

Do not use a shared NFS/EFS volume as a blob store backend. NFS introduces a single point of failure and does not provide the atomic put semantics required for correct CID-keyed storage.

### 15.5 Session Affinity

WebTransport (QUIC) connections maintain cryptographic state (QUIC connection ID, TLS session). The load balancer must route all packets from a given QUIC connection to the same relay instance for the duration of the connection.

WebSocket connections are long-lived TCP connections. The load balancer must not terminate and re-route WebSocket connections mid-stream.

**For AWS NLB.** UDP flows are tracked by 5-tuple (source IP, source port, destination IP, destination port, protocol) for the duration of the flow idle timeout. Set the NLB idle timeout to at least 350 seconds (longer than the QUIC idle timeout of 300 seconds).

**For Kubernetes.** Use a Service with `sessionAffinity: ClientIP` and `sessionAffinityConfig.clientIP.timeoutSeconds: 10800` (3 hours).

### 15.6 Peer Mesh: Per-Instance Peering

Each relay instance must independently participate in the gossipsub peer mesh. Do not front the Peer API behind the load balancer; peer relays should connect to individual relay instance endpoints for gossip.

Each instance announces itself with the same `relay_did` (the shared identity) but a distinct physical endpoint. The relay manifest should list the load balancer endpoint for client-facing transports and instance-specific endpoints for the Peer API and gossipsub:

```json
"endpoints": {
  "webTransport": "https://relay.example.com/v1/agora/wt",
  "webSocket":    "wss://relay.example.com/v1/agora/ws",
  "peerAPI":       "https://relay1.internal.example.com/v1/agora/peer",
  "jmapSync":      "https://relay.example.com/v1/agora/jmap",
  "admissionKeys": "https://relay.example.com/v1/agora/admission-keys",
  "gossipQuic":    "/ip4/10.0.1.1/udp/443/quic-v1"
}
```

Every other relay instance publishes its own manifest entries with its instance-specific Peer API endpoint. `admissionKeys` stays on the shared hostname because it must equal the `endpoint` in every relay agreement (spec §10.5.1). Every instance must see every registration through the shared database before it admits envelopes for the token.

### 15.7 Health Check and Failover

Configure the load balancer to health-check each relay instance via:
```
GET /v1/agora/peer/health
```

This endpoint is unauthenticated (spec §10.2.2) and returns `{ "status": "healthy" }` when the relay is operating normally. The load balancer must stop routing to an instance that returns `unhealthy` or does not respond within 5 seconds.

Health check interval: 10 seconds. Unhealthy threshold: 2 consecutive failures. Healthy threshold: 3 consecutive successes.

---

## 16. Decommissioning

### 16.1 Overview

Decommissioning a relay is a multi-step process designed to minimize disruption to the COs and clients that depend on it. Do not turn a relay off without following this procedure; abrupt shutdown leaves clients unable to reconnect, pinned CIDs potentially inaccessible, and peer relays with stale mesh entries. A CO replaces a relay by registering its admission keys with another relay, listing that relay to members, and deregistering the keys here, without changing any Space's identity or membership (spec §10.3.5, ARCHITECTURE S5). This procedure gives each CO the time and the CID lists to do that.

### 16.2 Pre-Decommissioning Notification

1. At least 30 days before the planned shutdown time, set `retiresAt` in the relay manifest to that time, as an RFC 3339 UTC timestamp, and publish the re-signed manifest (spec §10.2.1, spec §10.4.7):
   ```json
   "retiresAt": "2026-05-22T00:00:00Z"
   ```
   Spec §10.4.7 requires the 30 days unless the relay and a CO have agreed a different notice period out of band for that CO.

2. At the same time as step 1, notify every loaded agreement's CO at the agreement's `contact`, giving the `retiresAt` time (spec §10.4.7). The relay knows which COs it serves only through their agreements (ARCHITECTURE §5 item 6); it has no list of Spaces to notify. Each CO removes this relay from its relay lists and deregisters its keys here before `retiresAt` (spec §10.3.5).

3. Gossip a `RelayAd` update on `v1/agora/discovery`.

### 16.3 Drain

Until `retiresAt` the relay keeps admitting every registered token and accepting connections (spec §10.4.7). Traffic falls off before then as each CO deregisters its keys here; the relay sends `token-withdrawn` to the remaining subscribers of those tokens (spec §11.4). Do not refuse connections early, except that tokens whose COs have already deregistered need no service.

1. At `retiresAt`, stop accepting new client connections:
   ```toml
   [server]
   accepting_new_connections = false
   ```
   Reload the config via `POST /admin/reload`. Existing connections remain active; new connection attempts are refused.

2. Wait for active client connections to drop. Clients reconnect to the other relays their CO lists in each `ChannelAdmissionKey` (spec §10.3.5). Monitor:
   ```bash
   watch -n 5 'curl -s -H "Authorization: Bearer $ADMIN_TOKEN" localhost:9099/admin/status | jq .active_connections'
   ```

3. Allow at least 60 minutes of drain time. After drain, there should be fewer than 50 active connections (stragglers on slow reconnect schedules).

### 16.4 Export: Ensuring CID Availability

Content stored under an agreement belongs to that agreement's CO. The relay cannot tell which Space any CID belongs to, and does not need to: it hands each CO the list of CIDs stored under its agreement, and the CO arranges for another IO, or its own storage, to hold them.

1. For each agreement, export its CID list and send it to the agreement's `contact`:
   ```bash
   curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
       "localhost:9099/admin/agreements/$AGREEMENT_ID/cids" \
       > "cids-$AGREEMENT_ID.txt"
   ```

2. The CO arranges for its other relays to hold what it needs. Envelopes on tokens it registered at several relays already exist there through mesh fan-out. Blobs already exist on at least `replicationFloor` relays carrying the token, where that many carry it (spec §10.4.4). For the rest, the CO adds a successor relay to the channel's relay list and either lets it pull blobs as clients ask for them or sends it a `seed` instruction listing the CIDs (spec §11.4). Either way, the successor pulls from you over the Peer API, so keep the Peer API up and the tokens registered until the CO confirms. Pins apply per relay, so the CO pins what must outlive retention at the successor with a `PinInstruction`. A CO may instead ask you to copy the blobs to a successor relay directly; the blobs are ciphertext, so a copy from your blob store (filesystem or S3 bucket) to the successor's storage under the CO's agreement with the successor discloses nothing new.

3. Before shutdown, check that each listed CID is served by at least one other relay the CO named:
   ```bash
   while read cid; do
     if ! curl -sf "https://successor-relay.example.com/v1/agora/blob/$cid" \
         -o /dev/null; then
       echo "NOT AVAILABLE ON SUCCESSOR: $cid" >&2
     fi
   done < "cids-$AGREEMENT_ID.txt"
   ```
   Report missing CIDs to the CO. Whether to delay shutdown for them is a matter for the agreement's terms.

### 16.5 Peer Removal

1. Notify all Level 2+ peers of the planned shutdown by re-announcing the updated manifest (with its `retiresAt`) through the Peer API, whose body is the relay's `RelayManifest` (spec §10.2.2):
   ```bash
   # For each Level 2+ peer:
   curl -X POST https://peer.example.net/v1/agora/peer/announce \
       -H "Content-Type: application/cbor" \
       --data-binary @signed-manifest.cbor
   ```

   `announce` is an authenticated Peer API call, so the request must also carry the RFC 9421 signature of spec §10.2.3; the `curl` line shows only the body and content type. Send it with the relay's Peer API client.

2. Update the relay manifest to remove the relay from `knownPeers` entries gossiped by this relay.

3. Stop the peer heartbeat daemon. Peer relays detect the relay as unreachable after 3 missed heartbeats (180 seconds) and mark it for removal from their peer tables per spec §10.2.6.

### 16.6 DID Tombstone

Before shutdown, prepare a signed tombstone that retires the relay DID. The tombstone is a typed envelope (spec §13.1) with type `urn:agora:practice:RelayTombstone` and content type `application/json`, signed per spec §13.1.1 by the relay DID with its current active key. The signature is in the envelope's `sig` field, not in the body. The body is:

```json
{
  "relayDID": "did:web:relay.example.com",
  "retiredAt": "2026-05-22T00:00:00Z",
  "reason": "decommissioned",
  "successor": "did:web:relay-new.example.com"
}
```

`RelayTombstone` is an operational practice, not part of the protocol spec. Do not gossip it: spec §10.3.2 forbids relays to forward anything on `v1/agora/discovery` other than SpaceAds and RelayAds, so peers would drop it. Instead, serve the encoded envelope at a URL on that hostname that you publish in your operator documentation for as long as you control the hostname, and send it to Level 3 peer operators out of band. Peers that do not know the practice remove the relay after the heartbeat expiry in spec §10.2.6.

### 16.7 Final Shutdown

1. Stop the relay process:
   ```bash
   systemctl stop agora-relay
   # or: docker compose down relay
   ```

2. Take a final database backup (§8.3) only if an agreement or a preservation order requires one. It falls under the retention rules in §16.8.

### 16.8 Data Retention After Shutdown

Shutting down does not extend any retention limit. Data the relay held under an agreement is kept no longer than that agreement allows, and connection metadata no longer than the retention declared in the manifest (ARCHITECTURE §5 item 1, ARCHITECTURE §7 item 11).

| Data | Retention | Rationale |
|---|---|---|
| Relay signing key (private key) | Until the DID tombstone has propagated and been confirmed by all known peers (minimum 30 days) | Needed to sign any post-shutdown corrections to the tombstone |
| Database and blob backups | Until the end of each agreement's `retentionDays`, counted from when each item was stored; pinned CIDs until handed over (§16.4) | Envelopes and blobs are covered by agreement retention (spec §10.4.1) |
| Access logs (connection IP + timestamps) | `connectionLogRetentionDays` as declared in the manifest and agreements | ARCHITECTURE §7 item 11; access logs contain no message content |
| Signed agreements | As the agreements' own terms require | Contract records between the IO and each CO |
| Config file and Admin API audit log | 1 year | Operational record of the operator's own actions; contains no user data |

A preservation order received before deletion can require you to keep specific data longer. It can reach only what is still held within the observation budget (ARCHITECTURE §4); see §17.4.

Data not listed above may be deleted after shutdown. In particular:
- The local blob store may be deleted once each CO has confirmed its CIDs are held elsewhere, or once the agreement's notice period has passed (§16.4).
- Push registrations and ephemeral per-connection state should be deleted immediately on shutdown.

---

## 17. Abuse Handling

A relay is blind by design (spec §10.4.1), so abuse handling at a relay acts on what the relay holds: routing tokens, CIDs, agreements, and network addresses. Decisions about people (who is in a community, who is banned, what content is allowed) belong to the CO (ARCHITECTURE S2). Members report abuse to the CO's moderators with an `AbuseReport` in an MLS group, never to a relay (spec §4.7). What reaches a relay operator is usually a legal notice or a third-party report naming a CID.

### 17.1 Receiving Reports

Publish a working `abuseContact` in the manifest (spec §10.2.1). Ask reporters for what the relay can act on:

- a CID (for example, from a link to `/v1/agora/blob/{cid}`)
- a `channelToken`, if the reporter is a member and their client can show it
- network addresses and times, for connection floods
- for a public Space, its SpaceAd, which names the CO (`advertisedBy`) and the CO's Space endpoint (spec §10.3.2)

A report that names only a Space, a channel or a user cannot be mapped to anything the relay holds. The one exception is a `keyAccess: public` broadcast channel, whose token the CO publishes with its public Space (spec §10.4.1). Forward any other such report to the CO named in the SpaceAd, if there is one; otherwise tell the reporter the relay cannot identify the community.

### 17.2 What an Operator Can Do

**Takedown requests for a CID** (spec §10.4.5). The relay cannot read the blob or envelope, so it cannot judge it and does not try to decrypt it.

1. Look the CID up with `GET /admin/content/{cid}` (§5.2). It returns the `channelToken` under which the CID was stored or pinned, the agreement under which that token is registered, and the agreement's `contact`.
2. Forward the request, with the CID, to the CO at that `contact`. The CO identifies the content from its own records and handles it through its moderation process (spec §4.5).
3. If your policy or the law requires it, stop serving the CID and delete it with `DELETE /admin/content/{cid}`. This removes this relay's copy only. It is a storage decision, not a moderation decision (ARCHITECTURE S2).
4. Tell the requester only what is within the observation budget (ARCHITECTURE §5). The relay does not know, and so cannot say, which Space or member the content belongs to.

| Action | How | Effect |
|---|---|---|
| Delete a CID | `DELETE /admin/content/{cid}` (§5.2) | Deletes the blob or envelope here and refuses re-upload of the same bytes. Copies on other relays are unaffected. |
| Refer to the CO | The agreement's `contact`, or the CO named in a public SpaceAd | The CO can remove members (MLS Remove), rotate the channel's admission key and deregister the old one so that the relay stops admitting it, moderate content, and change policy (spec §4.7, ARCHITECTURE §6.2). |
| Suspend a token | `POST /admin/tokens/{token}/suspend` (§5.2); lift with `DELETE` | Stops admitting envelopes, pin instructions and uploads for that one token; subscribers receive `token-withdrawn`. The relay notifies the CO at the agreement's `contact`, naming the token, time and reason (spec §10.4.7). A new token after the CO rotates the key is admitted. |
| Throttle or block addresses | `[rate_limits]`, admission proof of work, or a firewall rule (§13.3) | Limits floods. Shared addresses (Tor exits, carrier NAT) affect many clients. |
| Terminate an agreement | `POST /admin/agreements/{id}/terminate` (§5.2) | Ends service for every token the CO registered under it, under the agreement's notice terms. Clients receive `token-withdrawn`. |
| Decline peering | `POST /admin/peers/{did}/trust` or `DELETE /admin/peers/{did}` (§5.2) | Stops gossip from an abusive peer relay (spec §10.2.4). |

Admitting a token is the CO's decision, made by registering or deregistering its key (spec §10.5.3). Suspending a token (§5.2), deleting a CID or terminating an agreement is the relay declining service. It is not a moderation decision about any member; do not present it as one.

### 17.3 What an Operator Cannot Do

- Identify the sender of a message, or any member of a group. The relay has no identities (spec §10.4.1).
- Read content, judge it, or delete a single message by content. Envelopes are MLS ciphertext.
- Ban or time out a user. Bans are MLS Removes followed by an admission key rotation by the CO; timeouts are enforced by members' clients (ARCHITECTURE §6.2).
- Map a Space or channel to its routing tokens or to the CIDs its members store, even for a public Space. The one exception is a `keyAccess: public` broadcast channel, whose token the CO publishes with its public Space (spec §10.4.1).
- Remove copies held by other relays or by the CO.

### 17.4 Legal Demands

A demand served on a relay operator yields only what is within the observation budget and still within its retention window: connection metadata, ciphertext envelopes and routing tokens, CIDs, agreement and quota state keyed to billing DIDs (ARCHITECTURE §4, ARCHITECTURE §5). It yields nothing about who is in a community or what they said, and nothing from any agreement beyond what the relay holds. The authoritative record for a regulated community is the CO's archive; refer requests for content to the CO named in the agreement or SpaceAd. A preservation order can stop scheduled deletion of specific held data, using the same handles as above (CID, token, agreement, address and time range).

Every Admin API action taken under this section is recorded in the admin audit log (`GET /admin/audit`). Record the report or order reference in each request's `reason` field.

---

*End of Agora Relay Operations Guide v0.1*
