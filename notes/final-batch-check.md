# Final batch check: S9, MLS-SoT, SC-1..SC-13, §4.6.3 policy senders, UX MUSTs

Scope: `git diff` of the working tree on 2026-10-17, excluding `.beads/`. Decisions in `bd memories agora` (agora-dm-compliance-ext, agora-dm-bogus-key-fix, agora-dm-key-cap, agora-dm-withdraw-limit, agora-ux-musts, agora-dm-key-in-group, agora-dm-no-descriptor) are taken as binding. The findings below are cases where the text, read together with those decisions, does not deliver what the decision intends.

Counts: P1 1, P2 4, P3 4.

Clean:
- No em dashes in added lines.
- No leftover `agora_admission_host`, `DMMembers`, `DMGroupDescriptor`, `AddApproval`, `consentModel`, `admissionHostDID`, `SpaceMembership`, `complianceLoggers`, `dmGroupDescriptorCID`, `/members` or `/v1/auth` in spec/, profiles/, guides/ or ARCHITECTURE.md. `import/` files are archival and still mention them.
- Every § reference added by the diff resolves (§7.5 retentionNotice, §7.7, §8.8, §12.10, §13.2, §4.6.4 and others checked).
- The TLS structs (`AgoraAdmission`, `AgoraSpaceList`, `AgoraCompliance`) match their prose and Appendix D. The Appendix C rows match §4.6 and §4.6.4.
- RFC 9420: the wholesale replacement in GroupContextExtensions (§12.1.7) and the `required_capabilities` support rule are handled correctly. The joiner's GroupContext comes from the Welcome (§12.4.3.1).
- UX MUSTs: apart from FB-9, the only BCP 14 MUSTs left on presentation are the kept ones: the legal notices (07:163, 07:285, 07:289, 06:360, 08:133), each with one "MUST present" and its send or transmit gate; bidi isolation (02:120); raw HTML (05:511); untrusted SFU text (06:177); directory sources (10:467); and the non-member broadcaster check (05:210, an authorization rule).

### FB-1 7-day host cap deregisters the current key when the newest issued key was never committed

Severity: P1
Location: spec/04-access-control.md §4.6 (host rules paragraph after the endpoint block; "The `agora_admission` extension", last sentences); spec/12-security.md "Bogus DM admission key"
Evidence: "Seven days after it issues a key for a group, the host deregisters every earlier key of that group on its own, unless the new key's issuee has deleted the new key by then". "It publishes that Commit under the last admitted key it holds, which is still registered, because the issuee of a replaced key deletes it only after a Relay has admitted the new key". §12: "Members recover with the previous key, which stays registered for at least 7 days".
Problem: The host cannot tell whether the key it issued was committed. A host's user's client POSTs key k+1 for a rotation, which happens automatically after a removal, and then never publishes the Commit or loses it. Causes include a crash, a phone suspended mid-flow, a lost device, or a Commit that lost and was not re-proposed before the client went offline. If that client does not return within 7 days, the host deregisters key k, which is the key in the current GroupContext. Every member then gets `token-withdrawn` and holds no admitted key. The rotation-or-move recovery needs a Commit published under an admitted token, and none exists, so the group is dead for every member. The issuee's other devices cannot help, because the host returned k+1 only to the device that POSTed. The "which is still registered" claim in §4.6 and the recovery stated in §12 are false in this case. No malice is needed.
Fix options: (a) Add a confirmation. Once the rotation Commit has won, the new key's issuee sends the host a request (for example `POST <host>/v1/agora/admission-key/<groupID>/<keyEpoch>/committed`). The 7-day cap runs from that confirmation instead of from issue. Until it arrives, earlier keys stay registered until their issuees DELETE them or are offboarded. The cost: if the rotator crashes between the win and the confirmation, the removed member keeps admission longer (relay capacity only, as SC-4 noted). (b) The host deregisters a key only once it is two or more behind the newest issued key. One stranded key no longer kills the group, but two stranded keys still do, and a removed member's key stays registered until the next rotation. (c) Keep the rule and change §4.6 and §12 to say that a host's user who goes offline for 7 days mid-rotation ends the group.
Recommendation: (a). It is the only option that keeps both liveness and the SC-4 cap in the normal case.
Needs decision: yes. Plain version: as written, one member's phone dying at the wrong moment, followed by a week offline, makes the conversation permanently unusable for everyone.

### FB-2 One Relay's `unknown-token` triggers a group move by every member

Severity: P2
Location: spec/04-access-control.md §4.6 "The `agora_admission` extension", last two sentences; spec/10-relays.md §10.3.5
Evidence: §4.6: "A member that finds the key in the current GroupContext not admitted by the group's relays, because a Relay in its `relays` answers a Subscribe to its channel token with `unknown-token` (§11.4), rotates the key if it is a host's user and otherwise moves the group". §10.3.5: "Clients SHOULD fall back to another listed Relay when one is unreachable or answers `unknown-token` or `token-withdrawn` for a token the client holds".
Problem: §10.3.5 treats one Relay's `unknown-token` as a reason to use another Relay, while §4.6 treats it as proof of a bogus key. A Relay that failed or lagged one registration, restored from backup (§10.4.7: "starts with no registrations"), or was newly listed makes every member who is not a host's user POST to its own host and commit a move at the same time. One move wins, the others DELETE, and the group's relays and host change because of an operational fault at one Relay. Implementers will choose differently between the two rules.
Fix: In §4.6, "because no Relay in its `relays` that it can reach accepts a Subscribe to its channel token". This mirrors the DELETE condition, which already uses "a Relay ... has accepted".
Needs decision: no

### FB-3 After a move, members drop the previous host's subscriptions, so the bogus-host recovery Commit reaches no one

Severity: P2
Location: spec/05-messaging.md §5.2.2 "Member duties"; spec/04-access-control.md §4.6 (recovery sentence) and §4.6.4; spec/12-security.md "Bogus DM admission key"
Evidence: §5.2.2: "When it processes a Commit that moves a DM group to another host (§4.6.4), it subscribes to the new token and ends its subscriptions to the previous host's tokens." §4.6: a member that finds the key not admitted "moves the group (§4.6.4). It publishes that Commit under the last admitted key it holds". §12: "any other member moves the group to its own identity host (§4.6.4), and publishes that Commit under the previous key."
Problem: Take a member who commits a move to a host value with an unregistered key (allowed, since `host` changes and only the committer's own MUST forbids it). Every member processes the move and unsubscribes from the previous host's token, as §5.2.2 requires. Each then finds the new token unknown and publishes its own recovery move under the previous token, which nobody now subscribes to. Under the no-sequencer rule each member sees only its own Commit for that epoch and applies it, so the group forks into one branch per member. The same rule also drops envelopes that slower members still publish under the old token during an ordinary move. Same-host rotation does not have the problem, because there §5.2.2 keeps the old subscription until the token is withdrawn.
Fix: In §5.2.2, on a move, "keeps its subscriptions to the previous host's tokens until a Relay in the new key's `relays` has accepted a Subscribe to the new token, and then ends them". This uses the same condition as the issuee's DELETE in §4.6.4.
Needs decision: no

### FB-4 DM clients have no action on `token-withdrawn`, and the replaced key is deleted with no grace period

Severity: P2
Location: spec/11-transport.md §11.4 "Withdrawn tokens"; spec/05-messaging.md §5.2.2 "Member duties"; spec/04-access-control.md §4.6 "Rotation"; spec/10-relays.md §10.5.3 "When the CO deregisters"
Evidence: §11.4: "On either code the client fetches the current `ChannelAdmissionKey` (§5.2.2)." "On `token-rotated` the client fetches the current `ChannelAdmissionKey`". §5.2.2: "In a DM group or a self-group it fetches nothing and instead uses the key in `agora_admission`". §4.6: "Once a Commit that replaces a key ... has won, and a Relay in the new key's `relays` has accepted a Subscribe ..., a client of the replaced key's issuee DELETEs the replaced key." §10.5.3: "deregisters the previous key once members have had time to move to the new token, after a grace period RECOMMENDED to be 300 seconds".
Problem: A Space member that gets `token-withdrawn` fetches the new key from the endpoint. A DM member cannot, because the new key is only in a Commit it has not yet processed. That Commit is in the withdrawn token's history, but no text tells the client to fetch it from there. The issuee's DELETE can follow the winning Commit within seconds, often from the rotator itself, so a member that was briefly offline, or is still inside the 5-second collection window, has its Publishes refused and its subscription ended. Space keys get a 300-second grace for exactly this case; DM keys get none. Implementers will diverge on recovery (refetch history, wait, or treat the group as broken).
Fix: (1) In §11.4, add: "In a DM group or a self-group, the client instead fetches that token's history (§11.8), processes the Commits in it, and uses the key in `agora_admission` (§4.6)." Mirror this in §5.2.2. (2) In §4.6 "Rotation" and §4.6.4, have the issuee DELETE "no sooner than 300 seconds after" the stated conditions, matching §10.5.3.
Needs decision: no

### FB-5 §5.2.1 capability restatement omits 0xF0A4

Severity: P2
Location: spec/05-messaging.md §5.2.1, Authentication Service paragraph
Evidence: "Every Agora client lists 0xF0A0 (`agora_admission`, §4.6), 0xF0A1 and 0xF0A3 (`agora_space_membership`, §2.6) in its leaf `capabilities.extensions`." The KeyPackage checks in the same section: "lists 0xF0A0, 0xF0A1, 0xF0A3 and 0xF0A4 (§5.2.1)". §7.8.2: "every Agora client lists 0xF0A4 in its leaf `capabilities.extensions`".
Problem: An implementer who follows the sentence that states the leaf duty will publish KeyPackages that every other client rejects. A DM group's `required_capabilities` also lists 0xF0A4, so such a client could not be added (RFC 9420 §12.1.7).
Fix: "lists 0xF0A0 (`agora_admission`, §4.6), 0xF0A1, 0xF0A3 (`agora_space_membership`, §2.6) and 0xF0A4 (`agora_compliance`, §7.8.2)".
Needs decision: no

### FB-6 Rotation MUST falls on a client the request state forbids from rotating

Severity: P3
Location: spec/04-access-control.md §4.6, "host's user" paragraph and "Rotation"
Evidence: "A client that holds the group in the message request state (§4.6.3) neither rotates the key nor moves the group." "the client of the host's user with the lowest leaf index MUST POST for a new key and commit".
Problem: In a group with several host's users (colleagues of one employer, or a self-group's new device), the lowest-index one may be in the request state. One reading skips to the next host's user; the other waits for the 24-hour fallback.
Fix: "the client of the host's user with the lowest leaf index among those not holding the group in the message request state".
Needs decision: no

### FB-7 Counsel guide restates deleted consent rule and old display gate

Severity: P3
Location: guides/counsel.md:81
Evidence: "The client will not send any message into the group until the logger is a member and the disclosure has been shown (spec §7.8.1). No consent threshold applies to adding the logger (spec §7.7)."
Problem: §7.8.1 now gates on having sent the `ComplianceDisclosureNotice`, not on it being shown. §7.7 no longer mentions a consent threshold, and DM Adds now need no approval at all (§4.6.1).
Fix: "until the logger is a member and the client has sent the disclosure notice (spec §7.8.1). Adding the logger needs no other member's consent (spec §4.6.1, §7.7)."
Needs decision: no

### FB-8 A logger leaf without an `agora_compliance` entry cannot be repaired

Severity: P3
Location: spec/07-compliance.md §7.8.5 and §7.8.2 (`agora_compliance` paragraph)
Evidence: §7.8.5: "verify on group join that their Space's logger DID has a leaf in the group's ratchet tree, and add it if absent". §7.8.2: "Members MUST treat as a policy violation (§4.5) a Commit that adds an entry without adding a leaf of that DID".
Problem: If the logger DID was added as a plain member (by a client that skipped the entry), the regulated member's check passes and no entry exists. Later joiners get no notice, and the §4.6 and §4.6.4 exclusions do not apply to it. Adding the entry now would be a policy violation.
Fix: In §7.8.5, check for "a leaf and an `agora_compliance` entry". If the leaf exists without an entry, the client removes the leaf and re-adds it with the entry in one Commit, as §7.8.2 allows.
Needs decision: no

### FB-9 Discord profile keeps a display MUST for the recovery key fingerprint

Severity: P3
Location: profiles/discord-onboarding.md:185
Evidence: "The tool MUST validate that the value decodes to a 32-byte Ed25519 public key and MUST show its fingerprint for the user to compare against the offline device."
Problem: notes/ux-musts.md does not list it. It is a display rule, but it serves key verification, close to the kept anti-spoofing class. Its status should be decided rather than left by omission.
Fix: Either keep it (key verification) or change it to "SHOULD show its fingerprint".
Needs decision: yes (keep or SHOULD)
