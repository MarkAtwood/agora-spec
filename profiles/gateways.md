# Profile: Gateways to Other Networks

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-17
**Depends on:** ARCHITECTURE S1, S3, S8; spec §5.2.1–§5.2.3, §9, §10.4.4, §14.3.4
**Sources:** the former MIMI and Matrix subsections of spec §9 (moved here, bead agora-pozi.38); `notes/mimi-vs-jmap-chat.md`

---

## 1. Summary

Spec §9 defines what every gateway is and must do. A gateway is a Communications Operator (CO) component with its own DID. It is admitted to the channel MLS group as a member, listed in a `GatewayDescriptor`, and announced by a `gateway-added` `SystemEvent` before any message flows through it. On a broadcast channel it is instead a broadcaster, disclosed by its descriptor and the `broadcasters` list (spec §9.3). This profile describes how a gateway to a particular network does its job inside those rules. It adds no protocol.

Every gateway described here breaks end-to-end encryption (E2EE) at the gateway, because it holds plaintext. Native More Instant Messaging Interoperability (MIMI) interop would not; section 4 records what it would take.

## 2. Matrix Gateway

A Matrix gateway decrypts Agora messages, re-encrypts them with Matrix's Megolm E2EE for delivery to Matrix users, and does the reverse for the Matrix-to-Agora direction.

### 2.1 Identity and Admission

The gateway runs as an Agora client with its own DID and is added to channel MLS groups by a channel admin (spec §9.1). Its DID document includes a `service` entry identifying it as a Matrix gateway:

```json
{
  "service": [{
    "id": "did:webvh:QmSCID...:example.com:agora:gateway#gateway",
    "type": "AgoraMatrixGateway",
    "serviceEndpoint": "https://matrix.example.com",
    "matrixServerName": "example.com"
  }]
}
```

Its `GatewayDescriptor` (spec §9.2) has `protocol` `"matrix"` and `target` set to the Matrix room ID, for example `"!abc123:example.com"`. `unencryptedRemote` is `true` when the bridged Matrix room does not have Megolm E2EE enabled.

### 2.2 Message Flow: Agora to Matrix

1. The gateway receives an MLS-encrypted message from the channel's relays (spec §11).
2. It decrypts the message with its MLS leaf key, as a full group member.
3. It translates the Agora inner payload to a Matrix event:
   - A new `urn:ietf:params:jmap:chat#Message` becomes `m.room.message` with `msgtype: m.text`.
   - A new `Message` with `attachments` becomes `m.room.message` with `msgtype: m.image`, `m.file`, or similar. The gateway fetches the media from the channel's relays (spec §10.4.4), decrypts it with the attachment's `contentKey`, checks it against its `sha256` (spec §14.3.4), and re-uploads it to the Matrix media server.
   - A `Message` edit (body contains `editedAt`, spec §5.2.3) becomes `m.room.message` with an `m.new_content` relation.
   - A `Message` deletion (body contains `deletedAt` and `deletedForAll: true`, spec §5.2.3) becomes `m.room.redaction`.
   - A `urn:ietf:params:jmap:chat#Reaction` becomes `m.reaction`.
4. If the Matrix room has Megolm E2EE enabled, it encrypts the event with Megolm.
5. It sends the event to the bridged Matrix room through the Matrix Client-Server API, attributed to a virtual Matrix user representing the Agora sender (section 2.4).

### 2.3 Message Flow: Matrix to Agora

1. The gateway receives a Matrix event through the Matrix Application Service API.
2. It translates the event to an Agora inner payload.
3. It encrypts the payload as a member of the channel MLS group.
4. It publishes the outer `RoutingEnvelope`, signed with the channel admission key (spec §5.2.2), to the channel's relays.
5. Agora clients see the message as sent by the gateway DID. The body's `bridgedFrom` member (spec §9.1) carries `protocol` `"matrix"`, the Matrix sender's MXID as `senderID`, and the Matrix event ID as `eventID`.

### 2.4 Identity and Namespace Mapping

Each Agora DID maps to a Matrix virtual user with a deterministic MXID: `@agora_<hash>:<gateway-homeserver>`, where `<hash>` is the first 20 bytes of the SHA-256 of the full DID string (UTF-8), encoded as lowercase RFC 4648 base32 without padding. The result contains only characters Matrix allows in a user localpart, for every DID method. In the other direction, the Matrix MXID travels as `bridgedFrom.senderID`.

Agora's nested channel namespace does not map cleanly to Matrix's flat room model. The gateway maps each Agora channel path to a separate Matrix room, organized into a Matrix Space:

```
agora://bafkrei.../general             -> !room1:example.com (in Space)
agora://bafkrei.../engineering/backend -> !room2:example.com (in Space)
agora://bafkrei.../engineering/fips    -> !room3:example.com (in Space)
```

Category channels (`type: category`) with no messages of their own map to Matrix Space sub-spaces rather than rooms.

### 2.5 E2EE Mismatch

When the Matrix room has Megolm E2EE enabled, the gateway holds both MLS session state (for Agora) and Megolm session state (for Matrix). It is the trust boundary: it decrypts on one side and re-encrypts on the other. This is the structural nature of bridging two incompatible E2EE systems. The plaintext handling rules of spec §9.1 apply.

When the Matrix room does not have Megolm E2EE enabled, the gateway sends plaintext to the Matrix homeserver, whose operator can then read bridged messages. The admin sets `unencryptedRemote` to `true` in the gateway's `GatewayDescriptor` (spec §9.2), and clients show it as spec §9.3 describes.

### 2.6 Implementation Approach

Use the **Matrix Application Service API** rather than the Client-Server API. Application services receive all events in a room without polling, can register virtual users in bulk, and get better rate-limit treatment. The gateway registers as an application service on the Matrix homeserver with a namespace regex matching all virtual Agora users.

**Reference implementations.** [`mautrix-go`](https://github.com/mautrix/go) and [`mautrix-python`](https://github.com/mautrix/python) provide the application service scaffolding.

## 3. Slack and Teams Bridges

Placeholder. Slack and Microsoft Teams bridges follow the same model as section 2: a CO component with its own DID, admitted as a channel member, with a `GatewayDescriptor` whose `protocol` is `"slack"` or `"teams"` and whose `target` is the workspace channel or Teams channel ID. Neither network offers end-to-end encryption to a bridge, so `unencryptedRemote` is `true`. Message mapping, attachment handling, and identity mapping are not yet written.

## 4. Path to Native MIMI

### 4.1 What It Gives

MIMI is the IETF working group producing a standard for cross-provider messaging over MLS. Agora and MIMI share RFC 9420. Native interop would put Agora and MIMI members in one MLS group with one tree and one set of epoch secrets, so a message stays end-to-end encrypted across the provider boundary. No component re-encrypts, and nothing in the path is a gateway.

### 4.2 Status (as of 2026-10-17)

- The drafts are active: `draft-ietf-mimi-arch-03`, `draft-ietf-mimi-protocol-06`, `draft-ietf-mimi-content-09`, `draft-ietf-mimi-room-policy-04`. Identity, identifiers, message status, attachments, and message-ID AAD are individual drafts.
- No major provider ships MIMI. Meta's interoperability offer under the EU Digital Markets Act is based on the Signal protocol, not MIMI.
- MIMI defines no voice or video interop.

Agora therefore specifies no native MIMI interop now, and decides the ordering question in section 4.3 when MIMI is needed.

### 4.3 What It Would Take

**Placement.** MIMI's hub and follower are provider roles that see the participant list, room policy, and metadata. On the Agora side they are CO components, consistent with spec §9 and ARCHITECTURE S1 and S8. Relays never take part: a relay is never a hub or follower and carries only token-keyed ciphertext. Exporter outputs that the CO-side endpoint holds never pass to an Infrastructure Operator (ARCHITECTURE S3).

**Ordering.** One orderer per MIMI-interop channel:
- When an Agora CO hosts the room, it is the MIMI hub, and the hub orders the interop channel's Commits in place of an Agora sequencer. Hosting also needs MIMI room state in the MLS GroupContext (participant list and room policy components) and a mapping from Agora Space roles and bans to MIMI room-policy roles, with Space state as the source of truth.
- When a peer provider hosts the room, the Agora CO endpoint is a follower. The foreign hub's order is authoritative, the channel runs with no Agora sequencer, and Agora cannot enforce Space policy on MIMI members.

**Content.** In a shared group, `application/mimi-content` (framed per the MLS content advertisement extension) is the only canonical content. Agora clients build their local JMAP `Message` view from it. They derive `senderMsgId` deterministically from the MIMI `MessageId` (for example, ULID time from the hub timestamp and ULID randomness from `MessageId` octets 1 to 10), so `replyTo`, `threadRootId`, and reaction references resolve the same way on every device. A CO-side translator between mimi-content and JMAP Chat would hold plaintext and be the MLS sender, so it would be a gateway under spec §9, not native interop. The mapping is lossy in both directions; `notes/mimi-vs-jmap-chat.md` has the feature table.

**Identity.** MIMI addresses users by `mimi://provider/u/user-id` URIs and has no DID support. An Agora leaf in a shared group would carry both the DID and the MIMI URI, in a new MLS credential type. The intended codepoint is 0xF0A2 from the RFC 9420 private-use range; it is not allocated in spec Appendix D. Interoperating with providers outside Agora needs an IANA "MLS Credential Types" codepoint (RFC 9420 §17.5) or a credential type MIMI defines, and MIMI clients would have to support it. The fallback is a `basic` credential holding the MIMI URI, with the CO-side endpoint holding the URI-to-DID mapping; that mapping never goes to a relay.

**Disclosure.** The peer provider learns the room's participant list, so native interop would need a disclosure to members comparable to the gateway disclosure in spec §9.3.

**Not mapped.** Franking-based abuse reports, relative expiry, and multipart alternatives have no Agora counterpart; Agora typing, presence, broadcast mentions, and pins have no MIMI counterpart.

### 4.4 Pointers

- `notes/mimi-vs-jmap-chat.md`: layer comparison, feature mapping, translation feasibility, recommendations.
- MIMI drafts on the IETF datatracker, at the revisions in section 4.2.
- RFC 9420 (MLS), RFC 9750 (MLS architecture).
