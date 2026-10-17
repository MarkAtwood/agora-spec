# CLM review: claims in README, PROPOSAL, PRFAQ, ARCHITECTURE vs the spec

Lens: factual and technical claims in the four top-level documents, checked
against spec/; stale claims after the 2026-10-16 decisions; PRFAQ dateline and
footer; ARCHITECTURE internal references.

### CLM-1: Spec claims cross-epoch unlinkability that the access-key chain removes by design
- Severity: P2
- Location: spec/10-relays.md:518; spec/12-security.md:34, 40, 46; spec/05-messaging.md:186, 216. Governing text: ARCHITECTURE.md:157-160 (§5 item 6), 196-198 (§6.2)
- Evidence: 10.4.2 "A Relay that captures routing tables across epochs cannot correlate them without also capturing the epoch secrets"; 12.3 a Relay cannot "Map routing tables across epochs without MLS group secrets"; 12.4 "long-term correlation requires capturing multiple epochs' tokens"; 05 l.216 the sealed envelope exists because `group_id` "could link every epoch of a channel" and "`epoch` and `content_type` would reveal epoch boundaries and which messages are Commits". Against: 05 l.203 "The relay thereby follows the chain from token to token"; the outer `RoutingEnvelope` carries `"epoch": 17` in the clear (l.186); only Commit-carrying envelopes carry an `accessKeyAnnouncement`.
- Problem: The epoch access proof (a binding decision) makes every epoch of a channel linkable at the relay, and exposes epoch numbers and which envelopes carry Commits. The security and relay sections still claim the opposite, and the sealed-envelope rationale claims to hide things the outer envelope and announcements reveal. ARCHITECTURE §5 item 6 is honest; the spec text overstates.
- Suggested fix: Rewrite 10.4.2 last paragraph, 12.3 "cannot do" bullet 3, 12.4 subscription paragraph and 12.4 l.40 to say the relay links all epochs of one chain (one channel's lifetime) and sees epoch boundaries and Commit frequency, but cannot map the chain to a channel or Space. Reduce the 05 l.216 rationale to what the wrapper still hides (`group_id` value, MLS sender data, content type of non-Commit traffic). Add `epoch`, `id`, `ts` and `powProof` to ARCHITECTURE §5 item 2, or state there that item 3 covers them.
- Needs decision: no

### CLM-2: Relay-side push registrations and `pushUrgency` are outside the observation budget
- Severity: P2
- Location: spec/11-transport.md:160, 194, 233-239; spec/12-security.md:48; ARCHITECTURE.md:161 (§5 item 7), 286 (§8 Q4); PRFAQ.md:31
- Evidence: 11.7.3 step 4 "Registers `{ pushHandle, proxyEndpoint, channelTokens }` with their Relay"; 11.7.4 "`urgency: "high"` is used for direct messages or @mentions" carried as unauthenticated `"pushUrgency"` in the outer envelope. ARCHITECTURE §5 item 7: "For push proxies only: opaque device push handles and wake-up timing." §8 Q4: "Push is in the §5 budget by default." 12.4: a Relay "cannot distinguish [DMs] from other traffic by type".
- Problem: With push on by default, every mobile client hands its relay one handle grouping all its channel tokens (a per-device cluster of channels) and labels DM/mention envelopes. No §5 item covers either for a relay, so the default configuration violates S6 as written, and 12.4's DM claim is false when push is used. PRFAQ "What does the relay operator see?" omits it.
- Suggested fix: Add a §5 item: "For relays serving push: per-`pushHandle` sets of routing tokens and the proxy endpoint, and the advisory urgency hint." Add the clustering to §9 alongside address clustering. Fix 12.4 l.48 to except `pushUrgency`. Optionally drop `pushUrgency` or require clients to send `normal` unless the user opts in.
- Needs decision: yes. (a) Extend the budget and disclose (recommended, matches Q4 "on by default"); (b) remove `pushUrgency` and require per-channel push registrations under distinct handles; (c) both.

### CLM-3: Sequencer, an IO, can map its streams to Spaces, contrary to S1 and the Space-anonymity claim
- Severity: P2
- Location: spec/14-jmap.md:193 (§14.4.6), 127-134 (§14.4.1); ARCHITECTURE.md:61 (§2.3 table), 86-88 (S1), 157-160 (§5 item 6)
- Evidence: 14.4.6 "Because it is named in the Space state of the Spaces that designate it, its operator can associate its streams with those Spaces." ARCHITECTURE S1: an IO MUST work "without knowing ... the mapping from routing tokens to channel or Space identities"; table lists Sequencer as IO with no caveat.
- Problem: The spec admits an IO component learns the token-to-Space mapping in the default arrangement; ARCHITECTURE states it never can. One of the two must change.
- Suggested fix: Either require the CO to designate one sequencer for all its Spaces or run it itself (making 14.4.6's mitigation a MUST), or add the sequencer case to ARCHITECTURE §9 and the §2.3 table note.
- Needs decision: yes. (a) MUST: one sequencer per CO or CO-operated (recommended; keeps S1 absolute); (b) accept and document in §9.

### CLM-4: "Cannot hijack the chain" depends on an ordering the spec does not require
- Severity: P2
- Location: spec/05-messaging.md:204; PROPOSAL.md:80-81; PRFAQ.md:99; ARCHITECTURE.md:198-200
- Evidence: 05 "The service countersigns only an announcement requested by a DID it authenticates as a current member of the channel under Space state, and at most one announcement per chain and `epoch`." PROPOSAL: "countersigned by the communications operator, so a member being removed cannot hijack the chain."
- Problem: The member being removed is still a current member under Space state until the CO changes Space state, and nothing orders that change before the removing Commit. It can request the single countersignature for the next epoch with its own key first, and the legitimate committer is then refused. The documents present the flaw as closed; the text closes it only if Space state is updated first.
- Suggested fix: Require the registration service to refuse countersignatures from a DID that is the subject of a pending removal, e.g. the Space-state change (or a CO-signed removal record) MUST precede the Commit, or the service countersigns only for the committer named in a CO-authorized removal. Until then soften PROPOSAL/PRFAQ wording. Flag for the agora-pozi.8 external review.
- Needs decision: yes. (a) Space-state removal MUST precede the removing Commit (recommended, simplest); (b) countersign by first valid request plus a CO override to re-key the chain; (c) leave to external review.

### CLM-5: Replaceability is not backed for a relay added mid-life of a group
- Severity: P2
- Location: spec/10-relays.md:612; ARCHITECTURE.md:106-109 (S5); PROPOSAL.md:31-34; PRFAQ.md:15, 35
- Evidence: 10.5.1 "submits an `AccessChainRegistration` to the Relay carrying the group's first-epoch access public key (§5.2.2); from then on the Relay follows the chain". S5: a CO MUST be able to "add, remove or replace any IO without changing ... MLS group state".
- Problem: A replacement relay never saw earlier announcements, and registration is specified only for the first epoch, so the text gives no way to admit an existing group at a new relay without a fresh chain. The headline "replace your provider, nobody re-enrolls" lacks a mechanism.
- Suggested fix: Allow `AccessChainRegistration` for the current `epoch` with that epoch's access public key and `channelToken` (the example already has an `epoch` field); say a CO registers every live chain at a new relay before switching.
- Needs decision: no

### CLM-6: "The provider cannot link your traffic to a particular Space" is absolute; ARCHITECTURE and spec say otherwise
- Severity: P2
- Location: PRFAQ.md:35, 17, 31; PROPOSAL.md:42. Contradicted by ARCHITECTURE.md:307-313 (§9), spec/14-jmap.md:193, spec/10-relays.md:19
- Evidence: PRFAQ "Your service agreement is signed with a billing key that appears nowhere in your Spaces, so the provider cannot link your traffic to a particular Space." ARCHITECTURE §9: "A CO with one Space gets none", plus registration-timing correlation and address clustering. 10.1 managed deployments are per-customer with `relayDID` "anchored to the customer's DNS domain"; SpaceAd `relayHints` name relays.
- Problem: The customer FAQ promises an unconditional property the governing document qualifies. The next FAQ ("It helps") is accurate; this one is not.
- Suggested fix: "...so the provider learns which customer, not which of that customer's Spaces; with one Space, or a Space that advertises its relays, that distinction is lost (see ARCHITECTURE §9)." Same qualifier on PROPOSAL l.42 and PRFAQ l.17.
- Needs decision: no

### CLM-7: "Interoperates natively with MIMI" overstates a design that depends on expired drafts
- Severity: P2
- Location: PRFAQ.md:21, 55; spec/09-interop.md:12, 71; spec/99-appendices.md:25
- Evidence: PRFAQ "interoperates natively with MIMI, the IETF's cross-platform messaging work" and "a single MLS group spans both systems and E2EE is preserved end to end". 09 Limitations: arch and delivery drafts "have both expired without replacement, indicating the WG is stalled on the delivery layer"; credential-field acceptance "is a known interoperability risk"; "Members SHOULD be told that the peer MIMI provider also learns the room's participant list."
- Problem: The press release presents MIMI interop as a delivered property; the spec presents it as a contingent design with an open interop risk and a membership disclosure to the peer provider. Press-release voice is allowed, but the FAQ answer should not drop the membership caveat.
- Suggested fix: Press release: "is designed to interoperate with MIMI". FAQ: add that the peer MIMI provider learns the room's participant list and that the delivery-layer drafts are stalled.
- Needs decision: no

### CLM-8: Stale identity-method references contradict the did:webvh decision stated in PROPOSAL/PRFAQ
- Severity: P3
- Location: spec/09-interop.md:22, 32; spec/99-appendices.md:11
- Evidence: 09 "Agora users are identified by DID (`did:key` or `did:web`)"; Appendix A "Identity | W3C DID Core, `did:key`, `did:web`". Versus §2.1 and PROPOSAL l.86-89: did:webvh default, did:plc and did:key opt-in.
- Problem: Leftovers from before the DID-method decision.
- Suggested fix: 09: "(`did:webvh`, `did:plc` or `did:key`, §2.1)"; example credential `did` may stay `did:key`. Appendix A Identity row: "W3C DID Core; methods in the rows below".
- Needs decision: no

### CLM-9: "One thing" undecided understates open items still marked in the spec; Appendix B is stale
- Severity: P3
- Location: PRFAQ.md:99; ARCHITECTURE.md:273; spec/99-appendices.md:40; spec/13-encoding.md:86; spec/10-relays.md:440
- Evidence: PRFAQ "What is still undecided? One thing". Appendix B item 2 "Push notification proxy conformance: see agora-pozi.11" (bead closed, Q4 decided). 13: "The JWS test-vector set does not exist yet"; 10: "The infohash value and its derivation are not yet fixed" (both cite closed bead agora-pozi.20.16). Appendix B item 1 (cross-space reputation) also open.
- Problem: Appendix B lists a decided question as open; two unfinished items cite a closed bead; PRFAQ's count ignores them. The infohash gap blocks implementation of DHT bootstrap.
- Suggested fix: Delete Appendix B item 2. Reopen or file beads for the two Open markers. PRFAQ: "One design question ... plus unfinished items listed as Open in the spec (test vectors, DHT infohash)".
- Needs decision: no

### CLM-10: ARCHITECTURE S3 forbids IOs holding exporter outputs, but `channelToken` is one
- Severity: P3
- Location: ARCHITECTURE.md:96-99 (S3); spec/05-messaging.md:194; spec/14-jmap.md:127
- Evidence: S3 "MUST NOT hold ... exporter outputs other than those specifically derived for IO verification (§6.2)". 05: "`channelToken` is derived from the MLS exporter ... `MLS-Exporter("agora channel token", channelCID, 32)`". 14.4.1: the sequencer "holds no MLS group secrets, exporter outputs".
- Problem: Every relay and sequencer holds channel tokens, so S3's exception list is incomplete and 14.4.1 is literally false.
- Suggested fix: S3: "other than routing tokens and those derived for IO verification (§6.2)". 14.4.1: "holds no exporter outputs other than routing tokens".
- Needs decision: no

### CLM-11: ARCHITECTURE reference and citation errors
- Severity: P3
- Location: ARCHITECTURE.md:262-264 (§7 item 9), 165-166 (§5), 34 (§2.1), 59 (§2.3); spec/11-transport.md:260
- Evidence: (a) §7 item 9 ends "Open question Q2", but §8 Q2 is resolved. (b) §5 "This matches the privacy whitepaper: 'Agora is not anonymous.'" The only such document is import/agora-privacy-whitepaper-clean.md, frozen, whose model has the relay seeing membership (notes/research-2026-10-16.md:98). (c) §2.1/§2.3 "IPFS pinning", while spec 10.4.4 says pin "does not mean pinning on the public IPFS network" and relays MUST NOT publish non-CO blobs there. (d) spec 11.8 cites "ARCHITECTURE S1, §5.3 item 4"; ARCHITECTURE has no §5.3 (intended: §7 item 4).
- Problem: Dangling or stale references; (b) cites a superseded document as corroboration.
- Suggested fix: (a) "Resolved: §8 Q2." (b) Drop the whitepaper sentence. (c) "Blob storage (content-addressed)". (d) "§7 item 4".
- Needs decision: no

### CLM-12: README and PROPOSAL profile lists are incomplete
- Severity: P3
- Location: README.md:22; PROPOSAL.md:65
- Evidence: README "employer-managed DIDs (O365, Google Workspace, generic IdP), Purview export, Discord onboarding". profiles/ also holds compliance-chain-witness.md, parlance.md, radio-mesh-gateway.md.
- Problem: Three profiles go unlisted.
- Suggested fix: Add them, or write "deployment profiles, including ...".
- Needs decision: no

## Checked and found consistent
- PRFAQ dateline "**SEATTLE, WA, [launch date]**" (PRFAQ.md:5) and the required "What is a PRFAQ?" footer (PRFAQ.md:115) are present and verbatim.
- ARCHITECTURE internal references check out: §2.3 table refs (§5 item 7, §7 item 6, §8 Q3, §6.3); §7 item 3 → §9; §7 item 11 → §5 item 1; §8 Q6 → §5 item 6, §6.1; spec refs §10.4.1, §10.5.1, §5.2.2, §14.4. §7's imported-document refs (§6.6, §7, §8.6, §8.8, §9.5, §10.6, §11.1–11.3, §17.8.9 and l.1536/1542/1797/2325/2439/2594/2962/3878) match import/agora-protocol-spec-unified.md.
- Backed by spec: no client identity at relays (11.6, 10.4.3); PoW under load (11.6) and per-channel PowPolicy, client-enforced (10.5.2); KeyPackages with the identity host (5.2.1.1, 2.5.3); did:webvh/plc/key claims, portability and "cannot quietly add keys" (2.1, 2.5.2); stable employer DIDs (2.5.2); encrypted broadcast with public-key variant (5.2.1.4, 3.4); discovery signing and public-only SpaceAds (10.3.2); push default, jitter, coalescing (11.7); billing-DID-signed RSA naming no Space (10.5.1); typed envelope + JWS, standards cited (13.1, App. A, HPKE in 6.12.4, SFrame in 6.9/6.13); JMAP management never on relays (11.8.9); sequencer blind to content (14.4); mesh ≤4 / SFU non-member (6.5, 6.6); recording consent split (6.12.3); logger capture gaps (7.8.9); gateway indicator (9.3); every spec part states what it binds.

Coverage: read in full README.md, PROPOSAL.md, PRFAQ.md, ARCHITECTURE.md, spec/01-overview.md, spec/99-appendices.md; read the claim-bearing spec sections in full: 02 §2.1, §2.5.2–2.5.3; 03 §3.4; 05 §5.2.1–5.2.2; 06 §6.5, §6.12.3, §6.13; 07 §7.8.9 (plus grep for chain/tamper); 09 §9.1, §9.3; 10 §10.3.2, §10.4–10.5; 11 §11.1–11.8 (all but 11.7.2); 12 §12.1–12.5; 14 §14.4.1, §14.4.5–14.5. The rest of spec/ was searched by grep only.
