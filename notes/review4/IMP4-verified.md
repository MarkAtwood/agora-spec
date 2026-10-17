# Review 4: IMP4 verified

Checked against the working tree at 4b76c3d (spec/ and ARCHITECTURE.md unmodified), `bd memories agora` (notably agora-dm-key-in-group, agora-dm-bogus-key-fix, agora-dm-key-cap, agora-dm-host-move, agora-dm-withdraw-limit, agora-dm-compliance-ext, agora-ux-musts, agora-gateways-profile), ARCHITECTURE §8 and §9, and spec §12.5. Every quote in IMP4.md was found verbatim at the cited lines.

Totals: 11 CONFIRMED, 2 PARTIAL (IMP4-1 fix options, IMP4-8), 0 REJECTED. Needs decision: IMP4-1.

### IMP4-1: DM host cannot replace a Relay; frozen relay list partitions DM groups and self-groups
- Verdict: CONFIRMED for the problem; PARTIAL on the options. The relay list is in `agora_admission` (04:196 "`key_epoch`, `seed` and `relays` are the `keyEpoch`, `seed` and `relays` of a `ChannelAdmissionKey` that `host` issued"), so it changes only by a member's GroupContextExtensions Commit. The host is the registration service and "acting as the CO for this purpose" (10:820), so S5 (ARCHITECTURE:110 "A CO MUST be able to add, remove or replace any IO without changing ... MLS group state") applies to it and cannot be met. §10.3.5's "Because members' MLS state, Space state and admission keys do not change" (10:555) is false for DM groups, and 10:555 itself says DM clients refresh relays only when "process a Commit that changes `agora_admission`". No rule forces rotation, so §10.4.7 retirement (10:688) or agreement end strands every group whose relays all depart. The recovery trigger (04:196 "each answering `unknown-token`") does not fire on unreachable Relays. Nothing in §12.5 or ARCHITECTURE §9 accepts this.
  The reviewer's recommended option (a) conflicts with binding text: agora-dm-key-in-group ("DM admission host keeps no member list and serves no members") and 12:258 ("the host does not learn the other members' DIDs or when they are active"). A host-published relay document fetched by non-host members tells the host when they are active. Option (a) is therefore not recommended.
- Severity: P1, keep. It breaks a normative ARCHITECTURE requirement and loses DM groups on routine Relay turnover.
- Fix (for option b, recommended):
  - spec/04-access-control.md, Rotation paragraph (04:200), append: "A host's user's client also rotates the key, as for a removal, when 7 days have passed since it processed the Commit that put the current key in `agora_admission`, so that the group picks up its host's current relays (§10.3.5). Competing rotations are resolved by the canonical-Commit rule (§5.1.1)."
  - spec/10-relays.md:555, after "...without touching Space identity or membership (ARCHITECTURE S5).", add: "For a DM group or a self-group the relay list is part of MLS state (§4.6) and changes at the next rotation, at most 7 days later; a DM admission host keeps a departing Relay registered until every key it issued that lists that Relay has been deregistered (§4.6), and so engages a replacement at least 14 days before a Relay's `retiresAt` (§10.4.7)."
  - spec/12-security.md §12.5, add bullet: "**Dormant DM groups and Relay replacement.** A DM group or self-group follows its admission host's relay changes only when a host's user's client is online to rotate (§4.6). A group none of whose host's users comes online before its listed Relays stop serving can no longer be used, and its members start a new one. This is an accepted limit."
- Needs decision: yes.
  - (a) Relays leave `agora_admission`; members fetch the host's current relay list. Contradicts agora-dm-key-in-group and 12:258.
  - (b) Keep relays in the extension; host's users rotate at least every 7 days; record the dormant-group limit in §12.5. Recommended: no new endpoint, keeps the host blind to other members, and fits inside the 30-day retirement notice.
  - (c) Record in §12.5 and ARCHITECTURE §9 that DM groups do not survive Relay replacement, and narrow S5 to Space groups.
  - In plain terms: a DM's Relays are written into the encrypted group, so the host cannot move them by itself. Option (b) has the host's own user refresh that list weekly, so Relay changes reach the group within about two weeks without the host learning anything new.

### IMP4-2: Routine withdrawal of a DM group's current key has no trigger, and the DM path loops on `token-withdrawn`
- Verdict: CONFIRMED. 02:454 step 4 ties removal to "when they next resolve the DID", and no rule sets when that happens. 04:175 deregisters the offboarded DID's keys at 30 days. 11:196 answers `token-withdrawn` while envelopes remain, and its DM path ("fetches that token's history ..., processes the Commits in it, and uses the key in `agora_admission`") has no exit when no new Commit exists. The §4.6 recovery fires only on `unknown-token` (04:196). The DELETE gate at 04:200 ("has not answered it with `unknown-token`") counts `token-withdrawn` as acceptance. This is distinct from the accepted limit at 12:71, which covers a removed host's user deleting the key at once.
- Severity: P2, keep.
- Fix:
  - spec/02-identity.md:454 step 4: change "members of groups outside the organization's control Remove them when they next resolve the DID" to "members of groups outside the organization's control Remove them when they next resolve the DID, which a member's client does for each other member of each DM group it holds at least once every 7 days (§4.6)". 7 days, not 24 hours, keeps resolution load low and still leaves time for the §4.6.4 move inside the 30-day window.
  - spec/04-access-control.md:196, change "each answering `unknown-token` (§11.4)" to "each answering `unknown-token` or `token-withdrawn` (§11.4)".
  - spec/04-access-control.md:200, change "that is, has not answered it with `unknown-token` (§11.4)" to "that is, has answered it with `Ack` and no per-token `Error` (§11.4)". Make the same change in §4.6.4 (04:247) where it refers back.
  - spec/11-transport.md:196, after "uses the key in `agora_admission` (§4.6)", add: "If that key is the refused one at every listed Relay, the client applies the recovery of §4.6 instead of retrying."
  - spec/12-security.md §12.5, extend the "Removed host's user withdraws the DM key" bullet: "The same holds when every listed Relay withdraws the current key, for example by token suspension (§10.4.7) or the end of the host's agreements, and no earlier key of the group is still admitted."
- Needs decision: no.

### IMP4-3: §10.5.3 registration-service rules contradict §4.6 DM host rules
- Verdict: CONFIRMED. 10:820 makes the DM host a registration service. 10:880 "deregisters the previous key ... after a grace period RECOMMENDED to be 300 seconds" contradicts 04:175 "Until a later key is confirmed, the host keeps an earlier key registered". 10:850 `replaces` MUST and 10:880 deletion rule assume knowledge the host lacks. 10:873 "before serving it to members" and 10:875 batching SHOULD are unreconciled with the synchronous POST. One small correction: the reviewer says DM clients ignore `token-rotated` per §11.4; 11:196 has no DM exception for `token-rotated`, which is a further reason to omit `replaces` for DM keys.
- Severity: P2, keep.
- Fix: spec/10-relays.md, at the end of the "When the CO deregisters" paragraph (10:880), add: "For a DM group or a self-group, §4.6 alone governs when the admission host deregisters a key: the 300-second grace period and the deletion rule above do not apply, the host omits `replaces` from every registration, and it completes registration with every IO it lists before it returns the key, with any batching delay applied before that response."
- Needs decision: no.

### IMP4-4: "Host's user" violation check depends on live resolution with no freshness or comparison rule
- Verdict: CONFIRMED. 04:167 and 04:196 quoted correctly. No origin comparison rule exists anywhere in spec/ (no RFC 6454 reference). §4.5 (04:143) gives Space groups a re-check ("fetches the current Space state head and re-checks") and nothing for DM groups. The check itself is binding (agora-dm-bogus-key-fix), so the fix keeps it and makes it convergent. Failing open on unresolvable committers is safe because 12:69 states a bogus key "gives a member no new power".
- Severity: P2, keep.
- Fix: spec/04-access-control.md:196, after the sentence "Members MUST treat as a policy violation (§4.5) a Commit that changes `agora_admission`, keeps `host`, and either keeps `key_epoch` or has a committer that is not a host's user.", add: "For this check `host` and the committer's `KeyPackageEndpoint` origin are compared as the ASCII serialization of their origins (RFC 6454 §6.2), byte for byte. Before treating a Commit as a violation because its committer is not a host's user, a member resolves the committer's DID document or Pkarr record afresh; if that resolution fails, it does not treat the Commit as a violation." Also state at 04:196 that a client writes `host` in that serialization.
- Needs decision: no.

### IMP4-5: Client conformance row omits member-side §7.8 duties
- Verdict: CONFIRMED. The Client row (01:79) lists §7.2, §7.5, §7.7 only. 07:240 binds all members ("Members MUST treat as a policy violation"), 07:271 and 07:285 bind every receiving and joining client. The §7.8 Conformance Summary (07:360 to 07:372) has rows only for the regulated member's client and the logger. The two "MUST present" duties are allowed by agora-ux-musts (one MUST present per legal notice).
- Severity: P2, keep.
- Fix:
  - spec/01-overview.md:79, change "§7.2, §7.5, §7.7 (adding the logger, expiry under logging, member disclosure)" to "§7.2, §7.5, §7.7 (adding the logger, expiry under logging, member disclosure); §7.8.2 (`agora_compliance` checks), §7.8.4 (presenting disclosure notices)".
  - spec/07-compliance.md Conformance Summary, add rows: "Treat an improper `agora_compliance` change as a policy violation | Any member's client | MUST" and "Present each `ComplianceDisclosureNotice`, and on joining a group with `agora_compliance` a notice per listed DID | Any member's client | MUST".
- Needs decision: no.

### IMP4-6: Gateways have no conformance class; recorder class lacks KeyPackage duties
- Verdict: CONFIRMED. 01:95 "A component that is not listed has no conformance definition". §9.1 (09:12, 09:33) and §9.3 (09:68) bind gateways and the adding Admin. The Client row says "§9.3 (gateway indicators)", hiding the Admin send-gate. The recorder is admitted with "a KeyPackage from the recorder's `KeyPackageEndpoint` (§7.8.2)" (06:348) and into DM groups by §6.12.7 (06:465), yet its row (01:89) omits KeyPackage host duties that the logger row has. Consistent with agora-gateways-profile, which keeps the core gateway rule normative.
- Severity: P2, keep.
- Fix (smaller than the reviewer's: a gateway is a member, so it builds on Client):
  - spec/01-overview.md table, add row: "Gateway | CO | Client (as a member of each channel it serves), plus §9.1 and §9.3 (gateway duties), §12.8".
  - spec/01-overview.md:79, change "§9.3 (gateway indicators)" to "§9.3 (send-gate for an Admin adding a gateway, indicators)".
  - spec/01-overview.md:89, change the recorder row to "§5.2.1.3, §6.12.1 to §6.12.7, the KeyPackage host class for its own DID, §7.8.2 (KeyPackage availability), §12.8".
- Needs decision: no.

### IMP4-7: "Send in the epoch the Add creates" is unsatisfiable when the epoch moves first
- Verdict: CONFIRMED. 07:271 and 07:285 ("in the epoch where the logger is admitted", "sent in the same epoch as the logger's admission commit"), 09:68 ("in the epoch that Add creates"), and 04:289 (§4.8 commit-before-send) quoted correctly. 07:311 "completed and acknowledged" has no defined meaning; "won (§5.1.1)" is already the term used at 07:217 and 04:175.
- Severity: P2, keep.
- Fix:
  - spec/07-compliance.md:271, replace "The notice MUST be sent as an application message in the epoch where the logger is admitted, before any other application message the client sends in that epoch:" with "The notice MUST be the client's first application message in the group after the Commit that admits the logger has won (§5.1.1), in whatever epoch is then current:".
  - spec/07-compliance.md:285, replace "sent in the same epoch as the logger's admission commit, prior to any other application messages" with "sent as described above".
  - spec/07-compliance.md:311, replace "completed and acknowledged" with "has won (§5.1.1)".
  - spec/09-interop.md:68, replace "and MUST send the `gateway-added` `SystemEvent` in the epoch that Add creates" with "and MUST send the `gateway-added` `SystemEvent` as its first application message in the channel after that Add has won (§5.1.1)".
  Members added after the notice are already covered by the later-joiner rule (07:289) and the `gateways` array (09:85).
- Needs decision: no.

### IMP4-8: Removal-attempt reporting has no mechanism; `removalAttempts` cannot be filled
- Verdict: PARTIAL. The first half is CONFIRMED and duplicates PRI4-5 (confirmed in PRI4-verified.md): no message type or endpoint carries "notify the regulated member's Space admin" (07:263, 07:369). The second half is overstated. Each re-add is a new logger admission (§7.8.3 re-adds "via the §7.8.2 procedure"), and 07:317 requires a `DMComplianceAuditEntry` for "each DM group compliance logger admission", so the logger writes a fresh entry at re-admission. As a member at the removal epoch it processes the Commit that removes it and sees its MLS sender. So `removalAttempts` can be filled in the re-admission entry; the defect is only that 07:334 names the wrong source ("that the regulated member's client detected"). Deleting the field would also break profiles/purview-bridge.md:607, guides/regulators.md:217 and guides/counsel.md:106, which PRI4-5's fix relies on. Redefining it is the smaller change and agrees with PRI4-5.
- Severity: P3 (lowered from P2, matching PRI4-5). Capture is unaffected; the defect is an unimplementable reporting MUST and a field defined from the wrong source.
- Fix: apply the PRI4-5 fix from PRI4-verified.md as written (drop the client notification and its Summary row, name the audit records as the notice, update the guides), plus:
  - spec/07-compliance.md:334, replace the `removalAttempts` sentence with: "`removalAttempts` lists, for the entry written at a re-admission (§7.8.3), the Remove Commit that removed the logger before this admission, as objects `{ \"epoch\": <epoch the Remove created>, \"removedBy\": <MLS sender DID of that Commit> }`; the logger takes both from the Commit, which it processes as a member. It is empty for a first admission."
  The new-message-type option (a) in IMP4.md is rejected: it adds a client duty and a type where the logger already observes everything needed.
- Needs decision: no. (The reviewer's options reduce to the PRI4-5 fix once the field is redefined; no binding decision is touched.)

### IMP4-9: No rule for DM groups that exist when a member becomes regulated
- Verdict: CONFIRMED. 07:203 covers only groups the member "creates or joins". No text anywhere covers a DID added to or removed from `regulatedMembers`, or `enabled` turning false (grep of "regulatedMembers" across spec/ finds only 07:46 to 07:52 and the §7.8 text). Also, 07:258 limits the removal ban to "the duration of the regulatory retention period", which no client can compute and which conflicts with the unconditional rule at 04:202 and 07:242 ("members do not remove it").
- Severity: P2, keep.
- Fix:
  - spec/07-compliance.md §7.8.1, after the numbered list, add: "When a client learns from Space state that its user has become a regulated member, it performs §7.8.2 and §7.8.4 in each DM group the user belongs to before the user next sends there. When its user stops being a regulated member, or `complianceLogging.enabled` becomes `false`, the client adds no further loggers; loggers already admitted stay (§7.8.3)."
  - spec/07-compliance.md:258, delete "for the duration of the regulatory retention period".
- Needs decision: no.

### IMP4-10: Rotation and handover duties are assigned by other members' local request state
- Verdict: CONFIRMED. 04:200 "lowest leaf index among those not holding the group in the message request state" is not computable by other members; request state is local (04:235 "kept locally"). 04:243 handover default has the same shape via 04:167. The outcome today is the same 24-hour delay, but undocumented and implementation-dependent.
- Severity: P3, keep.
- Fix:
  - spec/04-access-control.md:200, change "the client of the host's user with the lowest leaf index among those not holding the group in the message request state (§4.6.3) MUST POST" to "the client of the host's user with the lowest leaf index MUST POST", and append to that paragraph: "A client that holds the group in the message request state skips this duty (§4.6), so rotation can then wait for the 24-hour fallback."
  - spec/12-security.md:68, after "so the window lasts at least that long", add "or 24 hours if that client holds the group as a message request (§4.6.3)".
- Needs decision: no.

### IMP4-11: DM admission host API loose ends
- Verdict: CONFIRMED, all four points. (1) 04:175 sets `service` to `<host>`, an origin, so 03:335 gives `<host>/auth`, outside the versioned prefix of 13:141. (2) The API gives bare statuses where §10.5.3 (10:860 to 10:869) uses `{ "error": "<code>" }`. (3) 04:175 "records when it arrived" does not say which arrival wins on repeats, and the 7-day timer depends on it. (4) No rule for partial registration failure.
- Severity: P3, keep.
- Fix, all in spec/04-access-control.md:175:
  - Change "whose `service` is `<host>`" to "whose `service` is `<host>/v1/agora/admission-key`".
  - Replace the closing status list with: "Otherwise the host answers with the status below and a JSON body `{ \"error\": \"<code>\" }`: `400` `malformed`, `401` `unauthenticated`, `403` `not-served` (a DID it does not serve) or `not-issuee` (a confirmation or DELETE from a DID that is not the key's issuee), `404` `unknown` (group or `keyEpoch`), `429` `rate-limited`, `503` `no-relay` (below)."
  - After "the host records when it arrived and returns `204`", add "; it keeps the first arrival time and answers a repeated confirmation `204` without change".
  - After "registers it", add "; the key's `relays` lists only IOs that accepted the registration, and if none did the host answers `503`".
- Needs decision: no.

### IMP4-12: No rule tells a client whether a Welcome is for a Space group or a DM group
- Verdict: CONFIRMED. 04:90 scopes itself to "a Space channel group" but its fetch-and-hold rule needs a classification that 04:204 only implies. Space channel groups never carry `agora_admission` (it appears only for DM groups and self-groups at 04:192, 99:123, 10:551), so the extension is a sound discriminator.
- Severity: P3, keep.
- Fix: spec/04-access-control.md:90, at the start of the Welcome acceptance paragraph, add: "A Welcome whose GroupContext carries `agora_admission` is a DM group or self-group Welcome and is decided by §4.6 and §2.6; a client MUST reject such a Welcome whose group ID a channel or Space group in its copy of Space state declares. Any other Welcome is decided by this paragraph."
- Needs decision: no.

### IMP4-13: A member regulated by more than one Space has no rule
- Verdict: CONFIRMED. 07:203 "the Space's `loggerDID`" is singular; 07:297 covers several regulated members, not one member regulated by several Spaces.
- Severity: P3, keep.
- Fix: spec/07-compliance.md:203, change "Add the Space's `loggerDID` to the MLS group" to "For each Space whose `regulatedMembers` lists the user, add that Space's `loggerDID` to the MLS group". Apply the same "each such Space" wording at 07:340 (the §7.8.9 send-gate) and 06:465 (`recorderDID`).
- Needs decision: no.
