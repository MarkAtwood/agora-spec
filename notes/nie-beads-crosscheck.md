# nie / agoraold beads cross-check, 2026-10-16

Question: did the nie tracker, or the original Agora tracker, already notice
and fix the problems we found in the Agora specs? Did they fix them the same
way, a different way, or not at all?

Source: `~/PROJECT/nie/.beads/issues/*.json` (3116 files). I triaged by
keyword over title + description + close_reason + acceptance_criteria and then
read the hits. I did not read every file. `.beads/comments/` is empty. I also
read the 16 bd memories in `.beads/config_kv.json`. Two of them are Agora
decisions.

## Overview

**The trackers almost never review the spec.** Of 3116 issues, exactly one
(nie-xm4w) is about an Agora spec document. Everything else is implementation
work or code-review findings on the nie/Agora Rust code. So most of our
findings come out NOT FOUND. That is not because they disagree with us. They
never looked.

- **agoraold-\*** (924): created 2026-04-16..2026-04-23. 920 closed, 3
  deferred, 1 open. 889 of them are prefix-renamed copies of `nie-*` issues
  with the same suffix and title. They look like a snapshot taken during the
  brief nie→agora rename (agoraold-9ile). 35 are unique to agoraold:
  did:key (agoraold-ady2, agoraold-7g2k.*), relay-side guild/channel state
  (agoraold-sy6s.*), the rename, and Android/iOS/video scaffolds
  (agoraold-wtz, -2n0m, -5clb). The themes are the Zcash wallet and payments,
  relay JSON-RPC, MLS phase 1, sealed sender (agoraold-rwr7), clients, and
  review rounds.
- **agora-\* / AGORA-\*** (6): agora-7g2k plus .1/.2/.11 (closed 04-23) are a
  parallel copy of the did:key review. AGORA-4uk (open) is a JMAP Chat local
  user agent: "relay … cannot be the JMAP server". AGORA-hj6 (open) splits
  agora-cli into an agent library.
- **nie-\*** (2186): created 2026-04-16..2026-09-20. 1731 closed, 352 open, 96
  in_progress, 7 deferred. These are implementation issues and roughly 66
  numbered review rounds. 3105 of all 3116 issues were created in April. The
  ten from September are the nie-xaak epic (rebase the Agora fork onto nie
  HEAD) and nie-xm4w. nie-* covers protocol design only as decisions embedded
  in code reviews (type `decision`). It does not cover the spec.

## Findings table

Status and resolution columns come from the issue JSON. "Implicit" means the
code did the right thing but no issue records the spec problem.

### 1. Errata (agora-pozi.20.*)

| Our finding | nie/agoraold id(s) | Status | Their resolution | Verdict |
|---|---|---|---|---|
| 20.1 Ephemeral events as PublicMessage | none | – | – | NOT FOUND |
| 20.2 Device revoke via Update, must be Remove | nie-qgag.6 (tangential) | in_progress | nie has no member/device removal at all. qgag.6 adds a *relay* GROUP_REMOVE | NOT FOUND |
| 20.3 Logger issues Welcome | none | – | – | NOT FOUND |
| 20.4 KP validated against sender DID | nie-kef6.2, nie-s4qr.14, nie-14sh.21 | all open | Verify the KP's BasicCredential equals the *requested target* identity before Add, which defeats relay-assisted substitution. Not fixed in code | SAME (unresolved) |
| 20.5 Ban on IPFS-sourced KP Welcomes | none | – | – | NOT FOUND |
| 20.6 channelToken/TURN from epochSecret | agoraold-rwr7.6 (=nie-rwr7.6), nie-14sh.16 | closed | Code derives the room HPKE key with `export_secret("nie-room-hpke-key")`, i.e. the MLS exporter. 14sh.16 notes that every member holds it | SAME (implicit) |
| 20.7 Static DM token from group ID | agoraold-rwr7 (=nie-rwr7), nie-8nj4.5 | closed | Worse than the spec: whispers carry `to: pub_id` in clear and the offline queue is keyed by `to_pub_id`. rwr7 explicitly accepts "relay learns only who receives". Ours (per-epoch exporter token) is better | DIFFERENT |
| 20.8 Recovery backdating | none | – | – | NOT FOUND |
| 20.9 TURN HMAC key published | nie-5clb (tangential) | open | 1:1 P2P calls, "STUN … in client config with optional TURN". No credential scheme | NOT FOUND |
| 20.10 DM consent vs logger | none | – | – | NOT FOUND |
| 20.11 Canonicalization CBOR vs URDNA2015 | agoraold-sy6s.2 | closed | A third scheme: custom cryptosuite `agora-eddsa-v1`, Ed25519 over SHA-256 of `serde_json::to_vec(struct)`, i.e. struct field order, not JCS/RDFC/CBOR. The comment wrongly says "BTreeMap default = deterministic". Worse than either spec option | DIFFERENT |
| 20.12–20.18, 20.21, 20.23 (naming drift, stubs, wolfSSL examples, undefined types, ciphersuite, regulated scope, version skew, section refs, ops stubs) | none | – | – | NOT FOUND (×10) |
| 20.19 bolt12 metric (closed by us) | none | – | Payments stripping is tracked only as code (nie-xaak.1) | NOT FOUND |
| 20.20 Blob API exposure | none (nie-bwaa.20 is about blob ID hashing only) | – | – | NOT FOUND |
| 20.22 Abuse/takedown procedure | none | – | – | NOT FOUND |
| 20.24 ENROLL did:key vs O365 did:web | agoraold-ady2 (context) | closed | did:key adopted with no did:web reconciliation | NOT FOUND |
| 20.25–20.36 (enroll adapters, O365 circularity/recovery, UNIV drift, Purview ×4, LEGAL ×2, vendor payloads) and 20.26 WebCrypto recovery key | none | – | Enterprise companion docs never appear in the trackers | NOT FOUND (×13) |

Errata total: 2 SAME, 2 DIFFERENT, 32 NOT FOUND.

### 2. ARCHITECTURE.md §7 separation violations

| Our finding | id(s) | Status | Their resolution | Verdict |
|---|---|---|---|---|
| Relay enforces bans/timeouts/pins/deletes | nie-5sey, nie-qmq3.6, nie-r9nx.1, nie-tkof.2; *contra* nie-qgag.6 | closed; qgag.6 in_progress | Retract and role changes travel as Peer/* messages inside MLS, and the *receiving daemon* enforces authZ (owner check, admin check). That matches us. But qgag.6 is adding relay-enforced GROUP_REMOVE. Pins/timeouts: not found | SAME (partial; qgag.6 contradicts) |
| Relay compliance-hold Mechanisms A/B | none | – | – | NOT FOUND |
| channelToken→CID mapping, relay-side JMAP | AGORA-4uk, nie-zxpc, nie-wmql | open / in_progress / closed | The JMAP server runs in the local user agent and the relay stays opaque. That is the same as our §7 item 4 and the pozi.13 backport. The CID mapping itself is not discussed | SAME |
| Presence/typing in clear | nie-bwaa.10, nie-bwaa.17, nie-jmmd.21, nie-gsyn.10, nie-5sey | closed / open | Relay TYPING RPC kept, with the relay stamping `from` from the authenticated session. That is recorded as load-bearing (bwaa.17, jmmd.21). bwaa.10 (typing has no chat scope, leaks across groups) was closed as won't-fix ("single room"). Peer/typing inside MLS exists only for federation (5sey). Ours (all inside MLS) is better | DIFFERENT |
| SFU as MLS member | nie-5clb | open | P2P 1:1 calls only, no SFU | NOT FOUND |
| Admin API exposes space structure | none | – | – | NOT FOUND |
| Relay-hosted logger | none | – | – | NOT FOUND |
| Client–relay DID auth | agoraold-ady2, nie-967x, nie-bwaa.17, nie-jmmd.21 | closed/open | Ed25519 challenge-response on did:key, with PoW bound to the pubkey. Relay-known sender identity is treated as a security feature. Opposite of ARCHITECTURE | DIFFERENT |
| Relay signs community state | agoraold-sy6s.5, -sy6s.6; nie-xaak.4 | closed; xaak.4 open | They **noticed** it: "PROBLEM: the relay does NOT have the client's signing key … Option C: relay signs … simplification for Phase 1; Phase 2 can support client-signed state". The relay also keeps guild member/admin tables. xaak.4 plans to replay this as "the namespace/tenant boundary the service-provider model needs". Ours is better | DIFFERENT |
| Access-log retention mismatch | nie-po5v.10 (tangential) | in_progress | Only token redaction in access logs | NOT FOUND |

§7 total: 2 SAME, 3 DIFFERENT, 5 NOT FOUND.

### 3. Phase-B leaks (not yet filed)

| Our finding | id(s) | Status | Their resolution | Verdict |
|---|---|---|---|---|
| Gossip topic exposes spaceCID | none (nie has no gossip) | – | – | NOT FOUND |
| DMGroupDescriptor / mod log plaintext DIDs in IPFS | memory `decision-agora-ipfs-deliberately-retained` | decision | Not noticed. The decision has org "tanks" replicate "membership chains and moderation records", which spreads the leak further | NOT FOUND |
| DM Welcomes / logger KPs via DID-keyed inbox | agoraold-rwr7, nie-8nj4.5, nie-qmq3.8 | closed | Welcomes go by `whisper to: pub_id` and are queued by `to_pub_id`. Recipient visibility is accepted (rwr7). Ours is better | DIFFERENT |
| SpeakRequest in clear | none | – | – | NOT FOUND |
| KeyPackageRequest exposes requestedBy/targetDID | nie-kef6.2 (adjacent) | open | nie's GET_KEY_PACKAGE has the same leak (an authenticated requester asks by target pub_id). Nobody flagged it | NOT FOUND |
| Broadcast channels: no MLS group, undefined token/proof | agoraold-sy6s.6 | closed | Broadcast mode has `mls_group_id = None` and a *relay-generated* `channel_secret_b64` stored in relay-signed ChannelState and served by `channel.get`. So the relay knows the key. Worse | DIFFERENT |
| Passive members' reusable last-resort KPs | nie-1zcu, nie-bqoo.3 (adjacent) | closed | nie KPs are per-device and replaced in place (reusable), which is the pattern agora-pozi.18 already rejects. Passive members are not discussed | NOT FOUND |
| recordingKey decrypts nothing | none | – | – | NOT FOUND |
| §14.1 eddsa-rdna-2022 claim / phantom Go repo | agoraold-sy6s.2 (adjacent) | closed | Code invented `agora-eddsa-v1` instead of using any W3C suite | NOT FOUND |
| Social recovery commitment in two places | none | – | – | NOT FOUND |
| RelayServiceAgreement token→Space (pozi.22) | memory `decision-agora-subscribe-request-stub` | decision | Names the RSA (spec §12.2) as the future provisioning model, with no privacy analysis | NOT FOUND |

Leaks total: 0 SAME, 2 DIFFERENT, 9 NOT FOUND.

### 4. Open decisions

| Our decision | id(s) | Status | What they recorded | Verdict |
|---|---|---|---|---|
| agora-pozi.6 DID method | agoraold-ady2, agoraold-7g2k.9, nie-xaak.3 | closed; xaak.3 open | Chose did:key. 7g2k.9 praises determinism because "identity remains stable". There is no rotation or immutability analysis, and xaak.3 replays it | DIFFERENT |
| pozi.8 Q1 epoch access key | nie-14sh.16 (tangential) | closed | – | NOT FOUND |
| pozi.9 Q2 admission without DID | nie-967x, nie-hvw | closed | Hashcash PoW enrollment gate (20-bit, ±600 s, replay set) plus Zcash subscriptions, both keyed to the authenticated pubkey. The PoW mechanism is a working candidate for Q2, but it would need to be unbound from identity | DIFFERENT |
| pozi.10 Q3 KP store placement | nie-3s3r, nie-1zcu; memory `decision-agora-ipfs-deliberately-retained` | closed / decision | Relay-hosted, DID-keyed KP store. The memory calls the KeyPackage Store "the worked example" of a relay SLA endpoint. Leans against our CO/DID-doc option | DIFFERENT |
| pozi.11 Q4 push budget | none (nie-6pkc is EventSource, not push) | – | – | NOT FOUND |
| pozi.12 Q5 discovery | none | – | – | NOT FOUND |
| pozi.22 Q6 IO knows its Spaces | memory `decision-agora-subscribe-request-stub` | decision | Assumes RSA provisioning and does not address the mapping | NOT FOUND |

Decisions total: 0 SAME, 3 DIFFERENT, 4 NOT FOUND.

**Grand total (64 items): 4 SAME, 10 DIFFERENT, 50 NOT FOUND.** In every
DIFFERENT case I judge our version better on separation grounds, with one
exception. The PoW gate (nie-967x) is reusable engineering for Q2.

## Spec-relevant items they recorded that we missed

1. **Ops spec has no IPFS section** (nie-xm4w, open; memory
   `decision-agora-ipfs-deliberately-retained`). Missing pieces: `[ipfs]`
   config, pinning policy tied to `retentionDays`, GC safety while an
   agreement is live, sizing, retrieval timeouts and degraded behaviour,
   backup, metrics, org-tank guide. Also a **browser/wasm gateway fetch path**,
   which is unspecified because browsers cannot be DHT peers. The memory says
   "Relays MUST run a node" and "Do not re-litigate". ARCHITECTURE lists IPFS
   pinning as an IO role but does not say whether every relay must run a node.
2. **Invite revocation** (nie-4v7h, closed by allowing destroy). spec/03 l.62
   has `maxUses` and expiry, but grep finds no way to revoke a leaked invite
   before expiry. agora-pozi.17 covers entropy and message self-retract, not
   invite revocation.
3. **Ratchet tree delivery** (nie-7xs.13, decision). nie mandates the
   `ratchet_tree` extension in Welcome so that no relay ever serves group
   state. Our spec says to authenticate the adder "from the group's ratchet
   tree" (spec/03 l.64, l.138) but never says where joiners get the tree, and
   grep finds no GroupInfo or external-join text. If the tree is not in the
   Welcome, some service must hold per-epoch group state. That is a separation
   question.
4. **Welcome group-ID binding** (nie-tb8e.18, open). The Welcome acceptance
   rule should also require that the Welcome's group ID equals the
   `mlsGroupId` that Space state declares for that channel. The current text
   only rejects Welcomes for groups already held. Minor.
5. **Sealed-envelope redundancy, uncertain.** nie converged on dropping a
   self-asserted sender prefix and trusting the MLS-authenticated sender
   (agoraold-ostu, agoraold-2qc3; nie-14sh.16 notes that the exporter-derived
   room key is shared by all members). Our spec's `sealedEnvelope` (import
   l.1401–1418) adds sender DID + sig + ephemeral key "encrypted … to the
   channel's current MLS group key". No such single key exists in MLS, and
   PrivateMessage already encrypts and authenticates the sender. Worth a check
   when 20.1 is fixed. I have not verified this beyond reading those lines.

## Recorded decisions that contradict ARCHITECTURE.md

- **Relay-owned guild/channel state:** agoraold-sy6s.5/.6 (closed) and
  **nie-xaak.4 (open, still planned)**. The relay signs GuildState/ChannelState,
  keeps member/admin tables, and generates broadcast channel secrets. This
  contradicts S4 and §7 items 4 and 10. xaak.4 should be dropped or re-scoped
  before anyone replays it.
- **Relay-authenticated sender identity treated as load-bearing:** nie-bwaa.17
  (closed decision) and nie-jmmd.21 (open decision: "from-field relay-set …
  sender spoofing structurally impossible"). This contradicts §7 items 5 and 9.
- **Relay decides the MLS admin:** nie-8le.13 (decision: relay connection
  sequence = admin), with nie-f0pz.22, nie-tb8e.20 and nie-jq8m.12 (Welcome
  accepted only from `online[0]` by relay-assigned sequence). That puts
  community authority in the IO. It contradicts ARCHITECTURE and spec/03
  Welcome acceptance, where authority comes from Space state.
- **Relay-enforced kick:** nie-qgag.6 (in_progress) contradicts §7 item 1.
- **Recipient visible to relay:** agoraold-rwr7 accepts it. This contradicts
  token-only addressing in the observation budget.
- **KP store on the relay:** the IPFS memory names it as the worked example of
  a relay endpoint. That is in tension with Q3 (open, so not a hard
  contradiction).
- **did:key adopted:** agoraold-ady2 and nie-xaak.3 (open). This is in tension
  with agora-pozi.6. Decide pozi.6 before xaak.3 lands.

## Caveats

- Keyword triage can miss issues worded unexpectedly. NOT FOUND means "not
  found by my searches over the full issue text", not proof of absence.
- The "=" mirror links assume that same suffix + same title means the same
  issue. I verified this for agoraold-hlns/nie-hlns, and overall 889 of 924
  suffixes match.
- Code behaviour quoted from issue descriptions (e.g. sy6s.2 hashing
  `serde_json` bytes) is what the issue says was planned or done. I did not
  inspect the code.
