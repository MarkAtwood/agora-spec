# 9. Interoperability

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3427–3620 (§16).


*Binds: CO.*

Every interop component in this section (MIMI provider endpoints, gateways and bridges) is a CO component (ARCHITECTURE.md §2.3, S8). None of them runs in, or as part of, a relay or any other IO component. Relays carry interop traffic only as ordinary ciphertext envelopes keyed by `channelToken`.

## 9.1 MIMI Native Interop

MIMI (More Instant Messaging Interoperability) is an IETF working group producing a standard for cross-system E2EE messaging using MLS as the shared key agreement layer. Agora and MIMI share RFC 9420 as their cryptographic foundation, which means interop between the two is a content format and delivery protocol bridging problem rather than a gateway problem requiring re-encryption. E2EE is preserved end-to-end across the system boundary.

**Reference specifications:** `draft-ietf-mimi-arch-02` (MIMI architecture, expired), `draft-ietf-mimi-content-08` (content format, active), `draft-ietf-mimi-protocol-05` (delivery service protocol, expired).

### Shared MLS Group

In MIMI interop mode, a single MLS group spans both Agora and the MIMI-compliant peer system. Members from both systems hold leaves in the same MLS tree and share the same epoch secrets. There is no re-encryption at the boundary. A message sent by an Agora client is decryptable by a MIMI client using its own MLS implementation, and vice versa.

This requires that both systems use compatible MLS ciphersuites. Agora MUST support `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519` (ciphersuite 0x0001, the MIMI-mandated baseline) in addition to any other suites it implements. Channels operating in MIMI interop mode MUST use this ciphersuite.

### Identity Mapping

Agora users are identified by DID (`did:key` or `did:web`). MIMI defines its own identifier scheme: MIMI URIs of the form `mimi://provider/user-id`. This is a bespoke URI scheme minted by the MIMI WG rather than an adoption of any existing identity standard. It is functionally equivalent to `did:web` (a domain-scoped opaque user identifier with no standardized resolution mechanism beyond DNS) but is a distinct namespace with no interoperability with DID resolvers or any other identity infrastructure.

The consequence for Agora is that MIMI interop requires carrying two parallel identifiers for every user in a cross-system MLS group: the Agora DID (which has a resolution spec, a key material binding, and is used for all Agora-internal operations) and the MIMI URI (which the MIMI delivery service requires to route messages and manage room membership). There is no way to derive one from the other or collapse them into a single identifier without either Agora abandoning DIDs or MIMI adopting them.

Each leaf node's credential in a MIMI-interop MLS group therefore carries both:

```json
{
  "@type": "AgoraMIMICredential",
  "did": "did:key:z6Mk...",
  "mimiURI": "mimi://example.com/alice",
  "sig": "base64url..."
}
```

The credential is signed by the Agora authentication key. Agora clients verify the DID and signature. MIMI clients verify the MIMI URI portion and MUST treat the `did` field as an unknown extension. The `draft-ietf-mimi-content` spec does not explicitly specify that unknown credential fields are to be ignored rather than rejected, which is a known interoperability risk. Agora implementations SHOULD monitor MIMI client behavior for strict credential validation that rejects unknown fields; if this occurs in practice, the fallback is to strip the `did` field from credentials presented to MIMI clients and maintain a side-channel mapping from MIMI URI to Agora DID in the CO's MIMI provider endpoint (see Delivery Service Bridging). This mapping MUST NOT be held by a relay.

For display purposes, neither side needs to parse the other's identifier format: MIMI URIs are rendered as opaque display strings in Agora clients, and Agora DIDs are rendered as opaque display strings in MIMI clients.

### Content Format

Agora inner payloads use JSON-LD (`@type: ChatMessage` etc.). MIMI defines its own content format (`draft-ietf-mimi-content-08`). A channel in MIMI interop mode MUST negotiate a shared content format. Two modes are supported:

**MIMI content format mode**: the channel uses the MIMI content format as the canonical inner payload. Agora clients serialize outgoing messages to MIMI content format and deserialize incoming MIMI content to their local display model. Agora-specific features not representable in MIMI content format are carried as MIMI content extensions using the MIMI extension mechanism.

**Agora content format mode**: the channel uses Agora JSON-LD as the canonical inner payload. MIMI clients that support Agora content format (via a registered MIMI content type) can participate natively. MIMI clients that do not support Agora content format receive a fallback plain-text rendering negotiated at join time.

The content format in use is declared in the channel state document:

```json
"mimiInterop": {
  "@type": "MIMIInteropConfig",
  "enabled": true,
  "contentFormat": "mimi-v1",
  "mimiProvider": "example.com",
  "mimiRoomURI": "mimi://example.com/rooms/engineering",
  "mimiSpecVersion": "draft-ietf-mimi-content-08"
}
```

### Delivery Service Bridging

MIMI defines a delivery service protocol (`draft-ietf-mimi-protocol-05`) for cross-provider message routing. The MIMI delivery service tracks room participants by MIMI URI, so the Agora-side MIMI endpoint necessarily knows group membership. It is therefore a CO component: the CO operating the channel runs a MIMI provider endpoint, and a relay MUST NOT act as a MIMI delivery service endpoint (ARCHITECTURE.md S1). MLS Commits and Welcome messages are exchanged between the CO's MIMI provider endpoint and the peer MIMI provider via the MIMI delivery protocol. Gossipsub fanout through relays handles Agora-side delivery as token-keyed ciphertext; the MIMI protocol handles the cross-provider leg.

The CO's MIMI provider endpoint registers as the MIMI delivery service endpoint for the channel's MLS group with the peer MIMI provider. MLS handshake messages (Proposals, Commits, KeyPackages) flow bidirectionally between the two delivery services. The endpoint holds no MLS group secrets and sees no plaintext; it relays handshake messages between the MIMI provider and the channel's relays as ciphertext. Members SHOULD be told that the peer MIMI provider also learns the room's participant list.

### Limitations

MIMI interop is currently limited by the MIMI specification's own draft status. As of April 2026, the content format (`draft-ietf-mimi-content-08`) is active; the architecture (`draft-ietf-mimi-arch-02`) and delivery service protocol (`draft-ietf-mimi-protocol-05`) drafts have both expired without replacement, indicating the WG is stalled on the delivery layer. The MLS WG's own federation draft (`draft-ietf-mls-federation-03`, expired September 2023) was also abandoned without a successor; cross-system MLS federation has no active IETF standardization track as of this writing. Agora implementations SHOULD track the MIMI drafts and update their interop implementation as the specs stabilize. Channel state documents carrying `mimiInterop` configurations MUST include a `mimiSpecVersion` field to allow clients to detect and handle version skew.

MIMI interop does not currently specify voice/video interop. VTC channels cannot operate in MIMI interop mode until MIMI adds a media signaling specification.

---

## 9.2 Matrix Gateway

Matrix interop is a **gateway**, not native interop. A Matrix gateway is a CO component (ARCHITECTURE.md §2.3, S8): it MUST run under the control of the CO operating the channel and MUST NOT run in or as part of a relay. Co-location on IO hardware is permitted only as S8 allows, with the gateway remaining a CO principal with its own DID and keys. A Matrix gateway holds an Agora DID, is admitted to the relevant channel MLS groups as a member, decrypts Agora messages, re-encrypts them using Matrix's Megolm E2EE for delivery to Matrix users, and performs the reverse for Matrix→Agora direction. **E2EE is broken at the gateway: the gateway holds plaintext.** This MUST be made visible to all participants (§9.3).

### Gateway Identity and Admission

The Matrix gateway runs as an Agora client with its own DID. It is added to channel MLS groups by a channel Admin via a normal MLS Add commit, exactly like any other member. The gateway's DID document includes a `service` entry identifying it as a gateway:

```json
{
  "service": [{
    "id": "did:key:z6MkGateway...#gateway",
    "type": "AgoraMatrixGateway",
    "serviceEndpoint": "https://matrix.example.com",
    "matrixServerName": "example.com"
  }]
}
```

The channel state document records the gateway's presence and type:

```json
"gateways": [
  {
    "@type": "GatewayDescriptor",
    "did": "did:key:z6MkGateway...",
    "protocol": "matrix",
    "matrixRoomID": "!abc123:example.com",
    "addedBy": "did:key:z6MkAdmin...",
    "addedAt": "2026-03-12T00:00:00Z"
  }
]
```

### Message Flow: Agora → Matrix

1. Gateway receives an MLS-encrypted message from the Agora channel gossip topic.
2. Gateway decrypts it using its MLS leaf key (it is a full group member).
3. Gateway translates Agora inner payload to Matrix event format:
   - `TextBody` → `m.room.message` with `msgtype: m.text`
   - `MediaBody` → `m.room.message` with `msgtype: m.image/m.file` etc.; media fetched from IPFS and re-uploaded to the Matrix media server
   - `EditEvent` → `m.room.message` with `m.new_content` relation
   - `DeleteEvent` → `m.room.redaction`
   - `ReactionEvent` → `m.reaction`
4. Gateway sends the translated event to the bridged Matrix room via the Matrix Client-Server API, attributed to a virtual Matrix user representing the Agora sender (`@agora_z6Mk...:example.com`).
5. If the Matrix room has Megolm E2EE enabled, the gateway re-encrypts the event using Megolm before sending.

### Message Flow: Matrix → Agora

1. Gateway receives a Matrix event via the Matrix Application Service API.
2. Gateway translates the Matrix event to Agora inner payload format.
3. Gateway encrypts the payload using its MLS group membership.
4. Gateway publishes the outer `RoutingEnvelope` to the Agora channel gossip topic.
5. Agora clients see the message as coming from the gateway DID with a `bridgedFrom` field in the inner payload identifying the original Matrix sender:

```json
{
  "@type": "ChatMessage",
  "body": { "@type": "TextBody", "text": "hello from matrix" },
  "bridgedFrom": {
    "protocol": "matrix",
    "senderID": "@alice:example.com",
    "eventID": "$abc123"
  }
}
```

### Identity and Namespace Mapping

Agora DIDs map to Matrix virtual users with a deterministic MXID derived from the DID: `@agora_<did-fragment>:<gateway-homeserver>`. Matrix MXIDs map to Agora gateway messages with `bridgedFrom.senderID` carrying the MXID.

Agora's nested channel namespace does not map cleanly to Matrix's flat room model. The gateway maps each Agora channel path to a separate Matrix room, organized into a Matrix Space:

```
agora://bafyrei.../general             → !room1:example.com (in Space)
agora://bafyrei.../engineering/backend → !room2:example.com (in Space)
agora://bafyrei.../engineering/fips    → !room3:example.com (in Space)
```

Category channels (`type: category`) with no messages of their own map to Matrix Space sub-spaces rather than rooms.

### E2EE Mismatch Handling

When the Matrix room has Megolm E2EE enabled, the gateway holds both MLS session state (for Agora) and Megolm session state (for Matrix). The gateway is the trust boundary: it decrypts on one side and re-encrypts on the other. This is unavoidable; it is the structural nature of bridging two incompatible E2EE systems.

The gateway MUST NOT cache decrypted message content beyond the time needed for translation and re-encryption. It SHOULD operate in a memory-only mode with no persistent plaintext storage. Gateway operators SHOULD publish a transparency policy describing their plaintext handling.

When the Matrix room does not have Megolm E2EE enabled, the gateway sends plaintext to the Matrix server. This is a further trust degradation: the Matrix homeserver operator can read bridged messages. This MUST be disclosed to Agora channel members (§9.3).

### Implementation Approach

The recommended implementation uses the **Matrix Application Service API** rather than the Client-Server API. Application services receive all events in a room without polling, can register virtual users in bulk, and receive better rate limit treatment. The gateway registers as an application service on the Matrix homeserver with a namespace regex matching all virtual Agora users.

**Reference implementations:** [`mautrix-go`](https://github.com/mautrix/go) and [`mautrix-python`](https://github.com/mautrix/python) provide the application service scaffolding.

---

## 9.3 Gateway Transparency

Any gateway admitted to an Agora channel (Matrix, or any future gateway type) is a CO component subject to the same placement rule as §9.2 and MUST be disclosed to all channel members. This is enforced at the protocol level, not by policy.

**Channel state disclosure.** The `gateways` array in the channel state document (§9.2) is visible to all MLS group members. Clients MUST display a visible indicator when a channel has active gateways. The indicator MUST identify the gateway protocol and target system. A channel with an active gateway is not E2EE-private for bridged traffic; members must be able to determine this without reading protocol documentation.

**Gateway transparency message.** When a gateway DID is added to a channel's MLS group, the adding Admin MUST also send a signed `SystemEvent` inner payload to the channel announcing the gateway:

```json
{
  "@type": "SystemEvent",
  "event": "gateway-added",
  "gatewayDID": "did:key:z6MkGateway...",
  "protocol": "matrix",
  "target": "!abc123:example.com",
  "addedBy": "did:key:z6MkAdmin...",
  "e2eeNote": "Messages in this channel are bridged to Matrix. E2EE is not preserved for bridged traffic."
}
```

This event is stored in the channel's IPLD history, a permanent record that a gateway was added and when.

**Client rendering.** Clients MUST render a persistent banner or channel badge indicating gateway presence. The banner MUST NOT be dismissible per-session without re-appearing on reconnect. Members who joined after a gateway was added receive the `SystemEvent` from history and see the indicator immediately on first load.


---

