# FIXCHECK4: check of the review 4 fixes

Scope: `git diff 4b76c3d HEAD -- spec ARCHITECTURE.md profiles guides`, against
notes/review4/*-verified.md and Mark's binding decisions (review4-fix-brief.md,
`bd memories agora-r4`). Covers commits f048f81, 05adc54 (Relay-designated
proxy agreement, 11:262) and fe0681d (`pushProxy` registry row, 99:152).

Summary: 5 P2, 6 P3, no P1. Every confirmed finding has text in HEAD. CON4-8,
CRY4-1, CRY4-6 and SEP4-2 landed incompletely or with a defect; the rest landed
as specified. Global checks: no em dashes added (0 in added lines); no UX MUST
added (the ring limit became SHOULD NOT, "notify the Space admin" is gone, and
the new 07:385 conformance row indexes the pre-existing MUSTs at 07:287 and
07:291); every new § ref resolves (unmatched numbers are RFC 9420 / RFC 8032
sections); Appendix C rows match the body text.

Decision checks: closingHeads (03:195, 03:223, ARCHITECTURE §9 at 464-469),
all-zero channelID (03:173, 03:175, 03:318), 7-day rotation (04:200, 99:109),
the Relay hand-off (10:555, 99:110), the dormant-group limit (12:72), committed
confirmation forgery (12:71), CRY4-10 sentence (12:69 vs 04:167), idpToken
(02:350, o365 557-589), broadcast gateways (09:14, 09:70, radio-mesh:30),
removalAttempts (07:265, 07:337, guides), and audit chain `prevEntryCID`
(07:339 and every example) all landed as decided. Defects are below.

### FX-1: Logger repair Commit is still forbidden and still triggers a re-add
- Severity: P2
- Location: spec/07-compliance.md:242, :260, :265 (CON4-8)
- Evidence: 07:264 and 07:303 now let the regulated member's client remove
  every leaf of `loggerDID` and re-add it in one Commit. 07:260: "no member,
  including the regulated member, MAY issue an MLS Remove commit for the logger
  DID." 07:265: "On receiving a committed Remove for the Space's `loggerDID`
  (issued by another DM group member), immediately re-add the logger ... The
  removal attempt is recorded in `removalAttempts`". 07:242 keeps "The Commit
  that removes every leaf of a listed DID also removes that DID's entry"
  right after the new keep-the-entry clause.
- Problem: a repair Commit by regulated member A is, to regulated member B
  with the same logger, a committed Remove by another member. B's client
  re-adds a logger that already has a leaf, and the logger writes a false
  `removalAttempts` record at that re-admission (07:337). 07:260 forbids the
  repair outright. Clients diverge on whether the repair is legal.
- Fix: 07:260 append "except in a Commit that also adds a leaf of that DID
  (§7.8.5)". 07:265 change "a committed Remove for the Space's `loggerDID`" to
  "a committed Remove for the Space's `loggerDID` in a Commit that adds no leaf
  of that DID". 07:242 change "The Commit that removes every leaf of a listed
  DID also removes" to "A Commit that removes every leaf of a listed DID and
  adds none also removes".
- Needs decision: no

### FX-2: No-sequencer losing-branch recovery never triggers
- Severity: P2
- Location: spec/05-messaging.md:34 with :311 (CRY4-1, decision (a))
- Evidence: 05:34: "a member that applied a Commit for epoch N and then drops
  an envelope that opens under no sealing key it holds (§5.2.2) after
  processing its next Commit, and that obtains no Commit that explains it,
  deletes its state". 05:311: "An envelope that opens under no key is buffered
  until the recipient processes its next Commit (§5.1.1), then tried again,
  and dropped if it still does not open."
- Problem: the winning branch's next Commit is sealed under the winning epoch
  N+1 key, which the loser lacks, so the loser never processes a next Commit
  (unless it commits itself). It buffers forever, reads nothing, and never
  reaches delete-and-re-add. This is a stall in the approved text, not a
  transcription error. Second, smaller gap: the catch-up rule ("holds an
  envelope that opens under the sealing key ... of the epoch one of those
  Commits creates and of no other, applies that Commit") names no winner when
  held envelopes favour two different candidates.
- Fix: in 05:311 change "buffered until the recipient processes its next
  Commit (§5.1.1)" to "buffered until the recipient processes its next Commit
  (§5.1.1) or, in a group with no sequencer, for at most 24 hours". In 05:34
  change "after processing its next Commit" to "after processing its next
  Commit or after holding it for 24 hours". In the catch-up sentence change
  "applies that Commit" to "applies, among such Commits, the one with the
  lowest `id`". Add the 24 h row to Appendix C.
- Needs decision: yes. The verifier deliberately avoided a new timer; some
  bound is needed. 24 h is a suggestion (any value above the 5 s window and
  relay delivery jitter works).

### FX-3: Guests lose `closingHeads` after the one replacing view
- Severity: P2
- Location: spec/08-cross-space.md:97 (CRY4-6)
- Evidence: landed: "and the home Space's `sequencer` and that channel's entry
  of any `closingHeads` (§3.3)". 03:195: "`closingHeads` is present only in a
  Space state document that replaces one `sequencer` DID with another". The
  verifier's text was "the `closingHeads` of the latest home Space state that
  carried them while the shared channel's commit stream named there is within
  relay retention".
- Problem: the guest view is built from current state, so "any `closingHeads`"
  is empty once a later state is published. A guest that missed that view
  rejects old-DID stamps (05:29), refetches, still finds no head, and cannot
  catch up the closed stream: a stall on the shared channel, or a fork if it
  accepts old-DID stamps without a head.
- Fix: replace "that channel's entry of any `closingHeads` (§3.3)" with "that
  channel's entry of the `closingHeads` of the latest home Space state that
  carried them, while the commit stream it names is within relay retention
  (§3.3)".
- Needs decision: no

### FX-4: `pushProxy` in Space state lacks what a client needs to register
- Severity: P2
- Location: spec/03-spaces.md:197, :224; spec/11-transport.md:289-318, :329;
  spec/99-appendices.md:152 (SEP4-2 (b))
- Evidence: Space state: "`pushProxy` ... object `{did, endpoint}`". Manifest
  (11.7.2): `{endpoint, proxyDID, platforms, registrationEndpoint}`. Step 3
  POSTs to the proxy's register path; step 4: "the proxy's `endpoint`
  (§11.7.2)".
- Problem: for a CO-designated proxy a client has no `registrationEndpoint`
  and no `platforms`, and step 4 points only at the manifest form. Clients
  will guess the register URL differently (`endpoint` + `/register`, or
  `endpoint` itself), and cannot tell whether the proxy serves FCM or APNs.
- Fix: 03:197, 03:224, 99:152: "`pushProxy` is an object with the members of
  the Relay manifest's `pushProxy` (§11.7.2)". 11:318 step 4: "the proxy's
  `endpoint` (§11.7.2, or §3.3 for a CO-designated proxy)".
- Needs decision: no

### FX-5: `pushProxy` is public in the non-member view, and shared channels are undecided
- Severity: P2
- Location: spec/03-spaces.md:197, :224; spec/11-transport.md:329;
  spec/08-cross-space.md:97
- Evidence: the non-member view omits only `members`, hidden channels and now
  `closingHeads` (03:215, 03:223); the `pushProxy` row says only "optional".
  11:329: "It registers with a CO-designated proxy (§3.3) only the
  `channelToken`s of channels of Spaces whose state names that proxy". A
  shared channel is also aliased in each guest Space (08:16).
- Problem: (a) a public Space's view publishes its proxy endpoint. Every
  `PushRegister` shows the Relay that endpoint, and with per-proxy handles all
  tokens under that handle belong to Spaces naming it. A Relay can tie those
  tokens to the public Space, which §10.4.2 says it cannot do (S1, §5 budget).
  §9 accepts this only for `keyAccess: public` tokens. (b) A guest can read
  "channels of Spaces whose state names that proxy" as covering the alias in
  its own Space. It then registers the home CO's token with the guest CO's
  proxy. The home CO's Relays learn a guest CO's linkage, and the guest proxy
  rejects their wake-ups (11:361 "unknown or untrusted Relay DIDs").
- Fix: 03:224 "optional; omitted from the non-member view" (as for
  `closingHeads`). 03:197 and 11:329: "channels whose home Space's state names
  that proxy". Guests then fall to the Relay-designated proxy, because 08:97
  does not carry `pushProxy`.
- Needs decision: no

### FX-6: DM Relay hand-off duty is unbounded and the weekly rotation strength is unclear
- Severity: P3
- Location: spec/10-relays.md:555 vs :688; spec/04-access-control.md:200
  (IMP4-1 (b))
- Evidence: 10:555: "a DM admission host keeps a departing Relay registered
  until every key it issued that lists that Relay has been deregistered".
  10:688: "A CO ... deregisters its keys there before `retiresAt`". 04:175: "A
  host that does not offboard DIDs has no such bound." 04:200: "A host's
  user's client also rotates the key, as for a removal, when 7 days have
  passed".
- Problem: a dormant group's key may never be deregistered, so the 10:555 duty
  never ends and contradicts 10:688. The Relay stops at `retiresAt` anyway and
  12:72 accepts the loss, so this is only wording. "Also rotates, as for a
  removal" leaves open whether this is a MUST and whether only the lowest-leaf
  host's user acts. The 14-day bound depends on it; reading it as every host's
  user only adds churn.
- Fix: 10:555 append "or until `retiresAt`, whichever is first". 04:200: "the
  client of the host's user with the lowest leaf index MUST also rotate the
  key, as for a removal, when 7 days have passed".
- Needs decision: no

### FX-7: Space creation does not generate the Space group's admission key
- Severity: P3
- Location: spec/03-spaces.md:361 (CON4-3 / CRY4-5)
- Evidence: "4. The CO generates each channel's admission key". 03:175 extends
  only "§3.4, §5.1.1, §5.2.2 and §14.4.5" to the Space's own group.
- Problem: a creator implementing §3.6 literally never creates the
  all-zero-channelID key, so the Space group cannot publish until some other
  path creates it.
- Fix: 03:361 "generates each channel's admission key and the Space's own
  group's (§3.3)".
- Needs decision: no

### FX-8: Bogus-key bullet still says confirmation implies a committed key
- Severity: P3
- Location: spec/12-security.md:69 vs :71
- Evidence: 12:69: "a host deregisters an earlier key on its own only 7 days
  after the issuee of a later key confirms that key's Commit". 12:71 (CRY4-3
  accepted limit): a served DID can "have a key issued for the group and
  confirm it".
- Fix: 12:69 change "confirms that key's Commit" to "confirms that key (§4.6;
  see the stranding limit below)", matching 04:196.
- Needs decision: no

### FX-9: Move-by-default condition depends on state other members cannot see
- Severity: P3
- Location: spec/04-access-control.md:243
- Evidence: "the client of the remaining member with the lowest leaf index,
  other than a DID listed in `agora_compliance` (§7.8.2) and among those not
  holding the group in the message request state (§4.6.3), moves the group".
- Problem: the same defect CRY4-11 fixed at 04:200. No member knows who else
  holds a message request, so the second-lowest member cannot tell it is
  designated. The 24 h fallback and the canonical-Commit rule resolve it, so
  there is no fork.
- Fix: replace the added clause with the 04:200 pattern: "A client that holds
  the group in the message request state skips this duty, so the move can
  then wait for the 24-hour fallback."
- Needs decision: no

### FX-10: Admission-key endpoint error codes are not registered
- Severity: P3
- Location: spec/99-appendices.md:156; spec/04-access-control.md:175
- Evidence: the new codes `malformed`, `unauthenticated`, `not-served`,
  `not-issuee`, `unknown`, `rate-limited`, `no-relay` (04:175). The registry
  row covers "Error codes of the live protocol and of admission key
  registration | §11.4, §10.5.3, §14.4.3".
- Fix: change the row to "... of admission key registration and of the DM
  admission-key endpoint | §4.6, §11.4, §10.5.3, §14.4.3".
- Needs decision: no

### FX-11: Gateway profile intro still says every gateway joins the MLS group
- Severity: P3
- Location: profiles/gateways.md:13
- Evidence: "a CO component with its own DID, admitted to the channel MLS
  group as a member, ... announced by a `gateway-added` `SystemEvent` before
  any message flows through it."
- Problem: non-normative, but it now contradicts 09:70 for broadcast channels.
- Fix: append "(on a broadcast channel, a broadcaster disclosed by its
  descriptor and the `broadcasters` list, spec §9.3)".
- Needs decision: no
