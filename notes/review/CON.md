# CON review: cross-part consistency of the normative spec

Lens: places where two parts of ARCHITECTURE.md + spec/01..14, 99 disagree on a
name, field set, signer, sender, ordering, number, MUST/SHOULD, or
cross-reference, plus terms used but never defined. Binding decisions (bd
memories) were not re-litigated; findings report where the text fails to
carry them through consistently.

---

### CON-1: `channelCID` is the exporter context for token, access key and sealing key, but is never defined
- Severity: P1
- Location: spec/05-messaging.md:194, :202, :218; spec/03-spaces.md:60-97, :166; spec/06-calls.md:12; spec/11-transport.md:415; spec/12-security.md:52; spec/04-access-control.md:125
- Evidence: 05:194 `MLS-Exporter("agora channel token", channelCID, 32)`; 05:202 `MLS-Exporter("agora access", channelCID, 32)`; 05:218 `MLS-Exporter("agora sealed envelope", channelCID, Nk)`. §3.2 defines channels by path only: "Space and Channel identifiers are namespaced paths ... `agora://<space-id>/<channel-path>`"; the §3.3 channel entry has `path`, `type`, `mode`, `name`, `mlsGroupID`, no CID. DM groups have a `DMGroupCID` "the IPFS CID of the `DMGroupDescriptor`", which "is updated (new CID) on every membership or logger change" (04:145).
- Problem: No part says what bytes `channelCID` is (CID of which document? the `agora://` path? the channel entry?), so two implementations will derive different tokens, access keys and sealing keys and cannot interoperate. For DM groups the only CID candidate changes on every membership change, and the DM token uses a different label with empty context, so the access/sealing derivation for DMs is unspecified. `channelCID` is also the key of `/broadcast-key/<channelCID>` (03:166), SpeakRequest, RecordingGrant, ComplianceRecord index (07:111), etc.
- Suggested fix: Define once (e.g. in §3.3) a stable per-channel identifier: either add a required `channelID` (random 128-bit, set at channel creation, never changed) to the channel entry, or define `channelCID` as the CID of the channel's creation record. State the exporter context bytes exactly (e.g. the raw CID bytes). For DMs define the equivalent (e.g. `dmGroupID` from the descriptor, which is stable) and say whether DM groups use "agora channel token" or "agora-dm-token".
- Needs decision: yes. Options: (a) random `channelID` in channel entry; (b) CID of an immutable channel-genesis record; (c) use `mlsGroupID` as context. Recommend (a): stable, cheap, never exposed to IOs; (c) is attractive but `mlsGroupID` is S1-protected and a breakout/recreate changes it.

### CON-2: `accessSig` and `billingSig` are defined over "the envelope with the signature omitted", contradicting §13.1's no-canonical-form rule; the routing envelope field set is scattered and incomplete
- Severity: P1
- Location: spec/05-messaging.md:181-192, :203-206; spec/13-encoding.md:9, :27, :49; spec/10-relays.md:673-681; spec/11-transport.md:54, :233-237; spec/05-messaging.md:138
- Evidence: 05:206 "`accessSig` is an Ed25519 signature ... over the routing envelope with `accessSig` omitted"; 05:204 `billingSig` "signed per §13.1.1 over the announcement with `billingSig` omitted". §13.1: "Agora computes no canonical form of any payload"; §13.1.1: "A signature is never embedded in the `body` it signs" and it signs "the exact `body` bytes". §11.4: "Relays MUST accept both JSON and CBOR". Members of `RoutingEnvelope` defined in four places: 05:181 (`id`, `channelToken`, `epoch`, `ts`, `expiryHint`, `sealedEnvelope`, `accessSig`), 05:138 (`broadcastPayload`), 10:676 (`powProof`), 11:236 (`pushUrgency`), and 05:203 (`accessKeyAnnouncement`, whose own field names are never given).
- Problem: "Omit a field and sign the rest" requires a canonical serialization, which §13 forbids and which differs between the JSON and CBOR encodings relays must accept; every relay must verify every envelope, so this blocks implementation. §13.1 lists "the `accessKeyAnnouncement` countersignature" as a §13.1.1-signed object, but the announcement is not a typed envelope and its member names (public key, previous-key signature, `billingSig`) are nowhere specified. Whether `powProof`/`pushUrgency` are covered by `accessSig`, and whether PoW (`SHA256(envelopeBytes || nonce)`) includes `powProof`, is undefined. 05:196 also makes `id` "the CID of the canonical outer envelope" while `id` is inside that envelope.
- Suggested fix: Give one normative `RoutingEnvelope` definition (CBOR map, all members incl. `accessKeyAnnouncement`, `broadcastPayload`, `powProof`, `pushUrgency`) and define `accessSig` over an explicit byte string (e.g. a fixed-order concatenation or a detached CBOR array of the signed members as transmitted). Make `accessKeyAnnouncement` a typed envelope (`urn:agora:type:AccessKeyAnnouncement`) whose `body` is signed by the previous access key and whose `sig` carries the `billingSig` entry per §13.1.1. Define `id` as the hash of the bytes excluding `id`, or drop it in favour of a relay-computed CID.
- Needs decision: no

### CON-3: Every access-key announcement needs a CO `billingSig` authorized "under Space state", which DM groups cannot obtain
- Severity: P1
- Location: spec/05-messaging.md:203-204; spec/04-access-control.md:123-155; spec/10-relays.md:612; ARCHITECTURE.md:194-200
- Evidence: 05:204 "Every `accessKeyAnnouncement` MUST also carry `billingSig` ... The service countersigns only an announcement requested by a DID it authenticates as a current member of the channel under Space state ... Relays MUST reject an announcement without a valid `billingSig`". 04:125 "DM groups are not owned by any Space and do not appear in any Space state document"; DMs are "routed like any channel".
- Problem: A DM group, especially between individuals with no CO, or members of two different COs, has no registration service, no `RelayServiceAgreement`, and no Space state to authorize the countersignature, yet relays MUST reject its announcements without one. As written, DMs cannot be carried by any relay.
- Suggested fix: Specify which CO registers and countersigns a DM group (e.g. the creator's CO, or a personal "CO" for individuals that holds its own billing DID), what "current member" means for a DM (MLS membership attested how), and how an individual without an org obtains an agreement.
- Needs decision: yes. Options: (a) DM creator's CO (or the individual acting as own CO with own billing DID) registers and countersigns; (b) DMs exempt from countersignature (accept the removed-member lock-out risk for DMs); (c) each member's CO registers the chain separately on its own relays. Recommend (a), with an individual-as-CO profile.

### CON-4: Shared channels need two COs' `billingSig` on one announcement; format allows one
- Severity: P2
- Location: spec/08-cross-space.md:98; spec/05-messaging.md:204
- Evidence: 08:98 "Each CO engages Relays for the shared channel through its own `RelayServiceAgreement` ... by registering the shared group's access-key chain under it". 05:204 "Relays MUST reject an announcement without a valid `billingSig` from that agreement's billing DID"; "at most one announcement per chain and `epoch`".
- Problem: An announcement carried to relays of both COs must verify under two different billing DIDs, but `billingSig` is a single signature from "the CO's registration service". The guest CO's service would also have to authenticate the committer "as a current member of the channel under Space state" for a channel that is not in its Space state (only an alias, §8.5).
- Suggested fix: Allow `billingSig` to carry multiple §13.1.1 entries (one per registered agreement), and state that the guest CO authorizes on the strength of the `ChannelShareAgreement` plus its own member list.
- Needs decision: no

### CON-5: Broadcast key rotation requires a second countersigned announcement for the same epoch, which §5.2.2 forbids
- Severity: P2
- Location: spec/05-messaging.md:136; spec/05-messaging.md:204
- Evidence: 05:136 "On a key rotation without a Commit ... an `accessKeyAnnouncement` with the unchanged `epoch` and access public key and the new `channelToken` ... countersigned with `billingSig`". 05:204 "The service countersigns ... at most one announcement per chain and `epoch`."
- Problem: The broadcast rotation path cannot obtain its countersignature, so the relay cannot follow the token change.
- Suggested fix: Make the uniqueness rule "at most one announcement per chain and (`epoch`, `keyEpoch`)", or per chain and `channelToken`, and add `keyEpoch` to the announcement.
- Needs decision: no

### CON-6: §10.5 calls RelayServiceAgreements optional, but relays MUST verify access proofs that only exist under an agreement
- Severity: P2
- Location: spec/10-relays.md:584; spec/10-relays.md:527, :612; ARCHITECTURE.md:116-119; spec/11-transport.md:48; spec/12-security.md:62
- Evidence: 10:584 "Both mechanisms are **optional extensions** to the core protocol. A Relay that serves only private, trusted traffic requires neither." 10:527 a conformant Relay MUST "Verify the epoch access proof on every envelope". 10:612 the first-epoch key is registered by `AccessChainRegistration` under the agreement. ARCH S7: the agreement is "The only binding between a CO and an IO". Also 11:48 "Relays MUST use per-`channelToken` rate limits and PoW requirements as the primary spam control" vs 12:62 "a Relay MAY require a proof-of-work challenge".
- Problem: A relay without an agreement has no registered chains and must drop every envelope, so the agreement is not optional; and PoW is MUST in §11.3 but MAY in §10.5.2/§11.6/§12.5.
- Suggested fix: Say the `RelayServiceAgreement` and chain registration are mandatory for any relay that carries envelopes; keep only PoW optional, and change 11:48 to "per-`channelToken` rate limits (and PoW where the Relay requires it)".
- Needs decision: no

### CON-7: Welcomes listed as live-stream traffic, contradicting "never on a gossip topic / relay"
- Severity: P2
- Location: spec/11-transport.md:10, :405; spec/05-messaging.md:51; spec/04-access-control.md:147; spec/10-relays.md:264
- Evidence: 11:10 live stream carries "MLS handshake messages (Commits, Proposals, Welcomes)"; 11:405 "MLS handshake (Commit / Proposal / Welcome) ... Live Stream ✓". 05:51 "`Welcome`: delivered by POST to the new member's `KeyPackageEndpoint` ... never on a gossip topic". 04:147 "A Welcome is not sent on any gossipsub topic."
- Problem: Direct contradiction on where Welcomes travel; implementers following §11 would push Welcomes through relays.
- Suggested fix: Remove Welcome from 11:10 and the 11:405 row; add a note that Welcomes go to the `KeyPackageEndpoint` (§4.6).
- Needs decision: no

### CON-8: JMAP `Envelope` exposes `seqNo`, which is inside the ciphertext, and its fields do not match `RoutingEnvelope`
- Severity: P2
- Location: spec/11-transport.md:331-339, :349; spec/05-messaging.md:13, :181-196, :226; spec/05-messaging.md:318-322; spec/10-relays.md:561; spec/11-transport.md:279, :341-350, :404
- Evidence: 11:336 "`seqNo` UInt Sequence number within the epoch (for client-side ordering)"; 11:349 "sort by `receivedAt` (default) or `seqNo`". 05:13 `seq` is "inside the ciphertext"; 05:226 "invisible to Relays". `Envelope.id` is "ULID ... server-assigned" (11:332) while `RoutingEnvelope.id` is a CID and history entries are envelope CIDs (05:322); `Envelope` has no `accessSig`, `ts`, `expiryHint`, `broadcastPayload`. A second history API: 10:561 `GET /v1/agora/history/<channelToken>?before=<cid>&limit=50`. 11:279 "envelopes written through the sync API carry the same epoch access proof" but no `Envelope/set` exists (11:341-350) and 11:404 says JMAP does no "New message delivery".
- Problem: The relay cannot populate `seqNo`; the stored object does not round-trip the envelope relays must verify and clients must re-verify; two history APIs keyed by different ids; write capability stated and denied.
- Suggested fix: Drop `seqNo`; make `Envelope` carry the exact encoded `RoutingEnvelope` bytes plus relay metadata (`receivedAt`, CID); pick one history API (JMAP) and delete 10:561 or define it as an alias; either define `Envelope/set` with the access proof or delete the sentence in 11:279.
- Needs decision: no

### CON-9: P-256 device keys allowed in §12.6, but MLS ciphersuite, JWS and §2.2 are Ed25519-only
- Severity: P2
- Location: spec/12-security.md:89; spec/05-messaging.md:46; spec/13-encoding.md:51, :76; spec/02-identity.md:80, :255
- Evidence: 12:89 "P-256 (`ES256`) MAY be used as the authentication key algorithm for that device". 05:46 "All MLS groups in Agora MUST use `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519`". 13:76 verifier requires the method be "holding an Ed25519 public key". 02:80 "Each device signs with its own Ed25519 device key: its MLS leaf signatures, its KeyPackages and its JWS signatures". 02:255 keys are "generated inside the device's secure hardware boundary (Secure Enclave, ...)".
- Problem: A P-256 device key cannot sign MLS leaves under 0x0001 or JWS under §13.1.1, so the §12.6 permission produces a non-conformant device; and §2.5.1's Secure Enclave generation cannot yield the Ed25519 key §2.2 requires (decision D6 fixes Ed25519).
- Suggested fix: Delete the P-256 allowance; say platforms without Ed25519 in hardware use the best available protected software store (as §2.2 does for browsers), and drop "Secure Enclave" from the list in 02:255 or qualify it.
- Needs decision: no

### CON-10: Pin list is "sequenced-v1" with `#Chat` object bodies in §5.2.6, but §14 has no such default and requires `JmapSet` for sequenced ops
- Severity: P2
- Location: spec/05-messaging.md:354-364; spec/14-jmap.md:61, :73, :158; spec/05-messaging.md:297
- Evidence: 05:354 "A pin or unpin is an MLS application message of type `urn:ietf:params:jmap:chat#Chat`"; 05:362-364 "`Chat` is a sequenced type ... written under the `sequenced-v1` consistency model". 14:61 lists "`Chat` membership" as derived; no row for `Chat.pinnedMessageIds`; 14:73 "A type with no stated default is `single-author`". 14:158 a sequenced operation's "envelope has `type` `urn:agora:type:JmapSet` ... with an added member `after`".
- Problem: §14's classification makes the pin list single-author (wrong, multiple writers), and a `#Chat` object body has no `after` head, so it cannot be validated by §14.4.4's closing-epoch rule.
- Suggested fix: Add a §14.2.3 row "chat `Chat.pinnedMessageIds` | `sequenced-v1` | holders of `pin`", and change §5.2.6 to submit pin updates as `JmapSet` patches on `Chat` (or define that a sequenced object-form write also carries `after`).
- Needs decision: no

### CON-11: Relays must keep `pushHandle` → `channelTokens` registrations, which is outside the relay observation budget
- Severity: P2
- Location: spec/11-transport.md:160, :194-203, :209-212; ARCHITECTURE.md:143-162; spec/12-security.md:22
- Evidence: 11:160 "the Relay knows `channelToken` → pushHandle"; 11:194 client "Registers `{ pushHandle, proxyEndpoint, channelTokens }` with their Relay". ARCH §5 item 7: "For push proxies only: opaque device push handles and wake-up timing." 12:22 lists what a Relay can observe as "exactly the ARCHITECTURE.md §5 observation budget" and omits push state.
- Problem: The relay retains a persistent handle that links every channel token a device follows, which ARCH §5 grants only to push proxies; S6 makes anything outside §5 a violation unless opted in and declared. (Push-on-by-default is decided; the budget text was not updated to match.)
- Suggested fix: Add to ARCH §5 a relay item "push registrations: `pushHandle`, proxy endpoint, and the `channelToken`s registered under it", and mirror it in §12.3; also state how registrations follow token rotation each epoch (currently undefined).
- Needs decision: no

### CON-12: DM delivery uses "relay hints" from the recipient's DID document, which §2 forbids
- Severity: P2
- Location: spec/04-access-control.md:151, :153; spec/02-identity.md:37, :302; spec/10-relays.md:448, :476
- Evidence: 04:151 "the sending client SHOULD use the Relays known to be serving the recipient's DID (discoverable from the recipient's DID document relay hints)"; 04:153 "DM reachability is determined by the recipient's relay hints". 02:302 "The DID document MUST NOT name an infrastructure operator (relay or other IO) as the user's service endpoint". 02:37 Pkarr "record MUST NOT name a relay or other IO". 10:476 Pkarr lookup step 4 "use relay endpoints".
- Problem: §4.6 depends on data §2 prohibits, so DM reachability has no specified mechanism.
- Suggested fix: Rewrite §4.6 Relay routing / Cross-topology: the sender uses its own relays and relays reach each other by gossip/peering; or define CO-chosen relay hints in a CO record (not the user DID document). Delete "use relay endpoints" from 10:476.
- Needs decision: yes. Options: (a) no per-user relay hints; rely on mesh fan-out and the sender's CO relays; (b) relay hints in a CO-signed record per user; (c) relay hints inside the DM group only, after first contact via the `KeyPackageEndpoint`. Recommend (a)+(c).

### CON-13: Channel history head is said to live in CO-signed channel state, which members cannot update per message; history append is undefined
- Severity: P2
- Location: spec/05-messaging.md:318; spec/03-spaces.md:131; ARCHITECTURE.md:101-104; spec/06-calls.md:277; spec/09-interop.md:195; spec/14-jmap.md:115
- Evidence: 05:318 "Each message envelope CID is appended to the channel's history DAG, and the channel state document tracks the latest history CID." 03:131 channel state is "signed only by these CO keys". The `RoutingEnvelope` (05:181) has no previous-CID link.
- Problem: A per-message history head in owner/admin-signed state is impossible, and no part says who appends to the "IPLD linked list" or how. Several parts depend on "the channel's IPLD history DAG" (RecordingGrant 06:277, gateway SystemEvent 09:195, catch-up 14:115).
- Suggested fix: Define history as the set of envelope CIDs per `channelToken` held by relays (and walked via the sync API), or define a member-written link field inside the sealed payload; remove "channel state document tracks the latest history CID".
- Needs decision: yes. Options: (a) history = relay-indexed envelopes per token, no DAG; (b) per-sender hash chain inside the encrypted payload; (c) periodic CO-signed checkpoints. Recommend (a) with optional (c).

### CON-14: Space state is a linear signed chain in §3.3 but merged by union/LWW in §5.1.1
- Severity: P2
- Location: spec/03-spaces.md:49, :131, :157; spec/05-messaging.md:25
- Evidence: 03:49 "subsequent state is represented as a signed chain of mutations, each referencing the prior state CID in its `prevStateCID`". 05:25 "Concurrent non-conflicting mutations ... are merged by taking the union. Conflicting mutations ... resolved last-writer-wins using the `seq` value. In an exact tie ... owner beats admin."
- Problem: Two admins signing against the same `prevStateCID` fork the chain; §3.3/§3.4 (`GET /head` returns one CID) have no fork rule, and a union "merge" has no signer, so it is not valid Space state under 03:131.
- Suggested fix: State that forks are resolved by a defined rule (e.g. higher `seq`, then owner over admin, then lower CID) and that the losing branch's mutations must be re-signed on top of the winner; drop "merged by taking the union".
- Needs decision: no

### CON-15: The epoch access proof is used outside envelopes (pin instructions, SFU admission) with no defined form
- Severity: P2
- Location: spec/05-messaging.md:368; spec/10-relays.md:536; ARCHITECTURE.md:152, :210; spec/06-calls.md:111
- Evidence: 05:368 "sends the relay a pin instruction for the CID ... carried with an epoch access proof"; 06:111 "Client presents the MLS-membership access proof for the voice channel's `channelToken`". `accessSig` is defined only as a signature over a routing envelope (05:206).
- Problem: Neither the pin/unpin instruction (message, endpoint, signed bytes, replay protection, which agreement's quota it charges) nor the SFU proof (and how an SFU, which has no `AccessChainRegistration`, learns the current access public key) is specified anywhere, though relays MUST honor pin instructions.
- Suggested fix: Define a `urn:agora:type:PinInstruction` (CID list, `channelToken`, `epoch`, nonce/expiry) signed with the access key, its relay endpoint, and an SFU challenge-response that includes the access public key chain or an `accessKeyAnnouncement` the SFU can verify.
- Needs decision: no

### CON-16: The KeyPackage Store API is referenced as a versioned surface but never defined; its fragments disagree
- Severity: P2
- Location: spec/13-encoding.md:117; spec/07-compliance.md:185-195; spec/05-messaging.md:61-73; spec/02-identity.md:19, :34, :302, :381; spec/10-relays.md:457; ARCHITECTURE.md:284
- Evidence: 13:117 "KeyPackage Store API | v1 | URL path prefix `/v1/agora/kp/`". The only HTTP semantics are in the compliance section, 07:195 "MUST return a fresh, unused `KeyPackage` on each GET request and MUST accept a `Welcome` by POST", with example `https://archive.example.com/v1/agora/keypackages` and service `"type": "AgoraKeyPackageEndpoint"`. §2.1/ARCH call it the "`KeyPackageEndpoint` service entry"; 10:457 uses `/v1/agora/kp/z6Mk...`. §2.5.4 step 7 "uploads them" with no upload operation defined.
- Problem: Publish (upload, auth, last-resort marking), fetch, and Welcome delivery are implemented by every client and identity host but have no normative definition; the service `type` string and path prefix differ between parts.
- Suggested fix: Add a KeyPackage Store section (in §5.2.1.1) defining the service type (`AgoraKeyPackageEndpoint`), `POST` publish (signed by device key), `GET` fetch-and-consume, last-resort flag, `POST` Welcome, rate limiting, and the path prefix; point §2.1, §2.5, §4.6, §7.8.2 and §13.2 at it.
- Needs decision: no

### CON-17: `did:web` treated as a user identity in §4.6, §9.1 and Appendix A; §2.1/§14.6.2 exclude it
- Severity: P3
- Location: spec/09-interop.md:24; spec/04-access-control.md:153; spec/99-appendices.md:11; spec/02-identity.md:10; spec/14-jmap.md:225
- Evidence: 09:24 "Agora users are identified by DID (`did:key` or `did:web`)"; 04:153 "A user with a `did:web:agency.example` identity"; 99:11 Identity "W3C DID Core, `did:key`, `did:web`". 14:225 "`did:web` is not accepted as a user identity".
- Problem: Stale method lists contradict the decided three methods (webvh default, plc/key opt-in).
- Suggested fix: Replace with `did:webvh`, `did:plc` or `did:key` (and in 99:11 note `did:web` is used only for relay DIDs).
- Needs decision: no

### CON-18: MIMI section makes 0x0001 "in addition to any other suites"; §5.2.1 allows only 0x0001
- Severity: P3
- Location: spec/09-interop.md:20; spec/05-messaging.md:46
- Evidence: 09:20 "Agora MUST support ... 0x0001 ... in addition to any other suites it implements". 05:46 "All MLS groups in Agora MUST use" 0x0001.
- Problem: Implies other suites exist.
- Suggested fix: 09:20 "Agora groups use 0x0001 (§5.2.1), which is the MIMI baseline."
- Needs decision: no

### CON-19: Wrong or stale cross-references
- Severity: P3
- Location / Evidence / fix:
  - spec/02-identity.md:285 "gossipsub discovery mesh (§3)": discovery is §10.3. Fix: §10.3.
  - spec/10-relays.md:120 operator identity is "relevant to ... compliance logging (§7)": relays have no compliance-logging role (ARCH S8, §7.3). Fix: drop "and compliance logging (§7)".
  - spec/11-transport.md:260 "(ARCHITECTURE S1, §5.3 item 4)": ARCHITECTURE has no §5.3; the relay-side JMAP erratum is ARCHITECTURE §7 item 4. Fix accordingly.
  - spec/12-security.md:56 "Relays never authenticate client identity (ARCHITECTURE.md S1, §4)": the decision is ARCHITECTURE §8 Q2; §4 is compelled production. Fix: "S1, §8 Q2".
  - spec/12-security.md:132 helpdesk enrollment "recorded in the provisioning audit log (§2.5.5)": the helpdesk path and its audit requirement are §2.5.8. Fix: §2.5.8.
  - spec/08-cross-space.md:3 header "Binds: CO" vs line 6 "Binds: both (CO throughout; §8.6 peering also binds IO)". Fix header to "both".
  - spec/13-encoding.md:32 example `urn:agora:type:PresenceEvent`: no such type; presence is `urn:ietf:params:jmap:chat:websocket#ChatPresenceEvent` (05:273). Fix example to `urn:agora:type:SpeakRequest`.
- Needs decision: no

### CON-20: Same concept, different names across parts
- Severity: P3
- Location / Evidence / fix:
  - Recording disclosure label: spec/06-calls.md:306 "MUST include the `loggerLabel` from the space's `ComplianceLoggingConfig`" while the recorder's config has `recorderLabel` (06:359), and a Space may have VTC compliance without text logging. Fix: use `vtcCompliance.recorderLabel`.
  - Inner expiry field: spec/05-messaging.md:196 "`expiryHint` is set by the sender to match the inner payload `expiry` value" vs `senderExpiresAt` (05:307). Fix: `senderExpiresAt`.
  - Ephemeral types: spec/14-jmap.md:60 "chat `PresenceStatus`, `Chat/typing`" vs `ChatPresenceEvent`, `ChatTypingEvent` (05:272-273, 07:115). Fix names.
  - spec/14-jmap.md:111 "§5.1.1 (`seq`, `causalRefs`, gap buffering)": `causalRefs` is not defined anywhere; §5.1.1 uses `replyTo`/`threadRootId`. Fix: drop or define.
  - Pkarr profile record: spec/02-identity.md:35 `cid=<profile CID>` and 10:456 `"cid=bafyrei..."` vs 10:465 value "`ipfs://` URI of the user's current profile IPLD node"; 02:90/:115 call it the "`_profile` field". Fix: bare CID everywhere, call it the `_profile._agora` record.
  - `regulatedMembers`: 07:52 "part of the `ComplianceLoggingConfig`" and 07:161 `complianceLogging.regulatedMembers`, but the 07:26-38 example omits it and 07:48 shows it as a free-standing member. Fix: put it inside the example block.
  - Relay manifest signer: 10:102 "signed ... by the Relay operator's key" vs 10:116 signed "by the key declared in the [relay] DID document" and 10:298 "the Relay for relay records". Fix: "by `relayDID`".
  - Service tiers: 10:346 `RelayEntry.tiers` (`label`, `maxBandwidthMbps`) vs 10:642 `RelayAd.serviceTiers` (`id`, `retentionDays`, `bandwidthTierGbPerMonth`). Fix: one schema.
  - Sequencer endpoint path: 03:119 and 14:132 `https://seq.example.com/agora/v1` vs the §1.1 convention "path prefix on HTTP endpoints (`/v1/agora/...`)". Fix: `/v1/agora/seq`.
- Needs decision: no

### CON-21: Sender identity and non-URN types inside MLS bodies contradict §5.2.2 / §13.1 / §14.3.2
- Severity: P3
- Location: spec/06-calls.md:28; spec/09-interop.md:190; spec/07-compliance.md:222, :227; spec/05-messaging.md:228; spec/13-encoding.md:15; spec/14-jmap.md:105
- Evidence: 05:228 "Objects carried inside MLS have no object-level signature and no sender field"; 14:105 a store "MUST NOT take sender identity from the `body`". Yet `ParticipantState` has `"sender"` (06:28), gateway `SystemEvent` has `"addedBy"` (09:190), `ComplianceDisclosureNotice` has `"issuedBy"` (07:222). 07:227 says it is "an MLS application message of type `ComplianceDisclosureNotice`"; §13.1 requires `type` to be an absolute URI. `DMGroupDescriptor` (04:145) is sent as an MLS message with no type given.
- Problem: Receivers may trust a body sender field; unnamed/non-URN types are unknown types under §13.2 and would be ignored.
- Suggested fix: Remove sender fields from in-group bodies (or state they MUST equal the MLS sender and are otherwise ignored); name the types `urn:agora:type:ComplianceDisclosureNotice` and `urn:agora:type:DMGroupDescriptor` and add them to the §5.2.3 table with the §6.14 call types.
- Needs decision: no

### CON-22: Signers and fields that other parts rely on are unspecified
- Severity: P3
- Location / Evidence:
  - spec/07-compliance.md:267 `DMComplianceAuditEntry` "is signed per §13.1.1" with no signer, though §13.1.1 (13:53) says "The section defining each object states its required signer"; the conformance table (07:293) says the regulated member's client publishes it, 07:253 says "The regulated member's Space MUST record". Gap records required by 07:276 have no format.
  - spec/12-security.md:123 "The signing key fingerprint is embedded in the message's MLS authenticated data" and 12:147 "The compliance archive records ... the signing key fingerprint": no such field exists in §5.2.2 or in `ComplianceRecord` (07:94-106).
  - spec/02-identity.md:469 encrypted backup "restores MLS state and device keys" vs 02:224-229 (non-extractable keys cannot be backed up) and 02:255 (enterprise keys "never leave" hardware).
- Suggested fix: Name the `DMComplianceAuditEntry` signer (the regulated member's device key, or the logger) and define a gap-record type; either add a key-identifier field to `ComplianceRecord` and say where it comes from (the MLS leaf credential) or soften §12.7; qualify 02:469 to software keystores only.
- Needs decision: no

### CON-23: Terms used but never defined
- Severity: P3
- Location / Evidence:
  - `UserAd` (10:275, :298, :302): signing rule given, no schema.
  - "DID authentication to the CO" (03:184), registration service "authenticates as a current member" (05:204), TURN credential service "issues them only to current members" (06:214), CO invite service (14:216): four CO services authenticate members by DID with no defined method.
  - Space state members referenced but unnamed: moderation-log tail CID (04:121), references to `InviteRevocation`, `ChannelShareAgreement`/`ChannelShareRevocation` records (03:154, 08:57), `Space.calendarId`/`taskListId` (14:64); `commitPolicy` (04:16) has no value format. `speakerBot`, `broadcasterRoles`, `e2eeMedia`, `powPolicy`, `sfus`, `turnServers`, `gateways`, `mimiInterop`, `sharedChannels`, `complianceLogging`, `retentionNotice` are each defined only in their own section, and §3.3 is not an index of them.
  - "channel state document" (05:318, 09:50, 09:96, 09:179) vs channel entries inside Space state (03:131): no separate document is defined.
- Suggested fix: Add a `UserAd` schema or drop it; define one DID-auth mechanism for CO services (e.g. a §13.1.1-signed challenge); add a field index to §3.3 listing every Space-state and channel-entry member with its defining section; replace "channel state document" with "the channel's entry in Space state".
- Needs decision: no

### CON-24: Version registry claims to list "every versioned protocol surface" but omits several
- Severity: P3
- Location: spec/13-encoding.md:106-121; spec/11-transport.md:265, :283; spec/10-relays.md:570; spec/03-spaces.md:157; spec/14-jmap.md:159-163; spec/06-calls.md:99, :197
- Evidence: 13:106 "lists every versioned protocol surface". Missing: JMAP sync (`/v1/agora/jmap`, capability `urn:agora:v1`, `jmap-sync-v1`), blob API `/v1/agora/blob/`, history API, Space endpoint (`/head`, `/broadcast-key/`), sequencer API (`/submit`, `/log`), SFU endpoint `/v1/agora/sfu`, TURN credential endpoint, the `/.well-known/agora-relay` manifest. spec/01-overview.md:21 (§1.1) also says transport endpoints return "HTTP 404/410"; 13:113-114 says "HTTP 404".
- Suggested fix: Add the rows, or narrow the claim to "IO-facing surfaces" and list those fully.
- Needs decision: no

### CON-25: Other cross-part inconsistencies on observation and declarations
- Severity: P3
- Location / Evidence:
  - Manifest vs agreements: 10:628 the Relay "MUST declare the same values in its manifest" as each agreement's `observationBudget`, but the manifest holds one `observationBudget` (10:87) and a Relay may hold many agreements with different values (10:610). Fix: manifest declares the maximum across agreements.
  - §12.3 (12:22) lists "exactly the ARCHITECTURE.md §5 observation budget" but omits item 6 (billing DIDs and registered chains). Fix: add it.
  - `pushUrgency` "`high` is used for direct messages" (11:233) is relay-visible, while 04:125 and 12:48 say relays "cannot distinguish DM traffic from channel traffic". Fix: drop DM as an urgency trigger or acknowledge the leak in §12.4.
  - ARCH §5 item 6 says an IO "MUST NOT be able to map a chain to a Space", and S1 forbids IO knowledge of token→Space mapping; 14:193 accepts that a sequencer's "operator can associate its streams with those Spaces". The per-community sequencer is decided (D2); ARCHITECTURE should carry an explicit exception so the governing document and §14.4.6 agree.
- Needs decision: no

### CON-26: Exporter and KDF label inventory: all unique, naming style inconsistent
- Severity: P3
- Location: as listed
- Evidence (complete list found in ARCHITECTURE.md and spec/):

  | Label | Kind | Context / use | Where |
  |---|---|---|---|
  | `agora channel token` | MLS exporter | ctx `channelCID`, 32 | 05:194 |
  | `agora access` | MLS exporter | ctx `channelCID`, 32 | 05:202, ARCH:196 |
  | `agora sealed envelope` | MLS exporter | ctx `channelCID`, Nk | 05:218 |
  | `agora blob` | MLS exporter | ctx `""`, Nk | 03:190 |
  | `agora-dm-token` | MLS exporter | ctx `""`, 32 | 04:125 |
  | `agora-media-key` | MLS exporter (SFrame, RFC 9605 §5.2) | media | 06:160 |
  | `agora data channel` | MLS exporter (SFrame) | data channels | 06:410 |
  | `agora broadcast token` | HKDF info (+ `keyEpoch`) | broadcast token | 05:133 |
  | `agora/v1/social-recovery-key` | HKDF info | recovery seed | 02:174 |
  | `agora/sealed/v1` | AEAD aad prefix | sealed envelope | 05:218 |
  | `agora/blob/v1` | AEAD aad prefix | group blob | 03:190 |
  | `agora/broadcast/v1` | AEAD aad prefix | broadcast payload | 05:141 |
  | `agora-recording-archive-v1` | HPKE info | recording archive | 06:345 |
  | `agora-relay-v1` | SHA-1 preimage | DHT infohash (open) | 10:437 |

- Problem: No collision, but exporter labels mix space-separated and hyphenated forms (`agora-dm-token`, `agora-media-key` vs the rest), the DM token uses empty context while every other per-channel label uses `channelCID` (see CON-1), and only some labels carry a version. With no registry, a future label could collide.
- Suggested fix: Normalize exporter labels to one style (e.g. `agora <purpose> v1`), and add a label registry table to §13.
- Needs decision: no

---

No conflicts found in: timer and limit values (presence 30/60 s, typing 3/10 s, `ttl` 15 s, ring 120 s, SpaceAd 60/45 s, heartbeat 60 s, nonce 300/600 s, push TTL 30 days, broadcast rotation 30 days, `speakerCap` 200/500, interactive cap 200, mesh threshold 4, E = 4 epoch bits) are stated consistently wherever they recur. ARCHITECTURE.md's references into spec/ (§10.4.1, §5.2.2, §10.5.1, §14.4, §10.1/§11) point to the correct sections. Gossip topic names (`v1/agora/discovery`, `v1/agora/channel/<channelToken>`) and relay capability strings are spelled consistently.

Coverage: read fully ARCHITECTURE.md, spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; bd decision memories (agora-*).
