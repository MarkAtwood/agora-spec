# Agora Protocol: Cross-Space Channel Sharing

> Binds: CO. Verbatim from `import/agora-protocol-spec-unified.md` lines 3939–4083 (§18). Section numbers are the source's and will be renumbered.

## 18. Cross-Space Channel Sharing

### 18.1 Overview

A channel MAY be shared across Space boundaries, giving members of multiple Spaces access to the same message stream, history, and MLS group. From any member's perspective in either Space, the shared channel appears as a normal channel in their sidebar — there is no visible workspace transition or foreign-context indicator.

Agora channel sharing is structurally simpler than analogous features in centralized systems (like Slack Connect) because channels are already identified by content-addressed CID rather than opaque server-internal IDs. A channel shared between Space A and Space B is the same MLS group, the same IPLD history DAG, and the same `channelToken` — there is no synchronization problem because there is no duplication.

### 18.2 Home Space and Guest Spaces

Every shared channel has exactly one **home space** — the Space whose namespace contains the channel's canonical path and whose admin is responsible for channel state mutations. There MAY be one or more **guest spaces** whose members access the channel via a local alias path.

The home/guest distinction governs:
- Namespace ownership (home space owns the path)
- Channel state mutations (home space admin signs them)
- Compliance logging (home space's configuration applies to all members, including guests)
- Channel deletion (only the home space owner can delete)

Guest space members have full read/write access to the channel's message stream, subject to the roles negotiated in the `ChannelShareAgreement` (§18.3). They are first-class MLS group members — not observers or read-only participants unless the agreement specifies otherwise.

### 18.3 Channel Share Agreement

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
  "guestAlias": "shared/wolfssl-backend",
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

`guestAlias` is the channel path under which the shared channel appears in the guest space's sidebar. It is a local display alias only — the channel's canonical identity remains `homeChannel`. `guestRoles` is the list of guest space roles whose members are eligible for admission. `guestPermissions` defines the capability constraints applied to guest space members in this channel, independently of their role in their own space.

The agreement is stored as an IPLD node, CID-referenced from both space state documents, and gossiped on both `v1/agora/space/<homeSpaceCID>` and `v1/agora/space/<guestSpaceCID>`.

### 18.4 Member Admission

When a `ChannelShareAgreement` is established and gossiped, conformant clients from the guest space whose roles match `guestRoles` are eligible to join the shared channel's MLS group. Admission follows the standard MLS Add flow, initiated either by:

- A home space admin issuing a Welcome to the guest member directly, or
- A guest space admin issuing a bulk Welcome on behalf of all eligible members (this requires that the guest admin is themselves already an MLS group member, admitted by the home space admin as part of agreement setup).

The recommended flow is: home space admin admits the guest space admin first; guest space admin then admits their eligible members. This distributes the Commit workload and avoids requiring the home admin to manage foreign space membership individually.

Guest members appear in the channel participant list with a visual indicator of their home space (a space icon or badge), distinguishable from home space members. Clients SHOULD display the member's display name from their own space's profile, with the foreign space indicator making affiliation clear.

### 18.5 Namespace Resolution

A guest space member sees the channel at `guestAlias` in their space sidebar. Internally, the client resolves this alias to the home channel's CID and connects to the home channel's MLS group and gossip topic. The alias is purely a display and navigation convenience — all protocol operations (message send, history fetch, MLS operations) use the home channel's identity.

The guest space's state document records the alias mapping:

```json
"sharedChannels": [
  {
    "@type": "SharedChannelAlias",
    "aliasPath": "shared/wolfssl-backend",
    "homeChannelCID": "bafyrei...",
    "agreementCID": "bafyrei...",
    "homeSpaceCID": "bafyrei..."
  }
]
```

Clients resolve `guestAlias` → `homeChannelCID` before any protocol operation. If the agreement is revoked (§18.7), the alias entry is removed from the guest space state and clients remove the channel from their sidebar on next state refresh.

### 18.6 Relay Coordination

The home channel's gossip topic (`v1/agora/channel/<channelToken>`) is where all messages flow. Guest space members subscribe to this topic via their own Relays. For this to work, the guest space's Relays must be peered with (or able to reach) the home channel's Relays.

No special Relay configuration is required if both spaces' Relays participate in the same gossipsub mesh — this is the common case for public or semi-public spaces. For private spaces whose Relays are isolated (e.g., on a private Tailscale overlay), explicit Relay peering must be established between the home and guest space operators. The `ChannelShareAgreement` MAY include a `relayHints` array suggesting peering endpoints:

```json
"relayHints": [
  "wss://relay.home-space.example.com",
  "wss://relay.guest-space.example.com"
]
```

### 18.7 Revocation

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
3. The `ChannelShareRevocation` is gossiped on both space topics and stored in both space IPLD state chains.
4. Clients of the guest space remove the channel from their sidebar on next state refresh.
5. Guest space members lose the ability to decrypt new messages immediately (the MLS epoch advances on the Remove commits); they retain locally cached history up to the revocation epoch.

Either admin may revoke unilaterally; the counter-party does not need to co-sign the revocation.

### 18.8 Compliance Logging Across Space Boundaries

The home space's compliance logging configuration (§17) applies to all messages in the shared channel regardless of the sender's space affiliation. A guest space member sending a message in a compliance-logged shared channel has that message captured by the home space's compliance logger.

Guest space members MUST be notified of this at channel join time. The client displays the home space's `retentionNotice` to guest members on first entry to the shared channel, clearly attributing it to the home space:

> "This channel is hosted by [Home Space Name] and is subject to their message retention policy: [retentionNotice text]"

If the guest space also has compliance logging enabled, its logger MAY also be added to the shared channel's MLS group, subject to home space admin approval (an additional MLS Add commit is required). Both loggers may simultaneously hold membership. The home space admin MAY reject a guest space's compliance logger by declining to issue a Welcome; in that case the guest space admin is responsible for any resulting regulatory non-compliance on their side.

### 18.9 Voice Channel Sharing

Voice channels MAY be shared using the same `ChannelShareAgreement` mechanism. All VTC semantics (§10) apply unchanged — the shared voice channel has one MLS group, one set of call state gossip, and one SFU if configured. The SFU used is the home space's SFU (declared in the home space state document). Guest space members connect to the home space's SFU directly.

If the home space does not have an SFU configured and the shared voice channel exceeds the mesh threshold (§10.5), the home space admin is responsible for provisioning one. The `ChannelShareAgreement` MAY specify a minimum SFU capacity as a precondition for guest space participation.

---

