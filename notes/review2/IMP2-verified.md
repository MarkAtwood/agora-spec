# IMP2 verified

Verifier pass over notes/review2/IMP2.md. Each finding was checked against the cited text, a grep of spec/ and ARCHITECTURE.md, and `bd memories agora`. No finding attacks a recorded decision. Several are narrowed below.

### IMP2-1: A stamped but unpublished Commit blocks every later Commit in the channel
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:27, :30; spec/14-jmap.md:218, :222
- Fix: The losing test at 05:27 is "an earlier position holds an `op` that opens under the same epoch's sealing key ... to a Commit". It needs only the sealing layer and the clear `content_type` (05:280), not a valid Commit, and it does not need the winner to be published. The sealing key is a per-epoch MLS exporter output (09:79), so any epoch-N member can trigger this, including a member about to be Removed. The republish clause at 14:222 ("any member holding the pair MAY publish it") covers only operation streams, because 14:218 sends commit stamps in the routing envelope instead. Fix: (1) the earliest stamped Commit that fully validates (unseal, MLS-decrypt, RFC 9420 validation) wins, and receivers skip invalid ones; (2) extend 14:222 to commit streams: any member that sees a valid stamped Commit in the log but not on the channel within T publishes it in a routing envelope it signs with the admission key, carrying the existing `commitStamp`.
- Needs decision: yes. Which rule ends a stamped Commit that is never published: (a) anyone republishes it, the existing operation-stream rule extended (recommended); (b) it expires after T and the next position wins. The reviewer's option (c), where the sequencer withholds `n`, couples the sequencer to relays. Reject it.

### IMP2-2: The commit stream changes on admission key rotation, so competing Commits can be stamped on different streams
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:27; spec/14-jmap.md:160-162, :207, :238
- Fix: Confirmed against 10-relays.md:839. The old key stays registered for a RECOMMENDED 300 s grace period after rotation, and rotation follows exactly the removal Commits (05:257). The sequencer admits both tokens in that window (14:207), so two committers for epoch N+1 can be stamped on unrelated streams that each start at 0. §14.4.4 "Closing a stream" (14:238) covers only operation streams.
- Needs decision: yes. (a) Name the commit stream from a non-rotating member secret. The sequencer then cannot check `stream` against `channelToken` (14:207 "stream MUST be the operation stream or the commit stream of that channelToken"), so the admission rule changes as well. (b) Keep the token-based name, add a commit-stream closing rule that parallels 14:238, and require committers to check the previous stream to its end before submitting (recommended: it reuses the existing closing mechanism and leaves sequencer admission unchanged).

### IMP2-3: Guardian transfer completion fails the §3.3 signer rule, and the two fork rules disagree
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/03-spaces.md:166; spec/04-access-control.md:19-22; spec/05-messaging.md:32
- Fix: The signer-rule defect is real. 03:166 exempts only a document "signed by the guardian threshold", while the completion at 04:20 is signed by `newOwner`. The fork-rule conflict is narrower than described. 03:352 makes every `seq` exactly one more than its predecessor's, so siblings at a fork always have equal `seq`, and the "higher `seq`" scenario cannot occur. What remains: 04:19 says a late objection "has no effect" without saying whether it is invalid. If it is a valid owner-signed document, 05:32's owner preference beats the completion, contrary to 04:22. Fix: (1) extend the 03:166 exception to a completion signed by `pendingTransfer.newOwner` after `ts + delaySeconds`; (2) state that clients MUST reject an objection whose `objectedAt` is at or after `ts + delaySeconds`; (3) state that owner and admin mutations during the pending period MUST carry `pendingTransfer` unchanged, and that clients reject one that drops it without `objectedAt`.
- Needs decision: no

### IMP2-4: The Space endpoint cannot tell when a kick has ended
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:311; spec/04-access-control.md:98
- Fix: 03:311 withholds keys while a Kick is "standing", and 04:98 ends the kick only through an MLS re-Add, which the endpoint never sees. No grep hit defines an end record. Add an admin-signed record that ends a `KickRecord` for listed channels, distributed like other moderation records (04:96). The re-adding admin publishes it before the Add, and the endpoint checks it.
- Needs decision: no

### IMP2-5: Community-channel key access rules contradict each other
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:311; spec/05-messaging.md:49, :132
- Fix: 03:311 serves keys by role, while 05:49 and 05:132 serve them "only to members of the speaker group". The endpoint has no defined way to learn the speaker group. The broadcast decision memo ("non-speakers can't read") is met either way, because MLS protects the content.
- Needs decision: yes. (a) Role-based, as in 03:311: delete the speaker-only sentences at 05:49 and 05:132, and evictions do not rotate (recommended). (b) Speaker-only, with a SpeakerBot-signed speaker list for the endpoint and a rotation on every eviction.

### IMP2-6: The DM admission host member list has no bootstrap, Add ordering or freshness rule
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:150-158; spec/07-compliance.md:285
- Fix: Sub-points (1) creation authority, (2) the PUT-before-Welcome ordering, (4) replay freshness, and the missing PUT body and status codes are confirmed. The path exists (04:155), but the body encoding and codes do not. Drop sub-point (3), the rogue member. Any DM member can already Remove the others by MLS Commit (04:28, RFC 9420 default), so a member who rewrites the list gains no new power, and the optional Commit-hash rule is unneeded. Fix: the host accepts the first `DMMembers` for a `groupID` only from a DID it hosts; the committer of an Add MUST get a 2xx on the PUT before delivering Welcomes; the host rejects a `DMMembers` whose `ts` is not later than the last accepted one or is more than 300 s from its clock; the body is the `application/cbor` envelope, with 204, 400, 401, 403 and 409.
- Needs decision: no

### IMP2-7: `agora_admission_host` is in `required_capabilities`, but clients only advertise 0xF0A1
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:73; spec/04-access-control.md:158; spec/05-messaging.md:122-127
- Fix: RFC 9420 requires every leaf to support each extension listed in `required_capabilities`. Change 05:73 to "lists 0xF0A0 and 0xF0A1 in its leaf `capabilities.extensions`", and add the check to the KeyPackage validation list in §5.2.1.1.
- Needs decision: no

### IMP2-8: No procedure to move a DM group's admission host
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:150, :158, :259
- Fix: No grep hit covers a host change. The leave procedure at 04:259 does not mention it either, even when the initiator is the one leaving.
- Needs decision: yes. (a) A member-initiated GroupContextExtensions move after a PUT of the member list to the new host, with the old host free to stop after a stated period (recommended). (b) The host serves for the group's life. (c) The group ends, and the remaining members create a new one.

### IMP2-9: `did:key` leaves fail the IdentityChanged rule and compliance verification
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:541, :550; spec/07-compliance.md:142; spec/05-messaging.md:73
- Fix: As described. 02:509 already uses the right two-branch form ("a current `authentication` key of that DID, or for `did:key` a valid device binding"). Apply the same branch at 02:541, 02:550 and 07:142 step 6.
- Needs decision: no

### IMP2-10: Shared-channel guests cannot get the home state they need, and the home endpoint cannot authenticate to the guest endpoint
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/08-cross-space.md:85-92, :98; spec/03-spaces.md:343; spec/04-access-control.md:88
- Fix: Both gaps are real. 03:343 limits guests to "that channel's records only", and 03:343 has no clause for `homeAdminDID` at the guest endpoint, although 08:98 requires the guest endpoint to serve it. Drop the claim that this puts a person's device key on a server: §4.1 recommends a service DID for organizational CO keys, so the claim is speculative. The fix follows from existing rules. The non-member view of §4.4 already exists and carries channels and admins without `members`, and option (b), guest-side re-signing, would violate S4 (only the home CO signs home authority). Fix: the home endpoint serves eligible guests the §4.4 non-member view, and guest clients validate the Welcome adder and `ChannelAdmissionKey` against it; add to 03:343 that a Space endpoint accepts §3.5 auth from the counterparty admin DID of an in-force `ChannelShareAgreement` naming it, for state reads only.
- Needs decision: no

### IMP2-11: A new device has no source for the user's Spaces and endpoints
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:496-509; spec/03-spaces.md:315; spec/04-access-control.md:88
- Fix: Endpoints come only from a `SpaceInvite`, a `SpaceAd` or the owner's DID document (03:315), and the self-group contents (02:498-502) carry none of them. Add a single-author self-group record that lists each Space's genesis CID and `spaceEndpoint`. The existing device sends it before step 3 of 02:507.
- Needs decision: no

### IMP2-12: Non-member subscribers of a public broadcast channel cannot perform the poster check
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:200; spec/03-spaces.md:180, :311
- Fix: As described. The public view omits `members` (03:180), so the MUST at 05:200 cannot be evaluated.
- Needs decision: yes. (a) A CO-signed `broadcasters` list in the public view (recommended). (b) A poster list in `BroadcastKey`. (c) Waive the check for non-members and show an unverified mark.

### IMP2-13: History reads and blob uploads exist only on the optional JMAP sync API
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:579-580 (§10.4.3 list), :636; spec/11-transport.md:173, :389, :507-513
- Fix: The decision follows from existing text. 11-transport.md:12 ("JMAP is used only for history and blobs") and the §11.8.8 table (history and blob upload: JMAP yes, live stream no) already settle it. Fix: add "Implement the JMAP sync API (`jmap-sync-v1`, §11.8)" to the §10.4.3 MUST list; change 10:636 "through the live protocol and the JMAP sync API" to "through the JMAP sync API"; state that the upload response `blobId` is the CID text form of the uploaded bytes.
- Needs decision: no

### IMP2-14: Live-protocol Subscribe and Publish outcomes are underspecified
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:101-104, :126-132, :173, :181, :188; spec/10-relays.md:845-850
- Fix: As described. The `Error.token` comment says it is "for token-withdrawn", so it would need widening to `unknown-token`. Apply the reviewer's fix: one Ack for the request plus one `Error` without `id` naming each unregistered token; define `expired`; answer a duplicate Publish with `Ack` carrying the existing `cid`.
- Needs decision: no

### IMP2-15: A message request accepted after relay retention cannot catch up
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:211; spec/05-messaging.md:28, :420
- Fix: Real, but the fix follows from existing text. 04:211 makes "MUST NOT authenticate ... or fetch" an explicit privacy rule with only the regulated-member exception (04:213, 07:285), so option (a) would reverse it. 05:28 already uses "must be removed and re-added" for a member that cannot follow. Generalize: a client that finds it cannot reach the group's current epoch because Commits have left relay retention (after a request, or after any long offline period) deletes the group state and tells the user that a member must re-add them.
- Needs decision: no

### IMP2-16: The Client conformance class omits §2.6 and §2.7
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/01-overview.md:79
- Fix: Add §2.6 and §2.7 to the Client row. Drop the second half of the fix: the KeyPackage host row (01:85) already lists §5.2.1.1, which defines the `leaf` parameter.
- Needs decision: no

### IMP2-17: Form of `ChannelAdmissionKey.relays` entries and the DM key response encoding are undefined
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/03-spaces.md:291-295, :313; spec/04-access-control.md:150; spec/10-relays.md:525
- Fix: Apply the reviewer's text. Each entry is a Relay manifest origin, with endpoints read from §10.2.1. The DM host returns the `application/cbor` envelope with `sig` absent, using the status codes of 03:313. Without the second sentence, 03:313's "with `sig` present" reads as applying to DM hosts too.
- Needs decision: no

### IMP2-18: Broadcast `seq` is counted per `kid`, which every device of a `did:key` poster shares
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:200
- Fix: As described. Per the did:key decision memo, devices copy the identity key. Add a per-device value to the `BroadcastMessage` body, for example the device's leaf signature key, which is already unique per device under the did:key decision, and count `seq` per (`kid`, device).
- Needs decision: no

### IMP2-19: §12.9 cites a field that no longer exists
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/12-security.md:179
- Fix: The only occurrence of `x-agora-timestamp` in spec/ is 12:179. Replace it with "the RFC 9421 `created` parameter (§10.2.3)".
- Needs decision: no

### IMP2-20: Pinning cannot work in DM groups
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:445, :465; spec/14-jmap.md:62, :153
- Fix: 14:153 already says that without a sequencer, `sequenced-v1` types are read-only, and DM groups have no sequencer. State at 05:445 that pins are unavailable in DM groups, and drop "in a group chat, admins". The single-author last-writer-wins alternative would add a mechanism where the existing rule already decides.
- Needs decision: no

## Counts

- CONFIRMED: 15 (IMP2-1, 2, 4, 5, 7, 8, 9, 11, 12, 13, 14, 17, 18, 19, 20)
- CONFIRMED-ADJUSTED: 5 (IMP2-3, 6, 10, 15, 16)
- REJECTED: 0
- By severity: P1 1 (IMP2-1); P2 14; P3 5.
- Needs decision: IMP2-1, IMP2-2, IMP2-5, IMP2-8, IMP2-12. IMP2-10, IMP2-13 and IMP2-15 were changed to no, because existing text settles them.
