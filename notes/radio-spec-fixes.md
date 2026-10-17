# Radio spec fix list: IRONWEED and LICHEN

Prepared 2026-10-17, read-only. Source notes: `notes/lichen-ironweed.md`, `profiles/radio-mesh-gateway.md` §10. Paths: IRONWEED = `~/PROJECT/IRONWEED`, LICHEN = `~/GIT/project-LICHEN`. Items marked **[MARK]** need a decision.

## 0. Repo state and conventions

- **IRONWEED:** `main`, clean, up to date with `origin/main`. `AGENTS.md` and `CLAUDE.md` both carry the beads boilerplate: use `bd` for task tracking, run the session-close sequence (`bd dolt push`, `git push`), and use non-interactive `cp -f`/`mv -f`. There are no spec-style rules. SPEC.md is a single file of about 1270 lines.
- **LICHEN:** `main`, clean, up to date with `origin/main`. Conventions:
  - `spec/decisions.jsonl` entries override older prose. The two settled decisions are Yggdrasil addressing and best-effort custody. No decision covers link encryption or group keys.
  - RFC 2119 keywords are used consistently (I-D style).
  - "3x /codereview, file every finding as a bead, loop until dry" applies to source code. It does not apply to spec prose.
  - Use beads for everything. Test vectors need independent oracles.
  - The group test vectors (`test/vectors/groups_*.json`, `group_oscore_key.json`) may need updating if group rules change.

Both repos' session rules say "you MUST push". Mark's global rule (ask before commit/push) overrides that.

## 1. Group OSCORE citations

**Facts, checked 2026-10-17:**
- **Group OSCORE** is still an Internet-Draft: `draft-ietf-core-oscore-groupcomm-28` (2025-12-23), intended Proposed Standard. The IESG state is "RFC Ed Queue". The RFC Editor state is "Blocked" (since 2026-10-16), so it has no RFC number yet. Source: https://datatracker.ietf.org/doc/draft-ietf-core-oscore-groupcomm/
- **RFC 9594** is "Key Provisioning for Group Communication Using Authentication and Authorization for Constrained Environments (ACE)" (Proposed Standard, 2024). It is the generic ACE group key-provisioning framework, not Group OSCORE. Source: https://www.rfc-editor.org/info/rfc9594
- **RFC 9203** is "The OSCORE Profile of the ACE Framework" (Proposed Standard, 2022). It covers pairwise OSCORE for ACE access tokens. It is not group communication at all. Source: https://www.rfc-editor.org/info/rfc9203
- The Group OSCORE-specific ACE profile is `draft-ietf-ace-key-groupcomm-oscore`, which builds on RFC 9594.

**Replacement text:** "Group OSCORE (draft-ietf-core-oscore-groupcomm; in the RFC Editor queue)". Update it to the RFC number once one is assigned.

### Occurrences

| File:line | Current | Fix |
|---|---|---|
| IRONWEED `SPEC.md:607` (§6.4) | "Group OSCORE (RFC 9594)" | Cite draft-ietf-core-oscore-groupcomm. |
| IRONWEED `SPEC.md:614` (§6.4) | "Group rekey uses the CoAP group key management protocol" (no citation) | This is where RFC 9594 belongs: "...uses ACE key provisioning for group communication (RFC 9594) with the Group OSCORE profile (draft-ietf-ace-key-groupcomm-oscore)". |
| IRONWEED `SPEC.md:817` (§7.2) | "Group OSCORE security context (RFC 9594)" | Cite draft-ietf-core-oscore-groupcomm. |
| LICHEN `spec/12-apps.md:1197` (§18.8) | "OSCORE Group (RFC 9203) for group encryption" | "Group OSCORE (draft-ietf-core-oscore-groupcomm)". |
| LICHEN `spec/12-apps.md:1570` (§18.8.5) | "OSCORE Group per RFC 9203" | Same. Optionally add RFC 9594 as the key-provisioning reference. |
| LICHEN `standards/ietf-rfcs.md:61` | RFC 9594 row titled "Group OSCORE" | Retitle it "ACE key provisioning for groups". Add a separate draft row for Group OSCORE. |
| LICHEN `standards/ietf-rfcs.ai.md:116` | "## Group OSCORE (RFC 9594)" | Same fix as the previous row. |
| LICHEN `docs/spec-chapter-breakdowns.md:1752` | "Group OSCORE (RFC 9594)" | Cite the draft. |

The grep turned up no other citations. The bare "Group OSCORE" mentions in IRONWEED (lines 672, 770, 1003, 1196, 1265, README:98) and LICHEN (test/vectors/README.md:208, docs/spec-implementation-plan.md:170, 449) are fine.

## 2. LICHEN keyless groups are readable over the air

**What the spec says:**
- `12-apps.md:1202` (§18.8.1) lists the group "Encryption context" as an "Optional per-group OSCORE key". `key_id` is "(optional)" (line 1217).
- §18.8.2 (lines 1384–1410) and §18.8.5 (lines 1568–1583) apply only "for encrypted groups". Key distribution is "out-of-band or via secure unicast".
- §18.8.4 (lines 1548–1563) shows group messaging and group position as plain `POST/PUT coap://[group-mcast]/...` with no OSCORE and no caveat.
- Nothing in the spec says, or requires a UI to say, that a keyless group's traffic is plaintext on air. The device UX spec (`19-device-ux.md`) has no group-encryption indicator.
- No link encryption exists: `02-physical-link.md:267` says "E=1 encrypted frame unsupported; receivers MUST reject". `06-security.md:1540` (§15.4) lists only "Metadata visible: link-layer headers unencrypted". That understates the problem, because keyless group payloads are also visible.
- `06-security.md:49` (§8.2 diagram) shows "AES-128-CCM (optional)" link encryption. That contradicts 02 and would lead a reader to think keyless groups are protected (see §4, L1).

### Options [MARK]

**(a) Document the exposure.**
- Add to §18.8.1: "A group without a Group OSCORE key is a *public group*. Its messages, positions and membership traffic are readable by any LoRa receiver in range. LICHEN provides no link-layer confidentiality."
- Add a matching item 5 to 06 §15.4.
- Add a UI requirement in 19-device-ux: "Devices MUST show a persistent unencrypted indicator on a keyless group and MUST show a warning before the first send to it".
- Cost: text only, about 1 hour.

**(b) Require a key for non-public groups.**
- Add a `public: bool` field to the group CBOR (§18.8.1).
- Text: "A group with `public: false` MUST have a Group OSCORE context. Nodes MUST NOT send group traffic without OSCORE protection on such a group. Group creation without a key MUST set `public: true`."
- Do (a) as well for public groups.
- Cost: spec text plus updates to `groups_cbor.json`, `groups_membership*.json` and `groups_messaging.json`, plus implementation checks in Python, Rust and Zephyr. Estimated 1–3 days.

**(c) Add link-layer encryption.**
- The E bit already exists. The nonce can come from Epoch+SeqNum+SIID, and the existing Schnorr signature already authenticates the frame. So the airtime overhead could be close to 0 B (CTR-only).
- The real costs:
  - A mesh-wide key schedule: distribution, rekey and join.
  - Per-hop decrypt and re-encrypt.
  - Losing passive sniffing, KISS and monitoring interop.
  - A mesh-wide key protects only against outsiders, not against other mesh members.
  - Possible conflict with amateur-band deployments, where encryption is prohibited (Part 97).
- Estimated weeks of spec, implementation and vector work. This option is likely out of scope.

**Recommendation:** (b) together with (a).
- (a) alone leaves the default ambiguous.
- (c) solves the wrong problem: groups need per-group confidentiality, and a mesh-wide link key does not provide it.

## 3. IRONWEED frame size and PLI rate

### 3a. Frame size (add as SPEC §4.4.1 "Frame size", after line 156)

**Facts in the spec:**
- AEAD nonce of 8 B and tag of 16 B (§4.4, lines 138–152).
- CRC-32 on data frames (§4.6.6, line 257).
- Effective C4FM throughput of 4.8–7.2 kbps, or 2.4 kbps with repetition (§4.6.3 table, line 211).
- An 18 B PHY overhead and a 5 ms preamble (§7.3, line 830).
- The IPv6 MTU of 1280 B over 6LoWPAN, which requires fragmentation (§5.2).

**Draft text:**
> The link MAC PDU (plaintext MAC + network headers + payload, before AEAD) MUST NOT exceed **L_max** bytes. Per-frame fixed overhead within the coded block is nonce (8) + tag (16) + CRC-32 (4) = 28 B; preamble/sync/PHY header are additional. Upper layers rely on 6LoWPAN fragmentation (RFC 4944/RFC 6282) to carry the 1280-byte IPv6 MTU. L_max per mode:
>
> | Mode | L_max | Max data-frame airtime at rate 1/2 |
> |---|---|---|
> | C4FM / 4FSK | **127 B [MARK]** | ≈ 263 ms (155 B × 8 / 4.8 kbps + 5 ms) |
> | OFDM | **[MARK]**, e.g. 1024 B | depends on rate |
>
> A data frame MUST NOT be sent while the local node holds the voice floor; L_max bounds voice pre-emption delay to one frame airtime.

- Why 127 B: it matches the frame size 6LoWPAN was designed for and keeps one narrowband frame under about 0.26 s at rate 1/2.
- Alternative: 255 B, which takes about 0.5 s at rate 1/2.
- For 4FSK TDMA, L_max must fit one slot or a defined multi-slot burst. The slot length is not stated anywhere. **[MARK]**

### 3b. PLI rate (add to SPEC §8.1, after line 921)

> Nodes publish PLI at a configurable interval. Defaults: **30 s [MARK]** while moving (speed > 1 m/s or displacement > **50 m [MARK]**), **300 s** while stationary. Bounds: interval MUST NOT be below **5 s [MARK]** on narrowband modes and SHOULD NOT exceed 600 s. A node MAY send an immediate update on significant heading change or on MAYDAY. Net controllers MAY lower the rate per net; nodes MUST honor the slower of local and net policy.

**Budget check (estimate):**
- The §8.1 CBOR example is about 91 B. Adding OSCORE (13 B), compressed headers (about 16 B) and AEAD+CRC (28 B) gives about 148 B, or about 250 ms at 4.8 kbps.
- With 20 nodes on one net at 30 s intervals and multicast delivery, the channel load is about 17%.
- **Blocker [MARK]:** §8.1 (line 921) delivers PLI by CoAP Observe. Observe notifications are unicast per observer, so the load grows with N×(N−1): about 300% at 20 nodes. No rate is feasible under that design. Proposed fix: PLI notifications go out as Group OSCORE multicast to the net (one transmission per update). Alternatives are the draft multicast-Observe mechanism (draft-ietf-core-observe-multicast-notifications) or keeping Observe only for cross-net or higher-echelon observers.

## 4. Other concrete errors

### IRONWEED

- **I1. Voice airtime omits AEAD overhead (`SPEC.md:828–836`, §7.3).**
  - The table counts 30 B of payload, 18 B of PHY overhead and 5 ms of preamble. It omits the 24 B nonce+tag that §4.4 places in every frame (24 B cannot fit inside the 18 B).
  - With AEAD, a 3-frame Codec2 3200 burst at rate 3/4 is about 70 B coded, or about 78 ms per 60 ms of audio. That does not fit on C4FM. At rate 1/2 it is about 107 ms.
  - **[MARK]** Choose among: implicit nonce from the 2 B sequence counter plus a truncated voice tag (for example 4–8 B, SRTP-style); a lower-rate Codec2 default (1300 or 2400); or a statement that the 18 B already includes a truncated nonce/tag.
  - Uncertain: my arithmetic assumes the 18 B header sits outside the coded block.
- **I2. Frame layout contradiction (§4.4 vs §7.3).**
  - §4.4 (line 146) says "the sync pattern is the only plaintext" and §4.6.1 (line 181) says everything after sync is FEC-coded.
  - §7.3's airtime math treats the 18 B "PHY Header" as uncoded. Its diagram (lines 846–862) puts "Preamble + sync" *after* the payload.
  - Fix: put preamble and sync first, and state whether the PHY header sits inside the encrypted and coded block.
- **I3. Effective throughput ignores the RS(24,12) outer code (`SPEC.md:187–188` vs table at 211).**
  - RS(24,12) is rate 1/2. If it is concatenated on all frames, rate 3/4 gives 3.6 kbps, not 7.2.
  - Fix: either state that RS applies only to the header (as in P25), or recompute the table. **[MARK]**
- **I4. Nonce length (`SPEC.md:144`).**
  - AES-GCM and ChaCha20-Poly1305 take 12-B nonces, but only 8 B are sent.
  - Link keys come from the mesh-wide group key (line 156), so every sender shares one key.
  - Fix: specify the 4 implicit bytes and the 8 explicit bytes so that (key, nonce) cannot repeat across senders. For example, implicit = sender short ID and explicit = 64-bit frame counter. Also require rekey before the counter wraps.

### LICHEN

- **L1. False link-encryption claim (`spec/06-security.md:49`).**
  - The §8.2 diagram shows "AES-128-CCM (optional)" link encryption, which contradicts `02-physical-link.md:267`.
  - Fix: replace it with "no encryption (E bit MUST be rejected, 02 §4.2)".
- **L2. False anonymity claim (`spec/12-apps.md:1895`, §18.10.5).**
  - The spec says a Group OSCORE context gives "sender unlinkability ... receiver knows the sender is in the group, but not which member" and makes this the RECOMMENDED mode.
  - That is wrong. In group mode every message carries a countersignature made with the sender's private key, and recipients identify the sender by verifying it with that member's public key (draft-28 §1, §2.6.3, §3.1). The per-hop link signature and SIID also reveal the first-hop transmitter.
  - Fix: delete the claim and the RECOMMENDED. State that no OSCORE mode hides the sender from group members. If unlinkability is wanted, it needs a separate design. **[MARK]**
- **L3. Invalid IPv6 example (`spec/12-apps.md:1530`, §18.8.3).**
  - `ff35:0040:0200:1234:5678:9abc:0001::0001` has 8 explicit groups plus `::`, which RFC 4291 §2.2 does not allow.
  - The template at line 1525 also uses a 16-bit group ID, but RFC 3306 defines a 32-bit one.
  - Fix: use `ff35:40:200:1234:5678:9abc:0:1` (consistent with line 1210) and make the template's group ID 32 bits.
- **L4. Wrong section reference (`test/vectors/README.md:208`).**
  - It cites "spec 18.6" for group keys, but 18.6 is Check-In.
  - Fix: cite §18.8.2 and §18.8.5 (the grace period is at `12-apps.md:1469`).
