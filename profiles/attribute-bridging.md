# Profile: Attribute Bridging

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-17
**Version:** 0.1 Draft
**Depends on:** ARCHITECTURE §2.2, §2.3, §2.4, §3 (S1, S4, S5, S6, S7, S8, S9); spec §2.1, §2.5.4, §2.6, §3.3, §3.5, §4.1, §4.2, §4.3, §4.4, §4.5, §4.6.3, §5.2.1, §5.2.1.5, §12.11, §12.13, §13.1.1
**Sources:** Directories and IdPs: `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`, `profiles/universal-idp-did.md`; OpenID Connect Core 1.0 (https://openid.net/specs/openid-connect-core-1_0.html); SAML 2.0 (OASIS); NIST SP 800-63-4, Digital Identity Guidelines (https://pages.nist.gov/800-63-4/). CAC and PIV: FIPS 201-3, Personal Identity Verification (PIV) of Federal Employees and Contractors, January 2022 (https://csrc.nist.gov/pubs/fips/201-3/final); NIST SP 800-73-5 Part 1, Interfaces for Personal Identity Verification, July 2024 (https://csrc.nist.gov/pubs/sp/800/73/pt1/5/final); NIST SP 800-157, Guidelines for Derived PIV Credentials, December 2014, and SP 800-157 Rev. 1 Final Public Draft, 14 November 2024 (https://csrc.nist.gov/pubs/sp/800/157/r1/fpd); Federal PKI (https://www.idmanagement.gov/university/fpki/, https://www.idmanagement.gov/implement/announcements/FBCAG5/). EU Digital Identity Wallet: Regulation (EU) 2024/1183 (eIDAS 2.0, CELEX 32024R1183, http://data.europa.eu/eli/reg/2024/1183/oj); Implementing Regulations (EU) 2024/2977, 2024/2979, 2024/2982, 2025/848, and 2026/1731; EUDI Wallet Architecture and Reference Framework (ARF) v3.0.0, 23 July 2026 (https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework, https://eudi.dev/latest/main/); PID rulebook v1.7, 17 July 2026 (https://github.com/eu-digital-identity-wallet/eudi-doc-attestation-rulebooks-catalog); OpenID for Verifiable Presentations 1.0, Final, 9 July 2025 (https://openid.net/specs/openid-4-verifiable-presentations-1_0.html); OpenID for Verifiable Credential Issuance 1.0, Final, 16 September 2025 (https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html); OpenID4VC High Assurance Interoperability Profile (HAIP) 1.0, Final, 24 December 2025 (https://openid.net/specs/openid4vc-high-assurance-interoperability-profile-1_0.html); SD-JWT, RFC 9901; SD-JWT VC, draft-ietf-oauth-sd-jwt-vc-19 (https://datatracker.ietf.org/doc/draft-ietf-oauth-sd-jwt-vc/); European Business Wallet proposal COM(2025) 838, procedure 2025/0358(COD) (https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0358(COD)). EUDI research and full citations: `notes/eudi-wallet.md`.

---

## 1. Summary

Organizations already hold authoritative facts about their people: a directory knows who is an employee and in which department, an IdP knows how well a person was identity-proofed, a government smartcard proves federal affiliation, and an EU wallet carries a verified legal identity. This profile describes one pattern for bringing such facts into Agora without exposing them.

The pattern has one flow, built from existing Agora mechanisms:

1. An **attester** reads an authoritative source it is entitled to read and verifies what it reads.
2. The attester issues the member a credential with **derived claims**, with the member's Agora DID as subject and the attester's own issuing DID as issuer, that the member carries in `agora_credentials` (spec §5.2.1.5).
3. The CO lists the attester's issuing DID in the Space state member `trustedAttesters` (spec §3.3).
4. The CO's admission service admits the member with a `SpaceInvite` (spec §4.3), and may assign a role (spec §4.2), on credentials from a listed attester.

Nothing is trusted implicitly, including the CO's own issuing DID. A CO that wants to verify a source itself runs its own attester and lists it like any other; for directories and IdPs this CO-run attester is the common case. A third-party attester, such as an identity-proofing service, works the same way. Attesters only inform the CO's decision: the CO alone admits members and assigns roles (S4).

Raw source identifiers and attributes, such as a DoD EDIPI, PID attributes, a manager's name, or an employee number, stay at the attester. The CO holds them only when it runs its own attester. Other members see only the derived claims the member chooses to carry. No infrastructure operator (IO) takes part or learns anything: an attester must know who the member is, so a CO-run attester is a CO component by the key test (ARCHITECTURE §2.3) and a third-party attester is an outside credential issuer (section 2.5), and source verification runs outside relays (S1, S6).

This profile needs no Agora core change. Sections 3 to 6 apply the pattern to four kinds of source:

| Source | Section | What exists in Agora today |
|---|---|---|
| Directories (Active Directory, Entra ID, Google Workspace, LDAP) | 3 | `EmployeeCredential` and JML lifecycle in the employer profiles |
| Identity providers (OIDC, SAML) | 4 | `idpToken` at device registration (spec §2.5.4) |
| CAC and PIV smartcards | 5 | Nothing specific; usually reached through an IdP (section 4) |
| EU Digital Identity Wallet | 6 | Nothing specific; this profile defines the relying-party flow |

Section 7 covers other wallets and issuers.

## 2. Common Rules

These rules apply to every source in sections 3 to 6.

### 2.1 Data Minimization

The attester reads only the attributes its issuing policy uses, and asks for a claim rather than the record behind it where the source allows. An attester that follows this profile MUST NOT put raw source identifiers or personal attributes in a credential meant for `agora_credentials` unless the member asks for them. Raw identifiers include an EDIPI, FASC-N, card UUID, employee number, directory object ID, IdP subject identifier, and PID personal administrative number. Personal attributes include legal name, birth date, home address, and manager. Every member of every group carrying the leaf would see them (spec §12.11).

A client should not put a source credential itself, such as a PID presentation, an IdP token, or a PIV certificate, in `agora_credentials`. None of them names the member's Agora DID as subject, so none counts under spec §5.2.1.5, and each would show its raw attributes to the whole group.

### 2.2 Derived Claims

A derived claim states a conclusion the attester reached, not the data it reached it from. Guidance for attesters choosing claim names:

- **Boolean or enumerated, not free text.** `employment_status: "active"`, `affiliation: "contractor"`, `verified_natural_person: true`.
- **Bands, not values.** `age_over_18: true`, not a birth date; `tenure_band: "5y+"`, not a hire date.
- **Coarse, not precise.** A country of residence, not an address; a business unit, not a cost center, where the attester judges the unit coarse enough to show outsiders.
- **Assurance as its own claim.** `identity_assurance: "IAL2"` with the date the attester verified it (section 4).
- **One claim per decision.** Put only what a group's policy, or a stranger deciding whether to accept a DM (spec §4.6.3), would use.

SD-JWT VC (`application/dc+sd-jwt`) is the preferred format, because the member can disclose only the claims a given group's policy uses (spec §12.11). Any format spec §5.2.1.5 names works. No shared claim vocabulary exists (section 9).

### 2.3 Binding at Verification

Where the source supports a holder proof, the attester MUST bind it to the member's Agora DID and to this session: the challenge or nonce the source signs MUST be fresh and commit to the member's DID and a session identifier, for example a hash over a random value, the DID, and the session identifier. The member proves the DID itself with `MemberAuth` (spec §3.5) or a request signed per spec §13.1.1. This ties the source result to one DID and one attempt, and defeats relaying a QR code or challenge to someone else. Sections 4 to 6 say what the nonce is for each source.

### 2.4 Admission Flow

1. **Request.** The applicant's client proves its Agora DID (section 2.3) to an attester that the admission service names from the Space's `trustedAttesters`, since the non-member view omits the list (spec §3.3, §4.4), and asks the CO's admission service for a `SpaceInvite`, proving the same DID.
2. **Attester verification.** The attester reads and verifies the source as sections 3 to 6 describe, binding the result per section 2.3, and issues a credential with derived claims to that DID (section 2.5). On failure it issues nothing.
3. **Outcome.** The client presents the credential to the admission service. The admission service MUST accept it only if its issuer identifier equals a DID listed in the Space's `trustedAttesters` as an exact string, its signature verifies under a key in that DID's document, it is unexpired and unrevoked by the rules of its format, and its subject equals the DID proved in step 1 (spec §5.2.1.5). If the credential satisfies the Space's admission policy, the admission service issues the `SpaceInvite`, which MUST have `issuedTo` set to the DID proved in step 1 and be signed per spec §13.1.1 by an admin DID of the Space (spec §4.1, §4.3), and MAY name a role (spec §4.2). Otherwise it issues nothing.
4. **Records.** The attester records the verification event: the DID, the purpose, the source and credential type, the result, and the time. It keeps disclosed attributes only as long as its stated purpose and retention policy allow. The attester records verifications and the admission service records admissions, not group membership; MLS remains the source of truth for who is in a group (S9).

The invite and any role assignment are ordinary CO-signed records (S4); an attester's credential informs the CO's decision and grants nothing by itself. S7 already bars an IO from requiring source verification as a condition of service, and changing IOs touches neither an attester's source access nor the credentials it issued (S5).

### 2.5 Attester Credentials

**Who attests.** An attester is any party that verifies a source and issues derived claims to members' Agora DIDs under its own issuing DID. A CO that verifies a source itself runs a CO-run attester: a component with its own issuing DID, distinct from any IO key (ARCHITECTURE §2.4), and preferably separate from the component that holds Space policy. A CO-run attester is a CO component by the key test (ARCHITECTURE §2.3), and the raw attributes it holds stay under CO control (S8). A third-party attester is a separate party with its own DID, for example an identity-verification firm, a public body that runs an attestation service, or an organization's identity office serving several of its COs. It holds personal data in plaintext, so it can never be an IO, and it holds no Agora keys or Space policy, so it is not a CO. It is an outside credential issuer, like an IdP. One attester can serve every CO that lists it.

**Listing.** The CO lists each attester's issuing DID in the Space's `trustedAttesters`, at most 32 DIDs (spec §3.3). A CO that follows this profile trusts no issuer implicitly, its own CO-run attester included: its admission service accepts credentials only from listed DIDs (section 2.4).

**Subject and issuer.** The subject is the member's Agora DID (spec §2.1), in `sub` of an SD-JWT VC or `credentialSubject.id` of a W3C VC, as an exact string (spec §5.2.1.5). The issuer is the attester's issuing DID.

**Validity tied to re-verification.** The credential's validity matches the attester's re-verification policy for its source and never outlasts it. A directory-backed credential can be re-issued on each JML event and yearly, as the employer profiles already do; a credential derived from a one-time wallet or card check expires when the attester would next re-check.

**Revocation.** The attester publishes status in a status list and MUST revoke the credential when the member leaves, when re-verification fails, or when the source changes in a way that falsifies a claim, for example a mover event, a revoked PIV certificate, or a revoked PID to the attester's knowledge. The employer profiles' leaver and mover workflows are the model (`profiles/o365-employer-did.md` §5.3 and §5.4, `profiles/gsuite-employer-did.md` §4.3 and §4.4). Revoking a source credential or attester credential does not remove anyone: MLS membership is the only access control, so the CO removes the member by its usual means (spec §4.5, §12.13).

**Withdrawal.** If the CO stops trusting an attester, it removes the DID from `trustedAttesters` and from its admission policy. Credentials already issued stay valid by their own rules until they expire or the attester revokes them, so a CO that needs faster withdrawal re-verifies its affected members.

**How others trust it.** Issuer trust is the verifying client's policy (spec §5.2.1.5, §12.13). In the groups of a Space, a client MAY also trust the attesters that Space lists (spec §3.3), so members' clients can trust an attester's credential carried in a leaf with no CO re-issuance. The list is a recommendation: a client's own policy prevails, both to add issuers and to exclude them, and the list applies to no group outside the Space, such as a DM group, a self-group, or another Space's channel. A client's own policy can name an issuer DID directly, or ask a TRQP v2.0 trust registry whether the issuer is authorized for that credential type, as `profiles/dtg-openvtc.md` section 3 describes. The trust is in the attester, not in the source: an attester credential derived from a PIV card is not a PIV credential, and one derived from a PID is not a qualified attestation. Deployments should say so plainly to users.

### 2.6 Enterprise and Government Visibility (Deployment Guidance)

An enterprise or government CO may see its members' verified attributes within its own Space: those its CO-run attester, if it runs one, read from the source, and the attester-credential claims in the leaves of groups it is a member of (spec §12.11). Under GDPR purpose limitation, and comparable rules elsewhere, it uses them only for the purposes it told members about and, for EUDI, the intended uses its attester registered (section 6.3).

### 2.7 Scope of Requirements

The BCP 14 key words in this profile bind only attesters and the CO's admission service. Nothing here constrains how a client displays credentials or prompts its user.

## 3. Directories

Active Directory, Entra ID, Google Workspace, and other LDAP directories.

**What exists.** The employer profiles already read the directory, run the JML lifecycle, and issue an `EmployeeCredential` to the employee's Agora DID: `profiles/o365-employer-did.md` §4 and §5, `profiles/gsuite-employer-did.md` §4 and §5, and `profiles/universal-idp-did.md` (SCIM, HR systems, and on-premises AD). Role derivation from groups is in `profiles/gsuite-employer-did.md` §4.7 and the `agoraRoles` claim. This section adds only the mapping from directory attributes to derived claims.

**Who attests.** Usually a CO-run attester, because the directory is the CO's own system of record. In the employer profiles it is the sidecar's `EmployeeCredential` issuer: the Verified ID authority's DID (`profiles/o365-employer-did.md` §4.1), or the org root DID (`profiles/gsuite-employer-did.md` §3.2, `profiles/universal-idp-did.md`). The CO lists that DID in `trustedAttesters` (section 2.5).

**What is read.** User object attributes the attester's service account may read: account enabled state, group membership, department, job title, manager, employee type, employee number, and custom attributes (Entra extension attributes, Google Workspace custom schemas, AD `extensionAttribute*`).

**How it is verified.** The attester reads the directory over its authenticated API (Microsoft Graph, Google Directory API, LDAP over TLS). The link from directory record to Agora DID is the immutable user ID matched at enrollment, never email or UPN (`profiles/universal-idp-did.md` §8).

**Example mapping.**

| Directory attribute | Derived claim |
|---|---|
| account enabled, not in leaver state | `employment_status: "active"` |
| `employeeType` | `affiliation: "employee"`, `"contractor"`, or `"intern"` |
| group membership | `agoraRoles` (existing), or a named team the CO chooses to disclose |
| has direct reports | `people_manager: true`, never the manager's or reports' names |
| `department` | business unit, where the CO judges it safe to show outsiders |
| `employeeId`, `objectGUID`, manager | none; stays at the attester |

**Caveats.** The `EmployeeCredential` examples in the employer profiles carry raw attributes (`employeeId`, `displayName`, `officeLocation`). That suits presentation to the CO's own enrollment service (`profiles/o365-employer-did.md` §4.3). For `agora_credentials` in groups shared with outsiders, which `profiles/o365-employer-did.md` §4.4 already flags, an attester that follows this profile issues either a separate credential with derived claims only, or an SD-JWT VC from which the client discloses only the derived claims.

## 4. Identity Providers

OIDC and SAML 2.0 IdPs: enterprise IdPs such as Okta and Ping Identity, and identity-proofing services such as Login.gov and ID.me.

**What exists.** Device key registration already carries a signed IdP token: the client authenticates to the organization's IdP and sends the OIDC ID token, an access token, or the SAML assertion as `idpToken` (spec §2.5.4). The provisioning service links it to the user record by the IdP's immutable ID (`profiles/universal-idp-did.md` §8). This section adds reading assurance and other claims from that token, and using an identity-proofing IdP for admission to a Space whose CO is not the member's employer.

**Who attests.** For an enterprise IdP, usually a CO-run attester, such as the employer sidecar's credential issuer (section 3). For an identity-proofing IdP, either a CO-run attester or a third-party proofing service that serves several COs. Either way the CO lists the attester's DID in `trustedAttesters` (section 2.5).

**What is read.** The signed ID token or assertion at enrollment or admission: issuer, subject, authentication time, the authentication context (OIDC `acr` and `amr`, SAML `AuthnContextClassRef`), and any verified attributes the attester's client registration is permitted to receive.

**How it is verified.** The attester is the OIDC relying party or SAML service provider. It checks the signature against the IdP's published keys or metadata, `iss`, `aud`, expiry, and, for OIDC, sets the authorization request's `nonce` per section 2.3. SAML has no holder-chosen nonce; the attester binds the assertion to the session through `InResponseTo` and a `RelayState` that commits to the DID and session.

**Example derived claims.**

- `identity_assurance: "IAL2"`, with the verification date. NIST SP 800-63-4 defines identity assurance levels (IAL) for proofing and authenticator assurance levels (AAL) for each authentication. IAL describes the person and can be carried forward; AAL describes one sign-in, so an attester derives at most "verified at AAL3 at enrollment", not a lasting AAL.
- `verified_natural_person: true`, `country_of_residence`, or `age_over_18`, where the IdP releases a verified attribute that supports it.
- From an enterprise IdP, the same claims as section 3.

**Caveats.**

- How each IdP signals assurance is provider-defined. Login.gov and ID.me signal proofing level through `acr` values or provider-specific claims; exact values are **unverified** here and the attester reads its provider's documentation.
- Login.gov serves government agency partners, so only a government CO, through its own attester, can use it directly.
- IdP tokens are short-lived bearer tokens with the IdP's subject identifier, not the Agora DID. They are evidence for the attester, never something a member carries (section 2.1).
- Many CAC and PIV deployments reach the card through an IdP that supports certificate-based authentication; for them, section 5 reduces to this section with the `amr` showing hardware PKI.

## 5. CAC and PIV Smartcards

US federal Personal Identity Verification (PIV) cards under FIPS 201-3, and the DoD Common Access Card (CAC), which is PIV-compatible.

**What exists.** Nothing CAC- or PIV-specific. The simplest deployment fronts the card with an IdP and follows section 4. This section covers an attester that reads the card directly.

**Who attests.** Usually a CO-run attester, such as an agency's own card verifier. A third-party proofing service that checks CAC or PIV cards for several COs also works. Either way the CO lists the attester's DID in `trustedAttesters` (section 2.5).

**What is read.** The PIV Authentication certificate (key reference 9A) from the card through the SP 800-73-5 card interface. Its subject alternative name carries the FASC-N (`pivFASC-N`) and the card UUID as a `urn:uuid:` URI; FIPS 201-3 requires both (§4.2.2.1). On a CAC the subject CN and a UPN carry the DoD ID number (EDIPI) **[secondary: vendor integration guides; no current DoD primary source found]**.

**How it is verified.**

1. **Proof of possession.** The client has the card sign an attester challenge with the PIV Authentication key, either directly or as TLS client authentication in a session that then carries the member's §13.1.1-signed request. The challenge is the section 2.3 nonce. The PIV Authentication key works only after cardholder activation by PIN, and only over the contact interface (FIPS 201-3 §4.2.2.1). The Card Authentication key (9E) works without a PIN and gives far less assurance; the attester MUST NOT accept it for this purpose.
2. **Path validation.** The attester validates the certificate to a configured trust anchor: the DoD PKI roots (DoD Root CA 3 to 6) for CAC, or the Federal Common Policy CA G2 for civilian PIV. DoD PKI connects to the Federal PKI through the Federal Bridge, not by direct cross-certification with Common Policy; the bridge is migrating to FBCA G5 during 2026. It checks the PIV Authentication certificate policy OID.
3. **Revocation.** The attester checks status by OCSP or CRL at verification time; FIPS 201-3 requires issuers to provide both (§5.3, §5.5).

**Example derived claims.**

- `us_federal_piv: true`, with the verification date.
- Agency or component, from the issuing CA and the subject DN.
- `identity_assurance: "IAL3"`: FIPS 201-3 §6.1 states PIV issuance meets IAL3. Authentication with the PIV Authentication key is AAL3 and with the Card Authentication key AAL1 (FIPS 201-3 Table 6-2), which is one more reason step 1 refuses the latter.
- Affiliation (employee, contractor, military), with care: see caveats.

The FASC-N, card UUID, and EDIPI stay at the attester (section 2.1). The attester keys its record on them so it can match re-verifications and revocations.

**Caveats.**

- **Affiliation is not reliably in the certificate.** FIPS 201-3 requires affiliation printed on the card (Zone 8F), and the FASC-N has a person or organization association category, which this profile found only in a secondary source **[unverified]**. CAC certificates mark contractors with `OU=CONTRACTOR` **[secondary]**, but no primary source shows a dependable military and civilian split. An attester that needs affiliation should read it from the agency's personnel system (section 3) rather than infer it from the certificate.
- **Clearance is not on the card.** FIPS 201-3 defines no clearance field. A certificate may carry a background investigation indicator, which shows investigation status, not clearance. A clearance claim needs a separate authoritative source the attester is entitled to read, for example the agency's personnel security system.
- **Derived PIV credentials.** SP 800-157 lets a mobile device hold a PIV-derived key and certificate, issued on proof of possession of a valid card, at AAL2 or AAL3. DoD issues them through its Purebred system **[secondary]**. A client on such a device can answer the step 1 challenge without a card reader, and a CO provisioning service can require that answer alongside `idpToken` before registering the device's Agora key (spec §2.5.4), tying the Agora device key to a PIV-derived credential on the same device. SP 800-157 Rev. 1 is a final public draft, not final.
- **Key types differ.** PIV keys are RSA or NIST curve keys on the card; Agora device keys are Ed25519 in the DID document (spec §2.1). The card authenticates the person to the attester; it never becomes an Agora key.

## 6. EU Digital Identity Wallet

An attester registers as an EUDI wallet-relying party and verifies members' person identification data (PID) and attestations of attributes ((Q)EAA) over OpenID4VP under HAIP, then issues per section 2.5; the CO lists the attester and admits per section 2.4. A CO that wants to be the relying party itself runs its own attester. A third-party attester holds the PID, and the CO never receives it; one registration serves every CO that lists it.

### 6.1 Why an Attester Verifies

**The constraints.**

- **EUDI credentials are bound to a key, not a DID.** Every EUDI format binds the credential to a key generated inside the wallet's secure hardware, which the user cannot export. The PID rulebook defines no `sub`, the ARF never mentions DIDs, and SD-JWT VC makes `sub` optional. Under the subject check of spec §5.2.1.5, no EUDI credential counts in a leaf.
- **Wallets present only to registered relying parties.** The wallet authenticates every requester by its access certificate before presenting, remote or proximity (2024/2982 Art 3; ARF RPA_01, RPA_03). Under HAIP the response is encrypted to that relying party. An ordinary Agora client is not one.
- **Peer presentation is in person only.** ARF v3.0.0 wallet-to-wallet presentation works only in proximity, over ISO/IEC 18013-5 (Topic 30, W2W_08). A stranger's wallet will not produce a remote presentation for another user.
- **PID in a leaf shows legal identity to every member.** The PID minimum is family name, given name, birth date, birthplace, and nationality, and from 11 August 2028 a portrait. Every member of every group carrying the leaf would see it (spec §12.11), and one stored presentation reused across groups defeats the unlinkability the regulation requires (Art 5a(16)).

**The decision.** EUDI verification is a relying-party function of an attester. The attester vouches for the member's Agora DID with its own credential (section 2.5), the CO lists the attester in `trustedAttesters` (spec §3.3), and the CO admits on that credential (section 2.4). The common case for a CO that must or wants to be the relying party is a CO-run attester. The strict subject-DID rule of spec §5.2.1.5 stays as written.

**Rejected.**

- **A core exception for key-bound credentials with a group-bound Key Binding JWT.** The exception would count an entry with no subject DID if it carried a holder proof whose `nonce` commits to the group and leaf. Wallets cannot produce it: the relying party, not the holder, chooses the `nonce` and `aud`, and the response is encrypted to the relying party. It would also expose a legal name to every member and reverse the recorded no-holder-proof default.
- **Waiting.** Wallets ship from 24 December 2026, and the attester design works with them on day one. Waiting buys nothing.

### 6.2 What Is Read

Only the PID or (Q)EAA attributes registered for an intended use, the fewest the attester's issuing policy needs, for example PID `nationality` for a residency rule, or an EAA proving a licensed profession.

### 6.3 Relying-Party Setup

Every attester, CO-run or third-party, sets up the same way. A relying party is registered, not authorized (ARF §6.4.3). What it may receive is limited by its registered intended uses, any disclosure policy embedded in the attestation, and what the user approves. Steps:

1. **Be an established legal entity** in an EU Member State. The attester's operator registers where it is established (Art 5b(1)); for a CO-run attester, that is the CO. Registration requires an identified entity with official identifiers, so the attester's DID belongs to a service run by a registered entity, not to an anonymous account. How an entity established outside the EU registers is **unverified**; no path was found.
2. **Define each intended use** and the exact attestations and attributes it needs, for example "verify employee identity at enrollment: PID `family_name`, `given_name`" or "verify residency for membership: PID `nationality`". The attester may never request anything else (Art 5b(2)(c), 5b(3)). Its intended use must cover issuing derived attestations to the user; whether every Member State registrar accepts that use is **unverified**. The attester's operator is a GDPR controller for what it receives and needs a lawful basis of its own: wallet approval is not one (ARF §6.6.3.5), and an employer's choice of basis is a question for counsel.
3. **Register with the national registrar** under that Member State's registration policy (2025/848 Art 3, Art 4, Annex I): official and trade name, identifiers (for example EUID, LEI, VAT), contact details, a service description, and for each intended use a machine-readable list of attributes. The registrar verifies against authentic sources and publishes the entry. Registration applies from 24 December 2026 (2025/848 Art 11).
4. **Get an access certificate for each verifier instance** from a certificate authority the Member State authorizes (2025/848 Art 7, Annex IV; ARF §3.11.3). Its private key is attester key material, distinct from any IO key (ARCHITECTURE §2.4).
5. **Get a registration certificate** where the Member State offers one (2025/848 Art 8). Wallets warn when a request exceeds it, and must validate it from 11 August 2028 (2026/1731).
6. **Run an OpenID4VP 1.0 verifier under HAIP:** signed request objects with the `x509_hash` client identifier prefix and the access-certificate chain in `x5c`, a DCQL query, and encrypted responses (`direct_post.jwt`, or `dc_api.jwt` through the browser Digital Credentials API).

**What the user sees.** The wallet shows the attester's trade name, which is the CO's only for a CO-run attester, the attributes requested, the intended use, the privacy-policy URL, and the result of its registration checks, and asks for explicit approval; approving PID attributes requires authenticating to the wallet's secure element (ARF §6.6.3.5). The member approves the attester's request, then chooses to carry its credential in a Space. The transaction is logged in the user's dashboard, from which the user can report the attester to the data protection authority (Art 5a(4)(d)).

**Costs.** Registration and access-certificate fees are national or commercial and **unknown**; 2025/848 sets no fee rule. Each Member State's registration policy must be read for the attester's country.

**Obligation to accept.** A typical CO need not accept the wallet. A government CO that requires electronic identification must (Art 5f(1)), and so must a private CO in a regulated sector that requires strong user authentication, by about 24 December 2027 and on the user's request (Art 5f(2)).

**Reliance.** Some COs must be the relying party themselves, for example a government CO under Art 5f(1), or a firm whose anti-money-laundering rules limit reliance on third parties. Such a CO runs its own attester. Whether a given CO may rely on a third-party attester is a question for counsel.

### 6.4 How It Is Verified

Section 2.4 applies, with these specifics for step 2:

- **Request.** The attester sends a signed OpenID4VP request for only the attributes registered for this intended use, with the OpenID4VP `nonce` set per section 2.3. Same-device and Digital Credentials API flows are preferred: a cross-device QR code can be relayed to someone else's wallet.
- **Verification.** The attester MUST, before acting on a response:
  - decrypt it and verify the issuer's signature chain against the PID-provider list or the trusted lists for QEAA;
  - check validity and status by the attestation's own rules, for example its status list;
  - verify holder binding: the KB-JWT `aud` equals the attester's client identifier and its `nonce` equals the value it sent, or the mdoc device signature verifies over the OpenID4VP SessionTranscript.

### 6.5 Derived Claims

Examples: `verified_natural_person: true`, "employee of X", "licensed profession Y", `age_over_18: true`, or a country of residence. Whether the PID carries age-over attributes is **unverified** (not in the PID rulebook v1.7 list); an age claim may have to be derived from `birth_date` or come from the separate EU age-verification track. Section 2.5 governs subject, issuer, validity, and revocation. An attester credential carries no EU legal status and is not a QEAA unless the attester is a qualified trust service provider. SD-JWT VC is still an Internet-Draft, and HAIP pins an earlier revision, so wire details may move.

### 6.6 European Business Wallet

The European Business Wallet is a **proposal** (COM(2025) 838). Parliament confirmed its negotiating mandate on 7 October 2026, and trilogues have not started. It would identify organizations by their EUID and contains no DIDs. It would also narrow the EUDI wallet to natural persons.

Two plausible joins with the employer profiles (`profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`) once it is law, neither needing a core change:

- **Organization.** An attester verifies a business-wallet presentation of an organization's EUID and legal name, then issues a credential linking the organization's root DID to that EUID.
- **Employee.** A business wallet issues employment or mandate attestations to employees' EUDI wallets. These are key-bound like any EAA, so they enter Agora through section 6.4 and section 2.5.

### 6.7 Caveats

- **Wallet availability.** No certified wallet exists yet, and national launches are uneven, with Germany reported for January 2027 **[secondary]**. A CO should confirm wallet support in its members' Member States before relying on this section.
- **Pseudonyms.** Art 5b(9) bars a relying party from refusing a pseudonym where law does not require identification, which limits "verify real identity to join" designs outside regulated or government settings.
- **Non-EU attesters.** How an attester established outside the EU registers is **unverified**.

## 7. Other Wallets and Issuers

The attester model is source-agnostic: the Space asks only whether a credential was issued to the member's DID by a DID listed in `trustedAttesters` (section 2.5). Any issuer reaches a Space by one of two paths.

- **Direct issuers.** An issuer that already puts the member's DID in the subject is listed in `trustedAttesters` as-is, with no bridging. Examples: a W3C VC from a university or professional body, an Open Badges 3.0 credential, or an OpenVTC or DTG credential (`profiles/dtg-openvtc.md`).
- **Bridging attesters.** For a credential that is key-bound or cannot be presented to peers, an attester verifies it and issues derived claims to the member's DID, as in section 6. Examples: the EUDI wallet, ISO/IEC 18013-5 and 18013-7 mobile driver's licenses, including those held in platform wallets, national eID schemes such as BankID, and Login.gov.

The list holds at most 32 DIDs (spec §3.3), which limits how many issuers one Space can list.

## 8. Privacy and Security

See also spec §12.11 and §12.13.

- **Minimization.** Section 2.1 and section 2.2: read the fewest attributes, keep raw identifiers at the attester, and issue derived claims only.
- **Linkability across Spaces.** Identical attester-credential bytes in several groups let their members link the holder, and a fixed issuer signature or status-list index links the holder across verifiers (spec §12.11). An attester can issue a batch of instances, each with its own signature and status index (for example OpenID4VCI batch issuance), so the member's client can use a different instance in each group with a fresh selective-disclosure presentation. A member who carries an attester credential at all reveals the attester's issuing DID, which may itself identify an employer or agency.
- **Retention.** The attester keeps disclosed attributes and verification records under its stated retention policy, as a GDPR controller where GDPR applies. Raw identifiers it keeps to match re-verifications (section 5) are personal data under the same policy.
- **Status checks.** Fetching a status list can reveal a client's activity to the list host. Clients fetch whole lists and cache them (spec §12.11). A public status list also reveals departures to anyone watching bits flip (`profiles/gsuite-employer-did.md` §5.2).
- **Relay attacks.** A cross-device QR code or a smartcard challenge can be relayed by an attacker to the victim's device. The DID-bound nonce of section 2.3 ties the result to one DID and one attempt, and same-device flows avoid the QR code.
- **Issuer risk.** An attester credential is only as strong as the attester's source verification and issuing-key custody (spec §12.13). Listing an attester in `trustedAttesters` extends that risk to the Space, whether the CO runs the attester or not.

## 9. Open Questions

- Assurance. `trustedAttesters` carries no assurance level, so a strong identity-proofing attester and a weak one look the same to clients. The CO's choice of whom to list is the only quality control; this profile deliberately adds no assurance metadata.
- Claim vocabulary. Attesters may name the same derived claim differently, for example "over 18". Clients match each attester's own claim names, or the CO lists attesters that share a vocabulary. Attesters that want interoperable derived claims (`verified_natural_person`, `employment_status`, `affiliation`, age bands, assurance levels) would benefit from a shared vocabulary; none is defined here, and a deployment should document the names it uses.
- PIV affiliation. Whether the FASC-N association category gives a dependable affiliation should be checked against the primary FASC-N specification before an attester relies on it.
- IdP assurance signals. An attester should read its IdP's documentation for the `acr` values it emits; this profile does not list them.
- Fees and timelines for EUDI registration. National registration policies set them; an attester's operator should read its Member State's policy before planning.
- Employer lawful basis. Consent is weak in employment, and Art 5b(9) pseudonym rules interact with legitimate interest; this is for counsel.
- Remote peer presentation. If a later ARF adds it, or wallets gain a way to sign holder-chosen nonces for unregistered verifiers, a key-bound exception to spec §5.2.1.5 could be reconsidered. Neither is in ARF v3.0.0.
