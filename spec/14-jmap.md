# 14. JMAP-Family Data on Agora

> Binds: both. New in this revision.

## 14.1 Overview

*Binds: both.*

Agora carries objects of the JMAP specification family (the RFC 8620 data model and the drafts profiled in §14.6) as payloads of MLS application messages, each in a typed payload envelope (§13.1) whose `type` is the JMAP data type URI (for example `urn:ietf:params:jmap:chat#Message`) and whose `body` is the object's JSON bytes. A chat message on Agora is a `Message` of the JMAP Chat specification (draft-atwood-jmap-chat-00).

No JMAP server runs on any IO. The JMAP drafts assume a server that holds plaintext, assigns identifiers, orders writes and enforces permissions. On Agora those functions are split among:

- **per-member stores** (§14.3): each member's client, or a personal daemon serving that member's own devices, is the JMAP server for its user agent;
- **CO-signed Space state** (§3.3) for community structure, roles and bindings (ARCHITECTURE S4);
- **CO components** (ARCHITECTURE S8) where one plaintext decider is needed, such as a lobby bot, a calendar scheduling service or a scene referee;
- a **blind sequencer** (§14.4) for data types that need a single order, and for choosing among concurrent Commits (§5.1.1), which orders ciphertext and reads nothing.

The relay sync API (§11.8.1 to §11.8.8) moves only ciphertext envelopes and blobs. It is not a JMAP-family server and serves none of the types in this section.

## 14.2 Consistency Models

*Binds: both.*

### 14.2.1 Model Identifiers

Every JMAP data type carried on Agora is written under exactly one **consistency model** at a time. A consistency model defines who may write an object, how concurrent writes are ordered, and how conflicts are rejected. Models are named so that new algorithms can be adopted without revising this specification.

A model identifier is one of:

- a **bare name** (lowercase letters, digits and `-`, no `:`), reserved for models defined by this specification or a revision of it. This revision defines `single-author` (§14.3) and `sequenced-v1` (§14.4). A future revision may define further bare names, for example a `crdt-tree-move-2021` model based on the replicated tree move operation of Kleppmann et al. (2021);
- an **absolute URI** under the control of whoever defines the model, as for extension types (§13.2).

Identifiers are compared as exact, case-sensitive strings. A model is never redefined under an existing identifier; an incompatible change defines a new identifier.

### 14.2.2 Per-Space Selection

Each data type has a default model (§14.2.3). A Space MAY select another model for a type with the optional Space state field `consistencyModels`, a map from data type URI to model identifier:

```json
"consistencyModels": {
  "urn:ietf:params:jmap:tasks#Task": "sequenced-v1"
}
```

A type absent from the map uses its default. A CO changes a type's model by a Space state change (§3.3).

**Switching.** A model change for a type takes effect in each MLS group at the first epoch that begins after the Space state carrying the change is in force; the CO or any member SHOULD issue a Commit promptly to start that epoch. Members first settle the type's state under the old model as of the end of the previous epoch: under `sequenced-v1` this is the state immediately before the first applied operation of the new epoch in the channel's stream (§14.4.2); under `single-author` it is the state after all operations sent in earlier epochs, which converges as late operations arrive. That state is the starting state under the new model. Operations are always processed under the model that was in force for the epoch in which they were sent. Prior history is unchanged and is not replayed. An operation sent under the old model in an epoch where the new model is in force MUST be ignored.

**Unsupported model.** A client that does not implement the model a Space selects for a type MUST treat that type as read-only in that Space: it MAY display objects it holds, and MUST NOT send operations on that type.

### 14.2.3 Classification

The default model of each type in the family, and the types that are not written under any model because they are derived from other Agora state:

| Data type(s) | Default model | Author or source | Reason |
|---|---|---|---|
| chat `Message` (incl. `Attachment`, `Mention`, `MessageAction`, `MessageRevision`) | `single-author` | sender | Only the sender creates, edits or retracts a message. |
| chat `Reaction` (entry of `Message.reactions`) | `single-author` | reacting member | Keyed by the reactor's `senderReactionId`; no two members write the same entry. |
| chat `ReadPosition`, `ChatContact` | `single-author` | the user | Private to the user; synchronized only among the user's own devices, through the user's self-group (§2.6). |
| chat `ChatPresenceEvent`, `ChatTypingEvent` | ephemeral (§5.3) | sender | Not stored; carried as ephemeral MLS application messages. |
| chat `Space`, `SpaceRole`, `SpaceMember`, `SpaceBan`, `Category`, `ChannelPermission`, `CustomEmoji`, `SpaceInvite`, `Chat` membership | derived | CO-signed Space state (§3.3), MLS group membership | Community state is CO-signed (ARCHITECTURE S4). Members never replicate these as JMAP writes. |
| chat `Chat.pinnedMessageIds` | `sequenced-v1` | holders of the `pin` permission (§5.2.6) | Several members write one list. |
| `CalendarEvent` | `single-author` | event creator; each participant for its own `participants` entry | Low contention; an RSVP is a per-participant entry written only by that participant. Per-property last-writer-wins (§14.3.3). |
| `Task` | `single-author` | task creator; each assignee for its own progress | Last-writer-wins suffices when only the creator reassigns. A Space that lets any member edit or reassign selects `sequenced-v1`. |
| `Calendar`, `TaskList` binding (`Space.calendarId`, `Space.taskListId`) | derived | CO-signed Space state | A binding is community structure. |
| `FileNode` | `sequenced-v1` | any member permitted by Space state | Sibling-name uniqueness and cycle-free moves are not safe under concurrent last-writer-wins. |
| `SceneRegion` (structure) | `single-author` | region creator | Created and edited by one member, usually an admin. |
| `SceneRegion.worldState` | `single-author` | the region's referee principal | Shared simulation state has one authority (§14.6.11). |
| `SceneObject` | `single-author` | object owner | The scene draft permits only the owner to edit an object. |
| `SceneAsset` | `single-author` | uploader | Immutable once created; content is a blob. |
| `SceneAvatar` | `single-author` | the avatar's user | Slow presence record; poses use the real-time path (§14.5). |
| `VTCCall`, `VTCParticipant`, `VTCRecording`, `VTCLivestream` | not carried | §6 | Call state is §6 `ParticipantState` and group messages (§14.6.13). |

A type defined later states its default model where it is profiled. A type with no stated default is `single-author`.

## 14.3 Replicated Per-Member Stores (`single-author`)

*Binds: clients.*

### 14.3.1 The Store as JMAP Server

Each member's client, or a personal daemon run by or for that member, holds a JMAP store and serves the JMAP Chat specification and its companions to that member's user agent, as the "mailbox" of draft-atwood-jmap-chat-00 with exactly one user. It serves only the member's own devices (localhost or an authenticated link the member controls, §11.8.9) and MUST NOT be exposed as a service to other users. The store's contents are what the member's devices have decrypted from MLS application messages plus derived Space state.

Within the store, every RFC 8620 mechanism works locally: `state` strings, `/changes`, `/query`, `/queryChanges` and push to the user agent. State strings are local counters over the store's own change log and have no meaning in any other member's store; they MUST NOT be sent in Agora payloads.

### 14.3.2 Wire Forms

A write by the author travels as an MLS application message to the channel group, in one of two forms:

- **Object.** `type` is the JMAP data type URI and `body` is the object as defined by its specification, containing only properties the client may set. Properties the drafts mark server-set (`id` for chat `Message`, `receivedAt`, `deliveryState`, counts) are omitted by the sender and ignored if present; each receiving store computes them.
- **Patch.** `type` is `urn:agora:type:JmapSet` and `body` is a JSON object:

```json
{
  "dataType": "urn:ietf:params:jmap:tasks#Task",
  "at": "2026-10-16T12:00:00.000Z",
  "update": { "01JABCDEF...": { "progress": "completed" } },
  "destroy": []
}
```

`update` maps a global object id to an RFC 8620 PatchObject; `destroy` lists global object ids. `at` is the sender's clock (§12.9) and is used only as the first last-writer-wins key (§14.3.3). For a `sequenced-v1` type the body also carries `after`, the head of the latest stamp the client has applied for the channel, as a JSON object `{ "stream": <base64url channelToken>, "n": <position>, "hash": <base64url stamp hash> }` with base64url values unpadded, or `null` if the client has applied no stamp for the channel (§14.4.3).

Chat `Message` and `Reaction` are written only in object form (§5.2.3). A receiving store MUST ignore a `JmapSet` whose `dataType` is `urn:ietf:params:jmap:chat#Message` or `urn:ietf:params:jmap:chat#Reaction`.

**Global object ids.** Objects are referenced across members by a sender-assigned ULID: `senderMsgId` for a chat `Message`, `senderReactionId` for a `Reaction`, and the creator-assigned `id` for every other type. A store MUST index objects by global id and SHOULD use it as the local `id` where the type's specification allows. A `Chat` is the channel or DM group whose MLS group carried the message (§5.2.2) and has no sender-assigned id; a patch names it with the `update` key `chat`.

**Sender identity.** A store sets every author or sender property (for example `Message.senderId`) from the DID of the MLS credential that sent the message (§5.2.1) and stores it. It MUST NOT take sender identity from the `body`.

### 14.3.3 Validation and Ordering

A store MUST ignore an object or patch whose MLS sender is not the author that §14.2.3 names for the object or for the patched property. A patch MUST touch only paths that sender owns (for example, a participant patches only its own `participants` entry, a reactor only its own `reactions` entry). Checks that the drafts assign to a server (slow mode, the broadcast-mention gate, bans, channel permissions) are evaluated by each receiving store against CO-signed Space state, or by a CO component where one decision is required (§14.6.1).

Delivery order follows §5.1.1 (`seq`, gap buffering). For each property of an object, the store keeps the value from the update with the highest (`at`, routing envelope `id`) pair, comparing `at` as a timestamp and the envelope `id` (§5.2.2) as bytes. Since only the author writes a property, the pair matters only for concurrent writes by the author's own devices, and the result is the same in every store.

### 14.3.4 History Catch-Up

A store that was offline obtains missed operations from channel history (§5.2.5): the recent envelopes that Relays hold for each of the channel's `channelToken`s (§10.4.6), and older operations from other members' stores or the CO archive. It decrypts the epochs it holds keys for and applies the operations in the order above. A newly added device of an existing member can receive earlier history from the member's other devices by the optional history transfer of the self-group (§2.6). Members detect omitted operations by the per-sender `seq` (§5.1.1). Objects written in epochs before a member joined are not readable by that member. An author or a CO component MAY re-send current objects in object form so that later joiners hold them.

**Blobs.** Every file referenced by a durable object (an `Attachment`, a `FileNode`, a `SceneAsset`) is stored as a **chunked content-key blob**, encrypted under a key carried in that object, so that it stays readable after epoch changes and by any member who later receives the object. The plaintext file is split into chunks, each chunk is encrypted separately, and the encrypted chunks form a standard IPFS DAG:

```
n          = max(1, ceil(len(file) / 262144))           ; chunk count
chunk[i]   = file[i * 262144 .. min((i + 1) * 262144, len(file)))
nonce[i]   = i as a 96-bit big-endian unsigned integer
aad[i]     = "agora/chunk/v1" || uint64(i) || uint64(n) || uint8(i == n - 1 ? 1 : 0)
block[i]   = AES-128-GCM-Seal(contentKey, nonce[i], chunk[i], aad[i])
```

- `contentKey` is 16 bytes from a cryptographically secure random number generator, generated by the uploader for this file only. A `contentKey` seals exactly one plaintext. A client MUST NOT seal two different chunk plaintexts under the same `contentKey` and chunk index; any change of content, including a new revision of the same `FileNode`, uses a fresh `contentKey`. A client that re-encrypts after an interruption uses a fresh key or encrypts from a snapshot it has checked to be unchanged. Because a key seals exactly one plaintext, the nonce can be the chunk index. The object carries the key in its `contentKey` member, an Agora extension property whose value is the key as unpadded base64url (RFC 4648 §5). An `Attachment` that has a `thumbnailBlobId` carries the thumbnail's key, generated the same way, in the extension property `thumbnailContentKey`. The object travels only inside MLS ciphertext or a broadcast payload (§5.2.1.4), so no IO sees a key.
- Chunks are 262,144 bytes (256 KiB), except the last, which holds the remaining 1 to 262,144 bytes. An empty file is one empty chunk. A file MUST NOT exceed 2^32 bytes, so `n` is at most 16,384 (Appendix C). The integers in `aad[i]` are big-endian; the final byte is 1 for the last chunk and 0 otherwise. Binding the index, the count and the final flag makes a reordered, dropped, duplicated or truncated chunk fail to open. AES-128-GCM is the AEAD of the default ciphersuite (§5.2.1); the 16-byte tag follows the ciphertext (RFC 5116).
- Each `block[i]` is a block with its own CID, a CIDv1 with codec `raw` and a SHA2-256 multihash (§13.1).
- When `n` is 1, the blob identifier is the CID of `block[0]`. When `n` is greater than 1, the uploader also builds a **root block**: a `dag-pb` node (codec 0x70) whose `Links` name `block[0]` to `block[n-1]` in order, each with an empty `Name` and `Tsize` equal to the block's length, and whose `Data` is a UnixFS `File` node with `blocksizes` equal to the same lengths and `filesize` equal to their sum. The root block is encoded exactly as the IPLD dag-pb specification and the UnixFS v1 specification define: each `PBLink` carries `Hash` (the chunk CID in binary form), `Name` present with zero length, and `Tsize`; the `Links` are encoded before `Data`; `Data` is the protobuf UnixFS message with `Type` = `File` (2), `filesize`, and one non-packed `blocksizes` entry per chunk (UnixFS uses proto2 encoding), and no other fields. The root CID is a CIDv1 `dag-pb` `sha2-256` CID (§13.1). The blob identifier is the CID of the root block. The DAG is a valid UnixFS file whose content is the concatenated ciphertext, so standard IPFS tools and CAR files (CARv1) can store and move it without any key. The root block reveals only the chunk count and the ciphertext length, which an IO holding the blocks sees anyway.
- The object names the blob identifier in `blobId` (and `thumbnailBlobId` for an `Attachment`'s thumbnail), and gives `n` in the extension property `chunkCount` (`thumbnailChunkCount` for the thumbnail). Where the object has `size` and `sha256` members, they are the octet length and SHA-256 of the whole plaintext file (§14.6.4).

The uploader uploads the root block and every chunk block (§10.4.4). There is no convergent encryption: identical files uploaded by different members, or twice by one member, encrypt to different blocks, so no IO can test whether a file it holds matches a guess.

A receiver fetches the root block and the chunk blocks by CID from any source (§10.4.4) and MUST check each block against its CID before using it. It MUST reject a root block whose link count differs from `chunkCount` or whose links are not `raw` CIDs, and MUST reject the file if any chunk fails to open with `aad[i]` computed from `chunkCount`. Because each chunk is named and opened on its own, a receiver MAY fetch chunks in parallel from several Relays, resume an interrupted transfer from the first missing chunk, and fetch only the chunks covering a byte range; a chunk that opens is authentic, since only holders of `contentKey` can seal it under that key. When it holds the whole file, the receiver MUST discard it if the SHA-256 of the plaintext does not equal the object's `sha256`. Records that the CO stores on IO infrastructure use the group-encrypted blob format instead (§3.4). In both cases an IO holds and addresses only ciphertext by its CID.

## 14.4 Blind Sequencer (`sequenced-v1`)

*Binds: both.*

### 14.4.1 Role and Designation

A sequencer assigns a single order to encrypted operations on `sequenced-v1` types, and to concurrent Commits in the channels of the Spaces that designate it (§5.1.1). It is an IO. It holds no MLS group secrets, no exporter outputs, no admission private keys and no plaintext (ARCHITECTURE S3), is not an MLS member, and reads no operation. Members trust it for availability only: it can delay or drop operations, and it cannot alter, forge or read them.

The CO engages a sequencer under a `ServiceAgreement` with `serviceType` `sequencer` (§10.5.1), and registers the admission key of every channel of the designating Spaces with it as with any Relay (§10.5.3). A CO SHOULD designate as its sequencer a Relay with which it already holds an agreement, and SHOULD use one sequencer for all its Spaces (§14.4.6).

The CO designates the sequencer in Space state with the optional field `sequencer`:

```json
"sequencer": {
  "did": "did:web:relay.example.com",
  "endpoint": "https://relay.example.com/v1/agora/seq"
}
```

The designation is community state (ARCHITECTURE S4). `did` is the sequencer's DID, which signs stamps; for a Relay it is the manifest's `relayDID` (§10.2.1). If `sequencer` is absent, `sequenced-v1` types in the Space are read-only, and concurrent Commits are resolved without a sequencer (§5.1.1). DM groups have no Space and no sequencer, so `sequenced-v1` types, including `Chat.pinnedMessageIds` (§5.2.6), are read-only in every DM group; `single-author` data such as `ReadPosition` is unaffected.

### 14.4.2 Streams and Stamps

A **stream** is a sequence of stamped operations named by a 32-byte value. A channel has two streams per `channelToken` (§5.2.2):

- its **operation stream**, named by the `channelToken` itself, which orders `sequenced-v1` operations;
- its **commit stream**, named `SHA-256("agora/commits/v1" || channelToken)`, which orders Commits (§5.1.1).

A channel's streams change when its admission key rotates and the `channelToken` changes. Stream positions start at 0. The total order of a channel's sequenced operations is by stream, in the order of the channel's tokens, then by position.

Commits are stamped only on the commit stream of the channel's current token. When the sequencer applies an `AdmissionKeyRegistration` whose entry names a token in `replaces` (§10.5.3), it closes that token's commit stream: it stamps no further Commit there and refuses submissions to it with `stream-closed`. The operation stream of the replaced token stays open for the rotation's grace period, under the closing rule of §14.4.4. The stamp at position 0 of the new token's commit stream carries in `prev` the hash of the last stamp of the most recently closed commit stream of the channel that holds stamps by the same sequencer DID, or `null` if no earlier commit stream of the channel holds such stamps, so the first Commit on the new stream references the last earlier stamp. A member MUST treat as a fork (§14.4.5) a stamp by the same DID that follows the referenced stamp on its commit stream or lies on a commit stream closed after that one; if position 0 carries `null`, every stamp by the same DID on an earlier commit stream of the channel is such a fork.

An operation stream spans MLS epochs. A member applies operations in position order and skips an operation encrypted in an MLS epoch lower than that of an operation applied at an earlier position in the same stream. The first applied operation of an epoch therefore marks the epoch boundary in the stream, and every member places it at the same position.

A stamp is a typed payload envelope with `type` `urn:agora:type:SequenceStamp`, signed per §13.1.1 by the sequencer DID, whose `body` is:

```json
{
  "stream": "base64url stream name",
  "n": 41,
  "opHash": "base64url SHA-256 of the operation bytes",
  "prev": "base64url SHA-256 of the previous stamp body; at n = 0, null or the hash of the last earlier stamp on a closed commit stream",
  "ts": "2026-10-16T12:00:00.000Z"
}
```

Binary values are base64url without padding (RFC 4648 §5). The hash of a stamp is SHA-256 over its `body` bytes. `prev` chains stamps, so a stream's head (`stream`, `n`, stamp hash) commits to every earlier stamp in the stream. At `n` = 0, `prev` is `null`, except on a commit stream of a channel whose earlier commit streams hold stamps by the same sequencer DID, where it is the hash of the last such stamp (above).

### 14.4.3 Submission and Distribution

The **operation** is the exact bytes of a `sealedEnvelope` (§5.2.2) for the channel's current `channelToken`, sealing the MLS message. For a `sequenced-v1` write, the MLS message is an application message to the channel group in the current epoch whose payload has `type` `urn:agora:type:JmapSet` and whose body carries `after` (§14.3.2): the head of the latest stamp the client has applied for the channel. For a Commit, the procedure of §5.1.1 applies with the commit stream.

1. The client builds the operation.
2. The client sends `POST {endpoint}/submit` with `Content-Type: application/cbor` and a `Submit` body:

```cddl
Submit = {
  "stream": bstr .size 32,        ; operation or commit stream name, §14.4.2
  "op": bstr,                     ; the operation bytes
  "signed": bstr .cbor seq-auth,
  "admissionSig": bstr .size 64   ; Ed25519 over the exact bytes of "signed"
}

seq-auth = {
  "op": "sequence",
  "channelToken": bstr .size 32,
  "stream": bstr .size 32,        ; equal to Submit "stream"
  "opHash": bstr .size 32,        ; SHA-256 of Submit "op"
  "nonce": bstr .size 16,
  "expires": uint                 ; seconds since the Unix epoch
}
```

   `admissionSig` is made with the channel's admission private key (§5.2.2). The `op` member value `"sequence"` keeps this signature distinct from routing envelope, `PinInstruction` and upload signatures made with the same key (§11.4).
3. The sequencer admits the submission as a Relay admits an envelope (§10.5.4): `channelToken` MUST match a key registered under its agreement and not deregistered, `admissionSig` MUST verify over the exact bytes of `signed`, `stream` MUST be the operation stream or the commit stream of that `channelToken`, and a commit stream MUST NOT be closed (§14.4.2), `opHash` MUST equal SHA-256 of `op`, `expires` MUST NOT have passed or be more than 600 seconds ahead, and `nonce` MUST NOT repeat for that token. It then assigns the next position in the stream, signs the stamp, appends (stamp, operation) to the stream's log, and returns HTTP 200 with the encoded stamp envelope (`Content-Type: application/cbor`). If the stream already holds the same `opHash`, it returns the existing stamp and appends nothing. On failure it returns the status below with a JSON body `{ "error": "<code>" }`, using the codes of §11.4:

| Status | `error` | Condition |
|---|---|---|
| 400 | `bad-message` | Body does not match `Submit`, or `stream` or `opHash` does not match |
| 403 | `unknown-token` | No key registered for `channelToken` |
| 403 | `bad-admission-sig` | `admissionSig` does not verify |
| 403 | `expired` / `replayed` | `expires` or `nonce` check failed |
| 409 | `stream-closed` | `stream` is the commit stream of a token whose key a later registration replaces (§14.4.2) |
| 413 | `too-large` | `op` exceeds 65536 bytes |
| 429 | `rate-limited` | Rate limit exceeded |

4. For an operation stream, the client publishes to the channel an MLS application message with `type` `urn:agora:type:SequencedOp`, `contentType` `application/cbor`, and a `body` that is a CBOR map `{ "stamp": <encoded stamp envelope>, "op": <operation bytes> }`. This copy reaches members and history (§5.2.5) with the channel's other messages, so the order survives replacement of the sequencer. For a commit stream, the client carries the stamp in the Commit's routing envelope instead (§5.1.1); a client refused with `stream-closed` fetches the current `ChannelAdmissionKey` (§5.2.2) and resubmits on the new token's commit stream.

The sequencer serves its log at `GET {endpoint}/log/{stream}?after={n}`, where `{stream}` is the stream name in base64url without padding. The response is `Content-Type: application/cbor` and holds a CBOR array of maps `{ "stamp": <encoded stamp envelope>, "op": <operation bytes> }` for the positions greater than `n` in order (from position 0 if `after` is absent), up to a server-chosen limit; the client repeats the request from the last position received. The log needs no authorization, since it holds only ciphertext, and is rate-limited per network address. The sequencer MAY offer an EventSource stream of new entries at `GET {endpoint}/log/{stream}/events`, each event's data being one such map, base64url-encoded without padding. Clients fill gaps from the log or from history. If a submitter fails to publish step 4, any member holding the pair MAY publish it. For a commit stream, a member publishes an unpublished winning Commit as §5.1.1 describes.

A client deduplicates copies of an operation by `opHash` before decrypting it, because a second MLS decryption of the same message fails once its keys are deleted (RFC 9420 §9.2). A client that has already decrypted an operation reuses that result.

The sequencer MUST also rate-limit submissions per network address and per stream, and MAY require proof of work (§10.5.2).

### 14.4.4 Client Validation

For each operation stream, a client processes stamps in position order and MUST, for each:

1. verify the stamp per §13.1.1 against the DID that signed position 0 of the stream, which MUST be the `sequencer` DID in the Space state the client holds or in an earlier Space state; stamps in the stream by any other DID are ignored;
2. check that `n` is the next position, `prev` is the hash of the previous stamp, and `opHash` matches the operation bytes;
3. skip the position if its `opHash` was already processed; otherwise unseal the operation for the stream's `channelToken` (§5.2.2) and decrypt the MLS message; if unsealing, decryption or MLS authentication fails, skip the position;
4. skip the position if the message's MLS epoch is lower than the epoch of an operation applied at an earlier position in the stream (§14.4.2);
5. run the type's validation (for `FileNode`: the parent exists, the sibling name is unique, a move creates no cycle, and the sender holds the needed permission under Space state) against the state produced by all earlier positions, and apply the operation if it passes or reject it if it fails.

Every member holding the same stamps reaches the same result. Rejection is silent to the group; the submitter learns of it when it applies its own operation and MAY resubmit a revised one.

**Closing a stream.** When a channel's admission key rotates (§5.2.2), its operation stream changes. (Commit streams close at registration instead, §14.4.2, and their Commits are processed by the rules of §5.1.1.) The `after` member of the operation at position 0 of the new stream names the closing head of the previous stream. Positions after the closing head in that previous stream are rejected by every member. Before submitting on a new stream, a client MUST fetch the previous stream to its end from the log, so that its `after` is current. Before submitting a Commit on a new commit stream, it MUST likewise fetch the closed commit stream to its end (or, after a sequencer replacement, its Commits up to the closing head, §14.4.5) and process its Commits (§5.1.1).

**Offline sequencer.** If the sequencer is unreachable, clients queue operations as plaintext and encrypt them in the then-current epoch when submitting. Sequenced types remain readable at their last applied state. Commits in the Space's channels wait for the sequencer (§5.1.1).

**State strings.** A store's JMAP `state` for a `sequenced-v1` type MAY encode the last applied head; it remains local (§14.3.1).

### 14.4.5 Sequencer Misbehavior

- **Dropping.** A submission that gets no stamp is retried, then queued. A member whose operations repeatedly do not appear in the log SHOULD report it to the CO.
- **Reordering.** Ordering submissions is the sequencer's function. It cannot reorder after stamping without breaking the `prev` chain. Delaying selected submissions is an availability failure that members can observe only by timing; this is an accepted trust in the operator.
- **Equivocation.** Two validly signed stamps with the same `stream` and `n` and different bodies are proof of a fork. Clients detect forks by comparing heads: every operation carries its sender's `after` head in a group message, and a client whose own stamp at that position has a different hash has found a fork. A client that detects one MUST stop applying that stream after the fork point and SHOULD send to the group an MLS application message of `type` `urn:agora:type:SequencerFork` whose `body` is a CBOR map `{ "a": <stamp envelope>, "b": <stamp envelope> }`.
- **Replacement.** The CO replaces a faulty sequencer by a Space state change, then rotates the admission keys of the Space's channels (§10.5.3), so that the replacement starts new streams at position 0. The closing rule above selects one branch of a forked operation stream, and operations on the other branch are rejected and may be resubmitted. Before it chooses the heads, the CO deregisters the channels' admission keys at the old sequencer (§10.5.3), or ends its agreement with it, so that it stamps nothing more, and then reads each commit stream to its end. A misbehaving old sequencer that stamps after this does so above the head, and members reject those stamps. Commit streams close by the same rule: the Space state change that names a new `sequencer` DID carries `closingHeads` (§3.3), giving for each channel the closing head (`stream`, `n`, stamp hash) of the old DID's current commit stream, which the CO chooses from the old sequencer's log or from relay history. The CO MUST choose each head so that every winning Commit (§5.1.1) at or below it is available from the old log or from relay history, and on a forked stream it chooses one branch; a Commit that was stamped but never published, and that the old log no longer serves, therefore lies above the head. On that stream members accept a stamp signed by the old DID only at or below the head and only if the head's `prev` chain includes it; every later position, and every stamp on another branch, is rejected (§5.1.1). The new sequencer stamps only commit streams of tokens registered after the change, and members reject a stamp signed by the new DID on a stream named in `closingHeads`. A Space state change that removes `sequencer` also carries `closingHeads`, closing the old DID's streams the same way; the channels then follow the no-sequencer rule of §5.1.1 for later Commits. Position 0 of each new commit stream carries `prev` `null`, and the fork rule of §14.4.2 does not apply across the change. Before its first submission on the new commit stream, a committer processes the old stream's Commits up to the head (§5.1.1). A member missing a position at or below the head fetches it from the old sequencer's log if that is reachable, and otherwise from the channel's relay history, where each Commit carries its stamp in `commitStamp`.

### 14.4.6 What the Sequencer Learns

The sequencer learns what a Relay holding the same registrations learns (ARCHITECTURE §5 items 1 to 3 and 6): the stream names it orders, which are `channelToken`s and values derived from them, the CO's billing DID and which tokens are registered under it, which token each rotated key replaces (§10.5.3), operation sizes, timing, the rhythm of Commits in each channel, and submitters' network addresses. Admission signatures do not identify the submitter. It learns no member identity, membership or content, and it cannot map a token to a Space or channel.

Space state names the sequencer, but a private Space's state is served only to members (§3.4), so the operator cannot read the designation. A public Space's designation is a CO publication, and so are its channels. A CO that uses one sequencer for all its Spaces makes the set of Spaces the sequencer cannot tell apart every Space the CO serves through it, as with Relays (§10.4.2). Every Relay carrying a sequenced channel also reads the sequencer DID in each `commitStamp` (§5.2.2), so a CO that uses different sequencers for different Spaces lets its Relays group its tokens by sequencer, and tie a group to any public Space that names its sequencer.

## 14.5 Real-Time Data

*Binds: clients.*

Updates of a few per second or fewer per sender (placing a scene object, a `SceneAvatar` entering or leaving, call control) are ordinary MLS application messages through relays, ephemeral (§5.2.3) where they need not be kept.

Updates at 10 to 60 Hz (avatar poses, controller and haptic input) travel on a WebRTC data channel on the call path of §6: mesh up to four participants and SFU above (§6.5), with the same signaling (§6.4) and SFU admission (§6.6). Each data channel message is encrypted end to end before it enters the data channel, SFrame-style, with keys derived from the MLS exporter as for media (§6.9), so an SFU forwards it without reading it and is not an MLS member. A scene with live presence is a call that may carry no audio or video. §6 defines the mechanics; this section adds no transport.

## 14.6 The Agora Profile of the JMAP Family

*Binds: both.*

This section states, per draft, what Agora uses, what it overrides and what it forbids. Anything a draft assigns to a server is performed by the member's store (§14.3), by the sequencer (§14.4) or by a CO component, never by an IO (ARCHITECTURE S1, S2).

### 14.6.1 JMAP Chat (draft-atwood-jmap-chat-00)

Used: all data types and methods, served by the member's store (§14.3.1, §11.8.9). Chat messages on Agora are its `Message` objects.

Overridden:
- Server-enforced checks become checks by every receiving store against CO-signed Space state: slow mode, the broadcast-mention gate, channel permissions, blocked contacts and bans. A ban takes effect as an MLS Remove (§4.5).
- `Space/set` and the other Space-family `/set` calls are translated by the store into a signed Space state mutation (§3.3) by an owner or admin, or rejected locally if the user holds no such authority.
- A DM group (§4.6) is a `group` Chat. Its `members` are the DIDs with leaves in the group's current epoch (ARCHITECTURE S9), and every `ChatMember.role` is `member` (§4.6.2). `joinedAt` is the local receipt time of the Commit that added the DID's first current leaf, and `invitedBy` is that Commit's committer. The store translates `addMembers` and `removeMembers` into an MLS Add or Remove Commit (§4.6.1, §4.6), which any member may make, and rejects `updateMemberRoles` locally.
- `SpaceInvite.maxUses` and `Space/join` need one decider: a CO invite service enforces them, since a count cannot be enforced by independent stores. The invite service authenticates members per §3.5.
- `receivedAt` is local receipt time; cross-member references use `senderMsgId` (§14.3.2).

Forbidden: the draft's E2EE relay arrangement, in which a relay learns sender and recipient identifiers, violates ARCHITECTURE S1 and is not used. Relays carry only §5.2.2 envelopes.

### 14.6.2 JMAP Chat DID (draft-atwood-jmap-chat-did-00)

Used: DIDs as `ChatContact.id`, and `supportedDidMethods`.

Overridden: `supportedDidMethods` reports the Space's `acceptedDIDMethods` (§3.3), drawn from §2.1, and includes `did:webvh`. `did:web` is not accepted as a user identity; a parallel `did:web` document is ignored for key material (§2.1). A store sets DID-valued sender properties from the MLS credential (§14.3.2). RFC 9421 DID-bound signatures between servers are used only between COs or personal daemons (§14.6.5).

### 14.6.3 JMAP DID (draft-atwood-jmap-did-00)

Used: the account `did` property, set to the user's Agora DID.

Forbidden:
- Server-generated `did:key` and any binding in which a server holds a user's private signing key. User signing keys exist only on the user's devices (§2.2, §2.5.1).
- DID "rotation" in the draft's sense (a new DID, with historical objects relabeled). Agora DIDs are stable across key rotation (§2.1); stored sender DIDs are never rewritten. `previousDid` is always `null`.

Overridden: DID verification is mandatory, since every MLS credential is verified as a DID (§5.2.1); the draft makes it optional.

### 14.6.4 JMAP Blob Content Identifiers (draft-atwood-jmap-cid-00)

Used: `sha256` of plaintext inside MLS-encrypted objects (`Attachment.sha256`, `FileNode.sha256`), for integrity after decryption.

Overridden: anything an IO stores, serves or sees is addressed by a CID of ciphertext (§3.4, §14.3.4). A plaintext hash MUST NOT appear in any IO-visible field, upload request or blob identifier, since it permits confirmation-of-file attacks (ARCHITECTURE S6). A relay blob store does not advertise `urn:ietf:params:jmap:cid`.

### 14.6.5 JMAP Chat Federation (draft-atwood-jmap-chat-federation-00)

Used: the Peer/* vocabulary as a model for inter-member operations, which on Agora travel as MLS application messages (§14.3.2), not as HTTP calls.

Overridden: `Peer/groupUpdate` is replaced by MLS Commits and CO-signed Space state. Peer/* methods over HTTP are permitted only between COs or personal daemons, for example a CO gateway to a non-Agora JMAP Chat mailbox (§9).

Forbidden: Peer/* methods on a relay or any other IO. A Peer/* receiver learns senders and membership and enforces bans and permissions, which violates ARCHITECTURE S1 and S2. The draft's relay topology is not used.

### 14.6.6 JMAP Chat Push (draft-atwood-jmap-chat-push-00)

Used: `ChatMessagePush` as the on-device model for rendering a notification.

Overridden: push through any proxy is a content-free wake-up (§11.7). After waking, the device fetches and decrypts, then builds the notification locally. A `ChatMessagePush`, including its `encrypted: true` form with sender and chat metadata, MUST NOT leave the device.

### 14.6.7 JMAP Chat over WebSocket (draft-atwood-jmap-chat-wss-00)

Used: between a user agent and its own store, or a CO component.

Forbidden: toward a relay. Relays use the transport of §11. Typing and presence travel as ephemeral MLS application messages (§5.3).

### 14.6.8 JMAP Chat Calendars (draft-atwood-jmap-chat-calendars-00)

Used: `CalendarEvent` and RSVP under `single-author` (§14.2.3); the `calendar-event` and `availability` message actions.

Overridden: `Space.calendarId` is a Space state field. `.ics` parsing, iTIP sending (`sendSchedulingMessages`) and `Principal/getAvailability` need plaintext and are performed by the client or a CO calendar component. `jmap:` URIs naming accounts or objects appear only inside MLS ciphertext.

### 14.6.9 JMAP Chat Tasks (draft-atwood-jmap-chat-tasks-00)

Used: `Task` and the `task` message action, `single-author` by default (§14.2.3).

Overridden: `Space.taskListId` is a Space state field. Clearing `taskListId` or `chatId` when the referent is destroyed is done by each store on applying the destroy.

### 14.6.10 JMAP Chat File Storage (draft-atwood-jmap-chat-filenode-00)

Used: the Space file tree under `sequenced-v1` (§14.4), with the validation of §14.4.4.

Overridden: permission checks are made by every member against Space state. `maxSpaceStorageBytes` is accounted by clients; an IO enforces only quotas under its `ServiceAgreement` (§10.5.1). Thumbnails are generated by the uploading client.

Forbidden: content scanning and `Blob/convert` by an IO, which would require plaintext (ARCHITECTURE S3). A CO component MAY perform them.

### 14.6.11 JMAP for Scenes (draft-atwood-jmap-scene-00)

Used: `SceneRegion`, `SceneObject`, `SceneAvatar` and `SceneAsset` under the models of §14.2.3; slow records as MLS application messages (§14.5); glTF assets as blobs (§14.3.4).

Overridden:
- If a region has simulation authority (physics, interaction validation, game rules, `worldState`), it is a referee principal: a CO component that is an MLS member of the channel group and whose messages are authoritative for that region's simulated state. `simulationUri` and `inputUri` resolve to the call path of §14.5 or to such a component, never to an IO.
- Visibility filtering, blocked-contact filtering and moderation are performed by clients or CO components.
- `assetUri` MUST NOT point at an IO serving plaintext assets.

### 14.6.12 JMAP Scene over WebSocket (draft-atwood-jmap-scene-wss-00)

Used: the event vocabulary (`SceneAvatarEvent`, `SceneObjectEvent`, `SceneInteractionEvent`) as ephemeral MLS application messages, or on the data channel of §14.5 when its rate requires.

Overridden: interaction validation is done by the referee principal if the region has one, otherwise by each receiving client. The draft's rate caps apply per sender.

### 14.6.13 JMAP for Video/Voice Teleconferencing (draft-atwood-jmap-vtc-00)

§6 is the source of truth for calls, media, signaling, SFU, TURN and recording.

Used: the vocabulary of ring (including multi-device ring), scheduled calls, lobby, call policy and breakout rooms, carried as MLS group messages in the voice channel's group. These are enforced by clients, or by a CO bot member where one decider is needed (lobby admission). For a ring answered on several devices, the first answer in group message order wins.

Forbidden: `VTCCall`, `VTCParticipant`, `VTCRecording` and `VTCLivestream` as server-owned objects, and any call server that knows participants (ARCHITECTURE S1). Participation is `ParticipantState` (§6.2). Active-speaker mapping is done by clients; an SFU never maps streams to DIDs (§6.6). Recording is by a CO recorder member (§6.12), so it is compatible with E2EE media. `VTCCallPush` content follows §14.6.6: the wake-up is content-free.

### 14.6.14 JMAP VTC over WebSocket (draft-atwood-jmap-vtc-wss-00)

Used: the event vocabulary as ephemeral MLS application messages; media-state events correspond to `ParticipantState` updates (§6.2).

Forbidden: subscription to call events at any server. Every member of the voice channel's group receives them; the draft's rate caps apply per sender.

## 14.7 Security Considerations

*Binds: both.*

- **Identifiers in JMAP bodies.** JMAP objects carry `spaceId`, `chatId`, `accountId`, `jmap:` URIs and other identifiers that are S1-protected. They MUST appear only inside MLS ciphertext or group-encrypted blobs, never in a routing envelope, push payload, sequencer submission field other than `op`, or blob identifier.
- **Server-trusted fields.** Fields the drafts mark server-set are recomputed by each store. A store that accepted a sender's `senderId`, `receivedAt` or `deliveryState` from a `body` would allow impersonation or misordering.
- **Client-enforced policy.** Slow mode, permissions and broadcast-mention limits are enforced by honest clients only. A modified client can send operations that honest stores ignore but that it displays itself. This is the accepted cost of client enforcement (ARCHITECTURE §9).
- **Last-writer-wins clocks.** `at` is sender-chosen. An author can backdate or postdate only its own objects, since stores ignore patches from non-authors (§14.3.3).
- **Sequencer.** A sequencer can deny service and choose order, and cannot read, alter or forge operations. Equivocation is detectable and provable (§14.4.5). It admits only submissions signed with a registered channel admission key (§14.4.3), so non-members cannot take stream positions; a removed member can submit until the CO rotates the key (§10.5.3), but it can encrypt only in epochs it belonged to, and the epoch rule of §14.4.4 rejects such operations once any later-epoch operation is stamped. Rate limits bound flooding by key holders.
- **Plaintext hashes.** A plaintext `sha256` leaking to an IO enables confirmation-of-file attacks (§14.6.4).
- **Push.** Rich push payloads leak sender, chat and Space metadata to the push proxy and to the platform push service; they are confined to the device (§14.6.6).
- **Referee and bots.** A referee principal, lobby bot or calendar component holds plaintext and is a CO component (ARCHITECTURE S8). Members see it as an MLS member of the group.
