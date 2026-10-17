# SEP review: operator separation

Lens: ARCHITECTURE §10 review test (S1–S8, §5 observation budget) applied to every
spec part. Line numbers are of the files named.

### SEP-1: User-signed discovery gossip ties a DID to the client's relay connection
- Severity: P1
- Location: spec/10-relays.md:275, 298, 302 (UserAd); spec/02-identity.md:115 (profile updates); spec/02-identity.md:163 (RecoveryAssertion); vs ARCHITECTURE.md:86-88 (S1), spec/11-transport.md:76, spec/10-relays.md:498
- Evidence: "A **SpaceAd** or **UserAd** message is gossiped periodically (default TTL: 60 seconds; re-advertised at 45 seconds"; "A UserAd is signed the same way by the user's DID"; "Profile updates are signed by the user's authentication key and gossiped on `v1/agora/discovery`"; "The `RecoveryAssertion` is published to `v1/agora/discovery`".
- Problem: A client that publishes a DID-signed record over its relay connection tells that relay which DID owns the connection. That connection also carries the client's `channelToken` subscriptions, push registration and writes, so the relay learns sender identity and per-DID membership (S1). This breaks "I do not know who my users are" (§10.4.1). A UserAd re-sent every 45 s is also a mesh-wide presence beacon. UserAd has no schema anywhere in the spec.
- Suggested fix: Remove UserAd, since users are found by DID resolution or the Pkarr record. Do not gossip profile updates or RecoveryAssertions from clients: the DID document or Pkarr record already points at the profile CID, and the DID log carries recovery. If any user record must be gossiped, require that it is published only by the identity host (a CO component), never over a client connection that carries channel traffic.
- Needs decision: yes. (a) Delete UserAd and user-originated discovery gossip (recommended). (b) Keep it, but publish only through the identity host. (c) Keep it as an opt-in extension that the client declares, with a warning that it de-anonymizes the user to their relay.

### SEP-2: The access-key chain links every epoch of a channel at the relay, but the spec says rotation prevents this
- Severity: P2
- Location: spec/05-messaging.md:203, 216; spec/10-relays.md:500, 518; spec/12-security.md:27, 34, 46; spec/04-access-control.md:125; spec/11-transport.md:335
- Evidence: "an `accessKeyAnnouncement` containing the new `epoch`, the new `channelToken` ... signed with the previous epoch's access private key. The relay thereby follows the chain from token to token" vs "A Relay that captures routing tables across epochs cannot correlate them without also capturing the epoch secrets" (10-relays:518) and "Map routing tables across epochs without MLS group secrets" (12-security:34). Also the sealed-envelope rationale: "`epoch` and `content_type` would reveal epoch boundaries and which messages are Commits. The wrapper hides all three". Yet `RoutingEnvelope` carries `"epoch": 17` in the clear, the announcement rides on "the routing envelope carrying the Commit", and the JMAP `Envelope` exposes `mlsEpoch`.
- Problem: By design, any relay holding the chain links all of one group's tokens into a single pseudonymous stream, sees every epoch boundary and knows which envelope carries each Commit. Gossip peers see the announcements too. The spec's unlinkability claims in §10.4.1, §10.4.2, §12.3, §12.4 and §4.6, and its stated reason for hiding `epoch` and `content_type`, are false. Readers and counsel relying on §4/§12.3 would overstate what a relay can be compelled to produce. Linking epochs is not an S1 break, because the chain stays opaque. It does mean that §5 item 2 ("routing token") understates what the relay sees.
- Suggested fix: Rewrite §10.4.1–10.4.2, §12.3, §12.4 and §4.6 to say that relays link a group's epochs through the chain and see epoch boundaries and Commit envelopes. Token rotation hides only the channel CID, not continuity. Drop "epoch boundaries / which messages are Commits" from the §5.2.2 rationale, keeping `group_id`. Add "per-chain epoch sequence and announcement positions" to ARCHITECTURE §5 item 2 or 3.
- Needs decision: yes. (a) Correct the text and accept the linkage (recommended, since the chain is load-bearing for §6.2). (b) Keep per-epoch tokens but send announcements in separate, padded envelopes at random times, which hides Commit positions but not continuity. (c) Use one stable token per chain, because rotation buys nothing against chain holders.

### SEP-3: Billing countersignature and chain verification leak onto the open gossip mesh
- Severity: P2
- Location: spec/05-messaging.md:204; spec/10-relays.md:527, 612; spec/08-cross-space.md:96-100; spec/13-encoding.md:27 (kid in every JWS); vs ARCHITECTURE.md:157-160 (§5 item 6), 182-183
- Evidence: "Every `accessKeyAnnouncement` MUST also carry `billingSig` ... with the billing key of the agreement"; "Verify the epoch access proof on every envelope before caching or forwarding it"; ARCHITECTURE: "The billing DID of each CO it holds an agreement with" and "Agreements are private between the two parties and are not gossiped".
- Problem: Announcements travel in routing envelopes on `v1/agora/channel/<token>`, and the gossip mesh forwards these to relays that hold no agreement with the CO. Every JWS `kid` names the billing DID, so every mesh relay learns which CO owns each chain. §5 item 6 limits that knowledge to agreement parties. The converse problem also exists. A relay without the `AccessChainRegistration` cannot verify `accessSig`, so §10.4.3 forces it to drop the traffic. That leaves §8.6's "guest space's Relays must be peered with ... the home channel's Relays" with no working mechanism.
- Suggested fix: Say who may carry a channel topic. Either (a) only relays holding the chain's registration, with mesh forwarding of channel topics restricted to peers that also hold it, or (b) define how a chain is introduced to a peer relay. In either case, replace the billing-DID countersignature with a per-registration countersigning key. That key is carried in the `AccessChainRegistration` and is not linkable to the billing DID, so an announcement observed in transit does not name the CO.
- Needs decision: yes. Recommendation: (a) plus a per-registration countersign key.

### SEP-4: Relay-side push registration sits outside the relay's budget and links channels to a device
- Severity: P2
- Location: spec/11-transport.md:160, 194-203, 253; vs ARCHITECTURE.md:161 (§5 item 7), 286-288 (Q4)
- Evidence: "the Relay knows `channelToken` → pushHandle"; "Registers `{ pushHandle, proxyEndpoint, channelTokens }` with their Relay"; ARCHITECTURE item 7: "For push proxies only: opaque device push handles and wake-up timing."
- Problem: §5 grants push handles to push proxies only, but the relay stores a persistent 30-day handle against every token the device follows. Tokens rotate per epoch and the client re-registers under the same handle, so the relay builds a device-level co-membership graph across channels and epochs. That graph does not depend on network address, so it is stronger than the address clustering accepted in §9. Push is on by default, so this is not opt-in (S6).
- Suggested fix: Register a distinct random handle per token per epoch with the relay. The proxy maps each handle to the device token and never learns any channel token. Alternatively, amend ARCHITECTURE §5 explicitly to include the relay's per-handle token set and state the linkage.
- Needs decision: yes. (a) Per-token handles (recommended). (b) Amend §5 and disclose the linkage.

### SEP-5: `pushUrgency` in the outer envelope marks DMs and mentions in the clear
- Severity: P2
- Location: spec/11-transport.md:233-239; vs spec/04-access-control.md:125, spec/12-security.md:48, ARCHITECTURE.md:148-149 (§5 item 2)
- Evidence: "`urgency: \"high\"` is used for direct messages or @mentions ... the sending client attaches an advisory urgency hint to the outer `RoutingEnvelope`"; vs "so relays cannot distinguish DM traffic from channel traffic" and "it cannot distinguish them from other traffic by type".
- Problem: The field puts message kind in the clear on every envelope, outside §5 item 2 and without opt-in or declaration (S6). It also lets any member force high-priority wake-ups, because "Relays use it as-is".
- Suggested fix: Remove `pushUrgency` from the routing envelope. If urgency is needed, the recipient's client sets it per registered handle at registration time (with SEP-4's per-token handles). Sender-side marking should not exist.
- Needs decision: no

### SEP-6: §11 sends Welcomes over the relay live stream, contradicting KeyPackage-endpoint delivery
- Severity: P2
- Location: spec/11-transport.md:10, 405; vs spec/04-access-control.md:147, spec/05-messaging.md:51, spec/10-relays.md:264
- Evidence: "MLS handshake messages (Commits, Proposals, Welcomes)" on the live stream, and table row "MLS handshake (Commit / Proposal / Welcome) | ✗ | ✓"; vs "Welcome: delivered by POST to the new member's `KeyPackageEndpoint` ... never on a gossip topic".
- Problem: Routing Welcomes through relays would put the joiner-specific `KeyPackageRef`s and Welcome timing in front of an IO, which the Q3 design deliberately avoids.
- Suggested fix: Remove "Welcomes" from §11 l.10 and change the l.405 row to "Commit / Proposal"; add a note that Welcomes go to the `KeyPackageEndpoint` (§4.6).
- Needs decision: no

### SEP-7: DM routing relies on per-DID "relay hints" that identity records are forbidden to carry
- Severity: P2
- Location: spec/04-access-control.md:151, 153; vs spec/02-identity.md:37, 302, spec/10-relays.md:448
- Evidence: "the sending client SHOULD use the Relays known to be serving the recipient's DID (discoverable from the recipient's DID document relay hints)"; vs "The DID document MUST NOT name an infrastructure operator (relay or other IO)" and "The record MUST NOT name a relay or other IO".
- Problem: The DM routing rule depends on a record that §2 forbids. It also assumes relays "serving" a DID, which is a per-user IO association S1 rules out. As written, DMs have no defined way to agree on relays.
- Suggested fix: State that the DM creator chooses relays and registers the chain through its own CO's registration service. Carry the relay list inside the encrypted Welcome, for example as a GroupContext extension. Delete the relay-hint sentences in §4.6 "Relay routing" and "Cross-topology reachability".
- Needs decision: no

### SEP-8: IOs other than relays (TURN, SFU, sequencer) have no S7 binding, and the sequencer ignores the §6.2 proof
- Severity: P2
- Location: spec/06-calls.md:213 (TURN), 111 (SFU), spec/14-jmap.md:127-136, 165, 193 (sequencer); vs ARCHITECTURE.md:116-119 (S7), 191 (§6.2), 157-160 (§5 item 6)
- Evidence: "The TURN operator and the CO credential service share a secret"; SFU: "Client presents the MLS-membership access proof for the voice channel's `channelToken`"; sequencer: "The sequencer does not authenticate submitters" and "its operator can associate its streams with those Spaces"; S7: "The only binding between a CO and an IO is the `RelayServiceAgreement` ... and the verification material defined in §6."
- Problem: The TURN shared secret is a CO–IO binding outside S7. The SFU must verify an access proof, but only relays receive `AccessChainRegistration`s, and nothing says what the SFU's proof signs or how replay is stopped. The sequencer has no agreement and checks no membership proof, contrary to "Membership in the MLS group is the only access control" (§6.2). Anyone who sees a token, including any gossip peer, can occupy stream positions, including position 0 of a new epoch that the closing rule depends on. §14.4.6 concedes a token→Space association that §5 item 6 forbids.
- Suggested fix: Generalize S7 and §10.5.1 so that one service agreement form, keyed to the billing DID, engages any IO. Add the TURN REST secret and chain registration for SFUs and sequencers to ARCHITECTURE §6 as verification material. Require the SFU and the sequencer to verify `accessSig` against a registered chain, and define a fresh challenge for the SFU proof. Rewrite §14.4.6: the sequencer sees only chains, as a relay does, and any association with a Space comes from public Space state or out-of-band arrangements, which the CO controls.
- Needs decision: yes. (a) Generalize the RSA into an IO service agreement covering every IO type (recommended). (b) Keep the RSA relay-only and list per-IO bindings (TURN secret, SFU and sequencer chain registration) as further S7 exceptions.

### SEP-9: Shared channels expose a CO–CO link and leave the countersignature undefined
- Severity: P2
- Location: spec/08-cross-space.md:98; spec/05-messaging.md:204
- Evidence: "Each CO engages Relays for the shared channel through its own `RelayServiceAgreement` ... by registering the shared group's access-key chain under it ... they do not learn ... that the channel is shared"; "Relays MUST reject an announcement without a valid `billingSig` from that agreement's billing DID."
- Problem: A relay that holds agreements with both COs sees the same chain registered under two billing DIDs, so it learns that the two COs share a channel. That falsifies l.98. An announcement also carries a single `billingSig`, so relays registered under the other agreement reject it. The guest CO's service would have to authenticate "a current member of the channel under Space state" against another CO's Space.
- Suggested fix: Make `billingSig` one entry per registering agreement, or have only the home CO register the chain and guests use the home CO's relays. Replace the l.98 claim with an accurate statement of what a relay serving both COs learns.
- Needs decision: yes. (a) Only the home CO registers (recommended: no CO link is exposed and there is one countersigner). (b) Multi-entry countersignature, with the disclosure stated.

### SEP-10: Private-Space icon and custom-emoji images may be pinned in plaintext under a chain
- Severity: P2
- Location: spec/05-messaging.md:529, 549; spec/03-spaces.md:57 (`iconCID`), 188; spec/10-relays.md:535; spec/14-jmap.md:117
- Evidence: "`blobId` is the CID of the image file, which MUST be `image/png`, `image/gif`, or `image/webp`"; "Spaces SHOULD send relay pin instructions (§5.2.6) for custom emoji image CIDs"; §3.4 forbids clear storage only for "Records that name members".
- Problem: Nothing requires a private Space's icon or emoji images to be encrypted. A pin carries an access proof for a registered chain, so a plaintext logo pinned under that proof names the Space to the IO (S1, §5 item 6). §10.4.3 counts it as a CO "publication", which the CO did not intend.
- Suggested fix: For non-public Spaces, require icon and emoji blobs to be encrypted under a random content key carried in Space state (the §14.3.4 pattern). Extend the §3.4 mirroring rule from "records that name members" to "any Space-identifying content".
- Needs decision: no

### SEP-11: Relay "sequence attestations" give relays an undefined ordering role
- Severity: P3
- Location: spec/05-messaging.md:23
- Evidence: "Relays MAY provide **sequence attestations** (signed sequence numbers over a channel's message stream) as an optional ordering anchor for clients that require it."
- Problem: This is an IO-signed order over community data. It overlaps the blind sequencer (§14.4, decision D2), has no format, and no rules for validation or replacement.
- Suggested fix: Delete the sentence; ordering that clients rely on comes from §14.4.
- Needs decision: no

### SEP-12: The provisioning service wakes all of a user's devices through the push path
- Severity: P3
- Location: spec/02-identity.md:422; vs spec/11-transport.md:243
- Evidence: "Notifies the user's remaining enrolled devices via their push handles (if push proxy is configured)"; "Wake-up requests from unknown or untrusted Relay DIDs MUST be rejected."
- Problem: Proxies accept wake-ups only from relays, so this step cannot work. If it did, the proxy would receive a simultaneous wake of every handle belonging to one DID and could cluster handles by user.
- Suggested fix: Delete step 4. Devices learn of revocation from the DID log and MLS Removes.
- Needs decision: no

### SEP-13: Blob upload has no defined admission or quota attribution
- Severity: P3
- Location: spec/11-transport.md:271, 279; spec/10-relays.md:534, 537
- Evidence: "POST {base}/upload/{accountId}  Blob upload"; "Enforce the storage and bandwidth quotas set by each `RelayServiceAgreement` ..., keyed to the agreement and never to member identity."
- Problem: Envelopes are attributed to an agreement through the chain, but uploads carry no access proof. The relay cannot charge an upload to an agreement without inventing some identity-based admission, which S2/Q2 forbid.
- Suggested fix: Require each upload to carry an `accessSig` over the blob CID for a registered `channelToken`, the same as pin instructions.
- Needs decision: no

### SEP-14: The MIMI provider endpoint cannot do what §9.1 says without group secrets
- Severity: P3
- Location: spec/09-interop.md:216-218 (lines 66-68 of file); vs spec/05-messaging.md:206, 218
- Evidence: "The endpoint holds no MLS group secrets and sees no plaintext; it relays handshake messages between the MIMI provider and the channel's relays as ciphertext."
- Problem: Posting to relays needs `accessSig`, and unwrapping or wrapping `sealedEnvelope` needs exporter-derived keys. The endpoint therefore holds exporter outputs. It is already a CO component, so there is no IO leak, but the text understates what it holds.
- Suggested fix: State that the endpoint is a member of the group, or that it holds the access and sealing exporter outputs, as a CO component (S3 does not apply to it).
- Needs decision: no

Areas checked with no separation finding: §1; §2 apart from SEP-1 and SEP-12 (identity host and KeyPackage placement follow Q3); §3.3–3.4 Space endpoint, broadcast keys and group-encrypted blobs; §4.1–4.5 moderation (relays enforce nothing); §5.2.1.4 broadcast; §5.3 presence and typing; §6.2–6.14 call state, SFrame, recording (recorder is CO, SFU excluded); §7 compliance (logger and endpoints CO-side; §7.8.9 matches §6.3); §9.2–9.3 gateways; §10.2 peering; §10.3.2–10.3.4 discovery (Q5 signing rule followed for SpaceAd and directories); §10.4.4 blob read path; §11.6 admission; §11.8 JMAP sync (token-keyed only); §13; §14.3 and §14.5–14.7; Appendices.

Coverage: read in full ARCHITECTURE.md; spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; `bd memories agora` decision list.
