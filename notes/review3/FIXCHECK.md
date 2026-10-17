# Review 3 fix check

Scope: uncommitted `git diff -- spec ARCHITECTURE.md` against the review 3 fix brief and notes/review3/*-verified.md. No em dashes were added (0 in added lines). Every verified finding has a landed fix; the findings below are defects in, or left by, those fixes.

### FC-1: Creation-replacement lets a former member hijack the live DM list during handover
Severity: P2
Location: spec/04-access-control.md:194 (DMMembers acceptance), :316 (leaving), §4.6.4 :263
Evidence:
- :194 "A **creation** is the first list the host accepts for an `mlsGroupID`, or a list that replaces one on which no DID the host serves remains, signed by a DID the host serves"
- :194 "its `seq` is greater than that of the current list"; "The host rotates the key when it accepts a list that removes a DID."
- :316 "the leaver's client sends the admission host a `DMMembers` without its own DID"
- :170 "A PUT is authorized by the signature of its `DMMembers` and needs no bearer token."
Problem: When the host's user leaves (or is removed) and no other member is served by that host, the host's list has no DID it serves, yet the host is still the group's admission host until a move Commit lands. Any DID the host serves can then send a "creation": the leaver itself, a removed host's user, or any other account on a shared employer host that knows the group ID. The list may drop every remaining member (only loggers must be kept), so the host rotates the key and refuses the members. Members get `token-rotated` and must publish a move Commit within the 300 s grace; offline groups are stranded. The creation can also carry a huge `seq`, after which no member list (seq = MLS epoch) is accepted for that many epochs. The CON3-10 verifier rejected the reviewer's fix for letting a non-member overwrite a live list "while that host is still the group's admission host"; the applied version still allows it in exactly the handover window.
Fix: Accept a replacement creation only after the host has stopped serving the group: when the host deregisters a group's key under the 30-day rule (:274) it deletes the list, so a later creation is a "first list". Delete "or a list that replaces one on which no DID the host serves remains". A move back to a host that still holds a stale list is refused and falls to the next member (same path as the refused creation in :268).
Needs decision: yes. (a) Replacement creation only after deregistration (recommended; a constraint, no new state). (b) Keep replacement but require it to keep every DID of the replaced list and cap `seq` at current+1; still leaks the key to the squatter. (c) Accept and document in §12.

### FC-2: seq = MLS epoch with strictly greater seq makes every same-epoch correction unacceptable
Severity: P2
Location: spec/04-access-control.md:194, :196; §4.6.4 :270
Evidence:
- :194 "`seq` is an unsigned integer equal to the MLS epoch in which the listed membership takes effect"; "its `seq` is greater than that of the current list"
- :196 "The committer of an Add Commit whose list the host accepted but that lost (§5.1.1) sends a list without each DID it added that has no leaf in the winning epoch"
- :196 "A client whose PUT is answered `403` or `409` fetches the current list, recomputes the list from its MLS membership, and retries." "A client retries a required list with exponential backoff until the host accepts it or the host's list shows the change was made."
- :270 "a member whose handover Commit lost sends its own host a `DMMembers` without its own DID (§4.6), whose `seq` is the winning epoch."
Problem: The host holds at most one list per epoch. A losing Add's list already holds seq N+1, so the loser's cleanup list (seq N+1, the winning epoch) and the winner's own list for epoch N+1 are both answered 409; recomputing from MLS yields the same seq, so the retry loop never succeeds until some later Commit advances the epoch. In a quiet DM that may never happen, and a DID the winner removed keeps the admission key with no rotation. The same holds for the stray-DID cleanup when the stray entered at the current epoch, and for a member that retries a move after its handover lost (its own host holds seq = winning epoch). The IMP3-5 cleanup text was written for the old delta model and does not work under the CRY3-4 (a) numbering.
Fix: Either (a) a client that must correct a list whose `seq` equals the current epoch first commits an empty Commit (no proposals) and sends the corrected list with the new epoch; or (b) the host also accepts a list with equal `seq` and a later `ts` when signed by a listed DID. State the chosen rule in "Keeping the list".
Needs decision: yes. (a) Advance the epoch with an empty Commit (recommended; host rule unchanged, deterministic). (b) Equal seq with later ts (reintroduces sender clocks and lets two branches overwrite each other).

### FC-3: Same-host shortcut sends no Commit, so the 24-hour fallback still moves the group
Severity: P2
Location: spec/04-access-control.md:263, :268; spec/99-appendices.md:98
Evidence:
- :263 "if no handover Commit has arrived 24 hours after the host's user ceased to be a member, any remaining member's client does it."
- :268 "it skips both steps and only sends the `DMGroupDescriptor` with `admissionHostDID` set to its own DID."
- :218 "The committer of each membership or logger change sends the updated descriptor to the group ... in the new epoch"
- Appendix C:98 "any remaining member after 24 h without a handover Commit"
Problem: The shortcut produces no Commit, so by the literal rule every other remaining member's client moves the group 24 hours later, defeating the shortcut (the CRY3-7 normal enterprise case). Nothing defines whether a receiver accepts a descriptor sent outside a Commit by a non-committer, and two co-hosted members can each send one with different `admissionHostDID` with no tie-break. Implementers will diverge on whether the shortcut satisfies the fallback. (CRY3-7's verified fix made the shortcut a Commit that changes the DID in the GroupContext extension; that depended on CRY3-6, which was not applied.)
Fix: :263 "if neither a handover Commit nor a `DMGroupDescriptor` naming a new `admissionHostDID` has arrived 24 hours after ...". :268 add "Members accept a descriptor whose only change is `admissionHostDID` set to its sender's DID from any member; if several arrive, the one from the lowest leaf index wins." Update Appendix C:98 to match.
Needs decision: no

### FC-4: Sequencer replacement has no boundary for old-DID stamps and no rule for forked or unpublished old Commits
Severity: P2
Location: spec/14-jmap.md §14.4.5 "Replacement"; spec/05-messaging.md:13, :15, :17
Evidence:
- §14.4.5 "every commit stream stamped by the old DID is closed at that state change: members accept no further stamp signed by the old DID (§5.1.1), position 0 of each new commit stream carries `prev` `null`, and the fork rule of §14.4.2 does not apply across the change."
- §5.1.1 :15 "signed by the `sequencer` DID in the Space state the member holds (or, on a commit stream closed by a sequencer replacement, by the DID it replaced, §14.4.5)"
- :17 "The winning Commit for epoch N is the counting Commit for epoch N at the lowest position of the commit stream, whether or not it was ever published." "A member that cannot fill a gap on a stream closed by a sequencer replacement, because relay history no longer holds the position, deletes its state for the group"
- §14.4.5 "a committer processes the old stream's Commits from the channel's relay history ... and does not fetch the old stream from the replaced sequencer."
Problem: A stamp carries no reference to Space state, so "no further stamp" has no testable boundary. Between the state change and the key rotation the old sequencer keeps stamping the current token's commit stream for committers that have not seen the change; members that saw the change earlier or later disagree on which old-DID stamps count, and pick different MLS branches. A replaced sequencer is typically one that equivocated, and with `prev` `null` and the fork rule off, nothing selects one branch of a forked old commit stream (the operation-stream `after` closing rule has no commit-stream counterpart). A stamped winner that was never published exists only in the old log, which members are told not to read, so every member hits the same gap and deletes its group state, leaving no member to re-add the others ("no longer holds" does not cover "never held"). Also unstated: whether the new sequencer may stamp the commit stream of a token registered before the change, whose stream name is the same as the old DID's stream.
Fix: The Space state change that names a new `sequencer` carries, per channel, the closing head (`stream`, `n`, stamp hash) of the old DID's current commit stream, chosen by the CO from the old log or relay history. Members accept old-DID stamps only up to that head and treat later positions as rejected; the new sequencer stamps only commit streams of tokens registered after the change. A member missing a position at or below the head may fetch it from the old log if reachable, else from relay history.
Needs decision: yes. (a) CO-chosen closing head in the replacement state change (recommended; mirrors the operation-stream `after` rule). (b) Keep the current text and document that replacement after equivocation requires re-creating each channel's MLS group.

### FC-5: Every member that fills a gap from the log republishes the Commit
Severity: P2
Location: spec/05-messaging.md:17; spec/14-jmap.md §14.4.3 last paragraph
Evidence:
- :17 "A member that holds an envelope that opens under no sealing key it holds (§5.2.2) fetches the commit stream's log from its last processed position."
- :17 "A member that applies a winning Commit it has not received in a routing envelope publishes it ... members deduplicate such copies by `opHash`"
Problem: The committer publishes its Commit only after fetching the log, then sends epoch N+1 application messages. Gossipsub delivers the Commit and the next message over independent mesh paths, so members that see the N+1 message first fetch the log, apply the Commit, and each publish their own copy. Copies have distinct envelope `id`s (different `ts` and `admissionSig`), so Relays store and fan out every one; in a channel of n members a fraction k republish and the channel carries k*n extra deliveries per Commit, plus k*n log fetches. `opHash` dedup saves decryption, not bandwidth or relay storage.
Fix: "A member that applies a winning Commit it has not received in a routing envelope waits a random delay of 10 to 60 seconds and publishes it only if no copy has arrived by then." (A local timer, not a clock comparison; winner selection still consults no clock.) Add the delay to Appendix C.
Needs decision: no

### FC-6: §3.4 still defines the broadcasters entry without keyEpoch and checks against the current view
Severity: P2
Location: spec/03-spaces.md:313
Evidence:
- :313 "a `broadcasters` list with one entry per channel whose `keyAccess` is `public`: its `channelID` and `dids`" and "a subscriber that is not a member verifies each post's signer against the list in the current view (§5.2.1.4)"
- spec/05-messaging.md:210 "an array with one `{channelID, keyEpoch, dids}` entry" and "listed for the channel in a `broadcasters` entry with the post's `keyEpoch`, or, if it holds none for that `keyEpoch`, in the newest list it holds"
- spec/03-spaces.md:233 and Appendix D:140 now say `{channelID, keyEpoch, dids}`
Problem: The CRY3-10/IMP3-8 fix was applied to §3.3, §5.2.1.4 and Appendix D but not §3.4, which still gives the old field set and the "current view" rule that makes past posts undisplayable. An implementer reading §3.4 builds the old behavior.
Fix: :313 replace "its `channelID` and `dids`, the DIDs that hold a role in its `broadcasterRoles`" with "its `channelID`, `keyEpoch` and `dids` (§5.2.1.4)", and "verifies each post's signer against the list in the current view (§5.2.1.4)" with "verifies each post's signer as §5.2.1.4 describes".
Needs decision: no

### FC-7: Subscription switch after a DM handover is still keyed on a higher keyEpoch
Severity: P3
Location: spec/05-messaging.md:266
Evidence: "When it obtains a higher `keyEpoch`, it subscribes to the new token and keeps the previous subscription until the relay reports the old token withdrawn". §4.6.4 :270 "use it and the relays it lists in place of every key of the previous host regardless of `keyEpoch`".
Problem: The IMP3-4 qualifier was added to the signing sentence only. A new host's key may have a lower `keyEpoch`, so the literal subscription rule never fires, and the "keep the previous subscription" overlap (needed for members that have not yet processed the handover Commit) is not stated for a host change.
Fix: "When it obtains a higher `keyEpoch`, or in a DM group a key from a newly named host (§4.6.4), it subscribes ...".
Needs decision: no

### FC-8: The 403 a refused member reacts to is not a defined response
Severity: P3
Location: spec/04-access-control.md:176, :263; spec/03-spaces.md:345
Evidence: :263 "A member that its admission host refuses (`403`) while it is still in the MLS group SHOULD move the group". :176 "`403` to a bad signature or a change this section does not allow". §3.5 gives no status codes for a refused exchange.
Problem: A GET from an authenticated DID that is not on the list, and a §3.5 exchange refused because the DID is neither served nor listed, have no status code, so the SHOULD's trigger differs between implementations (403, 404, 401).
Fix: :176 add "`403` to a GET from a DID not on the group's member list"; §3.5 add that a refused exchange is answered `403`.
Needs decision: no

### FC-9: Precedence of the equal-list 204 over the seq and signer checks is unstated
Severity: P3
Location: spec/04-access-control.md:194
Evidence: "The host accepts a `DMMembers` if ... its `seq` is greater than that of the current list ... and it is a creation or is signed by a DID on the current list." then "A list whose `members` and `complianceLoggers` equal those of the current list is answered `204` without change."
Problem: The leaver's list (:316) usually arrives after the committer's identical list, with equal `seq` and a signer no longer listed. Checked in order, that is 409 or 403; with the 204 rule first, it is 204. The duplicate PUTs the brief intends to be idempotent depend on which reading an implementer takes.
Fix: Move the equal-list sentence before the acceptance sentence: "A list with a valid signature and fresh `ts` whose `members` and `complianceLoggers` equal those of the current list is answered `204` without change, whatever its `seq` and signer."
Needs decision: no

### FC-10: "always sends its merged record" can be read as send-on-receipt
Severity: P3
Location: spec/02-identity.md:527
Evidence: "A receiving device merges a record into the one it holds entry by entry ... and always sends its merged record."
Problem: Read as "on every receipt, send", two devices exchange the same merged record forever. The intent is that whenever a device sends, it sends the merged record.
Fix: "When it sends a record, it sends its merged record; receiving a record does not by itself trigger a send."
Needs decision: no

### FC-11: Consequence of the authorization-after-winner rule is not recorded
Severity: P3
Location: spec/05-messaging.md:19; spec/04-access-control.md:141; ARCHITECTURE.md:299-300
Evidence: :19 "Whether a Commit is authorized under Space state (§4) does not affect which Commit wins ... if the Commit is still unauthorized, it treats it as a policy violation (§4.5)." §4.5 :141 "MUST leave the group by deleting its group state; for a Space group, an admin re-creates the group".
Problem: Under decision 2 any channel member can, with one stamped unauthorized Commit, force every member of a sequenced channel to delete the group and an admin to re-create it. Before the diff such a Commit did not count. This follows from the binding decision and is not contested here, but neither §12 nor ARCHITECTURE §9 records it as an accepted cost.
Fix: Add to §12.5 (Denial of Service), beside the new DM entries: "A channel member can submit a valid but unauthorized Commit; if it wins, every member leaves the group and an admin re-creates it (§4.5), after which the admin can remove the sender identified by its MLS signature." Add one line to ARCHITECTURE §9.
Needs decision: no
