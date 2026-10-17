# CRY2 verified

Input: notes/review2/CRY2.md. I checked each finding against the cited spec text, the rest of spec/ and ARCHITECTURE.md, the recorded decisions (`bd memories agora`), and the local RFC copies (/home/mark/PROJECT/IETF/specs/rfc9420.txt, rfc9605.txt). There is no local copy of RFC 7515. The JWS points rest on the spec's own §13.1.1 text.

### CRY2-1: Commit streams are keyed to `channelToken`, so the sequencer rule forks the group across an admission-key rotation
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:27, 256; spec/14-jmap.md:157-162, 207, 238; spec/10-relays.md:839
- Fix: The cited text holds as described. The sequencer admits any registered, not yet deregistered `keyEpoch` (14-jmap.md:207: "`channelToken` and `keyEpoch` MUST match a key registered under its agreement and not deregistered"). Registrations carry nothing that links tokens (10-relays.md:807), so the sequencer cannot restrict Commits to the newest stream. The committer reads only "that stream's log" (05-messaging.md:27). One partial mitigation already exists: 14-jmap.md:162 says "The total order of a channel's sequenced operations is by stream, in the order of the channel's tokens, then by position". That gives members a defined cross-stream comparison if "lower `n`" in 05:27 is read as that order. It does not save the committer-side check, and the 5-second switch window does not cover a k-stream Commit stamped up to 300 s after a (k+1)-stream Commit was applied. The "Closing a stream" rule (14-jmap.md:238) depends on the `after` field of `JmapSet`, which Commits do not carry, so it does not extend to Commits by itself. Under (a), 05:27 and 14-jmap §14.4.2 change to name the commit stream by a CO-issued `commitStreamID` in `ChannelAdmissionKey`, kept across rotations. Linking key epochs is within budget: 12-security.md:39 says "It may link the key epochs of one channel", and 06-calls.md:176 says the same.
- Needs decision: yes. (a) Stable CO-issued `commitStreamID` in `ChannelAdmissionKey`. (b) Per-token commit streams plus a close/handover rule: position 0 of the new commit stream names the old head, committers read both streams during grace, and a Commit stamped on a closed stream loses. (c) No Commits during a rotation's grace period. Recommend (a). It is the smallest change, and it stays within the observation budget.

### CRY2-2: A stamped but unpublished, or invalid, Commit wins the epoch, and nobody can make progress
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:27, 30; spec/14-jmap.md:218-220
- Fix: Half of the finding is wrong. The unpublished case is already partly covered: the 14-jmap.md:220 sentence "If a submitter fails to publish step 4, any member holding the pair MAY publish it" follows step 4, and step 4 covers commit streams too ("For a commit stream, the client carries the stamp in the Commit's routing envelope instead"). Any member holds the admission key, so it can build that routing envelope. The invalid-Commit case is real and not handled. 05:27 makes a committer lose to any earlier `op` that "opens ... to a Commit", and nothing says what happens when the winning Commit fails RFC 9420 §12.4.2 processing. Any member can therefore block every membership change indefinitely. The fix changes 05:27 in three ways. (1) An earlier op counts only if it opens to a Commit that is valid for epoch N under RFC 9420 §12.4.2. Members likewise apply the lowest *valid* stamped Commit. (2) A committer that finds a valid earlier Commit not received within 5 s MUST publish it itself, as the routing envelope that 14-jmap.md:220 allows. Change that MAY to MUST for commit streams. (3) The sender of an invalid Commit counts as misbehaving under the existing policy-violation handling. A member who is being removed can delay a Remove only until its admission key is deregistered (about 300 s, 10-relays.md:839). The real threat is a non-removed member.
- Needs decision: no

### CRY2-3: Envelope `id` covers unsigned bytes, so any forwarder can change it, yet it decides Commit races and message order
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:28, 244, 248; spec/10-relays.md:756; spec/06-calls.md:495; spec/14-jmap.md:114
- Fix: Confirmed. `powProof` is outside `signed` (10-relays.md:756), and any nonce that meets the difficulty is valid. A forwarder can also add an optional `powProof` that was not there. A relay can therefore grind variants of the same `signed` bytes to any desired `id` ordering without the admission key. Under the no-sequencer rule, a member that receives both an honest copy and a ground copy still picks the lowest `id`, so the attack works even when honest relays deliver promptly. "Relays MUST store and forward ... exactly as received" binds honest relays only. There is no deterministic-CBOR requirement for the outer map either. Fix: define `id` as the CIDv1 (raw, SHA2-256) of the `signed` byte string at 05:248. State that `powProof` and the outer encoding are not part of the identity, and change 05:244 and 10-relays.md:756 ("the envelope `id` covers it") to match. Relays still store the full envelope. Dedup, pinning, history and ordering all keep working, because only an admission-key holder can produce new `signed` bytes.
- Needs decision: no

### CRY2-4: SFrame KID layout can make two senders share a KID, which reuses nonces under the shared `base_key`
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/06-calls.md:222, 479
- Fix: Confirmed against RFC 9605 §5.2 (rfc9605.txt:866-867): "Let S be the number of bits required to encode a member index in the group, i.e., the smallest value such that group_size <= (1 << S)." The RFC is itself ambiguous about "group_size". Counterexample: members sit at leaves 0, 1 and 5, so the member count is 3 and S = 2. KID(context 0, index 5) = 0x50+e equals KID(context 1, index 1) = 0x40+0x10+e, which reuses (key, nonce). Correct the citation: the leaf count is defined in RFC 9420 §4.1 ("The _size_ of a tree ... is the number of leaf nodes it contains"; every tree is perfect, with 2^d leaves), not §7.1, which covers ParentNode contents. Fix at 06:222: "S is the depth of the epoch's ratchet tree, that is, the smallest value with (number of leaves, including blank leaves, RFC 9420 §4.1) <= (1 << S)". 06:479 inherits the fix. Add a test vector with blank leaves.
- Needs decision: no

### CRY2-5: The DM admission host accepts any listed member's unordered `DMMembers` replacement, so one member can lock the others out
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:150-158, 259; spec/07-compliance.md:285
- Fix: Confirmed. The only check is "signed per §13.1.1 by a device key of a DID on the current list". There is no freshness or ordering check, and nothing limits whom a signer may drop. A further impact the reviewer missed: a listed member can also drop the compliance logger DID, which cuts the logger off from the admission key. That conflicts with 04-access-control.md:257 ("A self-Remove never removes a compliance logger") and with §7.8.3. Two parts follow from existing rules without a decision: a `ts` freshness and monotonicity check, as for registrations (10-relays.md:813: "within 300 seconds ... and later than the `ts` of the last request it accepted"), and "a replacement MUST NOT drop a logger DID". Who may drop other members is a genuine design choice. Note that 04:259 currently has the *committer* drop the leaver, so allowing only self-drops would need that flow changed too.
- Needs decision: yes. (a) A signer may drop only itself. The leaver PUTs its own drop as part of self-Remove, changing the committer step in 04:259. Drops of others need k-of-n listed signers. (b) Only the initiator, or a successor named in the list, may drop others. (c) Accept the lock-out risk and document it. Recommend (a) with k = 1 for self-drops, plus the no-decision `ts` and logger rules above.

### CRY2-6: Threshold multi-signer objects don't fit §13.1.1, and nothing requires distinct signer DIDs
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:18; spec/13-encoding.md:59, 78, 86
- Fix: Confirmed. §13.1.1 knows only "an entry for every required signer" and rejects "an entry from a signer that is not required". For "at least `threshold` of `guardian.dids`", the required set is undefined. Nothing stops two entries whose `kid`s are different authentication keys of one guardian DID. Fix: add a threshold rule to §13.1.1. The defining section names a candidate DID set and k. The verifier requires entries from at least k distinct DIDs in the set, rejects an object with two entries from the same DID, and rejects entries from DIDs outside the set. Point 04:18 at that rule.
- Needs decision: no

### CRY2-7: Compliance third-party verification can't succeed for `did:key` senders
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/07-compliance.md:142; spec/12-security.md:154; spec/05-messaging.md:73
- Fix: Confirmed. A `did:key` leaf `signature_key` "MUST NOT be the identity key" (05:73), and `did:key` has no DID log, so step 6 always fails for those senders. Fix at 07:142: "For `did:key`, instead verify the `agora_device_binding` extension of `senderLeaf.leafNode` under the key the DID encodes (§5.2.1)." At 12-security.md:154, add that a `did:key` binding cannot be revoked and that every device holds the copied identity key, so the proof shows only that some holder of the identity key vouched for the leaf key. This follows the did:key decision ("no per-device revocation").
- Needs decision: no

### CRY2-8: Public broadcast channels publish `channelToken`, so an IO can map a token to a Space and channel, contrary to ARCHITECTURE §5 item 6
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/03-spaces.md:297, 311; ARCHITECTURE.md:166-169; spec/12-security.md:31, 39; spec/11-transport.md:270
- Fix: The contradiction is real. 03:311 publishes the subscriber form, which carries `channelToken`, as public Space state, against ARCHITECTURE "An IO MUST NOT be able to map an admission key to a Space or channel". But a channel that anyone may read without authentication needs a token that anyone can get, and a relay operator counts as anyone. The reviewer concedes that option (b) "only moves the exposure", and option (c) adds a mechanism to protect metadata of a channel whose content is public. The only consistent fix is therefore (a): qualify ARCHITECTURE §5 item 6, 12-security.md:31 and :39, and 11-transport.md:270 to read "except the tokens of `keyAccess: public` broadcast channels, which the CO publishes". Lowered to P3: this is a wrong privacy claim about channels whose content is already public. Members' data is not exposed.
- Needs decision: no

### CRY2-9: `channelToken` derived from the admission seed mixes two uses of one secret and conflicts with the HSM guidance
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/12-security.md:167 (the part that holds); spec/05-messaging.md:255, spec/13-encoding.md:148 (rejected part)
- Fix: I reject the key-separation part. Deriving a token with HKDF under its own `info` label from a uniformly random 32-byte seed, which RFC 8032 separately hashes with SHA-512, has no attack. The reviewer says "There is no known attack", and the derivation is recorded design (ARCHITECTURE.md:241-243). The HSM conflict is real but independent of how the token is derived. 12-security.md:167 lists "the channel admission private keys the registration service issues" for HSM custody, yet 03-spaces.md:297 and 05:254 serve `seed` to every member. Fix: remove admission keys from the §12.8 HSM list and say that they are secrets shared with all current members, so hardware custody at the CO adds nothing.
- Needs decision: no

## Counts

- CONFIRMED: 5 (CRY2-1, -3, -5, -6, -7)
- CONFIRMED-ADJUSTED: 4 (CRY2-2, -4, -8, -9)
- REJECTED: 0 (the key-separation half of CRY2-9 is rejected inside an adjusted verdict)
- By severity: P1: 1 (CRY2-1). P2: 6 (CRY2-2, -3, -4, -5, -6, -7). P3: 2 (CRY2-8, -9)
- Needs decision: CRY2-1 (recommend stable `commitStreamID`), CRY2-5 (recommend self-drop only plus k-of-n for other drops; the `ts` and logger rules need no decision)
