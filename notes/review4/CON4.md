# Review 4, lens CON4: cross-file consistency

Commit 4b76c3d. Scope: spec/, ARCHITECTURE.md, Appendix C and D, guides/, profiles/.

Clean checks (not findings):
- No surviving description of a removed mechanism as current: DMMembers, DMGroupDescriptor, AddApproval, consentModel, SpaceMembership, agora_admission_host, a members GET, publication window, 10 s / 15 s commit windows, DM self-removal rules, envelope CID of agreements, Relay-to-Relay Bitswap. The MIMI mentions in spec/09, Appendix A and ARCHITECTURE all mark MIMI as a future option.
- Every numeric section reference in spec/ resolves to an existing heading, and RFC section citations (RFC 9420 §6.3.1, §6.3.2, §7.6, §12.1.2, §12.1.7, §12.4.1, §12.4.2, §12.4.3.1, §12.4.3.3; RFC 8032 §5.1.5; RFC 7515 §7.2.1; RFC 9110 §16.3; RFC 8620 §9.4) point to the right RFC sections.
- The DM admission endpoints (POST issue, POST `/committed`, DELETE, no GET) match across spec/04, spec/13, profiles/o365-employer-did.md and profiles/discord-onboarding.md. The 7-day confirmation cap matches across §4.6, §12 and Appendix C:100.
- Appendix D extension codepoints 0xF0A0 to 0xF0A5 match every definition, and `required_capabilities` and client capability lists agree. 0xF0A2 in profiles/gateways.md:113 is a credential type, which is a separate registry, so it does not collide.
- `closingHeads` `{channelID, stream, n, hash}` matches across §3.3, §14.4.5 and Appendix D.
- Space state `seq` must advance by exactly one (spec/03-spaces.md:356), so the fork rule at 05:38 cannot be gamed with a large `seq`.

---

### CON4-1: Whether a Commit "counts" depends on clock and DID-document state, contradicting "no clock is consulted"
- Severity: P1
- Location: spec/05-messaging.md:29, :30, :79, :127, :130; spec/12-security.md:187, :194
- Evidence:
  - 05:29: "A stamped Commit **counts** if it ... passes RFC 9420 §12.4.2 validation and the checks of §5.2.1."
  - 05:30: "The sequencer's log (§14.4.3) is the sole referee, and no clock is consulted."
  - 05:127: "every member processing the Commit MUST validate the KeyPackages it adds". 05:130: "The KeyPackage is within its `leaf_node.lifetime`."
  - 05:79: `signature_key` "MUST be ... listed under `authentication` in that DID's current DID document". The same paragraph says "A leaf that fails the check makes the carrying KeyPackage, Commit or Welcome invalid."
  - 12:187: "Message order does not depend on any clock: ... competing Commits in a Space with a sequencer by commit stream position (§5.1.1)". 12:194 lists the clock check "KeyPackage `lifetime.not_after` | Welcome recipient | §5.2.1.1".
- Problem: Both the lifetime check and the "current DID document" check give different answers at different times. A member that processes the stream live and a member that catches up from the log days later (after the KeyPackage expired, or after a device revocation under §2.5.5) disagree on whether the lowest-position Commit counts. They then apply different winners, and the group forks. The §12 table says only the Welcome recipient checks lifetime, which contradicts 05:127.
- Fix: Restrict "counts" to checks that give every member the same answer at any time. Move the lifetime check and the DID-document binding check after winner selection, and treat a failure there as a policy violation (§4.5), as 05:32 already does for Space-state authorization. Align the §12 clock table.
- Needs decision: yes. (a) Both checks move after winner selection, as policy violations. (b) Only the committer checks lifetime, and members judge the DID binding against the DID log as of the stamp. Recommendation: (a), because it implements the binding decision that the winner is chosen by MLS validity only. Plain language: today two honest members can disagree on which Commit won just because one of them looked later. Option (a) makes the winner depend only on the log, and handles late failures the way unauthorized Commits are handled.

### CON4-2: Sequencer replacement leaves a window in which the old sequencer stamps above the closing head, with no recovery
- Severity: P1
- Location: spec/14-jmap.md:257; spec/05-messaging.md:25, :29; spec/03-spaces.md:195
- Evidence:
  - 14:257: "The CO replaces a faulty sequencer by a Space state change, then rotates the admission keys of the Space's channels". The same paragraph: "On that stream members accept a stamp signed by the old DID only at or below the head".
  - 05:25: "once the CO registers a rotated key whose registration names the old token in `replaces` (§10.5.3), the sequencer stamps no further Commit on the old token's commit stream".
  - 05:29: a member checks the stamp "as signed by the `sequencer` DID in the Space state the member holds".
- Problem: The order given is: pick the head, sign the state change, then rotate. The old stream closes for stamping only at rotation. In between, the old sequencer, honest or not, keeps stamping. A committer that still holds the old state gets a stamp above the head and wins under its view. Members on the old state apply that Commit, and members on the new state reject it. 05:29 gives a recovery only for gaps that cannot be filled. It gives none for a member that has already applied a Commit above the head, so the group stays forked. This happens even in a planned provider switch.
- Fix: In §14.4.5, require the CO first to register the rotated keys (or deregister the channels' keys at the old sequencer), and only then read the heads and sign the state change. In §5.1.1, add: a member that learns of a `closingHeads` below a Commit it has applied deletes its group state and asks to be re-added, as at 05:30.
- Needs decision: no

### CON4-3: The Space's own MLS group has no admission key, so it cannot be published to or sequenced
- Severity: P2
- Location: spec/03-spaces.md:175, :193, :195, :280-281, :323; spec/05-messaging.md:27, :288; spec/04-access-control.md:295
- Evidence:
  - 03:193: `sequencer` is for "choosing among competing Commits in the Space's groups (§5.1.1)".
  - 05:27: "If the group is a channel of a Space whose state designates a `sequencer`".
  - 05:288: "**Admission key.** For each channel, the CO's registration service generates ...". 03:280: "GET <spaceEndpoint>/admission-key/<channelID>".
  - 03:195: `closingHeads` has "one entry ... per channel that has an MLS group".
  - 03:323 sends `SpaceStateHead` "in the Space's MLS group (`mlsGroupID`, §3.3)". 04:295: "A Commit in the Space's own group whose self-Removes cover every leaf of a member DID is that member's notice of leaving."
- Problem: The Space's own group carries leave notices and state-head notices, but nothing defines its admission key or `channelToken`. Members cannot publish to it or subscribe to it, and it has no commit stream. §3.3 says the sequencer orders it, §5.1.1 limits the sequencer rule to channels, and `closingHeads` omits it.
- Fix: Define the Space group's admission key (for example served at `<spaceEndpoint>/admission-key/space`). Then either give it a commit stream and a `closingHeads` entry, or state that it follows the no-sequencer rule, and align 03:193.
- Needs decision: yes. (a) Admission key plus sequencing, like a channel. (b) Admission key, unsequenced. Recommendation: (a), because every member is in this group, so it sees the most competing Commits. Plain language: the one group every member belongs to has no defined way to reach the relays. It needs a key like a channel's, and it should be ordered like a channel.

### CON4-4: Shared channels do not say whose sequencer orders their Commits
- Severity: P2
- Location: spec/05-messaging.md:27, :29; spec/08-cross-space.md:95-100, :141
- Evidence:
  - 05:29: the stamp must verify "as signed by the `sequencer` DID in the Space state the member holds".
  - 08:95: "The home Space's CO is the only CO that issues and registers anything for a shared channel."
  - 08:141 is explicit only for calls: "The SFU used is the home space's SFU".
- Problem: Guest members hold the guest Space's state. If the two Spaces name different sequencers, or only one names a sequencer, guests and home members apply different commit rules, and the group stalls or forks.
- Fix: State in §8.6 and §5.1.1 that a shared channel uses the home Space's `sequencer` and `closingHeads`, and that guests fetch the home Space state head for this purpose.
- Needs decision: no

### CON4-5: The no-sequencer rule does not exclude invalid Commits from "lowest envelope id"
- Severity: P2
- Location: spec/05-messaging.md:34 (contrast :29)
- Evidence: 05:34: a member "collects every Commit for epoch N that arrives within 5 seconds of the first. It then applies the Commit whose envelope `id` (§5.2.2) is lowest". Only the sequencer branch (05:29) defines a Commit that "counts".
- Problem: This rule covers every DM. One client picks the lowest valid Commit, and another picks the lowest envelope, then fails to apply it. Any holder of the admission key can trigger the split.
- Fix: Change 05:34 to "the Commit that counts (as defined above) whose envelope `id` is lowest". CON4-1 also applies here.
- Needs decision: no

### CON4-6: DM recovery fires only on `unknown-token`, but a withdrawn key returns `token-withdrawn`
- Severity: P2
- Location: spec/04-access-control.md:196; spec/11-transport.md:196; spec/12-security.md:71
- Evidence:
  - 04:196: "A member that finds the key ... not admitted ... because no Relay in its `relays` that it can reach accepts a Subscribe to its channel token, each answering `unknown-token` (§11.4), rotates the key if it is a host's user and otherwise moves the group".
  - 11:196: the Relay answers with "`token-withdrawn` for as long as it still holds envelopes under the token, and with `unknown-token` after that". The same paragraph: "In a DM group or a self-group, the client instead fetches that token's history (§11.8), processes the Commits in it, and uses the key in `agora_admission`".
  - 12:71 accepts stranding only for "Removed host's user withdraws the DM key".
- Problem: A current DM key is withdrawn when the host's agreement ends, when a Relay suspends the token, or at the 30-day offboarding deregistration. Members then get `token-withdrawn`, which §11.4 answers by going back to the same key, so the §4.6 move never starts until relay retention expires. Even then, the move Commit must be published under an earlier key that is still registered, and such keys are usually gone 7 days after confirmation. A host that stops operating therefore strands its DMs, and §12 does not list that limit.
- Fix: Change 04:196 to "each answering `unknown-token` or `token-withdrawn`". Add to §12 that a group is stranded when no earlier key is still registered.
- Needs decision: yes. (a) Widen the trigger, and accept host failure or agreement lapse as a stranding limit in §12. (b) Widen the trigger and add a recovery path, such as re-creating the group from members' state. Recommendation: (a). Plain language: when a DM's host goes away, members today keep retrying a dead key instead of moving the group. Widening the trigger fixes the common case, and the rare case where no old key is left gets written down as a known limit.

### CON4-7: Logger removal ban is limited to "the retention period" in §7.8.3 and the guides, but is permanent in §4.6
- Severity: P2
- Location: spec/07-compliance.md:258; spec/04-access-control.md:202; spec/07-compliance.md:242; guides/regulators.md:188; guides/counsel.md:101
- Evidence:
  - 07:258: "no member, including the regulated member, MAY issue an MLS Remove commit for the logger DID for the duration of the regulatory retention period."
  - 04:202: "Any member MAY remove any other member of a DM group, other than a compliance logger or recorder".
  - counsel.md:101: "the compliance logger may not be removed for the duration of the retention period (spec §7.8.3)". regulators.md:188: "No member may remove the l[ogger] ... during the retention period".
- Problem: The retention period applies to records, not to group membership, so the ban has no defined end in a live group. Clients will disagree on whether a later logger Remove is a policy violation.
- Fix: Delete "for the duration of the regulatory retention period" at 07:258, and make the same change in both guides.
- Needs decision: no

### CON4-8: §7.8.5 repair removes the logger, which §7.8.3 forbids, and a leaf-less entry has no repair
- Severity: P2
- Location: spec/07-compliance.md:301; spec/07-compliance.md:240, :258, :262, :263
- Evidence:
  - 07:301: "If the leaf exists without an entry, it removes every leaf of that DID and re-adds it with the entry in one Commit, as §7.8.2 allows."
  - 07:262: the client MUST "Refuse to commit an MLS Remove proposal targeting the Space's `loggerDID`."
  - 07:240 never describes a remove and re-add in one Commit. It says only "adds an entry in the same Commit as its Add ... including a re-add" and "No two entries have the same `did`".
  - 07:263: after a committed Remove, the client re-adds the logger, "which also restores its `agora_compliance` entry".
- Problem: A client that obeys §7.8.3 refuses the §7.8.5 repair, and the "as §7.8.2 allows" pointer cites a rule that is not there. In the reverse case, another member removes the logger's leaves but leaves its entry. That is a policy violation, but the Commit is valid MLS and stands. The §7.8.3 re-add then adds a second entry for the same DID, which breaks "No two entries have the same `did`".
- Fix: In §7.8.3, exempt a Commit that removes and re-adds the same logger DID with its entry. In 07:240, state that case, and that a re-add keeps an entry already present unchanged.
- Needs decision: no

### CON4-9: parlance profile makes an exception to a spec MUST
- Severity: P2
- Location: profiles/parlance.md:96; spec/06-calls.md:480
- Evidence: Profile: "intents MUST travel as MLS messages and never on a data channel. The one exception is a two-member group of one operator and the Arbiter front end, where membership identifies the sender." Spec 06:480: "A payload whose receiver acts on the identity of its sender MUST be sent as an MLS application message instead."
- Problem: A non-normative profile allows what the spec forbids. A data channel authenticates only "some current member", and a removed member can still hold the channel key, so membership does not identify the sender.
- Fix: Delete the "one exception" sentence.
- Needs decision: no

### CON4-10: discord-onboarding Add flow ignores the canonical-Commit rules and adds one KeyPackage
- Severity: P2
- Location: profiles/discord-onboarding.md:418-428; spec/05-messaging.md:25, :36, :107
- Evidence:
  - Step 1: "Fetches one KeyPackage from the user's `KeyPackageEndpoint`". Step 3: "Publishes the commit to the channel like any member's handshake message". Step 4: "POSTs the Welcome".
  - 05:25: "Before publishing a Commit, the committer submits it per §14.4.3 steps 2 and 3". 05:36: "A committer MUST NOT deliver the Welcome for an Add in its Commit until that Commit has won". 05:107: "A committer adding the user adds every returned KeyPackage."
- Problem: In a Space with a sequencer, the enrollment agent publishes an unstamped Commit. In any Space, it can send a Welcome for a Commit that lost, so the new user joins a dead branch. It also adds only one device.
- Fix: Step 1 adds every returned KeyPackage. Step 3 follows §5.1.1. Step 4 runs only after the Commit has won.
- Needs decision: no

### CON4-11: discord-onboarding passkey PRF wrapping is incompatible with spec §12.6
- Severity: P2
- Location: profiles/discord-onboarding.md:162, :177; spec/12-security.md:93
- Evidence: Profile: "prf: { eval: { first: prfSalt } }" and "stores only the wrapped key with the credential ID and `prfSalt`". Spec: "PRF input `first` set to SHA-256 of the UTF-8 string `agora/v1/webauthn-prf`, and derives a 32-byte wrapping key as `HKDF-SHA256(...info = "agora/v1/webauthn-prf-wrap", L = 32)` ... stores only the wrapped key and `iv`".
- Problem: The profile's `prfSalt` is undefined and it skips the HKDF step, so an Agora web client that follows §12.6 cannot unwrap the key the enrollment app stored, and the reverse also fails.
- Fix: Use the fixed §12.6 PRF input and the HKDF derivation, and store `iv` instead of `prfSalt`.
- Needs decision: no

### CON4-12: o365 profile moves `idpToken` out of the signed registration body
- Severity: P2
- Location: profiles/o365-employer-did.md:563, :578, :583 (inherited by profiles/gsuite-employer-did.md:429); spec/02-identity.md:350, :352
- Evidence: Profile: "a `body` that is the spec §2.5.4 Step 3 request without `idpToken`", "carries the step-up token in the `Authorization` header instead of the body's `idpToken` member", "Token is a valid Entra access token for the sidecar's audience". Spec: "`idpToken` is the OIDC ID token in compact serialization" and "because it covers `idpToken` it binds the key to that token."
- Problem: A non-normative profile changes a spec wire format, swaps an ID token for an access token, and drops the device-key signature over the token. A spec-conformant client's request fails at this sidecar.
- Fix: See options.
- Needs decision: yes. (a) Keep `idpToken` in the signed body and put the step-up token there. (b) Amend §2.5.4 to allow a bearer access token and define what replaces the binding. Recommendation: (a). Plain language: the profile changes a signed request format that the spec defines. Keeping the spec format means one client works with every employer's provisioning service.

### CON4-13: radio-mesh public broadcast bridging cannot meet the §9.3 disclosure gate
- Severity: P2
- Location: profiles/radio-mesh-gateway.md:29-30, :105-107; spec/09-interop.md:68; spec/05-messaging.md:182
- Evidence: Profile: the gateway "is an MLS member of each bridged channel, admitted by a normal Add Commit". §8 of the profile maps BROADCAST to "an Agora `broadcast` channel with `keyAccess: public`", with the gateway as poster. Spec §9.3: "MUST send the `gateway-added` `SystemEvent` in the epoch that Add creates. A gateway MUST NOT carry messages in either direction until ... it has received that `SystemEvent`". Spec 05:182: "A broadcast channel has no MLS group."
- Problem: A broadcast channel has no Add, no epoch and no `SystemEvent`, so the gateway can never pass the send gate. §9 has no broadcast case.
- Fix: See options.
- Needs decision: yes. (a) Add a broadcast case to §9.3: the `GatewayDescriptor` plus the gateway DID in `broadcasters` is the disclosure, with no `SystemEvent` gate. (b) Drop public broadcast from the profile. Recommendation: (a). Plain language: the spec's gateway rule assumes an MLS group, which broadcast channels do not have. A broadcast case lets the public listing serve as the disclosure.

### CON4-14: DM handover default mover and 24 h fallback ignore two exclusions
- Severity: P3
- Location: spec/04-access-control.md:243; spec/99-appendices.md:100; against spec/04-access-control.md:167, :200, :241; spec/07-compliance.md:242
- Evidence:
  - 04:243: "the client of the remaining member with the lowest leaf index, other than a DID listed in `agora_compliance` (§7.8.2), moves the group by default. If no Commit that changes `host` has arrived 24 hours after the last host's user ceased to be a member, any remaining member's client moves the group." Appendix C:100 says the same.
  - 04:241: "Any member other than a compliance logger or recorder MAY move the group". 07:242: a listed DID "never moves the group".
  - 04:167: "A client that holds the group in the message request state (§4.6.3) neither rotates the key nor moves the group." 04:200 excludes such clients from the rotation default.
- Problem: The 24 h fallback omits the logger exclusion. The default mover omits the message-request exclusion, so a default mover in the request state does nothing for 24 h, and if every remaining member is in that state, nobody moves the group.
- Fix: At 04:243 add "and not holding the group in the message request state" to the default mover, and "other than a DID listed in `agora_compliance`" to the fallback. Make the same change at Appendix C:100.
- Needs decision: no

### CON4-15: Restatements of the handover trigger and of the key record disagree with §4.6
- Severity: P3
- Location: ARCHITECTURE.md:270-271; spec/12-security.md:258; spec/03-spaces.md:299, :315
- Evidence:
  - ARCHITECTURE:270: "When that host's user is no longer a member, a remaining member's client moves the role". 12:258: "When its user leaves the group or is offboarded (§2.5.6), the remaining members' clients move the `agora_admission` extension". Against 04:243: "When no host's user remains a member" and 04:167: "A group can have more than one host's user."
  - 03:299: `keyEpoch` "increases by one on every rotation", while 04:196 says "`key_epoch` need not increase".
  - 03:315: "Clients MUST verify the signature, MUST reject a record whose `channelID` is not a channel of the Space". A DM key has "no `sig`" and carries `mlsGroupID` in place of `channelID` (04:175).
- Problem: ARCHITECTURE and §12 describe the wrong trigger. 03:315, read literally, rejects every DM key.
- Fix: ARCHITECTURE:270 and 12:258: "when no host's user remains a member (§4.6.4)". 03:299: "for a Space channel". 03:315: scope the checks to keys served by a Space endpoint.
- Needs decision: no

### CON4-16: "MUST NOT commit an `AgoraAdmission`" reads as blocking the logger GroupContextExtensions
- Severity: P3
- Location: spec/04-access-control.md:196; spec/07-compliance.md:214
- Evidence: 04:196: "A client MUST NOT commit an `AgoraAdmission` other than one carrying a key that its own identity host issued to its own user". 07:214: the regulated member's client commits "a GroupContextExtensions proposal ... that adds a `logger` entry", which must carry `agora_admission` because the proposal replaces the whole list.
- Problem: Read literally, a regulated member who is not a host's user cannot add the logger. The next sentence shows the intended meaning, but the text says otherwise.
- Fix: "A client MUST NOT commit a change to `agora_admission` other than to one carrying a key that its own identity host issued to its own user".
- Needs decision: no

### CON4-17: §10.3.5 says relay changes never touch MLS state, but a DM group's relays are in its GroupContext
- Severity: P3
- Location: spec/10-relays.md:555; spec/04-access-control.md:194
- Evidence: 10:555: "Because members' MLS state, Space state and admission keys do not change, a CO adds, removes or replaces a Relay without touching Space identity or membership". 04:194: "`key_epoch`, `seed` and `relays` are the `keyEpoch`, `seed` and `relays` of a `ChannelAdmissionKey` that `host` issued".
- Problem: A DM host cannot change the relay list of a key already committed, and it cannot prompt a rotation, so §10.3.5 does not apply to DM groups or self-groups.
- Fix: Add to 10:555: for a DM group or self-group, a host's relay change takes effect only with the next key the host issues.
- Needs decision: no

### CON4-18: §2.5.6 is cited for a deregistration rule it does not contain
- Severity: P3
- Location: spec/04-access-control.md:175, :247; spec/02-identity.md:447-456
- Evidence: 04:175: "the host keeps an earlier key registered until its issuee DELETEs it or the host deregisters it under §2.5.6". 04:247: "the key stays registered until the host deregisters it under §2.5.6". §2.5.6 lists offboarding steps and does not mention admission keys. The 30-day rule is stated only at 04:175.
- Problem: The reference points to the wrong place. §2.5.6 covers only employer-provisioned DIDs, so for an individual's host the key has no bound, and the text does not say so.
- Fix: "under the 30-day offboarding rule above (§2.5.6)". State that a host with no offboarding has no bound.
- Needs decision: no

### CON4-19: `replaces` is mandatory for rotated keys, but a DM host cannot know which key a new key replaces
- Severity: P3
- Location: spec/10-relays.md:850; spec/04-access-control.md:175
- Evidence: 10:850: the registration service "MUST set it in the first registration of each rotated key with each IO, and MUST omit it for a new channel's or DM group's first key." 04:175: the host keeps "only the last `keyEpoch` it issued" and no member list.
- Problem: A DM host's earlier keys may have lost the race or been deleted, and the group may have moved between hosts. Hosts will diverge on what `replaces` names.
- Fix: See options.
- Needs decision: yes. (a) Name the last issued key if it is still registered. (b) Always omit `replaces` for DM keys. Recommendation: (b): DM groups have no sequencer (05:34), so no commit stream needs closing, and omitting it avoids linking tokens at the IO. Plain language: the rule assumes the issuer knows the current key, which a DM host does not. Dropping the field for DMs removes the guess.

### CON4-20: Appendix C rows disagree with their sections
- Severity: P3
- Location: spec/99-appendices.md:49, :55, :73, :83, :90, :113
- Evidence:
  - :90 grace row cites only §10.5.3 ("RECOMMENDED"). The DM rule at 04:200 is binding: "DELETEs the replaced key, no sooner than 300 seconds after both have happened".
  - :49 "Members of an `interactive` channel group | 200 | Fixed", and 03:24 lists "DMs" as an `interactive` use. :113: "A DM group is bounded only by the 4096-leaf limit". The 200 cap has no committer MUST or member-reject rule.
  - :55 "KeyPackage `lifetime` | 90 days maximum | MUST". The validation list at 05:127-133 checks only "within its `leaf_node.lifetime`", so a 365-day KeyPackage passes.
  - :83 "Directory refresh | 1 h | Default | §10.3.4". §10.3.4 defines only a per-document `ttl` (example 3600) and no default.
  - :73 "Ring duration | 120 s after receipt | MUST NOT exceed". This MUST constrains how long a device rings, which is notification UX, against the binding UX-MUST decision.
- Problem: Implementers who read the table get a different rule than those who read the section.
- Fix: :90 add a DM row citing §4.6. Remove "DMs" from 03:24, and either add committer and member rules for 200 or mark the row descriptive. Add "spans at most 90 days" to the 05:127 list. :83 "per document `ttl`". :73 recast as a validity rule on `ringUntil` (a ring older than 120 s is expired) and leave device behavior as SHOULD.
- Needs decision: no

### CON4-21: Appendix C omits limits that sections state
- Severity: P3
- Location: spec/99-appendices.md:44 ("collects the protocol's numeric limits in one place"); spec/04-access-control.md:18-19; spec/03-spaces.md:181; spec/05-messaging.md:118; spec/14-jmap.md:214; spec/10-relays.md:227, :242, :271, :465, :495, :532
- Evidence: missing rows include: guardian-transfer `ts` 300 s ("MUST NOT accept a proposal whose `ts` is more than 300 seconds from its clock") and `delaySeconds` default 259200; KeyPackage upload `ts` 300 s ("The host MUST reject a request whose `ts` differs from its clock by more than 300 seconds"); sequencer `expires` 600 s ("MUST NOT have passed or be more than 600 seconds ahead"; App C:87 does not cite §14.4.3); BEP-5 re-announce 30 min; Pkarr re-publish 2 h; peer manifest cache 1 h and 5 s retry; 24 h block after 3 incidents in 7 days; `knownPeers` 7 days; directory backoff 30 s to 1 h, with a 7-day unreachable flag.
- Fix: Add the rows, or narrow the :44 claim.
- Needs decision: no

### CON4-22: Appendix D omissions and an undefined name
- Severity: P3
- Location: spec/99-appendices.md:123, :141-142, :159-168, :182
- Evidence:
  - :182 lists "IPNS name `/ipns/agora.protocol/relays/v1` | §1.1, §10.3.1, §10.2.5". 10:265 has only "an IPNS name configured by the operator (e.g. `/ipns/bootstrap.example.com`)", and no other text uses `agora.protocol`.
  - 02:316 defines the "`AgoraProvisioning` service entry", which is not in the DID service types table at :159-168.
  - :141-142 list only `stream-closed` and `token-rotated`. §10.5.3 and §11.4 define many more codes.
  - :123: "(0xF0A3, GroupContext of self-groups, §2.6) `agora_compliance`" is missing a comma.
  - profiles/compliance-chain-witness.md:32 and :90 and guides/relay-operator.md:2373 allocate `urn:agora:practice:*` names, and relay-operator.md:2384 uses `/.well-known/agora-relay-tombstone`. Appendix D:119 says "this specification is the only allocation authority".
- Fix: Delete the IPNS name. Add `AgoraProvisioning`. Point the error-code rows at §10.5.3 and §11.4. Add the comma. Either register `urn:agora:practice:` for non-normative names or rename those types, and have the guide use an operator-chosen URL.
- Needs decision: no

### CON4-23: References that point to the wrong section
- Severity: P3
- Location and fix:
  - ARCHITECTURE.md:250: "*Mechanism (protocol spec §5.2.2, §10.5.1)*". The bullets describe `AdmissionKeyRegistration`, which is §10.5.3. Fix: "§5.2.2, §10.5.3".
  - guides/relay-operator.md:235: "telling connections apart by ALPN ... per spec §10.1". The ALPN rule is in the §10.2 introduction (10:39). Fix: "spec §10.2".
  - profiles/o365-employer-did.md:192: "(spec §2.1, §6.6)" and :613 "(spec §4.6, §6.7)". Spec §6.6 is SFU Integration and §6.7 is Simulcast, while the profile's own §6.6 and §6.7 are meant. Fix: "§6.6 below", "§6.7 below".
  - profiles/purview-bridge.md:135: "at onboarding (spec §2.5.3) the DID provisioning service validates the IdP token". Token validation is §2.5.4 Step 4. Fix: cite §2.5.4.
  - profiles/corundum.md:51-52: "`serviceEndpoint` is `ipfs://<RootManifest CID>`" and "The pointer goes in the Pkarr record (spec §2.1, §10.3.4.6)". The spec record `_corundum._agora` carries only "`url`, `key`" (10:518), and the profile's own :149 uses endpoint plus posting key. Fix: rewrite :51-52, :67 and :124 to the endpoint-plus-key model.
  - spec/03-spaces.md:225: "| `seq` | ... | §3.6 |". The fork rule that uses `seq` is §5.1.1 (05:38). Fix: "§3.6, §5.1.1".
  - spec/11-transport.md:397: "blobs are encrypted (§3.4)". Member uploads use the §14.3.4 format, as 14:311 cites "(§3.4, §14.3.4)". Fix: the same pair.
- Needs decision: no

### CON4-24: Guide and profile restatements that contradict the spec
- Severity: P3
- Location, evidence and fix:
  - guides/relay-operator.md:2456 (also :2429): the relay cannot "Map a Space or channel to its routing tokens ... even for a public Space". Spec 10:569 and 03:315: the CO publishes the token of a `keyAccess: public` broadcast channel, and "anyone, including an IO, can map that channel's token". Fix: add that exception.
  - guides/relay-operator.md:1248: "it cannot count Commits, Proposals or application messages separately". Spec 12:26: "It recognizes envelopes that carry a stamped Commit by their `commitStamp`". Fix: add the sequenced-channel exception.
  - guides/regulators.md:203: DM compliance covers "bridged conversations where the counterparty uses Slack, Teams, or a MIMI-compatible platform". Gateways are disclosed in Space state (09:37), which DMs lack, and native MIMI is not specified (09:8). Fix: limit the claim to bridged Space channels and drop MIMI.
  - profiles/gateways.md:108: "the hub and the channel sequencer are the same CO component". 14:146: the sequencer "is an IO", and ARCHITECTURE:61 says "| Sequencer | IO |". Fix: say that the CO-side MIMI hub orders the interop channel in place of an Agora sequencer.
  - guides/counsel.md:183: "receive a mandatory disclosure at first join", and :83: "a visible system message that participants cannot suppress". Spec 07:163: "MUST present `retentionNotice` to its user before the user first sends". 07:285: it "SHOULD show it as a system notification". Fix: "before the user first sends", and "normally as a system notification".
  - profiles/o365-employer-did.md:547: "space membership is retained" after device-key revocation. The profile's own :543 and spec 02:445 have every leaf removed. Fix: say the user must be re-added to groups after re-enrollment.
  - profiles/o365-employer-did.md:589: "The remaining checks of spec §2.5.4 Step 4 (account active, device limit)" omits 02:360 "rejects a request that registers a key already present in any DID it serves". Fix: add it.
  - profiles/purview-bridge.md:408: `removalAttempts` "records those" recorder removals. Spec 07:334: "for any Remove commits targeting the logger". Fix: say that no field records recorder removals.
  - profiles/radio-mesh-gateway.md:125 and profiles/parlance.md:111: "per §13.1 a breaking change defines a new name" applies a rule §13.1 states only for `urn:agora:type:`. Fix: cite it as following the Agora convention.
- Needs decision: no

### CON4-25: Gateway profiles never state `unencryptedRemote`
- Severity: P3
- Location: profiles/parlance.md:69; profiles/radio-mesh-gateway.md:162; spec/09-interop.md:58, :85
- Evidence: 09:58: "`true` when traffic on the other network is not end-to-end encrypted". parlance:69: "readings are plaintext on the source site's own fabric ... the badge flags no loss of confidentiality". radio-mesh:162: LICHEN confidentiality comes "only from OSCORE ... or an optional Group OSCORE key", and the profile says only "or at least state it in the channel description".
- Problem: By the §9.2 definition both cases are `true`, but Parlance's wording suggests `false`, so deployers will set different values.
- Fix: Each profile states `unencryptedRemote: true` for these cases.
- Needs decision: no
