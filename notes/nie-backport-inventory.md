# nie → Agora backport inventory, 2026-10-16

Scope: the 65 commits on `~/PROJECT/nie` in `d0fe3b5..378f87d` (fork point to
nie HEAD), compared against `~/GIT/Agora-historical` (HEAD `a293312`) and the Agora spec
(`import/agora-protocol-spec-unified.md`, here SPEC). Line numbers are SPEC
lines unless a file is named.

Classes: **(a)** protocol/design to absorb into the spec · **(b)**
implementation hardening only · **(c)** nie-only, leave behind.

Method and confidence. I read the commit list and diffstats directly. Detailed
diff inspection for themes T1, T3–T6 was done by three read-only subagents
grepping `git show` output; their results are summarized here. I spot-checked
four of their claims myself (Agora `core/src/hpke.rs` seals with empty AAD;
Agora `desktop/src-tauri/src/lib.rs` `send_chat` broadcasts an unencrypted
`ClearMessage::Chat`; Agora `cli/src/commands.rs:~818` joins from any binary
whisper as a Welcome; nie `cli/src/commands.rs:997–1002` `group_contains`
guards, which fit the multidevice add bug). "Still in Agora" means the guard
or function was not found by grep in Agora. That is cheap evidence, not proof.

## Summary table

| # | Theme | Commits | Class | Maps to (SPEC) | Separation impact |
|---|---|---|---|---|---|
| T1 | Multidevice relay + per-device KeyPackages | 4de8a35 e9a99a7 f576413 (+a03c5d8 KP cap) | (a) partly, mostly cautionary; (b) | §2.2 Device Keys (l.100), §6.1.1 KeyPackage Store (l.1114–1302) | Neutral. The design conflicts with SPEC's atomic consume, and SPEC is right |
| T2 | JMAP Chat daemon, Space/Channel/Contact model | 31a82cf 48105f8 4634990 a7a2979 | (a) | §8.8 JMAP (l.2132–2356), §3.2–3.3 Space, §9.2 Roles, §9.3 Invites | **Respects.** JMAP state lives in the client daemon, and the relay learns nothing |
| T3 | JMAP review-fix rounds (RFC 8620 conformance, invite/role authZ) | 61f46ce 8325e58 c8bf9c7 ecb97a8 239d941 18000ea d1f9dd6 8e3760d 6edecdb 91cbc6d 24761ef 2fd042a 753fc49 7b884c3 4037366 ca15355 4ff361e 4dabff6 (+a03c5d8 daemon) | mostly (b); a few (a) | §8.8.5 methods, §9.3 invites | Neutral |
| T4 | Peer/* federation inside MLS + typing | 4634990 (+a03c5d8 authZ fixes) | (a) | §6.3 Message Types (l.1441), §7.2 Typing (l.1813), §9.5 Moderation (l.2418) | **Typing via relay RPC violates; Peer/* inside MLS respects** |
| T5 | Relay/core security hardening | a03c5d8 (relay/, core/) | (b) mostly; 3 items (a) | §6.2 Sealed Envelope (l.1401), §8.6 handshake (l.1900–1987), §6.1 Welcome handling | Respects (content-agnostic limits) |
| T6 | Client/bridge hardening | a03c5d8 (cli tui bot bridge-* wasm desktop daemon) a92f7aa 045fff5 4d780f1 5f9cc48 ea9162b | (b); a92f7aa also (a) | §6.7 TextBody (l.1591) for bidi | N/A |
| T7 | MLS epoch HPKE + deps | 935be0d 0c0f236 302ca33 | (b), **already in Agora** | n/a | N/A |
| T8 | Flutter/Android client + Codemagic CI | a25a1d1 b40ce2b 8610f9b 6555afa 8e4a840 9992a90 6da1448 0c46ab6 461434f f079004 b42953d 948d4af b5dd86a e09eb3e 5bbdd9e 0ca3862 1114f7f cf70755 c0dd987 1e8a66f ab5af84 2ace35e 4aaed50 00a615c a7fc362 | (b), minor (a) | §8.7 Push (l.2016) | Neutral |
| T9 | Payments / subscriptions | a03c5d8 (wallet/ payment_watcher nie-monero bot/payment) 5f7d654 | (c) | n/a | n/a |
| T10 | Docs, transparency log removal | 0014fc3 d325296 a55b174 | (c), plus one decision | OPS / LEGAL | Decision needed (see T10) |
| T11 | Beads tooling | 6067e35 378f87d | (c) | n/a | n/a |

Count check: 3+4+18+1(a03c5d8)+5+3+25+1+3+2 = 65. a7a2979 is listed under T2, 61f46ce under T3 (it also touched Flutter), and a03c5d8 spans T3, T5, T6 and T9.

---

## T1. Multidevice (4de8a35, e9a99a7, f576413; cap in a03c5d8)

What nie did:
- `core/src/protocol.rs`:
  - `PublishKeyPackageParams.device_id` (64 lowercase hex, checked in `relay/src/ws.rs`).
  - `GetKeyPackageParams.device_id: Option`. With no id, the relay returns all devices.
  - `GetKeyPackageResult.data` is now `Vec<Vec<u8>>`. This breaks the wire format.
  - `KeyPackageReadyParams.device_id`.
- `relay/src/state.rs` (e9a99a7):
  - The client map holds `Vec<(tx, seq)>` per identity, so one identity can have N connections.
  - Delivery fans out to all of them.
  - `USER_JOINED`/`USER_LEFT` fire only on 0→1 and 1→0 transitions (f576413).
- `relay/src/store.rs` (f576413):
  - `key_packages` primary key is `(pub_id, device_id)`.
  - A `PRAGMA user_version` migration moves old rows to `device_id='legacy'`.
  - a03c5d8 adds `MAX_KEY_PACKAGES_PER_USER=10` and an 8 KiB size cap per KP.
- `device_id` = SHA-256 of the KP's HPKE init key (`core/src/mls.rs` `key_package_and_device_id`).

Problems. These matter for the spec because nie's design should **not** be copied:
1. **KeyPackages are not consumed on fetch.** The relay serves one KP per device repeatedly, and deletes it when the publishing connection disconnects. That conflicts with SPEC l.1116/1131/1159, which require atomic, permanent consume. SPEC is correct per RFC 9420 §16.8 (KP reuse). It also means an offline device cannot be added. Agora should keep SPEC's model.
2. **`device_id` is not a device identifier.** It is derived per-KP, so it changes with every KP. SPEC should key KP supply by the device's DID `verificationMethod` id (§2.2), not by a KP hash.
3. **The MLS add path is incomplete.** In `cli/src/commands.rs` (~l.994–1002), the admin stops adding as soon as `group_contains(target)` is true. So only the first device ever joins. Agent-reported; the guards are visible at those lines.

What to absorb (class a):
- §2.2 should state that one identity can have N simultaneous relay sessions.
- Presence join/leave is per identity, not per device. In Agora, though, the relay should not emit presence at all (see T4).
- KP store limits (per-identity count cap, per-KP size cap) belong in §6.1.1 as **policy-free infrastructure limits**. They respect separation.

Agora status: no `device_id` anywhere in `~/GIT/Agora-historical/core` or `relay`, so Agora has no multidevice. SPEC §2.2 also says revocation is "via Update commit" (l.104); it should be Remove (already in research notes).

## T2. JMAP Chat daemon and Space model (31a82cf, 48105f8, 4634990, a7a2979)

What nie did:
- Added a full RFC 8620 JMAP server to the **local client daemon** (`daemon/src/jmap.rs`, `daemon/src/store.rs`, SQLite).
- Object types: ChatContact, Chat (get/changes/query/typing), Space (get/changes/set/query/queryChanges/join), SpaceInvite (get/set), Message, plus upload, download and EventSource.
- Capabilities `urn:ietf:params:jmap:core` and `urn:ietf:params:jmap:chat`.
- `SpaceRole` = fixed enum `Admin|Moderator|Member` (24761ef). Membership is `space_member(space_id, contact_id, role)`.
- MLS bridge (31a82cf): nie has one relay-wide MLS group. Every decrypted broadcast lands in a single default channel. There is **no per-Space or per-channel MLS group**.
- The default Space roster is copied from the relay's USER_JOINED (`daemon/src/relay.rs` `dispatch_notification`).

Relation to `~/PROJECT/jmap-chat-spec`:
- nie predates that repo's first commit (2026-04-26 vs nie work on 04-23/24). It tracks an earlier draft, linked in a7a2979 as `draft-atwood-jmap-chat-00`; code comments say "JMAP-CHAT-FED".
- Names and the capability URN match.
- Divergences:
  - jmap-chat-spec roles are objects (`permissions[]`, `position`, `@everyone`) with `SpaceMember.roleIds[]`. nie uses the 3-value enum.
  - nie lacks SpaceBan, ReadPosition, PresenceStatus, CustomEmoji, Chat/set, SpaceInvite/changes and Peer/presence*.
  - jmap-chat-spec defines Peer/* as server-to-server JMAP. nie carries them as MLS broadcasts (T4).
  - Typing transport differs.

Relation to Agora SPEC §8.8:
- They are different designs. SPEC §8.8 is a **relay-served** JMAP API with `urn:agora:v1`.
- SPEC's object types are Message, Channel (with `channelToken`), Space (`memberCount`, `channelIds`) and KeyPackage. It has no roles, invites, Peer/* or typing.
- nie's daemon does not implement SPEC §8.8.

Separation analysis:
- nie's placement is the one that **respects** operator separation. The JMAP server that holds Space, membership, roles and invites runs client-side. The relay is unchanged except for the typing RPC (T4).
- SPEC §8.8 puts JMAP on the relay. That relay serves Space objects with `memberCount` and Channel objects with `channelToken`. Research notes violations #3 and #5 already flag that this leaks comms structure to infrastructure.

Recommendation (class a, high):
- Split JMAP into two profiles. (1) A **client/communications-operator API** = jmap-chat-spec, run by the client or by the Space owner's own service, never by a relay. (2) A minimal relay API limited to blind infra objects: KeyPackage, blob, opaque envelope sync.
- Drop Space and Channel from the relay JMAP surface.
- This conflicts with current SPEC §8.8.4 and is the main structural import from nie.

## T3. JMAP review-fix rounds (18 commits + a03c5d8 daemon part)

These are mostly (b): RFC 8620 conformance. The protocol-relevant decisions, which a jmap-chat profile should state, are:
- `/changes` returns `cannotCalculateChanges` with `newState` when history is unavailable, and advertises `canCalculateChanges:false`. Before the fix it reported everything as "created" (239d941, 8e3760d, a03c5d8).
- `/set` is all-or-nothing per object: validate everything, then write in one transaction (c8bf9c7, 18000ea, 91cbc6d, 24761ef).
- Unknown properties get `invalidProperties` (91cbc6d). `description:null` clears the field (6edecdb). `deletedAt:null` is rejected (4dabff6).
- `maxCallsInRequest=64` (239d941).

Class (a) for SPEC §9.3 and §9.5:
- **Invite codes need real entropy.** 4dabff6 found nie codes were `Ulid[..8]`, pure timestamp; it switched to 40 random bits. SPEC §9.3 link invites use "a short random token" with no stated entropy. SPEC should require ≥128 bits.
- **Invite issuance requires issuer authority.** 4dabff6 made `space_invite_set` check membership. SPEC §9.3 has `issuedBy` + `sig`, but it should state that verifiers check `issuedBy` holds `canInvite` in the current SpaceState. In Agora that check belongs to clients and the Space owner, not the relay.
- **Error codes must not leak existence** (a03c5d8: membership and existence checked in one query). This is a general JMAP rule.

Agora status: none of this code exists in `~/GIT/Agora-historical/daemon` (no jmap.rs or store.rs). Only related gap: `~/GIT/Agora-historical/daemon/src/ws_events.rs` accepts `?token=` without nie's later `redact_token_query_param`. Low risk, since Agora's daemon has no TraceLayer.

## T4. Peer/* federation inside MLS, and typing (4634990; authZ in a03c5d8)

What nie did:
- New `ClearMessage` variants in `core/src/messages.rs`: `PeerDeliver`, `PeerReceipt`, `PeerTyping`, `PeerRetract`, `PeerGroupUpdate{space_id,action,contact_id,role?}`.
- They are carried **inside MLS application messages**, so the relay sees only ciphertext size and timing.
- Separately, a new relay RPC `typing{typing}` makes the relay broadcast `typing_notify{from=pub_id}` to all clients. 61f46ce adds a synthetic typing:false on disconnect.
- Authorization fixes in a03c5d8:
  - `PeerGroupUpdate` is accepted only from an Admin sender. Before, anyone could promote themselves.
  - `PeerRetract` is accepted only from the original sender.
  - `receipt_type` is allowlisted.
  - The `PeerGroupUpdate.action` vocabulary changed from join/leave/role_change to add/update/remove.

Separation analysis and spec mapping:
- **Typing.** nie's relay-RPC typing **violates** separation: the relay learns who is typing. SPEC §7.2 has the same flaw, with `TypingEvent` carrying sender DID and channel in the clear (research notes violation #4). nie's *other* path, `PeerTyping` inside MLS, is the right model. SPEC §7.1/§7.2 should make presence and typing MLS PrivateMessage application data, with no relay RPC. That also fixes the RFC 9420 erratum at l.1463/2549 (ephemeral events as PublicMessage).
- **Retract vs Delete.** nie's rule is author-only retract. SPEC §9.5 l.2455 has only Admin `DeleteEvent`. SPEC should define both: author retract and communications-operator (Admin) delete. Both should be enforced by **clients** checking SpaceState authority, because the relay cannot read the inner payload. SPEC l.2961, "relay deletes cache on valid DeleteEvent", requires the relay to read and judge inner content and stays a violation. The relay can only honour an outer, separately signed purge request from the Space owner.
- **Membership updates.** nie converges per-client rosters through Admin-signed `PeerGroupUpdate`. The lesson for Agora: without an authoritative signed state, rosters diverge, and before a03c5d8 any member could forge changes. SPEC §3.3 (owner-signed SpaceState rooted at a genesis CID) is the stronger design and should be kept. nie confirms the need for the rule "membership/role changes are valid only if signed by an authority in the current SpaceState". Respects separation.

## T5. Relay/core hardening (a03c5d8 relay/, core/)

These were agent-inventoried; 22 fixes in all. Unless noted, the guard was not found in Agora, so the bug is assumed still present.

Class (a), spec-relevant:
1. **HPKE recipient binding.** `core/src/hpke.rs` info string went from `nie/sealed/v1` to `v2`, and the recipient pub_id became AAD, which blocks re-targeting a sealed ciphertext to another recipient. SPEC §6.2 Sealed Envelope (l.1401) does not specify info or AAD; grep finds no "AAD". SPEC should mandate binding recipient DID and channel context. **Agora code still has it** (spot-checked: `seal_message` passes `&[]`).
2. **Challenge freshness.** The nonce embeds a 4-byte issue time, checked against a 300 s TTL (`core/src/auth.rs` `nonce_is_fresh`). SPEC §8.6 l.1969 already requires "not expired", so no spec change. Agora code lacks it.
3. **Welcome safety.** The client must not overwrite existing group state on a replayed Welcome (`core/src/mls.rs`). With T6 items, it must accept a Welcome only from a sender authorized to add members, and never from a sealed (sender-anonymous) whisper. SPEC §6.1/§9.3 should state: "a client MUST verify the Welcome's committer is authorized by current SpaceState and MUST reject a Welcome for a group it already holds unless it is a re-join." **Agora still has the bug** (spot-checked, cli ~l.818).

Class (b), Agora still has them:
- 30 s timeout waiting for Authenticate (Agora `relay/src/ws.rs:162`) and for reading the handshake.
- Payload caps: whisper 64 KiB, group send 64 KiB, group id 128 B, KP 8 KiB.
- Empty payloads rejected.
- Groups per user and members per group capped atomically.
- Offline queue capped at 1000; drain at 100 (unverified).
- Group fan-out re-checks membership via `group_id`.
- Low-order (all-zero) X25519 key rejected.
- PoW replay set bounded at 1M; client caps PoW difficulty.
- Client checks that the relay-returned id matches its own.
- `Zeroizing` for secrets.
- Corrupt or oversized keyfile returns an error instead of panicking (Agora `core/src/identity.rs:57`).
- Unbounded recursion on `Lagged` in `LocalBus::recv` (Agora `relay/src/bus.rs:89`).
- Startup config validation (KEEPALIVE_SECS=0 panic).
- Substring-match subscription detection (Agora `relay/src/ws.rs:494`). That is payment logic, but the pattern is a bug wherever it was kept.
- Content-agnostic size limits from `core/src/messages.rs`: ids 128 B, body 64 KiB, file ≤1 GiB, ≤102 chunks. These could go into SPEC as normative limits, enforced by clients for inner fields and by relays only on ciphertext size.

Class (c): nickname uniqueness, set-once and subscription gating; TYPING requiring a subscription.

Note on separation: "relay re-checks group membership before fan-out" assumes the relay knows group membership. In Agora's SPEC the relay is the MLS DS (research notes violation #8), so the fix applies to the code as it stands. It should not be written into SPEC as a relay duty.

## T6. Client and bridge hardening

All (b). Agora status was checked by grep (agent-reported unless noted).
- **a92f7aa:** tui strips bidi controls and zero-width chars. Agora `tui/src/ui.rs:141` handles CSI only, so the bug is still there. This is also (a): SPEC §6.7 should require clients to neutralize bidi overrides and invisible format characters in rendered text and display names.
- **ea9162b:** desktop `send_chat` sent plaintext. **Still in Agora** (spot-checked: `desktop/src-tauri/src/lib.rs` ~l.106–123 broadcasts unencrypted `ClearMessage::Chat`). High severity.
- **cli** (a03c5d8), still in Agora:
  - Welcome accepted from any peer (`cli/src/commands.rs:~818`) and via sealed whisper (~l.1344).
  - Keyfile written without 0600 or atomic rename (l.97; also `config.rs:104`, `profile.rs:132`).
  - No history text cap; no `Zeroizing`.
  - `FILE_MAX_CHUNKS` 230 vs core 102 (unverified).
- **tui:** Welcome admin check missing (event.rs:418); OSC escapes not parsed; `/cat` path traversal (event.rs:1104, local input only).
- **daemon:** `pid.rs` treats EPERM as dead, so a second daemon can start (Agora `daemon/src/pid.rs:36`). `?token=` is not redacted. No EventsDropped notice.
- **bot:** hook env not sanitized (Agora `bot/src/main.rs:162`).
- **bridge-jmap:** http session URL allowed, so the bearer token can travel in cleartext (Agora `config.rs:54`). `apiUrl` not origin-checked, an SSRF risk (`jmap.rs:119`). Seen-set unbounded and not persisted (`bridge.rs:68`).
- **wasm:** **5f9cc48** callback lost on reconnect (Agora `wasm/src/api.rs:156`). Old connection not closed before reconnect. No auth timeout.
- **desktop:** `lock().unwrap()` poisoning (Agora lib.rs:110).
- **N/A in Agora:** 045fff5 (bridge-matrix absent) and 4d780f1 (ffi `client_next_event` absent). 4d780f1 also changed a `core/src/transport.rs` crypto provider (`ring` → `aws_lc_rs`); whether Agora needs that is unverified.

## T7. Already in Agora

- 935be0d (re-derive room HPKE key on every epoch) = Agora 0e62b5a. The diff is identical modulo nie/agora tokens.
- 0c0f236 (rustls) = Agora 9a9d2e3 (adapted).
- 302ca33 (OsRng) = Agora 5fd6993 (adapted). Agora went further with 4049559/a293312 (rand 0.9).

Nothing to do.

## T8. Flutter/Android and CI (25 commits)

What nie did:
- a25a1d1: an FRB client.
- b5dd86a: replaced it with a pure-Dart relay client (`lib/src/services/relay_service.dart`, `identity_service.dart`).
- Hardening:
  - Auth-failure stops the reconnect loop (1e8a66f).
  - Seed backup and restore (1e8a66f, ab5af84).
  - Android foreground service to keep the relay socket alive, with wake-lock cap, START_NOT_STICKY and permission handling (2ace35e, 4aaed50, 61f46ce, 00a615c, a7fc362).
- The remaining commits are Codemagic CI churn (`codemagic.yaml`, `scripts/cm`).

Assessment:
- (b). Agora's `android/` is a 25-line FRB scaffold and `flutter-bridge/` exposes only stateless helpers, so none of this applies.
- **Do not port the nie seed handling as is.** The seed is stored as plaintext base64 in SharedPreferences, and backup goes through the clipboard.
- Minor (a): the foreground-service approach is the no-push fallback. SPEC §8.7 should note that a persistent socket is the alternative to the push proxy and that it costs battery.

## T9. Payments (c)

- a03c5d8 wallet/, `relay/src/payment_watcher.rs`, `nie-monero/`, `bot/src/payment.rs`: about 12 relay-side payment fixes plus the large `wallet/src/db.rs`/`scanner.rs` changes.
- 5f7d654 (zcash rev audit comments).
- Leave behind. The one transferable lesson is in T5: substring-matching a JSON payload to grant rights is a bug.

## T10. Docs and the transparency log

- **a55b174** imported the Agora spec set into `nie/docs`. All 13 files in `~/PROJECT/agora/import/` are byte-identical to nie HEAD `docs/`, so there is nothing further to import. `docs/ATTIC/` (older spec drafts, including `agora-spec-patch-dm-compliance.md`) and `docs/IETF/` (RFC 9420, 9750, MIMI and MLS drafts) were not compared here.
- **d325296, a7a2979:** nie README only (c).
- **0014fc3** removed the relay's legal transparency log (`relay/src/transparency.rs`, `/transparency`) and LEGAL.md. The commit message gives no rationale. **Agora still serves it** (`~/GIT/Agora-historical/relay/src/transparency.rs`, `relay/src/main.rs:108`). Decision for Agora:
  - A per-relay warrant/subpoena log is an **infrastructure-operator** artifact and fits SPEC §11.1 "subpoena testimony" (l.2924).
  - But it is operator policy, not protocol. Recommend moving it out of the protocol and into OPS as an optional operator practice, or deleting the code to match nie.
  - Needs Mark's call. I did not infer why nie dropped it.

## T11. Tooling (c)

6067e35, 378f87d: beads backend. Not relevant.

---

## Ranked spec-relevant items

1. **Move the JMAP Chat (Space, membership, roles, invites) API off the relay** (T2). Adopt jmap-chat-spec as the client/communications-operator API, and shrink SPEC §8.8 to blind infra objects. This directly enforces operator separation and resolves research violations #3/#5. It conflicts with current §8.8.4.
2. **Typing and presence go inside MLS** (T4). Use the PeerTyping model, not a relay RPC. Fixes SPEC §7.1/§7.2 leakage (violation #4) and the PublicMessage erratum (l.1463, 2549).
3. **Welcome acceptance rules** (T5.3, T6). Accept only a Welcome whose committer is authorized by SpaceState and that did not arrive via a sealed or anonymous path, and do not clobber existing groups. Normative text for §6.1/§9.3. The bug is live in Agora's cli and tui.
4. **Sealed-envelope HPKE context binding** (T5.1). Recipient DID (and channel) as AAD, plus a versioned info string. §6.2 is silent; Agora code is unbound.
5. **Authority rules for membership, role, retract and delete are client-verified against SpaceState** (T4). Add author-retract alongside Admin delete. Strip the relay's duty to judge `DeleteEvent` (l.2961) and replace it with an outer owner-signed purge.
6. **KeyPackage model** (T1). Keep SPEC's atomic consume; reject nie's non-consuming, disconnect-scoped KPs. Key supply by device `verificationMethod`, not a KP hash. Add per-identity count and per-KP size caps as policy-free relay limits.
7. **Invite token entropy and issuer authority** (T3). Require ≥128-bit link tokens in §9.3, and verifiers check `issuedBy` has `canInvite`.
8. **Normative size limits** (T5). Ciphertext caps enforced by the relay; inner-field caps enforced by clients.
9. **Text rendering safety** (a92f7aa). §6.7 requires neutralizing bidi and invisible format characters.
10. **Transparency log placement** (T10). Operator practice in OPS, not protocol; needs a decision.
11. **Role model reconciliation** (T2). SPEC §9.2 (`channelAccess` globs), jmap-chat-spec (`permissions[]`, `position`) and nie (fixed enum) are three different models. Pick one; nie's enum is the weakest candidate.

Highest-priority code fixes for `~/GIT/Agora-historical`, if the prototype is kept: desktop plaintext `send_chat` (ea9162b); Welcome sender checks (cli/tui); HPKE AAD; keyfile 0600 + atomic write; bridge-jmap https + SSRF; relay auth timeout; `LocalBus::recv` recursion; `pid.rs` EPERM.
