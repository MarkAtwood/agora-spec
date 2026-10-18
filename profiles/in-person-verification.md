# Profile: In-Person Verification

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-17
**Version:** 0.1 Draft
**Depends on:** spec §2.1, §2.2, §3.3, §4.6, §4.6.3, §5.2.1, §5.2.1.5, §12.11, §12.13, §13.1, §13.2, §13.3
**Sources:** W3C Verifiable Credentials Data Model 2.0 (https://www.w3.org/TR/vc-data-model-2.0/); W3C Data Integrity EdDSA Cryptosuites v1.0, `eddsa-jcs-2022` (https://www.w3.org/TR/vc-di-eddsa/); DTG Credentials, Working Draft 0.6.0 (https://trustoverip.github.io/dtgwg-cred-spec/); Trust Tasks ceremony `mutual-attestation/0.1`, merged in trustoverip/dtgwg-trust-tasks-tf PR 207 (https://github.com/trustoverip/dtgwg-trust-tasks-tf/blob/main/ceremonies/mutual-attestation/0.1/ceremony.json); RLTP Encounter Layer, real-life-org (https://github.com/real-life-org/trust-protocol, formerly rltp-spec); `profiles/dtg-openvtc.md`

---

## 1. Summary

Two people meet. Each phone shows a QR code, and they scan each other's. After that, each knows it holds the other's real Agora DID and current device key, so no operator or attacker has substituted a key between them. This is the safety-number check of other messengers, applied to a DID. Each then issues the other a credential saying "I verified this DID in person on this date", which the holder can carry in `agora_credentials` (spec §5.2.1.5).

The credential serves the "who is this stranger" question: when a stranger's leaf carries in-person credentials from people the user already trusts, a client can show that (section 5).

Everything here works on the spec as written. It needs no core change.

What an exchange proves, and what it does not:

- It proves that each scanned device key is listed in the counterpart's DID document at the version the counterpart stated, and that the document each side resolves is that version or descends from it. It proves that the counterpart's device holds the private key for that key only once a valid `Reveal` from it arrives (section 3.2); an exchange without a received, valid `Reveal` proves the listing but not possession. A key substituted by a DID host, a KeyPackage host, or a network attacker fails the check.
- It covers only the keys the counterpart's DID document listed at the stated version. A key added to the document after that version is not verified by the exchange (section 3.4).
- It does not prove physical presence. A channel can be relayed (section 8). The person who looks at the other's face and at what the client shows is the final check.
- It says nothing about who the person is beyond "the holder of this DID, whom I met". It carries no name, no age, and no attribute.

## 2. Threat Addressed

A client learns a contact's keys by resolving the contact's DID (spec §2.1). For `did:webvh` without witnesses, whoever holds an update key or serves the log can show one resolver a different valid log, a split view, or an old prefix of it (spec §2.1). A split view can list an extra device key that the attacker holds next to the real ones. For `did:key`, the document cannot be substituted, but the DID itself can, for example in a contact card relayed by a third party. In each case the user talks, end to end encrypted, to the wrong key.

Checking one device key against the resolved document misses the added-key case, because the real key is still listed. This profile therefore binds the whole document version: the presenting device states the version of its own DID document, and the scanning device confirms that the version it resolved is that version or a later version that descends from it, and treats any key added after that version as not verified by this exchange (section 3.4).

## 3. The Exchange

Call the two parties A and B. Every step is symmetric unless it says otherwise.

### 3.1 The QR Code

Each device generates a fresh 32-byte nonce from a CSPRNG and shows a QR code whose content is the UTF-8 JSON object:

| Member | Value |
|---|---|
| `type` | `"urn:agora:profile:in-person-verification:v1:qr"` |
| `kid` | DID URL of the device key that signs for this exchange, for example `did:webvh:QmSCID...:example.com:alice#keys-1`. Its DID is the party's Agora DID. |
| `pk` | That key's raw 32-byte Ed25519 public key, base64url without padding |
| `ver` | The version of the DID document the device holds: the `versionId` of the latest log entry for `did:webvh`, the CID text form of the latest operation for `did:plc`, and the empty string for `did:key` |
| `c` | The nonce commitment, base64url: `SHA-256(IPVCommit)` (section 3.3) |

The QR code carries a commitment to the nonce, not the nonce. Section 3.5 says why. A device MUST NOT reuse a nonce, and completes at most one exchange per nonce. To verify several people, it shows a fresh code for each.

The `kid` key is an `authentication` key of the party's DID, a device key (spec §2.1, §2.2). For `did:key`, it is the identity key.

Each device scans the other's code if it can. When both scan, the exchange is in **mutual-scan mode**. When only one can, for example because one device has no camera, it is in **one-scan mode**, and section 3.5 applies. When neither scans, there is no exchange.

### 3.2 The Reveal

The devices then exchange one `Reveal` message each, as an MLS application message in a DM between the two users (spec §4.6). An existing DM serves. Otherwise a device that scanned the other's code starts one with the scanned DID. A receiving user who did not scan sees a message request (spec §4.6.3) and accepts it as part of the exchange.

The envelope `type` is `urn:agora:profile:in-person-verification:v1:Reveal` and its `contentType` is `application/json` (spec §13.1, §13.2). The body is a JSON object with the members `kid`, `pk`, `ver`, `nonce`, and `peer`. `kid`, `pk`, and `ver` are as in the QR code, `nonce` is base64url, and `peer` is the `c` of the code the sender scanned, present only if the sender scanned one.

The DM need not be trusted. Every value it carries is checked against what was scanned, or against the SAS.

A device that follows this profile:

- MUST process a `Reveal` only if it scanned the sender's code, or the `Reveal`'s `peer` equals its own `c`. If it scanned a code in this exchange, it MUST process only the `Reveal` whose `kid` equals that code's `kid`.
- If it scanned the sender's code, MUST abort unless the `Reveal`'s `kid`, `pk`, and `ver` equal the scanned ones and `SHA-256(IPVCommit)` over the revealed nonce equals the scanned `c`.
- MUST discard a `Reveal` whose MLS sender's leaf is not bound to the `Reveal`'s `kid`, and process it no further. For `did:webvh` and `did:plc`, the leaf is bound when its `signature_key` equals `pk`, the key of the `kid` verification method (spec §5.2.1). For `did:key`, whose leaf `signature_key` is never the identity key, the leaf is bound when its `agora_device_binding` extension verifies under `pk`, the key the DID encodes (spec §5.2.1).
- If it did not scan the sender's code, MUST NOT send its own `Reveal` until it has received and processed the sender's. This orders a one-scan exchange so that the non-scanning side's nonce is revealed only after the other side's tuple is fixed.

The sender signs the `Reveal` with its leaf key, so a processed `Reveal` proves that the sender's device holds the private key for `kid` or, for `did:key`, a leaf key that `kid`'s key has bound.

In mutual-scan mode the `Reveal`s need not be sent at the meeting. The scans already authenticated the tuples, so the two devices can finish over the network later. The binding rule above applies to a late `Reveal` too, so possession of the `kid` key is proven when the valid `Reveal` arrives. An exchange in which a device has not received a valid `Reveal` proves that the scanned key is listed in the counterpart's DID document, but not that the counterpart holds it.

### 3.3 The Anchor

Both devices compute the anchor from the two parties' tuples. The encoding is the TLS presentation language with the variable-length vectors of RFC 9420 §2.1.2, as in spec §5.2.1.5 and §2.6:

```
struct {
    opaque kid<V>;          /* DID URL of the device key, UTF-8 */
    opaque public_key<V>;   /* raw Ed25519 public key, 32 bytes */
    opaque version<V>;      /* `ver` as UTF-8; empty for did:key */
    opaque nonce<V>;        /* 32 bytes */
} IPVParty;

struct {
    opaque label<V>;        /* "agora-profile/in-person-verification/v1/anchor" */
    IPVParty first;
    IPVParty second;
} IPVAnchorInput;

struct {
    opaque label<V>;        /* "agora-profile/in-person-verification/v1/commit" */
    opaque nonce<V>;        /* 32 bytes */
} IPVCommit;
```

`anchor = SHA-256(IPVAnchorInput)`. `first` is the party whose `kid` is lower in bytewise lexicographic order of its UTF-8 bytes, where a proper prefix sorts first. A device MUST abort if the two `kid`s name the same DID. Labels are UTF-8 with no terminator.

Neither party alone chooses the anchor: each contributes a nonce committed before the other's is known. The labels do not collide with any label in the spec's registry (spec §13.3), and the `agora-profile/` prefix keeps them out of the spec's own label space.

### 3.4 The Key Check

Each device resolves the other's DID per spec §2.1 and MUST abort unless:

1. for `did:webvh` or `did:plc`, the scanned or revealed `ver` names an entry in the verified log (a `did:webvh` entry with that `versionId`, or a `did:plc` operation with that CID), and the current document is that version or descends from it;
2. the document at that version, and the current document, both contain a verification method whose `id` equals `kid`, which holds the Ed25519 key `pk` and is referenced from `authentication`; and
3. for `did:key`, `pk` is the key the DID encodes.

The device MUST identify every key added to the counterpart's DID document after `ver`: each key referenced from `authentication`, `assertionMethod`, or `keyAgreement` in the current document that was absent from the document at `ver`. It MUST treat those keys as not verified by this exchange. A client may show them, so that the user can check them with the counterpart. The credential's evidence and claims cover only the keys present at `ver` (section 4.2).

The check binds the keys as they were at that version. A later change to the counterpart's DID document does not invalidate the credential, which is about the DID, but the key binding becomes stale (section 8).

### 3.5 The Short Authentication String

In one-scan mode, the device that did not scan received the other side's tuple over the network, so an attacker could have replaced it. Both devices therefore show a short authentication string (SAS):

`SAS` = the first 4 bytes of the anchor read as a big-endian unsigned integer, modulo 1,000,000, written as 6 decimal digits with leading zeros.

A device shows the SAS when it did not scan, or when the counterpart's `Reveal` has no `peer`. A device that did not scan MUST NOT issue a credential unless its user has confirmed that the SAS matches the one on the other device. A mismatch ends the exchange.

**What 6 digits give.** An attacker that replaces the scanning side's `Reveal` must fix its tuple, including its nonce, before the non-scanning side reveals its nonce (section 3.2), and that nonce is bound by the commitment the scanning side read optically. The attacker therefore gets one guess per exchange, succeeding with probability about 10^-6, and a failed guess shows as a mismatch to both people. This is why the QR code carries a commitment. If it carried the nonce, an attacker who can see the screen and also controls the network could try nonces offline until the SAS matched. Trying a million SHA-256 inputs takes well under a second.

The scanning side's own view is already authenticated by its scan, so it needs no SAS for its own safety. It shows the SAS so the other person can compare.

### 3.6 Issuance

When the checks pass, and in one-scan mode the SAS is confirmed, each client issues the other a credential (section 4) once its user confirms that the person present is the one the client shows. It sends that credential to the subject in the same DM, as an application message whose envelope `type` is `urn:agora:profile:in-person-verification:v1:Credential`, whose `contentType` is `application/vc`, and whose `body` is the credential's exact bytes.

A receiving client MUST check that the credential's issuer is the counterpart's DID, its subject is its own DID, its evidence anchor equals the anchor it computed, and its proof verifies (section 4.3). It then keeps the credential locally (section 7).

The two credentials together are the mutual attestation: each is signed by its issuer over the same anchor. No separate signature over the anchor is exchanged. The rejected alternative added each counterpart's anchor signature to the credential's evidence. It cost another round and another signature format, and proved nothing more to a third party: the issuer's proof already signs the anchor, and the holder's leaf signature already shows the holder accepts the credential (spec §5.2.1.5).

## 4. The Credential

### 4.1 Format

The credential is a W3C VC 2.0 secured with a Data Integrity proof using the `eddsa-jcs-2022` cryptosuite. In `agora_credentials`, its `media_type` is `application/vc` and its `credential` bytes are the credential as issued, with the proof embedded (spec §5.2.1.5).

Why `eddsa-jcs-2022` rather than `application/vc+jwt`: DTG credentials use it (DTG Credentials §Base Structure) and so does OpenVTC tooling (`profiles/dtg-openvtc.md` section 2), as do RLTP encounter credentials. It needs no RDF processing, so it verifies offline. It derives its signed form from the exact bytes Agora carries (spec §5.2.1.5). And it is the format of `profiles/dtg-openvtc.md` section 3, so one verifier serves both profiles.

### 4.2 Contents

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://registry.trustoverip.org/dtg/context/v1"
  ],
  "type": ["VerifiableCredential", "DTGCredential", "RelationshipCredential", "InPersonVerificationCredential"],
  "issuer": "did:webvh:QmSCIDa...:example.com:alice",
  "issuerScope": "directed",
  "validFrom": "2026-10-17T15:04:05Z",
  "credentialSubject": { "id": "did:webvh:QmSCIDb...:example.org:bob" },
  "evidence": [{
    "type": ["InPersonVerification"],
    "anchor": "base64url...",
    "parties": [
      { "kid": "did:webvh:QmSCIDa...:example.com:alice#keys-1", "pk": "base64url...", "ver": "7-QmEntry...", "nonce": "base64url..." },
      { "kid": "did:webvh:QmSCIDb...:example.org:bob#keys-3", "pk": "base64url...", "ver": "12-QmEntry...", "nonce": "base64url..." }
    ]
  }],
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "did:webvh:QmSCIDa...:example.com:alice#keys-1",
    "proofPurpose": "assertionMethod",
    "created": "2026-10-17T15:04:05Z",
    "proofValue": "z..."
  }
}
```

- `issuer` is the issuer's Agora DID, and `credentialSubject.id` is the counterpart's Agora DID, so the entry counts under spec §5.2.1.5 in the subject's leaf.
- `type` makes it a DTG relationship credential (VRC), with one added type naming what kind of relationship it is. RLTP adds `EncounterCredential` to the same base types in the same way.
- `issuerScope` is `directed`: in DTG terms, known to "a set of counterparties the holder chooses". That matches selective publication (section 7). `pairwise` would bar it from leaves under `profiles/dtg-openvtc.md` section 4.
- `validFrom` is the time of the exchange. There is no `validUntil`: a meeting does not expire. `credentialStatus` is optional (section 8).
- `evidence` holds the anchor and both `IPVParty` tuples in the order of section 3.3, with binary values in base64url (spec §13.1). A verifier can recompute the anchor and see which subject device key and document version were checked. The nonces were single use and reveal nothing.
- The proof's verification method MUST be referenced from `assertionMethod` in the issuer's current DID document, or the entry matches no issuer DID (spec §5.2.1.5). Spec §2.1 describes a user document with `authentication` and `keyAgreement` keys. A user who issues these credentials also lists a key under `assertionMethod`, for example by referencing a device key from both relationships. A `did:key` document already lists its key under both.

A credential is roughly 1.3 to 1.8 KB, depending on DID length, so several fit within the 8192-byte limit (spec §5.2.1.5).

### 4.3 Verification

A client that follows this profile and finds an entry with this type in a leaf:

- MUST apply the subject, issuer, and `assertionMethod` rules of spec §5.2.1.5 against the issuer DID's current document, resolved per spec §2.1, and verify the `eddsa-jcs-2022` proof. The signing key MUST be listed under `assertionMethod` in that document now; a key listed only at `validFrom` does not count.
- MUST NOT treat the entry as an in-person verification unless `evidence` holds exactly one object whose `type` includes `InPersonVerification`, its `parties` has two tuples whose `kid` DIDs are the issuer and the subject, and `anchor` equals the anchor recomputed from `parties` per section 3.3.
- MAY check, by historical resolution, that each tuple's key was an `authentication` key of its DID at the stated version. Doing so confirms the issuer's key check rather than taking the issuer's word for it.

A failing entry is ignored, and the leaf stays valid (spec §5.2.1.5).

## 5. Who Is This Stranger

A stranger adds the user to a DM. The stranger's leaf carries in-person credentials from Carol and Dave. The user's client verifies them (section 4.3) and finds that Carol is someone the user trusts, perhaps someone the user verified in person themselves. It can then show that Carol verified this person in person on a given date. It cannot say anything about Dave unless the user's policy covers Dave.

Which issuers count is the client's policy, set by the user or by whoever manages the device (spec §5.2.1.5, §12.13). The natural policy is the user's own contacts, or the people the user has verified in person. A credential from a DID the user does not know proves nothing: anyone can create DIDs that "met" each other. Fabricating many identities is cheap. What is hard is attaching a credential from a specific person the user already knows.

A Space's `trustedAttesters` (spec §3.3) is meant for organizations such as registered identity verifiers. A CO could list a person's DID there, for example an organizer of a small community who verifies members face to face, but that is unusual. A listed DID is trusted for every credential it issues, not only in-person ones, and the list holds at most 32 DIDs.

How a client shows this is the user agent's choice. A client may show the verifiers the user trusts and the dates, may mark a contact whose key binding has gone stale since the user's own verification (section 8), and may offer to verify in person when it meets a contact the user has never verified. A client that finds no credential shows nothing: the absence of a credential proves nothing (spec §12.13).

## 6. OpenVTC and DTG Mapping

The DTG Trust Tasks registry defines `mutual-attestation/0.1`, "In-person mutual attestation": two people meet, confirm each other, and each issues the other a credential. This profile is an Agora enactment of that shape.

| DTG `mutual-attestation/0.1` | This profile |
|---|---|
| Roles `first-person` and `second-person`, unordered | A and B; section 3.3 orders the tuples by `kid` only to compute the anchor |
| Steps `attest-first` and `attest-second`, each of type `https://trusttasks.org/spec/credential-exchange/issue/0.1`, with no `prev` | The two `Credential` messages of section 3.6, in either order |
| `anchor.kind` `coDerived`, `boundBy` both roles: "a scanned code, a key agreement, a compared short authentication string" | The anchor of section 3.3, from two committed nonces, scanned codes, and the SAS in one-scan mode |
| `evidence.level` `countersigned` | Both credentials sign the same anchor |
| `maxDuration` `PT1H` | No time limit; in mutual-scan mode the network leg may finish later (section 3.2) |
| `enactmentPrivacy` `blinded` | Not blinded: the anchor appears in plaintext (section 7) |

The credential is a DTG VRC (section 4.2) secured as DTG credentials are, so a DTG verifier can check its proof and see an ordinary relationship credential. A user with a Verifiable Trust Agent can keep received credentials there (`profiles/dtg-openvtc.md` section 6). Section 3 of `profiles/dtg-openvtc.md` evaluates these credentials alongside other DTG credentials: an in-person credential from a contact is a path from the user to the stranger.

Differences from DTG and RLTP practice:

- **Scope.** DTG recommends `pairwise` for VRCs, and RLTP encounter credentials require it. This profile uses `directed`, because the credential is issued to Agora DIDs so that it can be shown in Agora groups.
- **Anchor in the credential.** DTG blinds the enactment identifier in step documents, so that the anchor cannot correlate two credentials meant to stand alone. That blinding gains nothing here: both credentials name both DIDs in plaintext. RLTP makes the same point about its own binding (RLTP-ENC-5340).
- **Not an RLTP encounter credential.** RLTP's credential has a closed schema (`credentialSubject.format`, `ceremony`, `challenge`, `enactmentBinding`), computes its binding as SHA-256 over JCS of the ceremony identifier and the sorted challenges, and forbids `credentialStatus`. An RLTP verifier will not accept this credential, and this profile does not accept RLTP's as an in-person verification.

**Unverified:**

- How DTG derives the enactment identifier from a co-derived anchor. The ceremony says only that "the enactment identifier is derived from it".
- Whether the payload of `credential-exchange/issue/0.1` carries a credential unchanged, so that an OpenVTC agent could deliver or receive this credential as a Trust Task.
- Whether OpenVTC tooling accepts a VRC with an added type, `issuerScope` `directed`, and the VC 2.0 `evidence` member. The DTG Credentials text read for this profile does not use `evidence`.
- Whether `countersigned` in the DTG sense, "every participant signs the transcript", is met by two credentials over one anchor.

## 7. Privacy

- **A credential in a leaf shows every member of that group whom the holder met, and when** (spec §12.11). It also names the issuer, who did not choose that audience. A client that follows this profile keeps in-person credentials locally by default and puts one in a leaf only when its user chooses, for a group where it helps, such as a DM with a stranger.
- **KeyPackages.** A client SHOULD omit them from published KeyPackages (spec §5.2.1.5).
- **Linkability.** Identical credential bytes in several groups let their members link the holder across them (spec §12.11). A Data Integrity credential cannot be presented selectively, so this is the price of carrying one. An issuer that cares can issue several credentials for one meeting, each with its own proof, but they still name the same two DIDs.
- **The anchor** links the two credentials of one meeting. They name each other's DIDs anyway, so it adds nothing a reader cannot already see.
- **Operators see nothing new.** The QR codes never leave the room. The DM is MLS-encrypted, and its handshake messages are `PrivateMessage`s (spec §5.2.1). Relays see that a DM carries traffic, never its content.

## 8. Security

- **Shoulder surfing.** A QR code carries only public values: a DID, a public key, a document version, and a commitment. Photographing one reveals nothing secret. An onlooker can race the real scanner with its own `Reveal`, which ends that exchange as a mismatch or a check failure; the two people start again with fresh codes.
- **Relay.** Someone who relays one code to a distant device in real time, but not the reverse, fails mutual-scan mode, because the distant device cannot scan the local one. In one-scan mode such a relay fails at the SAS. A two-way real-time relay, where both cameras see relayed screens, defeats any optical exchange, including this one. The defense is the human check: each person confirms that the person in front of them is the one their client shows. A client that follows this profile does not claim physical presence.
- **SAS length.** Six digits give an attacker one chance in about a million per exchange (section 3.5). Fewer digits trade security for convenience. More than six add little, because a failed guess is visible.
- **Key rotation.** The exchange binds the keys and document version as they were. When the counterpart later adds or removes a device or rotates keys, the DID-level credential still stands, and the key binding is stale. The verified DID log carries trust forward from the checked version through entries signed by authorized update keys (spec §2.1), but it does not protect against a later split view. A user who wants that assurance verifies in person again.
- **Lost or compromised devices.** A verifier checks the proof against the issuer DID's current document (section 4.3), so a credential verifies only while its signing key is listed under `assertionMethod`. Removing a key from the document therefore invalidates everything it signed, including credentials that an attacker holding the key backdates with an earlier `validFrom`. The tradeoff is that the issuer's honest credentials signed by that key stop verifying too. When an issuer rotates or removes its assertion key, its client may re-issue its in-person credentials to those contacts over their DMs, signed with the new key.
- **Revocation.** Optional. An issuer that runs or uses a status list can include a `credentialStatus` entry, such as a W3C Bitstring Status List entry, and verifiers check it by the format's rules (spec §5.2.1.5). Most people will not run one. Checking status can reveal the holder's activity to the list's host, so verifiers fetch and cache whole lists (spec §12.11).
- **False claims.** An issuer can issue a credential without meeting anyone, or a compromised issuer key can. That is the trusting client's risk (spec §12.13), and it is why section 5 counts only issuers the user already trusts.

## 9. Open Questions

- **Type and label namespace.** The `urn:agora:type:` namespace is reserved for the spec (spec §13.2), so this profile uses `urn:agora:profile:`. Should the project reserve that prefix explicitly, or should profiles use HTTPS IRIs? Should profile labels be listed in the spec's registry (spec §13.3) to rule out future collisions?
- **`assertionMethod` for individuals.** Spec §2.1 describes user DID documents with `authentication` and `keyAgreement` keys only. Should it say that a user MAY also list keys under `assertionMethod` for issuing credentials? Every user who issues credentials under this profile or under `profiles/dtg-openvtc.md` needs one.
- **JSON-LD context.** `InPersonVerificationCredential`, `InPersonVerification`, `anchor`, and `parties` are not defined in any published context. Under the VC 2.0 base context they fall to the issuer-dependent vocabulary. A published context, or an entry in the DTG registry, would fix this.
- **Convergence with RLTP.** Should Agora accept RLTP encounter credentials issued to Agora DIDs, or should RLTP define a `directed` profile that this profile could adopt instead of its own?
- **Group meetups.** One code per exchange (section 3.1) makes verifying ten people at once slow. A multi-party ceremony is out of scope for 0.1.
- **SAS display.** Digits are a simple, universal format. Word lists compare faster aloud. Should the profile allow both?
