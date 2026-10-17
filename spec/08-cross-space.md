# 8. Cross-Space Channel Sharing

> Binds: both (CO throughout; relays and SFUs only verify admission, §8.6). Source: import/agora-protocol-spec-unified.md lines 3939–4083 (§18).

## 8.1 Overview

A channel MAY be shared across Space boundaries, giving members of multiple Spaces access to the same message stream, history, and MLS group (RFC 9420). To any member in either Space, the shared channel appears as a normal channel in their sidebar. There is no visible workspace transition or foreign-context indicator.

Agora channel sharing is structurally simpler than analogous features in centralized systems (like Slack Connect) because a channel's identity does not depend on any server: it is a random `channelID` fixed at creation (§3.3). A channel shared between Space A and Space B is the same MLS group, with the same `channelID`, the same channel admission key, and the same `channelToken` (§5.2.2). There is no synchronization problem because there is no duplication.

## 8.2 Home Space and Guest Spaces

Every shared channel has exactly one **home Space**: the Space whose namespace contains the channel's canonical path and whose admin is responsible for channel state mutations. There MAY be one or more **guest Spaces**, whose members access the channel via a local alias path.

The home/guest distinction governs:
- Namespace ownership (the home Space owns the path)
- Channel state mutations (the home Space admin signs them)
- Compliance logging (the home Space's configuration applies to all members, including guests)
- Channel deletion (only the home Space owner can delete; §3.6)

Guest Space members have full read/write access to the channel's message stream, subject to the roles negotiated in the `ChannelShareAgreement` (§8.3). They are full MLS group members, not observers or read-only participants, unless the agreement specifies otherwise.

## 8.3 Channel Share Agreement

Sharing a channel requires bilateral authorization: the home Space admin and the guest Space admin both sign a `ChannelShareAgreement`. Neither side can unilaterally impose sharing on the other.

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

`guestAlias` is the channel path under which the shared channel appears in the guest Space's sidebar. It is a local display alias only. The channel's identity remains `homeChannelID`, the shared channel's `channelID` in the home Space's state (§3.3). `guestRoles` is the list of guest Space roles whose members are eligible for admission. `guestPermissions` defines the capability constraints applied to guest Space members in this channel, independently of their role in their own Space.

The agreement is a document between two Communications Operators (COs). It is signed per §13.1.1 by both `homeAdminDID` and `guestAdminDID`: the envelope `sig` carries one entry for each, and both are CO keys of the respective Spaces (ARCHITECTURE S4). Because it links two Spaces, it is never sent on a gossipsub topic and is not stored on Infrastructure Operator (IO) infrastructure in the clear. It confers no authority on any IO.

The agreement has no `id` member. It is referenced by the CID of its signed envelope (§13.1), as `agreementCID` does below. It is stored as an IPLD node and CID-referenced from both Space state documents. Both Spaces' endpoints serve it, and it is announced to each Space's members in-band, like any Space state change (§3.4).

## 8.4 Member Admission

When a `ChannelShareAgreement` is established and published in both Spaces' state, conformant clients from the guest Space whose roles match `guestRoles` are eligible to join the shared channel's MLS group. Admission follows the standard MLS Add flow, initiated by either:

- A home Space admin, issuing a Welcome to the guest member directly
- A guest Space admin, issuing a bulk Welcome on behalf of all eligible members. This requires the guest admin to be an MLS group member already, admitted by the home Space admin as part of agreement setup.

The recommended flow is that the home Space admin admits the guest Space admin first, and the guest Space admin then admits their eligible members. This distributes the Commit workload and spares the home admin from managing foreign Space membership individually.

Clients accept such a Welcome only from a committer authorized to add members under the home Space state and the agreement (ARCHITECTURE §6.3).

Guest members appear in the channel participant list with a visual indicator of their home Space (a Space icon or badge), which distinguishes them from home Space members. Clients SHOULD display the member's display name from their own Space's profile, with the foreign Space indicator making affiliation clear.

## 8.5 Namespace Resolution

A guest Space member sees the channel at `guestAlias` in their Space sidebar. Internally, the client resolves this alias to the home channel's `channelID`, obtains the channel's admission key and relays from the home Space (§8.6), and subscribes to the channel's `channelToken`. The alias is purely a display and navigation convenience. All protocol operations (message send, history fetch, MLS operations) use the home channel's identity.

The guest Space's state document records the alias mapping:

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

Clients resolve `guestAlias` → `homeChannelID` before any protocol operation. If the agreement is revoked (§8.7), the alias entry is removed from the guest Space state, and clients remove the channel from their sidebar on next state refresh.

## 8.6 Admission Key and Relays

The home Space's CO is the only CO that issues and registers anything for a shared channel. The guest CO registers nothing with any IO for it.

- **Admission key.** The home CO generates the shared channel's admission key, rotates it, and registers it with the relays (and other IOs, such as its Selective Forwarding Unit (SFU), §8.9) that hold a `ServiceAgreement` with the home CO's billing DID (§5.2.2, §10.5.3). It serves the key from the home Space endpoint at `<spaceEndpoint>/admission-key/<channelID>` to home members and to eligible guest members.
- **Home Space view.** The home CO also serves eligible guest members the home Space's non-member view (§4.4), which carries the shared channel's entry and the admins but not `members`. Even when the view served to other non-members hides the channel (§4.4), the view served to eligible guest members MUST include:
  - the shared channel's entry
  - every admin entry whose scope covers it
  - the home Space's `sequencer` and that channel's entry of the `closingHeads` of the latest home Space state that carried them, while the commit stream it names is within relay retention (§3.3)

  Guest clients validate a shared-channel Welcome's adder (§8.4) and the channel's `ChannelAdmissionKey` against that view.
- **Guest eligibility.** A guest member authenticates to the home Space endpoint with the exchange of §3.5. For a guest, the endpoint checks, in place of membership of the home Space, that the DID holds a role in `guestRoles` under the guest Space's current state and that the agreement is unexpired and unrevoked. To check this, the home Space endpoint fetches the guest Space's state from the guest Space endpoint. The guest Space endpoint MUST serve that state to the home Space's CO, authenticated per §3.5 as `homeAdminDID`, for as long as the agreement is in force. §3.5 admits `homeAdminDID` for reads of the guest Space's state only. A guest CO that does not accept this does not sign the agreement.
- **Removal.** The home CO checks only eligibility for a guest. A guest admin therefore removes a guest member from the shared channel in two steps: first, change the guest Space state so that the member holds no role in `guestRoles`; then commit the member's MLS Remove. The home Space endpoint MUST use guest Space state fetched no more than one hour earlier. When the home CO finds that a DID it has served the key to is no longer eligible, it rotates the admission key (§5.2.2) and does not serve the new key to that DID.
- **Relays.** Guest members learn the channel's relay list from the home Space endpoint, as home members do (§10.3.5), and connect to the home CO's relays. They need no relay of their own Space.

Relays route by `channelToken` and see one registration under one billing DID. They do not learn which Space a subscriber belongs to, that the channel is shared, or the contents of the `ChannelShareAgreement` (ARCHITECTURE S1). Relays verify `admissionSig` as for any channel, and guest members need no other relay-side admission. If the home CO's relays are reachable only on a private network, such as a Tailscale overlay, the home CO MUST make them reachable to guest members. It can do so, for example, by adding guest devices to that network or by registering the key with a relay that guest members can reach.

## 8.7 Revocation

Either party MAY revoke the `ChannelShareAgreement` unilaterally by publishing a `ChannelShareRevocation`, signed per §13.1.1 by `revokedBy`. The counter-party does not need to co-sign the revocation.

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

1. The revoking admin issues MLS Remove Commits for all members of the foreign Space from the channel's MLS group. The home CO rotates the channel admission key and stops serving it to guest members (§8.6). When the guest admin revokes, the home CO does this as soon as it receives the revocation.
2. The alias entry is removed from the guest Space's state document.
3. The `ChannelShareRevocation` is stored in both Spaces' IPLD state chains and distributed like any Space state change (§3.4).
4. Clients of the guest Space remove the channel from their sidebar on next state refresh.
5. Guest Space members lose the ability to decrypt new messages immediately, because the MLS epoch advances on the Remove Commits. They retain locally cached history up to the revocation epoch.

## 8.8 Compliance Logging Across Space Boundaries

The home Space's compliance logging configuration (§7) applies to all messages in the shared channel, regardless of the sender's Space affiliation. When a guest Space member sends a message in a compliance-logged shared channel, the home Space's compliance logger captures it.

A guest member's client MUST present the home Space's `retentionNotice` to its user, attributed to the home Space, before the user first sends in the shared channel. The client displays the notice on first entry to the shared channel:

> "This channel is hosted by [Home Space Name] and is subject to their message retention policy: [retentionNotice text]"

If the guest Space also has compliance logging enabled, its logger MAY also be added to the shared channel's MLS group, subject to home Space admin approval (an additional MLS Add Commit is required). Both loggers can then hold membership at the same time. The home Space admin MAY reject a guest Space's compliance logger by declining to commit its Add (and so never sending it a Welcome). In that case, the guest Space admin is responsible for any resulting regulatory non-compliance on their side.

## 8.9 Voice Channel Sharing

Voice channels MAY be shared using the same `ChannelShareAgreement` mechanism. All video teleconferencing (VTC) semantics (§6) apply unchanged: the shared voice channel has one MLS group, one set of call state messages, and one SFU if configured. The SFU used is the home Space's SFU, declared in the home Space state document and registered with the channel's admission key by the home CO (§8.6). Guest Space members connect to the home Space's SFU directly and admit themselves with the admission key (§6.6).

If the home Space does not have an SFU configured and the shared voice channel exceeds the mesh threshold (§6.5), the home Space admin is responsible for provisioning one. The `ChannelShareAgreement` MAY specify a minimum SFU capacity as a precondition for guest Space participation.

---
