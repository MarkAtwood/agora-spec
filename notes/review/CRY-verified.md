# CRY verified

Verifier pass over notes/review/CRY.md (25 findings). RFC claims were checked
against /home/mark/PROJECT/IETF/specs/rfc9420.txt, rfc9605.txt and rfc9750.txt.
Binding decisions were checked with `bd kv list` (memory.agora-*). Q1 (countersign
every announcement), D1 (exact bytes), D6 (JWS EdDSA/Ed25519) and Q6 (billing DID)
are the relevant ones. No finding below attacks a decision unless it says so.

### CRY-1: No canonical-Commit rule, and the countersignature does not prevent the lockout it was added for
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:23, spec/05-messaging.md:203-205, spec/04-access-control.md:16, ARCHITECTURE.md:194-201
- Fix: (a) RFC 9420 §14 (rfc9420.txt:5207) says: "Applications MUST have an established way to resolve conflicting Commit messages for the same epoch", and (5219-5221) the Welcome "MUST NOT be delivered to a new joiner until it's clear that the Commit has been accepted". The only ordering text is 05:23 ("Relays MAY provide sequence attestations"), which is optional and is not a conflict rule. `commitPolicy` (04:16) is a MAY and only "recommended" for large channels. The §14.4 sequencer orders JMAP operations, not Commits. (b) 05:204 gates countersigning on "a DID it authenticates as a current member of the channel under Space state, and at most one announcement per chain and `epoch`". The service cannot derive the exporter value, so any current member, including one whose Remove has not yet reached Space state, can claim epoch N+1 with a key only it knows. The "one per epoch" rule then locks out the legitimate committer. That is the lockout the sentence says the countersignature prevents. This does not attack Q1. Q1 chose countersigning, and the finding is that the text's version of it does not deliver Q1's stated purpose ("closes removed-member forgery race"). The proposed fix stands: the announcement names the Commit hash and becomes the canonical-Commit rule; Welcomes are sent only after the countersignature; members verify the announced key against their own derivation; there is a re-registration path on mismatch; losing Commits are discarded.
- Needs decision: yes. The options are as listed in CRY.md: (A) the countersignature names the canonical Commit hash, with member verification and CO re-registration on mismatch; (B) a CO-run MLS member derives the key before countersigning; (C) a single committer. Recommend A. It stays within Q1 and the existing registration service.

### CRY-2: Sealed-envelope AEAD has no nonce rule, under a key shared by every member for the whole epoch
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:214-220
- Fix: The text defines the key (`MLS-Exporter("agora sealed envelope", channelCID, Nk)`) and the AAD but no nonce and no byte layout. The word "nonce" appears in §5 only for broadcast (05:141-144). Every member shares the key for the whole epoch, so any deterministic per-sender nonce collides across senders under AES-128-GCM. Define `sealedEnvelope = nonce(12, random) || AEAD-Seal(...)`, mirroring 05:141-144. One correction to the suggested fix: no single sender can count seals across all members, so a "new epoch before 2^32 seals" rule cannot be enforced. Make the bound a per-sender SHOULD, and rely on the §12.2 7-day epoch cap for the aggregate.
- Needs decision: no

### CRY-3: SFrame (base_key, KID, CTR) uniqueness is not guaranteed across streams or restarts; RFC 9605 §5.2 is misdescribed
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/06-calls.md:160, spec/06-calls.md:410
- Fix: The core defect is real. RFC 9605 §9.1 (rfc9605.txt:1187) says: "Applications MUST ensure that each (base_key, KID, CTR) combination is used for at most one SFrame encryption operation". 06:160 says the KID "is built from the leaf index and the low bits of the MLS epoch", which reads as context ID 0 for every track. Nothing covers multiple tracks per sender or CTR loss on a reload within one epoch. Two adjustments. (1) The "misdescribed / pre-RFC draft" charge is overstated. RFC 9605 §5.2 itself uses the term "sframe_epoch_secret" (rfc9605.txt:884), and 06:160 defers to "as RFC 9605 Section 5.2 specifies". Only the phrase "each sender's base key is derived from it and the sender's MLS leaf index" is wrong: the RFC has one base_key per epoch, and per-KID keys are derived from it. Correct that one phrase. (2) RFC 9605 §9.1 makes CTR persistence conditional ("In applications where an SFrame context might be written to persistent storage"). So require one of two things: persist CTR per (epoch, KID) before use, or, after CTR state is lost, use a context ID not used before in that epoch (simpler than a forced Update Commit). Require a distinct context ID for each outbound track and data channel.
- Needs decision: no

### CRY-4: KeyPackage init keys are described as coming from the long-term DID `keyAgreement` key
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/02-identity.md:44, spec/02-identity.md:74, spec/02-identity.md:314
- Fix: RFC 9420 §10 (rfc9420.txt, Key Packages) requires that init_key "MUST be unique among the set of KeyPackages created by this client". 02:44, 02:74 and 02:314 describe the DID `keyAgreement` key as the "source" of init keys. This is downgraded from P1 because the spec elsewhere contradicts a reuse reading. 05:67 says "reuse lets two groups share HPKE init secrets", and 05:117 forbids giving groups "the same HPKE init key". So the defect is contradictory text, not mandated reuse. Fix as proposed: init_key and leaf encryption_key are fresh per KeyPackage and unrelated to the DID document; `keyAgreement` serves only out-of-group HPKE. 06:345 (recorder archive sealing to the recorder's `keyAgreement` key) is a legitimate out-of-group use and needs no change. 12:95 already scopes `keyAgreement` to recovery shares and HPKE.
- Needs decision: no

### CRY-5: Hardware-key requirements cannot be met for Ed25519/X25519 on major platforms, and the ES256 escape hatch contradicts the fixed algorithms
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/12-security.md:89, spec/12-security.md:91, spec/02-identity.md:255, spec/02-identity.md:316, spec/12-security.md:122, spec/12-security.md:147; vs spec/13-encoding.md:59, spec/05-messaging.md:46
- Fix: The contradiction is real. 12:89 says "P-256 (`ES256`) MAY be used as the authentication key algorithm", but 13:59 fixes `alg` to `"EdDSA"` and 05:46 fixes ciphersuite 0x0001 (Ed25519). An ES256 device can produce neither a JWS nor an MLS leaf signature. 02:255 ("generated inside the device's secure hardware boundary (Secure Enclave, StrongBox, TPM) and never leave it") is unconditional. 12:122 and 12:147 rest on it. Note that 12:80 already defines a non-extractable WebCrypto key as "the secure boundary" for browsers, so the 12:91 MUST can be read loosely. 02:255 and 12:122 cannot. Adjustment: decision D6 ("Ed25519 (RFC 8037)") already excludes option B, so the fix follows from existing rules. Delete the ES256 MAY. Reword 02:255, 12:91 and 12:122 to "hardware-backed where the platform supports Ed25519/X25519, otherwise an OS-protected non-extractable key". Weaken 12:147 to match.
- Needs decision: no (D6 settles it; option C, a hardware P-256 key attesting a software Ed25519 key, can be raised later as an extension)

### CRY-6: Nothing stops relays accepting previous-epoch access signatures, so a removed member keeps write access
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:205-208, spec/10-relays.md:527
- Fix: The retirement rule exists only by implication. 05:205 ("A member removed after the last countersigned epoch can write until then") presumes that relays stop accepting the old key once a later announcement is accepted, but no sentence requires it. 05:206 only requires verification "against the access public key for the envelope's `channelToken` and `epoch`", which an epoch-N envelope on token N still satisfies. Add a normative rule. After accepting a countersigned announcement for epoch N+1 on a chain, a relay MUST reject envelopes for epoch N or earlier on that chain once a fixed grace period has passed. The grace covers in-flight traffic and members still processing the Commit, which 05:23 makes them buffer. State that the grace period is the removed member's residual write window. Choosing the value (for example 60 s) is a parameter, not a design choice.
- Needs decision: no

### CRY-7: The shared epoch access key signs several structures with no domain separation; the SFU admission proof is undefined and replayable
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/06-calls.md:111, spec/06-calls.md:119, spec/05-messaging.md:203, spec/05-messaging.md:206, spec/05-messaging.md:368
- Fix: Split the finding. (a) The SFU proof is undefined (P2). 06:111 says the client "presents the MLS-membership access proof", and 06:119 says it "uses the epoch access proof (§5.2.2)". But §5.2.2 defines only envelope signatures, with no challenge, so whatever is presented is either a replayable gossiped envelope or an undefined signature over SFU-chosen bytes. Defining the proof as a signature over a context string, the SFU DID, a fresh SFU nonce and the `channelToken` closes both. This is a text gap, not something only the agora-pozi.8 external review can settle. (b) Domain separation (P3 on its own). No concrete cross-structure collision can be shown, because none of the signed structures has a defined encoding yet (see CRY-8). Distinct context prefixes are still the right fix and cost nothing once CRY-8 defines encodings.
- Needs decision: no

### CRY-8: The routing-envelope signing input is undefined, `id` is circular, and the "ts not authenticated" claim is wrong
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:181-196, spec/05-messaging.md:204, spec/05-messaging.md:313, spec/10-relays.md:673
- Fix: 13:9 says "Agora computes no canonical form", yet 05:206 signs "the routing envelope with `accessSig` omitted", which is a JSON object (05:181-191) with no byte encoding, so no two implementations produce the same input. 05:204 says `billingSig` is "signed per §13.1.1 over the announcement with `billingSig` omitted", but §13.1.1 signs an envelope `body` (13:49, 13:68), and the announcement is not one. `id` is "the CID of the canonical outer envelope" (05:196) while also being a member of it. PoW hashes `envelopeBytes` (10:673) while `powProof` sits inside the envelope. `ts` and `expiryHint` are covered by `accessSig`, so they are authenticated to "some current member", contrary to 05:196 and 05:313. Fix as proposed. It is consistent with D1 ("signatures over exact bytes"): fixed CBOR signing input excluding `id`, `accessSig` and `powProof`; `id` computed over the signed bytes; the announcement as a typed envelope `urn:agora:type:AccessKeyAnnouncement`; corrected `ts`/`expiryHint` sentences.
- Needs decision: no

### CRY-9: Cross-epoch unlinkability claims contradict the chain-following design (and ARCHITECTURE §5)
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:518, spec/12-security.md:34, spec/12-security.md:40, spec/12-security.md:46, spec/05-messaging.md:133, spec/05-messaging.md:216
- Fix: 05:203 says "The relay thereby follows the chain from token to token". ARCHITECTURE §5 item 6 lists "which access-key chains (§6.2) are registered under each agreement" as within the IO budget. Yet 10:518 says a relay "cannot correlate them without also capturing the epoch secrets", and 12:34 says it cannot "Map routing tables across epochs". Both are false. 05:216 claims the wrapper hides "epoch boundaries and which messages are Commits", but the routing envelope carries `epoch` in clear (05:186), and the announcement rides on the envelope carrying the Commit (05:203). 05:133 ("tokens of different key epochs are unlinkable") is false for broadcast because of 05:136. Rewrite as proposed: chains are linkable but not mappable to a channel or Space; epoch numbers and Commits are visible; the wrapper hides `group_id`, `content_type` and sender data. Remove or qualify the decoy rationale at 12:46.
- Needs decision: no

### CRY-10: DM groups have no defined exporter context, chain registration or countersigner
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:125, spec/05-messaging.md:194, spec/05-messaging.md:202-204, spec/05-messaging.md:218, spec/10-relays.md:612
- Fix: The access seed (05:202), channel token (05:194) and sealing key (05:218) all take `channelCID` as exporter context. A DM has no `channelCID`, and its `DMGroupCID` changes on each membership change (04:145). 04:125 gives a separate `dmGroupToken` with context `""`, but no access seed or sealing key for DMs. 05:204's countersign gate is "a current member of the channel under Space state", which does not exist for DMs, which "do not appear in any Space state document" (04:125). Nothing says which billing DID registers a DM chain. One note on the fix: using the MLS `group_id` as exporter context is compatible with 04:125's ban on deriving the token "from the MLS group ID". The exporter output still rotates per epoch, so the reworded rule must say "not derived from a constant value alone".
- Needs decision: yes. The options are as listed in CRY.md: (A) the creator's CO registers and countersigns, relying on DM membership asserted by the requester; (B) DMs are exempt from the access proof; (C) the regulated member's CO. Recommend A, with the caveat that an individual with no CO needs a fallback (a user-chosen registration host, in parallel with Q3's KeyPackage host).

### CRY-11: MLS credential format and Authentication Service checks are undefined; KeyPackage validation is assigned to the wrong party
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:55, spec/05-messaging.md:77-84, spec/02-identity.md:43, spec/02-identity.md:80
- Fix: Neither `BasicCredential` nor any other credential type appears anywhere in spec/. 05:77 tells "Recipients of a Welcome" to validate "the KeyPackage used to construct it". That is their own KeyPackage, so the check proves nothing. RFC 9420 §10.1 places that check on the adder, and §12.4.3.1 requires the joiner to validate the tree. 05:65 makes the KeyPackage host check the credential, which is necessary but does not replace the member-side checks. No text requires leaf `signature_key` to be a current `authentication` method of the credential's DID at Add, Update and path. 02:43 ("Ed25519 key used to sign all protocol messages") conflicts with per-device keys at 02:80. Fix as proposed.
- Needs decision: no

### CRY-12: Client-side rejection of valid Commits has no fork semantics; the DM consent model is not implementable in MLS
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:159, spec/04-access-control.md:103
- Fix: 04:159 says "The Add is not committed until a configurable consent threshold of existing members issues a matching Commit". One Commit per epoch makes "a threshold of matching Commits" impossible. The alternative "or explicit approval signal" is undefined. 04:103 says "Clients MUST reject a Commit that adds a DID with a standing `BanRecord`". Under RFC 9420 §14, a member that refuses the canonical Commit is left on a dead branch, and the spec gives no next step. Fix as proposed: define the approval signal as signed application messages that must precede the Commit, and define the reaction to a policy-violating Commit (leave, alert the user, recreate the group). The location 04:78 in CRY.md is not affected, because it constrains a joiner before it has any state.
- Needs decision: no

### CRY-13: Passive members can never update their leaf, so post-compromise security is permanently lost for the most exposed keys
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:113, spec/07-compliance.md:88, spec/07-compliance.md:199; vs spec/12-security.md:14
- Fix: The problem is real. A passive member "MUST NOT issue Commits or Proposals" (05:113), so its leaf HPKE key never changes. Every UpdatePath that covers it encrypts to that key, and compromising one logger yields path secrets in every group it belongs to indefinitely. That contradicts 12:14. Adjustment: the alternative fix in CRY.md ("require admins to Remove and re-Add the logger periodically") conflicts with 07:199, which says "no member ... MAY issue an MLS Remove commit for the logger DID for the duration of the regulatory retention period" in DMs. The fix therefore does not follow mechanically. It requires either changing the passive-member contract or carving an exception into 07:199.
- Needs decision: yes. Options: (A) allow passive members a scheduled self-update Commit (empty Commit with path) and forbid all other proposals; (B) periodic Remove and re-Add, with an exception in 07:199 for an immediate re-Add by the same principal. Recommend A: it keeps 07:199 intact and needs no admin action. In both cases, state the residual risk in §12.2.

### CRY-14: The sequencer receives raw MLSMessage bytes, which expose `group_id` and `epoch`
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/14-jmap.md:158-159, spec/14-jmap.md:193
- Fix: 14:158 says "The resulting MLS message bytes are the **operation**", and 14:159 POSTs them raw. An RFC 9420 PrivateMessage carries `group_id`, `epoch` and `content_type` in clear. 05:216 says those are what the wrapper hides from IOs, and 14:193 ("learns no member identity, membership or content") does not disclose the constant `group_id`, which links streams across epochs. Wrap the operation in the §5.2.2 sealed envelope bound to `stream`. Adjustment: 14:166 already says "copies are deduplicated by `opHash`". The missing part is only that deduplication MUST happen before MLS decryption, because the RFC 9420 §9.2 deletion schedule makes a second decryption of the same PrivateMessage fail.
- Needs decision: no

### CRY-15: Overclaim that media is bound to a DID through an SFU
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/06-calls.md:74, spec/06-calls.md:178, spec/06-calls.md:182
- Fix: RFC 9605 §6.1.1 (rfc9605.txt:953-955) says: "in order to prevent impersonation by a malicious participant (not the SFU), a mechanism based on digital signature would be required. SFrame does not protect against such attacks". §7.2 says the same. 06:182 claims "Participant-to-participant binding is then provided by the SFrame keys", and 06:74 claims a stream is "cryptographically bound to their DID" without qualification. 06:412 already states the correct property for data channels. Restrict the DID binding to mesh DTLS-SRTP, and state group-only authentication for SFU media.
- Needs decision: no

### CRY-16: Non-repudiation claim is not supported by the archive format
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/12-security.md:123, spec/12-security.md:147; vs spec/07-compliance.md:94-109
- Fix: 12:123 says "The signing key fingerprint is embedded in the message's MLS authenticated data". Nothing defines such a field (a grep for "authenticated_data" and "fingerprint" finds no definition). The `ComplianceRecord` (07:96-108) stores `plaintextPayload`, the decrypted inner envelope, plus the logger's JWS. It keeps no sender signature, FramedContent, leaf `signature_key` or GroupContext, so a third party cannot re-verify the sender as 12:147 claims. In-group objects carry no `sig` (13:23).
- Needs decision: yes. The options are as listed in CRY.md: (A) archive the verification material; (B) weaken the claim to logger attestation. Recommend A if 17a-4 authenticity claims are to stand; otherwise B.

### CRY-17: JWS verification does not say which DID-document state a key is checked against
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/13-encoding.md:76
- Fix: 13:76 resolves `kid` with no time reference. Only 02:163 ("the DID document in effect before the assertion") states one. Archived compliance records, agreements and Space state signed by a later-revoked device key either fail verification or keep verifying for new objects, depending on how an implementer reads it. Fix as proposed: check new objects against the current document, and stored objects against the version recorded at acceptance (`versionId` or PLC operation CID). Revocation is not retroactive.
- Needs decision: no

### CRY-18: did:webvh split-view and rollback are unaddressed; "auditable without trusting the organization" is overstated
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:23, spec/02-identity.md:255, spec/12-security.md:135
- Fix: 02:23 and 12:135 claim that the organization "cannot rewrite or hide the entry without producing an invalid history". Hash chaining prevents an invalid single history. It does not prevent serving a different valid fork, signed with the org's own update key, to a targeted resolver, or serving a stale prefix. 02:241's conflict rule only helps a resolver that sees both entries. A grep finds no "witness" or "watcher" anywhere in spec/, although did:webvh v1.0 defines both for this purpose.
- Needs decision: yes. The options are as listed in CRY.md: (A) require witnesses for employer-hosted DIDs; (B) gossip log heads; (C) weaken the claim. Recommend A for CO-provisioned identities, plus C's wording for individuals who do not use witnesses.

### CRY-19: A `RecoveryAssertion` can be replayed; nothing binds it to the identity state it replaces
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/02-identity.md:153-163, spec/02-identity.md:243, spec/02-identity.md:467
- Fix: Narrow the scope. For self-hosted did:webvh, a replayed assertion changes nothing by itself, because the device key enters the document only through a log entry signed with the update key (02:123). The replay works against the provisioning service, which "accepts a `RecoveryAssertion` as equivalent to an IdP token" (02:467). The assertion is published to discovery (02:163). The recovery key is never rotated after use, and the social-recovery key only "SHOULD" be (02:198), so the old assertion still verifies against the current document. The 24-hour rule at 02:243 bounds the window but does not close it. Fix as proposed: add `prev` (`versionId` or PLC operation CID) and reject an assertion whose `prev` is not the current head.
- Needs decision: no

### CRY-20: Backing up MLS state undermines forward secrecy and risks nonce reuse on restore; the "stateOnly" claim is wrong
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/02-identity.md:220, spec/02-identity.md:225, spec/02-identity.md:229, spec/02-identity.md:469; vs spec/12-security.md:10
- Fix: Drop the nonce-reuse leg. RFC 9420 (rfc9420.txt:1843-1845) says the 4-byte random `reuse_guard` "is used to avoid nonce reuse in the case of state loss or corruption", which is exactly this restore case. The rest stands. A snapshot retains keys that the RFC 9420 §9.2 deletion schedule requires to be deleted, which is a forward-secrecy exception that 12:10 does not mention. Rewound sender generations would in any case be refused by receivers that have already deleted those keys, so "restores MLS continuity" (02:229) is false. A "stateOnly" backup lacks the leaf signature key and cannot send. The exporter (§8.5) derives secrets and does not export state, and RFC 9420 §11 is Group Creation. Fix as proposed: no live ratchet state in backups; rejoin as a new leaf.
- Needs decision: no

### CRY-21: Device enrollment has no proof of possession of the new key
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:336
- Fix: 02:336 says the request "is signed per §13.1.1 by an existing registered device key. For first-device enrollment the envelope `sig` is absent". The new key never signs, so a holder of an IdP token can register any public key, including one that belongs to someone else. The impact is limited to duplicate-key and unknown-key-share confusion, because the registrant cannot sign with the key, hence P3. Add a self-signature by the new key over the request, bound to the IdP token nonce.
- Needs decision: no

### CRY-22: Underspecified parameters in several primitives
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:211-212, spec/02-identity.md:231, spec/02-identity.md:171, spec/12-security.md:82-83, spec/06-calls.md:215
- Fix: All four gaps are present as described. The backup has no salt length or nonce, and its self-describing header (02:231) is not bound as AAD. Share encryption (02:171) names no scheme. The PRF wrap (12:82) gives no salt, HKDF info or IV. The TURN `HMAC(secret, username)` (06:215) names no hash. Fix as proposed.
- Needs decision: no

### CRY-23: The broadcast content key is used both as an AES key and as HKDF input
- Verdict: REJECTED
- Severity: P3
- Location: spec/05-messaging.md:133, spec/05-messaging.md:141
- Fix: Rejected as too speculative. The finding concedes "No practical attack is known". HKDF-Extract with an empty salt is HMAC-SHA256 keyed with zeros over `key`, a PRF evaluation whose output (the token) reveals nothing usable about `key` as an AES-GCM key. No interaction between HMAC-SHA256 and AES under the same key is known. For `keyAccess: public` channels the key is public in any case (05:131). Deriving separate subkeys costs little, but it is optional cleanup, not a defect. Raise it again only if the broadcast format is reworked for another reason.
- Needs decision: no

### CRY-24: External commits and external proposals are not addressed
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/05-messaging.md:48-53
- Fix: The gap is real. A grep finds no "external commit", "new_member" or "external_pub" in spec/, so a conforming client would accept a valid `new_member_commit` (RFC 9420 §12.4.3.2). Adjustment to the threat: no Agora flow publishes GroupInfo, and external proposals already require an `external_senders` extension (§12.1.8). An outsider can therefore join only if a current member leaks GroupInfo with `external_pub`. That route skips the joiner-side adder check of 04:78, which a colluding joiner could ignore in any case, hence P3. Fix as proposed: clients MUST reject `new_member_commit`, `new_member_proposal` and `external` senders, and MUST NOT include `external_pub`.
- Needs decision: no

### CRY-25: RFC section citations are wrong
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:55, spec/02-identity.md:225, spec/12-security.md:93
- Fix: Checked against rfc9420.txt headings. §10 is Key Packages and has only §10.1, so §10.3 does not exist. §11 is Group Creation and has only §11.1-§11.3, so §11.5 does not exist. Exporters is §8.5 (rfc9420.txt:3210). The DS and AS roles are defined in RFC 9750. Cite RFC 9420 §8.5 and RFC 9750.
- Needs decision: no

## Counts

- CONFIRMED: 14 (CRY-1, 2, 8, 9, 10, 11, 12, 15, 16, 17, 18, 21, 22, 25)
- CONFIRMED-ADJUSTED: 10 (CRY-3, 4, 5, 6, 7, 13, 14, 19, 20, 24)
- REJECTED: 1 (CRY-23)
- Severity after adjustment (excluding the rejected finding): P1 = 4 (CRY-1, 2, 3, 5); P2 = 16; P3 = 4 (CRY-21, 22, 24, 25)
- Needs decision: CRY-1, CRY-10, CRY-13, CRY-16, CRY-18 (CRY-5 moved to "no" because of D6; CRY-13 moved to "yes" because of the 07:199 conflict)
