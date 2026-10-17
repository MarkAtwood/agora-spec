# 14. JMAP-Family Data on Agora

> Binds: both. New in this revision.

## 14.1 Overview

*Binds: both.*

Agora carries objects of the JMAP specification family (the RFC 8620 data model and the drafts profiled in §14.6) as payloads of MLS application messages, each in a typed payload envelope (§13.1) whose `type` is the JMAP data type URI (for example `urn:ietf:params:jmap:chat#Message`) and whose `body` is the object's JSON bytes. A chat message on Agora is a `Message` of the JMAP Chat specification (draft-atwood-jmap-chat-00).

No JMAP server runs on any IO. The JMAP drafts assume a server that holds plaintext, assigns identifiers, orders writes and enforces permissions. On Agora those functions are split among:

- **per-member stores** (§14.3): each member's client, or a personal daemon serving that member's own devices, is the JMAP server for its user agent;
- **CO-signed Space state** (§3.3) for community structure, roles and bindings (ARCHITECTURE S4);
- **CO components** (ARCHITECTURE S8) where one plaintext decider is needed, such as a lobby bot, a calendar scheduling service or a scene referee;
- a **blind sequencer** (§14.4) for data types that need a single order, which orders ciphertext and reads nothing.

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

**Switching.** A model change for a type takes effect in each MLS group at the first epoch that begins after the Space state carrying the change is in force; the CO or any member SHOULD issue a Commit promptly to start that epoch. Members first settle the type's state under the old model as of the end of the previous epoch: under `sequenced-v1` this is the state at the closing head of the previous epoch's stream (§14.4.4); under `single-author` it is the state after all operations sent in earlier epochs, which converges as late operations arrive. That state is the starting state under the new model. Operations are always processed under the model that was in force for the epoch in which they were sent. Prior history is unchanged and is not replayed. An operation sent under the old model in an epoch where the new model is in force MUST be ignored.

**Unsupported model.** A client that does not implement the model a Space selects for a type MUST treat that type as read-only in that Space: it MAY display objects it holds, and MUST NOT send operations on that type.

### 14.2.3 Classification

The default model of each type in the family, and the types that are not written under any model because they are derived from other Agora state:

| Data type(s) | Default model | Author or source | Reason |
|---|---|---|---|
| chat `Message` (incl. `Attachment`, `Mention`, `MessageAction`, `MessageRevision`) | `single-author` | sender | Only the sender creates, edits or retracts a message. |
| chat `Reaction` (entry of `Message.reactions`) | `single-author` | reacting member | Keyed by the reactor's `senderReactionId`; no two members write the same entry. |
| chat `ReadPosition`, `ChatContact` | `single-author` | the user | Private to the user; synchronized only among the user's own devices. |
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

`update` maps a global object id to an RFC 8620 PatchObject; `destroy` lists global object ids. `at` is the sender's clock and is used only as the first last-writer-wins key (§14.3.3). For a `sequenced-v1` type the body also carries `after`, the head of the latest stamp the client has applied for the channel, as a JSON object `{ "stream": <base64url channelToken>, "n": <position>, "hash": <base64url stamp hash> }`, or `null` if the client has applied no stamp for the channel (§14.4.3).

Chat `Message` and `Reaction` are written only in object form (§5.2.3). A receiving store MUST ignore a `JmapSet` whose `dataType` is `urn:ietf:params:jmap:chat#Message` or `urn:ietf:params:jmap:chat#Reaction`.

**Global object ids.** Objects are referenced across members by a sender-assigned ULID: `senderMsgId` for a chat `Message`, `senderReactionId` for a `Reaction`, and the creator-assigned `id` for every other type. A store MUST index objects by global id and SHOULD use it as the local `id` where the type's specification allows. A `Chat` is the channel or DM group whose MLS group carried the message (§5.2.2) and has no sender-assigned id; a patch names it with the `update` key `chat`.

**Sender identity.** A store sets every author or sender property (for example `Message.senderId`) from the DID of the MLS credential that sent the message (§5.2.1) and stores it. It MUST NOT take sender identity from the `body`.

### 14.3.3 Validation and Ordering

A store MUST ignore an object or patch whose MLS sender is not the author that §14.2.3 names for the object or for the patched property. A patch MUST touch only paths that sender owns (for example, a participant patches only its own `participants` entry, a reactor only its own `reactions` entry). Checks that the drafts assign to a server (slow mode, the broadcast-mention gate, bans, channel permissions) are evaluated by each receiving store against CO-signed Space state, or by a CO component where one decision is required (§14.6.1).

Delivery order follows §5.1.1 (`seq`, gap buffering). For each property of an object, the store keeps the value from the update with the highest (`at`, routing envelope `id`) pair, comparing `at` as a timestamp and the envelope `id` (§5.2.2) as bytes. Since only the author writes a property, the pair matters only for concurrent writes by the author's own devices, and the result is the same in every store.

### 14.3.4 History Catch-Up

A store that was offline, or a newly added device, obtains missed operations by walking the channel history (§5.2.5) and decrypting the epochs it holds keys for, then applying them in the order above. Objects written in epochs before a member joined are not readable by that member. An author or a CO component MAY re-send current objects in object form so that later joiners hold them.

**Blobs.** A blob referenced by a durable object (an `Attachment`, a `FileNode`, a `SceneAsset`) that later joiners must read is encrypted under a random content key carried in that object, so it stays readable after epoch changes; other blobs use the group-encrypted blob format (§3.4). In both cases an IO holds and addresses only ciphertext by its CID.

## 14.4 Blind Sequencer (`sequenced-v1`)

*Binds: both.*

### 14.4.1 Role and Designation

A sequencer assigns a single order to encrypted operations on `sequenced-v1` types. It holds no MLS group secrets, no exporter outputs other than routing tokens, and no plaintext (ARCHITECTURE S3), is not an MLS member, and reads no operation. Members trust it for availability only: it can delay or drop operations, and it cannot alter, forge or read them.

The CO designates the sequencer in Space state with the optional field `sequencer`:

```json
"sequencer": {
  "did": "did:webvh:QmSCID...:seq.example.com",
  "endpoint": "https://seq.example.com/v1/agora/seq"
}
```

The designation is community state (ARCHITECTURE S4). Any party the CO chooses MAY operate the sequencer, including the CO beside its registration service (§5.2.2). If `sequencer` is absent, `sequenced-v1` types in the Space are read-only.

### 14.4.2 Streams and Stamps

A **stream** is one channel's sequenced operations in one MLS epoch, named by that epoch's `channelToken` (§5.2.2). Stream positions start at 0. The total order of a channel's sequenced operations is by epoch, then position.

A stamp is a typed payload envelope with `type` `urn:agora:type:SequenceStamp`, signed per §13.1.1 by the sequencer DID, whose `body` is:

```json
{
  "stream": "base64url channelToken",
  "n": 41,
  "opHash": "base64url SHA-256 of the operation bytes",
  "prev": "base64url SHA-256 of the previous stamp body, or null at n = 0",
  "ts": "2026-10-16T12:00:00.000Z"
}
```

The hash of a stamp is SHA-256 over its `body` bytes. `prev` chains stamps, so a stream's head (`stream`, `n`, stamp hash) commits to every earlier stamp in the stream.

### 14.4.3 Submission and Distribution

1. The client encrypts the operation as an MLS application message to the channel group in the current epoch. Its envelope has `type` `urn:agora:type:JmapSet`, and its body carries `after` (§14.3.2): the head (`stream`, `n`, stamp hash) of the latest stamp the client has applied for the channel. The resulting MLS message bytes are the **operation**.
2. The client sends `POST {endpoint}/submit` with a CBOR map `{ "stream": <channelToken bytes>, "op": <operation bytes> }`.
3. The sequencer assigns the next position in that stream, signs the stamp, appends (stamp, operation) to the stream's log and returns the encoded stamp envelope.
4. The client publishes to the channel an MLS application message with `type` `urn:agora:type:SequencedOp`, `contentType` `application/cbor`, and a `body` that is a CBOR map `{ "stamp": <encoded stamp envelope>, "op": <operation bytes> }`. This copy enters channel history (§5.2.5), so the order survives replacement of the sequencer.

The sequencer serves its log at `GET {endpoint}/log/{stream}?after={n}`, returning (stamp, operation) pairs in order, and MAY offer an EventSource stream of new entries. Clients fill gaps from the log or from history. If a submitter fails to publish step 4, any member holding the pair MAY publish it; copies are deduplicated by `opHash`.

The sequencer does not authenticate submitters. It MUST rate-limit submissions per network address and per stream, and MAY require proof of work (§10.5.2). An operation from a non-member fails decryption at every member and is skipped (§14.4.4).

### 14.4.4 Client Validation

For each stream, a client processes stamps in position order and MUST, for each:

1. verify the stamp per §13.1.1 against the DID that signed position 0 of the stream, which MUST be the `sequencer` DID in the Space state the client holds or in an earlier Space state; stamps in the stream by any other DID are ignored;
2. check that `n` is the next position, `prev` is the hash of the previous stamp, and `opHash` matches the operation bytes;
3. decrypt the operation as an MLS message of the epoch whose `channelToken` equals `stream`; if decryption or MLS authentication fails, or the epoch differs, skip the position;
4. run the type's validation (for `FileNode`: the parent exists, the sibling name is unique, a move creates no cycle, and the sender holds the needed permission under Space state) against the state produced by all earlier positions, and apply the operation if it passes or reject it if it fails.

Every member holding the same stamps reaches the same result. Rejection is silent to the group; the submitter learns of it when it applies its own operation and MAY resubmit a revised one.

**Closing an epoch.** The `after` member of the operation at position 0 of a new epoch's stream names the closing head of the previous epoch's stream. Positions after the closing head in that previous stream are rejected by every member. Before submitting in a new epoch, a client MUST fetch the previous stream to its end from the log, so that its `after` is current.

**Offline sequencer.** If the sequencer is unreachable, clients queue operations as plaintext and encrypt them in the then-current epoch when submitting. Sequenced types remain readable at their last applied state.

**State strings.** A store's JMAP `state` for a `sequenced-v1` type MAY encode the last applied head; it remains local (§14.3.1).

### 14.4.5 Sequencer Misbehavior

- **Dropping.** A submission that gets no stamp is retried, then queued. A member whose operations repeatedly do not appear in the log SHOULD report it to the CO.
- **Reordering.** Ordering submissions is the sequencer's function. It cannot reorder after stamping without breaking the `prev` chain. Delaying selected submissions is an availability failure that members can observe only by timing; this is an accepted trust in the operator.
- **Equivocation.** Two validly signed stamps with the same `stream` and `n` and different bodies are proof of a fork. Clients detect forks by comparing heads: every operation carries its sender's `after` head in a group message, and a client whose own stamp at that position has a different hash has found a fork. A client that detects one MUST stop applying that stream after the fork point and SHOULD send to the group an MLS application message of `type` `urn:agora:type:SequencerFork` whose `body` is a CBOR map `{ "a": <stamp envelope>, "b": <stamp envelope> }`.
- **Replacement.** The CO replaces a faulty sequencer by a Space state change. The replacement serves streams of epochs that begin afterwards; the closing rule above selects one branch of a forked stream, and operations on the other branch are rejected and may be resubmitted.

### 14.4.6 What the Sequencer Learns

The sequencer learns the streams it orders (`channelToken`s), operation sizes, timing and submitters' network addresses, which is what a relay learns (ARCHITECTURE §5 items 1 and 2). It learns no member identity, membership or content. Because it is named in the Space state of the Spaces that designate it, its operator can associate its streams with those Spaces. A CO that must hide that association from the operator runs the sequencer itself, or designates one sequencer for all its Spaces so that the set of Spaces it cannot tell apart is all of them.

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

Overridden: permission checks are made by every member against Space state. `maxSpaceStorageBytes` is accounted by clients; an IO enforces only quotas under its `RelayServiceAgreement` (§10.5.1). Thumbnails are generated by the uploading client.

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
- **Sequencer.** A sequencer can deny service and choose order, and cannot read, alter or forge operations. Equivocation is detectable and provable (§14.4.5). The sequencer accepts unauthenticated submissions, so its rate limits are its only defense against flooding.
- **Plaintext hashes.** A plaintext `sha256` leaking to an IO enables confirmation-of-file attacks (§14.6.4).
- **Push.** Rich push payloads leak sender, chat and Space metadata to the push proxy and to the platform push service; they are confined to the device (§14.6.6).
- **Referee and bots.** A referee principal, lobby bot or calendar component holds plaintext and is a CO component (ARCHITECTURE S8). Members see it as an MLS member of the group.
