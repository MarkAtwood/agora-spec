# IMP review: implementability

Lens: build an interoperable client, relay and CO services from spec/01..14 and 99 alone. Each entry is a place where two independent implementers would have to guess and could diverge. Ordered roughly by how badly divergence breaks interop.

### IMP-1: The live client-relay protocol has no message set
- Severity: P1
- Location: spec/11-transport.md:36, :54-64, :20-22; spec/11-transport.md:398-407
- Evidence: "`[version: u8, type: u8, topic: string, payload: bytes]`"; "`type` values: `0x01` Gossip, `0x02` MLS, `0x03` Ephemeral, `0x04` Control"; "Multiplexing is handled by a lightweight channel ID prefix on each frame"; "Relays MUST accept both JSON and CBOR"
- Problem: Only ClientHello/RelayHello/AdmissionChallenge/AdmissionProof are defined. Nothing defines how a client subscribes or unsubscribes to a `channelToken`, publishes an envelope, receives delivered envelopes, gets an ack or rejection, catches up on queued messages after push wake-up, sends pin/unpin instructions, or registers push "over the live stream" (the §11.8.8 table says push registration is live-stream only). Also undefined: whether the frame is a CBOR array or map, how a frame is delimited on a WebTransport stream (length prefix?), which frame types go on datagrams vs which stream, the WebSocket "channel ID prefix" (which the frame structure does not contain), how a relay tells JSON from CBOR, the maximum frame size, and the meaning of `topic` for Control frames. Two clean-room implementations will not exchange a single message after the hello.
- Suggested fix: Add §11.4.1 "Control messages" with a CDDL definition for each frame type and Control message (Subscribe, Unsubscribe, Publish, Deliver, Ack, Error, Pin, Unpin, PushRegister, HistoryRequest), framing rules per transport (for example a 4-byte big-endian length prefix on bidirectional streams, one frame per WebSocket binary message), a maximum frame size, and drop the JSON variant or require JSON only on a separately negotiated debug flag.
- Needs decision: yes. (a) Define a native frame protocol as above; (b) reuse JMAP-over-WebSocket (RFC 8887) with Agora methods; (c) put all writes on HTTP and keep the live stream delivery-only. Recommend (a): it is the smallest change from the current text and keeps one framing for both transports.

### IMP-2: Exact bytes covered by `accessSig`, `billingSig` and the envelope `id` are undefined
- Severity: P1
- Location: spec/05-messaging.md:181-206; spec/13-encoding.md:85, :91
- Evidence: "`id` is the CID of the canonical outer envelope"; "`accessSig` is an Ed25519 signature ... over the routing envelope with `accessSig` omitted"; "`billingSig` ... signed per §13.1.1 over the announcement with `billingSig` omitted"; §13.1: "The map itself is not signed, so its key order and integer widths carry no meaning."
- Problem: The RoutingEnvelope is shown only as JSON with base64url strings, yet relays receive CBOR frames (§11.4) or JSON. No serialization of "the routing envelope with `accessSig` omitted" is defined: no encoding, key order, or rule for whether `powProof`, `pushUrgency`, `accessKeyAnnouncement` and `broadcastPayload` are covered. "Canonical" contradicts §13.1's "no canonical form", and `id` is a CID of an envelope that contains `id`, which is circular. `billingSig` is said to be "per §13.1.1", but §13.1.1 signs an envelope `body`, and the announcement is not an envelope. Every relay would reject every envelope from a client that serializes differently. This is the core admission check.
- Suggested fix: Define RoutingEnvelope and accessKeyAnnouncement in CDDL as CBOR. Define the signed input as an explicit byte string (for example, `accessSig` signs `"agora/access/v1" || deterministic-CBOR(envelope minus accessSig and id)` per RFC 8949 §4.2.1), or carry the announcement as a typed envelope body so that §13.1.1 applies literally. Define `id` as computed over the bytes excluding `id`, or drop `id` from the wire and let each party compute it.
- Needs decision: yes. (a) Deterministic CBOR (RFC 8949 §4.2) only for these relay-verified structures; (b) sign a fixed binary concatenation of fields; (c) make the routing envelope a §13.1 typed envelope whose `body` is the signed bytes. Recommend (c) for announcements and registrations, since it reuses §13.1.1 and its test vectors, and (b) for per-message `accessSig`, since it is cheap and unambiguous.

### IMP-3: `accessKeyAnnouncement` and the registration-service API do not exist as wire formats
- Severity: P1
- Location: spec/05-messaging.md:203-205; spec/10-relays.md:612-624; spec/13-encoding.md:91
- Evidence: "attaches to the routing envelope carrying the Commit an `accessKeyAnnouncement` containing the new `epoch`, the new `channelToken`, and the new access public key"; "The committer obtains it from the service before publishing the Commit. The service countersigns only an announcement requested by a DID it authenticates as a current member"; "The CO's registration service submits an `AccessChainRegistration` to the Relay"
- Problem: Several pieces are missing. (1) There is no field list, types or key encoding for `accessKeyAnnouncement` (compare `accessPublicKey: "z6Mk..."`, multibase, in AccessChainRegistration). (2) No document says where the registration service is: no Space state field and no DID service type. (3) No request or response format and no member-authentication mechanism exist for countersignature or registration requests. (4) No relay endpoint or frame accepts an `AccessChainRegistration`, and the relay has no defined way to obtain the private `RelayServiceAgreement` it must verify `billingSig` against. (5) No rule says how a relay picks the agreement for a chain. An implementer cannot create a group that any relay will accept.
- Suggested fix: Add a "Registration service" subsection: a `registrationService {did, endpoint}` field in Space state (as for `sequencer`), `POST {endpoint}/register` and `POST {endpoint}/countersign` with CDDL bodies, and the member-auth scheme (see IMP-11). Add a relay endpoint (Peer API or a new `/v1/agora/rsa/` surface) that accepts the agreement and registrations, with error codes.
- Needs decision: no.

### IMP-4: Broadcast key rotation cannot be countersigned under the one-per-epoch rule
- Severity: P1
- Location: spec/05-messaging.md:136; spec/05-messaging.md:204
- Evidence: "an `accessKeyAnnouncement` with the unchanged `epoch` and access public key and the new `channelToken` ... countersigned with `billingSig`"; "and at most one announcement per chain and `epoch`"
- Problem: A rotation announcement reuses the current epoch. That epoch already had its announcement countersigned at the last publisher-group Commit, or at registration. A conformant registration service must therefore refuse to countersign the rotation. Implementers will diverge: some services allow it, others follow the letter, and relays cannot follow the token change. The text also does not say which of several posters is "first" to send the rotation announcement, or what the others do when they race.
- Suggested fix: Make the uniqueness key (chain, `epoch`, `keyEpoch`), carry `keyEpoch` in the announcement, and have the registration service, which is the CO, issue the rotation announcement itself when it publishes a new `BroadcastKey`, instead of "the first poster".
- Needs decision: no.

### IMP-5: `channelCID` is used as exporter context but never defined; DMs have none
- Severity: P1
- Location: spec/05-messaging.md:194, :202, :218; spec/03-spaces.md:166; spec/04-access-control.md:125, :145; spec/05-messaging.md:97, :146
- Evidence: "`MLS-Exporter(\"agora channel token\", channelCID, 32)`"; "`accessSeed = MLS-Exporter(\"agora access\", channelCID, 32)`"; "`GET <spaceEndpoint>/broadcast-key/<channelCID>`"; DM: "`MLS-Exporter(\"agora-dm-token\", \"\", 32)`"; "The `DMGroupDescriptor` is updated (new CID) on every membership or logger change"
- Problem: A channel is an entry inside the Space state document, not a separate content-addressed object, so nothing says what bytes "channelCID" is (CID of what? binary or string form?). Members who compute it differently derive different tokens, access keys and sealing keys, and cannot talk at all. DMs define only the token derivation. Access key and sealing key derivations for DMs still name `channelCID`, and the only DM CID (DMGroupCID) changes on every membership change. That would change keys mid-epoch.
- Suggested fix: Define a stable channel identifier, for example the MLS `group_id` bytes, or a fixed `channelID` minted at channel creation and recorded in the channel entry, and use it everywhere `channelCID` appears. Define its byte form as exporter context. Give one derivation table covering channels, DMs and broadcast.
- Needs decision: yes. (a) Use the MLS `group_id` as the exporter context, which is stable and already known to members; (b) mint a random 16-byte `channelID` in the channel entry and the DMGroupDescriptor. Recommend (a): no new field, and it exists for DMs.

### IMP-6: CID computation and the Space genesis self-reference are undefined
- Severity: P1
- Location: spec/13-encoding.md:91; spec/01-overview.md:43; spec/03-spaces.md:36, :49, :55
- Evidence: "its CID is computed over the encoded envelope bytes as stored"; "IPLD | Content-addressed data model (CIDv1 dag-cbor)"; "`<space-id>` is the CID of the Space's root state document"; genesis document contains `"id": "agora://bafyrei..."`
- Problem: No multicodec (raw 0x55 vs dag-cbor 0x71), multihash (sha2-256?) or string base (examples use `bafyrei`, which is base32 dag-cbor) is given. Envelopes are explicitly non-canonical CBOR, so they are not valid dag-cbor anyway. Two implementations will compute different CIDs for the same bytes, so Space IDs, `prevStateCID` links, invite and revocation references and blob addresses all diverge. The genesis SpaceState must contain its own CID in `id`, which is impossible.
- Suggested fix: State the rule once: CIDv1, codec `raw` (0x55) for envelopes and blobs, multihash sha2-256, text form base32 lower (`b...`), binary form wherever a CID is exporter or HKDF input. State that the genesis state omits `id` (or sets it to null) and that the Space ID is the CID of the genesis envelope.
- Needs decision: no.

### IMP-7: MLS credential format and the leaf-to-DID binding are undefined
- Severity: P1
- Location: spec/05-messaging.md:55, :79-80; spec/02-identity.md:80; spec/09-interop.md:28-36
- Evidence: "MLS leaf node credentials are bound to DID verification keys, so verifying an MLS credential means verifying a DID"; "The signature verifies against the KeyPackage owner's DID authentication key"; "`KeyPackage.leaf_node.credential` contains a valid DID"; MIMI: "`{\"@type\": \"AgoraMIMICredential\", ...}`"
- Problem: No MLS credential type is named (`basic`, x509, or a new registered type), nor what bytes `identity` holds (the DID string? a DID URL with fragment?). Nothing says how the leaf `signature_key` maps to a verification method: must it equal a device key in `authentication`? Is it matched by key bytes or by `kid`? What happens for P-256 devices (§12.6:89) under ciphersuite 0x0001, which is Ed25519-only? The MIMI credential is shown as JSON, which is not an MLS credential encoding and has no credential-type code. Every add/Welcome validation depends on this.
- Suggested fix: Specify `BasicCredential` with `identity` = UTF-8 DID (no fragment), and require `signature_key` to equal the raw Ed25519 public key of a verification method listed in the DID's `authentication` at validation time. Forbid P-256 device keys for MLS leaves under 0x0001, or name a P-256 ciphersuite. For MIMI, name the credential type and its TLS encoding.
- Needs decision: no.

### IMP-8: KeyPackage endpoint and Welcome delivery have no API
- Severity: P1
- Location: spec/05-messaging.md:50-51, :63-73; spec/07-compliance.md:185-195; spec/13-encoding.md:181; spec/10-relays.md:457; spec/02-identity.md:381; spec/04-access-control.md:147
- Evidence: "`\"type\": \"AgoraKeyPackageEndpoint\"`" (§7.8.2) vs "a `KeyPackageEndpoint` service entry" (§2.1, §2.5.3, §5.2.1.1); "The endpoint MUST return a fresh, unused `KeyPackage` on each GET request and MUST accept a `Welcome` by POST"; version table: "KeyPackage Store API | v1 | URL path prefix `/v1/agora/kp/`"
- Problem: Several things are missing. The DID service `type` string differs between sections, so clients cannot even find the endpoint. Nothing defines the URL layout (is `serviceEndpoint` the base for `/v1/agora/kp/...` or the full resource?), the upload method or its authentication (§2.5.4 says only "signed with the new device key"), the media types (`message/mls`? CBOR? JSON?), or how a committer gets one KeyPackage per device of the target. Each device is a separate leaf, and a single GET returns one KeyPackage. Also undefined: how the last-resort KeyPackage is flagged, the empty-supply response code, the rate-limit response, the Welcome POST body, the Welcome POST authentication and anti-spam rules, and how each device fetches and deletes its pending Welcomes (it must prove it is that device, by what mechanism?). There is also no expiry for unclaimed Welcomes.
- Suggested fix: Specify the KeyPackage Store API v1 in full: `POST {kp}/keypackages` (device-signed, see IMP-11), `GET {kp}/keypackages?device=all` returning one consumed KeyPackage per active device, `POST {kp}/welcome` with `message/mls` bodies, `GET/DELETE {kp}/welcome` authenticated by a device signature, status codes (404 no supply, 429 rate-limited), and one service type string.
- Needs decision: no.

### IMP-9: Concurrent Commits: no rule chooses the winning Commit
- Severity: P1
- Location: spec/05-messaging.md:23, :52, :203-205; spec/04-access-control.md:16
- Evidence: "by default, any current MLS group member may issue Commit messages"; "Clients MUST buffer application messages from a new epoch until the Commit that opened that epoch has been received"; "at most one announcement per chain and `epoch`"
- Problem: Gossip gives no total order. When two members commit in the same epoch, RFC 9420 requires the delivery service to choose one, and Agora names no rule. The registration service's one-countersignature-per-epoch rule in effect serializes Commits, but the text never says that clients MUST adopt the Commit whose envelope carries the countersigned announcement, or what the losing committer does (discard, then re-propose). Groups will fork across implementations. `commitPolicy` is mentioned but has no schema.
- Suggested fix: State that the Commit for epoch N+1 is the one whose routing envelope carries the `accessKeyAnnouncement` countersigned for N+1. Losing committers discard their pending Commit and retry against the new epoch. Define `commitPolicy` in the channel entry schema.
- Needs decision: no.

### IMP-10: HTTP representation of signed objects is undefined (CBOR envelope vs JSON)
- Severity: P1
- Location: spec/03-spaces.md:157-158, :166-167; spec/10-relays.md:49, :102, :315-317, :359; spec/13-encoding.md:91
- Evidence: "`GET <spaceEndpoint>/<cid> → the record with that CID, exactly as signed`"; "The manifest is a signed JSON document"; "A directory document is a static JSON file"; "The document is signed per §13.1.1 by the `maintainer` DID"; §13.1: "stored, served and forwarded as its encoded envelope with `sig` present"
- Problem: §13.1 says signed objects travel as CBOR envelopes, while the manifest and directories are described as JSON files served at well-known URLs. A static JSON file cannot carry a detached JWS over its own bytes. Undefined: the `Content-Type` of every response (`application/cbor`? an Agora media type?), what `/head` returns (a bare CID string? JSON? binary?), how `/broadcast-key/...` responses are encoded, and the error statuses. Peer relays, clients and directory publishers will pick different representations.
- Suggested fix: Register one media type (for example `application/agora-envelope+cbor`). Require every signed object served over HTTP, including the manifest and directories, to be served as its encoded envelope with that type. Define `/head` as `text/plain` base32 CID. Add a status code table.
- Needs decision: no.

### IMP-11: Member and device authentication to CO services is unspecified
- Severity: P1
- Location: spec/03-spaces.md:184; spec/05-messaging.md:204; spec/06-calls.md:214; spec/02-identity.md:320-336; spec/14-jmap.md:216
- Evidence: "clients that authenticate as current members (by DID authentication to the CO)"; "requested by a DID it authenticates as a current member"; "issues them only to current members of the Space"; "a CO invite service enforces them"
- Problem: The Space endpoint, registration service, TURN credential service, KeyPackage host, provisioning service and CO invite service must all authenticate a DID. No mechanism is defined: no challenge-response, no RFC 9421 profile, no JWS bearer token, no replay window. A client built against one CO's services will fail at another's.
- Suggested fix: Define one "DID request authentication" profile used by every CO service. For example, RFC 9421 with `keyid` = DID URL of a device `authentication` key, covered components `@method @target-uri content-digest`, `created`/`nonce` parameters and a 300 s window, mirroring §10.2.3. Reference it from each service.
- Needs decision: yes. (a) RFC 9421 per request, reusing §10.2.3 machinery; (b) a challenge/response that yields a short-lived bearer token. Recommend (a): no session state, and it already exists for relays.

### IMP-12: SFU signaling protocol is undefined
- Severity: P1
- Location: spec/06-calls.md:108-117
- Evidence: "Client presents the MLS-membership access proof for the voice channel's `channelToken`"; "the SFU responds with an SDP answer signed by the SFU's DID key"
- Problem: The SFU is an IO from a different vendor than the client, yet the WebSocket subprotocol, message types (offer, answer, candidate, subscribe, layer selection, leave), message encoding, how an access proof is presented (signature over what challenge? replay protection?) and the SDP signature format (a JWS per §13.1.1? over what bytes and `agoraType`?) are all undefined. Data-channel forwarding rules (§6.13) depend on this too.
- Suggested fix: Define the SFU signaling messages in CDDL, an access-proof challenge (SFU nonce signed with the epoch access key), and the signed answer as a §13.1.1 envelope of type `urn:agora:type:SfuAnswer`.
- Needs decision: no.

### IMP-13: Attachment encryption is contradictory and the key field is undefined
- Severity: P1
- Location: spec/05-messaging.md:255; spec/14-jmap.md:117; spec/03-spaces.md:190
- Evidence: §5.2.2: "An attachment's `blobId` is the CID of the file stored as a group-encrypted blob (§3.4)"; §14.3.4: "A blob referenced by a durable object (an `Attachment`, a `FileNode`, a `SceneAsset`) ... is encrypted under a random content key carried in that object"
- Problem: A sender following §5.2.2 uses the epoch-exporter key, while a receiver following §14.3.4 looks for a content key in the Attachment. No field name, AEAD or nonce layout is defined for the random-key format. Attachments will not decrypt across implementations.
- Suggested fix: Pick §14.3.4 for durable objects. Define the Attachment extension fields (for example `agoraKey`, base64url 16 bytes) and the blob layout `nonce(12) || AES-128-GCM(key, nonce, file, aad="agora/attachment/v1")`. Fix §5.2.2 to match.
- Needs decision: no.

### IMP-14: Gossipsub parameters needed for mesh interop are missing
- Severity: P2
- Location: spec/10-relays.md:253-266; spec/10-relays.md:154-156
- Evidence: "`v1/agora/channel/<channelToken>`"; "`POST /v1/agora/peer/gossip` ... Body: CBOR-encoded gossipsub message batch"
- Problem: Undefined items: the text encoding of `channelToken` in the topic string (base64url? hex?); the gossipsub signature policy (StrictSign attaches a peer ID and signature to every message, while StrictNoSign does not, and peers with mismatched policies drop each other's messages, which is also a blindness issue); the message-ID function used for deduplication; the maximum message size; what bytes a gossip message carries (a CBOR RoutingEnvelope? a §11.4 frame?); the format of the Peer API "gossip batch" and how it relates to the libp2p mesh. Also missing: the client-to-relay mapping of `channelToken` topics, and the `v1/agora/discovery` payload type (an encoded envelope?).
- Suggested fix: Specify topic = `v1/agora/channel/` + base64url-nopad(token); signature policy StrictNoSign; message-id = SHA-256 of the message data; maximum size equal to `maxEnvelopeBytes`; data = the CBOR-encoded RoutingEnvelope (or the encoded typed envelope on discovery); and a CDDL for the batch body.
- Needs decision: no.

### IMP-15: Space state schema is scattered and missing fields that signature checks need
- Severity: P2
- Location: spec/03-spaces.md:51-128, :131; spec/04-access-control.md:14, :16; spec/05-messaging.md:92, :127, :318; spec/06-calls.md:95, :193, :168; spec/09-interop.md:50-61, :98; spec/10-relays.md:670; spec/07-compliance.md:26, :120; spec/08-cross-space.md:81; spec/04-access-control.md:121
- Evidence: "clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state"; "Admin: a role granted by the owner and recorded in the Space state document"; "the channel state document tracks the latest history CID"; "The content format in use is declared in the channel state document"
- Problem: No field records admins or their scope, yet every state, moderation, BroadcastKey and invite verification depends on "admin authorized under the prior state". Channel fields (`commitPolicy`, `speakerBot`, `broadcasterRoles`, `keyAccess`, `e2eeMedia`, `powPolicy`, `gateways`, `mimiInterop`, the history head) and Space fields (`sfus`, `turnServers`, `complianceLogging`, `retentionNotice`, `sharedChannels`, the moderation log tail, `spaceEndpoint`?) appear only in scattered fragments, some attributed to a "channel state document" that does not exist. Types, defaults and required-ness are unstated.
- Suggested fix: Add one normative CDDL (or JSON Schema) for SpaceState and ChannelEntry in §3.3 that lists every field with its type, default and defining section, including an `admins: [{did, scope}]` member. Replace "channel state document" with "channel entry".
- Needs decision: no.

### IMP-16: Space state ordering contradicts the signed hash chain
- Severity: P2
- Location: spec/05-messaging.md:25; spec/03-spaces.md:49, :131
- Evidence: "Concurrent non-conflicting mutations ... are merged by taking the union. Conflicting mutations ... are resolved last-writer-wins using the `seq` value"; "subsequent state is represented as a signed chain of mutations, each referencing the prior state CID"
- Problem: Two admins signing from the same `prevStateCID` produce a fork. A "union" merge produces a document nobody signed, and the Space endpoint's `/head` can name only one. Implementations will variously reject forks, merge them or pick one by `seq`. The state document is also a full snapshot, not a mutation, so per-field merge is undefined.
- Suggested fix: Make the chain linear: the Space endpoint (CO) accepts only a state whose `prevStateCID` is the current head and whose `seq` is head+1, and clients treat the endpoint's `/head` as authoritative among validly signed successors. Delete the union/LWW paragraph.
- Needs decision: no.

### IMP-17: Sequencer wire details are incomplete, and pin updates use the wrong type
- Severity: P2
- Location: spec/14-jmap.md:156-165, :178; spec/05-messaging.md:354, :362-364
- Evidence: "Its envelope has `type` `urn:agora:type:JmapSet` ... with an added member `after`: the head (`stream`, `n`, stamp hash)"; "returns the encoded stamp envelope"; "`GET {endpoint}/log/{stream}?after={n}`, returning (stamp, operation) pairs"; §5.2.6: "A pin or unpin is an MLS application message of type `urn:ietf:params:jmap:chat#Chat`"
- Problem: Undefined: the encoding of `after` (a CBOR array in the envelope map? JSON?), the request and response content types, error and rate-limit statuses, the encoding of `{stream}` in the path, the log response format, the EventSource event format, and whether the operation is sealed (§5.2.2) or is a raw MLSMessage, which exposes the constant `group_id` to the sequencer. §5.2.6 sends pin updates as type `Chat`, while §14.4.3 requires the sequenced operation to be a `JmapSet`.
- Suggested fix: Give CDDL for submit, stamp and log bodies; specify base64url-nopad for `{stream}`; require the op to be a sealed envelope (§5.2.2 construction); and make pin updates `JmapSet` patches on `Chat.pinnedMessageIds`.
- Needs decision: no.

### IMP-18: MLS group configuration is unspecified
- Severity: P2
- Location: spec/05-messaging.md:46-55, :214, :303; spec/02-identity.md:44
- Evidence: "Ephemeral events ... are MLS application messages sent as `PrivateMessage`"; "keyAgreement key: X25519 key used as the source for MLS `KeyPackage` init keys"
- Problem: Not stated: the wire-format policy for handshake messages (PublicMessage vs PrivateMessage Commits; openmls rejects mismatches by default), `group_id` generation, required extensions/capabilities in KeyPackages and the GroupContext (`ratchet_tree`, `last_resort`, `required_capabilities`), the KeyPackage `lifetime` range, the padding policy and the out-of-order tolerance window. §2.1 also says DID `keyAgreement` keys are the source of init keys, which conflicts with single-use, fresh-per-KeyPackage init keys.
- Suggested fix: Add an "MLS profile" subsection fixing these values. Remove the claim that init keys derive from the DID keyAgreement key.
- Needs decision: no.

### IMP-19: The Space endpoint has no error or offline behaviour, and Welcome validation depends on it
- Severity: P2
- Location: spec/03-spaces.md:154-186; spec/04-access-control.md:78; spec/05-messaging.md:131
- Evidence: "If no channel in the client's copy of Space state declares that group ID, the client MUST fetch the current Space state (§3.4) before deciding"; "Clients ... MUST fetch it when they see an `accessKeyAnnouncement` whose `channelToken` they cannot derive"
- Problem: Undefined: status codes, retry and backoff, how long a Welcome may be held pending state, and what happens when every Space endpoint is unreachable (reject the Welcome? hold it? KeyPackage already consumed?). Broadcast posting stalls with no rule. How an invitee "presents" a SpaceInvite or link token (header? body?) is also missing.
- Suggested fix: Define a retry schedule and a hold limit (for example, hold an unvalidated Welcome for up to 7 days, then delete it). Define invite presentation (an `Authorization: AgoraInvite <base64url envelope>` header) and status codes 401/403/404/410.
- Needs decision: no.

### IMP-20: Device registration and revocation have no HTTP binding
- Severity: P2
- Location: spec/02-identity.md:320-336, :387-421, :379
- Evidence: "The client sends a signed registration request to the DID Provisioning Service"; "Gossips a `DeviceRevocation` control message on `v1/agora/discovery`"; "gossips the updated DID document hash"
- Problem: There is no endpoint URL or discovery (DID service type?), method, response (new log entry? error codes for limit exceeded, inactive account or bad token?), or encoding of `idpToken` (a SAML assertion base64url'd?). `DeviceRevocation` and the "DID document hash" gossip have no schema. First-device enrollment has no proof of key possession (sig absent), so the request can bind a key the requester does not hold.
- Suggested fix: Define an `AgoraProvisioning` service entry, `POST {endpoint}/devices` and `POST {endpoint}/revocations` with response and error tables, schemas for `DeviceRevocation` and `DIDUpdateNotice`, and require a self-signature by the new device key even on first enrollment.
- Needs decision: no.

### IMP-21: Social recovery share format is undefined across clients
- Severity: P2
- Location: spec/02-identity.md:171, :188
- Evidence: "splits it into `N` shares using Shamir's Secret Sharing (SSS), and encrypts each share individually to a guardian's X25519 key agreement key"; "`\"encryptedShare\": \"base64url...\"`"
- Problem: The guardian's client is usually a different implementation from the owner's. Undefined: the SSS field (GF(2^8)? which polynomial?), the share encoding (index byte plus value?), the encryption scheme (HPKE suite, `info`, which guardian device key) and the "transmits it to the recovering user" channel. The listed reference libraries use incompatible share formats.
- Suggested fix: Fix GF(2^8) with the AES polynomial, share = `x(1 byte) || y(32 bytes)`, and encryption = HPKE base mode with the §6.12.4 suite and `info="agora/v1/recovery-share" || ownerDID`. Define a `RecoveryShareRelease` MLS DM payload for returning shares.
- Needs decision: no.

### IMP-22: Field encodings in JSON bodies are not normative
- Severity: P2
- Location: spec/02-identity.md:327-328; spec/10-relays.md:620; spec/05-messaging.md:185, :189; spec/03-spaces.md:67, :175; throughout
- Evidence: "`\"deviceEd25519PublicKey\": \"base64url(Ed25519 pubkey)\"`"; "`\"accessPublicKey\": \"z6Mk...\"`" (multibase); "`\"mlsGroupID\": \"base64url...\"`"; "`\"ts\": \"2026-03-12T12:00:00.000Z\"`" vs "`\"2026-03-12T00:00:00Z\"`"
- Problem: Keys appear as base64url in some places and multibase in others. Padding is never specified, timestamp precision and format (RFC 3339 profile) are not fixed, CIDs in JSON have no text base, and integer ranges (`epoch`, `keyEpoch`, `seq`) are not bounded. Exact-string comparisons (`channelCID` match, `spaceCID` match) will fail across implementations.
- Suggested fix: Add a §13.3 "Common encodings": base64url without padding (RFC 4648 §5) for all binary, RFC 3339 UTC `Z` timestamps, CID text = base32 lower, public keys as raw 32-byte base64url (or multibase everywhere, but one choice), integers 0..2^53-1 in JSON.
- Needs decision: no.

### IMP-23: Relay blob upload and pin instructions have no format or authorization
- Severity: P2
- Location: spec/11-transport.md:271, :279; spec/05-messaging.md:368-376; spec/10-relays.md:534-537
- Evidence: "`POST {base}/upload/{accountId}` Blob upload"; "a client ... sends the relay a pin instruction for the CID ... carried with an epoch access proof"
- Problem: Undefined: how an upload proves membership (which token or epoch key signs it, and over what bytes); how a relay attributes an upload or pin to a `RelayServiceAgreement` quota without client identity (via the registered chain?); the pin/unpin instruction message; its response; and the quota-exceeded error. Blob upload via JMAP is listed, but live-stream-only clients have no upload path.
- Suggested fix: Define `PinInstruction {cid, channelToken, epoch, op: pin|unpin, accessSig}` and an upload header carrying `channelToken`, `epoch` and `accessSig` over the blob's CID. State that quota is charged to the agreement under which the chain for that `channelToken` is registered.
- Needs decision: no.

### IMP-24: JMAP Envelope object does not match the routing envelope
- Severity: P2
- Location: spec/11-transport.md:327-339, :279, :343
- Evidence: "`encryptedPayload String base64url: MLS ciphertext`"; "`seqNo UInt Sequence number within the epoch`"; "envelopes written through the sync API carry the same epoch access proof"
- Problem: The Envelope object drops `accessSig`, `accessKeyAnnouncement`, `broadcastPayload` and `expiryHint`, so a history-sync client cannot follow the token chain or verify anything. It calls the payload "MLS ciphertext" rather than the sealed envelope. `seqNo` is relay-assigned, yet it is described as the sender's order, which a relay cannot know. No `Envelope/set` exists for the writes the text says are allowed.
- Suggested fix: Make the Envelope object carry the encoded RoutingEnvelope verbatim (`envelope: base64url`) plus relay metadata (`receivedAt`, `expiresAt`). Drop `seqNo` or define it as relay arrival order. Either define `Envelope/set` or remove the write claim.
- Needs decision: no.

### IMP-25: Push registration endpoint at the relay is ambiguous
- Severity: P2
- Location: spec/11-transport.md:184, :194-203, :407; spec/13-encoding.md:183
- Evidence: proxy: "`POST /v1/agora/push/register`"; relay: "`POST /v1/agora/push/register`"; table: "Push notification registration | ✗ (JMAP) | ✓ (Live Stream)"
- Problem: The same path is given for the proxy and the relay. The relay's base URL is not in the manifest's `endpoints`, and the scope table says registration happens over the live stream. Also undefined: the format of the `DELETE` for relay registrations, the TTL field on relay registrations, and how "including the old `pushHandle`" is expressed.
- Suggested fix: Put relay push registration in a live-stream Control message (IMP-1) or under `endpoints.push`, with a CDDL body including `replaces`.
- Needs decision: no.

### IMP-26: PoW input and placement are ambiguous
- Severity: P2
- Location: spec/10-relays.md:673-683; spec/11-transport.md:125
- Evidence: "computes a nonce such that `SHA256(envelopeBytes || nonce)` has at least `difficulty` leading zero bits, then includes the nonce in the outer `RoutingEnvelope`"
- Problem: `envelopeBytes` would have to include the nonce it is searching for, and with no defined serialization (IMP-2) relay and sender hash different bytes. Nonce length, whether `accessSig` covers `powProof`, and the order of computation (PoW before or after `accessSig`) are all unstated.
- Suggested fix: Define PoW input = `"agora/pow/v1" || sealedEnvelope-or-broadcastPayload bytes || channelToken || epoch(u64be)`, nonce = 8 to 32 bytes, computed before `accessSig`, which covers `powProof`.
- Needs decision: no.

### IMP-27: RFC 9421 profile and manifest signer are under-specified
- Severity: P2
- Location: spec/10-relays.md:102, :116, :167-183
- Evidence: "The manifest is signed per §13.1.1 by the Relay operator's key"; "the manifest ... is signed by the key declared in the DID document" (relayDID); "Required signature components ... `x-agora-timestamp` ... `x-agora-nonce`"
- Problem: It is unclear whether the manifest signer is `operatorDID` or `relayDID`; peers will verify against different DIDs. The 9421 profile omits the signature label, the `keyid` value form (DID URL? key `id` from the manifest?), the `alg` parameter, whether the standard `created` and `nonce` parameters are used instead of custom headers, and the Content-Digest algorithm (sha-256 per RFC 9530).
- Suggested fix: Make `relayDID` the signer. Specify label `sig1`, `keyid` = the manifest key `id`, `alg="ed25519"`, `created` and `nonce` signature parameters (dropping the `x-agora-*` headers), and `content-digest` with sha-256.
- Needs decision: no.

### IMP-28: Required test vectors do not exist and several constructions have none planned
- Severity: P2
- Location: spec/13-encoding.md:148-150; spec/05-messaging.md:133, :194, :202, :218; spec/03-spaces.md:190; spec/04-access-control.md:125
- Evidence: "A JWS signing test-vector set MUST be published ... Implementations MUST pass all test vectors"; "Open (agora-pozi.20.16): The JWS test-vector set does not exist yet"
- Problem: The only mandated set is missing. There are no vectors at all for the constructions where byte divergence is silent: exporter-derived `channelToken`, access key, sealed envelope AAD and nonce layout, broadcast token HKDF, the group-encrypted blob, CID computation, `accessSig` input, the social-recovery seed, and SFrame labels.
- Suggested fix: Extend the §13.1.1 requirement into a §13.4 test-vector set covering each derivation above, generated from an MLS test-vector epoch (RFC 9420 test vectors) and cross-checked by two implementations.
- Needs decision: no.

### IMP-29: No list of spec-defined type URIs, DID service types or exporter labels
- Severity: P2
- Location: spec/05-messaging.md:283-301; spec/06-calls.md:422; spec/07-compliance.md:227; spec/13-encoding.md:164; spec/02-identity.md:96; spec/03-spaces.md:182
- Evidence: "an MLS application message of type `ComplianceDisclosureNotice`"; "whose `type` is `urn:agora:type:` followed by the object name" (CallRing, CallResponse, CallEnd, CallSchedule, LobbyDecision, CallPolicy, CallBreakout, absent from the §5.2.3 table); "No registry is needed"
- Problem: Extension types need no registry, but the spec's own reserved values are scattered and inconsistent. `ComplianceDisclosureNotice` and `DMGroupDescriptor` have no URN, the call types and `SystemEvent.event` values are not listed, and DID service types vary (`KeyPackageEndpoint`/`AgoraKeyPackageEndpoint`, `AgoraProfile`, `AgoraSpaceEndpoint`, ...). Exporter labels use mixed styles and appear in several sections. Implementers will miss types and mis-name services.
- Suggested fix: Add appendix tables listing every `urn:agora:type:*` (with defining section, content type and in-MLS/out-of-MLS signing rule), every DID service `type`, every MLS exporter label and HKDF `info` string, and every manifest capability.
- Needs decision: no.

### IMP-30: DM-specific gaps: relay hints, consent signal, descriptor bootstrap
- Severity: P2
- Location: spec/04-access-control.md:151, :159; spec/02-identity.md:37, :302
- Evidence: "the sending client SHOULD use the Relays known to be serving the recipient's DID (discoverable from the recipient's DID document relay hints)"; "The DID document MUST NOT name an infrastructure operator (relay or other IO)"; "a configurable consent threshold of existing members issues a matching Commit or explicit approval signal"
- Problem: The DM relay discovery path relies on DID relay hints, which §2 forbids, so a new DM has no defined way to pick a relay the invitee also watches. Relay registration for DM chains (which billing DID, given that DMs have no CO) is also undefined. The "explicit approval signal" and the `consentModel` values have no schema, and an MLS Add proposal cannot wait for votes without a defined proposal-retention rule.
- Suggested fix: State how DM relays are chosen (the creator's relays, communicated in the DMGroupDescriptor inside the group, and the Welcome being delivered via the KeyPackageEndpoint already) and who registers the DM chain. Define `urn:agora:type:AddApproval {proposalRef}` and the `consentModel` enum.
- Needs decision: yes. (a) The DM creator's own CO (or personal registration service) registers the chain; (b) DMs use relays that do not require registration. Recommend (a) for consistency with S7.

### IMP-31: `seq` semantics differ between devices and are unbounded
- Severity: P3
- Location: spec/05-messaging.md:13, :226; spec/13-encoding.md:83
- Evidence: "`seq` (monotonically increasing integer per sender per channel)"
- Problem: Several points are unstated. Is "sender" the DID or the leaf? Two devices of one DID would collide. The start value, whether `seq` resets per epoch, behaviour on device restore from backup, and how gap detection interacts with ephemeral messages (do they consume `seq`?) are all missing. §14.3.3 cites `causalRefs`, which is defined nowhere.
- Suggested fix: Define `seq` per leaf (per device), starting at 0 for each new leaf, not reset by epoch, consumed by non-ephemeral messages only. Define or delete `causalRefs`.
- Needs decision: no.

### IMP-32: Minor contradictions that will cause small divergences
- Severity: P3
- Location: spec/06-calls.md:28-29 vs spec/05-messaging.md:228; spec/02-identity.md:35 vs spec/10-relays.md:465; spec/11-transport.md:85-88 vs :21; spec/02-identity.md:215, :231
- Evidence: ParticipantState carries `"sender"` and `"channel"` while "Objects carried inside MLS have no ... sender field"; Pkarr `_profile` is "`cid=<profile CID>`" vs "`ipfs://` URI"; ClientHello `supportedTransportVersions` while "the URL path version is fixed at connection time"; backup "`backupPayload` is a CBOR-encoded structure" with no schema, salt length or nonce layout
- Problem: Each of these is small, but implementers will differ on them: trusting the `sender` field, the Pkarr value form, and backup portability between clients.
- Suggested fix: Drop `sender`/`channel` from ParticipantState. Pick `cid=` with a bare CID. Remove `supportedTransportVersions`, or define what it negotiates. Give the backup CDDL with a 16-byte salt and a 12-byte nonce prefix.
- Needs decision: no.

## CDDL candidates (highest ambiguity removed first)
1. Client-relay frame and all Control messages (IMP-1).
2. RoutingEnvelope including `accessKeyAnnouncement`, `billingSig`, `powProof`, `pushUrgency`, `broadcastPayload`, with the signed-bytes definition (IMP-2, IMP-3, IMP-26).
3. AccessChainRegistration, RelayServiceAgreement exchange, registration-service request/response (IMP-3).
4. SpaceState and ChannelEntry, complete (IMP-15).
5. KeyPackage Store API bodies and Welcome delivery (IMP-8).
6. Sequencer submit, SequenceStamp, log entries, SequencedOp, the `after` head (IMP-17).
7. SFU signaling messages (IMP-12).
8. PinInstruction and blob-upload proof (IMP-23).
9. BroadcastKey, SpaceStateHead, DMGroupDescriptor and the call coordination bodies (IMP-4, IMP-29).
10. Device registration/revocation and recovery share structures (IMP-20, IMP-21).

Areas with no real implementability gap found: §13.1/§13.1.1 JWS procedure itself (precise apart from missing vectors), §6.9/§6.13 SFrame derivation (precise given RFC 9605 §5.2), §6.14 call coordination ordering rule (precise once envelope `id` is fixed), §11.6 admission challenge, §10.2.4-10.2.6 trust levels and heartbeat timers.

Coverage: read fully spec/01-overview.md, 02-identity.md, 03-spaces.md, 04-access-control.md, 05-messaging.md, 06-calls.md, 07-compliance.md, 08-cross-space.md, 09-interop.md, 10-relays.md, 11-transport.md, 12-security.md, 13-encoding.md, 14-jmap.md, 99-appendices.md; grep-checked ARCHITECTURE.md for registration-service/KeyPackage/credential details (none add wire formats). Did not review profiles/, guides/, import/.
