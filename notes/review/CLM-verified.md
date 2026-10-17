# CLM verified

Verifier pass over notes/review/CLM.md. Each finding was checked against the cited
text, a grep of spec/ and ARCHITECTURE.md, and the recorded decisions
(`bd memories agora`, full text via `bd kv list`).

### CLM-1: Spec claims cross-epoch unlinkability that the access-key chain removes by design
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:518; spec/12-security.md:34, 46; spec/05-messaging.md:216 (vs 05:186, 05:203); ARCHITECTURE.md:145-160
- Fix: As proposed. 10.4.2 still says a Relay "cannot correlate [routing tables across epochs] without also capturing the epoch secrets" and 12.3 says it cannot "Map routing tables across epochs without MLS group secrets", while 05:203 says "The relay thereby follows the chain from token to token", and Q1/Q6 make chain-following the design. The outer envelope carries `"epoch": 17` in the clear, so the 05:216 claim that the wrapper hides "epoch boundaries and which messages are Commits" is false (announcements ride only on Commit envelopes). Rewrite those three passages to say the relay links one chain's epochs and sees epoch boundaries and Commit cadence, not the chain's channel or Space; cut the 05:216 rationale to `group_id` value, sender data and non-Commit content type. 12.4 l.40 ("keep ... the message kind away") needs the same Commit exception. ARCHITECTURE §5 item 2 should name `epoch`, `id` and `ts` (`powProof` is a connection-level object at 10-relays.md:676 and falls under item 3 or 1; state which).
- Needs decision: no

### CLM-2: Relay-side push registrations and `pushUrgency` are outside the observation budget
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/11-transport.md:160, 194, 233-238; spec/12-security.md:48; ARCHITECTURE.md:161, 286-288; PRFAQ.md:31
- Fix: The registration half follows from decision Q4 ("push on by default"; ARCHITECTURE §8 Q4 "Push is in the §5 budget by default"): S6 forbids observing anything outside §5, and the relay necessarily holds `channelToken → pushHandle` (11-transport.md:160), yet §5 item 7 reads "For push proxies only". Extend item 7 to relays serving push (per-`pushHandle` token sets and proxy endpoint), add per-handle clustering to §9 next to address clustering, and add it to the PRFAQ relay-visibility answer. No decision needed for that part. `pushUrgency` is different: Q4 says "content-free wake-ups" and does not cover a sender-supplied DM/mention label, and 12.4 says a Relay "cannot distinguish them from other traffic by type". Keeping it means a budget extension and a 12.4 exception. Dropping it makes the 12.4 claim true.
- Needs decision: yes, narrowed to `pushUrgency` only. (a) Drop `pushUrgency` and send every wake-up at one urgency (recommended: matches "content-free" and the 12.4 claim); (b) keep it, list it in §5 item 7, add the 12.4 exception. The original option (b), per-channel handles, is not needed.

### CLM-3: Sequencer, an IO, can map its streams to Spaces, contrary to S1 and the Space-anonymity claim
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/14-jmap.md:193; ARCHITECTURE.md:61, 86-88, 157-160
- Fix: 14.4.6 states "its operator can associate its streams with those Spaces", which is outside §5 (S6) and contradicts §5 item 6's anonymity-set claim. The mitigation in 14.4.6 is only advisory.
- Needs decision: yes. (a) Make 14.4.6's mitigation a MUST: the CO runs the sequencer or designates one sequencer for all its Spaces (recommended; mirrors billing-DID reuse in 10.5.1). (b) Accept and document in §9 and the §2.3 table. Note: decision D2 says "blind per-community sequencer"; if "community" means one Space, (a) as "one per CO" needs Mark to confirm it does not contradict D2. In that case the only S1-compatible form of (a) is CO-operated.

### CLM-4: "Cannot hijack the chain" depends on an ordering the spec does not require
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:204; spec/04-access-control.md:88; spec/03-spaces.md:28; PROPOSAL.md:80-81; PRFAQ.md:99
- Fix: The gap is wider than the finding says. (1) The gate is "a DID it authenticates as a current member of the channel under Space state", but 03:28 says "Space membership does not imply channel membership" and a Kick (04:88) "removes a member from one or more channel MLS groups without a space-level ban" and changes no Space state, so a kicked member always passes the gate. (2) The service countersigns "at most one announcement per chain and `epoch`" and cannot check that the announced key matches a real Commit, so any current member, not only one being removed, can grab the single countersignature with a key only they hold and lock out the channel. Option (a) as originally proposed (Space-state removal first) covers neither case. This attacks the implementation, not decision Q1, which says the countersignature "closes removed-member forgery race". Until it is fixed, soften PROPOSAL l.80-81 and PRFAQ l.99. Add to agora-pozi.8 (open) scope, which already lists "commit ordering".
- Needs decision: yes. (a) The service countersigns only on a CO-authorized membership-change record naming the committer and the removed DIDs, so removals and kicks go through the CO first (recommended; the registration service is already a CO component). (b) First-come countersigning plus a CO re-key path that registers a fresh chain for a locked-out channel. (c) Defer entirely to the pozi.8 external review.

### CLM-5: Replaceability is not backed for a relay added mid-life of a group
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:612-622; ARCHITECTURE.md:106-109 (S5)
- Fix: 10.5.1 registers only "the group's first-epoch access public key" and then "the Relay follows the chain". Nothing lets a new relay pick up a live chain, and grep finds no relay-replacement procedure in 10 or 11. Allow `AccessChainRegistration` at the current `epoch` with that epoch's `channelToken` and access key (the format already has `epoch`), signed by the same billing DID. The registration service holds those values because it countersigned the announcement. Require the CO to register live chains at a new relay before switching. This keeps Q6's trust model (same service, same billing key) and is required by S5, which governs on conflict.
- Needs decision: no

### CLM-6: "The provider cannot link your traffic to a particular Space" is absolute
- Verdict: CONFIRMED
- Severity: P2
- Location: PRFAQ.md:35, 17; PROPOSAL.md:42-43; vs ARCHITECTURE.md:307-313
- Fix: As proposed. ARCHITECTURE §9: "A CO with one Space gets none", plus registration-timing correlation and address clustering. PROPOSAL l.42 ("or which channel or Space a routing token belongs to") and PRFAQ l.17 need the same qualifier as l.35. PRFAQ l.31 ("which of a customer's Spaces") needs it too.
- Needs decision: no

### CLM-7: "Interoperates natively with MIMI" overstates
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: PRFAQ.md:55 (FAQ); press-release line PRFAQ.md:21 excluded
- Fix: The press release is written "as if the product has already launched" (PRFAQ footer, l.115), so its present tense is the genre and not an error. Also, spec 9.1 itself says "E2EE is preserved end-to-end across the system boundary". The real gap is the FAQ at l.55, which drops the caveat from 09:66: "Members SHOULD be told that the peer MIMI provider also learns the room's participant list." Add that sentence there. The stalled delivery-layer drafts belong under "top risks" at most.
- Needs decision: no

### CLM-8: Stale identity-method references
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/09-interop.md:22; spec/99-appendices.md:11
- Fix: As proposed. 09:22 says "(`did:key` or `did:web`)", which contradicts the agora-did-methods decision (did:webvh default, did:plc/did:key opt-in). 09:32's example credential may stay `did:key`. Appendix A Identity row becomes "W3C DID Core; methods in rows below" (the rows at 99:31-33 already list them).
- Needs decision: no

### CLM-9: "One thing" undecided understates; Appendix B is stale
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/99-appendices.md:40, 38; spec/13-encoding.md:86; spec/10-relays.md:440; PRFAQ.md:99
- Fix: Appendix B item 2 points to agora-pozi.11, which is CLOSED ("Decided by Mark 2026-10-16"). Delete the item. 13:86 and 10:440 cite agora-pozi.20.16, which is CLOSED ("Resolved in P3 errata pass"), yet both still say Open. File new beads and re-point the markers. The PRFAQ question is about open design questions, so unfinished work items (test vectors) do not belong in it. Appendix B item 1 (cross-space reputation) is an open question, though, so "One thing" is wrong. Reword to name the access-proof review as the one blocking question and mention cross-space reputation as an open optional extension. The finding calls the infohash gap "blocks DHT bootstrap", but Mainline is one of several parallel bootstrap methods (10-relays.md:202), so that claim is overstated.
- Needs decision: no

### CLM-10: S3 forbids IOs holding exporter outputs, but `channelToken` is one
- Verdict: CONFIRMED
- Severity: P3
- Location: ARCHITECTURE.md:96-99; spec/14-jmap.md:124; spec/05-messaging.md:194
- Fix: As proposed. `channelToken` is `MLS-Exporter("agora channel token", ...)`, held by relays (§5 item 2) and sequencers (14.4.6 "the streams it orders (`channelToken`s)"). 14.4.1's "holds no ... exporter outputs" is literally false. S3: "other than routing tokens and those derived for IO verification (§6.2)". 14.4.1: "no exporter outputs other than routing tokens".
- Needs decision: no

### CLM-11: ARCHITECTURE reference and citation errors
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: ARCHITECTURE.md:264; spec/11-transport.md:260
- Fix: Keep (a): ARCHITECTURE.md:264 "Open question Q2" becomes "Resolved: §8 Q2". Keep (d): spec/11-transport.md:260 "§5.3 item 4" becomes "§7 item 4" (ARCHITECTURE has no §5.3; §7 item 4 is the channelToken→channelCid/JMAP erratum). Reject (b): the quoted sentence exists verbatim (import/agora-privacy-whitepaper-clean.md:267, "Agora is not anonymous"), and ARCHITECTURE cites it only for the narrow network-layer point, which is still accurate. Reject (c): §2.1 lists IO kinds, and spec 10.4.4 permits mirroring CO-published records to public IPFS (10-relays.md:574), so an IPFS pinning service is a valid IO and nothing contradicts it.
- Needs decision: no

### CLM-12: README and PROPOSAL profile lists are incomplete
- Verdict: CONFIRMED
- Severity: P3
- Location: README.md:22; PROPOSAL.md:65
- Fix: profiles/ also has compliance-chain-witness.md, parlance.md and radio-mesh-gateway.md. List them, or write "including ...".
- Needs decision: no

## Counts
- CONFIRMED: 7 (CLM-1, 3, 5, 6, 8, 10, 12)
- CONFIRMED-ADJUSTED: 5 (CLM-2, 4, 7, 9, 11)
- REJECTED: 0 (sub-items CLM-11 (b) and (c) rejected)
- By severity after adjustment: P1 0, P2 6 (CLM-1 to 6), P3 6 (CLM-7 to 12)
- Needs decision: CLM-2 (narrowed to `pushUrgency`), CLM-3, CLM-4
