# Review 3: IMP3 (implementability)

Scope: `git diff 9e7711f HEAD -- spec ARCHITECTURE.md profiles guides`, read as one client implementer and one relay implementer.

### IMP3-1: Stamped-Commit "counts" rule mixes sender-chosen `ts` with arrival time, so online and catching-up members fork
- Severity: P1
- Location: spec/05-messaging.md:31, spec/05-messaging.md:34
- Evidence: "**Published in time.** The `ts` of the routing envelope carrying it (§5.2.2) is no more than 10 seconds after the `ts` of its stamp" and "a member keeps its epoch N state until 15 seconds after the stamp `ts` of the Commit it applied for epoch N, and switches to a counting Commit at an earlier position that arrives in that time; it discards Commits for epoch N that arrive later."
- Problem: Two different tests decide the winner. (1) "Counts" is judged from the routing envelope `ts`, which the committer writes inside `signed`; nothing checks it against arrival (a Relay only rejects `ts` more than 300 s ahead, §11.4). (2) Online members use arrival time against their own clock for the 15 s hold. Consequences an implementer cannot avoid:
  - Commit A at position 1 with an honest or backdated envelope `ts` reaches online members after their 15 s hold (gossip delay, or a deliberate late publish). Online members applied B (position 2) and discard A. A member that was offline fetches history, sees both, processes "in stamp order", finds A counts by its `ts`, and applies A. The group splits silently.
  - Any member with commit rights can cause this on purpose: stamp, wait, publish with envelope `ts` = stamp `ts` + 1 s.
  - The 10 s and 15 s tests compare the committer's clock and the member's clock with the sequencer's clock, while §12 tolerates 300 s of skew. A committer whose clock runs 11 s ahead never "counts" and livelocks; a member whose clock runs behind holds the window far longer than others.
- Suggested fix: Make "counts" depend only on data every member sees identically. Options: have the sequencer record publication (the committer submits the full routing envelope, or a second "published" stamp, and only Commits whose envelope `id` is in the log count); or drop the arrival-time hold entirely and define the winner as the lowest-position stamped Commit whose envelope is retrievable from the sequencer log, which the committer must upload with the stamp request (op already equals the `sealedEnvelope`, so the sequencer can serve it).
- Needs decision: yes. (a) sequencer-logged envelope, the log is authoritative and arrival time is irrelevant; (b) keep envelope `ts` but require Relays to reject envelopes whose `ts` differs from arrival by more than a few seconds (still clock-dependent, does not fix history replay); (c) accept the fork and document recovery. Recommend (a): the sequencer already holds `op`, which is the exact `sealedEnvelope` bytes, so "first stamped op that validates" is decidable from the log alone and needs no clocks.

### IMP3-2: Blobs uploaded before an admission key rotation become unreachable by pull-through, seeding and pinning
- Severity: P2
- Location: spec/10-relays.md:637, spec/10-relays.md:650, spec/10-relays.md:656, spec/10-relays.md:658, spec/10-relays.md:660, spec/10-relays.md:173-176
- Evidence: "Each blob is held under the `channelToken` for which it was uploaded or replicated."; Peer GET: "404 if this relay does not hold the CID under that token"; Fetching: "with `token` set to the channel's current `channelToken`"; "A Relay MUST NOT pull, push or cache blobs for a token not registered with it."; pin: "it exempts each listed CID that it holds under that token".
- Problem: Admission keys rotate on every removal and at least every 30 days for broadcast. After rotation:
  - A client fetches an old attachment with `token` = current token. A Relay lacking it pulls with the current token; every peer holds it under the old token and answers 404. Pull-through fails for every pre-rotation blob.
  - A Relay added after the rotation (Relay replacement, retirement successor in guides/relay-operator.md) only has the current token registered, so it may not hold, pull or be seeded with any pre-rotation blob, and `seed` is signed with the current key for the current token.
  - Pinning an old Message's attachment (the main use of pins) needs an instruction for the token the blob is held under; once the old key is deregistered the Relay answers `token-withdrawn`, and an instruction for the current token gets `unknown-cid`.
  So the retention and replication guarantees silently hold only within one key epoch.
- Suggested fix: Decouple blob custody from the per-epoch token. Either (a) on registration with `replaces`, the Relay re-homes every blob held under the replaced token to the new token (the Relay already links them, §10.5.3), and peer GET/POST, pull-through, seed and pin match a blob held under the named token or any token it replaced; or (b) clients send the token under which the blob was uploaded (they keep earlier tokens, §5.2.2) and Relays keep serving pull/pin for deregistered tokens of a current agreement until retention ends.
- Needs decision: yes. (a) re-home on `replaces`; (b) per-blob original token. Recommend (a): one rule at the Relay, no client bookkeeping, and `replaces` already exists.

### IMP3-3: No trust level grants the new Peer API blob endpoints
- Severity: P2
- Location: spec/10-relays.md:173-183, spec/10-relays.md:233 (trust table, §10.2.4)
- Evidence: "Trust level determines which Peer API operations a Relay is permitted to invoke"; Level 1: "`announce`, `health`"; Level 2 ("7+ days of sustained peering"): "Full gossip; `peers` accessible". The new endpoints say only "Authenticated."
- Problem: One Relay implementation will allow blob push/pull at Level 1, another only at Level 2 or 3. Under a Level 2 reading, a Relay the CO newly adds (the replacement path of §10.4.4 and §10.3.5) cannot pull or receive blobs for 7 days, so eager replication to it and pull-through from it fail exactly when they matter.
- Suggested fix: Add the blob endpoints to the table and state the gate explicitly: permitted at Level 1 or higher, and only for a `token` registered with both Relays (which the 404 already enforces).
- Needs decision: no

### IMP3-4: DM admission host handover resets `keyEpoch`, colliding with the "highest keyEpoch" member rule
- Severity: P2
- Location: spec/04-access-control.md:262-273 (§4.6.4), spec/05-messaging.md:267, spec/04-access-control.md:167
- Evidence: §4.6.4 step 1: "That host generates a new admission key, registers it (§10.5.3) and serves it"; §5.2.2: "A member signs every envelope it publishes to the channel with the admission key of the highest `keyEpoch` it holds ... When it obtains a higher `keyEpoch`, it subscribes to the new token"; `GET <host>/admission-key/<groupID>/<keyEpoch>`.
- Problem: §4.6.4 says nothing about the new host's `keyEpoch`. A new host starts at 0 like any first key. A member holding epoch 3 from the old host, applying §5.2.2 literally, keeps signing with the old host's key and never moves to the new token, and the new-token subscription rule ("higher `keyEpoch`") never fires. Per-epoch history fetch (`/<keyEpoch>`) is ambiguous across two hosts. Also `replaces` is not set across hosts, so a sequencer-free DM is fine but Relays cannot link, which is intended; only the epoch ordering is broken.
- Suggested fix: Require the new host's first `keyEpoch` to be one greater than the old host's current `keyEpoch` (the handing-over client knows it and can put it in the creation `DMMembers` or a new field), or state that a change of `agora_admission_host` supersedes all keys of the old host regardless of `keyEpoch` and members key history fetches by (host, `keyEpoch`).
- Needs decision: yes. (a) continue the epoch counter across hosts; (b) host change resets ordering. Recommend (a): keeps §5.2.2 unchanged.

### IMP3-5: DMMembers has no read path, no recovery from 409, and no cleanup when the Commit it accompanies loses
- Severity: P2
- Location: spec/04-access-control.md:166-175, spec/04-access-control.md:177-199
- Evidence: Endpoints are only `GET .../<groupID>`, `GET .../<groupID>/<keyEpoch>`, `PUT .../members`. "`409` to a `seq` or `ts` that is not later than the current list's". Addition: "keeps every DID and every `complianceLoggers` entry of the current list"; "The committer of every Commit that adds a DID ... MUST send this addition and receive a `204` before it delivers the Welcome."
- Problem: The Addition and Removal rules are defined relative to the host's current list and `seq`, but no client can read either. `DMGroupDescriptor` carries no `seq`, and the host list can drift from MLS membership (a removal PUT that was never sent because the committer went offline, a leaver that crashed). Then:
  - Two members change membership concurrently; the second gets 409 and cannot learn the current `seq` or list, so it guesses or gives up.
  - An Add whose Commit later loses the canonical-Commit race (DMs have the 5 s no-sequencer rule) has already put the DID on the host list, because the PUT precedes the Welcome. No rule removes it, so a DID that is not in the group keeps getting the admission key.
  - Drift makes every later Addition or Removal fail with 403 forever, since "keeps every DID" or "differs only by removal" no longer holds against the client's view.
  - Unreachable host or rejected removal: no retry or fallback is defined for the "MUST send this removal" duty, including the leaver who deletes its state afterwards.
- Suggested fix: Add `GET <host>/admission-key/<groupID>/members` returning the current signed `DMMembers` to authenticated listed members; on 409 or 403 the client re-reads, recomputes from MLS membership and retries; require the committer of a losing Add (or any member noticing a listed DID with no leaf, other than loggers) to send a removal; state retry-with-backoff for removal and that a leaver keeps retrying before deleting state, or that remaining members send it.
- Needs decision: no

### IMP3-6: SpaceMembership "each record replaces the previous one" has no ordering between devices
- Severity: P2
- Location: spec/02-identity.md:525
- Evidence: "Each record replaces the previous one. A device sends a new record whenever the user joins or leaves a Space or a Space's endpoints change."
- Problem: The self-group has no sequencer and MLS gives no total order of application messages from different senders. Two devices that each join a different Space at about the same time each send a full list missing the other's Space. Which one is "previous" differs by device and by arrival order, so implementations diverge, and a new device added later can be missing a Space, which then fails own-device Welcome validation and channel key fetches (the record's stated purpose).
- Suggested fix: Define a merge: each record carries the sender's view plus a per-entry `joinedAt`/`leftAt` (or a per-device record and the union across devices), and a receiving device merges rather than replaces; or require a device to merge the latest record it holds from every other device before sending.
- Needs decision: no

### IMP3-7: Eager replication MUST has no timing, retry or failure path
- Severity: P3
- Location: spec/10-relays.md:647-652
- Evidence: "A Relay that accepts an upload MUST copy the blob ... until it is held by at least `replicationFloor` Relays including itself ... or by every Relay carrying the token if fewer carry it."
- Problem: Not stated: whether replication completes before the upload response (so a sender knows the floor is met before posting the Message) or after; what to do when peers answer 507 or are unreachable (retry schedule, give up); how "every Relay carrying the token" is known when the gossipsub mesh is only D peers. guides/relay-operator.md has an `agora_relay_blob_below_floor` gauge "because no further peer accepted them", implying giving up, which the MUST does not allow. Uploader-relay crash before replication loses the only copy with no signal to the client.
- Suggested fix: State that replication is asynchronous after the 201, retried with backoff for a bounded period (name it), and that a Relay that cannot reach the floor after that keeps its copy and stops; or say a client MAY upload to a second Relay when it needs the floor guaranteed.
- Needs decision: no

### IMP3-8: Non-member subscriber has no refresh rule for the `broadcasters` list
- Severity: P3
- Location: spec/05-messaging.md:211, spec/03-spaces.md:313
- Evidence: "A non-member subscriber MUST NOT display a post whose `senderDID` is not listed for the channel in the newest `broadcasters` list it holds."
- Problem: No fetch interval or trigger is given. After the CO adds a broadcaster, clients with a stale view drop that poster's posts, others show them, with no rule saying when the drop is final.
- Suggested fix: On a post from an unlisted `senderDID`, the client re-fetches the non-member view (rate-limited) before deciding, and re-fetches at least as often as it fetches the `BroadcastKey`.
- Needs decision: no

### IMP3-9: DMMembers minor ambiguities (status code, one Commit with Add and Remove)
- Severity: P3
- Location: spec/04-access-control.md:175, spec/04-access-control.md:194-198
- Evidence: "its `ts` is within 300 seconds of the host's clock"; codes listed are 400/401/403/404/409/429. Addition and Removal are each "only" one direction.
- Problem: No code is assigned for a `ts` outside 300 s or a bad signature (400 or 403 diverge). A single MLS Commit that adds and removes needs two PUTs whose `ts` must strictly increase; with second-precision RFC 3339 timestamps the second PUT in the same second gets 409.
- Suggested fix: Assign 403 (or 400) to signature and freshness failures; state that a Commit with both changes sends the removal then the addition with `seq` +1 each, and that `ts` comparison uses full precision or that `seq` alone orders lists.
- Needs decision: no

### IMP3-10: Conformance table misses new client and CO-archive duties
- Severity: P3
- Location: spec/01-overview.md:79; spec/10-relays.md:656, spec/10-relays.md:670-676 (§10.4.4)
- Evidence: Client row cites §5, §14.2 to §14.4 but not §10.4.4, which now holds client MUSTs: "A client MUST verify that the bytes it receives hash to the requested CID ... whatever the source", "Relays, clients and the CO MUST NOT announce on ... the public IPFS network", "Devices of different members MUST NOT exchange blobs directly, and clients MUST NOT announce themselves ... by mDNS". The `ChannelAdmissionKey` `archive` ("serves the channel's blobs at `GET /v1/agora/blob/{cid}`") belongs to no class.
- Problem: A client claiming the Client class need not implement the fetch order, CID verification or the no-public-IPFS and no-mDNS rules; no class obliges an archive to implement the blob GET semantics (CORS, CID-addressed, unauthenticated) that clients will call.
- Suggested fix: Add "§10.4.4 (blob upload, fetch and exchange limits)" to the Client row, and add the `archive` blob GET to the Space endpoint row (or a new "CO archive" row).
- Needs decision: no

No other implementability defects found in the delta. Checked and found consistent: SFU `keyEpoch` removal, `stream-closed` code placement (§11.4, §14.4.3, §10.5.3), envelope `id` over `signed` bytes and Publish dedup, `replaces` semantics, chunked blob layout and root-block encoding, KickLift schema and type-table entries, Appendix A/B entries for the new identifiers.
