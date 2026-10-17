# Profile: Parlance on Agora

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components, not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-16
**Depends on:** ARCHITECTURE.md; spec §6.13, §9.1–§9.3, §13.1, §14.2–§14.5
**Sources:** bead agora-pozi.28.8; Parlance documents (read only): WHITEPAPER-2099-Substrate-Parlance-Surface.md §2.2; SPEC-Substrate.md §3.4, §11.3–§11.5, §12, §19; SUBSTRATE/docs/strand/id-atwood-strand-arch.md §4–§5; id-atwood-strand-data.md §2, §4–§8

---

## 1. Summary

This profile describes one way to carry Parlance device data (IPSO/LwM2M typed objects in canonical units) across Agora. It uses only mechanisms the Agora spec already defines and adds no protocol.

A Substrate site produces Parlance readings. Every value is an IPSO object/resource in one canonical unit, with no unit negotiation (SPEC-Substrate §3.4; strand-data §4). Inside a site these readings travel on the Substrate event fabric (MQTT and Kafka, SPEC-Substrate §11). This profile covers the leg that leaves the site: to another site, to another organization (installer fleet, campus facilities, a relative's house; SPEC-Substrate §19.2), and to people's phones and desktops.

The site gateway carries readings and commands as typed envelopes inside MLS application messages. Devices never join Agora. Gateways, Arbiter front ends, logic engines, and people do.

Why Agora for this leg:

- **Cross-site and cross-org.** Substrate federation today is controller-to-controller over a separate Plane 3 PKI (SPEC-Substrate §19.3). Agora gives the same leg DIDs, MLS group membership, and replaceable relays, and puts the humans in the same groups as the machines.
- **Telemetry is sensitive.** Presence (3350), CO2 (3325), power (3305), and lighting state reveal occupancy and routine. On Agora, relays and sequencers see only ciphertext, routing tokens, sizes, and timing (ARCHITECTURE §5 items 1–2, S3). No relay operator can read a building's occupancy.
- **Policy stays with the owner.** The relay operator decides nothing about who may read or command a site (ARCHITECTURE S2). The site owner, as Communications Operator (CO), admits members and runs the Arbiters.

## 2. Payload mapping

Each Parlance object is one typed envelope (spec §13.1). `contentType` is `application/cbor`. Inside an MLS group `sig` is absent (spec §13.1.1). A gateway that must hand a reading to an auditor outside the group adds `sig` so the bytes can be forwarded unchanged.

**Type naming: name the message, not the object.** `type` names the Parlance message kind. The IPSO object, resource, and catalogue edition go in the body. Types use the `urn:parlance:` namespace, owned by the Parlance editors and treated as registered (spec §13.1 "Any other type"):

| `type` | Carries | Author |
|---|---|---|
| `urn:parlance:Measurement` | A value that physically closes: traced to a transducer reading with a stated transfer function (whitepaper §2.2.2). Includes actuator state reports. | Site gateway |
| `urn:parlance:Derived` | A computed conclusion (comfort index, occupancy estimate, energy forecast). Carries provenance in place of instrument uncertainty. | Logic engine member |
| `urn:parlance:Intent` | A request to change an actuator resource. | Person, logic engine, or remote gateway |

Rejected alternative: one `type` per IPSO object, such as the OMA registry URN `urn:oma:lwm2m:oma:3303:1.1`. That URN names the object definition, not the reading message, so spec §13.1 would credit OMA with a body format OMA did not define. Receivers drop envelopes with a `type` they do not recognize (spec §6.13, §13.1). With per-object types, a client meeting a new object would drop the whole reading. With message-kind types, the same client can still show the value and its UCUM unit. Per-object types would also prevent batching (§6).

**Measurement body.** The SPEC-Substrate §11.3 state event, unchanged, plus two keys:

```cbor
{
  "topic": "ipsov1/state/<realm>.<site>.<building>.<zone>.<device_uuid>/3303/0/5700",
  "catalogue": "urn:oma:lwm2m:oma:3303:1.1",   / pinned edition /
  "ts": 1792152000.0,
  "val": 2932,                                 / 293.2 K /
  "unit": "dK",                                 / see note /
  "semantics": "3303.5700",
  "cause": { "type": "device_report", "via": "coap", "command_id": null, "policy_version": null },
  "raw": { "vendor_val": null, "vendor_unit": null }
}
```

- **Pinned editions.** `catalogue` cites a dated object edition, so a later registry revision does not change the meaning of a deployed reading (whitepaper §2.2.1, "Editions are pinned, not bodies"). Extension objects in the Strand range 42001–42255 cite the extension registry entry (strand-data §6.1).
- **Canonical units, no negotiation.** The unit is fixed by object, resource, and edition (strand-data §4). The sources disagree on whether a unit appears on the wire: strand-data §4 and the whitepaper carry none, while SPEC-Substrate §11.3 carries a UCUM code. This profile keeps `unit` as a check value only. A receiver that finds a `unit` other than the catalogue's canonical unit rejects the reading. It never converts. Conversion for display happens at the glass (whitepaper §2.3.2).
- **`raw` never drives logic** (strand-data §7.3). Receivers render it as diagnostic only.

**Derived body.** A derived body carries `val`, `ts`, and `unit`. In place of `semantics` and `cause` it carries `definition` (URI of the derivation's definition, which need not be a catalogue quantity), `producer` (the logic engine), and `inputs` (the `topic` and `ts` of each input). Measured and derived values have different `type`s so neither can be mistaken for the other (whitepaper §2.2.2). Derived values also cover computational closure. A derived value whose inputs include another derived value lists it as an input.

**Intent body.** The SPEC-Substrate §11.4 intent event plus `topic`. The receiving Arbiter takes `origin` from the MLS sender credential and ignores the body field, as stores do for JMAP sender properties (spec §14.3.2).

**Why not SenML (`application/senml+cbor`, RFC 8428).** SenML adds its own names, base values, and unit field. That makes a second encoding on an axis Parlance already fixes (whitepaper §2.2.1, "one source per axis"), and gateways would have to translate in both directions.

## 3. Membership

**Devices are not members.** Strand devices are constrained and speak CoAP with DTLS and OSCORE over Thread, Wi-Fi, or Ethernet. Each holds an OSCORE context with its own controller (strand-arch §4.3, §4.6). They run no MLS. Device trust ends at the realm's controller. Federation is controller-to-controller, never device-to-device (strand-arch §5; SPEC-Substrate §19.1).

**Group size.** Interactive MLS groups cap at 200 members (spec §5.2.1, `interactive` mode). A building can have thousands of devices. Groups therefore contain gateways, Arbiter front ends, logic engines, and people, never devices.

**The site gateway bridges.** The Substrate federation gateway (SPEC-Substrate §19.3) subscribes to site MQTT topics and is admitted to Agora channels as a gateway (spec §9.1):

- It is a CO component (ARCHITECTURE §2.3, S8). It holds plaintext on the site side and runs under the site owner's control, with its own DID and keys.
- It is disclosed: a `GatewayDescriptor` in channel state with `protocol` `"substrate"`, a `gateway-added` `SystemEvent`, and the persistent client badge (spec §9.3). Its `e2eeNote` should say that readings are plaintext on the source site's own fabric. That data never left the owner's control, so the badge flags no loss of confidentiality to a third party, unlike a Matrix bridge. The admin sets `unencryptedRemote: true` (spec §9.2).
- It publishes only what the federation export view allows (SPEC-Substrate §7.12): no device identity keys, audit logs, or configuration.

**Suggested layouts.** Membership is the read grant, so split groups by who may read and who may command:

- **Per site, per domain.** One telemetry channel per site, and separate channels for each safety domain (SPEC-Substrate §8). Class A life-safety and security get their own small channel.
- **Read and control in separate channels.** Read-only viewers (a relative, a monitoring installer) are members of telemetry channels only. The control channel holds the Arbiter front end and the people allowed to send intents.
- **Fleet.** An installer's Space with one channel per customer site, each holding that customer's gateway (SPEC-Substrate §19.2, pro installer fleet).
- **Hierarchy.** Campus or DoD tiers use one Space per tier. Each tier's gateway is a member of the tier above it, so readings go up and intents go down (SPEC-Substrate §19.2).

## 4. Data classes and consistency

**Readings are `single-author`** (spec §14.2, §14.3). The gateway that owns the topic prefix authors `Measurement`. Its logic engine authors `Derived`. A receiver ignores a reading whose MLS sender is not the author for that `topic` (compare spec §14.3.3). Readings are append-only facts, so last-writer-wins per topic gives the current value and the MQTT retained-value behavior (SPEC-Substrate §11.5). Alarms, summaries, and actuator state changes are durable. High-rate telemetry that need not be kept goes as ephemeral events (spec §5.2.3), which are excluded from history.

**Commands go to an Arbiter.** An `Intent` is addressed to the site's Arbiter front end. This is a CO-run MLS member that hands intents to the per-device Arbiters on the site fabric (SPEC-Substrate §12). The Arbiter is the single plaintext decider (spec §14.1, "CO components where one plaintext decider is needed"). It runs priority merge, manual-override hold, interlocks, rate limiting, and OPA policy (PLAN-02-01-arbiters-core). Its decision appears as a `Measurement` whose `cause.command_id` is the `intent_id`, with `policy_version` stamped.

Group membership lets a member send an intent. The Arbiter's policy decides whether the intent takes effect. Cross-realm writes stay forbidden by default (SPEC-Substrate §19.3). None of this logic runs at a relay or sequencer (ARCHITECTURE S2).

- Intents are not `sequenced-v1`. The Arbiter already orders them by receipt, priority, and TTL. A sequencer would add a round trip and a dependency without settling anything the Arbiter does not already settle.
- `ttl_ms` must allow for relay latency. The Arbiter discards a stale intent (SPEC-Substrate §11.5), which is the correct outcome.
- Class A commands need COSE Sign1 at the device (strand-data §5.4). The Arbiter signs with its own controller key and records the Agora sender DID for audit. A person's Agora key never reaches a device.

**When `sequenced-v1` fits.** Use it for shared configuration that several people edit concurrently with no site component as owner: scenes, schedules, setpoint calendars. Validation such as "no overlapping schedule entries" then runs identically at every member (spec §14.4.4). This needs a `sequencer` in Space state and an entry in `consistencyModels` (spec §14.2.2, §14.4.1). If a site logic engine already owns schedules, keep them `single-author` by that engine and have people send it requests. Then no sequencer is needed.

## 5. Paths

- **Slow path (default).** Readings, derived values, intents, and configuration go as MLS application messages through relays (spec §14.5). Substrate state changes arrive at well under the few-per-second line, so the slow path fits.
- **Fast path (rare).** A WebRTC data channel in a scene session with no media (spec §6.13) suits live 10–60 Hz views: vibration, waveform, joystick (3336) streaming to an operator console. Data channel messages authenticate only "some current member", not a particular one (spec §6.13). An Arbiter acts on sender identity, so intents MUST travel as MLS messages and never on a data channel. Persistent state never depends on a data channel.

## 6. Separation and leakage

- **Topics stay inside the ciphertext.** `realm.site.building.zone.device_uuid` and object paths travel only in `body`. Relays see `channelToken` (which changes only when the CO rotates the channel admission key, spec §5.2.2), size, and timing (ARCHITECTURE §5 item 2). Channel names in public Space state should not name sensitive zones.
- **Timing still leaks occupancy.** A motion-triggered reading is visible as a burst even when encrypted. The gateway should batch readings into one envelope per fixed interval, sent whether or not anything changed, and pad each `PrivateMessage` (RFC 9420 §6.3.1). Spec §5.2.1 already recommends padding content to a multiple of 256 bytes. A gateway may pad to larger fixed buckets. The cost is latency equal to the interval. Alarms that bypass the batch leak by timing, and that trade is accepted for life safety.
- **The sequencer sees what a relay sees.** The sequencer, if used, learns the same as a relay (spec §14.4.6). The batching rule applies to configuration edits only by convention.

## 7. What Agora does not replace

- The intra-site bus (MQTT for live state, Kafka/Redpanda for history; SPEC-Substrate §11), the Strand device protocol, the Registry, and the Arbiter pipeline all stay as they are.
- Agora is the federation and human-facing leg. It can replace the Plane 3 controller-to-controller link of SPEC-Substrate §19.3 or run beside it. It never sits between a device and its controller.

## 8. Open questions

1. Versioning of `urn:parlance:` names. Under the Agora convention for `urn:agora:type:` names (spec §13.1), a breaking change defines a new name. Do the Parlance editors accept that rule?
2. Cross-org gateways. Spec §9.1 requires a gateway to run under the CO that operates the channel. In an installer's fleet Space, the customer's gateway is run by a different CO. Does a disclosed gateway of another CO need a distinct descriptor field?
3. Topic-prefix authorship. Where is the mapping from topic prefix to authoring gateway DID recorded so that receivers can enforce single-author? A channel state field signed by the CO is the obvious place.
4. Intent rejection. A rejected intent produces no state change. Should the Arbiter send an explicit decision message, or is silence plus TTL enough?
5. Padding buckets. Spec §5.2.1 recommends padding to a multiple of 256 bytes. Is that enough for telemetry, or should this profile name larger bucket sizes?
6. Closure-domain marker. Do derived values need a closure-domain marker (physical or computational) beyond `definition`, or is the definition URI enough?
