# Agora Protocol: Messaging

> Binds: both. Verbatim from `import/agora-protocol-spec-unified.md` lines 1066–1831 (§5–7). Section numbers are the source's and will be renumbered.

## 5. Message Ordering

### 5.1 Ordering Model

Agora uses **best-effort causal ordering**. Gossipsub does not guarantee total message order and does not need to. The requirement is that messages arrive in approximately the right order on average, with clients able to reconstruct causal order locally.

Each message envelope carries a `seq` (monotonically increasing integer per sender per channel) and an optional `causalRefs` array of message CIDs that the sender had observed before composing the message. This gives clients enough information to:

- Detect gaps (missing `seq` values from a given sender)
- Buffer out-of-order arrivals and flush the buffer when gaps close
- Detect and display causal relationships for reply threading and reaction targets

Clients SHOULD buffer messages for up to 500ms waiting for a gap to close before rendering out-of-order. After 500ms, the client should display what is available and backfill visually when the missing message eventually arrives.

**MLS Commit ordering.** MLS Commits (which advance the group epoch) require stricter ordering than application messages. Clients MUST buffer application messages from a new epoch until the Commit that opened that epoch has been received and processed. Relays MAY provide **sequence attestations** — signed sequence numbers over a channel's message stream — as an optional ordering anchor for clients that require it.

**Space state ordering.** Space state mutations are ordered by a `seq` field on the `SpaceState` document and a Lamport timestamp. Concurrent non-conflicting mutations (e.g., two admins each independently adding a different channel) are merged by taking the union. Conflicting mutations (e.g., two admins simultaneously changing the same user's role) are resolved last-writer-wins using the `seq` value. In a true simultaneous tie, the mutation signed by the higher-authority key wins (owner beats admin).


---

## 6. Messaging

### 6.1 MLS Group Structure

Each channel's encryption model is determined by its **mode** (§3.2). `interactive` and `community` channels each have their own MLS group; `broadcast` channels use a signature-only model with no MLS group. In all cases, space membership does not imply channel membership — each channel manages its own state independently.

This section covers `interactive` and `community` channels. `broadcast` channels are specified in §6.1.4.

**`interactive` mode** (§3.2): full MLS group, all channel members hold leaves. Maximum 200 members. Standard §6.1 behavior applies without modification.

**`community` mode** (§3.2): MLS group limited to active speakers. Space members outside the speaker group can observe the gossipsub topic but cannot decrypt messages until admitted. See §6.1.2.

Each channel manages its own MLS epoch independently. This enables per-channel access control (e.g., private channels within a public space) without any additional mechanism; it is a direct consequence of the MLS design.

MLS operations follow RFC 9420 exactly:

- **`KeyPackage`** — uploaded to the Relay KeyPackage Store (§6.1.1); rotated on each new device session and after each use.
- **`Welcome`** — sent to new members via `v1/agora/mls/<groupID>` or direct encrypted delivery.
- **`Commit`** — a state-advancing operation (Add, Remove, Update); gossiped to all current group members.
- **`Proposal`** — a pre-commit operation that may be included in a subsequent Commit by any authorized member.

The **Delivery Service** role (as defined in RFC 9420 §4) is performed by the gossipsub mesh in combination with the Relay KeyPackage Store. The **Authentication Service** role is performed by DID verification — MLS leaf node credentials are bound to DID verification keys, so verifying an MLS credential means verifying a DID.

**Reference implementations for MLS (RFC 9420):**
- Rust: [`openmls`](https://github.com/openmls/openmls) — the most complete open-source implementation
- C/C++: [`mlspp`](https://github.com/cisco/mlspp) (Cisco)

### 6.1.1 KeyPackage Store

IPFS alone is insufficient for KeyPackage distribution. IPFS provides no delivery guarantees, no availability SLA, and — critically — no mechanism for a sender to atomically fetch-and-consume a KeyPackage to prevent reuse. Two concurrent senders fetching the same KeyPackage from IPFS would both construct valid-looking Welcomes, but the second would fail MLS validation at the recipient because the leaf credential is bound to a single use. Relays MUST therefore implement a **KeyPackage Store** — an authenticated key-value endpoint that makes consumption atomic and provides the availability properties IPFS cannot.

The KeyPackage availability problem has three layers that must be addressed together: the relay's baseline behavior (what it does by default), the operator's contractual commitment (what it promises in a service agreement), and the client's self-healing supply chain (what happens when the user is offline). This section specifies all three.

#### Relay KeyPackage API

All endpoints are authenticated using the client-relay session established in §8.6.

```
PUT  /v1/agora/kp/{did}
     Upload one or more KeyPackages for the authenticated DID.
     Body: CBOR array of RFC 9420 KeyPackage TLS-serialized objects.
     Response: 200 { "stored": N }

GET  /v1/agora/kp/{did}
     Fetch and atomically consume one KeyPackage for the target DID.
     The relay removes the returned KeyPackage from the store in the same operation.
     Response: 200 { "keyPackage": "base64url...", "remaining": N }
              404 if no KeyPackages are available for that DID

GET  /v1/agora/kp/{did}/count
     Return the number of available (unconsumed) KeyPackages without consuming any.
     Response: 200 { "count": N }

DELETE /v1/agora/kp/{did}/{keyPackageRef}
     Revoke a specific KeyPackage by its ref (the SHA-256 hash of the TLS-serialized bytes).
     Only the owning DID may revoke its own KeyPackages.
```

The `GET /count` endpoint allows a client to monitor its own KeyPackage supply and replenish proactively. Clients SHOULD maintain at least 20 pre-uploaded KeyPackages per device at all times. When `count` falls below 5, the client MUST upload a fresh batch immediately.

#### Relay Default Behavior (Baseline, No SLA)

In the absence of a `RelayServiceAgreement` with a `keyPackageSLA` clause (§12.2), a relay operates in **best-effort mode**: it stores and serves KeyPackages on a best-effort basis with no durability, availability, or minimum-count guarantees beyond the session in which they were uploaded.

Best-effort mode is appropriate for:
- Private organizational deployments where the relay is operator-controlled and users are online frequently.
- Development and testing.
- Small spaces where channel membership changes are infrequent.

Best-effort mode is **not appropriate** for large public spaces or any deployment where a user may be offline for days or weeks and needs to be addable to new channels on their return.

Even in best-effort mode, a relay MUST NOT:
- Return a previously consumed KeyPackage on a subsequent `GET` (consumption is always atomic and permanent).
- Silently drop stored KeyPackages before the session ends without notifying the owning DID.

#### Relay Service Agreement SLA (Contractual Guarantee)

A `RelayServiceAgreement` (§12.2) MAY include a `keyPackageSLA` clause that extends the relay's obligations beyond best-effort:

```json
"keyPackageSLA": {
  "minimumCount": 20,
  "alertThreshold": 5,
  "alertMechanism": "push",
  "guaranteedRetentionDays": 90,
  "replenishFromIPFS": true
}
```

**`minimumCount`** — the relay commits to maintaining at least this many live, unconsumed KeyPackages per DID it serves under this agreement. This is not a hard real-time guarantee but an obligation to alert the client promptly when supply drops and to attempt IPFS-based replenishment before returning 404.

**`alertThreshold`** — when the stored count for a DID falls at or below this value, the relay MUST notify the owning DID. The notification mechanism is declared in `alertMechanism`:
- `"push"` — the relay sends a push proxy wake-up (§8.7) with `urgency: "high"`.
- `"gossip"` — the relay publishes a `KeyPackageLowAlert` message to `v1/agora/discovery`.
- `"both"` — both mechanisms are attempted.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "KeyPackageLowAlert",
  "targetDID": "did:key:z6Mk...",
  "relayDID": "did:key:z6MkRelay...",
  "currentCount": 3,
  "alertThreshold": 5,
  "ts": "2026-03-12T12:00:00Z",
  "sig": "base64url..."
}
```

`KeyPackageLowAlert` is gossiped only to `v1/agora/discovery`, not to any channel topic — it contains no channel or space information.

**`guaranteedRetentionDays`** — the relay will retain uploaded KeyPackages (without consuming them) for at least this many days from the upload timestamp. After this period, unexpired KeyPackages are still valid but the relay MAY evict them under storage pressure, and MUST alert the owning DID before doing so.

**`replenishFromIPFS`** — if `true`, the relay will attempt to fetch fresh KeyPackages from the owning DID's declared IPFS supply endpoint before returning 404 on a fetch or before triggering an alert. This is the relay self-healing from IPFS without requiring the user to be online.

Violation of a `keyPackageSLA` clause constitutes a breach of the service agreement. Enforcement is by relay selection — space owners and users choose relays that honor their declared terms.

#### IPFS as Durable Supply (Client-Controlled)

The relay store handles atomic consumption. IPFS handles durable supply. These roles are deliberately separate: IPFS is a write-many supply source, not a consumption endpoint. The same KeyPackage must never be consumed from two places.

A client MAY publish a batch of pre-generated KeyPackages to IPFS and register the CID in their DID document's `service` endpoints:

```json
{
  "service": [{
    "id": "did:key:z6Mk...#keypackage-supply",
    "type": "AgoraKeyPackageSupply",
    "serviceEndpoint": "ipfs://bafyrei.../keypackages.cbor",
    "uploadedAt": "2026-03-12T00:00:00Z",
    "count": 50
  }]
}
```

`serviceEndpoint` is an IPFS CID URL pointing to a CBOR-encoded array of RFC 9420 KeyPackage TLS-serialized objects — the same wire format accepted by `PUT /v1/agora/kp/{did}`. The `count` field is informational; the actual count is authoritative at the CID.

This CID is immutable — publishing new KeyPackages to IPFS produces a new CID. Clients rotate the `serviceEndpoint` in their DID document by publishing a new KeyPackage batch to IPFS and updating the service entry with the new CID and `uploadedAt`. The old CID remains valid and accessible but is superseded.

**Relay self-replenishment flow.** When a relay with `replenishFromIPFS: true` in its service agreement is about to return 404 on `GET /kp/{did}` (or has dropped below `alertThreshold`), it:

1. Resolves the target DID document and checks for an `AgoraKeyPackageSupply` service entry.
2. If found, fetches the CBOR KeyPackage array from IPFS via its configured gateway.
3. Imports the batch into the local relay store via the same path as a client `PUT` — each KeyPackage is stored individually, deduplication checked by ref hash.
4. Returns to the original `GET /kp/{did}` request now that supply is replenished, consuming one atomically as normal.
5. Publishes a `KeyPackageSupplyImported` gossip message to `v1/agora/discovery` so that other relays serving the same DID know the supply has been refreshed:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "KeyPackageSupplyImported",
  "targetDID": "did:key:z6Mk...",
  "relayDID": "did:key:z6MkRelay...",
  "importedCount": 50,
  "sourceCID": "bafyrei...",
  "ts": "2026-03-12T12:00:00Z",
  "sig": "base64url..."
}
```

The relay MUST verify the imported KeyPackages before adding them to the store. Corrupted or expired packages from IPFS are silently dropped; only valid packages are stored.

**Client workflow.** To take advantage of IPFS supply, the client:

1. At account setup or after a key rotation event, generates a large batch of KeyPackages (50–200 is reasonable).
2. Uploads the batch to IPFS and pins it (via their own IPFS node, a pinning service, or a relay with IPFS pinning enabled).
3. Updates their DID document's `serviceEndpoint` for `AgoraKeyPackageSupply` to the new CID.
4. Uploads a subset (20–50) to their connected relays' stores via `PUT /v1/agora/kp/{did}` for fast-path access.

The IPFS batch is a **reserve tank** — the relay draws from it when the fast-path store runs low, without requiring the client to be online.

**Important:** a relay fetching from the IPFS supply CID and consuming packages from it into its local store is the only authorized consumption path for IPFS packages. Senders MUST NOT fetch directly from the IPFS supply CID and attempt to construct Welcomes from it — the atomic consumption guarantee applies only to the relay's `GET /v1/agora/kp/{did}` endpoint. Any Welcome constructed using a KeyPackage sourced directly from IPFS (bypassing the relay store) MUST be rejected by recipients as potentially reused.

#### KeyPackage Replication Across Relays

A client connected to multiple Relays SHOULD upload its KeyPackages to all of them. When a sender needs to fetch a KeyPackage to issue a Welcome, it contacts the target user's preferred Relay (declared in their DID document's `service` endpoints). If that Relay has no KeyPackages for the target, it SHOULD attempt to fetch one from other known Relays serving the same space before returning 404.

Inter-relay KeyPackage forwarding uses a simple pull model:

```
GET /v1/agora/kp/{did}?forward=true
```

The `forward=true` parameter instructs the Relay to attempt peer-relay fetching before returning 404. If `replenishFromIPFS` is also enabled, the relay attempts IPFS replenishment after peer-relay fetching fails, before finally returning 404. Relays that support forwarding declare `"keypackage-forwarding-v1"` in their capabilities.

#### KeyPackage Exhaustion

If all KeyPackages for a target DID have been consumed and no fresh ones are available from peer relays or IPFS supply, the sender MUST NOT reuse a previously consumed KeyPackage. Instead:

1. The sender queues the Welcome message locally.
2. The sender publishes a `KeyPackageRequest` to `v1/agora/discovery`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "KeyPackageRequest",
  "targetDID": "did:key:z6Mk...",
  "requestedBy": "did:key:z6MkSender...",
  "ts": "2026-03-12T12:00:00Z"
}
```

3. When the target comes online, their client sees the `KeyPackageRequest`, generates fresh KeyPackages, uploads them to both IPFS and the relay store, and the waiting sender completes the Welcome flow.

`KeyPackageRequest` messages are ephemeral (not stored in IPLD history) and MUST NOT identify which channel or space triggered the request.

#### KeyPackage Validation

Recipients of a Welcome MUST validate the KeyPackage used to construct it:

- The signature verifies against the sender's DID authentication key.
- `KeyPackage.leaf_node.credential` contains a valid DID matching the sender.
- The KeyPackage has not expired (`leaf_node.lifetime.not_after`).
- The ciphersuite matches the group's declared ciphersuite.

A Welcome constructed with an invalid or expired KeyPackage MUST be rejected. A Welcome constructed using a KeyPackage sourced directly from an IPFS supply CID (rather than consumed via the relay store API) MUST also be rejected.

### 6.1.2 Community Channel Mode

A `community` channel has a bounded MLS group called the **speaker group**. Only members of the speaker group can post or decrypt messages. Space members outside the speaker group can subscribe to the channel's gossipsub topic but will receive ciphertext they cannot decrypt until they are admitted.

**Speaker group bounds.** The `speakerCap` field in the channel state (default 200, maximum 500) is the hard upper limit on simultaneous MLS group members. A channel admin MUST NOT issue an Add commit that would push membership above `speakerCap`.

**Idle eviction.** A speaker who has not sent any `ApplicationMessage` in the channel within `idleEvictDays` days (default 7) is eligible for eviction. The channel's designated **SpeakerBot** (a DID listed in the channel state as `speakerBot`) issues periodic Remove commits for idle speakers. If no `speakerBot` is configured, channel admins perform evictions manually. Eviction is not punitive — evicted members are eligible for immediate re-admission when they next request to speak.

**SpeakRequest.** A space member who is not currently in the speaker group and wants to post sends a `SpeakRequest` gossip message to the channel topic:

```json
{
  "@type": "SpeakRequest",
  "channelCid": "bafyrei...",
  "requesterDid": "did:key:z6Mk...",
  "ts": "2026-04-22T09:00:00Z",
  "sig": "base64url..."
}
```

`sig` is the requester's Ed25519 signature over the canonical CBOR of the message body (excluding `sig`). The SpeakerBot or a channel admin responds by issuing a standard MLS Add commit using a KeyPackage from the requester's store. If the speaker group is at capacity, the SpeakerBot SHOULD first evict the longest-idle current speaker before adding the requester.

**Admission latency.** Admission requires one round of MLS Add + Welcome delivery. Clients in `community` channels SHOULD display a "waiting to join" indicator if the user tries to post before their Welcome has been processed.

**History access.** A member who was evicted and later re-admitted receives a new Welcome for the new MLS epoch. They can decrypt messages from epochs in which they held a leaf node; they cannot decrypt messages sent during periods when they were not in the group. This is the correct behavior — they were not a group member during those periods. Clients SHOULD display a clear indicator when history is unavailable for a given time range.

**Compliance logging.** Compliance loggers (§17) in `community` channels are passive members (§6.1.3) and MUST NOT be subject to idle eviction. The SpeakerBot MUST check for a passive member leaf before evicting any member.

### 6.1.3 Passive Members

A **passive member** is an MLS group member that holds a leaf credential and participates in epoch ratchets — receiving all application messages and group state updates — but MUST NOT issue Commits or Proposals. Passive members are indistinguishable from standard members at the MLS wire protocol layer; the constraint is behavioral, not cryptographic.

**Use cases in Agora.** Compliance loggers (§17) and VTC recorders (§10.12) are passive members. Both hold leaf credentials, receive all application messages in their admitted groups, and never modify group state.

**KeyPackages.** Passive members require KeyPackages to receive Welcome messages. Because passive members never initiate group operations, they SHOULD publish last-resort KeyPackages (`draft-ietf-mls-extensions-09`, §last-resort-keypackage) — KeyPackages marked for reuse when the single-use supply is exhausted — rather than maintaining a large single-use supply. Relays MUST serve a passive member's last-resort KeyPackage when no single-use packages remain.

**Idle eviction.** Passive members MUST NOT be subject to idle eviction (§6.1.2). A passive member generates no traffic by design; evicting one on that basis would silently break the compliance capture chain.

**Future standard alignment.** This concept anticipates `draft-ietf-mls-partial-00` ("Partial MLS"), which defines an MLS extension allowing receive-only participants to carry only membership proofs rather than the full ratchet tree, reducing overhead for large groups. That draft expired without a successor. When a partial client standard is published, Agora implementations SHOULD upgrade passive member implementations to native partial client support; the behavioral contract (no Commits, no Proposals, full message receipt) is identical.

### 6.1.4 Broadcast Channel Mode

A `broadcast` channel carries no MLS group. Messages are **signed but not encrypted** — they are readable by any space member who knows the channel token. The security property provided is authenticity (was this posted by an authorized poster?) not confidentiality.

**Authorized posters.** The set of authorized posters for a broadcast channel is determined by space role: any space member holding a role listed in the channel state's `broadcasterRoles` array may post. Typically this is a dedicated `broadcaster` role held by admins or a bot.

**Message structure.** Broadcast messages use the standard outer routing envelope (§6.2) but with no inner MLS encryption. The `innerPayload` field carries a plaintext-signed JSON-LD body:

```json
{
  "@type": "BroadcastMessage",
  "channelCid": "bafyrei...",
  "body": {
    "@type": "TextBody",
    "content": "v2.1.0 released — see release notes for details.",
    "mimeType": "text/markdown;variant=commonmark"
  },
  "senderDid": "did:key:z6Mk...",
  "ts": "2026-04-22T09:00:00Z",
  "sig": "base64url..."
}
```

`sig` is the sender's Ed25519 signature over the canonical CBOR of the message body (excluding `sig`). Recipients MUST verify `sig` against the sender's DID document before displaying the message. Recipients MUST also verify that `senderDid` holds a space role listed in `broadcasterRoles`.

**Relay handling.** The Relay stores broadcast messages as signed blobs, identical to any other channel message. Because broadcast messages are not encrypted, the Relay CAN read their content — this is an intentional and declared property of broadcast channels. Clients MUST display a visible indicator (e.g., a megaphone icon) on broadcast channels to make clear to users that messages in this channel are not confidential.

**No MLS group means no KeyPackage consumption** for broadcast channels. Senders do not need to consume a recipient's KeyPackage to post. There are no Welcome or Commit messages for broadcast channels.

**Compliance logging.** Broadcast channel messages are already plaintext; no special compliance logger admission is required. The Relay stores them as durable signed records. For FINRA/MiFID purposes, broadcast messages in a space with compliance logging enabled are automatically captured to the compliance archive.

### 6.2 Message Format

All messages use a two-layer structure: an outer **routing envelope** visible to Relays, and an inner **sealed envelope** whose sender identity is hidden from Relays. The inner payload is MLS-encrypted.

#### Outer Routing Envelope

The outer envelope contains only what Relays strictly need for delivery routing. It does not contain the sender's DID.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RoutingEnvelope",
  "id": "urn:agora:msg:bafyrei...",
  "channelToken": "base64url...",
  "epoch": 17,
  "seq": 1042,
  "ts": "2026-03-12T12:00:00.000Z",
  "expiryHint": "2026-03-19T12:00:00.000Z",
  "sealedEnvelope": "base64url..."
}
```

`channelToken` is a one-way derivation from the channel CID and the current MLS epoch secret: `HKDF(epochSecret, "channel-token" || channelCID)`. It rotates with every epoch. Relays use it for topic routing without learning the actual channel identifier or any member identity.

`id` is the CID of the canonical outer envelope, used for deduplication and history indexing. `ts` is present for gossipsub ordering and relay-side TTL enforcement only — it is not authenticated at the outer layer and MUST NOT be trusted for application-level ordering (use the inner `seq` for that). `expiryHint` is set by the sender to match the inner payload `expiry` value; Relays use it as a cache TTL hint (§6.4).

#### Sealed Envelope (Sender-Sealed, Relay-Opaque)

`sealedEnvelope` bundles the sender's DID, a per-message ephemeral key, and the MLS ciphertext, all encrypted together to the channel's current MLS group key. No Relay or non-member can open it.

Plaintext of `sealedEnvelope` before encryption:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SealedEnvelope",
  "sender": "did:key:z6Mk...",
  "senderEphemeralKey": "base64url...",
  "mlsCiphertext": "base64url...",
  "sig": "base64url..."
}
```

`sig` covers `sender + senderEphemeralKey + mlsCiphertext`, signed by the sender's authentication key. Recipients verify the signature after decrypting the sealed envelope. `senderEphemeralKey` is a fresh X25519 key generated per-message; it binds the sealed envelope to this specific send without exposing long-term key material to the outer layer.

This design is derived from Signal's Sealed Sender construction. A Relay processing this message learns: a `channelToken` (epoch-rotating, non-reversible without the epoch secret), a sequence number, a timestamp, and an opaque encrypted blob. It learns nothing about who sent the message.

#### Inner Payload (After MLS Decryption)

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ChatMessage",
  "body": {
    "@type": "TextBody",
    "text": "the fips conversion is green",
    "format": "markdown"
  },
  "expiry": "2026-03-19T12:00:00.000Z",
  "attachments": [],
  "replyTo": null,
  "mentions": [],
  "causalRefs": []
}
```

### 6.3 Message Types

All inner payload types are defined in the Agora JSON-LD context namespace (`https://agora.protocol/ns/v1`):

| `@type` | Description |
|---|---|
| `TextBody` | Formatted text; `format` field declares the content type (see §6.7) |
| `MediaBody` | Reference to IPFS-hosted media (CID + MIME type + size) |
| `EmbedBody` | URL unfurl card (title, description, image CID) |
| `ReactionEvent` | Emoji reaction add/remove targeting a message CID (see §6.8) |
| `EditEvent` | Replacement body for a prior message CID |
| `DeleteEvent` | Tombstone for a prior message CID |
| `PinEvent` | Pin a CID to the channel's persistent pin list (§6.6) |
| `UnpinEvent` | Remove a CID from the channel's pin list (§6.6) |
| `SystemEvent` | Protocol-level event (member join, role change, gateway added, etc.) |
| `VoiceSignal` | WebRTC SDP offer/answer/ICE candidate, targeted to a specific DID |
| `ParticipantState` | Ephemeral VTC room presence (joined/left, muted, video on/off, screen share) |
| `RecordingGrant` | Admin authorization for an SFU DID to decrypt media for recording |
| `RecordingRevoke` | Revocation of a prior `RecordingGrant` |
| `TypingEvent` | Ephemeral typing indicator; not stored |
| `PresenceEvent` | Ephemeral online/idle/dnd status; not stored |

Ephemeral events (`TypingEvent`, `PresenceEvent`, `ParticipantState`) use the MLS `PublicMessage` application data subtype and are excluded from history storage.

### 6.4 Message Expiry

Message lifetime is a **sender-side cryptographic commitment**, not a server-side promise or a UI affordance. The sender encodes an `expiry` timestamp in the inner payload, inside the MLS ciphertext and therefore invisible to Relays. Recipients' clients are bound by protocol to honor it — not because a Relay requested deletion, but because the expiry is part of the authenticated message content signed by the sender.

Expiry semantics:

- `expiry` is an ISO 8601 timestamp in the inner payload. Absence means no expiry (persistent by default).
- On receipt, the client schedules local deletion of the decrypted message at the expiry time.
- On expiry, clients SHOULD also submit a signed `DeleteEvent` to the channel, so that the IPLD history DAG records a tombstone and Relays drop the cached envelope.
- Relays that cache message envelopes MUST respect the `expiryHint` field in the outer `RoutingEnvelope` as a cache TTL. This field is unauthenticated at the outer layer — Relays use it as a hint only, not as authoritative content.
- The authoritative expiry is always the inner payload value, verified by recipients after MLS decryption.

### 6.5 Message History

Message history is stored as an IPLD linked list. Each message envelope CID is appended to the channel's history DAG, and the channel state document tracks the latest history CID.

Clients fetch history by walking the IPLD DAG backwards from the latest CID. Relays SHOULD pin recent history within their configured retention window (default 30 days). Long-term archival beyond the retention window is the responsibility of space operators or interested members.

IPFS provides content-addressed deduplication automatically — the same message (same CID) stored at multiple Relays is inherently deduplicated.

**Reference implementations for IPFS/IPLD:**
- Go: [`go-ipfs`](https://github.com/ipfs/go-ipfs), [`go-ipld-prime`](https://github.com/ipld/go-ipld-prime)
- JS: [`helia`](https://github.com/ipfs/helia), [`@ipld/dag-cbor`](https://github.com/ipld/js-dag-cbor)
- Rust: [`rust-ipfs`](https://github.com/rs-ipfs/rust-ipfs), [`libipld`](https://github.com/ipld/libipld)

### 6.6 Pinned Content

Channels support a **pin list** — a set of CID references in the channel's IPLD state that mark specific content as persistent and surfaced. Pinning is a preservation signal: pinned CIDs are exempt from relay retention expiry and are surfaced by clients as a dedicated "pinned messages" view.

#### What Can Be Pinned

Any content that already has a CID may be pinned:

- A message envelope CID (a specific chat message, a file share, a thread root)
- A media attachment CID (an image, document, or other file already stored in IPFS)
- An archived external URL — clients MUST archive external URLs to IPFS and pin the resulting CID rather than the URL itself. URLs rot; CIDs do not. The `label` field carries the human-readable original URL or description.

Pinning does not copy data. It records a reference that tells relays and clients "this CID must be retained and displayed prominently."

#### Pin List in Channel IPLD State

The channel's IPLD state document includes a `pins` array. Each entry is a signed pin record:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ChannelState",
  "channelCID": "bafyrei...",
  "latestHistoryCID": "bafyrei...",
  "pins": [
    {
      "cid": "bafyrei...",
      "pinnedBy": "did:key:z6Mk...",
      "pinnedAt": "2026-03-12T12:00:00Z",
      "label": "onboarding guide",
      "sig": "base64url..."
    },
    {
      "cid": "bafyrei...",
      "pinnedBy": "did:key:z6MkAdmin...",
      "pinnedAt": "2026-03-12T10:00:00Z",
      "label": "https://example.com/rules (archived)",
      "sig": "base64url..."
    }
  ],
  "pinLimit": 50
}
```

`sig` is the pinner's Ed25519 signature over the canonical CBOR serialization of the pin entry fields (excluding `sig` itself). Pins are attributable and tamper-evident — adding or removing a pin without a valid signature MUST be rejected.

`pinLimit` is the maximum number of simultaneous pins for the channel. Default is 50. Space Admins may set a different limit via a signed `ChannelStateMutation`. Relays MUST reject `PinEvent` messages that would cause the pin count to exceed `pinLimit`.

#### Authorization

- **Any current MLS group member** MAY add a pin (`PinEvent`).
- **Space/Channel Admins and the original pinner** MAY remove a pin (`UnpinEvent`). Other members MAY NOT remove pins they did not add.
- Pin operations on channels where the pinner is not a current MLS group member MUST be rejected by relays.

#### PinEvent and UnpinEvent

Pin and unpin operations are MLS application messages with the following inner payload types:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "PinEvent",
  "cid": "bafyrei...",
  "label": "onboarding guide",
  "pinnedBy": "did:key:z6Mk...",
  "ts": "2026-03-12T12:00:00Z",
  "sig": "base64url..."
}
```

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "UnpinEvent",
  "cid": "bafyrei...",
  "unpinnedBy": "did:key:z6MkAdmin...",
  "ts": "2026-03-12T12:30:00Z",
  "sig": "base64url..."
}
```

Both are stored in the channel's IPLD history DAG — the audit trail records who pinned and unpinned what and when, non-repudiably.

#### Retention Exemption

Pinned CIDs are **permanently exempt from relay retention expiry**. A relay serving a channel MUST NOT evict any CID that appears in the channel's current `pins` array, regardless of:

- The configured retention window
- The `expiryHint` on the original envelope
- Storage pressure

The relay MUST continue to serve pinned CIDs via IPFS until they are explicitly unpinned via a valid `UnpinEvent`. If a relay is running low on storage, it MUST evict unpinned content before considering eviction of pinned content, and MUST alert the space operator before evicting anything from the pin list.

The retention exemption applies only to the pinned CID itself — not to the full IPLD history DAG. Relays are required to retain the pinned CID and its directly referenced content (e.g., a media attachment CID referenced by a pinned message envelope).

#### Message Expiry Interaction

A pinned message whose inner payload contains an `expiry` timestamp presents a conflict: the sender requested deletion, but a subsequent pinner requested retention. The resolution: **explicit unpinning is required before expiry takes effect on a pinned CID**. A relay MUST NOT evict a pinned CID on expiry. The channel admin responsible for the pin SHOULD unpin expired content; if they do not, the content persists until explicitly unpinned. Clients SHOULD warn admins when a pinned message's inner payload expiry has passed without an unpin action.

This is a deliberate policy choice: pinning is an admin override of sender expiry. Users who post content they intend to be ephemeral should be aware that an admin may pin it. Channels with strict expiry requirements SHOULD configure a `noPin` policy (a boolean flag in channel state, default false) that disables the pin feature entirely for that channel.

### 6.7 TextBody Content Format

#### 6.7.1 Baseline Format: CommonMark

The `body` field of a `ChatMessage` inner payload carries a `TextBody` object. The `format` field of `TextBody` declares the content type of the `text` field. The baseline and default format is **CommonMark** ([spec.commonmark.org](https://spec.commonmark.org/)), specifically the most recent stable release at the time of implementation (currently 0.31.2).

```json
{
  "@type": "TextBody",
  "text": "**hello** from `agora`",
  "format": "text/markdown;variant=commonmark"
}
```

Clients MUST support CommonMark rendering. Clients that cannot render CommonMark MUST display the `text` field verbatim.

**Permitted CommonMark features:** All constructs defined in the CommonMark spec are in-scope. No extensions are included in the baseline. The following are explicitly **not** in the CommonMark baseline and MUST NOT be rendered unless negotiated as an extension (§6.7.2):

- Tables (GFM extension)
- Strikethrough (GFM extension)
- Task list items (GFM extension)
- Footnotes
- Math / LaTeX blocks
- Raw HTML blocks or inline HTML

Clients MUST strip or escape any raw HTML in a CommonMark `text` field rather than rendering it. A `text` field containing raw HTML is not a conformance violation at the protocol layer, but clients MUST treat it as literal text.

#### 6.7.2 Extension Formats

Additional `format` values MAY be defined as named extensions. An extension format is identified by a MIME-type-style string in the `format` field. Clients that do not recognize a `format` value MUST fall back to rendering `text` verbatim.

Reserved extension format strings:

| `format` value | Meaning |
|---|---|
| `text/markdown;variant=commonmark` | CommonMark baseline (default) |
| `text/markdown;variant=gfm` | GitHub Flavored Markdown (CommonMark + tables, strikethrough, task lists) |
| `text/plain` | Literal plaintext; no markup rendering |

The `format` field is extensible: implementations MAY define additional values using reverse-domain namespacing (e.g., `text/markdown;variant=com.example.custom`). Unknown `format` values MUST be treated as `text/plain` by conformant clients.

If `format` is absent, clients MUST treat the `text` field as `text/markdown;variant=commonmark`.

#### 6.7.3 Compliance Logger Behavior

Compliance loggers (§17) store the raw `text` field as-is in `plaintextPayload`. The `format` field is preserved alongside it. Loggers are not required to render or interpret the markup — the stored `text` is the authoritative record.

#### 6.7.4 Format Capability Advertisement

A sender composing a message has no way to know whether a recipient can render a non-baseline `format` value unless capabilities are advertised. Agora provides two complementary advertisement mechanisms: a persistent declaration in the DID document and an ephemeral declaration in the client handshake.

**DID document declaration (persistent)**

A client MAY publish its supported text formats as a service entry in its DID document:

```json
{
  "id": "did:key:z6Mk...#text-formats",
  "type": "AgoraTextFormatCapabilities",
  "serviceEndpoint": "inline",
  "supportedTextFormats": [
    "text/markdown;variant=commonmark",
    "text/markdown;variant=gfm",
    "text/plain"
  ]
}
```

**ClientHello declaration (ephemeral)**

The `supportedTextFormats` field in `ClientHello` (§8.6) declares the current connected device's rendering capabilities for the duration of the session. On receiving a `ClientHello` with `supportedTextFormats`, the Relay SHOULD cache this information keyed by DID + deviceKey for the session duration and make it available to other authenticated clients via the capability query endpoint:

```
GET /v1/agora/caps/{did}
```

Response:

```json
{
  "@type": "ClientCapabilities",
  "did": "did:key:z6Mk...",
  "online": true,
  "supportedTextFormats": [
    "text/markdown;variant=commonmark",
    "text/markdown;variant=gfm",
    "text/plain"
  ],
  "source": "session",
  "cachedAt": "2026-03-12T12:00:00Z"
}
```

`source` is `"session"` if the data comes from a live `ClientHello`, or `"did-document"` if the Relay fell back to the DID document service entry because no live session is present. If neither source is available, the Relay returns a 404 and the sender SHOULD assume baseline CommonMark only.

Relays MUST NOT cache `ClientHello` capability data beyond the session. On disconnect, the cached entry is discarded.

**Sender behavior**

When composing a message with a non-baseline `format`, a conformant client SHOULD:

1. Query `/v1/agora/caps/{did}` for each recipient (in DM groups) or check the DID document (in space channels, where per-member querying at compose time is impractical).
2. If all reachable recipients declare support for the chosen format, send with that format.
3. If any recipient's capabilities are unknown or do not include the chosen format, either fall back to `text/markdown;variant=commonmark` or send with the preferred format and accept that some recipients will display raw markup.

In space channels with many members, per-member capability queries at compose time are not required. Clients MAY display a warning when a non-baseline format is selected without blocking the send.

**Multi-device considerations**

A user's devices may have different rendering capabilities. The DID document entry SHOULD reflect the union of all active devices' capabilities — declaring a format only if all devices the user actively uses can render it. The `ClientHello` entry reflects the specific device currently connected and MAY differ from the DID document entry.

### 6.8 Emoji and Reactions

#### 6.8.1 Emoji in Message Text

Unicode emoji are valid UTF-8 content in any `TextBody` `text` field. No special handling is required.

**Shortcodes** (`:thumbsup:`, `:wolfssl_logo:`) are a client-side rendering convenience, not a wire format. Shortcodes MUST NOT appear on the wire in `TextBody.text` unless the sender intentionally wants the literal text to appear. Clients that support shortcode input MUST expand shortcodes to their Unicode codepoint(s) (for standard emoji) or to a custom emoji reference (for space emoji, see §6.8.4) before constructing the `TextBody`.

**ZWJ sequences and skin tone modifiers** are treated as atomic units. A `ReactionEvent` targeting a message with `"emoji": "👍🏽"` (thumbs up + medium skin tone) is a distinct reaction from `"emoji": "👍"` (thumbs up, no modifier). Clients SHOULD display them as separate reaction types.

#### 6.8.2 ReactionEvent Schema

A reaction is an MLS application message of type `ReactionEvent`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ReactionEvent",
  "targetCID": "bafyrei...",
  "emoji": "👍",
  "action": "add",
  "senderDID": "did:key:z6Mk...",
  "ts": "2026-03-12T12:00:00.000Z",
  "sig": "base64url..."
}
```

`targetCID` is the `envelopeID` CID of the message being reacted to. `emoji` is either a Unicode emoji string (one or more codepoints forming a single grapheme cluster, including ZWJ sequences and modifier sequences) or a custom emoji reference string of the form `:space:<shortcode>:` (see §6.8.4). `action` is `"add"` or `"remove"`. `sig` is the sender's Ed25519 signature over the canonical CBOR serialization of the other fields.

`targetCID` MUST refer to a message in the same MLS group. Reactions targeting messages in other groups or channels are invalid and MUST be rejected by clients.

#### 6.8.3 Reaction Semantics

**One reaction per emoji per sender per target.** A sender MAY NOT add the same `emoji` value to the same `targetCID` more than once. A second `"action": "add"` for the same `(senderDID, targetCID, emoji)` tuple is a no-op; clients MUST deduplicate and MUST NOT display it as a separate reaction.

**Reaction state is derived from the ordered event stream.** Clients reconstruct the current reaction set for a message by replaying all `ReactionEvent` messages targeting that CID in `seq` order. The canonical reaction state at any point is:

```
reactionSet[(targetCID, emoji, senderDID)] = last action seen for that tuple
```

**Aggregation.** Clients SHOULD aggregate reactions by `emoji` value, displaying a count and (on hover or tap) the list of sender display names. A reaction count of zero MUST NOT be displayed.

**Reactions on deleted messages.** If the `targetCID` has been tombstoned by a `DeleteEvent`, clients MUST NOT display reactions for it. Reactions in the event stream targeting a deleted message CID are silently ignored on render.

**Reactions and compliance logging.** `ReactionEvent` messages are logged by the compliance logger identically to `ChatMessage` messages — they are MLS application messages and the logger holds group membership.

#### 6.8.4 Custom Emoji

Spaces MAY define custom emoji — space-specific images referenced by shortcode. Custom emoji are IPFS-hosted and declared in the space state document.

**Space state declaration:**

```json
"customEmoji": [
  {
    "shortcode": "wolfssl_logo",
    "imageCID": "bafyrei...",
    "mimeType": "image/png",
    "width": 64,
    "height": 64,
    "addedBy": "did:key:z6MkAdmin...",
    "addedAt": "2026-03-12T00:00:00Z"
  }
]
```

`shortcode` MUST match `[a-z0-9_]{1,32}` — lowercase alphanumeric and underscores, 1–32 characters. Shortcodes MUST be unique within a space. `imageCID` is the IPFS CID of the image file. `mimeType` MUST be `image/png`, `image/gif`, or `image/webp`. Images SHOULD be square and SHOULD be 64×64 or 128×128 pixels.

**Wire format for custom emoji reactions:**

When a custom emoji is used in a `ReactionEvent`, the `emoji` field uses the reference string:

```json
"emoji": ":space:wolfssl_logo:"
```

Clients resolve `:space:<shortcode>:` by looking up `shortcode` in the current space's `customEmoji` array, fetching the image from IPFS at `imageCID`, and rendering it inline. Clients that cannot resolve the shortcode MUST display the literal reference string `:space:wolfssl_logo:` as a fallback.

**Custom emoji in message text:**

Custom emoji MAY appear inline in `TextBody.text` using the same `:space:<shortcode>:` reference syntax. Clients resolve and render them inline alongside the surrounding text.

**Custom emoji management:**

Adding or removing a custom emoji is a signed `SpaceState` mutation by a Space Admin or Owner. The `customEmoji` array in the space state document is the authoritative list. Removing a custom emoji from the array does not delete the IPFS content, but clients MUST stop rendering it after the next space state refresh.

Spaces SHOULD pin custom emoji image CIDs to prevent relay eviction.

---

## 7. Presence and Ephemeral State

### 7.1 Presence

Presence is gossiped on `v1/agora/channel/<channelToken>` as a `PresenceEvent`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "PresenceEvent",
  "sender": "did:key:z6Mk...",
  "channel": "agora://bafyrei.../general",
  "status": "online",
  "ts": "2026-03-12T12:00:00.000Z",
  "ttl": 30
}
```

`status` values: `online`, `idle`, `dnd`, `invisible`. `ttl` is the number of seconds this presence state is valid without a refresh. Clients treat absence of a refresh within the TTL window as offline. Clients MUST publish a fresh `PresenceEvent` before TTL expiry if they remain in the stated status.

### 7.2 Typing Indicators

`TypingEvent` is gossiped to the channel topic and is never written to persistent storage:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "TypingEvent",
  "sender": "did:key:z6Mk...",
  "channel": "agora://bafyrei.../general",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

A client that receives no `TypingEvent` from a sender for 5 seconds SHOULD clear their typing indicator for that sender.


---

