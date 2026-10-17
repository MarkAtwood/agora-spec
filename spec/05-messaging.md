# 5. Messaging

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1066–1831 (§5–7).

## 5.1 Message Ordering

*Binds: both.*

### 5.1.1 Ordering Model

Agora uses **best-effort causal ordering**. Gossipsub does not guarantee total message order and does not need to. The requirement is that messages arrive in approximately the right order on average, with clients able to reconstruct causal order locally.

Each inner payload carries a `seq` (monotonically increasing integer per sender per channel), inside the ciphertext (§5.2.2). A JMAP Chat `Message` (§5.2.3) refers to earlier Messages by `senderMsgId` in `replyTo` and `threadRootId`, and edits, deletions and reactions name their target Message the same way (§5.2.2). This gives clients enough information to:

- Detect gaps (missing `seq` values from a given sender)
- Buffer out-of-order arrivals and flush the buffer when gaps close
- Detect and display causal relationships for reply threading and reaction targets

Clients order Messages by this model. `sentAt` is the sender's claim and MUST NOT be used for ordering, as the JMAP Chat specification (draft-atwood-jmap-chat-00) requires; `receivedAt` in a member's store records when that store applied the Message.

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

- **`KeyPackage`:** published to the user's `KeyPackageEndpoint` (§5.2.1.1); single-use, and rotated on each new device session and after each use.
- **`Welcome`:** delivered by POST to the new member's `KeyPackageEndpoint` (§4.6); never on a gossip topic. A Welcome MUST include the `ratchet_tree` extension (RFC 9420 §12.4.3.3) carrying the full ratchet tree. A joiner MUST obtain the ratchet tree only from that extension and MUST NOT fetch it from a relay or any other IO; no IO stores or serves ratchet trees or other MLS group state. A joiner MUST reject a Welcome that lacks the `ratchet_tree` extension.
- **`Commit`:** a state-advancing operation (Add, Remove, Update); gossiped to all current group members.
- **`Proposal`:** a pre-commit operation that may be included in a subsequent Commit by any authorized member.

The **Delivery Service** role (as defined in RFC 9420 §10.3) is performed by the gossipsub mesh in combination with each user's `KeyPackageEndpoint` (§5.2.1.1). The **Authentication Service** role is performed by DID verification: MLS leaf node credentials are bound to DID verification keys, so verifying an MLS credential means verifying a DID.

**Reference implementations for MLS (RFC 9420):**
- Rust: [`openmls`](https://github.com/openmls/openmls) (the most complete open-source implementation)
- C/C++: [`mlspp`](https://github.com/cisco/mlspp) (Cisco)

#### 5.2.1.1 KeyPackage Store

A user's KeyPackages are held by whoever runs the user's identity: the employer's provisioning service (§2.5) for an employee, or a host the user chooses or runs for an individual. The client publishes KeyPackages to, and a committer fetches them from, the user's `KeyPackageEndpoint`. For `did:webvh` and `did:plc` the endpoint is a `KeyPackageEndpoint` service entry in the DID document; for `did:key` it is published in the user's Pkarr record (§2.1). Welcomes are delivered by POST to the same endpoint (§4.6). Relays and other IOs store and serve no KeyPackages.

The host MUST make a fetch atomically consume the returned KeyPackage, and MUST verify that each published KeyPackage's leaf credential and signature belong to the endpoint's DID. A committer MUST obtain a KeyPackage only by fetching it from the target's `KeyPackageEndpoint`. A client MUST NOT publish any message on a gossip topic that names the target DID or the requesting DID to solicit KeyPackages.

**Why single-use.** KeyPackages are consumed exactly once. RFC 9420 assumes each KeyPackage's init key is used for one Welcome; reuse lets two groups share HPKE init secrets and lets a replayed Welcome be accepted. A known failure mode is a store that hands out KeyPackages without consuming them, keeps them only while the owning device is connected (so they vanish on disconnect), and keys them to an unstable per-session device identifier, so that adding a user's other devices silently fails. Agora's endpoint avoids this: consumption is atomic and permanent, supply persists independent of connection state, and supply is keyed to the owning DID.

**Last-resort KeyPackages.** A client SHOULD also publish one last-resort KeyPackage (`draft-ietf-mls-extensions-09`, §last-resort-keypackage) per device, which the host returns, without consuming it, only when no single-use KeyPackage remains.

##### KeyPackage Exhaustion

The host rate-limits fetches to prevent a caller from draining a user's supply, and falls back to the last-resort KeyPackage when single-use supply runs out. If neither is available, the committer MUST NOT reuse a previously consumed KeyPackage; it queues the Add locally and retries the fetch with backoff. The client replenishes its supply at the host when it next comes online.

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

**SpeakRequest.** A space member who is not currently in the speaker group and wants to post sends a `SpeakRequest` as an MLS application message in a DM group (§4.6) with the channel's `speakerBot`, or with a channel admin if no `speakerBot` is configured. The requester holds no key for the speaker group, so the request cannot travel in the channel's own envelopes; it MUST NOT be sent in the clear on any topic. The requester's identity is the MLS sender of the DM group message, authenticated by the MLS signature (§5.2.2), so the inner payload, an envelope of type `urn:agora:type:SpeakRequest` (§5.2.3), carries only the channel:

```json
{
  "channelCID": "bafyrei...",
  "ts": "2026-04-22T09:00:00Z"
}
```

The SpeakerBot or a channel admin responds by issuing a standard MLS Add commit using a KeyPackage fetched from the requester's `KeyPackageEndpoint` (§5.2.1.1). If the speaker group is at capacity, the SpeakerBot SHOULD first evict the longest-idle current speaker before adding the requester.

**Admission latency.** Admission requires one round of MLS Add + Welcome delivery. Clients in `community` channels SHOULD display a "waiting to join" indicator if the user tries to post before their Welcome has been processed.

**History access.** A member who was evicted and later re-admitted receives a new Welcome for the new MLS epoch. They can decrypt messages from epochs in which they held a leaf node; they cannot decrypt messages sent during periods when they were not in the group. This is the correct behavior: they were not a group member during those periods. Clients SHOULD display a clear indicator when history is unavailable for a given time range.

**Compliance logging.** Compliance loggers (§7) in `community` channels are passive members (§5.2.1.3) and MUST NOT be subject to idle eviction. The SpeakerBot MUST check for a passive member leaf before evicting any member.

#### 5.2.1.3 Passive Members

A **passive member** is an MLS group member that holds a leaf credential and participates in epoch ratchets (receiving all application messages and group state updates) but MUST NOT issue Commits or Proposals. Passive members are indistinguishable from standard members at the MLS wire protocol layer; the constraint is behavioral, not cryptographic.

**Use cases in Agora.** Compliance loggers (§7) and VTC recorders (§6.12) are passive members. Both hold leaf credentials, receive all application messages in their admitted groups, and never modify group state.

**KeyPackages.** Passive members require KeyPackages to receive Welcome messages. Because passive members never initiate group operations, they SHOULD publish last-resort KeyPackages (`draft-ietf-mls-extensions-09`, §last-resort-keypackage), KeyPackages marked for reuse when the single-use supply is exhausted, rather than maintaining a large single-use supply. The passive member's `KeyPackageEndpoint` host serves the last-resort KeyPackage when no single-use packages remain (§5.2.1.1).

**Idle eviction.** Passive members MUST NOT be subject to idle eviction (§5.2.1.2). A passive member generates no traffic by design; evicting one on that basis would silently break the compliance capture chain.

**Future standard alignment.** This concept anticipates `draft-ietf-mls-partial-00` ("Partial MLS"), which defines an MLS extension allowing receive-only participants to carry only membership proofs rather than the full ratchet tree, reducing overhead for large groups. That draft expired without a successor. When a partial client standard is published, Agora implementations SHOULD upgrade passive member implementations to native partial client support; the behavioral contract (no Commits, no Proposals, full message receipt) is identical.

#### 5.2.1.4 Broadcast Channel Mode

A `broadcast` channel is a one-to-many CO publication. Posts are encrypted under a channel **content key** that the CO distributes (§3.4) and are signed inside the ciphertext by the poster. The outer envelope reveals no sender. The properties provided are authenticity (was this posted by an authorized poster?) and confidentiality against IOs and non-members, without MLS forward secrecy (see Security properties below).

**Authorized posters.** The set of authorized posters for a broadcast channel is determined by space role: any space member holding a role listed in the channel state's `broadcasterRoles` array may post. Typically this is a dedicated `broadcaster` role held by admins or a bot.

**Publisher group.** The authorized posters form the channel's MLS group, the **publisher group**. Channel admins Add each DID that holds a role in `broadcasterRoles` and Remove it when the role is revoked. Subscribers are not members of the publisher group and consume no KeyPackages. The publisher group provides the epoch access proof (§5.2.2) unchanged: the access key chain is registered and announced as for any channel, and relays admit only envelopes signed with the current epoch access key, so only current posters can publish. The publisher group does not carry the content key: the CO issues it, and posters fetch it from the Space endpoint (§3.4) as subscribers do.

**Content key.** Each broadcast channel has a sequence of content keys, each a `BroadcastKey` record (§3.4) numbered by `keyEpoch`. Subscribers and posters obtain the current key from the Space endpoint; for a channel with `keyAccess: public` the key is public Space state, so whether a broadcast channel is private or public is an access policy on the same mechanism. A poster MUST encrypt under the `BroadcastKey` with the highest `keyEpoch` whose `notBefore` has passed. Clients SHOULD fetch the current `BroadcastKey` on reconnect and MUST fetch it when they see an `accessKeyAnnouncement` whose `channelToken` they cannot derive.

**Broadcast channel token.** A broadcast channel's `channelToken` is derived from the content key, not from the MLS exporter: `channelToken = HKDF-SHA256(IKM = key, salt = "" (zero-length), info = "agora broadcast token" || keyEpoch, L = 32)`, with `keyEpoch` as a big-endian uint64. Subscribers compute it from the `BroadcastKey`. It rotates whenever the key rotates and does not change on publisher group Commits; tokens of different key epochs are unlinkable without the keys. The access key chain carries the token change:

- On a publisher group Commit, the committer's `accessKeyAnnouncement` carries the new MLS `epoch`, the new access public key and the `channelToken` of the current content key, and is countersigned with `billingSig` (§5.2.2).
- On a key rotation without a Commit, the first poster to post under the new `keyEpoch` first sends, on the previous `channelToken`, an envelope carrying an `accessKeyAnnouncement` with the unchanged `epoch` and access public key and the new `channelToken`, signed with the current epoch's access private key and countersigned with `billingSig` (§5.2.2). The relay follows the chain from token to token as for any channel.

**Message structure.** Broadcast messages use the standard outer routing envelope (§5.2.2), whose `epoch` and `accessSig` are those of the publisher group. In place of `sealedEnvelope`, the envelope carries a `broadcastPayload` field:

```
broadcastPayload = nonce || AEAD-Seal(key, nonce, plaintext, aad = "agora/broadcast/v1" || channelToken)
```

The AEAD is that of the default ciphersuite (§5.2.1), AES-128-GCM. `nonce` is 12 bytes, freshly random for every message; because many posters share one key, counter nonces are not used. Recipients MUST reject a `broadcastPayload` whose associated data does not match the `channelToken` of the envelope it arrived in. `plaintext` is one typed payload envelope (§13.1) of type `urn:agora:type:BroadcastMessage` with `sig` present. Its body binds a JMAP Chat `Message` (§5.2.3) to the channel, key epoch and poster:

```json
{
  "channelCID": "bafyrei...",
  "keyEpoch": 7,
  "senderDID": "did:key:z6Mk...",
  "seq": 311,
  "message": {
    "senderMsgId": "01J3XM2C4V0Q6R9T8Y7W5E3B1A",
    "body": "v2.1.0 released; see release notes for details.",
    "bodyType": "text/markdown;variant=commonmark",
    "sentAt": "2026-04-22T09:00:00Z"
  }
}
```

`seq` is the poster's per-channel sequence number (§5.1.1). `message` carries the fields of a new Message as defined in §5.2.2. Subscribers are not members of the publisher group, so no MLS sender signature covers the payload; `sig` is the poster's JWS, signed per §13.1.1. Recipients MUST verify `sig` per §13.1.1 with the DID of its `kid` equal to `senderDID` before displaying the message, MUST verify that `channelCID` and `keyEpoch` match the key used to decrypt, and MUST verify that `senderDID` holds a space role listed in `broadcasterRoles`.

**Relay handling.** The Relay stores broadcast messages as ciphertext blobs, identical to any other channel message. It learns a `channelToken`, the publisher group's epoch access signature, a timestamp and an opaque blob, and nothing about who posted. Clients MUST display a visible indicator (e.g., a megaphone icon) on broadcast channels to make clear to users that the channel has the weaker properties stated below.

**Rotation and removal.** To remove a subscriber, the CO publishes a new `BroadcastKey` with `keyEpoch` incremented and stops serving keys to the removed subscriber (§3.4). The CO SHOULD also rotate the key at least every 30 days, and MUST rotate it before 2^32 messages have been encrypted under one key (the AES-GCM limit for random nonces).

**Security properties.** A broadcast channel provides confidentiality against IOs and non-members, and sender authenticity through the inner signature. It is weaker than MLS: there is no forward secrecy or post-compromise security within a key epoch, since one key protects every message of that epoch; a removed subscriber retains the keys of the epochs it held and can read their messages; and any key holder can decrypt the whole epoch. Only the inner signature, not possession of the key, authorizes a post. This is appropriate for one-to-many announcements; channels that need MLS properties MUST use `community` or `interactive` mode.

**KeyPackage consumption.** Only publisher group changes consume KeyPackages, and only those of posters. Posting consumes no recipient's KeyPackage, and subscribers receive no Welcome or Commit messages.

**Compliance logging.** The compliance logger needs no publisher group admission. It obtains each `BroadcastKey` from the Space endpoint as a member (§3.4), follows the channel's tokens, and decrypts. For FINRA/MiFID purposes, broadcast messages in a space with compliance logging enabled are automatically captured to the compliance archive.

### 5.2.2 Message Format

All messages use a two-layer structure: an outer **routing envelope** visible to Relays, and an inner **sealed envelope** that hides the MLS framing from Relays. The inner payload is MLS-encrypted, except in `broadcast` channels, whose payload is encrypted under the channel content key instead (§5.2.1.4).

#### Outer Routing Envelope

The outer envelope contains only what Relays strictly need for delivery routing. It does not contain the sender's DID.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RoutingEnvelope",
  "id": "urn:agora:msg:bafyrei...",
  "channelToken": "base64url...",
  "epoch": 17,
  "ts": "2026-03-12T12:00:00.000Z",
  "expiryHint": "2026-03-19T12:00:00.000Z",
  "sealedEnvelope": "base64url...",
  "accessSig": "base64url..."
}
```

`channelToken` is derived from the MLS exporter of the channel's group: `MLS-Exporter("agora channel token", channelCID, 32)`. It rotates with every epoch. Relays use it for topic routing without learning the channel identifier or any member identity.

`id` is the CID of the canonical outer envelope, used for deduplication and history indexing. `ts` is present for gossipsub ordering and relay-side TTL enforcement only; it is not authenticated at the outer layer and MUST NOT be trusted for application-level ordering (use the inner `seq` for that, §5.1.1). `expiryHint` is set by the sender to match the inner payload `expiry` value; Relays use it as a cache TTL hint (§5.2.4). `accessSig` is the epoch access proof defined below.

#### Epoch Access Proof

Relays admit an envelope only if it comes from a current member of the channel's MLS group, without learning which member (ARCHITECTURE §6.2).

- **Epoch access key.** Each epoch, every member derives `accessSeed = MLS-Exporter("agora access", channelCID, 32)` and uses it as an Ed25519 private key (RFC 8032 seed). All members of the epoch hold the same access key pair.
- **Announcement.** The committer, after creating a Commit, derives the new epoch's access public key and `channelToken`, and attaches to the routing envelope carrying the Commit an `accessKeyAnnouncement` containing the new `epoch`, the new `channelToken`, and the new access public key, signed with the previous epoch's access private key. The relay thereby follows the chain from token to token without learning the channel. The access public key of the group's first epoch is registered with the relay by the CO's registration service in an `AccessChainRegistration` under the CO's `RelayServiceAgreement` (§10.5.1); the registration identifies neither the Space nor the channel.
- **Countersignature.** Every `accessKeyAnnouncement` MUST also carry `billingSig`, a signature by the CO's registration service with the billing key of the agreement under which the chain is registered, signed per §13.1.1 over the announcement with `billingSig` omitted. The committer obtains it from the service before publishing the Commit. The service countersigns only an announcement requested by a DID it authenticates as a current member of the channel under Space state, and at most one announcement per chain and `epoch`. Relays MUST reject an announcement without a valid `billingSig` from that agreement's billing DID. The countersignature exists because the previous epoch's access private key is also held by a member being removed, who could otherwise announce a key only they know, keep relay access, and lock out the remaining members.
- **Outage.** If the registration service is unreachable, relays keep accepting envelopes signed with the last countersigned access key, and members MUST retain that key and sign with the latest access key the relay accepts until a countersigned announcement for a later epoch is accepted. A member removed after the last countersigned epoch can write until then.
- **Envelope signature.** `accessSig` is an Ed25519 signature under the current epoch's access private key over the routing envelope with `accessSig` omitted. Relays MUST verify `accessSig` against the access public key for the envelope's `channelToken` and `epoch` and MUST reject envelopes that fail verification.

A removed member does not hold the next epoch's access key, so bans and removals take effect at the relay through the MLS Remove alone. Because the key is shared, a valid signature does not identify the signer.

> **Open (agora-pozi.8):** the epoch access proof awaits external cryptographic review.

#### Sealed Envelope (Sender-Sealed, Relay-Opaque)

`sealedEnvelope` is one AEAD ciphertext over the complete serialized `MLSMessage` (a `PrivateMessage`, or a handshake message such as a Commit or Proposal), keyed from the channel's current MLS epoch. No Relay or non-member can open it.

The wrapper exists because MLS framing is visible in the clear: `group_id`, `epoch` and `content_type` precede the encrypted content. `group_id` is constant for the life of the group, so a Relay that saw it could link every epoch of a channel despite the rotating `channelToken`; `epoch` and `content_type` would reveal epoch boundaries and which messages are Commits. The wrapper hides all three.

The sealing key is `MLS-Exporter("agora sealed envelope", channelCID, Nk)`, used with the AEAD of the group's ciphersuite. The AEAD associated data MUST bind the recipient context: `"agora/sealed/v1" || channelToken || epoch` (epoch as a big-endian uint64). Implementations MUST NOT seal with empty associated data. A recipient MUST reject a sealed envelope whose associated data does not match the `channelToken` and `epoch` of the routing envelope it arrived in, which prevents re-targeting a sealed envelope to another channel or epoch.

The plaintext is the serialized `MLSMessage` with no further structure. The wrapper carries no sender DID, ephemeral key or signature of its own: the sender is identified by the MLS sender data, which MLS encrypts, and authenticated by the MLS signature (§13.1.1).

The idea of hiding the sender from the delivery service comes from Signal's Sealed Sender; the construction is different, since sender authentication here is entirely MLS's. A Relay processing this message learns: a `channelToken` (epoch-rotating, non-reversible without the group's exporter secret), an epoch access signature that does not identify the signer, a timestamp, an expiry hint, and an opaque encrypted blob. It learns nothing about who sent the message.

#### Inner Payload (After MLS Decryption)

The `application_data` of every MLS application message is exactly one typed payload envelope (§13.1). The envelope's `type` names the object (§5.2.3) and its `body` holds the object's exact bytes. Inside MLS the envelope carries one further member, `seq`, the sender's per-channel sequence number used for gap detection (§5.1.1). It is covered by the MLS signature and invisible to Relays.

Objects carried inside MLS have no object-level signature and no sender field. The MLS sender signature authenticates the sender (§13.1.1), and the sender is the DID in the sending leaf's credential (§5.2.1). An object that is also verified outside the group carries `sig` per §13.1.1 so that it can be forwarded or archived byte-for-byte.

A chat message is a `Message` of the JMAP Chat specification (draft-atwood-jmap-chat-00), shown here with `body` decoded:

```
{
  "type": "urn:ietf:params:jmap:chat#Message",
  "contentType": "application/json",
  "seq": 1042,
  "body":                         / the exact JSON bytes of: /
    {
      "senderMsgId": "01J3XM2C4V0Q6R9T8Y7W5E3B1A",
      "body": "the fips conversion is green",
      "bodyType": "text/markdown;variant=commonmark",
      "sentAt": "2026-03-12T12:00:00Z",
      "senderExpiresAt": "2026-03-19T12:00:00Z",
      "attachments": [],
      "mentions": []
    }
}
```

The body of a new `Message` carries the fields that the JMAP Chat federation specification (draft-atwood-jmap-chat-federation-00) defines for the `message` object of `Peer/deliver`, under these rules:

- `senderMsgId` is the sender-assigned ULID and identifies the Message to every member. Every cross-member reference to a Message (`replyTo`, `threadRootId`, edit, deletion and reaction targets, `pinnedMessageIds`) uses its `senderMsgId`.
- `chatId` and the sender are not carried. The Chat is the channel or DM group whose MLS group carried the envelope, and the sender is the MLS sender.
- Each member's client or daemon keeps the Message in its own JMAP store and sets the server-set fields there: `id`, `senderId` (the sender's DID, or `"self"`), `receivedAt` and the delivery fields.
- An attachment's `blobId` is the CID of the file stored as a group-encrypted blob (§3.4); `fetchUrl` is not used. `sha256` is a hash of the plaintext and MUST NOT be sent to any IO.

A receiving client performs the checks that the JMAP Chat federation specification assigns to a receiving server (New Message Validation, Edit and Reaction Validation), evaluating membership, bans and permissions against current signed Space state (§3.3).

### 5.2.3 Message Types

The `type` of an inner payload envelope is one of the values below or a type defined in another section or by an extension (§13.2).

#### Chat objects (JMAP Chat)

Chat content uses the data types and ephemeral events of the JMAP Chat specifications. Agora defines no chat object of its own.

| `type` | Body | JMAP Chat definition |
|---|---|---|
| `urn:ietf:params:jmap:chat#Message` | New Message, edit, or deletion (below) | `Message`, with embedded `Attachment`, `Mention`, `BroadcastMention` and `MessageAction`; rich text per the Rich Body Format |
| `urn:ietf:params:jmap:chat#Reaction` | The fields of the federation `reactionUpdate` object (§5.2.8.2) | `Reaction` |
| `urn:ietf:params:jmap:chat#Chat` | `pinnedMessageIds` only (§5.2.6) | `Chat.pinnedMessageIds` |
| `urn:ietf:params:jmap:chat:websocket#ChatTypingEvent` | §5.3.2 | `ChatTypingEvent` (draft-atwood-jmap-chat-wss-00) |
| `urn:ietf:params:jmap:chat:websocket#ChatPresenceEvent` | §5.3.1 | `ChatPresenceEvent` (draft-atwood-jmap-chat-wss-00) |

A `Message` body is one of:

- **New Message:** the fields described in §5.2.2.
- **Edit:** the target's `senderMsgId` and the fields of the federation `edit` object (`body`, `bodyType`, `editedAt`, and optionally `mentions` and `broadcastMentions`). A body containing `editedAt` is an edit.
- **Deletion for all:** the target's `senderMsgId`, `deletedAt`, and `deletedForAll: true`, with the effect of `Peer/retract`. A body containing `deletedAt` is a deletion.

Receivers MUST apply an edit or deletion only if its MLS sender is the sender of the target Message. Deletion of another member's Message by an Admin is a moderation operation (§4.5).

#### Agora protocol types

These types have no JMAP Chat equivalent and are defined by this specification:

| `type` | Description |
|---|---|
| `urn:agora:type:SpeakRequest` | Request for admission to a `community` channel's speaker group, sent in a DM group (§5.2.1.2) |
| `urn:agora:type:SpaceStateHead` | Notice of a new Space state head CID (§3.4) |
| `urn:agora:type:ClientCapabilities` | Ephemeral per-device list of renderable body types (§5.2.7.4) |
| `urn:agora:type:SystemEvent` | Protocol-level event (member join, role change, gateway added (§9.3), etc.) |
| `urn:agora:type:VoiceSignal` | WebRTC SDP offer/answer/ICE candidate, targeted to a specific DID (§6.4) |
| `urn:agora:type:ParticipantState` | Ephemeral call presence (joined/left, muted, video on/off, screen share) (§6.2) |
| `urn:agora:type:RecordingGrant` | Authorization and disclosure record admitting a CO-run recorder to a call (§6.12) |
| `urn:agora:type:RecordingRevoke` | Revocation of a prior `RecordingGrant` (§6.12) |
| `urn:agora:type:JmapSet` | Patch to JMAP-family objects (§14.3.2); for a `sequenced-v1` type, carries the `after` head (§14.4.3) |
| `urn:agora:type:SequencedOp` | A sequencer stamp with the operation it orders (§14.4.3) |
| `urn:agora:type:SequencerFork` | Proof of sequencer equivocation: two conflicting stamps (§14.4.5) |

`urn:agora:type:BroadcastMessage` (§5.2.1.4) is carried only in a `broadcastPayload`, never in an MLS application message. `urn:agora:type:SequenceStamp` (§14.4.2) is issued by the sequencer and carried only inside a `SequencedOp` body or returned by the sequencer's endpoint, never as an MLS application message by itself. Access key announcements travel in the routing envelope (§5.2.2), and compliance records (§7.4) are written by the logger; neither is an MLS application message.

Ephemeral events (`ChatTypingEvent`, `ChatPresenceEvent`, `ParticipantState`) are MLS application messages sent as `PrivateMessage`, never as `PublicMessage` application data, and are excluded from history storage.

### 5.2.4 Message Expiry

Message lifetime is a **sender-side commitment**. The sender sets the JMAP Chat `senderExpiresAt` field of a `Message` (§5.2.3), inside the MLS ciphertext and therefore invisible to Relays. Recipients' clients are bound by protocol to honor it because it is part of the message content authenticated by the MLS sender signature.

Expiry semantics:

- `senderExpiresAt` has the meaning the JMAP Chat specification gives it: each member's store hard-deletes the Message at or before that time and keeps no tombstone. Absence means no expiry (persistent by default). A pinned Message is the one exception (§5.2.6, Message Expiry Interaction).
- Clients send no deletion message on expiry; every member already holds the deadline. Relays drop the cached envelope by `expiryHint`.
- Relays that cache message envelopes MUST respect the `expiryHint` field in the outer `RoutingEnvelope` as a cache TTL. This field is unauthenticated at the outer layer; Relays use it as a hint only, not as authoritative content.
- The authoritative expiry is always `senderExpiresAt`, read by recipients after MLS decryption.

### 5.2.5 Message History

Message history is stored as an IPLD linked list. Each message envelope CID is appended to the channel's history DAG, and the channel state document tracks the latest history CID.

Clients fetch history by walking the IPLD DAG backwards from the latest CID. Relays SHOULD pin recent history within the retention window set by the `RelayServiceAgreement` (§10.5.1). Long-term archival beyond the retention window is the responsibility of space operators or interested members.

History entries are envelope CIDs, while Messages refer to each other by `senderMsgId` (§5.2.2). A client records the envelope CID that carried each Message, so that it can resolve references and send relay pin instructions (§5.2.6) for a Message.

IPFS provides content-addressed deduplication automatically: the same message stored at multiple Relays has the same CID.

**Reference implementations for IPFS/IPLD:**
- Go: [`go-ipfs`](https://github.com/ipfs/go-ipfs), [`go-ipld-prime`](https://github.com/ipld/go-ipld-prime)
- JS: [`helia`](https://github.com/ipfs/helia), [`@ipld/dag-cbor`](https://github.com/ipld/js-dag-cbor)
- Rust: [`rust-ipfs`](https://github.com/rs-ipfs/rust-ipfs), [`libipld`](https://github.com/ipld/libipld)

### 5.2.6 Pinned Content

A channel's **pin list** is the JMAP Chat `pinnedMessageIds` property of its Chat, listing pinned Messages by `senderMsgId`. Pinning is a preservation signal: the envelopes of pinned Messages are exempt from relay retention expiry (see Retention Exemption), and clients surface pinned Messages in a dedicated "pinned messages" view. Clients validate pin updates against signed Space and channel state; relays never read them.

#### What Can Be Pinned

Only Messages can be pinned, as in the JMAP Chat specification. A file or an external URL is pinned by pinning the Message that carries it. To preserve an external URL, the pinner archives it to IPFS and pins a Message that attaches the archived copy, since URLs rot and CIDs do not.

Pinning does not copy data. It records a reference that tells clients, and through pin instructions tells relays, that the Message must be retained and displayed prominently.

#### Pin List in Channel IPLD State

Retired. The pin list is `Chat.pinnedMessageIds` in each member's JMAP store, changed by the pin updates below; channel state carries no `pins` array. Two Agora fields remain in CO-signed channel state (§3.3):

- `pinLimit`: the maximum number of simultaneous pins for the channel. Default is 50. Space Admins may set a different limit. Clients MUST ignore a pin update that would make `pinnedMessageIds` longer than `pinLimit`. Relays do not enforce `pinLimit`.
- `noPin`: a boolean, default false. When true, clients MUST ignore every pin update for the channel (see Message Expiry Interaction).

#### Authorization

Who may change `pinnedMessageIds` is defined by the JMAP Chat specification: in a channel, members holding the `"pin"` Space permission; in a group chat, admins. Clients evaluate this against current signed Space and channel state (§3.3) and MUST ignore pin updates that fail it. Only current MLS group members can produce pin updates at all; relays admit them only with a valid epoch access proof (§5.2.2).

#### PinEvent and UnpinEvent

Retired. A pin or unpin is an MLS application message of type `urn:ietf:params:jmap:chat#Chat` (§5.2.3) whose body carries the complete new list:

```json
{
  "pinnedMessageIds": ["01J3XM2C4V0Q6R9T8Y7W5E3B1A", "01J3XKZQN4MWVT8PPBEHTJ3HX0"]
}
```

Several members may write the list, so `Chat` is a sequenced type: clients apply pin updates in sequencer order, run the checks above on each, and each valid update replaces the list. Pin updates are kept in the channel's history DAG, and the MLS sender signature on each records who changed the pin list and when.

Pin updates are written under the `sequenced-v1` consistency model and ordered by the Space's blind sequencer as defined in §14.4. A client MUST submit a pin update per §14.4.3 and MUST apply pin updates only in the stamped order validated per §14.4.4.

#### Retention Exemption

Pinned Messages are **exempt from relay retention expiry**. A relay cannot read `pinnedMessageIds`. Instead, a client that has applied a pin update adding a Message sends the relay a pin instruction for the CID of the envelope that carried that Message (§5.2.5), carried with an epoch access proof (§5.2.2); a pin update removing a Message is mirrored by an unpin instruction the same way. Within the storage quota of its `RelayServiceAgreement` (§10.5.1), a relay MUST NOT evict a CID for which it holds a valid pin instruction, regardless of:

- The configured retention window
- The `expiryHint` on the original envelope
- Storage pressure

The relay MUST continue to serve pinned CIDs via IPFS until it receives a valid unpin instruction. If a relay is running low on storage, it MUST evict unpinned content before considering eviction of pinned content, and MUST alert the CO party to the `RelayServiceAgreement` before evicting any pinned CID.

The retention exemption applies only to the pinned CID itself, not to the full IPLD history DAG. Because a relay cannot see what a pinned envelope references, the pinning client sends pin instructions for the envelope CID and for its directly referenced content (e.g., the `blobId` CIDs of the Message's attachments).

#### Message Expiry Interaction

A pinned Message that carries `senderExpiresAt` presents a conflict: the sender requested deletion, but a subsequent pinner requested retention. The resolution: **explicit unpinning is required before expiry takes effect on a pinned Message**. Clients MUST NOT hard-delete a pinned Message at `senderExpiresAt`; they delete it when it is unpinned if the deadline has passed. This overrides the JMAP Chat hard-deletion rule for pinned Messages only. A relay MUST NOT evict a CID it holds a pin instruction for on expiry; it honors `expiryHint` for all other envelopes. The channel admin responsible for the pin SHOULD unpin expired content; if they do not, the content persists until explicitly unpinned. Clients SHOULD warn admins when a pinned Message's `senderExpiresAt` has passed without an unpin action.

This is a deliberate policy choice: pinning is an admin override of sender expiry. Users who post content they intend to be ephemeral should be aware that an admin may pin it. Channels with strict expiry requirements SHOULD set `noPin` in channel state, which disables the pin feature entirely for that channel.

### 5.2.7 TextBody Content Format

Retired as an Agora format. Message text is the JMAP Chat `Message.body` with its `bodyType` (§5.2.3). The subsections below keep only the Agora rules that the JMAP Chat specification does not state.

#### 5.2.7.1 Baseline Format: CommonMark

The baseline `bodyType` is `text/markdown;variant=commonmark`: **CommonMark** ([spec.commonmark.org](https://spec.commonmark.org/)), the most recent stable release at the time of implementation (currently 0.31.2). Clients MUST treat `text/markdown` without a `variant` parameter as CommonMark, the profile the JMAP Chat specification names.

Clients MUST support CommonMark rendering and `text/plain`. Clients that cannot render CommonMark MUST display `body` verbatim.

The following are not in the CommonMark baseline and MUST NOT be rendered unless the `bodyType` names an extension that includes them (§5.2.7.2):

- Tables (GFM extension)
- Strikethrough (GFM extension)
- Task list items (GFM extension)
- Footnotes
- Math / LaTeX blocks
- Raw HTML blocks or inline HTML

Clients MUST strip or escape any raw HTML in a Markdown `body` rather than rendering it. A `body` containing raw HTML is not a conformance violation at the protocol layer, but clients MUST treat it as literal text.

#### 5.2.7.2 Extension Formats

`bodyType` values are media types, as defined by the JMAP Chat specification. Values with defined meaning on Agora:

| `bodyType` value | Meaning |
|---|---|
| `text/markdown;variant=commonmark` | CommonMark baseline (default) |
| `text/markdown;variant=gfm` | GitHub Flavored Markdown (CommonMark + tables, strikethrough, task lists) |
| `text/plain` | Literal plaintext; no markup rendering |
| `application/jmap-chat-rich` | JMAP Chat Rich Body Format |

Implementations MAY define additional values using reverse-domain namespacing (e.g., `text/markdown;variant=com.example.custom`). A JMAP server rejects a `bodyType` outside its `supportedBodyTypes`; an Agora receiver has no server to do so, and MUST render a `body` whose `bodyType` it does not recognize as `text/plain`.

#### 5.2.7.3 Compliance Logger Behavior

Compliance loggers (§7) store the decrypted envelope as received in `plaintextPayload` (§7.4), so a Message's `body` and `bodyType` are kept exactly as sent. Loggers are not required to render or interpret the markup; the stored `body` is the authoritative record.

#### 5.2.7.4 Format Capability Advertisement

A sender composing a message has no way to know whether a recipient can render a non-baseline `bodyType` unless capabilities are advertised. The JMAP Chat `supportedBodyTypes` account capability describes one server and does not reach other members, so Agora provides two complementary advertisement mechanisms: a persistent declaration in the DID document and an ephemeral declaration inside the MLS group. Both use the JMAP Chat name `supportedBodyTypes`.

**DID document declaration (persistent)**

A client MAY publish its supported body types as a service entry in its DID document:

```json
{
  "id": "did:key:z6Mk...#text-formats",
  "type": "AgoraTextFormatCapabilities",
  "serviceEndpoint": "inline",
  "supportedBodyTypes": [
    "text/markdown;variant=commonmark",
    "text/markdown;variant=gfm",
    "text/plain"
  ]
}
```

**In-group declaration (ephemeral)**

A device MAY announce its current rendering capabilities to a group in an ephemeral MLS application message of type `urn:agora:type:ClientCapabilities` (sent as `PrivateMessage`, not stored in history):

```json
{
  "supportedBodyTypes": [
    "text/markdown;variant=commonmark",
    "text/markdown;variant=gfm",
    "text/plain"
  ]
}
```

Relays do not cache or serve client capabilities; doing so would require the relay to know member DIDs and their online state. If neither source is available, the sender SHOULD assume baseline CommonMark only.

**Sender behavior**

When composing a message with a non-baseline `bodyType`, a conformant client SHOULD:

1. Use the most recent in-group `ClientCapabilities` from each recipient (in DM groups) or check the DID document (in space channels, where per-member checking at compose time is impractical).
2. If all reachable recipients declare support for the chosen body type, send with it.
3. If any recipient's capabilities are unknown or do not include the chosen body type, either fall back to `text/markdown;variant=commonmark` or send with the preferred body type and accept that some recipients will display raw markup.

In space channels with many members, per-member capability queries at compose time are not required. Clients MAY display a warning when a non-baseline body type is selected without blocking the send.

**Multi-device considerations**

A user's devices may have different rendering capabilities. The DID document entry SHOULD reflect the union of all active devices' capabilities, declaring a body type only if all devices the user actively uses can render it. An in-group `ClientCapabilities` message reflects the specific device that sent it and MAY differ from the DID document entry.

### 5.2.8 Emoji and Reactions

#### 5.2.8.1 Emoji in Message Text

Unicode emoji are valid UTF-8 content in any Message `body`. No special handling is required.

**Shortcodes** (`:thumbsup:`, `:example_logo:`) are a client-side rendering convenience, not a wire format. Shortcodes MUST NOT appear on the wire in a Message `body` unless the sender intentionally wants the literal text to appear. Clients that support shortcode input MUST expand shortcodes to their Unicode codepoint(s) (for standard emoji) or to a custom emoji reference (for space emoji, see §5.2.8.4) before constructing the Message.

**ZWJ sequences and skin tone modifiers** are treated as atomic units. A Reaction with `"emoji": "👍🏽"` (thumbs up + medium skin tone) is a distinct reaction from one with `"emoji": "👍"` (thumbs up, no modifier). Clients SHOULD display them as separate reaction types.

#### 5.2.8.2 ReactionEvent Schema

Retired. A reaction is an MLS application message of type `urn:ietf:params:jmap:chat#Reaction` (§5.2.3). Its body carries the fields of the federation `reactionUpdate` object and follows the add and remove semantics of the JMAP Chat `Reaction` type:

```json
{
  "senderMsgId": "01J3XM2C4V0Q6R9T8Y7W5E3B1A",
  "senderReactionId": "01J3XN7D2K8F4G6H0J9M1P3Q5R",
  "emoji": "👍",
  "action": "add",
  "sentAt": "2026-03-12T12:00:00Z"
}
```

`senderMsgId` names the target Message, which MUST be in the same Chat, as the JMAP Chat specifications require. For a custom emoji, `customEmojiId` is set and `emoji` carries the `:space:<name>:` reference as the fallback (§5.2.8.4).

#### 5.2.8.3 Reaction Semantics

**One reaction per emoji per sender per target.** A sender MUST NOT add a second Reaction with the same `emoji` value, or the same `customEmojiId`, to the same Message while its first such Reaction is present. A receiving client MUST treat such a second add as a no-op and MUST NOT display it as a separate reaction.

**Reaction state.** The reaction set of a Message is its JMAP Chat `reactions` map: an add stores the Reaction under its `senderReactionId`, and a remove deletes that entry.

**Aggregation.** Clients SHOULD aggregate reactions by `emoji` value, displaying a count and (on hover or tap) the list of sender display names. A reaction count of zero MUST NOT be displayed.

**Reactions on deleted messages.** If the target Message has `deletedAt` set or has been hard-deleted, clients MUST NOT display reactions for it. Reactions targeting such a Message are silently ignored on render.

**Reactions and compliance logging.** Reactions are logged by the compliance logger identically to Messages: they are MLS application messages and the logger holds group membership.

#### 5.2.8.4 Custom Emoji

Spaces MAY define custom emoji: space-specific images referenced by name. A custom emoji is a JMAP Chat `CustomEmoji`, declared in the CO-signed space state document.

**Space state declaration:**

```json
"customEmoji": [
  {
    "id": "01J3XP0A1B2C3D4E5F6G7H8J9K",
    "name": "example_logo",
    "blobId": "bafyrei...",
    "createdBy": "did:key:z6MkAdmin...",
    "createdAt": "2026-03-12T00:00:00Z"
  }
]
```

`name` follows the JMAP Chat rules and on Agora MUST be at most 32 characters. `blobId` is the CID of the image file, which MUST be `image/png`, `image/gif`, or `image/webp`. Images SHOULD be square and SHOULD be 64×64 or 128×128 pixels.

**Custom emoji reactions:**

A Reaction using a custom emoji sets `customEmojiId` to the emoji's `id` and `emoji` to the reference string:

```json
"emoji": ":space:example_logo:"
```

Clients resolve `customEmojiId` against the current space's `customEmoji` array, fetch the image at `blobId`, and render it inline. Clients that cannot resolve it MUST display the `emoji` string `:space:example_logo:` as a fallback.

**Custom emoji in message text:**

Custom emoji MAY appear inline in a Message `body` using the `:space:<name>:` reference syntax. Clients resolve and render them inline alongside the surrounding text.

**Custom emoji management:**

Adding or removing a custom emoji is a signed `SpaceState` mutation by a Space Admin or Owner. The `customEmoji` array in the space state document is the authoritative list. Removing a custom emoji from the array does not delete the IPFS content, but clients MUST stop rendering it after the next space state refresh.

Spaces SHOULD send relay pin instructions (§5.2.6) for custom emoji image CIDs to prevent relay eviction.

---

## 5.3 Presence and Ephemeral State

*Binds: CO.*

### 5.3.1 Presence

Presence is a JMAP Chat `ChatPresenceEvent` (draft-atwood-jmap-chat-wss-00) sent as an MLS application message (`PrivateMessage`, §5.2.3) of type `urn:ietf:params:jmap:chat:websocket#ChatPresenceEvent` inside an ordinary routing envelope on `v1/agora/channel/<channelToken>`. Nothing about presence is visible to relays beyond an ordinary envelope. Body:

```json
{
  "presence": "online",
  "lastActiveAt": "2026-03-12T12:00:00Z",
  "statusText": null,
  "statusEmoji": null
}
```

`contactId` is not carried; the receiver sets it to the MLS sender's DID before handing the event to a local JMAP client. `presence` takes the JMAP Chat values, and a client whose own presence is `"invisible"` sends `"offline"`, as draft-atwood-jmap-chat-wss-00 requires.

A client MUST re-send its `ChatPresenceEvent` every 30 seconds while its state is unchanged, matching the JMAP Chat presence rate limit. Recipients treat a sender from whom no `ChatPresenceEvent` has arrived for 60 seconds as `"offline"`.

### 5.3.2 Typing Indicators

Typing is a JMAP Chat `ChatTypingEvent` (draft-atwood-jmap-chat-wss-00) sent as an MLS application message (`PrivateMessage`, §5.2.3) of type `urn:ietf:params:jmap:chat:websocket#ChatTypingEvent` inside an ordinary routing envelope on the channel topic, so relays see only an ordinary envelope, and it is never written to persistent storage. Body:

```json
{
  "typing": true
}
```

`chatId` and `senderId` are not carried; the receiver sets them from the carrying group and the MLS sender. A client sends at most one `ChatTypingEvent` per 3 seconds per Chat while its user is typing, and sends `"typing": false` when typing stops. A client that receives no `ChatTypingEvent` from a sender for 10 seconds SHOULD clear the typing indicator for that sender, as the JMAP Chat specification recommends.


---

