# Profile: Attribute Bridging

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-17
**Version:** 0.1 Draft
**Depends on:** ARCHITECTURE §2.2, §2.3, §2.4, §3 (S1, S4, S5, S6, S7, S8, S9); spec §2.1, §2.5.4, §2.6, §3.5, §4.1, §4.2, §4.3, §4.5, §4.6.3, §5.2.1, §5.2.1.5, §12.11, §12.13, §13.1.1
**Sources:** Directories and IdPs: `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`, `profiles/universal-idp-did.md`; OpenID Connect Core 1.0 (https://openid.net/specs/openid-connect-core-1_0.html); SAML 2.0 (OASIS); NIST SP 800-63-4, Digital Identity Guidelines (https://pages.nist.gov/800-63-4/). CAC and PIV: FIPS 201-3, Personal Identity Verification (PIV) of Federal Employees and Contractors, January 2022 (https://csrc.nist.gov/pubs/fips/201-3/final); NIST SP 800-73-5 Part 1, Interfaces for Personal Identity Verification, July 2024 (https://csrc.nist.gov/pubs/sp/800/73/pt1/5/final); NIST SP 800-157, Guidelines for Derived PIV Credentials, December 2014, and SP 800-157 Rev. 1 Final Public Draft, 14 November 2024 (https://csrc.nist.gov/pubs/sp/800/157/r1/fpd); Federal PKI (https://www.idmanagement.gov/university/fpki/, https://www.idmanagement.gov/implement/announcements/FBCAG5/). EU Digital Identity Wallet: Regulation (EU) 2024/1183 (eIDAS 2.0, CELEX 32024R1183, http://data.europa.eu/eli/reg/2024/1183/oj); Implementing Regulations (EU) 2024/2977, 2024/2979, 2024/2982, 2025/848, and 2026/1731; EUDI Wallet Architecture and Reference Framework (ARF) v3.0.0, 23 July 2026 (https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework, https://eudi.dev/latest/main/); PID rulebook v1.7, 17 July 2026 (https://github.com/eu-digital-identity-wallet/eudi-doc-attestation-rulebooks-catalog); OpenID for Verifiable Presentations 1.0, Final, 9 July 2025 (https://openid.net/specs/openid-4-verifiable-presentations-1_0.html); OpenID for Verifiable Credential Issuance 1.0, Final, 16 September 2025 (https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html); OpenID4VC High Assurance Interoperability Profile (HAIP) 1.0, Final, 24 December 2025 (https://openid.net/specs/openid4vc-high-assurance-interoperability-profile-1_0.html); SD-JWT, RFC 9901; SD-JWT VC, draft-ietf-oauth-sd-jwt-vc-19 (https://datatracker.ietf.org/doc/draft-ietf-oauth-sd-jwt-vc/); European Business Wallet proposal COM(2025) 838, procedure 2025/0358(COD) (https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0358(COD)). EUDI research and full citations: `notes/eudi-wallet.md`.

---

## 1. Summary

Organizations already hold authoritative facts about their people: a directory knows who is an employee and in which department, an IdP knows how well a person was identity-proofed, a government smartcard proves federal affiliation, and an EU wallet carries a verified legal identity. This profile describes one pattern for bringing such facts into Agora without exposing them.

A communications operator (CO) component reads an authoritative source the CO is entitled to read and verifies what it reads. On the result, the CO does one or more of three things, all existing Agora mechanisms:

- admits the member with a `SpaceInvite` (spec §4.3);
- assigns the member a role (spec §4.2);
- issues its own credential with **derived claims**, with the member's Agora DID as subject and a CO DID as issuer, that the member carries in `agora_credentials` (spec §5.2.1.5).

Raw source identifiers and attributes, such as a DoD EDIPI, PID attributes, a manager's name, or an employee number, stay at the CO. Other members see only the derived claims the member chooses to carry. No infrastructure operator (IO) takes part or learns anything: the verifier and issuer must know who the member is, so they are CO components by the key test (ARCHITECTURE §2.3), and source verification runs outside relays (S1, S6). Components that hold the raw attributes run under CO control (S8).

This profile needs no Agora core change. Sections 3 to 6 apply the pattern to four kinds of source:

| Source | Section | What exists in Agora today |
|---|---|---|
| Directories (Active Directory, Entra ID, Google Workspace, LDAP) | 3 | `EmployeeCredential` and JML lifecycle in the employer profiles |
| Identity providers (OIDC, SAML) | 4 | `idpToken` at device registration (spec §2.5.4) |
| CAC and PIV smartcards | 5 | Nothing specific; usually reached through an IdP (section 4) |
| EU Digital Identity Wallet | 6 | Nothing specific; this profile defines the relying-party flow |

## 2. Common Rules

These rules apply to every source in sections 3 to 6.

### 2.1 Data Minimization

The CO reads only the attributes its admission, role, or issuing policy uses, and asks for a claim rather than the record behind it where the source allows. A CO that follows this profile MUST NOT put raw source identifiers or personal attributes in a credential meant for `agora_credentials` unless the member asks for them. Raw identifiers include an EDIPI, FASC-N, card UUID, employee number, directory object ID, IdP subject identifier, and PID personal administrative number. Personal attributes include legal name, birth date, home address, and manager. Every member of every group carrying the leaf would see them (spec §12.11).

A client should not put a source credential itself, such as a PID presentation, an IdP token, or a PIV certificate, in `agora_credentials`. None of them names the member's Agora DID as subject, so none counts under spec §5.2.1.5, and each would show its raw attributes to the whole group.

### 2.2 Derived Claims

A derived claim states a conclusion the CO reached, not the data it reached it from. Guidance for COs choosing claim names:

- **Boolean or enumerated, not free text.** `employment_status: "active"`, `affiliation: "contractor"`, `verified_natural_person: true`.
- **Bands, not values.** `age_over_18: true`, not a birth date; `tenure_band: "5y+"`, not a hire date.
- **Coarse, not precise.** A country of residence, not an address; a business unit, not a cost center, where the CO judges the unit coarse enough to show outsiders.
- **Assurance as its own claim.** `identity_assurance: "IAL2"` with the date the CO verified it (section 4).
- **One claim per decision.** Put only what a group's policy, or a stranger deciding whether to accept a DM (spec §4.6.3), would use.

SD-JWT VC (`application/dc+sd-jwt`) is the preferred format, because the member can disclose only the claims a given group's policy uses (spec §12.11). Any format spec §5.2.1.5 names works. No shared claim vocabulary exists (section 8).

### 2.3 Binding at Verification

Where the source supports a holder proof, the CO's verifier MUST bind it to the member's Agora DID and to this session: the challenge or nonce the source signs MUST be fresh and commit to the member's DID and a session identifier, for example a hash over a random value, the DID, and the session identifier. The member proves the DID itself with `MemberAuth` (spec §3.5) or a request signed per spec §13.1.1. This ties the source result to one DID and one attempt, and defeats relaying a QR code or challenge to someone else. Sections 4 to 6 say what the nonce is for each source.

### 2.4 Admission Flow

1. **Request.** The applicant's client asks the CO's admission service for a `SpaceInvite` and proves its Agora DID (section 2.3).
2. **Source verification.** The CO's verifier reads and verifies the source as sections 3 to 6 describe, binding the result per section 2.3.
3. **Outcome.** On success the admission service MUST issue the `SpaceInvite` with `issuedTo` set to the DID proved in step 1, signed per spec §13.1.1 by an admin DID of the Space (spec §4.1, §4.3), and MAY name a role (spec §4.2). It MAY also issue a CO credential (section 2.5). On failure it issues nothing.
4. **Records.** The CO records the verification event: the DID, the purpose, the source and credential type, the result, and the time. It keeps disclosed attributes only as long as its stated purpose and retention policy allow. The verifier records verifications, not group membership; MLS remains the source of truth for who is in a group (S9).

The invite and any role assignment are ordinary CO-signed records (S4). S7 already bars an IO from requiring source verification as a condition of service, and changing IOs touches neither the CO's source access nor the credentials it issued (S5).

### 2.5 CO-Issued Credentials

**Subject and issuer.** The subject is the member's Agora DID (spec §2.1), in `sub` of an SD-JWT VC or `credentialSubject.id` of a W3C VC, as an exact string (spec §5.2.1.5). The issuer is a DID the CO controls for issuing, distinct from any IO key (ARCHITECTURE §2.4).

**Validity tied to re-verification.** The credential's validity matches the CO's re-verification policy for its source and never outlasts it. A directory-backed credential can be re-issued on each JML event and yearly, as the employer profiles already do; a credential derived from a one-time wallet or card check expires when the CO would next re-check.

**Revocation.** The CO publishes status in a status list and MUST revoke the credential when the member leaves, when re-verification fails, or when the source changes in a way that falsifies a claim, for example a mover event, a revoked PIV certificate, or a revoked PID to the CO's knowledge. The employer profiles' leaver and mover workflows are the model (`profiles/o365-employer-did.md` §5.3 and §5.4, `profiles/gsuite-employer-did.md` §4.3 and §4.4). Revoking a source credential or CO credential does not remove anyone: MLS membership is the only access control, so the CO removes the member by its usual means (spec §4.5, §12.13).

**How others trust it.** Issuer trust is the verifying client's policy (spec §5.2.1.5, §12.13). A client can name the CO's issuer DID directly, or ask a TRQP v2.0 trust registry whether the issuer is authorized for that credential type, as `profiles/dtg-openvtc.md` section 3 describes. The trust is in the CO, not in the source: a CO credential derived from a PIV card is not a PIV credential, and one derived from a PID is not a qualified attestation. Deployments should say so plainly to users.

### 2.6 Enterprise and Government Visibility (Deployment Guidance)

An enterprise or government CO may see its members' verified attributes within its own Space: those its verifier read from the source, and the CO-credential claims in the leaves of groups it is a member of (spec §12.11). Under GDPR purpose limitation, and comparable rules elsewhere, it uses them only for the purposes it told members about and, for EUDI, the intended uses it registered (section 6.3).

### 2.7 Scope of Requirements

The BCP 14 key words in this profile bind only the CO's verifier, admission, and issuing components. Nothing here constrains how a client displays credentials or prompts its user.

## 3. Directories

Active Directory, Entra ID, Google Workspace, and other LDAP directories.

**What exists.** The employer profiles already read the directory, run the JML lifecycle, and issue an `EmployeeCredential` to the employee's Agora DID: `profiles/o365-employer-did.md` §4 and §5, `profiles/gsuite-employer-did.md` §4 and §5, and `profiles/universal-idp-did.md` (SCIM, HR systems, and on-premises AD). Role derivation from groups is in `profiles/gsuite-employer-did.md` §4.7 and the `agoraRoles` claim. This section adds only the mapping from directory attributes to derived claims.

**What is read.** User object attributes the CO's service account may read: account enabled state, group membership, department, job title, manager, employee type, employee number, and custom attributes (Entra extension attributes, Google Workspace custom schemas, AD `extensionAttribute*`).

**How it is verified.** The directory is the CO's own system of record, read over its authenticated API (Microsoft Graph, Google Directory API, LDAP over TLS). The link from directory record to Agora DID is the immutable user ID matched at enrollment, never email or UPN (`profiles/universal-idp-did.md` §8).

**Example mapping.**

| Directory attribute | Derived claim |
|---|---|
| account enabled, not in leaver state | `employment_status: "active"` |
| `employeeType` | `affiliation: "employee"`, `"contractor"`, or `"intern"` |
| group membership | `agoraRoles` (existing), or a named team the CO chooses to disclose |
| has direct reports | `people_manager: true`, never the manager's or reports' names |
| `department` | business unit, where the CO judges it safe to show outsiders |
| `employeeId`, `objectGUID`, manager | none; stays at the CO |

**Caveats.** The `EmployeeCredential` examples in the employer profiles carry raw attributes (`employeeId`, `displayName`, `officeLocation`). That suits presentation to the CO's own enrollment service (`profiles/o365-employer-did.md` §4.3). For `agora_credentials` in groups shared with outsiders, which `profiles/o365-employer-did.md` §4.4 already flags, a CO that follows this profile issues either a separate credential with derived claims only, or an SD-JWT VC from which the client discloses only the derived claims.

## 4. Identity Providers

OIDC and SAML 2.0 IdPs: enterprise IdPs such as Okta and Ping Identity, and identity-proofing services such as Login.gov and ID.me.

**What exists.** Device key registration already carries a signed IdP token: the client authenticates to the organization's IdP and sends the OIDC ID token, an access token, or the SAML assertion as `idpToken` (spec §2.5.4). The provisioning service links it to the user record by the IdP's immutable ID (`profiles/universal-idp-did.md` §8). This section adds reading assurance and other claims from that token, and using an identity-proofing IdP for admission to a Space whose CO is not the member's employer.

**What is read.** The signed ID token or assertion at enrollment or admission: issuer, subject, authentication time, the authentication context (OIDC `acr` and `amr`, SAML `AuthnContextClassRef`), and any verified attributes the CO's client registration is permitted to receive.

**How it is verified.** The CO is the OIDC relying party or SAML service provider. Its verifier checks the signature against the IdP's published keys or metadata, `iss`, `aud`, expiry, and, for OIDC, sets the authorization request's `nonce` per section 2.3. SAML has no holder-chosen nonce; the verifier binds the assertion to the session through `InResponseTo` and a `RelayState` that commits to the DID and session.

**Example derived claims.**

- `identity_assurance: "IAL2"`, with the verification date. NIST SP 800-63-4 defines identity assurance levels (IAL) for proofing and authenticator assurance levels (AAL) for each authentication. IAL describes the person and can be carried forward; AAL describes one sign-in, so a CO derives at most "verified at AAL3 at enrollment", not a lasting AAL.
- `verified_natural_person: true`, `country_of_residence`, or `age_over_18`, where the IdP releases a verified attribute that supports it.
- From an enterprise IdP, the same claims as section 3.

**Caveats.**

- How each IdP signals assurance is provider-defined. Login.gov and ID.me signal proofing level through `acr` values or provider-specific claims; exact values are **unverified** here and the CO reads its provider's documentation.
- Login.gov serves government agency partners, so only a government CO can use it directly.
- IdP tokens are short-lived bearer tokens with the IdP's subject identifier, not the Agora DID. They are evidence for the CO, never something a member carries (section 2.1).
- Many CAC and PIV deployments reach the card through an IdP that supports certificate-based authentication; for them, section 5 reduces to this section with the `amr` showing hardware PKI.

## 5. CAC and PIV Smartcards

US federal Personal Identity Verification (PIV) cards under FIPS 201-3, and the DoD Common Access Card (CAC), which is PIV-compatible.

**What exists.** Nothing CAC- or PIV-specific. The simplest deployment fronts the card with an IdP and follows section 4. This section covers a CO verifier that reads the card directly.

**What is read.** The PIV Authentication certificate (key reference 9A) from the card through the SP 800-73-5 card interface. Its subject alternative name carries the FASC-N (`pivFASC-N`) and the card UUID as a `urn:uuid:` URI; FIPS 201-3 requires both (§4.2.2.1). On a CAC the subject CN and a UPN carry the DoD ID number (EDIPI) **[secondary: vendor integration guides; no current DoD primary source found]**.

**How it is verified.**

1. **Proof of possession.** The client has the card sign a CO challenge with the PIV Authentication key, either directly or as TLS client authentication in a session that then carries the member's §13.1.1-signed request. The challenge is the section 2.3 nonce. The PIV Authentication key works only after cardholder activation by PIN, and only over the contact interface (FIPS 201-3 §4.2.2.1). The Card Authentication key (9E) works without a PIN and gives far less assurance; the verifier MUST NOT accept it for this purpose.
2. **Path validation.** The verifier validates the certificate to a configured trust anchor: the DoD PKI roots (DoD Root CA 3 to 6) for CAC, or the Federal Common Policy CA G2 for civilian PIV. DoD PKI connects to the Federal PKI through the Federal Bridge, not by direct cross-certification with Common Policy; the bridge is migrating to FBCA G5 during 2026. It checks the PIV Authentication certificate policy OID.
3. **Revocation.** The verifier checks status by OCSP or CRL at verification time; FIPS 201-3 requires issuers to provide both (§5.3, §5.5).

**Example derived claims.**

- `us_federal_piv: true`, with the verification date.
- Agency or component, from the issuing CA and the subject DN.
- `identity_assurance: "IAL3"`: FIPS 201-3 §6.1 states PIV issuance meets IAL3. Authentication with the PIV Authentication key is AAL3 and with the Card Authentication key AAL1 (FIPS 201-3 Table 6-2), which is one more reason step 1 refuses the latter.
- Affiliation (employee, contractor, military), with care: see caveats.

The FASC-N, card UUID, and EDIPI stay at the CO (section 2.1). The verifier keys its record on them so it can match re-verifications and revocations.

**Caveats.**

- **Affiliation is not reliably in the certificate.** FIPS 201-3 requires affiliation printed on the card (Zone 8F), and the FASC-N has a person or organization association category, which this profile found only in a secondary source **[unverified]**. CAC certificates mark contractors with `OU=CONTRACTOR` **[secondary]**, but no primary source shows a dependable military and civilian split. A CO that needs affiliation should read it from the agency's personnel system (section 3) rather than infer it from the certificate.
- **Clearance is not on the card.** FIPS 201-3 defines no clearance field. A certificate may carry a background investigation indicator, which shows investigation status, not clearance. A clearance claim needs a separate authoritative source the CO is entitled to read, for example the agency's personnel security system.
- **Derived PIV credentials.** SP 800-157 lets a mobile device hold a PIV-derived key and certificate, issued on proof of possession of a valid card, at AAL2 or AAL3. DoD issues them through its Purebred system **[secondary]**. A client on such a device can answer the step 1 challenge without a card reader, and a CO provisioning service can require that answer alongside `idpToken` before registering the device's Agora key (spec §2.5.4), tying the Agora device key to a PIV-derived credential on the same device. SP 800-157 Rev. 1 is a final public draft, not final.
- **Key types differ.** PIV keys are RSA or NIST curve keys on the card; Agora device keys are Ed25519 in the DID document (spec §2.1). The card authenticates the person to the CO; it never becomes an Agora key.

## 6. EU Digital Identity Wallet

The CO registers as an EUDI wallet-relying party and verifies its members' person identification data (PID) and attestations of attributes ((Q)EAA) over OpenID4VP under HAIP, then applies section 2.4 and section 2.5.

### 6.1 Why the CO Verifies

**The constraints.**

- **EUDI credentials are bound to a key, not a DID.** Every EUDI format binds the credential to a key generated inside the wallet's secure hardware, which the user cannot export. The PID rulebook defines no `sub`, the ARF never mentions DIDs, and SD-JWT VC makes `sub` optional. Under the subject check of spec §5.2.1.5, no EUDI credential counts in a leaf.
- **Wallets present only to registered relying parties.** The wallet authenticates every requester by its access certificate before presenting, remote or proximity (2024/2982 Art 3; ARF RPA_01, RPA_03). Under HAIP the response is encrypted to that relying party. An ordinary Agora client is not one.
- **Peer presentation is in person only.** ARF v3.0.0 wallet-to-wallet presentation works only in proximity, over ISO/IEC 18013-5 (Topic 30, W2W_08). A stranger's wallet will not produce a remote presentation for another user.
- **PID in a leaf shows legal identity to every member.** The PID minimum is family name, given name, birth date, birthplace, and nationality, and from 11 August 2028 a portrait. Every member of every group carrying the leaf would see it (spec §12.11), and one stored presentation reused across groups defeats the unlinkability the regulation requires (Art 5a(16)).

**The decision.** EUDI verification is a CO relying-party function. When other members need to see the result, the CO vouches for the member's Agora DID with its own credential. The strict subject-DID rule of spec §5.2.1.5 stays as written.

**Rejected.**

- **A core exception for key-bound credentials with a group-bound Key Binding JWT.** The exception would count an entry with no subject DID if it carried a holder proof whose `nonce` commits to the group and leaf. Wallets cannot produce it: the relying party, not the holder, chooses the `nonce` and `aud`, and the response is encrypted to the relying party. It would also expose a legal name to every member and reverse the recorded no-holder-proof default.
- **Waiting.** Wallets ship from 24 December 2026, and the CO-side design works with them on day one. Waiting buys nothing.

### 6.2 What Is Read

Only the PID or (Q)EAA attributes registered for an intended use, the fewest the CO's policy needs, for example PID `nationality` for a residency rule, or an EAA proving a licensed profession.

### 6.3 Relying-Party Setup

A relying party is registered, not authorized (ARF §6.4.3). What it may receive is limited by its registered intended uses, any disclosure policy embedded in the attestation, and what the user approves. Steps:

1. **Be an established legal entity** in an EU Member State. The CO registers where it is established (Art 5b(1)). How an entity established outside the EU registers is **unverified**; no path was found.
2. **Define each intended use** and the exact attestations and attributes it needs, for example "verify employee identity at enrollment: PID `family_name`, `given_name`" or "verify residency for membership: PID `nationality`". The CO may never request anything else (Art 5b(2)(c), 5b(3)). The CO is a GDPR controller for what it receives and needs a lawful basis of its own: wallet approval is not one (ARF §6.6.3.5), and an employer's choice of basis is a question for counsel.
3. **Register with the national registrar** under that Member State's registration policy (2025/848 Art 3, Art 4, Annex I): official and trade name, identifiers (for example EUID, LEI, VAT), contact details, a service description, and for each intended use a machine-readable list of attributes. The registrar verifies against authentic sources and publishes the entry. Registration applies from 24 December 2026 (2025/848 Art 11).
4. **Get an access certificate for each verifier instance** from a certificate authority the Member State authorizes (2025/848 Art 7, Annex IV; ARF §3.11.3). Its private key is CO key material, distinct from any IO key (ARCHITECTURE §2.4).
5. **Get a registration certificate** where the Member State offers one (2025/848 Art 8). Wallets warn when a request exceeds it, and must validate it from 11 August 2028 (2026/1731).
6. **Run an OpenID4VP 1.0 verifier under HAIP:** signed request objects with the `x509_hash` client identifier prefix and the access-certificate chain in `x5c`, a DCQL query, and encrypted responses (`direct_post.jwt`, or `dc_api.jwt` through the browser Digital Credentials API).

**What the user sees.** The wallet shows the CO's trade name, the attributes requested, the intended use, the privacy-policy URL, and the result of its registration checks, and asks for explicit approval; approving PID attributes requires authenticating to the wallet's secure element (ARF §6.6.3.5). The transaction is logged in the user's dashboard, from which the user can report the CO to the data protection authority (Art 5a(4)(d)).

**Costs.** Registration and access-certificate fees are national or commercial and **unknown**; 2025/848 sets no fee rule. Each Member State's registration policy must be read for the CO's country.

**Obligation to accept.** A typical CO need not accept the wallet. A government CO that requires electronic identification must (Art 5f(1)), and so must a private CO in a regulated sector that requires strong user authentication, by about 24 December 2027 and on the user's request (Art 5f(2)).

### 6.4 How It Is Verified

Section 2.4 applies, with these specifics for step 2:

- **Request.** The verifier sends a signed OpenID4VP request for only the attributes registered for this intended use, with the OpenID4VP `nonce` set per section 2.3. Same-device and Digital Credentials API flows are preferred: a cross-device QR code can be relayed to someone else's wallet.
- **Verification.** The verifier MUST, before acting on a response:
  - decrypt it and verify the issuer's signature chain against the PID-provider list or the trusted lists for QEAA;
  - check validity and status by the attestation's own rules, for example its status list;
  - verify holder binding: the KB-JWT `aud` equals the verifier's client identifier and its `nonce` equals the value it sent, or the mdoc device signature verifies over the OpenID4VP SessionTranscript.

### 6.5 Derived Claims

Examples: `verified_natural_person: true`, "employee of X", "licensed profession Y", `age_over_18: true`, or a country of residence. Whether the PID carries age-over attributes is **unverified** (not in the PID rulebook v1.7 list); an age claim may have to be derived from `birth_date` or come from the separate EU age-verification track. Section 2.5 governs subject, issuer, validity, and revocation. A CO credential carries no EU legal status and is not a QEAA unless the CO is a qualified trust service provider. SD-JWT VC is still an Internet-Draft, and HAIP pins an earlier revision, so wire details may move.

### 6.6 European Business Wallet

The European Business Wallet is a **proposal** (COM(2025) 838). Parliament confirmed its negotiating mandate on 7 October 2026, and trilogues have not started. It would identify organizations by their EUID and contains no DIDs. It would also narrow the EUDI wallet to natural persons.

Two plausible joins with the employer profiles (`profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`) once it is law, neither needing a core change:

- **Organization.** A CO verifies a business-wallet presentation of an organization's EUID and legal name, then issues a credential linking the organization's root DID to that EUID.
- **Employee.** A business wallet issues employment or mandate attestations to employees' EUDI wallets. These are key-bound like any EAA, so they enter Agora through section 6.4 and section 2.5.

### 6.7 Caveats

- **Wallet availability.** No certified wallet exists yet, and national launches are uneven, with Germany reported for January 2027 **[secondary]**. A CO should confirm wallet support in its members' Member States before relying on this section.
- **Pseudonyms.** Art 5b(9) bars a relying party from refusing a pseudonym where law does not require identification, which limits "verify real identity to join" designs outside regulated or government settings.
- **Non-EU COs.** How a CO established outside the EU registers is **unverified**.

## 7. Privacy and Security

See also spec §12.11 and §12.13.

- **Minimization.** Section 2.1 and section 2.2: read the fewest attributes, keep raw identifiers at the CO, and issue derived claims only.
- **Linkability across Spaces.** Identical CO-credential bytes in several groups let their members link the holder, and a fixed issuer signature or status-list index links the holder across verifiers (spec §12.11). A CO can issue a batch of instances, each with its own signature and status index (for example OpenID4VCI batch issuance), so the member's client can use a different instance in each group with a fresh selective-disclosure presentation. A member who carries a CO credential at all reveals the CO's issuer DID, which may itself identify an employer or agency.
- **Retention.** The CO keeps disclosed attributes and verification records under its stated retention policy, as a GDPR controller where GDPR applies. Raw identifiers it keeps to match re-verifications (section 5) are personal data under the same policy.
- **Status checks.** Fetching a status list can reveal a client's activity to the list host. Clients fetch whole lists and cache them (spec §12.11). A public status list also reveals departures to anyone watching bits flip (`profiles/gsuite-employer-did.md` §5.2).
- **Relay attacks.** A cross-device QR code or a smartcard challenge can be relayed by an attacker to the victim's device. The DID-bound nonce of section 2.3 ties the result to one DID and one attempt, and same-device flows avoid the QR code.
- **Issuer risk.** A CO credential is only as strong as the CO's source verification and issuing-key custody (spec §12.13).

## 8. Open Questions

- Shared claim names. COs that want interoperable derived claims (`verified_natural_person`, `employment_status`, `affiliation`, age bands, assurance levels) would benefit from a shared vocabulary; none is defined here, and a deployment should document the names it uses.
- PIV affiliation. Whether the FASC-N association category gives a dependable affiliation should be checked against the primary FASC-N specification before a CO relies on it.
- IdP assurance signals. A CO should read its IdP's documentation for the `acr` values it emits; this profile does not list them.
- Fees and timelines for EUDI registration. National registration policies set them; a CO should read its Member State's policy before planning.
- Employer lawful basis. Consent is weak in employment, and Art 5b(9) pseudonym rules interact with legitimate interest; this is for counsel.
- Remote peer presentation. If a later ARF adds it, or wallets gain a way to sign holder-chosen nonces for unregistered verifiers, a key-bound exception to spec §5.2.1.5 could be reconsidered. Neither is in ARF v3.0.0.
