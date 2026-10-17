# 8. Cross-Space Channel Sharing

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3939–4083 (§18).


*Binds: both (CO throughout; §8.6 peering also binds IO).*

## 8.1 Overview

A channel MAY be shared across Space boundaries, giving members of multiple Spaces access to the same message stream, history, and MLS group. From any member's perspective in either Space, the shared channel appears as a normal channel in their sidebar; there is no visible workspace transition or foreign-context indicator.

Agora channel sharing is structurally simpler than analogous features in centralized systems (like Slack Connect) because channels are already identified by content-addressed CID rather than opaque server-internal IDs. A channel shared between Space A and Space B is the same MLS group, the same IPLD history DAG, and the same `channelToken`; there is no synchronization problem because there is no duplication.

## 8.2 Home Space and Guest Spaces

Every shared channel has exactly one **home space**: the Space whose namespace contains the channel's canonical path and whose admin is responsible for channel state mutations. There MAY be one or more **guest spaces** whose members access the channel via a local alias path.

The home/guest distinction governs:
- Namespace ownership (home space owns the path)
- Channel state mutations (home space admin signs them)
- Compliance logging (home space's configuration applies to all members, including guests)
- Channel deletion (only the home space owner can delete)

Guest space members have full read/write access to the channel's message stream, subject to the roles negotiated in the `ChannelShareAgreement` (§8.3). They are full MLS group members, not observers or read-only participants, unless the agreement specifies otherwise.

## 8.3 Channel Share Agreement

Sharing a channel requires bilateral authorization: the home space admin and the guest space admin both sign a `ChannelShareAgreement`. Neither side can unilaterally impose sharing on the other.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ChannelShareAgreement",
  "schemaVersion": "1",
  "id": "urn:agora:csa:bafyrei...",
  "homeSpace": "agora://bafyrei.../",
  "homeChannel": "agora://bafyrei.../engineering/backend",
  "guestSpace": "agora://bafyxyz.../",
  "guestAlias": "shared/example-backend",
  "guestRoles": ["member", "engineer"],
  "guestPermissions": {
    "canSend": true,
    "canReact": true,
    "canUpload": true,
    "canDeleteOwn": true,
    "canDeleteOthers": false,
    "canInviteToChannel": false
  },
  "validFrom": "2026-03-12T00:00:00Z",
  "validUntil": "2027-03-12T00:00:00Z",
  "homeAdminSig": "base64url...",
  "guestAdminSig": "base64url...",
  "homeAdminDID": "did:key:z6MkHomeAdmin...",
  "guestAdminDID": "did:key:z6MkGuestAdmin..."
}
```

`guestAlias` is the channel path under which the shared channel appears in the guest space's sidebar. It is a local display alias only; the channel's canonical identity remains `homeChannel`. `guestRoles` is the list of guest space roles whose members are eligible for admission. `guestPermissions` defines the capability constraints applied to guest space members in this channel, independently of their role in their own space.

The agreement is stored as an IPLD node, CID-referenced from both space state documents, and served by both Spaces' endpoints and announced to each Space's members in-band, like any Space state change (§3.4).

The agreement is a CO-to-CO document: both signatures are CO keys of the respective Spaces (S4). It links two Spaces, so it is never sent on a gossipsub topic and is not stored on IO infrastructure in the clear; it confers no authority on any IO.

## 8.4 Member Admission

When a `ChannelShareAgreement` is established and published in both Spaces' state, conformant clients from the guest space whose roles match `guestRoles` are eligible to join the shared channel's MLS group. Admission follows the standard MLS Add flow, initiated either by:

- A home space admin issuing a Welcome to the guest member directly, or
- A guest space admin issuing a bulk Welcome on behalf of all eligible members (this requires that the guest admin is themselves already an MLS group member, admitted by the home space admin as part of agreement setup).

Clients accept such a Welcome only from a committer authorized to add members under the home space state and the agreement (ARCHITECTURE §6.3).

The recommended flow is: home space admin admits the guest space admin first; guest space admin then admits their eligible members. This distributes the Commit workload and avoids requiring the home admin to manage foreign space membership individually.

Guest members appear in the channel participant list with a visual indicator of their home space (a space icon or badge), distinguishable from home space members. Clients SHOULD display the member's display name from their own space's profile, with the foreign space indicator making affiliation clear.

## 8.5 Namespace Resolution

A guest space member sees the channel at `guestAlias` in their space sidebar. Internally, the client resolves this alias to the home channel's CID and connects to the home channel's MLS group and gossip topic. The alias is purely a display and navigation convenience; all protocol operations (message send, history fetch, MLS operations) use the home channel's identity.

The guest space's state document records the alias mapping:

```json
"sharedChannels": [
  {
    "@type": "SharedChannelAlias",
    "aliasPath": "shared/example-backend",
    "homeChannelCID": "bafyrei...",
    "agreementCID": "bafyrei...",
    "homeSpaceCID": "bafyrei..."
  }
]
```

Clients resolve `guestAlias` → `homeChannelCID` before any protocol operation. If the agreement is revoked (§8.7), the alias entry is removed from the guest space state and clients remove the channel from their sidebar on next state refresh.

## 8.6 Relay Coordination

The home channel's gossip topic (`v1/agora/channel/<channelToken>`) is where all messages flow. Guest space members subscribe to this topic via their own Relays. For this to work, the guest space's Relays must be peered with (or able to reach) the home channel's Relays.

Each CO engages Relays for the shared channel through its own `RelayServiceAgreement` (§10.5.1) by registering the shared group's access-key chain under it (S7). Neither agreement identifies the Space or the channel. Relays route by `channelToken` alone; they do not learn which Space a subscriber belongs to, that the channel is shared, or the contents of the `ChannelShareAgreement` (S1). Access is by MLS membership (ARCHITECTURE §6.2), so guest members need no Relay-side admission.

No special Relay configuration is required if both spaces' Relays participate in the same gossipsub mesh; this is the common case for public or semi-public spaces. For private spaces whose Relays are isolated (e.g., on a private Tailscale overlay), the two COs arrange peering between their IOs through their respective `RelayServiceAgreement`s; peering itself is an IO-to-IO relationship (ARCHITECTURE §5 item 7). The `ChannelShareAgreement` MAY include a `relayHints` array suggesting peering endpoints, for the COs' use; Relays do not read it:

```json
"relayHints": [
  "wss://relay.home-space.example.com",
  "wss://relay.guest-space.example.com"
]
```

## 8.7 Revocation

Either party MAY revoke the `ChannelShareAgreement` by publishing a signed `ChannelShareRevocation`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ChannelShareRevocation",
  "agreementCID": "bafyrei...",
  "revokedBy": "did:key:z6MkRevoker...",
  "revokedBySpace": "agora://bafyrei.../",
  "reason": "partnership-ended",
  "ts": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

On revocation:

1. The revoking admin issues MLS Remove commits for all members of the foreign space from the channel's MLS group.
2. The alias entry is removed from the guest space's state document.
3. The `ChannelShareRevocation` is stored in both space IPLD state chains and distributed like any Space state change (§3.4).
4. Clients of the guest space remove the channel from their sidebar on next state refresh.
5. Guest space members lose the ability to decrypt new messages immediately (the MLS epoch advances on the Remove commits); they retain locally cached history up to the revocation epoch.

Either admin may revoke unilaterally; the counter-party does not need to co-sign the revocation.

## 8.8 Compliance Logging Across Space Boundaries

The home space's compliance logging configuration (§7) applies to all messages in the shared channel regardless of the sender's space affiliation. A guest space member sending a message in a compliance-logged shared channel has that message captured by the home space's compliance logger.

Guest space members MUST be notified of this at channel join time. The client displays the home space's `retentionNotice` to guest members on first entry to the shared channel, clearly attributing it to the home space:

> "This channel is hosted by [Home Space Name] and is subject to their message retention policy: [retentionNotice text]"

If the guest space also has compliance logging enabled, its logger MAY also be added to the shared channel's MLS group, subject to home space admin approval (an additional MLS Add commit is required). Both loggers may simultaneously hold membership. The home space admin MAY reject a guest space's compliance logger by declining to commit its Add (and so never sending it a Welcome); in that case the guest space admin is responsible for any resulting regulatory non-compliance on their side.

## 8.9 Voice Channel Sharing

Voice channels MAY be shared using the same `ChannelShareAgreement` mechanism. All VTC semantics (§6) apply unchanged: the shared voice channel has one MLS group, one set of call state gossip, and one SFU if configured. The SFU used is the home space's SFU (declared in the home space state document). Guest space members connect to the home space's SFU directly.

If the home space does not have an SFU configured and the shared voice channel exceeds the mesh threshold (§6.5), the home space admin is responsible for provisioning one. The `ChannelShareAgreement` MAY specify a minimum SFU capacity as a precondition for guest space participation.

---

