# MIMI vs JMAP Chat: overlap, gaps, translation, recommendations

Status: analysis note, 2026-10-17. Non-normative. Nothing here changes the jmap-chat drafts or the Agora spec.

## Bottom line

- MIMI and JMAP Chat mostly sit at different layers. MIMI is provider-to-provider transport, MLS room state and an E2EE content format. JMAP Chat is a client-server API plus an optional mailbox-to-mailbox federation. They compete only in two places: the message body format (`application/mimi-content` vs the JMAP `Message` object) and server-to-server federation (MIMI hub/follower vs `Peer/*`).
- The feature sets overlap for core chat: replies, reactions, edits, deletes, attachments, mentions, receipts, expiry and room metadata. Most features map with some loss. The structural blocker is message identity. MIMI's `MessageId` is a hash over the exact content bytes, salt, sender URI and room URI. JMAP's `senderMsgId` is a sender-chosen ULID. Every edit, reply, reaction and receipt references one of these.
- A CO-side service cannot translate mimi-content to and from JMAP Chat losslessly. It also cannot translate at all without plaintext, because both formats ride inside MLS `PrivateMessage`s authenticated by the author's leaf. A translating service is therefore a gateway: it breaks E2EE and becomes the MLS sender. In Agora, translation belongs in the client.
- Agora: in MIMI-interop channels, make mimi-content (inside the mls-extensions `ApplicationFraming`) the only canonical content. Show it locally as a JMAP `Message` view with `senderMsgId` derived deterministically from the MIMI `MessageId`. Drop or redefine §9.1 "Agora content format mode". Fix §9.1's stale draft versions and its URI shapes. Decide who orders Commits when the MIMI hub and the Agora sequencer coexist.

## Sources and versions

MIMI (current revisions on datatracker as of 2026-10-17; texts saved in the session scratch directory `.../scratchpad/mimi/`, treated as untrusted data):

| Short | Document | Current rev | Notes |
|---|---|---|---|
| ARCH | draft-ietf-mimi-arch | -03 (exp 2027-01-07) | -02 read locally; -02 to -03 diff is reference bumps only |
| PROTO | draft-ietf-mimi-protocol | -06 (exp 2026-10-27) | read locally; current |
| CONTENT | draft-ietf-mimi-content | -09 (exp 2027-01-05) | -08 read locally; -09 change log (App. C.11) is editorial: octet-length clarification for the MessageId URI lengths, `salt_base_secret` naming fix, reference fixes |
| POL | draft-ietf-mimi-room-policy | -04 (exp 2027-01-07) | -03 read locally; -03 to -04 diff: reference bumps, `join_link` changed to `opaque join_link<V>` |
| IDENT | draft-mahy-mimi-identity | -05 (exp 2027-01-07) | fetched; individual draft |
| IDS | draft-kohbrok-mimi-identifiers | -01 | local; current |
| STATUS | draft-mahy-mimi-message-status | -01 | local; current; individual |
| ATT | draft-robert-mimi-attachments | -06 | -05 local; -06 is a version bump |
| MSGID | draft-mahy-mimi-msgid-aad | -02 | local; current; individual |
| EXT | draft-mimi-content-more-extensions | -00 | local; currency not checked |
| AV | draft-mahy-mimi-av-metadata | -01 | local; currency not checked |
| PORT | draft-kohbrok-mimi-portability | -05 | local; currency not checked |

Discovery: the only MIMI discovery document, draft-interop-mimi-discovery-requirements-03, expired 2025-12-23. Section numbers below are from the revisions read. They are unchanged in the newer revisions as far as the diffs show.

JMAP Chat (`~/PROJECT/jmap-chat-spec`): CORE = draft-atwood-jmap-chat-00, FED = draft-atwood-jmap-chat-federation-00, WSS = draft-atwood-jmap-chat-wss-00, PUSH = draft-atwood-jmap-chat-push-00, CDID = draft-atwood-jmap-chat-did-00, JDID = draft-atwood-jmap-did-00, CID = draft-atwood-jmap-cid-00, FILE = draft-atwood-jmap-chat-filenode-00. These drafts use named sections, so they are cited by section title in quotes.

## 1. Scope by layer

| Layer | MIMI | JMAP Chat | Relationship |
|---|---|---|---|
| Client-server API | Out of scope (ARCH §5; PROTO §3, client steps shown only as non-normative) | Core purpose: `Message/*`, `Chat/*`, `Space/*` over JMAP (CORE) | Complementary. CORE "Relationship to MIMI" says it fills this gap |
| Server-server | Hub/follower over mutually authenticated HTTPS: `submitMessage`, `notify`, `update`, `keyMaterial`, `groupInfo`, and others (PROTO §4.1, §5) | Mailbox-per-user `Peer/deliver`, `Peer/receipt`, `Peer/typing`, `Peer/retract`, `Peer/groupUpdate`, plus optional presence (FED) | Competing designs. FED "Relationship to MIMI" says they are not interoperable at this layer and a deployment could run both |
| Message content | `application/mimi-content`, deterministic CBOR (CONTENT §3.1, §4) | JSON `Message` object; `bodyType` can be text/plain, text/markdown, `application/jmap-chat-rich` or (MAY) `application/mimi-content` (CORE capability `supportedBodyTypes`) | Competing; partially bridged by the MAY |
| Room state, policy | MLS GroupContext `app_data_dictionary` components: participant list, roles, base policy, metadata (PROTO §7; POL §3 to §6) | Server-side `Chat`/`Space` objects with JMAP `/set` (CORE "Space", "Updating a Chat") | Different homes for the same concepts |
| Identity, addressing | `mimi://` URIs, called "notional" in PROTO (§1.1, §3 Table 1; IDENT §4 Table 3); identifier taxonomy (IDS §2 to §3) | Opaque `userId` (CORE "ChatContact"); DIDs (CDID; JDID) | Different namespaces. Agora already carries both (§9.1 `AgoraMIMICredential`) |
| E2EE | MLS mandatory; app messages are `PrivateMessage` (PROTO §4.2, §7.4) | Optional deployment mode; body opaque, sensitive outer fields empty (CORE "End-to-End Encrypted Deployments", "Fields Inside the Ciphertext") | mimi-content is designed as an MLS payload; JMAP E2EE has no key fields of its own |
| Push, sync, search | None | `/changes`, `/query`, EventSource, PushSubscription, PUSH, WSS | JMAP only |

## 2. Overlap table

Difficulty legend:
- **L**: lossless.
- **Ly**: lossy.
- **X**: no mapping exists.

Where the two directions differ, the cell gives M->J (MIMI to JMAP) first and J->M (JMAP to MIMI) second.

| Feature | MIMI | JMAP Chat | Difficulty | Notes |
|---|---|---|---|---|
| Message identity | `MessageId` = hashAlg octet followed by the first 31 octets of SHA-256(len‖senderUri‖len‖roomUri‖message‖salt) (CONTENT §3.3). Any member can compute it; there is no separate ID field. Optional `externalMessageId` extension (EXT §4). Optional `message_id` in Safe AAD, visible to providers (MSGID §3) | Receiver-assigned ULID `id` that differs per mailbox; sender-assigned ULID `senderMsgId` used for all federation references (CORE "Message IDs"; FED "Outbound Message Preparation") | M->J Ly, J->M Ly | A 32-octet hash does not fit ULID syntax. A translator needs a durable bidirectional table, or a deterministic derivation (§5a R1). `senderMsgId` can travel as `externalMessageId` with scope = a URI, but that ID is not what MIMI peers use for references |
| Ordering, timestamps | The hub's accepted timestamp is the authority for sorting (CONTENT §3.4, §4.2; PROTO §5.5). The sender may claim a time with `senderTimestamp` (EXT §3). Optional `lastSeen` DAG (EXT §6) | `receivedAt` is per mailbox and authoritative locally; `sentAt` is untrusted. There is no global order; concurrent operations resolve by last-write-wins (FED "Message Ordering"). `lastSeenSenderMsgId` is only a display hint | M->J L, J->M Ly | The hub timestamp maps to `receivedAt`. A MIMI room has one order while JMAP has one order per mailbox, so J->M gains an order and M->J loses only the global guarantee |
| Replies | `inReplyTo` = the MessageId of one specific *version* (CONTENT §4.1, §5.2) | `replyTo` = target message (CORE Message fields) | M->J Ly, J->M L | A reply to version N of an edited message collapses to the message. J->M needs the target's current-version MessageId |
| Threads, topics | `topicId` is opaque bytes; it may be the first message's ID (CONTENT §4.1, §5.11). `subject` extension (EXT §5) | `threadRootId` with `supportsThreads` (CORE "Thread Model"); `Chat.topic` is chat-level | Ly | Slack-style topics (topicId = root MessageId) map to `threadRootId`. Named or opaque topics and per-message `subject` have no JMAP field |
| Reactions | A full message: `inReplyTo` = target, disposition `reaction`, usually an emoji text part. Several per message are allowed via processAll; media reactions are allowed (CONTENT §5.3) | `reactions` map keyed by client ULID `senderReactionId`: `{emoji, customEmojiId?, senderId, sentAt}` (CORE "Reaction"); FED `reactionUpdate` | M->J Ly, J->M Ly | Emoji reactions map if the reaction MessageId and `senderReactionId` are paired in a table. Media reactions have no JMAP form. `customEmojiId` has no MIMI form (send the fallback emoji) |
| Edits | New message, `replaces` = the MessageId of the *first* instance (CONTENT §4.1, §5.5); each version has its own MessageId | `body`, `bodyType`, `mentions` and `broadcastMentions` replaced; `editedAt`; optional `editHistory` (CORE "Editing a Message", "MessageRevision"); FED `edit` | M->J Ly, J->M L | M->J must record the version ID of every edit so later `inReplyTo` references resolve. MIMI edits can change the whole NestedPart (attachments too); JMAP edits cannot change `attachments` |
| Delete, retract | `replaces` = first instance, NullPart body (CONTENT §5.6). Only the sender may delete unless policy allows others (CONTENT §9.3; POL §8.3 `canDeleteOtherMessage`) | `deletedForAll` triggers `Peer/retract` (FED); a local `deletedAt` tombstone; `senderExpiresAt` and `burnOnRead` cause hard deletes (CORE "Deleting a Message") | L | Delete-for-all maps one to one. A JMAP local-only delete has no wire form on either side. Moderator delete: MIMI uses a policy capability; JMAP has no explicit field |
| Unreact | `replaces` = the reaction's MessageId, NullPart, disposition reaction (CONTENT §5.7) | Remove `reactions/<senderReactionId>` (CORE "Adding and Removing Reactions") | L with table | If one MIMI message carried several reactions, an unlike removes all of them |
| Attachments | `ExternalPart` inline: url, key, nonce, encAlg, aad, hashAlg, contentHash, size, expires, description, filename; AES-128-GCM is MTI (CONTENT §4.5). Alternative MLS-exporter-keyed token scheme, not aligned with CONTENT (ATT §3) | `Attachment {blobId, filename, contentType, size, sha256}`; blobs are server-local; FED adds `fetchUrl` (CORE "Attachment"; FED "Blob Fetch and SSRF"). No key fields; under E2EE all metadata goes inside the ciphertext (CORE "Fields Inside the Ciphertext"; CID "Client-Encrypted Blobs") | M->J Ly, J->M X without extension | JMAP has nowhere to put a per-file key, nonce or URL. J->M needs a fetchable URL and a key that the JMAP object does not carry. `description`, `expires` and part-level `language` have no JMAP equivalent |
| Mentions | No field: a Markdown or HTML link to a user or group URI (CONTENT §5.4, §9.6) | Structured `Mention {id, offset, length}` (byte offsets) and `BroadcastMention {scope}` (CORE "Mention", "BroadcastMention") | M->J Ly, J->M Ly | User mentions convert by parsing links or emitting them. The display text may be replaced (CONTENT §9.6), so offsets shift. Broadcast `everyone`/`here`/`admins` have no MIMI form, including JMAP's bypass-mute semantics. Whether a `did:` URI is an acceptable MIMI mention target is not stated (uncertain) |
| Receipts, delivery status | STATUS: `application/mimi-message-status`, a list of [messageId, status] where status is unread, delivered, read, expired, deleted, hidden or error (STATUS §3, §4). Policy: required, optional or forbidden (POL §6.1) | `deliveryState`, per-recipient `deliveryReceipts {deliveredAt, deviceDeliveredAt, readAt, readDisposition}`, `ReadPosition`; `Peer/receipt`; bilateral `receiptSharing` (CORE Message fields, "ReadDisposition"; FED `Peer/receipt`) | Ly | delivered and read map; deleted maps to `readDisposition` deleted. expired, hidden, error and unread have no JMAP value. `deviceDeliveredAt` and `processed` have no MIMI value. MIMI's per-room policy and JMAP's bilateral opt-in are different consent models |
| Typing, presence | None. POL reserves `canChangeOwnPresence` (§8.7) | `Chat/typing`, `Peer/typing`, `PresenceStatus`, `Peer/presence`, WSS `ChatTypingEvent`/`ChatPresenceEvent` | X (J->M) | A gap in MIMI. Could be carried as a proprietary media type that MIMI peers ignore |
| Rich text | MTI: text/plain and `text/markdown;variant=GFM-MIMI` (tables, task lists, strikethrough; no HTML, no autolink). RECOMMENDED: CommonMark, text/html (CONTENT §7.1, §7.1.1). Multipart chooseOne, singleUnit, processAll; per-part language and disposition (CONTENT §4.4) | `bodyType`: text/plain MUST; text/markdown (CommonMark), `application/jmap-chat-rich` SHOULD (CORE capability; "Rich Body Format") | M->J Ly, J->M Ly | jmap-chat-rich spans map to GFM-MIMI. Code-block `lang` and mentions convert; HTML must be escaped. MIMI chooseOne alternatives, singleUnit groups, language tags and dispositions (profile, icon, session, preview, inline) collapse to one JMAP body plus attachments |
| Expiry | `expires = [relative, uint32]`: relative means seconds after read, absolute means epoch seconds. A hint only (CONTENT §4.1, §5.8). Room policy component (POL §6.8) | `senderExpiresAt` (absolute; receivers MUST honour), `burnOnRead`, `Chat.messageExpirySeconds` (local policy) (CORE Message fields) | M->J Ly, J->M L | Absolute expiry maps to `senderExpiresAt`. Relative N>0 has no JMAP equivalent; only N=0 is close to `burnOnRead`. The obligation differs: MIMI's is a hint, JMAP's is a MUST |
| Room/chat metadata | `RoomMetaData {room_uri, room_name, room_descriptions[media_type, language, content], room_avatar (https URI), room_subject, room_mood}` (PROTO §7.6) | `Chat.name`, `description`, `avatarBlobId`, `topic`, `pinnedMessageIds`; Space name, description, icon (CORE "Chat Object Fields", "Space") | Ly | Multilingual or typed descriptions and `room_mood` are lost M->J. The avatar URI and blobId need fetching and re-hosting. Pins have no MIMI form |
| Membership, roles, permissions | Exactly one role per user, with about 80 capabilities in a registry; role 1 means banned; min/max counts; authorized role changes (POL §3, §8, §10.2). Participant list (users) and MLS membership (clients) are separate (ARCH §2, §4.2; PROTO §7.5) | Group chat roles admin and member (CORE "Updating a Chat"); Space RBAC with 10 permissions, position hierarchy and channel overrides (CORE "SpaceRole", "Space Permission Resolution") | Ly both ways | No common lattice. A MIMI room can express capabilities JMAP lacks: canReact, canEdit, upload by media class, link policy, call controls. JMAP channel overrides and role ordering have no MIMI analogue |
| Invites, joins | External join via `groupInfo` with an optional joining code (PROTO §5.6); preauthorization by credential claims (POL §4); join links (POL §6.2). Knock and invite are listed as gaps (PROTO §1.1) | `SpaceInvite {code, expiresAt, maxUses}`, `Space/join` (CORE "SpaceInvite", "Space/join"); group chat members are added by an admin | Ly | Codes roughly correspond. Preauthorization by credential claims has no JMAP form. Neither side defines knock or invite |
| Moderation | Ban, kick, voice (POL §2.1); `reportAbuse` to the hub with message franking (PROTO §5.4.1, §5.9) | `SpaceBan {reason, expiresAt}`, slow mode, block, kick via removeMembers (CORE "SpaceBan"). No abuse reporting | Ly | MIMI lacks timed bans and slow mode. JMAP lacks report and franking. MIMI kick (remove clients, keep the participant) has no exact JMAP form |
| Search, sync | None between servers; history to joiners is policy only (POL §6.6) | `/changes`, `/query`, `/queryChanges`; full-text and mention filters (CORE "Message/query") | n/a | Complementary: JMAP is the client's view of a MIMI room |
| Push | None | PushSubscription + `chatPush` (PUSH); EventSource; WSS | n/a | Complementary |

## 3. Gaps

### In MIMI, absent from JMAP Chat

1. Content-addressed, receiver-verifiable `MessageId` and version-specific references (CONTENT §3.3, §4.1).
2. Multipart semantics (chooseOne, singleUnit, processAll), per-part `language`, the disposition registry, and `cid:` part references (CONTENT §4.4, §8.2.2).
3. Inline per-attachment encryption parameters in `ExternalPart` (CONTENT §4.5).
4. Opaque `topicId`, `subject`, `senderTimestamp` precision, `lastSeen` DAG, `externalMessageId` (CONTENT §4.1; EXT §3 to §6).
5. Relative expiry, i.e. N seconds after read (CONTENT §5.8).
6. Room policy breadth: per-capability RBAC, preauthorization, max clients and users, `pseudonyms_allowed`, `multi_device`, `fixed_membership`, link preview, logging, bot and history policies (POL §3 to §6).
7. Franking and hub-directed abuse reports (PROTO §5.4.1, §5.9); consent request and grant (PROTO §5.7, §8); `identifierQuery` user discovery (PROTO §5.8); minimal-metadata rooms with pseudonymous credentials (PROTO §6).
8. `room_mood` and multilingual room descriptions (PROTO §7.6).
9. AV rendering metadata (AV §3); group portability between delivery services (PORT).
10. Message statuses `expired`, `hidden`, `error` (STATUS §4).

### In JMAP Chat, absent from MIMI

1. The whole client-server surface: query, sync, search, push, WebSocket (CORE; PUSH; WSS).
2. Typing indicators and presence (CORE "Chat/typing", "PresenceStatus"; FED presence methods).
3. Broadcast mentions with bypass-mute semantics (CORE "BroadcastMention").
4. Pinned messages, custom emoji, Space categories, slow mode, timed bans with reasons (CORE).
5. `MessageAction` and `Endpoint` capability links (payments, VTC, calendar, task, filenode) (CORE "MessageAction", "Endpoint").
6. Server-side edit history (CORE "MessageRevision").
7. Device-delivered vs delivered vs read, `readDisposition processed`, bilateral receipt opt-in (CORE; FED `Peer/receipt`).
8. A DID-based identity and key-rotation story (CDID; JDID). IDENT §6.3 discusses Verifiable Credentials and notes DIDs are optional there; it does not define DID use.
9. Calendars, tasks, filenodes, VTC integration (sibling drafts).

## 4. Translation feasibility (CO-side mimi-content <-> JMAP Chat Message)

**Verdict: not lossless in either direction. In an E2EE MLS group it is not possible at all without making the translator a plaintext gateway.**

Reasons, in order of severity:

1. **E2EE and authorship.** Both formats travel as MLS `PrivateMessage` payloads authenticated by the author's leaf signature. A CO service that rewrites them must decrypt them, which means it holds the group's application secrets as a member. It must also re-send the result under its own leaf. Receivers then see the service, not the user, as the MLS sender. CONTENT §9.1 says a receiver discards a message whose apparent sender is not a group member. The `senderUri` extension cannot paper over this, because MLS authenticates the leaf, not the URI. Agora §9.1's RECOMMENDED endpoint form holds only the sealing key and sees no plaintext, so it cannot translate.
2. **Identity derivation.** `MessageId` hashes the exact CBOR bytes and the salt (CONTENT §3.3). Each JMAP->MIMI translation produces a new message with a new salt and a new ID, so two translators produce two IDs for one JMAP message. Each MIMI->JMAP translation must mint a ULID and persist the mapping. Without a deterministic rule, independent translators disagree.
3. **Version-addressed references.** MIMI edits get new IDs, and `inReplyTo` names a version (CONTENT §4.1, §5.5). JMAP has one ID per logical message. The translator needs a version-to-original index, and replies to old versions lose that precision.
4. **Ordering.** MIMI has one hub order. JMAP orders per mailbox with last-write-wins (FED "Message Ordering"). M->J is fine. J->M edits and retractions that cross in flight can end up applied differently on the two sides.
5. **Attachments.** JMAP `Attachment` has no key, nonce or URL. J->M needs the translator to fetch and decrypt the blob, then re-encrypt and re-host it. M->J needs a fetch plus re-hosting, or a JMAP extension.
6. **Unmappable content**:
   - from MIMI: multipart alternatives, singleUnit, language tags, media reactions, relative expiry, named topics;
   - from JMAP: broadcast mentions, custom emoji, actions, pins, typing, presence.

What translates cleanly given an ID table: plain or Markdown text, emoji reactions and unreactions, delete-for-all, absolute expiry, Slack-style threads, and delivered or read receipts.

## 5. Recommendations

### 5a. jmap-chat drafts (suggestions only; drafts not edited)

R1. **Specify a deterministic `MessageId` -> `senderMsgId` mapping** in CORE "Relationship to MIMI" for servers that accept `application/mimi-content`. For example, take ULID time = hub accepted timestamp in milliseconds and the 80-bit randomness = octets 1 to 10 of the MessageId. This lets independent servers agree without a shared table. Alternative: add an optional `Message.mimiMessageId` (base64url, 32 octets) and allow references by it. The derivation is the smaller change. Its collision bound is about 2^-40 per same-millisecond pair, acceptable for display references (estimated).

R2. **Add per-revision identity**: an optional `revisionId` on `MessageRevision` and on the FED `edit` payload, and an optional `replyToRevision`, so a MIMI `inReplyTo` that names an older version survives the round trip.

R3. **Extend `Attachment` for E2EE and MIMI**: optional `url`, `encAlg`, `key`, `nonce`, `aad`, `contentHashAlg`, `expires`, `description`. These follow CONTENT §4.5 and are valid only inside the ciphertext. They also close CORE's own gap that E2EE attachment metadata has no defined fields.

R4. **Expiry**: add `expiresAfterReadSeconds`, matching CONTENT relative expiry, and generalise `burnOnRead` as the value 0.

R5. **Topics**: add optional `Message.topicId` (opaque, base64url) and `subject`, or state that only root-message topics are supported.

R6. **Receipts**: add `expired`, `hidden` and `error` to `ReadDisposition`, or state the STATUS mapping explicitly.

R7. **Reactions**: allow a reaction body that is not an emoji (a blob reference), or state that MIMI media reactions are rendered as replies, as CONTENT §5.3 allows.

R8. **Version currency**: CORE cites MIMI-CONTENT without a revision. Pin it to `draft-ietf-mimi-content-09`. Cite POL (`draft-ietf-mimi-room-policy-04`) in FED's contrast, since role and capability mapping is where Space RBAC differs most.

R9. **Do not** try to make FED interoperate with the MIMI hub model. The drafts already state it is a different architecture, and that position is correct.

### 5b. Agora

A1. **Carry mimi-content natively, not as a translation target.** Under D1 (typed bytes, signatures over exact bytes), mimi-content fits Agora's model: the body is exact CBOR bytes and `MessageId` is computed over those bytes. Two cases:
- In a MIMI-interop group (`contentFormat: "mimi-v1"`), MIMI peers expect `application_data` framed by the mls-extensions content advertisement (`ApplicationFraming` carrying a media type; CONTENT-09 §2, PROTO §5.4.1.1), not the Agora §13.1 envelope. Specify that such groups use `ApplicationFraming` with `application/mimi-content`. Its `{media_type, content}` is the same shape as D1's `{contentType, body}`.
- Outside MIMI groups, an envelope `{type: <Agora type URI for mimi-content>, contentType: "application/mimi-content", body}` is enough if Agora wants mimi-content as an optional body format. Agora clients would build the JMAP `Message` view locally.

A2. **Drop or redefine §9.1 "Agora content format mode".** It relies on "a registered MIMI content type" and a plain-text fallback "negotiated at join time". Neither exists in MIMI. The supported way to send proprietary content is a chooseOne alternative next to a standard type (CONTENT §7.2). If the mode stays, define it as mimi-content whose NestedPart is chooseOne [`text/markdown;variant=GFM-MIMI`, Agora JMAP Message media type]. Reconcile §5.2.7.4 `ClientCapabilities` with mls-extensions content advertisement in MIMI groups.

A3. **IDs in MIMI groups.** The MIMI `MessageId` is canonical. Derive the local `senderMsgId` per R1, so `replyTo`, `threadRootId` and reaction references inside Agora clients resolve the same way on every device. Agora's per-device `seq` (§5.1.1) cannot ride in `ApplicationFraming`. Either carry it as a private-use (negative-key) MIMI extension, or state that gap detection is unavailable in MIMI groups.

A4. **Hub and follower placement under operator separation.**
- Hub and follower are provider roles that see the participant list, policy and metadata (PROTO §6, §7). They are CO components, consistent with §9.1 and ARCHITECTURE S1/S8. A relay (IO) must never be a hub or follower.
- When an Agora CO hosts the room it is the MIMI hub. That needs MIMI room state in the MLS GroupContext (`mimiParticipantList`, `mimiRoomPolicy` AppSync components, PROTO §4.3.2, §7) in addition to CO-signed Space state. Define a mapping from Agora Space roles and bans to POL roles and capabilities, and treat Space state as the source of truth.
- When a peer provider hosts it, the Agora CO endpoint is a follower and cannot enforce Agora Space policy on MIMI members.
- **Needs decision.** The commit-ordering authorities conflict. MIMI's hub orders handshakes and fan-out (PROTO §5.5, §7.1). Agora orders Commits by sequencer stamp or the lowest-hash rule (§4.1, §5.1.1). Recommendation: one orderer per MIMI-interop channel. When Agora is the hub, the hub and the channel sequencer are the same CO component. When Agora is a follower, the foreign hub's fan-out order is authoritative and the channel runs with no Agora sequencer.

A5. **Do not emit `message_id` Safe AAD (MSGID).** It exposes message IDs to providers. Agora relays would not see it, because of the sealed envelope, but every MIMI hub on the path would.

A6. **Fix §9.1 facts**:
- References: it cites `draft-ietf-mimi-protocol-05` and calls arch and protocol "expired without replacement". As of 2026-10-17, arch-03 (exp 2027-01-07), protocol-06, content-09 and room-policy-04 are all active, so the "WG is stalled" sentence is out of date.
- URI shapes: `mimi://example.com/alice` and `mimi://example.com/rooms/engineering` do not match the `/u/` and `/r/` forms (PROTO §3 Table 1; IDENT §4 Table 3). They should be `mimi://example.com/u/alice` and `mimi://example.com/r/engineering`. Bump `mimiSpecVersion` in the example to `draft-ietf-mimi-content-09`.

A7. **Gateway or interop profile (agora-pozi.38)**:
- Keep the MIMI hook in core §9, since native shared-group MLS is not a gateway. Move to `profiles/gateways.md`:
  - the content-mapping table above, restricted to lossless and lossy rows;
  - the rule that any service translating between mimi-content and JMAP Chat is a plaintext gateway subject to the §9.3 disclosure;
  - the ID-table persistence requirement for gateways.
- Add to the profile the MIMI features Agora cannot honour, so bridge UX can disclose them: franking-based reports (Agora reports via `AbuseReport` in a DM group, §4.7), relative expiry, multipart alternatives.

A8. **Track, do not implement yet**:
- STATUS, ATT, EXT, MSGID, IDENT and IDS are individual drafts.
- ATT's attachment scheme is not aligned with CONTENT (ATT §3.2 TODO) and differs from Agora's `agora blob` group-encrypted blobs (§3.4).
- Agora's per-epoch exporter key is closer to ATT §3.6 than to CONTENT §4.5's explicit key. If CONTENT keeps explicit keys, MIMI-group attachments need per-file random keys inside the ExternalPart, not `agora blob`.

## Uncertainties

- CONTENT §3.3 does not say what to hash when the optional `senderUri`/`roomUri` extensions are absent. Presumably the derived URLs of §4.6 (uncertain).
- Whether `contentHash` in ExternalPart covers ciphertext or plaintext. The wording suggests ciphertext (uncertain).
- Whether a `did:` URI is acceptable as a MIMI mention or user target. CONTENT §3.2 allows "any IM scheme"; no text addresses DIDs.
- PROTO §5.1 vs §5.7 disagree on consent endpoint path parameters, and PROTO §3.1 uses capability names absent from POL. These are MIMI-internal inconsistencies, not resolved here.
- FED is internally inconsistent on whether group "delivered" needs all recipients or one ("Group Chat Delivery").
- Currency of EXT, AV and PORT was not checked against datatracker.
