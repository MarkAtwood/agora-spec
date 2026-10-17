# LICHEN and IRONWEED data over Agora

**Verdict.** Running Agora *over* either radio mesh is not viable. Carrying their application data *over Agora* through a gateway (a CO component) is viable and fits the existing Matrix-gateway pattern (spec/09-interop.md §9.2–9.3). Recommendation: one non-normative "constrained radio mesh gateway" profile with two short per-mesh annexes.

## 1. What the two meshes carry

**IRONWEED** (VHF/UHF, SDR). PHY: C4FM 9.6 kbps or 4FSK TDMA 12 kbps in 12.5 kHz channels, narrowband OFDM 20–100 kbps (SPEC §4.1). Every frame is link-encrypted (AES-256-GCM or ChaCha20-Poly1305). Only the sync pattern is in the clear, so no unit ID or talkgroup is visible (§4.4). The stack is IPv6, 6LoWPAN, RPL/hybrid routing, and MPL multicast. Each net (team, group, org, specialty) is an IPv6 multicast group (§5.4). Security: an Ed25519 identity, with the address derived from the key (§6.2). Pairwise security is OSCORE with EDHOC (§6.3). Each net is protected by a Group OSCORE context, rekeyed hourly, on revocation, and on federation (§6.4). Trust runs in three tiers: external X.509 CA via EST, an elected mesh-local CA with 4 h certs, and TOFU with out-of-band upgrade (§6.5). Data:
- **PLI:** CBOR map (lat, lon, alt, hdg, spd, fix, t, bat, call), distributed by CoAP Observe on `/pli` (§8.1). The spec gives no update rate.
- **Text:** CoAP PUT to `/msg/inbox`, store-and-forward (§9.1).
- **Reports:** SALUTE, SITREP, MEDEVAC, CFF, SPOT, ACE as CDDL-defined CBOR under `/rpt/*` (§9.2).
- **Files:** CoAP block-wise, 256 KB default cap (§9.3).
- **Overlays:** versioned GeoJSON resources, updated by Observe (§10.1).
- **Org tree:** each node of the tree is a net, a member set, and a key context (§10.2).
- **Voice:** Codec2 over RTP, multicast to the net, protected by Group OSCORE. PTT floor control uses CoAP (§7).

Federation re-encrypts traffic at command-designated border nodes, under a default-deny, per-data-type policy (§11.4–11.5). The spec states no frame MTU (uncertain).

**LICHEN** (LoRa). Default SF10, 125 kHz, CR 4/5, about 980 bps (02-physical-link §3.2; design-rationale §372). Link frames are at most 255 B. A signed frame spends 61 B on link security, including a 48 B Schnorr-48 signature. Link-layer encryption is unsupported (E bit must be rejected; 02 §4.1–4.2; 09 §13.2). SCHC compresses IPv6+UDP+CoAP to 23 B (link-local) or 37 B (Yggdrasil). Duty budgets per node (02a §2a.9.1):

| Density | EU | US |
|---|---|---|
| Dense | 0.5% (18 s airtime/h) | 1% |
| Moderate | 1% | 2% |
| Sparse | 2% | 5% |

Identity is a single Ed25519 seed that yields the IID, the X25519 key, and a Yggdrasil 0200::/8 address. Trust is TOFU by default, with optional BR-provisioning or DANE (06 §8.5, §8.7). OSCORE (8–13 B overhead) is established with EDHOC. The spec states there is no forward secrecy and that link headers leak metadata (06 §15.4). Data (12-apps.md):
- **Messages:** CBOR (id, from, to, ts, body, ack, priority, ttl) to `/msg/inbox`, with custody and store-and-forward (§18.1).
- **Position:** SenML-CBOR beacons, every 60 s moving, 300 s stationary, at least 300 s when dense (§18.2).
- **Waypoints:** GeoJSON (§18.3).
- **SOS:** CBOR alert with a 56 B origin signature, link dispatch 0x16, limit 3/h (§18.4).
- **Other apps:** presence (§18.5), check-in and roll call (§18.6).
- **Groups:** a multicast address, an optional Group OSCORE key distributed "out-of-band or via secure unicast", owner/admin/member roles, and COSE delegation tokens (§18.8).
- **Dead drop and anonymous confessions board** (§18.9–18.10).
- **Raw UDP ports:** Compact CoT (17 B PLI), SenML, Cayenne, APRS, NMEA (07 §9.1, §10.1). MQTT-SN also runs (§10.4).

LICHEN has no voice.

## 2. Direction 1: Agora over the radio: infeasible

Estimated per-message floor, before payload. These are estimates; Agora has no binary wire size yet:
- Three Ed25519 signatures: the MLS sender signature, the sealed-envelope `sig`, and `accessSig` (192 B).
- Two AEAD tags (32 B).
- `channelToken` (32 B) and `senderEphemeralKey` (32 B).
- The sender DID (≥34 B binary for did:key) and the CID `id` (~36 B).
- MLS sender-data framing and the group ID (~50 B).
- Typed-envelope `type` and `contentType` strings (~50 B).

That is roughly 450 B even with compact CBOR; the JSON forms shown in 05-messaging §5.2.2 are larger.

- **LICHEN:** about 165 B of application room per frame, so one Agora message is about 3–4 frames, or about 7–9 s airtime at SF10 (2.3 s per 255 B frame, computed with the Semtech formula). Under the dense EU budget (18 s/h) that is **about 2 messages per node per hour**, before relaying. MLS Commits and Welcomes (KB-scale ratchet trees), KeyPackage fetches, gossipsub control traffic, and the `billingSig` round trip to the CO's registration service on each epoch make it worse.
- **IRONWEED:** a 450 B overhead costs about 0.5 s at 7.2 kbps effective, competing with voice. It is technically possible on OFDM links but wasteful. It would also duplicate what IRONWEED already provides: link encryption, Group OSCORE, and per-net keys. Agora further assumes reachable relays, DID resolution, and the CO registration service. IRONWEED's disconnected-operations design (§6.5.2) explicitly removes such dependencies.

Conclusion: do not put Agora members on the radio side. This matches the planned Substrate/Parlance stance.

## 3. Direction 2: radio data over Agora (gateway model)

**Gateway.** A radio-mesh gateway is a CO component under the rules of 09-interop §9.2–9.3:
- It has its own DID and is an MLS member of each bridged channel.
- It holds plaintext from both sides.
- It is disclosed in the channel state `gateways` array (`protocol: "ironweed"` or `"lichen"`), and the client shows a persistent banner.
- It never runs inside a relay.

On the radio side, it is the IRONWEED border/backhaul node (§11.5, §11.9) or a LICHEN border router. It is a member of the radio nets it bridges. IRONWEED's border re-encryption is already the same trust shape: a trusted relay holds both contexts and enforces policy. The radio operator, or the CO acting for it, runs the gateway.

**Keys: bridge, do not unify.** Map one Group OSCORE net/group to one Agora channel (one MLS group). The two key schedules stay independent: radio rekeys (hourly, on revocation) do not cause MLS Commits, and the reverse also holds. Mapping the org tree to Spaces and channels is an administrative mapping configured at the gateway, not a protocol link.

**Identity.** Radio nodes are not Agora principals. The recommended default is that the gateway authors bridged messages under its own DID and carries the radio identity inside the body. That identity is the Ed25519 key or IID, plus IRONWEED's trust tier and callsign. Optional: a per-radio `did:key` derived from the radio's Ed25519 key (same curve), used only inside the body for attribution. It must not be a separate MLS leaf, because the radio cannot run MLS. Agora clients display radio-sourced trust (TOFU vs CA) from the body, not as DID-verified.

**Envelope mapping.** `urn:agora:type:` is reserved for this specification (13-encoding §13.1), so the profile names types in a URN or HTTPS namespace the IRONWEED/LICHEN authors control. The body is the radio payload bytes verbatim (no re-encoding, matching §13.1).

| Data | contentType | Model (§14) |
|---|---|---|
| IRONWEED PLI, LICHEN position | `application/cbor`; `application/senml+cbor` | single-author (per node) |
| Text message | `application/cbor` (their maps); or translate to JMAP Chat `Message` for native rendering | single-author |
| IRONWEED reports | `application/cbor` (CDDL) | single-author |
| Overlays, waypoints | `application/geo+json` | single-author if only the command node edits, else sequenced-v1 |
| Check-in, presence | `application/cbor` | single-author |
| Group/net membership, org tree | Space/channel state, not a payload | none |
| PTT floor | no Agora equivalent; local to the gateway | none |

All of these go on the slow path (MLS application messages). Radio rates (60–300 s per position) are far below the threshold in 06-calls §6.13. The fast path matters only for voice (§5 below).

**Separation risks.**
- Positions, callsigns, unit keys, and the talkgroup/net identity must appear only inside the MLS ciphertext. None may go in the routing envelope, topic, or data-channel labels.
- Each bridged net needs its own channel. Merging several nets into one channel would leak cross-net data to members.
- The gateway enforces the radio side's federation precision caps (IRONWEED §11.4) before injection into Agora.
- Agora relays learn only per-channel traffic timing. Bridged PLI produces a periodic pattern that reveals beacon cadence (an IO-budget observation, ARCHITECTURE §5). Recommend padding or batching at the gateway.

## 4. Special channels

- **IRONWEED BROADCAST** (signed, ≤1 KB, geofence, expiry; §5.5.3) maps to an Agora `broadcast` channel with `keyAccess: public` (05-messaging §5.2.1.4). The gateway must not re-sign as the poster. Recommend carrying the original mesh-CA signature inside the body, so receivers keep "verified/unverified source", alongside the gateway's JWS.
- **MAYDAY and HAIL** (§5.5.1–5.5.2) are inbound from unaffiliated radios. They map to a CO-run intake channel. HAIL acceptance becomes a DM group with a responder. The sender's self-signed key travels in the body. Agora has no anonymous-ingress channel today; this is a gap to note, not to build.
- **LICHEN SOS** (§18.4) maps to the same intake. The gateway preserves the 56 B origin signature for verification.
- **LICHEN Confessions** (§18.10) is anonymous by design. MLS reveals senders to members, so bridging it would attribute posts to the gateway only. Probably out of scope.

## 5. Voice

Codec2 bursts (60 ms of audio per burst, about 125 ms single-hop / 235 ms over 3 hops; §7.3–7.4) cannot ride WebRTC natively, because browsers lack Codec2. The gateway joins the Agora call as a participant:
- It transcodes Codec2 to and from Opus and holds SFrame media keys (06-calls §6.9).
- It maps the PTT floor to talker state.
- It adds transcode delay (estimated, not measured) on top of WebRTC latency.

One net corresponds to one call. Agora calls have no floor control, so floor arbitration stays on the radio side at the gateway.

## 6. Borrow / conflict

**Borrow.**
- Compact binary PLI (LICHEN Compact CoT, 17 B; 07 §10.1.1) as a registered `application/cbor` or binary type for high-rate data-channel pose/PLI.
- IRONWEED's per-data-type, trust-graduated, default-deny gateway policy (§11.4) as the model for any Agora gateway's egress policy.
- IRONWEED's well-known public channels as a pattern for an Agora public intake.

**Conflicts.**
- LICHEN has no forward secrecy and leaves link headers in the clear (06 §15.4).
- Group key distribution in both meshes is out-of-band or controller-pushed, unrelated to MLS.
- LICHEN's stable key-derived addresses are deliberately non-private (06 §15.5).

None of these blocks bridging, but bridged channels must not claim MLS-grade security for the radio leg.

**Citation note (uncertain).** LICHEN 12-apps §18.8 cites RFC 9203 for Group OSCORE and IRONWEED §6.4 cites RFC 9594. To my knowledge, RFC 9203 is the ACE OSCORE profile and RFC 9594 covers ACE key provisioning for group communication; Group OSCORE itself is draft-ietf-core-oscore-groupcomm. Verify before cross-citing.

## 7. Recommendation

Write **one** non-normative "Constrained Radio Mesh Gateway" profile, sibling to Parlance. The core:
- Gateway is a CO component.
- One radio net corresponds to one channel.
- Radio identity goes in the body.
- Payload bytes are carried verbatim.
- Disclosure follows §9.3.
- No Agora membership on the radio side.
- PLI separation rules and egress policy.
- Public intake and broadcast mapping.

Then add two annexes:
- **IRONWEED annex:** type and CDDL table, voice transcode and call bridging, BROADCAST/MAYDAY/HAIL mapping, trust-tier display, federation policy mapping.
- **LICHEN annex:** SenML/CoT/CBOR type table, SOS intake, no voice, Yggdrasil-backhaul note.

Two full profiles would duplicate about 80% of the text.
