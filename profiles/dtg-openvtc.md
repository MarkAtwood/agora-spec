# Profile: OpenVTC and the Decentralized Trust Graph

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-17
**Version:** 0.1 Draft
**Depends on:** ARCHITECTURE §2.2, §2.3, §2.4, §5; spec §2.1, §2.5, §2.6, §4.1, §4.3, §4.5, §4.6.3, §5.2.1, §5.2.1.1, §5.2.1.5, §6.9, §6.14, §9, §12.13, §13.1, §13.1.1, Appendix C
**Sources:** OpenVTC Verifiable Trust Infrastructure (https://github.com/OpenVTC/verifiable-trust-infrastructure, https://github.com/OpenVTC/openvtc, https://openvtc.net/); DTG Credentials, Working Draft 0.6.0 (https://trustoverip.github.io/dtgwg-cred-spec/); Trust Tasks, Working Draft 0.7.0 (https://github.com/trustoverip/dtgwg-trust-tasks-tf, https://trusttasks.org); Trust Registry Query Protocol (TRQP) v2.0 (https://trustoverip.github.io/tswg-trust-registry-protocol/) and https://github.com/affinidi/affinidi-trust-registry-rs; Trust Spanning Protocol (TSP) (https://trustoverip.github.io/tswg-tsp-specification/); ToIP Decentralized Trust Graph Working Group (https://lf-toip.atlassian.net/wiki/spaces/HOME/pages/257785857/Decentralized+Trust+Graph+Working+Group)

---

## 1. Summary

OpenVTC is an open-source (Apache-2.0) Rust implementation of the Decentralized Trust Graph (DTG) stack from the Trust over IP Foundation (ToIP) DTG Working Group, run as a Linux Foundation Decentralized Trust (LFDT) lab. It is a credential, community-membership, and personal-agent stack, not a messaging protocol: it has no chat, no calls, and no group messaging transport. Agora interoperates with it at the credential and DID layer. Everything in this profile works on the spec as written. It needs no core change.

What this profile gives:

- A client can tell a user who a stranger who just sent a DM request is, from DTG credentials in the stranger's leaf, checked against a TRQP trust registry (section 3).
- A Space can admit members on a Verifiable Trust Community's decision (section 5).
- A user's personal agent has a defined place in Agora's roles (section 6).
- Both sides already share `did:webvh` identities (section 7).

**Terminology.** In this profile **VTC** means a Verifiable Trust Community. Elsewhere in the Agora spec, VTC means video teleconferencing (spec §6). Where both could be meant, this profile writes "trust community".

## 2. The DTG Stack

| Component | What it is |
|---|---|
| Verifiable Trust Agent (VTA) | A per-person, always-on agent holding the user's keys, DIDs, credentials, personas, and policy. Keys derive from one seed into separate "trust contexts". Runs on a server or a small home device. |
| Verifiable Trust Community (VTC) | A community service that keeps a roster, admits members by policy, issues credentials, and publishes its decisions to a trust registry. |
| DTG credentials | W3C Verifiable Credentials 2.0 secured by a Data Integrity proof with the `eddsa-jcs-2022` cryptosuite. Types: membership (VMC), relationship (VRC), delegation (VDC), invitation (VIC), persona (VPC), authority (VAC), and statement (VSC), with the VSC profiles endorsement (VEC) and witnessed (VWC). Each credential declares an `issuerScope` of `pairwise`, `directed`, or `public`. |
| TRQP v2.0 | A query protocol for trust registries: is entity X authorized for action Y under governance authority Z. OpenVTC publishes VTC decisions through it. |
| Trust Tasks | A JSON request envelope (`id`, `type` URI, `payload`, `issuer`, `recipient`, `proof`) used as OpenVTC's API between agents and services. |
| TSP and DIDComm | The transports between agents. TSP is preferred, then DIDComm v2. Both route through mediators. |

**Maturity.** The DTG credential and Trust Tasks specifications are working drafts, and every Trust Task type is a draft. TSP is an experimental implementer's draft whose revisions do not interoperate. OpenVTC makes frequent breaking releases. TRQP v2.0 is the one approved ToIP deliverable here. A deployment that follows this profile pins the versions it implements, and the Agora spec references none of these artifacts.

## 3. Who Is This Stranger?

The primary use case: someone the user has never talked to adds them to a DM. Before accepting, the user wants to know who it is. Every step uses an existing spec mechanism.

1. **The adder attaches credentials.** When the stranger's client creates the DM group, it puts chosen DTG credentials in the `agora_credentials` extension of its own leaf (spec §5.2.1.5). This leaf belongs to a group the adder creates, not to a published KeyPackage, so the placement advice of §5.2.1.5 does not discourage it. Each entry carries media type `application/vc` and the credential as issued, with its embedded `eddsa-jcs-2022` proof and the DTG context, as opaque bytes. A Data Integrity credential is usually 1 to 3 KB, so a few fit in the 8 entry, 8192 byte limit (spec Appendix C).
2. **The request arrives.** The user's client receives the Welcome. The adder is not an accepted sender, so the client holds the group in the message request state (spec §4.6.3). The adder's leaf, with its credentials, is in the Welcome's ratchet tree.
3. **The client checks each entry.** For each `application/vc` entry it supports, the client verifies the Data Integrity proof by the rules of that cryptosuite, checks that `credentialSubject.id` equals the adder's leaf DID as an exact string (spec §5.2.1.5), and checks expiry and status by the credential's own rules (spec §12.13). An entry that fails any check is ignored, and the leaf stays valid.
4. **The client asks whether the issuer counts.** Issuer trust is the client's policy (spec §5.2.1.5). Under this profile that policy names one or more TRQP v2.0 registries, and the client asks each whether the credential's issuer is authorized to issue that credential type under the governance authority the policy names. A VMC from a trust community the registry recognizes says "member of that community", backed by the community's governance rather than by the stranger's word.
5. **The client looks for paths through people the user knows.** A public-scope VEC or VSC about the stranger, issued by a DID the user already knows (a contact, or the counterparty of a relationship credential the user holds), is a path from the user to the stranger. The user's own relationship credentials stay on the user's devices or in the user's VTA (section 6), and the client evaluates the path locally. Nothing about the user's relationships is sent to the stranger or to the registry.
6. **The user decides.** The client shows what it verified, for example "member of trust community X (registry R)" and "endorsed by Carol, a contact", and the user accepts, declines, or blocks (spec §4.6.3). A rule the user or device manager sets can make verified holders of a named issuer's credential accepted senders automatically, as §4.6.3 already allows. How a client shows this is the user agent's choice.

The client of a user who never installs DTG support sees an ordinary message request: an unsupported entry is ignored (spec §5.2.1.5).

A TRQP query shows the registry operator which issuer the user's client asked about, and when. It does not show the stranger's DID, unless the policy queries the stranger's own authorization. Clients can cache registry answers for as long as the registry allows.

## 4. Credential Scope

A client that follows this profile MUST NOT put a DTG credential in `agora_credentials` unless its `issuerScope` is `public` or `directed` and its `credentialSubject.id` equals the member's Agora DID, the DID of the leaf's credential (spec §5.2.1). Pairwise-scope credentials stay inside the relationship they were issued for.

Why: a credential shown to a stranger in a leaf is public by nature. Every member of every group carrying that leaf can read it, and copies of the group state outlive the member's intent. A `public` or `directed` credential was issued to be shown. A `pairwise` credential names a DID that exists for one relationship, and showing it elsewhere lets anyone who sees both contexts correlate them.

**Why not a linked-DID proof.** The rejected alternative was to let a leaf carry a credential issued to a pairwise DID, plus a proof that the pairwise DID and the Agora DID belong to the same person. That proof would publish exactly the correlation that pairwise DIDs exist to prevent. It would also change the spec, because §5.2.1.5 counts an entry only if its subject equals the leaf DID. A trust community that wants its members recognized in Agora issues them a public- or directed-scope credential to their Agora DID instead.

## 5. Space Admission by a Trust Community

A Space's CO can delegate admission to a trust community. The VTC, or an adapter in front of it, acts as a CO admission component and plugs in at the invite flow (spec §4.3) with no wire change. It is CO-side under the key test: it must know who is being admitted to do its job (ARCHITECTURE §2.3).

Either of two triggers leads to an invite:

- the applicant presents a VMC, through OpenID for Verifiable Presentations or a Trust Task, to the CO's admission endpoint; or
- the VTC admits the applicant under its own policy and tells the CO.

The admission component:

- MUST verify a presented VMC's proof, expiry, status, and holder binding before acting on it, because a presentation outside an MLS group has no leaf signature to bind it;
- MUST issue the `SpaceInvite` only with `issuedTo` set to the DID that the VMC names as its subject, and only when that DID is the applicant's Agora DID;
- MUST sign the `SpaceInvite` per spec §13.1.1 with an admin DID of the Space (spec §4.1, §4.3), held by the CO and distinct from any IO key (ARCHITECTURE §2.4).

Revoking a VMC blocks later admissions. It does not remove anyone from a Space: MLS membership is the only access control, so the CO removes the member by its usual means (spec §4.5). The VTC is never placed on the IO side, so it does not run the Space's relays under the same keys (ARCHITECTURE §2.4).

## 6. Where a VTA Fits

ARCHITECTURE §2.3 places a personal agent by what it holds: a personal agent that holds a user's keys, MLS secrets, or plaintext is one of that user's devices when the user runs it, and its host is a CO component when a provider runs it. No new role is needed.

- **Self-hosted VTA.** A VTA the user runs, on a home server or a small device, that takes part in Agora is one of the user's devices. It has its own leaf in each group, joins them by an own-device Add, and is a member of the user's self-group (spec §2.6). There it can hold the user's accepted-sender rules and block list (spec §4.6.3) and evaluate the endorsement paths of section 3 for the user's other devices.
- **Provider-hosted VTA.** A VTA a provider runs holds the user's keys and, if it takes part in groups, MLS secrets and plaintext. Its host is a CO-side component, trusted as an employer's provisioning service is trusted (spec §2.5). A trusted execution environment narrows what the operator can reach, but it does not change the classification, which depends on what the component holds.

A VTA may also host the user's KeyPackages and receive their Welcomes as the user's `KeyPackageEndpoint` (spec §2.1, §5.2.1.1). That host is CO-side already (ARCHITECTURE §2.3, KeyPackage host), and the endpoint protocol is the one the spec defines, over HTTPS.

## 7. Identities

Agora's default DID method is `did:webvh` (spec §2.1), and OpenVTC uses `did:webvh` for personas and communities. An Agora client can resolve an OpenVTC `did:webvh` DID, and a VTC can issue credentials to an Agora `did:webvh` DID, with no change on either side. OpenVTC does not support `did:plc`, so a user whose Agora DID is a `did:plc` cannot hold a DTG credential that counts in a leaf.

## 8. Out of Scope

- **More DID methods in core.** `did:peer`, `did:scid`, and `did:webs` stay out of Agora's small method set. `did:peer` is pairwise by design, which section 4 keeps out of leaves anyway.
- **KeyPackage and Welcome delivery over DIDComm or TSP.** It would add a second delivery path beside `KeyPackageEndpoint` (spec §5.2.1.1). DIDComm and TSP route through mediators, and a mediator that forwards Welcomes sees who is starting a conversation with whom. Agora would then have an observer with no declared observation budget (ARCHITECTURE §5).
- **The Trust Task envelope as a message format.** Agora messages are typed payloads inside MLS (spec §13.1). A second envelope would duplicate them.
- **JSON Canonicalization Scheme (JCS).** Agora signs exact bytes and computes no canonical form (spec §13.1.1). A DTG credential's `eddsa-jcs-2022` proof is checked by the credential verifier inside the client, by the cryptosuite's rules. Agora itself carries the credential bytes unchanged.

## 9. Openings

- **Calls.** An open Trust Tasks proposal (dtgwg-trust-tasks-tf pull request 672) adds a `communications` category for real-time call setup, with no specification yet. Agora's call coordination (spec §6.14), with ringing, lobbies, and policy as MLS messages that no server reads, and SFrame media encryption (spec §6.9), is a worked design the DTG work could reference rather than build again.
- **Gateways to VTI agents.** A CO could run a gateway that carries chat between an Agora channel and OpenVTC agents over Trust Tasks. It would be an ordinary gateway under spec §9 and `profiles/gateways.md`: a disclosed CO component that holds plaintext.

## 10. Open Questions

- Which governance authority identifiers and credential types a client's default TRQP policy should name. This is a matter for deployments and trust communities, not this profile.
- How often trust communities issue public- or directed-scope VMCs to members' own DIDs. If they mostly issue pairwise credentials, section 3 finds little to show until they add a public issuance.
- Whether spec §5.2.1.5, which says a signature is verified "over exactly those bytes", should say "by the rules of the format" for proof formats such as Data Integrity with JCS, where the verifier derives the signed form from the carried bytes. Agora still never transforms the bytes.
- Whether a VSC with predicates, proved in zero knowledge, can satisfy the subject check of §5.2.1.5. The DTG zero-knowledge profile is not settled.
