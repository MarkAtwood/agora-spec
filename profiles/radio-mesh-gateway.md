# Profile: Constrained Radio Mesh Gateway

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-16
**Depends on:** ARCHITECTURE.md; spec §5.2.1.4, §6.9, §6.13, §9.1–§9.3, §13.1, §14.2–§14.5
**Sources:** bead agora-pozi.28.11; research notes `notes/lichen-ironweed.md`; IRONWEED (read only) `IRONWEED/SPEC.md` §4.1, §4.4, §5.4–§5.5, §6.2–§6.5, §7, §8.1, §9, §10, §11.4–§11.9; LICHEN (read only) `project-LICHEN/spec/02-physical-link.md`, `02a-coordinated-capacity.md` §2a.9.1, `06-security.md` §8.5, §15.4–§15.5, `07-transport-app.md` §10.1, `12-apps.md` §18, `appendix-border-router.md`

---

## 1. Summary

This profile describes one way to carry data from constrained radio meshes (IRONWEED, LICHEN) across Agora through a gateway. It uses only mechanisms the Agora spec already defines and adds no protocol.

IRONWEED (VHF/UHF land mobile) and LICHEN (LoRa) are IPv6 radio meshes with their own identities, OSCORE security, and per-group keys. Agora cannot run over either radio.

An Agora message costs roughly 470 B before payload. The CBOR routing envelope (spec §5.2.2) takes about 210 B: its `signed` field holds `ctx`, the 32-byte `channelToken`, `ts`, and `expiryHint` with their text keys, and `admissionSig` adds a 64-byte Ed25519 signature. The sealed envelope adds a 12-byte nonce and a 16-byte AEAD tag. The MLS `PrivateMessage` adds about 95 B of framing (32-byte `group_id`, epoch, encrypted sender data with its own tag, and the content tag) and a 64-byte MLS signature. The inner envelope's `type`, `contentType`, and `seq` add about 70 B. The envelope `id` and the epoch are not carried, and the sealed wrapper has no sender DID, ephemeral key, or signature of its own. Spec §5.2.1 recommends padding MLS content to a multiple of 256 bytes, which brings a short message to about 590 B. These are estimates from the CDDL and RFC 9420 framing, not measurements.

- **LICHEN.** About 165 B of application room per 255 B frame, so one Agora message is 3–4 frames, or 4 with the recommended padding, and 7–9 s of airtime at SF10. The dense EU duty budget is 0.5%, or 18 s per hour (02a §2a.9.1). That allows about two Agora messages per node per hour, before relaying, Commits, Welcomes, or KeyPackage fetches.
- **IRONWEED.** 470 B is at least 0.4 s of airtime at the 9.6 kbps C4FM raw rate, more after FEC, on a channel shared with voice (SPEC §4.1, §7.3). It would also duplicate IRONWEED's own link encryption and Group OSCORE, and add dependencies that IRONWEED's disconnected-operations design removes (SPEC §6.5.2): relays, DID resolution, and the registration service of the Communications Operator (CO).

Radios therefore never join Agora. Agora is the encrypted backhaul between the places that have IP: command posts, dispatch centers, agencies, and the people working there. A gateway at the radio edge carries mesh traffic into Agora channels as typed envelopes inside MLS application messages, and carries permitted traffic back.

Shared rules are in §2–§9. System specifics are in Annex A (IRONWEED) and Annex B (LICHEN).

## 2. Gateway role

The gateway is a CO component under spec §9.1–§9.3 and ARCHITECTURE S8:

- It runs under the control of the CO operating the channel, with its own DID and keys, and never in or as part of a relay.
- It is an MLS member of each bridged channel, admitted by a normal Add Commit.
- It is disclosed by a `GatewayDescriptor` in channel state with `protocol` `"ironweed"` or `"lichen"` and `target` naming the radio net, a `gateway-added` `SystemEvent`, and the persistent client badge (spec §9.3). On a public broadcast channel (this profile's §8), the disclosure is the `GatewayDescriptor` and the `broadcasters` list, with no `SystemEvent` (spec §9.3).
- It holds plaintext from both sides. On the radio side it holds the net's Group OSCORE context or pairwise OSCORE contexts. On the Agora side it holds MLS group state.

On the radio side the gateway is a member of each net it bridges. For IRONWEED it is the backhaul gateway node (SPEC §11.9); for LICHEN, it is an application proxy on a border router, which appendix-border-router.md names as the route for conventional Internet integration. The trust shape matches IRONWEED's federation border node: a command-designated relay that holds both security contexts so it can enforce policy (SPEC §11.5).

**Filter.** Every gateway applies a default-deny, per-data-type filter modeled on the IRONWEED federation policy (SPEC §11.4). The radio operator, or the CO acting for it, writes the filter. Each rule names a data type, a direction (`radio-to-agora`, `agora-to-radio`, or both), the nets it applies to, and for position data a precision cap. Types not listed are dropped. Radio command traffic is never bridged. For IRONWEED, the gateway also enforces the mesh's own `/fed/policy` and SPEC §11.9 egress policy, and the stricter rule wins.

**Revocation.** A gateway is often a field device, such as a vehicle or a command post kit. If it is lost, the CO removes its DID from every bridged MLS group and the radio side rekeys without it (IRONWEED SPEC §6.4). Each side's removal is independent, and both are needed.

## 3. Net-to-channel mapping

- **One radio net is one Agora channel.** An IRONWEED net (SPEC §5.4) or a LICHEN group (12-apps §18.8) maps to exactly one Agora channel and one MLS group.
- **Never merge nets.** Bridging two nets into one channel would show each net's traffic to the other net's Agora members. Each net needs its own channel even when the same people sit in both.
- **Independent key schedules.** A radio rekey (IRONWEED: hourly, on revocation, on federation; SPEC §6.4) causes no MLS Commit, and an MLS epoch change causes no radio rekey. The gateway re-encrypts across the boundary as an IRONWEED border node does.
- **Hierarchy is configuration.** An IRONWEED org tree (SPEC §10.2) maps to Spaces and channels by administrative choice at the gateway, not by a protocol link. One Space per agency, one channel per bridged net, is a reasonable default.
- **Names.** Channel names in public Space state should not name sensitive nets or units.

## 4. Identity

Radio nodes are not Agora principals and are never MLS members. The gateway authors every bridged message under its own DID. The radio identity rides in the body (§5): the node's Ed25519 public key (IRONWEED SPEC §6.2; LICHEN 06 §8.5), its callsign if known, and its radio trust level.

Clients display radio-sourced identity as "reported by gateway <name>", never as DID-verified. Clients display trust levels from the body: IRONWEED tiers per SPEC §6.5.4, LICHEN TOFU, border-router provisioned or DANE (06 §8.7). A client may derive a `did:key` from the radio's Ed25519 key for display and correlation. That DID is attribution only and never becomes an MLS leaf, because the radio cannot run MLS.

## 5. Payload mapping

Each bridged item is one typed envelope (spec §13.1). `type` names the message kind in the radio project's own namespace, `urn:ironweed:` or `urn:lichen:`, owned by those projects' editors and treated as registered (spec §13.1 "Any other type"). The type tables are in the annexes.

**Body.** `contentType` is `application/cbor`. The body is a CBOR array of one or more frames of that type, so the gateway can batch (§5.2). Each frame is a CBOR map:

| Key | Value |
|---|---|
| `src` | Radio identity public key, 32-byte bstr |
| `addr` | Radio IPv6 address (optional) |
| `call` | Callsign (optional) |
| `trust` | Radio trust level string (§4) |
| `rx` | Gateway receive time, Unix seconds |
| `res` | CoAP resource or UDP port the payload arrived on, for example `/rpt/medevac` |
| `ct` | Media type of `p`: `application/cbor`, `application/senml+cbor`, `application/geo+json`, or `application/octet-stream` |
| `p` | The radio payload bytes, verbatim |
| `osig` | Origin signature bytes, verbatim, where the radio payload has one (optional) |

The gateway never re-encodes `p`. A receiver that understands the radio format parses `p` by `ct`. A receiver that does not can still show sender, callsign, trust, and time.

Rejected alternative: put the radio media type in the envelope `contentType` and the body as the bare radio payload. Provenance (`src`, `trust`, `rx`) would then need a second message or an extra envelope key. Spec §13.1 tells receivers to ignore unknown keys, so provenance would be silently dropped, and a second message can be separated from the first.

**Consistency.** All bridged types are `single-author` (spec §14.2–§14.3) with the gateway as author. Current state per radio node (latest position, presence) is last-writer-wins (LWW) keyed by `src` and `res`. A receiver ignores `urn:ironweed:` or `urn:lichen:` envelopes whose MLS sender is not a gateway listed in the channel's `gateways` array.

**Paths.** Everything goes on the slow path, as MLS application messages through relays (spec §14.5). Radio rates (positions every 60–300 s; LICHEN 12-apps §18.2.1) are far below the few-per-second line of spec §6.13. The fast path is used only for voice (§6).

### 5.2 Batching and padding

Relays see per-channel size and timing (ARCHITECTURE §5). Bridged position beacons produce a periodic pattern that reveals beacon cadence and, by count, roughly how many radios are on the net. The gateway should send one envelope per type per fixed interval, whether or not anything changed, and pad each `PrivateMessage` (RFC 9420 §6.3.1). Spec §5.2.1 recommends a multiple of 256 bytes; the gateway may pad to larger fixed buckets. The cost is added latency up to one interval. Distress and broadcast items bypass the batch and leak by timing; that trade is accepted.

## 6. Voice

Voice applies to IRONWEED only. LICHEN has none (12-apps defines no voice service). Browsers have no Codec2, so radio voice cannot ride WebRTC natively.

- The gateway joins the Agora call of the channel mapped to the net as an ordinary participant and holds SFrame media keys (spec §6.9).
- It transcodes Codec2 (SPEC §7.1, default mode 3200) to Opus toward Agora, and Opus to Codec2 toward the radio, in the mode negotiated in the floor grant (SPEC §7.1.1).
- **The push-to-talk (PTT) floor stays radio-side.** Agora calls have no floor control. The gateway requests the radio floor (SPEC §7.2) when an Agora participant talks, transmits only while it holds the floor, and drops Agora audio otherwise. Preemption follows the radio's rank and role rules. Agora clients for bridged channels should offer push-to-talk.
- Latency adds transcode and WebRTC delay to the radio's about 125 ms single hop (SPEC §7.4). The transcode figure is not measured.
- Voice is bridged only for nets the filter lists, matching IRONWEED's per-net voice federation rule (SPEC §11.4).

## 7. Distress

Agora has no anonymous-inbound path, and this profile does not add one. Distress traffic stays on the radio:

- IRONWEED MAYDAY and HAIL (SPEC §5.5.1–§5.5.2) and LICHEN SOS (12-apps §18.4) are received by the gateway as a radio node.
- The gateway relays each item into the CO's responsible channels (dispatch, command) as a typed envelope, with the sender's self-signed key in `src` and the origin signature in `osig`, so any member can verify it. Trust is `TOFU` or unknown.
- Responses go out on the radio, by radio operators, under the radio rules (IRONWEED HAIL scoped context, SPEC §5.5.2). Relaying a HAIL does not admit the sender to anything in Agora.

**The gap.** A person who is neither an Agora member nor on a monitored radio cannot reach an agency through Agora. A stranger's radio cannot post into an Agora channel. Only the gateway can, on its behalf. A general stranger inbox would be a separate future decision.

## 8. Public broadcast

IRONWEED BROADCAST (SPEC §5.5.3) maps to an Agora `broadcast` channel with `keyAccess: public` (spec §5.2.1.4), which only a public Space can have. The content key is public Space state, so anyone can read the channel. Infrastructure Operators (IOs) still see only the routing envelope. They can tie the channel's published token to the CO's agreement, which is an accepted cost (ARCHITECTURE §9).

- The gateway holds a role in the channel's `broadcasterRoles`, so the Space endpoint serves it the channel admission key, including its private key. The gateway is the poster (spec §5.2.1.4). The CO lists the gateway's DID in the channel's signed `broadcasters` list in the public view of Space state, and non-member receivers check the poster's signature against that list (spec §3.4, §5.2.1.4).
- A broadcast payload is always a `urn:agora:type:BroadcastMessage` carrying a JMAP Chat `Message`, signed by the poster (spec §5.2.1.4, §13.1). The gateway puts a readable rendering of the broadcast in the `Message` text and attaches the original `urn:ironweed:Broadcast` frame (§5) as an encrypted blob, so receivers that understand IRONWEED can check `osig`. The gateway uploads the blob once, to one relay in the channel's relay list, and the relays replicate it (spec §10.4.4). Because the channel is public, its blobs are public content that the CO, a member, or a relay may also publish on the public IPFS network (spec §10.4.4). Blobs of the gateway's other channels never go there.
- The original mesh signature and source mesh CA certificate travel in the frame (`osig`, and `p` verbatim). Receivers keep "verified source" versus "source unverified" from the mesh signature, not from the gateway's JWS. The gateway's signature says only "this gateway relayed it".
- The gateway never presents itself as the originating mesh. Clients should display the mesh identity, the verification result and the expiry, and should not act automatically (SPEC §5.5.3).
- Broadcast channels have no MLS forward secrecy (spec §5.2.1.4). That is acceptable for public information.

## 9. Separation risks

- **Metadata stays inside the ciphertext.** Positions, callsigns, radio keys, and net identities appear only in `body`. None goes in the routing envelope, topics, channel names in public Space state, or data channel labels (spec §6.13).
- **The gateway is a concentration point.** It holds radio group keys and MLS state for every bridged net. Run it on CO-controlled hardware and keep its net list minimal.
- **Precision caps apply before injection.** The gateway degrades position precision per the filter (IRONWEED SPEC §11.4) before the frame enters Agora. Agora members cannot undo it.
- **The radio leg is weaker.** Bridged channels must not claim MLS-grade security for the radio leg. The `e2eeNote` should say what the radio side protects and what it does not (see the annexes).
- **Cross-net leakage through the gateway.** One gateway bridging several nets must keep their frames separate. A bug that routes net A's frame into net B's channel defeats §3. Separate processes or key stores per net reduce the risk.

## 10. Open questions

1. Spec §5.2.1 recommends padding MLS content to a multiple of 256 bytes. Is that enough to hide beacon counts, or should this profile name larger buckets?
2. Group OSCORE citations in both radio specs look wrong. IRONWEED SPEC §6.4 and §7.2 cite RFC 9594, which covers ACE key provisioning for groups. LICHEN 12-apps §18.8 and §18.8.5 cite RFC 9203, the ACE OSCORE profile. Group OSCORE itself is draft-ietf-core-oscore-groupcomm. Flag for the radio authors.
3. Versioning of `urn:ironweed:` and `urn:lichen:` names: following the Agora convention for `urn:agora:type:` names (spec §13.1), a breaking change defines a new name. Confirm both projects accept that rule.
4. Redundant gateways on one net will deliver duplicates. Dedupe by (`src`, hash of `p`), or allow only one active gateway per channel?
5. Agora-to-radio BROADCAST would require the gateway to sign as the mesh CA or command node (SPEC §5.5.3). Out of scope here; needs a decision by the radio operators.
6. Should an Agora dispatcher be able to answer a HAIL through the gateway acting as the responding radio node, or must a radio operator always answer?

---

## Annex A. IRONWEED

**Link budget.** C4FM 9.6 kbps or 4FSK TDMA 12 kbps in 12.5 kHz, OFDM 20–100 kbps in 25–100 kHz (SPEC §4.1). Voice at Codec2 3200 uses three-frame bursts of 53 ms airtime per 60 ms of audio (SPEC §7.3). The gateway should rate-limit Agora-to-radio traffic so that it does not starve voice and PLI, as SPEC §9.3 does for files.

**Security model.** Every frame is link-encrypted; only the sync pattern is in the clear, so no unit ID or net is visible on air (SPEC §4.4). Pairwise OSCORE with EDHOC (SPEC §6.3); one Group OSCORE context per net (SPEC §6.4); three trust tiers plus TOFU variants (SPEC §6.5.4). Suggested `e2eeNote`: "Bridged to IRONWEED net <name>. Radio traffic is protected by IRONWEED link and group encryption; the gateway holds plaintext."

| Data | `type` | `ct` of `p` | Model | Path |
|---|---|---|---|---|
| PLI (SPEC §8.1) | `urn:ironweed:Pli` | `application/cbor` | single-author, LWW per `src` | slow, batched |
| Text (SPEC §9.1) | `urn:ironweed:Text` | `application/cbor` | single-author | slow |
| Reports: SALUTE, SITREP, MEDEVAC, CFF, SPOTREP, ACE (SPEC §9.2) | `urn:ironweed:Report` (kind from `res`) | `application/cbor` (CDDL) | single-author | slow |
| File (SPEC §9.3) | `urn:ironweed:File` | as sent; large files as Agora blobs | single-author | slow |
| Overlay (SPEC §10.1) | `urn:ironweed:Overlay` | `application/geo+json` | single-author, LWW per overlay version | slow |
| MAYDAY (SPEC §5.5.1) | `urn:ironweed:Mayday` | `application/cbor` | single-author | slow, unbatched |
| HAIL (SPEC §5.5.2) | `urn:ironweed:Hail` | `application/cbor` | single-author | slow, unbatched |
| BROADCAST (SPEC §5.5.3) | `urn:ironweed:Broadcast`, attached to a `BroadcastMessage` (§8) | `application/cbor` | broadcast channel (§8) | slow, unbatched |
| Voice (SPEC §7) | none; Agora call media | Codec2 to Opus | none | fast (§6) |
| Org tree, net membership (SPEC §10.2) | none; Space and channel configuration | | | |
| PTT floor (SPEC §7.2) | none; local to the gateway | | | |

A large file becomes an Agora attachment: a chunked content-key blob of 256 KiB encrypted chunks, at most 2^32 bytes (spec §14.3.4). On radio-to-Agora, the gateway uploads it once to one relay in the channel's relay list, and the relays replicate it (spec §10.4.4). On Agora-to-radio, the gateway fetches the chunks by CID from any listed relay or the channel's `archive`, never from the public IPFS network (spec §10.4.4), and sends the file on air under the SPEC §9.3 rate limits.

The radio command node edits overlays. Agora members who want a change ask through text. A writable Agora-to-radio overlay path needs the command node's authority and is not covered here.

**Special channels.** MAYDAY and HAIL follow §7, and BROADCAST follows §8. IRONWEED leaves monitoring and response obligations to local governance (SPEC §5.5.5); so does this profile.

## Annex B. LICHEN

**Link budget.** Default SF10, 125 kHz, CR 4/5, about 980 bps (02-physical-link; appendix-design-rationale). Frames are at most 255 B, and a signed frame carries a 48 B Schnorr-48 signature. Per-node duty budgets run from 0.5% (dense, EU) to 5% (sparse, US) (02a §2a.9.1). Agora-to-radio traffic spends the gateway node's duty budget; the filter should allow little beyond short text.

**Security model.** No link-layer encryption: the frame's Encrypted flag is unsupported and receivers reject it (02-physical-link frame flags). Confidentiality comes only from OSCORE (pairwise, EDHOC) or an optional Group OSCORE key per group, distributed out of band or by secure unicast (12-apps §18.8.5). LICHEN has no forward secrecy, and link headers are visible (06 §15.4). Addresses are stable and key-derived (06 §15.5). Suggested `e2eeNote`: "Bridged to LICHEN group <name>. Radio traffic may be readable over the air if the group has no OSCORE key, and radio metadata is visible; the gateway holds plaintext." The gateway should refuse to bridge a group without a Group OSCORE key into a channel whose members expect confidentiality, or at least state it in the channel description. The admin sets `unencryptedRemote: true` (spec §9.2) for a group without a Group OSCORE key, and for any broadcast or pairwise traffic not protected by OSCORE.

| Data | `type` | `ct` of `p` | Model | Path |
|---|---|---|---|---|
| Message (12-apps §18.1) | `urn:lichen:Message` | `application/cbor` | single-author | slow |
| Position beacon (§18.2.1) | `urn:lichen:Position` | `application/senml+cbor` | single-author, LWW per `src` | slow, batched |
| Waypoint (§18.3) | `urn:lichen:Waypoint` | `application/cbor` | single-author, LWW per waypoint `id` | slow |
| SOS (§18.4) | `urn:lichen:Sos` | `application/cbor`, 56 B origin signature in `osig` | single-author | slow, unbatched |
| Presence (§18.5) | `urn:lichen:Presence` | `application/cbor` | single-author, LWW per `src` | slow, batched |
| Check-in, roll call (§18.6) | `urn:lichen:CheckIn` | `application/cbor` | single-author | slow |
| Compact CoT (07 §10.1.1) | `urn:lichen:CompactCot` | `application/octet-stream` | single-author | slow, batched |
| Group membership (§18.8) | none; channel configuration | | | |
| Dead drop (§18.9), Confessions (§18.10) | not bridged | | | |

LICHEN waypoints are CBOR maps (12-apps §18.3.1), not GeoJSON. A gateway may also render them to `application/geo+json` for map clients, as a separate frame with its own `ct`, never in place of the original.

Confessions are anonymous by design. MLS reveals senders to members, so a bridged post would be attributed to the gateway and logged in channel history, contradicting the no-log guarantee (12-apps §18.10.4). The gateway does not bridge them.

**Special channels.** SOS follows §7. The gateway forwards an SOS only after verifying its origin signature, as every LICHEN receiver must (12-apps §18.4.1), and respects the 3-per-hour source limit when relaying. LICHEN has no BROADCAST equivalent.

**Backhaul.** LICHEN nodes hold Yggdrasil addresses (06 §8.5), and a border router may reach them over IP. This profile still applies: Yggdrasil carries node traffic, and Agora carries the human-facing and inter-agency leg.
