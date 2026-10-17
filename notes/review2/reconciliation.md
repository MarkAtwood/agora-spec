# Review 2 reconciliation

Status of the 87 open final-pass issues checked against the current tree (after fd8710f), 2026-10-17. File refs: `NN:line` = `spec/NN-*.md`; other paths are from the repo root. Line numbers are as of this check.

| id | lens-id | priority | status | evidence/remaining |
|---|---|---|---|---|
| agora-pozi.33.64 | IMP2-1 | 1 | FIXED | 05:29-33 stamped Commit counts only if published within 10 s and valid; skip otherwise; 14:228 republish counts only within window (10 s window replaces "within T") |
| agora-pozi.33.65 | IMP2-2 | 2 | FIXED | 14:170 Commits only on current token's stream, `stream-closed`; 05:27; 10:876 |
| agora-pozi.33.66 | IMP2-3 | 2 | FIXED | 03:165 completion by newOwner after ts+delaySeconds; 04:19 late objection rejected; 04:22 |
| agora-pozi.33.67 | IMP2-4 | 2 | FIXED | 04:98, :124 `KickLift`; 03:313 Kick stands until KickLift |
| agora-pozi.33.68 | IMP2-5 | 2 | FIXED | 03:313 every role holder gets ChannelAdmissionKey; 05:56, :140 match |
| agora-pozi.33.69 | IMP2-6 | 2 | FIXED | 04:193-196 ts window, creation rules, 204 before Welcome; 04:175 status codes |
| agora-pozi.33.70 | IMP2-7 | 2 | FIXED | 05:80, :134 clients list 0xF0A0/0xF0A1 |
| agora-pozi.33.71 | IMP2-8 | 2 | FIXED | 04:260-271 §4.6.4 handover; 04:313 |
| agora-pozi.33.72 | IMP2-9 | 2 | FIXED | 02:510, :557 auth key or did:key device binding; 07:144 |
| agora-pozi.33.73 | IMP2-10 | 2 | FIXED | 08:97 guest non-member view, adder validation; 03:345 homeAdminDID read-only |
| agora-pozi.33.74 | IMP2-11 | 2 | FIXED | 02:507-525 SpaceMembership record keyed by Space id with spaceEndpoint |
| agora-pozi.33.75 | IMP2-12 | 2 | FIXED | 05:209-211 non-members check `broadcasters`; 03:313 public only in public Space |
| agora-pozi.33.76 | IMP2-13 | 2 | FIXED | 10:591 JMAP sync sole history/blob path; 11:396 blobId is CID |
| agora-pozi.33.77 | IMP2-14 | 2 | FIXED | 11:176, :184, :187, :131 Ack/Error/unknown-token/expired semantics |
| agora-pozi.33.78 | IMP2-15 | 2 | FIXED | 05:432 client past retention tells user a member must re-add them |
| agora-pozi.33.79 | IMP2-16 | 3 | FIXED | 01:79 Client row cites §2.6-2.8 |
| agora-pozi.33.80 | IMP2-17 | 3 | FIXED | 03:297 relay origins + manifest; 04:175 GET returns key as application/cbor |
| agora-pozi.33.81 | IMP2-18 | 3 | FIXED | 05:209 `device` 16 random bytes; seq per (kid, device) |
| agora-pozi.33.82 | IMP2-19 | 3 | FIXED | 12:179 RFC 9421 `created`; no `x-agora-timestamp` in spec/ |
| agora-pozi.33.83 | IMP2-20 | 3 | FIXED | 05:457 DM groups have no pin list; "in a group chat, admins" gone |
| agora-pozi.33.45 | CON2-1 | 2 | FIXED | Per decision 33.85: 03:313 every role holder served ChannelAdmissionKey; 05:56, :140 |
| agora-pozi.33.46 | CON2-2 | 2 | FIXED | 05:80, :134; 04:173 clients list 0xF0A0/0xF0A1 |
| agora-pozi.33.47 | CON2-3 | 2 | FIXED | 04:196 committer of any Add (incl. logger/recorder) MUST send DMMembers addition; 07:217, :350; 06:465 |
| agora-pozi.33.48 | CON2-4 | 2 | FIXED | ARCHITECTURE.md:101-103, :122-123, :321 TURN shared secret |
| agora-pozi.33.49 | CON2-5 | 2 | FIXED | 01:79 Client row cites §2.6-2.8 |
| agora-pozi.33.50 | CON2-6 | 3 | PARTIAL | Main sites fixed (ARCHITECTURE.md:217-218, :246; 03:356; 05:265; 10:814). Remaining: 05:215 "registers the new admission key with its relays" (omits SFU/sequencer); 10:868 "with every IO" lacks the serviceType qualifier used at 10:814 |
| agora-pozi.33.51 | CON2-7 | 3 | FIXED | 05:421 covered by admissionSig, hint only |
| agora-pozi.33.52 | CON2-8 | 3 | FIXED | 03:89-98 broadcast example lacks mlsGroupID; 03:243, :353 |
| agora-pozi.33.53 | CON2-9 | 3 | FIXED | 04:163, :181 `mlsGroupID` in place of channelID |
| agora-pozi.33.54 | CON2-10 | 3 | FIXED | Per decision 33.86: 05:457; 14:159 |
| agora-pozi.33.55 | CON2-11 | 3 | FIXED | 10:272 RelayPeerAnnouncement via Peer API, not gossip; 05:407 |
| agora-pozi.33.56 | CON2-12 | 3 | FIXED | 10:797 PoW on HTTP endpoints or sequencer |
| agora-pozi.33.57 | CON2-13 | 3 | FIXED | 01:86, :91, :92 conformance rows cite §5.2.1.4, §10.5.x |
| agora-pozi.33.58 | CON2-14 | 3 | FIXED | 12:179 RFC 9421 `created`; 05:364 cites §2.7; ARCHITECTURE.md:286 |
| agora-pozi.33.59 | CON2-15 | 3 | FIXED | 03:345 homeAdminDID read-only on guest endpoint |
| agora-pozi.33.60 | CON2-16 | 3 | FIXED | 04:175 GET/204/409 semantics; 03:315 DM exception |
| agora-pozi.33.61 | CON2-17 | 3 | FIXED | 99:154, :174, :178 registry entries |
| agora-pozi.33.62 | CON2-18 | 3 | FIXED | 99:85 expiryHint vs retentionDays; new rows 99:92-102. Unconfirmed: no "hourly admission key fetch" row found (agent grep for "hourly" empty) |
| agora-pozi.33.63 | CON2-19 | 3 | FIXED | 03:228 `vtcCompliance` row |
| agora-pozi.33.27 | SEP2-1 | 2 | FIXED | Per decision 33.4: 03:313; ARCHITECTURE.md:176-178, :438; 10:564; 12:31, :39 |
| agora-pozi.33.28 | SEP2-2 | 3 | FIXED | 10:844 registrations carry no keyEpoch; none in 14 seq-auth or 06 sfu-admission |
| agora-pozi.33.29 | SEP2-3 | 2 | FIXED | 10:733 identity-host CO logger MUST NOT be served user; ARCHITECTURE.md:426-429; 12:53; 10:563 |
| agora-pozi.33.30 | SEP2-4 | 2 | FIXED | ARCHITECTURE.md:472-478; 04:171 SHOULD list relays it does not operate; profiles/corundum.md:38 |
| agora-pozi.33.31 | SEP2-5 | 2 | FIXED | Per decision 33.5 (option A: add + self-remove only): 04:197, :199, :313. Fix part (ii) (drop DIDs with no device keys) was superseded by the decision; consequence: revoked/offboarded DIDs stay on the DM list |
| agora-pozi.33.32 | SEP2-6 | 2 | FIXED | 04:260-271 §4.6.4 handover; 12:239, :247; 99:100-101 |
| agora-pozi.33.33 | SEP2-7 | 3 | FIXED | ARCHITECTURE.md:434-437; 12:26 (§12.3 only, not §12.4); 10:582 |
| agora-pozi.33.34 | SEP2-8 | 3 | FIXED | ARCHITECTURE.md:451-455; 12:53 self-group token |
| agora-pozi.33.35 | SEP2-9 | 3 | FIXED | ARCHITECTURE.md:189-194, :467-470; 06:185, :190 |
| agora-pozi.33.36 | CRY2-1 | 1 | FIXED | 05:27 Commits stamped only on current token's commit stream; 14:170 sequencer closes old token stream on `replaces`; 14:214, :246 |
| agora-pozi.33.37 | CRY2-2 | 2 | FIXED | Redesigned: 05:29-33 stamped Commit counts only if published within 10 s and valid; 14:228 any member MAY publish within window |
| agora-pozi.33.38 | CRY2-3 | 2 | FIXED | 05:259 `id` is CIDv1 of the `signed` byte string; admissionSig/powProof excluded; 10:793 matches |
| agora-pozi.33.39 | CRY2-4 | 2 | FIXED | 06:221 S counts leaves incl. blank leaves; test vector with blank leaves required |
| agora-pozi.33.40 | CRY2-5 | 2 | FIXED | 04:193 ts within 300 s, seq/ts monotonic; 04:197-199 self-removal only, never removes complianceLoggers |
| agora-pozi.33.41 | CRY2-6 | 2 | FIXED | 13:61 threshold needs k distinct DIDs, reject duplicate-DID kids; 13:80, :94; 04:18 references 13.1.1 |
| agora-pozi.33.42 | CRY2-7 | 2 | FIXED | 07:144 did:key verified via agora_device_binding; 12:154 non-revocable caveat |
| agora-pozi.33.43 | CRY2-8 | 3 | FIXED | ARCHITECTURE.md:177, 12:31/:39, 11:277 public-broadcast token exception; 03:313 accepted cost |
| agora-pozi.33.44 | CRY2-9 | 3 | FIXED | 12:167 admission private keys excluded from HSM list with rationale |
| agora-pozi.33.6 | DOC2-1 | 1 | FIXED | guides/relay-operator.md:1650 discard registrations, never reinstate from backup; :1652 notify contact; :1515; matches 10:680 |
| agora-pozi.33.7 | DOC2-2 | 2 | FIXED | guides/relay-operator.md:1068/:1094 suspend endpoints; :1231 `suspended` label; :2404 table row |
| agora-pozi.33.8 | DOC2-3 | 2 | FIXED | guides/relay-operator.md:2263 `retiresAt` 30 days ahead; :2271, :2275, :2277; no `maintenance` field |
| agora-pozi.33.9 | DOC2-4 | 2 | PARTIAL | Spec fixed (07:135 logger MUST fetch/decrypt/check attachments). Remaining: guides/counsel.md:33 and guides/regulators.md:65 still say spec "does not yet define how the logger stores the file contents" |
| agora-pozi.33.10 | DOC2-5 | 2 | FIXED | ARCHITECTURE.md:425-429 identity-host CO caveat; PRFAQ.md:31 |
| agora-pozi.33.11 | DOC2-6 | 3 | FIXED | guides/counsel.md:43, guides/regulators.md:205 cite §4.6.3, §7.8.7 |
| agora-pozi.33.12 | DOC2-7 | 3 | FIXED | 10:797 PoW on HTTP endpoints/sequencer; ARCHITECTURE.md:162-163 |
| agora-pozi.33.13 | DOC2-8 | 3 | FIXED | PROPOSAL.md:71 "(pending revision)" removed |
| agora-pozi.33.14 | DOC2-9 | 3 | FIXED | profiles/corundum.md:38 cites ARCHITECTURE §9 accepted cost |
| agora-pozi.33.15 | DOC2-10 | 3 | FIXED | profiles/compliance-chain-witness.md:89-93 CompliancePruneRecord practice type, not a ComplianceRecord |
| agora-pozi.33.16 | DOC2-11 | 3 | FIXED | guides/relay-operator.md:1514, :1527, :1545 scoped to did:key vs did:web |
| agora-pozi.33.17 | DOC2-12 | 3 | FIXED | guides/relay-operator.md:1947 HiddenServicePort 80; :1953 plaintext WS |
| agora-pozi.33.18 | DOC2-13 | 3 | FIXED | profiles/universal-idp-did.md:694-695 proxy list; :24 defers to O365 §6.7 |
| agora-pozi.33.19 | DOC2-14 | 3 | FIXED | profiles/discord-onboarding.md:62 admission-key endpoints + own ServiceAgreements; :531 DM DIDs privacy |
| agora-pozi.33.20 | DOC2-15 | 2 | FIXED | 02 §2.4 (~:128) self-hosted vs CO-provisioned did:webvh update keys |
| agora-pozi.33.21 | DOC2-16 | 2 | FIXED | profiles/purview-bridge.md:564-569 entry types; :406 reseal chain; :603 gap alert |
| agora-pozi.33.22 | DOC2-17 | 3 | PARTIAL | profiles/purview-bridge.md:302 blob/contentKey/sha256 fixed; remaining: "spec ... does not itself define that fetch" now stale vs 07:135 |
| agora-pozi.33.23 | DOC2-18 | 3 | FIXED | profiles/gsuite-employer-did.md:301, :412 AgoraDIDAdmin is sidecar mapping |
| agora-pozi.33.24 | DOC2-19 | 3 | FIXED | profiles/o365-employer-did.md:257; profiles/universal-idp-did.md:24, :42 AgoraProvisioning |
| agora-pozi.33.25 | DOC2-20 | 3 | FIXED | profiles/o365-employer-did.md:686 registers with every IO per §10.5.3 |
| agora-pozi.33.26 | DOC2-21 | 3 | FIXED | Non-normative banner in five profiles |
| agora-pozi.33.2 | - | 1 | FIXED | 05:28-34 stamped Commit counts only if published within 10 s and valid; 99:94 |
| agora-pozi.33.1 | - | 1 | FIXED | 05:27 Commits only on current token's commit stream; 14:170 closes old stream; 10:876 |
| agora-pozi.33.87 | - | 2 | FIXED | 05:211 signed `broadcasters` list in public view; non-members MUST NOT display unlisted senders; 03:233, :313; 04:92; 99:140 |
| agora-pozi.33.85 | - | 2 | FIXED | 03:313 every member whose role covers the channel is served ChannelAdmissionKey; 05:56, :140, :144, :268 |
| agora-pozi.33.84 | - | 2 | FIXED | 04:260-269 §4.6.4 Admission Host Handover via GCE proposal; 99:100-101 24 h fallback, 30-day serve tail |
| agora-pozi.33.5 | - | 2 | FIXED | 04:193-199 addition + self-removal only, monotonic seq/ts; 04:175 409 on replay |
| agora-pozi.33.4 | - | 2 | FIXED | 03:246, :313 `keyAccess: public` only in public Spaces; 05:183; ARCHITECTURE.md:438-446; 11:277; 12:31, :39; 10:564 |
| agora-pozi.33.86 | - | 3 | FIXED | 14:159 sequenced-v1 incl. pinnedMessageIds read-only in DMs; 05:457 DM groups have no pin list |
| agora-pozi.33.3 | - | 3 | FIXED | Non-normative banner in 7 profiles (profiles/*.md:3-4); compliance-chain-witness and radio-mesh-gateway have no BCP 14 keywords |

## Counts

| Status | Count |
|---|---|
| FIXED | 84 |
| PARTIAL | 3 |
| MOOT | 0 |
| OPEN | 0 |
| DECIDED-UNIMPLEMENTED | 0 |

All 9 DECIDED decision issues are implemented.

## Non-FIXED items by file

**guides/counsel.md, guides/regulators.md**
- agora-pozi.33.9 (DOC2-4, P2): counsel.md:33 and regulators.md:65 still say the spec "does not yet define how the logger stores the file contents". spec/07-compliance.md:135 now defines it.

**profiles/purview-bridge.md**
- agora-pozi.33.22 (DOC2-17, P3): line 302 says "The spec ... does not itself define that fetch; it is this profile's requirement". That is stale since 07:135 defines it.

**spec/05-messaging.md, spec/10-relays.md**
- agora-pozi.33.50 (CON2-6, P3): 05:215 says the key is registered "with its relays", leaving out SFUs and sequencers. 10:868 says "with every IO" without the serviceType qualifier used at 10:814.

## Notes (FIXED, but worth knowing)
- SEP2-5: Decision 33.5 deliberately left out fix part (ii), so a revoked or offboarded DID cannot be removed from a DM member list by anyone else.
- CON2-18: The agent could not confirm an "hourly admission key fetch" row in Appendix 99.
- SEP2-7: The removal-inference sentence is in §12.3 only, not §12.4.
