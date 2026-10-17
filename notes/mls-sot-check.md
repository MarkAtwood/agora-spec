# MLS source-of-truth rewrite: check

Scope: uncommitted `git diff -- spec ARCHITECTURE.md` against
scratchpad `mls-sot-brief.md` and the lead's added binding decisions.

Clean: no leftover `DMMembers`, `DMGroupDescriptor`, `AddApproval`,
`consentModel`, `SpaceMembership`, `agora_admission_host`, `/members`,
`complianceLoggers`, `admissionHostDID` or `dmGroupDescriptorCID` in spec/
or ARCHITECTURE.md (the two `createdBy` hits, 03:145 and 05:631, are unrelated
Space records). The GCE use matches RFC 9420: wholesale replacement (§12.1.7,
"This is a wholesale replacement, not a merge"), one GCE per Commit (§12.2),
GCE applied before Adds (§12.3), and required_capabilities checked against
current members (§11.1). The Welcome carries the GroupContext (§12.4.3.1).
Both TLS structs are well formed, and each is defined once. The section
references I checked resolve (§2.5.6, §4.6.4, §5.1.1, §5.2.1.1, §5.2.1.3,
§7.4, §12.11).

Counts: P1 2, P2 5, P3 6.

### SC-1 Every self-group Space-list change is a policy violation

Severity: P1
Location: spec/04-access-control.md §4.6 "The `agora_admission` extension"; spec/02-identity.md §2.6 "Space membership list"
Evidence: 04: "A client MUST NOT commit an `AgoraAdmission` that keeps `host` unchanged and does not increase `key_epoch`, and members MUST treat such a Commit as a policy violation (§4.5)." and "Such a proposal replaces the whole extension list, so its committer copies every other GroupContext extension unchanged". 02: a Space-list change "commits a GroupContextExtensions proposal ... it also carries the group's other extensions unchanged."
Problem: A Space-list GCE in the self-group must carry `agora_admission` unchanged, because RFC 9420 §12.1.7 replaces the whole list. Read literally, that Commit "commits an `AgoraAdmission`" with the same `host` and `key_epoch`. Members must then treat it as a policy violation, and under §4.5 every device deletes its self-group state. The same wording also clashes with "commits one only when it creates the group, rotates ... or moves".
Fix: Scope both rules to a GCE that changes `agora_admission`: "A GroupContextExtensions proposal that changes `agora_admission` MUST either change `host` or increase `key_epoch` ...; a proposal that carries `agora_admission` byte-for-byte unchanged is not such a change."
Needs decision: no

### SC-2 Later joiners cannot identify compliance loggers or see the disclosure

Severity: P1
Location: spec/04-access-control.md §4.6, §4.6.4, §4.8; spec/07-compliance.md §7.8.3, §7.8.4; brief item 3
Evidence: 05 §5.2.1.3: "Passive members are indistinguishable from standard members at the MLS wire protocol layer; the constraint is behavioral, not cryptographic." 07 §7.8.4: the notice is "sent in the same epoch as the logger's admission commit" and MUST be visible "to all DM group members". Rules that depend on knowing which leaves are loggers: "Any member MAY remove any other member ... other than a compliance logger or recorder"; "A compliance logger or recorder ... is never a host's user"; "the remaining member with the lowest leaf index, other than a compliance logger or recorder, moves the group"; "When no member remains other than one DID and compliance loggers, the group has ended".
Problem: Before this diff, a joiner learned logger DIDs from `complianceLoggers` in the descriptor, which the committer re-sent with every membership change. Brief item 3 assumes "logger presence come[s] from the ratchet tree", but §5.2.1.3 says a logger leaf looks like any other leaf. A member added after the logger's admission epoch cannot decrypt the disclosure notice. It therefore never learns that a logger is present, which is a gap in the §7.8.4 MUST. It also cannot apply the four rules above, so two clients pick different movers, give different host's-user answers and disagree on whether the group has ended.
Fix options:
(a) A new GroupContext extension `agora_compliance` (for example 0xF0A4) listing logger and recorder DIDs. The regulated member's client sets it in the same Commit as the logger Add, so joiners get it in the Welcome. Other GCEs copy it unchanged, and it is authenticated by the committer's MLS signature, as the old descriptor was.
(b) The regulated member's client re-sends `ComplianceDisclosureNotice` in the epoch of every Commit that adds a member. Joiners learn of the logger only when that client is online.
(c) A self-asserted LeafNode marker on logger leaves. Any member could claim it to make itself unremovable by compliant clients.
Recommendation: (a). It is the same pattern as `agora_admission`, keeps the state in MLS (S9), needs no regulated client to be online, and has the same trust as the deleted descriptor.
Needs decision: yes. The brief's premise that the ratchet tree shows logger presence is false, so a mechanism has to come back. Option (a) puts it in the group's MLS state, where joiners receive it.

### SC-3 Bogus-key recovery fails in two common cases

Severity: P2
Location: spec/04-access-control.md §4.6 "The `agora_admission` extension" and "Rotation"; spec/12-security.md "Bogus DM admission key"
Evidence: "A member that finds the key in the current GroupContext not admitted by the group's relays moves the group (§4.6.4), publishing the move Commit under the last admitted key it holds." "Once a Commit that replaces a key with another key of the same host has won, a client of the replaced key's issuee DELETEs the replaced key." "A client MUST NOT commit an `AgoraAdmission` that keeps `host` unchanged and does not increase `key_epoch`".
Problem: (i) If the bogus GCE keeps `host` and raises `key_epoch`, the real key's issuee DELETEs the last admitted key as soon as the bogus Commit wins. No admitted key is left to publish the move under. (ii) If every remaining member shares the bogus key's host (one employer's staff), "move to its own host" is a same-host change. It needs a `key_epoch` above the bogus one, but the host issues last+1. A bogus `key_epoch` of 2^64-1 blocks every later rotation and move to that host for good. The §12 text says the cure works, and in these cases it does not. Under the binding decision, recovery is supposed to be a move.
Fix: (i) The issuee DELETEs a replaced key only after a Relay in the new `relays` has accepted a Subscribe to the new key's `channelToken`, that is, it did not answer `unknown-token` (§11). (ii) Members MUST reject a same-host change whose committer is not a host's user (it can be checked through `KeyPackageEndpoint` origins). Then drop the "increase `key_epoch`" policy-violation rule for DM groups, or bound the increase. Epoch order already comes from MLS (S9), and `channelToken` needs only distinct (`seed`, `keyEpoch`) pairs, not increasing ones.
Needs decision: yes. Options: (a) both fixes above (recommended); (b) keep the rules and change §12 to say a bogus key can kill a same-host group, which then must be re-created. Plain version: as written, one member can make a group of coworkers permanently unusable, and the stated recovery does not get them out.

### SC-4 A removed member keeps relay admission for up to 30 days, or forever

Severity: P2
Location: spec/04-access-control.md §4.6 "Rotation", §4.6.4 last paragraphs; spec/12-security.md §12 bullet on DM tokens
Evidence: "a client of the replaced key's issuee DELETEs the replaced key. Until then a removed member can still have envelopes admitted". "A client whose user's last leaf is removed ... DELETEs 30 days after that Commit each key issued to its user". The host deregisters only "on its user's request or 30 days after its user is offboarded". 12: "every DM and self-group token registered under them belongs to a group that user is in or recently left".
Problem: The host accepts a DELETE only from the issuee. When the replaced key's issuee is the removed member itself (a same-host group where the creator is removed, or any move after removing the host's user), only the removed member's client can withdraw the key. It never sees the rotation Commit, and the 30-day rule is the only thing that deletes the key. If that client never returns (a lost device, a non-offboarded individual), the key stays registered forever. The same happens when the issuee is a member who stays offline. "Until then" understates the window, and "recently left" in §12 is not guaranteed.
Fix options: (a) Let the host accept DELETE of `keyEpoch` k from the issuee of any later key of that group. This closes the window, but in a same-host group a removed host's user can then POST a later key and kill the current one. That widens the accepted removed-host's-user limit to same-host groups. (b) Keep the rule and state the window in §4.6 and §12: until the replaced key's issuee's client DELETEs it, at most 30 days after removal when that client is alive, unbounded otherwise. Bounded by per-token rate limits, and the envelopes fail MLS.
Recommendation: (b), with a host-side cap: the host deregisters any key 30 days after it issued a later key for that group. That cap removes the unbounded case without the DoS that (a) opens.
Needs decision: yes (options above). Plain version: as written, a removed person's old key can keep working at relays long after removal, and nobody left in the group can switch it off.

### SC-5 The admission host's base URL is never defined

Severity: P2
Location: spec/04-access-control.md §4.6 ("`<host>` is the admission host's base URL"), "Creation", §4.6.4 move
Evidence: "the initiator's client POSTs to its identity host for the new group ID"; "The **host's user** is a member whose identity host, the origin of its `KeyPackageEndpoint` (§5.2.1.1), equals the origin of `host`". The only path rule elsewhere is §3.5's `POST <service>/auth` and its check that "`service` equals its own base URL".
Problem: Nothing tells a client which URL to POST to or to write as `host`. One implementer writes the origin, another `https://id.example.com/v1/agora`. The §3.5 `service` check then fails across implementations. An identity host that serves KeyPackages on another origin than its admission API has no host's user at all, which sets off the move fallback at once. This gap existed before the diff, but host's-user detection now depends on it.
Fix: "`<host>` is the origin of the user's `KeyPackageEndpoint`; the paths are `<host>/v1/agora/admission-key/<groupID>[/<keyEpoch>]`, and the §3.5 `service` is `<host>`." Add the endpoint to the versioned table in §13 if that table lists HTTP APIs.
Needs decision: no

### SC-6 The initial self-group GroupContext has no Space list

Severity: P2
Location: spec/02-identity.md §2.6; spec/04-access-control.md §4.6 "Creation"
Evidence: "A device that sees the user join or leave a Space, or a Space's endpoints change, commits a GroupContextExtensions proposal"; "A new device receives the list in its self-group Welcome"; step 3 "commits an Add of a further KeyPackage of the new device to each other group". RFC 9420 §11.1 requires an extension listed in required_capabilities to be supported, not to be present.
Problem: The spec never says that the device creating the self-group puts the current `AgoraSpaceList` in the initial GroupContext. §4.6 "Creation" covers only `agora_admission`. An implementation that adds the extension only on the next change sends the second device a Welcome with no list. That device then cannot validate the own-device Welcomes of step 3. The deleted "after it has sent the current `SpaceMembership` record" step used to guarantee this.
Fix: Add to §2.6: "The device that creates the self-group puts `agora_space_membership` with the current list in its initial GroupContext, and every self-group GroupContext carries it."
Needs decision: no

### SC-7 Rotation stalls when the lowest-leaf host's user is in the request state or offline

Severity: P2
Location: spec/04-access-control.md §4.6 "Rotation", §4.6.3
Evidence: "the client of the host's user with the lowest leaf index MUST POST for a new key and commit ...; another host's user's client MAY do the same." §4.6.3: a request-state client "MUST NOT send ... any other message to the group" and "MUST NOT fetch the group's messages until the user accepts".
Problem: A host's user still in the request state (same employer as the initiator, not yet accepted) cannot see the Remove and must not commit. If it has the lowest leaf, its MUST cannot be met, and nothing else is required to happen. The others only MAY act, and no timer applies. Request state is local, so other members cannot skip that member. Moves have a 24 h fallback, but rotation has none.
Fix: "If no Commit that changes `agora_admission` has arrived 24 hours after a Commit that removed the last leaf of a DID, every host's user's client not in the request state MUST rotate (competition resolved by §5.1.1)." State that a request-state client does not rotate or move.
Needs decision: no

### SC-8 Device removal never sets off rotation

Severity: P3 (existed before this diff; the new wording makes it explicit)
Location: spec/04-access-control.md §4.6 "Rotation"; spec/02-identity.md §2.6
Evidence: "After it processes a Commit that removes the last leaf of a DID".
Problem: In a self-group every leaf has the same DID, so removing a revoked or stolen device never rotates the key. The same holds for a revoked device's leaf in a DM. That device keeps relay admission for the self-group token, and §12 already says that token links the user's devices and push handles.
Fix: Rotate after any Commit that removes a leaf because of a device revocation (§2.5.5), or at least after any Remove in a self-group. Otherwise list this as an accepted limit in §12.
Needs decision: no (out of this diff's scope; recorded so it is tracked)

### SC-9 `archive` is dropped without saying so

Severity: P3
Location: spec/04-access-control.md `AgoraAdmission`; spec/03-spaces.md §3.4
Evidence: `ChannelAdmissionKey` has "`archive` is optional: the origin of a CO-operated blob store"; `AgoraAdmission` carries only `host`, `key_epoch`, `seed`, `relays`.
Problem: A host that returns `archive` has it silently discarded. Implementers will differ on whether DM members may use it.
Fix: "A DM admission host's `ChannelAdmissionKey` has no `archive`." This keeps the brief's field set.
Needs decision: no

### SC-10 False claim that members already know every `KeyPackageEndpoint`

Severity: P3
Location: spec/04-access-control.md §4.6 "host's user"
Evidence: "Members already resolve each member's DID for the credential binding (§5.2.1), which gives them its `KeyPackageEndpoint`." 02:19 and 05 §5.2.1.1: for `did:key` the endpoint is in the Pkarr record, and the `did:key` binding is checked against the key the DID encodes.
Problem: For `did:key` members, finding the host's user takes an extra Mainline DHT lookup, which an IO observes. The sentence hides that.
Fix: Add "for `did:key`, by fetching its Pkarr pointer record (§2.1)".
Needs decision: no

### SC-11 §12.11 table understates what the host learns

Severity: P3
Location: spec/12-security.md §12.11 table row "DM admission host"
Evidence: "Which DM group IDs its own user's client requests admission keys for, and when; not the group's other members".
Problem: After creation, every POST is a rotation (a removal) or a move, so the host also learns when members are removed and when the group moves. That is less than before, but the table is meant to be complete.
Fix: Add "and, from later requests, when members are removed or the group moves to its host".
Needs decision: no

### SC-12 Subscription to the old token: §5.2.2 and §4.6.4 disagree; Appendix C lacks client timers

Severity: P3
Location: spec/05-messaging.md §5.2.2 "Member duties"; spec/04-access-control.md §4.6.4; spec/99-appendices.md Appendix C
Evidence: 05: on "a Commit that changes `agora_admission`, it subscribes to the new token and keeps the previous subscription until the relay reports the old token withdrawn". 04: "keep the previous host's `channelToken`s only to fetch history". After a move, the old key is withdrawn 30 days later.
Problem: The two sections disagree on whether members stay subscribed to the old token for 30 days after a move. If they do, they keep receiving a removed member's envelopes for that long. Appendix C also lacks the two client-side 30-day DELETE timers (after a move, after one's own removal), and it collects "numeric limits in one place".
Fix: In §5.2.2, limit the keep-subscribed rule to same-host rotation. Add Appendix C rows for both client DELETE timers (§4.6.4).
Needs decision: no

### SC-13 The compliance-archive justification names the wrong reader

Severity: P3
Location: spec/12-security.md "Compliance archives and DM admission keys"
Evidence: "a logger's archive of a DM group holds that group's admission key seed. The logger, as a member, already holds that key."
Problem: The parties that gain are the people who read the archive (auditors, eDiscovery recipients), not the logger. From the seed they can compute the DM's `channelToken`s and link stored relay traffic, and while the key is current they can post envelopes. The decision to accept this is binding. Only the stated reason is wrong.
Fix: Add "Anyone given the archive can compute the group's channel tokens; this is accepted."
Needs decision: no
