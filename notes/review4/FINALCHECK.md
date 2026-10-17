# FINALCHECK: final check of review 4 closure

Scope: `git diff f048f81` (committed f048f81..HEAD plus working tree) over
spec/, ARCHITECTURE.md, guides/, profiles/, against notes/review4/FIXCHECK4.md
and `bd memories agora` (in particular `agora-r4-no-autodrop`).

Summary: 2 P2, 0 P1, 0 P3. Both P2s come from the new out-of-sync flag. All
FIXCHECK4 fixes landed as specified and complete:

- FX-1: 07:242, 07:260, 07:265, 07:337 and 07:346 all changed.
- FX-2 (now no-autodrop): 05:34 and 05:311, plus Appendix C row 99:94.
- FX-3: 03:195 and 08:97.
- FX-4 and FX-5: 03:197, 03:224, 11:318, 11:329 and 99:153.
- FX-6 to FX-11: 10:555, 04:200, 03:361, 12:70, 04:243, 99:157,
  profiles/gateways.md:13 and the o365 profile line 690.
- 8-day fallback: 04:200, mirrored in 10:555 and row 99:109 ("every host's
  user's client 24 h later" equals 8 days).

Global checks:
- No em dashes in added lines.
- No UX MUST added. The out-of-sync suggestion is SHOULD, and the new rotation
  MUSTs are protocol actions.
- New § refs resolve. "the stranding limit below" is 12:73. §7.8.5 holds the
  repair at 07:303.
- ARCHITECTURE.md:222-225 matches the pushProxy and agreement text.
- No old-style `{did, endpoint}` pushProxy remains.
- No delete-on-unopenable text remains in ARCHITECTURE, guides or profiles.
  05:452 (Commits past relay retention) is a separate trigger and is unchanged.
- The flag is local. Nothing transmits it.

### FN-1: Flagged member of a no-sequencer Space channel can never be re-added
- Severity: P2
- Location: spec/04-access-control.md:90 vs spec/05-messaging.md:34
- Evidence: 05:34 says: "including in every DM group" ... "It keeps its state,
  and the flag, until it accepts a Welcome for the group, which replaces that
  state (§4.6)." 04:90 (Space channel and Space group Welcomes) says: "MUST
  reject a Welcome for a group ID for which it already holds group state; a
  Welcome never replaces an existing group." The only exception is in the DM
  paragraph (04:204).
- Problem: the no-sequencer rule covers Space groups whose Space has no
  `sequencer` (03:193), not only DMs. Take a flagged member of such a channel.
  It no longer deletes its state, and the §4.3 rule rejects every re-add
  Welcome. The member is cut off from that channel for good. The spec text
  contradicts itself, and the result is a permanent stall.
- Fix: in 04:90, replace "a Welcome never replaces an existing group" with
  "a Welcome never replaces an existing group, except that a client that has
  flagged itself out of sync in the group (§5.1.1) accepts a Welcome for it
  that passes the other checks of this paragraph and replaces its state,
  keeping the messages in its own store". In 05:34, change "(§4.6)" to
  "(§4.3, §4.6)".
- Needs decision: no (follows `agora-r4-no-autodrop`).

### FN-2: Anyone who can trigger the flag lets any DM member replace a victim's state with a forged group
- Severity: P2
- Location: spec/04-access-control.md:204; spec/05-messaging.md:34;
  spec/12-security.md:69
- Evidence: 04:204 says: "a client that has flagged itself out of sync in a
  group (§5.1.1) accepts a Welcome for that group ID that passes the other
  checks of this paragraph, and replaces its state". One of those checks is
  "an adder authenticated from the group's ratchet tree as a member of the
  group", and that tree is the Welcome's own. 05:34 says the client "keeps its
  state, and the flag, until it accepts a Welcome", so nothing else clears the
  flag. 12:69 says anyone who can get an envelope admitted "can publish bytes
  that open under no sealing key", and that the sender "destroys no group
  state".
- Problem: a current DM member M, a removed member before rotation, or a
  holder of a leaked key publishes one garbage envelope. 24 hours later every
  member is flagged, including members that are fully in sync. The flag never
  clears. M then builds a fresh MLS group with the same group_id. It holds M,
  victim V (from a fetched KeyPackage) and a copied `agora_admission`. M is a
  member of that tree, so the Welcome passes every check, and V's client
  replaces its real state. V's leaf stays in the real group, so the other
  members think V still reads. V meanwhile posts into M's group. A removal is
  visible to every member, but this split is visible only to V, through a
  changed member list. It is a new silent-separation power. It also makes
  12:69's "destroys no group state" false. 04:90 also needs the exception
  (FN-1). There, the Space-state authorization of the adder limits this abuse
  to authorized adders.
- Fix (proposed):
  (a) In 05:34, add "It clears the flag when it processes a Commit for a later
  epoch issued by another member". A member flagged by garbage stops being
  open to replacement at the group's next Commit. A real loser on its own
  branch receives no such Commit from the winning branch.
  (b) In 04:204, add "whose adder's DID is a member of the group in the state
  it holds". This rules out strangers who hold a leaked key. Removed members
  the victim has not yet seen removed still qualify.
  (c) In 12:69, replace "destroys no group state" with an accepted-limit
  sentence: "while a member is flagged, any member of the group in its held
  state can replace that state with a group of the adder's making by sending a
  Welcome (§4.6); the member list the client then shows is the only sign".
- Needs decision: yes. Flag stickiness and who may re-add are new policy
  beyond the memory, and no cryptographic check ties a Welcome to the real
  group's lineage. Alternatively, Mark can accept the whole risk as a limit,
  with (c) alone.
