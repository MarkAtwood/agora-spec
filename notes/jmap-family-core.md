# JMAP family (core slice) vs Agora

Status: research note, 2026-10-16. Sources: `~/PROJECT/jmap-chat-spec/draft-atwood-jmap-{chat,chat-did,did,cid,chat-federation,chat-push,chat-wss}-00.md`, `jmap-unified-client-architecture.md`, Agora `ARCHITECTURE.md`, `spec/03`, `spec/11`, `spec/13`. The drafts use kramdown anchors and have no section numbers, so citations here are `{{anchor}}` or heading names.

## 1. Per draft

**jmap-chat-00** (`urn:ietf:params:jmap:chat`). Client-to-server chat API. It has 21 types. The top-level ones with methods are ChatContact, Chat (direct/group/channel), Message, Space, SpaceInvite, SpaceBan, CustomEmoji, ReadPosition and PresenceStatus. Embedded types: Attachment, Endpoint, MessageAction, Mention, BroadcastMention, MessageRevision, Reaction, ChatMember, SpaceRole, SpaceMember, Category, ChannelPermission. Every top-level type has standard `/get /set /changes`, most also have `/query /queryChanges`. The custom methods are `Chat/typing` (ephemeral) and `Space/join`. `Space/set` deliberately uses semantic keys (`addMembers`, `addRoles`, `addChannels`…) instead of PatchObject, because each one is a permission-checked transaction ({{space-set}}). Push goes over EventSource (MUST) plus `typing` and `presence` events with no state token ({{push}}). Blobs use RFC 8620 upload with `sha256` from jmap-cid ({{blobs}}). It assumes a lot of the server:
- assigns IDs. Chat IDs are ULIDs from the creating server; Message IDs are ULIDs assigned by the *receiving* mailbox ({{chat-id}}, {{message-ids}}).
- sets `receivedAt`, which is authoritative for ordering.
- computes `unreadCount`, `replyCount` and `deliveryState`.
- enforces all Space RBAC server-side; "Clients MUST NOT be trusted" ({{authorization}}, {{space-permissions}}).
- does the atomic `SpaceInvite.uses` vs `maxUses` check, `slowModeSeconds` rate limiting, the `mention_broadcast` gate and blocked-contact drops.

Authentication is "a stable opaque user identity string" from the transport. Authorization is owner-or-401: one mailbox serves exactly one user.

**jmap-chat-federation-00** (no new URN; adds `role: "owner"|"peer"` to the chat account capability). Mailbox-to-mailbox protocol. Required methods: `Peer/deliver` (message, edit, reactionUpdate), `Peer/receipt`, `Peer/typing`, `Peer/retract`, `Peer/groupUpdate`. Optional: `Peer/subscribePresence`, `Peer/unsubscribePresence`, `Peer/presence`. Discovery is `/.well-known/jmap` plus `ownerUserId`. Peer authentication is deployment-defined (mTLS, OAuth, overlay). The receiver checks `senderUserId` against the authenticated peer, and checks membership, SpaceBan, `send` permission and slow mode ({{new-message-validation}} steps 1–14). Attachments are pulled from a sender `fetchUrl`. Ordering: "no vector clock, causal ordering, or consensus… last-write-wins on each server" (Message Ordering). Spaces are not federated: "enforced by the Space-hosting server at delivery time" (Space-Level Federation).

**jmap-chat-push-00** (`urn:ietf:params:jmap:chat:push`). Adds `PushSubscription.chatPush` → `ChatPushConfig`, delivering a `ChatMessagePush` that carries `senderId`, `senderDisplayName`, `chatName`, `spaceName`, `hasMention`, `mentionScopes`, `bodySnippet` and the post-delivery `Message` state. Under E2EE it sets `encrypted: true` and omits the snippet, but all the metadata is still sent ({{e2ee}}). The server generates the payload from stored data.

**jmap-chat-wss-00** (`urn:ietf:params:jmap:chat:websocket`). RFC 8887 plus `ChatStreamEnable/Disable`, `ChatTypingEvent` and `ChatPresenceEvent`. Rate limits are 3 s for typing and 30 s for presence. The server applies `receiveTypingIndicators`, block and membership checks at delivery time. It defines no new methods.

**jmap-chat-did-00** (`urn:ietf:params:jmap:chat:did`). Account capability `supportedDidMethods`. Mandatory-to-implement methods are **did:web, did:key, did:plc** ({{methods}}). `ChatContact.id` MAY be a DID. There is an optional `ChatContact.did` for the pseudonymous case, "to keep MLS group membership stable across DID rotations". Federation auth is a DID-bound signature, RECOMMENDED as RFC 9421 with Ed25519. Cache refresh is required after a verification failure.

**jmap-did-00** (`urn:ietf:params:jmap:did`). Generic, for any JMAP type. Session `supportedMethods` and `verificationEndpoint`; account `did`, `didDocumentUri`, `previousDid`. "The server is authoritative for the mapping between an accountId and a DID" ({{binding}}). Binding can come from an OIDC claim, an employer sidecar, self-registration, or a *server-generated* `did:key`. Consuming specs mark "DID-bearing" properties, which are server-set and *derived*: after rotation every historical object reports the new DID ({{did-property}}, {{rotation}}). Client verification is OPTIONAL ({{verification}}).

**jmap-cid-00** (`urn:ietf:params:jmap:cid`). Adds `sha256` (lowercase hex of the full raw blob) to the upload response and to `FileNode.sha256`. Servers that transform bytes MUST NOT advertise it. It provides integrity, not authenticity. It warns about blob probing and upload-timing side channels under cross-account dedup ({{blob-probing}}).

## 2. Common shape

- Pure RFC 8620: `Foo/get /set /changes /query /queryChanges`, per-type opaque `state`, `accountId` scoping, creation IDs, ResultReferences (RefPlus recommended), SetError types (`forbidden`, `overQuota`, plus new `rateLimited` and `notPermitted`).
- Two push lanes: durable state through StateChange → `/changes`, and ephemeral events (typing, presence, VTC, Scene) as fire-and-forget frames ({{push}} "Why Ephemeral Events Are Not State Changes"; client guide §3.2).
- Horizontal capabilities: did and cid extend any type, and companion specs register permission names, Endpoint `type` URNs and `ChatStreamEnable.dataTypes`.
- Identity is an opaque transport-supplied string that MAY be a DID. DID verification is optional and layered on top. Server-asserted identity is the baseline.
- Content addressing is plain SHA-256 hex. No CIDs, no multihash.
- Federation is mailbox-per-user, point-to-point, with each server LWW. A "relay topology" is also permitted in which "the relay implements Peer/*".
- Client model: "Server Wins… no client-side conflict resolution" (client guide §1.4, §5.4).
- No JSON-LD. `@type` appears only on control frames (`StateChange`, `ChatMessagePush`, `ChatTypingEvent`), never on data objects.

## 3. Authority model

Every draft puts the authoritative copy in **a JMAP server**, and that server orders writes by assigning IDs and `receivedAt`.
- Mailbox topology: one server per user, authoritative for that user's view. Different users' copies can diverge in order (federation, Message Ordering).
- Spaces: one Space-hosting server, authoritative and enforcing (federation, Space-Level Federation), so effectively a hub per Space.
- DID binding: the server (jmap-did {{binding}}).

Agora splits authority by kind of state:
- Group membership and epoch order come from the MLS commit sequence.
- Community state is a CO-signed hash chain (`prevStateCID`, spec/03) that clients verify, not one that a server asserts.
- Relays assign `receivedAt` but are not authoritative for anything (S2, S4).
- Message authorship comes from MLS sender authentication, not from a server claim.

## 4. Overlap and conflict

**chat-00 vs Agora messaging.** The vocabulary overlaps heavily: Space, channel, role, permission override, invite, ban, reaction, edit, retract, expiry, burn-on-read, typing, presence, receipts. Agora §11.8.9 already adopts chat-00 as the client/CO management API. Conflicts:
- **E2EE relay section.** {{e2ee}} accepts that the relay sees "sender id, recipient id" and lists that as a leak. Under Agora that is an S1 violation, not a leak to tolerate.
- **Server-side enforcement.** Slow mode, broadcast-mention gate, `SpaceInvite.maxUses` atomicity, `Space/join` and SpaceBan checks all assume a trusted enforcing server. In Agora these become client-enforced (as timeouts are, ARCH §6.2 and §9) or CO-component-enforced. They are never relay-enforced.
- **Receiver-assigned Message IDs.** These are fine locally but useless as cross-member references. Agora needs a sender-global ID; `senderMsgId` already exists for this.
- **Name collision.** Agora's relay type `Message` under `urn:agora:v1` (§11.8.4) collides by name with chat `Message`. JMAP's `using` scoping disambiguates, but the IANA Data Types registry is global and a daemon serving both is confusing. Rename the relay type (e.g. `Envelope`).

**federation vs Agora relays.** Peer/* receivers must know `senderUserId`, `chatId` and membership, and must decide ban, permission and rate. By the ARCH §2.3 key test that makes a federation peer a **CO component**. A per-user mailbox that is the user's own daemon passes. chat-00's "relay implements Peer/*" topology would violate S1 (sender and membership knowledge), S2 (bans, slow mode, permissions enforced at infrastructure), S3 if plaintext, and §5 budget item 2. The same disposition applies as ARCH §7 items 1, 4 and 9. Peer authentication by DID/RFC 9421 between servers is acceptable CO-to-CO only and forbidden toward IOs (§7 item 9). Space-Level Federation (the hosting server enforces at delivery) clashes with Agora's member-verified, CO-signed state, although hosting by the CO itself is permitted.

**jmap-did / chat-did vs Agora DIDs.**
- Method sets differ. chat-did mandates web+key+plc. Agora has webvh (default), plc and key, and Agora clients MUST NOT accept a key from a `did:web` document unless it is in the verified webvh log (spec/02). An Agora profile needs to add `webvh` to `supportedDidMethods`, which the open method set allows, and to constrain `web`. A flat chat-did "MUST resolve did:web" is acceptable only if web keys are never trusted on their own.
- jmap-did's server-authoritative binding and server-generated `did:key` (server holds the user's private key) make that server a CO component holding user signing keys. That fits the employer case and is unacceptable elsewhere.
- jmap-did "rotation" means *the DID changes*, and historical objects are retroactively relabeled. Agora DIDs stay stable across key rotation (webvh log, plc ops), and MLS-authenticated history must not be relabeled. The two lifecycle models conflict; Agora should derive `senderDid` from the MLS credential at receipt and store it.
- chat-did's `ChatContact.did` rationale (stable MLS membership across DID rotation) suggests the drafts anticipated MLS.

**jmap-cid vs Agora CIDs.** jmap-cid is the SHA-256 hex of plaintext bytes. Agora uses CIDv1 multihash (dag-cbor for structured data), and IO-stored blobs are group-encrypted and addressed by the CID of the *ciphertext* (spec/03). The plaintext `sha256` is safe inside MLS (`Attachment.sha256`) but MUST NOT reach an IO: it enables confirmation-of-file attacks, which jmap-cid {{blob-probing}} itself warns about. A raw-codec sha2-256 CIDv1 converts losslessly to and from jmap-cid hex. Chunked IPFS (UnixFS) CIDs do not. *Unverified:* I did not check which codec or chunking Agora mandates for blobs.

**chat-push vs Agora push proxy.** `ChatMessagePush` carries sender, chat and Space names and mention flags. From an IO push proxy that violates S1 and S6. ARCH Q4 says wake-ups carry no content. Agora can use chat-push only as an *on-device* format: the client decrypts after a contentless wake and renders locally, or the CO's own push service sends it. Even from a CO, native APNs/FCM payloads are visible to Apple and Google unless encrypted (RFC 8291 covers Web Push only). The `state` field assumes a single per-account server.

**chat-wss vs Agora transport.** RFC 8887 is client-to-own-server. Agora's live stream is its own CBOR framing to relays (§11.4). The drafts have no direct conflict. chat-wss fits the daemon-to-local-UI link or the client-to-CO link. Its typing and presence frames correspond to Agora MLS application messages (ARCH §7 item 5).

## 5. Mapping options

**(a) Replicated local JMAP stores; operations travel as MLS application messages.** Each member's daemon is the "mailbox" from chat-00: one user, owner-or-401, served on localhost or to the user's own devices. The federation Peer/* payloads (`deliver` message/edit/reactionUpdate, `retract`, `receipt`, `typing`, `presence`) are already the right inter-member vocabulary, carried inside MLS instead of HTTPS. `Peer/groupUpdate` is replaced by MLS commits plus CO-signed state.
- *What survives:* everything the owner API offers, since `state`, `/changes` and `/query` are local by nature.
- *Ordering:* per-store `receivedAt`, exactly as federation specifies. MLS epochs add a partial order. Most objects are single-writer: messages are edited and retracted only by their sender, and reactions are keyed by `senderReactionId`. So LWW is safe. Space mutations follow the CO-signed linear chain.
- *What breaks:* atomic invite counters, slow mode as a hard guarantee, and server-trusted broadcast-mention checks. Each receiving client must check against signed Space state, which inverts federation's "receiver MUST NOT re-check" (Broadcast Mention Resolution).
- *Separation:* fully compliant, because relays carry only envelopes.
- *Limit:* multi-writer shared objects (FileNode trees, shared calendars, tasks) need CRDTs or a sequencer.

**(b) CO-run JMAP server holding plaintext.** All JMAP semantics survive: server-assigned IDs, a total write order, atomic operations, and real enforcement. It complies with S8 as a CO component, but it is not end-to-end among members, since the CO reads everything. A stronger variant makes the server an MLS **member and sequencer**, like the compliance logger: it receives members' operations, applies them, and re-broadcasts CO-signed canonical state (S4) as application messages. This fits regulated organizations and is the only practical path for shared-mutable JMAP types without inventing CRDTs. It MUST NOT run on a relay.

**(c) RFC 8887 frames tunneled in Agora envelopes** (a two-member group of device plus CO server or home daemon). This is just a transport for (b) or for remote access to one's own daemon: everything survives, with added latency, and relays see the request/response timing and volume (within budget). A two-party token is linkable as a pair. Its value is NAT traversal and hiding the client's IP from the CO; otherwise direct TLS to the CO is simpler.

**Recommendation:** use (a) for chat-shaped, sender-owned data in E2EE communities. Use the (b) sequencer-member variant for shared-mutable data and compliance-heavy COs. Use (c) only as an access path.

## 6. JSON vs JSON-LD

Retrofitting contexts onto JMAP types is possible but costly:
- per-capability `@vocab`, e.g. `urn:ietf:params:jmap:chat#`;
- type-scoped contexts for overloaded terms (`id`, `name`, `members`, `position`);
- `@container: @index` for Id-keyed maps (`reactions`);
- `@type: @json` for open `metadata` objects and the rich `body`.

PatchObject keys (`"reactions/<id>"`) and the `Space/set` semantic keys cannot be modeled at all. More seriously, Agora's pipeline **drops unknown terms on expansion** (§13.1.1 step 1). Any JMAP extension property missing from the context would be silently unsigned while still displayed. Contexts would also have to track each IETF draft revision, and running URDNA2015 on every chat message is expensive.

**Recommendation:** carry JMAP payloads as typed plain JSON. Use a small Agora JSON-LD wrapper `{ "@type": "JmapObject" | "JmapOp", "capability": "<urn>", "dataType": "Message", "payload": <@json literal> }`. JSON-LD 1.1 JSON literals are canonicalized with JCS (RFC 8785) inside URDNA2015, so Agora keeps one signing pipeline and the inner object travels byte-for-byte unmodified. Inside MLS, framing already authenticates the sender, so per-object signatures are needed only for objects that leave MLS (archives, CO endpoints, forwarding). Mint JSON-LD contexts only for Agora-native types that need RDF linking (Space state, DIDs, CIDs). *Uncertain:* I have not verified that rdf-canonize and `ssi` handle `rdf:JSON` literals; test before committing.

## 7. Incidental finding

`spec/11-transport.md` §11.7 cites "ARCHITECTURE §5 item 6" for push-proxy observations and "item 7" for the relayDID relationship. In ARCHITECTURE §5, item 6 is the billing DID, item 7 is push handles and item 8 is peering. Both citations are off by one.
