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

**MLS Group Committer:** by default, any current MLS group member may issue Commit messages (RFC 9420 default). Space operators MAY restrict Commit authority with a `commitPolicy` field in the channel entry: a list of role IDs whose holders may commit. Restricting commits to a smaller set is recommended for large public channels to reduce competing Commits. A `commitPolicy` does not restrict a Commit that only updates the committer's own leaf (§5.2.1.3), that is an own-device Add (§2.6), or whose only proposals are self-Removes (§4.8). When two Commits target the same epoch, the canonical-Commit rule decides which one stands (§5.1.1): the one the Space's sequencer stamps first, or, with no sequencer, the lowest-hash rule. Clients discard the losing Commit and its committer re-proposes in the new epoch.

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

**Welcome acceptance.** A client MUST accept an MLS Welcome to a Space channel group only if the adding member's credential identifies a DID authorized to add members to that channel under current Space state (§4.1, §4.2), or the Welcome is an own-device Add by one of the client's own user's devices (§2.6). A client MUST reject a Welcome whose adder cannot be authenticated from the group's ratchet tree, and MUST reject a Welcome for a group ID for which it already holds group state; a Welcome never replaces an existing group. A client MUST reject a Welcome whose group ID (RFC 9420 GroupContext `group_id`) differs from the `mlsGroupID` that current Space state declares for that channel, or for the Space's own group (§3.3). If no channel in the client's copy of Space state declares that group ID, the client MUST fetch the current Space state (§3.4) before deciding. If no Space endpoint is reachable, the client holds the Welcome, retries with backoff, and discards the Welcome if it still cannot decide after 7 days.

## 4.4 Private Channels

A channel is private if its MLS group membership is a strict subset of the Space's member list. The channel's existence MAY be hidden from non-members: the channel path is omitted from the view of Space state that the CO's Space endpoint (§3.4) serves to non-members, and that access-controlled view is signed by the space owner or a delegated admin. Only the Space endpoint serves Space state to non-members; no Relay does. Non-members have no way to enumerate private channels they are not members of. In a public Space with a broadcast channel whose `keyAccess` is `public`, the view also carries the `broadcasters` list (§3.4). The home Space endpoint of a shared channel serves this view to eligible guest members (§3.5, §8.6), whose clients validate a Welcome's adder and the channel's `ChannelAdmissionKey` against it.

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

**Policy-violating Commits.** A Commit is valid MLS even when it breaks an Agora rule, such as adding a banned DID or an Add that lacked the consent of §4.6.1. A client that receives one MUST NOT process later messages in that group, MUST alert its user, and MUST leave the group by deleting its group state; for a Space group, an admin re-creates the group under a new `mlsGroupID` in Space state, and for a DM group, a remaining member MAY create a new one. A client MUST NOT stay on a branch of its own after refusing the canonical Commit (§5.1.1).

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

**Admission key and relays.** The DM initiator's identity host (the host of the initiator's `KeyPackageEndpoint`: the employer's provisioning service, or the host the individual chose, §5.2.1.1) plays the CO's part for the DM group's admission. It generates the group's admission key, registers it by `AdmissionKeyRegistration` with every IO holding a `ServiceAgreement` with it whose `serviceType` receives registrations (§10.5.1, §10.5.3), rotates it on removals, and serves it to the group's members as a `ChannelAdmissionKey` (§3.4) that carries `mlsGroupID`, the MLS group ID in unpadded base64url, in place of `channelID`, and that has no `sig`; members authenticate it by TLS to `<host>`:

```
GET <host>/admission-key/<groupID>              → current ChannelAdmissionKey
GET <host>/admission-key/<groupID>/<keyEpoch>   → ChannelAdmissionKey of that keyEpoch
PUT <host>/admission-key/<groupID>/members      → replace the member list
```

`<host>` is the identity host's base URL, carried in the group's `agora_admission_host` GroupContext extension (below), and `<groupID>` is the group's `mlsGroupID` in unpadded base64url. The record's `relays` list is the DM group's relay list; members publish and subscribe there. A host SHOULD list relays it does not operate, because a host that is also the group's relay sees both the member DIDs and the group's traffic. The host authenticates members by the §3.5 exchange and serves the key only to DIDs on the group's member list, which includes any compliance loggers and recorders (§7.8, §6.12.7). The host learns the DM group's member DIDs; it is a member's own CO-side service, and no IO learns them.

The initiator's client MUST put that URL in the DM group's GroupContext as the `agora_admission_host` extension, extension type 0xF0A0 from the RFC 9420 private-use range, listed in `required_capabilities`, whose data is the URL as UTF-8; a member joining by Welcome thereby finds the host before it receives any message. Because the extension is required, every Agora client lists 0xF0A0 in its leaf `capabilities.extensions` (§5.2.1). The same scheme admits a user's self-group (§2.6), whose host is the user's own identity host and whose member list is the user's DID.

**Responses.** A GET returns the `ChannelAdmissionKey` as its encoded typed payload envelope (§13.1) with `sig` absent, as `application/cbor`. A PUT takes an encoded `DMMembers` envelope (below) as `application/cbor` and returns `204` on success. Otherwise the host answers `400` to a malformed body, `401` to a request without authentication, `403` to a change this section does not allow, `404` for an unknown group or `keyEpoch`, `409` to a `seq` or `ts` that is not later than the current list's, and `429` when rate-limiting.

**Member list.** The member list is a typed payload envelope of type `urn:agora:type:DMMembers`, signed per §13.1.1 by a device key of one DID, the signer, with body:

```json
{
  "mlsGroupID": "base64url...",
  "seq": 3,
  "ts": "2026-03-12T12:00:00Z",
  "members": [
    "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
    "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
    "did:webvh:QmSCID...:compliance.example.com:logger"
  ],
  "complianceLoggers": ["did:webvh:QmSCID...:compliance.example.com:logger"]
}
```

`members` lists every member DID. `complianceLoggers` lists the compliance logger and recorder DIDs among them (§7.8, §6.12.7). `seq` is an unsigned integer. The host accepts a `DMMembers` only if its signature verifies, its `ts` is within 300 seconds of the host's clock, its `seq` and `ts` are both greater than those of the list it replaces, and it is one of these changes:

1. **Creation.** The first list the host accepts for an `mlsGroupID`, signed by a DID the host serves: the initiator when it creates the group, or the member taking the group over (§4.6.4).
2. **Addition.** A list that keeps every DID and every `complianceLoggers` entry of the current list and adds one or more DIDs, signed by a DID on the current list. The committer of every Commit that adds a DID not already on the list, including a compliance logger or recorder, MUST send this addition and receive a `204` before it delivers the Welcome. The consent rules of §4.6.1 and §7.8.2 govern the Add in the group; the host does not see them.
3. **Removal.** A list that differs from the current list only by the removal of one or more DIDs, none of them listed in `complianceLoggers`, signed by a DID on the current list. The signer may remove itself, another member, or both. The committer of every Commit that removes the last leaf of a DID MUST send this removal; a leaver sends it for itself (§4.8). The host rotates the key when it accepts one.

The host refuses every other change. In particular it never accepts the removal of a DID listed in `complianceLoggers`, by itself or by anyone: a compliance logger or recorder stays on the list for the life of the group (§7.8.3).

**Removing a member.** Any member MAY remove any other member of a DM group, other than a compliance logger or recorder (§7.8.3), by committing MLS Removes for every leaf of that member's DID. No consent, approval or authority is needed, and members MUST NOT treat such a Commit as a policy violation (§4.5). The committer sends the removal `DMMembers` above and the updated `DMGroupDescriptor`. DM membership is deliberately uncontrolled: a conversation that needs controlled membership belongs in a private Space channel (§4.6.2).

**DMGroupDescriptor schema:**

```json
{
  "@type": "DMGroupDescriptor",
  "schemaVersion": "1",
  "mlsGroupID": "base64url...",
  "consentModel": "unanimous",
  "created": "2026-03-12T00:00:00Z",
  "createdBy": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
  "members": [
    "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
    "did:plc:ewvi7nxzyoun6zhxrhs64oiz"
  ],
  "complianceLoggers": []
}
```

`members` is the current member DID list. `complianceLoggers` is the list of `ComplianceLogger` DIDs that have been admitted to the group under §7.8. `consentModel` is optional (§4.6.1), and so is `admissionHostDID` (§4.6.4). The committer of each membership or logger change sends the updated descriptor to the group as an MLS application message of type `urn:agora:type:DMGroupDescriptor` (§5.2.3) in the new epoch, and members keep it locally. Because it lists member DIDs, it travels only inside the group. As an inside-group object it carries no object signature; the committer's MLS sender signature authenticates it (§13.1.1). It MUST NOT be stored on IO infrastructure except as a group-encrypted blob (§3.4).

**MLS group initialization:** The DM group creator generates a fresh MLS group, adds KeyPackages for each invited member, and delivers each Welcome by `POST {kp}/welcome` (§5.2.1.1) to the invitee's `KeyPackageEndpoint`, the endpoint the KeyPackage was fetched from: the `AgoraKeyPackageEndpoint` service entry of the invitee's DID document, or for `did:key` the endpoint in the invitee's Pkarr pointer record (§2.1). Delivery therefore reveals nothing to that endpoint beyond what the KeyPackage fetch already did. A Welcome is not sent on any gossipsub topic or relay. There is no Space admin in the invite path; any DM group member may add new members via standard MLS Add + Commit, subject to the consent mechanism in §4.6.1. A client MUST accept a DM Welcome only from an adder authenticated from the group's ratchet tree as a member of the group, MUST NOT accept an anonymous Welcome, and MUST reject a Welcome for a group ID for which it already holds group state. A client MUST ignore a `DMGroupDescriptor` whose `mlsGroupID` differs from the group ID of the group it was received in, and MUST leave a DM group joined by Welcome if the first descriptor it receives there names a different `mlsGroupID`. An accepted Welcome from a sender the user has not accepted enters the message request state (§4.6.3).

The `KeyPackageEndpoint` is hosted by whoever runs the recipient's identity (§5.2.1.1), so only that host observes Welcome deliveries.

**Reachability.** Relay choice for a DM follows the initiator's identity host, not the recipient's DID method or the recipient's usual relays: members use the relays in the group's `ChannelAdmissionKey`. A relay in that list may be reachable only over Tor (a `.onion` address); a member that cannot reach it directly connects over Tor (§11.3) or through a relay with Tor reachability. Relays learn neither party's identity (§10.4.1).

**History and storage:** DM history is held like channel history (§5.2.5): relays hold recent envelopes for each channel token for the retention their agreements set, and members keep their own stores. MLS signatures prevent forgery, and the per-sender `seq` (§5.1.1) exposes omissions. There is no Space-level archive; members are responsible for keeping their own DM history.

### 4.6.1 Member Addition Consent

Any DM group member MAY propose adding a new member via an MLS Add Proposal. The `consentModel` of the `DMGroupDescriptor` sets how many existing members must approve: `unanimous` (every member other than the proposer), `majority` (more than half of the members other than the proposer), or `any` (no approval). When it is absent, the default is `unanimous` for groups of 2 to 4 members and `majority` for groups of 5 or more.

A member approves by sending, in the same epoch as the Proposal, an MLS application message of type `urn:agora:type:AddApproval` with body `{"proposalRef": <base64url>}`, where `proposalRef` is the ProposalRef of the Add (RFC 9420 §5.2). A member MUST NOT commit an Add until it has received enough approvals for it. Each member MUST check, when it processes the Commit, that the approvals it has received for that Add meet the model; an Add committed without them is a policy violation (§4.5).

Compliance logger additions are not subject to this consent threshold. They follow §7.8.2: the regulated member's own user agent commits the logger's Add unilaterally, not a remote admin, and the logger's presence is disclosed to all members (§7.8.4), not consented to. An own-device Add (§2.6) is also exempt.

### 4.6.2 DM Group vs. Private Channel

A DM group and a private Space channel (§4.4) are structurally similar: both are MLS groups with a restricted membership set. The distinction is:

- A private channel is owned by a Space, appears in that Space's state document (for authorized members), and is subject to the Space's compliance logging configuration.
- A DM group is owned by its members collectively, has no Space parent, and is subject to compliance logging only through the per-member obligation in §7.8. Any member can add (subject to §4.6.1) or remove (§4.6) any other member; no member has authority over the rest.

Users who need a persistent, named, multi-party private conversation with Space-level administration (roles, moderation, compliance) SHOULD use a private Space channel rather than a DM group.

### 4.6.3 Message Requests

A client MUST hold a DM group in a **message request** state when the member who added the user is not an accepted sender. An accepted sender is a DID the user has accepted a request from, has started a DM with, or has marked as a contact. While a group is in the request state the client:

- MUST NOT notify the user beyond an unobtrusive request list;
- MUST NOT send read receipts, typing indicators or any other message to the group, except as a regulated member's client below;
- MUST NOT authenticate to the group's admission host or fetch the group's messages until the user accepts, except as a regulated member's client below; the request shows the adder and the members named in the Welcome's ratchet tree.

**Regulated members.** The request state MUST NOT suppress compliance capture. The client of a regulated member (§7.8.1) MUST process the Welcome and perform the logger admission and disclosure of §7.8.2 and §7.8.4 while the group is in the request state, as for a deferred join (§7.8.7). To do so it authenticates to the group's admission host, fetches the group's messages so that it follows the group's epochs, commits the logger's Add, sends the updated `DMGroupDescriptor` and the `ComplianceDisclosureNotice`, and re-adds a removed logger (§7.8.3). Those are the only messages it sends to the group before the user accepts. Only notification, read receipts, typing indicators and display of the group's messages remain suppressed until the user accepts. On decline or block, the client deletes the group state as below; the logger keeps what it has captured under its retention (§7.2).

The user accepts, declines or blocks. On accept, the client adds the sender to its accepted senders and treats the group as any other. On decline, the client deletes the group state and sends nothing. On block, the client also adds the sender's DID to the user's block list, and later Welcomes whose adder is blocked are discarded without notice. The block list and accepted senders are kept locally and synchronized among the user's devices in the self-group (§2.6).

A `KeyPackageEndpoint` host MAY refuse KeyPackage fetches and Welcome POSTs from blocked senders, or by other policy, such as rate limits or a proof of work (§10.5.2). A Welcome is encrypted to the recipient, so the host cannot see its adder; a host that gates by sender requires the caller to authenticate by the §3.5 exchange before a fetch or POST, which shows the caller's DID to the recipient's host. A client MAY give its own host its block list for this purpose.

### 4.6.4 Admission Host Handover

The **host's user** is the DID whose identity host is named in `agora_admission_host`: the `createdBy` of the `DMGroupDescriptor`, or after a handover its `admissionHostDID`. `admissionHostDID` is an optional descriptor field; absent, it means `createdBy`.

When the host's user is no longer a member of the DM group, because it left (§4.8), was removed (§4.6) or was offboarded (§2.5.6), the group moves to another member's identity host. The client of the remaining member with the lowest leaf index, other than a compliance logger or recorder, does this automatically; if no handover Commit has arrived 24 hours after the host's user ceased to be a member, any remaining member's client does it. The client:

1. sends the current member list to its own identity host as a creation `DMMembers` (§4.6), whose `seq` and `ts` are greater than those of the list at the old host. That host generates a new admission key, registers it (§10.5.3) and serves it at the paths of §4.6;
2. commits a GroupContextExtensions proposal (RFC 9420 §12.1.7) that sets `agora_admission_host` to its identity host's base URL, and sends the updated `DMGroupDescriptor`, with `admissionHostDID` set to its own DID, in the new epoch.

Members that process the Commit fetch the admission key from the new host and use the relays it lists. Members MUST treat a Commit that changes `agora_admission_host` while the host's user is still a member as a policy violation (§4.5). Competing handover Commits are resolved by the canonical-Commit rule (§5.1.1); a member whose handover Commit lost sends its own host a removal `DMMembers` (§4.6) that removes its own DID.

An identity host MAY stop serving a DM group's admission key, and deregister it, 30 days after no DID it serves remains on the group's member list, or after every such DID has been offboarded (§2.5.6). Remaining members complete the handover within that period.

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

Each item gives the CID of the routing envelope (§5.2.2), the DID of its MLS sender as the reporter's client authenticated it, and the decrypted typed payload envelope. For a report about a DM group, `space` and `channelID` are absent. Agora has no message franking, so a report is not verifiable by a third party: the recipient must trust the reporter's account, or compare it with its own copy if it is a member of the same group. A moderator acts through §4.5.

**CO moderation.** For abuse in a Space the CO uses kicks, bans, timeouts and deletions (§4.5); kicks and bans rotate the affected channel admission keys. To cut off a key at relays at once, the CO deregisters it by `AdmissionKeyDeregistration` (§10.5.3) and registers the new one. An abused open-link invite is revoked by `InviteRevocation` (§4.3).

**Takedowns.** A relay that receives a legal takedown notice for a CID it cannot read handles it as §10.4.5 specifies: it notifies the CO through the contact in the `ServiceAgreement` and may drop the CID.

**Open-link joins.** The CO's invite endpoint MUST rate-limit open-link token resolution per network address and per token, and MAY require a proof of work in the format of §10.5.2 from the requester before resolving a token, for example when join requests exceed a rate the CO sets.

## 4.8 Leaving

**Self-Remove.** A self-Remove proposal is an MLS Remove proposal, sent as a standalone proposal message, whose removed leaf's credential names the proposer's DID. RFC 9420 §12.2 does not let a Commit remove its committer, so another member commits it. A client leaves a group as follows:

1. It sends a self-Remove proposal for its own leaf and, when the user is leaving rather than retiring one device (§2.5.5), for every other leaf of the user's DID in the group.
2. It sends no further application messages in the group.
3. It keeps its group state until it processes a Commit that removes its leaf, re-sending its proposals in each new epoch in which it is still a member, and then deletes the group state.

A member other than a passive member (§5.2.1.3) that receives a self-Remove proposal MUST commit it before sending any further application message in that group, so that nothing it sends is readable by the leaver. Committing a self-Remove needs no Space admin authority (§4.1) and no consent (§4.6.1), and a `commitPolicy` does not restrict it (§4.1). Competing Commits are resolved by the canonical-Commit rule (§5.1.1). A self-Remove never removes a compliance logger, and §7.8.3 still applies to loggers.

**Leaving a DM group.** A member leaves a DM group by the self-Remove procedure. The committer sends the updated `DMGroupDescriptor`. After it processes the Commit that removes its last leaf, and before it deletes its group state, the leaver's client sends the admission host a removal `DMMembers` that removes its own DID, which rotates the admission key (§4.6). If the leaver was the host's user, the remaining members move the group to another host (§4.6.4). When no member remains other than one DID and compliance loggers, the group has ended: that member's client SHOULD tell the user and MAY delete its group state.

**Leaving a channel.** A member leaves a Space channel by the self-Remove procedure in that channel's group. Space state does not change: the member's roles still permit it to read the channel (§4.2), and an admin MAY add it again at its request.

**Leaving a Space.** A member leaves a Space by leaving every group of the Space it belongs to, the Space's own group (`mlsGroupID`, §3.3) last. A Commit in the Space's own group whose self-Removes cover every leaf of a member DID is that member's notice of leaving. The CO MUST then publish Space state, signed by the owner or by an admin whose scope is `["*"]`, that removes the DID from `members` (§3.3), and an admin Removes any of the DID's leaves that remain in the Space's channel groups. The CO stops serving that DID the Space's state and channel keys and rotates the keys it served it (§3.4), as for any removal it authorizes. Leaving creates no moderation record; the former member can rejoin only by a new invite (§4.3).

**Deleting an account.** A user who deletes an account leaves every Space and group by this section first (§2.8).


---
