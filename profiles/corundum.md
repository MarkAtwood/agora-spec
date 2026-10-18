# Profile: CORUNDUM and Agora

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-16; revised 2026-10-18 (C2 reversed: CORUNDUM keeps IPNS)
**Depends on:** ARCHITECTURE §2.3, §2.4, §9; spec §2.1, §2.3, §4.5, §4.6, §4.7, §5.2.1.1, §10.2, §10.4.4, §10.5.1, §10.5.3, §13.1.1, Appendix E
**Sources:** Mark's decisions C1–C8 (epic agora-pozi.32), with C2, C2a, C2b, and the posting-key part of C4 superseded by Mark's CORUNDUM decisions of 2026-10-18; analysis in `notes/corundum-fit.md`; CORUNDUM at c014c29 (read only): `README.md`, `docs/spec/03-identity.md` (Ch 5–8), `04-content-storage.md` (Ch 9–13), `08-social-graph.md` (Ch 25–26), `10-crypto.md` (Ch 33–36), `13-out-of-scope.md` (Ch 40), `14-implementation-guide.md` (Ch 41–46)

---

## 1. Summary

CORUNDUM is the public layer: posts, timelines, replies, follows, and curation. Agora is the private layer: direct messages (DMs), private groups, and calls. A person has one DID and uses it in both. This profile describes how the two share that identity and stay separate everywhere else. The labels C1–C8 name the decisions it records.

The two protocols cover different ground. CORUNDUM covers "the public conversation" only. It puts direct messages and private groups out of scope and lists end-to-end encryption as future work (Ch 40). Agora provides exactly those. Neither protocol carries the other's traffic, and their federation meshes stay separate (`notes/corundum-fit.md` §4 (b), (e)).

What the two share:

- **One identity.** The DID methods are the same (C3). One DID document carries service entries for both protocols, and each protocol uses its own keys (section 3).
- **The same signing primitives.** Both sign exact bytes with JWS and Ed25519 (C1, section 4). Each protocol defines its own signing rules and header members.
- **A one-way border.** Agora messages may reference public CORUNDUM content. Nothing private from Agora ever lands in CORUNDUM public data (C6, section 5).

## 2. Roles

**A CORUNDUM operator is an Agora Communications Operator (CO).** The test is what a component holds, not who runs it (ARCHITECTURE §2.3). By default a CORUNDUM operator holds each user's CORUNDUM content-signing key (section 3). It knows the social graph and who replies to whom (Ch 17, Ch 21, Ch 26). Both put it on the CO side. That is why CORUNDUM operators can enforce blocks and curation without breaking any Agora rule: those rules limit Infrastructure Operators (IOs), and the operator is not one (`notes/corundum-fit.md` §3).

What follows in practice:

- A CORUNDUM operator may host a user's `did:webvh` log and their `AgoraKeyPackageEndpoint` (spec §2.1, §5.2.1.1). The KeyPackage host is a CO component (ARCHITECTURE §2.3 table). If the host lacks the user's update keys, it cannot add a key without producing an invalid log (spec §2.1). CORUNDUM requires operators that create `did:webvh` DIDs for users to set `portable: true`, so users can move the log away (CORUNDUM Ch 7).
- The CORUNDUM content key gives its holder no power in Agora (section 3). Hosting the DID log and the KeyPackage endpoint does not make the operator a member of, or an authority over, any Agora Space.
- The operator's IPFS pinning is IO-like. Its Kubo node (Ch 46) carries CIDs and decides nothing, which matches "Blob / IPFS pinning: IO" in ARCHITECTURE §2.3. What it pins is public data, so the blindness rules have little to protect there.

**Running Agora relays too (C5).** A CORUNDUM operator may also run Agora relays, as ARCHITECTURE §2.4 allows:

- IO keys (`relayDID`, `operatorDID`) MUST differ from every CO key, including the operator's CORUNDUM manifest keys and any user content key it holds (ARCHITECTURE §2.4).
- Relay service is bought under a `ServiceAgreement` like any other (spec §10.5.1). Sharing an operator gives no shortcut.
- **Disclosed cost.** A party that runs both a social or identity service and relays can link its own users to the COs whose traffic passes through its relays. ARCHITECTURE §9 lists the combined-operator costs below as accepted.
  - **Spaces.** The party cannot learn content, channel, or Space.
  - **DM groups.** The identity host is the DM admission host of a DM group its user started or moved to it. As admission host, it learns that its user asked for keys for that group ID, and it chooses the group's relay list (spec §4.6). If those are its own relays, it can tie that DM's traffic at them to its user. It does not learn the group's other members, except its own users whose clients also request keys for the group. It still cannot read content.
  - **Token registration.** As identity host acting as CO for its users' DM groups and self-groups, it registers their tokens under its own billing DID (spec §10.5.3). Their anonymity at a relay is only as large as its user base, and a single-user host gives none.
  - **Avoiding it.** Users and communities can avoid the relay linkage by choosing other relays. A DM admission host should list relays it does not operate.

## 3. Shared identity (C2 reversed, C3, C4)

**DID methods (C3).** CORUNDUM uses Agora's methods (spec §2.1), and has adopted them (CORUNDUM Ch 5):

- `did:webvh` is the default.
- `did:plc` and `did:key` are opt-in.
- Plain `did:web` is not accepted. A `did:webvh` holder may publish a parallel `did:web` copy for older tools, but keys are trusted only if they appear in the verified log (spec §2.1).

**CORUNDUM keeps IPNS (C2 reversed, Mark, 2026-10-18).** The earlier decision C2 had CORUNDUM drop IPNS and point at the RootManifest from the DID. Mark reversed it: the chain is handle → DID → IPNS → RootManifest (CORUNDUM Ch 5).

- **The service entry.** The DID document carries exactly one `CorundumIdentity` service entry, `{ipnsName, operatorEndpoint, listKey, additionalKeys?}` (CORUNDUM Ch 6). `operatorEndpoint` is the operator's origin. `listKey` is an X25519 key to which the user's encrypted follow, block, and mute lists are encrypted.
- **The IPNS name is the content key and the pointer.** For Ed25519, the IPNS name embeds the public key. That key signs the user's posts and RootManifests, and the IPNS record it signs names the current RootManifest CID with a sequence number.
- **Resolution.** Readers fetch the IPNS record from the user's operator through the standard IPFS delegated routing endpoint, `GET /routing/v1/ipns/{name}` at `operatorEndpoint`, and fall back to the DHT only when the operator is unreachable.
- **Why IPNS stays.** An IPNS record is self-verifying, so anyone can serve it and timelines stay fetchable without trusting any operator. IPNS needs no history of its own, because the DID log records which IPNS name was current and when. Delegated routing removes DHT latency from the common case.
- **`did:key` users.** A `did:key` and an Ed25519 IPNS name encode the same key, so the IPNS name is derived from the DID, and the RootManifest names the operator endpoint and `listKey`. No Pkarr record is needed: the `_corundum._agora` record that C2b added to spec §10.3.4.6 has been removed.

**Key custody (C4, revised 2026-10-18).** Users hold their own identity keys. The operator never receives them.

- **Update and recovery keys** change the DID document and are held by the user only.
- **The content key** (the IPNS key) is held by the operator by default, which signs on the user's behalf; a user may hold it on their own devices instead (self-custody). It signs the user's CORUNDUM posts and RootManifests. It cannot change the identity, add devices, or act in Agora. This replaces C4's "posting key that signs only the RootManifest".
- **Keeping it out of Agora and generic DID tooling.** Content keys appear only in the `CorundumIdentity` service entry, and in no verification relationship (`verificationMethod`, `authentication`, `assertionMethod`, or any other). An Agora verifier accepts only `authentication` keys unless a section names another relationship (spec §13.1.1, Verification step 3), so a CORUNDUM content key fails every Agora signature check without any new rule. Generic DID software does not treat service entries as keys.
- **Switching operators.** The user's update key signs a DID log entry naming a new `ipnsName` and `operatorEndpoint`. A hostile old operator cannot block the move, because it never held an update key. It keeps the old content key, but the DID no longer names it, so nothing it signs is accepted (CORUNDUM Ch 7, Ch 34).

**One DID document, both protocols.** Each protocol finds its entries by `type`:

| Entry | Protocol | Key Used |
|---|---|---|
| `authentication` Ed25519 device keys, `keyAgreement` X25519 (spec §2.1) | Agora | User devices |
| `AgoraKeyPackageEndpoint`, `AgoraProfile` services (spec §2.1, §2.3) | Agora | Not applicable |
| `CorundumIdentity` service: `ipnsName` and `additionalKeys` (content keys) | CORUNDUM | Operator by default, or the user |
| `CorundumIdentity` service: `listKey` (X25519) | CORUNDUM | User (kept with recovery material) |
| Update or rotation keys, recovery keys | Both | User only |

No key appears in two rows. In particular, CORUNDUM's `listKey` and Agora's `keyAgreement` key are different keys. Anyone who resolves the DID can see both sets of service entries (section 5).

## 4. Signing (C1)

Both protocols sign the exact stored bytes with JWS (RFC 7515) and Ed25519. CORUNDUM's rules are its own (CORUNDUM Ch 33–36), with their own protected-header type member, `corundumType`, in place of Agora's `agoraType`, and their own test vectors (CORUNDUM Ch 45). Agora's rules and vectors do not govern CORUNDUM objects, and a change to either protocol's signing rules does not change the other's. As CORUNDUM specifies them:

- **A post's id is the CID of its stored bytes,** CIDv1 with the `raw` codec and sha2-256. Stored objects are never re-serialized; there is no canonical JSON and no NFKC.
- **Activities use a detached JWS** (RFC 7797 unencoded payload), the SigningRecord; other objects, such as the RootManifest, are attached JWS. Resignatures add entries to `signatures`.
- **`kid` is the signing key's IPNS name** for the Ed25519 content key, which embeds the public key, or the key's `kid` in `additionalKeys`. It is not a DID URL. Authorization comes from the key being listed in the signer's DID document.
- **`alg` is `Ed25519`** (RFC 9864), with a strict verification profile; `EdDSA` is not accepted.
- **Historical content is authenticated by inclusion** in the user's current RootManifest, not by signing timestamps.

## 5. The border (C6)

- **Agora to CORUNDUM: by reference only.** An Agora message may reference public CORUNDUM content by CID, for example an `ipfs://` link in a message body. Fetching it is an ordinary public IPFS fetch, which is allowed because CORUNDUM content is public. A client that fetches through a public gateway reveals its interest in that CID to the gateway, so clients should fetch through the user's own node or operator where they can. Agora's own blobs are different: a channel's private ciphertext is fetched only from its relays, its archive, or the user's own devices, and never announced on or requested from the public IPFS network (spec §10.4.4).
- **Nothing private crosses back.** No software writes Agora membership, Space names, channels, or member lists into CORUNDUM public data. That covers RootManifests, profiles, posts, and published follow lists. A person can still choose to post about an Agora Space. Software never does it for them.
- **Disclosure.** Clients tell the user that one identity is shared across both systems. A public DID document that lists an `AgoraKeyPackageEndpoint` next to a CORUNDUM identity service tells anyone who resolves it that the person uses Agora (`notes/corundum-fit.md` §4 (a)). A person who wants the two unlinked uses two DIDs. CORUNDUM has one identity per DID (Ch 6), so CORUNDUM personas that must not be linked also use separate DIDs.
- **Private follow lists.** CORUNDUM follow lists are private by default (Ch 25):
  - **Storage.** They are encrypted (JWE) to the user's `listKey` and their operator's encryption key, which needs the list to build the feed. Users may choose to publish all or part of the list.
  - **Notices.** Every follow sends a signed FollowNotification to the followed person's operator (Ch 26). CORUNDUM decided this against the earlier "follower's setting" idea, because followers-only reply policies need the followed person's operator to know who follows them.
  - **Accepted loss.** Friends-of-friends discovery comes only from published lists or from curators.

## 6. Moderation (C7)

Agora has no CORUNDUM curator integration:

- No curator feed is applied inside encrypted groups, whether to accounts or to content.
- Agora communities moderate only with their own tools: CO-signed moderation records (spec §4.5) and member reports to the CO (spec §4.7).
- Curators, `CurationEntry` judgments, and operator policy tables (Ch 27–32) apply on the CORUNDUM public side only, where the operator enforces them.

This rules out the client-side matching of end-to-end encrypted (E2EE) content discussed as option (d) in `notes/corundum-fit.md` §4.

## 7. Lineage (C8)

Agora's relay peering (spec §10.2) derives from CORUNDUM's operator federation (Ch 18–20):

- **What carries over.** The signed well-known manifest with a `keys` lifecycle, RFC 9421 request signing within a 300 s window, and four graduated trust levels.
- **What changed.** Agora applies the design one layer down, between relays that hold no identity or membership knowledge, and adds a replay nonce and JWS manifest signing.
- **Credit.** Spec Appendix E records the debt. That acknowledgment is already in `spec/99-appendices.md`.

## 8. Changes made in CORUNDUM

CORUNDUM made these changes on 2026-10-18 (up to c014c29). The one item checked earlier was made on the Agora side and has since been reverted.

**Signing (C1)**
- [x] Ch 33: Canonical JSON, NFKC, timestamp, and null rules removed; objects are never re-serialized.
- [x] Ch 34: JWS over the stored bytes, with `corundumType`, a strict Ed25519 profile, and inclusion-based historical validity. `kid` is the IPNS name, not a DID URL (section 4).
- [x] Ch 11, Ch 12: activity id = CIDv1 `raw` sha2-256 over the stored bytes; the SigningRecord is a detached JWS.
- [x] Ch 35, Ch 36: agility through `additionalKeys` and multiple `signatures`; a short registry of JOSE `alg` names; the downgrade rule is judged against the signer's DID document.
- [x] Ch 45: JWS and CID test vectors, checked against three Ed25519 implementations.

**Identity (C2 reversed)**
- [x] Ch 5: three layers kept, in the order handle → DID → IPNS → RootManifest. Handles are `alice@domain` via WebFinger, or a domain the user owns via DNS.
- [x] Ch 6: the `CorundumIdentity` service carries `ipnsName`, `operatorEndpoint`, `listKey`, and optional `additionalKeys`.
- [x] Ch 11, Ch 25, Ch 26: `attributedTo`, following lists, and notifications name DIDs, not `ipns://` names.
- [ ] ~~Define the `did:key` pointer in the Pkarr record `_corundum._agora` (spec §10.3.4.6).~~ Reverted: not needed, because a `did:key` user's IPNS name is derived from the DID.

**Key custody (C4, revised)**
- [x] Ch 3, Ch 7: key handover replaced by DID updates signed by the user's update key; the MigrationNotification is an unsigned hint.
- [x] Ch 17: operators never hold update keys, and hold content keys only for custodial users.

**DID method (C3)**
- [x] Ch 5, Ch 6, Ch 42: `did:webvh` default, `did:plc` and `did:key` opt-in, plain `did:web` rejected.

**Private follow lists (C6)**
- [x] Ch 25: following lists private by default, encrypted, publishable in whole or in part.
- [x] Ch 26: every follow sends a signed FollowNotification (section 5).

**Minor inconsistencies**
- [x] The Go MVP plan is moved to the attic; the implementation language is Rust.
- [x] `"ed25519"` and `ed25519-v1` replaced by the JOSE name `Ed25519`.
- [x] The duplicate Chapter 36 is resolved; the client event stream moved to the non-normative client API.

## 9. Open questions

1. **Pointer update cadence.** Superseded (2026-10-18). C2a had the operator serve a posting-key-signed manifest chain from a DID service entry. CORUNDUM keeps IPNS: the IPNS record carries the sequence number, the RootManifest is signed by the content keys, and old content is authenticated by inclusion in the current manifest (section 3).
2. **`did:key` users.** Superseded (2026-10-18). C2b added a `_corundum._agora` Pkarr record. CORUNDUM derives a `did:key` user's IPNS name from the DID, so the record is not needed and has been removed from spec §10.3.4.6.
3. **The content key relationship.** Resolved (Mark, 2026-10-17), and still holds: CORUNDUM content keys are in no verification relationship. They appear only in the `CorundumIdentity` service entry, so generic DID tooling never treats them as able to authenticate or assert claims for the user.
4. **JWS header members.** Resolved (Mark, 2026-10-17): the protocols do not share a header profile. CORUNDUM defines its own signing rules, protected-header type member, and test vectors (section 4). Agora's vectors cover only Agora.
5. **Follow list encryption.** Resolved in CORUNDUM (2026-10-18): JWE with `ECDH-ES+A256KW` over X25519 to the user's `listKey` and the operator's encryption key, re-encrypted to the new operator when the user switches (CORUNDUM Ch 25).
6. **Witnesses.** When a CORUNDUM operator hosts an individual's `did:webvh` log but holds no update key, is that DID individual (witnesses optional) or CO-provisioned (witnesses required, spec §2.1)?
7. **Curated content inside Agora.** Is it enough that the fetch path applies whatever policy it has when a CORUNDUM post that curators later flag is referenced in an Agora message, or should clients warn?

## 10. Optional integrations

These let CORUNDUM use Agora where a user or operator has it, without CORUNDUM requiring it. None changes either protocol. Each is gated by **discovery through the DID document**. A CORUNDUM client looks for the other party's Agora entries, `AgoraKeyPackageEndpoint` in particular (spec §2.1). If the entry is present, the client uses Agora; if not, it falls back as stated or does not offer the feature. A user who wants to keep their CORUNDUM identity unlinked from Agora uses a separate DID (section 5).

1. **Private messages from public context.** CORUNDUM has no direct messages (Ch 40). A CORUNDUM client MAY offer "message privately" on a profile or post when the person's DID document carries an `AgoraKeyPackageEndpoint`, and opens or requests an Agora DM group with that DID (spec §4.6, §4.6.3). Without the entry, the client offers nothing. This adds no CORUNDUM mechanism, and the public post is never sent through Agora.
2. **Device sync for self-custody keys.** A CORUNDUM self-custody user keeps their content key and their `listKey` on their own devices (CORUNDUM Ch 5, Ch 6). CORUNDUM defines no way to get those keys onto a second device. A user who also uses Agora MAY carry them in their Agora self-group (spec §2.6), which reaches only their own devices. They travel as a typed payload that only the user's own clients read, and no other party ever receives them. Without Agora, clients use whatever export the CORUNDUM client offers, for example an encrypted file or a QR code.
3. **Restricted curation feeds over broadcast channels.** CORUNDUM requires feeds carrying `legal/*` entries to be restricted (CORUNDUM Ch 32). Over authenticated HTTPS, the feed's host and CDN can still read the hashes. A curator MAY instead publish such a feed in a private Agora Space: vetted operators are members, and feed updates are posts in a broadcast channel (spec §5.2.1.4) carrying the same signed CORUNDUM `CurationEntry` and feed-head objects. Relays and storage then hold only ciphertext, and removing an operator is a key rotation (spec §5.2.1.4, "Rotation and removal"). The CORUNDUM objects and their verification are unchanged, so operators without Agora keep using the HTTPS feed. This does not make the curator an Agora authority over anyone; it is the curator's own Space.
4. **Private audiences beside a public profile.** Every CORUNDUM post is public (CORUNDUM Ch 11). A user who also wants a "close friends" or subscriber audience MAY link, from their CORUNDUM profile, an Agora broadcast channel or board (`notes/private-boards.md`) in a Space they control. The private posts live only in Agora, and nothing private crosses into CORUNDUM (section 5). A profile that publishes the link discloses that the private audience exists, but not who is in it.
5. **Private reports and appeals.** Reports to a CORUNDUM operator, and appeals to a curator under its Authority Declaration (CORUNDUM Ch 30), often contain sensitive detail. When the recipient's DID document carries an `AgoraKeyPackageEndpoint`, a client MAY send the report or appeal as an Agora DM; otherwise it uses the recipient's HTTPS process. The operator's or curator's decision is still taken and published on the CORUNDUM side.

**The reverse direction.** Agora MAY use CORUNDUM as a signal without depending on it. A recipient's client MAY treat a message request (spec §4.6.3) as coming from a known sender when the recipient follows that sender's DID on CORUNDUM. The client reads this from the recipient's own following list, which it can decrypt (CORUNDUM Ch 25). The check is local to the recipient's client and needs no new message, and a recipient without CORUNDUM is unaffected.

**What not to do.** Do not route CORUNDUM public traffic through Agora relays, which would put identity-bearing public data on the IO tier (`notes/corundum-fit.md` §4 (b), (e)). Do not make Agora keys a precondition for any CORUNDUM feature. Do not reuse keys across the two protocols (section 3).
