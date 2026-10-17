# JMAP-family payloads over Agora: calendars, tasks, filenode, scene, vtc

Research note, 2026-10-16. Read-only survey of seven drafts in
`~/PROJECT/jmap-chat-spec/` against `ARCHITECTURE.md`, `spec/05`, `spec/06`,
`spec/13`, `attic/futures.md`. Section numbers are computed from heading order
in the kramdown source (no rendered numbering exists); anchors given where
useful.

## 1. Per-draft summary

**chat-calendars-00** (`urn:ietf:params:jmap:chat:calendars`). Binds a Space
to one JMAP Calendars Calendar. Adds `Space.calendarId` (§4.1), refines the
`urn:jmap:chat:cap:calendar-event` and `urn:jmap:chat:cap:availability`
MessageAction types (§5, §8), optional server-side `.ics` parsing (§7). No new
methods; RSVP is upstream `CalendarEvent/set` on `participants` (§6). Durable,
low rate, small objects (JSCalendar events; `.ics` capped at "a few hundred
kilobytes", §7.2). Server assumed to: hold the calendar, evaluate JMAP Calendars
authz on every op (§4.3), parse `.ics` and auto-create tentative events
(§7.1-7.2), answer `Principal/getAvailability` under deployment policy (§8.2).
Upstream calendars-26 also has `sendSchedulingMessages`: the server sends iTIP
on the user's behalf (calendars-26 l.1890).

**chat-tasks-00** (`urn:ietf:params:jmap:chat:tasks`). Adds `Space.taskListId`
(§4.1) and `Task.chatId` back-reference (§5.1), refines
`urn:jmap:chat:cap:task` (§6). No new methods. Durable, low rate, small. Server
assumed to: enforce JMAP Tasks authz (§4.3), clear `taskListId`/`chatId` on
destroy of the referent (§4.1, §5.3), tolerate transient dangling `chatId`
(§7.2). Assignment comes from upstream tasks-06 `assignees` extension (§4.5).

**chat-filenode-00** (`urn:ietf:params:jmap:chat:filenode`). Profiles
FileNode for a Space file tree: role `urn:jmap:chat:filenode:space` plus
immutable `spaceId` on the root (§4.1); flat Space-permission-to-FileNode map
(§5); `Attachment.filenodeId` and `thumbnailBlobId` (§6); destroy-with-Space
plus grace period (§7). Durable; metadata small, blobs large (capped by
`maxSpaceStorageBytes`, §3.2). Server assumed to: derive membership and roles
"from its own authoritative state" on every op (§5, §8.1), enforce quota,
generate thumbnails via `Blob/convert` (§6.2), optionally content-scan at
upload (§8.3). Upstream filenode-14 adds server-enforced sibling-name
uniqueness and `onExists` handling (l.242) and parent-cycle rejection (l.527).

**scene-00** (`urn:ietf:params:jmap:scene`). Spatial *state at rest*:
SceneRegion, SceneObject, SceneAvatar, SceneAsset with get/changes/set/query/
queryChanges plus spatial filters (§5, §6.3.4). Normative coordinate system
(§3). Regions carry opaque `simulationUri`/`inputUri` to a deployment-defined
real-time layer (§5.3.1, §7). Two rates: JMAP records reconciled every 5-30 s
with StateChange coalesced 1-5 s (§7.2, §10.1.1); simulation layer at
10-60 Hz, out of scope. Assets are glTF blobs (mandatory `model/gltf-binary`,
§5.2.1), potentially MB-scale. Server assumed to: own spawn, avatar IDs and
`activeAvatarCount`; enforce `accessPolicy` (§8.1) and owner-only object edits
(§8.2); do position-based visibility filtering (§7.3); filter blocked contacts
(§9.9); content-moderate assets and text (§9.10); reconcile positions from the
simulation layer (§7.2). `worldState` is opaque shared application state.

**scene-wss-00** (`urn:ietf:params:jmap:scene:websocket`). Discrete ephemeral
events over JMAP WebSocket: SceneAvatarEvent, SceneObjectEvent,
SceneInteractionEvent (§4). Rate caps: 2 object updates/object/s, 5
interactions/user/region/s (§6.3). Best-effort ordering (§6.4). Server
validates interactions (avatar present, object interactable) and relays
(§4.3.1), applies visibility and block filters (§6.5, §6.6).

**vtc-00** (`urn:ietf:params:jmap:vtc`). *Call state, not media* (§1.1):
VTCCall (ring/room/scheduled state machines, §4.6.4), VTCParticipant,
VTCRecording, VTCLivestream; gateways for PSTN/SIP/H.323 (§4.1). Ring push via
VTCCallPush with APNs VoIP / FCM high priority, 2 s target (§1.1, §6.1).
Eight ephemeral events (§6.2-6.5). Server assumed to: be the single authority
for call state transitions ("server-enforced", §4.6.4), arbitrate "first device
to answer wins" (§6.6), run ring timeout (§6.7), enforce moderator roles,
lobby and `VTCCallPolicy` (§4.3, §9.6-9.7), record and livestream server-side
(§5.3.3, §4.7), enforce Space bans on active calls (§7.1). `joinUri` points to
an opaque media stack; WebRTC signaling explicitly out of scope (appendix,
Non-Prescriptions).

**vtc-wss-00** (`urn:ietf:params:jmap:vtc:websocket`). Subscription control
(VTCStreamEnable/Disable, §4) for the vtc-00 events. Rate caps: 1 media-state
event/participant/s, 2 active-speaker/call/s (§5.3). Per-delivery authz
against current participation (§9.2).

## 2. Real-time vs durable, and mapping to Agora paths

| Payload | Class | Agora path |
|---|---|---|
| CalendarEvent, Task, TaskList, Calendar, FileNode metadata | durable replicated record | MLS application message in channel envelope, stored in history; or CO-held record with `*Head` CID notification like `SpaceStateHead` (spec/03) |
| `.ics`, files, glTF assets, thumbnails | blob | group-encrypted blob by CID (spec/03 "Group-encrypted blob"), referenced from a `MediaBody`-style payload |
| Space-to-Calendar/TaskList/FileTree binding | community state | field in CO-signed Space state (ARCH S4) |
| SceneRegion, SceneObject (structural) | durable, moderate rate | MLS app messages in history, or snapshot blob + deltas |
| SceneAvatar enter/leave, Scene*Event, VTCParticipantEvent, VTCMediaStateEvent, VTCActiveSpeakerEvent | ephemeral | ephemeral `PrivateMessage` like `TypingEvent`/`ParticipantState` (spec/05 §5.2.3), not stored |
| Avatar pose at 10-60 Hz, `inputUri` HID/haptics | real-time stream | **no current Agora path fits.** Relay envelopes plus per-message MLS and gossip are not built for 60 Hz (futures.md "Performance"). Candidates: WebRTC data channel on the voice/video path (mesh or SFU, SFrame-protected) keyed from the MLS exporter. Uncertain; needs design |
| VTC media | media | spec/06 WebRTC + SFrame path, unchanged |
| VTCCallPush ring | push | IO push proxy wake-up only (ARCH §5 item 7, Q4); content must come from MLS after wake |

Ring latency (vtc §6.1, 2 s) is a real tension: Agora push carries no content
(ARCH Q4), so the device must wake, sync from a relay, decrypt, then show
CallKit. Achievable but unproven; flag for measurement.

## 3. Authority and ordering

Every draft assumes a trusted server that holds plaintext and serializes
writes. With no trusted server, per type:

- **Calendars / tasks.** Mostly per-object, low contention. Per-property
  last-writer-wins keyed on Agora `seq` + `causalRefs` (spec/05 §5.1.1)
  suffices, with RSVP as a per-participant field written only by that
  participant (natural single-writer, no conflict). iTIP sending, `.ics`
  parsing, free/busy and external scheduling need a plaintext actor: a
  CO-run calendar component (allowed; same class as the archive). Task
  assignment: LWW on `assignees` is acceptable; no evidence the drafts need
  stronger.
- **FileNode.** Sibling-name uniqueness and no-cycle constraints (filenode-14)
  are not LWW-safe under concurrency. Options: a tree CRDT (move-op CRDT) with
  deterministic rename-on-collision, or a CO-run file-tree authority that
  sequences ops. Quota (§3.2) becomes per-agreement at the IO (ARCH §6.2) plus
  client-side per-Space accounting; it cannot be server-enforced per Space at
  the IO without learning Space identity.
- **Scene.** Static structure (regions, placed objects): LWW per object.
  Physics, `physicsMode: "dynamic"`, interaction validation (§4.3.1 of
  scene-wss), position-speed validation (§9.4), game rules: need a single
  simulation authority. This is exactly the **referee principal** in
  futures.md: an MLS member (CO-run service, agreed player, or published
  autonomous program) whose messages are authoritative for world state. It is
  a CO component by ARCH §2.3 (holds plaintext). Fork resolution for
  persistent worlds remains open (futures.md "World state authority").
- **VTC.** State machine, first-answer-wins, ring timeout, lobby admission and
  moderator policy all assume one arbiter. In Agora, spec/06 already chose:
  no call object, only per-participant `ParticipantState` with TTL. Ring
  "answered elsewhere" can be a client-sent message; races resolve by lowest
  `(ts, DID)` deterministically. Lobby and `participantsCanUnmute` become
  client-enforced (like timeouts, ARCH §6.2) unless a CO moderator bot is a
  member.

## 4. jmap-vtc vs Agora spec/06

**Overlap.** Participant join/leave and media flags (VTCMediaState ≈
`ParticipantState` audioMuted/videoEnabled/screenSharing/handRaised);
recording consent signal (VTCRecordingStateEvent ≈ RecordingGrant +
§6.12.3 disclosure); room model (vtc `callType: "room"` ≈ spec/06 §6.1
always-open voice channel); E2EE flag (`e2eeEnabled` ≈ `e2eeMedia`).

**Conflicts.**

1. *Server sees participants.* vtc's server knows who is in every call,
   `speakerTimeMs`, `kickedBy`, metadata (§9.4 admits it). In Agora that is
   S1-protected; only members and CO components may know it.
2. *Recording.* vtc §4.6.2/§5.3.3: recording requires "server-side media
   access" and is forbidden with E2EE. spec/06 §6.12: recording works with
   E2EE because the recorder is a CO-run MLS member. Agora's model is strictly
   better and compatible with operator separation. Livestream and gateways
   (PSTN/SIP) are likewise CO components that must be MLS members to
   decrypt; vtc forbids them under E2EE.
3. *Active speaker.* vtc has the server or media layer emit
   VTCActiveSpeakerEvent with participant ids. spec/06 §6.7: SFU sees audio
   levels per SSRC but never maps SSRC to DID. Clients must do the mapping.
4. *Signaling.* vtc leaves SDP/ICE to the media stack; spec/06 §6.4 makes it
   MLS-encrypted `VoiceSignal` with DTLS fingerprint binding. Not a conflict,
   a gap vtc deliberately leaves.
5. *Ring calls, scheduled calls, breakout rooms, lobby, call policy,
   livestream* exist in vtc and not in spec/06.
6. *Ban enforcement.* vtc §7.1 server sets `leftAt` on ban. Agora: ban is an
   MLS Remove; media keys rotate (spec/06 §6.9).

**Recommendation.** spec/06 is source of truth for media, signaling, E2EE,
SFU/TURN and recording. Use vtc as a *vocabulary source* for the features
spec/06 lacks (ring, scheduled, lobby, policy, breakout), re-expressed as
MLS-carried ephemeral or stored messages with client or CO-bot enforcement.
Do not carry VTCCall/VTCParticipant as server-owned objects.

Side finding (pre-existing, out of this slice): spec/05 §5.2.3 table
describes `RecordingGrant` as "authorization for an SFU DID to decrypt
media", contradicting spec/06 §6.6 and §6.12 (SFU MUST NOT decrypt; grantee
is a CO recorder). Erratum candidate.

## 5. Separation risks if carried naively

- `jmap:` URIs embed `accountId` and object ids (calendars §5.1, tasks §6.1);
  `spaceId`/`chatId`/`channelId` on VTCCall, SceneRegion, Task. Harmless
  inside MLS ciphertext; fatal in any outer envelope, push payload, or
  IO-visible field.
- **VTCCallPush** (vtc §6.1) carries `initiatorId`, display name, subject,
  `joinUri`, `spaceId`. Must never go through an IO push proxy in clear (ARCH
  §5 item 7 allows only opaque handles and timing).
- `simulationUri`, `inputUri`, `assetUri`, `joinUri` point at deployment
  servers. A simulation server that receives poses and interactions holds
  plaintext and knows participants: it is a CO component, not IO. If run by
  an IO it violates S3/S8. Same for a CDN `assetUri` serving plaintext assets
  (also a per-user tracking vector, scene §9.2).
- Server-side visibility filtering (scene §7.3), blocked-contact filtering
  (§9.9), content moderation (§9.10), `.ics` parsing and thumbnails
  (filenode §6.2) all need plaintext and identity; CO components or
  clients only.
- FileNode §5 permission enforcement by the server is an IO-incompatible
  pattern (S2); in Agora it is group membership plus client checks.
- Group-encrypted blobs are keyed per epoch (spec/03). Durable shared files
  read by later joiners need key carry-forward or re-encryption; spec does
  not yet say how. Uncertain whether already addressed elsewhere.
- Scene spatial metadata (who is where, when) is S1-class; position
  reconciliation must stay inside MLS or with a CO simulation component.

## 6. JSON vs JSON-LD for these objects

Agora signs JSON-LD via expand → URDNA2015 → SHA-256 → Ed25519
(spec/13 §13.1.1), and expansion **drops unknown terms**. Carrying JMAP
plain JSON under that pipeline unchanged means every property must be mapped
in a context, or it silently vanishes from the signed digest.

Adding `@context` per JMAP type: benefit is uniform signing and IRI-typed
vocabulary (JSCalendar has no published JSON-LD context that I found; this
would be new work). Costs: a context per draft that must track draft
revisions; opaque deployment blobs (`worldState`, `environment`, `gatewayData`,
`data`, `metadata`) need `@type: @json` or they lose content; quaternion and
coordinate arrays need `@list` or order may not be preserved in RDF (JSON-LD
arrays are unordered sets by default); URDNA2015 cost is meaningful for large
scene snapshots and prohibitive at simulation rates.

Alternative: a single Agora JSON-LD wrapper (e.g. `@type: JmapObject`,
`objectType: "urn:ietf:params:jmap:..."`/type name, `body` as `@json`
literal). The wrapper signs via URDNA2015 as today; the body is carried as a
JSON literal, so its canonical form is JCS (RFC 8785) inside the RDF literal.
This keeps JMAP objects byte-identical to their drafts, needs one context
entry instead of dozens, and avoids per-draft context maintenance. Cost:
JMAP properties are not RDF-queryable. Note that inside MLS application
messages the MLS signature already authenticates sender and content; a
second object-level signature is only needed for objects that outlive the
message (archived records, CO-signed state, blobs). Ephemeral and real-time
traffic should not be URDNA2015-signed at all. Recommendation (tentative):
wrapper + `@json` body for JMAP-family objects; full JSON-LD mapping only for
types Agora itself must reason about (Space state bindings, grants).
