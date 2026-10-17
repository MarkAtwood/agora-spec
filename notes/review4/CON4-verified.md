# Review 4: CON4 verified

Checked against the working tree at 4b76c3d (spec/, ARCHITECTURE.md, guides/ and profiles/ unmodified), against `bd memories agora` (notably agora-commit-authz, agora-commit-winner, agora-sequencer-replacement, agora-channelid, agora-dm-withdraw-limit, agora-dm-key-in-group, agora-dm-key-cap, agora-ux-musts), against ARCHITECTURE §8 and §9, and against the accepted limits in spec §12.5. Overlaps are reconciled into single fixes: CON4-1 with agora-commit-authz, CON4-2 with CRY4-2, CON4-3 with CRY4-5, CON4-4 with CRY4-6, CON4-5 with CRY4-1, CON4-6 with IMP4-2 (verified), CON4-17 with IMP4-1, and CON4-19 with IMP4-3.

Totals: 21 CONFIRMED (CON4-17 and CON4-19 are subsumed by IMP4-1 and IMP4-3), 4 PARTIAL (CON4-9, CON4-14, CON4-20, CON4-25), 0 REJECTED. Severity changes: CON4-2 P1 to P2, CON4-7 P2 to P3, CON4-9 P2 to P3. Needs decision: CON4-12, CON4-13. CON4-17 follows the IMP4-1 decision.

### CON4-1: Whether a Commit "counts" depends on clock and DID-document state, contradicting "no clock is consulted"
- Verdict: CONFIRMED. All quotes are verbatim (05:29, 05:31 "no clock is consulted", 05:79, 05:127, 05:130, 12:187, 12:194). "Counts" at 05:29 includes "the checks of §5.2.1", and those cover the 05:127 rule that every processing member validates lifetime (05:130) and the 05:79 rule that `signature_key` is in "that DID's current DID document". Both answers change over time, so a live member and a catch-up member can disagree on the lowest counting Commit. §12 (12:194) names only the Welcome recipient as the clock holder, which contradicts 05:127.
  On the decision interaction: agora-commit-authz says the winner is "chosen by MLS validity only", and agora-commit-winner says "no clocks". RFC 9420 does not make either check part of MLS validity. RFC 9420 §7.3 makes the lifetime check mandatory only for the sender of a LeafNode, and only RECOMMENDED for a receiver, because the LeafNode "might have expired in the time between when the message was sent and when it was received". Credential validity (RFC 9420 §5.3.1) is delegated to the Authentication Service, which Agora defines as DID verification (05:79). Agora can therefore place its AS check after winner selection without departing from MLS validity. 02:445 already handles a leaf whose key is no longer in the DID document: "other group members MUST issue `Remove` commits when they detect the key is revoked". The reviewer's option (b) cannot work in DM groups, which have no stamp, and the routing `ts` is set by "an unidentified holder of the admission key" (12:187).
- Severity: P1, keep. It forks groups on normal timing (offline phones, routine device revocation), in every group type.
- Fix:
  - spec/05-messaging.md:29, after "...passes RFC 9420 §12.4.2 validation and the checks of §5.2.1.", add: "Counting depends only on the Commit's bytes and the group's state. It consults no clock and no DID resolution: the lifetime check and the DID-document check of §5.2.1.1 are not part of it, and a member applies them only after the winner is chosen, as §5.2.1 describes."
  - spec/05-messaging.md:79, after "...which is the device key of §2.2.", add: "A committer checks this before it adds a KeyPackage or sends an UpdatePath. A member processing a Commit checks it only after applying the winning Commit (§5.1.1): a leaf whose `signature_key` is not listed is a revoked device key, and members Remove it as §2.5.5 requires, and the Commit stays applied." Leave the device-binding check (did:key, 0xF0A1) and its "makes the carrying KeyPackage, Commit or Welcome invalid" sentence as they are, because that check uses only the bytes.
  - spec/05-messaging.md:127, change "and every member processing the Commit MUST validate the KeyPackages it adds:" to "and every member processing the Commit MUST validate the KeyPackages it adds, except that only the committer checks the first two items against the DID document and its clock (RFC 9420 §7.3). A processing member checks the DID-document binding after applying the Commit (§5.2.1), and checks the lifetime only to confirm that it spans at most 90 days (§5.2.1):".
  - spec/05-messaging.md:135, change "failing these checks" to "failing the checks it applies under this list".
  - spec/12-security.md:194, change the row to "| KeyPackage `lifetime.not_after` | Committer adding the KeyPackage; Welcome recipient | §5.2.1.1 |". A joiner's own rejection of a Welcome decides only whether it joins, so it does not affect the winner.
  - This fix and CON4-20 item :55 (spans at most 90 days) edit the same list. Apply them together.
- Needs decision: no. The two options were (a) move both checks after winner selection and (b) judge them as of the stamp. Option (b) is not possible without a stamp, and DM groups have none, so only (a) is consistent with agora-commit-winner. Option (a) also reuses the existing revocation rule (02:445).

### CON4-2: Sequencer replacement leaves a window in which the old sequencer stamps above the closing head, with no recovery
- Verdict: CONFIRMED. The quotes are verbatim. The "05:25" quote is at 05:27. 14:257 orders the steps as "replaces a faulty sequencer by a Space state change, then rotates the admission keys". 05:27 stops stamping on the old stream only "once the CO registers a rotated key whose registration names the old token in `replaces`". The only failure path in 05:31 covers a gap that cannot be filled. Nothing covers a member that has already applied a Commit above the head. The finding duplicates CRY4-2 gaps (1) and (2). CRY4-2 also raises gap (3): a member with stale state rejects new-DID stamps and must refetch. A single fix should cover all three.
- Severity: lower P1 to P2, matching CRY4-2. The fork needs a Commit stamped inside the replacement window and a member that applies it before learning the new state. Only those members fork. With the fix below, an honest old sequencer stops stamping before the heads are read, so a planned switch cannot fork.
- Fix (the reconciled CON4-2 and CRY4-2 fix; apply once):
  - spec/14-jmap.md:257, Replacement, insert before "Commit streams close by the same rule:": "Before it chooses the heads, the CO deregisters the channels' admission keys at the old sequencer (§10.5.3), or ends its agreement with it, so that it stamps nothing more, and then reads each commit stream to its end. A misbehaving old sequencer that stamps after this does so above the head, and members reject those stamps."
  - spec/05-messaging.md:29, after the stamp-verification sentence (ending "...the logged `op` for a Commit taken from the log)."), add: "A member that receives a Commit whose stamp is signed by a DID other than the `sequencer` it holds, or an unstamped Commit in a channel whose Space state it holds names a sequencer, fetches the current Space state head (§3.4) before it rejects the Commit."
  - spec/05-messaging.md:31, after the sentence ending "...as for Commits past relay retention (§5.2.5).", add: "A member that finds it has applied a Commit that a later Space state's `closingHeads`, or the fork rule of §14.4.5, rejects does the same."
- Needs decision: no

### CON4-3: The Space's own MLS group has no admission key, so it cannot be published to or sequenced
- Verdict: CONFIRMED. The quotes are verbatim (03:175, 03:193, 03:195, 03:280, 04:295, 05:27, 05:289). No text in spec/ issues or serves an admission key for the Space's own group. 05:289 says only "For each channel". 03:355 creates the group, and 03:323 and 04:295 send traffic in it. This is the same finding as CRY4-5. The reviewer's option question is already settled by the spec: 03:193 makes the sequencer order Commits "in the Space's groups", and the Space's own group is one of them. Only 05:27 ("a channel of a Space") is narrower. One more inconsistency on the same line: 03:193 calls the no-sequencer rule "the lowest-hash rule", but 05:34 picks the lowest envelope `id`.
- Severity: P2, keep.
- Fix (compatible with CRY4-5; this version uses a reserved value instead of a new field, so §3.6 genesis needs no change):
  - spec/03-spaces.md:175, append: "The Space's own group is admitted and ordered as a channel whose `channelID` is 16 zero bytes, which no channel entry uses. Every rule of §3.4, §5.1.1, §5.2.2 and §14.4.5 that names a channel or `channelID` applies to it, and the Space endpoint serves its admission key to every member of the Space."
  - spec/03-spaces.md:173, after "Every channel entry MUST carry one.", add: "It is never 16 zero bytes, which names the Space's own group (§3.3)."
  - spec/03-spaces.md:315, change "MUST reject a record whose `channelID` is not a channel of the Space" to "MUST reject a record whose `channelID` is neither a channel of the Space nor the Space's own group (§3.3)". This also interacts with CON4-15, which scopes the same checks to Space-endpoint keys.
  - spec/03-spaces.md:193, change "competing Commits are resolved by the lowest-hash rule (§5.1.1)" to "competing Commits are resolved by the no-sequencer rule of §5.1.1".
  - spec/03-spaces.md:195, change "per channel that has an MLS group" to "per channel that has an MLS group, including the Space's own group (§3.3)".
  - If the editor prefers CRY4-5's random `spaceChannelID` field, the same rules apply. Choose one of the two, not both.
- Needs decision: no. 03:193 already gives the answer, sequenced, which is the reviewer's option (a).

### CON4-4: Shared channels do not say whose sequencer orders their Commits
- Verdict: CONFIRMED. The quotes are verbatim (05:29, 08:95, 08:141). 08:97 requires the guest view to carry only "the shared channel's entry and every admin entry whose scope covers it". It does not require `sequencer` or `closingHeads`. This duplicates CRY4-6.
- Severity: P2, keep.
- Fix (the reconciled CON4-4 and CRY4-6 fix; apply once):
  - spec/08-cross-space.md:97, change "that view MUST include the shared channel's entry and every admin entry whose scope covers it" to "that view MUST include the shared channel's entry, every admin entry whose scope covers it, and the home Space's `sequencer` and any `closingHeads`".
  - spec/05-messaging.md:27, after the first sentence of the "Space with a sequencer" bullet, add: "For a shared channel (§8), the home Space's state decides, as served to guests in the view of §8.6. A guest refetches that view wherever this section tells a member to fetch the current Space state head."
- Needs decision: no

### CON4-5: The no-sequencer rule does not exclude invalid Commits from "lowest envelope id"
- Verdict: CONFIRMED. 05:34 quoted verbatim. "Counts" is defined only inside the sequencer bullet (05:29), and it is phrased for "A stamped Commit". It is also related to CON4-1: once counting is free of clock and DID checks, applying it here makes the DM choice deterministic among the Commits a member considers.
- Severity: P2, keep.
- Fix (compatible with CRY4-1 under any of its options):
  - spec/05-messaging.md:29, change "A stamped Commit **counts** if" to "A Commit **counts** if". The definition stays in place, and the no-sequencer rule refers to it.
  - spec/05-messaging.md:34, change "It then applies the Commit whose envelope `id` (§5.2.2) is lowest" to "It then applies, among those Commits that count (as defined above), the one whose envelope `id` (§5.2.2) is lowest". If CRY4-1 (a) is adopted, its rule for history and later envelopes selects among counting Commits in the same way.
- Needs decision: no. The window and catch-up question belongs to CRY4-1.

### CON4-6: DM recovery fires only on `unknown-token`, but a withdrawn key returns `token-withdrawn`
- Verdict: CONFIRMED. The quotes are verbatim (04:196, 11:196, 12:71). This is the same defect as IMP4-2, which IMP4-verified CONFIRMED with a fix that widens the trigger, adds an exit to the 11:196 loop, and extends the 12:71 limit.
- Severity: P2, keep.
- Fix: apply the IMP4-2 verified fix, which covers this finding completely. Its parts are: 04:196 "each answering `unknown-token` or `token-withdrawn` (§11.4)"; the 04:200 Ack definition; the 11:196 sentence "If that key is the refused one at every listed Relay, the client applies the recovery of §4.6 instead of retrying."; and the §12.5 extension of the "Removed host's user withdraws the DM key" bullet ("The same holds when every listed Relay withdraws the current key, for example by token suspension (§10.4.7) or the end of the host's agreements, and no earlier key of the group is still admitted."). Do not add a separate CON4-6 sentence.
- Needs decision: no. The reviewer's option (a) is what the IMP4-2 fix does. The stranding case extends the limit Mark already accepted in agora-dm-withdraw-limit ("members start a new group"). Option (b), re-creating the group from members' state, would be a new mechanism, and nothing requires it.

### CON4-7: Logger removal ban is limited to "the retention period" in §7.8.3 and the guides, but is permanent in §4.6
- Verdict: CONFIRMED. 07:258 reads "for the duration of the regulatory retention period" verbatim. 04:202 ("other than a compliance logger or recorder") and 07:242 ("members do not remove it (§4.6, §7.8.3)") have no time bound, and 07:263 requires the re-add unconditionally. counsel.md:101 and regulators.md:188 repeat the bounded form. No text defines when a retention period starts or ends for group membership.
- Severity: P3 (from P2). The operative rules in §4.6, §7.8.2 and the §7.8.3 client MUSTs are unconditional, and enforcement is the regulated member's own client, which re-adds regardless. The phrase misleads readers but does not change what a conformant client does.
- Fix:
  - spec/07-compliance.md:258: delete " for the duration of the regulatory retention period", so the sentence ends "MAY issue an MLS Remove commit for the logger DID."
  - guides/counsel.md:101: change "may not be removed for the duration of the retention period (spec §7.8.3)" to "may not be removed (spec §7.8.3)".
  - guides/regulators.md:188: change "No member may remove the logger during the retention period:" to "No member may remove the logger:".
- Needs decision: no.

### CON4-8: §7.8.5 repair removes the logger, which §7.8.3 forbids, and a leaf-less entry has no repair
- Verdict: CONFIRMED. 07:301 "removes every leaf of that DID and re-adds it with the entry in one Commit, as §7.8.2 allows" conflicts with 07:262 "Refuse to commit an MLS Remove proposal targeting the Space's `loggerDID`". 07:240 allows an entry "in the same Commit as its Add ... including a re-add" and removal of the entry by "The Commit that removes every leaf", but never says what a single Commit doing both yields, so "as §7.8.2 allows" is at best implicit. The reverse case holds: a Remove of the logger's leaves that leaves the entry is a policy violation under 07:240 but stands under agora-commit-authz (winner by MLS validity only), and the 07:263 re-add "which also restores its `agora_compliance` entry" then adds a second entry, breaking "No two entries have the same `did`". 07:301 also covers only "both are absent" and "leaf exists without an entry", not an entry without a leaf.
- Severity: P2, keep. Two client MUSTs contradict, and the second case produces a malformed extension.
- Fix:
  - spec/07-compliance.md:262: change to "Refuse to commit an MLS Remove proposal targeting the Space's `loggerDID`, except in a Commit that also adds a leaf of that DID and keeps its `agora_compliance` entry (§7.8.5)."
  - spec/07-compliance.md:240, after "including a re-add (§7.8.3);", insert: "a Commit that removes every leaf of a listed DID and adds a leaf of that DID keeps that DID's one entry, and a re-add of a DID whose entry is still present keeps that entry unchanged and adds none;"
  - spec/07-compliance.md:301, change "as §7.8.2 allows." to "as §7.8.2 allows. If the entry exists without a leaf, it adds the logger by the §7.8.2 procedure and keeps the entry."
- Needs decision: no.

### CON4-9: parlance profile makes an exception to a spec MUST
- Verdict: PARTIAL. The contradiction is real: profiles/parlance.md:96 "The one exception is a two-member group of one operator and the Arbiter front end, where membership identifies the sender" against 06:480 "A payload whose receiver acts on the identity of its sender MUST be sent as an MLS application message instead". The profile header says its BCP 14 words are not Agora requirements, so it cannot relax a spec MUST. The reviewer's reasoning is wrong in one part: "a removed member can still hold the channel key" does not hold, because data keys are exported per epoch and "rotate with MLS epochs" (06:478), so in a two-member group only the other current member can produce a valid message. The exception is technically sound but still contradicts the spec's unconditional rule.
- Severity: P3 (from P2). Non-normative profile; the case it allows is not exploitable as described.
- Fix: profiles/parlance.md:96, delete the sentence "The one exception is a two-member group of one operator and the Arbiter front end, where membership identifies the sender."
- Needs decision: no.

### CON4-10: discord-onboarding Add flow ignores the canonical-Commit rules and adds one KeyPackage
- Verdict: CONFIRMED. profiles/discord-onboarding.md:418 "Fetches one KeyPackage", :427 "Publishes the commit to the channel like any member's handshake message", :428 "POSTs the Welcome" with no wait. Against 05:25 (submit to the sequencer before publishing), 05:36 "MUST NOT deliver the Welcome for an Add in its Commit until that Commit has won", and 05:107 "A committer adding the user adds every returned KeyPackage". The profile header says the spec governs on conflict, so this is an editing error, not a competing rule.
- Severity: P2, keep. An implementer following the profile's step list delivers Welcomes to losing branches.
- Fix: profiles/discord-onboarding.md §8.2:
  - Step 1: change "Fetches one KeyPackage from the user's `KeyPackageEndpoint`; the fetch consumes it" to "Fetches the user's KeyPackages from the user's `KeyPackageEndpoint`, one per device; the fetch consumes them". Change "It validates the KeyPackage" to "It validates each KeyPackage".
  - Step 2: change "Add { KeyPackage: <fetched from the user's KeyPackageEndpoint> }" to "Add { KeyPackage: <each KeyPackage fetched from the user's KeyPackageEndpoint> }" (one Add per KeyPackage).
  - Step 3: insert at the start "Follows the canonical-Commit rule of spec §5.1.1, including submission to the Space's sequencer when it names one, and then".
  - Step 4: insert at the start "Once the Commit has won (spec §5.1.1),".
- Needs decision: no.

### CON4-11: discord-onboarding passkey PRF wrapping is incompatible with spec §12.6
- Verdict: CONFIRMED. `prfSalt` appears only at profiles/discord-onboarding.md:162 and :177 and is never defined. 12:93 fixes the PRF input to SHA-256 of `agora/v1/webauthn-prf`, derives the wrapping key with HKDF info `agora/v1/webauthn-prf-wrap`, and stores "only the wrapped key and `iv`". :177 says "a key derived from the PRF output" without the HKDF parameters and omits `iv`, while also claiming "In later sessions the Agora web client unwraps the key", which needs the §12.6 parameters.
- Severity: P2, keep. The enrollment app and the Agora web client cannot interoperate on the stored key.
- Fix:
  - profiles/discord-onboarding.md:162: change `first: prfSalt` to `first: sha256("agora/v1/webauthn-prf")` and add a comment line above the call: "// PRF input fixed by spec §12.6".
  - profiles/discord-onboarding.md:177: change "wraps the device key under a key derived from the PRF output, stores only the wrapped key with the credential ID and `prfSalt`," to "wraps the device key exactly as spec §12.6 step 1 specifies (HKDF-SHA256 wrapping key, AES-GCM `wrapKey` with a fresh 12-byte `iv`), stores only the wrapped key, `iv` and the credential ID,".
- Needs decision: no.

### CON4-12: o365 profile moves `idpToken` out of the signed registration body
- Verdict: CONFIRMED. profiles/o365-employer-did.md:563 "the spec §2.5.4 Step 3 request without `idpToken`", :578 "carries the step-up token in the `Authorization` header instead", :583 "valid Entra access token for the sidecar's audience". Spec 02:350 defines `idpToken` as "the OIDC ID token ... or ... SAML assertion", 02:352 says the device-key signature "covers `idpToken`", and Step 3 (02:335 to 02:346) has no header alternative. profiles/gsuite-employer-did.md:429 inherits the O365 checks. One refinement: option (a) as written still conflicts, because the Entra step-up token is an access token (the `acrs` claim the profile relies on is an access-token claim), and 02:350 admits only an ID token or SAML assertion. So (a) needs one phrase in §2.5.4.
- Severity: P2, keep. A generic conformant client fails at this sidecar, and the signature no longer binds the key to the token.
- Fix (for option a, recommended):
  - spec/02-identity.md:350: change "`idpToken` is the OIDC ID token in compact serialization, or the unpadded base64url of the SAML assertion XML." to "`idpToken` is the OIDC ID token in compact serialization, an access token the IdP issued for the provisioning service's audience in compact serialization, or the unpadded base64url of the SAML assertion XML; the provisioning service states which it accepts."
  - profiles/o365-employer-did.md:557: delete the line "Authorization: Bearer <step-up-token>".
  - profiles/o365-employer-did.md:563: change "a `body` that is the spec §2.5.4 Step 3 request without `idpToken`:" to "a `body` that is the spec §2.5.4 Step 3 request, with the step-up access token as `idpToken`:", and add `"idpToken": "<step-up access token>"` as the last member of the JSON example.
  - profiles/o365-employer-did.md:578: replace the paragraph with "The step-up access token travels in `idpToken`, so the device-key signature covers it (spec §2.5.4 Step 3)."
  - profiles/o365-employer-did.md:583: change "Token is" to "`idpToken` is".
- Needs decision: yes.
  - (a) Keep `idpToken` in the signed body, let it carry an IdP access token for the provisioning audience (one phrase in §2.5.4), and move the profile's step-up token into it. Recommended: one wire format, binding kept, and Entra's `acrs` check still works.
  - (b) Amend §2.5.4 to allow the token in an `Authorization` header and define a replacement binding (for example a hash of the token in the body). More spec text and a second wire format.
  - (c) Keep the profile as is and record it as a non-conformant deployment. Leaves generic clients unable to enroll.
  - In plain terms: the Microsoft profile sends the sign-in token in a different place than the spec says, so a standard Agora client cannot enroll there. Putting the token back in the signed request, and letting the spec accept the kind of token Microsoft issues for step-up, fixes both.

### CON4-13: radio-mesh public broadcast bridging cannot meet the §9.3 disclosure gate
- Verdict: CONFIRMED. profiles/radio-mesh-gateway.md:105 maps BROADCAST to "an Agora `broadcast` channel with `keyAccess: public`" with the gateway as poster via `broadcasterRoles`. 05:182 "A broadcast channel has no MLS group." §9.1 (09:14) defines a gateway as "any component that carries Agora traffic to or from another network" and requires it to join "each channel MLS group it serves ... through a normal MLS Add commit". §9.3 (09:68) gates sending on a `SystemEvent` "in the epoch that Add creates". No broadcast case exists in §9 or profiles/gateways.md. The profile's own disclosure bullet (:29) also lists the `SystemEvent`, which cannot exist for the broadcast channel.
- Severity: P2, keep. Spec gap: the §9 rules cannot be met for any broadcast gateway, not only this profile's.
- Fix (for option a, recommended):
  - spec/09-interop.md §9.3, after the Send-gate paragraph, add: "**Broadcast channels.** A gateway that posts to a `broadcast` channel (§5.2.1.4) joins no MLS group; it posts as a holder of a role in `broadcasterRoles`. Its disclosure is its `GatewayDescriptor` in the channel's entry and its DID in the channel's `broadcasters` list (§3.4). For a channel with `keyAccess` `public`, the non-member view carries that channel's `gateways` array. The gateway MUST NOT post until its `GatewayDescriptor` is in the channel's current Space state; the `SystemEvent` and Add-epoch rules above do not apply."
  - spec/09-interop.md §9.1 Identity and admission, after "exactly like any other member.", add: "On a broadcast channel it instead holds a role in `broadcasterRoles` (§9.3)."
  - profiles/radio-mesh-gateway.md:29: append "; on a public broadcast channel (§8) the disclosure is the `GatewayDescriptor` and the `broadcasters` list, with no `SystemEvent` (spec §9.3)".
- Needs decision: yes.
  - (a) Add a broadcast case to §9.3: descriptor plus `broadcasters` listing is the disclosure, no `SystemEvent`. Recommended: small text, uses records the CO already signs and publishes.
  - (b) Drop public broadcast from the radio-mesh profile and state in §9.1 that gateways serve only channels with an MLS group.
  - In plain terms: the spec's gateway disclosure rule assumes a group the gateway joins, and broadcast channels have no group. Option (a) treats the public, signed list of posters plus the gateway's description as the disclosure.

### CON4-14: DM handover default mover and 24 h fallback ignore two exclusions
- Verdict: PARTIAL. The message-request gap is real. 04:167 says "A client that holds the group in the message request state (§4.6.3) neither rotates the key nor moves the group", and the rotation default at 04:200 skips such clients ("the host's user with the lowest leaf index among those not holding the group in the message request state"), but the default mover at 04:243 ("the client of the remaining member with the lowest leaf index, other than a DID listed in `agora_compliance` (§7.8.2), moves the group by default") does not. When that member is in the request state it may not move, so the group waits the full 24 h. The logger half is not a gap: 04:241 ("Any member other than a compliance logger or recorder MAY move the group") and 07:242 ("it never moves the group (§4.6.4)") already bind every mover, including the fallback. The "nobody moves if every remaining member is in the request state" case is intended: 04:167 makes request-state clients passive until the user accepts, and accepting ends the state. The Appendix C row is :98 ("DM admission host handover fallback | any remaining member after 24 h"), not :100, which is the deregistration row.
- Severity: P3, keep. A 24 h delay, no fork or loss.
- Fix:
  - spec/04-access-control.md:243, change "other than a DID listed in `agora_compliance` (§7.8.2), moves the group by default" to "other than a DID listed in `agora_compliance` (§7.8.2) and among those not holding the group in the message request state (§4.6.3), moves the group by default". Change "any remaining member's client moves the group" to "any remaining member's client that may move it (above) moves the group".
  - spec/99-appendices.md:98, change "any remaining member after 24 h without a handover Commit" to "any remaining member that may move the group (§4.6.4) after 24 h without a handover Commit".
- Needs decision: no.

### CON4-15: Restatements of the handover trigger and of the key record disagree with §4.6
- Verdict: CONFIRMED. ARCHITECTURE.md:270 "When that host's user is no longer a member, a remaining member's client moves the role" and 12:258 "When its user leaves the group or is offboarded (§2.5.6), the remaining members' clients move the `agora_admission` extension" both trigger on one user, against 04:243 "When no host's user remains a member" and 04:167 "A group can have more than one host's user." 03:299 "`keyEpoch` ... increases by one on every rotation" holds for a DM host's issuance (04:175 "one more than the last it issued") but not for the committed sequence, which 04:196 says "need not increase", and a move to a new host restarts at 0 (agora-dm-host-keyepoch). 03:315 places "Clients MUST verify the signature, MUST reject a record whose `channelID` is not a channel of the Space" right after the DM clause that says the DM key has "no `sig`", and 04:175 says the DM key carries `mlsGroupID` "in place of `channelID`", so a literal reading rejects every DM key.
- Severity: P3, keep. Restatements; the normative §4.6 text is clear.
- Fix:
  - ARCHITECTURE.md:270, change "When that host's user is no longer a member, a remaining member's client moves the role" to "When no host's user remains a member, a remaining member's client moves the role".
  - spec/12-security.md:258, change "When its user leaves the group or is offboarded (§2.5.6)" to "When no host's user remains a member (§4.6.4)".
  - spec/03-spaces.md:299, change "increases by one on every rotation" to "increases by one on every rotation of a Space channel's key; for a DM group §4.6 governs".
  - spec/03-spaces.md:315, change "Clients MUST verify the signature, MUST reject a record whose `channelID` is not a channel of the Space" to "For a record served by a Space endpoint, clients MUST verify the signature, MUST reject a record whose `channelID` is not a channel of the Space".
- Needs decision: no.

### CON4-16: "MUST NOT commit an `AgoraAdmission`" reads as blocking the logger GroupContextExtensions
- Verdict: CONFIRMED. 04:196: "A client MUST NOT commit an `AgoraAdmission` other than one carrying a key that its own identity host issued to its own user". The same paragraph says a GroupContextExtensions proposal "replaces the whole extension list" and that one carrying `agora_admission` "byte-for-byte unchanged does not change it", so the unchanged copy is still an `AgoraAdmission` the client commits. That catches the 07:214 logger GCE by a regulated member who is not a host's user, and also a host's user copying a key that its host issued to another of its users. The following clause ("changes `agora_admission` only when ...") shows the intent.
- Severity: P3, keep.
- Fix: spec/04-access-control.md:196, change "A client MUST NOT commit an `AgoraAdmission` other than one carrying a key that its own identity host issued to its own user" to "A client MUST NOT commit a change to `agora_admission` other than to one carrying a key that its own identity host issued to its own user".
- Needs decision: no.

### CON4-17: §10.3.5 says relay changes never touch MLS state, but a DM group's relays are in its GroupContext
- Verdict: CONFIRMED, and subsumed by IMP4-1. 10:555 "Because members' MLS state, Space state and admission keys do not change, a CO adds, removes or replaces a Relay without touching Space identity or membership" is false for DM groups and self-groups, whose relays sit in `agora_admission` (04:194). The same paragraph's last sentence already admits DM clients refresh only when they "process a Commit that changes `agora_admission`", so the contradiction is inside one paragraph. IMP4-1 (verified P1, needs decision) covers the same text with a fuller fix.
- Severity: P3 as a consistency finding; the substance is IMP4-1 at P1.
- Fix: Apply whichever 10:555 text the IMP4-1 decision selects. If that decision is (b), its sentence ("For a DM group or a self-group the relay list is part of MLS state (§4.6) and changes at the next rotation, at most 7 days later; ...") fixes this finding. If IMP4-1 is resolved some other way, at minimum add after "(ARCHITECTURE S5).": "For a DM group or a self-group the relay list is part of MLS state (§4.6), so a host's relay change reaches the group only with the next key the host issues."
- Needs decision: no (decided under IMP4-1).

### CON4-18: §2.5.6 is cited for a deregistration rule it does not contain
- Verdict: CONFIRMED. 04:175 "until its issuee DELETEs it or the host deregisters it under §2.5.6" and 04:247 "the key stays registered until the host deregisters it under §2.5.6". §2.5.6 (02:447 to 02:456) lists six offboarding steps and never mentions admission keys; the 30-day rule appears only in 04:175 ("The host also deregisters every key it issued to a DID 30 days after that DID is offboarded (§2.5.6)") and Appendix C:100. §2.5.6 applies to employer-provisioned DIDs, so for an individual's host an unreturning issuee's key has no bound. That cost falls only on the host's relay agreements (04:247 "envelopes admitted under it reach no member"), so stating it is enough.
- Severity: P3, keep.
- Fix:
  - spec/04-access-control.md:175, change "or the host deregisters it under §2.5.6" to "or the host deregisters it 30 days after the issuee is offboarded (below)". After "30 days after that DID is offboarded (§2.5.6).", add: "A host that does not offboard DIDs has no such bound."
  - spec/04-access-control.md:247, change "until the host deregisters it under §2.5.6" to "until the host deregisters it 30 days after the issuee is offboarded (§4.6), which a host that does not offboard DIDs never does".
- Needs decision: no.

### CON4-19: `replaces` is mandatory for rotated keys, but a DM host cannot know which key a new key replaces
- Verdict: CONFIRMED, and resolved by IMP4-3. 10:850: the registration service "MUST set it in the first registration of each rotated key with each IO, and MUST omit it for a new channel's or DM group's first key." 04:175: "For each group the host keeps only the last `keyEpoch` it issued", and the host is not told which issued key won until a confirmation, and never after a move away from it (04:247). The verified IMP4-3 fix already says "the host omits `replaces` from every registration" for a DM group or self-group, which is the reviewer's option (b). Option (b) is also consistent with 05:34 (DM groups have no sequencer, so no commit stream needs closing) and with agora-dm-key-in-group (host keeps no group knowledge beyond its own user).
- Severity: P3, keep.
- Fix: Apply the IMP4-3 sentence at 10:880. For local consistency also change 10:850 "MUST set it in the first registration of each rotated key with each IO, and MUST omit it for a new channel's or DM group's first key" to "MUST set it in the first registration of each rotated Space channel key with each IO, and MUST omit it for a new channel's first key and for every key of a DM group or self-group (§4.6)".
- Needs decision: no (IMP4-3 already selects option b).

### CON4-20: Appendix C rows disagree with their sections
- Verdict: PARTIAL. Item by item:
  - :90 grace row. PARTIAL. 04:200 does bind DM hosts: "no sooner than 300 seconds after both have happened". But a DM row already exists at 99:100 ("DM admission host deregisters a group's key ... §4.6"); it only omits the 300 s floor. A new row is not needed.
  - :49 200 cap. CONFIRMED. 03:24 lists "DMs" as an `interactive` use, 99:113 says "A DM group is bounded only by the 4096-leaf limit", and 05:53 ("Maximum 200 members") has no committer MUST NOT or member-reject rule, unlike the 4096 limit at 05:71.
  - :55 KeyPackage lifetime. PARTIAL. The row is not wrong: §5.2.1 states the rule at 05:75 ("A KeyPackage's `lifetime` spans at most 90 days"). The real gap is narrower: the validation list at 05:130 checks only "within its `leaf_node.lifetime`", so no one is told to reject a longer span.
  - :83 directory refresh. REJECTED. §10.3.4 does define the default at 10:366: "Clients fetch and merge all configured sources on startup and refresh on a configurable interval (default: 1 hour)." The row is correct.
  - :73 ring duration. CONFIRMED. 06:512 "Clients MUST NOT ring for more than 120 seconds after receipt" constrains device notification, which agora-ux-musts forbids ("normative MUSTs never constrain user agent UX (display, notification, prompts, rendering)"). The row repeats it.
- Severity: P3, keep.
- Fix:
  - spec/99-appendices.md:100, append to the value cell: "; never sooner than 300 s after the new key's Commit has won and a Relay in its `relays` has accepted a Subscribe (§4.6)".
  - spec/03-spaces.md:24, change "Team channels, DMs, small communities" to "Team channels, small communities".
  - spec/99-appendices.md:49, change "Fixed" to "Descriptive; the enforced cap is the 4096-leaf limit (§5.2.1)". (If the editor wants 200 enforced instead, 05:53 needs "A committer MUST NOT issue a Commit that would give an `interactive` channel group more than 200 member DIDs, and members MUST reject one that does", and the row stays MUST.)
  - spec/05-messaging.md:130, change "The KeyPackage is within its `leaf_node.lifetime`." to "The KeyPackage is within its `leaf_node.lifetime`, and that lifetime spans at most 90 days." The span check is time-independent, so it does not interact with CON4-1.
  - spec/06-calls.md:512, change "Clients MUST NOT ring for more than 120 seconds after receipt, whatever `ringUntil` says." to "A ring is expired 120 seconds after receipt, whatever `ringUntil` says, and a client SHOULD NOT ring for an expired ring." spec/99-appendices.md:73: "| Ring expiry | 120 s after receipt | MUST (validity); device ringing SHOULD | §6.14.1 |".
  - No change at :83.
- Needs decision: no.

### CON4-21: Appendix C omits limits that sections state
- Verdict: CONFIRMED. Every cited limit is present verbatim and absent from Appendix C: 04:18 guardian `ts` ("more than 300 seconds from its clock"), 03:181 `delaySeconds` "default 259200", 05:118 KeyPackage upload `ts` 300 s, 14:214 sequencer `expires` ("more than 600 seconds ahead"; 99:87 cites only §11.4, §11.8.2), 10:495 re-announce "every 30 minutes", 10:532 Pkarr "re-publish every 2 hours", 10:227 manifest cache "1 hour" and "retries once after 5 seconds", 10:242 "blocked for 24 hours" and "3 or more incidents within 7 days", 10:271 `knownPeers` "7 days", 10:465 backoff "base 30 seconds, maximum 1 hour" and "7 days" flag. 99:44 claims the table "collects the protocol's numeric limits in one place". The table already declares the section governs, so the harm is limited.
- Severity: P3, keep.
- Fix: Add rows to spec/99-appendices.md:
  - "| Guardian transfer proposal `ts` window; objection period | 300 s; default 259200 s | MUST; Default | §4.1, §3.3 |"
  - "| KeyPackage upload `ts` window | 300 s | MUST | §5.2.1.1 |"
  - Change 99:87 "§11.4, §11.8.2" to "§11.4, §11.8.2, §14.4.3" and the label to "`PinInstruction`, upload and sequencer submission `expires`".
  - "| BEP-5 re-announce | 30 min | SHOULD | §10.3.4.6 |"
  - "| Pkarr re-publish | 2 h | SHOULD | §10.3.4.6 |"
  - "| Peer manifest cache; retry on fetch failure | 1 h; once after 5 s | Descriptive | §10.2.3 |"
  - "| Peer block after a violation; permanent blocklisting | 24 h; 3 incidents in 7 days | Descriptive | §10.2.4 |"
  - "| Unreachable peer kept in `knownPeers` | 7 days | Descriptive | §10.2.6 |"
  - "| Directory fetch backoff; unreachable flag | 30 s to 1 h; 7 days | Descriptive | §10.3.4 |"
- Needs decision: no.

### CON4-22: Appendix D omissions and an undefined name
- Verdict: CONFIRMED, with stale line numbers. 99:182 lists "IPNS name `/ipns/agora.protocol/relays/v1`" and no spec text uses `agora.protocol` (10:265: "an IPNS name configured by the operator (e.g. `/ipns/bootstrap.example.com`)"). 02:316 defines "an `AgoraProvisioning` service entry", absent from the table at 99:161-168. The error-code rows are at 99:144-145, not :141-142, and list only `stream-closed` and `token-rotated` while §11.4 and §10.5.3 define more Agora-internal codes (for example `unknown-token`, `token-withdrawn`). 99:123 is missing the comma after "§2.6)". profiles/compliance-chain-witness.md:32, :90 and guides/relay-operator.md:2373 use `urn:agora:practice:*` against 99:119 ("this specification is the only allocation authority"); relay-operator.md:2384 uses `/.well-known/agora-relay-tombstone`, an unregistered well-known path.
- Severity: P3, keep.
- Fix:
  - spec/99-appendices.md:182, delete ", IPNS name `/ipns/agora.protocol/relays/v1`" and "§10.2.5" from that row.
  - spec/99-appendices.md DID service types table, add "| `AgoraProvisioning` | §2.5.3 |".
  - spec/99-appendices.md:144-145, replace the two rows with "| Error codes of the live protocol and of admission key registration | Error codes | §11.4, §10.5.3, §14.4.3 |".
  - spec/99-appendices.md:123, change "§2.6) `agora_compliance`" to "§2.6), `agora_compliance`".
  - spec/99-appendices.md:119, append: "The prefix `urn:agora:practice:` is reserved for names used by the non-normative guides and profiles in this repository; those names carry no protocol meaning."
  - guides/relay-operator.md:2384, change "`https://<hostname>/.well-known/agora-relay-tombstone`" to "a URL on that hostname that you publish in your operator documentation".
- Needs decision: no.

### CON4-23: References that point to the wrong section
- Verdict: CONFIRMED for all seven. ARCHITECTURE.md:250 cites "§5.2.2, §10.5.1" for registration, which is §10.5.3 (10:818). guides/relay-operator.md:235 cites "spec §10.1" (Deployment Topologies, 10:5); the ALPN text is in the §10.2 introduction (10:33-39). profiles/o365-employer-did.md:192 "(spec §2.1, §6.6)" and :613 "(spec §4.6, §6.7)" mean the profile's own §6.6 Witnesses (:682) and §6.7 (:688); spec §6.6 is SFU Integration and §6.7 is Simulcast. The profile already writes "§6.6 below" at :17. profiles/purview-bridge.md:135 cites §2.5.3 for token validation; §2.5.3 (02:301) creates a stub document and has no token, while validation is §2.5.4 Step 4 (02:340s). profiles/corundum.md:51-52 describe a CID pointer, contradicting spec 10:518 (`url`, `key`) and the profile's own resolved decision at :149. spec/03-spaces.md:225 cites only §3.6 for `seq`, which 05:38 uses for the fork rule. spec/11-transport.md:397 "blobs are encrypted (§3.4)" omits §14.3.4, which 14:311 pairs with it.
- Severity: P3, keep.
- Fix: as the reviewer gives:
  - ARCHITECTURE.md:250: "§5.2.2, §10.5.3".
  - guides/relay-operator.md:235: "per spec §10.2".
  - profiles/o365-employer-did.md:192: "(spec §2.1, §6.6 below)"; :613: "(spec §4.6, §6.7 below)".
  - profiles/purview-bridge.md:135: "at onboarding and device registration (spec §2.5.3, §2.5.4 Step 4) the DID provisioning service validates the IdP token".
  - profiles/corundum.md:51-52, :67, :124: rewrite to the endpoint-plus-posting-key model of :149 and spec 10:518 (the `did:webvh`/`did:plc` service entry names the operator's content endpoint and the posting key; for `did:key` the `_corundum._agora` record carries `url` and `key`).
  - spec/03-spaces.md:225: "§3.6, §5.1.1".
  - spec/11-transport.md:397: "blobs are encrypted (§3.4, §14.3.4)".
- Needs decision: no.

### CON4-24: Guide and profile restatements that contradict the spec
- Verdict: CONFIRMED for all nine; every quote found at the cited line.
  - relay-operator.md:2456 "even for a public Space" contradicts 10:569 "except the token of a `keyAccess: public` broadcast channel, which the CO publishes".
  - relay-operator.md:1248 "it cannot count Commits ... separately" contradicts 12:26 "It recognizes envelopes that carry a stamped Commit by their `commitStamp` (§5.2.2)".
  - regulators.md:203: gateways are listed in a channel's Space state entry (09:37), DM groups have none, and 09:8 says native MIMI "is not specified in this version".
  - gateways.md:108 "the hub and the channel sequencer are the same CO component" contradicts 14:146 "It is an IO" and ARCHITECTURE:61 "| Sequencer | IO |".
  - counsel.md:183 "at first join" and :83 "participants cannot suppress" overstate 07:163 ("before the user first sends") and 07:285/289 ("SHOULD show it as a system notification"); agora-ux-musts keeps display as SHOULD.
  - o365-employer-did.md:547 "space membership is retained" contradicts its own :543 and spec 02:445 (leaves removed).
  - o365-employer-did.md:589 omits 02:360 "rejects a request that registers a key already present in any DID it serves".
  - purview-bridge.md:408 ends "for DM voice groups the `DMComplianceAuditEntry` `removalAttempts` field (spec §7.8.8) records those" (recorder removals); 07:334 limits the field to "Remove commits targeting the logger".
  - radio-mesh-gateway.md:125 and parlance.md:111 apply §13.1, which states the rule only for `urn:agora:type:` (13:38).
- Severity: P3, keep.
- Fix:
  - guides/relay-operator.md:2456, append: "The one exception is a `keyAccess: public` broadcast channel, whose token the CO publishes with its public Space (spec §10.4.1)." Add the same exception at :2429.
  - guides/relay-operator.md:1248, change "so it cannot count Commits, Proposals or application messages separately" to "so it cannot count Commits, Proposals or application messages separately, except that an envelope in a sequenced channel that carries a `commitStamp` is a Commit (spec §12.3)".
  - guides/regulators.md:203, change "(including bridged conversations where the counterparty uses Slack, Teams, or a MIMI-compatible platform)" to "(including conversations in Space channels bridged by a disclosed gateway to Slack or Teams)".
  - profiles/gateways.md:108, change "it is the MIMI hub, and the hub and the channel sequencer are the same CO component" to "it is the MIMI hub, and the hub orders the interop channel's Commits in place of an Agora sequencer".
  - guides/counsel.md:183, change "at first join" to "before they first send"; :83, change "a visible system message that participants cannot suppress" to "a system message, normally shown as a system notification".
  - profiles/o365-employer-did.md:547, change "space membership is retained, but the user cannot send or receive messages until re-enrollment completes" to "the user's leaves were removed from every group, so after re-enrollment the user must be re-added to each group".
  - profiles/o365-employer-did.md:589, change "(account active, device limit)" to "(account active, device limit, and rejecting a key already present in any DID the service serves)".
  - profiles/purview-bridge.md:408, change "for DM voice groups the `DMComplianceAuditEntry` `removalAttempts` field (spec §7.8.8) records those" to "no audit field records recorder removals; `removalAttempts` (spec §7.8.8) covers only the logger".
  - profiles/radio-mesh-gateway.md:125 and profiles/parlance.md:111, change "per §13.1 a breaking change defines a new name" to "following the Agora convention for `urn:agora:type:` names (§13.1), a breaking change defines a new name".
 
- Needs decision: no.

### CON4-25: Gateway profiles never state `unencryptedRemote`
- Verdict: PARTIAL. Parlance CONFIRMED: 09:58 defines `true` "when traffic on the other network is not end-to-end encrypted", and parlance.md:69 says readings "are plaintext on the source site's own fabric" while "the badge flags no loss of confidentiality", inviting `false`. Radio-mesh only partly: radio-mesh-gateway.md:162 already discloses plaintext in its suggested `e2eeNote`, and for a group with a Group OSCORE key the traffic on LICHEN is end-to-end protected among that network's endpoints, so `true` is clear only for a group without one. Neither profile names the field.
- Severity: P3, keep.
- Fix:
  - profiles/parlance.md:69, append: "The Admin sets `unencryptedRemote: true` (spec §9.2)."
  - profiles/radio-mesh-gateway.md:162, append: "The Admin sets `unencryptedRemote: true` (spec §9.2) for a group without a Group OSCORE key, and for any broadcast or pairwise traffic not protected by OSCORE."
- Needs decision: no.
