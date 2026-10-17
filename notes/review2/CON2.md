# CON2: cross-part consistency of new names and flows

Lens: the names and flows introduced by b07bead, a5fdf42 and 9e7711f (channel admission key, registration, channelToken, routing envelope `signed`, ServiceAgreement, sequencer/commitStamp, channelID/group_id, self-group, DMMembers, device binding, Pkarr, live CDDL, PoW, limits, codepoints, Appendix D). Items already FIXED or DECIDED in notes/review/reconciliation.md and bd memories are not repeated. Known-open items (IPNS name in App. D, CON-24 version registry) are not re-reported.

### CON2-1: Community channel admission key: served to every role holder, or only to speakers?
- Severity: P2
- Location: spec/03-spaces.md:311; spec/05-messaging.md:49, :132
- Evidence: 03 §3.4: "The endpoint serves a channel's records only under the access control below: to members permitted to read the channel (a role whose `channelAccess` covers it, §4.2, and no standing Kick or Ban for it, §4.5) ..." vs 05 §5.2.1: "the CO serves the channel's admission key ... only to members of the speaker group (§5.2.2)" and §5.2.1.2: "Space members outside the speaker group are not served the channel's admission key".
- Problem: The two parts give different access rules for the same record. Under §3.4 every role holder of a `community` channel gets the seed and can post envelopes the relay admits. That contradicts §5.2.1.2. Neither part says how the Space endpoint learns who is in the speaker group: that is MLS membership, not Space state. Neither says whether idle eviction (§5.2.1.2), which §3.4 treats as "stops serving a channel to a member", forces a key rotation each time.
- Suggested fix: In §3.4, add a `community` clause: the endpoint serves the `ChannelAdmissionKey` only to DIDs the SpeakerBot or a channel admin has admitted, and to the logger. Define how the endpoint learns that list, for example a CO-signed speaker list or a `DMMembers`-style replacement by the SpeakerBot. Then state whether eviction rotates the key.
- Needs decision: yes. (a) Speakers only, with a speaker list kept at the endpoint and rotation on eviction. (b) Every role holder gets the key, so relay admission is Space-role-wide and the speaker group bounds only decryption; §5.2.1 and §5.2.1.2 are then reworded. (c) Speakers only, with no rotation on eviction (an evictee keeps relay write access until the next rotation). Recommend (b): it needs no new endpoint state and matches how relay admission already works for removed members (members drop the envelopes).

### CON2-2: `agora_admission_host` is required in DM GroupContexts, but no client is told to support it
- Severity: P2
- Location: spec/04-access-control.md:158; spec/05-messaging.md:73; spec/99-appendices.md:107
- Evidence: 04 §4.6: "`agora_admission_host` extension, extension type 0xF0A0 ..., listed in `required_capabilities`". 05 §5.2.1: "Every Agora client lists 0xF0A1 in its leaf `capabilities`." Nothing requires 0xF0A0 in leaf capabilities.
- Problem: Under RFC 9420 (§11.1, §12.1.1), a KeyPackage whose leaf does not list every extension in the group's `required_capabilities` cannot be added. A client that follows §5.2.1 to the letter publishes KeyPackages listing only 0xF0A1, so it cannot be added to any DM group or self-group.
- Suggested fix: In §5.2.1, change the sentence to "Every Agora client lists 0xF0A0 and 0xF0A1 in its leaf `capabilities.extensions`".
- Needs decision: no

### CON2-3: No rule makes anyone update the DM admission host's member list when a member, logger or recorder is added
- Severity: P2
- Location: spec/04-access-control.md:158, :259; spec/07-compliance.md:210-216, :285, :336-349; spec/06-calls.md:466
- Evidence: 04 §4.6: "any listed member replaces it after a membership change, by ... `urn:agora:type:DMMembers` ... signed ... by a device key of a DID on the current list". 4.8 obliges a committer to send `DMMembers` only on leave. 7.8.7 sends `DMMembers` to add the logger only in the message-request path. 7.8.2 steps 1-5 and the §7.8 Conformance Summary never mention it. 6.12.7 adds a recorder to a DM, but §4.6's list "includes any compliance loggers" and says nothing about recorders.
- Problem: The host serves the DM key only to DIDs on its list. If the committer of an Add does not send `DMMembers`, the new member, logger or recorder cannot fetch the key, subscribe, or publish its self-update Commit (§7.3). The ordinary DM capture path (§7.8.2) therefore fails. A regulated member in the request state (§7.8.7) cannot send `DMMembers` either, unless the adder put it on the list first, because the envelope must be signed by a DID already listed.
- Suggested fix: In §4.6, say "The committer of every Commit that adds or removes a member MUST send `DMMembers`". Add the step to §7.8.2 (after step 4) and to §6.12.7, add a row to the §7.8 Conformance Summary, and extend "includes any compliance loggers" to "and recorders (§6.12.7)".
- Needs decision: no

### CON2-4: The TURN shared secret is IO key material that ARCHITECTURE S3 and S7 do not allow
- Severity: P2
- Location: ARCHITECTURE.md:97-101, :119-123; spec/06-calls.md:281; spec/10-relays.md:689
- Evidence: S3: "The only key material an IO holds for a community is the verification material of §6.2: registered admission public keys and the routing tokens registered with them." S7: "The only binding between a CO and an IO is the `ServiceAgreement` ... and the verification material defined in §6. This holds for every IO service type: relay, SFU, TURN ...". 06 §6.11: "The TURN operator, which holds a `ServiceAgreement` with `serviceType` `turn` ..., and the CO credential service share a secret."
- Problem: The HMAC secret is community-specific key material held by an IO and defined outside ARCHITECTURE §6. By the governing document's own rule, §6.11 is therefore an erratum, even though the design itself (TURN REST credentials) is sound.
- Suggested fix: Add the TURN REST shared secret to ARCHITECTURE §6 as a third form of verification material (it authenticates the CO credential service, not members). Extend S3 and S7 to name it. Alternatively, carry the secret in the `turn` ServiceAgreement and cite that agreement in S3.
- Needs decision: no

### CON2-5: Client conformance class leaves out the new identity flows (§2.6 to §2.8)
- Severity: P2
- Location: spec/01-overview.md:79
- Evidence: The Client row lists "§2.1, §2.2 (DID resolution, device keys); §3.3 to §3.5; §4; §5.1, §5.2.1 to §5.2.8, §5.3; ... §14.2 to §14.4". §2.6 (self-group, own-device Add, HistoryTransfer), §2.7 (`IdentityChanged`) and §2.8 (account deletion) are absent.
- Problem: §1.4 says a class must implement only "every requirement that the listed sections place on that class". So a conformant Client need not accept own-device Adds (which §4.3 and §4.6.1 rely on), keep the self-group the block list syncs through (§4.6.3), or send and act on `IdentityChanged`, which is the only revocation signal now that identity records are not gossiped (§2.2, §2.5.5, §12.12).
- Suggested fix: Add "§2.6, §2.7, §2.8 (multi-device, identity change notice, account deletion)" to the Client row.
- Needs decision: no

### CON2-6: Who receives admission key registrations: "every IO", "relays", or the agreement types marked Yes?
- Severity: P3
- Location: ARCHITECTURE.md:199-203, :229-231; spec/05-messaging.md:254; spec/10-relays.md:684-690, :777; spec/03-spaces.md:354
- Evidence: ARCHITECTURE §6.1: "Registration gives every IO, of any service type, a way to admit members". §6.2: "registers the public key with every IO that holds a `ServiceAgreement` with the CO". 05 §5.2.2: "with every relay and other IO that holds a `ServiceAgreement`". 10 §10.5.1 table: `turn` and `push-proxy` "No". 10 §10.5.3: "The IOs holding the agreements a registration service uses are the relays it lists to members" (SFUs and sequencers are not in `relays`). 03 §3.6 step 4: "registers each admission key with its relays".
- Problem: The text is inconsistent about where registrations go. Read literally, ARCHITECTURE and §5.2.2 send registrations to TURN and push proxies, which §10.5.3 answers with `agreement-invalid`, and §3.6 and §10.5.3 leave out SFUs and sequencers.
- Suggested fix: Use the §10.5.3 opening wording everywhere: "every IO holding a `ServiceAgreement` whose `serviceType` receives registrations (§10.5.1)". Delete the "are the relays it lists" sentence in §10.5.3, or restrict it to `relay` agreements.
- Needs decision: no

### CON2-7: Is `expiryHint` authenticated or not?
- Severity: P3
- Location: spec/05-messaging.md:240 vs :409
- Evidence: §5.2.2: "It is authenticated in the same weak sense as `ts`" (it is inside `signed`, covered by `admissionSig`). §5.2.4: "This field is unauthenticated at the outer layer".
- Problem: §5.2.4 predates the `signed` field and now contradicts §5.2.2.
- Suggested fix: In §5.2.4, change it to "It is covered by `admissionSig`, which shows only that some key holder set it (§5.2.2); Relays use it as a hint only".
- Needs decision: no

### CON2-8: Broadcast channels have no MLS group, but the example and the creation steps give them one
- Severity: P3
- Location: spec/03-spaces.md:26, :97, :176, :242, :351; spec/05-messaging.md:43, :175
- Evidence: §3.2 table: `broadcast` "MLS group: None (§5.2.1.4)". §5.2.1.4: "A broadcast channel has no MLS group." The §3.3 example announcements channel nevertheless carries `"mlsGroupID": "base64url..."`. §3.6 step 1: "for each initial channel, a `channelID` and an MLS group".
- Problem: The example contradicts the rule. A client that applies "required on a channel that has an MLS group" against the example will expect a group that does not exist. (The prior fix EXA-6 added `mlsGroupID` to every channel before the broadcast decision.)
- Suggested fix: Remove `mlsGroupID` from the broadcast entry in the example. In §3.6 step 1, say "an MLS group for each channel that has one (§3.2)". In the field index, add "never on `broadcast`".
- Needs decision: no

### CON2-9: The DM group ID is called `groupID` in some places and `mlsGroupID` in others
- Severity: P3
- Location: spec/04-access-control.md:150, :153-155, :158 (`groupID`); spec/04-access-control.md:166, spec/06-calls.md:606, spec/07-compliance.md:124, :252, :294, :317 (`mlsGroupID`)
- Evidence: The DM `ChannelAdmissionKey` "carries `groupID` ... in place of `channelID`", and `DMMembers` has body `{"groupID": ...}`. `DMGroupDescriptor`, `CallBreakout`, `ComplianceRecord`, `ComplianceDisclosureNotice`, `DMComplianceAuditEntry` and `ComplianceGapEntry` all use `mlsGroupID`.
- Problem: The same value has two field names across records the same client handles. This invites mismatched parsers.
- Suggested fix: Rename to `mlsGroupID` in the DM `ChannelAdmissionKey` and `DMMembers` (the URL path segment can stay `<groupID>`).
- Needs decision: no

### CON2-10: Pinning in DM groups cannot be done
- Severity: P3
- Location: spec/05-messaging.md:445, :465; spec/14-jmap.md:62, :153; spec/05-messaging.md:28
- Evidence: §5.2.6: "in a group chat, admins" may change `pinnedMessageIds`. "`Chat.pinnedMessageIds` is written under the `sequenced-v1` consistency model ... ordered by the Space's blind sequencer". §14.4.1: "If `sequencer` is absent, `sequenced-v1` types ... are read-only". DM groups belong to no Space and have no sequencer (§5.1.1: "including in every DM group").
- Problem: §5.2.6 grants a DM pin permission that no DM can exercise, and DM groups have no defined "admins".
- Suggested fix: State that DM groups do not support pin lists. Or give DM groups a model they can use (for example `single-author` per pinner, or a sequencer named by the admission host).
- Needs decision: yes. (a) No pins in DMs. (b) A DM-specific model. Recommend (a).

### CON2-11: `RelayPeerAnnouncement` is a "gossip message" with no topic allowed to carry it
- Severity: P3
- Location: spec/10-relays.md:256; spec/10-relays.md:282-291, :332; spec/05-messaging.md:395
- Evidence: §10.2.6: share "as a `RelayPeerAnnouncement` gossip message". §10.3.1 defines only `v1/agora/discovery` and channel topics, and "Only SpaceAds and RelayAds travel on it". §10.3.2: a Relay "MUST NOT forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd".
- Problem: §10.2.6 cannot be followed without breaking §10.3.1 and §10.3.2.
- Suggested fix: Carry it as the body of `POST /v1/agora/peer/announce` or a new Peer API call, not as gossip. Alternatively, add it to the allowed discovery-topic records.
- Needs decision: no

### CON2-12: §10.5.2 calls the sequencer a CO endpoint
- Severity: P3
- Location: spec/10-relays.md:760
- Evidence: "A CO HTTP endpoint that requires proof of work ..., such as a `KeyPackageEndpoint` host (§4.6.3), an invite endpoint ... or a sequencer (§14.4)". ARCHITECTURE §2.3 and §14.4.1 make the sequencer an IO.
- Suggested fix: Change it to "An HTTP endpoint (CO or IO) ...".
- Needs decision: no

### CON2-13: Conformance classes cite the wrong sections, or too few, for the new services
- Severity: P3
- Location: spec/01-overview.md:84, :90, :91
- Evidence: Space endpoint: "§5.2.1.4 (`ChannelAdmissionKey` and `BroadcastKey` service)". The service is defined in §3.4; §5.2.1.4 is broadcast mode. Sequencer: "§14.4" only. SFU: "§6.6, §6.9, §6.10".
- Problem: SFUs and sequencers must accept and process `AdmissionKeyRegistration`s (§10.5.3), honor agreement lifecycle (§10.5.1) and admit by §10.5.4. Their class rows do not list these sections, and §1.4 limits obligations to the listed sections.
- Suggested fix: Space endpoint: cite "§3.4 (admission and broadcast key service)". Add "§10.5.1, §10.5.3, §10.5.4" to the Sequencer and SFU rows.
- Needs decision: no

### CON2-14: Dangling or wrong cross-references in the new text
- Severity: P3
- Location: spec/12-security.md:179; spec/05-messaging.md:353; ARCHITECTURE.md:265
- Evidence: (1) §12.9: "`x-agora-timestamp` (§10.2.3)". §10.2.3 uses RFC 9421 `created`, and no `x-agora-timestamp` exists anywhere. (2) §5.2.3 `IdentityChanged` row cites "(§2.1, §2.3)". The notice is defined in §2.7. (3) ARCHITECTURE §6.2: "**Pin and delete instructions** are authorized by the same key (a `PinInstruction` ...)". The spec has pin and unpin only, and deletes are client-side (§4.5).
- Suggested fix: (1) Write "the RFC 9421 `created` parameter (§10.2.3)". (2) Cite §2.7. (3) Write "Pin and unpin instructions".
- Needs decision: no

### CON2-15: §3.5 has no case for the guest Space endpoint authenticating the home CO
- Severity: P3
- Location: spec/08-cross-space.md:98; spec/03-spaces.md:343
- Evidence: §8.6: the guest Space endpoint "MUST serve it to the home Space's CO, authenticated per §3.5 as `homeAdminDID`". §3.5's checks: "`did` is a current member ... (for an identity host ...; for the home Space endpoint of a shared channel, a guest member ...)". `homeAdminDID` is not a member of the guest Space.
- Problem: A guest endpoint that follows §3.5 rejects the home CO.
- Suggested fix: In §3.5, add: "for a guest Space endpoint, the `homeAdminDID` of an in-force `ChannelShareAgreement` naming that Space (§8.6), which grants the guest Space's state only".
- Needs decision: no

### CON2-16: DM admission host responses are unspecified
- Severity: P3
- Location: spec/04-access-control.md:153-158; spec/03-spaces.md:313
- Evidence: The `GET`/`PUT` routes are listed in §4.6, but status codes, media types and body forms are given only for the Space endpoint in §3.4 ("Every other response is the record's encoded typed payload envelope with `sig` present"). The DM record "has no `sig`", and the `PUT .../members` response is undefined.
- Suggested fix: In §4.6, add: GET returns the encoded envelope without `sig` as `application/cbor`; PUT takes the encoded `DMMembers` envelope and returns 204, with 401/403/404/409 (stale `ts`)/429 as in §3.4.
- Needs decision: no

### CON2-17: Appendix D leaves out identifiers that the new text allocates
- Severity: P3
- Location: spec/99-appendices.md:117-149; spec/10-relays.md:497; spec/02-identity.md:415; spec/06-calls.md:108; spec/10-relays.md:682-690
- Evidence: Not listed: the `_corundum._agora` Pkarr record (§10.3.4.6); the DID service type `AgoraProvisioning` (§2.5.3); the WebSocket subprotocol `agora-sfu.v1` (§6.6, IANA "WebSocket Subprotocol Name Registry", RFC 6455 §11.5); the `serviceType` values `relay`, `sfu`, `sequencer`, `turn`, `push-proxy` (§10.5.1).
- Suggested fix: Add each to the matching Appendix D table (DNS children, DID service types, Web identifiers with IANA registry, capability and model strings).
- Needs decision: no

### CON2-18: Appendix C has a stale default and is missing the new numeric rules
- Severity: P3
- Location: spec/99-appendices.md:82; spec/10-relays.md:580, :636
- Evidence: App. C: "Relay envelope cache | lesser of `expiryHint` and the retention window (default 30 days)". §10.4.3 and §10.4.6 use the agreement's `retentionDays` and define no default. Missing from App. C: the 5-second canonical-Commit window and 5-second stamped-Commit hold (§5.1.1); 60-second retention of the previous sealing key (§5.2.2); hourly admission key fetch (§5.2.2); 7-day hold of an undecidable Welcome (§4.3); 30-second SFU challenge freshness (§6.6); 32/1000 generation window (§5.2.1); 32-byte `group_id` (§5.2.1).
- Suggested fix: Change the row to "lesser of `expiryHint` and the agreement's `retentionDays`" and add the listed rows.
- Needs decision: no

### CON2-19: The new Space field index omits `vtcCompliance`
- Severity: P3
- Location: spec/03-spaces.md:200-233; spec/06-calls.md:420-441
- Evidence: §3.3: "The tables below list every field of a Space state document". §6.12.5 adds `vtcCompliance` (`VTCComplianceConfig`) to Space state. It is absent from the table, while `complianceLogging` is present.
- Suggested fix: Add the row "`vtcCompliance` | `VTCComplianceConfig` | optional | §6.12.5". (This is what remains of reconciliation CON-23.)
- Needs decision: no

## Areas checked with no finding

- channelToken derivation: ARCHITECTURE §6.2, §5.2.2 and §13.3 match (IKM seed, salt empty, info `agora channel token` || uint64 BE keyEpoch, L = 32).
- `admissionSig` context separation: `ctx` `agora/envelope/v1`, `pin-op`/`upload-op` `op`, `seq-auth` `op: "sequence"`, `sfu-admission` `ctx`. These are distinct and consistent across §5.2.2, §6.6, §11.4, §14.4.3 and §13.1.1.
- commitStamp, SequenceStamp and commit stream: §5.1.1, §5.2.2, §14.4.2 to §14.4.4, ARCHITECTURE §5 item 2 and §12.4 agree.
- Exporter contexts use group_id, with the SFrame exception stated in §13.3.
- `ServiceAgreement` signers (provider + billing), billing DID and lifecycle, and §12.12 billing compromise agree with ARCHITECTURE §6.1.
- Live CDDL message set and error codes are used consistently by §11.4, §10.5.4 and §14.4.3.
- PowPolicy / `minPowDifficulty` / `powProof` / HTTP PoW are consistent between §3.3, §10.2.1, §10.5.2 and §11.6.
- Codepoints 0xF0A0, 0xF0A1 and 0xF0A2 match between §4.6, §5.2.1, §9.1 and Appendix D (apart from CON2-2).
- Pkarr record names are consistent between §2.1, §5.2.1.1 and §10.3.4.6.
- `IdentityChanged`, `HistoryTransfer`, `AddApproval`, `AbuseReport` and `KickRecord` (channelIDs) have consistent types and senders across parts.
- No dangling § numbers (scripted check of every § reference against headings).

Coverage: read fully ARCHITECTURE.md; spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; notes/review/reconciliation.md (status lookups only); bd decision memories.
