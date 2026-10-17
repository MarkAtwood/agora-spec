# CON verified

Verifier pass over notes/review/CON.md. Every cited location was re-read and spec/ plus ARCHITECTURE.md grepped for text that already resolves the finding. Checked against bd memories agora-* (D1-D7, Q1-Q6, did-methods, broadcast, format-open).

### CON-1: `channelCID` is the exporter context for token, access key and sealing key, but is never defined
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:194, :202, :218; spec/03-spaces.md:55-97 (channel entries have `path`, `type`, `mode`, `name`, `mlsGroupID`, with no CID); spec/03-spaces.md:166, :173; spec/04-access-control.md:125
- Fix: Define the per-channel identifier and its exact byte encoding as exporter context once in §3.3. Then point §5.2.2, §3.4 (`/broadcast-key/<channelCID>`), §6 and §7 at it. For DM groups, say which identifier and label apply. Today 04:125 uses `"agora-dm-token"` with empty context and gives no access or sealing derivation. Grep found no definition anywhere: `channelCID` appears only as a context and as a JSON field with the value `"bafyrei..."`.
- Needs decision: yes. The options are (a) a random, immutable `channelID` in the channel entry; (b) the CID of an immutable channel-genesis record; (c) `mlsGroupID`. Recommend (a). With (c), the context changes whenever a group is recreated, and `mlsGroupID` is S1-sensitive. For DMs, use `dmGroupID` (04:131, already stable), not `DMGroupCID`, which changes on every membership change (04:145).

### CON-2: `accessSig` and `billingSig` sign "the envelope with the signature omitted", which contradicts §13.1's no-canonical-form rule; the routing envelope field set is scattered
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:206 (accessSig), :204 (billingSig), :196 (`id` is "CID of the canonical outer envelope"); spec/13-encoding.md:9, :27, :49; spec/11-transport.md:54 (relays accept JSON and CBOR), :236 (`pushUrgency`); spec/10-relays.md:676 (`powProof`); spec/05-messaging.md:138 (`broadcastPayload`)
- Fix: As the reviewer proposes. Write one normative `RoutingEnvelope` definition listing every member. Define `accessSig` over an explicit byte string, and state whether `powProof` and `pushUrgency` are covered. Make `accessKeyAnnouncement` a typed envelope with named members, signed with the previous access key, with `billingSig` as a §13.1.1 `sig` entry. Redefine `id` so it does not hash itself. All of this follows from D1/D6 (signatures over exact bytes, no canonicalization).
- Needs decision: no

### CON-3: Every access-key announcement needs a CO `billingSig` authorized "under Space state", which DM groups cannot obtain
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:204; spec/04-access-control.md:125, :151
- Fix: Specify who registers and countersigns DM access chains, and how "current member" is established without Space state. Q1 (countersign every epoch announcement) and Q6 (agreements are signed by a CO billing DID) do not address DMs. The text as written makes DMs undeliverable: 04:125 says DM groups "do not appear in any Space state document" and 05:204 says "Relays MUST reject an announcement without a valid `billingSig`".
- Needs decision: yes. The options are (a) the creator's CO countersigns, with an individual-as-own-CO profile for users without an org; (b) DMs are exempt and accept the removed-member lock-out race (this reopens Q1 for DMs); (c) each member's CO registers the chain separately. Recommend (a), because it keeps Q1 intact.

### CON-4: Shared channels need two COs' `billingSig` on one announcement, but the format allows one
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/08-cross-space.md:98; spec/05-messaging.md:204
- Fix: Let `billingSig` carry one §13.1.1 entry per agreement under which the chain is registered (§13.1.1 already supports multi-signer `sig`). State that the guest CO authorizes on the basis of the `ChannelShareAgreement` plus its own member list. This depends on the CON-2 fix that turns the announcement into a typed envelope.
- Needs decision: no

### CON-5: Broadcast key rotation requires a second countersigned announcement for the same epoch, which §5.2.2 forbids
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:136 vs :204
- Fix: Make the uniqueness rule "at most one announcement per chain and (`epoch`, `channelToken`)". Alternatively, add `keyEpoch` to the announcement and key the rule on (`epoch`, `keyEpoch`).
- Needs decision: no

### CON-6: §10.5 calls RelayServiceAgreements optional, but relays MUST verify access proofs that exist only under an agreement
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:584 vs :527, :612; ARCHITECTURE.md S7; spec/11-transport.md:48 vs spec/10-relays.md:667, spec/11-transport.md:114, spec/12-security.md:62
- Fix: Delete "Both mechanisms are optional extensions" for the agreement and keep PoW optional. Change 11:48 to "per-`channelToken` rate limits (and PoW where the Relay requires it)". Q2 makes PoW optional under load, so 11:48's MUST also contradicts the decision.
- Needs decision: no

### CON-7: Welcomes are listed as live-stream traffic, contradicting "never on a gossip topic"
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:9, :406 vs spec/05-messaging.md:51, spec/04-access-control.md:147, spec/10-relays.md:264
- Fix: Remove "Welcomes" from 11:9 and "/ Welcome" from the 11:406 row. Add a pointer to the `KeyPackageEndpoint` (§4.6, §5.2.1.1). This follows from Q3.
- Needs decision: no

### CON-8: The JMAP `Envelope` exposes `seqNo` (which is inside the ciphertext) and does not match `RoutingEnvelope`
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:336, :349; spec/05-messaging.md:226; spec/10-relays.md:561 (SHOULD-level second history API); spec/11-transport.md:279 vs :341-350, :404
- Fix: As the reviewer proposes. Drop `seqNo`. Store the exact encoded `RoutingEnvelope` bytes plus `receivedAt` and the CID. Delete 10:561 or make it an alias. Either define `Envelope/set` with the access proof or delete the write clause at 11:279.
- Needs decision: no

### CON-9: §12.6 allows P-256 device keys, but the MLS ciphersuite, JWS and §2.2 are Ed25519-only
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/12-security.md:89; also 12:91 ("MLS leaf operations ... MUST use keys held in the secure boundary", which cannot be met on Secure Enclave) and 12:121 ("generated inside the device's secure enclave"); spec/02-identity.md:80, :255; spec/05-messaging.md:46; spec/13-encoding.md:76
- Fix: Delete the P-256 allowance (D6 fixes Ed25519). Relax 12:91 and 02:255 to "hardware-backed where the platform supports Ed25519, otherwise the best protected software store". Fix 12:121 to match.
- Needs decision: no

### CON-10: The pin list is `sequenced-v1` with `#Chat` bodies in §5.2.6, but §14 has no such default and requires `JmapSet` for sequenced operations
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:354-364; spec/14-jmap.md:61, :73, :158
- Fix: Add a §14.2.3 row: `Chat.pinnedMessageIds` | `sequenced-v1` | holders of `pin`. Change §5.2.6 so pin updates are `JmapSet` patches on `Chat` carrying `after`, per §14.4.3.
- Needs decision: no

### CON-11: Relays must keep `pushHandle` → `channelTokens` registrations, which is outside the relay observation budget
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:160, :194-203; ARCHITECTURE.md:161 (item 7, "For push proxies only"); spec/12-security.md:22
- Fix: Add a relay item to ARCH §5 for push registrations (`pushHandle`, proxy endpoint, registered `channelToken`s) and mirror it in §12.3. Define how registrations follow token rotation each epoch; 11:194-212 does not say. Q4 decided push-on, and the budget text was never updated.
- Needs decision: no

### CON-12: DM delivery uses "relay hints" from the recipient's DID document, which §2 forbids
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:151, :153; spec/02-identity.md:37, :302; spec/10-relays.md:476 (step 4, "use relay endpoints", although the record format at 10:455-466 has no relay field)
- Fix: Rewrite §4.6 "Relay routing" and "Cross-topology reachability". Delete "relay endpoints" from 10:476. 04:153 also uses `did:web` (see CON-17).
- Needs decision: yes. The options are (a) no per-user relay hints: the sender uses its own CO's relays and relies on mesh/peering; (b) relay hints in a CO-signed per-user record; (c) hints exchanged inside the DM group after first contact through the `KeyPackageEndpoint`. Recommend (a)+(c). (b) needs a new record type and risks naming IOs against identity (ARCH §2).

### CON-13: The channel history head is said to live in CO-signed channel state, which members cannot update per message; history append is undefined
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:318-320; spec/03-spaces.md:131; dependants spec/04-access-control.md:118, :155, spec/06-calls.md:277, spec/09-interop.md:195, spec/14-jmap.md:115
- Fix: Replace the DAG/"channel state document tracks the latest history CID" model.
- Needs decision: yes. The options are (a) history is the relay-indexed set of envelopes per token, read through the sync API; (b) a per-sender hash chain inside the encrypted payload; (c) periodic CO-signed checkpoints. Recommend (a), optionally with (c). This also settles the "tombstone in the IPLD history DAG" language at 04:118 and DM history at 04:155.

### CON-14: Space state is a linear signed chain in §3.3 but merged by union/LWW in §5.1.1
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:49, :131, :157-159 (`/head` returns one CID); spec/05-messaging.md:24
- Fix: Replace 05:24 with a fork rule: a deterministic winner (higher `seq`, then owner over admin, then lower CID). The losing branch's mutations are re-signed on top of the winner. An unsigned "union" cannot be valid state under 03:131 (S4). This follows from existing rules.
- Needs decision: no

### CON-15: The epoch access proof is used outside envelopes (pin instructions, SFU admission) with no defined form
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:368, :374; spec/10-relays.md:536; spec/06-calls.md:111; ARCHITECTURE.md:210-213
- Fix: As the reviewer proposes. Define a typed `PinInstruction` (CIDs, `channelToken`, `epoch`, nonce/expiry) signed with the access key, plus its relay endpoint. Define SFU admission as a challenge signed with the access key, and state how the SFU learns the access public key. The SFU has no `AccessChainRegistration`, so it needs an `accessKeyAnnouncement` chain or must be a relay-registered party. Grep found no definition of either.
- Needs decision: no

### CON-16: The KeyPackage Store API is referenced as a versioned surface but its wire protocol is never defined; its fragments disagree
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:61-73; spec/13-encoding.md:117; spec/07-compliance.md:185-195; spec/10-relays.md:457
- Fix: The reviewer overstates the gap. §5.2.1.1 (05:61-73) does define the behaviour: atomic consume on fetch, leaf-credential check, last-resort KeyPackage, rate limiting, and Welcome by POST. What is missing is the wire layer: the service `type` string, which differs between `KeyPackageEndpoint` and `AgoraKeyPackageEndpoint` (07:190); the path (`/v1/agora/kp/` vs `/v1/agora/keypackages`); and the publish method and its device-key authentication. Add these to §5.2.1.1 and align 07:190-191, 10:457 and 13:117.
- Needs decision: no

### CON-17: `did:web` is treated as a user identity in §4.6, §9.1 and Appendix A; §2.1/§14.6.2 exclude it
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/09-interop.md:24; spec/04-access-control.md:153; spec/99-appendices.md:11
- Fix: Replace with `did:webvh` / `did:plc` / `did:key` (decision agora-did-methods). In 99:11, note that `did:web` is used for relay DIDs (10:110).
- Needs decision: no

### CON-18: The MIMI section requires 0x0001 "in addition to any other suites"; §5.2.1 allows only 0x0001
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/09-interop.md:20
- Fix: Use the reviewer's wording: "Agora groups use 0x0001 (§5.2.1), which is the MIMI baseline."
- Needs decision: no

### CON-19: Wrong or stale cross-references
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:285; spec/10-relays.md:120; spec/11-transport.md:260; spec/12-security.md:56, :132; spec/08-cross-space.md:3; spec/13-encoding.md:32
- Fix: Apply the reviewer's fixes. Each was checked: §10.3 is Discovery; ARCH has no §5.3, and the relay JMAP item is §7 item 4; Q2 is ARCH §8; the helpdesk path is 02:471 in §2.5.8; 08:3 vs 08:6; there is no `PresenceEvent` type. For 12:56, ARCH §7 item 9 also fits. Separately, 02:285 has a provisioning service "publish DID document updates" to gossip, a role §10.3 does not define. Changing the reference alone leaves that claim unsupported, so consider deleting the bullet.
- Needs decision: no

### CON-20: Same concept, different names across parts
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/06-calls.md:306; spec/05-messaging.md:196; spec/14-jmap.md:60, :111; spec/02-identity.md:35 / spec/10-relays.md:465; spec/10-relays.md:102 vs :116, :298; spec/10-relays.md:346 vs :642; spec/03-spaces.md:119, spec/14-jmap.md:132
- Fix: Apply the reviewer's fixes, except drop the `regulatedMembers` sub-item. 07:52 already says "The field is part of the `ComplianceLoggingConfig`", and it is optional, so leaving it out of the example is not an inconsistency. The manifest-signer item is worth keeping, because 10:120 distinguishes `operatorDID` from `relayDID`, so "operator's key" is genuinely ambiguous.
- Needs decision: no

### CON-21: Sender identity fields and non-URN types inside MLS bodies contradict §5.2.2 / §13.1 / §14.3.2
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/06-calls.md:27; spec/09-interop.md:189; spec/07-compliance.md:221, :227; spec/04-access-control.md:145
- Fix: Remove `sender`/`addedBy`/`issuedBy`, or state that each MUST equal the MLS sender and is otherwise ignored. Name `urn:agora:type:ComplianceDisclosureNotice` and `urn:agora:type:DMGroupDescriptor` and add them to the §5.2.3 table.
- Needs decision: no

### CON-22: Signers and fields that other parts rely on are unspecified
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/07-compliance.md:266, :276; spec/12-security.md:123, :147; spec/02-identity.md:469 vs :224-229
- Fix: Apply the reviewer's fixes. Name the `DMComplianceAuditEntry` signer and define a gap-record type. Either source the "signing key fingerprint" from the MLS leaf credential and record it in `ComplianceRecord`, or soften 12:123/12:147; no "MLS authenticated data" field carries it today. Qualify 02:469 to software keystores.
- Needs decision: no

### CON-23: Terms used but never defined
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:275, :298, :302 (`UserAd`); spec/03-spaces.md:184, spec/05-messaging.md:204, spec/06-calls.md:214, spec/14-jmap.md:216 (CO DID auth); spec/04-access-control.md:121; spec/09-interop.md:50, :96, :179 and spec/05-messaging.md:318 ("channel state document")
- Fix: Apply the reviewer's fixes. Grep confirms there is no `UserAd` schema and no defined DID-auth method for CO services. "Channel state document" has no definition apart from the channel entry in Space state.
- Needs decision: no

### CON-24: The version registry claims to list "every versioned protocol surface" but omits several
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/13-encoding.md:106-121; spec/01-overview.md:21
- Fix: Add the missing rows (JMAP sync, blob, Space endpoint, sequencer, SFU, TURN credential, `/.well-known/agora-relay`), or narrow the claim. Pick 404 or 404/410 in both places.
- Needs decision: no

### CON-25: Other cross-part inconsistencies on observation and declarations
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:628 vs :87; spec/12-security.md:22; spec/11-transport.md:233; spec/14-jmap.md:193 vs ARCHITECTURE.md:157-160
- Fix: Apply the reviewer's fixes. On the sequencer item: D2 settles per-community sequencers, so the fix is an explicit ARCH §5 item 6 exception (or a cross-reference to §14.4.6), not a design change. SFUs named in `SFUDescriptor` (06:110) are in the same position and belong in the same exception.
- Needs decision: no

### CON-26: Exporter and KDF label inventory: all unique, naming style inconsistent
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/04-access-control.md:125; spec/06-calls.md:160; spec/13-encoding.md (no registry)
- Fix: The inventory is accurate (re-grepped). Mixed hyphen/space style alone is cosmetic: the labels are opaque byte strings and cause no interop problem, so do not renormalize for style alone. The substantive part is adding a label registry table to §13 to prevent future collisions. The DM empty-context issue is CON-1's.
- Needs decision: no

---

## Counts

- CONFIRMED: 23 (CON-1 to CON-15, CON-17 to CON-19, CON-21 to CON-25)
- CONFIRMED-ADJUSTED: 3 (CON-16, CON-20, CON-26)
- REJECTED: 0
- Severity after adjustment: P1 3 (CON-1, 2, 3); P2 13 (CON-4 to CON-16); P3 10 (CON-17 to CON-26)
- Needs decision: CON-1, CON-3, CON-12, CON-13
