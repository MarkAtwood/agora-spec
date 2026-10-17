# CRY2: cryptographic correctness of the new constructions (final pass)

Lens: channel admission key, channelToken, admissionSig, envelope id, sealed envelope, canonical Commit and commitStamp, SFrame and data channel keys, content-key blobs, device binding, PRF wrapping, compliance verification, recording, JWS multi-signer, HTTP PoW, broadcast keys, guardian transfer, witnesses. Prior CRY-1..25 were checked against reconciliation.md and are not re-reported.

### CRY2-1: Commit streams are keyed to `channelToken`, so the sequencer rule forks the group across an admission-key rotation
- Severity: P1
- Location: spec/05-messaging.md:27; spec/14-jmap.md:157-162, 207, 238; spec/05-messaging.md:256; spec/10-relays.md:839
- Evidence: "with `stream` set to the channel's **commit stream**, `SHA-256("agora/commits/v1" || channelToken)`"; "If an earlier position holds an `op` that opens under the same epoch's sealing key and associated data (§5.2.2) to a Commit, its Commit has lost"; "Of two such Commits for one epoch, the one whose stamp has the lower `n` wins"; sequencer admits when "`channelToken` and `keyEpoch` MUST match a key registered under its agreement and not deregistered"; members sign "with the admission key of the highest `keyEpoch` it holds"; old key deregistered "after a grace period RECOMMENDED to be 300 seconds".
- Problem: The CO rotates the admission key on every removal. For the following ~300 s, members that have fetched keyEpoch k+1 submit Commits to the k+1 commit stream, while members that have not yet fetched it submit to the k stream. The sequencer accepts both. Each committer looks only at its own stream, finds no earlier Commit, and publishes. Members then compare `n` across two unrelated streams (or each rejects the other's stamp as "not the channel's commit stream"). The sealed-envelope AAD contains `channelToken`, so the "opens under the same associated data" check cannot see the other stream either. The "Closing a stream" rule in §14.4.4 covers operation streams only. This brings back the fork the sequencer exists to prevent, right after removals, when follow-up Commits are most likely.
- Suggested fix: Make the commit stream independent of `keyEpoch`, e.g. `SHA-256("agora/commits/v1" || mlsGroupID-derived value)`. That would expose a stable per-group value to the sequencer, so a better option is a per-channel random `commitStreamID` that the CO issues in every `ChannelAdmissionKey`, unchanged across rotations. Alternatively, add a closing rule for commit streams: position 0 of the new stream must name the closing head of the old one; a committer must read both streams during the grace period; and a Commit stamped on a stream after its close loses.
- Needs decision: yes. (a) Stable CO-issued `commitStreamID` carried in `ChannelAdmissionKey`. The sequencer then links a channel across rotations, which §6.6 and §12.3 already accept for relays and SFUs. (b) Per-token streams plus an explicit commit-stream close/handover rule. (c) Freeze Commits while a rotation is in its grace period. Recommend (a): smallest change, no new protocol state machine.

### CRY2-2: A stamped but unpublished, or invalid, Commit wins the epoch, and nobody can make progress
- Severity: P2
- Location: spec/05-messaging.md:27, 30; spec/14-jmap.md:218-220
- Evidence: "If an earlier position holds an `op` that opens ... to a Commit, its Commit has lost."; "A client whose Commit lost discards it ... and ... re-proposes it as a new Commit for the winning epoch."; for commit streams, "the client carries the stamp in the Commit's routing envelope instead"; "If a submitter fails to publish step 4, any member holding the pair MAY publish it" (stated for operation streams only).
- Problem: The rule only asks whether the earlier `op` decrypts to a Commit. It does not ask whether that Commit is valid or was ever published. If a committer crashes after being stamped, or a malicious member submits a well-sealed but invalid Commit (or a valid one it never publishes), every later committer for that epoch concludes it lost and waits for a winning epoch that never arrives. The group cannot change membership until the next rotation changes the stream. A member facing removal can front-run each Remove this way for as long as its admission key stays registered.
- Suggested fix: A committer that finds an earlier stamped Commit MUST process it. If the Commit is invalid, the committer ignores it and treats the next valid one as the candidate. If it is valid and absent from the channel after T seconds, any member MUST publish it by wrapping the log's `op` and stamp in a routing envelope with `commitStamp`. Members apply the lowest-`n` *valid* stamped Commit.
- Needs decision: no

### CRY2-3: Envelope `id` covers unsigned bytes, so any forwarder can change it, yet it decides Commit races and message order
- Severity: P2
- Location: spec/05-messaging.md:28, 218, 244, 248; spec/10-relays.md:756; spec/06-calls.md:495; spec/14-jmap.md:114; spec/07-compliance.md:130
- Evidence: "The envelope **`id`** is the CIDv1 of the complete encoded `RoutingEnvelope` ... because relays forward those bytes unchanged, every holder computes the same `id`"; "`powProof` ... lies outside `signed` ... the envelope `id` covers it"; no-sequencer rule: "applies the Commit whose envelope `id` ... is lowest"; §6.14 "messages are compared by MLS epoch ... and then by routing envelope `id`".
- Problem: Only `signed` is authenticated. The outer CBOR map (key order, length encoding) and `powProof` (any nonce meeting the difficulty) can be re-encoded by any relay or gossip peer without the admission key, which gives the same `signed` bytes a different `id`. When two Commits race in a DM or in a Space with no sequencer, one malicious relay can hand different members variants whose ids flip the winner, and split the group even while other relays deliver everything promptly. The same trick reorders §6.14 call coordination (first `CallResponse` or `LobbyDecision` wins) and the §14.3.3 last-writer-wins tiebreak, and it defeats id-based deduplication, pin instructions and `outerEnvelopeCID`. The claim that every holder computes the same `id` holds only for honest forwarders.
- Suggested fix: Define `id` as the CID of the `signed` byte string, which only an admission-key holder can produce. Alternatively, use SHA-256 of `signed` for ordering and Commit tiebreaks, and keep the whole-envelope CID for storage only. Say explicitly that `powProof` is not part of the identity.
- Needs decision: no

### CRY2-4: SFrame KID layout can make two senders share a KID, which reuses nonces under the shared `base_key`
- Severity: P2
- Location: spec/06-calls.md:222, 479
- Evidence: "`sender_index` is the sender's MLS leaf index, E = 4 epoch bits ..., S is the number of bits RFC 9605 Section 5.2 derives from the group's size"; RFC 9605 §5.2: "S be the number of bits required to encode a member index in the group, i.e., the smallest value such that group_size <= (1 << S)".
- Problem: Every member derives the same `base_key`, and RFC 9605 §4.4.2 derives key and salt from the KID alone, so a KID collision between two senders means (key, nonce) reuse. MLS leaf indices run up to the tree's leaf count. With blank leaves left by removals, that count exceeds the member count. If an implementer reads "group's size" as the member count, a leaf index ≥ 2^S spills into the context bits and can equal another sender's (context, index) pair. AES-GCM nonce reuse then exposes plaintext XORs and the GHASH key to the SFU. Data channels inherit the same rule.
- Suggested fix: State that S is the smallest value with `n_leaves <= (1 << S)`, where `n_leaves` is the leaf count of the epoch's ratchet tree including blank leaves (RFC 9420 §7.1). Add a test vector with blank leaves.
- Needs decision: no

### CRY2-5: The DM admission host accepts any listed member's unordered `DMMembers` replacement, so one member can lock the others out
- Severity: P2
- Location: spec/04-access-control.md:150-158, 259; spec/07-compliance.md:285
- Evidence: "any listed member replaces it after a membership change, by a typed payload envelope of type `urn:agora:type:DMMembers` with body `{"groupID": ..., "members": [...], "ts": ...}`, signed per §13.1.1 by a device key of a DID on the current list. When a replacement drops a DID, the host rotates the key."
- Problem: The host is not an MLS member and enforces nothing beyond "signer is currently listed". There is no `ts` window, no monotonic version and no link to MLS state. A member just removed by MLS, before the committer's update arrives, or any malicious member at any time, can PUT `{members: [self]}`. The host then rotates the key and serves it only to that member. The honest members can no longer fetch the key or replace the list, so they lose relay admission and must recreate the group. A delayed honest PUT computed before a removal can also re-add the removed DID. The self-group uses the same scheme.
- Suggested fix: At minimum, require `ts` to be within 300 s and later than the last accepted list, or better, a strictly increasing `version`. To prevent a hostile takeover: allow a signer to remove only itself, or require removals of other DIDs to carry the MLS epoch together with a confirmation from a second listed member. Alternatively, make the initiator's DID the only party that may drop others.
- Needs decision: yes. (a) Monotonic version plus "a signer may drop only itself; drops of others need k-of-n listed signers" (multi-signer JWS). (b) Only the initiator (or its successor named in the list) may drop others. (c) Accept the lock-out risk and document it. Recommend (a).

### CRY2-6: Threshold multi-signer objects don't fit §13.1.1, and nothing requires distinct signer DIDs
- Severity: P2
- Location: spec/04-access-control.md:18; spec/13-encoding.md:59, 78, 86
- Evidence: guardian proposal: "At least `threshold` of `guardian.dids` sign, per §13.1.1 as a multi-signer object"; §13.1.1: "it contains an entry for every required signer"; "A verifier MUST reject the object if any entry fails these checks, including an entry from a signer that is not required."
- Problem: §13.1.1 knows only fixed signer lists. For a k-of-n guardian proposal it is undefined which signers are "required", so a proposal signed by more than k guardians may be rejected. Nothing says two entries whose `kid`s belong to the same guardian DID (two authentication keys) count once. A single guardian with two device keys could then supply two of the k signatures.
- Suggested fix: Add a threshold mode to §13.1.1. The defining section names a candidate set and k. The verifier counts entries whose `kid` DIDs are distinct members of the set, requires at least k, rejects duplicate DIDs, and rejects entries from DIDs outside the set.
- Needs decision: no

### CRY2-7: Compliance third-party verification can't succeed for `did:key` senders
- Severity: P2
- Location: spec/07-compliance.md:142; spec/12-security.md:154; spec/05-messaging.md:73
- Evidence: step 6: "check that its `signature_key` was a device key of `senderDID` in the DID document version in effect at `ts`, using the DID log"; §5.2.1: "For `did:key`, the `signature_key` ... MUST NOT be the identity key ... Such a leaf MUST carry the `agora_device_binding` LeafNode extension".
- Problem: A `did:key` leaf key never appears in any DID document and there is no DID log. Step 6 therefore fails for every `did:key` sender, and §12.7.4's non-repudiation claim does not hold for them. The device-binding extension is the proof that should replace this check, but the procedure does not mention it.
- Suggested fix: Add to step 6: "for `did:key`, verify the `agora_device_binding` extension in `senderLeaf.leafNode` under the key the DID encodes, per §5.2.1". In §12.7.4, note that the binding cannot be revoked, so the proof shows only that the identity key holder vouched for the leaf key at some time.
- Needs decision: no

### CRY2-8: Public broadcast channels publish `channelToken`, so an IO can map a token to a Space and channel, contrary to ARCHITECTURE §5 item 6
- Severity: P2
- Location: spec/03-spaces.md:297, 311; spec/05-messaging.md:175; ARCHITECTURE.md:168-170; spec/12-security.md:31, 39; spec/11-transport.md:270
- Evidence: "For `public`, the CO publishes the channel's `BroadcastKey` and the subscriber form of its `ChannelAdmissionKey` as public Space state"; the subscriber form "carries `channelToken`"; ARCHITECTURE: "An IO MUST NOT be able to map an admission key to a Space or channel"; §12.3 says a Relay cannot "Map a `channelToken` or admission key to a channel, Space or member".
- Problem: Any relay can fetch public Space state and read the channel's token for every key epoch. It can then attribute that channel's traffic volume and timing, plus push registrations and subscriber addresses, to a named Space. The decision to publish the content key for public channels is binding, but the text also publishes the routing token without qualifying the absolute claims in ARCHITECTURE §5, §12.3 and §11.7.1. §14.4.6 already carves out this exception for the sequencer.
- Suggested fix: Either qualify ARCHITECTURE §5 item 6, §12.3 and §11.7.1 ("except tokens of `keyAccess: public` broadcast channels, which the CO publishes"), or keep tokens unlinkable: the public record carries only the `BroadcastKey`, and readers obtain the subscriber form from the Space endpoint unauthenticated without it being mirrored. The second option only moves the exposure to whoever queries the endpoint.
- Needs decision: yes. (a) Accept and qualify the claims. (b) Stop mirroring the subscriber form and serve it only on request. (c) Route public broadcast channels through a dedicated billing DID per public Space. Recommend (a).

### CRY2-9: `channelToken` derived from the admission seed mixes two uses of one secret and conflicts with the HSM guidance
- Severity: P3
- Location: spec/05-messaging.md:255; spec/13-encoding.md:148; spec/12-security.md:167; ARCHITECTURE.md:241-243
- Evidence: "`channelToken = HKDF-SHA256(IKM = seed, ...)`, where `seed` is the 32-byte Ed25519 private key seed"; §12.8: "the channel admission private keys the registration service issues ... SHOULD be held in an HSM".
- Problem: The same 32 bytes feed SHA-512 (RFC 8032 §5.1.5) for signing and HKDF for the token. There is no known attack, but it breaks the key-separation rule the registry otherwise follows, and it ties the token to private-key bytes. That buys nothing: relays get the token in the registration, and broadcast subscribers get it directly in the subscriber form. It also requires the raw seed to be exportable, so the §12.8 HSM recommendation for admission keys cannot be met. (The seed is served to every member in any case.)
- Suggested fix: Have the CO generate a separate 32-byte `rootSecret` per `keyEpoch` and derive both `seed = HKDF(rootSecret, "agora admission seed" || keyEpoch)` and `channelToken = HKDF(rootSecret, "agora channel token" || keyEpoch)`, serving `seed` and `channelToken` in the record. Alternatively, have the CO choose a random token and carry it in `ChannelAdmissionKey`. Drop admission keys from the §12.8 HSM list, or say they are distributed secrets.
- Needs decision: no

## Areas checked with no new defect

- Sealed envelope: random 96-bit nonce, 2^20 per-leaf cap × 4096 leaves = 2^32 (NIST SP 800-38D §8.3); exporter label and `group_id` context; AAD binds token and epoch. Correct, apart from the stream issue in CRY2-1.
- admissionSig domain separation across envelope (`ctx`), SFU join (`ctx`), PinInstruction, upload and sequencer `seq-auth` (`op` values). Sound.
- SFU admission: SFU DID and 30 s single-use nonce inside `signed`; `clientNonce` echoed in signed SDP. Sound.
- Content-key blob, group-encrypted blob, asset blob, history blob: per-object keys or exporter keys, random nonces, distinct AAD labels. Sound.
- Broadcast: AAD binds token; inner JWS binds `channelID`, `keyEpoch` and poster; 2^32 cap stated; the earlier CRY-23 dual use is gone.
- Device binding: the prefix `agora/v1/device-binding` cannot collide with a JWS signing input (base64url has no `/`) or a BEP-44 input.
- PRF wrapping (§12.6): extractable-then-wrap, unwrap as non-extractable; consistent with §2.2.
- Compliance `messageKeys`: the per-generation content key and the per-sample sender-data key disclose nothing beyond that message (RFC 9420 §6.3.1, §6.3.2). The FramedContentTBS includes GroupContext.
- Recording archive: HPKE info binds `grantCID`; `sealedTo` survives rotation.
- HTTP and connection PoW: single-use challenges with an expiry.
- RecoveryAssertion `prev`, witnesses, registration replay (`ts` monotonic per token): fixed as recorded in reconciliation.

Coverage: read fully: spec/02-identity.md, spec/03-spaces.md, spec/04-access-control.md, spec/05-messaging.md, spec/06-calls.md, spec/07-compliance.md, spec/08-cross-space.md, spec/11-transport.md, spec/12-security.md, spec/13-encoding.md; spec/14-jmap.md §14.3-§14.5; spec/10-relays.md §10.2.3 and §10.5; spec/99-appendices.md Appendix C; ARCHITECTURE.md §5-§8; notes/review/reconciliation.md (CRY rows) and CRY-verified.md headings; RFC 9605 §4.4.2 and §5.2. Grepped guides/, profiles/, PRFAQ.md, PROPOSAL.md and README.md for stale admission-design text (none found). Not read: spec/01, spec/09, the rest of spec/10 and spec/14, and the non-normative profiles and guides in full.
