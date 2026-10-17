# 3. Spaces and Space State

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 485–583 (§3.1–3.3).


*Binds: both.*

## 3.1 Participants

Agora separates the Infrastructure Operator (IO), which runs Relays and other infrastructure, from the Communications Operator (CO), which runs a community; for a Space the CO is the Space owner and its delegated admins (ARCHITECTURE §2). A Relay is an IO component.

- **Client:** a user agent (web browser, desktop application, mobile app). Connects to one or more Relays. Has access to the user's cryptographic keys and MLS state, either directly (software keystore) or via a co-located secure boundary (OS Secure Enclave, hardware security key, HSM). Responsible for all encryption and decryption operations; those operations SHOULD be performed inside the secure boundary wherever the platform supports it.
- **Relay:** an always-on server that participates in gossipsub, caches recent messages within a configured retention window, serves WebTransport and WebSocket endpoints for clients, and optionally pins IPFS content. Anyone may operate a Relay; no permission is required.
- **Peer:** any participant in the gossipsub mesh, including both Relays and clients with persistent connections.

## 3.2 Space and Channel Hierarchy

A **Space** is a named collection of channels, analogous to a Discord server. A **Channel** is a named, typed stream of messages within a Space.

Every channel has a **mode** that determines its encryption and membership model:

| Mode | MLS group | Who can post | Encrypted | Use case |
|---|---|---|---|---|
| `interactive` | All members (≤ 200) | All members | Yes: full MLS E2EE | Team channels, DMs, small communities |
| `community` | Active speakers only (≤ `speakerCap`) | Space members in speaker group | Yes: full MLS E2EE for speakers | Large community channels |
| `broadcast` | Publisher group (posters only, §5.2.1.4) | Space admins / designated posters | Yes: CO-distributed content key (§5.2.1.4) | Announcements, release notes |

Space membership does not imply channel membership in any mode. A space may have thousands of members while a channel's active MLS group remains small.

Space and Channel identifiers are **namespaced paths**:

```
agora://<space-id>/<channel-path>
```

Where `<space-id>` is the CID of the Space's root state document, and `<channel-path>` is a slash-delimited path supporting arbitrary nesting:

```
agora://bafyrei.../general
agora://bafyrei.../engineering/backend
agora://bafyrei.../engineering/backend/incidents
agora://bafyrei.../voice/lounge
```

Channel nesting is structural only: a parent channel (such as `engineering`) can itself be a message channel, a category header, or both. The namespace is a tree; there is no enforced depth limit.

## 3.3 Space State Document

The Space state document is stored as an IPLD DAG node. Its CID changes on every mutation. The Space's identity is anchored to its genesis CID; subsequent state is represented as a signed chain of mutations, each referencing the prior state CID in its `prevStateCID` field. This makes the Space history tamper-evident: replacing any intermediate state document breaks the chain.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SpaceState",
  "schemaVersion": "1",
  "id": "agora://bafyrei...",
  "name": "Example Dev",
  "iconCID": "bafyrei...",
  "owner": "did:webvh:QmSCID...:example.com:alice",
  "acceptedDIDMethods": ["did:webvh", "did:plc"],
  "channels": [
    {
      "path": "general",
      "type": "text",
      "mode": "interactive",
      "name": "general"
    },
    {
      "path": "announcements",
      "type": "text",
      "mode": "broadcast",
      "name": "Announcements",
      "keyAccess": "members"
    },
    {
      "path": "community",
      "type": "text",
      "mode": "community",
      "name": "Community",
      "speakerCap": 200,
      "idleEvictDays": 7
    },
    {
      "path": "engineering",
      "type": "category",
      "name": "Engineering",
      "children": [
        { "path": "engineering/backend", "type": "text", "mode": "interactive" },
        { "path": "engineering/fips",    "type": "text", "mode": "interactive" }
      ]
    },
    {
      "path": "voice/lounge",
      "type": "voice"
    }
  ],
  "roles": [...],
  "customEmoji": [],
  "vtcCompliance": {},
  "mlsGroupID": "base64url...",
  "prevStateCID": "bafyrei...",
  "seq": 42,
  "sig": "base64url..."
}
```

`sig` is an Ed25519 signature over the document, signed per §13.1.1 by the Space owner's authentication key or a delegated admin's key. Space state and channel state are signed only by these CO keys (ARCHITECTURE S4). A Relay or other IO key MUST NOT sign Space or channel state, and clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state.

`acceptedDIDMethods` is an optional list of the user DID methods (§2.1) the CO accepts for members of the Space. When it is absent, all methods of §2.1 are accepted. Clients enforce it: a client MUST NOT issue a `SpaceInvite` (§4.3) to, or add to any of the Space's MLS groups, a DID whose method is not listed, and MUST NOT join a Space whose list excludes its own DID method. A client that sees a member with an unlisted method (for example, after the list is narrowed) SHOULD flag that member to admins, who MAY remove them. The list applies to user identities only, not to device keys or service identities.


## 3.4 Space State Distribution

*Binds: CO.*

Space state reaches members from the CO, never from a Relay topic. No gossipsub topic, Relay API or other IO-visible address carries a Space CID, MLS group ID or other Space identifier (ARCHITECTURE S1).

**Space endpoint.** Every Space has one or more **Space endpoints**: HTTPS services operated by the CO (ARCHITECTURE §2.2) that serve the signed Space state chain (§3.3) and every record it references by CID, including moderation records (§4.5), `ChannelShareAgreement` and `ChannelShareRevocation` records (§8), and the compliance configuration (§7.2). A Space endpoint is a CO component: it knows membership and authenticates members. It serves:

```
GET <spaceEndpoint>/head     → CID of the current Space state document
GET <spaceEndpoint>/<cid>    → the record with that CID, exactly as signed
```

Clients MUST verify each fetched record against its CID and its signature chain (§3.3) and MUST NOT trust the endpoint for anything the signatures do not prove; an endpoint can withhold state but cannot forge it (ARCHITECTURE S4).

**Broadcast keys.** The Space endpoint also serves the content keys of the Space's `broadcast` channels (§5.2.1.4):

```
GET <spaceEndpoint>/broadcast-key/<channelCID>              → current BroadcastKey
GET <spaceEndpoint>/broadcast-key/<channelCID>/<keyEpoch>   → BroadcastKey of that keyEpoch
```

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "BroadcastKey",
  "channelCID": "bafyrei...",
  "keyEpoch": 7,
  "key": "base64url...",
  "notBefore": "2026-10-16T00:00:00Z",
  "sig": "base64url..."
}
```

`key` is 16 random bytes generated by the CO (the key length of AES-128-GCM). `keyEpoch` is an unsigned integer that starts at 0 and increases by one on every rotation. `notBefore` is the time from which posters MUST use this key. `sig` is signed per §13.1.1 by the Space owner or a delegated admin, as for Space state (§3.3); clients MUST verify it and MUST reject a `BroadcastKey` whose `channelCID` is not a `broadcast` channel of the Space. The channel entry's `keyAccess` field selects the policy: `members` (the default) or `public`. For `members`, the endpoint serves `BroadcastKey` records only under the access control below, to members permitted to read the channel, to holders of a role in the channel's `broadcasterRoles`, and to the `loggerDID` of an enabled compliance configuration (§7.2) whose scope covers the channel. For `public`, the CO publishes `BroadcastKey` records as public Space state: the endpoint serves them without authentication, and the CO MAY mirror them like other public Space state. The mechanism is the same in both cases; only the access policy differs. When the CO stops serving the channel to a member, it MUST rotate the key (§5.2.1.4) and MUST NOT serve that member any `BroadcastKey` with a higher `keyEpoch`.

**Locating the endpoint.** The CO lists its Space endpoint URLs in the `spaceEndpoint` array of each `SpaceInvite` (§4.3) and `SpaceAd` (§10.3.2), and MAY list them as an `AgoraSpaceEndpoint` service entry in the Space owner's DID document. A CO changes endpoints by publishing new URLs through these same records; Space identity (genesis CID) is unaffected.

**Access control.** For a private Space, the endpoint MUST serve state only to clients that authenticate as current members (by DID authentication to the CO) or that present an unexpired `SpaceInvite` naming them or an open-link invite token. For a public Space, the endpoint serves non-members the access-controlled view of §4.4, signed by the owner or a delegated admin; it is a separate signed document and is never a substitute for the members' chain. Because the endpoint is the CO, its knowledge of who fetches state is not an IO observation.

**Real-time notification.** When Space state changes, the signer SHOULD send the new head CID to members as an MLS application message of type `SpaceStateHead` (field `stateCID`) in the Space's MLS group (`mlsGroupID`, §3.3) and MAY send it in channel groups. Recipients fetch and verify the new state from the Space endpoint. The notification needs no signature of its own because the state it points to is signed. Clients SHOULD also poll `/head` on reconnect.

**Mirroring.** A CO MAY mirror a public Space's state chain on IPFS by CID; doing so is a CO publication. Records that name members other than the owner and admins (the state of a private Space, the moderation log, any state carrying `regulatedMembers`) MUST NOT be stored on IO infrastructure in the clear. The CO either holds them only at the Space endpoint or stores them on IO infrastructure as **group-encrypted blobs**.

**Group-encrypted blob.** A group-encrypted blob is `epoch || nonce || AEAD(key, nonce, record, aad = "agora/blob/v1" || epoch)`, where `key` is `MLS-Exporter("agora blob", "", Nk)` of the MLS epoch in which it is written, the AEAD is that of the group's ciphersuite, `epoch` is a big-endian uint64 in the clear, and `nonce` is freshly random. It is addressed by the CID of the whole ciphertext. Only members of that epoch can decrypt it. An IO storing it holds only an opaque CID (ARCHITECTURE §5 item 4).
