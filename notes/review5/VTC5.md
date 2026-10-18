# Review 5: profiles/dtg-openvtc.md against the current spec

Scope: profiles/dtg-openvtc.md in full, against spec at HEAD (149a936), including §5.2.1.5 as changed by 7cd5949, `trustedAttesters` (§3.3, 2c5714d), and profiles/attribute-bridging.md. External OpenVTC and DTG facts were not re-verified.

Checked with no finding: every spec § reference (§2.1, §2.5, §2.6, §4.1, §4.3, §4.5, §4.6.3, §5.2.1, §5.2.1.1, §5.2.1.5, §6, §6.9, §6.14, §9, §12.13, §13.1, §13.1.1, Appendix C) and every ARCHITECTURE reference (§2.3, §2.4, §5) resolves and supports the claim made. Section 3 steps 1 to 3 and section 8 (JCS) match the new §5.2.1.5 wording: the verifier checks the Data Integrity proof by the cryptosuite's rules from the carried bytes. Section 4 (issuerScope rule) binds only what a conforming client puts in its own leaf. It is not a display rule and contradicts nothing in §5.2.1.5. No BCP 14 key words apply to UX. Serial commas are correct. There are no em dashes. Section 6 (VTA placement) restates ARCHITECTURE §2.3 accurately.

Summary: 1 P1, 1 P2, 1 P3. VTC5-2 needs a decision.

### VTC5-1: Space admission accepts a VMC from any issuer; no `trustedAttesters` check

**Severity:** P1

**Location:** Section 5, admission component bullets (lines 70-74); Depends on (line 7)

**Evidence:** "The admission component: MUST verify a presented VMC's proof, expiry, status, and holder binding before acting on it". There is no issuer requirement anywhere in section 5. profiles/attribute-bridging.md §2.4 step 3 says: "The admission service MUST accept it only if its issuer identifier equals a DID listed in the Space's `trustedAttesters` as an exact string, its signature verifies under a key in that DID's document, ...". §2.5 says: "A CO that follows this profile trusts no issuer implicitly". §7 names "an OpenVTC or DTG credential" as a direct issuer "listed in `trustedAttesters` as-is". Spec §3.3 defines `trustedAttesters` as the CO's list of credential issuers for the Space.

**Problem:** As written, a component that conforms to this profile admits on any VMC whose proof, expiry, status, and holder binding check out, including one that the applicant or anyone else issued. Nothing ties the VMC to the trust community the CO meant to rely on. The text relies on the reader assuming "VMC" means "from the right VTC", which is an implicit trust path. It also contradicts attribute-bridging.md, which makes listing in `trustedAttesters` the only way a Space trusts a credential issuer. The profile also never says the CO lists the VTC. Listing it would let members' clients trust the same VMCs carried in leaves of the Space's groups (§3.3, §5.2.1.5).

**Fix:** Add to section 5: "The CO lists the trust community's issuing DID in the Space's `trustedAttesters` (spec §3.3), as profiles/attribute-bridging.md §2.5 and §7 describe for a direct issuer." Make the first admission bullet: "MUST accept a presented VMC only if its issuer equals a DID listed in the Space's `trustedAttesters` as an exact string and its proof verifies under a key in that DID's document, and MUST verify its expiry, status, and holder binding before acting on it, because ...". Optionally add one sentence: with the VTC listed, members' clients in the Space's groups MAY trust its VMCs in leaves (spec §3.3), and in no other group. Add §3.3 to Depends on. Add §4.2 as well if the VTC5-2 fix cites it.

**Needs decision:** No

### VTC5-2: "Admit on a trust community's decision" gives the VTC admission authority outside the attester model

**Severity:** P2

**Location:** Section 1, second bullet (line 19); section 5, lines 63-68 and line 74

**Evidence:** Line 19: "A Space can admit members on a Verifiable Trust Community's decision". Line 63: "A Space's CO can delegate admission to a trust community. The VTC, or an adapter in front of it, acts as a CO admission component". Line 68 gives the second trigger: "the VTC admits the applicant under its own policy and tells the CO". Line 74: sign "with an admin DID of the Space ... held by the CO". profiles/attribute-bridging.md §1 says: "Attesters only inform the CO's decision: the CO alone admits members and assigns roles (S4)". §2.5 says listing an attester "gives it no authority over Space state. A CO that also wants it to admit members or assign roles makes it a delegated admin (spec §4.1)".

**Problem:** Section 5 mixes two trust paths. (a) The VTC informs a CO-run admission service by issuing VMCs. This is the attester path. (b) The VTC runs the admission component, or decides on its own and "tells the CO". This is an admission authority that is not listed, not a delegated admin, and backed by no credential. Under trigger 2, no VMC exists, so none of the section 5 MUSTs, all of which are stated in terms of a "presented VMC", constrains how the applicant's DID is established. Line 74 also leaves custody unclear. If the VTC runs the component and signs invites, it holds the admin key, and the "held by the CO" wording does not hold. attribute-bridging.md resolves this by making such a party a delegated admin under §4.1, and this profile does not.

**Fix:** Option A: drop trigger 2. Reword line 19 and line 63 as "admit members on credentials from a trust community the CO lists (section 5)". State that the admission component is the CO's own, and the VTC only issues VMCs. Option B: keep trigger 2, but state that a VTC that admits under its own policy holds an admin DID of the Space as a delegated admin (spec §4.1), with the scope the CO grants, is a CO component by the key test, and binds `issuedTo` to a DID the applicant proved (MemberAuth, spec §3.5, or a request signed per spec §13.1.1, as in profiles/attribute-bridging.md §2.3). In both options, drop the "held by the CO" custody claim, or limit it to option A.

**Needs decision:** Yes. Mark needs to choose option A (attester only) or option B (VTC as a delegated admin).

### VTC5-3: Section 3 does not say that a shared Space's `trustedAttesters` has no effect on a DM request

**Severity:** P3

**Location:** Section 3, step 4 (line 45)

**Evidence:** "Issuer trust is the client's policy (spec §5.2.1.5). Under this profile that policy names one or more TRQP v2.0 registries". Spec §3.3 says: "The list applies to no other group: not to DM groups, self-groups, or the channels of other Spaces." profiles/attribute-bridging.md §2.5 says the same.

**Problem:** The step is correct. Section 3 was written before `trustedAttesters` existed, so it does not rule out a plausible misreading: if the user and the stranger share a Space that lists the stranger's VTC, a DTG-aware client might count the VMC as trusted in the DM request. The spec forbids that. This profile is the main description of the stranger-DM credential display, so it is the place a client implementer would look for this.

**Fix:** Append to step 4: "A Space's `trustedAttesters` does not apply here, even when the user and the stranger share that Space: a DM group is outside every Space's list (spec §3.3), so only the client's own policy decides." Add §3.3 to Depends on if VTC5-1 has not already added it.

**Needs decision:** No
