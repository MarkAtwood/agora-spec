# BRIDGE5: Review of profiles/attribute-bridging.md and trustedAttesters additions

Scope: `profiles/attribute-bridging.md` in full; `git diff 33d5565 -- profiles/o365-employer-did.md profiles/gsuite-employer-did.md profiles/universal-idp-did.md`.

Summary: 0 P1, 4 P2, 5 P3. Needing a decision: BRIDGE5-2.

Verified clean: every spec § reference resolves and says what the profile claims (§2.1 Ed25519 device keys, §2.5.4 `idpToken`, §3.3 `trustedAttesters` incl. 32-entry limit, scoping, non-member and guest omission, client policy prevails; §3.5 `MemberAuth`; §4.1 to §4.5; §4.6.3; §5.2.1.5 exact-string subject match and no holder proof required; §12.11 visibility, linkability, and status-list caching; §12.13; §13.1.1). Every internal "section N.N" reference resolves. Cross-profile references resolve (o365 §4.1, §4.3, §4.4, §5.3, §5.4; gsuite §3.2, §4.3, §4.4, §4.7, §5.2; universal §8; dtg-openvtc section 3). No IO sees source data or credentials anywhere in the flows. No em dashes; no serial-comma misses; no BCP 14 key word applies to UX.

---

### BRIDGE5-1: CO's own issuer is still trusted by configuration in the employer profiles

**Severity:** P2

**Location:** `profiles/o365-employer-did.md` §4.1 (line 310, added sentence) and §4.3 item 1 (line 382); `profiles/gsuite-employer-did.md` §5.1 (added sentence after the VC example) and §5.3 (line 397); `profiles/universal-idp-did.md` §1 (line 32, added sentence)

**Evidence:** The added sentences say the CO lists the issuer in `trustedAttesters` "so members' clients may trust the credential". o365 §4.3 item 1 has the Enrollment Service, which MUST verify the VC, check that the "VC issuer DID resolves to the expected org (`did:web:verifiedid.example.com`)". gsuite §5.3 says "the trusted issuer is the org root DID (§3.2)". attribute-bridging §2.5 Listing: "A CO that follows this profile trusts no issuer implicitly, its own CO-run attester included: its admission service accepts credentials only from listed DIDs."

**Problem:** Under the binding model, nothing is trusted implicitly, including the CO's own issuer. The employer profiles still have the CO's own enrollment service trust its issuer by a configured value, which "resolves to the expected org" does not even define as an exact match. The added sentences make listing a client convenience and leave the admission side alone. A deployer following o365 §4.3 and one following attribute-bridging §2.4 will gate admission differently: the first keeps admitting on the issuer after the CO delists it, and the second does not.

**Fix:** In each added sentence, make the list govern admission too: "The CO lists this issuer DID in the Space's `trustedAttesters` (spec §3.3); its enrollment service accepts the credential only from a listed issuer, and members' clients may also trust it (`profiles/attribute-bridging.md` section 2.5)." In o365 §4.3 item 1: "VC issuer DID equals, as an exact string, a DID listed in the Space's `trustedAttesters` (spec §3.3), here `did:web:verifiedid.example.com`." In gsuite §5.3: "the issuer the CO lists is the org root DID (§3.2)."

**Needs decision:** No. The binding model settles it. The o365 §4.3 edit goes beyond the one-sentence additions.

### BRIDGE5-2: The classification of a third-party attester contradicts its own key-test premise

**Severity:** P2

**Location:** §1 paragraph 4 (line 25); §2.5 "Who attests" (line 75)

**Evidence:** Line 25: "an attester must know who the member is, so a CO-run attester is a CO component by the key test (ARCHITECTURE §2.3) and a third-party attester is an outside credential issuer (section 2.5)". ARCHITECTURE §2.3: a component that "must know group membership or sender identity to do its job, is a **CO component**, regardless of operator or hosting location." Line 75: "It is an outside credential issuer, like an IdP." The ARCHITECTURE §2.3 table lists "IdP / DID sidecar, enrollment service" as **CO**.

**Problem:** The premise that the attester must know who the member is, fed into a test that applies "regardless of operator", makes a third-party attester a CO component too. The sentence then exempts it with no stated reason, and the "like an IdP" analogy points at a component ARCHITECTURE classifies as CO. Deployers will diverge on whether a third-party attester must run under CO control or under a processor contract (S8), or whether it falls outside the taxonomy. The separation guarantee itself holds either way: the attester is never an IO.

**Fix:** Option A: treat it as outside the taxonomy, on a correct basis: "The key test classifies components that perform Agora functions for a community. A third-party attester performs none: it holds no Agora signing key, MLS secret, or message plaintext and needs no group membership. It is a credential issuer under spec §5.2.1.5, like an employer or university that issues VCs, and because it holds personal data and knows members' DIDs it can never be an IO." Drop "like an IdP", and in §1 do not derive both classifications from the same premise. Option B: classify it as a CO component that the CO engages under contract, per S8.

**Needs decision:** Yes. Choose A (an external issuer, outside CO and IO) or B (a CO component under contract).

### BRIDGE5-3: "With whatever scope the CO chooses" overstates what a delegated-admin grant can limit

**Severity:** P2

**Location:** §2.5 "Who attests" (line 75)

**Evidence:** "A CO that also wants it to admit members or assign roles makes it a delegated admin (spec §4.1), with whatever scope the CO chooses." Spec §3.3 (line 168): an `admins` entry's `scope` is "a list of channel path patterns". Spec §4.1: admins "can sign Space state mutations within their granted scope, issue invites, execute moderation operations ..., and add or remove members".

**Problem:** Scope limits channel paths, not operations. No grant is limited to invites or to role assignment. An attester made an admin to admit members can also mutate Space state, moderate, and remove members within its paths, and with `["*"]` across the whole Space short of owner-reserved acts. A deployer reading "whatever scope" will think it can grant admission-only authority.

**Fix:** "... makes it a delegated admin (spec §4.1). An admin's scope is a set of channel path patterns (spec §3.3), not a set of operations: within its scope the attester gets every admin power, including Space state mutations, moderation, and removing members. A CO that wants only its decisions keeps admission in its own admission service and lists the attester as an issuer."

**Needs decision:** No.

### BRIDGE5-4: The SAML and TLS client-auth bindings do not meet the section 2.3 MUST

**Severity:** P2

**Location:** §2.3 (line 62); §4 "How it is verified" (line 132); §5 step 1 (line 159)

**Evidence:** §2.3: "the challenge or nonce the source signs MUST be fresh and commit to the member's DID and a session identifier". §4: "SAML has no holder-chosen nonce; the attester binds the assertion to the session through `InResponseTo` and a `RelayState` that commits to the DID and session." §5: the card signs "either directly or as TLS client authentication in a session that then carries the member's §13.1.1-signed request. The challenge is the section 2.3 nonce."

**Problem:** SAML `RelayState` is not signed by the IdP, so the value that commits to the DID is not one "the source signs". The OIDC `nonce` is not holder-chosen either: the relying party chooses it, as it chooses the AuthnRequest `ID` that returns signed in `InResponseTo`. With TLS client authentication, the card signs the handshake transcript, which commits to no DID. The link to the DID rests on the signed request travelling in the same connection, which the request's signature does not bind. Implementers following §4 or §5 as written fail the profile's own MUST, and those who notice will bind in incompatible ways.

**Fix:** §4: "SAML has no `nonce` parameter; the attester sets the AuthnRequest `ID` to the section 2.3 value (as an `xs:ID`, for example `_` followed by its base64url form) and checks that the signed `InResponseTo` in the Response and in `SubjectConfirmationData` equals it. `RelayState` only routes." §5: either drop the TLS variant, or require the member's §13.1.1-signed request to include the connection's TLS exporter value (RFC 9266 `tls-exporter`), so that the DID signature commits to the session the card authenticated.

**Needs decision:** No. Keeping or dropping the TLS variant is an editorial choice within the fix.

### BRIDGE5-5: The Withdrawal paragraph says delisted credentials "stay valid", which contradicts section 2.4

**Severity:** P3

**Location:** §2.5 "Withdrawal" (line 85)

**Evidence:** "Credentials already issued stay valid by their own rules until they expire or the attester revokes them, so a CO that needs faster withdrawal re-verifies its affected members." §2.4 step 3: the admission service MUST accept a credential only if its issuer is listed. Spec §3.3: list-based client trust requires the issuer to be listed.

**Problem:** Once the CO delists the attester, its credentials no longer count for the CO's admission service or for clients that rely on the list. What survives is admissions and roles already granted (spec §12.13) and trust from clients whose own policy names the attester. "Stay valid" reads as if the CO keeps accepting them.

**Fix:** "Delisting stops new admissions on that attester's credentials and stops clients that rely on the list from trusting them; clients whose own policy names the attester still may. Admissions and role assignments already made stand (spec §12.13), so a CO that must undo them re-verifies the affected members and removes or reassigns them by its usual means (spec §4.2, §4.5)."

**Needs decision:** No.

### BRIDGE5-6: "Wallets ship from 24 December 2026" conflicts with section 6.7

**Severity:** P3

**Location:** §6.1 "Rejected", Waiting (line 197); §6.7 (line 247)

**Evidence:** Line 197: "Wallets ship from 24 December 2026, and the attester design works with them on day one." Line 247: "No certified wallet exists yet, and national launches are uneven, with Germany reported for January 2027."

**Problem:** The two statements disagree on availability. One says wallets ship on a fixed date; the other says no certified wallet exists and at least one launch falls after that date.

**Fix:** "Member States must offer wallets from 24 December 2026, though launches are uneven (section 6.7); the attester design works with each wallet as it launches."

**Needs decision:** No.

### BRIDGE5-7: The revocation trigger "when the member leaves" is undefined for a multi-CO attester

**Severity:** P3

**Location:** §2.5 "Revocation" (line 83)

**Evidence:** "MUST revoke the credential when the member leaves, when re-verification fails, ..." §2.5 also says: "One attester can serve every CO that lists it."

**Problem:** "Member" of what? For an employer attester it means the person leaves the organization. For a third-party attester serving several COs, the obvious reading, leaving a Space, would make leaving one Space revoke the credential every other Space relies on. Attesters will implement different triggers under a MUST.

**Fix:** "... when the subject leaves the population the credential's claims describe (for example a leaver event in the source), ..."

**Needs decision:** No.

### BRIDGE5-8: Section 2.7 says BCP 14 words bind only attesters and the admission service, but section 2.5 has a client MAY

**Severity:** P3

**Location:** §2.7 (line 95); §2.5 "How others trust it" (line 87)

**Evidence:** Line 95: "The BCP 14 key words in this profile bind only attesters and the CO's admission service." Line 87: "a client MAY also trust the attesters that Space lists (spec §3.3)".

**Problem:** The client MAY restates spec §3.3, which the preamble's carve-out permits, but §2.7 states the scope without that carve-out, so the two sentences disagree on their face.

**Fix:** Lowercase the restatement, "a client may also trust ... (spec §3.3)", or add to §2.7: "except where a sentence restates the spec, which it cites."

**Needs decision:** No.

### BRIDGE5-9: "Admission service" is never defined and is close to two other spec terms

**Severity:** P3

**Location:** §1 item 4 (line 21); §2.4 (lines 66 to 71); §2.5 Listing (line 77)

**Evidence:** The profile uses "the CO's admission service" throughout without defining it. ARCHITECTURE §2.3 lists an "Admission key registration service" (CO), which holds channel admission keys (§6.2). Spec §4.6.4 defines a DM "admission host" and `agora_admission`.

**Problem:** An implementer can read the profile's admission service as the existing admission-key component, which never sees credentials and must not sign invites. The profile also never says, in key-test terms, why the component that receives credentials is a CO component.

**Fix:** At the first use in §2.4: "the CO's admission service, a CO component that holds an admin key of the Space (spec §4.1) and issues `SpaceInvite`s; it is not the admission key registration service of ARCHITECTURE §6.2 nor a DM admission host (spec §4.6.4)."

**Needs decision:** No.
