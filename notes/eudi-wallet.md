# EU Digital Identity Wallet: fit with Agora

Research note, 2026-10-17. Public sources only. Every claim cites a primary source unless it is marked **[secondary]** (press or trackers) or **[unverified]** (my own knowledge, not checked against the source today). The EU legal texts were read from the Official Journal XHTML published by the Publications Office (`http://publications.europa.eu/resource/celex/<CELEX>`), because EUR-Lex served a bot challenge.

Agora sources used: ARCHITECTURE §2 to §6; spec §3.5, §4.2, §4.3, §4.6.3, §5.2.1.5, §12.11, and §12.13; profiles/dtg-openvtc.md; profiles/o365-employer-did.md §4. Binding decisions: beads memories `agora-credentials`, `agora-credentials-defaults`, and `agora-dtg-public-scope`.

## Summary

- An EUDI credential is bound to a **key held in the user's wallet**, never to a DID. The PID rulebook defines no `sub`, the ARF never mentions DIDs, and SD-JWT VC makes `sub` optional. Under Agora's strict subject-DID rule (§5.2.1.5), no EUDI credential counts in `agora_credentials` today.
- A wallet presents only to a **registered relying party** that authenticates with an access certificate. This applies to every presentation, remote or proximity. Wallet-to-wallet presentation exists in the ARF, but only in proximity (ISO/IEC 18013-5 over NFC or BLE). An Agora client therefore cannot ask a stranger's wallet for a remote presentation.
- The workable fit is **CO-side**. The CO registers as a relying party, runs an OpenID4VP verifier, and then either issues a `SpaceInvite`, assigns a role, or issues its own derived credential whose subject is the member's Agora DID. None of these needs a core change.
- **Recommendation.** Keep the strict subject-DID rule and keep EUDI verification at the CO. Use a CO-issued derived credential when other members need to see the result. Do not add a key-bound exception to §5.2.1.5 now.

## 1. The EUDI ecosystem in plain language, as of 2026-10-17

**What it is.** Every EU Member State must give its residents a free phone wallet. The wallet holds a government identity credential, the **PID** (person identification data). It also holds other signed credentials, the **attestations of attributes** (EAA). When the issuer is a qualified trust service provider these are QEAA. When the issuer is a public body responsible for an authentic source they are PuB-EAA. The user shows credentials to online services, the **relying parties**, and chooses which attributes to reveal. The wallet also creates qualified electronic signatures and site-specific pseudonyms.

**Law.**

- Regulation (EU) 2024/1183 ("eIDAS 2.0") amends Regulation 910/2014. It inserts Art 5a (wallets), 5b (relying parties), 5c to 5e (certification, list, breaches), 5f (mandatory acceptance), and 45d to 45h (attestations). CELEX 32024R1183, OJ 30.4.2024, http://data.europa.eu/eli/reg/2024/1183/oj.
- Implementing regulations relevant to wallets and relying parties:

| Act | Subject | Notes |
|---|---|---|
| 2024/2977 | PID and EAA | |
| 2024/2979 | Integrity and core functions | Logs Art 9; embedded disclosure policies Art 10 and Annex III; relying-party-specific pseudonyms |
| 2024/2980 | Notifications | |
| 2024/2981 | Certification | |
| 2024/2982 | Protocols and interfaces | Art 3: the wallet authenticates the relying party |
| 2025/846 | Cross-border identity matching | Applies from 24.12.2026 |
| 2025/847 | Security breaches | |
| 2025/848 | Registration of wallet-relying parties | Applies from 24.12.2026 |
| 2025/849 | List of certified wallets | |
| 2025/1566 to 2025/1572 | QEAA and trust-service batch | 2025/1569 covers QEAA and PuB-EAA |
| **2026/1731** (OJ 22.7.2026) | Standards update | Amends 2977, 2979, 2980, and 2982. Brings in OpenID4VCI wallet attestations, an ISO/IEC 18013-7:2025 Annex C profile, an OpenID4VC HAIP profile, and ETSI TS 119 472-2/-3. Makes validation of registration certificates mandatory from 11 August 2028. Makes the portrait a mandatory PID attribute from 11 August 2028, unless the user opts out. |

The 2024 batch was published in OJ 4.12.2024 and entered into force 24.12.2024. The other acts are listed with their CELEX numbers in this note's sources.

**Technical framework.**

- **Architecture and Reference Framework (ARF): v3.0.0, 23 July 2026.** https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework/releases, rendered at https://eudi.dev/latest/main/. v3.0.0 aligns with the amending regulations, adds Relying Party Services, updates wallet-to-wallet interactions, and accepts Trusted Lists and LoTEs (Lists of Trusted Entities) as trust anchors. A "Topic AA" discussion paper (v0.8, 14 October) is not a release.
- **PID rulebook v1.7, 17 July 2026.** https://github.com/eu-digital-identity-wallet/eudi-doc-attestation-rulebooks-catalog, `rulebooks/pid/pid-rulebook.md`.
  - Mandatory attributes: `family_name`, `given_name`, `birth_date`, `birth_place`, `nationality`, and `portrait` (from 2028, opt-out allowed). Mandatory metadata: `issuing_authority` and `issuing_country`.
  - Optional attributes include the address set, `personal_administrative_number`, birth names, `sex`, `email_address`, and `mobile_phone_number`.
  - Formats: mdoc doctype `eu.europa.ec.eudi.pid.1`, and SD-JWT VC with `vct` `urn:eudi:pid:1`.
  - No persistent identifier is mandated, and technical PIDs are deliberately short-lived.
  - v1.7 adds that the PID private key must not sign transactional data.
  - **[unverified]** Age-over attributes (`age_over_18` and similar) are not in the v1.7 list I saw. The EU age-verification work is a separate track that I did not check.

**Credential formats and holder binding.**

| Format | Status | Holder binding | Subject identifier |
|---|---|---|---|
| SD-JWT | **RFC 9901**, Proposed Standard, November 2025 | Optional Key Binding JWT (`typ: kb+jwt`, with `iat`, `aud`, `nonce`, `sd_hash`) **[unverified detail]** | n/a |
| SD-JWT VC | **draft-ietf-oauth-sd-jwt-vc-19**, 2026-08-31, at the IESG ("Waiting for AD Go-Ahead"), no RFC number. https://datatracker.ietf.org/doc/draft-ietf-oauth-sd-jwt-vc/ | `cnf` (a JWK is recommended; `cnf` must not be selectively disclosable) plus a KB-JWT at presentation | `sub` is **optional** and may be selectively disclosable. Nothing binds `sub` to `cnf`. |
| ISO/IEC 18013-5 mdoc | Paywalled ISO standard | The MSO's `deviceKeyInfo` holds the device key. `DeviceAuth` carries a `deviceSignature` or `deviceMac` over `DeviceAuthentication`, which includes the `SessionTranscript` **[unverified, not read]**. Online, OpenID4VP Appendix B.2.6 sets the handover to `["OpenID4VPHandover", SHA-256(CBOR([client_id, nonce, jwk_thumbprint or null, response_uri]))]`. | None: the binding is to a key only |

In every EUDI format the binding is to a **key generated inside the wallet's secure hardware** (WSCA/WSCD). The user cannot export that key, and it is unrelated to any Agora device key.

**Protocols.**

- **OpenID4VP 1.0: Final, 9 July 2025.** https://openid.net/specs/openid-4-verifiable-presentations-1_0.html. It defines DCQL queries, client identifier prefixes (`x509_hash`, `x509_san_dns`, `decentralized_identifier`, `verifier_attestation`, and others), `transaction_data`, and the response modes `direct_post.jwt` and `dc_api.jwt`.
- **OpenID4VCI 1.0: Final, 16 September 2025.** https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html. It defines batch issuance (a different key per instance is recommended), key attestation, and wallet attestation.
- **HAIP 1.0: Final, 24 December 2025.** https://openid.net/specs/openid4vc-high-assurance-interoperability-profile-1_0.html.
  - Issuance: FAPI 2 with PAR, PKCE, and DPoP, plus wallet attestation.
  - Presentation: signed requests with the **`x509_hash`** prefix, DCQL, and responses encrypted with ECDH-ES P-256.
  - Formats: `dc+sd-jwt` (with `cnf.jwk`, KB-JWT, `x5c`, and a status list) or `mso_mdoc`. ES256 at minimum.
- The ARF requires HAIP compliance for OpenID4VP (Annex 2, OIA_03b, OIA_03c, and OIA_08a). The ARF text I fetched does not mention `x509_san_dns`.

**Privacy rules.**

- Selective disclosure: Art 5a(4)(a).
- Issuers learn nothing about how their attestations are used: Art 5a(5)(b).
- No party may track, link, or correlate the user after issuance unless the user authorizes it, and the framework must provide unlinkability where identification is not needed: Art 5a(16), 2024/2982 Art 3(10).
- Use of wallet data is limited and kept logically separate: Art 5a(14).
- The ARF implements unlinkability by batch issuance.
  - Methods A (once-only) and B (reuse) are mandatory, and C and D are optional (ISSU_37, ISSU_44, ISSU_49, ISSU_52, ISSU_55).
  - Batch timestamps must not reveal batch membership (ISSU_36).
- Pseudonyms:
  - The wallet can generate pseudonyms (Art 5a(4)(b)).
  - Relying parties "shall not refuse the use of pseudonyms, where the identification of the user is not required by Union or national law" (Art 5b(9)).
  - The ARF bases pseudonyms on WebAuthn (Topic 11, PA_01 to PA_22).
- Dashboard: every transaction is logged, and from the log the user can request erasure and report a relying party to the data protection authority (Art 5a(4)(d), 2024/2979 Art 9).

**Timelines.**

- **Wallets: 24 December 2026.** Art 5a(1) gives Member States 24 months from the entry into force of the implementing acts, which was 24.12.2024. This date is my computation; it matches the application date of 2025/848.
- **Relying-party registration** applies from 24.12.2026 (2025/848 Art 11).
- **Mandatory acceptance:**
  - Public bodies that require electronic identification must accept the wallet (Art 5f(1)). No separate deadline is written into that paragraph.
  - Private relying parties that law or contract requires to use strong user authentication must accept it by **about 24 December 2027**, and only when the user asks. Micro and small enterprises are exempt. Sectors include banking, telecoms, health, energy, and transport (Art 5f(2)).
  - Very large online platforms must accept the wallet on request, for the minimum data necessary (Art 5f(3)).
- **Status as of 2026-10-17 [secondary, sources disagree]:**
  - Eudigo (12 October 2026) reports no certified wallets and seven "precursor" wallets live: CY, DK, FR, GR, IT, PL, and SK. https://eudigo.eu/en/eudi-index/
  - Germany's wallet is reported for 2 January 2027 and Romania's for 14 January 2027. https://www.openideurope.eu/digital-identity/eudi-wallet-timeline/
  - I found no official Commission status page.

**European Business Wallet.**

- **Proposal:** COM(2025) 838, procedure 2025/0358(COD), 19 November 2025.
- **Who gets it:** economic operators (sole traders included), public-sector bodies, and optionally non-EU operators.
- **What it does:**
  - issue, hold, and present attestations;
  - exchange data with EUDI wallets;
  - qualified signatures and seals;
  - a mandatory qualified electronic registered delivery service with a digital address and a European Digital Directory;
  - delegation to multiple users.
- **Identifier:** the **EUID** under Directive 2017/1132 wherever one exists (Art 9). Otherwise a new identifier is defined by implementing act.
- **Effect on the EUDI wallet:** the proposal amends Art 5a so that the EUDI wallet covers natural persons only.
- **Public-sector obligation:** public bodies must accept business wallets within 24 months.
- **DIDs:** the proposal contains no occurrence of "decentralised identifier" or "did:".
- **Status:**
  - The Council reached a general approach on 9 June 2026 **[secondary]**.
  - The European Parliament's ITRE committee adopted its report on 10 September 2026 (A10-0240/2026), and plenary confirmed the negotiating mandate on 7 October 2026.
  - The Legislative Observatory shows "Awaiting Parliament's position in 1st reading" and no trilogues yet. https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0358(COD)

## 2. How an organization becomes an authorized relying party

A relying party is **registered**, not authorized. ARF §6.4.3 says registration provides transparency and grants no authorization. What a relying party may receive is limited by three things: its registered intended uses (Art 5b(3)), any embedded disclosure policy the issuer put on an attestation, and what the user approves. The steps for an enterprise or government CO are:

1. **Be an established legal entity.** A relying party registers in the Member State where it is established (Art 5b(1)). **[unverified]** I did not find how an entity established outside the EU registers.
2. **Define intended uses and a lawful basis.** List each intended use and, for each, the exact attestations and attributes it needs. The relying party may never request anything else (Art 5b(2)(c), 5b(3)). The CO is a GDPR controller for what it receives. The ARF notes that user approval in the wallet is **not** itself a GDPR legal basis (ARF §6.6.3.5).
   - For an employer, consent is weak in the employment context, so legitimate interest or a legal obligation is the likely basis. This is a GDPR judgment for counsel, not a finding.
3. **Register with the national registrar** under that Member State's published registration policy (2025/848 Art 3 and Art 4). The registrant supplies (Annex I):
   - official name and user-friendly trade name;
   - identifiers: EORI, business register number, LEI, VAT, tax reference, **EUID**, or another national identifier;
   - address, website, and contact details;
   - a description of the service;
   - for each intended use, a description and a **machine-readable list of the attestations and attributes** to be requested;
   - whether it is a public-sector body;
   - its entitlement, for example `Service_Provider`;
   - whether it uses an intermediary, and which one.

   The registrar checks the information against authentic sources and must reject what it cannot verify (Art 6). The entry is published, apart from the address, as signed JWS records in a free, unauthenticated, common REST API and on a national website (Art 3(4) and (5), Annex II). The relying party must keep the entry current (Art 5).
4. **Get an access certificate** from a certificate authority the Member State authorizes. These certificates are issued "exclusively to registered wallet-relying parties" under ETSI EN 319 411-1 NCP and ETSI TS 119 411-8 (2025/848 Art 7, Annex IV; ARF RPA_02).
   - Each **relying-party instance**, meaning each deployed verifier, gets its own certificate (ARF §3.11.3).
   - The CA monitors the register. It must publish a revocation within 24 hours, and data protection authorities and supervisory bodies can demand revocation.
5. **Get a registration certificate** if the Member State offers them. They are optional for Member States (2025/848 Art 8, Annex V).
   - Format: a JWT or CWT stating one intended use, the registered attributes, a privacy-policy URL, and a general access policy.
   - Wallets must warn the user when a request exceeds it. Validating it becomes mandatory for wallets on 11 August 2028 (2026/1731).
6. **Run a verifier** that speaks OpenID4VP 1.0 under HAIP:
   - a signed request object (JAR) using the `x509_hash` client identifier prefix, with the access-certificate chain in `x5c`;
   - a DCQL query for only the registered attributes, and a fresh `nonce`;
   - an encrypted response (`direct_post.jwt`, or `dc_api.jwt` through the browser Digital Credentials API).
7. **The wallet checks the requester** (2024/2982 Art 3; ARF §6.6.3.2 and §6.6.3.3):
   - It verifies the request signature and validates the access-certificate chain against the Commission-published LoTE of access CAs, checking revocation by CRL or OCSP. This happens on every presentation, remote or proximity (ARF RPA_01 and RPA_03).
   - It validates the registration certificate, if one is present.
   - It evaluates the attestation's embedded disclosure policy, which is either "authorised relying parties only" or "specific root of trust" (2024/2979 Annex III).
8. **The user consents** (ARF §6.6.3.5):
   - The wallet shows the relying party's trade name, the attributes requested, the intended use, the privacy-policy URL, and the results of the registration and policy checks. A portrait triggers a separate biometric warning.
   - Approval must be explicit: "silence or pre-ticked boxes do not suffice". Approving PID attributes requires user authentication to the wallet's secure element.
   - The transaction goes into the user's dashboard, from which the user can report the relying party to the data protection authority (Art 5a(4)(d)).
9. **The relying party verifies the response:**
   - the issuer's signature chain, against the PID-provider list or the trusted lists for QEAA;
   - status, by status list;
   - holder binding: the KB-JWT `aud` equals its client identifier and `nonce` equals its nonce, or the mdoc device signature verifies over the OpenID4VP SessionTranscript.

**Obligations and costs.**

- Request only registered data (5b(3)).
- Identify yourself to the user (5b(8)).
- Validate PID and EAA yourself (5b(9)).
- Do not refuse pseudonyms where the law does not require identification (5b(9)).
- An intermediary counts as a relying party and must not store transaction content (5b(10)).
- The registrar may suspend a relying party that requests more than it registered (2025/848 Art 9).
- Use of the wallet is free for natural persons (5a(13)).
- Registration must be "cost-effective and proportionate-to-risk" (5b(2)). 2025/848 sets no fee rule, so **registration and access-certificate fees are national or commercial and unknown**.
- A typical Agora CO is not obliged to accept the wallet. A government CO that requires electronic identification must accept it (5f(1)), and so must a private CO in a regulated sector (5f(2)).

## 3. Fit with Agora, by use case

### (a) Space admission by a CO acting as a registered relying party

**Fit: good, CO-side, no core change; a profile would suffice.**

The CO's Space endpoint or invite service already decides who receives a `SpaceInvite` (§4.3), and it already authenticates callers by DID (§3.5). A verifier sits beside it:

1. The joining client proves its DID to the CO service, by `MemberAuth` or an equivalent signed request.
2. The CO verifier sends an OpenID4VP request for the registered attributes. For example, `nationality`, or proof of being a natural person resident in a given state. The request goes same-device or through the DC API, or cross-device by QR code.
3. The CO sets the OpenID4VP `nonce` to include a hash of the caller's DID and the session. That links the wallet's KB-JWT or mdoc device signature to this join attempt in the CO's records.
4. On success the CO issues a `SpaceInvite` with `issuedTo` set to that DID, and optionally a role (§4.2).

Agora never sees EUDI bytes, and Space state carries no credential policy (§4.2).

Cross-device flows are open to relay phishing: someone else's wallet scans the QR code. Mitigations are to prefer same-device or DC API flows and to show the DID in the request's intended-use text. This is a known OpenID4VP risk, not an Agora one.

### (b) Enterprise or government instances viewing members' credentials

**Fit: good under Mark's guidance; this is ordinary relying-party behavior.**

The CO registers each intended use, for example "verify employee identity at enrollment" or "verify citizen eligibility for this service". It receives the disclosed attributes and keeps them under its GDPR controller duties and retention policy.

Spec §12.11 already says that every group member, including a compliance logger, sees any `agora_credentials` claims, so a CO that is a group member sees leaf credentials anyway. Three constraints still apply:

- The CO may request only what it registered.
- A user's wallet will warn about, and may let the user refuse, anything beyond the registration certificate.
- A government CO must honor pseudonyms unless law requires identification (5b(9)). An enterprise CO falls under the same Art 5b(9) rule only where it is a wallet-relying party.

### (c) "Who is this stranger who DMed me" between ordinary users

**Fit: not with EUDI directly.**

- **No remote peer presentation.** The ARF's wallet-to-wallet feature is proximity only, using ISO/IEC 18013-5 (Topic 30, W2W_08). It is user-initiated (W2W_05), rate-limited, and must not store what it receives (W2W_17, W2W_21). Remote presentation requires a registered relying party with an access certificate (RPA_01). An ordinary Agora client is not one, so the stranger's wallet will not produce a fresh presentation addressed to the recipient.
- **Privacy.** The PID's minimum is legal name, birth date, birthplace, and nationality, and from 2028 a portrait. Showing that to a stranger exposes far more than "this is a real person". It also defeats the unlinkability the regulation demands, because one presentation stored in a leaf is reused across groups.
- **What works instead.** A CO, or a dedicated "identity check" CO, verifies the user's PID as a relying party (use case a). It then issues its own **derived credential** to the user's Agora DID: an SD-JWT VC with `sub` set to the DID and minimal claims, such as `verified_natural_person: true`, an age band, or a country. The stranger's client checks it under §4.6.3 and §5.2.1.5 like any other credential.
  - The trust is in that CO, not in the EU trust lists. This should be stated plainly to users.
  - It fits the DTG public-scope decision: a credential shown to a stranger is public by nature.

### (d) Employer and business identity: European Business Wallet vs Agora's employer DID profiles

**Fit: complementary; watch, no change now.**

The European Business Wallet is still a proposal. Parliament has a negotiating mandate, but trilogues have not started. It identifies organizations by EUID and does not mention DIDs. Agora's O365 and Google Workspace profiles identify the employer by an org root DID and issue an `EmployeeCredential` whose subject is the employee's DID.

Two plausible joins once the regulation lands:

1. **Organization level.** A CO, or a member's client, verifies a business-wallet presentation of the organization's EUID and legal name. It then records that the org root DID belongs to that EUID, which would need a signed link or a derived credential.
2. **Employee level.** The business wallet issues employment or mandate attestations to employees' EUDI wallets. These are key-bound like any EAA, so they enter Agora the same way as in use cases (a) or (c).

Neither join needs a core change.

### (e) Carrying EUDI credentials in `agora_credentials`

**Fit: not under current rules, and not recommended to force.**

- **Subject check.** The PID and EUDI attestations have no subject DID, so they fail the subject check (§5.2.1.5), as the `agora-credentials-defaults` decision anticipated for key-only bindings.
- **No usable fresh presentation.** A user cannot get a fresh KB-JWT or mdoc device signature addressed to an Agora group without a relying party in the loop, because the wallet signs only for authenticated relying parties. HAIP responses are also encrypted to the verifier, so the user's Agora client does not receive the presentation unless the CO returns it.
- **Wrong reuse model.** Placing one presentation in a leaf shown to many groups contradicts once-only batch use (Method A) and the unlinkability rules.
- **Media types.**
  - `application/dc+sd-jwt` is the type SD-JWT VC registers, and the draft is not yet an RFC.
  - **[unverified]** I could not confirm `application/mdoc`, which spec §5.2.1.5 cites as an example, as an IANA-registered media type. It should be checked before it stays in the spec.

## 4. Conflicts with current Agora decisions, and options

**Conflict 1: strict subject DID = leaf DID.** EUDI credentials are bound to a wallet key, not to a DID, so they never count.

**Conflict 2: no holder proof required, because the leaf signature binds.** The no-holder-proof default works only because the subject DID ties the credential to the leaf. A key-bound credential has no such tie. Without a holder proof, anyone who has seen a presentation could replay it into their own leaf.

**Options.**

- **A. Keep EUDI on the CO side only, and issue derived DID-bound credentials when members need to see a result.**
  - The CO, as a registered relying party, verifies by OpenID4VP. It then acts on the result through invites or roles, or issues its own credential with subject = member DID.
  - No core change, and it satisfies both decisions.
  - Cost: trust shifts from EU trust lists to the CO, and the CO holds PID data.
- **B. Accept key-bound credentials with a holder-binding proof bound to the MLS group and leaf.**
  - Add a §5.2.1.5 exception: an entry whose format has no subject identifier counts if it carries a holder proof made with the credential's `cnf` key whose `nonce` (or `aud`) commits to the leaf. For example, `nonce = SHA-256("agora leaf binding" || group_id || leaf signature_key)` in an SD-JWT KB-JWT, or the same value in the mdoc SessionTranscript.
  - Binding to the leaf's signature key rather than to the epoch keeps the proof valid across epochs, but limits it to one group. Binding to the epoch would force a fresh wallet presentation on every Commit.
  - Cryptographically sound in principle, but unworkable with EUDI wallets today:
    - the wallet signs only for an access-certificate-authenticated relying party, which chooses the nonce and `aud`;
    - HAIP encrypts the response to that relying party;
    - each group would need a fresh wallet interaction;
    - every member would see the full disclosed claims, typically a legal name.
  - It only works with the CO as relying party passing the presentation back, which is option A with extra exposure.
  - It would also reverse a recorded decision (`agora-credentials-defaults`), which is Mark's call.
- **C. Allow key-bound credentials with no holder proof.** Rejected. Anyone who has seen a presentation could copy it into their own leaf, which the subject check exists to prevent (§12.13).

**Recommendation: option A.** Record in a short profile, for example `profiles/eudi-wallet.md`, that EUDI verification is a CO relying-party function, and define the derived credential's minimal claims. Revisit option B only if the ARF adds remote peer presentation, or wallets gain a way to sign holder-chosen nonces for unregistered verifiers. Neither is in ARF v3.0.0.

**Plain explanation:** EU wallet credentials prove "the phone that holds this key belongs to a verified person", not "this Agora account belongs to a verified person", and the wallet will only talk to organizations registered with their government. So the organization running the Agora community checks the EU credential itself, and then vouches for the Agora account with its own credential that other members can verify.

## 5. Operator-separation check (ARCHITECTURE S1 to S9)

- **The relying party is the CO's verifier service.** It holds personal data and acts on community membership, so it is a CO component under the key test (ARCHITECTURE §2.3). It may be the CO's Space endpoint, invite service, or enrollment service.
  - An intermediary acting for it is a relying party under Art 5b(10) and a CO processor. It is not an IO.
  - The access-certificate key is CO key material and is distinct from any IO key (§2.4).
- **IOs learn nothing.**
  - The OpenID4VP exchange runs between the user's wallet and the CO verifier over HTTPS, outside relays (S1, S6).
  - Leaf credentials travel only in `PrivateMessage` handshakes, which relays never see (spec §5.2.1.5).
  - No relay, SFU, TURN, sequencer, or push proxy is involved.
- **No new IO obligations.** An IO must not require EUDI verification as a condition of service (S7). It never sees admission decisions, only admission keys, which stay unchanged (S2, S3).
- **Community state remains CO-signed.** An invite or role assignment based on EUDI is an ordinary CO-signed record (S4). Space state carries no credential policy (spec §4.2).
- **Replaceability holds.** Changing IOs does not touch relying-party registration or derived credentials (S5).
- **Membership stays in MLS (S9).** The verifier must not become a parallel membership list. It records verification events, not group membership.
- **Residual leak.** A client checking the status list of a derived credential, or of an EUDI credential, reveals its activity to the list host. Spec §12.11 already advises fetching whole lists. EUDI status lists are run by issuers, and Art 5a(5)(b) forbids issuers from learning about usage. Whole-list fetching is consistent with that rule.

## 6. Risks, unknowns, and licensing

**Risks and unknowns.**

- **Wallet availability.** No certified wallet exists yet [secondary]. The legal deadline of 24 December 2026 will likely be met unevenly, with Germany in January 2027 [secondary].
- **Fees.** Registration and access-certificate fees are set nationally and are unknown, as are processing times. Each Member State's registration policy (2025/848 Art 4) must be read for the CO's country.
- **Non-EU COs.** I found no path for a CO established outside the EU [unverified].
- **Registration certificates** are optional per Member State until wallets must validate them in August 2028. Until then, over-asking warnings may not appear.
- **Pseudonyms.** Art 5b(9) may require a CO acting as relying party to accept a pseudonym where law does not require identification. That limits "verify real identity to join" designs for non-government COs. The interaction with an employer's legitimate interest is a legal question.
- **SD-JWT VC is not yet an RFC.** HAIP pins draft-13 while the current draft is -19, so wire details may move.
- **ISO/IEC 18013-5** is paywalled. The mdoc details above come from OpenID4VP Appendix B and my own knowledge.
- **Unchecked sources.**
  - I did not read ARF chapters 4 and 5 or every annex for DID mentions. Chapters 3 and 6 and Annex 2.02 contain none.
  - Age-over attributes in the PID are unconfirmed.
- **Derived-credential risk.** A CO-issued "verified" credential is only as strong as the CO's verification and key custody. It carries no EU legal status: it is not a QEAA unless the CO is a QTSP.
- **Phishing.** Cross-device OpenID4VP can be relayed by an attacker who shows the victim's QR code to a third party. Prefer same-device or DC API flows.

**Licensing, as written.**

- **ARF:** CC BY 4.0, per the repository README and LICENCE file. I did not check the rulebooks catalog's license.
- **OpenID4VP and OpenID4VCI:** "Copyright (c) 2025 The OpenID Foundation". The notice grants a non-exclusive, royalty-free, worldwide copyright license to reproduce, adapt, and distribute the document for developing and implementing specifications, with attribution and no implied endorsement, and refers to the OpenID patent promise (OpenID4VP Appendix G). I did not read the OpenID4VCI and HAIP notices.
- **IETF (RFC 9901, SD-JWT VC draft)** **[unverified]**: IETF Trust copyright under BCP 78 and the Trust Legal Provisions, code components under the Revised BSD License, and IPR disclosures under BCP 79.
- **ISO/IEC 18013-5 and 18013-7** **[unverified]**: ISO/IEC copyright, sold, no free redistribution.
- **ETSI** (EN 319 411-1, TS 119 411-8, TS 119 472, TS 119 475) **[unverified]**: free download, ETSI copyright.
- **EU legislation (Official Journal)** **[unverified]**: reusable under Commission Decision 2011/833/EU.
