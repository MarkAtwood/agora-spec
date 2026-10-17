# Review 3: CON3 verified

Checked against HEAD 46add2b.

### CON3-1: Agreement CID is "body bytes" in §10.5.1/§10.5.3 but "encoded envelope" in §13.1 and the relay guide
- Verdict: PARTIAL. guides/relay-operator.md:889 is already fixed in 46add2b ("the CID of the agreement body bytes both parties signed (spec §10.5.1)"). Still wrong: spec/13-encoding.md:31 lists `ServiceAgreement` among stored objects and says "Where such an object is content-addressed, its CID is computed over the encoded envelope bytes as stored", and guides/relay-operator.md:423 (config comment) says "An agreement is identified by the CID of its encoded envelope." spec/10-relays.md:698, :741, :846 agree with each other on body bytes. `ChannelShareAgreement` (spec/08-cross-space.md:56, envelope CID) is consistent with §13.1 and needs no change.
- Severity: P2 kept. A relay built from the guide's config comment rejects every registration whose `agreement` is the body CID.
- Fix:
  - spec/13-encoding.md §13.1 "Stored and published objects", last sentence: replace with "Where such an object is content-addressed, its CID is computed over the encoded envelope bytes as stored, except a `ServiceAgreement`, which is identified by the CID of its body bytes (§10.5.1)."
  - guides/relay-operator.md:422-423: replace "An agreement is identified by the CID of its encoded envelope." with "An agreement is identified by the CID of its body bytes, the bytes both parties signed (spec §10.5.1)."
- Needs decision: no

### CON3-2: Commit-stream chaining across a rotation cannot work across a sequencer replacement
- Verdict: CONFIRMED. spec/14-jmap.md:170 closes the old commit stream only "When the sequencer applies an `AdmissionKeyRegistration` whose entry names a token in `replaces`", and position 0 of the new stream carries the old stream's last stamp hash "or `null` if that stream has no stamps". spec/10-relays.md:846: "An IO ignores a `replaces` that names a token not registered under the agreement." The replacement sequencer (§14.4.5 "Replacement") never held the old token, so it cannot close the old stream or know its last stamp, and `null` is ambiguous. §14.4.4 "Closing a stream" and §5.1.1 require fetching "the closed commit stream to its end" from the log before submitting, which may be served only by the faulty sequencer; §5.1.1 "If the sequencer is unreachable, the committer waits." Operation streams already handle a signer change (§14.4.4 step 1 accepts position 0 signed by the sequencer in the current "or in an earlier Space state"), commit streams do not. One refinement to the reviewer's fix: the old stream's Commits are still obtainable without the old sequencer, because each counted Commit carries its stamp in `commitStamp` in the routing envelope held by the channel's relays (§5.1.1).
- Severity: P2 kept. The flow that exists to recover from a faulty sequencer stalls all Commits.
- Fix: append to spec/14-jmap.md §14.4.5 "Replacement": "When the Space state change names a new `sequencer` DID, every commit stream stamped by the old DID is closed at that state change: members accept no further stamp signed by the old DID (§5.1.1), position 0 of each new commit stream carries `prev` `null`, and the fork rule of §14.4.2 does not apply across the change. Before its first submission on the new commit stream, a committer processes the old stream's Commits from the channel's relay history, where each carries its stamp in `commitStamp` (§5.1.1), and does not fetch the old stream from the replaced sequencer." In §14.4.4 "Closing a stream", last sentence, add "(or, after a sequencer replacement, its Commits from relay history, §14.4.5)" after "fetch the closed commit stream to its end".
- Needs decision: no

### CON3-3: §3.5 identity-host membership check blocks the creation `DMMembers`
- Verdict: CONFIRMED. spec/03-spaces.md:345 requires "`did` is a current member ... (for an identity host, a member of the DM group under §4.6 ...)". spec/04-access-control.md §4.6: "The host authenticates members by the §3.5 exchange" and answers "`401` to a request without authentication". A creation is "The first list the host accepts for an `mlsGroupID`", so no list exists and no caller can pass §3.5. `MemberAuth` (spec/03-spaces.md:333-339) carries no group, so "a member of the DM group" is undefined at a host serving many groups.
- Severity: P2 kept. Blocks DM creation and every §4.6.4 handover as written.
- Fix (constraint form, simpler than the reviewer's token rework): a `DMMembers` PUT is already a signed, fresh (`ts` within 300 s), monotone (`seq` greater) envelope, so its signature is its authorization.
  - spec/04-access-control.md §4.6, "Admission key and relays", replace "The host authenticates members by the §3.5 exchange and serves the key only to DIDs on the group's member list" with "A GET is authenticated by the §3.5 exchange, and the host serves the key only to a DID on that group's member list. A PUT is authorized by the signature of its `DMMembers` and needs no bearer token."
  - §4.6 "Responses": change "`401` to a request without authentication" to "`401` to a GET without authentication".
  - spec/03-spaces.md:345 parenthetical: replace "for an identity host, a member of the DM group under §4.6" with "for an identity host, a DID it serves or a DID on a member list it holds; the host checks on each GET that the DID is on that group's list (§4.6)".
- Needs decision: no

### CON3-4: `broadcasters` list conflicts with the Mirroring rule
- Verdict: CONFIRMED. spec/03-spaces.md:323: "Records that name members other than the owner and admins ... MUST NOT be stored on IO infrastructure in the clear." The public view carries `broadcasters` `dids` (spec/03-spaces.md:313, spec/05-messaging.md:211), and spec/05-messaging.md:181 says posters are "Typically ... admins or a bot", so non-admin DIDs appear. §3.4 says "the CO MAY mirror them like other public Space state" and §10.4.4 allows public records on public IPFS. ARCHITECTURE.md §9 (:438-446) covers token mapping for public broadcast channels but not the disclosure of poster DIDs.
- Severity: P3 kept.
- Fix (if (a)): spec/03-spaces.md:323, change "Records that name members other than the owner and admins" to "Records that name members other than the owner, admins and the DIDs in a public view's `broadcasters` list". Add to ARCHITECTURE.md §9 "Public broadcast channels are mapped to their Space" bullet: "The Space's public view also names every DID that may post to such a channel."
- Needs decision: yes. Options: (a) exempt `broadcasters` DIDs from the Mirroring rule and record the disclosure in ARCHITECTURE §9; (b) require every DID in a public channel's `broadcasterRoles` to be an admin; (c) keep the rule and forbid mirroring a view that carries `broadcasters`. Recommend (a): a public broadcast channel must already show subscribers who may post, so the names are public by design and (b) or (c) only push bots into admin roles or stop mirroring. Plain-language: a public announcement channel has to tell outsiders who is allowed to post, so those names are public anyway. The question is whether to admit that openly in the rules or to restrict who can post.

### CON3-5: §8.6 says the guest view carries the shared channel, but §4.4 lets the CO hide it
- Verdict: CONFIRMED. spec/08-cross-space.md:97 says the view served to guests "carries the shared channel's entry and the admins". spec/04-access-control.md:92 lets the channel path be "omitted from the view of Space state that the CO's Space endpoint (§3.4) serves to non-members" and its last sentence says the home endpoint serves "this view" to guests. spec/03-spaces.md:313: clients "MUST reject a record whose `channelID` is not a channel of the Space", so a guest given the hiding view rejects the shared channel's `ChannelAdmissionKey`.
- Severity: P3 kept.
- Fix: spec/08-cross-space.md §8.6 "Admission key", after "which carries the shared channel's entry and the admins without `members`" add ": that view MUST include the shared channel's entry and every admin entry whose scope covers it, even when the view served to other non-members hides the channel (§4.4)". In spec/04-access-control.md:92 last sentence, change "serves this view to eligible guest members" to "serves eligible guest members this view with the shared channel's entry included (§8.6)".
- Needs decision: no

### CON3-6: Attachment capture-gap variant of `ComplianceGapEntry` missing from §7.8.9
- Verdict: CONFIRMED. spec/07-compliance.md:135 defines the variant with `recordCID` and `missingBlobId` "in place of `removedAtEpoch` and `readmittedAtEpoch`"; §7.8.9 (:318-330) shows only the epoch form and its prose covers only the `channelID` substitution. profiles/purview-bridge.md:302 consumes the variant.
- Severity: P3 kept.
- Fix: spec/07-compliance.md §7.8.9, after "`readmittedAtEpoch` is `null` while the logger has not been re-admitted." add: "An attachment capture gap (§7.4) carries `recordCID`, the CID of the Message's `ComplianceRecord`, and `missingBlobId`, the attachment's `blobId`, in place of `removedAtEpoch` and `readmittedAtEpoch`."
- Needs decision: no

### CON3-7: Relay guide still allows disabling JMAP
- Verdict: CONFIRMED. guides/relay-operator.md:551-553 "Whether to expose the JMAP sync API and declare jmap-sync-v1. default: true / enabled = true". spec/10-relays.md:591 makes it mandatory ("the only path for envelope history and blob upload"). Conditional wording remains at spec/10-relays.md:639 ("A Relay that declares `jmap-sync-v1` also serves") and spec/11-transport.md:380 ("A Relay that declares the `jmap-sync-v1` capability MUST expose").
- Severity: P3 kept.
- Fix: delete the `enabled` comment and line from the guide's `[jmap]` block. spec/10-relays.md:639: "A Relay that declares `jmap-sync-v1` also serves" to "A Relay also serves". spec/11-transport.md:380: "A Relay that declares the `jmap-sync-v1` capability MUST expose" to "Every Relay declares the `jmap-sync-v1` capability (§10.4.3) and MUST expose".
- Needs decision: no

### CON3-8: Matrix gateway fetches attachments "from IPFS"
- Verdict: CONFIRMED. spec/09-interop.md:134 "media fetched from IPFS and re-uploaded". spec/10-relays.md:662 forbids requesting non-public blobs from the public IPFS network. The gateway is a full group member (spec/09-interop.md:130), so it holds `contentKey`.
- Severity: P3 kept.
- Fix: spec/09-interop.md:134, replace "media fetched from IPFS and re-uploaded to the Matrix media server" with "media fetched from the channel's relays (§10.4.4), decrypted with the attachment's `contentKey` and checked against its `sha256` (§14.3.4), and re-uploaded to the Matrix media server".
- Needs decision: no

### CON3-9: "CID of the routing envelope" in §4.7 and the Purview profile
- Verdict: CONFIRMED. spec/04-access-control.md:297 and profiles/purview-bridge.md:210 both still say "CID of the routing envelope". spec/10-relays.md:674 and §5.2.2 define the envelope `id` as the CID of the `signed` bytes only. No other occurrence in spec, guides, profiles or ARCHITECTURE.
- Severity: P3 kept.
- Fix: spec/04-access-control.md:297, "Each item gives the CID of the routing envelope (§5.2.2)" to "Each item gives the envelope `id` (§5.2.2)". profiles/purview-bridge.md:210, "CID of the routing envelope that carried the message (spec §5.2.2)" to "Envelope `id` of the routing envelope that carried the message (spec §5.2.2)".
- Needs decision: no

### CON3-10: Handover back to a host that already holds a stale list fails
- Verdict: CONFIRMED, but the suggested fix is unsafe. The scenario holds: "Creation. The first list the host accepts for an `mlsGroupID`", addition and removal need "a DID on the current list", and §4.6.4 lets a host keep a list after no DID it serves remains ("MAY stop serving ... 30 days after", not MUST delete). A returning host's user's client gets 403. The reviewer's fix ("a creation that replaces any list held for the group ... signer is a DID the host serves") lets any DID served by the same host overwrite a live group's list and obtain its admission key while that host is still the group's admission host.
- Severity: P3 kept.
- Fix: spec/04-access-control.md §4.6 item 1, replace "The first list the host accepts for an `mlsGroupID`, signed by a DID the host serves" with "The first list the host accepts for an `mlsGroupID`, or a list that replaces one on which no DID the host serves remains, signed by a DID the host serves". The `seq` and `ts` monotonicity already stated for every change still applies, and §4.6.4 step 1 already sets them above the old host's list.
- Needs decision: no
