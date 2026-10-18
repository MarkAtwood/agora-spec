# 3. Spaces and Space State

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 485–583 (§3.1–§3.3).

## 3.1 Participants

Agora separates the Infrastructure Operator (IO), which runs relays and other infrastructure, from the Communications Operator (CO), which runs a community (ARCHITECTURE §2). For a Space, the CO is the Space owner and its delegated admins. A relay is an IO component.

- **Client:** a user agent (web browser, desktop application, mobile app). Connects to one or more relays. Has access to the user's cryptographic keys and MLS state, either directly (software keystore) or via a co-located secure boundary (OS Secure Enclave, hardware security key, HSM). Responsible for all encryption and decryption operations; those operations SHOULD be performed inside the secure boundary wherever the platform supports it.
- **Relay:** an always-on server that participates in gossipsub, holds recent envelopes for the retention its `ServiceAgreement` sets (§10.5.1), serves WebTransport and WebSocket endpoints for clients, and optionally pins IPFS content. Anyone can operate a relay; no permission is required.
- **Peer:** any participant in the gossipsub mesh, including both relays and clients with persistent connections.

## 3.2 Space and Channel Hierarchy

A **Space** is a named collection of channels, analogous to a Discord server. A **channel** is a named, typed stream of messages within a Space.

Every text channel has a **mode** that determines its encryption and membership model:

| Mode | MLS Group | Who Can Post | Encrypted | Use Case |
|---|---|---|---|---|
| `interactive` | All members (about 200) | All members | Yes: full MLS E2EE | Team channels, small communities |
| `community` | Active speakers only (≤ `speakerCap`) | Space members in speaker group | Yes: full MLS E2EE for speakers | Large community channels |
| `broadcast` | None (§5.2.1.4) | Holders of a role in `broadcasterRoles` | Yes: CO-distributed content key (§5.2.1.4) | Announcements, release notes |

Space membership does not imply channel membership in any mode. A Space may have thousands of members while a channel's active MLS group remains small.

Space and channel identifiers are **namespaced paths**:

```
agora://<space-id>/<channel-path>
```

Here `<space-id>` is the CID of the Space's genesis state document (§3.3), and `<channel-path>` is a slash-delimited path supporting arbitrary nesting:

```
agora://bafkrei.../general
agora://bafkrei.../engineering/backend
agora://bafkrei.../engineering/backend/incidents
agora://bafkrei.../voice/lounge
```

Channel nesting is structural only: a parent channel (such as `engineering`) can itself be a message channel, a category header, or both. The namespace is a tree with no enforced depth limit. A channel path MUST be in Unicode Normalization Form C and MUST NOT contain an empty segment. Paths are compared code point by code point. A path names a channel for display and for `channelAccess` matching (§4.2) only. A channel's identity is its `channelID` (§3.3), which does not change when the channel is renamed or moved.

## 3.3 Space State Document

The Space state document is stored as an IPLD DAG node. Its CID changes on every mutation. The Space's identity is anchored to its genesis CID. Later state is a signed chain of mutations, each referencing the prior state CID in its `prevStateCID` field. This makes the Space history tamper-evident: replacing any intermediate state document breaks the chain.

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
      "noPin": true
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

The document is signed per §13.1.1 by the Space owner's authentication key or a delegated admin's key. Space state and channel state are signed only by these CO keys (ARCHITECTURE S4). A relay or other IO key MUST NOT sign Space or channel state. Clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state. The exceptions are the guardian transfer documents of §4.1: a proposal signed by the guardian threshold, and a completion signed by `pendingTransfer.newOwner` after `ts + delaySeconds`.

Binary values in Space state (`channelID`, `mlsGroupID`, `assetKey`) are unpadded base64url (RFC 4648 §5).

`id` is absent from the genesis state document, whose CID it would otherwise have to contain. In every later state document, `id` is `agora://<genesis CID>`, with no trailing slash (§3.2).

`guardian` is optional and RECOMMENDED. It is set in the genesis state and names the DIDs (`dids`), the number of them whose signatures are required (`threshold`), and the objection period in seconds (`delaySeconds`, default 259200, that is 72 hours) for a guardian ownership transfer (§4.1). Only the owner may change it after genesis. Clients MUST reject a state document that changes `guardian` and is signed neither by the owner under the prior state nor, in a guardian transfer completion, by `pendingTransfer.newOwner` (§4.1).

`admins` lists the delegated admins (§4.1). Each entry's `scope` is a list of channel path patterns, matched as `channelAccess` is (§4.2). `["*"]` covers the whole Space, including Space-level mutations other than those reserved to the owner (§4.1). Only the owner may change `admins`. Clients MUST reject a state document that changes `admins` and is signed neither by the owner under the prior state nor, in a guardian transfer completion, by `pendingTransfer.newOwner` (§4.1).

`members` assigns roles (§4.2) to member DIDs. A DID not listed is not a member. The access-controlled view served to non-members (§4.4) omits `members`.

`acceptedDIDMethods` is an optional list of the user DID methods (§2.1) the CO accepts for members of the Space. When it is absent, all methods of §2.1 are accepted. Clients enforce it. A client MUST NOT issue a `SpaceInvite` (§4.3) to a DID whose method is not listed, MUST NOT add such a DID to any of the Space's MLS groups, and MUST NOT join a Space whose list excludes its own DID method. A client that sees a member with an unlisted method (for example, after the list is narrowed) SHOULD flag that member to admins, who MAY remove them. The list applies to user identities only, not to device keys or service identities.

`assetKey` is present in a Space that is not public. It is a 16-byte AES-128-GCM key under which the Space icon (`iconCID`) and custom emoji images are encrypted (§3.4, Mirroring).

`channelID` is 16 random bytes generated when the channel is created. Every channel entry MUST carry one. It is never 16 zero bytes, which names the Space's own group (§3.3). It never changes, including when the channel is renamed, moved to another path, or its MLS group is replaced. Records and endpoints name a channel by `channelID` (for example `ChannelAdmissionKey` and `BroadcastKey`, §3.4). Clients MUST reject a Space state in which two channel entries share a `channelID` or in which an existing channel's `channelID` differs from the prior state. MLS exporter contexts use the MLS group ID, not `channelID` (§5.2.2).

`mlsGroupID` on a channel entry is the MLS group ID of that channel's group. A channel entry that has an MLS group MUST carry its `mlsGroupID` (§4.3). The Space-level `mlsGroupID` is the group ID of the Space's own MLS group. The Space's own group is admitted and ordered as a channel whose `channelID` is 16 zero bytes, which no channel entry uses. Every rule of §3.4, §5.1.1, §5.2.2, and §14.4.5 that names a channel or `channelID` applies to it, and the Space endpoint serves its admission key to every member of the Space.

`pinLimit` and `noPin` are optional channel-state fields that bound and disable pinning in that channel (§5.2.6).

`powPolicy` is an optional channel-state field that sets the per-envelope proof-of-work difficulty members' clients enforce in that channel (§10.5.2).

`roles` is defined in §4.2. A role's optional `permissions` list uses the permission names of the JMAP Chat specification (draft-atwood-jmap-chat-00) `SpaceRole`. Holders of the `"pin"` permission may change a channel's pin list (§5.2.6). Clients ignore unrecognized permission names.

`customEmoji` lists the Space's custom emoji. Each entry is a JMAP Chat `CustomEmoji` object as defined in draft-atwood-jmap-chat-00, with the Agora constraints of §5.2.8.4. This document does not redefine it.

`moderationLog` is the CID of the newest entry of the moderation log (§4.5).

`sequencer` is optional and designates the sequencer (`did`, `endpoint`) for the Space's `sequenced-v1` data types (§14.4.1) and for choosing among competing Commits in the Space's groups (§5.1.1). A sequencer is an IO bound by the rules of a relay. It serves the CO under a `ServiceAgreement` with `serviceType` `sequencer`, signed by the CO's billing DID (§10.5.1). It admits only envelopes carrying a registered channel admission key (§5.2.2). It learns the CO that holds the agreement but not the Space. A CO SHOULD use one sequencer across all its Spaces, and SHOULD designate a relay it already holds an agreement with. If `sequencer` is absent, `sequenced-v1` types are read-only in the Space, and competing Commits are resolved by the no-sequencer rule of §5.1.1.

`closingHeads` is present only in a Space state document that replaces one `sequencer` DID with another or removes `sequencer`. It is an array with one entry `{channelID, stream, n, hash}` per channel that has an MLS group, including the Space's own group (§3.3). `stream` is the commit stream (§14.4.2) of the channel's current `channelToken` under the prior state. `n` and `hash` are the position and stamp hash of the last stamp signed by the old DID that members accept on it; both are `null` if members accept none. `stream` and `hash` are base64url. The CO chooses each head, and members apply it, as §14.4.5 describes. `closingHeads` is omitted from the non-member view (§4.4). The view served to eligible guest members of a shared channel carries only that channel's entry, taken from the latest state that carried `closingHeads` (§8.6).

`pushProxy` is optional and names the push proxy that the CO designates for its members (§11.7). It is an object with the members of the relay manifest's `pushProxy` (§11.7.2). It is omitted from the non-member view (§4.4). The proxy is an IO that serves the CO under a `ServiceAgreement` with `serviceType` `push-proxy` (§10.5.1). A client registers with this proxy only the `channelToken`s of channels whose home Space's state names it (§11.7.3), under a `pushHandle` it uses with no other proxy. The client registers every other token, including those of direct message (DM) groups and self-groups, with a relay-designated proxy.

`trustedAttesters` is optional. It is an array of at most 32 DIDs naming credential issuers that the CO recommends members' clients trust within the Space (§5.2.1.5), for example a registered identity verifier that issues derived claims to members' DIDs. It is omitted from the non-member view (§4.4), including the view served to guest members of a shared channel. A client MAY treat an `agora_credentials` entry as coming from a trusted issuer when the entry's issuer identifier equals a listed DID as an exact string, its signature verifies under a key listed under `assertionMethod` in that DID's document (§5.2.1.5), and the leaf carrying it is in the group of a channel whose home Space is this Space, or in the Space's own group. The list applies to no other group: not to DM groups, self-groups, or the channels of other Spaces. A client's own trust policy (§5.2.1.5) prevails over the list, both to add issuers and to exclude them. The list changes only which issuers a client trusts; the binding, verification, and revocation rules of §5.2.1.5 apply unchanged. Over the limit, clients ignore the list.

`consistencyModels` is optional and maps a JMAP data type URI to the consistency model identifier the Space selects for that type, overriding the type's default (§14.2.2).

The Space `name`, each channel `name`, and each role `label` are text for people to read. They follow the rules of §2.3 for `displayName`. The signer stores each in the enforced form of the PRECIS Nickname profile (RFC 8266). Clients apply that profile's enforcement rule before display or comparison, and isolate each string as a bidirectional run when displaying it. Clients SHOULD warn an admin who gives a channel a name confusable (Unicode Technical Standard #39) with another channel name in the Space. Channel paths follow §3.2 instead.

**Field index.** The tables below list every field of a Space state document and of a channel entry, with its type and when it is present. The section named defines the field. "Base64url" means unpadded base64url (RFC 4648 §5); times are RFC 3339 UTC.

| Space Field | Type | Presence | Defined In |
|---|---|---|---|
| `@type` | `"SpaceState"` | required | §3.3 |
| `schemaVersion` | string, `"1"` | required | §3.3 |
| `id` | string | required, except in genesis | §3.3 |
| `name` | string | required | §3.3 |
| `iconCID` | CID | optional | §3.3, §3.4 |
| `owner` | DID | required | §4.1 |
| `guardian` | object | optional, RECOMMENDED | §3.3, §4.1 |
| `admins` | array of `{did, scope}` | optional; absent means none | §3.3, §4.1 |
| `members` | array of `{did, roles}` | required; omitted from the non-member view | §3.3, §4.2, §4.4 |
| `acceptedDIDMethods` | array of strings | optional; absent means all of §2.1 | §3.3 |
| `assetKey` | base64url, 16 bytes | required in a Space that is not public | §3.3, §3.4 |
| `channels` | array of channel entries | required | §3.3 |
| `roles` | array of role objects | required | §4.2 |
| `customEmoji` | array of `CustomEmoji` | optional | §5.2.8.4 |
| `moderationLog` | CID | absent until the first moderation entry | §4.5 |
| `sequencer` | object `{did, endpoint}` | optional | §3.3, §14.4.1 |
| `closingHeads` | array of `{channelID, stream, n, hash}` | only in a state that replaces or removes the `sequencer` DID; omitted from the non-member view; in a guest view, see §8.6 | §3.3, §14.4.5 |
| `pushProxy` | object with the members of the relay manifest's `pushProxy` (§11.7.2) | optional; omitted from the non-member view | §3.3, §11.7 |
| `trustedAttesters` | array of DIDs, at most 32 | optional; omitted from the non-member view | §3.3, §5.2.1.5 |
| `consistencyModels` | object | optional | §14.2.2 |
| `mlsGroupID` | base64url | required | §3.3 |
| `prevStateCID` | CID | required, except in genesis | §3.3 |
| `seq` | unsigned integer | required | §3.6, §5.1.1 |
| `pendingTransfer` | object `{newOwner, ts}` | only while a guardian transfer is pending | §4.1 |
| `objectedAt` | time | only in an owner's objection | §4.1 |
| `archived` | boolean, default `false` | optional | §3.6 |
| `deleted` | time | only in the terminal document | §3.6 |
| `complianceLogging` | `ComplianceLoggingConfig` | optional | §7.2 |
| `vtcCompliance` | `VTCComplianceConfig` | optional | §6.12.5 |
| `retentionNotice` | string | required while compliance logging is enabled | §7.5 |
| `sfus` | array of `SFUDescriptor` | optional | §6.6 |
| `turnServers` | array of `TURNDescriptor` | optional | §6.11 |
| `sharedChannels` | array of `SharedChannelAlias` | optional | §8.5 |
| `broadcasters` | array of `{channelID, keyEpoch, dids}` | only in the non-member view of a Space with a `keyAccess` `"public"` channel | §3.4, §5.2.1.4 |
| `calendarId`, `taskListId` | JMAP Id | optional | §14.6.8, §14.6.9 |

| Channel Field | Type | Presence | Defined In |
|---|---|---|---|
| `channelID` | base64url, 16 bytes | required | §3.3 |
| `path` | string | required | §3.2 |
| `type` | `"text"`, `"voice"` or `"category"` | required | §3.2, §6.1 |
| `name` | string | optional | §3.3 |
| `mode` | `"interactive"`, `"community"` or `"broadcast"` | required on a `text` channel | §3.2 |
| `mlsGroupID` | base64url | required on a channel that has an MLS group; absent on `broadcast` | §3.3 |
| `children` | array of channel entries | `category` only | §3.2 |
| `commitPolicy` | array of role IDs | optional; absent means any member | §4.1 |
| `keyAccess` | `"members"` or `"public"`, default `"members"` | `broadcast` only; `"public"` only in a public Space | §3.4 |
| `broadcasterRoles` | array of role IDs | `broadcast` only | §5.2.1.4 |
| `speakerCap` | unsigned integer, default 200, at most 500 | `community` only | §5.2.1.2 |
| `idleEvictDays` | unsigned integer, default 7 | `community` only | §5.2.1.2 |
| `speakerBot` | DID | optional, `community` only | §5.2.1.2 |
| `pinLimit` | unsigned integer, default 50 | optional | §5.2.6 |
| `noPin` | boolean, default `false` | optional | §5.2.6 |
| `powPolicy` | `PowPolicy` | optional | §10.5.2 |
| `e2eeMedia` | boolean | required, `true`, on a channel that uses an SFU | §6.9 |
| `gateways` | array of `GatewayDescriptor` | optional | §9.2 |
| `archived` | boolean, default `false` | optional | §3.6 |


## 3.4 Space State Distribution

*Binds: CO.*

Space state reaches members from the CO, never from a relay topic. No gossipsub topic, relay API, or other IO-visible address carries a Space CID, MLS group ID, or other Space identifier (ARCHITECTURE S1).

**Space endpoint.** Every Space has one or more **Space endpoints**. A Space endpoint is an HTTPS service operated by the CO (ARCHITECTURE §2.2) that serves the signed Space state chain (§3.3) and every record it references by CID, including moderation records (§4.5), `InviteRevocation` records (§4.3), `ChannelShareAgreement` and `ChannelShareRevocation` records (§8), and the compliance configuration (§7.2). A Space endpoint is a CO component: it knows membership and authenticates members. It serves:

```
GET <spaceEndpoint>/head     → CID of the current Space state document
GET <spaceEndpoint>/<cid>    → the record with that CID, exactly as signed
```

Clients MUST verify each fetched record against its CID and its signature chain (§3.3) and MUST NOT trust the endpoint for anything the signatures do not prove. An endpoint can withhold state but cannot forge it (ARCHITECTURE S4).

**Locating the endpoint.** The CO lists its Space endpoint URLs in the `spaceEndpoint` array of each `SpaceInvite` (§4.3) and `SpaceAd` (§10.3.2), and MAY list them as an `AgoraSpaceEndpoint` service entry in the Space owner's DID document. A CO changes endpoints by publishing new URLs through these same records. Space identity (genesis CID) is unaffected.

**Access control.** For a private Space, the endpoint MUST serve state only to clients that authenticate as current members (§3.5) or that present an unexpired, unrevoked (§4.3) `SpaceInvite` naming them or an open-link invite token. For a public Space, the endpoint serves non-members the access-controlled view of §4.4, signed by the owner or a delegated admin. That view is a separate signed document and is never a substitute for the members' chain. Because the endpoint is the CO, its knowledge of who fetches state is not an IO observation.

**Channel keys.** The Space endpoint also serves each channel's keys. The CO issues them, and members fetch them here:

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
  "relays": ["https://relay.example.net", "https://relay2.example.org"],
  "archive": "https://archive.co.example.com"
}
```

A `ChannelAdmissionKey` carries the private half of the channel's admission key pair (§5.2.2). `seed` is the 32-byte Ed25519 private key seed (RFC 8032 §5.1.5), generated at random by the CO registration service. `keyEpoch` is an unsigned integer that starts at 0 and increases by one on every rotation of a Space channel's key; §4.6 governs it for a DM group. Members derive the channel token from `seed` and `keyEpoch` (§5.2.2). `relays` lists the relays with which the CO has registered this key by `AdmissionKeyRegistration` under a `ServiceAgreement` (§10.5.1). Members publish and subscribe at those relays. Each entry is the origin of a relay, and the client reads the relay's endpoints from its manifest (§10.2.1). `archive` is optional. It is the origin of a CO-operated blob store that serves the channel's blobs at `GET /v1/agora/blob/{cid}` (§10.4.4), which clients use when no listed relay holds a blob.

When the CO adds a relay or renews an agreement, it registers the current key with that relay and adds the relay to `relays`. The CO rotates the admission key when it authorizes a removal of a member from the channel (§4.5) and whenever else it needs to (periodically, or after a compromise). It does not rotate on every MLS epoch. A client fetches the current `ChannelAdmissionKey` at the times §5.2.2 lists. If the endpoint is unreachable, the client keeps using the last key it holds.

The **subscriber form** of a `ChannelAdmissionKey` omits `seed` and carries `channelToken` in its place: the channel token of that `keyEpoch` in unpadded base64url. It lets the holder subscribe to and read the channel's envelopes at relays but not sign envelopes. It is used only for `broadcast` channels (§5.2.1.4).

```json
{
  "@type": "BroadcastKey",
  "channelID": "base64url...",
  "keyEpoch": 7,
  "key": "base64url...",
  "notBefore": "2026-10-16T00:00:00Z"
}
```

A `BroadcastKey` is the content key of a `broadcast` channel (§5.2.1.4). `key` is 16 random bytes generated by the CO (the key length of AES-128-GCM). `notBefore` is the time from which posters MUST use this key. For a broadcast channel, the content key and the admission key rotate together and share `keyEpoch`. Sharing the counter exposes no secret: what a public channel publishes is the `BroadcastKey` and the subscriber form of the `ChannelAdmissionKey`, never `seed`.

Both records are signed per §13.1.1 by the Space owner or a delegated admin, as for Space state (§3.3). For a DM group, the identity host named in the group's `agora_admission` GroupContext extension gives the `ChannelAdmissionKey` only to its own user, authenticated by TLS and with no `sig`, and the other members read the key from that extension (§4.6). For a record served by a Space endpoint, clients MUST verify the signature, MUST reject a record whose `channelID` is neither a channel of the Space nor the Space's own group (§3.3), and MUST reject a `BroadcastKey` for a channel that is not in `broadcast` mode.

Both records are distributed by the same rules. The endpoint serves a channel's records only to members permitted to read the channel (a role whose `channelAccess` covers it, §4.2, and no standing Kick or Ban for it, §4.5), to eligible guest members of a shared channel (§8.6), to holders of a role in the channel's `broadcasterRoles`, and to the `loggerDID` of an enabled compliance configuration (§7.2) whose scope covers the channel. A Kick stands for a channel until a `KickLift` that names the `KickRecord` and covers that channel (§4.5). When the CO stops serving a channel to a member, it MUST rotate that channel's keys and MUST NOT serve that member any record with a higher `keyEpoch`.

For a `community` channel, every member whose role covers the channel is served its `ChannelAdmissionKey`, not only the speaker group. The speaker group (§5.2.1.2) bounds who can decrypt, not who is admitted at relays, and evicting an idle speaker does not rotate the channel's keys.

For a `broadcast` channel, the endpoint serves the complete `ChannelAdmissionKey` only to holders of a role in `broadcasterRoles`, and the subscriber form to every other permitted reader. A broadcast channel's `keyAccess` field selects the policy: `members` (the default) or `public`. `public` is allowed only in a public Space: clients MUST reject Space state that carries `assetKey` (§3.3) and a channel with `keyAccess` `public`. For `public`, the CO publishes the channel's `BroadcastKey` and the subscriber form of its `ChannelAdmissionKey` as public Space state, never the complete form. The endpoint serves them without authentication, and the CO MAY mirror them like other public Space state. Because the subscriber form carries `channelToken`, anyone, including an IO, can map that channel's token, and the billing DID it is registered under, to the Space. This is an accepted cost of a public broadcast channel (ARCHITECTURE §9).

The non-member view of the Space (§4.4) carries a `broadcasters` list with one entry per channel whose `keyAccess` is `public`: its `channelID`, `keyEpoch`, and `dids` (§5.2.1.4). The view is signed by the owner or an admin, so the list is CO-signed. The CO publishes a new view whenever the list changes, and a subscriber that is not a member verifies each post's signer as §5.2.1.4 describes.

**Responses.** `/head` returns the CID as text (`text/plain`). Every other response is the record's encoded typed payload envelope with `sig` present (§13.1), as `application/cbor`. A DM identity host's `ChannelAdmissionKey` is the same envelope with `sig` absent (§4.6). The endpoint answers `401` to a request that needs authentication and has none, `403` to a client that is not permitted the record, `404` for an unknown CID, `channelID`, or `keyEpoch`, and `429` when rate-limiting. A client that cannot reach any of a Space's endpoints retries with exponential backoff and keeps using the state and keys it holds.

**Real-time notification.** When Space state changes, the signer SHOULD send the new head CID to members as an MLS application message of type `SpaceStateHead` (field `stateCID`) in the Space's MLS group (`mlsGroupID`, §3.3) and MAY send it in channel groups. Recipients fetch and verify the new state from the Space endpoint. The notification needs no signature of its own because the state it points to is signed. Clients SHOULD also poll `/head` on reconnect.

**Mirroring.** A CO MAY mirror a public Space's state chain on IPFS by CID; doing so is a CO publication. Records that name members other than the owner, admins, and the DIDs in a public view's `broadcasters` list (the state of a private Space, the moderation log, any state carrying `regulatedMembers`), and other content that identifies a Space that is not public, MUST NOT be stored on IO infrastructure in the clear. The CO either holds such records only at the Space endpoint or stores them on IO infrastructure as **group-encrypted blobs**. In a Space that is not public, the icon and custom emoji images are stored only as `nonce || AES-128-GCM-Seal(assetKey, nonce, image, aad = "agora/asset/v1")`, with `nonce` 12 random bytes and `assetKey` from Space state (§3.3). `iconCID` and each emoji `blobId` name that ciphertext.

**Group-encrypted blob.** A group-encrypted blob is `epoch || nonce || AEAD(key, nonce, record, aad = "agora/blob/v1" || epoch)`. `key` is `MLS-Exporter("agora blob", group_id, Nk)` of the MLS epoch in which the blob is written, with the group's MLS group ID as context. The AEAD is that of the group's ciphersuite. `epoch` is a big-endian uint64 in the clear, and `nonce` is 12 freshly random bytes (the AES-128-GCM nonce length). The blob is addressed by the CID of the whole ciphertext. Only members of that epoch can decrypt it. An IO storing it holds only an opaque CID (ARCHITECTURE §5 item 4).

## 3.5 Member Authentication

*Binds: CO.*

A CO service that serves or issues something only to current members authenticates a member by DID as follows. Such services include the Space endpoint (§3.4), the TURN credential service (§6.11), the invite service (§14.6.1), and an identity host giving DM admission keys to its own user (§4.6). A `KeyPackageEndpoint` host that gates fetches and Welcome POSTs by sender (§4.6.3, §5.2.1.1) uses the same exchange to learn the caller's DID, without the membership check. Relays and other IOs never use this exchange (§11.6).

The client sends `POST <service>/auth`, where `<service>` is the service's base URL, with a typed payload envelope (§13.1) of type `urn:agora:type:MemberAuth`, signed per §13.1.1 by a device key of `did`. Its body is:

```json
{
  "did": "did:webvh:QmSCID...:example.com:alice",
  "service": "https://spaces.example.com/v1/agora/space/1f3a...",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

An invitee who is not yet a member adds `invite`, the unpadded base64url of the encoded `SpaceInvite` envelope that names it (§4.3), or `inviteToken`, an open-link invite token.

The service MUST verify the signature with `did` as the required signer, MUST check that `service` equals its own base URL and that `ts` is within 300 seconds of its clock, and MUST reject an envelope it has accepted in the previous 600 seconds. It MUST check that `did` is a current member under the Space state it holds or, for the Space endpoint, is named by the presented unexpired, unrevoked `SpaceInvite` or holds a valid open-link token (§4.3). For the following services, "current member" has a special meaning:

- For an identity host, a DID it serves (§4.6).
- For the home Space endpoint of a shared channel, a guest member eligible under §8.6. This grants access to that channel's records and to the home Space's non-member view (§4.4) only.
- For a guest Space endpoint, the `homeAdminDID` of an in-force `ChannelShareAgreement` naming that Space (§8.6). This grants reads of the guest Space's state only.

The service answers a refused exchange `403`. On success it returns a bearer token of at least 128 random bits, valid for at most one hour, which the client sends as `Authorization: Bearer <token>` on later requests to that service.

## 3.6 Space and Channel Lifecycle

*Binds: CO.*

**Creation.** A Space is created in this order:

1. The creating client generates the Space's own MLS group under a fresh random group ID. For each initial channel, it generates a `channelID` and, for a channel that has one (§3.2), an MLS group (§3.3).
2. The owner signs the genesis state document per §13.1.1. It MUST carry `@type`, `schemaVersion`, `name`, `owner`, `members`, `roles`, `channels`, `mlsGroupID`, and `seq` set to 0; `assetKey` if the Space is not public; and `guardian` if the Space has one (§4.1). It MUST NOT carry `id` or `prevStateCID`.
3. The CO serves the genesis document at its Space endpoints (§3.4). The Space's identifier is `agora://<genesis CID>` (§3.2).
4. The CO generates the admission key of each channel and of the Space's own group (§3.3) and, for a `broadcast` channel, its `BroadcastKey`. It registers each admission key with every IO holding a `ServiceAgreement` whose `serviceType` receives registrations (§3.4, §10.5.1, §10.5.3).
5. Admins are granted by later state documents (§4.1), and members join by invite (§4.3).

Every later state document has a `seq` one greater than that of the document its `prevStateCID` names. Clients MUST reject one that does not.

**Channel creation, rename, move, and deletion.** Each is a Space state mutation signed by the owner or by an admin whose scope covers the channel's path (§3.3).

- *Create.* The mutation adds a channel entry with a fresh `channelID` and, for a channel that has one, the `mlsGroupID` of a new MLS group. The CO issues the channel's keys (§3.4) before members are added. Members whose roles cover the path are added as §4.2 describes, and a compliance logger as §7.2 describes.
- *Rename or move.* The mutation changes `name` or `path` and nothing that identifies the channel. `channelID` and `mlsGroupID` stay the same, so the admission key, channel token, and MLS exporter contexts are unchanged (§5.2.2). A move can change which `channelAccess` patterns, admin scopes, and compliance `scope` globs match the channel. Admins then add the members the new path covers (§4.2) and Remove those it no longer covers, the CO serves keys under the new matching (§3.4), and loggers are added or removed under §7.2.
- *Delete.* The mutation removes the channel entry. Only the home Space owner may delete a shared channel (§8.2). The home Space SHOULD first revoke each `ChannelShareAgreement` that covers it (§8.7). On accepting the mutation, clients stop sending in the channel's group and delete its group state. They keep the messages in their own stores unless the user deletes them. The CO stops serving the channel's keys and deregisters its admission key (§10.5.3). Clients MUST reject a later state document in which a deleted channel's `channelID` appears again.

**Archival.** The owner archives a Space, and the owner or an admin whose scope covers a channel archives that channel, by a mutation that sets `archived` to `true`. While a Space or channel is archived, clients MUST NOT send application messages in its groups and MUST NOT commit an Add to them. Clients SHOULD present it as read-only. Commits that only Remove leaves, self-Removes (§4.8), and Commits that only update the committer's own leaf remain allowed. The CO keeps serving the state and keys to members, and MAY deregister the admission keys (§10.5.3), after which members read history only from their own stores (§5.2.5). Compliance logging configuration still applies. A mutation by the same authority that sets `archived` to `false` or removes it ends the archival.

**Deletion.** The owner deletes a Space by a final state document that chains on the head as usual and sets `deleted` to the time of deletion. Clients MUST reject a document carrying `deleted` that is not signed by the owner, and MUST reject any document whose `prevStateCID` names a document carrying `deleted`. Before deleting, the owner SHOULD revoke every `ChannelShareAgreement` the Space is party to (§8.7). Clients of a guest Space treat a shared channel whose home Space is deleted as revoked.

On accepting the deletion, clients stop sending in all of the Space's groups, delete the group state of the Space's own group and channel groups, and SHOULD show the Space as deleted. They keep the messages in their own stores unless the user deletes them. DM groups are not part of any Space and are not affected (§4.6). The CO announces the deletion like any state change (§3.4), keeps serving `/head` and the final document to members so that members who were offline learn of it, stops serving channel keys, deregisters every admission key (§10.5.3), and stops any mirroring of the Space's records. Relays drop the Space's envelopes when their retention expires (§5.2.5); no protocol message removes them sooner. Deletion does not shorten the compliance logger's retention of what it captured (§7.2) or the removal prohibition of §7.8.3.
