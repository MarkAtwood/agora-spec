# Review 2 verification: SEP2

Verifier pass over notes/review2/SEP2.md. Checked against the spec text, ARCHITECTURE.md and the `bd memories agora` decisions (notably agora-broadcast-decision, agora-doorkey-B, agora-q6-billing-did, agora-did-methods, agora-q4-push).

### SEP2-1: Public broadcast channels publish their channelToken, so any IO can map that token (and the CO's billing DID) to a named Space and channel
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/03-spaces.md:311, :297, :245; spec/05-messaging.md:175; ARCHITECTURE.md:166-170 (§5 item 6), :392-404 (§9); spec/10-relays.md:546; spec/12-security.md:39
- Fix: The leak is real. 03:311 publishes the subscriber form, which per 03:297 "carries `channelToken`", while ARCHITECTURE §5 item 6 says "An IO MUST NOT be able to map an admission key to a Space or channel" and 10:546 has the relay testify "I do not know which Space or channel any token belongs to". This is not an attack on a decision: agora-broadcast-decision says "public channels publish key in public Space state", and a subscriber cannot read without the token. Disclosure therefore follows from the decision. Option (b) in the finding contradicts the decision and, as the finding admits, does not stop the mapping. Fix: add to ARCHITECTURE §5 item 6 "except the token of a `keyAccess: public` broadcast channel, which the CO publishes with its Space", add a matching §9 bullet (an IO can map a public channel's token, and the billing DID it is registered under, to the Space; this ties that CO's billing DID to a named Space and lets push/address clustering tie followers' other tokens under that CO to a known community), and qualify 10:546 and 12:39 ("except tokens a CO publishes"). Additional defect the finding missed: in a non-public Space, "public Space state" has no defined meaning. 03:317 serves a private Space's state only to authenticated members and invitees, and 03:321 forbids storing "content that identifies a Space that is not public" on IO infrastructure in the clear. That conflicts with 03:311's "MAY mirror them like other public Space state".
- Needs decision: yes, narrowed to one question: may `keyAccess: public` be set in a non-public Space? (a) Restrict it to public Spaces: one line at 03:245 that also removes the 03:317/321 conflict. (b) Allow it, and define it as an unauthenticated endpoint path for those two records only, with no IO mirroring. Recommend (a). The disclosure text is required in either case and is not a decision.

### SEP2-2: Admission key registrations disclose `keyEpoch`, which tells every IO a channel's removal count and when it was created
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3 (from P2)
- Location: spec/10-relays.md:790, :807; spec/14-jmap.md:198, :207, :212; spec/06-calls.md:134, :138, :163, :167
- Fix: `keyEpoch` is redundant at the IO. 10:815 says "A token is registered with at most one key", and the token is derived per epoch (05:255), so `channelToken` alone identifies the key. The leak is smaller than claimed. "Undoes the random delay" is wrong: the delay hides the registration time whatever the body says. An IO can already tell a new channel from a rotation, because a new channel's registration has no matching deregistration (10:564). The real extra leak is the cumulative rotation count, including rotations before this IO was engaged (a newly engaged relay receives the current key with its full counter, 10:829). That is outside §5 item 6. Fix as suggested: drop `keyEpoch` from `AdmissionKeyRegistration` (10:790, 10:807 sentence), from `seq-auth` (14:198, :207 "and `keyEpoch`", :212 error text), and from `sfu-admission`/`sfu-admitted` (06:134, :138, :163, :167). IOs match on `channelToken` only. Keep `keyEpoch` member-side. Replay protection at the SFU comes from the nonce, so nothing else depends on the field.
- Needs decision: no

### SEP2-3: A DM's or self-group's "CO" can be a single-user identity host, which gives the relay the initiator's identity; no billing-DID rule covers identity hosts
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:777, :696; spec/12-security.md:53; spec/02-identity.md:496; ARCHITECTURE.md:395-396 (§9); spec/10-relays.md:545
- Fix: As suggested. 10:696 restricts the billing DID only from records "that identif[y] a Space", so nothing stops a self-hosting individual from using their own DID. agora-q6-billing-did makes anonymity depend on the CO serving many Spaces, and §9 accepts "A CO with one Space gets none", but no counterpart exists for identity hosts. agora-did-methods allows the individually chosen hosts that create this case. Extend 10:696 with "and, for an identity host, MUST NOT be a DID of a user it serves or appear in any DID document, Pkarr record or other user-identifying record". Add the §9 bullet ("DM and self-group anonymity at the IO is only as large as the initiator's identity host; a host serving one user gives none"). Qualify 12:53 ("does not learn who is in a DM, except as above") and 10:545.
- Needs decision: no

### SEP2-4: ARCHITECTURE §9 says an identity-plus-relay operator "never learns ... channel", but as DM admission host it knows DM membership by DID, and as relay it sees each DM's traffic
- Verdict: CONFIRMED
- Severity: P2
- Location: ARCHITECTURE.md:405-408; profiles/corundum.md:38; spec/04-access-control.md:158; spec/12-security.md:239
- Fix: As suggested. 04:158 says "The host learns the DM group's member DIDs" and also names the relays. When those are its own relays, the "never learns content, channel or Space" claim at ARCHITECTURE:406 is false for DMs. The ARCHITECTURE bullet now exists at :405-408, so corundum.md:38 "That text is not in ARCHITECTURE.md yet" is stale and should be deleted. Rewrite the §9 bullet as proposed, mirror it in corundum.md §2, and add the RECOMMEND that a DM admission host list relays it does not operate.
- Needs decision: no

### SEP2-5: Any single DM member can rewrite the admission host's member list, silently cutting others off at relays or handing the admission key to non-members
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:158, :259; spec/02-identity.md:452
- Fix: Only the removal half holds. Adding non-members grants nothing beyond what any member can already do: every member holds the `ChannelAdmissionKey` seed (12:57 "Anyone who holds a `ChannelAdmissionKey` ... can compute the token"), so a hostile member can give it to anyone directly, and an added outsider still cannot read without MLS. That half is REJECTED. The removal half is real. A DM has no "remove another member" operation (04:257-259 define only self-Remove; 02:452 allows Removes only of revoked devices), yet 04:158 lets any one listed member drop any DID, and the host then rotates and refuses that DID the key. The fix follows from existing rules: the host accepts a `DMMembers` replacement that drops a DID only if (i) the signer is that DID (self-leave), or (ii) the dropped DID's resolved DID document has no current device keys (revoked/offboarded, matching 02:452). Additions remain accepted from any listed member. Change 04:259 so the leaving member's client sends its own `DMMembers` replacement, not the committer's.
- Needs decision: no

### SEP2-6: A DM's admission host stays with the initiator's identity host after the initiator leaves or is offboarded, and the remaining members cannot replace it
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:158, :259; spec/02-identity.md:447-456; spec/12-security.md:239
- Fix: No text changes `agora_admission_host` (it appears only at 04:158, 03:311 and 99:107). agora-doorkey-B says "DMs via initiator's identity host" but does not cover an initiator who has left. After offboarding (§2.5.6), the employer's provisioning service keeps issuing keys for, and observing the fetch timing of, outside members of a DM in which it has no member.
- Needs decision: yes. (a) Handover: a remaining member commits a GroupContextExtensions proposal setting `agora_admission_host` to its own identity host, which issues and registers a new key. Clients MUST do this when the host's user is no longer a member. (b) Constraint: when the initiator leaves, the DM ends at the admission layer, and a remaining member MAY create a new group (the same path 04:128 already uses after a policy violation). Recommend (a): it is one standard MLS proposal and keeps the conversation. (b) is simpler to specify but breaks every multi-party DM whose initiator leaves. In either case, note in §12.11 that the initiator's host sees the other members' fetch timing.

### SEP2-7: Undelayed removal rotations let an IO see that a member was removed and which subscriber was dropped
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/10-relays.md:564, :837; spec/05-messaging.md:256; ARCHITECTURE.md:392-397; spec/12-security.md:26
- Fix: The premise that "periodic rotations [are] batched, delayed" is wrong. 10:837 requires delay only for "new channels and DM groups", so periodic and removal rotations are not timing-distinguished by the spec. The real signal is the subscriber that stays on the old token (10:564 "the same subscribers move across"). That gives the IO pseudonymous removal events, which neither §9 nor 12.3 states. Fix: add the disclosure sentence to ARCHITECTURE §9 and spec §12.3/§12.4 ("An IO can see which subscribers do not move to a rotated key's token, and so can infer that a removal occurred and which connection or push handle it affected"). Drop the optional timing recommendation, since it addresses a difference the spec does not create.
- Needs decision: no

### SEP2-8: The self-group gives relays a token that only one person's devices hold, which links that person's devices, addresses and push handles
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:496; spec/04-access-control.md:158; ARCHITECTURE.md:395-401
- Fix: As suggested. §9 accepts linkage of one device via push and same-address clustering, not linkage across a person's devices on different networks. A self-group token is followed only by the user's devices, which gives exactly that linkage. Add the sentence to the §9 push/address bullet, with the optional RECOMMEND of a distinct relay.
- Needs decision: no

### SEP2-9: The SFrame KID gives the SFU a stable per-member pseudonym and epoch-change signal; §6.6 wrongly calls this within budget items 1-2
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/06-calls.md:186, :191, :222; ARCHITECTURE.md:149-157
- Fix: As suggested. Item 2 lists only envelope routing fields, while the KID (06:222, RFC 9605 §5.2) carries `sender_index` (the MLS leaf index, stable across calls in the group) and `epoch % 16`, which reveals MLS epoch changes that 12.4 otherwise keeps from IOs. Add the KID to ARCHITECTURE §5 (an SFU item), add the §9 sentence, and correct the 06:191 citation. The KID format comes from RFC 9605 and is not something to redesign.
- Needs decision: no

## Counts

- CONFIRMED: 5 (SEP2-3, -4, -6, -8, -9)
- CONFIRMED-ADJUSTED: 4 (SEP2-1, -2, -5, -7)
- REJECTED: 0 (the "add non-members" half of SEP2-5 is rejected within the adjusted finding)

By severity after adjustment: P2 5 (SEP2-1, -3, -4, -5, -6); P3 4 (SEP2-2, -7, -8, -9).
Needs decision: SEP2-1 (whether `keyAccess: public` is allowed in non-public Spaces), SEP2-6 (handover vs. end the DM).
