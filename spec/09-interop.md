# 9. Interoperability

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3427–3620 (§16).


*Binds: CO.*

This section states the rules every gateway follows, whatever network it reaches. Mechanics for particular networks (Matrix, Slack, Teams) are in the non-normative `profiles/gateways.md`. Native MIMI interop, a single MLS group shared with another provider, is not specified in this version; `profiles/gateways.md` describes it as a future option.

## 9.1 Gateways

A **gateway** is any component that carries Agora traffic to or from another network. It decrypts Agora messages to send them on, and builds Agora messages from what arrives, so it holds plaintext. A gateway is therefore a CO component (ARCHITECTURE.md §2.3, S8): it MUST run under the control of the CO operating the channel and MUST NOT run in or as part of a relay or any other IO component. Co-location on IO hardware is permitted only as S8 allows, with the gateway remaining a CO principal with its own DID and keys.

**Identity and admission.** A gateway has its own DID and joins each channel MLS group it serves as a member, added by a channel Admin through a normal MLS Add commit (§5.2.1), exactly like any other member. It reads from and publishes to the channel's relays as a member does, signing routing envelopes with the channel admission key it obtains as a member (§5.2.2). Relays carry its traffic only as ordinary ciphertext envelopes keyed by `channelToken`.

**Inbound attribution.** A message a gateway brings in from the other network is sent under the gateway's own leaf, so Agora members see the gateway DID as its MLS sender. The `urn:ietf:params:jmap:chat#Message` body (§5.2.3) can carry a `bridgedFrom` member naming the original sender:

```json
{
  "senderMsgId": "01J3XQ7Z8W6V5T4S3R2Q1P0N9M",
  "body": "hello from matrix",
  "bodyType": "text/plain",
  "bridgedFrom": {
    "protocol": "matrix",
    "senderID": "@alice:example.com",
    "eventID": "$abc123"
  }
}
```

`protocol` has the value of the gateway's `GatewayDescriptor.protocol` (§9.2); `senderID` and `eventID` are the sender and message identifiers on the other network, in its own syntax. `bridgedFrom` is the gateway's assertion; MLS authenticates only the gateway.

**Plaintext handling.** A gateway MUST NOT keep decrypted message content beyond the time needed to translate and forward it. It SHOULD hold plaintext only in memory. Gateway operators SHOULD publish a transparency policy describing their plaintext handling.

## 9.2 Gateway Descriptor

Each gateway admitted to a channel is listed in the `gateways` array of the channel's entry in Space state (§3.3):

```json
"gateways": [
  {
    "@type": "GatewayDescriptor",
    "did": "did:webvh:QmSCID...:example.com:agora:gateway",
    "protocol": "matrix",
    "target": "!abc123:example.com",
    "unencryptedRemote": false,
    "addedBy": "did:key:z6MkAdmin...",
    "addedAt": "2026-03-12T00:00:00Z"
  }
]
```

| Member | Type | Presence | Meaning |
|---|---|---|---|
| `did` | DID | required | The gateway's DID |
| `protocol` | string | required | The other network, as a lowercase token such as `matrix`, `slack` or `teams` |
| `target` | string | required | The room, channel or system on the other network, in that network's own syntax; clients treat it as an opaque display string |
| `unencryptedRemote` | boolean, default `false` | optional | `true` when traffic on the other network is not end-to-end encrypted |
| `addedBy` | DID | required | The Admin who added the gateway |
| `addedAt` | RFC 3339 timestamp | required | When the gateway was added |

The gateway determines the other side's encryption state. Because only Admins sign Space state (§3.3), the Admin who adds the gateway records `unencryptedRemote`, and an Admin updates it when the gateway reports a change.

## 9.3 Gateway Transparency

Every gateway is disclosed to all channel members before messages flow through it. The obligation is on the wire: the `GatewayDescriptor` in Space state and the `gateway-added` `SystemEvent`. Presentation is guidance.

**Send-gate.** The Admin who adds a gateway MUST publish the Space state update that adds its `GatewayDescriptor` before committing the MLS Add that admits it, and MUST send the `gateway-added` `SystemEvent` in the epoch that Add creates. A gateway MUST NOT carry messages in either direction until its `GatewayDescriptor` is in the channel's current Space state and it has received that `SystemEvent`. It MUST NOT carry to the other network any message from an epoch earlier than its Add, including messages it obtains from the channel's history archive.

**Gateway transparency message.** The `SystemEvent` is an MLS application message (§5.2.3). As an inside-group object it carries no object signature; the Admin's MLS sender signature authenticates it (§13.1.1):

```json
{
  "@type": "SystemEvent",
  "event": "gateway-added",
  "gatewayDID": "did:webvh:QmSCID...:example.com:agora:gateway",
  "protocol": "matrix",
  "target": "!abc123:example.com",
  "e2eeNote": "Messages in this channel are bridged to Matrix. E2EE is not preserved for bridged traffic."
}
```

This specification defines one `event` value, `gateway-added`; receivers MUST ignore a `SystemEvent` whose `event` they do not recognize. The `SystemEvent` reaches members like any message (§5.2.5) and is not the durable record: the `gateways` array in Space state is, and the Space state chain (§3.3) records when each gateway was added.

**Channel state disclosure.** The `gateways` array is visible to all MLS group members. Clients SHOULD display an indicator when a channel has active gateways. The indicator SHOULD identify the gateway protocol and target system, and SHOULD say that the remote side is not end-to-end encrypted when a gateway has `unencryptedRemote` set to `true`. A channel with an active gateway is not E2EE-private for bridged traffic; members must be able to determine this without reading protocol documentation.

**Client rendering.** Clients SHOULD render a persistent banner or channel badge indicating gateway presence. A dismissed banner SHOULD reappear on reconnect. Members who joined after a gateway was added see the indicator from the `gateways` array in Space state immediately on first load, whether or not they received the `SystemEvent`.
