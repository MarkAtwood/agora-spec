# 5. Messaging

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1066–1831 (§5–7).

## 5.1 Message Ordering

*Binds: both.*

### 5.1.1 Ordering Model

Agora uses **best-effort causal ordering**. Gossipsub does not guarantee total message order and does not need to. The requirement is that messages arrive in approximately the right order on average, with clients able to reconstruct causal order locally.

Each message envelope carries a `seq` (monotonically increasing integer per sender per channel) and an optional `causalRefs` array of message CIDs that the sender had observed before composing the message. This gives clients enough information to:

- Detect gaps (missing `seq` values from a given sender)
- Buffer out-of-order arrivals and flush the buffer when gaps close
- Detect and display causal relationships for reply threading and reaction targets

Clients SHOULD buffer messages for up to 500ms waiting for a gap to close before rendering out-of-order. After 500ms, the client should display what is available and backfill visually when the missing message eventually arrives.

**MLS Commit ordering.** MLS Commits (which advance the group epoch) require stricter ordering than application messages. Clients MUST buffer application messages from a new epoch until the Commit that opened that epoch has been received and processed. Relays MAY provide **sequence attestations** (signed sequence numbers over a channel's message stream) as an optional ordering anchor for clients that require it.

**Space state ordering.** Space state mutations are ordered by a `seq` field on the `SpaceState` document. Concurrent non-conflicting mutations (e.g., two admins each independently adding a different channel) are merged by taking the union. Conflicting mutations (e.g., two admins simultaneously changing the same user's role) are resolved last-writer-wins using the `seq` value. In an exact tie, the mutation signed by the higher-authority key wins (owner beats admin).


---

## 5.2 Messaging

*Binds: both.*

### 5.2.1 MLS Group Structure

Each channel's encryption model is determined by its **mode** (§3.2). `interactive` and `community` channels each have their own MLS group; a `broadcast` channel has an MLS group of its authorized posters only (the publisher group) and carries content encrypted under a CO-distributed channel content key. In all cases, space membership does not imply channel membership; each channel manages its own state independently.

This section covers `interactive` and `community` channels. `broadcast` channels are specified in §5.2.1.4.

**`interactive` mode** (§3.2): full MLS group, all channel members hold leaves. Maximum 200 members. Standard §5.2.1 behavior applies without modification.

**`community` mode** (§3.2): MLS group limited to active speakers. Space members outside the speaker group cannot follow the channel's envelopes, because they do not hold the exporter-derived `channelToken`, until admitted. See §5.2.1.2.

Each channel manages its own MLS epoch independently. This enables per-channel access control (e.g., private channels within a public space) without any additional mechanism; it is a direct consequence of the MLS design.

**Ciphersuite.** All MLS groups in Agora MUST use `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519` (0x0001), matching Ed25519 DID identity keys. A group's declared ciphersuite is this value unless a future revision of this specification defines another.

MLS operations follow RFC 9420 exactly:

- **`KeyPackage`:** uploaded to the Relay KeyPackage Store (§5.2.1.1); single-use, and rotated on each new device session and after each use.
- **`Welcome`:** delivered by POST to the new member's `KeyPackageEndpoint` (§4.6); never on a gossip topic. A Welcome MUST include the `ratchet_tree` extension (RFC 9420 §12.4.3.3) carrying the full ratchet tree. A joiner MUST obtain the ratchet tree only from that extension and MUST NOT fetch it from a relay or any other IO; no IO stores or serves ratchet trees or other MLS group state. A joiner MUST reject a Welcome that lacks the `ratchet_tree` extension.
- **`Commit`:** a state-advancing operation (Add, Remove, Update); gossiped to all current group members.
- **`Proposal`:** a pre-commit operation that may be included in a subsequent Commit by any authorized member.

The **Delivery Service** role (as defined in RFC 9420 §10.3) is performed by the gossipsub mesh in combination with the Relay KeyPackage Store. The **Authentication Service** role is performed by DID verification: MLS leaf node credentials are bound to DID verification keys, so verifying an MLS credential means verifying a DID.

**Reference implementations for MLS (RFC 9420):**
- Rust: [`openmls`](https://github.com/openmls/openmls) (the most complete open-source implementation)
- C/C++: [`mlspp`](https://github.com/cisco/mlspp) (Cisco)

#### 5.2.1.1 KeyPackage Store

IPFS alone is insufficient for KeyPackage distribution. IPFS provides no delivery guarantees, no availability SLA, and no mechanism for a sender to atomically fetch-and-consume a KeyPackage to prevent reuse. Two concurrent senders fetching the same KeyPackage from IPFS would both construct valid-looking Welcomes, but the second would fail MLS validation at the recipient because the leaf credential is bound to a single use. Relays MUST therefore implement a **KeyPackage Store**: an authenticated key-value endpoint that makes consumption atomic and provides the availability properties IPFS cannot.

> **Open (agora-pozi.10):** a DID-keyed store learns who fetches whose KeyPackages, which reveals the social graph at group creation; store placement (CO-hosted via the DID document versus IO-hosted as a declared budget extension) is unresolved.

**Why single-use.** KeyPackages are consumed exactly once. RFC 9420 assumes each KeyPackage's init key is used for one Welcome; reuse lets two groups share HPKE init secrets and lets a replayed Welcome be accepted. A known failure mode is a store that hands out KeyPackages without consuming them, keeps them only while the owning device is connected (so they vanish on disconnect), and keys them to an unstable per-session device identifier, so that adding a user's other devices silently fails. Agora's store avoids this: consumption is atomic and permanent, supply persists independent of connection state, and supply is keyed to the owning DID.

The KeyPackage availability problem has three layers that must be addressed together: the relay's baseline behavior (what it does by default), the operator's contractual commitment (what it promises in a service agreement), and the client's self-healing supply chain (what happens when the user is offline). This section specifies all three.

##### Relay KeyPackage API

`PUT` and `DELETE` MUST be authorized by the owning DID: the store verifies that each uploaded KeyPackage's leaf credential and signature belong to `{did}`, and a `DELETE` carries the owner's signature over the `keyPackageRef`. `GET` and `GET /count` do not require the caller to authenticate a DID.

> **Open (agora-pozi.9):** how the store rate-limits anonymous `GET` callers to prevent KeyPackage exhaustion without authenticating them.

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

##### Relay Default Behavior (Baseline, No SLA)

In the absence of a `RelayServiceAgreement` with a `keyPackageSLA` clause (§10.5.1), a relay operates in **best-effort mode**: it stores and serves KeyPackages on a best-effort basis with no durability, availability, or minimum-count guarantees beyond the session in which they were uploaded.

Best-effort mode is appropriate for:
- Private organizational deployments where the relay is operator-controlled and users are online frequently.
- Development and testing.
- Small spaces where channel membership changes are infrequent.

Best-effort mode is **not appropriate** for large public spaces or any deployment where a user may be offline for days or weeks and needs to be addable to new channels on their return.

Even in best-effort mode, a relay MUST NOT:
- Return a previously consumed KeyPackage on a subsequent `GET` (consumption is always atomic and permanent).
- Silently drop stored KeyPackages before the session ends without notifying the owning DID.

##### Relay Service Agreement SLA (Contractual Guarantee)

A `RelayServiceAgreement` (§10.5.1) MAY include a `keyPackageSLA` clause that extends the relay's obligations beyond best-effort:

```json
"keyPackageSLA": {
  "minimumCount": 20,
  "alertThreshold": 5,
  "alertMechanism": "push",
  "guaranteedRetentionDays": 90,
  "replenishFromIPFS": true
}
```

**`minimumCount`:** the relay commits to maintaining at least this many live, unconsumed KeyPackages per DID it serves under this agreement. This is not a hard real-time guarantee but an obligation to alert the client promptly when supply drops and to attempt IPFS-based replenishment before returning 404.

**`alertThreshold`:** when the stored count for a DID falls at or below this value, the relay MUST notify the owning DID. The notification mechanism is declared in `alertMechanism`:
- `"push"`: the relay sends a push proxy wake-up (§11.7) with `urgency: "high"`.
- `"gossip"`: the relay publishes a `KeyPackageLowAlert` message to `v1/agora/discovery`.
- `"both"`: both mechanisms are attempted.

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

`KeyPackageLowAlert` is gossiped only to `v1/agora/discovery`, not to any channel topic; it contains no channel or space information.

> **Open (agora-pozi.10):** `KeyPackageLowAlert` and `KeyPackageSupplyImported` broadcast a user DID to the whole relay mesh; this is resolved with KeyPackage store placement.

**`guaranteedRetentionDays`:** the relay will retain uploaded KeyPackages (without consuming them) for at least this many days from the upload timestamp. After this period, unexpired KeyPackages are still valid but the relay MAY evict them under storage pressure, and MUST alert the owning DID before doing so.

**`replenishFromIPFS`:** if `true`, the relay will attempt to fetch fresh KeyPackages from the owning DID's declared IPFS supply endpoint before returning 404 on a fetch or before triggering an alert. This is the relay self-healing from IPFS without requiring the user to be online.

Violation of a `keyPackageSLA` clause constitutes a breach of the service agreement. Enforcement is by relay selection: space owners and users choose relays that honor their declared terms.

##### IPFS as Durable Supply (Client-Controlled)

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

`serviceEndpoint` is an IPFS CID URL pointing to a CBOR-encoded array of RFC 9420 KeyPackage TLS-serialized objects, the same wire format accepted by `PUT /v1/agora/kp/{did}`. The `count` field is informational; the actual count is authoritative at the CID.

This CID is immutable: publishing new KeyPackages to IPFS produces a new CID. Clients rotate the `serviceEndpoint` in their DID document by publishing a new KeyPackage batch to IPFS and updating the service entry with the new CID and `uploadedAt`. The old CID remains valid and accessible but is superseded.

**Relay self-replenishment flow.** When a relay with `replenishFromIPFS: true` in its service agreement is about to return 404 on `GET /kp/{did}` (or has dropped below `alertThreshold`), it:

1. Resolves the target DID document and checks for an `AgoraKeyPackageSupply` service entry.
2. If found, fetches the CBOR KeyPackage array from IPFS via its configured gateway.
3. Imports the batch into the local relay store via the same path as a client `PUT`; each KeyPackage is stored individually, deduplication checked by ref hash.
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

The IPFS batch is a **reserve tank**: the relay draws from it when the fast-path store runs low, without requiring the client to be online.

A relay fetching from the IPFS supply CID and consuming packages from it into its local store is the intended consumption path for IPFS packages. Committers SHOULD NOT fetch directly from the IPFS supply CID and construct Welcomes from it: the atomic consumption guarantee applies only to the relay's `GET /v1/agora/kp/{did}` endpoint, so a KeyPackage taken directly from IPFS may also be consumed by another committer, and one of the two Welcomes will fail. Recipients cannot tell where a committer obtained a KeyPackage, so this rule is not checked by recipients.

##### KeyPackage Replication Across Relays

A client connected to multiple Relays SHOULD upload its KeyPackages to all of them. When a sender needs to fetch a KeyPackage to issue a Welcome, it contacts the target user's preferred Relay (declared in their DID document's `service` endpoints). If that Relay has no KeyPackages for the target, it SHOULD attempt to fetch one from its peer Relays before returning 404.

Inter-relay KeyPackage forwarding uses a pull model:

```
GET /v1/agora/kp/{did}?forward=true
```

The `forward=true` parameter instructs the Relay to attempt peer-relay fetching before returning 404. If `replenishFromIPFS` is also enabled, the relay attempts IPFS replenishment after peer-relay fetching fails, before finally returning 404. Relays that support forwarding declare `"keypackage-forwarding-v1"` in their capabilities.

##### KeyPackage Exhaustion

If all KeyPackages for a target DID have been consumed and no fresh ones are available from peer relays or IPFS supply, the sender MUST NOT reuse a previously consumed KeyPackage. Instead, the sender queues the Add locally and retries the fetch from the target's store with backoff. The target replenishes its own supply when it next comes online, through the `GET /count` monitoring above.

KeyPackages are obtained only by fetching them directly from the target's store. A client MUST NOT publish any message on a gossip topic that names the target DID or the requesting DID to solicit KeyPackages.

##### KeyPackage Validation

Recipients of a Welcome MUST validate the KeyPackage used to construct it:

- The signature verifies against the KeyPackage owner's DID authentication key.
- `KeyPackage.leaf_node.credential` contains a valid DID matching the KeyPackage owner (the recipient's own DID).
- The KeyPackage has not expired (`leaf_node.lifetime.not_after`).
- The ciphersuite matches the group's declared ciphersuite.

A Welcome constructed with an invalid or expired KeyPackage MUST be rejected.

#### 5.2.1.2 Community Channel Mode

A `community` channel has a bounded MLS group called the **speaker group**. Only members of the speaker group can post or decrypt messages. Space members outside the speaker group do not hold the channel's exporter-derived `channelToken` and cannot follow or decrypt its traffic until they are admitted.

**Speaker group bounds.** The `speakerCap` field in the channel state (default 200, maximum 500) is the hard upper limit on simultaneous MLS group members. A channel admin MUST NOT issue an Add commit that would push membership above `speakerCap`.

**Idle eviction.** A speaker who has not sent any `ApplicationMessage` in the channel within `idleEvictDays` days (default 7) is eligible for eviction. The channel's designated **SpeakerBot** (a DID listed in the channel state as `speakerBot`) issues periodic Remove commits for idle speakers. If no `speakerBot` is configured, channel admins perform evictions manually. Eviction is not punitive: evicted members are eligible for immediate re-admission when they next request to speak.

**SpeakRequest.** A space member who is not currently in the speaker group and wants to post sends a `SpeakRequest` as an MLS application message in a DM group (§4.6) with the channel's `speakerBot`, or with a channel admin if no `speakerBot` is configured. The requester holds no key for the speaker group, so the request cannot travel in the channel's own envelopes; it MUST NOT be sent in the clear on any topic. The requester's identity is carried and authenticated by the sealed envelope (§5.2.2), so the inner payload carries only the channel:

```json
{
  "@type": "SpeakRequest",
  "channelCID": "bafyrei...",
  "ts": "2026-04-22T09:00:00Z"
}
```

The SpeakerBot or a channel admin responds by issuing a standard MLS Add commit using a KeyPackage from the requester's store. If the speaker group is at capacity, the SpeakerBot SHOULD first evict the longest-idle current speaker before adding the requester.

**Admission latency.** Admission requires one round of MLS Add + Welcome delivery. Clients in `community` channels SHOULD display a "waiting to join" indicator if the user tries to post before their Welcome has been processed.

**History access.** A member who was evicted and later re-admitted receives a new Welcome for the new MLS epoch. They can decrypt messages from epochs in which they held a leaf node; they cannot decrypt messages sent during periods when they were not in the group. This is the correct behavior: they were not a group member during those periods. Clients SHOULD display a clear indicator when history is unavailable for a given time range.

**Compliance logging.** Compliance loggers (§7) in `community` channels are passive members (§5.2.1.3) and MUST NOT be subject to idle eviction. The SpeakerBot MUST check for a passive member leaf before evicting any member.

#### 5.2.1.3 Passive Members

A **passive member** is an MLS group member that holds a leaf credential and participates in epoch ratchets (receiving all application messages and group state updates) but MUST NOT issue Commits or Proposals. Passive members are indistinguishable from standard members at the MLS wire protocol layer; the constraint is behavioral, not cryptographic.

**Use cases in Agora.** Compliance loggers (§7) and VTC recorders (§6.12) are passive members. Both hold leaf credentials, receive all application messages in their admitted groups, and never modify group state.

**KeyPackages.** Passive members require KeyPackages to receive Welcome messages. Because passive members never initiate group operations, they SHOULD publish last-resort KeyPackages (`draft-ietf-mls-extensions-09`, §last-resort-keypackage), KeyPackages marked for reuse when the single-use supply is exhausted, rather than maintaining a large single-use supply. Relays MUST serve a passive member's last-resort KeyPackage when no single-use packages remain.

**Idle eviction.** Passive members MUST NOT be subject to idle eviction (§5.2.1.2). A passive member generates no traffic by design; evicting one on that basis would silently break the compliance capture chain.

**Future standard alignment.** This concept anticipates `draft-ietf-mls-partial-00` ("Partial MLS"), which defines an MLS extension allowing receive-only participants to carry only membership proofs rather than the full ratchet tree, reducing overhead for large groups. That draft expired without a successor. When a partial client standard is published, Agora implementations SHOULD upgrade passive member implementations to native partial client support; the behavioral contract (no Commits, no Proposals, full message receipt) is identical.

#### 5.2.1.4 Broadcast Channel Mode

A `broadcast` channel is a one-to-many CO publication. Posts are encrypted under a channel **content key** that the CO distributes (§3.4) and are signed inside the ciphertext by the poster. The outer envelope reveals no sender. The properties provided are authenticity (was this posted by an authorized poster?) and confidentiality against IOs and non-members, without MLS forward secrecy (see Security properties below).

**Authorized posters.** The set of authorized posters for a broadcast channel is determined by space role: any space member holding a role listed in the channel state's `broadcasterRoles` array may post. Typically this is a dedicated `broadcaster` role held by admins or a bot.

**Publisher group.** The authorized posters form the channel's MLS group, the **publisher group**. Channel admins Add each DID that holds a role in `broadcasterRoles` and Remove it when the role is revoked. Subscribers are not members of the publisher group and consume no KeyPackages. The publisher group provides the epoch access proof (§5.2.2) unchanged: the access key chain is registered and announced as for any channel, and relays admit only envelopes signed with the current epoch access key, so only current posters can publish. The publisher group does not carry the content key: the CO issues it, and posters fetch it from the Space endpoint (§3.4) as subscribers do.

**Content key.** Each broadcast channel has a sequence of content keys, each a `BroadcastKey` record (§3.4) numbered by `keyEpoch`. Subscribers and posters obtain the current key from the Space endpoint; for a channel with `keyAccess: public` the key is public Space state, so whether a broadcast channel is private or public is an access policy on the same mechanism. A poster MUST encrypt under the `BroadcastKey` with the highest `keyEpoch` whose `notBefore` has passed. Clients SHOULD fetch the current `BroadcastKey` on reconnect and MUST fetch it when they see an `accessKeyAnnouncement` whose `channelToken` they cannot derive.

**Broadcast channel token.** A broadcast channel's `channelToken` is derived from the content key, not from the MLS exporter: `channelToken = HKDF-SHA256(IKM = key, salt = "" (zero-length), info = "agora broadcast token" || keyEpoch, L = 32)`, with `keyEpoch` as a big-endian uint64. Subscribers compute it from the `BroadcastKey`. It rotates whenever the key rotates and does not change on publisher group Commits; tokens of different key epochs are unlinkable without the keys. The access key chain carries the token change:

- On a publisher group Commit, the committer's `accessKeyAnnouncement` carries the new MLS `epoch`, the new access public key and the `channelToken` of the current content key.
- On a key rotation without a Commit, the first poster to post under the new `keyEpoch` first sends, on the previous `channelToken`, an envelope carrying an `accessKeyAnnouncement` with the unchanged `epoch` and access public key and the new `channelToken`, signed with the current epoch's access private key. The relay follows the chain from token to token as for any channel.

**Message structure.** Broadcast messages use the standard outer routing envelope (§5.2.2), whose `epoch` and `accessSig` are those of the publisher group. In place of `sealedEnvelope`, the envelope carries a `broadcastPayload` field:

```
broadcastPayload = nonce || AEAD-Seal(key, nonce, plaintext, aad = "agora/broadcast/v1" || channelToken)
```

The AEAD is that of the default ciphersuite (§5.2.1), AES-128-GCM. `nonce` is 12 bytes, freshly random for every message; because many posters share one key, counter nonces are not used. Recipients MUST reject a `broadcastPayload` whose associated data does not match the `channelToken` of the envelope it arrived in. `plaintext` is the signed JSON-LD body:

```json
{
  "@type": "BroadcastMessage",
  "channelCID": "bafyrei...",
  "keyEpoch": 7,
  "body": {
    "@type": "TextBody",
    "content": "v2.1.0 released; see release notes for details.",
    "mimeType": "text/markdown;variant=commonmark"
  },
  "senderDID": "did:key:z6Mk...",
  "ts": "2026-04-22T09:00:00Z",
  "sig": "base64url..."
}
```

`sig` is the sender's Ed25519 signature, signed per §13.1.1. Recipients MUST verify `sig` against the sender's DID document before displaying the message, MUST verify that `channelCID` and `keyEpoch` match the key used to decrypt, and MUST verify that `senderDID` holds a space role listed in `broadcasterRoles`.

**Relay handling.** The Relay stores broadcast messages as ciphertext blobs, identical to any other channel message. It learns a `channelToken`, the publisher group's epoch access signature, a sequence number, a timestamp and an opaque blob, and nothing about who posted. Clients MUST display a visible indicator (e.g., a megaphone icon) on broadcast channels to make clear to users that the channel has the weaker properties stated below.

**Rotation and removal.** To remove a subscriber, the CO publishes a new `BroadcastKey` with `keyEpoch` incremented and stops serving keys to the removed subscriber (§3.4). The CO SHOULD also rotate the key at least every 30 days, and MUST rotate it before 2^32 messages have been encrypted under one key (the AES-GCM limit for random nonces).

**Security properties.** A broadcast channel provides confidentiality against IOs and non-members, and sender authenticity through the inner signature. It is weaker than MLS: there is no forward secrecy or post-compromise security within a key epoch, since one key protects every message of that epoch; a removed subscriber retains the keys of the epochs it held and can read their messages; and any key holder can decrypt the whole epoch. Only the inner signature, not possession of the key, authorizes a post. This is appropriate for one-to-many announcements; channels that need MLS properties MUST use `community` or `interactive` mode.

**KeyPackage consumption.** Only publisher group changes consume KeyPackages, and only those of posters. Posting consumes no recipient's KeyPackage, and subscribers receive no Welcome or Commit messages.

**Compliance logging.** The compliance logger needs no publisher group admission. It obtains each `BroadcastKey` from the Space endpoint as a member (§3.4), follows the channel's tokens, and decrypts. For FINRA/MiFID purposes, broadcast messages in a space with compliance logging enabled are automatically captured to the compliance archive.

### 5.2.2 Message Format

All messages use a two-layer structure: an outer **routing envelope** visible to Relays, and an inner **sealed envelope** whose sender identity is hidden from Relays. The inner payload is MLS-encrypted, except in `broadcast` channels, whose payload is encrypted under the channel content key instead (§5.2.1.4).

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
  "sealedEnvelope": "base64url...",
  "accessSig": "base64url..."
}
```

`channelToken` is derived from the MLS exporter of the channel's group: `MLS-Exporter("agora channel token", channelCID, 32)`. It rotates with every epoch. Relays use it for topic routing without learning the channel identifier or any member identity.

`id` is the CID of the canonical outer envelope, used for deduplication and history indexing. `ts` is present for gossipsub ordering and relay-side TTL enforcement only; it is not authenticated at the outer layer and MUST NOT be trusted for application-level ordering (use the inner `seq` for that). `expiryHint` is set by the sender to match the inner payload `expiry` value; Relays use it as a cache TTL hint (§5.2.4). `accessSig` is the epoch access proof defined below.

#### Epoch Access Proof

Relays admit an envelope only if it comes from a current member of the channel's MLS group, without learning which member (ARCHITECTURE §6.2).

- **Epoch access key.** Each epoch, every member derives `accessSeed = MLS-Exporter("agora access", channelCID, 32)` and uses it as an Ed25519 private key (RFC 8032 seed). All members of the epoch hold the same access key pair.
- **Announcement.** The committer, after creating a Commit, derives the new epoch's access public key and `channelToken`, and attaches to the routing envelope carrying the Commit an `accessKeyAnnouncement` containing the new `epoch`, the new `channelToken`, and the new access public key, signed with the previous epoch's access private key. The relay thereby follows the chain from token to token without learning the channel. The access public key of the group's first epoch is registered with the relay by the CO's registration service in an `AccessChainRegistration` under the CO's `RelayServiceAgreement` (§10.5.1); the registration identifies neither the Space nor the channel.
- **Envelope signature.** `accessSig` is an Ed25519 signature under the current epoch's access private key over the routing envelope with `accessSig` omitted. Relays MUST verify `accessSig` against the access public key for the envelope's `channelToken` and `epoch` and MUST reject envelopes that fail verification.

A removed member does not hold the next epoch's access key, so bans and removals take effect at the relay through the MLS Remove alone. Because the key is shared, a valid signature does not identify the signer.

> **Open (agora-pozi.8):** validate against MLS security properties before relying on it.

#### Sealed Envelope (Sender-Sealed, Relay-Opaque)

`sealedEnvelope` bundles the sender's DID, a per-message ephemeral key, and the MLS ciphertext, all encrypted together to the channel's current MLS group key. No Relay or non-member can open it.

The sealing key is `MLS-Exporter("agora sealed envelope", channelCID, Nk)`, used with the AEAD of the group's ciphersuite. The AEAD associated data MUST bind the recipient context: `"agora/sealed/v1" || channelToken || epoch` (epoch as a big-endian uint64). Implementations MUST NOT seal with empty associated data. A recipient MUST reject a sealed envelope whose associated data does not match the `channelToken` and `epoch` of the routing envelope it arrived in, which prevents re-targeting a sealed envelope to another channel or epoch.

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

This design is derived from Signal's Sealed Sender construction. A Relay processing this message learns: a `channelToken` (epoch-rotating, non-reversible without the group's exporter secret), an epoch access signature that does not identify the signer, a sequence number, a timestamp, and an opaque encrypted blob. It learns nothing about who sent the message.

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

### 5.2.3 Message Types

All inner payload types are defined in the Agora JSON-LD context namespace (`https://agora.protocol/ns/v1`):

| `@type` | Description |
|---|---|
| `TextBody` | Formatted text; `format` field declares the content type (see §5.2.7) |
| `MediaBody` | Reference to IPFS-hosted media (CID + MIME type + size) |
| `EmbedBody` | URL unfurl card (title, description, image CID) |
| `SpeakRequest` | Request for admission to a `community` channel's speaker group, sent in a DM group (§5.2.1.2) |
| `ReactionEvent` | Emoji reaction add/remove targeting a message CID (see §5.2.8) |
| `EditEvent` | Replacement body for a prior message CID |
| `DeleteEvent` | Tombstone for a prior message CID |
| `PinEvent` | Pin a CID to the channel's persistent pin list (§5.2.6) |
| `UnpinEvent` | Remove a CID from the channel's pin list (§5.2.6) |
| `SystemEvent` | Protocol-level event (member join, role change, gateway added, etc.) |
| `VoiceSignal` | WebRTC SDP offer/answer/ICE candidate, targeted to a specific DID |
| `ParticipantState` | Ephemeral VTC room presence (joined/left, muted, video on/off, screen share) |
| `RecordingGrant` | Admin authorization for an SFU DID to decrypt media for recording |
| `RecordingRevoke` | Revocation of a prior `RecordingGrant` |
| `TypingEvent` | Ephemeral typing indicator; not stored |
| `PresenceEvent` | Ephemeral online/idle/dnd status; not stored |

Ephemeral events (`TypingEvent`, `PresenceEvent`, `ParticipantState`) are MLS application messages sent as `PrivateMessage`, never as `PublicMessage` application data, and are excluded from history storage.

### 5.2.4 Message Expiry

Message lifetime is a **sender-side cryptographic commitment**. The sender encodes an `expiry` timestamp in the inner payload, inside the MLS ciphertext and therefore invisible to Relays. Recipients' clients are bound by protocol to honor it because the expiry is part of the authenticated message content signed by the sender.

Expiry semantics:

- `expiry` is an ISO 8601 timestamp in the inner payload. Absence means no expiry (persistent by default).
- On receipt, the client schedules local deletion of the decrypted message at the expiry time.
- On expiry, clients SHOULD also submit a signed `DeleteEvent` to the channel, so that the IPLD history DAG records a tombstone. Relays cannot read a `DeleteEvent` and do not act on it; they drop the cached envelope by `expiryHint`.
- Relays that cache message envelopes MUST respect the `expiryHint` field in the outer `RoutingEnvelope` as a cache TTL. This field is unauthenticated at the outer layer; Relays use it as a hint only, not as authoritative content.
- The authoritative expiry is always the inner payload value, verified by recipients after MLS decryption.

### 5.2.5 Message History

Message history is stored as an IPLD linked list. Each message envelope CID is appended to the channel's history DAG, and the channel state document tracks the latest history CID.

Clients fetch history by walking the IPLD DAG backwards from the latest CID. Relays SHOULD pin recent history within the retention window set by the `RelayServiceAgreement` (§10.5.1). Long-term archival beyond the retention window is the responsibility of space operators or interested members.

IPFS provides content-addressed deduplication automatically: the same message stored at multiple Relays has the same CID.

**Reference implementations for IPFS/IPLD:**
- Go: [`go-ipfs`](https://github.com/ipfs/go-ipfs), [`go-ipld-prime`](https://github.com/ipld/go-ipld-prime)
- JS: [`helia`](https://github.com/ipfs/helia), [`@ipld/dag-cbor`](https://github.com/ipld/js-dag-cbor)
- Rust: [`rust-ipfs`](https://github.com/rs-ipfs/rust-ipfs), [`libipld`](https://github.com/ipld/libipld)

### 5.2.6 Pinned Content

Channels support a **pin list**: a set of CID references in the channel's IPLD state that mark specific content as persistent and surfaced. Pinning is a preservation signal: pinned CIDs are exempt from relay retention expiry (see Retention Exemption) and are surfaced by clients as a dedicated "pinned messages" view. Pin semantics (who may pin, limits, validity) are validated by clients against signed Space and channel state; relays never read pin records.

#### What Can Be Pinned

Any content that already has a CID may be pinned:

- A message envelope CID (a specific chat message, a file share, a thread root)
- A media attachment CID (an image, document, or other file already stored in IPFS)
- An archived external URL: clients MUST archive external URLs to IPFS and pin the resulting CID rather than the URL itself. URLs rot; CIDs do not. The `label` field carries the human-readable original URL or description.

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

`sig` is the pinner's Ed25519 signature over the pin entry, signed per §13.1.1. Pins are attributable and tamper-evident: adding or removing a pin without a valid signature MUST be rejected.

`pinLimit` is the maximum number of simultaneous pins for the channel. Default is 50. Space Admins may set a different limit in the CO-signed channel state. Clients MUST ignore `PinEvent` messages that would cause the pin count to exceed `pinLimit`. Relays do not enforce `pinLimit`.

#### Authorization

- **Any current MLS group member** MAY add a pin (`PinEvent`).
- **Space/Channel Admins and the original pinner** MAY remove a pin (`UnpinEvent`). Other members MAY NOT remove pins they did not add.
- Clients validate these rules against current signed Space and channel state and MUST ignore pin operations that fail them. Only current MLS group members can produce pin operations at all; relays admit them only with a valid epoch access proof (§5.2.2).

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

Both are stored in the channel's IPLD history DAG; the audit trail records who pinned and unpinned what and when, non-repudiably.

#### Retention Exemption

Pinned CIDs are **exempt from relay retention expiry**. A relay cannot read the channel's `pins` array. Instead, a client that has validated a `PinEvent` sends the relay a pin instruction for the CID, carried with an epoch access proof (§5.2.2); an `UnpinEvent` is mirrored by an unpin instruction the same way. Within the storage quota of its `RelayServiceAgreement` (§10.5.1), a relay MUST NOT evict a CID for which it holds a valid pin instruction, regardless of:

- The configured retention window
- The `expiryHint` on the original envelope
- Storage pressure

The relay MUST continue to serve pinned CIDs via IPFS until it receives a valid unpin instruction. If a relay is running low on storage, it MUST evict unpinned content before considering eviction of pinned content, and MUST alert the CO party to the `RelayServiceAgreement` before evicting any pinned CID.

The retention exemption applies only to the pinned CID itself, not to the full IPLD history DAG. Because a relay cannot see what a pinned envelope references, the pinning client sends pin instructions for the pinned CID and for its directly referenced content (e.g., a media attachment CID referenced by a pinned message envelope).

#### Message Expiry Interaction

A pinned message whose inner payload contains an `expiry` timestamp presents a conflict: the sender requested deletion, but a subsequent pinner requested retention. The resolution: **explicit unpinning is required before expiry takes effect on a pinned CID**. A relay MUST NOT evict a CID it holds a pin instruction for on expiry; it honors `expiryHint` for all other envelopes. The channel admin responsible for the pin SHOULD unpin expired content; if they do not, the content persists until explicitly unpinned. Clients SHOULD warn admins when a pinned message's inner payload expiry has passed without an unpin action.

This is a deliberate policy choice: pinning is an admin override of sender expiry. Users who post content they intend to be ephemeral should be aware that an admin may pin it. Channels with strict expiry requirements SHOULD configure a `noPin` policy (a boolean flag in channel state, default false) that disables the pin feature entirely for that channel.

### 5.2.7 TextBody Content Format

#### 5.2.7.1 Baseline Format: CommonMark

The `body` field of a `ChatMessage` inner payload carries a `TextBody` object. The `format` field of `TextBody` declares the content type of the `text` field. The baseline and default format is **CommonMark** ([spec.commonmark.org](https://spec.commonmark.org/)), specifically the most recent stable release at the time of implementation (currently 0.31.2).

```json
{
  "@type": "TextBody",
  "text": "**hello** from `agora`",
  "format": "text/markdown;variant=commonmark"
}
```

Clients MUST support CommonMark rendering. Clients that cannot render CommonMark MUST display the `text` field verbatim.

**Permitted CommonMark features:** All constructs defined in the CommonMark spec are in-scope. No extensions are included in the baseline. The following are explicitly **not** in the CommonMark baseline and MUST NOT be rendered unless negotiated as an extension (§5.2.7.2):

- Tables (GFM extension)
- Strikethrough (GFM extension)
- Task list items (GFM extension)
- Footnotes
- Math / LaTeX blocks
- Raw HTML blocks or inline HTML

Clients MUST strip or escape any raw HTML in a CommonMark `text` field rather than rendering it. A `text` field containing raw HTML is not a conformance violation at the protocol layer, but clients MUST treat it as literal text.

#### 5.2.7.2 Extension Formats

Additional `format` values MAY be defined as named extensions. An extension format is identified by a MIME-type-style string in the `format` field. Clients that do not recognize a `format` value MUST fall back to rendering `text` verbatim.

Reserved extension format strings:

| `format` value | Meaning |
|---|---|
| `text/markdown;variant=commonmark` | CommonMark baseline (default) |
| `text/markdown;variant=gfm` | GitHub Flavored Markdown (CommonMark + tables, strikethrough, task lists) |
| `text/plain` | Literal plaintext; no markup rendering |

The `format` field is extensible: implementations MAY define additional values using reverse-domain namespacing (e.g., `text/markdown;variant=com.example.custom`). Unknown `format` values MUST be treated as `text/plain` by conformant clients.

If `format` is absent, clients MUST treat the `text` field as `text/markdown;variant=commonmark`.

#### 5.2.7.3 Compliance Logger Behavior

Compliance loggers (§7) store the raw `text` field as-is in `plaintextPayload`. The `format` field is preserved alongside it. Loggers are not required to render or interpret the markup; the stored `text` is the authoritative record.

#### 5.2.7.4 Format Capability Advertisement

A sender composing a message has no way to know whether a recipient can render a non-baseline `format` value unless capabilities are advertised. Agora provides two complementary advertisement mechanisms: a persistent declaration in the DID document and an ephemeral declaration inside the MLS group.

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

**In-group declaration (ephemeral)**

A device MAY announce its current rendering capabilities to a group in an ephemeral MLS application message (sent as `PrivateMessage`, not stored in history):

```json
{
  "@type": "ClientCapabilities",
  "supportedTextFormats": [
    "text/markdown;variant=commonmark",
    "text/markdown;variant=gfm",
    "text/plain"
  ]
}
```

Relays do not cache or serve client capabilities; doing so would require the relay to know member DIDs and their online state. If neither source is available, the sender SHOULD assume baseline CommonMark only.

**Sender behavior**

When composing a message with a non-baseline `format`, a conformant client SHOULD:

1. Use the most recent in-group `ClientCapabilities` from each recipient (in DM groups) or check the DID document (in space channels, where per-member checking at compose time is impractical).
2. If all reachable recipients declare support for the chosen format, send with that format.
3. If any recipient's capabilities are unknown or do not include the chosen format, either fall back to `text/markdown;variant=commonmark` or send with the preferred format and accept that some recipients will display raw markup.

In space channels with many members, per-member capability queries at compose time are not required. Clients MAY display a warning when a non-baseline format is selected without blocking the send.

**Multi-device considerations**

A user's devices may have different rendering capabilities. The DID document entry SHOULD reflect the union of all active devices' capabilities, declaring a format only if all devices the user actively uses can render it. An in-group `ClientCapabilities` message reflects the specific device that sent it and MAY differ from the DID document entry.

### 5.2.8 Emoji and Reactions

#### 5.2.8.1 Emoji in Message Text

Unicode emoji are valid UTF-8 content in any `TextBody` `text` field. No special handling is required.

**Shortcodes** (`:thumbsup:`, `:example_logo:`) are a client-side rendering convenience, not a wire format. Shortcodes MUST NOT appear on the wire in `TextBody.text` unless the sender intentionally wants the literal text to appear. Clients that support shortcode input MUST expand shortcodes to their Unicode codepoint(s) (for standard emoji) or to a custom emoji reference (for space emoji, see §5.2.8.4) before constructing the `TextBody`.

**ZWJ sequences and skin tone modifiers** are treated as atomic units. A `ReactionEvent` targeting a message with `"emoji": "👍🏽"` (thumbs up + medium skin tone) is a distinct reaction from `"emoji": "👍"` (thumbs up, no modifier). Clients SHOULD display them as separate reaction types.

#### 5.2.8.2 ReactionEvent Schema

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

`targetCID` is the `envelopeID` CID of the message being reacted to. `emoji` is either a Unicode emoji string (one or more codepoints forming a single grapheme cluster, including ZWJ sequences and modifier sequences) or a custom emoji reference string of the form `:space:<shortcode>:` (see §5.2.8.4). `action` is `"add"` or `"remove"`. `sig` is the sender's Ed25519 signature, signed per §13.1.1.

`targetCID` MUST refer to a message in the same MLS group. Reactions targeting messages in other groups or channels are invalid and MUST be rejected by clients.

#### 5.2.8.3 Reaction Semantics

**One reaction per emoji per sender per target.** A sender MAY NOT add the same `emoji` value to the same `targetCID` more than once. A second `"action": "add"` for the same `(senderDID, targetCID, emoji)` tuple is a no-op; clients MUST deduplicate and MUST NOT display it as a separate reaction.

**Reaction state is derived from the ordered event stream.** Clients reconstruct the current reaction set for a message by replaying all `ReactionEvent` messages targeting that CID in `seq` order. The canonical reaction state at any point is:

```
reactionSet[(targetCID, emoji, senderDID)] = last action seen for that tuple
```

**Aggregation.** Clients SHOULD aggregate reactions by `emoji` value, displaying a count and (on hover or tap) the list of sender display names. A reaction count of zero MUST NOT be displayed.

**Reactions on deleted messages.** If the `targetCID` has been tombstoned by a `DeleteEvent`, clients MUST NOT display reactions for it. Reactions in the event stream targeting a deleted message CID are silently ignored on render.

**Reactions and compliance logging.** `ReactionEvent` messages are logged by the compliance logger identically to `ChatMessage` messages: they are MLS application messages and the logger holds group membership.

#### 5.2.8.4 Custom Emoji

Spaces MAY define custom emoji: space-specific images referenced by shortcode. Custom emoji are IPFS-hosted and declared in the space state document.

**Space state declaration:**

```json
"customEmoji": [
  {
    "shortcode": "example_logo",
    "imageCID": "bafyrei...",
    "mimeType": "image/png",
    "width": 64,
    "height": 64,
    "addedBy": "did:key:z6MkAdmin...",
    "addedAt": "2026-03-12T00:00:00Z"
  }
]
```

`shortcode` MUST match `[a-z0-9_]{1,32}`: lowercase alphanumeric and underscores, 1–32 characters. Shortcodes MUST be unique within a space. `imageCID` is the IPFS CID of the image file. `mimeType` MUST be `image/png`, `image/gif`, or `image/webp`. Images SHOULD be square and SHOULD be 64×64 or 128×128 pixels.

**Wire format for custom emoji reactions:**

When a custom emoji is used in a `ReactionEvent`, the `emoji` field uses the reference string:

```json
"emoji": ":space:example_logo:"
```

Clients resolve `:space:<shortcode>:` by looking up `shortcode` in the current space's `customEmoji` array, fetching the image from IPFS at `imageCID`, and rendering it inline. Clients that cannot resolve the shortcode MUST display the literal reference string `:space:example_logo:` as a fallback.

**Custom emoji in message text:**

Custom emoji MAY appear inline in `TextBody.text` using the same `:space:<shortcode>:` reference syntax. Clients resolve and render them inline alongside the surrounding text.

**Custom emoji management:**

Adding or removing a custom emoji is a signed `SpaceState` mutation by a Space Admin or Owner. The `customEmoji` array in the space state document is the authoritative list. Removing a custom emoji from the array does not delete the IPFS content, but clients MUST stop rendering it after the next space state refresh.

Spaces SHOULD pin custom emoji image CIDs to prevent relay eviction.

---

## 5.3 Presence and Ephemeral State

*Binds: CO.*

### 5.3.1 Presence

Presence is sent as a `PresenceEvent` MLS application message (`PrivateMessage`, §5.2.3) inside an ordinary routing envelope on `v1/agora/channel/<channelToken>`. Nothing about presence is visible to relays beyond an ordinary envelope. Inner payload:

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

### 5.3.2 Typing Indicators

`TypingEvent` is sent as an MLS application message (`PrivateMessage`, §5.2.3) inside an ordinary routing envelope on the channel topic, so relays see only an ordinary envelope, and it is never written to persistent storage. Inner payload:

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

