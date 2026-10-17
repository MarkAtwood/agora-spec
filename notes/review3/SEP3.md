# SEP3: operator separation (delta since 9e7711f)

Scope: every changed rule in spec/, ARCHITECTURE.md, profiles/, guides/,
checked against S1-S8, the §5 observation budget, the §6 CO-IO interface and
the §10 review test. Items already accepted in ARCHITECTURE §9 (replaces
linkage, removal inference, public broadcast token mapping, single-user
identity host, SFrame KID, host-plus-relay DM operator) are not reported.

Checked and found consistent: TURN shared secret (S3, S7, §6.4, spec §6.11
username carries no identifier); `replaces` ignored across agreements
(spec §10.5.3) so DM handover creates no cross-billing-DID link at the IO;
registrations without `keyEpoch`; sequencer commit-stream closure driven
only by CO-signed registrations (S2 holds); eager replication and Peer API
pull limited to Relays registered for the token (§5 item 4, spec §10.3.1);
community channel keys to all role holders; envelope `id` over `signed`;
identity-host billing DID rules (spec §10.5.1); no member-to-member blob
exchange.

### SEP3-1: Relay Bitswap leaks private CIDs to Relays that do not carry the token
- Severity: P2
- Location: spec/10-relays.md:652; ARCHITECTURE.md §5 item 4
- Evidence: spec: "Relays carrying the same token MAY exchange its blobs with Bitswap over the libp2p connections they hold for the channel topic, in place of the Peer API, under the same rules." ARCHITECTURE §5 item 4 allows an IO to observe "CIDs it stores or pins ... This includes CIDs it replicates to or pulls from other IOs carrying the same routing token".
- Problem: A libp2p connection is per peer pair, not per topic; two Relays share one connection for every topic and for `v1/agora/discovery`. Bitswap messages carry no token, and stock Bitswap implementations broadcast want-haves to all connected peers (or all session peers). A Relay fetching a private blob by Bitswap therefore announces the CID, and its interest in it, to peers that carry no registration for the token, which is outside the §5 item 4 budget. "Under the same rules" cannot be implemented: the receiver cannot check that a want is for a token registered with it, so it serves any CID it holds to any connected peer. The Peer API paths already carry `token` and do the same job.
- Suggested fix: Delete the Bitswap bullet for Relays. Keep Bitswap only for a user's own devices and, if wanted, the CO archive (both known peers with no token boundary to enforce). Delete "Relays carrying the same token under the CO's agreements (above)," from the Public IPFS paragraph (spec/10-relays.md:662). guides/relay-operator.md already runs Peer API only.
- Needs decision: no

### SEP3-2: A Relay may publish "public content" to public IPFS but cannot identify it without mapping tokens to Spaces, and doing so overrides the CO's retention
- Severity: P2
- Location: spec/10-relays.md:662; guides/relay-operator.md:146; ARCHITECTURE.md S1, S2, §9 ("Public content on the public IPFS network cannot be withdrawn")
- Evidence: spec: "Public content MAY be published to the public IPFS network by the CO, a member or a Relay holding it". Guide: "It also never publishes public content to IPFS, because it cannot tell public content from ciphertext by looking at the bytes." ARCHITECTURE §9: "Once announced there, copies outlive any deletion or takedown by the CO".
- Problem: (1) A Relay can tell that a blob or envelope is public broadcast content only by matching its token against tokens published in public Spaces' views, i.e. by building the token-to-Space map S1 says an IO should not need; for CO-published records (SpaceAds, public state) held under no token there is no signal at all. An IO that guesses wrong puts private ciphertext and its CIDs on the public DHT, which §5 item 4 forbids absolutely. (2) Publishing to public IPFS makes the content permanent and beyond CO takedown; that is a retention decision about community content the CO has not expressed in any form the IO can verify, which S2 reserves to the CO. The non-normative guide already concludes a Relay cannot do this safely, so the spec grants a permission the reference deployment treats as unimplementable.
- Suggested fix: Change to "Public content MAY be published to the public IPFS network by the CO or a member." Members already know the channel's `keyAccess`; a Relay never decides. If a CO wants a Relay to do it, that is a commercial arrangement outside the protocol.
- Needs decision: yes. (a) remove Relays from the permission (recommended: constraint, removes the classification problem and the S2 conflict); (b) keep it but require an explicit CO signal per token (a new agreement or registration field), which adds CO-IO coupling under S7 and a mechanism nobody needs.

### SEP3-3: Pull-through and `seed` are keyed to the current token, so a new Relay cannot obtain blobs uploaded before the last admission key rotation
- Severity: P2
- Location: spec/10-relays.md:645-658; spec/11-transport.md (`seed` in PinInstruction); spec/10-relays.md:871; spec/04-access-control.md:266-273
- Evidence: "Each blob is held under the `channelToken` for which it was uploaded or replicated." Peer pull: "404 if this relay does not hold the CID under that token." Client fetch: "with `token` set to the channel's current `channelToken`". "A Relay MUST NOT pull, push or cache blobs for a token not registered with it." The CO registers "every current key with an IO that it engages".
- Problem: Rotation happens on every authorized removal, so most channels have blobs held under earlier tokens. A Relay added after a rotation is registered only for the current token. Its pull-through or `seed` fetch asks peers for the CID under the current token; peers hold it under the old token and answer 404; the new Relay may not pull under the old token because that token is not registered with it. The "Relay replacement" flow therefore recovers only blobs uploaded since the last rotation, and only the CO archive (optional) covers the rest. The same holds after a DM admission host handover (spec §4.6.4): the new host's Relays carry a new token under a different agreement, the old host's Relays never carry it, and once the old host deregisters (30 days) earlier DM attachments are reachable only from members' stores. Separation note: the obvious workaround, Relays serving and pulling by CID regardless of token, adds nothing to what an IO learns (the client blob GET is already unauthenticated and token-free), and the token linkage it reveals is already disclosed by `replaces`; so the fix has no separation cost, whereas leaving it lets implementers invent ad hoc cross-token pulls.
- Suggested fix: State that a Relay answers a Peer API pull for a CID it holds under any token in the same `replaces` chain under the same agreement as the requested token, and that a pull-through or `seed` fetch stores the result under the requested (current) token. For DM handover, state that blobs from before the handover are available only from members' stores and the old host's Relays until it deregisters, and that clients SHOULD keep attachment blobs they need, or have the new host's members re-upload.
- Needs decision: yes. (a) chain-aware peer pull as above (recommended); (b) accept the loss and say in §10.4.4 that relay replacement recovers only blobs uploaded under the current key unless the CO keeps an `archive`.

### SEP3-4: The lowest-leaf rule for DM handover is not enforced, so any member can re-home a DM to an identity host and relays it chooses
- Severity: P3
- Location: spec/04-access-control.md:266-271; ARCHITECTURE.md §9 (host-plus-relay bullet)
- Evidence: "The client of the remaining member with the lowest leaf index ... does this automatically; if no handover Commit has arrived 24 hours after ..., any remaining member's client does it." "Members MUST treat a Commit that changes `agora_admission_host` while the host's user is still a member as a policy violation". With "Any member MAY remove any other member ... No consent, approval or authority is needed".
- Problem: No receiver rule rejects a handover from a member other than the lowest leaf within the 24 hours. Combined with consentless removal, any member can remove the host's user and immediately commit a handover to its own identity host, which then chooses the group's relays. If that party runs relays (the case §9 describes), it gains the network addresses of every member at its relay tied to tokens it knows, for a group it did not start. Before this delta only the initiator could put a DM on relays of its choosing. §9 covers the host-plus-relay cost but implies the host is the initiator's or a deterministic successor's.
- Suggested fix: Make the rule checkable: within 24 hours after the host's user ceased to be a member, members MUST treat a handover Commit not committed by the lowest-index remaining non-logger leaf as a policy violation. This does not stop a determined lowest-leaf member, but restores a deterministic successor.
- Needs decision: no

### SEP3-5: `chunkCount` "MUST NOT be sent to any IO" contradicts the root block every IO receives
- Severity: P3
- Location: spec/05-messaging.md:328; spec/14-jmap.md:133
- Evidence: §5.2.3: "`contentKey`, `chunkCount` and `sha256` travel only inside the encrypted Message and MUST NOT be sent to any IO." §14.3.4: "The root block reveals only the chunk count and the ciphertext length, which an IO holding the blocks sees anyway."
- Problem: The uploaded `dag-pb` root lists one link per chunk, so every Relay receives the chunk count. An implementer reading §5.2.3 literally cannot upload the root block; one reading §14.3.4 does. No separation loss (block count and sizes are within §5 item 4), but the rules contradict.
- Suggested fix: In §5.2.3 drop `chunkCount` from the MUST NOT list, or say "the `chunkCount` property is carried only inside the encrypted Message; the root block discloses the count to IOs (§14.3.4)".
- Needs decision: no
