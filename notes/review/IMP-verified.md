# IMP verified

Verifier pass over notes/review/IMP.md. Every claim of "undefined" was grep-checked across spec/*.md and ARCHITECTURE.md, and checked against `bd memories agora`. Line numbers for spec/13-encoding.md in IMP.md are off by about 64 lines (the file has 125 lines); corrected locations are given below. All other cited line numbers were spot-checked and are accurate.

### IMP-1: The live client-relay protocol has no message set
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/11-transport.md:36, :54-64, :80-135, :398-407
- Fix: As proposed. Only ClientHello, RelayHello, AdmissionChallenge and AdmissionProof exist (11:80-133). No grep hit anywhere for a subscribe, publish, deliver, ack or pin message. "channel ID prefix" (11:36) does not appear in the frame structure (11:59). §11.8.8 assigns push registration and MLS handshake to the live stream only, so the gap blocks those features too.
- Needs decision: yes. (a) native CBOR frame and Control message set; (b) RFC 8887 JMAP-over-WebSocket with Agora methods; (c) HTTP writes plus a delivery-only stream. Recommend (a). (c) contradicts the §11.8.8 table as written, and no recorded decision prefers it.

### IMP-2: Exact bytes covered by `accessSig`, `billingSig` and the envelope `id` are undefined
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/05-messaging.md:181-206; spec/13-encoding.md:21, :27 (not :85, :91)
- Fix: The `accessSig` input and the circular `id` ("CID of the canonical outer envelope", 05:196, against 13:9 "Agora computes no canonical form") are real gaps. `billingSig` is partly settled already: 13:27 lists "the `accessKeyAnnouncement` countersignature" among objects "stored, served and forwarded as its encoded envelope with `sig` present". That makes the announcement a typed envelope whose `body` is signed per §13.1.1, so `billingSig` = that envelope's `sig` entry by the billing DID. Still undefined: the announcement's own signature by the previous epoch access key. That key is not a DID, so §13.1.1's DID-URL `kid` cannot name it. Define it as a raw Ed25519 signature over the announcement `body` bytes with a domain-separation prefix.
- Needs decision: yes, narrowed. D1/D6 ("signatures over exact bytes; no canonicalization") and 13:49 ("no canonical CBOR ... is computed") exclude option (a), deterministic CBOR. Remaining options: (b) a fixed binary concatenation for `accessSig`; (c) carry the signed envelope fields as one byte string (a §13.1 envelope `body`) and sign those bytes. Recommend (c) for announcements, which is already implied by 13:27. For `accessSig`, choose between (b) and (c). Define `id` as computed over bytes that exclude `id`, or drop it from the wire.

### IMP-3: `accessKeyAnnouncement` and the registration-service API do not exist as wire formats
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:203-205; spec/10-relays.md:612-624; spec/13-encoding.md:27 (not :91)
- Fix: As proposed. "registration service" appears only at 05:203-205, 10:612/624, 14:136 and ARCHITECTURE:181/198/276, and none of these gives an endpoint, field list or relay intake. Constraint from Q6: the locator for the registration service may sit in Space state, but the billing DID must not (10:608). Agreement exchange to the relay also needs an endpoint, because the agreement is private and never gossiped (10:610).
- Needs decision: no.

### IMP-4: Broadcast key rotation cannot be countersigned under the one-per-epoch rule
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/05-messaging.md:133-136, :204
- Fix: The contradiction is real. The proposed fix is partly wrong: "have the registration service ... issue the rotation announcement itself" fails because the announcement must be signed with the current epoch access private key (05:136, 05:203), which the CO does not hold. The CO is not a publisher-group member and holds no MLS secrets (05:129). Correct fix: make the countersignature uniqueness key (chain, `epoch`, `channelToken`) or (chain, `epoch`, `keyEpoch`), and carry `keyEpoch` in the announcement. A poster still signs. The service countersigns the first request for a given key and returns that same countersigned announcement to later requesters, which settles the race among posters.
- Needs decision: no.

### IMP-5: `channelCID` is used as exporter context but never defined; DMs have none
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:194, :202, :218; spec/03-spaces.md:166; spec/04-access-control.md:125, :145
- Fix: Grep finds no definition of `channelCID` anywhere. Channels are entries in SpaceState (03:60-98), not content-addressed objects. The only DM CID changes on every membership change (04:145), which would change access and sealing keys mid-epoch. Also used as an identifier in BroadcastKey (03:173), BroadcastMessage (05:148), SpeakRequest (05:98), RecordingGrant (06:250) and `homeChannelCID` (08:81).
- Needs decision: yes. (a) MLS `group_id` (`mlsGroupID`, already REQUIRED on every channel entry with a group, 03:137, and present in DMGroupDescriptor, 04:134) as exporter context and channel identifier; (b) a minted `channelID`. Recommend (a).

### IMP-6: CID computation and the Space genesis self-reference are undefined
- Verdict: CONFIRMED-ADJUSTED (location only)
- Severity: P1
- Location: spec/13-encoding.md:27 (not :91); spec/01-overview.md:43; spec/99-appendices.md:12; spec/03-spaces.md:36, :49, :55
- Fix: As proposed. Grep for multicodec/multihash/sha2-256/base32 finds nothing. 01:43 and 99:12 say "dag-cbor", but 13:21 says envelopes are non-canonical CBOR maps, so they are not valid dag-cbor. Also fix 01:43 and 99:12 to the chosen codec.
- Needs decision: no.

### IMP-7: MLS credential format and the leaf-to-DID binding are undefined
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/05-messaging.md:55, :79-80; spec/02-identity.md:80; spec/12-security.md:258-260; spec/09-interop.md:28-36
- Fix: Part of this is already stated: 02:80 says "Each device signs with its own Ed25519 device key: its MLS leaf signatures", so `signature_key` = a device `authentication` key. Still undefined: the credential type and the bytes of `identity` (no grep hit for BasicCredential or credential type), how key bytes are matched, and the P-256 conflict (12:258 allows P-256 authentication keys, while 05:46 mandates the Ed25519-only suite 0x0001). Forbid P-256 for MLS leaves. The MIMI credential at 09:32 has no MLS encoding.
- Needs decision: no.

### IMP-8: KeyPackage endpoint and Welcome delivery have no API
- Verdict: CONFIRMED-ADJUSTED (location)
- Severity: P1
- Location: spec/05-messaging.md:50-51, :63-73; spec/07-compliance.md:185-195; spec/13-encoding.md:117 (not :181); spec/02-identity.md:302, :381; spec/04-access-control.md:147
- Fix: As proposed. The type mismatch is confirmed: 07:190 uses `"type": "AgoraKeyPackageEndpoint"`, while 02:19/302, 05:63 and 10:466 use `KeyPackageEndpoint`. Q3 (KeyPackages at the identity host, found via the DID-doc KeyPackageEndpoint) settles where the endpoint is, not its API. The per-device fetch is a real gap: 05:65 says "a fetch atomically consume[s] the returned KeyPackage", one per fetch, while each device is a leaf (02:78).
- Needs decision: no.

### IMP-9: Concurrent Commits: no rule chooses the winning Commit
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2 (from P1)
- Location: spec/05-messaging.md:23, :203-205; spec/04-access-control.md:16
- Fix: The normal path is mostly serialized already. 05:204 says "The committer obtains it from the service before publishing the Commit" and "at most one announcement per chain and `epoch`", so a careful loser cannot obtain a countersignature and does not publish. The gaps that remain: (1) the outage path (05:205) allows Commits while the service is unreachable, and the text does not say whether those may be published; (2) no rule tells clients to reject a Commit whose envelope lacks a countersigned announcement; (3) the loser's action is unstated; (4) `commitPolicy` has no schema (only 04:16). The fix follows from Q1: the Commit for epoch N+1 is the one carried with the countersigned announcement for N+1, no Commit is published without one (including during outage), and the loser discards and retries.
- Needs decision: no.

### IMP-10: HTTP representation of signed objects is undefined (CBOR envelope vs JSON)
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2 (from P1)
- Location: spec/03-spaces.md:157-158, :166-167; spec/10-relays.md:49, :102, :315, :359; spec/13-encoding.md:27
- Fix: 13:27 already gives the rule a careful implementer follows: an object verified outside MLS "is stored, served and forwarded as its encoded envelope with `sig` present". A detached JWS cannot sit inside a bare JSON file, so the manifest and directories must be envelopes. "signed JSON document" (10:49) and "static JSON file" (10:315) contradict that rule and need fixing. Still undefined: media type, the `/head` response format, the BroadcastKey response, and status codes. Divergence in these is recoverable, so P2.
- Needs decision: no.

### IMP-11: Member and device authentication to CO services is unspecified
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/03-spaces.md:184; spec/05-messaging.md:204; spec/06-calls.md:214; spec/02-identity.md:320-336; spec/14-jmap.md:216
- Fix: As proposed. The only RFC 9421 profile is relay-to-relay (10:165-183), and Q2 removed DID login only for relays. Nothing covers CO services.
- Needs decision: yes. (a) RFC 9421 per request with a DID-URL `keyid`; (b) challenge/response yielding a bearer token. Recommend (a), reusing the §10.2.3 machinery once IMP-27 fixes that profile.

### IMP-12: SFU signaling protocol is undefined
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/06-calls.md:84-119
- Fix: As proposed. Also 06:88 says "the SFU's signaling messages are signed by the DID in that entry", but no signature format exists, and 06:111 says the client "presents the MLS-membership access proof", with no challenge or replay rule.
- Needs decision: no.

### IMP-13: Attachment encryption is contradictory and the key field is undefined
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/05-messaging.md:255; spec/14-jmap.md:117; spec/03-spaces.md:190
- Fix: As proposed. Checked draft-atwood-jmap-chat-00 §Attachment (~/PROJECT/jmap-chat-spec, line 241): its fields are `blobId`, `filename`, `contentType`, `size` and `sha256`, with no key field. So Agora must define the extension field and the blob layout.
- Needs decision: no.

### IMP-14: Gossipsub parameters needed for mesh interop are missing
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:154-156, :253-266
- Fix: As proposed. The client-to-relay subscription part overlaps IMP-1.
- Needs decision: no.

### IMP-15: Space state schema is scattered and missing fields that signature checks need
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:51-145; spec/04-access-control.md:14, :16, :121; spec/05-messaging.md:318; spec/09-interop.md:53, :99
- Fix: As proposed, with two additions. (1) The SpaceState example has no member list or member-to-role assignment, which §4.2 role assignment and JMAP Chat SpaceMember `roleIds` need. (2) JMAP Chat leaves the admin predicate "deployment-defined" (draft-atwood-jmap-chat-00:337), so Agora must define it. Either an explicit `admins` list or a stated mapping from SpaceRole permissions (`manage_space`, `manage_members`, `manage_channels`) to admin scope would work. Reusing roles and permissions is the smaller change, consistent with 03:135.
- Needs decision: no.

### IMP-16: Space state ordering contradicts the signed hash chain
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:25; spec/03-spaces.md:49, :157
- Fix: As proposed. No recorded decision supports union/LWW merge.
- Needs decision: no.

### IMP-17: Sequencer wire details are incomplete, and pin updates use the wrong type
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/14-jmap.md:156-165; spec/05-messaging.md:354, :362-364
- Fix: As proposed. Confirmed: 05:354 gives type `urn:ietf:params:jmap:chat#Chat` and 05:364 says "MUST submit a pin update per §14.4.3", while 14:158 says the envelope "has `type` `urn:agora:type:JmapSet`". Also confirmed: 14:158 makes the raw MLSMessage the operation, which exposes the constant `group_id` to the sequencer (05:216 explains why that framing is otherwise sealed).
- Needs decision: no.

### IMP-18: MLS group configuration is unspecified
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:46-55, :214, :303; spec/02-identity.md:44, :74, :314
- Fix: As proposed. The init-key conflict also appears at 02:74 and 02:314.
- Needs decision: no.

### IMP-19: The Space endpoint has no error or offline behaviour, and Welcome validation depends on it
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/03-spaces.md:154-186; spec/04-access-control.md:78; spec/05-messaging.md:131
- Fix: As proposed. Invite presentation ties to the IMP-11 profile.
- Needs decision: no.

### IMP-20: Device registration and revocation have no HTTP binding
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:320-336, :379, :417-421
- Fix: As proposed. `DeviceRevocation` (02:421) and the "DID document hash" gossip (02:379) have no schema anywhere.
- Needs decision: no.

### IMP-21: Social recovery share format is undefined across clients
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:171, :188, :198
- Fix: As proposed. Also name which guardian `keyAgreement` key is the target when a guardian has several devices.
- Needs decision: no.

### IMP-22: Field encodings in JSON bodies are not normative
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/02-identity.md:327-328; spec/10-relays.md:620; spec/05-messaging.md:185-189; spec/03-spaces.md:67
- Fix: As proposed. Grep finds no padding or RFC 4648 rule anywhere in spec/.
- Needs decision: no.

### IMP-23: Relay blob upload and pin instructions have no format or authorization
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:271, :279; spec/05-messaging.md:368-376; spec/10-relays.md:536-537
- Fix: As proposed.
- Needs decision: no.

### IMP-24: JMAP Envelope object does not match the routing envelope
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:327-350, :279
- Fix: As proposed. Also, 11:329 "always MLS ciphertext" is false for `broadcastPayload` envelopes (05:138).
- Needs decision: no.

### IMP-25: Push registration endpoint at the relay is ambiguous
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/11-transport.md:184, :194-203, :253-254, :407
- Fix: The "same path" point is not itself ambiguous, because the proxy and the relay are different origins, and an absolute path on the relay origin is resolvable as with `/v1/agora/blob/` (10:570). The real conflicts: the §11.8.8 table says registration happens on the live stream only, while §11.7.3 step 4 uses HTTP. Also missing: the relay TTL field, the relay-side DELETE, and how the old `pushHandle` is carried (11:253). Pick one transport (a Control message per IMP-1 is consistent with the table) and give a body with `replaces`.
- Needs decision: no.

### IMP-26: PoW input and placement are ambiguous
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:673-683; spec/11-transport.md:125
- Fix: As proposed. Depends on the IMP-2 byte definition.
- Needs decision: no.

### IMP-27: RFC 9421 profile and manifest signer are under-specified
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:102, :116, :167-183; spec/11-transport.md:214-219
- Fix: As proposed. The signer conflict is confirmed: 10:102 says "by the Relay operator's key", while 10:116 says "signed by the key declared in the DID document" of `relayDID`. Apply the same profile to the push wake-up (11:214-219).
- Needs decision: no.

### IMP-28: Required test vectors do not exist and several constructions have none planned
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3 (from P2)
- Location: spec/13-encoding.md:84-86 (not :148-150)
- Fix: The missing JWS vector set is already tracked ("Open (agora-pozi.20.16)", 13:86), so it is not new. The new part is that no vectors are planned for the exporter, HKDF, AEAD-layout and CID constructions. Missing vectors do not themselves cause divergence: the ambiguities are counted under IMP-2/5/6/13. Add a §13.4 vector requirement once those are fixed.
- Needs decision: no.

### IMP-29: No list of spec-defined type URIs, DID service types or exporter labels
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3 (from P2)
- Location: spec/07-compliance.md:227; spec/04-access-control.md:127; spec/05-messaging.md:283-301; spec/13-encoding.md:32, :100 (not :164)
- Fix: Mostly resolved by existing rules. 13:32 says "An Agora protocol type is named `urn:agora:type:` followed by the type name", which fixes the URNs for `ComplianceDisclosureNotice` and `DMGroupDescriptor`. 05:261 admits "a type defined in another section", and 06:422 defines the call-type naming. The service-type mismatch is IMP-8. Mixed exporter-label styles are each exact strings and cause no divergence. What remains: write the full URN at 07:227 and 04:145 for clarity, and define the `SystemEvent.event` values (only one example exists, at 09:185). An appendix index is optional.
- Needs decision: no.

### IMP-30: DM-specific gaps: relay hints, consent signal, descriptor bootstrap
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1 (from P2)
- Location: spec/04-access-control.md:151, :153, :159; spec/02-identity.md:37, :302; spec/10-relays.md:612
- Fix: Raised to P1 because DM chain registration has no rule at all. Relays admit only chains registered by a CO billing DID under a RelayServiceAgreement (10:612, Q6, S7), and DMs have no CO (04:125, 04:168). As written, no DM envelope passes relay admission, and implementers will each invent a different workaround. The relay-hint contradiction is confirmed: 04:151/153 rely on "DID document relay hints", while 02:37 and 02:302 forbid naming any relay. `consentModel` and the "explicit approval signal" (04:159) have no schema.
- Needs decision: yes. Who registers a DM chain: (a) the creator's CO, or a personal registration service the user chooses for an individual without a CO (did:key users); (b) relays accept unregistered chains for DMs, which weakens Q1's removed-member protection and the S7 quota binding. Recommend (a), because it keeps Q1 and S7 intact. Relay choice: put the creator's relays in the DMGroupDescriptor; this follows from 04:145 and needs no decision.

### IMP-31: `seq` semantics differ between devices and are unbounded
- Verdict: CONFIRMED-ADJUSTED (location)
- Severity: P3
- Location: spec/05-messaging.md:13, :226; spec/13-encoding.md:19 (not :83); spec/14-jmap.md:111
- Fix: As proposed. `causalRefs` appears only at 14:111.
- Needs decision: no.

### IMP-32: Minor contradictions that will cause small divergences
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/06-calls.md:28-29 vs spec/05-messaging.md:228; spec/02-identity.md:35 vs spec/10-relays.md:456, :465; spec/11-transport.md:85-88 vs spec/13-encoding.md:121; spec/02-identity.md:211-215, :231
- Fix: As proposed. The Pkarr example at 10:456 already uses `cid=bafyrei...`, so only the table text at 10:465 needs to change.
- Needs decision: no.

## Counts

- Verdicts: CONFIRMED 20, CONFIRMED-ADJUSTED 12, REJECTED 0.
- Severity after adjustment: P1 12 (IMP-1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 30), P2 16, P3 4 (IMP-28, 29, 31, 32).
- Severity changes: IMP-9 P1→P2, IMP-10 P1→P2, IMP-28 P2→P3, IMP-29 P2→P3, IMP-30 P2→P1.
- Needs decision: yes for IMP-1, IMP-2 (narrowed to b/c by D1), IMP-5, IMP-11, IMP-30.
- No finding attacks a recorded decision. None was rejected: each "undefined" claim was grep-checked, and no definition exists in spec/ or ARCHITECTURE.md. Partial resolutions in existing text are noted under IMP-2, 7, 9, 10, 25 and 29.
