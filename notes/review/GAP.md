# GAP review: protocol-level completeness

Lens: topics a protocol spec of this kind must cover that Agora omits or only
gestures at. Contradictions, example errors and field-level implementability
are left to other lenses; where a gap has a contradiction as its symptom, the
contradiction is cited only as evidence.

### GAP-1: No way to bring a live group onto a new relay (S5 has no mechanism)
- Severity: P1
- Location: ARCHITECTURE.md:106-109 (S5); spec/10-relays.md:610-622; spec/05-messaging.md:203; spec/12-security.md:36; spec/02-identity.md:302; spec/04-access-control.md:151
- Evidence: S5: "A CO MUST be able to add, remove or replace any IO without changing ... MLS group state or history". 10-relays:612: "The CO's registration service submits an `AccessChainRegistration` to the Relay carrying the group's first-epoch access public key"; the example has `"epoch": 0`. 12-security:36: "Clients SHOULD connect to multiple Relays simultaneously." 02-identity:302: "The DID document MUST NOT name an infrastructure operator (relay or other IO)".
- Problem: Registration can only start a chain at its first epoch. A relay added when a group is at epoch N has no specified way to learn the current access key, so it cannot verify `accessSig` and must reject every envelope. Nothing tells members which relays serve a private Space or DM, or that the set has changed: Space state has no relay field, invites carry only `spaceEndpoint`, and DID documents may not name relays. Nothing says how a new relay accepts history envelopes signed under past-epoch keys it never saw, or what an outgoing relay owes at `validUntil` or on termination (keep, delete, hand off). S5 is a governing MUST that the spec text cannot satisfy today.
- Suggested fix: Add a "Relay migration" subsection to §10.5. (1) Allow `AccessChainRegistration` at any epoch: the registration service registers (`epoch`, `channelToken`, `accessPublicKey`) for the current epoch, countersigned as for announcements. (2) Define a CO-signed, member-only relay set (for example a `relays` field in the Space-only view served by the Space endpoint, plus a group-encrypted per-DM equivalent), together with client behavior when it changes. (3) Define bulk history import: the CO or a member re-uploads historical envelopes or blobs as content-addressed blobs under the agreement quota, which is not live publication and needs no `accessSig`. (4) Define what an agreement owes at end of term (a data deletion deadline, and an optional export window for the CO). (5) Give a worked "replace relay A with relay B" sequence.
- Needs decision: yes. (a) A CO-signed relay set in member-only Space state; (b) relay hints carried only in MLS messages; (c) leave it to client configuration. Recommend (a): it is CO-authored (S4), never reaches the IO (S1), and it makes replacement a single state change.

### GAP-2: Billing key and registration service have no rotation or compromise procedure
- Severity: P1
- Location: spec/05-messaging.md:204-205; spec/10-relays.md:588, 608-624; ARCHITECTURE.md:177-183
- Evidence: 05-messaging:204: "Relays MUST reject an announcement without a valid `billingSig` from that agreement's billing DID." 10-relays:608: "A CO MAY use one billing DID for all of its Spaces".
- Problem: The billing key is an online key held by the registration service. It is the single trust anchor for every chain of every Space the CO runs through a relay. Someone holding it can countersign an announcement only they can use, which is the lockout attack the countersignature exists to stop, and they can register chains under the CO's quota. The spec defines no rotation, no revocation, no "agreement re-keyed" message, and no way to move existing chains to a new billing DID (this needs GAP-1's mid-chain registration). There is also no availability requirement for the service. Under the outage rule, a removed member can keep writing for as long as the service is down.
- Suggested fix: Add a §10.5.3 "Billing key lifecycle". Cover a `BillingKeyRotation` record signed by the old and new billing DIDs and by the relay, which re-binds the agreement and every registered chain in one step. Cover emergency revocation when the old key is presumed hostile: a fresh agreement signed with the new key, plus re-registration of current epochs under it (GAP-1), with relays dropping chains under the revoked agreement. Recommend HSM custody and per-member, per-chain rate limits on countersigning. State a maximum tolerated outage, after which members force a Commit once the service returns.
- Needs decision: no

### GAP-3: Incident response is missing for most key classes
- Severity: P2
- Location: spec/04-access-control.md:12; spec/02-identity.md:151-165, 439-459; spec/07-compliance.md:58-88; spec/06-calls.md:345; spec/10-relays.md:231; spec/14-jmap.md:189; spec/11-transport.md:164-173
- Evidence: 04-access-control:12: "Ownership transfer is executed via a signed `SpaceState` mutation that replaces the `owner` DID, signed by the current owner." 10-relays:231 covers only planned rotation ("old key with `\"status\": \"deprecated\"`"). The word "compromise" appears only in §12.1/12.2 (MLS), the broadcast security note and push-handle rotation.
- Problem: Device revocation is specified (§2.2, §2.5.5). The other key classes have no response:
  - **Space owner or admin key.** Compromise lets an attacker transfer ownership or rewrite state. Loss, including an offboarded employee owner whose DID is blanked (02-identity:437), freezes the Space forever. The spec has no recovery or override.
  - **Recovery and social-recovery keys** are `did:webvh` update keys (02-identity:123). A thief can take over the DID, and nothing says what the user or their contacts do next.
  - **Provisioning service key and update key.** Compromise lets an attacker add keys to every employee DID. The additions are auditable, but the spec defines no detection, bulk response or contact notification.
  - **Compliance logger and recorder keys.** The logger holds all plaintext. The recorder's `keyAgreement` key decrypts every archive (06-calls:345). The spec gives no rotation, re-encryption or removal procedure.
  - **Relay signing key.** The manifest has no `revoked` status and peers get no emergency path.
  - **Sequencer key.** Replacement is defined (14-jmap:189) but forged stamps are not addressed.
  - **Push proxy.**
  - **Space endpoint / TLS.**
- Suggested fix: Add a §12.8 "Key compromise and incident response" with one row per key class: what an attacker gains, how compromise is detected, the immediate response (records to publish, MLS actions), the recovery end state, and residual exposure. It needs at least two new mechanisms: (1) a Space owner recovery path, for example an optional `ownerRecovery` DID or quorum in genesis state that can sign an ownership transfer after a delay; (2) a manifest key `status: "revoked"` that peers honor at once.
- Needs decision: yes, for Space owner recovery. (a) An optional recovery DID or quorum fixed at genesis; (b) for enterprise Spaces, require the owner to be an org service DID, not a person; (c) no recovery, so the Space is re-founded. Recommend (a) plus (b) as guidance.

### GAP-4: Space and channel lifecycle undefined beyond "the owner may transfer or delete"
- Severity: P2
- Location: spec/04-access-control.md:12; spec/03-spaces.md:49, 131; spec/08-cross-space.md:22
- Evidence: 04-access-control:12: "The Space Owner has sole authority to transfer or delete the space". 03-spaces:49: "The Space's identity is anchored to its genesis CID". 08-cross-space:22: "Channel deletion (only the home space owner can delete)".
- Problem: Many lifecycle steps are named but none is specified:
  - **Creation.** The genesis document's required fields, who signs it, and the bootstrap order: Space MLS group, then channel groups, then chain registration (§10.5.1), then Space endpoint.
  - **Deletion.** There is no deletion record. The spec does not say what clients do or what happens to relay-pinned CIDs, registered chains, the compliance archive (whose retention outlives the Space) and shared channels.
  - **Archival.** There is no read-only mode.
  - **Channel create, rename, move and delete.** The spec does not say whether a path change alters `channelCID`, and so the `channelToken` and exporter context.
  - **Admin grant and revoke.** Space state has no `admins` field, though S4 validation depends on "an admin authorized under the prior state".
- Suggested fix: Add a §3.5 "Space lifecycle" covering creation (genesis contents and bootstrap order), ownership transfer (including acceptance by the new owner and recovery per GAP-3), archival (an `archived: true` state that clients enforce as read-only, with groups kept), deletion (a terminal `SpaceDeleted` state record, then client behavior, unpinning, chain de-registration, and compliance archive retention that continues past deletion), and channel lifecycle (create, rename without changing `channelCID`, delete with MLS group teardown).
- Needs decision: no

### GAP-5: Member exit flows are missing (leave Space, leave channel or DM, delete account)
- Severity: P2
- Location: spec/07-compliance.md:231; spec/02-identity.md:426; spec/04-access-control.md:20, 88-96; spec/14-jmap.md:61
- Evidence: 07-compliance:231: "They MAY leave the group (via standard MLS Remove self-proposal) at any time." 02-identity:426: "The revoked device's client (if still running) SHOULD issue `Remove` self-proposals".
- Problem: Under RFC 9420 a member cannot commit a proposal that removes itself, so someone else must commit it. The spec never says who must do so, how fast, or what happens if nobody does: the leaver stays a member, and keeps getting the access key and media keys. Leaving a Space has no defined operation at all: no Space-state change, and no rule for being removed from every channel group. Space state as specified also has no member or role-assignment list, though §14.2.3 calls `SpaceMember` "derived" from it. There is also no flow for a user deleting their identity (`did:webvh` deactivation, effect on groups, `did:key` abandonment), and no rule for what happens when a DM group drops to one member.
- Suggested fix: Add a §4.7 "Leaving". Define `SpaceLeave` (a member-signed request that an admin turns into a state change plus Removes). Define a self-Remove commit duty: any member, or a designated committer if `commitPolicy` restricts commits, MUST commit a pending self-Remove proposal within N seconds of receiving it, and clients MUST stop sending to a member with a pending self-Remove. Define account deletion: deactivate the DID log, then contacts' clients Remove all of the DID's leaves on seeing the deactivation. Define DM-group teardown when one member remains.
- Needs decision: no

### GAP-6: Abuse and spam handling stops at relay rate limits
- Severity: P2
- Location: spec/10-relays.md:59, 665-683; spec/12-security.md:54-64; ARCHITECTURE.md:305-306; spec/04-access-control.md:62, 147, 157-159; spec/99-appendices.md:315 (Appendix B item 1)
- Evidence: Manifest has `"abuseContact": "abuse@example.com"` with no process. 12-security:64: "Spam control is local policy". 04-access-control:62: "`maxUses: 0` means unlimited uses". 04-access-control:147: the DM creator "delivers each Welcome by POST to the `KeyPackageEndpoint` in the invitee's DID document".
- Problem: With blind relays, abuse handling is a CO and client problem, and the spec has no end-to-end path for it:
  - **No member reporting.** There is no report message type and no way to send evidence (franked plaintext) to the CO's moderators.
  - **No DM consent on the invitee side.** Anyone who can reach a user's `KeyPackageEndpoint` can drain KeyPackages and add the user to DM groups. §4.6.1 covers consent among existing members only. There is no message-request state or block list, and blocked contacts are mentioned only in 14-jmap:214.
  - **No CO-to-IO escalation.** A CO cannot ask a relay to drop a chain it registered, for example after an open invite link is abused.
  - **No relay-side legal takedown.** A relay that receives a takedown for a CID it cannot read has no defined action, and no rule for whether it notifies the CO.
  - **Open-link joins.** Admission at scale has no rate or PoW gate.
- Suggested fix: Add a §4.8 "Abuse handling". Cover (1) a `urn:agora:type:AbuseReport` sent in a DM group to the CO moderation principal, carrying the reported envelope's decrypted bytes and its MLS-authenticated sender proof, so the report is verifiable. (2) Invitee-side consent for DMs: groups from non-contacts start in a "request" state, with no read receipts and no automatic join, and KeyPackage hosts MAY require the requester to be a contact or solve PoW. (3) An agreement-scoped `ChainDeregistration` signed by the billing DID. (4) Relay takedown handling: unpin and evict the named CID, and notify the agreement's CO through a defined channel. (5) Open-link admission throttling at the CO invite service.
- Needs decision: yes, for invitee DM consent. (a) A message-request state in the client only; (b) plus KeyPackage-host gating by contact list; (c) nothing. Recommend (a) as MUST and (b) as MAY.

### GAP-7: Limits and quotas are scattered, partly local policy, and lack floors
- Severity: P2
- Location: spec/05-messaging.md:40, 90, 572; spec/06-calls.md:78, 101; spec/02-identity.md:346; spec/11-transport.md:112, 303-304; spec/12-security.md:61; spec/10-relays.md:540
- Evidence: "Maximum 200 members" (05:40); "`speakerCap` ... default 200, maximum 500" (05:90); `"maxParticipants": 500` (06:101); device limit "default: 10" (02:346); `"maxEnvelopeBytes": 65536` only in the JMAP Session object (11:303); "Limit values are local Relay policy" (11:112); "Relays MUST enforce per-`channelToken` rate limits" (12:61).
- Problem: Several limits are missing:
  - DM group size.
  - Space state document size. It inlines roles, channels, emoji and `regulatedMembers`, so it grows with membership.
  - Live-stream envelope size. 64 KiB appears only as a JMAP capability, yet a Commit, or a Welcome carrying a 500-leaf ratchet tree, can exceed it.
  - KeyPackage batch size.
  - Message body length.
  - Channel count.
  Relays MUST rate-limit per token but have no minimum rate they must allow. The protocol itself generates steady traffic: presence every 30 s per member per channel, which is about 6.7 envelopes/s in a 200-member channel before any chat. So a conformant relay can throttle presence or Commits and break groups.
- Suggested fix: Add a §13.3 "Limits" table. List every protocol limit with its value and whether it is fixed or a configurable default: group sizes per mode, DM size, maximum envelope and payload size per transport, Space state size, KeyPackage stock, attachment size. Give relays a normative floor: "a relay MUST admit at least X envelopes/s and Y bytes/s per `channelToken` before rate-limiting", derived from the presence, typing and Commit cadence the spec mandates. Consider moving presence to the Space group only, or lowering its cadence.
- Needs decision: no

### GAP-8: A user's devices have no way to sync private data or history
- Severity: P2
- Location: spec/14-jmap.md:59, 115; spec/02-identity.md:208-229; spec/05-messaging.md:107, 320
- Evidence: 14-jmap:59: "`ReadPosition`, `ChatContact` ... synchronized only among the user's own devices." 14-jmap:115: "Objects written in epochs before a member joined are not readable by that member." 02-identity:220: backup contains "Current MLS key material for all group memberships".
- Problem: The spec defines no channel for a user's own devices to synchronize: no per-user "self" group or equivalent. So read positions, contacts, block lists and drafts cannot sync as stated. A newly added device sees no history from before it joined, which is a large UX gap for a "Discord-like" protocol, and the spec offers no device-to-device history transfer. Restoring a "full" backup of MLS state onto a second device while the first is still active would fork a leaf, reusing generation counters and secrets. The spec does not forbid this or explain the risk.
- Suggested fix: Add a §2.6 "Multi-device". Define a per-user MLS self-group containing only the user's devices, which carries the private `single-author` types and an optional history-transfer payload: an encrypted archive blob plus its key, sent from an existing device to a new one. State that a restored MLS state backup MUST NOT be used while the source device remains active. A restored device either replaces the source, which is then revoked, or rejoins every group as a new leaf and uses the backup only to read old history.
- Needs decision: yes. (a) A self-group plus optional history transfer; (b) a self-group only, with no history for new devices; (c) leave history to backups. Recommend (a).

### GAP-9: No privacy considerations section; CO-side observation and data-subject rights unaddressed
- Severity: P2
- Location: spec/12-security.md:38-52 (IO-only metadata analysis); spec/03-spaces.md:154, 184; spec/05-messaging.md:204; spec/04-access-control.md:121, 149; spec/02-identity.md:437; spec/07-compliance.md:40
- Evidence: §12.4 covers only what relays and mesh peers see. 05-messaging:204: the registration service "countersigns only an announcement requested by a DID it authenticates as a current member of the channel". 04-access-control:121: the moderation log has "no ability to retroactively delete entries". 02-identity:437: DID documents "MUST NOT be removed".
- Problem: The spec analyses IO observation carefully but never states what CO components learn:
  - The registration service gets per-member, per-channel Commit activity.
  - The Space endpoint gets every state fetch.
  - The KeyPackage host gets who adds whom and when, through fetches and Welcome POSTs.
  - The TURN credential service gets call attendance.
  - The sequencer operator can link streams to Spaces.
  Nor does it say what members learn about each other (presence, `lastActiveAt`, device labels with names, `platform` in public DID documents). It does not reconcile append-only, content-addressed records (IPLD history, moderation log, DID log, profile CIDs mirrored on IPFS) with erasure rights or a member's departure. Retention disposal after `retentionDays` and legal hold are not specified.
- Suggested fix: Add a §12.9 "Privacy considerations" (in the style of RFC 6973). Give per-component observation tables for CO services, matching the IO budget in ARCHITECTURE §5. Add data minimization guidance, for example: `deviceLabel` and `platform` SHOULD NOT be published in the DID document, and the registration service SHOULD NOT log requester DIDs beyond what abuse handling requires. Add an erasure model: what can be deleted (blobs, profile, cached copies), what cannot (signed chains), and the crypto-shredding option for group-encrypted blobs. Add compliance archive disposal and legal-hold rules.
- Needs decision: no

### GAP-10: No conformance classes beyond the relay, and no must-understand extensions
- Severity: P2
- Location: spec/10-relays.md:520-564 (the only conformance section); spec/07-compliance.md:281-300; spec/13-encoding.md:100-102 (§13.2)
- Evidence: §10.4.3 "A conformant Relay MUST:". Elsewhere "conformant client" is used without definition (04-access-control:10, 07-compliance:54). 13-encoding:102: "Space state documents MAY include extension fields ...; recipients MUST ignore extension fields they do not understand."
- Problem: Many roles have no conformance definition: client, Space endpoint, registration service, KeyPackage host, sequencer, push proxy, SFU, TURN credential service, compliance logger. Nothing marks which features are optional for a client: calls, broadcast, community mode, JMAP types, MIMI, the gateway UI. An implementer cannot claim conformance, and a CO cannot know which clients will enforce its policy. Because unknown Space-state fields are always ignored, a future policy field such as a new retention or capture rule would be silently ignored by older clients. That is unsafe for the enforcement points of ARCHITECTURE §6.3.
- Suggested fix: Add a §1.3 "Conformance". Define classes (Core Client; Client with Calls, Broadcast and Regulated-Member profiles; Relay; each CO service; Sequencer; SFU; Push Proxy), and give each a required-section list and a list of MUST-level behaviors. Add a `requiredExtensions` array to Space state, naming fields a client MUST understand. A client that does not understand one MUST treat the Space as read-only, or refuse to join and tell the user why.
- Needs decision: no

### GAP-11: Required disclosures have no accessibility or language requirements
- Severity: P2
- Location: spec/06-calls.md:293-308; spec/07-compliance.md:120-126, 227-229; spec/09-interop.md:179, 197; spec/05-messaging.md:163
- Evidence: 06-calls:293: "MUST display the `participantDisclosure` string ... as a non-dismissable system message ... and as a visible indicator in the call UI". 05-messaging:163: "a visible indicator (e.g., a megaphone icon)". `retentionNotice`, `participantDisclosure` and `e2eeNote` are each a single untagged string.
- Problem: The compliance consent model ("Consent is expressed by transmitting media after the disclosure is shown") rests on these disclosures, but the spec requires them only visually and in one language. Several participants are not covered: a blind participant, an audio-only or headless device, a speakerphone room, and a member whose language differs from the CO's. For them, "shown" may not mean "perceived", which weakens the legal basis the design relies on. The same applies to the gateway, broadcast and compliance indicators.
- Suggested fix: Require each mandated disclosure to have a programmatically exposed text equivalent (an accessibility API label, not an icon only). Require an audible announcement for recording disclosures in calls, before media starts. Make disclosure fields language maps (`{"en": "...", "de": "..."}`, BCP 47 keys) with a required default, and make clients pick the user's language. Name the protocol-mandated strings that clients MUST localize from a fixed meaning rather than show verbatim.
- Needs decision: no

### GAP-12: Internationalization unaddressed for human-visible identifiers
- Severity: P3
- Location: spec/03-spaces.md:30-45, 56; spec/02-identity.md:106-112; spec/05-messaging.md:529; spec/10-relays.md:380
- Evidence: Channel paths are "slash-delimited" with "no enforced depth limit" (03-spaces:45). Custom emoji `name` "MUST be at most 32 characters" (05-messaging:529). The only language marker is a directory `"language": "en"` (10-relays:380).
- Problem: Several basics are undefined:
  - The character set and normalization for channel paths. Two NFC/NFD spellings yield distinct paths, and matching against `channelAccess` globs and `scope` globs depends on the form.
  - Whether "characters" means code points or grapheme clusters.
  - Confusable and bidi handling for `displayName`, Space and channel names, which is an impersonation vector given that "Clients identify a person by the display profile" (02-identity:275).
  - Language tags for Space names and descriptions.
- Suggested fix: Add a §13.4 "Internationalization". Paths use a PRECIS IdentifierClass profile (RFC 8264) with NFC, and globs match after normalization. Display strings use the PRECIS FreeformClass / Nickname profile (RFC 8266). Lengths count Unicode scalar values. Clients SHOULD apply UTS #39 confusable detection to display names within a Space and isolate bidi text (UAX #9). Human-visible descriptive fields MAY be language maps.
- Needs decision: no

### GAP-13: No statement of time and clock assumptions
- Severity: P3
- Location: spec/05-messaging.md:131; spec/04-access-control.md:107; spec/10-relays.md:181; spec/02-identity.md:243; spec/06-calls.md:40, 444; spec/12-security.md:14
- Evidence: "A poster MUST encrypt under the `BroadcastKey` with the highest `keyEpoch` whose `notBefore` has passed" (05:131). "`x-agora-timestamp` MUST be within 300 seconds of the receiving Relay's clock" (10:181). Timeouts carry `expiresAt` (04:107).
- Problem: Correctness depends on wall clocks in at least eight places: broadcast key cut-over, which is also the subscriber-removal boundary; timeout expiry; invite, agreement, share-agreement and grant validity; KeyPackage lifetime; ring limits; the 24-hour recovery rule; the 7-day epoch lifetime; relay replay windows. Yet no clock-sync requirement or skew tolerance is stated for clients or CO services. A poster with a slow clock keeps encrypting under the old broadcast key after a removal.
- Suggested fix: Add a short §13.5 "Time". All timestamps are RFC 3339 UTC. Clients and services SHOULD synchronize their clocks (NTP or Roughtime) and MUST tolerate ±N seconds of skew. Each time-bounded check states whether it uses sender time or receiver time. Removal-critical cut-overs, such as a `BroadcastKey` issued for a removal, take effect when received, whatever `notBefore` says.
- Needs decision: no

### GAP-14: No IANA / registry considerations
- Severity: P3
- Location: spec/10-relays.md:43-46, 208-214, 437; spec/11-transport.md:283; spec/13-encoding.md:59-64 (`agoraType` header); spec/09-interop.md:30-36; spec/10-relays.md:176-178; spec/03-spaces.md:33
- Evidence: `GET /.well-known/agora-relay`; `_agora-relay._udp` / `._tcp` SRV; capability `urn:agora:v1`; JWS protected header member `agoraType`; credential `AgoraMIMICredential`; header fields `x-agora-relay-did`, `x-agora-timestamp`, `x-agora-nonce`; URI scheme `agora://`. No grep hit for "IANA" anywhere.
- Problem: Several identifiers need registration or at least a central allocation list:
  - A well-known URI (RFC 8615).
  - DNS-SD service names (RFC 6335).
  - A JMAP capability (RFC 8620 §9.4 registry).
  - A JWS header parameter. `agoraType` is not collision-resistant under RFC 7515 §4.3.
  - An MLS credential type. A MIMI-interop credential needs a codepoint from the IANA MLS Credential Types registry to interoperate at all.
  - HTTP fields (RFC 9110 registry; RFC 6648 deprecates `X-`).
  - A URI scheme (RFC 7595).
  - DID service types (DID Specification Registries).
  - MLS exporter labels. These are scattered across §3.4, §4.6, §5.2, §6.9, §6.13 and only a central list prevents collisions.
  `urn:agora:` itself is treated as registered per decision and is not raised.
- Suggested fix: Add §99 Appendix C "Registries and identifiers". List every allocated identifier (exporter labels, `urn:agora:type:` names, DID service types, well-known URI, SRV names, HTTP fields, JWS header, MLS credential and extension codepoints, JMAP capability, URI scheme), and mark each "IANA registration required" or "Agora-internal, no registration". Rename `x-agora-*` to `Agora-*` and `agoraType` to a collision-resistant name or plan its registration.
- Needs decision: no

### GAP-15: No operational security requirements for CO services
- Severity: P2
- Location: ARCHITECTURE.md:121-125 (S8); spec/12-security.md:101 (relay keys only); spec/03-spaces.md:154, 184; spec/05-messaging.md:65, 73; spec/06-calls.md:211-216
- Evidence: 12-security:101 covers "Relay operator key storage" only. 03-spaces:184: the Space endpoint authenticates members "by DID authentication to the CO", and no such protocol is defined. 04-access-control:147: Welcomes go "by POST to the `KeyPackageEndpoint`". The spec states no authentication or quota for that POST.
- Problem: The CO now runs the security-critical online services:
  - The registration service holds the online billing key and is consulted on every epoch of every channel.
  - The Space endpoint serves state and broadcast keys.
  - The KeyPackage host.
  - The TURN credential service.
  - The compliance logger and recorder.
  - The provisioning service.
  The spec gives none of them key custody, availability, audit-logging or authentication requirements. The Space endpoint's member authentication and the KeyPackage host's Welcome intake are unauthenticated surfaces with no stated DoS controls. The relay, the lower-trust component, gets more operational guidance than the CO services.
- Suggested fix: Add a §12.10 "CO service operations". It should give per-service requirements:
  - Key custody (HSM for the billing, provisioning and recorder archive keys).
  - Authentication. Define the member DID-auth exchange once, for example a JWS challenge signed by a current device key, and reuse it for the Space endpoint, registration service and TURN credentials.
  - Rate limits and quotas, including for Welcome POSTs.
  - Audit logs, retained under CO policy.
  - Availability targets tied to the GAP-2 outage rule.
  - Separation of duties: the billing key is not co-hosted with the Space endpoint.
- Needs decision: no

Coverage: Read in full: ARCHITECTURE.md; spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; decision list (`bd memories agora`). Not reviewed: profiles/, guides/, PROPOSAL.md, PRFAQ.md, README.md (outside this lens's assignment); import/ (frozen).
