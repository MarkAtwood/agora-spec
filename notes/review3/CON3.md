# Review 3: CON3 (cross-file consistency)

Scope: `git diff 9e7711f HEAD -- spec ARCHITECTURE.md profiles guides`, checked against every other part that names the same object or flow.

Checked with no finding: stale `keyEpoch` in registrations, SFU `join` and `seq-auth` (none left); `content-blob/v1` and `contentKeyBlob` (none left); "Relays do not exchange blobs" and "upload to every Relay" wording (none left in spec, guides or profiles); community admission key served to all role holders (spec §3.2 table, §3.4, §5.2.1.2, §5.2.2 agree); `DMMembers` field rename `groupID` to `mlsGroupID` (body and DM `ChannelAdmissionKey` agree, path parameter defined); DM removal rules (§4.6, §4.8, §6.12.7, §7.8.2, §7.8.3, §7.8.7, App. C agree); envelope `id` over `signed` bytes (§5.2.2, §10.4.6, §10.5.2, §11.4, §11.8, §13.1, §7.4 `outerEnvelopeCID` agree); threshold signers (§4.1, §13.1.1 agree); `broadcasters` (§3.3, §3.4, §4.4, §5.2.1.4, App. D agree); App. C and App. D rows for new limits and identifiers resolve to the right sections; ARCHITECTURE §5 item 9 and §9 cover the costs the spec cites.

### CON3-1: Agreement CID is "body bytes" in §10.5.1/§10.5.3 but "encoded envelope" in §13.1 and the relay guide
- Severity: P2
- Location: spec/13-encoding.md:31; spec/10-relays.md:698, :741, :846; guides/relay-operator.md:423, :889
- Evidence: §13.1: "An object verified outside an MLS group (for example ... `ServiceAgreement` ...) ... Where such an object is content-addressed, its CID is computed over the encoded envelope bytes as stored." §10.5.1: "An agreement is identified by the CID (§13.1) of its body bytes, the exact bytes both parties signed (§13.1.1), not of the encoded envelope." Guide :423: "An agreement is identified by the CID of its encoded envelope." Guide :889: "`id`, the CID of the encoded agreement envelope (spec §10.5.1)".
- Problem: §13.1 is the general rule and names `ServiceAgreement` explicitly, so it contradicts §10.5.1. A relay built from the guide computes `id` over the envelope. A CO following §10.5.3 puts the body CID in `agreement`, so the relay finds no matching agreement and rejects every registration (`agreement-invalid`). `supersedes` breaks the same way.
- Suggested fix: In §13.1, add the exception: "except a `ServiceAgreement`, which is identified by the CID of its body bytes (§10.5.1)." Change guide :423 and :889 to "the CID of its body bytes (the bytes both parties signed), spec §10.5.1".
- Needs decision: no

### CON3-2: Commit-stream chaining across a rotation cannot work across a sequencer replacement
- Severity: P2
- Location: spec/14-jmap.md:170, :257; spec/05-messaging.md:27; spec/10-relays.md:846
- Evidence: §14.4.2: "The stamp at position 0 of the new token's commit stream carries in `prev` the hash of the last stamp of the closed commit stream, or `null` if that stream has no stamps ... A member MUST treat a stamp on a closed commit stream at a position after the one that position 0 of the new stream references as a fork." §5.1.1: "Before its first submission on a new commit stream, the committer fetches the replaced commit stream to its end from the log". §14.4.5 Replacement: "The CO replaces a faulty sequencer by a Space state change, then rotates the admission keys ... so that the replacement starts new streams at position 0." §10.5.3: "An IO ignores a `replaces` that names a token not registered under the agreement."
- Problem: The replacement sequencer never held the old token, so it ignores `replaces`, cannot know the old stream's last stamp, and writes `prev = null`. Members cannot tell "no stamps" from "unknown", so the fork rule has no reference position. The old commit stream is never closed, because the CO no longer registers with the faulty sequencer. Committers must also fetch the old stream from the old sequencer, which may be unreachable, and §5.1.1 then makes them wait without limit. The replacement flow, which exists for a faulty sequencer, stalls Commits.
- Suggested fix: Add to §14.4.2/§14.4.5: when the commit stream's new token is stamped by a different sequencer DID (a replacement), position 0 carries `prev = null`; members close the old commit stream at the Space state change that replaces the sequencer and do not apply the fork rule across it; committers do not fetch the old stream from the replaced sequencer.
- Needs decision: no

### CON3-3: §3.5 identity-host membership check blocks the creation `DMMembers` (new group and §4.6.4 handover)
- Severity: P2
- Location: spec/03-spaces.md:345; spec/04-access-control.md:171, :175, :195; spec/04-access-control.md §4.6.4 step 1
- Evidence: §3.5: the service "MUST check that `did` is a current member ... (for an identity host, a member of the DM group under §4.6 ...)". §4.6 Responses: the host answers "`401` to a request without authentication". Creation: "The first list the host accepts for an `mlsGroupID`, signed by a DID the host serves: the initiator ..., or the member taking the group over (§4.6.4)". The `MemberAuth` body has no group field.
- Problem: For a creation, the host holds no list for the group, so no caller can pass the §3.5 check, and without a bearer token the PUT gets 401. The initiator and the §4.6.4 takeover can never register the group. Because `MemberAuth` names no group, "a member of the DM group" is also undefined for a host that serves many groups. Implementers will either deadlock or skip the check.
- Suggested fix: In §3.5, have the identity host issue the token to any DID it serves or any DID on a member list it holds. Authorize per request: a GET or a non-creation PUT needs the DID on that group's list, and a creation PUT needs a DID the host serves.
- Needs decision: no

### CON3-4: `broadcasters` list conflicts with the Mirroring rule for records naming non-admin members
- Severity: P3
- Location: spec/03-spaces.md:313, :323; spec/10-relays.md:662
- Evidence: §3.4: the non-member view "carries a `broadcasters` list ... `dids`, the DIDs that hold a role in its `broadcasterRoles`", and the CO "MAY mirror them like other public Space state". Mirroring: "Records that name members other than the owner and admins ... MUST NOT be stored on IO infrastructure in the clear." §10.4.4 allows public Space records on public IPFS.
- Problem: A broadcaster role holder need not be an admin (§5.2.1.4: "held by admins or a bot"), so the public view of a Space with a public broadcast channel names non-admin members. Mirroring then forbids putting that view on IO infrastructure, while §3.4 and §10.4.4 allow it. Implementers will disagree on whether the view may be mirrored or relay-stored.
- Suggested fix: Either (a) add `broadcasters` DIDs to the Mirroring exception ("other than the owner, admins and DIDs in a `broadcasters` list"), or (b) require every DID in `broadcasters` to be an admin.
- Needs decision: yes. (a) keeps bots as posters and makes the disclosure explicit, (b) narrows who can post. Recommend (a), and also list it in ARCHITECTURE §9 under public broadcast channels.

### CON3-5: §8.6 says the non-member view carries the shared channel, but §4.4 lets the CO hide it
- Severity: P3
- Location: spec/08-cross-space.md:97; spec/04-access-control.md:92
- Evidence: §8.6: the home endpoint "serves eligible guest members the home Space's non-member view (§4.4), which carries the shared channel's entry and the admins without `members`; guest clients validate a shared-channel Welcome's adder ... against that view." §4.4: "The channel's existence MAY be hidden from non-members: the channel path is omitted from the view ... served to non-members".
- Problem: If the shared channel is private and hidden, guest clients cannot validate the Welcome or the `ChannelAdmissionKey` (§3.4: "MUST reject a record whose `channelID` is not a channel of the Space"), so guests cannot join.
- Suggested fix: In §8.6, state that the view served to eligible guests MUST include the shared channel's entry and the admin entries whose scope covers it, even when the general non-member view hides it.
- Needs decision: no

### CON3-6: Attachment capture gap variant of `ComplianceGapEntry` is not reflected where the entry is defined
- Severity: P3
- Location: spec/07-compliance.md:135, :315-330
- Evidence: §7.4: a capture gap is "a `ComplianceGapEntry` (§7.8.9) that carries `recordCID` ... and `missingBlobId` ... in place of `removedAtEpoch` and `readmittedAtEpoch`." §7.8.9 defines the entry with only `mlsGroupID`/`channelID`, `loggerDID`, `removedAtEpoch`, `readmittedAtEpoch`, `detectedAt`, and says nothing about the variant.
- Problem: A verifier or bridge built from §7.8.9 (profiles/purview-bridge.md parses it) will reject or misread the attachment form.
- Suggested fix: Add the variant and its two members to §7.8.9 next to the schema, with a back-reference to §7.4.
- Needs decision: no

### CON3-7: Relay guide still allows disabling JMAP, which is now mandatory
- Severity: P3
- Location: guides/relay-operator.md:551-553; spec/10-relays.md:591
- Evidence: Spec §10.4.3: "Implement the JMAP sync API (`jmap-sync-v1`, §11.8), which is the only path for envelope history and blob upload." Guide: "# Whether to expose the JMAP sync API and declare jmap-sync-v1. # default: true / enabled = true".
- Problem: An operator who sets `enabled = false` runs a non-conformant relay that cannot accept blob uploads, which breaks upload-once for channels that list it. The spec also still reads as optional in places ("A Relay that declares `jmap-sync-v1` ...", §10.4.4, §11.8.1).
- Suggested fix: Remove the toggle from the guide, or document that `false` is non-conformant. In §10.4.4 and §11.8.1, say "A Relay serves ... (it always declares `jmap-sync-v1`)".
- Needs decision: no

### CON3-8: Matrix gateway fetches attachments "from IPFS", contrary to the new public-IPFS ban
- Severity: P3
- Location: spec/09-interop.md:134; spec/10-relays.md:662
- Evidence: §9: "media fetched from IPFS and re-uploaded to the Matrix media server". §10.4.4: "Relays, clients and the CO MUST NOT ... request from the public IPFS network ... any blob other than public content".
- Problem: A gateway implementer following §9 requests private ciphertext CIDs from public IPFS, which §10.4.4 forbids. It also omits decryption of the chunked blob.
- Suggested fix: "media fetched from the channel's relays or archive (§10.4.4), decrypted with the attachment's `contentKey` (§14.3.4), and re-uploaded".
- Needs decision: no

### CON3-9: Abuse report and Purview profile still describe the envelope id as "CID of the routing envelope"
- Severity: P3
- Location: spec/04-access-control.md:297; profiles/purview-bridge.md:210
- Evidence: §4.7: "Each item gives the CID of the routing envelope (§5.2.2)". Purview: "CID of the routing envelope that carried the message (spec §5.2.2)". §5.2.2 now: "The envelope `id` is the CIDv1 of the content of the `signed` byte string".
- Problem: An implementer reading "CID of the routing envelope" literally computes it over the whole envelope, which matches no relay-held `id`, so the CO cannot locate the reported envelope for takedown (§10.4.5).
- Suggested fix: Replace both with "the envelope `id` (§5.2.2)".
- Needs decision: no

### CON3-10: Handover back to a host that already holds a stale list for the group fails
- Severity: P3
- Location: spec/04-access-control.md:195, §4.6.4 step 1
- Evidence: Creation: "The first list the host accepts for an `mlsGroupID`". Addition and removal must be "signed by a DID on the current list". §4.6.4: the old host keeps serving for up to 30 days.
- Problem: If A's host hosted the group, A left (removing its own DID there), A was re-added, and the current host's user then leaves, A's client must send a creation to A's host. That host still holds a list for the `mlsGroupID`, so the request is not a creation, and A is not on that list, so it cannot be an addition. The handover is refused.
- Suggested fix: Allow a creation that replaces any list held for the group, provided its `seq` and `ts` are greater and the signer is a DID the host serves.
- Needs decision: no
