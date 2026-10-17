# DOC lens: non-normative documents vs. normative spec

Reviewer lens: guides/ and profiles/ against spec/ and ARCHITECTURE.md. Every
finding below was checked against the exact spec text cited.

### DOC-1: VC revocation is presented as an access-revocation fast path, but MLS membership is the only access control
- Severity: P2
- Location: profiles/o365-employer-did.md:17, :29, :458; profiles/gsuite-employer-did.md:119, :260, :513; ARCHITECTURE.md §6.2; spec/02-identity.md §2.5.5
- Evidence: o365:17 "VC revocation is the organization's mechanism for immediately invalidating access without writing a DID log entry." o365:458 "Any space configured to require VC validation MUST reject the user's next message or MLS epoch participation check. This is the fast path". gsuite:260 "The fast enforcement path is VC revocation". ARCHITECTURE §6.2: "Membership in the MLS group is the only access control."
- Problem: The only place either profile checks the VC is the Enrollment Service at admission (o365 §4.3). After admission nothing in the spec checks a VC per message or per epoch, so revoking a VC revokes no access. The real cut-off is the MLS Remove (o365 Action C, gsuite Phase 1 third bullet). The o365:458 MUST also invents a check that has no spec hook.
- Suggested fix: State that VC revocation blocks future admissions and role-based checks only, and that access ends with the MLS Remove commits. Make Action C/Phase 1 MLS Remove the fast path and drop the o365:458 MUST. Update the table rows at o365:29 and gsuite:513.
- Needs decision: no

### DOC-2: RelayTombstone uses JSON-LD `@context` and a signature embedded in the body
- Severity: P2
- Location: guides/relay-operator.md:2206-2220; spec/13-encoding.md §13.1, §13.1.1
- Evidence: `"@context": "https://agora.protocol/ns/v1", "@type": "RelayTombstone", ... "sig": "base64url(signature by relay signing key)"`. §13.1.1: "A signature is never embedded in the `body` it signs." §13.1: "`sig` ... JWS General JSON Serialization".
- Problem: This is a leftover of the retired JSON-LD design with body signature fields. A peer implementing it as written cannot verify it with the single §13.1.1 procedure.
- Suggested fix: Define it as a typed envelope with `type` `urn:agora:practice:RelayTombstone` (or an operator-owned URI, following profiles/compliance-chain-witness.md:27), `contentType` `application/json`, a body of `relayDID`, `retiredAt`, `reason`, `successor`, and `sig` in the envelope per §13.1.1.
- Needs decision: no

### DOC-3: Universal IdP profile uses one key for both VC issuance and DID-log updates
- Severity: P2
- Location: profiles/universal-idp-did.md:51-53, :644; contrast profiles/gsuite-employer-did.md:150, :457-459
- Evidence: universal:53 `signing_key_path = "/secrets/org-root-ed25519.pem"   # also signs DID log entries (§9)`; universal:644 "The sidecar supports the following backends for both keys" (with one `signing_key_type`/`signing_key_path`). gsuite:150 says the org root key "is separate from the update key of the employee logs (§7), so it confers no authority over any employee's DID log."
- Problem: Reusing the public `did:web` VC-issuer key as the `did:webvh` update key for every employee log lets anyone who obtains the issuer key rewrite every identity. It also contradicts the companion profile it claims to inherit from ("identical to the Google Workspace spec", universal:26).
- Suggested fix: Add separate config entries for `update_key_*` and `provisioning_signing_key_*`, as gsuite §7 does with three KMS keys. Remove the "also signs DID log entries" comment.
- Needs decision: no

### DOC-4: Google Business-tier "step-up" WebAuthn check verifies nothing and is mislabeled as the device-key PoP
- Severity: P2
- Location: profiles/gsuite-employer-did.md:419-423, :427; spec/02-identity.md §2.2; profiles/o365-employer-did.md:555
- Evidence: gsuite:419 "the sidecar issues a 32-byte challenge, requires the user to sign it using their WebAuthn credential (browser path) ... This is the same proof-of-possession check as O365 spec §5.6". o365:555 defines that check as "a valid Ed25519 signature by `devicePublicKey`". spec §2.2: "A WebAuthn credential (passkey) is not a device key".
- Problem: The profile never registers a WebAuthn credential with the sidecar. A WebAuthn assertion therefore can only be checked against a key the client presents in the same request, which proves nothing about the user. And it is not the same check as the device-key PoP. On non-CAA tiers the only real authentication is the Google OAuth token without MFA claims. The profile presents this as step-up MFA.
- Suggested fix: Say plainly that Business tiers have no step-up beyond the Google sign-in policy (enforce 2SV/security keys at the Workspace level) plus the device-key PoP. Alternatively, have the sidecar register a passkey at first enrollment and require it for later registrations. Remove "same proof-of-possession check".
- Needs decision: yes. Options: (a) document that there is no step-up on these tiers and require Workspace-enforced 2SV with security keys; (b) have the sidecar enroll its own passkey per user; (c) require Enterprise Plus for this profile. Recommend (a), since it adds no mechanism.

### DOC-5: Entra step-up depends on `acr`/`amr` values Entra is not documented to emit
- Severity: P2
- Location: profiles/o365-employer-did.md:530, :551-552, :605; :514 of gsuite repeats it
- Evidence: o365:530 "a short-lived Entra ID token with the `acr` claim set to `"mfa"` and the `amr` array including a phishing-resistant method (`"hwk"` for Windows Hello, `"fido"` for FIDO2/WebAuthn)". The doc does not hedge this.
- Problem: As far as I know, Entra v1 tokens carry `acr` "0"/"1", and step-up is expressed through Conditional Access authentication contexts (`acrs` claim). Entra's documented `amr` values (pwd, rsa, otp, fed, wia, mfa, mngd, ngcmfa, wiaormfa, none) do not include "hwk" or "fido". If so, a sidecar built to this text would reject every request or, if the check is loosened, enforce nothing. The purview profile hedges Microsoft behavior with "verify against current Microsoft Graph documentation". This profile does not.
- Suggested fix: Base step-up on a Conditional Access authentication context requiring phishing-resistant authentication strength, checked via `acrs`. Mark the exact claim names "verify against current Entra documentation", as purview-bridge.md:10 does.
- Needs decision: no

### DOC-6: Google CAA custom-scope enforcement and Directory push details are stated as fact and are likely wrong
- Severity: P2
- Location: profiles/gsuite-employer-did.md:417, :448-452, :93, :101
- Evidence: gsuite:448 "Defined as a custom app scope in the GCP project. Name: `AgoraDIDKeyRegistration`." gsuite:417 "Google enforces the hardware key requirement at the OAuth consent step." gsuite:101 notifications "carry the changed resource's ID and state (`exists` or `not_exists`)".
- Problem: As far as I know, Google's OAuth server issues only Google-defined scopes, so a project cannot mint a custom scope that CAA then gates. The Enterprise Plus security control rests on this. `exists`/`not_exists` are Drive/Calendar resource states. Directory API user watch events are add/update/delete/undelete/makeAdmin. The 7-day channel expiration is also unverified.
- Suggested fix: Hedge each item ("verify against current Google documentation") or replace the CAA path with Workspace-level 2SV/security-key enforcement for the enrollment OAuth client. Correct the push-event semantics.
- Needs decision: no

### DOC-7: Records-retention law is stated incorrectly or without a hedge in the regulator and counsel guides
- Severity: P2
- Location: guides/counsel.md:10, :206, :250; guides/regulators.md:248, :253, :258, :301, :375; profiles/purview-bridge.md:620
- Evidence: counsel:206 "FINRA/SEC 17a-4: 2555 days = 7 years; HIPAA: 2190 days = 6 years minimum for most records". regulators:248 "Six-year retention ... for most records; seven years for certain records. Non-erasable, non-alterable storage (WORM)." regulators:375 "Rule 17a-4 requires WORM storage". counsel:10 / regulators:258 "FINRA-registered ... archiving vendor".
- Problem: Under SEC Rule 17a-4(b)(4), business communications are kept 3 years, the first 2 easily accessible. I know of no general 7-year 17a-4 requirement, and "FINRA 17a-4" is not a FINRA rule. The October 2022 17a-4(f) amendments added an audit-trail alternative to WORM. FINRA does not register archiving vendors. The HIPAA 6-year rule (45 CFR 164.316(b)(2)) covers required documentation, not communications generally. These guides are addressed to examiners and counsel, so errors here cost credibility.
- Suggested fix: Replace the fixed figures with "the period your applicable rule requires (for example, 17a-4(b)(4): three years, first two easily accessible); many firms configure longer". Describe WORM as "WORM or the audit-trail alternative (2022 amendments)". Replace "FINRA-registered archiving vendor" with "qualified third-party archiving vendor". Ask counsel to confirm each figure.
- Needs decision: no

### DOC-8: Radio profile sizes the Agora message using the retired sealed-envelope design
- Severity: P3
- Location: profiles/radio-mesh-gateway.md:246; spec/05-messaging.md §5.2.2 "Sealed Envelope"
- Evidence: radio:246 "three Ed25519 signatures, two AEAD tags, `channelToken`, `senderEphemeralKey`, the sender DID, the CID and MLS framing". spec §5.2.2: "The wrapper carries no sender DID, ephemeral key or signature of its own".
- Problem: The profile describes the retired sealed envelope with an inner sender DID and ephemeral key. The current envelope has the `accessSig` plus the MLS signature, the sealed-envelope AEAD plus the MLS AEAD, `channelToken`, `epoch`, `id`, `ts` and `expiryHint`. The conclusion (radios cannot carry Agora) probably still holds, but the figure is wrong.
- Suggested fix: Recompute the estimate from §5.2.2 as it stands and remove `senderEphemeralKey` and "the sender DID". Fix the source note notes/lichen-ironweed.md §2 to match.
- Needs decision: no

### DOC-9: The "non-normative" relay guide and some profiles write RFC 2119 requirements the spec does not have
- Severity: P3
- Location: guides/relay-operator.md:5 vs :20-22 (key-words section), e.g. :1243, :2129, :2278; profiles/o365-employer-did.md:250, :458, :496; profiles/parlance.md:207
- Evidence: relay-operator:5 "Status: Draft, non-normative" but :22 "The key words "MUST" ... are to be interpreted as described in RFC 2119", and :1243 "These alert rules MUST be configured for any production relay", :2129 "A relay MUST NOT be turned off without following this procedure". o365:250 "Agora clients MUST ignore unknown fields in `verificationMethod` entries"; o365:496 "For involuntary terminations, it MUST be 0."
- Problem: Non-normative documents create apparent conformance rules on relays and Agora clients. Where they restate the spec this is harmless. Where they add rules (alerting, decommissioning, client parsing, DID-log grace periods) they read as protocol requirements that no spec section backs.
- Suggested fix: In relay-operator.md, drop the key-words section and lower-case requirements that are not in spec/ or ARCHITECTURE, or tag each one with its spec/ARCHITECTURE source. In o365, either cite the spec rule or reword as "this profile recommends".
- Needs decision: no

### DOC-10: Profiles disagree on the `KeyPackageEndpoint` service `type` string
- Severity: P3
- Location: profiles/o365-employer-did.md:158, :238 (and gsuite/universal by reference) use `"KeyPackageEndpoint"`; profiles/discord-onboarding.md:211 uses `"AgoraKeyPackageEndpoint"`; spec/07-compliance.md:190 (§7.8.2) uses `"AgoraKeyPackageEndpoint"`
- Evidence: o365:158 `"type": "KeyPackageEndpoint"`; discord:211 `"type": "AgoraKeyPackageEndpoint"`.
- Problem: Clients locate the endpoint by service type. Employer-provisioned documents built to o365 would not match the only example the spec gives. The spec itself never states the string normatively.
- Suggested fix: Pick one string, state it normatively in spec §5.2.1.1, and align all profiles.
- Needs decision: yes. Options: (a) `AgoraKeyPackageEndpoint` (matches §7.8.2 and the `AgoraProfile`/`AgoraSpaceEndpoint` naming); (b) `KeyPackageEndpoint`. Recommend (a).

### DOC-11: O365 device-key registration request diverges from spec §2.5.4 and embeds `sig` in the body
- Severity: P3
- Location: profiles/o365-employer-did.md:536-547, :555; spec/02-identity.md §2.5.4 Step 3; spec/13-encoding.md §13.1.1
- Evidence: o365 body has `"devicePublicKey"`, `"proofOfPossession"`, `"sig": { ... }` and calls `sig` "the envelope signature of spec §13.1.1". o365:555 "over the canonical proof payload". spec §2.5.4 uses `deviceEd25519PublicKey`, `deviceX25519PublicKey`, `idpToken`, with `sig` in the envelope.
- Problem: `sig` is shown inside the body it signs, the field names differ from the spec, the X25519 key is missing, and "canonical" refers to a form Agora no longer defines.
- Suggested fix: Show the request as the spec §2.5.4 body inside a typed envelope with envelope `sig`. Define `proofOfPossession` as a JWS per §13.1.1 over a stated byte string, or drop it if the envelope signature covers it.
- Needs decision: no

### DOC-12: Discord browser key generation does not follow the spec §12.6 non-PRF path
- Severity: P3
- Location: profiles/discord-onboarding.md:140, :170; spec/12-security.md §12.6 (lines 82-85)
- Evidence: discord:140 generates with `extractable: true` before the passkey exists. discord:170 "If the authenticator does not support PRF, the app stores a non-extractable device key unwrapped". §12.6: "Where the authenticator does not support PRF, the client generates the key with `extractable: false`".
- Problem: The extractable key from line 140 cannot become non-extractable. In the non-PRF case the profile would store an extractable key, contrary to §12.6.
- Suggested fix: Create the passkey and test PRF first, then generate the key with `extractable: true` (PRF path) or `false` (no PRF), as §12.6 orders it.
- Needs decision: no

### DOC-13: Relay guide drift from §10.2.1/§10.2.5 (DNS TXT owner, minPowDifficulty)
- Severity: P3
- Location: guides/relay-operator.md:1772-1773, :544-548; spec/10-relays.md §10.2.5 Method 3, §10.2.1
- Evidence: relay-operator:1773 `_agora.relay.example.com.  IN  TXT  "did=... manifest=..."`. §10.2.5: "Each SRV record has a TXT record at the same owner name (RFC 6763 §6)" (`_agora-relay._udp.example.com.`). relay-operator:544 `envelope_pow_min_difficulty` is never tied to the manifest member `minPowDifficulty`, unlike the `endpoints.jmapSync` and `observationBudget` mappings.
- Problem: Operators following the guide publish the TXT record where DNS-SD bootstrap will not find it, and cannot tell which config value becomes the manifest's `minPowDifficulty`.
- Suggested fix: Put TXT records at both SRV owner names. Add "Published in the manifest as `minPowDifficulty` (spec §10.2.1)" to the config comment.
- Needs decision: no

### DOC-14: Other third-party claims that are wrong, internally inconsistent, or unhedged
- Severity: P3
- Location / Evidence / Problem:
  - profiles/o365-employer-did.md:723 and profiles/gsuite-employer-did.md:378: "Bitstring Status List ... adds/supports encrypted status entries". W3C Bitstring Status List defines no encrypted entries.
  - profiles/o365-employer-did.md:312: `.../v1.0/<tenant>/verifiableCredentials/createIssuanceRequest`. Microsoft documents the Request Service path without a tenant segment, and the §7 permission list (:667-669) omits the Request Service permission (`VerifiableCredential.Create.All`). Hedge or correct.
  - profiles/universal-idp-did.md:157: `filter=eventType eq "user.lifecycle.*"`. Okta's `eq` takes no wildcard; use `sw "user.lifecycle"`.
  - profiles/universal-idp-did.md:457, :568 say DirSync needs `DS-Replication-Get-Changes`, but :545 passes `ldap.DirSyncObjectSecurity`, the flag that lets an unprivileged account use DirSync. The doc contradicts itself.
  - profiles/universal-idp-did.md:76 (`USER_CREATED`, ...) vs :190 (`USER.CREATE`, ...): PingOne event names differ between the two tables.
  - profiles/gsuite-employer-did.md:514 "Entra Conditional Access (... all tiers)" vs profiles/o365-employer-did.md:682 "Conditional Access ... Entra ID P1".
  - profiles/gsuite-employer-did.md:152 "W3C CCG DID Configuration spec". It is DIF's Well Known DID Configuration (the profile's own `@context` at :160 is identity.foundation).
  - profiles/discord-onboarding.md:496 "CSP headers MUST include `Cache-Control: no-store`". Cache-Control is not a CSP directive.
  - profiles/discord-onboarding.md:128: Discord "explicitly permits" loopback URIs "with a wildcard port". This is unverified; hedge it.
  - guides/relay-operator.md:1676-1678: the HSM table states FIPS levels and price as fact (AWS CloudHSM's current type is FIPS 140-3; Azure Dedicated HSM availability may have changed). Hedge it or date it.
- Suggested fix: Correct the items that are clearly wrong. Mark the rest "verify against current vendor documentation", following purview-bridge.md:10.
- Needs decision: no

### DOC-15: Stale spec version pins and inconsistent lifecycle state names
- Severity: P3
- Location: profiles/discord-onboarding.md:4, profiles/universal-idp-did.md:4, profiles/purview-bridge.md:8 ("Agora Protocol Spec v0.1"); profiles/universal-idp-did.md:32, :42 (`TOMBSTONED`) vs profiles/o365-employer-did.md:115, :129 (`DEACTIVATED`), which gsuite:125 says are "identical"; discord:4 also cites a "`discord2agora` spec v0.1" that is not in the repo
- Evidence: as quoted.
- Problem: The guides say they are aligned to spec 0.2. Three profiles pin 0.1, and the state machine has two names for one state.
- Suggested fix: Change to "the Agora protocol specification (`spec/`, current draft)" as o365/gsuite do. Use `DEACTIVATED` throughout. Either drop the discord2agora reference or mark it external.
- Needs decision: no

## Areas checked with no findings

- Retired designs: no payments, relay KeyPackage store, client DID auth at relays, relay-hosted logger, compliance hold Mechanisms A/B, relay transparency log, or did:web employee identities in any guide or profile. relay-operator.md is consistent with ARCHITECTURE throughout (§2.1, §3.2, §5, §14, §17). The "public append-only transparency log" in compliance-chain-witness.md:71 is an external witness a firm chooses, not the retired relay log. The optional parallel `did:web` document (o365:102) is permitted by spec §2.1. Relay `did:web` (relay-operator:1709) matches spec §10.2.1.
- P2/P3 drift: relay-operator.md matches `PowPolicy` (§10.5.2), JMAP paths under `endpoints.jmapSync` (§11.8.1), the blob endpoint (§10.4.4), `billingSig` (§5.2.2), frame types (§11.4), push jitter/coalescing (§11.7.4) and the 48 h key overlap / 1 h manifest cache (§10.2.6, §10.2.3). Nothing in the docs touches SFrame parameters or InviteRevocation.
- counsel.md and regulators.md match spec §7.2-§7.8.9, §6.12.3, §5.2.3 and ARCHITECTURE §4-§6, apart from DOC-7. `seq` in ComplianceRecord is the inner per-sender seq (spec §5.1.1), not the retired outer seq.
- purview-bridge.md hedges its Microsoft dependencies consistently. Its spec citations (§7.4, §6.12.4, §6.12.6, §4.6, §5.2.2, §3.4) check out.
- parlance.md and radio-mesh-gateway.md cite existing sections correctly (§6.13, §9.2-§9.3, §13.1, §14.x, §5.2.1.4), apart from DOC-8.
- Automated check: every "spec §N" citation in guides/ and profiles/ resolves to an existing heading.

Coverage: read in full: guides/counsel.md, guides/regulators.md, guides/relay-operator.md, profiles/compliance-chain-witness.md, profiles/discord-onboarding.md, profiles/gsuite-employer-did.md, profiles/o365-employer-did.md, profiles/parlance.md, profiles/purview-bridge.md, profiles/radio-mesh-gateway.md, profiles/universal-idp-did.md, ARCHITECTURE.md. Spec sections read in full for verification: §2.1-§2.2, §2.5-§2.5.8, §5.1-§5.2.2, §7.2-§7.8.9, §10.2.1-§10.2.6, §10.4-§10.5.2, §11.4, §11.6, §11.7.4-§11.8.3, §13. The rest of spec/ was consulted by targeted grep (§3.4, §4.3, §4.6, §6.12, §10.3.2, §10.3.4.6, §12.6, §14.1, §14.4.6, §14.5).
