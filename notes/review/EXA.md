# EXA review: examples in spec/01..14 and 99

All 118 fenced blocks were extracted. Every block tagged `json`, or starting with `{` or `[`, was parsed with Python `json`. Results:
- All complete JSON documents parse.
- The 23 blocks that fail to parse are deliberate member fragments (`"roles": [...]`, `"sfus": [...]` and so on), CBOR-diagnostic envelopes (05:232, 13:39), pseudo-structures (11:58, 11:184, 11:196, 11:214) or alternation placeholders (`"high" | "normal"`, 11:236). None of them is meant to be a whole JSON document, so I report no parse defects. The findings below are about content.

Note: §13.1 says an Agora type's `body` "is the JSON object shown in that section" (13:32). The examples are therefore normative body definitions, which raises the cost of the mismatches below.

### EXA-1: Routing envelope has no defined byte encoding, yet `accessSig`, `id` and PoW all hash or sign it
- Severity: P1
- Location: spec/05-messaging.md:181-196, 05:206; spec/10-relays.md:673-681; spec/11-transport.md:54
- Evidence: example is a JSON object with `"@type": "RoutingEnvelope"` and `"id": "urn:agora:msg:bafyrei..."`; "`id` is the CID of the canonical outer envelope"; "`accessSig` is an Ed25519 signature ... over the routing envelope with `accessSig` omitted"; PoW: "`SHA256(envelopeBytes || nonce)` ... then includes the nonce in the outer `RoutingEnvelope`"; frames: "Relays MUST accept both JSON and CBOR".
- Problem: The routing envelope is not a §13.1 typed envelope. No section defines its serialization, so the bytes that `accessSig` covers are undefined, and every relay must check that signature. "Canonical" contradicts §13.1.1 ("no canonical CBOR, JCS ... form is computed"). `id` is the CID of an object that contains `id`. The PoW hash covers envelope bytes that include the `powProof` nonce. Two independent implementations will not interoperate on relay admission.
- Suggested fix: Define the routing envelope as a CBOR map with fixed text keys. State that `accessSig` covers the encoded map with `accessSig` and `powProof` removed, sent as exact bytes, with the same byte-for-byte rule as §13.1.1. Define `id` as the CID of the encoded envelope as stored. Remove `id` from the wire example, or state that it is computed and never sent. Define the PoW input as the encoded envelope without `powProof`. Drop `@type` from the example (the routing envelope has no `type` URN), and drop "canonical".
- Needs decision: no

### EXA-2: Inside-MLS bodies carry sender fields that §5.2.2 forbids
- Severity: P2
- Location: spec/06-calls.md:28 (`ParticipantState`); spec/07-compliance.md:222 (`ComplianceDisclosureNotice`); spec/09-interop.md:190 (`SystemEvent`)
- Evidence: 05:228 "Objects carried inside MLS have no object-level signature and no sender field." 14:105 "It MUST NOT take sender identity from the `body`." Examples: `"sender": "did:key:z6Mk..."`, `"issuedBy": "did:key:z6MkRegulatedMember..."`, `"addedBy": "did:key:z6MkAdmin..."`. Each section also says the MLS sender authenticates the message (06:44, 07:227, 09:181).
- Problem: Because §13.1 makes the shown body normative, these bodies define a sender field that can differ from the MLS sender. That invites the impersonation that §14.7 warns about.
- Suggested fix: Delete `sender` from `ParticipantState`, `issuedBy` from `ComplianceDisclosureNotice` and `addedBy` from `SystemEvent`. Keep `gatewayDID` and `targetDID`, because they name other parties.
- Needs decision: no

### EXA-3: `did:key` used where a DID-document service entry is required
- Severity: P2
- Location: spec/05-messaging.md:432; spec/09-interop.md:85-93, 102; spec/06-calls.md:251, 358, 383 (with 06:372)
- Evidence: 05:432 service entry `"id": "did:key:z6Mk...#text-formats"`. 09:88 `"id": "did:key:z6MkGateway...#gateway"`. 06:372 "The recorder ... MUST have a `KeyPackageEndpoint` service entry in its DID document", but the examples use `"recorderDID": "did:key:z6MkRecorder..."` and `"grantedTo": "did:key:z6MkRecorder..."`. 02:14 says the `did:key` document is "derived from the key" and has no `service` entries.
- Problem: A `did:key` document cannot carry services. These examples cannot exist as shown, and the recorder examples contradict their own MUST. §5.2.7.4 also tells senders to "check the DID document" (05:463), which is impossible for `did:key` users.
- Suggested fix: Change the gateway and recorder examples to `did:webvh:QmSCID...:example.com:agora:gateway` and `did:webvh:QmSCID...:example.com:agora:recorder`, matching the compliance logger at 07:69. In §5.2.7.4, use a `did:webvh` id and add "A `did:key` user cannot publish this entry; it uses only the in-group declaration."
- Needs decision: no

### EXA-4: User DID method lists and examples contradict §2.1
- Severity: P2
- Location: spec/09-interop.md:24; spec/04-access-control.md:153; spec/99-appendices.md:11
- Evidence: 09:24 "Agora users are identified by DID (`did:key` or `did:web`)". 04:153 "A user with a `did:web:agency.example` identity". 99:11 "Identity | W3C DID Core, `did:key`, `did:web`". Against these: 02:10 (three methods: `did:webvh`, `did:plc`, `did:key`) and 14:225 "`did:web` is not accepted as a user identity".
- Problem: These statements describe a method set that was replaced, which contradicts the binding DID-method decision.
- Suggested fix: 09:24 should read "(`did:webvh`, `did:plc` or `did:key`, §2.1)". 04:153 should use `did:webvh:QmSCID...:example.com:users:k7f3qd2m` (this also fixes the domain, see EXA-14). 99:11 should read "W3C DID Core; `did:webvh`, `did:plc`, `did:key` for users; `did:web` for relays".
- Needs decision: no

### EXA-5: DM reachability relies on "relay hints" in the recipient's DID document, which §2 forbids
- Severity: P2
- Location: spec/04-access-control.md:151, 153; with spec/02-identity.md:37, 302 and spec/10-relays.md:448
- Evidence: 04:151 "the Relays known to be serving the recipient's DID (discoverable from the recipient's DID document relay hints)". 04:153 "the recipient's relay hints ... the recipient's advertised relay hints". 02:302 "The DID document MUST NOT name an infrastructure operator (relay or other IO)". 02:37 the Pkarr record "MUST NOT name a relay".
- Problem: The worked example depends on a field that identity documents are forbidden to carry. Relays route by `channelToken`, and a DM's token comes from the group, so no per-recipient relay hint is needed.
- Suggested fix: Rewrite 04:151-153 so that the Welcome goes to the recipient's `KeyPackageEndpoint` (as 04:147 already says), and DM traffic then flows on any relay that serves the group's access chain under the CO's `RelayServiceAgreement`. Drop "relay hints" from the DID-document wording.
- Needs decision: no

### EXA-6: SpaceState example omits fields its own text makes mandatory
- Severity: P2
- Location: spec/03-spaces.md:70-97, 124; with 03:137, spec/05-messaging.md:127-129
- Evidence: 03:137 "A channel entry that has an MLS group MUST carry its `mlsGroupID`". The `announcements` (broadcast, which has a publisher MLS group per 03:26), `community`, `engineering/backend` and `engineering/fips` entries have no `mlsGroupID`. The broadcast entry has no `broadcasterRoles`, and 05:127 says only holders of a role in `broadcasterRoles` may post. `"vtcCompliance": {}` is an empty `VTCComplianceConfig`.
- Problem: An implementer copying the central example produces a state that clients must reject under §4.3 Welcome checks (no `mlsGroupID` to match) and a broadcast channel nobody can post to. The empty `vtcCompliance` object has no defined meaning.
- Suggested fix: Add `"mlsGroupID": "base64url..."` to every channel entry that has a group. Add `"broadcasterRoles": ["broadcaster"]` to `announcements`, plus a matching role in `roles`. Either drop `vtcCompliance` or show a complete block.
- Needs decision: no

### EXA-7: Relay manifest key ids are invalid `did:key` DID URLs, and the manifest signer is ambiguous
- Severity: P2
- Location: spec/10-relays.md:72, 102, 116, 359
- Evidence: 10:72 `"id": "did:key:z6MkRelay...#key-1"`. 10:102 "signed per §13.1.1 by the Relay operator's key". 10:116 "the manifest ... is signed by the key declared in the DID document" (the `relayDID` document). 10:359 "the Relay-signed manifest". 13:62 shows the correct `did:key` form `did:key:z6Mk...#z6Mk...`.
- Problem: A `did:key` document has exactly one verification method, whose fragment is the multibase key. `#key-1` never resolves, so verification fails at §13.1.1 step 3. §13.1.1 step 4 requires the section to name the signer DID, and "operator's key" (`operatorDID`) conflicts with `relayDID`.
- Suggested fix: Change 10:72 to `did:key:z6MkRelay...#z6MkRelay...`, or use the `did:web` relay form with `#key-1`. Change 10:102 to "signed per §13.1.1 by `relayDID`".
- Needs decision: no

### EXA-8: KeyPackageEndpoint service `type` and path are never fixed, and the one example disagrees with the registry
- Severity: P2
- Location: spec/07-compliance.md:188-192; spec/02-identity.md:19, 302; spec/05-messaging.md:63; spec/13-encoding.md:117; spec/10-relays.md:457
- Evidence: 07:190 `"type": "AgoraKeyPackageEndpoint"`, 07:191 `".../v1/agora/keypackages"`. Everywhere else the prose says "`KeyPackageEndpoint` service entry". The version registry says "KeyPackage Store API | v1 | URL path prefix `/v1/agora/kp/`", and the Pkarr example uses `/v1/agora/kp/z6Mk...`.
- Problem: Committers find KeyPackages by service type. With two spellings and two paths, a client and an identity host can each be "conformant" and fail to interoperate.
- Suggested fix: In §2.1, state the service `type` value once (for example `AgoraKeyPackageEndpoint`) and refer to it from §5.2.1.1 and §7.8.2. Change 07:191 to `https://archive.example.com/v1/agora/kp/`.
- Needs decision: no

### EXA-9: JmapSet example edits a chat Message by patch, bypassing the §5.2.3 edit form
- Severity: P2
- Location: spec/14-jmap.md:92-99; spec/05-messaging.md:278
- Evidence: 14:94-96 `"dataType": "urn:ietf:params:jmap:chat#Message"`, `"update": { "01JABCDEF...": { "body": "corrected text" } }`. 05:278 "Edit: the target's `senderMsgId` and the fields of the federation `edit` object (`body`, `bodyType`, `editedAt` ...). A body containing `editedAt` is an edit."
- Problem: The example sets up a second wire form for message edits with no `editedAt` and no `MessageRevision`. Receivers applying §5.2.3 and receivers applying §14.3.2 will show different edit histories.
- Suggested fix: Use a non-chat type in the JmapSet example (for example `urn:ietf:params:jmap:tasks#Task`). Add to §14.3.2: "chat `Message` and `Reaction` are written only in object form (§5.2.3); a JmapSet naming them is ignored."
- Needs decision: no

### EXA-10: Relay sync `Envelope` object does not match the routing envelope
- Severity: P2
- Location: spec/11-transport.md:331-339; spec/05-messaging.md:181-196
- Evidence: `id ... ULID (time-sortable, server-assigned)`, `encryptedPayload ... MLS ciphertext`, `seqNo ... Sequence number within the epoch`, `expiresAt`. The routing envelope has `id` = CID, `sealedEnvelope` or `broadcastPayload`, `accessSig`, `expiryHint`, and its `seq` is inside the ciphertext (05:13).
- Problem: The relay cannot know `seqNo`. The object omits `accessSig` (needed for writes through the sync API, 11:279) and `broadcastPayload`. The ULID `id` collides with the CID `id` used for ordering in 06:426 and 14:111. A client cannot rebuild the envelope it needs to verify and decrypt.
- Suggested fix: Define `Envelope` as `{id: <envelope CID>, channelToken, epoch, ts, expiryHint, sealedEnvelope | broadcastPayload, accessSig, receivedAt}`, or as `{id, channelToken, receivedAt, envelope: <base64url of the exact encoded routing envelope>}`. Drop `seqNo`.
- Needs decision: no

### EXA-11: Compliance VTC examples contradict their own rules
- Severity: P3
- Location: spec/06-calls.md:257 with 06:306-308; 06:335-336 with 06:343
- Evidence: Compliance grant `"participantDisclosure": "This call is being recorded for regulatory compliance by Example Corp Compliance Archive."`, but 06:306 says the disclosure "MUST include the `loggerLabel` ... and the grant's `retentionDays`". The record has `"mediaFormat": "audio/ogg;codec=opus"` with `"scope": "audio-video"`, but 06:343 says audio-video goes in a WebM container.
- Problem: Both examples break MUST/SHOULD text a few lines below them.
- Suggested fix: Append "and retained for 2555 days." to the disclosure. Use `"mediaFormat": "video/webm;codecs=\"vp9,opus\""` (the RFC 6381 parameter is `codecs`).
- Needs decision: no

### EXA-12: §13.1 example body starts with a server-set `id`, and the caption says "decoded" over hex
- Severity: P3
- Location: spec/13-encoding.md:37-44
- Evidence: "shown with `body` decoded for readability", then `"body": h'7b226964223a...'`. The hex decodes to `{"id":`. 14:89 says "`id` for chat `Message` ... [is] omitted by the sender".
- Problem: The canonical envelope example carries a field senders must omit, and its caption is wrong.
- Suggested fix: Use `h'7b2273656e6465724d73674964223a...'` (`{"senderMsgId":`) and change the caption to "with `body` shown as hex".
- Needs decision: no

### EXA-13: Self-referential and undefined `urn:agora:` identifiers
- Severity: P3
- Location: spec/10-relays.md:593, 617; spec/08-cross-space.md:34-37, 118; spec/07-compliance.md:97, 104; spec/04-access-control.md:133; spec/03-spaces.md:55
- Evidence: `"id": "urn:agora:rsa:bafyrei..."`, `"id": "urn:agora:csa:bafyrei..."`, `"envelopeID": "urn:agora:msg:bafyrei..."` next to `"outerEnvelopeCID": "bafyrei..."`, `"dmGroupID": "urn:agora:dmgroup:<uuid>"`. §13.1 reserves only `urn:agora:type:`. 08:35 `"agora://bafyrei.../"` (trailing slash) versus 03:55 `"agora://bafyrei..."`.
- Problem: No section defines the `rsa`, `csa`, `msg` or `dmgroup` sub-namespaces. Where the suffix is the CID of the containing object, it cannot be computed. In the genesis state, `id` would have to contain the CID of its own document. `ComplianceRecord` carries the same envelope id in two forms. The DMGroupDescriptor text identifies the group by `DMGroupCID` (04:125), which changes on every update (04:145), while the example uses a stable `dmGroupID`.
- Suggested fix: Remove `id` from `RelayServiceAgreement` and `ChannelShareAgreement`, and reference them by CID (`agreement: <CID>`, as `agreementCID` already does in §8). Drop `envelopeID` (keep `outerEnvelopeCID`). Define `dmGroupID` once in §4.6 as the stable identifier, and list `urn:agora:dmgroup:` in §13.1 as reserved. State that `id` is absent from the genesis SpaceState. Use one `agora://` form without the trailing slash.
- Needs decision: no

### EXA-14: Example domains that are not example.com or example.net, including one real company domain
- Severity: P3
- Location: spec/10-relays.md:327, 354, 369, 386 (`raw.githubusercontent.com`); 10:221 (`/ipns/agora.protocol/relays/v1`); spec/06-calls.md:197 (`turn-creds.acme.example`), 06:510 (`acme.example`); spec/04-access-control.md:153 (`agency.example`)
- Evidence: `"id": "https://raw.githubusercontent.com/example/agora-relays/main/relays.json"`; "resolves `/ipns/agora.protocol/relays/v1` for a community-maintained signed bootstrap list".
- Problem: Example identifiers should use RFC 2606 example.com or example.net. `agora.protocol` reads as a normative name that nobody owns: IPNS names are keys or DNSLink domains, and `.protocol` is not a TLD.
- Suggested fix: Use `https://directory.example.com/relays.json` (and similar). Use `turn-creds.example.com` and `did:webvh:QmSCID...:example.com:agora:admit-bot`. Either replace the IPNS bootstrap with "an IPNS name configured by the operator", or mark it as an example (`/ipns/bootstrap.example.com`).
- Needs decision: no

### EXA-15: Employer-namespace admin DID derived from a role name
- Severity: P3
- Location: spec/02-identity.md:410
- Evidence: `"adminDID": "did:webvh:QmSCID...:example.com:users:it-admin"`. 02:273 says "`localIdentifier` ... MUST NOT be derived from a person's name, email address, UPN, or any other attribute that can change."
- Problem: The admin is a person in the `users:` namespace, and "it-admin" is a role that will change hands, which breaks the stable-DID decision. The individual DIDs elsewhere (`example.com:alice`, `bob` and others) are outside the `users:` namespace and are allowed.
- Suggested fix: Use `did:webvh:QmSCID...:example.com:users:r2v8n5xw`.
- Needs decision: no

### EXA-16: Pkarr record examples disagree with each other and with the no-relay rule
- Severity: P3
- Location: spec/10-relays.md:456, 465, 476; spec/02-identity.md:35, 37
- Evidence: Example `_profile._agora. TXT "cid=bafyrei..."` and 02:35 `cid=<profile CID>`, but the table at 10:465 says "`ipfs://` URI of the user's current profile IPLD node". 10:476 says "use relay endpoints, profile CID, or KeyPackage endpoint", but 02:37 says the record "MUST NOT name a relay".
- Problem: The value format is ambiguous, and the lookup step tells clients to read a field that must not exist.
- Suggested fix: Change the 10:465 value to "bare CID (no scheme)". Change 10:476 to "use the profile CID or KeyPackage endpoint".
- Needs decision: no

### EXA-17: RelayAd example violates "exactly these members" and omits a manifest client endpoint
- Severity: P3
- Location: spec/10-relays.md:634-641, 663; with 10:62-69
- Evidence: 10:663 "A `RelayAd` carries exactly these members", and the list does not include `@type`, but the example has `"@type": "RelayAd"`. "`endpoints` ... MUST list every client-facing endpoint the manifest lists". The same relay's manifest (`did:key:z6MkRelay...`, `relay.example.com`) lists `jmapSync`, a client API (§11.8.1), but the RelayAd omits it.
- Problem: The example fails its own strict rule twice.
- Suggested fix: Drop `@type` from the example (`type` is in the envelope), and add `"jmapSync": "https://relay.example.com/v1/agora/jmap"`.
- Needs decision: no

### EXA-18: Agora types sent as MLS application messages without a listed type URI
- Severity: P3
- Location: spec/07-compliance.md:227; spec/04-access-control.md:145; spec/05-messaging.md:287-299
- Evidence: 07:227 "an MLS application message of type `ComplianceDisclosureNotice`". 04:145 the committer "sends the updated descriptor to the group as an MLS application message". Neither type appears in the §5.2.3 Agora types table, and 13:101 says unknown types are ignored.
- Problem: The disclosure notice is safety-relevant. A client built from the §5.2.3 table would silently ignore it.
- Suggested fix: Add `urn:agora:type:ComplianceDisclosureNotice` and `urn:agora:type:DMGroupDescriptor` to the §5.2.3 table, and use the full URN at 07:227.
- Needs decision: no

### EXA-19: Smaller example and definition mismatches
- Severity: P3
- Location: as listed
- Evidence and fix:
  - 02:107 `UserProfile` has `"did": "did:key:z6Mk..."`, but it is the profile linked from alice's `did:webvh` document (02:95). Use `did:webvh:QmSCID...:example.com:alice`.
  - 07:267 "`DMComplianceAuditEntry` ... is signed per §13.1.1" names no signer (§13.1.1 step 4 needs one), and the body has both `loggerDID` and `admittedBy`. State "signed by `admittedBy`" (or by the logger) explicitly.
  - 14:158 says `after` is "an added member" of the envelope, but §13.1 envelope keys do not include it, the JmapSet body example (14:93) lacks it, and 05:297 says the JmapSet "carries the `after` head". Put `after` in the JmapSet body and show it.
  - 14:132 sequencer `endpoint` `https://seq.example.com/agora/v1` breaks the 01:15 `/v1/agora/...` prefix convention and is missing from the 13.2 registry. Use `/v1/agora/seq` and add a registry row.
  - 14:111 cites "`causalRefs`" from §5.1.1. No such field exists anywhere in the spec; delete it.
  - 10:55 and 10:213: a public `relay.example.com` manifest and SRV/TXT record use `did:key:z6MkRelay...`, although 10:110 says public relays SHOULD use `did:web`. Use `did:web:relay.example.com` there. Separately, 13:76 resolves `kid` "per §2.1", but §2.1 does not cover `did:web`, which relay signatures need. Add `did:web` resolution for IO principals.
  - 09:121 and 09:147 define the MXID as `@agora_<did-fragment>`, which only works for `did:key`. `did:webvh` and `did:plc` contain `:`, and `:` is not allowed in an MXID localpart. Define the localpart as a hash or base32 of the full DID.
- Needs decision: no

## Areas with no example defects found
- §1 has no examples.
- §2: DID documents, recovery and provisioning examples are consistent with the rules except EXA-15 and EXA-19.
- §5.3 presence and typing, §5.2.8 reactions and §5.2.6 pin bodies match JMAP Chat naming and carry no sender.
- §6.14 call-coordination bodies: `callID` values are valid 22-character base64url (128-bit) strings, and the bodies have no sender field.
- §8 ChannelShareAgreement signer fields match the multi-signer rule.
- §11 JMAP Session and request examples conform to RFC 8620.
- §12 has no examples.
- §99 has no examples (one DID-method row, EXA-4).
- No Agora body carries a body-level signature field: every signature is the envelope `sig`.
- No `@context` appears on an Agora body; it appears only on DID documents, which is correct.
- Type URNs: every `urn:agora:type:*` and JMAP `capability#Type` value is in the right namespace. `urn:ietf:params:jmap:tasks#Task` is correct, because `Task` is defined by upstream JMAP Tasks, not chat-tasks.

Coverage: read in full spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md. Machine-parsed all 118 fenced blocks. Consulted `bd memories` decisions and notes/jmap-family-payloads.md (only for the Task capability URN).
