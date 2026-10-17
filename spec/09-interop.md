# 9. Interoperability

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3427–3620 (§16).

This section states the rules every gateway follows, whatever network it reaches. Mechanics for particular networks (Matrix, Slack, Teams) are in the non-normative `profiles/gateways.md`. This version does not specify native More Instant Messaging Interoperability (MIMI), where Agora and another provider share a single MLS group (RFC 9420). `profiles/gateways.md` describes it as a future option.

## 9.1 Gateways

A **gateway** is any component that carries Agora traffic to or from another network. It decrypts Agora messages to send them on, and builds Agora messages from what arrives, so it holds plaintext. A gateway is therefore a Communications Operator (CO) component (ARCHITECTURE §2.3, S8). It MUST run under the control of the CO operating the channel. It MUST NOT run in or as part of a relay or any other Infrastructure Operator (IO) component. Co-location on IO hardware is permitted only as ARCHITECTURE S8 allows. A co-located gateway remains a CO principal with its own DID and keys.

**Identity and admission.** A gateway has its own DID. It joins each channel MLS group it serves as a member: a channel admin adds it through a normal MLS Add Commit (§5.2.1), as for any other member. On a broadcast channel the gateway instead holds a role in `broadcasterRoles` (§9.3). A gateway joins only Space channel groups. A direct message (DM) group or self-group has no Space state, so no gateway can satisfy §9.3 there. A gateway reads from and publishes to the channel's relays as a member does. It signs routing envelopes with the channel admission key it obtains as a member (§5.2.2). Relays carry its traffic only as ordinary ciphertext envelopes keyed by `channelToken`.

**Inbound attribution.** A gateway sends each message it brings in from the other network under its own leaf, so Agora members see the gateway DID as the MLS sender. The `urn:ietf:params:jmap:chat#Message` body (§5.2.3) can carry a `bridgedFrom` member naming the original sender:

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

`protocol` has the value of the gateway's `GatewayDescriptor.protocol` (§9.2). `senderID` and `eventID` are the sender and message identifiers on the other network, in its own syntax. `bridgedFrom` is the gateway's assertion; MLS authenticates only the gateway.

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
| `protocol` | string | required | The other network, as a lowercase token such as `matrix`, `slack`, or `teams` |
| `target` | string | required | The room, channel, or system on the other network, in that network's own syntax; clients treat it as an opaque display string |
| `unencryptedRemote` | boolean, default `false` | optional | `true` when traffic on the other network is not end-to-end encrypted |
| `addedBy` | DID | required | The admin who added the gateway |
| `addedAt` | RFC 3339 timestamp | required | When the gateway was added |

The gateway determines the other side's encryption state. Only admins sign Space state (§3.3), so the admin who adds the gateway records `unencryptedRemote`. An admin updates it when the gateway reports a change.

## 9.3 Gateway Transparency

Every gateway is disclosed to all channel members before messages flow through it. The obligation is on the wire: the `GatewayDescriptor` in Space state and the `gateway-added` `SystemEvent`. Presentation is guidance.

**Gateway transparency message.** The `SystemEvent` is an MLS application message (§5.2.3). As an inside-group object it carries no object signature; the sending admin's MLS sender signature authenticates it (§13.1.1):

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

This specification defines one `event` value, `gateway-added`. Receivers MUST ignore a `SystemEvent` whose `event` they do not recognize. The `SystemEvent` reaches members like any message (§5.2.5). It is not the durable record. The `gateways` array in Space state is the durable record, and the Space state chain (§3.3) records when each gateway was added.

**Send-gate.** The admin who adds a gateway MUST publish the Space state update that adds its `GatewayDescriptor` before committing the MLS Add that admits it. That admin MUST send the `gateway-added` `SystemEvent` as its first application message in the channel after that Add has won (§5.1.1). A gateway MUST carry messages in either direction only while its `GatewayDescriptor` is in the channel's current Space state, and only after it has received that `SystemEvent`. It MUST NOT carry to the other network any message from an epoch earlier than its Add, including messages it obtains from the channel's history archive.

**Broadcast channels.** A gateway that posts to a `broadcast` channel (§5.2.1.4) joins no MLS group; it posts as a holder of a role in `broadcasterRoles`. Its disclosure is its `GatewayDescriptor` in the channel's entry and its DID in the channel's `broadcasters` list (§3.4). For a channel with `keyAccess` `public`, the non-member view carries that channel's `gateways` array. The gateway MUST NOT post until its `GatewayDescriptor` is in the channel's current Space state. The `SystemEvent` and Add-epoch rules above do not apply.

**Removal.** An admin removes a gateway by committing MLS Removes for every leaf of its DID. Only after that Commit has won (§5.1.1) does the admin publish Space state without the gateway's `GatewayDescriptor`. A channel has an active gateway while a `GatewayDescriptor` for it is in the channel's current Space state.

**Channel state disclosure.** The `gateways` array is visible to all MLS group members. Clients SHOULD display an indicator when a channel has active gateways. The indicator SHOULD identify the gateway protocol and target system. It SHOULD say that the remote side is not end-to-end encrypted when a gateway has `unencryptedRemote` set to `true`. A channel with an active gateway does not give bridged traffic the privacy of end-to-end encryption (E2EE). Members need to be able to determine this without reading protocol documentation.

**Client rendering.** Clients SHOULD render a persistent banner or channel badge indicating gateway presence. A dismissed banner SHOULD reappear on reconnect. Members who joined after a gateway was added see the indicator from the `gateways` array in Space state immediately on first load, whether or not they received the `SystemEvent`.
