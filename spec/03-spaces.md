# 3. Spaces and Space State

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 485–583 (§3.1–3.3).


*Binds: both.*

## 3.1 Participants

Agora separates the Infrastructure Operator (IO), which runs Relays and other infrastructure, from the Communications Operator (CO), which runs a community; for a Space the CO is the Space owner and its delegated admins (ARCHITECTURE §2). A Relay is an IO component.

- **Client** — a user agent (web browser, desktop application, mobile app). Connects to one or more Relays. Has access to the user's cryptographic keys and MLS state, either directly (software keystore) or via a co-located secure boundary (OS Secure Enclave, hardware security key, HSM). Responsible for all encryption and decryption operations; those operations SHOULD be performed inside the secure boundary wherever the platform supports it.
- **Relay** — an always-on server that participates in gossipsub, caches recent messages within a configured retention window, serves WebTransport and WebSocket endpoints for clients, and optionally pins IPFS content. Anyone may operate a Relay; no permission is required.
- **Peer** — any participant in the gossipsub mesh, including both Relays and clients with persistent connections.

## 3.2 Space and Channel Hierarchy

A **Space** is a named collection of channels, analogous to a Discord server. A **Channel** is a named, typed stream of messages within a Space.

Every channel has a **mode** that determines its encryption and membership model:

| Mode | MLS group | Who can post | Encrypted | Use case |
|---|---|---|---|---|
| `interactive` | All members (≤ 200) | All members | Yes — full MLS E2EE | Team channels, DMs, small communities |
| `community` | Active speakers only (≤ `speakerCap`) | Space members in speaker group | Yes — full MLS E2EE for speakers | Large community channels |
| `broadcast` | None | Space admins / designated posters | No — signed but readable | Announcements, release notes |

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

Channel nesting is structural only — a parent channel (such as `engineering`) can itself be a message channel, a category header, or both. The namespace is a tree; there is no enforced depth limit.

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
  "owner": "did:key:z6Mk...",
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
      "name": "Announcements"
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

