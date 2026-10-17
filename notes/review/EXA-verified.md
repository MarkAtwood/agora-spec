# EXA verified

Verifier checked each finding against the cited text, grep across spec/ and ARCHITECTURE.md, and `bd memories agora`. No finding attacks a recorded decision. Several fixes were corrected.

### EXA-1: Routing envelope has no defined byte encoding, yet `accessSig`, `id` and PoW all hash or sign it
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/05-messaging.md:181-196, 05:206; spec/10-relays.md:673-681; spec/11-transport.md:54
- Fix: The defect is real. No section defines the routing envelope encoding. §13.1 covers only typed payload envelopes, and the routing envelope is not one. 05:196 says "CID of the canonical outer envelope", which contradicts 13:9 ("Agora computes no canonical form"). 05:206 has accessSig cover "the routing envelope with `accessSig` omitted". 10:673 hashes `envelopeBytes` and then puts the nonce inside the same envelope. 11:54 has "Relays MUST accept both JSON and CBOR", so the same envelope can arrive as two different byte strings. The reviewer's fix is wrong in one place. "The encoded map with `accessSig` and `powProof` removed" still needs a re-encoding step, and §13.1 says CBOR map order and integer widths "carry no meaning". Use the D1 exact-bytes rule instead. Define the routing envelope as a CBOR map `{ "signed": bstr, "accessSig": bstr, "powProof"?: map, "urgency"?: text, "accessKeyAnnouncement"?: ... }`. `signed` holds the exact bytes of a CBOR map with keys `channelToken`, `epoch`, `ts`, `expiryHint`, and `sealedEnvelope` or `broadcastPayload`. `accessSig` is computed over the `signed` bytes. `id` is the CID of the `signed` bytes, is never sent, and the receiver computes it. The PoW input is `SHA256(signed || nonce)`. Drop `@type`, `id` and "canonical" from the 05:181-196 example and its prose. State in 11:54 that the JSON debugging encoding never applies to routing envelopes on the relay path.
- Needs decision: no

### EXA-2: Inside-MLS bodies carry sender fields that §5.2.2 forbids
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/06-calls.md:28; spec/07-compliance.md:224; spec/09-interop.md:190
- Fix: As the reviewer proposed. Delete `sender` (ParticipantState), `issuedBy` (ComplianceDisclosureNotice) and `addedBy` (SystemEvent). This follows 05:228: "Objects carried inside MLS have no object-level signature and no sender field".
- Needs decision: no

### EXA-3: `did:key` used where a DID-document service entry is required
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:432; spec/09-interop.md:88, 102; spec/06-calls.md:251, 358, 383 (vs 06:372)
- Fix: As the reviewer proposed. The 02:14 table says `did:key` has "No: document derived from the key", and a `did:key` profile or KP pointer goes through Pkarr. A `did:key` gateway or recorder therefore cannot carry the `KeyPackageEndpoint` that 06:372 requires. Use `did:webvh:...` for the gateway and recorder. In §5.2.7.4, note that `did:key` users rely only on the in-group declaration.
- Needs decision: no

### EXA-4: User DID method lists and examples contradict §2.1
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/09-interop.md:24; spec/04-access-control.md:153; spec/99-appendices.md:11
- Fix: As the reviewer proposed. The agora-did-methods decision and 14:225 ("`did:web` is not accepted as a user identity") settle this.
- Needs decision: no

### EXA-5: DM reachability relies on "relay hints" in the recipient's DID document, which §2 forbids
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:151, 153
- Fix: The contradiction with 02:37 and 02:302 is real. The reviewer's replacement text says DM traffic flows "under the CO's `RelayServiceAgreement`", but a DM group has no CO. 04:116 says "DM groups are not owned by any Space". Relays admit only envelopes on a chain registered by a CO registration service (05:203, 10:612), and every announcement needs `billingSig` (05:204). Nothing in spec/ or ARCHITECTURE says who registers and countersigns a DM group's access chain. Delete the relay-hint text either way, and also fix `did:web:agency.example` (EXA-4).
- Needs decision: yes. Who registers and countersigns DM access chains? Options:
  - (a) The CO registration service of a Space the DM creator belongs to.
  - (b) The party that runs the creator's identity (the KeyPackageEndpoint host, per Q3), acting as a CO-equivalent with its own billing DID.
  - (c) Each user's chosen "home" registration service, declared nowhere public.
  - Recommendation: (b). It reuses the Q3 host, which every user already has, and leaks nothing new. The open question is what plays the CO role for `did:key` users.

### EXA-6: SpaceState example omits fields its own text makes mandatory
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/03-spaces.md:63-97, 124 (rule at 03:137; spec/05-messaging.md:127)
- Fix: As the reviewer proposed. Also add `mlsGroupID` to `voice/lounge` (03:93-96). Voice channels have an MLS group (06:44, "encrypted to the channel group").
- Needs decision: no

### EXA-7: Relay manifest key ids are invalid `did:key` DID URLs, and the manifest signer is ambiguous
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/10-relays.md:72, 102
- Fix: As the reviewer proposed. The preferred form is to switch the example to `did:web:relay.example.com` with `#key-1`, because 10:110 says public relays SHOULD use `did:web`. That also resolves EXA-19's 10:55 point. Change 10:102 to "signed per §13.1.1 by `relayDID`".
- Needs decision: no

### EXA-8: KeyPackageEndpoint service `type` and path are never fixed, and the one example disagrees with the registry
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/07-compliance.md:190-191; spec/02-identity.md:19; spec/13-encoding.md:117
- Fix: As the reviewer proposed. Define the service `type` string once in §2.1 and align 07:191 with `/v1/agora/kp/`.
- Needs decision: no

### EXA-9: JmapSet example edits a chat Message by patch, bypassing the §5.2.3 edit form
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/14-jmap.md:92-99; spec/05-messaging.md:278
- Fix: As the reviewer proposed. Under D7, JMAP Chat Message is the chat format, and 05:278 defines the only edit form.
- Needs decision: no

### EXA-10: Relay sync `Envelope` object does not match the routing envelope
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:331-339
- Fix: Use the reviewer's second form, `{id, channelToken, receivedAt, envelope: <base64url exact bytes>}`. It composes with the EXA-1 fix. Drop `seqNo`, `encryptedPayload` and the ULID `id`.
- Needs decision: no

### EXA-11: Compliance VTC examples contradict their own rules
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/06-calls.md:257 (vs 06:306); 06:335-336 (vs 06:343)
- Fix: As the reviewer proposed.
- Needs decision: no

### EXA-12: §13.1 example body starts with a server-set `id`, and the caption says "decoded" over hex
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/13-encoding.md:39-44
- Fix: As the reviewer proposed. `7b226964223a` is `{"id":`, which 14:89 says senders omit.
- Needs decision: no

### EXA-13: Self-referential and undefined `urn:agora:` identifiers
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/10-relays.md:593, 617; spec/08-cross-space.md:34-37, 118; spec/07-compliance.md:97, 217, 258; spec/04-access-control.md:133; spec/03-spaces.md:55
- Fix: The finding is real. The agora-urn decision covers only registration, not undefined sub-namespaces or self-reference. Keep the reviewer's fixes for `rsa`, `csa`, `msg` and the `agora://` form. For SpaceState, 03:49 anchors identity to the genesis CID, so state that `id` is absent from genesis and equals `agora://<genesis CID>` afterward. Replace the reviewer's DM fix with a simpler one: drop `dmGroupID` and identify DM groups by the descriptor's `mlsGroupID`. It is already stable and only ever appears inside the group or in compliance records. Then change 04:117 from "identified by a `DMGroupCID`" to that. No new `urn:agora:dmgroup:` namespace is needed.
- Needs decision: no

### EXA-14: Example domains that are not example.com or example.net, including one real company domain
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/10-relays.md:221 only
- Fix: Part of this finding is wrong. `.example` is an RFC 2606 reserved TLD, so `acme.example`, `turn-creds.acme.example` and `agency.example` are valid. `raw.githubusercontent.com` is deliberate: 10:317 says "A file committed to a public GitHub repository and served via `raw.githubusercontent.com` ... is a valid directory", and the path uses the `example` org. Only `/ipns/agora.protocol/relays/v1` remains a defect: it is an unowned name that reads as normative. Replace it with "an IPNS name configured by the operator (e.g. `/ipns/bootstrap.example.com`)".
- Needs decision: no

### EXA-15: Employer-namespace admin DID derived from a role name
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:410
- Fix: As the reviewer proposed. This follows the agora-stable-did decision and 02:273.
- Needs decision: no

### EXA-16: Pkarr record examples disagree with each other and with the no-relay rule
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:465, 476
- Fix: As the reviewer proposed.
- Needs decision: no

### EXA-17: RelayAd example violates "exactly these members" and omits a manifest client endpoint
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:634-641, 663
- Fix: As the reviewer proposed. 13:32 tolerates `@type` in general, but 10:663 "exactly these members" overrides that here.
- Needs decision: no

### EXA-18: Agora types sent as MLS application messages without a listed type URI
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2 (raised from P3)
- Location: spec/05-messaging.md:287-299; spec/07-compliance.md:227; spec/04-access-control.md:145
- Fix: As the reviewer proposed. Severity is raised because 07:227 says clients "MUST render it as a visible system notification". A client built from the table ignores the type as unknown (13.2), so the regulatory disclosure fails between conformant implementations.
- Needs decision: no

### EXA-19: Smaller example and definition mismatches
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/02-identity.md:107; spec/07-compliance.md:267; spec/14-jmap.md:111, 132, 158; spec/10-relays.md:55, 213; spec/13-encoding.md:76; spec/09-interop.md:121, 147
- Fix: All seven sub-points check out. Two corrections:
  - 07:267: name the signer as `loggerDID`, not `admittedBy`. 07:276 and 07:299 make the logger the writer of the compliance audit chain.
  - MXID: `@agora_<did-fragment>` fails even for `did:key`. Matrix localparts must be lowercase (`a-z0-9._=-/+`), and `z6Mk...` contains uppercase letters. Use a lowercase base32 encoding of a hash of the full DID.
  - 10:55 is resolved together with EXA-7.
- Needs decision: no

## Counts
- Total: 19. Confirmed 12, Confirmed-adjusted 7, Rejected 0.
- Severity after adjustment: P1 1 (EXA-1), P2 10 (EXA-2 through EXA-10, EXA-18), P3 8.
- Needs decision: EXA-5 (who registers and countersigns DM access chains).
