# DOC lens: verified findings

Verifier: adversarial pass over notes/review/DOC.md. Each cited location was
reopened. spec/ and ARCHITECTURE.md were grepped for text that already resolves
the finding, and each finding was checked against `bd memories agora`. No finding
attacks a recorded decision. Third-party claims were checked against vendor or
primary legal sources where they were reachable (listed at the end).

### DOC-1: VC revocation is presented as an access-revocation fast path, but MLS membership is the only access control
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/o365-employer-did.md:17, :29, :458, :480; profiles/gsuite-employer-did.md:119, :260, :262-271, :513; ARCHITECTURE.md:191
- Fix: As proposed. ARCHITECTURE.md:191 says "Membership in the MLS group is the only access control." No spec section checks a VC per message or per epoch: `grep -i "verifiable credential|EmployeeCredential"` over spec/ returns nothing. o365:480 (Action C) already says MLS Remove is what stops decryption. Reword o365:17, :29 and gsuite:119, :260 so that VC revocation blocks only future admissions (o365 §4.3), and the Action C / Phase 1 MLS Remove is the access cut-off. Delete the o365:458 MUST. gsuite:513 is a row about speed. Relabel it "admission block speed" rather than an access-revocation row.
- Needs decision: no

### DOC-2: RelayTombstone uses JSON-LD `@context` and a signature embedded in the body
- Verdict: CONFIRMED
- Severity: P2
- Location: guides/relay-operator.md:2206-2220; spec/13-encoding.md:18, :51
- Fix: As proposed. spec/13-encoding.md:51 says "A signature is never embedded in the `body` it signs." Use a typed envelope with an operator- or practice-owned type URI (following compliance-chain-witness.md:26-27), `contentType` `application/json`, the body fields listed in DOC.md, and `sig` in the envelope per §13.1.1. Agora has no JSON-LD (decision agora-d1-envelope).
- Needs decision: no

### DOC-3: Universal IdP profile uses one key for both VC issuance and DID-log updates
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/universal-idp-did.md:49-53, :644-655; contrast profiles/gsuite-employer-did.md:150, :456-458
- Fix: As proposed. universal:53 says `signing_key_path = ... # also signs DID log entries (§9)`, and :644 offers one backend config "for both keys". gsuite:150 says the issuer key "is separate from the update key of the employee logs ... so it confers no authority over any employee's DID log". Add separate `update_key_*` and `provisioning_signing_key_*` entries that mirror gsuite:456-458, and remove the comment.
- Needs decision: no

### DOC-4: Google Business-tier "step-up" WebAuthn check verifies nothing and is mislabeled as the device-key PoP
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/gsuite-employer-did.md:419, :421, :427-428, :514; profiles/o365-employer-did.md:555; spec/02-identity.md:80
- Fix: The gsuite profile never registers a WebAuthn credential (grep for passkey/webauthn finds only :419-428 and :514). An assertion against a key that was never enrolled proves nothing about the user. o365:555 is a device-key signature, not a WebAuthn check, and spec/02-identity.md:80 says "A WebAuthn credential (passkey) is not a device key". Remove "same proof-of-possession check" and pick one of the options below.
- Needs decision: yes. (a) State that Business tiers have no step-up beyond Workspace-enforced 2SV with security keys, plus the device-key signature. (b) The sidecar enrolls its own passkey per user at first registration and requires it for later devices. spec/02-identity.md:80 explicitly sanctions passkeys "to authenticate the user to the identity host", so (b) is spec-consistent. (c) Make the profile Enterprise Plus only. Recommendation: (a), since it adds no mechanism. Choose (b) only if Mark wants step-up independent of Google's sign-in policy.

### DOC-5: Entra step-up depends on `acr`/`amr` values Entra is not documented to emit
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/o365-employer-did.md:530, :551-552, :605 (and gsuite:514, which inherits it)
- Fix: Microsoft's access-token claims reference describes `acr` as "a `0` or `1`, only present in v1.0 tokens". Its `amr` value table lists pwd, rsa, otp, fed, wia, mfa, ngcmfa, wiaormfa and none, with no "hwk" or "fido". Step-up is expressed through `acrs` (Auth Context IDs, "used to trigger a demand for step-up authentication"). Rewrite the check as follows: a Conditional Access authentication context that requires phishing-resistant authentication strength, verified via `acrs`, with the claims-challenge flow (`xms_cc`). Keep the purview-bridge.md style "verify against current Entra documentation" hedge on the exact names.
- Needs decision: no

### DOC-6: Google CAA custom-scope enforcement and Directory push details are stated as fact and are likely wrong
- Verdict: CONFIRMED
- Severity: P2
- Location: profiles/gsuite-employer-did.md:93, :97, :101, :417, :448-451
- Fix: Google's Directory API push guide lists user watch events `add`, `delete`, `makeAdmin`, `undelete` and `update`. The resource state is `sync` or the event name, not `exists`/`not_exists`. The guide gives no 7-day channel maximum: expiration is "the more restrictive" of the requested value and internal limits. Correct :101 accordingly and make :93/:97 renew on the returned `expiration` rather than a fixed 7 days. I found no Google documentation that lets a GCP project define a custom OAuth scope that CAA gates (Google issues only Google-defined API scopes). Replace :417 and :448-451 with Workspace-level 2SV/security-key enforcement for the enrollment OAuth client, or hedge them as "verify against current Google documentation". This ties to DOC-4's decision.
- Needs decision: no

### DOC-7: Records-retention law is stated incorrectly or without a hedge in the regulator and counsel guides
- Verdict: CONFIRMED
- Severity: P2
- Location: guides/counsel.md:10, :206, :250; guides/regulators.md:248, :253, :258, :301, :375; profiles/purview-bridge.md:620
- Fix: The text of 17 CFR 240.17a-4(b) says "not less than three years, the first two years in an easily accessible place", and (b)(4) covers "all communications received and ... sent". The rule contains no seven-year period. Its periods are six years ((a), (c), some of (e)), three years ((b)), and life of the enterprise ((d)). regulators:248 "seven years for certain records" is therefore wrong. Its "six-year ... most records" misattributes 17a-4(a) to communications. 17a-4(f)(2)(i)(A) allows "a complete time-stamped audit trail" as an alternative to (B) "non-rewriteable, non-erasable format", so regulators:375 "requires WORM" is wrong after the 2022 amendments. The hash-chain argument at :375 fits the audit-trail alternative better and should be framed that way. I found no FINRA vendor-registration regime. The 2022 amendments use a "designated third party" or "designated executive officer" (Dechert, ACA summaries). I could not find a source that proves the negative, so hedge rather than assert: replace "FINRA-registered" with "qualified third-party archiving vendor (or the firm's designated third party under 17a-4(f))". Apply the retention-figure fix from DOC.md everywhere, including purview-bridge.md:620's "FINRA 17a-4" label. HIPAA: 45 CFR 164.316(b)(2) applies to required documentation. Hedge counsel:206 and ask counsel to confirm. The MiFID II figure at regulators:301 was not checked.
- Needs decision: no

### DOC-8: Radio profile sizes the Agora message using the retired sealed-envelope design
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/radio-mesh-gateway.md:246; spec/05-messaging.md:220; notes/lichen-ironweed.md §2
- Fix: As proposed. spec/05-messaging.md:220 says "The wrapper carries no sender DID, ephemeral key or signature of its own". Recompute from §5.2.2 as it now stands. Fix the note too, but note edits are out of scope for spec/doc reviewers unless Mark wants it.
- Needs decision: no

### DOC-9: The "non-normative" relay guide and some profiles write RFC 2119 requirements the spec does not have
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: guides/relay-operator.md:5, :22, :1243, :2129, :2278; profiles/o365-employer-did.md:250
- Fix: The relay-guide part stands. :5 "Draft, non-normative" contradicts :22's RFC 2119 clause and the operational MUSTs at :1243 and :2129, which have no spec backing (grep for decommission in spec/ and ARCHITECTURE returns nothing). Drop :22 and lower-case MUSTs not sourced from spec/ARCHITECTURE, or cite their source. Corrections to the original finding: parlance.md:207 contains no requirement, so drop it. The one parlance MUST (:96) restates §6.13 logic. o365:496 (`tombstoneGracePeriodSeconds` MUST be 0) is a rule on the profile's own sidecar configuration, a field that exists only in the profile, so it is legitimate profile normativity. Drop it. o365:458 is covered by DOC-1. o365:250 imposes a rule on Agora clients. Cite DID Core's handling of unknown properties, or reword it as advice.
- Needs decision: no

### DOC-10: Profiles disagree on the `KeyPackageEndpoint` service `type` string
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: profiles/o365-employer-did.md:158, :238; profiles/discord-onboarding.md:211; spec/07-compliance.md:185-190; spec/02-identity.md:302
- Fix: The existing text already settles this. spec/02-identity.md:302 says the provisioning service "MUST add a `KeyPackageEndpoint` service entry (§7.8.2)", and §7.8.2's only example (07-compliance.md:190) uses `"type": "AgoraKeyPackageEndpoint"`. The name also matches the `Agora*` service naming. Change o365:158 and :238 to `AgoraKeyPackageEndpoint`, and add one sentence to spec §2.5.3 or §7.8.2 that states the type string normatively.
- Needs decision: no (the §2.5.3 → §7.8.2 cross-reference fixes the value)

### DOC-11: O365 device-key registration request diverges from spec §2.5.4 and embeds `sig` in the body
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/o365-employer-did.md:532-547, :555; spec/02-identity.md:327-332; spec/13-encoding.md:51
- Fix: As proposed. The spec body uses `deviceEd25519PublicKey`, `deviceX25519PublicKey` and `idpToken` (02-identity.md:327-332). The profile uses `devicePublicKey`, omits X25519, carries the token as a Bearer header, and puts `sig` inside the body. Also align the token placement, or state that the Bearer header substitutes for `idpToken`.
- Needs decision: no

### DOC-12: Discord browser key generation does not follow the spec §12.6 non-PRF path
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/discord-onboarding.md:139-140, :170; spec/12-security.md:82-85
- Fix: As proposed. The key is generated `extractable: true` at :140 before PRF support is known, but the non-PRF path at :170 stores "a non-extractable device key". An extractable CryptoKey cannot be made non-extractable. Reorder so the passkey is created and PRF tested first, then generate with `true` (PRF) or `false` (no PRF). The genesis signing at :136-137 must follow that step.
- Needs decision: no

### DOC-13: Relay guide drift from §10.2.1/§10.2.5 (DNS TXT owner, minPowDifficulty)
- Verdict: CONFIRMED
- Severity: P3
- Location: guides/relay-operator.md:1772-1773, :544-548; spec/10-relays.md:213-217, :106, :683
- Fix: As proposed. spec/10-relays.md:213-214 puts TXT at `_agora-relay._udp` and `_agora-relay._tcp`. The guide puts it at `_agora.relay.example.com.`. Map `envelope_pow_min_difficulty` to manifest `minPowDifficulty` (spec :106, :683).
- Needs decision: no

### DOC-14: Other third-party claims that are wrong, internally inconsistent, or unhedged
- Verdict: CONFIRMED
- Severity: P3
- Location: o365:723, gsuite:378 (Bitstring "encrypted entries"); o365:312, :665-669 (Request Service path and permission); universal:157 (Okta `eq` wildcard); universal:457, :545, :568 (DirSync rights vs `DirSyncObjectSecurity`); universal:76 vs :190 (PingOne names); gsuite:514 vs o365:682 (CA licensing); gsuite:152 vs :160 (DIF, not W3C CCG); discord:496 (Cache-Control is not CSP); discord:128 (Discord wildcard port); relay-operator.md:1676-1678 (HSM FIPS levels and prices)
- Fix: All quoted text is present as cited. These items are clearly wrong or internally inconsistent: universal:76 vs :190, gsuite:514 vs o365:682, gsuite:152 vs :160, discord:496, and universal:457/:568 vs :545. Correct them directly. Hedge the vendor-behavior items (Bitstring, Request Service path, Okta filter, Discord ports, HSM table) with "verify against current vendor documentation" and a date, unless the editor confirms them. I did not re-fetch those vendor pages.
- Needs decision: no

### DOC-15: Stale spec version pins and inconsistent lifecycle state names
- Verdict: CONFIRMED
- Severity: P3
- Location: profiles/discord-onboarding.md:4; profiles/universal-idp-did.md:4, :32, :42; profiles/purview-bridge.md:8; profiles/o365-employer-did.md:115, :129; profiles/gsuite-employer-did.md:125
- Fix: As proposed. guides/counsel.md:6 and regulators.md:6 align to spec 0.2, while three profiles pin v0.1. Universal uses `TOMBSTONED`, while o365 and gsuite use `DEACTIVATED` and gsuite:125 says the two are "identical". `discord2agora` appears only in import/ and notes/, so mark it external or drop it.
- Needs decision: no

## Sources
- Microsoft Learn, Access token claims reference (acr, amr, acrs): https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference
- 17 CFR 240.17a-4 (Cornell LII): https://www.law.cornell.edu/cfr/text/17/240.17a-4
- Google Directory API push notifications: https://developers.google.com/workspace/admin/directory/v1/guides/push
- 2022 17a-4(f) amendments (designated third party): https://www.dechert.com/knowledge/onpoint/2022/11/-sec-adopts-amendments-to-rule-17a-4-electronic-recordkeeping-re.html ; https://www.acaglobal.com/insights/amendments-rule-17a-4-electronic-recordkeeping-requirement/

## Counts
- CONFIRMED: 13 (P2: 7 — DOC-1..7; P3: 6 — DOC-8, 11, 12, 13, 14, 15)
- CONFIRMED-ADJUSTED: 2 (P3: DOC-9, DOC-10)
- REJECTED: 0
- Needs decision: DOC-4
