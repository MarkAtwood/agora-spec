# CON2 verified

Verifier pass over notes/review2/CON2.md. Each cited location was opened and checked against the rest of spec/, ARCHITECTURE.md and the bd decision memories (notably agora-doorkey-B, agora-broadcast-decision, agora-channelid, agora-d2-sequencer).

### CON2-1: Community channel admission key: served to every role holder, or only to speakers?
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:311; spec/05-messaging.md:49, :132
- Fix: Real contradiction. 03 §3.4 serves "to members permitted to read the channel (a role whose `channelAccess` covers it ...)" with no `community` exception; 05 §5.2.1 says the CO serves the key "only to members of the speaker group" and §5.2.1.2 says non-speakers "are not served the channel's admission key". The Space endpoint has no speaker list (speaker-group membership is MLS state; Space state holds only `speakerBot`). agora-doorkey-B ("served to authenticated members by the Space endpoint, rotated on removals") does not say whether "members" means channel role holders or MLS group members, and agora-broadcast-decision's "non-speakers can't read" is satisfied by MLS either way.
- Needs decision: yes. (a) Speakers only, endpoint keeps a speaker list fed by the SpeakerBot/admin, rotate on every eviction. (b) Every role holder gets the key; relay admission is role-wide, the speaker group bounds decryption only; reword §5.2.1 and §5.2.1.2. (c) Speakers only, no rotation on eviction. Recommend (b): no new endpoint state, matches §3.4 as written and doorkey-B, and avoids a key rotation per idle eviction (§3.4's "When the CO stops serving a channel to a member, it MUST rotate").

### CON2-2: `agora_admission_host` is required in DM GroupContexts, but no client is told to support it
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:73 (fix site); spec/04-access-control.md:158
- Fix: 04 §4.6 puts 0xF0A0 in `required_capabilities`; 05 §5.2.1 says only "Every Agora client lists 0xF0A1 in its leaf `capabilities`". Under RFC 9420 a leaf lacking a required extension cannot be added. Change to "Every Agora client lists 0xF0A0 and 0xF0A1 in its leaf `capabilities.extensions`."
- Needs decision: no

### CON2-3: No rule makes anyone update the DM admission host's member list when a member, logger or recorder is added
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:158, :259; spec/07-compliance.md:210-216, :336-352; spec/06-calls.md:466
- Fix: §4.6 is permissive ("any listed member replaces it after a membership change"); the only obligations are on create ("The initiator registers the list") and on leave (§4.8 line 259). §7.8.2 steps 1-5 and the §7.8 Conformance Summary never mention `DMMembers`. A new member not put on the list cannot authenticate to the host, and a regulated member in request state (§7.8.7) cannot sign a `DMMembers` replacement unless already listed. Apply the reviewer's fix: "The committer of every Commit that adds or removes a member MUST replace the member list by `DMMembers` before delivering the Welcome"; add the step to §7.8.2 after step 4 and to §6.12.7; add a Conformance Summary row (Committing client, MUST). The recorder clause is a clarity gain only: §6.12.7 already says `complianceLoggers` "records both text logger DIDs and VTC recorder DIDs", but §4.6 should say "compliance loggers and recorders" explicitly.
- Needs decision: no

### CON2-4: The TURN shared secret is IO key material that ARCHITECTURE S3 and S7 do not allow
- Verdict: CONFIRMED
- Severity: P2
- Location: ARCHITECTURE.md:97-101, :119-123; spec/06-calls.md:281
- Fix: S3: "The only key material an IO holds for a community is the verification material of §6.2: registered admission public keys and the routing tokens registered with them." S7 lists TURN explicitly. 06 §6.11 step 1 gives the TURN operator a CO-shared HMAC secret. Design is sound (no member identity exposed); the invariant text is wrong. Extend ARCHITECTURE S3 and S7 to name "the TURN REST shared secret of a `turn` agreement (protocol spec §6.11), which authenticates the CO credential service and identifies no member", and add it to §6 beside admission keys.
- Needs decision: no

### CON2-5: Client conformance class leaves out the new identity flows (§2.6 to §2.8)
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/01-overview.md:79
- Fix: The Client row lists §2.1, §2.2 then jumps to §3.3. §2.6 holds "Members MUST accept an own-device Add" and the self-group MUST; §2.7 holds the `IdentityChanged` send/receive rules, the only re-resolve signal. §1.4 limits obligations to listed sections. Add "§2.6, §2.7, §2.8 (multi-device, identity change notice, account deletion)" to the Client row.
- Needs decision: no

### CON2-6: Who receives admission key registrations: "every IO", "relays", or the agreement types marked Yes?
- Verdict: CONFIRMED
- Severity: P3
- Location: ARCHITECTURE.md:199-203, :221-225; spec/05-messaging.md:254; spec/10-relays.md:777; spec/03-spaces.md:354
- Fix: §10.5.1 table marks `turn` and `push-proxy` "No"; ARCHITECTURE §6.1 ("every IO, of any service type"), §6.2 ("every IO that holds a `ServiceAgreement`") and 05 §5.2.2 ("every relay and other IO") contradict it; §10.5.3 ("The IOs holding the agreements a registration service uses are the relays it lists to members") and 03 §3.6 step 4 ("with its relays") omit SFUs and sequencers, which §6.6 and §14.4.1 say receive registrations. Use the §10.5.3 opening wording everywhere ("every IO holding a `ServiceAgreement` whose `serviceType` receives registrations (§10.5.1)"); restrict the "relays it lists" sentence to `relay` agreements.
- Needs decision: no

### CON2-7: Is `expiryHint` authenticated or not?
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:409 (fix site) vs :240
- Fix: §5.2.2: "It is authenticated in the same weak sense as `ts`"; §5.2.4: "This field is unauthenticated at the outer layer". Replace the §5.2.4 sentence with "It is covered by `admissionSig`, which shows only that some key holder set it (§5.2.2); Relays use it as a hint only."
- Needs decision: no

### CON2-8: Broadcast channels have no MLS group, but the example and the creation steps give them one
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/03-spaces.md:97, :351, :242
- Fix: The broadcast entry of the §3.3 example (lines 90-98, `"mode": "broadcast"`) carries `"mlsGroupID"` at line 97, contradicting §3.2 ("None (§5.2.1.4)") and §5.2.1.4. §3.6 step 1 gives "for each initial channel, a `channelID` and an MLS group". Remove line 97's `mlsGroupID`; step 1: "a `channelID` and, for a channel that has one (§3.2), an MLS group"; field index line 242: add "absent on `broadcast`". (§3.6 Create at :359 already says "for a channel that has one".)
- Needs decision: no

### CON2-9: The DM group ID is called `groupID` in some places and `mlsGroupID` in others
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/04-access-control.md:150, :158
- Fix: §4.6's DM `ChannelAdmissionKey` "carries `groupID`" and `DMMembers` body is `{"groupID": ...}`, while `DMGroupDescriptor` (04:166) and the compliance records use `mlsGroupID`. Rename the two JSON fields to `mlsGroupID`; keep the `<groupID>` URL path segment. Consistent with agora-channelid ("DMs named by group ID").
- Needs decision: no

### CON2-10: Pinning in DM groups cannot be done
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:445, :465; spec/14-jmap.md:153
- Fix: §5.2.6 grants pin rights "in a group chat, admins" but pins are `sequenced-v1` "ordered by the Space's blind sequencer"; DM groups have no Space, no sequencer (05:28 "including in every DM group") and no defined admins. The §14.4.1 rule "If `sequencer` is absent, `sequenced-v1` types in the Space are read-only" covers Spaces only.
- Needs decision: yes. (a) No pin lists in DM groups (extend the §14.4.1 read-only rule to DM groups and drop "in a group chat, admins"). (b) A DM-specific model (per-pinner `single-author`, or a sequencer named by the admission host). Recommend (a): it follows the existing no-sequencer rule and agora-d2-sequencer adds no DM sequencer.

### CON2-11: `RelayPeerAnnouncement` is a "gossip message" with no topic allowed to carry it
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:256; :282-286, :332; spec/05-messaging.md:395
- Fix: §10.2.6 sends it "as a `RelayPeerAnnouncement` gossip message"; §10.3.1 allows only SpaceAds/RelayAds on `v1/agora/discovery` and §10.3.2 says a Relay "MUST NOT forward any record on `v1/agora/discovery` other than a SpaceAd or RelayAd". Carry it over the Peer API (`POST /v1/agora/peer/announce`, 10:153, already exists for peer introduction) to Level 2+ peers, and change the 05:395 row to "relay-to-relay Peer API".
- Needs decision: no

### CON2-12: §10.5.2 calls the sequencer a CO endpoint
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:760
- Fix: "A CO HTTP endpoint ... or a sequencer (§14.4)" conflicts with ARCHITECTURE.md:61 (Sequencer | IO). Write "An HTTP endpoint, CO or IO, that requires proof of work ...".
- Needs decision: no

### CON2-13: Conformance classes cite the wrong sections, or too few, for the new services
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/01-overview.md:84, :90, :91
- Fix: Space endpoint row already lists §3.4 first, so the problem is only the mislabeled parenthetical: change "§5.2.1.4 (`ChannelAdmissionKey` and `BroadcastKey` service)" to "§5.2.1.4 (broadcast key policy)" or drop it. For Sequencer and SFU, §14.4.3 step 3 and §6.6 join check already place the admission obligations themselves (citing §10.5.3/§10.5.4); what is genuinely unbound is registration intake and agreement lifecycle. Use the Relay row's form: "§14.4 and the sections it cites" / "§6.6, §6.9, §6.10 and the sections they cite", or add "§10.5.1, §10.5.3" explicitly (§10.5.4 is reached through the citations).
- Needs decision: no

### CON2-14: Dangling or wrong cross-references in the new text
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/12-security.md:179; spec/05-messaging.md:353; ARCHITECTURE.md:265
- Fix: (1) `x-agora-timestamp` appears nowhere else; §10.2.3 uses RFC 9421 `created` ("integer seconds since the Unix epoch", 10:190). Write "the RFC 9421 `created` parameter (§10.2.3)". (2) `IdentityChanged` row cites "(§2.1, §2.3)"; it is defined in §2.7: cite §2.7. (3) ARCHITECTURE "Pin and delete instructions": `PinInstruction` `op` is "pin" / "unpin" only (11:146); write "Pin and unpin instructions".
- Needs decision: no

### CON2-15: §3.5 has no case for the guest Space endpoint authenticating the home CO
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/03-spaces.md:343; spec/08-cross-space.md:98
- Fix: §8.6 requires the guest endpoint to serve state to the home CO "authenticated per §3.5 as `homeAdminDID`", but §3.5's checks admit only current members, DM members, eligible guests and invitees. Add to §3.5's parenthetical: "for a guest Space endpoint, the `homeAdminDID` of an in-force `ChannelShareAgreement` naming that Space (§8.6), which grants the guest Space's state only".
- Needs decision: no

### CON2-16: DM admission host responses are unspecified
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/04-access-control.md:153-158; spec/03-spaces.md:313
- Fix: §3.4 Responses says "Every other response is the record's encoded typed payload envelope with `sig` present", which the DM record (no `sig`) cannot satisfy, and the `PUT .../members` result is undefined. In §4.6 add: GET returns the encoded envelope without `sig` as `application/cbor`; PUT takes the encoded `DMMembers` envelope, returns 204, and otherwise 401/403/404/429 as §3.4, plus 409 for a `ts` not later than the current list's.
- Needs decision: no

### CON2-17: Appendix D leaves out identifiers that the new text allocates
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/99-appendices.md:117-149
- Fix: Drop `AgoraProvisioning`: no such DID service type exists anywhere in spec/ (grep finds none; 02:415 is a revocation body). The rest holds: `_corundum._agora` (10:497) is missing from the `_agora` children row; WebSocket subprotocol `agora-sfu.v1` (06:108) needs a Web identifiers row with IANA "WebSocket Subprotocol Name Registry" (RFC 6455 §11.5); `serviceType` values `relay`, `sfu`, `sequencer`, `turn`, `push-proxy` (§10.5.1) go in the capability and model strings table.
- Needs decision: no

### CON2-18: Appendix C has a stale default and is missing the new numeric rules
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/99-appendices.md:82
- Fix: "lesser of `expiryHint` and the retention window (default 30 days)" conflicts with §10.4.3 (10:580) and §10.4.6 (10:636), which use the agreement's `retentionDays` and give no default. Change to "lesser of `expiryHint` and the agreement's `retentionDays`" and add the missing rows listed by the reviewer (5 s canonical-Commit window, 60 s previous sealing key, hourly admission key fetch, 7-day undecidable Welcome hold, 30 s SFU challenge freshness, 32/1000 generation window).
- Needs decision: no

### CON2-19: The new Space field index omits `vtcCompliance`
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/03-spaces.md:200-233
- Fix: §3.3 claims to "list every field"; `complianceLogging` is present (line 228), `vtcCompliance` (06:420-441) is not. Add "`vtcCompliance` | `VTCComplianceConfig` | optional | §6.12.5".
- Needs decision: no

## Counts

- CONFIRMED: 17 (P2: 5, P3: 12)
- CONFIRMED-ADJUSTED: 2 (P3: 2; CON2-13, CON2-17)
- REJECTED: 0
- Needs decision: CON2-1 (recommend b), CON2-10 (recommend a)
