# 9. Interoperability

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3427–3620 (§16).


*Binds: CO.*

Every interop component in this section (MIMI provider endpoints, gateways and bridges) is a CO component (ARCHITECTURE.md §2.3, S8). None of them runs in, or as part of, a relay or any other IO component. Relays carry interop traffic only as ordinary ciphertext envelopes keyed by `channelToken` and signed with the channel admission key (§5.2.2).

## 9.1 MIMI Native Interop

MIMI (More Instant Messaging Interoperability) is an IETF working group producing a standard for cross-system E2EE messaging using MLS as the shared key agreement layer. Agora and MIMI share RFC 9420 as their cryptographic foundation, which means interop between the two is a content format and delivery protocol bridging problem rather than a gateway problem requiring re-encryption. E2EE is preserved end-to-end across the system boundary.

**Reference specifications:** `draft-ietf-mimi-arch-02` (MIMI architecture, expired), `draft-ietf-mimi-content-08` (content format, active), `draft-ietf-mimi-protocol-05` (delivery service protocol, expired).

### Shared MLS Group

In MIMI interop mode, a single MLS group spans both Agora and the MIMI-compliant peer system. Members from both systems hold leaves in the same MLS tree and share the same epoch secrets. There is no re-encryption at the boundary. A message sent by an Agora client is decryptable by a MIMI client using its own MLS implementation, and vice versa.

This requires that both systems use compatible MLS ciphersuites. Agora groups use `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519` (ciphersuite 0x0001, §5.2.1), which is the MIMI baseline.

### Identity Mapping

Agora users are identified by DID (`did:webvh`, `did:plc` or `did:key`, §2.1). MIMI defines its own identifier scheme: MIMI URIs of the form `mimi://provider/user-id`. This is a bespoke URI scheme minted by the MIMI WG rather than an adoption of any existing identity standard. It is functionally equivalent to `did:web` (a domain-scoped opaque user identifier with no standardized resolution mechanism beyond DNS) but is a distinct namespace with no interoperability with DID resolvers or any other identity infrastructure.

The consequence for Agora is that MIMI interop requires carrying two parallel identifiers for every user in a cross-system MLS group: the Agora DID (which has a resolution spec, a key material binding, and is used for all Agora-internal operations) and the MIMI URI (which the MIMI delivery service requires to route messages and manage room membership). There is no way to derive one from the other or collapse them into a single identifier without either Agora abandoning DIDs or MIMI adopting them.

Each leaf node's credential in a MIMI-interop MLS group therefore carries both. Outside MIMI interop, leaves carry the `basic` credential of §5.2.1. In a MIMI-interop group, an Agora leaf carries an `AgoraMIMICredential` instead, an MLS credential of credential type 0xF0A2, a value from the RFC 9420 private-use range (0xF000 to 0xFFFF) used until a codepoint is registered (Appendix D). In the TLS presentation language of RFC 9420:

```
struct {
    opaque did<V>;        /* UTF-8 bytes of the member's DID */
    opaque mimi_uri<V>;   /* UTF-8 bytes of the member's MIMI URI */
} AgoraMIMICredential;

struct {
    CredentialType credential_type;
    select (Credential.credential_type) {
        case basic:     opaque identity<V>;
        case x509:      Certificate certificates<V>;
        case agora_mimi: AgoraMIMICredential agora_mimi;   /* 0xF0A2 */
    };
} Credential;
```

For example, `did` holds the bytes of `did:key:z6Mk...` and `mimi_uri` those of `mimi://example.com/alice`. The leaf's `signature_key` and any `agora_device_binding` extension follow §5.2.1 exactly, with `did` in place of the `basic` credential's `identity`; every check §5.2.1 and §5.2.1.1 make against the credential's DID uses `did`. The credential is carried only inside MLS and has no object-level signature (§13.1.1); the leaf node signature authenticates it.

RFC 9420 §7.3 requires every member's leaf `capabilities.credentials` to list each credential type in use in the group, so every Agora leaf in a MIMI-interop group lists 0xF0A2, and a MIMI client can join only if it supports type 0xF0A2. Agora clients verify `did`, the signature key binding and the leaf signature. A MIMI client that supports the type verifies `mimi_uri` and need not interpret `did`. No MIMI draft defines this credential type, so MIMI clients that implement only the credential types MIMI defines will not support it; this is a known interoperability risk. Where a peer provider's clients cannot support it, the fallback is for Agora leaves to carry a `basic` credential whose `identity` is the MIMI URI, and for the CO's MIMI provider endpoint to hold the mapping from MIMI URI to Agora DID and serve it to Agora members (see Delivery Service Bridging). Agora clients then cannot check the DID binding from the leaf alone; how they obtain the mapping from that endpoint is not specified in this version. This mapping MUST NOT be held by a relay.

For display purposes, neither side needs to parse the other's identifier format: MIMI URIs are rendered as opaque display strings in Agora clients, and Agora DIDs are rendered as opaque display strings in MIMI clients.

### Content Format

Agora inner payloads are typed payload envelopes (§13.1); chat content is JMAP Chat objects such as `urn:ietf:params:jmap:chat#Message` (§5.2.3). MIMI defines its own content format (`draft-ietf-mimi-content-08`). A channel in MIMI interop mode MUST negotiate a shared content format. Two modes are supported:

**MIMI content format mode**: the channel uses the MIMI content format as the canonical inner payload. Agora clients serialize outgoing messages to MIMI content format and deserialize incoming MIMI content to their local display model. Agora-specific features not representable in MIMI content format are carried as MIMI content extensions using the MIMI extension mechanism.

**Agora content format mode**: the channel uses Agora typed payload envelopes carrying JMAP Chat objects (§5.2.3) as the canonical inner payload. MIMI clients that support Agora content format (via a registered MIMI content type) can participate natively. MIMI clients that do not support Agora content format receive a fallback plain-text rendering negotiated at join time.

The content format in use is declared in the channel's entry in Space state (§3.3):

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

MIMI defines a delivery service protocol (`draft-ietf-mimi-protocol-05`) for cross-provider message routing. The MIMI delivery service tracks room participants by MIMI URI, so the Agora-side MIMI endpoint necessarily knows group membership. It is therefore a CO component: the CO operating the channel runs a MIMI provider endpoint, and a relay MUST NOT act as a MIMI delivery service endpoint (ARCHITECTURE.md S1). MLS Commits and Welcome messages are exchanged between the CO's MIMI provider endpoint and the peer MIMI provider via the MIMI delivery protocol. The channel's relays handle Agora-side delivery as token-keyed ciphertext; the MIMI protocol handles the cross-provider leg.

The CO's MIMI provider endpoint registers as the MIMI delivery service endpoint for the channel's MLS group with the peer MIMI provider. MLS handshake messages (Proposals, Commits, KeyPackages) flow bidirectionally between the two delivery services, and the endpoint carries the group's application messages between the peer provider and the channel's relays.

To publish to the relays, the endpoint signs routing envelopes with the channel admission key, and to read from them and post to them it removes and applies the sealed envelope (§5.2.2). The admission key is a CO-issued key, which the endpoint holds as a CO component. The sealing key is an MLS exporter output of each epoch, so the endpoint holds group secrets in one of two ways:

- It is a member of the group, admitted as a passive member (§5.2.1.3) and visible in the group's membership like a compliance logger (§7.7). As a member it can decrypt the group's content.
- It is not a member and receives the sealing key of each epoch from a CO component that is a member. It then handles only MLS ciphertext and does not see plaintext. This is the RECOMMENDED form.

Either way the endpoint is inside the CO trust boundary (ARCHITECTURE §2.3), and the exporter outputs it holds MUST NOT be passed to any IO (ARCHITECTURE S3). Members SHOULD be told that the peer MIMI provider also learns the room's participant list.

### Limitations

MIMI interop is currently limited by the MIMI specification's own draft status. As of April 2026, the content format (`draft-ietf-mimi-content-08`) is active; the architecture (`draft-ietf-mimi-arch-02`) and delivery service protocol (`draft-ietf-mimi-protocol-05`) drafts have both expired without replacement, indicating the WG is stalled on the delivery layer. The MLS WG's own federation draft (`draft-ietf-mls-federation-03`, expired September 2023) was also abandoned without a successor; cross-system MLS federation has no active IETF standardization track as of this writing. Agora implementations SHOULD track the MIMI drafts and update their interop implementation as the specs stabilize. Channel entries carrying `mimiInterop` configurations MUST include a `mimiSpecVersion` field to allow clients to detect and handle version skew.

MIMI interop does not currently specify voice/video interop. VTC channels cannot operate in MIMI interop mode until MIMI adds a media signaling specification.

---

## 9.2 Matrix Gateway

Matrix interop is a **gateway**, not native interop. A Matrix gateway is a CO component (ARCHITECTURE.md §2.3, S8): it MUST run under the control of the CO operating the channel and MUST NOT run in or as part of a relay. Co-location on IO hardware is permitted only as S8 allows, with the gateway remaining a CO principal with its own DID and keys. A Matrix gateway holds an Agora DID, is admitted to the relevant channel MLS groups as a member, decrypts Agora messages, re-encrypts them using Matrix's Megolm E2EE for delivery to Matrix users, and performs the reverse for Matrix→Agora direction. **E2EE is broken at the gateway: the gateway holds plaintext.** This MUST be made visible to all participants (§9.3).

### Gateway Identity and Admission

The Matrix gateway runs as an Agora client with its own DID. It is added to channel MLS groups by a channel Admin via a normal MLS Add commit, exactly like any other member. The gateway's DID document includes a `service` entry identifying it as a gateway:

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

The channel's entry in Space state records the gateway's presence and type:

```json
"gateways": [
  {
    "@type": "GatewayDescriptor",
    "did": "did:webvh:QmSCID...:example.com:agora:gateway",
    "protocol": "matrix",
    "matrixRoomID": "!abc123:example.com",
    "addedBy": "did:key:z6MkAdmin...",
    "addedAt": "2026-03-12T00:00:00Z"
  }
]
```

### Message Flow: Agora → Matrix

1. Gateway receives an MLS-encrypted message from the channel's relays (§11).
2. Gateway decrypts it using its MLS leaf key (it is a full group member).
3. Gateway translates Agora inner payload to Matrix event format:
   - New `urn:ietf:params:jmap:chat#Message` → `m.room.message` with `msgtype: m.text`
   - New `Message` with `attachments` → `m.room.message` with `msgtype: m.image/m.file` etc.; media fetched from the channel's relays (§10.4.4), decrypted with the attachment's `contentKey` and checked against its `sha256` (§14.3.4), and re-uploaded to the Matrix media server
   - `Message` edit (body contains `editedAt`, §5.2.3) → `m.room.message` with `m.new_content` relation
   - `Message` deletion (body contains `deletedAt` and `deletedForAll: true`, §5.2.3) → `m.room.redaction`
   - `urn:ietf:params:jmap:chat#Reaction` → `m.reaction`
4. Gateway sends the translated event to the bridged Matrix room via the Matrix Client-Server API, attributed to a virtual Matrix user representing the Agora sender (`@agora_<hash>:example.com`, see Identity and Namespace Mapping).
5. If the Matrix room has Megolm E2EE enabled, the gateway re-encrypts the event using Megolm before sending.

### Message Flow: Matrix → Agora

1. Gateway receives a Matrix event via the Matrix Application Service API.
2. Gateway translates the Matrix event to Agora inner payload format.
3. Gateway encrypts the payload using its MLS group membership.
4. Gateway publishes the outer `RoutingEnvelope`, signed with the channel admission key it obtains as a member (§5.2.2), to the channel's relays.
5. Agora clients see the message as coming from the gateway DID. The payload is a `urn:ietf:params:jmap:chat#Message` whose body carries a `bridgedFrom` field identifying the original Matrix sender:

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

### Identity and Namespace Mapping

Agora DIDs map to Matrix virtual users with a deterministic MXID derived from the DID: `@agora_<hash>:<gateway-homeserver>`, where `<hash>` is the first 20 bytes of the SHA-256 of the full DID string (UTF-8), encoded as lowercase RFC 4648 base32 without padding. The result contains only characters Matrix allows in a user localpart, for every DID method. Matrix MXIDs map to Agora gateway messages with `bridgedFrom.senderID` carrying the MXID.

Agora's nested channel namespace does not map cleanly to Matrix's flat room model. The gateway maps each Agora channel path to a separate Matrix room, organized into a Matrix Space:

```
agora://bafkrei.../general             → !room1:example.com (in Space)
agora://bafkrei.../engineering/backend → !room2:example.com (in Space)
agora://bafkrei.../engineering/fips    → !room3:example.com (in Space)
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

**Channel state disclosure.** The `gateways` array in the channel's entry in Space state (§9.2) is visible to all MLS group members. Clients MUST display a visible indicator when a channel has active gateways. The indicator MUST identify the gateway protocol and target system. A channel with an active gateway is not E2EE-private for bridged traffic; members must be able to determine this without reading protocol documentation.

**Gateway transparency message.** When a gateway DID is added to a channel's MLS group, the adding Admin MUST also send a `SystemEvent` MLS application message (§5.2.3) to the channel announcing the gateway. As an inside-group object it carries no object signature; the Admin's MLS sender signature authenticates it (§13.1.1):

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

**Client rendering.** Clients MUST render a persistent banner or channel badge indicating gateway presence. The banner MUST NOT be dismissible per-session without re-appearing on reconnect. Members who joined after a gateway was added see the indicator from the `gateways` array in Space state immediately on first load, whether or not they received the `SystemEvent`.


---

