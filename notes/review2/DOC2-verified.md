# DOC2 verified

Verifier pass over notes/review2/DOC2.md at HEAD 9e7711f. Every cited location was opened. Each finding was checked against spec/, ARCHITECTURE.md and the bd memories (Q2, Q3, Q6, doorkey-B, did-methods, stable-did, recording-consent).

### DOC2-1: Relay guide's restore procedure brings back deregistered admission keys
- Verdict: CONFIRMED
- Severity: P1
- Location: guides/relay-operator.md:1614 (§8.5 step 7), :1481 (§8.1 Database row); spec/10-relays.md:644
- Fix: Spec §10.4.7 says: "MUST NOT reinstate admission key registrations from the backup ... It starts with no registrations and answers `unknown-token` for every token". Guide step 7 says instead: "A restored database holds the registrations of the backup time: keys the CO deregistered since then are admitted again". Rewrite step 7 to match. After a restore, purge every registration and per-token `ts` record, answer `unknown-token`, and notify each agreement's `contact` that registrations were lost. Restored envelopes and blobs may be kept within retention and served once their token is re-registered. In §8.1, mark the registration and `ts` state as backed up for audit only and never restored. A side effect of the purge: dropping `ts` state is safe because the CO re-registers with fresh requests.
- Needs decision: no

### DOC2-2: Relay guide says a relay cannot suspend a token
- Verdict: CONFIRMED
- Severity: P2
- Location: guides/relay-operator.md:1060, :2373, §17.2 table (:2365-2371), metric `cause` labels (:1195); spec/10-relays.md:642; spec/11-transport.md:188
- Fix: The guide says "There is no admin operation that suspends or blocks a token" and "The relay has no control that blocks a single token". Spec §10.4.7 says "A Relay MAY stop admitting ... for one registered `channelToken` ... MUST notify the CO", and §11.4 lists suspension as a `token-withdrawn` cause. Apply the reviewer's fix as written: add a suspend/lift admin operation, a §17.2 row, a `suspended` cause label and the mandatory `contact` notice, and delete both "no control" sentences.
- Needs decision: no

### DOC2-3: Relay guide's retirement procedure uses an invented `maintenance` field and drains early
- Verdict: CONFIRMED
- Severity: P2
- Location: guides/relay-operator.md:2225-2238 (§16.2), :2242-2254 (§16.3); spec/10-relays.md:112, :646
- Fix: `retiresAt` appears nowhere in the guide. The CO notice is framed "as the agreement's notice terms require", but the spec makes it a 30-day MUST, with an exception only for an out-of-band agreement. §16.3 refuses new connections, which contradicts "Until `retiresAt` the Relay keeps admitting registered tokens." Apply the reviewer's fix: set `retiresAt` at least 30 days ahead, notify every `contact` at the same time, and drop `maintenance` or demote it to an optional hint. Start the drain at `retiresAt`, or earlier only for tokens whose COs have already deregistered.
- Needs decision: no

### DOC2-4: Counsel and regulators guides promise attachment capture the spec does not provide
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/07-compliance.md:171 (scope) and §7.4 (fix site); guides/counsel.md:33; guides/regulators.md:65
- Fix: The gap is real. spec/07 mentions attachments only in the scope line, and no text has the logger fetch, decrypt or retain a blob. The guides' claim "The CID matches the original's" describes the retired design: per 05-messaging.md:317, the CID now hashes ciphertext and `sha256` covers the plaintext. Adjustment: the design choice is already made. §7 scope says §7.1-§7.5 "cover ... file attachments", so option (a) only implements an existing commitment. Add to §7.4: on archiving a Message with attachments, the logger fetches each blob (§10.4.4), decrypts it with `contentKey`, checks `sha256`, stores it re-sealed under the archive key, and records a failed fetch as a capture gap. Then say in both guides that integrity is shown by the `sha256` in the archived signed Message, not by the CID. Option (b) would contradict the existing scope line.
- Needs decision: no (the §7 scope line settles it in favour of option a)

### DOC2-5: Identity-host DM agreements are an undocumented anonymity cost
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: ARCHITECTURE.md §9 (:392-397); spec/12-security.md:53; PRFAQ.md:31
- Fix: The core point is real. Under §10.5.3 an individually chosen identity host registers under "its own billing DID ... acting as the CO". A single-user host therefore puts all of that person's DM and self-group tokens under one billing DID, and §9 and the PRFAQ address only Spaces. Rejected part: the claim that the relay can "distinguish them ... by type" in contradiction to §12.4. That sentence of §12.4 concerns presence and typing versus other messages, and the same paragraph already says "a Relay learns whose agreement covers a DM token". Options (b) and (c) change the decided design. Memory agora-doorkey-B says "DMs via initiator's identity host", and Q6 rests the anonymity set on the CO, so the fix follows from existing rules. Extend the §9 bullet "Space anonymity at the IO is only as large as the CO" so it also covers an identity host acting as CO for DM groups and self-groups: its anonymity set is its users, and a single-user host gets none. Add one clause to PRFAQ "What does the relay operator see?". No change to §12.4 is needed beyond an optional cross-reference.
- Needs decision: no

### DOC2-6: Guides cite §7.8.2 for the message-request capture rule
- Verdict: CONFIRMED
- Severity: P3
- Location: guides/counsel.md:43; guides/regulators.md:205
- Fix: §7.8.2 is the generic Add procedure. The message-request rule is in spec/04-access-control.md §4.6.3 "Regulated members" and spec/07-compliance.md §7.8.7 "Message requests". Cite "spec §4.6.3, §7.8.7" in place of §7.8.2.
- Needs decision: no

### DOC2-7: HTTP proof-of-work text calls the sequencer a CO endpoint
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:760; ARCHITECTURE.md:61, :158-160
- Fix: The spec reads "A CO HTTP endpoint ... such as ... a sequencer (§14.4)", while ARCHITECTURE lists "Sequencer | IO". Apply the reviewer's rewording, and extend ARCHITECTURE §5 item 3 to cover HTTP proof of work (§10.5.2).
- Needs decision: no

### DOC2-8: PROPOSAL still calls the guides "pending revision"
- Verdict: CONFIRMED
- Severity: P3
- Location: PROPOSAL.md:71
- Fix: Drop "(pending revision)" once DOC2-1 to DOC2-3 land.
- Needs decision: no

### DOC2-9: CORUNDUM profile says the combined-operator cost is not yet in ARCHITECTURE
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/corundum.md:38; ARCHITECTURE.md:405-408
- Fix: The ARCHITECTURE §9 bullet exists. Replace "That text is not in ARCHITECTURE.md yet." with "ARCHITECTURE §9 lists it as an accepted cost."
- Needs decision: no

### DOC2-10: Chain-witness profile records pruning as a `ComplianceRecord`
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/compliance-chain-witness.md:89-91; spec/07-compliance.md:96-133
- Fix: §7.4 gives `ComplianceRecord` mandatory per-message fields (`senderDID`, `plaintextPayload`, `senderMessage`, `messageKeys`, `groupContext`, `senderLeaf`) and a third-party check that "MUST treat the record as unverified if any step fails". A prune statement fails that check. Apply the reviewer's fix: a practice type such as `urn:agora:practice:CompliancePruneRecord`, signed by the logger DID and chained by `prevRecordCID`, which verifiers exempt from the sender check.
- Needs decision: no

### DOC2-11: Relay guide key-loss text treats the relay DID as derived from the key
- Verdict: CONFIRMED
- Severity: P3
- Location: guides/relay-operator.md:1478, :1491, :1509; compare :284-289, :1789
- Fix: The guide's own default is `relay_did = "did:web:..."`, and :1789 explains that did:web keeps the DID across key changes. Limit "the relay DID is permanently lost", "There is no recovery path" and "The DID is derived from the public key" to `did:key` relays. For did:web, recovery means publishing a new key in `did.json` and the manifest.
- Needs decision: no

### DOC2-12: Tor mapping cannot serve the advertised `ws://` onion endpoint
- Verdict: CONFIRMED
- Severity: P3
- Location: guides/relay-operator.md:1908, :1916
- Fix: `HiddenServicePort 80 127.0.0.1:443` sends plaintext `ws://` traffic to the TLS listener. Forward onion port 80 to a plaintext WebSocket listener bound to loopback, or advertise `wss://` on onion port 443. The first matches the spec's `ws://` onion examples (spec/10-relays.md:64, :713).
- Needs decision: no

### DOC2-13: Universal-IdP profile omits the sidecar's admission-key host role
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: profiles/universal-idp-did.md:22, :686-697
- Fix: The profile "extends the DID Sidecar's `IdentityProvider` interface" and "Depends On ... O365 DID Spec", so the O365 §6.7 duties are arguably inherited. That lowers the severity. The concrete defect is the reverse-proxy list, which claims to expose "only the public endpoints" and leaves out `/v1/admission-key/*` and `/v1/auth` (O365:602-606). Under that topology, DMs and self-group admission fail. Add those paths to the proxy list, and add one sentence at :22 deferring to O365 §6.7.
- Needs decision: no

### DOC2-14: Discord onboarding omits identity-host admission-key and agreement duties
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: profiles/discord-onboarding.md:45-48, :527
- Fix: The omission is real (grep finds no "admission" or "ServiceAgreement" in the host description). Severity is lowered because the profile's scope is Space enrollment, and the host duties are defined normatively in spec §4.6 and §10.5.3. Apply the reviewer's fix: list the admission-key endpoints and the host's own ServiceAgreements and billing DID among host requirements, and extend the "Identity host" privacy item to cover DM member DIDs (spec §12.4, §12.11).
- Needs decision: no

### DOC2-15: Spec §2.4 requires recovery keys as update keys for every did:webvh, contradicting §2.5.8
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/02-identity.md:128 (fix site); profile o365-employer-did.md:149, :194 is correct
- Fix: The contradiction is real. Adjustment: the spec already distinguishes the two cases. :171 says "for a self-hosted `did:webvh` the recovering client writes the new device key into the log ... and for a CO-provisioned identity it submits the assertion to the provisioning service (§2.5.8)", and §2.5.8 says the recovery key "cannot override an organization-initiated `revokeAll`". The rationale of the :128 MUST ("so that the device key ... is written into the document by a log entry signed with the same key") applies only to the self-hosted path. Scope the :128 MUST to self-hosted (individually held) did:webvh. For CO-provisioned DIDs, recovery keys are `recoverableIdentity` only and the provisioning service writes the entry. Option (b) contradicts :171 and §2.5.8.
- Needs decision: no

### DOC2-16: Purview bridge never receives `ComplianceGapEntry` or `ArchiveResealEntry`
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/purview-bridge.md:403-406, :548-559, :586-598; spec/07-compliance.md:312-325, :374-386
- Fix: The §8.3 stream schema carries only `ComplianceRecord`s plus blobs. Yet §9.2 alerts on `DMComplianceAuditEntry.removalAttempts`, and §5 reads `VTCComplianceAuditEntry` "from the recorder's record stream", so audit entries are used without being specified. `ComplianceGapEntry` and `ArchiveResealEntry` are never mentioned. §5.2 step 3 ("sealed form matches its `mediaCID`") fails for re-sealed media, per spec :374 ("Re-sealing changes the CID ... the signed record cannot change"). Apply the reviewer's fix.
- Needs decision: no

### DOC2-17: Purview bridge describes the retired group-encrypted attachment blob
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/purview-bridge.md:300; spec/05-messaging.md:317
- Fix: Replace "CID of a group-encrypted blob ... Only a group member can decrypt it" with content-key decryption using the captured Message's `contentKey`, verified against `sha256`. Note that Exchange items carrying the Message are plaintext-equivalent for attachments. The logger's fetch duty depends on the DOC2-4 spec fix.
- Needs decision: no

### DOC2-18: gsuite profile still relies on a custom `AgoraDIDAdmin` OAuth scope
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/gsuite-employer-did.md:299, :410; contradicted by :446
- Fix: :299 "Google OAuth token with the `AgoraDIDAdmin` scope (§7)" contradicts :446 "No custom OAuth scope", and §7 defines no admin mechanism. Authorize admin calls by mapping the token `sub` to a sidecar admin list or Google group, and define the `AgoraDIDAdmin` "role" at :410 as that sidecar-side mapping.
- Needs decision: no

### DOC2-19: Employer profiles leave out the `AgoraProvisioning` service entry
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: profiles/o365-employer-did.md:247-258 (active-document example only); profiles/universal-idp-did.md:22, :40
- Fix: The O365 genesis already includes the entry (:170, :190), so O365 is only internally inconsistent: the post-enrollment example drops it. Universal l.640 uses `{prov}`, but the stub text at :40 says "one `KeyPackageEndpoint` service entry". Add `AgoraProvisioning` to the O365 active-document example and to universal :22 and :40.
- Needs decision: no

### DOC2-20: O365 profile registers DM admission keys only with relays
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/o365-employer-did.md:679; spec/10-relays.md:684-686, :777
- Fix: Spec: "with every IO that holds a `ServiceAgreement` with it whose `serviceType` receives registrations". Reword to "every IO (relay, SFU, sequencer) whose agreement receives registrations (spec §10.5.3)".
- Needs decision: no

### DOC2-21: Five profiles use BCP 14 key words and carry no non-normative banner
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/o365-employer-did.md:1, gsuite-employer-did.md:1, universal-idp-did.md:1, discord-onboarding.md:1, purview-bridge.md:1; README.md:22 marks profiles/ non-normative
- Fix: The headers read "# Specification:" or "Implementation Specification v0.1" and carry no banner. The other four profiles open with "> Non-normative." Under the reviewer's option (a), the o365:190 tightening (MUST where spec §2.5.2 :291 says SHOULD) is legitimate, because it binds only conformance to the profile.
- Needs decision: yes. Options: (a) add the standard banner ("Non-normative; where it conflicts with the spec or ARCHITECTURE.md, those govern") and state that key words bind only implementations that claim conformance to the profile; (b) lowercase the key words, matching the DOC-9 relay-guide precedent (reconciliation.md:207). Recommendation: (a). These are implementation specs for sidecars and bridges where profile-level conformance is useful, and it is the smaller change. The DOC-9 precedent covered a guide, not an implementation profile.

## Counts

- CONFIRMED: 15 (DOC2-1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 16, 17, 18, 20, 21)
- CONFIRMED-ADJUSTED: 6 (DOC2-4, 5, 13, 14, 15, 19)
- REJECTED: 0 (the §12.4 "distinguish by type" sub-claim of DOC2-5 was rejected inside an adjusted finding)

Severity after adjustment: P1 1 (DOC2-1); P2 6 (DOC2-2, 3, 4, 5, 15, 16); P3 14.

Needs decision: DOC2-21 only. DOC2-4, DOC2-5 and DOC2-15 were downgraded to no, because the §7 scope line, the doorkey-B/Q6 decisions and spec/02:171 with §2.5.8 settle them.
