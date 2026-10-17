# GAP review: verification

Verifier pass over notes/review/GAP.md. For each finding I grepped spec/ and
ARCHITECTURE.md for text that already covers the topic, and checked it against
`bd memories agora`. No finding attacks a recorded decision, so none is
rejected on that ground. Several are narrowed where the spec already covers
part of the topic.

### GAP-1: No way to bring a live group onto a new relay (S5 has no mechanism)
- Verdict: CONFIRMED
- Severity: P1
- Location: ARCHITECTURE.md:106-109; spec/10-relays.md:612-624; spec/05-messaging.md:203; spec/02-identity.md:302; spec/04-access-control.md:151; spec/12-security.md:36
- Fix: As proposed. I found no relay-set, migration or history-import text: "migrat" hits only the managed/SaaS DNS paragraph (10-relays:19), and `relayHints` exists only in public SpaceAds (10-relays:284) and ChannelShareAgreement (08-cross-space:103). More evidence: 04-access-control:151 tells senders to use relays "discoverable from the recipient's DID document relay hints", but 02-identity:302 forbids DID documents from naming relays, so DMs also have no relay-discovery path. ARCHITECTURE §9 already contemplates "A Space that publishes its relay list", so a CO-signed relay set fits the architecture. Registering mid-chain is an extension of Q6's "AccessChainRegistration of first-epoch access keys". Its trust matches the per-epoch `billingSig`, but Mark should confirm it because it changes recorded wording.
- Needs decision: yes. (a) A CO-signed relay set in member-only Space state (plus a group-encrypted per-DM equivalent), together with mid-chain `AccessChainRegistration`; (b) relay hints only in MLS messages; (c) client configuration. Recommend (a), and confirm that the extension to Q6 is acceptable.

### GAP-2: Billing key and registration service have no rotation or compromise procedure
- Verdict: CONFIRMED-ADJUSTED
- Severity: P1
- Location: spec/05-messaging.md:203-205; spec/10-relays.md:588-624; ARCHITECTURE.md:177-183
- Fix: The gap is real. "billing" appears nowhere with rotate, revoke or renew. The compromise impact needs correcting. An `accessKeyAnnouncement` must be signed with the previous epoch's access key (05:203) as well as carry `billingSig`, so a thief holding only the billing key cannot lock out a group. Lockout also needs a colluding current or removed member. The billing key alone gains quota theft and fake chain registration (DoS against the CO's agreement). The stronger P1 driver is routine lifecycle, not compromise. Registrations name an `agreement` id (10-relays:617), and agreements expire at `validUntil` (10-relays:604). Nothing moves registered chains to a renewed agreement or a new billing DID, and registration exists only at epoch 0. So every chain dies at agreement end unless the group is re-created, which contradicts S5. Fix as proposed (a `BillingKeyRotation`/agreement re-bind record plus re-registration under GAP-1), and add an explicit agreement-renewal case. Drop the "maximum tolerated outage" item here: the outage rule at 05:205 is deliberate, and availability belongs with GAP-15.
- Needs decision: no

### GAP-3: Incident response is missing for most key classes
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:12; spec/02-identity.md:117-247, 437; spec/06-calls.md:345; spec/10-relays.md:231
- Fix: Narrow the list. (1) Losing the owner key does not freeze the Space for did:webvh or did:plc owners. Space state is signed by the owner DID's authentication key (03:131), and DID recovery restores it: the recovery key, social recovery, and for employees the org helpdesk path (02:471), which works even after offboarding because the org holds the update key. Losing the key is fatal only for a `did:key` owner. What remains is compromise: a hostile ownership transfer signed by a stolen owner key has no undo, and nothing says how clients treat state signed by a device key that was later revoked. (2) Recovery-key theft is partly handled by §2.4.4 (02:238-245: log ordering, conflict detection, a 24 h admin-review rule). What is missing is rotating a compromised recovery or social key out. (3) Drop the sequencer: a forged stamp is equivocation, which 14-jmap:188 already detects and handles. (4) Drop the push proxy and Space endpoint/TLS bullets. They state no attacker gain, and §3.4 (03:161) already says an endpoint "can withhold state but cannot forge it". Keep the following: logger/recorder key rotation and re-encryption, a manifest `status: "revoked"`, bulk response to a provisioning-key compromise, and owner compromise. Write §12.8 as proposed for those.
- Needs decision: yes, for undoing an owner compromise (not loss). (a) An optional recovery DID or quorum fixed at genesis that can sign a transfer after a delay; (b) guidance that enterprise owners be org service DIDs; (c) re-found the Space. Recommend (b) as guidance plus (a) as optional.

### GAP-4: Space and channel lifecycle undefined beyond "the owner may transfer or delete"
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/04-access-control.md:12; spec/03-spaces.md:49, 51-128, 131; spec/08-cross-space.md:22
- Fix: As proposed. Grep confirms there is no deletion record, no archival state, no rename text and no genesis contents. Two additions. `channelCID` is used as the exporter context for the token, access key and sealing key (05:194, 202, 218), but no text defines what it hashes, so channel rename and move are undefined at the crypto layer too. Space state has no admin list or role-assignment field, though 03:131 makes "an admin authorized under the prior state" the S4 validation rule. The §3.5 fix must add both fields (`admins` and member-to-role assignments).
- Needs decision: no

### GAP-5: Member exit flows are missing (leave Space, leave channel or DM, delete account)
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/07-compliance.md:231; spec/02-identity.md:426; spec/04-access-control.md:20, 88-96; spec/14-jmap.md:61
- Fix: As proposed. Self-Remove is mentioned only at 07:231 and 02:426, and neither text says who commits it. The spec has no Space-leave operation and no account deactivation ("deactivat" hits only 02:254, which is about the org's revocation authority). The missing member list is the same missing field as in GAP-4, so fix them together.
- Needs decision: no

### GAP-6: Abuse and spam handling stops at relay rate limits
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/10-relays.md:59, 665-683; spec/12-security.md:54-64; spec/04-access-control.md:62, 147, 157-161; spec/99-appendices.md:38 (the original cited :315; the file has 44 lines)
- Fix: The core gap is confirmed: there is no report type, no invitee-side DM consent, no CO-to-IO chain deregistration and no takedown handling. Grep for report, takedown and frank finds nothing relevant. Correct one claim: KeyPackage draining is already addressed. "The host rate-limits fetches to prevent a caller from draining a user's supply" (05:73, also 02:381). Unsolicited DM adds remain open. On fix item (1): Agora has no message franking, so the claim that an MLS-signature-based `AbuseReport` would be third-party verifiable needs the same external crypto review as Q1. State it as such, or drop "verifiable". `ChainDeregistration` fits S7 and Q6.
- Needs decision: yes, for invitee DM consent. (a) A client-side message-request state; (b) plus KeyPackage-host gating; (c) nothing. Recommend (a) as MUST and (b) as MAY.

### GAP-7: Limits and quotas are scattered, partly local policy, and lack floors
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/05-messaging.md:40, 90, 572; spec/11-transport.md:112, 303-304; spec/12-security.md:61; spec/10-relays.md:540; spec/02-identity.md:346
- Fix: Confirmed. 11:112 says "Limit values are local Relay policy" and sets no floor. Presence is re-sent every 30 s on each channel topic (05:559, 572), and nothing caps DM size, state size or body length. Correct one example: Welcomes never go to relays (05:51; they are POSTed to the `KeyPackageEndpoint`), so the 64 KiB envelope limit does not apply to a 500-leaf Welcome. The real size risk on relays is a Commit that batches many Adds, since each carries a KeyPackage. The fix is otherwise as proposed.
- Needs decision: no

### GAP-8: A user's devices have no way to sync private data or history
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/14-jmap.md:59, 81, 115; spec/02-identity.md:84-86, 208-232; spec/05-messaging.md:107
- Fix: Partly covered. §14.3.1 (14:81) allows "a personal daemon run by or for that member" serving the member's own devices. Where one is used, it is the sync point for `ReadPosition` and `ChatContact`. The gap remains for daemon-less clients. A related gap the finding misses: no procedure says who adds a newly enrolled device's leaf to every group the user is in. Enrollment ends at the KeyPackage upload (02:381), and 02:229 only says "having an existing device add it". For DMs, it is also unstated whether the §4.6.1 consent threshold applies to a member's own new device. The backup-fork risk is real and unaddressed. 02:220 exports "Current MLS key material for all group memberships", and nothing forbids using it alongside the source device. Fix as proposed, and add the new-device group-join duty (the user's existing devices commit Adds for their own new device, exempt from DM consent).
- Needs decision: yes. (a) A self-group plus optional history transfer; (b) a self-group only; (c) leave sync to the personal daemon and history to backups. Recommend (a). Option (c) is now viable given §14.3.1 but leaves daemon-less clients without sync.

### GAP-9: No privacy considerations section; CO-side observation and data-subject rights unaddressed
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/12-security.md:38-52; spec/05-messaging.md:204; spec/04-access-control.md:121, 147; spec/02-identity.md:326-360, 437
- Fix: Confirmed. There is no hit for erasure, GDPR or data subject, and §12.4 covers only IO observation. `deviceLabel: "Alice's MacBook Pro"` and `platform` are written into the public DID document (02:359-360). Narrow one part: legal hold and archive disposal are CO policy by design ("under its own retention and legal-hold controls", ARCHITECTURE:136), so the spec should state that they are out of protocol scope, not define them. Keep the per-CO-component observation tables, the minimization guidance and the erasure model (which records can be deleted, which cannot, and crypto-shredding).
- Needs decision: no

### GAP-10: No conformance classes beyond the relay, and no must-understand extensions
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/10-relays.md:520-564; spec/07-compliance.md:54, 165, 281-300; spec/13-encoding.md:102; spec/01-overview.md:23
- Fix: The missing conformance classes are confirmed: "conformant client" is used at 07:54, 07:165 and 05:461 but never defined. The must-understand half is partly covered already. Documents with an unsupported `schemaVersion` MUST be rejected (01:23, 13:112), and 14-jmap:49 already makes an unsupported consistency model read-only. So a new enforcement-relevant field can be forced on old clients by bumping `schemaVersion`. A simpler fix than a new `requiredExtensions` array is a rule that any Space-state field which a CO enforcement point (ARCHITECTURE §6.3) depends on requires a `schemaVersion` bump. Either works. Prefer the existing mechanism unless finer granularity is wanted.
- Needs decision: no

### GAP-11: Required disclosures have no accessibility or language requirements
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/06-calls.md:293-308; spec/07-compliance.md:120-126, 227-229; spec/05-messaging.md:163
- Fix: Confirmed: there is no hit for accessibility, audible or localize. The "accessible" at 07:126 means reachable from the info panel. Lowered to P3. The disclosures are already required as text system messages (06:293), which assistive technology reads, and the CO writes the disclosure strings in whatever language it chooses. The real residual gaps are audio-only and headless devices in calls, and icon-only indicators (05:163). Fix: require a programmatic text equivalent for every mandated indicator, an audible notice before media for recording disclosures on devices without a display, and optional BCP 47 language maps for the disclosure strings. This does not touch the recording-consent decision.
- Needs decision: no

### GAP-12: Internationalization unaddressed for human-visible identifiers
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/03-spaces.md:30-45; spec/04-access-control.md:41; spec/05-messaging.md:529; spec/10-relays.md:380
- Fix: As proposed. Grep finds no NFC, PRECIS, confusable or bidi text. The only normalization statement covers type URIs (13:29). Path-glob matching for `channelAccess` depends on normalization, so that part is a correctness issue, not cosmetic.
- Needs decision: no

### GAP-13: No statement of time and clock assumptions
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:131; spec/04-access-control.md:107; spec/10-relays.md:181; spec/12-security.md:14; spec/14-jmap.md:101, 319
- Fix: As proposed. Grep finds no skew, NTP or Roughtime. The only clock rules are the relay-to-relay 300 s window (10:181) and the sender-clock caveat for last-writer-wins (14:319). The broadcast-removal example holds: a removal-driven key cut-over depends on the poster's clock.
- Needs decision: no

### GAP-14: No IANA / registry considerations
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/10-relays.md:46, 176-178, 208-214; spec/11-transport.md:303; spec/13-encoding.md:64; spec/09-interop.md:30-36; spec/03-spaces.md:33
- Fix: As proposed. There is no hit for "IANA". 13:100 says "No registry is needed", but that covers type URIs only. One strengthening: RFC 9420 §17 defines IANA registries for MLS Credential Types and MLS Exporter Labels, so `AgoraMIMICredential` and the exporter labels ("agora access", "agora channel token", "agora sealed envelope", "agora blob", "agora-dm-token", and others) each need a registry entry, not only a central list. `urn:agora:` stays excluded per decision.
- Needs decision: no

### GAP-15: No operational security requirements for CO services
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/03-spaces.md:154, 184; spec/05-messaging.md:65, 204; spec/04-access-control.md:147; spec/12-security.md:101
- Fix: Confirmed. §12.6 gives key-custody guidance for relays (12:101) and nothing for CO services. The most concrete gap is that member DID authentication is named twice and defined nowhere: "by DID authentication to the CO" (03:184), and "a DID it authenticates as a current member" for the registration service (05:204). Clients and CO services come from different implementers, so this is an interoperability gap, not just ops guidance. Define one challenge-response exchange, as proposed. Billing-key custody and registration-service availability overlap with GAP-2, so handle them here and drop them from GAP-2's fix. The fix is otherwise as proposed.
- Needs decision: no

## Counts

- CONFIRMED: 6 (GAP-1, 4, 5, 12, 13, 14)
- CONFIRMED-ADJUSTED: 9 (GAP-2, 3, 6, 7, 8, 9, 10, 11, 15)
- REJECTED: 0
- Severity after adjustment: P1 2 (GAP-1, 2); P2 9 (GAP-3, 4, 5, 6, 7, 8, 9, 10, 15); P3 4 (GAP-11, 12, 13, 14)
- Needs decision: GAP-1, GAP-3, GAP-6, GAP-8
