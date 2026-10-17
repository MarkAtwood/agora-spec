# Profile: CORUNDUM and Agora

> Non-normative. Describes how CORUNDUM (public social media) and Agora (private groups, DMs and calls) share one identity and stay separate everywhere else. Records Mark's decisions C1-C8 (beads agora-pozi.32.1 to .32.8). Most of the work falls on CORUNDUM; section 8 lists the changes, none of which have been made yet. Capitalized BCP 14 key words here state what a deployment that follows this profile requires of its own components, not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source.

**Status:** Draft, 2026-10-16
**Depends on:** ARCHITECTURE.md §2.3, §2.4, §9; spec §2.1, §2.3, §4.5, §4.7, §5.2.1.1, §10.2, §10.3.4.6, §10.5.1, §13.1.1, Appendix E
**CORUNDUM sources (read only, at b7abcd5):** README.md; PRFAQ.md; docs/spec/01-overview.md (Ch 1-3), 03-identity.md (Ch 5-8), 04-content-storage.md (Ch 9-13), 08-social-graph.md (Ch 25-26), 09-curation.md (Ch 29-32), 10-crypto.md (Ch 33-36), 14-out-of-scope.md (Ch 40), 15-implementation-guide.md (Ch 41-46); docs/corundum-mvp-implementation-plan.md
**Analysis:** notes/corundum-fit.md

---

## 1. Summary

CORUNDUM is the public layer: posts, timelines, replies, follows and curation. Agora is the private layer: DMs, private groups and calls. A person has one DID and uses it in both.

The two protocols cover different ground. CORUNDUM covers "the public conversation" only. It puts direct messages and private groups out of scope and lists end-to-end encryption as future work (Ch 40, "Direct messages and private groups", "End-to-end encryption", "Private groups"). Agora provides exactly those. Neither protocol carries the other's traffic, and their federation meshes stay separate (notes/corundum-fit.md §4 (b), (e)).

What the two share:

- **One identity.** The DID methods are the same (C3). One DID document carries service entries for both protocols, and each protocol uses its own keys (section 3).
- **One signing scheme.** Both sign exact bytes with JWS and Ed25519 (C1, section 4).
- **A one-way border.** Agora messages may reference public CORUNDUM content. Nothing private from Agora ever lands in CORUNDUM public data (C6, section 5).

## 2. Roles

**A CORUNDUM operator is an Agora CO.** The test is what a component holds, not who runs it (ARCHITECTURE §2.3). A CORUNDUM operator holds a delegated signing key for each user (C4, section 3). It knows the social graph and who replies to whom (Ch 17, Ch 21, Ch 26). Both put it on the CO side. That is why CORUNDUM operators can enforce blocks and curation without breaking any Agora rule: those rules limit IOs, and the operator is not one (notes/corundum-fit.md §3).

What follows in practice:

- A CORUNDUM operator may host a user's `did:webvh` log and their `AgoraKeyPackageEndpoint` (spec §2.1, §5.2.1.1). The KeyPackage host is a CO component (ARCHITECTURE §2.3 table). If the host lacks the user's update keys, it cannot add a key without producing an invalid log (spec §2.1).
- The operator's posting key gives it no power in Agora (section 3). Hosting the DID log and the KeyPackage endpoint does not make it a member of, or an authority over, any Agora Space.
- **Its IPFS pinning is IO-like.** The operator's Kubo node (Ch 46) carries CIDs and decides nothing, which matches "Blob / IPFS pinning: IO" in ARCHITECTURE §2.3. What it pins is public data, so the blindness rules have little to protect there.

**Running Agora relays too (C5).** A CORUNDUM operator may also run Agora relays, as ARCHITECTURE §2.4 allows:

- IO keys (`relayDID`, `operatorDID`) MUST differ from every CO key, including the operator's manifest key and any posting key it holds (ARCHITECTURE §2.4).
- Relay service is bought under a `ServiceAgreement` like any other (spec §10.5.1). Sharing an operator gives no shortcut.
- **Disclosed cost.** A party that runs both a social or identity service and relays can link its own users to the COs whose traffic passes through its relays. For Spaces it cannot learn content, channel or Space. DMs differ: as the DM admission host of a DM group its user started, the identity host learns that group's member DIDs and its relay list (spec §4.6), so if those are its own relays it can also attribute that DM's traffic at them to known members. It still cannot read content. As identity host acting as CO for its users' DM groups and self-groups, it also registers their tokens under its own billing DID (spec §10.5.3), so their anonymity at a relay is only as large as its user base, and a single-user host gives none. Users and communities can avoid the relay linkage by choosing other relays, and a DM admission host should list relays it does not operate. ARCHITECTURE §9 lists the combined-operator cost as accepted.

## 3. Shared identity (C2, C3, C4)

**DID methods (C3).** CORUNDUM adopts Agora's methods (spec §2.1):

- `did:webvh` is the default.
- `did:plc` and `did:key` are opt-in.
- A `did:webvh` holder may also publish a parallel `did:web` copy for older tools. Keys are trusted only if they appear in the verified log (spec §2.1).
- CORUNDUM today defaults to `did:web` and lets operators issue `did:web` DIDs for their users (Ch 5). Agora does not accept keys from a bare `did:web` document, so CORUNDUM has to move.

**Content pointer is the DID, not IPNS (C2).** CORUNDUM drops IPNS. Today IPNS names the operational key and points at the RootManifest (Ch 5, Ch 9). Instead:

- **`did:webvh` and `did:plc`.** The DID document carries a `service` entry whose `serviceEndpoint` is `ipfs://<RootManifest CID>`. This is the same pattern as Agora's `AgoraProfile` entry (spec §2.3). Updating the pointer is a DID log entry for `did:webvh`, witnessed where the log's parameters require it (spec §2.1), or a PLC operation.
- **`did:key`.** The pointer goes in the Pkarr record (spec §2.1, §10.3.4.6). One identity and one pointer mechanism serve both systems.
- **Why drop IPNS.** It has sequence numbers but no verifiable history, and DHT resolution takes 30-60 s (Ch 5). Agora already dropped IPNS except as a relay's last-resort bootstrap (spec §10.2.5).

**Key custody (C4).** Users hold their own identity keys. The operator never receives them.

- **The delegated posting key.** The operator gets a separate posting key, listed in the user's DID document and therefore visible in the `did:webvh` log. It signs only the user's public content index, the RootManifest. It cannot change the identity, add devices or act in Agora.
- **Keeping it out of Agora.** List the posting key under a verification relationship other than `authentication`; this profile suggests `assertionMethod`. An Agora verifier accepts only `authentication` keys unless a section names another relationship (spec §13.1.1, Verification step 3). A posting key therefore fails every Agora signature check without any new rule.
- **Switching operators.** Remove the old posting key and add the new one, both as DID log entries signed by the user's update keys. This replaces CORUNDUM's cooperative and hostile migration flows (Ch 7) and Earl handing his IPNS private key to Birdsite (Ch 3). A hostile old operator cannot block the move, because it never held an update key.

**One DID document, both protocols.** Each protocol finds its entries by `type`:

| Entry | Protocol | Key used |
|---|---|---|
| `authentication` Ed25519 device keys, `keyAgreement` X25519 (spec §2.1) | Agora | User devices |
| `AgoraKeyPackageEndpoint`, `AgoraProfile` services (spec §2.1, §2.3) | Agora | Not applicable |
| CORUNDUM identity service with the RootManifest CID and the operator endpoint | CORUNDUM | Not applicable |
| Posting key (`assertionMethod`) | CORUNDUM | Operator, delegated |
| Update or rotation keys, recovery keys | Both | User only |

No key appears in two rows. Anyone who resolves the DID can see both sets of service entries (section 5).

## 4. Signing (C1)

Both protocols sign the exact stored bytes with JWS (RFC 7515), using a detached unencoded payload (RFC 7797) and EdDSA with Ed25519 (RFC 8037). This is the procedure in spec §13.1.1:

- **A post's id is the CID of its stored bytes,** using the `raw` codec and sha2-256. The id no longer depends on a canonical form, so it stops depending on the id-less re-serialization in Ch 11 and Ch 12.
- **No canonical JSON and no NFKC.** CORUNDUM's Canonical JSON (Ch 33) goes beyond RFC 8785 with NFKC, timestamp rewriting and null omission. NFKC is lossy: it folds ligatures and full-width forms, so a verifier can end up checking bytes the author never wrote. The byte-for-byte rule of spec §13.1.1 replaces all of it. A stored object is never re-serialized.
- **The detached SigningRecord stays, as a JWS.** The detached design of Ch 12 maps cleanly to a JWS with a detached payload over the activity's stored bytes. Resignatures add JWS `signatures` entries. The activity and its CID do not change.
- **Key binding by DID URL.** `kid` names the signing key as a DID URL. That key must be in the signer's verified DID document under the expected relationship (spec §13.1.1 step 3). Ch 34 avoided embedded key ids because an attacker could name a key it created. Resolving through the verified DID document answers that concern.
- **This also fixes a CORUNDUM bug.** CORUNDUM labels the id CID `dag-json` while hashing canonical-JSON bytes (Ch 11, step 4), and those bytes need not be valid DAG-JSON.

## 5. The border (C6)

- **Agora to CORUNDUM: by reference only.** An Agora message may reference public CORUNDUM content by CID, for example an `ipfs://` link in a message body. Fetching it is an ordinary public IPFS fetch. A client that fetches through a public gateway reveals its interest in that CID to the gateway, so clients should fetch through the user's own node or operator where they can.
- **Nothing private crosses back.** No software writes Agora membership, Space names, channels or member lists into CORUNDUM public data. That covers RootManifests, profiles, posts and published follow lists. A person can still choose to post about an Agora Space. Software never does it for them.
- **Disclosure.** Clients tell the user that one identity is shared across both systems. A public DID document that lists an `AgoraKeyPackageEndpoint` next to a CORUNDUM identity service tells anyone who resolves it that the person uses Agora (notes/corundum-fit.md §4 (a)). A person who wants the two unlinked uses two DIDs. CORUNDUM's multiple personas under one DID (Ch 6) share a root of trust by design, so they do not give that separation.
- **Private follow lists.** CORUNDUM follow lists become private by default:
  - **Today.** They are public by default and stored in the RootManifest on IPFS in the clear (Ch 25).
  - **Proposed.** They are stored encrypted and readable only by the user and their own operator, which needs the list to build the feed. Users may choose to publish all or part of the list.
  - **Notices.** Whether a new follow sends a notice to the followed person's operator (Ch 26, `FollowNotification`) is the follower's setting.
  - **Accepted loss.** Friends-of-friends discovery comes only from published lists or from curators.

## 6. Moderation (C7)

Agora has no CORUNDUM curator integration:

- No curator feed is applied inside encrypted groups, whether to accounts or to content.
- Agora communities moderate only with their own tools: CO-signed moderation records (spec §4.5) and member reports to the CO (spec §4.7).
- Curators, `CurationEntry` judgments and operator policy tables (Ch 27-32) apply on the CORUNDUM public side only, where the operator enforces them.

This rules out the client-side matching of E2EE content discussed as option (d) in notes/corundum-fit.md §4.

## 7. Lineage (C8)

Agora's relay peering (spec §10.2) derives from CORUNDUM's operator federation (Ch 18-20):

- **What carries over.** The signed well-known manifest with a `keys` lifecycle, RFC 9421 request signing within a 300 s window, and four graduated trust levels.
- **What changed.** Agora applies the design one layer down, between relays that hold no identity or membership knowledge, and adds a replay nonce and JWS manifest signing.
- **Credit.** Spec Appendix E records the debt. That acknowledgment is already in spec/99-appendices.md.

## 8. Changes CORUNDUM needs to adopt this profile

None of these changes have been made in CORUNDUM. Each is a proposal, mapped to the chapter it affects.

**Signing (C1)**
- [ ] Ch 33: drop Canonical JSON as the signing input, including NFKC, timestamp and null rules. Remove the Ch 45 test vectors, or replace them with JWS vectors.
- [ ] Ch 34: replace strip-canonicalize-sign with JWS over the stored bytes (RFC 7515/7797/8037). Replace key lookup through the IPNS RootManifest with a `kid` DID URL.
- [ ] Ch 11, Ch 12: activity id = CIDv1 with the `raw` codec and sha2-256 over the stored bytes. The SigningRecord becomes a detached JWS. Removes the `dag-json` label.
- [ ] Ch 35, Ch 36: map algorithm agility onto the JWS `alg` and multiple `signatures` entries. Keep the sunset registry. Keep the downgrade rule (require every active algorithm family).

**Identity and IPNS removal (C2)**
- [ ] Ch 5: two layers instead of three (DID and handles). The verification chain becomes Handle, DID, RootManifest, Handle.
- [ ] Ch 6: the CORUNDUM identity service drops `ipnsName` and carries the RootManifest CID. Add the posting key (section 3).
- [ ] Ch 9: the RootManifest is reached from the DID document, not an IPNS name.
- [ ] Ch 11, Ch 25, Ch 26: `attributedTo`, following lists and notifications name DIDs, not `ipns://` names.
- [ ] Ch 15, Ch 41, Ch 43, Ch 46: remove IPNS keypair generation, Kubo IPNS publishing and the DID-to-IPNS cache. Kubo stays for pinning.
- [x] Define the `did:key` pointer in the Pkarr record: `_corundum._agora` (spec §10.3.4.6).

**Key custody and the delegated posting key (C4)**
- [ ] Ch 3 (Earl), Ch 7: replace key handover and the cooperative and hostile migration flows with swapping posting keys in the DID log. `MigrationNotification` names the old and new posting keys and operators, not IPNS names.
- [ ] Ch 17, Ch 41: operators no longer generate or store user identity keys. They hold only their own posting keys.
- [ ] Ch 26: follow and block steps where "the operator signs the updated RootManifest" use the posting key.

**DID method (C3)**
- [ ] Ch 5, Ch 6, Ch 42: change the default from `did:web` to `did:webvh`, with `did:plc` and `did:key` opt-in. Operator-issued `did:web:birdsite...` identities move to `did:webvh` with a parallel `did:web` copy. Keys are trusted only from the verified log.

**Private follow lists (C6)**
- [ ] Ch 25: following lists are private by default, encrypted to the user and their operator, and publishable in whole or in part.
- [ ] Ch 26: sending a `FollowNotification` becomes the follower's setting.

**Minor inconsistencies (notes/corundum-fit.md §5)**
- [ ] README.md ("Rust Implementation") and PRFAQ.md ("Why Rust?") say Rust. docs/corundum-mvp-implementation-plan.md is titled "(Go)". Pick one.
- [ ] Ch 29, Ch 30: `CurationEntry.signature.algorithm` and the curator `keys[].algorithm` say `"ed25519"`. Everywhere else says `ed25519-v1`. This becomes moot once C1 moves curation signatures to JWS.
- [ ] Two chapters are numbered 36: "Algorithm Sunset Registry" (10-crypto.md) and "Real-Time Notifications" (11-event-streams.md).

## 9. Open questions

1. **Pointer update cadence.** Resolved (Mark, 2026-10-16, C2a): the DID document carries a stable service entry naming the operator's content endpoint and the posting key. The operator serves each new RootManifest signed by the posting key, with a sequence number and the CID of the previous manifest. Readers check the key against the DID document, the signature, the rising sequence and the chain, and remember the highest sequence seen. The DID log changes only when the operator or posting key changes.
2. **`did:key` users.** Resolved (Mark, 2026-10-16, C2b): the Pkarr record carries an optional `_corundum._agora` service record with the operator's content endpoint and the posting key (spec §10.3.4.6). The user's device updates it only when switching operators; the operator re-publishes the unchanged signed record to keep it alive.
3. **The posting key relationship.** Is `assertionMethod` right, or should CORUNDUM define its own relationship so generic DID tooling does not treat the key as able to assert claims for the identity?
4. **JWS header members.** CORUNDUM needs its own protected-header member in place of Agora's `agoraType` (spec §13.1.1). Should both protocols share one header profile, so that one test-vector set (agora-pozi.31.69) covers both?
5. **Follow list encryption.** Which construction (for example HPKE to the user's `keyAgreement` key and an operator key), and how re-encryption works when the user switches operators.
6. **Witnesses.** When a CORUNDUM operator hosts an individual's `did:webvh` log but holds no update key, is that DID individual (witnesses optional) or CO-provisioned (witnesses required, spec §2.1)?
7. **Curated content inside Agora.** Is it enough that the fetch path applies whatever policy it has when a CORUNDUM post that curators later flag is referenced in an Agora message, or should clients warn?

---

*Prepared under epic agora-pozi.32. Non-normative; where it conflicts with the spec or ARCHITECTURE.md, those govern.*
