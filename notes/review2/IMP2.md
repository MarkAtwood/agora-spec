# IMP2: Implementability of the new protocol pieces

Lens: could two independent implementers build the flows introduced or rewritten in b07bead / a5fdf42 / 9e7711f from the text alone, and would they interoperate? Every finding below traces to text introduced in b07bead (checked with `git log -S`).

Mechanical checks: all 8 CDDL blocks in spec/ parse with `cddlparser` (02:226, 02:523, 05:220, 06:110, 10:174, 10:749, 11:65, 14:187). The only cross-block reference, `PowProof` (05 to 10), resolves. All `json` blocks in spec/ and ARCHITECTURE.md are valid JSON or valid `"key": value` fragments. No syntax defects were found. The problems are semantic and are listed below.

### IMP2-1: A stamped but unpublished Commit blocks every later Commit in the channel
- Severity: P1
- Location: spec/05-messaging.md:27 (also :30); spec/14-jmap.md:220
- Evidence: "It then fetches that stream's log up to its own position (§14.4.3). If an earlier position holds an `op` that opens under the same epoch's sealing key and associated data (§5.2.2) to a Commit, its Commit has lost." / "A client whose Commit lost discards it ... re-proposes it as a new Commit for the winning epoch." / §14.4.3 lets "any member holding the pair" republish only for operation streams: "For a commit stream, the client carries the stamp in the Commit's routing envelope instead".
- Problem: The losing test needs only an earlier `op` whose sealing layer opens and whose clear `PrivateMessage` header says `content_type = commit`. It does not require a valid MLS Commit, and it does not require that the winner was ever published. A committer that crashes after stamping, or any current member acting on purpose, can submit such an `op` and never publish it. Every later committer for that epoch then concludes it lost and waits for a "winning epoch" that never arrives. A member can use this to block its own Remove indefinitely. Receivers are never told to read the commit stream log, so they cannot recover either.
- Suggested fix: Have the earliest *valid* Commit win. The committer fully processes the earlier `op` (unseal, MLS-decrypt, validate the Commit) and treats it as a winner only if it is valid. Add a rule for a stamped winner that is not published: any member that sees a valid stamped Commit in the commit-stream log but not on the channel within T seconds (e.g. 10 s) wraps it in a routing envelope (its own `ts`, `admissionSig`, the existing `commitStamp`) and publishes it. Receivers skip invalid stamped Commits and take the next lowest `n`.
- Needs decision: yes. (a) Earliest valid Commit wins, plus a republish-by-anyone rule (recommended). (b) A stamped Commit expires if it is not published within T, and the next position wins. (c) The sequencer withholds `n` until the routing envelope is published to it (this couples the sequencer to relays).

### IMP2-2: The commit stream changes on admission key rotation, so competing Commits can be stamped on different streams
- Severity: P2
- Location: spec/05-messaging.md:27; spec/14-jmap.md:159-162, :238; spec/05-messaging.md:256
- Evidence: "commit stream, `SHA-256("agora/commits/v1" || channelToken)`" / "A channel's streams change when its admission key rotates" / "Closing a stream. When a channel's admission key rotates (§5.2.2), its operation stream changes." (there is no closing rule for commit streams) / "Of two such Commits for one epoch, the one whose stamp has the lower `n` wins".
- Problem: Rotation happens exactly at removals, and members MUST refetch the key "after processing a Commit that removes a member". After such a Commit, some members hold keyEpoch k and others k+1, depending on when the CO rotated. Two committers for epoch N+1 then submit to two different commit streams. Each sees no earlier Commit in its own log, and both publish. Receivers compare `n` values from unrelated streams; the new stream starts at 0, so it usually wins. A late arrival after the 5-second window splits the group, which is the failure the sequencer was added to prevent.
- Suggested fix: Name the commit stream by a value that does not rotate and is known only to members, e.g. `SHA-256("agora/commits/v1" || MLS-Exporter("agora commit stream", group_id, 32))`, re-derived per epoch, or the stream of the epoch's first-held token. Alternatively, define a commit-stream closing rule that parallels §14.4.4 and require committers to check both the old and the new stream during the deregistration grace period.
- Needs decision: yes. (a) A per-epoch exporter-derived stream name, which the sequencer still cannot link to the channel (recommended; add the label to §13.3). (b) Keep the token-based name and add a closing rule plus a dual-stream check.

### IMP2-3: Guardian transfer completion fails the §3.3 signer rule, and the two fork rules disagree
- Severity: P2
- Location: spec/03-spaces.md:166; spec/04-access-control.md:18-22; spec/05-messaging.md:32
- Evidence: §3.3: "clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state. The one exception is a guardian transfer document, signed by the guardian threshold (§4.1)." §4.1 step 3: "`newOwner` signs a Space state document that ... sets `owner` to `newOwner`". §4.1: "If an objection and a completion both chain on the same document, the objection wins if its `objectedAt` is before `ts + delaySeconds`". §5.1.1: "the one with the higher `seq` wins; on equal `seq`, the one signed by the owner wins over one signed by an admin; otherwise the one whose CID is lower".
- Problem: The completion is signed by `newOwner`, who is neither owner nor admin under the prior state and is not the guardian threshold. A client that follows §3.3 rejects every completion. On a fork between an objection and a completion, §5.1.1 gives the owner-signed objection the win only on equal `seq`, while §4.1 decides by `objectedAt`. An objection that chains on a later document has a higher `seq` and wins under §5.1.1 even when `objectedAt` is too late under §4.1. Implementers who apply one rule or the other end on different heads.
- Suggested fix: Extend the §3.3 exception to the three guardian documents: a proposal signed by the threshold, an objection signed by the owner, and a completion signed by `pendingTransfer.newOwner` after `ts + delaySeconds`. In §5.1.1, state that a fork involving a document carrying or removing `pendingTransfer` is resolved by §4.1 first, then by the general rule. Also say whether ordinary owner or admin mutations during the pending period MUST carry `pendingTransfer` forward. As written, one that drops it is neither an objection nor a completion.
- Needs decision: no

### IMP2-4: The Space endpoint cannot tell when a kick has ended, so a re-added member cannot get the channel key
- Severity: P2
- Location: spec/03-spaces.md:311; spec/04-access-control.md:98
- Evidence: §3.4: the endpoint serves keys "to members permitted to read the channel (a role whose `channelAccess` covers it, §4.2, and no standing Kick or Ban for it, §4.5)". §4.5: "The member ... may be re-added to channels by an Admin, which ends the kick for those channels."
- Problem: A kick ends through an MLS Add, which the endpoint does not observe, and no record ends a `KickRecord`. One implementer treats a `KickRecord` as standing forever: the re-added member decrypts but cannot publish or subscribe. Another serves keys again on some heuristic.
- Suggested fix: Define an end-of-kick record, e.g. a `KickRecord` with `endsAt`, or a `KickLift` record signed by an admin and referenced from the moderation log. The re-adding admin publishes it, and the endpoint checks it.
- Needs decision: no

### IMP2-5: Community-channel key access rules contradict each other
- Severity: P2
- Location: spec/03-spaces.md:311; spec/05-messaging.md:49, :132
- Evidence: §3.4 serves keys "to members permitted to read the channel (a role whose `channelAccess` covers it ...)". §5.2.1: "the CO serves the channel's admission key ... only to members of the speaker group". §5.2.1.2: "Space members outside the speaker group are not served the channel's admission key".
- Problem: The speaker group is MLS membership managed by the SpeakerBot or admins. The Space endpoint has no defined way to learn it. Under §3.4, every role holder gets the key, so non-speakers can follow (but not decrypt) the channel. Under §5.2.1, only speakers do, and every idle eviction is a CO-authorized removal that rotates the key. Implementers will pick different rules, and the rotation load differs by orders of magnitude.
- Suggested fix: Pick one rule. If speaker-only, define how the endpoint learns the speaker set (e.g. a SpeakerBot-signed speaker list, or the SpeakerBot running the endpoint's check), and state whether evictions rotate the key.
- Needs decision: yes. (a) Role-based access as in §3.4; non-speakers can see traffic volume but cannot decrypt, and evictions do not rotate (recommended: simplest, and nothing is lost because content is MLS-protected). (b) Speaker-only, with a SpeakerBot-signed list and rotation on eviction.

### IMP2-6: The DM admission host member list has no bootstrap, no required update on Add, and no protection against a rogue member
- Severity: P2
- Location: spec/04-access-control.md:150-158; spec/07-compliance.md:285
- Evidence: "The initiator registers the list when it creates the group, and any listed member replaces it after a membership change, by a typed payload envelope of type `urn:agora:type:DMMembers` ... signed per §13.1.1 by a device key of a DID on the current list. When a replacement drops a DID, the host rotates the key."
- Problem: (1) Creation: no list exists yet, so nothing defines who may create an entry for a new `groupID`. A host that accepts any DID lets anyone register DM groups under the host's agreements and quota. (2) Add: no MUST requires the committer of an Add to PUT the new list before delivering the Welcome. A joiner that authenticates per §3.5 gets 403 and cannot fetch the key. (3) Any listed member can replace the list with any content, for example drop everyone else, and the host cannot check it against MLS state. (4) There is no `ts` freshness or monotonicity rule, so a replayed older `DMMembers` restores a dropped DID. No request or response encoding and no status codes are given for the PUT.
- Suggested fix: At creation, the host accepts the first `DMMembers` for a `groupID` only from a DID it hosts (the initiator). The committer of any Add MUST PUT the updated list, and get a 2xx, before delivering Welcomes. The host rejects a `DMMembers` whose `ts` is not later than the last accepted one, or more than 300 s off its clock. Define the body (`application/cbor` envelope), the 204/400/401/403/409 codes, and an optional rule that a replacement may only remove DIDs other than the signer's when it also references an MLS Commit hash. Otherwise accept the rogue-member DoS explicitly in §12.
- Needs decision: no

### IMP2-7: `agora_admission_host` is listed in `required_capabilities`, but clients are only required to advertise 0xF0A1
- Severity: P2
- Location: spec/04-access-control.md:158; spec/05-messaging.md:73
- Evidence: "extension type 0xF0A0 ... listed in `required_capabilities`" / "Every Agora client lists 0xF0A1 in its leaf `capabilities`."
- Problem: RFC 9420 (§7.2, §11.1) requires every member's leaf `capabilities.extensions` to include each extension named in `required_capabilities`. It also requires an Add or Welcome to be rejected when the KeyPackage lacks it. A client that follows §5.2.1 literally publishes KeyPackages without 0xF0A0. Those KeyPackages can never be added to a DM group or self-group by an RFC-conformant stack.
- Suggested fix: "Every Agora client lists 0xF0A0 and 0xF0A1 in its leaf `capabilities.extensions`." Add 0xF0A0 to the KeyPackage Validation list in §5.2.1.1.
- Needs decision: no

### IMP2-8: No procedure to move a DM group's admission host
- Severity: P2
- Location: spec/04-access-control.md:150, :158; spec/02-identity.md §2.5.6
- Evidence: "The DM initiator's identity host ... plays the CO's part for the DM group's admission." / "The initiator's client MUST put that URL in the DM group's GroupContext as the `agora_admission_host` extension".
- Problem: The host stays fixed for the group's life. When the initiator leaves the DM, deletes the account (§2.8), or is offboarded by the employer whose provisioning service is the host (§2.5.6), nothing says whether the host must keep serving and paying relays for a group that may contain none of its users. Nothing says whether remaining members may move the group with a GroupContextExtensions proposal. Implementers will differ: some hosts stop (the group can no longer publish after the next rotation), and some clients rewrite the extension (which other clients may treat as a policy violation).
- Suggested fix: Define the move: any member commits a GroupContextExtensions proposal that sets `agora_admission_host` to its own identity host, after first PUTting the member list there. Members fetch the key from the new host from the next epoch on. The old host MAY stop serving 30 days after its last hosted member leaves the list.
- Needs decision: yes. (a) Member-initiated GCE move (recommended). (b) The host serves for the group's life (unbounded cost to the initiator's CO). (c) The group ends, and the remaining members create a new one.

### IMP2-9: `did:key` leaves fail the IdentityChanged rule and compliance third-party verification
- Severity: P2
- Location: spec/02-identity.md:541; spec/07-compliance.md:142; spec/05-messaging.md:73
- Evidence: §2.7: "a client re-resolves the sender's DID ... including Removing leaves whose signature keys are no longer `authentication` keys of the DID". §7.4 step 6: "check that its `signature_key` was a device key of `senderDID` in the DID document version in effect at `ts`". §5.2.1: for `did:key` the `signature_key` "MUST NOT be the identity key".
- Problem: A `did:key` leaf key is never an `authentication` key. It is bound by `agora_device_binding`. A literal implementer of §2.7 removes all of a `did:key` user's leaves on the first `IdentityChanged`, which §2.7 says is sent after a profile change. Every `ComplianceRecord` from a `did:key` sender fails step 6, so it is unverifiable by a third party.
- Suggested fix: In §2.7, exempt `did:key` leaves whose device binding verifies. In §7.4 step 6, add: "for `did:key`, check instead that the LeafNode carries a valid `agora_device_binding` (§5.2.1)". The same carve-out applies to the §2.2 revocation sentence and §2.8.
- Needs decision: no

### IMP2-10: Shared-channel guests cannot get the home state they need, and the home endpoint cannot authenticate to the guest endpoint
- Severity: P2
- Location: spec/08-cross-space.md:67, :98; spec/03-spaces.md:311, :343; spec/04-access-control.md:88
- Evidence: §3.5: the home endpoint's check for a guest "grants access to that channel's records only". §4.3: a client "MUST reject a Welcome whose group ID ... differs from the `mlsGroupID` that current Space state declares for that channel ... If no Space endpoint is reachable ... discards the Welcome ... after 7 days". §8.4: "Clients accept such a Welcome only from a committer authorized to add members under the home space state and the agreement". §3.4: clients "MUST reject a record whose `channelID` is not a channel of the Space". §8.6: "the home Space endpoint fetches the guest Space's state from the guest Space endpoint, which MUST serve it to the home Space's CO, authenticated per §3.5 as `homeAdminDID`".
- Problem: A guest's own Space state holds only a `SharedChannelAlias` with no `mlsGroupID` and no home admin list. To validate the Welcome, the committer, and the signature and `channelID` of the `ChannelAdmissionKey`, the guest needs the home `SpaceState`. Whether that counts as "that channel's records" is undefined, so guests either discard shared-channel Welcomes or skip the checks. In the other direction, the §3.5 check requires `did` to be a member or invitee of the guest Space; `homeAdminDID` is neither. It would also put a person's device key on the home endpoint server.
- Suggested fix: State that the home endpoint serves eligible guests the home Space's members-omitted view (§4.4 form) plus the shared channel's entry, and that guest clients validate against it. Add `mlsGroupID` to `SharedChannelAlias`. For guest-state fetch, add a §3.5 clause: a Space endpoint accepts `MemberAuth` from the counterparty admin DID of an in-force `ChannelShareAgreement`. Alternatively, use a home-CO service DID named in the agreement.
- Needs decision: yes. (a) Members-omitted home view for guests plus an agreement-counterparty clause in §3.5 (recommended). (b) The guest admin re-signs the needed home fields into guest state (duplicated authority).

### IMP2-11: A new device has no source for the user's Spaces and endpoints, so it cannot accept own-device Adds to Space groups
- Severity: P2
- Location: spec/02-identity.md:496-509; spec/04-access-control.md:88
- Evidence: Self-group contents are single-author data, `SocialRecoveryConfig`, history transfers and `IdentityChanged`. §4.3: "If no channel in the client's copy of Space state declares that group ID, the client MUST fetch the current Space state (§3.4) before deciding. ... discards the Welcome if it still cannot decide after 7 days."
- Problem: A freshly enrolled device holds no Space state and no `spaceEndpoint` URLs. The original device obtained them from a `SpaceInvite`. Each own-device Welcome to a channel group names only a group ID, so the new device cannot fetch state, must discard the Welcome after 7 days, and cannot authenticate to any endpoint for admission keys. Implementers will invent different side channels.
- Suggested fix: Add to the self-group a `urn:agora:type:SpaceMembership` record (single-author, synced among the user's devices) listing each Space's genesis CID and `spaceEndpoint` URLs. The existing device sends it before committing the own-device Adds of §2.6 step 3.
- Needs decision: no

### IMP2-12: Non-member subscribers of a public broadcast channel cannot perform the required poster check
- Severity: P2
- Location: spec/05-messaging.md:200; spec/03-spaces.md:180, :311, :317
- Evidence: "Recipients ... MUST verify that `senderDID` holds a space role listed in `broadcasterRoles`." / "The access-controlled view served to non-members (§3.4) omits `members`." / For `keyAccess: public` "the endpoint serves them without authentication".
- Problem: A non-member reading a public broadcast channel gets only the public view, which has no `members`. It cannot evaluate the MUST, so it either drops every post or displays posts unchecked.
- Suggested fix: For a broadcast channel with `keyAccess: public`, the public view includes a `broadcasters` list (DIDs holding a role in `broadcasterRoles`). Alternatively, `BroadcastKey` carries the authorized poster DIDs for that `keyEpoch`, signed with it.
- Needs decision: yes. (a) A `broadcasters` list in the public view (recommended: one field, CO-signed). (b) Poster list in `BroadcastKey`. (c) Waive the check for non-members and display an "unverified poster" mark.

### IMP2-13: History reads and blob uploads exist only on the optional JMAP sync API
- Severity: P2
- Location: spec/10-relays.md:138, :580, :624, :636; spec/11-transport.md:173, :389; spec/05-messaging.md:416
- Evidence: §10.4.6: "It serves them to clients through the live protocol and the JMAP sync API". §11.4: "A subscription delivers only envelopes accepted after it; earlier envelopes come from the JMAP sync API (§11.8)." §10.4.4 upload admission refers to the JMAP upload (`POST {base}/upload/{accountId}`, §11.8.2). `jmap-sync-v1` is only a manifest capability, and §10.4.3 does not list it as a MUST.
- Problem: A conformant Relay without `jmap-sync-v1` can neither serve history (the live protocol has no history request, contrary to §10.4.6) nor accept a blob upload, so attachments and catch-up break against it. The JMAP upload response's `blobId` is server-assigned under RFC 8620, but Agora requires it to be the ciphertext CID. The text does not say the Relay returns the CID.
- Suggested fix: Make `jmap-sync-v1` mandatory for a conformant Relay (add it to §10.4.3), and fix §10.4.6 to say history is served through JMAP only. Alternatively, add a history request and an upload path outside JMAP. Either way, state that the upload response `blobId` is the CID text form of the uploaded bytes.
- Needs decision: yes. (a) JMAP sync mandatory (recommended: no new surface). (b) Add live-protocol history and an HTTP blob PUT.

### IMP2-14: Live-protocol Subscribe and Publish outcomes are underspecified
- Severity: P2
- Location: spec/11-transport.md:173, :181, :188; spec/10-relays.md:850
- Evidence: "A Relay delivers nothing for a token that has no registered admission key." / "It answers a later `Subscribe` ... naming that token with `token-withdrawn` ... and with `unknown-token` after that." / Publish step 5 answers "`expired`, `rate-limited` or `quota-exceeded` as they apply". §10.5.4 lists no expiry check.
- Problem: (1) A `Subscribe` naming an unregistered token is Acked in one reading (deliver nothing) and gets `unknown-token` in another. With several tokens, one `Ack` or `Error` per request plus a single `token` field cannot report a partial result. Clients that rely on `unknown-token` to fail over (§10.3.5) will differ from Relays that Ack. (2) Nothing defines when a Publish is `expired`: there is no `ts` skew window and no rule for an `expiryHint` in the past, so captured envelopes can be replayed after their retention lapses. (3) The answer to a duplicate Publish (same `id` already held) is undefined.
- Suggested fix: Subscribe: the Relay Acks the registered tokens and sends one `Error` without `id` (`unknown-token`, `token`) per unregistered token. Alternatively, reject the whole request and list the tokens. Define `expired`: `ts` more than 300 s ahead of, or more than the retention period behind, the Relay's clock, or `expiryHint` already passed. A duplicate Publish is answered with `Ack` carrying the existing `cid`.
- Needs decision: no

### IMP2-15: A message request accepted after relay retention cannot catch up with the group
- Severity: P2
- Location: spec/04-access-control.md:211, :215; spec/05-messaging.md:420
- Evidence: "MUST NOT authenticate to the group's admission host or fetch the group's messages until the user accepts" / "A client can open a relay-held envelope only while it still holds the keys of that envelope's MLS epoch".
- Problem: While a request is pending, the client processes no Commits. If the user accepts after the relays have dropped the Commits since the Welcome epoch (`retentionDays`, possibly 7), the client can never reach the current epoch. Nothing says whether it must leave, request a re-add, or show the group as broken. Implementers will leave stuck groups in different states.
- Suggested fix: State that a client whose request is older than the shortest relay retention it can learn, or that finds a gap in Commits it cannot fill, deletes the group state and tells the user that the sender must re-add them. Alternatively, let the client fetch handshake envelopes only (not application messages) during the request state, which reveals no more to the admission host than accept does.
- Needs decision: yes. (a) Fetch and process handshake messages during the request state without authenticating as accepted (this does reveal processing to the host). (b) Expire stale requests and require a re-add (recommended: keeps request-state privacy).

### IMP2-16: The Client conformance class omits §2.6 and §2.7
- Severity: P3
- Location: spec/01-overview.md (§1.4 table, Client row)
- Evidence: Client "MUST implement §2.1, §2.2 (DID resolution, device keys); §3.3 to §3.5 ...". The row has no §2.6 or §2.7.
- Problem: The own-device Add acceptance rule ("Members MUST accept an own-device Add", 02:509), the self-group and the `IdentityChanged` handling are outside the Client class. An implementer who scopes by §1.4 rejects own-device Adds, which then count as policy-violating Commits under §4.5.
- Suggested fix: Add §2.6 and §2.7 to the Client row, and add the `leaf` fetch parameter (already in §5.2.1.1) to the KeyPackage host row's description.
- Needs decision: no

### IMP2-17: Form of `ChannelAdmissionKey.relays` entries and the DM key response encoding are undefined
- Severity: P3
- Location: spec/03-spaces.md:291-295, :311-313; spec/04-access-control.md:150
- Evidence: `"relays": ["https://relay.example.net", ...]`, "`relays` lists the relay endpoints"; DM record "has no `sig`"; §3.4 Responses: "Every other response is the record's encoded typed payload envelope with `sig` present".
- Problem: Entries could be manifest origins (fetch `/.well-known/agora-relay`, then pick WT or WS) or client endpoint URLs like `relayHints` (`wss://...`). For the DM host, it is not stated whether the response is the same CBOR envelope without `sig`, or JSON.
- Suggested fix: "Each entry is the origin of a Relay; the client reads its endpoints from the manifest (§10.2.1)." "An identity host answers with the encoded typed payload envelope, `application/cbor`, `sig` absent, and the status codes of §3.4."
- Needs decision: no

### IMP2-18: Broadcast `seq` is counted per `kid`, which every device of a `did:key` poster shares
- Severity: P3
- Location: spec/05-messaging.md:200
- Evidence: "`seq` is the poster's per-channel sequence number (§5.1.1), counted per signing device key (the `kid` of `sig`)".
- Problem: All devices of a `did:key` poster sign with the identity key (§2.1), so two devices produce colliding `seq` values. Gap detection then reports false gaps or hides real ones.
- Suggested fix: Add a `device` member (the device's leaf signature key, or a random per-device ID) to the `BroadcastMessage` body and count `seq` per (`kid`, `device`).
- Needs decision: no

### IMP2-19: §12.9 cites a field that no longer exists
- Severity: P3
- Location: spec/12-security.md:179; spec/10-relays.md:190
- Evidence: "fields that a section defines as integer Unix seconds, such as `x-agora-timestamp` (§10.2.3)". §10.2.3 now uses the RFC 9421 `created` parameter.
- Problem: The reference is dangling. Implementers will look for a header that was removed.
- Suggested fix: Replace it with "the RFC 9421 `created` parameter (§10.2.3), `expires` in `PinInstruction`, upload and sequencer authorizations (§11.4, §14.4.3)".
- Needs decision: no

### IMP2-20: Pinning cannot work in DM groups
- Severity: P3
- Location: spec/05-messaging.md:445, :465; spec/14-jmap.md:62, :153
- Evidence: "in a group chat, admins" may pin / "`Chat.pinnedMessageIds` is written under the `sequenced-v1` consistency model ... A client MUST submit a pin update per §14.4.3" / "If `sequencer` is absent, `sequenced-v1` types in the Space are read-only". A DM group belongs to no Space and has no sequencer.
- Problem: DM pinning is impossible. Some implementers will fall back to `single-author` and others will disable it.
- Suggested fix: State that pins are unavailable in DM groups, or that DM groups use `single-author` with last-writer-wins for `pinnedMessageIds`.
- Needs decision: no

## Areas checked with nothing to report

Client hello, PoW challenge and proof (§11.6). Admission-key registration request processing, replay, supersession and the billing-key compromise path (§10.5.1, §10.5.3, §12.12). Relay recovery from backup and retirement (§10.4.7). Sequencer operation-stream submission, validation and closing (§14.4.3-§14.4.4). SFU join and re-join on rotation (§6.6). Content-key blob layout and attachment fields (§5.2.2, §14.3.4). Device-binding wire format (§5.2.1). Space creation order, archival and deletion (§3.6). Leave flows (§4.8), except the DM list-update issue in IMP2-6. Compliance record steps 1-5 (§7.4).

Coverage: read in full ARCHITECTURE.md; spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 07-compliance.md, 08-cross-space.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; spec/06-calls.md §6.6-§6.12 intro (SFU, E2EE media, TURN); spec/09-interop.md admission references only (grep). Mechanically validated every CDDL and JSON block in spec/. Cross-checked against notes/review/reconciliation.md and `bd memories agora`. Not reviewed: profiles/, guides/, PROPOSAL.md, PRFAQ.md, README.md (outside this lens).
