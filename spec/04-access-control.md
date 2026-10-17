# 4. Access Control and Moderation

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 2357–2509 (§9).


*Binds: both.*

## 4.1 Keyholders

Agora uses a three-tier authority model. Each tier's permissions are enforced cryptographically: an operation not signed by a key with the required authority MUST be rejected by conformant clients. Relays do not evaluate Space authority; their only access control is the channel admission key (§5.2.2, ARCHITECTURE §6.2).

**Space Owner:** holds the signing key for the Space state document. The Space Owner has sole authority to transfer, archive or delete the space (§3.6), grant or revoke the Admin role (`admins`, §3.3), set `guardian`, and sign Space state mutations affecting top-level structure. There is exactly one Space Owner at any time. Ownership transfer is executed via a signed `SpaceState` mutation that replaces the `owner` DID, signed by the current owner, or by the guardian procedure below.

A Space run by an organization, whether a CO serving a community or an enterprise, SHOULD have as owner a service DID of that organization (for example `did:webvh:...:example.com:agora:spaces`), not the personal DID of an employee, so that the organization's key custody and recovery (§2.5) cover the Space and staff changes do not require a transfer.

**Guardian transfer.** If the Space state carries `guardian` (§3.3), a threshold of guardians can transfer ownership when the owner key is lost or compromised:

1. **Proposal.** The guardians sign, as a threshold multi-signer object under §13.1.1 with `guardian.dids` as the candidate set and `threshold` as the required number of distinct signer DIDs, a Space state document that differs from the current head only in `seq`, `prevStateCID` and an added `pendingTransfer` member: `{"newOwner": <DID>, "ts": <RFC 3339 UTC>}`. Clients accept this document as the exception to the signer rule of §3.3. The Space endpoint MUST NOT accept a proposal whose `ts` is more than 300 seconds from its clock, and announces an accepted proposal to members (§3.4). Clients MUST reject a proposal whose `ts` is more than 300 seconds ahead of their clock.
2. **Objection.** Until `ts + delaySeconds`, the owner MAY object by signing a Space state document that chains on the proposal (or on any later document), removes `pendingTransfer` and adds `objectedAt`, the RFC 3339 UTC time of the objection. An objection whose `objectedAt` is at or after `ts + delaySeconds` is invalid, and clients MUST reject it. Clients MUST also reject an objection whose `objectedAt` is more than 300 seconds ahead of their clock.
3. **Completion.** After `ts + delaySeconds`, if no objection is in the chain, `newOwner` signs a Space state document that chains on the proposal or a later document, sets `owner` to `newOwner` and removes `pendingTransfer`. Clients MUST NOT accept a completion before their own clock passes `ts + delaySeconds`.

If a valid objection and a completion both chain on the same document, the objection wins. This rule decides a fork between an objection and a completion before the general fork rule of §5.1.1 applies. While a proposal is pending, the owner and admins continue to sign state as usual, and every such document other than an objection MUST carry `pendingTransfer` unchanged; clients MUST reject one that drops or changes it. A completion SHOULD also replace `guardian` if a guardian was involved in the loss. Guardians who collude at or above `threshold` and backdate `ts` can shorten the objection period, so `guardian` SHOULD name independent parties. An owner key held by an attacker can object to every proposal, backdating `objectedAt` if needed; if that happens, or if the Space has no `guardian`, the remaining remedy is to found a new Space and move members to it.

**Channel/Space Admin:** a role granted by the owner and recorded in `admins` in the Space state document (§3.3). Admins can sign Space state mutations within their granted scope, issue invites, execute moderation operations within channels they administer, and add or remove members from channel MLS groups within their scope.

**MLS Group Committer:** by default, any current MLS group member may issue Commit messages (RFC 9420 default). Space operators MAY restrict Commit authority with a `commitPolicy` field in the channel entry: a list of role IDs whose holders may commit. Restricting commits to a smaller set is recommended for large public channels to reduce competing Commits. A `commitPolicy` does not restrict a Commit that only updates the committer's own leaf (§5.2.1.3), that is an own-device Add (§2.6), or whose only proposals are self-Removes (§4.8). When two Commits target the same epoch, the canonical-Commit rule decides which one stands (§5.1.1): the one the Space's sequencer stamps first, or, with no sequencer, the no-sequencer rule of §5.1.1. Clients discard the losing Commit and its committer re-proposes in the new epoch.

## 4.2 Space Roles

Roles beyond Owner and Admin are defined freely in the Space state document and enforced through MLS group membership. A user's assigned role determines which channel MLS groups they are added to when they join. Role assignment is a Space state mutation of `members` (§3.3) signed by an Admin or Owner.

```json
"roles": [
  {
    "id": "member",
    "label": "Member",
    "color": "#5865F2",
    "channelAccess": ["general", "engineering/*"],
    "canInvite": false
  },
  {
    "id": "engineer",
    "label": "Engineer",
    "color": "#57F287",
    "channelAccess": ["general", "engineering/*", "voice/*"],
    "canInvite": true
  }
]
```

`channelAccess` is a list of channel path patterns. A pattern without `*` matches exactly that path. A pattern whose last segment is `*` matches every path that has the preceding segments as a prefix and at least one more segment; `*` alone matches every path. No other wildcard is defined. Patterns are matched against NFC paths (§3.2). When a user is assigned a role, they are added to the MLS groups for all matching channels via a Commit signed by the Admin performing the assignment.

An Admin's client MAY base invite issuance (§4.3) and role assignment on a member's verified credentials (§5.2.1.5), for example assigning a role to every member whose leaf carries a trusted employer credential with a given claim. It reads them from the member's leaf in a group they share, such as the Space's own group, or from a KeyPackage in which the member chose to publish them. Which issuers and claims qualify is the CO's policy, applied by the Admin's client; Space state carries no credential policy, and other members do not re-check the Admin's decision, which is authorized as any role assignment is.

## 4.3 Invite Flow

Invites are signed tokens linking a specific DID (or an open link) to a Space and an optional role:

```json
{
  "@type": "SpaceInvite",
  "space": "agora://bafkrei...",
  "issuedTo": "did:key:z6MkInvitee...",
  "role": "member",
  "issuedBy": "did:key:z6MkAdmin...",
  "expiresAt": "2026-04-12T00:00:00Z",
  "maxUses": 1,
  "spaceEndpoint": ["https://spaces.example.com/v1/agora/space/1f3a..."]
}
```

The invite is signed per §13.1.1 by `issuedBy`. `spaceEndpoint` lists the CO's Space endpoint URLs, from which the invitee fetches Space state (§3.4).

Link-based invites (no `issuedTo` field) are supported for public spaces. These use a random token that resolves to a signed invite document via an endpoint operated by the issuing CO, not by a Relay (ARCHITECTURE §7 item 4). Every invite code or token MUST carry at least 128 bits generated by a cryptographically secure random number generator. Link-based invites support a `maxUses` limit; setting `maxUses: 0` means unlimited uses until the expiry date. The endpoint rate-limits open-link joins (§4.7).

**Revocation.** An invite MAY be revoked before `expiresAt` by an `InviteRevocation`, signed per §13.1.1 by the invite's `issuedBy`, the Space owner or an admin (§4.1):

```json
{
  "@type": "InviteRevocation",
  "space": "agora://bafkrei...",
  "inviteCID": "bafkrei...",
  "revokedBy": "did:key:z6MkAdmin...",
  "ts": "2026-04-01T00:00:00Z"
}
```

`inviteCID` is the CID of the signed `SpaceInvite`; the revocation does not repeat `issuedTo`. It is distributed like moderation records (§4.5): referenced from the Space state chain and served by the Space endpoint (§3.4). Clients MUST validate an `InviteRevocation` against current Space state and MUST ignore one whose signer is not the invite's issuer, the owner or an admin. The Space endpoint MUST NOT resolve a link token to, serve state against, or count a use of a revoked invite. A client MUST NOT add a member to any of the Space's MLS groups on the strength of a revoked invite. Revocation is permanent; re-inviting requires a new invite.

**Welcome acceptance.** A Welcome whose GroupContext carries `agora_admission` is a DM group or self-group Welcome and is decided by §4.6 and §2.6; a client MUST reject such a Welcome whose group ID a channel or Space group in its copy of Space state declares. Any other Welcome is decided by this paragraph. A client MUST accept an MLS Welcome to a Space channel group only if the adding member's credential identifies a DID authorized to add members to that channel under current Space state (§4.1, §4.2), or the Welcome is an own-device Add by one of the client's own user's devices (§2.6). A client MUST reject a Welcome whose adder cannot be authenticated from the group's ratchet tree, and MUST reject a Welcome for a group ID for which it already holds group state; a Welcome never replaces an existing group. A client MUST reject a Welcome whose group ID (RFC 9420 GroupContext `group_id`) differs from the `mlsGroupID` that current Space state declares for that channel, or for the Space's own group (§3.3). If no channel in the client's copy of Space state declares that group ID, the client MUST fetch the current Space state (§3.4) before deciding. If no Space endpoint is reachable, the client holds the Welcome, retries with backoff, and discards the Welcome if it still cannot decide after 7 days.

## 4.4 Private Channels

A channel is private if its MLS group membership is a strict subset of the Space's member list. The channel's existence MAY be hidden from non-members: the channel path is omitted from the view of Space state that the CO's Space endpoint (§3.4) serves to non-members, and that access-controlled view is signed by the space owner or a delegated admin. Only the Space endpoint serves Space state to non-members; no Relay does. Non-members have no way to enumerate private channels they are not members of. In a public Space with a broadcast channel whose `keyAccess` is `public`, the view also carries the `broadcasters` list (§3.4). The home Space endpoint of a shared channel serves eligible guest members (§3.5) this view with the shared channel's entry included (§8.6), whose clients validate a Welcome's adder and the channel's `ChannelAdmissionKey` against it.

## 4.5 Moderation Operations

All moderation records (`BanRecord`, `KickRecord`, `KickLift`, `TimeoutRecord` and the moderation log) are verified outside any MLS group and are signed per §13.1.1 by a CO key (the Space owner or an admin) and distributed like Space state (§3.4): referenced from the Space state chain, served by the Space endpoint, and announced to members in-band. Clients validate each record against current Space state, checking that the signer holds the required role and scope, and MUST ignore records that fail validation. Relays do not enforce moderation records (ARCHITECTURE §6.2).

**Kick:** removes a member from one or more channel MLS groups without a space-level ban. The Admin records a `KickRecord` and issues MLS Remove commits for the target DID across the relevant channel groups. The member retains space membership and may be re-added to channels by an Admin. Before re-adding the member, the Admin publishes a `KickLift`, which ends the kick for the channels it lists; the Space endpoint serves the member those channels' keys again only once it holds the `KickLift` (§3.4).

```json
{
  "@type": "KickRecord",
  "space": "agora://bafkrei...",
  "target": "did:key:z6MkKicked...",
  "channels": ["base64url..."],
  "kickedBy": "did:key:z6MkAdmin...",
  "ts": "2026-03-12T12:00:00Z"
}
```

`channels` lists the `channelID`s (§3.3) the target is removed from.

```json
{
  "@type": "KickLift",
  "space": "agora://bafkrei...",
  "kickRecord": "bafkrei...",
  "channels": ["base64url..."],
  "liftedBy": "did:key:z6MkAdmin...",
  "ts": "2026-03-13T12:00:00Z"
}
```

`kickRecord` is the CID of the `KickRecord` that the lift ends, and `channels` lists the `channelID`s for which it ends, each of which MUST appear in that record. Clients and the Space endpoint MUST ignore a `KickLift` whose signer does not hold an admin scope covering every listed channel.

**Ban:** removes a member from all space channel MLS groups and records a signed `BanRecord` in the space's moderation log:

```json
{
  "@type": "BanRecord",
  "space": "agora://bafkrei...",
  "target": "did:key:z6MkBanned...",
  "reason": "spam",
  "bannedBy": "did:key:z6MkAdmin...",
  "ts": "2026-03-12T12:00:00Z"
}
```

Kicks and bans are removals the CO authorizes. On a `KickRecord` or `BanRecord` the CO stops serving the target the affected channels' keys and rotates those channels' admission keys (§3.4); once the CO deregisters the old key (§10.5.3), relays reject the target's envelopes without learning its DID. The MLS Removes stop the target from reading later epochs. Until the old key is deregistered the target can still post envelopes, which members discard because the target is no longer in the MLS group. Relays do not keep DID ban lists. Clients MUST NOT commit an Add of a DID with a standing `BanRecord` to any of the Space's channel groups, and MUST treat such a Commit by another member as a policy violation (below).

**Policy-violating Commits.** A Commit is valid MLS even when it breaks an Agora rule, such as adding a banned DID. A client that receives one MUST NOT process later messages in that group and MUST leave the group by deleting its group state, and SHOULD tell its user; for a Space group, an admin re-creates the group under a new `mlsGroupID` in Space state, and for a DM group, a remaining member MAY create a new one. A client MUST NOT stay on a branch of its own after refusing the canonical Commit (§5.1.1). Before a client treats a winning Commit as a policy violation because it is unauthorized under Space state, it fetches the current Space state head and re-checks (§5.1.1).

**Timeout:** a time-bounded moderation action with an `expiresAt` field. Timeouts are client-enforced: members' clients MUST discard application messages from the target DID in that space until expiry. Relays do not enforce timeouts (ARCHITECTURE §6.2). MLS group membership is not affected; the user remains a group member and can receive messages, and can still send ciphertext that other members' clients discard.

```json
{
  "@type": "TimeoutRecord",
  "space": "agora://bafkrei...",
  "target": "did:key:z6MkMuted...",
  "expiresAt": "2026-03-12T13:00:00Z",
  "issuedBy": "did:key:z6MkAdmin..."
}
```

**Message Delete:** a JMAP Chat `Message` retraction (§5.2.3): an MLS application message whose body carries the target's `senderMsgId`, `deletedAt`, and `deletedForAll: true`. The original author may retract their own message. A keyholder with Admin authority over the channel (§4.1) may retract any member's message in that channel. The retraction carries no object signature; its MLS sender signature identifies the sender (§13.1.1). Clients MUST apply a retraction only if its MLS sender is the sender of the target Message or holds Admin authority over the channel under current Space state, and MUST ignore it otherwise. Relays cannot read retractions, which travel inside ciphertext, and do not enforce them (ARCHITECTURE §7 item 2). The encrypted envelope remains at relays until their retention expires (§5.2.5); members' clients delete or hide the message in their own stores.

**Moderation Log:** all moderation actions are appended to a signed, hash-linked list; each entry carries the CID of the previous one. `moderationLog` in Space state names the newest entry (§3.3). The log names members, so it is served to space members only by the Space endpoint and MUST NOT be stored on IO infrastructure except as group-encrypted blobs (§3.4). This log is readable by space members and provides an auditable record of who moderated whom and when; removing or altering an entry breaks the hash links, so retroactive deletion is detectable.

## 4.6 Direct Message Channels

A **Direct Message (DM) channel** is an MLS group established between two or more users outside of any Space's channel hierarchy. DM groups are not owned by any Space and do not appear in any Space state document. A DM group is named by its MLS group ID. It is routed like any channel, on a channel token derived from its admission key (§5.2.2), so relays cannot distinguish DM traffic from channel traffic.

**Admission key and relays.** A DM group's admission key (§5.2.2) is part of the group's MLS state: it is carried in the group's `agora_admission` GroupContext extension (below). An identity host, the group's **admission host**, plays the CO's part for that key and nothing more. At creation the admission host is the initiator's identity host (the host of the initiator's `KeyPackageEndpoint`: the employer's provisioning service, or the host the individual chose, §5.2.1.1). The admission host generates the key, registers it by `AdmissionKeyRegistration` with every Relay holding a `relay` `ServiceAgreement` with it (§10.5.1, §10.5.3), and with no SFU or sequencer, and gives it only to its own user. It keeps no member list and serves nothing to the group's other members.

The **host's user** is a member whose identity host, the origin of its `KeyPackageEndpoint` (§5.2.1.1), equals `host` in the group's `agora_admission` extension. A member learns each other member's `KeyPackageEndpoint` from its DID document, which it already resolves for the credential binding (§5.2.1), or for `did:key` by fetching its Pkarr pointer record (§2.1). A member's client resolves each other member's DID in this way at least once every 7 days, so that it Removes the leaves of revoked device keys (§2.5.5, §2.5.6). A group can have more than one host's user. A compliance logger or recorder, that is, a DID listed in the group's `agora_compliance` extension (§7.8.2), is never a host's user. A client that holds the group in the message request state (§4.6.3) neither rotates the key nor moves the group.

```
POST   <host>/v1/agora/admission-key/<groupID>                       → issue a new ChannelAdmissionKey
POST   <host>/v1/agora/admission-key/<groupID>/<keyEpoch>/committed  → confirm that the key's Commit won
DELETE <host>/v1/agora/admission-key/<groupID>/<keyEpoch>            → deregister that key
```

`<host>` is the origin of the user's `KeyPackageEndpoint`, and `<groupID>` is the group's MLS group ID in unpadded base64url. All three requests are authenticated by the §3.5 exchange, whose `service` is `<host>/v1/agora/admission-key`, and the host accepts them only from a DID it serves. Both POSTs have an empty body. For each POST that issues a key, the host generates a new key whose `keyEpoch` is one more than the last it issued for that `<groupID>`, or 0 for the first, registers it, records the requesting DID as the key's **issuee**, and returns it as a `ChannelAdmissionKey` (§3.4) that carries `mlsGroupID`, the group ID in unpadded base64url, in place of `channelID`, and that has no `sig` and no `archive`. The key's `relays` lists only Relays that accepted the registration; if none did, the host answers `503`. The response body is the key's encoded typed payload envelope (§13.1) as `application/cbor`, authenticated by TLS to `<host>`. A DELETE deregisters the key by `AdmissionKeyDeregistration` (§10.5.3) and returns `204`; the host accepts it only from the key's issuee. Once a key is in the group's initial GroupContext, or a Commit that puts it in `agora_admission` at a rotation or a move (§4.6.4) has won (§5.1.1), a client of the key's issuee POSTs the confirmation for that key; the host records when it arrived and returns `204`, and accepts it only from the key's issuee; it keeps the first arrival time and answers a repeated confirmation `204` without change. Seven days after it receives the confirmation of a key, the host deregisters every earlier key of that group on its own; the issuee of an earlier key MAY DELETE it sooner (below). Until a later key is confirmed, the host keeps an earlier key registered until its issuee DELETEs it or the host deregisters it 30 days after the issuee is offboarded (below). The host also deregisters every key it issued to a DID 30 days after that DID is offboarded (§2.5.6). A host that does not offboard DIDs has no such bound. For each group the host keeps only the last `keyEpoch` it issued and, for each key it has not deregistered, that key's `channelToken`, admission public key, issuee and when its confirmation arrived, if it has. Otherwise the host answers with the status below and a JSON body `{ "error": "<code>" }`: `400` `malformed`, `401` `unauthenticated`, `403` `not-served` (a DID it does not serve) or `not-issuee` (a confirmation or DELETE from a DID that is not the key's issuee), `404` `unknown` (group or `keyEpoch`), `429` `rate-limited`, `503` `no-relay` (above).

The key's `relays` list is the DM group's relay list; members publish and subscribe there. A host SHOULD list relays it does not operate, because a host that is also the group's relay can tie the group's traffic to the user who asked for its key. The host learns that its user asked for keys for a group ID, and when. It does not learn the group's other members, except which of its own users also request or confirm keys for the group, and no IO learns them.

**The `agora_admission` extension.** `agora_admission` is GroupContext extension type 0xF0A0, from the RFC 9420 private-use range. Every DM group and self-group lists it in `required_capabilities`, and every Agora client lists 0xF0A0 in its leaf `capabilities.extensions` (§5.2.1). Its `extension_data` is an `AgoraAdmission` in the TLS presentation language (RFC 9420 §2.1):

```
struct {
    opaque origin<V>;        /* Relay origin, UTF-8 */
} RelayOrigin;

struct {
    opaque host<V>;          /* admission host origin, UTF-8 */
    uint64 key_epoch;
    opaque seed[32];         /* Ed25519 seed, RFC 8032 §5.1.5 */
    RelayOrigin relays<V>;
} AgoraAdmission;
```

`host` is the admission host's origin, the `<host>` above. `key_epoch`, `seed` and `relays` are the `keyEpoch`, `seed` and `relays` of a `ChannelAdmissionKey` that `host` issued, each relay given as its origin (§3.4). Members sign envelopes with that key and derive its channel token from `seed` and `key_epoch` (§5.2.2). A joiner reads the extension from the GroupContext in its Welcome (RFC 9420 §12.4.3.1), so it can reach the group before it receives any message. A removed member never sees the GroupContext of a later epoch. Handshake messages are sent as `PrivateMessage` (§5.2.1), so relays never see the extension.

Only a GroupContextExtensions proposal (RFC 9420 §12.1.7) changes `agora_admission`. Such a proposal replaces the whole extension list, so its committer copies every other GroupContext extension unchanged, including `required_capabilities` and `agora_compliance` (§7.8.2). A proposal that carries `agora_admission` byte-for-byte unchanged does not change it. A client MUST NOT commit a change to `agora_admission` other than one carrying a key that its own identity host issued to its own user, and makes such a change only when it creates the group, rotates the key as a host's user, or moves the group (§4.6.4). A client MUST NOT commit a change that keeps `host` and gives a `key_epoch` equal to that of an earlier key of that host in the group. Members MUST treat as a policy violation (§4.5) a Commit that changes `agora_admission`, keeps `host`, and either keeps `key_epoch` or has a committer that is not a host's user. For this check `host` and the committer's `KeyPackageEndpoint` origin are compared as the ASCII serialization of their origins (RFC 6454 §6.2), byte for byte, and a client writes `host` in that serialization. Before treating a Commit as a violation because its committer is not a host's user, a member resolves the committer's DID document or Pkarr record afresh; if that resolution fails, it does not treat the Commit as a violation. Members MUST also treat as a policy violation a Commit after which a DM group's or self-group's GroupContext lacks `agora_admission`, or its `required_capabilities` lacks 0xF0A0 (for a DM group, also 0xF0A4; for a self-group, also 0xF0A3). `key_epoch` need not increase: the host issues each `keyEpoch` once per group, so each of its keys for the group has its own (`seed`, `keyEpoch`) pair and channel token (§5.2.2), and MLS orders the changes (ARCHITECTURE S9). Members cannot check that a committed key is registered at any relay. A member that installs a bogus key gains no power beyond removing every other member, which this section already allows. A member that finds the key in the current GroupContext not admitted by the group's relays, because no Relay in its `relays` that it can reach accepts a Subscribe to its channel token, each answering `unknown-token` or `token-withdrawn` (§11.4), and that has seen this either while a Relay in `relays` admits an earlier key of the group or for 24 hours, rotates the key if it is a host's user and otherwise moves the group (§4.6.4). It publishes that Commit under the last admitted key it holds, which is still registered, because the issuee of a replaced key deletes it only after a Relay has admitted the new key (below), and the host deregisters it on its own only 7 days after the issuee of a later key confirms that key (above).

**Creation.** Before it creates a DM group, the initiator's client POSTs to its identity host for the new group ID and puts the returned key in the group's initial GroupContext as `agora_admission`. The same scheme admits a user's self-group (§2.6), whose admission host is the user's own identity host and each of whose devices is a host's user.

**Rotation.** After it processes a Commit that removes a leaf, the client of the host's user with the lowest leaf index MUST POST for a new key and commit a GroupContextExtensions proposal that carries it; another host's user's client MAY do the same. A client that holds the group in the message request state (§4.6.3) skips this duty (§4.6), so rotation can then wait for the 24-hour fallback. If no Commit that changes `agora_admission` has arrived 24 hours after such a Commit, every host's user's client MUST do so. Competing Commits are resolved by the canonical-Commit rule (§5.1.1). A client whose rotation Commit lost to a Commit that did not change `agora_admission` re-proposes it with the same key; a client whose key was never committed because another Commit changed `agora_admission` first DELETEs that key. Once a Commit that replaces a key with another key of the same host has won, and a Relay in the new key's `relays` has accepted a Subscribe to the new key's channel token, that is, has answered it with `Ack` and no per-token `Error` for that token (§11.4), a client of the replaced key's issuee DELETEs the replaced key, no sooner than 300 seconds after both have happened, so that members still processing the Commit can publish under the replaced key (§10.5.3). Until the replaced key is deregistered, by that DELETE or by the host 7 days after the new key's issuee confirms the new key (above), a removed member can still have envelopes admitted, which members discard because the sender is no longer in the MLS group. Rotation waits until a host's user's client is online. The client of the host's user with the lowest leaf index MUST also rotate the key, as for a removal, when 7 days have passed since it processed the Commit that put the current key in `agora_admission`; if no Commit that changes `agora_admission` has arrived 8 days after that Commit, every host's user's client MUST do so, so that the group picks up its host's current relays (§10.3.5). Competing rotations are resolved by the canonical-Commit rule (§5.1.1).

**Removing a member.** Any member MAY remove any other member of a DM group, other than a compliance logger or recorder (a DID listed in the group's `agora_compliance` extension, §7.8.2, §7.8.3), by committing MLS Removes for every leaf of that member's DID. No consent, approval or authority is needed, and members MUST NOT treat such a Commit as a policy violation (§4.5). A host's user then rotates the admission key (above). DM membership is deliberately uncontrolled: a conversation that needs controlled membership belongs in a private Space channel (§4.6.2).

**MLS group initialization:** The DM group creator generates a fresh MLS group, adds KeyPackages for each invited member, and delivers each Welcome by `POST {kp}/welcome` (§5.2.1.1) to the invitee's `KeyPackageEndpoint`, the endpoint the KeyPackage was fetched from: the `AgoraKeyPackageEndpoint` service entry of the invitee's DID document, or for `did:key` the endpoint in the invitee's Pkarr pointer record (§2.1). Delivery therefore reveals nothing to that endpoint beyond what the KeyPackage fetch already did. A Welcome is not sent on any gossipsub topic or relay. There is no Space admin in the invite path; any DM group member may add new members via standard MLS Add + Commit (§4.6.1). A client MUST accept a DM Welcome only from an adder authenticated from the group's ratchet tree as a member of the group, MUST NOT accept an anonymous Welcome, MUST reject a Welcome for a group ID for which it already holds group state, and MUST reject a DM Welcome whose GroupContext lacks `agora_admission`. An accepted Welcome from a sender the user has not accepted enters the message request state (§4.6.3).

The `KeyPackageEndpoint` is hosted by whoever runs the recipient's identity (§5.2.1.1), so only that host observes Welcome deliveries.

**Reachability.** Relay choice for a DM follows the admission host, not the recipient's DID method or the recipient's usual relays: members use the relays in the group's `agora_admission` extension. A relay in that list may be reachable only over Tor (a `.onion` address); a member that cannot reach it directly connects over Tor (§11.3) or through a relay with Tor reachability. Relays learn neither party's identity (§10.4.1).

**History and storage:** DM history is held like channel history (§5.2.5): relays hold recent envelopes for each channel token for the retention their agreements set, and members keep their own stores. MLS signatures prevent forgery, and the per-sender `seq` (§5.1.1) exposes omissions. There is no Space-level archive; members are responsible for keeping their own DM history.

### 4.6.1 Member Addition

Any member of a DM group MAY add anyone by an MLS Add and Commit. No approval is needed, and members MUST NOT treat such a Commit as a policy violation (§4.5). A user added against their wishes is protected by the message request state (§4.6.3), and a member who objects to an addition MAY remove the added member (§4.6) or leave (§4.8). Compliance logger additions follow §7.8.2.

### 4.6.2 DM Group vs. Private Channel

A DM group and a private Space channel (§4.4) are structurally similar: both are MLS groups with a restricted membership set. The distinction is:

- A private channel is owned by a Space, appears in that Space's state document (for authorized members), and is subject to the Space's compliance logging configuration.
- A DM group is owned by its members collectively, has no Space parent, and is subject to compliance logging only through the per-member obligation in §7.8. Any member can add (§4.6.1) or remove (§4.6) any other member; no member has authority over the rest.

Users who need a persistent, named, multi-party private conversation with Space-level administration (roles, moderation, compliance) SHOULD use a private Space channel rather than a DM group.

### 4.6.3 Message Requests

A client SHOULD hold a DM group in a **message request** state when the member who added the user is not an accepted sender. An accepted sender is a DID the user has accepted a request from, has started a DM with, or has marked as a contact, or a DID that matches a rule set by the user or by whoever manages the user's device, for example every DID under the user's employer's domain, every member of a Space the user belongs to, or every adder whose leaf in the Welcome's ratchet tree carries a verified credential from an issuer that the rule names (§5.2.1.5). How a client presents requests is the user agent's choice; this section's recommendations describe the intended behavior. While a group is in the request state the client:

- SHOULD NOT notify the user beyond an unobtrusive request list;
- MUST NOT send read receipts, typing indicators or any other message to the group, except as a regulated member's client below;
- SHOULD NOT fetch the group's messages until the user accepts, except as a regulated member's client below; the request shows the adder and the members named in the Welcome's ratchet tree.

**Regulated members.** The request state MUST NOT suppress compliance capture. The client of a regulated member (§7.8.1) MUST process the Welcome and perform the logger admission and disclosure of §7.8.2 and §7.8.4 while the group is in the request state, as for a deferred join (§7.8.7). To do so it fetches the group's messages so that it follows the group's epochs, commits the logger's Add, sends the `ComplianceDisclosureNotice`, and re-adds a removed logger (§7.8.3). Those are the only messages it sends to the group before the user accepts. Until the user accepts, it still sends no read receipts or typing indicators, and the recommendation above on notification still applies. On decline or block, the client deletes the group state as below; the logger keeps what it has captured under its retention (§7.2).

The user accepts, declines or blocks. On accept, the client adds the sender to its accepted senders and treats the group as any other. On decline, the client deletes the group state and sends nothing. On block, the client also adds the sender's DID to the user's block list, and later Welcomes whose adder is blocked are discarded without notice. The block list and accepted senders are kept locally and synchronized among the user's devices in the self-group (§2.6).

A `KeyPackageEndpoint` host MAY refuse KeyPackage fetches and Welcome POSTs from blocked senders, or by other policy, such as rate limits or a proof of work (§10.5.2). A Welcome is encrypted to the recipient, so the host cannot see its adder; a host that gates by sender requires the caller to authenticate by the §3.5 exchange before a fetch or POST, which shows the caller's DID to the recipient's host. A client MAY give its own host its block list for this purpose.

### 4.6.4 Admission Host Handover

Any member other than a compliance logger or recorder MAY move the group to its own identity host at any time; members MUST NOT treat such a Commit as a policy violation (§4.5). To move the group, the client POSTs to its own identity host for the group (§4.6) and commits a GroupContextExtensions proposal (RFC 9420 §12.1.7) that sets `agora_admission` to that host's origin and the returned key, in one Commit. If its host refuses the POST, the client does not commit.

When no host's user remains a member, because the last one left (§4.8), was removed (§4.6) or was offboarded (§2.5.6), the client of the remaining member with the lowest leaf index, other than a DID listed in `agora_compliance` (§7.8.2), moves the group by default. A client that holds the group in the message request state (§4.6.3) skips this duty, so the move can then wait for the 24-hour fallback. If no Commit that changes `host` has arrived 24 hours after the last host's user ceased to be a member, any remaining member's client that may move it (above) moves the group.

Members that process the Commit use the new key and the relays it lists in place of every key of the previous host, whatever its `keyEpoch`, and keep the previous host's `channelToken`s only to fetch history (§5.2.5) and, until a Relay in the new key's `relays` has accepted a Subscribe to the new key's channel token, to receive envelopes (§5.2.2). `keyEpoch` ordering applies only among keys of one host (§4.6). Competing handover Commits are resolved by the canonical-Commit rule (§5.1.1); a member whose handover Commit lost DELETEs the key its host issued for it (§4.6).

A client of the issuee of a key that a move replaced DELETEs that key 30 days after the move Commit, and not before a Relay in the new key's `relays` has accepted a Subscribe to the new key's channel token (§4.6). The previous host receives no confirmation of a later key for the group, so its 7-day deregistration (§4.6) does not apply: if that client never returns, the key stays registered until the host deregisters it 30 days after the issuee is offboarded (§4.6), which a host that does not offboard DIDs never does. Members no longer subscribe to it (§5.2.2), so envelopes admitted under it reach no member. A client whose user's last leaf is removed from the group, because the user left or another member removed it, DELETEs 30 days after that Commit each key issued to its user that was current in the group at that Commit. Remaining members complete any handover within that period.

Blobs uploaded before a handover stay at the old host's Relays until its keys are deregistered, and in members' stores; a client that needs such an attachment after that re-uploads it under the new token.

## 4.7 Abuse Handling

Relays cannot read content, so abuse handling is done by members and the CO. This section collects the pieces.

**Reports.** A member reports abuse by sending an MLS application message of type `urn:agora:type:AbuseReport` in a DM group (§4.6) with the Space owner or an admin whose scope covers the channel (§4.1). Its body is:

```json
{
  "space": "agora://bafkrei...",
  "channelID": "base64url...",
  "reason": "harassment",
  "comment": "Repeated messages after I asked them to stop.",
  "items": [
    {
      "envelopeID": "bafkrei...",
      "sender": "did:key:z6MkReported...",
      "payload": "base64url..."
    }
  ]
}
```

Each item gives the envelope `id` (§5.2.2), the DID of its MLS sender as the reporter's client authenticated it, and the decrypted typed payload envelope. For a report about a DM group, `space` and `channelID` are absent. Agora has no message franking, so a report is not verifiable by a third party: the recipient must trust the reporter's account, or compare it with its own copy if it is a member of the same group. A moderator acts through §4.5.

**CO moderation.** For abuse in a Space the CO uses kicks, bans, timeouts and deletions (§4.5); kicks and bans rotate the affected channel admission keys. To cut off a key at relays at once, the CO deregisters it by `AdmissionKeyDeregistration` (§10.5.3) and registers the new one. An abused open-link invite is revoked by `InviteRevocation` (§4.3).

**Takedowns.** A relay that receives a legal takedown notice for a CID it cannot read handles it as §10.4.5 specifies: it notifies the CO through the contact in the `ServiceAgreement` and may drop the CID.

**Open-link joins.** The CO's invite endpoint MUST rate-limit open-link token resolution per network address and per token, and MAY require a proof of work in the format of §10.5.2 from the requester before resolving a token, for example when join requests exceed a rate the CO sets.

## 4.8 Leaving

**Self-Remove.** A self-Remove proposal is an MLS Remove proposal, sent as a standalone proposal message, whose removed leaf's credential names the proposer's DID. RFC 9420 §12.2 does not let a Commit remove its committer, so another member commits it. A client leaves a group as follows:

1. It sends a self-Remove proposal for its own leaf and, when the user is leaving rather than retiring one device (§2.5.5), for every other leaf of the user's DID in the group.
2. It sends no further application messages in the group.
3. It keeps its group state until it processes a Commit that removes its leaf, re-sending its proposals in each new epoch in which it is still a member, and then deletes the group state.

A member other than a passive member (§5.2.1.3) that receives a self-Remove proposal MUST commit it before sending any further application message in that group, so that nothing it sends is readable by the leaver. Committing a self-Remove needs no Space admin authority (§4.1), and a `commitPolicy` does not restrict it (§4.1). Competing Commits are resolved by the canonical-Commit rule (§5.1.1). A self-Remove never removes a compliance logger, and §7.8.3 still applies to loggers.

**Leaving a DM group.** A member leaves a DM group by the self-Remove procedure, after which a host's user rotates the admission key (§4.6). If the leaver was the last host's user, the remaining members move the group to another host (§4.6.4), and the leaver's client deregisters its key later as §4.6.4 describes. When no member remains other than one DID and DIDs listed in the group's `agora_compliance` extension (§7.8.2), the group has ended: that member's client SHOULD tell the user and MAY delete its group state.

**Leaving a channel.** A member leaves a Space channel by the self-Remove procedure in that channel's group. Space state does not change: the member's roles still permit it to read the channel (§4.2), and an admin MAY add it again at its request.

**Leaving a Space.** A member leaves a Space by leaving every group of the Space it belongs to, the Space's own group (`mlsGroupID`, §3.3) last. A Commit in the Space's own group whose self-Removes cover every leaf of a member DID is that member's notice of leaving. The CO MUST then publish Space state, signed by the owner or by an admin whose scope is `["*"]`, that removes the DID from `members` (§3.3), and an admin Removes any of the DID's leaves that remain in the Space's channel groups. The CO stops serving that DID the Space's state and channel keys and rotates the keys it served it (§3.4), as for any removal it authorizes. Leaving creates no moderation record; the former member can rejoin only by a new invite (§4.3).

**Deleting an account.** A user who deletes an account leaves every Space and group by this section first (§2.8).


---
