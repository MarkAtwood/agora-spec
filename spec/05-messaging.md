# 5. Messaging

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 1066–1831 (§5–7).

## 5.1 Message Ordering

*Binds: both.*

### 5.1.1 Ordering Model

Agora uses **best-effort causal ordering**. Gossipsub does not guarantee total message order and does not need to. The requirement is that messages arrive in approximately the right order on average, with clients able to reconstruct causal order locally.

Each non-ephemeral inner payload carries a `seq` inside the ciphertext (§5.2.2). `seq` is counted per sending device (MLS leaf) per channel: it starts at 0 when the device's leaf joins the group, increases by one with each non-ephemeral message the device sends in that group, is not reset when the epoch changes, and stays below 2^53. Ephemeral events (§5.2.3) carry no `seq` and do not consume a value. A JMAP Chat `Message` (§5.2.3) refers to earlier Messages by `senderMsgId` in `replyTo` and `threadRootId`, and edits, deletions and reactions name their target Message the same way (§5.2.2). This gives clients enough information to:

- Detect gaps (missing `seq` values from a given sending device)
- Buffer out-of-order arrivals and flush the buffer when gaps close
- Detect and display causal relationships for reply threading and reaction targets

Clients order Messages by this model. `sentAt` is the sender's claim and MUST NOT be used for ordering, as the JMAP Chat specification (draft-atwood-jmap-chat-00) requires; `receivedAt` in a member's store records when that store applied the Message.

Clients SHOULD buffer messages for up to 500ms waiting for a gap to close before rendering out-of-order. After 500ms, the client should display what is available and backfill visually when the missing message eventually arrives.

**MLS Commit ordering.** MLS Commits (which advance the group epoch) require stricter ordering than application messages. Clients MUST buffer application messages from a new epoch until the Commit that opened that epoch has been received and processed.

**Canonical Commit.** RFC 9420 §14 requires an established way to resolve conflicting Commits for the same epoch. When more than one Commit targets the same MLS epoch of a group, exactly one wins, chosen as follows:

- **Space with a sequencer.** If the group is a channel of a Space whose state designates a `sequencer` (§14.4.1), Commits are ordered by the channel's **commit stream**, `SHA-256("agora/commits/v1" || channelToken)` (§14.4.2), of the current admission key. Before publishing a Commit, the committer submits it per §14.4.3 steps 2 and 3, with `stream` set to the commit stream of the `channelToken` of the highest `keyEpoch` it holds, and `op` set to the exact bytes of the `sealedEnvelope` that will carry the Commit in a routing envelope for that `channelToken` (§5.2.2). Commits are stamped only on the current token's commit stream: once the CO registers a rotated key whose registration names the old token in `replaces` (§10.5.3), the sequencer stamps no further Commit on the old token's commit stream, and the rotation's grace period applies only to application messages. A committer whose submission is refused with `stream-closed` fetches the current `ChannelAdmissionKey` (§5.2.2) and resubmits on the new token's commit stream. The first stamp of a new commit stream references the last stamp of the commit stream it replaces (§14.4.2). Before its first submission on a new commit stream, the committer fetches the replaced commit stream to its end from the log (§14.4.4) and processes it as below. The committer then fetches its own stream's log up to its own position (§14.4.3) and publishes the Commit promptly, with the encoded stamp envelope in the `commitStamp` field of the routing envelope's `signed` map, unless a Commit at an earlier position already counts. If the sequencer is unreachable, the committer waits; it MUST NOT publish an unstamped Commit to such a channel.

  A member MUST NOT apply such a channel's Commit unless `commitStamp` verifies per §13.1.1 as signed by the `sequencer` DID in the Space state the member holds, its `stream` is the commit stream of the routing envelope's `channelToken`, and its `opHash` is SHA-256 of the envelope's `sealedEnvelope` bytes. A stamped Commit **counts** only if both of the following hold:

  1. **Published in time.** The `ts` of the routing envelope carrying it (§5.2.2) is no more than 10 seconds after the `ts` of its stamp (§14.4.2).
  2. **Valid.** It opens under the epoch's sealing key (§5.2.2), decrypts, and is a well-formed Commit for that epoch that passes RFC 9420 §12.4.2 validation and the checks of §5.2.1, made by a sender authorized for every change it makes under current Space state (§4).

  Every member skips a stamped Commit that does not count, and its position has no effect on later Commits. Members process the stamped Commits for one epoch in stamp order (§14.4.2) and apply the first that counts. Because a counting Commit at an earlier position can arrive after one at a later position, a member keeps its epoch N state until 15 seconds after the stamp `ts` of the Commit it applied for epoch N, and switches to a counting Commit at an earlier position that arrives in that time; it discards Commits for epoch N that arrive later. The committer's own Commit has won when it counts and no counting Commit at an earlier position has arrived by that time. A member that sees a stamped Commit fail the validity check treats its sender as misbehaving, as for any message that fails MLS processing.
- **No sequencer.** Otherwise, including in every DM group, a member that receives a Commit for epoch N keeps its epoch N state and collects every Commit for epoch N that arrives within 5 seconds of the first. It then applies the Commit whose envelope `id` (§5.2.2) is lowest, compared as bytes, and discards Commits for epoch N that arrive later. The committer applies the same rule to its own Commit, counting from when it published it. A Commit delayed by more than the window at some members but not others splits the group; members left on the losing branch cannot process later traffic and must be removed and re-added. A Space avoids this by designating a sequencer.

A committer MUST NOT deliver the Welcome for an Add in its Commit until that Commit has won (RFC 9420 §14). A client whose Commit lost discards it and its pending state, and, if the change is still wanted, re-proposes it as a new Commit for the winning epoch.

**Space state ordering.** Space state is one signed chain (§3.3), and each state document carries a `seq` field. Two valid state documents that name the same `prevStateCID` fork the chain. Every client resolves a fork by the same rule, applied to the two documents that follow the fork point: the one with the higher `seq` wins; on equal `seq`, the one signed by the owner wins over one signed by an admin; otherwise the one whose CID is lower, compared as bytes, wins. Clients follow the winning branch, and the Space endpoint serves its head (§3.4). State on the losing branch has no effect. A signer whose mutation lost re-signs it, if it is still wanted, as a new state document on top of the winning head. Clients MUST NOT merge two branches into one state, since a merged state has no signer (§3.3).


---

## 5.2 Messaging

*Binds: both.*

### 5.2.1 MLS Group Structure

Each channel's encryption model is determined by its **mode** (§3.2). `interactive` and `community` channels each have their own MLS group; a `broadcast` channel has no MLS group and carries content encrypted under a CO-distributed channel content key. In all cases, space membership does not imply channel membership; each channel manages its own state independently.

This section covers `interactive` and `community` channels. `broadcast` channels are specified in §5.2.1.4.

**`interactive` mode** (§3.2): full MLS group, all channel members hold leaves. Maximum 200 members. Standard §5.2.1 behavior applies without modification.

**`community` mode** (§3.2): MLS group limited to active speakers. The Space endpoint serves the channel's admission key, from which the `channelToken` is derived, to every member whose role covers the channel (§3.4), so those members can follow the channel's envelopes at relays; only the speaker group can decrypt them. See §5.2.1.2.

Each channel manages its own MLS epoch independently. This enables per-channel access control (e.g., private channels within a public space) without any additional mechanism; it is a direct consequence of the MLS design.

**Ciphersuite.** All MLS groups in Agora MUST use `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519` (0x0001), matching Ed25519 DID identity keys. A group's declared ciphersuite is this value unless a future revision of this specification defines another.

MLS operations follow RFC 9420 exactly:

- **`KeyPackage`:** published to the user's `KeyPackageEndpoint` (§5.2.1.1); single-use, and rotated on each new device session and after each use. Each KeyPackage's `init_key` and its leaf `encryption_key` are fresh X25519 key pairs generated for that KeyPackage alone, distinct from each other (RFC 9420 §10.1). They MUST NOT be derived from, or equal to, the DID's `keyAgreement` key or any other long-term key; the `keyAgreement` key serves only out-of-group HPKE.
- **`Welcome`:** delivered by POST to the new member's `KeyPackageEndpoint` (§4.6); never on a gossip topic. A Welcome MUST include the `ratchet_tree` extension (RFC 9420 §12.4.3.3) carrying the full ratchet tree. A joiner MUST obtain the ratchet tree only from that extension and MUST NOT fetch it from a relay or any other IO; no IO stores or serves ratchet trees or other MLS group state. A joiner MUST reject a Welcome that lacks the `ratchet_tree` extension.
- **`Commit`:** a state-advancing operation (Add, Remove, Update); published on the channel's topic in a routing envelope (§5.2.2) and resolved against concurrent Commits by the canonical Commit rule (§5.1.1).
  A routing envelope carrying a Commit MUST fit the 65536-byte envelope limit (Appendix C). A committer whose Commit would exceed it MUST split the membership changes across successive Commits, each of which fits; Welcomes are delivered to `KeyPackageEndpoint`s over HTTPS (§4.6) and are not subject to this limit.
- **`Proposal`:** a pre-commit operation that may be included in a subsequent Commit by any authorized member.

**Group configuration.** Every Agora MLS group uses these settings:

- `group_id` is 32 random bytes chosen by the group's creator.
- A group has at most 4096 leaves. A committer MUST NOT issue a Commit that would exceed it, and members MUST reject one that does. The limit bounds the use of the sealing key (§5.2.2).
- All handshake and application messages are sent as `PrivateMessage`. Members MUST reject a `PublicMessage`.
- External joins and external senders are not used. Members MUST reject a Commit or Proposal whose sender type is `new_member_commit`, `new_member_proposal` or `external` (RFC 9420 §6), MUST NOT include the `external_senders` extension in a GroupContext, and MUST NOT publish a GroupInfo carrying `external_pub`.
- A KeyPackage's `lifetime` spans at most 90 days.
- Senders SHOULD pad each `PrivateMessage` (RFC 9420 §6.3.1) so that its content length is a multiple of 256 bytes.
- A member keeps the decryption keys of at least 32 generations behind the newest it has used for each sender in an epoch, and accepts messages up to 1000 generations ahead.

The **Delivery Service** role (RFC 9750) is performed by the relays in combination with each user's `KeyPackageEndpoint` (§5.2.1.1). The **Authentication Service** role (RFC 9750) is performed by DID verification. Each leaf carries a `basic` credential (RFC 9420 §5.3) whose `identity` is the UTF-8 encoding of the member's DID. For `did:webvh` and `did:plc`, its `signature_key` MUST be the raw 32-byte Ed25519 public key of a verification method listed under `authentication` in that DID's current DID document, which is the device key of §2.2. For `did:key`, the `signature_key` is a key the device generated for itself and MUST NOT be the identity key, because RFC 9420 requires each leaf's signature key to be unique within a group and every device of a `did:key` user holds the same identity key (§2.1). Such a leaf MUST carry the `agora_device_binding` LeafNode extension, extension type 0xF0A1 from the RFC 9420 private-use range, whose data is the 64-byte Ed25519 signature (RFC 8032), made with the identity key, over the UTF-8 bytes of `agora/v1/device-binding` followed by the 32-byte `signature_key`; the signature verifies under the key the DID encodes. The leaf signature covers the extension. Every Agora client lists 0xF0A0 (`agora_admission_host`, §4.6) and 0xF0A1 in its leaf `capabilities.extensions`. A device binding cannot be revoked (§2.1). A member MUST check this binding for the leaf of every KeyPackage it adds, for every leaf in an Update or UpdatePath it processes, and, as a joiner, for every leaf in the ratchet tree of a Welcome. A leaf that fails the check makes the carrying KeyPackage, Commit or Welcome invalid.

**Reference implementations for MLS (RFC 9420):**
- Rust: [`openmls`](https://github.com/openmls/openmls) (the most complete open-source implementation)
- C/C++: [`mlspp`](https://github.com/cisco/mlspp) (Cisco)

#### 5.2.1.1 KeyPackage Store

A user's KeyPackages are held by whoever runs the user's identity: the employer's provisioning service (§2.5) for an employee, or a host the user chooses or runs for an individual. The client publishes KeyPackages to, and a committer fetches them from, the user's `KeyPackageEndpoint`. For `did:webvh` and `did:plc` the endpoint is a `KeyPackageEndpoint` service entry in the DID document; for `did:key` it is published in the user's Pkarr record (§2.1). Welcomes are delivered by POST to the same endpoint (§4.6). Relays and other IOs store and serve no KeyPackages.

The host MUST make a fetch atomically consume the returned KeyPackage, and MUST verify that each published KeyPackage's leaf credential and signature belong to the endpoint's DID. A committer MUST obtain a KeyPackage only by fetching it from the target's `KeyPackageEndpoint`. A client MUST NOT publish any message on a gossip topic that names the target DID or the requesting DID to solicit KeyPackages.

**Why single-use.** KeyPackages are consumed exactly once. RFC 9420 assumes each KeyPackage's init key is used for one Welcome; reuse lets two groups share HPKE init secrets and lets a replayed Welcome be accepted. A known failure mode is a store that hands out KeyPackages without consuming them, keeps them only while the owning device is connected (so they vanish on disconnect), and keys them to an unstable per-session device identifier, so that adding a user's other devices silently fails. Agora's endpoint avoids this: consumption is atomic and permanent, supply persists independent of connection state, and supply is keyed to the owning DID.

**Last-resort KeyPackages.** A client SHOULD also publish one last-resort KeyPackage (`draft-ietf-mls-extensions-09`, §last-resort-keypackage) per device, which the host returns, without consuming it, only when no single-use KeyPackage remains.

##### Endpoint Protocol

For `did:webvh` and `did:plc`, the `KeyPackageEndpoint` is the DID document service entry whose `type` is `AgoraKeyPackageEndpoint` (§2.1). For `did:key` it is the `url` value of the `_kp._agora` record (§10.3.4.6). In both cases it is an HTTPS URL for one DID, with a path that begins with `/v1/agora/kp/` (§13.2). Relative to that URL, written `{kp}`:

```
GET  {kp}                 fetch one KeyPackage per device, consumed atomically
GET  {kp}?leaf=<key>      fetch one KeyPackage of one device, consumed atomically
POST {kp}                 publish KeyPackages
POST {kp}/welcome         deliver a Welcome
POST {kp}/auth            authenticate the caller (§3.5), where the host requires it
```

- **Fetch.** The request carries no caller identity, unless the host gates fetches by sender (§4.6.3): such a host answers an unauthenticated fetch or Welcome POST with HTTP 401, and the caller authenticates by the §3.5 exchange at `{kp}/auth` and repeats the request with the bearer token. Each of the DID's devices is a separate leaf (§2.2), so one fetch returns one KeyPackage for each device that has any supply: for each device, a single-use KeyPackage if one remains, otherwise that device's last-resort KeyPackage. The response body, media type `application/cbor`, is a CBOR array of byte strings, each one `MLSMessage` with `wire_format` `mls_key_package` (RFC 9420 §6). A committer adding the user adds every returned KeyPackage. If no device has supply the host returns HTTP 404. A rate-limited caller receives HTTP 429. With the `leaf` query parameter, the unpadded base64url of a leaf `signature_key`, the host returns a one-element array holding a KeyPackage of only the device whose leaf carries that key, and HTTP 404 if that device has no supply; an existing device uses this to add a new device of the same user (§2.6) without consuming the KeyPackages of the user's other devices.
- **Publish.** The request body is a typed payload envelope (§13.1) of type `urn:agora:type:KeyPackagePublish`, signed per §13.1.1 by a device key of the endpoint's DID (for `did:key`, the identity key). Its body is:

```json
{
  "keyPackages": ["base64url...", "base64url..."],
  "lastResort": "base64url...",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

`keyPackages` are encoded `MLSMessage` KeyPackages added to the single-use supply, each in base64url without padding (RFC 4648 §5), as is `lastResort`. `lastResort` is optional; it replaces the last-resort KeyPackage of the device whose leaf it carries. The host MUST reject a request whose `ts` differs from its clock by more than 300 seconds, MUST reject any KeyPackage it has stored before, so that a replayed request cannot restore consumed KeyPackages, and MUST apply the checks above to each KeyPackage. It returns HTTP 204 on success.
- **Welcome.** The request body is one `MLSMessage` with `wire_format` `mls_welcome`, media type `message/mls`. The host returns HTTP 202 and holds the Welcome for the DID's devices. How a device collects Welcomes from its own host is a matter between the device and the host.

##### KeyPackage Exhaustion

The host rate-limits fetches to prevent a caller from draining a user's supply, and falls back to the last-resort KeyPackage when single-use supply runs out. If neither is available, the committer MUST NOT reuse a previously consumed KeyPackage; it queues the Add locally and retries the fetch with backoff. The client replenishes its supply at the host when it next comes online.

##### KeyPackage Validation

A committer MUST validate each KeyPackage before adding it (RFC 9420 §10.1), and every member processing the Commit MUST validate the KeyPackages it adds:

- The KeyPackage signature verifies under its leaf `signature_key`, and the leaf credential binds that key to the DID whose `KeyPackageEndpoint` served it (§5.2.1).
- The KeyPackage is within its `leaf_node.lifetime`.
- The ciphersuite matches the group's declared ciphersuite.
- `init_key` differs from `leaf_node.encryption_key`.
- The leaf `capabilities.extensions` lists 0xF0A0 and 0xF0A1 (§5.2.1).

A member MUST reject a Commit that adds a KeyPackage failing these checks. A joiner MUST validate the ratchet tree of a Welcome as RFC 9420 §12.4.3.1 requires, including the credential binding for every leaf, and MUST reject the Welcome if it fails.

#### 5.2.1.2 Community Channel Mode

A `community` channel has a bounded MLS group called the **speaker group**. Only members of the speaker group can post or decrypt messages. Every Space member whose role covers the channel is served its admission key (§3.4, §5.2.2) and can subscribe to its envelopes, but a member outside the speaker group cannot decrypt them, and envelopes it publishes fail MLS processing at every member. The speaker group bounds decryption only; relay admission covers every role holder.

**Speaker group bounds.** The `speakerCap` field in the channel state (default 200, maximum 500) is the hard upper limit on simultaneous MLS group members. A channel admin MUST NOT issue an Add commit that would push membership above `speakerCap`.

**Idle eviction.** A speaker who has not sent any `ApplicationMessage` in the channel within `idleEvictDays` days (default 7) is eligible for eviction. The channel's designated **SpeakerBot** (a DID listed in the channel state as `speakerBot`) issues periodic Remove commits for idle speakers. If no `speakerBot` is configured, channel admins perform evictions manually. Eviction is not punitive: evicted members are eligible for immediate re-admission when they next request to speak. An idle eviction removes the speaker from the MLS group only; the evicted member's role still covers the channel, so the CO does not rotate the admission key for it.

**SpeakRequest.** A space member who is not currently in the speaker group and wants to post sends a `SpeakRequest` as an MLS application message in a DM group (§4.6) with the channel's `speakerBot`, or with a channel admin if no `speakerBot` is configured. The requester holds no key for the speaker group, so the request cannot travel in the channel's own envelopes; it MUST NOT be sent in the clear on any topic. The requester's identity is the MLS sender of the DM group message, authenticated by the MLS signature (§5.2.2), so the inner payload, an envelope of type `urn:agora:type:SpeakRequest` (§5.2.3), carries only the channel:

```json
{
  "channelID": "base64url...",
  "ts": "2026-04-22T09:00:00Z"
}
```

`channelID` is the channel's 16-byte identifier from Space state (§3.3), in base64url without padding (RFC 4648 §5). The SpeakerBot or a channel admin responds by issuing a standard MLS Add commit using a KeyPackage fetched from the requester's `KeyPackageEndpoint` (§5.2.1.1). If the speaker group is at capacity, the SpeakerBot SHOULD first evict the longest-idle current speaker before adding the requester.

**Admission latency.** Admission requires one round of MLS Add + Welcome delivery. Clients in `community` channels SHOULD display a "waiting to join" indicator if the user tries to post before their Welcome has been processed.

**History access.** A member who was evicted and later re-admitted receives a new Welcome for the new MLS epoch. They can decrypt messages from epochs in which they held a leaf node; they cannot decrypt messages sent during periods when they were not in the group. This is the correct behavior: they were not a group member during those periods. Clients SHOULD display a clear indicator when history is unavailable for a given time range.

**Compliance logging.** Compliance loggers (§7) in `community` channels are passive members (§5.2.1.3) and MUST NOT be subject to idle eviction. The SpeakerBot MUST check for a passive member leaf before evicting any member.

#### 5.2.1.3 Passive Members

A **passive member** is an MLS group member that holds a leaf credential and participates in epoch ratchets (receiving all application messages and group state updates) but MUST NOT issue Proposals or any Commit other than the scheduled self-update below. Passive members are indistinguishable from standard members at the MLS wire protocol layer; the constraint is behavioral, not cryptographic.

**Use cases in Agora.** Compliance loggers (§7) and VTC recorders (§6.12) are passive members. Both hold leaf credentials, receive all application messages in their admitted groups, and never change group membership.

**Scheduled self-update.** A passive member SHOULD issue a self-update Commit in each of its groups on a fixed schedule, for example weekly. A self-update Commit is a Commit with no proposals and with an UpdatePath (RFC 9420 §12.4), so it changes the passive member's own leaf and nothing else. It always replaces the leaf HPKE key, and it MAY also replace the leaf signature key when the logger or recorder rotates that key (§7.9); the new signature key MUST satisfy the credential binding of §5.2.1. Without it, a passive member's leaf HPKE key would never change, and one compromise of that key would expose the path secrets of every later Commit in every group it belongs to; the self-update restores post-compromise security for its leaf (§12.2). The self-update is subject to the canonical Commit rule (§5.1.1) like any Commit.

**KeyPackages.** Passive members require KeyPackages to receive Welcome messages, and the single-use rule of §5.2.1.1 applies to them without exception. A compliance logger or recorder is added to many groups, so serving it a reused last-resort KeyPackage would give all of those groups the same HPKE init key. It runs as an always-on service whose `KeyPackageEndpoint` is hosted by its own CO, which can keep its single-use supply replenished; its endpoint MUST return a fresh, unused KeyPackage on every fetch (§7.8.2).

**Idle eviction.** Passive members MUST NOT be subject to idle eviction (§5.2.1.2). A passive member generates no traffic by design; evicting one on that basis would silently break the compliance capture chain.

**Future standard alignment.** This concept anticipates `draft-ietf-mls-partial-00` ("Partial MLS"), which defines an MLS extension allowing receive-only participants to carry only membership proofs rather than the full ratchet tree, reducing overhead for large groups. That draft expired without a successor. When a partial client standard is published, Agora implementations SHOULD upgrade passive member implementations to native partial client support; the behavioral contract (no Proposals, no Commits other than scheduled self-updates, full message receipt) is identical.

#### 5.2.1.4 Broadcast Channel Mode

A `broadcast` channel is a one-to-many CO publication. Posts are encrypted under a channel **content key** that the CO distributes (§3.4) and are signed inside the ciphertext by the poster. The outer envelope reveals no sender. The properties provided are authenticity (was this posted by an authorized poster?) and confidentiality against IOs and non-members, without MLS forward secrecy (see Security properties below).

**Authorized posters.** The set of authorized posters for a broadcast channel is determined by space role: any space member holding a role listed in the channel state's `broadcasterRoles` array may post. Typically this is a dedicated `broadcaster` role held by admins or a bot.

**Keys.** A broadcast channel has no MLS group. It uses the channel admission mechanism of §5.2.2 with one addition, the content key, and the CO issues the two together: each rotation produces a `ChannelAdmissionKey` and a `BroadcastKey` (§3.4) with the same `keyEpoch`, both served by the Space endpoint. The Space endpoint serves the complete `ChannelAdmissionKey`, including its private key, only to holders of a role in `broadcasterRoles`, so only posters can sign envelopes that relays admit. To subscribers it serves the `ChannelAdmissionKey` without the private key: this form carries the `channelToken` and lets a subscriber follow the channel but not post to it. For a channel with `keyAccess: public`, the `BroadcastKey` and the subscriber form of the `ChannelAdmissionKey` are public Space state, so whether a broadcast channel is private or public is an access policy on the same mechanism. `keyAccess: public` is allowed only in a public Space (§3.4); a private Space has no public broadcast channels. Publishing the `channelToken` lets any IO map that token, and the CO billing DID it is registered under, to the Space and channel, an accepted cost (ARCHITECTURE §9). A poster MUST encrypt under the `BroadcastKey` with the highest `keyEpoch` whose `notBefore` has passed (§12.9) and MUST sign the envelope with the admission key of the same `keyEpoch`. Posters and subscribers fetch both keys whenever §5.2.2 requires a member to fetch the admission key.

**Message structure.** Broadcast messages use the routing envelope of §5.2.2. Its `signed` map carries `broadcastPayload` in place of `sealedEnvelope`:

```
broadcastPayload = nonce || AEAD-Seal(key, nonce, plaintext, aad = "agora/broadcast/v1" || channelToken)
```

The AEAD is that of the default ciphersuite (§5.2.1), AES-128-GCM. `nonce` is 12 bytes, freshly random for every message; because many posters share one key, counter nonces are not used. Recipients MUST reject a `broadcastPayload` whose associated data does not match the `channelToken` of the envelope it arrived in. `plaintext` is one typed payload envelope (§13.1) of type `urn:agora:type:BroadcastMessage` with `sig` present. Its body binds a JMAP Chat `Message` (§5.2.3) to the channel, key epoch and poster:

```json
{
  "channelID": "base64url...",
  "keyEpoch": 7,
  "senderDID": "did:key:z6Mk...",
  "device": "base64url...",
  "seq": 311,
  "message": {
    "senderMsgId": "01J3XM2C4V0Q6R9T8Y7W5E3B1A",
    "body": "v2.1.0 released; see release notes for details.",
    "bodyType": "text/markdown;variant=commonmark",
    "sentAt": "2026-04-22T09:00:00Z"
  }
}
```

`channelID` is the channel's identifier (§3.3) in base64url without padding (RFC 4648 §5). `device` is 16 random bytes, in base64url without padding, that the posting device chooses once for the channel and uses for all its posts there; it distinguishes devices that share one signing key, as every device of a `did:key` user does (§2.1). `seq` is the poster's per-channel sequence number (§5.1.1), counted per (`kid` of `sig`, `device`) pair because a broadcast channel has no leaves. `message` carries the fields of a new Message as defined in §5.2.2. There is no MLS group, so no MLS sender signature covers the payload; `sig` is the poster's JWS, signed per §13.1.1. Recipients MUST verify `sig` per §13.1.1 with the DID of its `kid` equal to `senderDID` before displaying the message, MUST verify that `channelID` and `keyEpoch` match the key used to decrypt, and MUST verify that `senderDID` is an authorized poster. A member checks that `senderDID` holds a space role listed in `broadcasterRoles` under current Space state. A subscriber that is not a member cannot see roles, since the public view of Space state omits `members` (§3.3); it checks instead that `senderDID` is listed for the channel in `broadcasters`, below.

**Broadcasters list.** For every channel with `keyAccess: public`, the CO publishes in the public view of Space state (§3.3, §3.4) a `broadcasters` list, an array with one `{channelID, dids}` entry per such channel: `channelID` is the channel's identifier and `dids` lists the DIDs that currently hold a role in its `broadcasterRoles`. Because `keyAccess: public` is allowed only in a public Space (§3.4), only a public Space's view carries the list. The list is part of the signed public view and changes with it. A non-member subscriber MUST NOT display a post whose `senderDID` is not listed for the channel in the newest `broadcasters` list it holds.

**Relay handling.** The Relay stores broadcast messages as ciphertext blobs, identical to any other channel message. It learns a `channelToken`, an admission signature that does not identify the signer, a timestamp and an opaque blob, and nothing about who posted. For a `keyAccess: public` channel it can also map the token to the Space and channel, because the CO publishes the token (ARCHITECTURE §9). Clients MUST display a visible indicator (e.g., a megaphone icon, with a text equivalent per §12.10) on broadcast channels to make clear to users that the channel has the weaker properties stated below.

**Rotation and removal.** To remove a subscriber or a poster, the CO issues a new `BroadcastKey` and `ChannelAdmissionKey` with `keyEpoch` incremented, registers the new admission key with every IO whose ServiceAgreement `serviceType` receives admission key registrations (§10.5.1) and deregisters the old one (§10.5.3), and stops serving keys to the removed party (§3.4). The CO SHOULD also rotate at least every 30 days, and MUST rotate before 2^32 messages have been encrypted under one content key (the AES-GCM limit for random nonces).

**Security properties.** A broadcast channel provides confidentiality against IOs and non-members, and sender authenticity through the inner signature. It is weaker than MLS: there is no forward secrecy or post-compromise security within a key epoch, since one key protects every message of that epoch; a removed subscriber retains the keys of the epochs it held and can read their messages; and any key holder can decrypt the whole epoch. The admission key only gets a poster's envelopes past relays; the inner signature, checked against `broadcasterRoles`, is what authorizes a post to recipients. This is appropriate for one-to-many announcements; channels that need MLS properties MUST use `community` or `interactive` mode.

**KeyPackage consumption.** A broadcast channel consumes no KeyPackages: it has no MLS group, and no poster or subscriber receives a Welcome or Commit for it.

**Compliance logging.** The compliance logger needs no group admission. It obtains each `BroadcastKey` and the subscriber form of each `ChannelAdmissionKey` from the Space endpoint as a member (§3.4), follows the channel's tokens, and decrypts. For FINRA/MiFID purposes, broadcast messages in a space with compliance logging enabled are automatically captured to the compliance archive.

### 5.2.2 Message Format

All messages use a two-layer structure: an outer **routing envelope** visible to Relays, and an inner **sealed envelope** that hides the MLS framing from Relays. The inner payload is MLS-encrypted, except in `broadcast` channels, whose payload is encrypted under the channel content key instead (§5.2.1.4).

#### Outer Routing Envelope

The routing envelope contains only what Relays need to admit and route a message. It does not contain the sender's DID. It is a CBOR map (RFC 8949) with two required members and one optional member. `signed` is a byte string holding the CBOR encoding of the routing fields, and `admissionSig` signs exactly those bytes. `powProof` carries a per-envelope proof of work where one is required (§10.5.2). No party re-encodes anything to verify the signature or to compute the envelope's `id`. The routing envelope has no JSON form; every transport carries it as CBOR (§11).

```cddl
RoutingEnvelope = {
  "signed": bstr .cbor SignedFields,
  "admissionSig": bstr .size 64,
  ? "powProof": PowProof,        ; §10.5.2
}

SignedFields = {
  "ctx": "agora/envelope/v1",
  "channelToken": bstr .size 32,
  "ts": uint,
  ? "expiryHint": uint,
  ? "commitStamp": bstr,
  ( "sealedEnvelope": bstr // "broadcastPayload": bstr ),
}
```

- `ctx` is a fixed string that separates envelope signatures from anything else signed with an admission key.
- `channelToken` is the channel's routing token for the current admission key (Channel Admission, below). Relays route by it without learning the channel identifier or any member identity.
- `ts` is the sender's clock in milliseconds since the Unix epoch. Relays use it for TTL enforcement. `admissionSig` covers it, so a relay knows that some holder of the admission key set it, but not which member did; clients MUST NOT use it for application-level ordering (use the inner `seq`, §5.1.1).
- `expiryHint`, in milliseconds since the Unix epoch, is set by the sender to match the `senderExpiresAt` of the inner `Message` (§5.2.4). Relays use it as a cache TTL hint only. It is authenticated in the same weak sense as `ts`.
- `commitStamp` is present only on an envelope that carries a Commit for a channel whose Space designates a sequencer: the encoded `SequenceStamp` envelope (§14.4.2) obtained under the canonical Commit rule (§5.1.1).
- `sealedEnvelope` is the sealed MLS message (Sealed Envelope, below). `broadcastPayload` replaces it in `broadcast` channels (§5.2.1.4).
- `admissionSig` is an Ed25519 signature (RFC 8032) under the channel's admission private key over the exact bytes of `signed`.
- `powProof` is present when the Relay's `minPowDifficulty` or the channel's `powPolicy` requires proof of work (§10.5.2). It lies outside `signed` because it is computed over the `signed` bytes; the envelope `id` does not cover it.

A relay verifies `admissionSig` over the `signed` bytes with the admission public key registered for the `channelToken` those bytes carry, and admits or drops the envelope by the rule of §10.5.4. Relays MUST store and forward the encoded routing envelope exactly as received.

The envelope **`id`** is the CIDv1 of the content of the `signed` byte string (the encoded `SignedFields`), using the `raw` codec (0x55) and a SHA2-256 multihash. It is not carried in the envelope. `admissionSig`, `powProof` and the encoding of the outer map are not part of it, so a party that forwards an envelope cannot change its `id` without the admission key, and every holder of the same `signed` bytes computes the same `id`. Relays still store and forward the complete envelope. It is used for deduplication, history indexing (§5.2.5), pin instructions (§5.2.6) and the canonical Commit rule (§5.1.1). Where an `id` is written as text, it is in CID text form (§13.1).

#### Channel Admission

Relays admit an envelope only if it is signed with the channel's current admission key, which only current members hold, and they learn nothing about which member signed it (ARCHITECTURE §6.2).

- **Admission key.** For each channel, the CO's registration service generates a random Ed25519 key pair, the **channel admission key**, numbered by `keyEpoch` from 0. It registers the public key and its `channelToken` with every IO holding a `ServiceAgreement` with the CO whose `serviceType` receives registrations (§10.5.1), by an `AdmissionKeyRegistration`, and withdraws a key by an `AdmissionKeyDeregistration` (§10.5.3). Neither is gossiped. The Space endpoint serves the private key to authenticated current members of the channel (§3.5) as a `ChannelAdmissionKey` at `<spaceEndpoint>/admission-key/<channelID>` (§3.4). For a DM group, the initiator's identity host issues and registers the key and serves it at `<host>/admission-key/<groupID>` (§4.6). For a shared channel, the home Space's CO issues and registers it (§8). The admission key is independent of MLS: it does not change when the MLS epoch changes.
- **Channel token.** `channelToken = HKDF-SHA256(IKM = seed, salt = "" (zero-length), info = "agora channel token" || keyEpoch, L = 32)`, where `seed` is the 32-byte Ed25519 private key seed (RFC 8032) of the admission key and `keyEpoch` is a big-endian uint64. Members compute it from the `ChannelAdmissionKey`; relays receive it in the registration. It changes when, and only when, the admission key rotates.
- **Member duties.** A member signs every envelope it publishes to the channel with the admission key of the highest `keyEpoch` it holds, and subscribes (§11) to that key's `channelToken`. A client MUST fetch the current `ChannelAdmissionKey` when it joins the channel, on reconnect, after processing a Commit that removes a member, when a relay reports that a `channelToken` is no longer admitted (§11), and at least once an hour while connected. When it obtains a higher `keyEpoch`, it subscribes to the new token and keeps the previous subscription until the relay reports the old token withdrawn, so that it still receives envelopes from members who have not yet fetched the new key. A client retains the `channelToken`s of earlier key epochs in order to fetch history (§5.2.5).
- **Rotation.** The CO rotates the admission key, incrementing `keyEpoch`, when it authorizes the removal of a member from the channel (not on the idle eviction of a speaker from a `community` channel's speaker group, §5.2.1.2), and at other times of its choosing (periodically, or on suspected compromise). It does not rotate on MLS epochs. It registers the new key before it deregisters the old one (§10.5.3); the interval between the two is the window in which a removed member can still have envelopes admitted. When the CO enters into or renews a `ServiceAgreement`, it registers the current key with that IO.
- **Outage.** If the Space endpoint or the registration service is unreachable, relays keep accepting the last registered key and members keep using it. A member removed during the outage can still have envelopes admitted until the CO rotates the key, but it cannot read anything sent after its MLS removal, and its envelopes fail MLS processing at every member.

Because the key is shared, a valid `admissionSig` does not identify the signer. Admission keeps non-members from using relay capacity; it does not authorize content. Recipients authorize content by the MLS sender signature (§13.1.1), and a removed member's envelopes carry none that verifies.

> **Open (agora-pozi.8):** channel admission awaits external cryptographic review.

#### Sealed Envelope (Sender-Sealed, Relay-Opaque)

`sealedEnvelope` is one AEAD ciphertext over the complete serialized `MLSMessage` (a `PrivateMessage` carrying an application message, a Commit or a Proposal, §5.2.1), keyed from the channel's MLS epoch:

```
sealedEnvelope = nonce || AEAD-Seal(key, nonce, MLSMessage, aad)
key            = MLS-Exporter("agora sealed envelope", group_id, Nk)
aad            = "agora/sealed/v1" || channelToken || epoch
```

`MLS-Exporter` is the exporter of RFC 9420 §8.5 for the epoch in which the message is sent, and `group_id` is the MLS group ID of the channel or DM group, as its exporter context. The AEAD and `Nk` are those of the group's ciphersuite (AES-128-GCM, `Nk` = 16). `epoch` is the MLS epoch of the message as a big-endian uint64. Implementations MUST NOT seal with empty associated data.

The routing envelope does not carry the epoch. A recipient opens a sealed envelope by trying the sealing keys of the epochs it holds, newest first, with each epoch's associated data; it keeps the previous epoch's sealing key for 60 seconds after advancing, for envelopes still in flight. An envelope that opens under no key is buffered until the recipient processes its next Commit (§5.1.1), then tried again, and dropped if it still does not open. A recipient MUST reject a sealed envelope that does not open with the `channelToken` of the routing envelope it arrived in, which prevents re-targeting a sealed envelope to another channel or epoch.

**Nonce.** `nonce` is 12 bytes (96 bits) drawn from a cryptographically secure random number generator for every envelope. Every member of an epoch holds the same sealing key, so nonces must not collide across senders. Random nonces need no coordination; a counter or per-sender nonce would need either a shared counter, which members do not have, or a sender-specific value, which would identify the sender to relays in the clear nonce. With random 96-bit nonces, one AES-GCM key MUST NOT seal more than 2^32 messages (NIST SP 800-38D §8.3). No member can count the others' messages, so the limit is enforced per sender: a sending leaf MUST NOT seal more than 2^20 envelopes in one epoch, and a member whose leaf reaches that number MUST issue an Update Commit (for a passive member, its self-update, §5.2.1.3) before sealing more. A group has at most 4096 leaves (§5.2.1), so at most 4096 × 2^20 = 2^32 messages are sealed under one key.

**What the wrapper hides.** MLS framing is visible in the clear: a `PrivateMessage` begins with `group_id`, `epoch` and `content_type`. The wrapper hides the `group_id` value, which Space state carries as `mlsGroupID` (§3.3), so that a relay cannot map the group's traffic to a channel and Space. It also hides the epoch number and the content type. A relay can still recognize envelopes that carry a stamped Commit by their `commitStamp`, and sees envelope sizes and timing.

The plaintext is the serialized `MLSMessage` with no further structure. The wrapper carries no sender DID, ephemeral key or signature of its own: the sender is identified by the MLS sender data, which MLS encrypts, and authenticated by the MLS signature (§13.1.1).

The idea of hiding the sender from the delivery service comes from Signal's Sealed Sender; the construction is different, since sender authentication here is entirely MLS's. A Relay processing this message learns: a `channelToken` (stable for one admission key epoch and not reversible to a channel), an admission signature that does not identify the signer, a timestamp, an expiry hint, the presence of a `commitStamp`, and an opaque encrypted blob. It may link successive key epochs of one channel by the timing of their registration and deregistration (ARCHITECTURE §5 item 6), but it cannot map them to a channel or Space. It learns nothing about who sent the message.

#### Inner Payload (After MLS Decryption)

The `application_data` of every MLS application message is exactly one typed payload envelope (§13.1). The envelope's `type` names the object (§5.2.3) and its `body` holds the object's exact bytes. Inside MLS the envelope of a non-ephemeral message carries one further member, `seq`, the sending device's per-channel sequence number used for gap detection (§5.1.1). It is covered by the MLS signature and invisible to Relays.

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
- An attachment's file is stored as a chunked content-key blob (§14.3.4). The `Attachment` carries the random per-attachment key in its `contentKey` member, an Agora extension of the JMAP Chat `Attachment`, and its `blobId` is the CID of the encrypted file's root block, with `chunkCount` giving its number of chunks; `fetchUrl` is not used. `size` and `sha256` describe the plaintext file. `contentKey`, `chunkCount` and `sha256` travel only inside the encrypted Message and MUST NOT be sent to any IO. The sender uploads the blocks to one Relay of the channel's relay list (§10.4.4).

A receiving client performs the checks that the JMAP Chat federation specification assigns to a receiving server (New Message Validation, Edit and Reaction Validation), evaluating membership, bans and permissions against current signed Space state (§3.3).

### 5.2.3 Message Types

The `type` of an inner payload envelope is one of the values below or a type defined in another section or by an extension (§13.2).

#### Chat objects (JMAP Chat)

Chat content uses the data types and ephemeral events of the JMAP Chat specifications. Agora defines no chat object of its own.

| `type` | Body | JMAP Chat definition |
|---|---|---|
| `urn:ietf:params:jmap:chat#Message` | New Message, edit, or deletion (below) | `Message`, with embedded `Attachment`, `Mention`, `BroadcastMention` and `MessageAction`; rich text per the Rich Body Format |
| `urn:ietf:params:jmap:chat#Reaction` | The fields of the federation `reactionUpdate` object (§5.2.8.2) | `Reaction` |
| `urn:agora:type:JmapSet` with `dataType` `urn:ietf:params:jmap:chat#Chat` | Patch of `pinnedMessageIds` only (§5.2.6) | `Chat.pinnedMessageIds` |
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
| `urn:agora:type:IdentityChanged` | Notice, sent by a user to each of its groups, that its DID document or display profile has changed; members re-resolve the sender's DID and profile (§2.7). The body is an empty JSON object; the MLS sender identifies the user |
| `urn:agora:type:ClientCapabilities` | Ephemeral per-device list of renderable body types (§5.2.7.4) |
| `urn:agora:type:SystemEvent` | Protocol-level event named by its `event` member; this specification defines only `gateway-added` (§9.3) |
| `urn:agora:type:VoiceSignal` | WebRTC SDP offer/answer/ICE candidate, targeted to a specific DID (§6.4) |
| `urn:agora:type:ParticipantState` | Ephemeral call presence (joined/left, muted, video on/off, screen share) (§6.2) |
| `urn:agora:type:RecordingGrant` | Authorization and disclosure record admitting a CO-run recorder to a call (§6.12) |
| `urn:agora:type:RecordingRevoke` | Revocation of a prior `RecordingGrant` (§6.12) |
| `urn:agora:type:JmapSet` | Patch to JMAP-family objects (§14.3.2); for a `sequenced-v1` type, carries the `after` head (§14.4.3) |
| `urn:agora:type:SequencedOp` | A sequencer stamp with the operation it orders (§14.4.3) |
| `urn:agora:type:SequencerFork` | Proof of sequencer equivocation: two conflicting stamps (§14.4.5) |
| `urn:agora:type:DMGroupDescriptor` | Current membership and logger list of a DM group, sent by the committer of each change (§4.6) |
| `urn:agora:type:ComplianceDisclosureNotice` | Notice that a compliance logger has been admitted to a DM group (§7.8.4) |
| `urn:agora:type:AddApproval` | A member's approval of a pending Add Proposal in a DM group (§4.6.1) |
| `urn:agora:type:AbuseReport` | Abuse report sent to a Space owner or admin in a DM group (§4.7) |
| `urn:agora:type:SocialRecoveryConfig` | The user's social recovery configuration, kept in the self-group, with each guardian's entry sent in a DM group (§2.4.2) |
| `urn:agora:type:HistoryTransfer` | Key and location of an encrypted history archive, sent in the self-group to a new device (§2.6) |
| `urn:agora:type:SpaceMembership` | The Spaces the user is a member of, kept in the self-group for the user's devices (§2.6) |
| `urn:agora:type:CallRing`, `CallResponse`, `CallEnd`, `CallSchedule`, `LobbyDecision`, `CallPolicy`, `CallBreakout` | Call coordination (§6.14); each name is prefixed with `urn:agora:type:` |

Ephemeral events (`ChatTypingEvent`, `ChatPresenceEvent`, `ParticipantState`) are MLS application messages sent as `PrivateMessage`, never as `PublicMessage` application data, and are excluded from history storage.

#### Types carried outside MLS application messages

The types below are never sent as an MLS application message. Each is named `urn:agora:type:` followed by the name shown (§13.1).

| Type | Carried | Defined in |
|---|---|---|
| `BroadcastMessage` | Only inside a `broadcastPayload` | §5.2.1.4 |
| `SequenceStamp` | Inside a `SequencedOp` body, in a routing envelope's `commitStamp` (§5.2.2), or returned by the sequencer's endpoint | §14.4.2 |
| `KeyPackagePublish` | HTTPS to the user's `KeyPackageEndpoint` | §5.2.1.1 |
| `MemberAuth` | HTTPS to a CO service | §3.5 |
| `DMMembers` | HTTPS to a DM group's admission host | §4.6 |
| `DeviceKeyRegistrationRequest`, `DeviceRevocationRequest`, `AdminRevocationRequest` | HTTPS to the provisioning service | §2.5.4, §2.5.5 |
| `UserProfile`, `RecoveryAssertion` | Published with or through the user's DID document and log | §2.3, §2.4.1 |
| `SpaceState`, `BanRecord`, `KickRecord`, `KickLift`, `TimeoutRecord`, `SpaceInvite`, `InviteRevocation` | Served by the Space endpoint (§3.4); a `SpaceInvite` is also handed to its invitee | §3.3, §4.3, §4.5 |
| `ChannelAdmissionKey`, `BroadcastKey` | Served by the Space endpoint or a DM group's admission host | §3.4, §4.6 |
| `ChannelShareAgreement`, `ChannelShareRevocation`, `SharedChannelAlias` | Space state records | §8.3, §8.5, §8.7 |
| `ComplianceLoggingConfig`, `ComplianceRecord`, `ComplianceGapEntry`, `DMComplianceAuditEntry`, `ArchiveResealEntry` | Compliance configuration, archive and audit chain | §7.2, §7.4, §7.8.8, §7.8.9, §7.9 |
| `VTCComplianceConfig`, `VTCComplianceRecord`, `VTCComplianceAuditEntry` | Recording configuration, archive and audit chain | §6.12.4 to §6.12.6 |
| `SFUDescriptor`, `TURNDescriptor` | Entries in Space state | §6.6, §6.11 |
| `SfuDescription` | SFU signaling connection | §6.6 |
| `GatewayDescriptor`, `MIMIInteropConfig` | Entries in a channel's Space state | §9.1, §9.2 |
| `ServiceAgreement`, `AdmissionKeyRegistration`, `AdmissionKeyDeregistration` | HTTPS between CO and IO | §10.5.1, §10.5.3 |
| `RelayManifest`, `RelayPeerAnnouncement` | Relay manifest location and relay-to-relay Peer API | §10.2.1, §10.2.6 |
| `SpaceAd`, `RelayAd` | Discovery topic | §10.3.2, §10.5.1 |
| `RelayDirectory`, `SpaceDirectory`, `AgoraDirectory` | Published directories | §10.3.4.1 to §10.3.4.3 |

Compliance records (§7.4) are written by the logger and are not MLS application messages.

### 5.2.4 Message Expiry

Message lifetime is a **sender-side commitment**. The sender sets the JMAP Chat `senderExpiresAt` field of a `Message` (§5.2.3), inside the MLS ciphertext and therefore invisible to Relays. Recipients' clients are bound by protocol to honor it because it is part of the message content authenticated by the MLS sender signature.

Expiry semantics:

- `senderExpiresAt` has the meaning the JMAP Chat specification gives it: each member's store hard-deletes the Message at or before that time and keeps no tombstone. Absence means no expiry (persistent by default). A pinned Message is the one exception (§5.2.6, Message Expiry Interaction).
- Clients send no deletion message on expiry; every member already holds the deadline. Relays drop the cached envelope by `expiryHint`.
- Relays that cache message envelopes MUST respect the `expiryHint` field in the outer `RoutingEnvelope` as a cache TTL. It is covered by `admissionSig`, which shows only that some key holder set it (§5.2.2); Relays use it as a hint only.
- The authoritative expiry is always `senderExpiresAt`, read by recipients after MLS decryption.

### 5.2.5 Message History

Channel history comes from three sources. There is no history chain or index in Space state.

- **Relays.** A relay keeps the envelopes it has admitted for each `channelToken` for the retention period of its `ServiceAgreement` (§10.5.1) and serves them by `channelToken` through the JMAP sync API (§11.8). A client fetches from each `channelToken` it has held (§5.2.2).
- **Members' stores.** Each member's client or daemon keeps the Messages it has received in its own JMAP store (§14.3), and a user's devices can pass history among themselves.
- **CO archive.** A CO MAY archive its channels beyond relay retention, for example through its compliance logger (§7). Beyond that, long-term archival is the responsibility of space operators or interested members.

A client can open a relay-held envelope only while it still holds the keys of that envelope's MLS epoch, so relay history serves catch-up after a client has been offline; older history comes from members' stores or the CO archive. A client that cannot reach the group's current epoch because the Commits it needs have passed relay retention (after a message request is accepted late, §4.6.3, or after any long offline period) deletes its state for the group and tells the user that a member must re-add them (§5.1.1).

History is not chained. Its integrity rests on two properties: the MLS sender signature prevents forgery of any message, and the per-device `seq` (§5.1.1) exposes omission, since a missing message leaves a gap in its sender's `seq`. A history source can withhold envelopes but cannot alter or invent them, and a member detects withholding only through such gaps.

Messages refer to each other by `senderMsgId` (§5.2.2). A client records the envelope `id` (§5.2.2) that carried each Message, so that it can send relay pin instructions (§5.2.6) for that Message. The same envelope held by several relays has the same `id`.

### 5.2.6 Pinned Content

A channel's **pin list** is the JMAP Chat `pinnedMessageIds` property of its Chat, listing pinned Messages by `senderMsgId`. Pinning is a preservation signal: the envelopes of pinned Messages are exempt from relay retention expiry (see Retention Exemption), and clients surface pinned Messages in a dedicated "pinned messages" view. Clients validate pin updates against signed Space and channel state; relays never read them.

#### What Can Be Pinned

Only Messages can be pinned, as in the JMAP Chat specification. A file or an external URL is pinned by pinning the Message that carries it. To preserve an external URL, the pinner saves a copy of the page as an attachment (§14.3.4) and pins a Message that carries it, since URLs rot and CIDs do not.

Pinning does not copy data. It records a reference that tells clients, and through pin instructions tells relays, that the Message must be retained and displayed prominently.

#### Pin List in Channel State

Retired. The pin list is `Chat.pinnedMessageIds` in each member's JMAP store, changed by the pin updates below; channel state carries no `pins` array. Two Agora fields remain in CO-signed channel state (§3.3):

- `pinLimit`: the maximum number of simultaneous pins for the channel. Default is 50. Space Admins may set a different limit. Clients MUST ignore a pin update that would make `pinnedMessageIds` longer than `pinLimit`. Relays do not enforce `pinLimit`.
- `noPin`: a boolean, default false. When true, clients MUST ignore every pin update for the channel (see Message Expiry Interaction).

#### Authorization

Who may change `pinnedMessageIds` in a channel is defined by the JMAP Chat specification: members holding the `"pin"` Space permission. DM groups have no pin list: they have no sequencer, so `Chat.pinnedMessageIds` is read-only in them (§14.4.1), and clients MUST ignore pin updates in a DM group. Clients evaluate this against current signed Space and channel state (§3.3) and MUST ignore pin updates that fail it. Only current MLS group members can produce pin updates at all; relays admit them only with a valid `admissionSig` (§5.2.2).

#### PinEvent and UnpinEvent

Retired. A pin or unpin is a `JmapSet` patch (§14.3.2) on the channel's `Chat` that sets `pinnedMessageIds` to the complete new list:

```json
{
  "dataType": "urn:ietf:params:jmap:chat#Chat",
  "at": "2026-03-12T12:00:00.000Z",
  "after": { "stream": "base64url...", "n": 40, "hash": "base64url..." },
  "update": {
    "chat": {
      "pinnedMessageIds": ["01J3XM2C4V0Q6R9T8Y7W5E3B1A", "01J3XKZQN4MWVT8PPBEHTJ3HX0"]
    }
  },
  "destroy": []
}
```

The `update` key `chat` names the Chat of the group that carries the message (§14.3.2). A pin update MUST patch only `pinnedMessageIds`. Several members may write the list, so `Chat.pinnedMessageIds` is written under the `sequenced-v1` consistency model (§14.2.3) and ordered by the Space's blind sequencer (§14.4); it therefore exists only in channels of a Space that designates one, never in a DM group. A client MUST submit a pin update per §14.4.3, MUST apply pin updates only in the stamped order validated per §14.4.4, and runs the checks above on each; each valid update replaces the list. Pin updates are part of channel history (§5.2.5), and the MLS sender signature on each records who changed the pin list and when.

#### Retention Exemption

Pinned Messages are **exempt from relay retention expiry**. A relay cannot read `pinnedMessageIds`. Instead, a client that has applied a pin update adding a Message sends the relay a `PinInstruction` (§11), signed with the channel's admission key, for the `id` of the envelope that carried that Message (§5.2.5); a pin update removing a Message is mirrored by an unpin instruction the same way. Within the storage quota of its `ServiceAgreement` (§10.5.1), a relay MUST NOT evict a CID for which it holds a valid pin instruction, regardless of:

- The configured retention window
- The `expiryHint` on the original envelope
- Storage pressure

The relay MUST continue to serve pinned CIDs from its blob endpoints (§10.4.4) until it receives a valid unpin instruction. If a relay is running low on storage, it MUST evict unpinned content before considering eviction of pinned content, and MUST alert the CO party to the `ServiceAgreement` before evicting any pinned CID.

The retention exemption applies only to the pinned CID itself, not to other envelopes of the channel. Because a relay cannot see what a pinned envelope references, the pinning client sends pin instructions for the envelope CID and for its directly referenced content (e.g., the `blobId` CIDs of the Message's attachments).

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

A `did:webvh` or `did:plc` user's client MAY publish its supported body types as a service entry in its DID document. A `did:key` user cannot publish this entry (§2.1) and uses only the in-group declaration below.

```json
{
  "id": "did:webvh:QmSCID...:example.com:alice#text-formats",
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

1. Use the most recent in-group `ClientCapabilities` from each recipient (in DM groups) or check the DID document, where the recipient has one with this entry (in space channels, where per-member checking at compose time is impractical).
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
    "blobId": "bafkrei...",
    "createdBy": "did:key:z6MkAdmin...",
    "createdAt": "2026-03-12T00:00:00Z"
  }
]
```

`name` follows the JMAP Chat rules and on Agora MUST be at most 32 Unicode scalar values. `blobId` is the CID of the image file, which MUST be `image/png`, `image/gif`, or `image/webp`. Images SHOULD be square and SHOULD be 64×64 or 128×128 pixels.

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

