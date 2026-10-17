# SEP review: verified

Verifier pass over notes/review/SEP.md. Each finding was checked against the cited
text, a grep of spec/ and ARCHITECTURE.md, and `bd memories agora` (Q1–Q6, D1–D7).

### SEP-1: User-signed discovery gossip ties a DID to the client's relay connection
- Verdict: CONFIRMED
- Severity: P1
- Location: spec/10-relays.md:275, 298, 302; spec/02-identity.md:115, 163; vs spec/10-relays.md:500 ("I do not know who my users are"), ARCHITECTURE.md:88 (S1)
- Fix: As proposed. Nothing in the spec routes user-signed discovery records off the client's channel-carrying relay connection, and UserAd has no schema anywhere (grep shows only 10-relays:275, 298, 302). Q5 ("discovery records signed by whoever they describe") governs who signs a user record. It does not require that user records be gossiped or that clients publish them, so options (a) and (b) both fit Q5.
- Needs decision: yes. (a) Delete UserAd and client-originated profile/RecoveryAssertion gossip, leaving discovery to the DID document or Pkarr record and the DID log (recommended). (b) Keep user records, published only by the identity host. (c) Opt-in, declared extension with a de-anonymization warning.

### SEP-2: The access-key chain links every epoch of a channel at the relay, but the spec says rotation prevents this
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:185 (`"epoch": 17` in clear), 203, 216; spec/10-relays.md:504, 518; spec/12-security.md:34, 46; spec/11-transport.md:335
- Fix: As proposed. 05:203 says "The relay thereby follows the chain from token to token", while 10:518 says a relay "cannot correlate them without also capturing the epoch secrets" and 12:34 says it cannot "Map routing tables across epochs". 05:216 says the wrapper hides `epoch`, but the RoutingEnvelope carries `epoch` in clear. The chain is fixed by Q1/Q6, so the text must change. Also note in §12.4 that gossip peers can follow the chain, because announcements ride in clear on the routing envelope.
- Needs decision: yes. The text correction follows from Q1/Q6. Whether to keep per-epoch token rotation remains open, since it buys little against any chain holder. (a) Correct the text and keep rotation (recommended; least change). (b) Also separate and pad announcements. (c) Use one stable token per chain.

### SEP-3: Billing countersignature and chain verification leak onto the open gossip mesh
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:204; spec/13-encoding.md:62 (`kid` is the signer's DID URL); spec/10-relays.md:527, 608; spec/08-cross-space.md:96; vs ARCHITECTURE.md:157-160, 182
- Fix: As proposed. `billingSig` is a §13.1.1 JWS whose `kid` names the billing DID, and announcements travel on the gossiped channel topic, so every mesh relay learns the billing DID behind each chain. 10:608 says agreements are "not gossiped", but this is their signer gossiped on every rotation. In the other direction, 10:527 requires dropping envelopes whose `accessSig` cannot be verified, and no mechanism introduces a chain to a peer relay without a registration. That leaves 08:96 unworkable. Q1 fixes that a CO countersigns. It does not fix that the countersigning key is the billing DID, so a per-registration key is open.
- Needs decision: yes. (a) Only registration-holding relays carry a channel topic, plus a per-registration countersign key carried in `AccessChainRegistration` (recommended). (b) Define chain introduction to peer relays, with the same per-registration key.

### SEP-4: Relay-side push registration sits outside the relay's budget and links channels to a device
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3 (from P2)
- Location: spec/11-transport.md:160, 198-205, 253; vs ARCHITECTURE.md:161, 286-288
- Fix: The budget gap is real. Q4 puts push "in the §5 budget by default", but §5 item 7 grants handles to push proxies only, and 11:160's claim "Neither party links a device to a DID or a channel" is false for the relay. The severity is lower than stated. A connected client already exposes its per-connection token set, and SEP-2's chain already links epochs. What the handle adds is cross-session, address-independent persistence of the cross-channel set. Minimum fix, which follows from Q4: amend §5 item 7 to cover the relay's pushHandle→channelToken set and correct 11:160.
- Needs decision: yes. Per-token handles move linkage to the proxy, which would then see per-handle wake timing that clusters to one device. (a) Disclose only (recommended as the minimum). (b) Per-token handles, accepting the proxy-side clustering.

### SEP-5: `pushUrgency` in the outer envelope marks DMs and mentions in the clear
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/11-transport.md:233-239; vs spec/04-access-control.md:145 ("relays cannot distinguish DM traffic from channel traffic"), spec/12-security.md:48
- Fix: Remove `pushUrgency` from the RoutingEnvelope. Without depending on SEP-4, the recipient can give a per-token urgency in its relay registration, changing `channelTokens` to `[{token, urgency}]`. This keeps message kind off every envelope and stops senders from forcing high-priority wakes.
- Needs decision: no

### SEP-6: §11 sends Welcomes over the relay live stream, contradicting KeyPackage-endpoint delivery
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3 (from P2)
- Location: spec/11-transport.md:10, 405; vs spec/05-messaging.md:51, spec/04-access-control.md:147, spec/10-relays.md:264
- Fix: As proposed: drop "Welcomes" at 11:10, change the row at 11:405 to "Commit / Proposal", and point to §4.6. Lowered to P3 because §11's mentions are overview prose and a table, while the normative rules in 05:51 ("never on a gossip topic") and 04:147 are explicit MUSTs. This is an editorial contradiction, not an open leak.
- Needs decision: no

### SEP-7: DM routing relies on per-DID "relay hints" that identity records are forbidden to carry
- Verdict: CONFIRMED-ADJUSTED
- Severity: P2
- Location: spec/04-access-control.md:151, 153; vs spec/02-identity.md:37, 302
- Fix: The contradiction is as described. The finding's fix assumes a registration path for DMs that does not exist. 05:204 requires every announcement to carry a `billingSig` from a service that authenticates the requester "as a current member of the channel under Space state", but DMs have no Space (04:145), and no text says who registers or countersigns a DM chain. Fix: delete the relay-hint sentences at 04:151 and 04:153, carry the relay list in the Welcome (for example as a GroupContext extension), and specify DM chain registration and countersigning.
- Needs decision: yes. Who registers and countersigns DM chains: (a) the creator's CO or identity host's registration service, authenticating against the DM group's membership instead of Space state (recommended); (b) a defined path for CO-less users (did:key), such as any relay-agreement holder the creator chooses; (c) DMs exempt from countersigning, accepting the Q1 removed-member race for DMs.

### SEP-8: IOs other than relays (TURN, SFU, sequencer) have no S7 binding, and the sequencer ignores the §6.2 proof
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/06-calls.md:110, 212; spec/14-jmap.md:166, 171, 178, 193; vs ARCHITECTURE.md:116-119 (S7)
- Fix: As proposed. One more concrete failure: the closing rule (14:178) reads `after` from "the operation at position 0 of a new epoch's stream". The sequencer "does not authenticate submitters" (14:166), so a non-member who saw the token can take position 0, and members skip that op at decryption (14:173), which leaves the closing head undefined. Requiring `accessSig` at the sequencer fits D2 ("Sequencer reads nothing"), because verifying the proof reads no content. 14:193's Space association holds only for Spaces whose state the operator can see (public Spaces, which are CO publications). Reword it rather than call it a §5 violation.
- Needs decision: yes. (a) Generalize the RSA into one IO service agreement covering relays, SFUs, sequencers and TURN (recommended). (b) Keep the RSA relay-only and list the TURN secret and SFU/sequencer chain registration as named verification material in ARCHITECTURE §6.

### SEP-9: Shared channels expose a CO–CO link and leave the countersignature undefined
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/08-cross-space.md:98; spec/05-messaging.md:204
- Fix: As proposed. A relay holding both agreements sees one first-epoch key and token registered under two billing DIDs, which falsifies "they do not learn ... that the channel is shared". A single `billingSig` cannot satisfy relays registered under the other agreement.
- Needs decision: yes. (a) Only the home CO registers and countersigns; guests reach the home CO's relays (recommended; this also resolves the guest-side half of SEP-3). (b) Multi-entry countersignature, with the CO–CO link disclosed.

### SEP-10: Private-Space icon and custom-emoji images may be pinned in plaintext under a chain
- Verdict: CONFIRMED
- Severity: P2
- Location: spec/05-messaging.md:529, 549; spec/03-spaces.md:57, 188; spec/14-jmap.md:117
- Fix: As proposed. §3.4's mirroring rule (03:188) covers only "Records that name members", and the §14.3.4 blob-encryption rule (14:117) covers blobs referenced by JMAP durable objects, not Space-state `iconCID` or `customEmoji`. A pin instruction carries an access proof for a registered chain, so a plaintext logo links chain to Space (S1). For non-public Spaces, encrypt icon and emoji blobs under a content key carried in Space state, and widen 03:188 to "Space-identifying content".
- Needs decision: no

### SEP-11: Relay "sequence attestations" give relays an undefined ordering role
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/05-messaging.md:23
- Fix: Delete the sentence. The spec defines no format or validation for it, and D2 assigns sequenced order to the blind sequencer (§14.4).
- Needs decision: no

### SEP-12: The provisioning service wakes all of a user's devices through the push path
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/02-identity.md:422; vs spec/11-transport.md:243
- Fix: Delete step 4. Proxies reject wake-ups from anything but known relay DIDs (11:243), and devices learn of revocation from the DID log and MLS Removes (02:424).
- Needs decision: no

### SEP-13: Blob upload has no defined admission or quota attribution
- Verdict: CONFIRMED
- Severity: P3
- Location: spec/11-transport.md:271, 279; spec/10-relays.md:537, 566-578
- Fix: As proposed. 11:279 applies the access proof to envelopes only, and §10.4.4 defines no write-side rule for blobs. Require an `accessSig` over the blob CID for a registered `channelToken` on upload, as with pin instructions, so quota is charged to the agreement through the chain.
- Needs decision: no

### SEP-14: The MIMI provider endpoint cannot do what §9.1 says without group secrets
- Verdict: CONFIRMED-ADJUSTED
- Severity: P3
- Location: spec/09-interop.md:67 (not 216-218)
- Fix: As proposed. Posting to relays needs `accessSig` and sealing, both of which are exporter-derived (05:202, 218), so "holds no MLS group secrets" is false. State that the endpoint holds the access and sealing exporter outputs, or is a group member, as a CO component (09:8, 65 already make it CO).
- Needs decision: no

## Counts

- CONFIRMED: 10 (SEP-1, 2, 3, 5, 8, 9, 10, 11, 12, 13)
- CONFIRMED-ADJUSTED: 4 (SEP-4, 6, 7, 14)
- REJECTED: 0
- By severity after adjustment: P1 1, P2 7, P3 6
- Needs decision: yes for SEP-1, 2, 3, 4, 7, 8, 9 (7); no for 7
