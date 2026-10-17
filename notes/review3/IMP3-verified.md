# Review 3: IMP3 verification

Checked against the working tree at 46add2b. Binding decisions consulted: agora-d2-sequencer, agora-dm-removal, agora-doorkey-B, agora-ipfs, agora-q2-admission, agora-broadcast-decision.

### IMP3-1: Stamped-Commit "counts" rule mixes sender-chosen `ts` with arrival time, so online and catching-up members fork
- Verdict: CONFIRMED. spec/05-messaging.md:31 judges "published in time" from the routing envelope `ts`, which the committer sets and which a Relay rejects only if more than 300 s ahead or older than retention (spec/11-transport.md:184). spec/05-messaging.md:34 judges the hold by arrival against the member's own clock. A member online during the hold discards a late-arriving earlier-position Commit; a member replaying history later applies it because its envelope `ts` passes test 1. The fork is silent and can be caused deliberately by any committer (stamp, wait, publish with a backdated envelope `ts`). The 10 s test also compares the committer's clock with the sequencer's, while §12.9 tolerates 300 s of skew, and the §12.9 table (spec/12-security.md:185-200) does not list either commit window, so the clock dependence is undisclosed. spec/12-security.md:183 states "Message order does not depend on any clock", which this rule contradicts.
- Severity: keep P1. Silent permanent group split, triggerable by one member with commit rights.
- Fix (implements option (a), using data the log already holds: `op` is the exact `sealedEnvelope`, spec/05-messaging.md:27, spec/14-jmap.md:228):
  1. spec/05-messaging.md:29-34. Delete condition 1 ("Published in time") and the 15-second hold. Replace the paragraph after the conditions with: "A stamped Commit **counts** if it is valid: it opens under the epoch's sealing key (§5.2.2), decrypts, and is a well-formed Commit for that epoch that passes RFC 9420 §12.4.2 validation and the checks of §5.2.1, made by a sender authorized for every change it makes under current Space state (§4). A member processes a commit stream in position order with no gaps, as for an operation stream (§14.4.4 steps 1 and 2): before applying the Commit at position p it holds every earlier position of the stream, fetching any it lacks from the sequencer's log (§14.4.3), and for each epoch it applies the first Commit in position order that counts and skips the rest. A member that holds an envelope that opens under no sealing key (§5.2.2) fetches the commit stream's log from its last processed position. A member that cannot reach the sequencer to fill a gap waits. No clock is consulted. The committer's own Commit has won when every earlier position holds no counting Commit for its epoch, which it learns by fetching the log up to its own position."
  2. spec/05-messaging.md:27. Add after "publishes the Commit promptly": "Before submitting, the committer MUST persist the pending Commit and its new path secrets, since a stamped Commit counts whether or not the committer publishes it."
  3. spec/05-messaging.md:29. Replace "its `stream` is the commit stream of the routing envelope's `channelToken`" with "its `stream` is the commit stream of the `channelToken` under which the member received or fetched it".
  4. spec/14-jmap.md:228. Delete "For a commit stream, such a copy counts only within the publication window of §5.1.1."
  5. ARCHITECTURE.md:295-296. Replace "among stamped Commits published within 10 seconds of their stamp and valid under Space state" with "among stamped Commits valid under Space state; members fill gaps in the stamp order from the sequencer's log".
- Needs decision: yes. (a) the sequencer log is authoritative: first valid Commit in stamp order wins, gaps filled from the log, no clocks; (b) keep envelope `ts` and add an arrival-skew check at Relays (still clock-dependent, does not fix history replay); (c) accept the fork and document recovery. Recommend (a). Plain language: today two members can pick different winners for the same change because one uses the clock on the message and the other uses when it arrived. With (a) every member reads the same numbered list from the sequencer and picks the first valid entry, so they always agree.

### IMP3-2: Blobs uploaded before an admission key rotation become unreachable by pull-through, seeding and pinning
- Verdict: CONFIRMED, with one correction. Direct fetch still works: a Relay serves "every blob it holds" at the unauthenticated `GET /v1/agora/blob/{cid}` regardless of token (spec/10-relays.md:640), so a client that asks a Relay already holding the blob gets it. What breaks is everything keyed on the token: peer GET 404s for a blob held under the old token (spec/10-relays.md:173-176), pull-through and `seed` use the current token (spec/10-relays.md:650, :658; spec/11-transport.md:197), a Relay added after rotation cannot hold old blobs (spec/10-relays.md:651), and `pin` matches only "each listed CID that it holds under that token" (spec/11-transport.md:197) while the old token answers `token-withdrawn` after deregistration. spec/10-relays.md:854 says "Other IOs ignore `replaces`", so nothing links them today.
- Severity: keep P2.
- Fix (option (a), no client bookkeeping, no new linkage since spec/10-relays.md:582 already concedes it):
  1. spec/10-relays.md:854. Replace "Other IOs ignore `replaces`." with "A Relay that applies such a registration moves every blob it holds under the replaced token, with its pin exemptions, to the new token, charged to the same agreement and keeping its retention clock. Other IOs ignore `replaces`."
  2. spec/10-relays.md:637. After "Each blob is held under the `channelToken` for which it was uploaded or replicated" add ", or under the token that replaced it (§10.5.3)".
- Needs decision: no. Option (b) (per-blob original token) adds client state and keeps deregistered tokens alive at Relays; (a) is one Relay-side rule using a field that already exists.

### IMP3-3: No trust level grants the new Peer API blob endpoints
- Verdict: CONFIRMED. The trust table (spec/10-relays.md:233-238) lists `announce`, `health`, gossip and `peers`, and nothing for `GET/POST /v1/agora/peer/blob`, which say only "Authenticated" (spec/10-relays.md:173-183).
- Related gap found during verification: `POST /v1/agora/peer/blob` carries no admission proof. Channel topic names contain the token (spec/10-relays.md:301), so any authenticated Relay that learns a token from mesh subscriptions can push arbitrary bytes that the receiver charges to the CO's storage quota (spec/10-relays.md:651). Envelopes on the same path need `admissionSig` (spec/10-relays.md:882); blobs do not. This violates the intent of "Upload admission" (spec/10-relays.md:644: "the same member-only admission as envelopes").
- Severity: keep P2 (raise to P1 if the quota-burning gap is counted here rather than filed separately).
- Fix:
  1. spec/10-relays.md, trust table, Level 1 Permissions: append "; blob pull and push (§10.4.4) for tokens registered with the receiving Relay".
  2. spec/10-relays.md:178-183, POST description: add "The request carries the uploader's `Agora-Storage-Auth` header unchanged (§11.8.2); the receiving Relay verifies `admissionSig` against the key registered for `token` and `sha256` against the body, and does not check `expires` or `nonce`. 403 if the header is missing or fails."
  3. spec/10-relays.md:649: after "with `POST /v1/agora/peer/blob`," add "forwarding the upload's `Agora-Storage-Auth`,".
- Needs decision: no.

### IMP3-4: DM admission host handover resets `keyEpoch`, colliding with the "highest keyEpoch" member rule
- Verdict: CONFIRMED. spec/04-access-control.md:262-273 says the new host "generates a new admission key" with no epoch; keys are "numbered by `keyEpoch` from 0" (spec/05-messaging.md:265). The member duty (spec/05-messaging.md:267) uses "the highest `keyEpoch` it holds", so a member holding the old host's epoch 3 keeps using it. The "Members that process the Commit fetch the admission key from the new host" sentence says fetch, not switch. The per-epoch path ambiguity is minor: paths are already per host, and clients retain tokens rather than re-fetching by epoch.
- Severity: keep P2.
- Fix (recommend option (b), a constraint needing no new field):
  1. spec/04-access-control.md:273, replace "Members that process the Commit fetch the admission key from the new host and use the relays it lists." with "Members that process the Commit fetch the admission key from the new host, use it and the relays it lists in place of every key of the previous host regardless of `keyEpoch`, and keep the previous host's `channelToken`s only to fetch history (§5.2.5). `keyEpoch` ordering applies among keys of one host."
  2. spec/05-messaging.md:267, after "with the admission key of the highest `keyEpoch` it holds" add "from the host currently named for the group (§4.6.4)".
- Needs decision: yes. (a) continue the epoch counter across hosts, which needs the handing-over client to send the old epoch in a new field; (b) a host change supersedes all old-host keys, ordering is per host. Recommend (b): one sentence, no new field, and the old host stops serving within 30 days anyway. Plain language: when a DM group moves to a new key server, the new server's key counter starts at zero, so clients comparing numbers keep using the old key. Option (b) simply says a new server always wins over the old one, whatever the numbers.

### IMP3-5: DMMembers has no read path, no recovery from 409, and no cleanup when the Commit it accompanies loses
- Verdict: CONFIRMED, except the leaver sub-point is PARTIAL. The endpoint list (spec/04-access-control.md:168-172) has no member-list GET; `DMGroupDescriptor` carries no `seq`; the Addition/Removal rules (:194-198) are deltas against a list only the host and the last signer know. A losing Add leaves its DID on the host list (the PUT precedes the Welcome, :196) with no cleanup rule. The leaver case is mostly covered: a leaver cannot commit its own MLS removal, and "The committer of every Commit that removes the last leaf of a DID MUST send this removal" (:198) puts the duty on the committer too; what is missing is any retry rule when the host is unreachable. Note also that a losing Add of a compliance logger cannot be cleaned up, since logger entries are never removable (:200); this is harmless because the regulated member must re-add the logger anyway (§7.8.3), and the fix should say so rather than create an exception.
- Severity: keep P2.
- Fix:
  1. spec/04-access-control.md:171, add the endpoint line "GET <host>/admission-key/<groupID>/members → current DMMembers" and in Responses: "The member-list GET returns the current `DMMembers` envelope to an authenticated DID on the list."
  2. After rule 3 (:198) add: "A client whose PUT is answered `403` or `409` fetches the current list, recomputes the change from its MLS group state, and retries. The committer of an Add Commit that lost (§5.1.1) sends a removal for each DID it added that has no leaf in the winning epoch, other than a `complianceLoggers` entry, which the regulated member's client re-adds (§7.8.3). A member that finds on the host list a DID with no leaf in the group, other than a `complianceLoggers` entry, sends a removal for it. A client retries a required removal with exponential backoff until it is accepted or the group's state shows it was made."
- Needs decision: no.

### IMP3-6: SpaceMembership "each record replaces the previous one" has no ordering between devices
- Verdict: CONFIRMED. spec/02-identity.md:525 "Each record replaces the previous one"; the self-group has no sequencer (§14.4.1 sequencing is per Space), and application messages from different senders have no total order. Two devices joining different Spaces concurrently each send a list missing the other's Space, and devices converge on whichever arrived last at them.
- Severity: keep P2. Rare trigger, but the divergence persists until the next join or leave, and its effect (a later-added device cannot validate own-device Welcomes or fetch channel keys for the missing Space) is a functional failure.
- Fix (per-entry last-writer-wins, as already used for single-author types, §14.3.3):
  1. spec/02-identity.md, JSON example: add to each entry `"state": "member"` and `"at": "2026-10-16T12:00:00Z"`.
  2. Replace "Each record replaces the previous one." with "`state` is `member` or `left`, and `at` is when the sending device last changed that entry. A receiving device merges a record into the one it holds entry by entry, keyed by `space`, keeping the entry with the later `at` (on equal `at`, `left` wins), and always sends its merged record. A device keeps `left` entries so that a stale record cannot restore a Space the user left."
- Needs decision: no.

### IMP3-7: Eager replication MUST has no timing, retry or failure path
- Verdict: CONFIRMED. spec/10-relays.md:649 is an unconditional MUST; guides/relay-operator.md:1322 describes a gauge for blobs left below the floor "because no further peer accepted them", which the spec does not allow. spec/11-transport.md:396 says "The Relay then replicates", which suggests after the response but does not say so.
- Severity: keep P3.
- Fix: spec/10-relays.md:649, append: "Replication follows the upload response and does not delay it. The Relay retries Relays that are unreachable or answer `507` with exponential backoff for at least 24 hours, then stops and keeps its own copy. "Relays carrying the token" means the peers it knows to be subscribed to the token's channel topic. A client that needs the floor met before it posts the Message MAY also upload the blob to a second listed Relay."
- Needs decision: no.

### IMP3-8: Non-member subscriber has no refresh rule for the `broadcasters` list
- Verdict: CONFIRMED. spec/05-messaging.md:211 and spec/03-spaces.md:313 require checking the "newest"/"current" list but give no fetch trigger. The hourly `ChannelAdmissionKey` fetch (spec/05-messaging.md:267) covers the key, not the non-member view.
- Severity: keep P3.
- Fix: spec/05-messaging.md:211, append: "A non-member subscriber fetches the non-member view whenever it fetches the channel's `ChannelAdmissionKey` (§5.2.2). On a post whose `senderDID` is not listed, it fetches the view again, at most once a minute per Space, before it decides; until then it holds the post undisplayed."
- Needs decision: no.

### IMP3-9: DMMembers minor ambiguities (status code, one Commit with Add and Remove)
- Verdict: CONFIRMED. No code is assigned to a bad signature or a `ts` outside 300 s (spec/04-access-control.md:175, :194). The example `ts` has second precision (:184), so two PUTs within one second for an Add-plus-Remove Commit collide on the strict `ts` rule.
- Severity: keep P3.
- Fix:
  1. spec/04-access-control.md:175, Responses: replace "`403` to a change this section does not allow" with "`403` to a bad signature or a change this section does not allow", and "`409` to a `seq` or `ts` that is not later than the current list's" with "`409` to a `ts` outside the 300-second window or a `seq` that is not greater than the current list's", matching the `stale` use of 409 at spec/10-relays.md:863.
  2. :194, replace "its `seq` and `ts` are both greater than those of the list it replaces" with "its `seq` is greater than that of the list it replaces"; `ts` then serves only freshness.
  3. After rule 3 add: "A Commit that both adds and removes DIDs sends the removal, then the addition."
- Needs decision: no.

### IMP3-10: Conformance table misses new client and CO-archive duties
- Verdict: CONFIRMED, and slightly wider. The Client row (spec/01-overview.md:79) omits §10.4.4 and also §11.8.2, which holds the client's `Agora-Storage-Auth` duty for uploads (spec/11-transport.md:396). No class covers the `archive` origin (spec/03-spaces.md:297).
- Severity: keep P3.
- Fix: spec/01-overview.md:79, Client row: after "§11.1 or §11.2, §11.4, §11.6 (transport and hello);" insert "§10.4.4 (blob upload, fetch, CID verification and exchange limits); §11.8.2 (upload authorization);". Add a row: "| CO archive | CO | §10.4.4 (`GET /v1/agora/blob/{cid}`: unauthenticated, CID-addressed, `Access-Control-Allow-Origin: *`; public IPFS limits), §12.8 |".
- Needs decision: no.
