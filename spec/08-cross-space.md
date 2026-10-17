# 8. Cross-Space Channel Sharing

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 3939–4083 (§18).


*Binds: both (CO throughout; relays and SFUs only verify admission, §8.6).*

## 8.1 Overview

A channel MAY be shared across Space boundaries, giving members of multiple Spaces access to the same message stream, history, and MLS group. From any member's perspective in either Space, the shared channel appears as a normal channel in their sidebar; there is no visible workspace transition or foreign-context indicator.

Agora channel sharing is structurally simpler than analogous features in centralized systems (like Slack Connect) because a channel's identity does not depend on any server: it is a random `channelID` fixed at creation (§3.3). A channel shared between Space A and Space B is the same MLS group, with the same `channelID`, the same channel admission key and the same `channelToken` (§5.2.2); there is no synchronization problem because there is no duplication.

## 8.2 Home Space and Guest Spaces

Every shared channel has exactly one **home space**: the Space whose namespace contains the channel's canonical path and whose admin is responsible for channel state mutations. There MAY be one or more **guest spaces** whose members access the channel via a local alias path.

The home/guest distinction governs:
- Namespace ownership (home space owns the path)
- Channel state mutations (home space admin signs them)
- Compliance logging (home space's configuration applies to all members, including guests)
- Channel deletion (only the home space owner can delete; §3.6)

Guest space members have full read/write access to the channel's message stream, subject to the roles negotiated in the `ChannelShareAgreement` (§8.3). They are full MLS group members, not observers or read-only participants, unless the agreement specifies otherwise.

## 8.3 Channel Share Agreement

Sharing a channel requires bilateral authorization: the home space admin and the guest space admin both sign a `ChannelShareAgreement`. Neither side can unilaterally impose sharing on the other.

```json
{
  "@type": "ChannelShareAgreement",
  "schemaVersion": "1",
  "homeSpace": "agora://bafkrei...",
  "homeChannelID": "base64url...",
  "guestSpace": "agora://bafkreixyz...",
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
  "homeAdminDID": "did:key:z6MkHomeAdmin...",
  "guestAdminDID": "did:key:z6MkGuestAdmin..."
}
```

`guestAlias` is the channel path under which the shared channel appears in the guest space's sidebar. It is a local display alias only; the channel's identity remains `homeChannelID`, the shared channel's `channelID` in the home Space's state (§3.3). `guestRoles` is the list of guest space roles whose members are eligible for admission. `guestPermissions` defines the capability constraints applied to guest space members in this channel, independently of their role in their own space.

The agreement has no `id` member; it is referenced by the CID of its signed envelope (§13.1), as `agreementCID` does below. It is stored as an IPLD node, CID-referenced from both space state documents, and served by both Spaces' endpoints and announced to each Space's members in-band, like any Space state change (§3.4).

The agreement is a CO-to-CO document, signed per §13.1.1 by both `homeAdminDID` and `guestAdminDID`: the envelope `sig` carries one entry for each, and both are CO keys of the respective Spaces (S4). It links two Spaces, so it is never sent on a gossipsub topic and is not stored on IO infrastructure in the clear; it confers no authority on any IO.

## 8.4 Member Admission

When a `ChannelShareAgreement` is established and published in both Spaces' state, conformant clients from the guest space whose roles match `guestRoles` are eligible to join the shared channel's MLS group. Admission follows the standard MLS Add flow, initiated either by:

- A home space admin issuing a Welcome to the guest member directly, or
- A guest space admin issuing a bulk Welcome on behalf of all eligible members (this requires that the guest admin is themselves already an MLS group member, admitted by the home space admin as part of agreement setup).

Clients accept such a Welcome only from a committer authorized to add members under the home space state and the agreement (ARCHITECTURE §6.3).

The recommended flow is: home space admin admits the guest space admin first; guest space admin then admits their eligible members. This distributes the Commit workload and avoids requiring the home admin to manage foreign space membership individually.

Guest members appear in the channel participant list with a visual indicator of their home space (a space icon or badge), distinguishable from home space members. Clients SHOULD display the member's display name from their own space's profile, with the foreign space indicator making affiliation clear.

## 8.5 Namespace Resolution

A guest space member sees the channel at `guestAlias` in their space sidebar. Internally, the client resolves this alias to the home channel's `channelID`, obtains the channel's admission key and relays from the home Space (§8.6), and subscribes to the channel's `channelToken`. The alias is purely a display and navigation convenience; all protocol operations (message send, history fetch, MLS operations) use the home channel's identity.

The guest space's state document records the alias mapping:

```json
"sharedChannels": [
  {
    "@type": "SharedChannelAlias",
    "aliasPath": "shared/example-backend",
    "homeChannelID": "base64url...",
    "agreementCID": "bafkrei...",
    "homeSpaceCID": "bafkrei..."
  }
]
```

Clients resolve `guestAlias` → `homeChannelID` before any protocol operation. If the agreement is revoked (§8.7), the alias entry is removed from the guest space state and clients remove the channel from their sidebar on next state refresh.

## 8.6 Admission Key and Relays

The home Space's CO is the only CO that issues and registers anything for a shared channel. The guest CO registers nothing with any IO for it.

- **Admission key.** The home CO generates the shared channel's admission key, rotates it, and registers it with the relays (and other IOs, such as its SFU, §8.9) that hold a `ServiceAgreement` with the home CO's billing DID (§5.2.2, §10.5.3). It serves the key from the home Space endpoint at `<spaceEndpoint>/admission-key/<channelID>` to home members and to eligible guest members. It also serves eligible guest members the home Space's non-member view (§4.4), which carries the shared channel's entry and the admins without `members`: that view MUST include the shared channel's entry and every admin entry whose scope covers it, even when the view served to other non-members hides the channel (§4.4); guest clients validate a shared-channel Welcome's adder (§8.4) and the channel's `ChannelAdmissionKey` against that view.
- **Guest eligibility.** A guest member authenticates to the home Space endpoint by the exchange of §3.5, which the endpoint applies to guests as follows: in place of membership of the home Space, it checks that the DID holds a role in `guestRoles` under the guest Space's current state and that the agreement is unexpired and unrevoked. To check this, the home Space endpoint fetches the guest Space's state from the guest Space endpoint, which MUST serve it to the home Space's CO, authenticated per §3.5 as `homeAdminDID` (which §3.5 admits for reads of the guest Space's state only), for as long as the agreement is in force. A guest CO that does not accept this does not sign the agreement.
- **Removal.** Eligibility is the only thing the home CO checks for a guest, so a guest admin removes a guest member from the shared channel by first changing the guest Space state so that the member holds no role in `guestRoles`, and then committing the member's MLS Remove. The home Space endpoint MUST use guest Space state fetched no more than one hour earlier. When it finds that a DID it has served the key to is no longer eligible, the home CO rotates the admission key (§5.2.2) and does not serve the new key to that DID.
- **Relays.** Guest members learn the channel's relay list from the home Space endpoint, as home members do (§10.3.5), and connect to the home CO's relays. They need no relay of their own Space.

Relays route by `channelToken` and see one registration under one billing DID, so they do not learn which Space a subscriber belongs to, that the channel is shared, or the contents of the `ChannelShareAgreement` (S1). Relays verify `admissionSig` as for any channel; guest members need no other Relay-side admission. If the home CO's relays are reachable only on a private network, such as a Tailscale overlay, the home CO MUST make them reachable to guest members, for example by adding guest devices to that network or by registering the key with a relay guest members can reach.

## 8.7 Revocation

Either party MAY revoke the `ChannelShareAgreement` by publishing a `ChannelShareRevocation`, signed per §13.1.1 by `revokedBy`:

```json
{
  "@type": "ChannelShareRevocation",
  "agreementCID": "bafkrei...",
  "revokedBy": "did:key:z6MkRevoker...",
  "revokedBySpace": "agora://bafkrei...",
  "reason": "partnership-ended",
  "ts": "2026-03-12T00:00:00Z"
}
```

On revocation:

1. The revoking admin issues MLS Remove commits for all members of the foreign space from the channel's MLS group, and the home CO rotates the channel admission key and stops serving it to guest members (§8.6). When the guest admin revokes, the home CO does this as soon as it receives the revocation.
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

Voice channels MAY be shared using the same `ChannelShareAgreement` mechanism. All VTC semantics (§6) apply unchanged: the shared voice channel has one MLS group, one set of call state messages, and one SFU if configured. The SFU used is the home space's SFU, declared in the home space state document and registered with the channel's admission key by the home CO (§8.6). Guest space members connect to the home space's SFU directly and admit themselves with the admission key (§6.6).

If the home space does not have an SFU configured and the shared voice channel exceeds the mesh threshold (§6.5), the home space admin is responsible for provisioning one. The `ChannelShareAgreement` MAY specify a minimum SFU capacity as a precondition for guest space participation.

---

