# 3. Spaces and Space State

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 485–583 (§3.1–3.3).


*Binds: both.*

## 3.1 Participants

Agora separates the Infrastructure Operator (IO), which runs Relays and other infrastructure, from the Communications Operator (CO), which runs a community; for a Space the CO is the Space owner and its delegated admins (ARCHITECTURE §2). A Relay is an IO component.

- **Client:** a user agent (web browser, desktop application, mobile app). Connects to one or more Relays. Has access to the user's cryptographic keys and MLS state, either directly (software keystore) or via a co-located secure boundary (OS Secure Enclave, hardware security key, HSM). Responsible for all encryption and decryption operations; those operations SHOULD be performed inside the secure boundary wherever the platform supports it.
- **Relay:** an always-on server that participates in gossipsub, holds recent envelopes for the retention its `ServiceAgreement` sets (§10.5.1), serves WebTransport and WebSocket endpoints for clients, and optionally pins IPFS content. Anyone may operate a Relay; no permission is required.
- **Peer:** any participant in the gossipsub mesh, including both Relays and clients with persistent connections.

## 3.2 Space and Channel Hierarchy

A **Space** is a named collection of channels, analogous to a Discord server. A **Channel** is a named, typed stream of messages within a Space.

Every channel has a **mode** that determines its encryption and membership model:

| Mode | MLS group | Who can post | Encrypted | Use case |
|---|---|---|---|---|
| `interactive` | All members (≤ 200) | All members | Yes: full MLS E2EE | Team channels, DMs, small communities |
| `community` | Active speakers only (≤ `speakerCap`) | Space members in speaker group | Yes: full MLS E2EE for speakers | Large community channels |
| `broadcast` | None (§5.2.1.4) | Holders of a role in `broadcasterRoles` | Yes: CO-distributed content key (§5.2.1.4) | Announcements, release notes |

Space membership does not imply channel membership in any mode. A space may have thousands of members while a channel's active MLS group remains small.

Space and Channel identifiers are **namespaced paths**:

```
agora://<space-id>/<channel-path>
```

Where `<space-id>` is the CID of the Space's genesis state document (§3.3), and `<channel-path>` is a slash-delimited path supporting arbitrary nesting:

```
agora://bafkrei.../general
agora://bafkrei.../engineering/backend
agora://bafkrei.../engineering/backend/incidents
agora://bafkrei.../voice/lounge
```

Channel nesting is structural only: a parent channel (such as `engineering`) can itself be a message channel, a category header, or both. The namespace is a tree; there is no enforced depth limit. A channel path MUST be in Unicode Normalization Form C and MUST NOT contain an empty segment; paths are compared code point by code point. A path names a channel for display and for `channelAccess` matching (§4.2) only. A channel's identity is its `channelID` (§3.3), which does not change when the channel is renamed or moved.

## 3.3 Space State Document

The Space state document is stored as an IPLD DAG node. Its CID changes on every mutation. The Space's identity is anchored to its genesis CID; subsequent state is represented as a signed chain of mutations, each referencing the prior state CID in its `prevStateCID` field. This makes the Space history tamper-evident: replacing any intermediate state document breaks the chain.

```json
{
  "@type": "SpaceState",
  "schemaVersion": "1",
  "id": "agora://bafkrei...",
  "name": "Example Dev",
  "iconCID": "bafkrei...",
  "owner": "did:webvh:QmSCID...:example.com:agora:spaces",
  "guardian": {
    "dids": [
      "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
      "did:webvh:QmSCID...:example.com:users:r2v8n5xw",
      "did:plc:ewvi7nxzyoun6zhxrhs64oiz"
    ],
    "threshold": 2,
    "delaySeconds": 259200
  },
  "admins": [
    { "did": "did:webvh:QmSCID...:example.com:users:k7f3qd2m", "scope": ["*"] },
    { "did": "did:webvh:QmSCID...:example.com:users:r2v8n5xw", "scope": ["engineering/*"] }
  ],
  "members": [
    { "did": "did:webvh:QmSCID...:example.com:alice", "roles": ["member", "broadcaster"] },
    { "did": "did:key:z6MkBob...", "roles": ["member"] }
  ],
  "acceptedDIDMethods": ["did:webvh", "did:plc"],
  "assetKey": "base64url...",
  "channels": [
    {
      "channelID": "base64url...",
      "path": "general",
      "type": "text",
      "mode": "interactive",
      "name": "general",
      "pinLimit": 50,
      "mlsGroupID": "base64url..."
    },
    {
      "channelID": "base64url...",
      "path": "announcements",
      "type": "text",
      "mode": "broadcast",
      "name": "Announcements",
      "keyAccess": "members",
      "broadcasterRoles": ["broadcaster"],
      "noPin": true,
      "mlsGroupID": "base64url..."
    },
    {
      "channelID": "base64url...",
      "path": "community",
      "type": "text",
      "mode": "community",
      "name": "Community",
      "speakerCap": 200,
      "idleEvictDays": 7,
      "mlsGroupID": "base64url..."
    },
    {
      "channelID": "base64url...",
      "path": "engineering",
      "type": "category",
      "name": "Engineering",
      "children": [
        { "channelID": "base64url...", "path": "engineering/backend", "type": "text", "mode": "interactive", "mlsGroupID": "base64url..." },
        { "channelID": "base64url...", "path": "engineering/fips",    "type": "text", "mode": "interactive", "mlsGroupID": "base64url..." }
      ]
    },
    {
      "channelID": "base64url...",
      "path": "voice/lounge",
      "type": "voice",
      "mlsGroupID": "base64url..."
    }
  ],
  "roles": [
    {
      "id": "member",
      "label": "Member",
      "channelAccess": ["general", "engineering/*"],
      "canInvite": false,
      "permissions": ["view", "send", "pin"]
    },
    {
      "id": "broadcaster",
      "label": "Broadcaster",
      "channelAccess": ["announcements"],
      "canInvite": false
    }
  ],
  "customEmoji": [
    {
      "id": "01J3XP0A1B2C3D4E5F6G7H8J9K",
      "name": "example_logo",
      "blobId": "bafkrei...",
      "createdBy": "did:webvh:QmSCID...:example.com:alice",
      "createdAt": "2026-03-12T00:00:00Z"
    }
  ],
  "moderationLog": "bafkrei...",
  "sequencer": {
    "did": "did:web:relay.example.net",
    "endpoint": "https://relay.example.net/v1/agora/seq"
  },
  "consistencyModels": {
    "urn:ietf:params:jmap:tasks#Task": "sequenced-v1"
  },
  "mlsGroupID": "base64url...",
  "prevStateCID": "bafkrei...",
  "seq": 42
}
```

`id` is absent from the genesis state document, whose CID it would otherwise have to contain. In every later state document `id` is `agora://<genesis CID>`, with no trailing slash (§3.2).

The document is signed per §13.1.1 by the Space owner's authentication key or a delegated admin's key. Space state and channel state are signed only by these CO keys (ARCHITECTURE S4). A Relay or other IO key MUST NOT sign Space or channel state, and clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state. The one exception is a guardian transfer document, signed by the guardian threshold (§4.1).

Binary values in Space state (`channelID`, `mlsGroupID`, `assetKey`) are unpadded base64url (RFC 4648 §5).

`acceptedDIDMethods` is an optional list of the user DID methods (§2.1) the CO accepts for members of the Space. When it is absent, all methods of §2.1 are accepted. Clients enforce it: a client MUST NOT issue a `SpaceInvite` (§4.3) to, or add to any of the Space's MLS groups, a DID whose method is not listed, and MUST NOT join a Space whose list excludes its own DID method. A client that sees a member with an unlisted method (for example, after the list is narrowed) SHOULD flag that member to admins, who MAY remove them. The list applies to user identities only, not to device keys or service identities.

`roles` is defined in §4.2. A role's optional `permissions` list uses the permission names of the JMAP Chat specification (draft-atwood-jmap-chat-00) `SpaceRole`. Holders of the `"pin"` permission may change a channel's pin list (§5.2.6). Clients ignore unrecognized permission names.

`channelID` is 16 random bytes generated when the channel is created. Every channel entry MUST carry one. It never changes, including when the channel is renamed, moved to another path, or its MLS group is replaced. Records and endpoints name a channel by `channelID` (for example `ChannelAdmissionKey` and `BroadcastKey`, §3.4). Clients MUST reject a Space state in which two channel entries share a `channelID` or in which an existing channel's `channelID` differs from the prior state. MLS exporter contexts use the MLS group ID, not `channelID` (§5.2.2).

`mlsGroupID` on a channel entry is the MLS group ID of that channel's group; the Space-level `mlsGroupID` is the group ID of the Space's own MLS group. A channel entry that has an MLS group MUST carry its `mlsGroupID` (§4.3).

`admins` lists the delegated admins (§4.1). Each entry's `scope` is a list of channel path patterns, matched as `channelAccess` is (§4.2); `["*"]` covers the whole Space, including Space-level mutations other than those reserved to the owner (§4.1). Only the owner may change `admins`.

`members` assigns roles (§4.2) to member DIDs. A DID not listed is not a member. The access-controlled view served to non-members (§3.4) omits `members`.

`guardian` is optional and RECOMMENDED. It is set in the genesis state and names the DIDs (`dids`), the number of them whose signatures are required (`threshold`), and the objection period in seconds (`delaySeconds`, default 259200, that is 72 hours) for a guardian ownership transfer (§4.1). Only the owner may change it after genesis.

`moderationLog` is the CID of the newest entry of the moderation log (§4.5).

`assetKey` is present in a Space that is not public. It is a 16-byte AES-128-GCM key under which the Space icon (`iconCID`) and custom emoji images are encrypted (§3.4, Mirroring).

`pinLimit` and `noPin` are optional channel-state fields that bound and disable pinning in that channel (§5.2.6).

`powPolicy` is an optional channel-state field that sets the per-envelope proof-of-work difficulty members' clients enforce in that channel (§10.5.2).

`customEmoji` lists the Space's custom emoji. Each entry is a JMAP Chat `CustomEmoji` object as defined in draft-atwood-jmap-chat-00, with the Agora constraints of §5.2.8.4; this document does not redefine it.

`sequencer` is optional and designates the sequencer (`did`, `endpoint`) for the Space's `sequenced-v1` data types (§14.4.1) and for choosing among competing Commits in the Space's groups (§5.1.1). A sequencer is an IO bound by the rules of a relay: it serves the CO under a `ServiceAgreement` with `serviceType` `sequencer`, signed by the CO's billing DID (§10.5.1), admits only envelopes carrying a registered channel admission key (§5.2.2), and learns the CO that holds the agreement but not the Space. A CO SHOULD use one sequencer across all its Spaces, and SHOULD designate a relay it already holds an agreement with. If `sequencer` is absent, `sequenced-v1` types are read-only in the Space, and competing Commits are resolved by the lowest-hash rule (§5.1.1).

`consistencyModels` is optional and maps a JMAP data type URI to the consistency model identifier the Space selects for that type, overriding the type's default (§14.2.2).


## 3.4 Space State Distribution

*Binds: CO.*

Space state reaches members from the CO, never from a Relay topic. No gossipsub topic, Relay API or other IO-visible address carries a Space CID, MLS group ID or other Space identifier (ARCHITECTURE S1).

**Space endpoint.** Every Space has one or more **Space endpoints**: HTTPS services operated by the CO (ARCHITECTURE §2.2) that serve the signed Space state chain (§3.3) and every record it references by CID, including moderation records (§4.5), `InviteRevocation` records (§4.3), `ChannelShareAgreement` and `ChannelShareRevocation` records (§8), and the compliance configuration (§7.2). A Space endpoint is a CO component: it knows membership and authenticates members. It serves:

```
GET <spaceEndpoint>/head     → CID of the current Space state document
GET <spaceEndpoint>/<cid>    → the record with that CID, exactly as signed
```

Clients MUST verify each fetched record against its CID and its signature chain (§3.3) and MUST NOT trust the endpoint for anything the signatures do not prove; an endpoint can withhold state but cannot forge it (ARCHITECTURE S4).

**Channel keys.** The Space endpoint also serves each channel's keys. The CO issues them; members fetch them here:

```
GET <spaceEndpoint>/admission-key/<channelID>              → current ChannelAdmissionKey
GET <spaceEndpoint>/admission-key/<channelID>/<keyEpoch>   → ChannelAdmissionKey of that keyEpoch
GET <spaceEndpoint>/broadcast-key/<channelID>              → current BroadcastKey (broadcast channels)
GET <spaceEndpoint>/broadcast-key/<channelID>/<keyEpoch>   → BroadcastKey of that keyEpoch
```

`<channelID>` is the channel's `channelID` (§3.3) in unpadded base64url.

```json
{
  "@type": "ChannelAdmissionKey",
  "channelID": "base64url...",
  "keyEpoch": 3,
  "seed": "base64url...",
  "relays": ["https://relay.example.net", "https://relay2.example.org"]
}
```

A `ChannelAdmissionKey` carries the private half of the channel's admission key pair (§5.2.2). `seed` is the 32-byte Ed25519 private key seed (RFC 8032 §5.1.5), generated at random by the CO registration service. `keyEpoch` is an unsigned integer that starts at 0 and increases by one on every rotation. `relays` lists the relay endpoints with which the CO has registered this key by `AdmissionKeyRegistration` under a `ServiceAgreement` (§10.5.1); members publish and subscribe at those relays. Members derive the channel token from `seed` and `keyEpoch` (§5.2.2). When the CO adds a relay or renews an agreement, it registers the current key with that relay and adds the relay to `relays`. The CO rotates the admission key when it authorizes a removal of a member from the channel (§4.5) and whenever else it needs to (periodically, or after a compromise); it does not rotate on every MLS epoch. A client fetches the current `ChannelAdmissionKey` at the times §5.2.2 lists. If the endpoint is unreachable, the client keeps using the last key it holds.

The **subscriber form** of a `ChannelAdmissionKey` omits `seed` and carries `channelToken`, the channel token of that `keyEpoch` in unpadded base64url, in its place. It lets the holder subscribe to and read the channel's envelopes at relays but not sign envelopes. It is used only for `broadcast` channels (§5.2.1.4).

```json
{
  "@type": "BroadcastKey",
  "channelID": "base64url...",
  "keyEpoch": 7,
  "key": "base64url...",
  "notBefore": "2026-10-16T00:00:00Z"
}
```

A `BroadcastKey` is the content key of a `broadcast` channel (§5.2.1.4). `key` is 16 random bytes generated by the CO (the key length of AES-128-GCM), and `notBefore` is the time from which posters MUST use this key. For a broadcast channel the content key and the admission key rotate together and share `keyEpoch`. Sharing the counter exposes no secret: what a public channel publishes is the `BroadcastKey` and the subscriber form of the `ChannelAdmissionKey`, never `seed`.

Both records are signed per §13.1.1 by the Space owner or a delegated admin, as for Space state (§3.3); for a DM group, the `ChannelAdmissionKey` is instead authenticated by TLS to the identity host named in the group's `agora_admission_host` extension and carries no `sig` (§4.6). Clients MUST verify the signature, MUST reject a record whose `channelID` is not a channel of the Space, and MUST reject a `BroadcastKey` for a channel that is not in `broadcast` mode. Both are distributed by the same rules. The endpoint serves a channel's records only under the access control below: to members permitted to read the channel (a role whose `channelAccess` covers it, §4.2, and no standing Kick or Ban for it, §4.5), to eligible guest members of a shared channel (§8.6), to holders of a role in the channel's `broadcasterRoles`, and to the `loggerDID` of an enabled compliance configuration (§7.2) whose scope covers the channel. For a `broadcast` channel, the endpoint serves the complete `ChannelAdmissionKey` only to holders of a role in `broadcasterRoles`, and the subscriber form to every other permitted reader. A broadcast channel's `keyAccess` field selects the policy: `members` (the default) or `public`. For `public`, the CO publishes the channel's `BroadcastKey` and the subscriber form of its `ChannelAdmissionKey` as public Space state, never the complete form: the endpoint serves them without authentication, and the CO MAY mirror them like other public Space state. When the CO stops serving a channel to a member, it MUST rotate that channel's keys and MUST NOT serve that member any record with a higher `keyEpoch`.

**Responses.** `/head` returns the CID as text (`text/plain`). Every other response is the record's encoded typed payload envelope with `sig` present (§13.1), as `application/cbor`. The endpoint answers `401` to a request that needs authentication and has none, `403` to a client that is not permitted the record, `404` for an unknown CID, `channelID` or `keyEpoch`, and `429` when rate-limiting. A client that cannot reach any of a Space's endpoints retries with exponential backoff and keeps using the state and keys it holds.

**Locating the endpoint.** The CO lists its Space endpoint URLs in the `spaceEndpoint` array of each `SpaceInvite` (§4.3) and `SpaceAd` (§10.3.2), and MAY list them as an `AgoraSpaceEndpoint` service entry in the Space owner's DID document. A CO changes endpoints by publishing new URLs through these same records; Space identity (genesis CID) is unaffected.

**Access control.** For a private Space, the endpoint MUST serve state only to clients that authenticate as current members (§3.5) or that present an unexpired, unrevoked (§4.3) `SpaceInvite` naming them or an open-link invite token. For a public Space, the endpoint serves non-members the access-controlled view of §4.4, signed by the owner or a delegated admin; it is a separate signed document and is never a substitute for the members' chain. Because the endpoint is the CO, its knowledge of who fetches state is not an IO observation.

**Real-time notification.** When Space state changes, the signer SHOULD send the new head CID to members as an MLS application message of type `SpaceStateHead` (field `stateCID`) in the Space's MLS group (`mlsGroupID`, §3.3) and MAY send it in channel groups. Recipients fetch and verify the new state from the Space endpoint. The notification needs no signature of its own because the state it points to is signed. Clients SHOULD also poll `/head` on reconnect.

**Mirroring.** A CO MAY mirror a public Space's state chain on IPFS by CID; doing so is a CO publication. Records that name members other than the owner and admins (the state of a private Space, the moderation log, any state carrying `regulatedMembers`), and other content that identifies a Space that is not public, MUST NOT be stored on IO infrastructure in the clear. The CO either holds such records only at the Space endpoint or stores them on IO infrastructure as **group-encrypted blobs**. In a Space that is not public, the icon and custom emoji images are stored only as `nonce || AES-128-GCM-Seal(assetKey, nonce, image, aad = "agora/asset/v1")`, with `nonce` 12 random bytes and `assetKey` from Space state (§3.3); `iconCID` and each emoji `blobId` name that ciphertext.

**Group-encrypted blob.** A group-encrypted blob is `epoch || nonce || AEAD(key, nonce, record, aad = "agora/blob/v1" || epoch)`, where `key` is `MLS-Exporter("agora blob", group_id, Nk)` of the MLS epoch in which it is written, with the group's MLS group ID as context, the AEAD is that of the group's ciphersuite, `epoch` is a big-endian uint64 in the clear, and `nonce` is freshly random. It is addressed by the CID of the whole ciphertext. Only members of that epoch can decrypt it. An IO storing it holds only an opaque CID (ARCHITECTURE §5 item 4).

## 3.5 Member Authentication

*Binds: CO.*

A CO service that serves or issues something only to current members, such as the Space endpoint (§3.4), the TURN credential service (§6.11), the invite service (§14.6.1) or an identity host serving DM admission keys (§4.6), authenticates a member by DID as follows. A `KeyPackageEndpoint` host that gates fetches and Welcome POSTs by sender (§4.6.3, §5.2.1.1) uses the same exchange to learn the caller's DID, without the membership check. Relays and other IOs never use this exchange (§11.6).

The client sends `POST <service>/auth`, where `<service>` is the service's base URL, with a typed payload envelope (§13.1) of type `urn:agora:type:MemberAuth`, signed per §13.1.1 by a device key of `did`. Its body is:

```json
{
  "did": "did:webvh:QmSCID...:example.com:alice",
  "service": "https://spaces.example.com/v1/agora/space/1f3a...",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

An invitee who is not yet a member adds `invite`, the unpadded base64url of the encoded `SpaceInvite` envelope that names it (§4.3), or `inviteToken`, an open-link invite token.

The service MUST verify the signature with `did` as the required signer, MUST check that `service` equals its own base URL and that `ts` is within 300 seconds of its clock, MUST reject an envelope it has accepted in the previous 600 seconds, and MUST check that `did` is a current member under the Space state it holds (for an identity host, a member of the DM group under §4.6; for the home Space endpoint of a shared channel, a guest member eligible under §8.6, which grants access to that channel's records only) or, for the Space endpoint, is named by the presented unexpired, unrevoked `SpaceInvite` or holds a valid open-link token (§4.3). On success it returns a bearer token of at least 128 random bits, valid for at most one hour, which the client sends as `Authorization: Bearer <token>` on later requests to that service.
