# Corundum and Agora: fit analysis

Status: research note, non-normative. 2026-10-16. Sources: `~/PROJECT/CORUNDUM` at b7abcd5 (README, PRFAQ, `docs/spec/*`, MVP plan skimmed); Agora `ARCHITECTURE.md`, `spec/02,03,04,05,10,13,14`.

**Update, 2026-10-18.** Decision 2 below is settled the other way: CORUNDUM keeps IPNS (handle → DID → IPNS → RootManifest), and the IPNS key is the delegated content-signing key, held by the operator by default. This reverses C2, C2a, and C2b and the posting-key part of C4. CORUNDUM has also made the C1, C3, and C6 changes and fixed the minor inconsistencies listed in §5. `profiles/corundum.md` has the current design; the rest of this note is the analysis as of 2026-10-16.

**Verdict.** A Corundum operator is an Agora **CO**. It is not an IO. Once it is classified that way, the "operators enforce moderation" conflict goes away. The two protocols cover complementary ground: Corundum explicitly leaves DMs, private groups and E2EE out of scope (Corundum Ch 40). Recommended combination: (a) public/private split, (c) shared DID layer, and optionally (d) curator feeds consumed at CO enforcement points. Do not route Corundum through Agora relays, and do not merge the federation meshes.

## 1. Corundum in brief

- **Layers** (Ch 1–2): identity, content storage (IPFS), service provision (operators) and moderation (curators), plus "the IPFS network" as a substrate that is "not an actor".
- **Identity** (Ch 5–8): three layers. *IPNS* is the operational key that signs content and points to the signed `RootManifest`. The *DID* (`did:web`, `did:plc`, `did:key`) is canonical. Operators MUST key users by DID, and recovery keys sit in `capabilityInvocation`. A `CorundumIdentity` service entry carries `ipnsName` and `operatorEndpoint`. *Handles* are verified bidirectionally (DNS TXT `_corundum.`, DID `alsoKnownAs`, ENS, IPNS). Operators routinely custody the user's IPNS key: Earl hands his private key to Birdsite (Ch 3), the operator signs the user's RootManifest (Ch 26 step 2), and keys live in the Kubo keystore (Ch 46).
- **Archive** (Ch 9–13): RootManifest → ArchiveIndex → IndexPages → immutable 256-entry epochs → `Entry` (`seq`, `content` CID, `contentHash`, `signingRecord`, `replies`). Lookup is O(1) by `seq`. Activities are ActivityStreams 2.0 objects, stored *unsigned*, with `id` = CID of the id-less canonical form. Authorship comes from a detached `SigningRecord`. Deletion uses tombstones and keeps the archive skeleton. Edits use `EditRecord`.
- **Operator federation** (Ch 17–20, 47–52): permissionless. Each operator signs its own manifest at `/.well-known/corundum-operator`, authenticates with RFC 9421 (`corundum-timestamp`, 300 s skew), and is placed in one of four trust levels. Keys are `active`, `deprecated` or `revoked`, and downgrade is prevented by requiring every declared algorithm. Operators exchange a reply-submission protocol and a pull NDJSON event stream.
- **Moderation** (Ch 21–23, 27–32): curators publish an `AuthorityDeclaration` (governance, appeal, jurisdiction, delegate keys). They issue signed `CurationEntry` judgments over *content hashes* (sha256, PDQ, TMK+PDQ, Chromaprint, SimHash), each with a reason taxonomy and an `ordinal`. Feeds are hosted statically: sharded paths, a Bloom filter, log pages and snapshots. Operators keep their own policy tables and enforce them, including retroactively. Blocks are "strong": the receiving operator rejects replies.
- **Signing** (Ch 33–36): Canonical JSON, which is RFC 8785 plus NFKC normalization, timestamp normalization and null omission, signed with Ed25519. Keys are resolved through the signer's manifest, not by an embedded key id. Algorithms are versioned (`ed25519-v1`) and tracked in a sunset registry.

## 2. Shared DNA

- **Peering lineage.** Agora §10.2 reproduces Corundum Ch 18–20 almost exactly: a self-signed well-known manifest with `keys[]`, `status: deprecated` overlap, RFC 9421 over `@method`/`@target-uri`/`@authority`/`content-digest` plus a timestamp header and a 300 s window, four graduated trust levels, peer lists in the manifest, and directories treated as "just lists". Agora added a replay nonce (`x-agora-nonce`) and JWS manifest signing. `notes/research-2026-10-16.md` l.64 records that the "Corundum credit for peering model" was dropped. The important difference: **Agora moved the mechanism down a layer.** Corundum uses it CO↔CO, with full knowledge of who replies to whom. Agora uses it IO↔IO, stripped of identity.
- **Identity.** Both use DIDs above Ed25519 keys and accept `did:plc` and `did:key`. Both are built around portability.
- **Content addressing.** Both put history in IPFS/IPLD DAGs (Agora §5.2.5), and both tombstone without breaking the DAG.
- **Separation of concerns.** Both split roles to remove options from a dominant party, but on different axes. Corundum separates *judgment* (curator) from *enforcement* (operator). Agora separates *decision and enforcement* (CO) from *carriage* (IO).

## 3. Role mapping

| Corundum role | Agora role | Basis |
|---|---|---|
| User | Member (DID holder) | Usually custodial in Corundum. In Agora, individual keys are held on the user's devices (§2.1). |
| Operator (protocol server, reply validation, identity, keystore) | **CO** | Key test (ARCH §2.3): holds user signing keys and knows the social graph and sender identity. |
| Operator's Kubo node / pinning service | IO (blob/IPFS pinning) | Carries CIDs and decides nothing. |
| IPFS network | IO substrate | "Not an actor" (Ch 2). |
| Curator | No Agora role; an external policy source | Signs judgments, not community state. |
| Directory | Directory document (§10.3.4) | Both untrusted lists. |
| DID host issuing `did:web:birdsite…:users:alice` | CO DID Provisioning Service | Same pattern as `profiles/universal-idp-did.md`. |

Against the rules:

- **S1, S2, S3, S6:** these bind IOs only. Corundum has no IO beyond IPFS pinning, so a Corundum operator enforcing curation and blocks does not violate S2. *Agree.*
- **S4:** Corundum community state (manifests, reply trees) is signed by the user or operator key, i.e. CO-side. *Agree.* Curator judgments are not CO-signed, so under S4 an Agora CO must *adopt* them; they cannot act as moderation records directly.
- **S5:** in Corundum the *user* replaces the operator (migration). In Agora the *CO* replaces IOs. These are analogous sovereignty moves at different levels. *No conflict*, but Corundum does not provide IO replaceability.
- **S7:** Corundum is contract-free. Agora is contract-free for IO↔IO peering, but CO↔IO requires a `RelayServiceAgreement`. *Partial conflict* if a Corundum operator buys Agora relay service.
- **S8 / §3.4:** Corundum puts the follow list and reply trees (which name repliers) on IPFS in the clear. Inside an Agora Space, records naming members MUST NOT sit on IOs in the clear. *Conflict for imported data. None for Corundum-native public content.*
- **§2.4:** an entity that is both a Corundum operator and an Agora relay operator needs distinct IO and CO keys. Corundum has a single manifest key. *Conflict only if one key is used for both roles.*

## 4. Fit options

**(a) Corundum public layer + Agora private layer.** *Recommended.* Corundum Ch 40 names DMs, private groups and E2EE as out of scope or future work. Agora does exactly those. A Corundum operator would act as its users' Agora CO for identity and KeyPackages, and would buy IO service separately. Pros: no core change to either protocol; one DID per user; clean legal story (public content on the Corundum side, private on the Agora side). Cons: two stacks and two signing schemes. Custodial Corundum users still need device keys before they can join MLS. A `KeyPackageEndpoint` in a public DID document reveals that the person uses Agora.

**(b) Agora carrying Corundum content.** *Only in a light form.* §13.1 can carry an AS2 activity as a typed payload (`contentType: application/activity+json`), and §5.2.1.4 broadcast with `keyAccess: public` gives authenticated one-to-many publication. But it provides no permanent archive, no ArchiveIndex, no reply protocol and no curation, retention follows the relay agreement, and a per-user Space as a "timeline" is heavy. Worth doing: referencing Corundum posts by CID inside Agora messages, plus a CO-run bot that mirrors a timeline into a broadcast channel. Not worth doing: Agora as a social transport.

**(c) Shared identity layer.** *Recommended.* `did:plc` and `did:key` are common to both. One DID document can carry a `CorundumIdentity` service plus Agora's `KeyPackageEndpoint`/`AgoraSpaceEndpoint`, an Ed25519 `authentication` key and an X25519 `keyAgreement` key. The blocker is that Corundum's default is `did:web`, while Agora MUST NOT accept `did:web` keys outside a verified `did:webvh` log (§2.1). `did:webvh` can publish a parallel `did:web`, so Corundum could adopt it without breaking `did:web` readers. Keep the keys separate: the IPNS content key, the Agora `authentication` key and the per-device MLS keys. Uncertain: whether Corundum's IPNS key is meant to appear as a `verificationMethod` (the Ch 6 example is ambiguous). Also, I believe an Ed25519 IPNS name embeds the public key and so maps mechanically to `did:key`. Verify before relying on it.

**(d) Shared moderation.** *Optional, CO-side only.* It fits "CO decides" if three conditions hold: the CO lists curator subscriptions in CO-signed Space state; enforcement happens only at §6.3 enforcement points (client display filtering, the compliance logger, retroactive archive matching, vetting public SpaceAds and directory entries); and IOs never consume feeds (S2). Pros: CSAM obligations for regulated COs, transparent governance and appeals. Cons: matching E2EE content on the client *is* client-side scanning, a policy decision Agora has not taken. Bloom positives trigger sharded fetches that reveal hash prefixes to the curator's CDN. Subjects are content hashes, and how `identity/*` reasons apply to DIDs is unspecified. A curator judgment must never become a ban except through a CO-issued MLS Remove.

**(e) Shared federation and discovery.** *Low value.* The meshes sit at different layers (CO↔CO versus IO↔IO), so a shared mesh would leak identity into the IO tier. A shared RFC 9421 convention, covering headers, key lifecycle, trust levels and the nonce, is cheap and harmless. Corundum's static feed format (sharded entries, `index.json`, log pages, snapshots) could serve Agora directory documents, but nothing currently requires that.

## 5. Decisions for Mark

1. **Canonicalization.** Corundum signs Canonical JSON with NFKC (Ch 33). Agora signs exact bytes with JWS and computes no canonical form (§13.1.1). NFKC is lossy (for example ligatures and full-width forms) and goes beyond RFC 8785. Corundum's motivation is a content-derived `id` that matches across signers for curation. Options: keep both schemes and verify each protocol's objects by its own rules, or move Corundum to exact bytes with a CID over the stored bytes. Unverified: Corundum labels the `id` CID `dag-json` while hashing canonical-JSON bytes that may not be valid DAG-JSON encoding.
2. **IPNS vs `did:webvh`.** Agora dropped IPNS except as a last-resort bootstrap (§10.2.5). IPNS offers sequence numbers but no verifiable history, and DHT resolution takes 30–60 s (Ch 5). Should Corundum keep IPNS, or point a `did:webvh` service entry at the RootManifest CID? The `did:key` case raises the same question: Agora's Pkarr/Mainline pointer versus IPNS.
3. **`did:web` vs `did:webvh`** as the shared default.
4. **Key custody.** Corundum operators hold user keys. Is a Corundum operator an Agora CO provisioning service (as in the employer profiles), or must individuals hold their own Agora keys?
5. **Operator enforcement vs blind relays.** Resolved by classifying the operator as a CO. Decide whether a Corundum operator may also run Agora relays (allowed under §2.4 with distinct keys).
6. **Public vs private defaults.** Corundum is public by default (`to: Public`, public follow lists). Agora is private by default, and only public Spaces advertise (§10.3.2). No Corundum data that names members should go into Agora Spaces in the clear.
7. **Client-side curation in E2EE.** Agora needs an explicit yes or no before option (d).
8. **Lineage credit.** Decide whether to restore a non-normative acknowledgment in `spec/10` (dropped per the research note).

Minor, in Corundum: README and PRFAQ say the implementation is in Rust, while the MVP plan says Go. `CurationEntry.signature.algorithm` is `"ed25519"`, while everywhere else uses `ed25519-v1`. This only matters if Agora COs verify curation entries.

## 6. Next step

Write a non-normative `profiles/corundum.md` covering (a), (c) and (d). It should specify the shared DID document layout (service entries, key separation), the Corundum operator as CO and provisioning service with no IO role, and curator subscriptions as CO-signed Space state enforced only at §6.3 points. Settle decisions 2–4 first in a one-page identity note, because the profile depends on them.
