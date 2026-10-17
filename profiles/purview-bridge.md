# Agora Protocol: Microsoft Purview Bridge
## Implementation Specification v0.1

**Status:** Draft

**Scope:** This document specifies the Agora Purview Bridge, a compliance gateway that ingests Agora `ComplianceRecord` objects (spec §7.4) and VTC compliance records (spec §6.12.4, spec §6.12.6) into Microsoft Exchange Online mailboxes for processing by Microsoft Purview Communication Compliance, eDiscovery, retention policies, and litigation hold.

**Dependencies:** the Agora protocol specification (`spec/`, current draft), spec §7 (Compliance Logging), spec §6.12 (Recording Grant Sub-Protocol), spec §4.6 (Direct Message Channels), spec §5.2.3 (Message Types), spec §13.1 (Typed Payload Envelope).

**Microsoft behavior in this document.** Statements marked "verify against current Microsoft Graph documentation" or "verify against current Purview documentation" describe Microsoft behavior this profile depends on but has not confirmed. An implementer MUST confirm each one before production deployment.

**Citations.** "spec §N" refers to the Agora Protocol Specification; a bare "§N" refers to a section of this document.

---

## 1. Overview

### 1.1 Architecture

The Purview Bridge is a Communications Operator (CO) component that runs alongside the CO's `ComplianceLogger` principal (spec §7.3). It does not replace the logger; the logger's IPLD compliance log (spec §7.4) remains the authoritative tamper-evident record. The bridge is a one-way export pipeline:

```
Agora MLS groups
      │
      ▼ (MLS decryption, logger is a passive member)
ComplianceLogger (spec §7.3)
      │
      ├── IPLD compliance log (spec §7.4)   ← authoritative Agora record
      │
      └── PurviewBridge                ← this spec
            │
            ▼ (Microsoft Graph, create item, no send)
      Exchange Online mailboxes of regulated members
            │
            ▼
      Microsoft Purview
      (Communication Compliance,
       eDiscovery, Retention,
       Litigation Hold)
```

The bridge reads signed `ComplianceRecord` envelopes from the logger's local record stream (§8.3) and, for each record, creates one Exchange item in the mailbox of each regulated member (spec §7.2 `regulatedMembers`) who was a member of the group when the message was sent. Purview then applies retention, Communication Compliance and eDiscovery to these items as it does to other mailbox items.

### 1.2 Scope of the Bridge

The bridge performs the following functions:

- Translates each `ComplianceRecord` and its payload (a typed envelope, for example a JMAP Chat `Message`; spec §5.2.3) into an Exchange item with a human-readable body, defined `x-agora-*` headers, and the signed record attached byte-for-byte.
- Creates items in the compliance archive folder of each target regulated member's mailbox (§4.1).
- Handles new Messages, edits, deletions, reactions, pin changes, file attachments, DM group messages, and other logged payload types.
- Exports VTC compliance metadata and references to the sealed recordings (not raw media; see §5).
- Maintains idempotency; no duplicate items are created on retry.
- Is append-only. The bridge never deletes, moves or modifies an item it has created. Edits, deletions and expiry are recorded by appending items or headers, never by changing earlier items (§6).
- Tracks bridge delivery state separately from the IPLD compliance log.

The bridge does not perform the following:

- Replace the IPLD compliance log as the tamper-evident compliance record.
- Hold MLS keys or decrypt anything. It receives only records the logger has already decrypted and signed.
- Touch relay traffic. It reads from the logger, never from relays or the network.
- Process anything the logger did not capture. Capture scope is set by `complianceLogging.scope` for Space channels and by `regulatedMembers` for DM groups (spec §7.2, spec §7.8).

### 1.3 Deployment Model

The bridge runs on CO infrastructure, co-located with or directly connected to the ComplianceLogger. It handles plaintext and member identities and MUST NOT run on a relay or any other IO component (ARCHITECTURE S8). It requires:

- Service principal credentials for the Microsoft 365 tenant (Entra ID app registration; §2.1).
- Read access to the CO's private mapping from Agora DIDs to Exchange Online UPNs (§2.3).
- Network access to `https://graph.microsoft.com` and `https://login.microsoftonline.com`.
- Read access to the ComplianceLogger's record stream (§8.3).

---

## 2. Microsoft 365 Provisioning

### 2.1 Entra ID App Registration

The bridge authenticates to Microsoft Graph using the OAuth 2.0 client credentials flow (application permissions, no user context). The app registration requires the following application permissions (not delegated):

- `Mail.ReadWrite`: create items and folders in regulated members' mailboxes. The permission also allows deletion; the bridge never uses it for that (§6).
- `User.Read.All`: read display names of mapped users (§3.2).

`Mail.ReadWrite` as an application permission covers every mailbox in the tenant. The operator SHOULD restrict the app to the regulated members' mailboxes with Exchange Online's application access scoping (RBAC for Applications or an application access policy; verify against current Microsoft Graph documentation).

The bridge MUST authenticate using a certificate credential, not a client secret. Certificate rotation SHOULD be automated via Azure Key Vault or an equivalent HSM-backed credential store.

Tenant admin consent is required for all application permissions above. The bridge operator provisions consent once; it applies tenant-wide.

```powershell
# Provision service principal (run once per tenant, as Global Admin)
az login
az ad sp create --id <bridge-app-client-id>
# Grant admin consent in the Entra portal or via:
az ad app permission admin-consent --id <bridge-app-client-id>
```

### 2.2 Compliance Mailbox Folder

The bridge creates items in a dedicated subfolder of each regulated member's primary mailbox, not in their Inbox, to keep compliance items out of the user's active mail view.

**Folder name:** `Agora Compliance Archive`

The bridge creates this folder on first deposit for each user:

```http
POST https://graph.microsoft.com/v1.0/users/{targetUPN}/mailFolders
Content-Type: application/json

{
  "displayName": "Agora Compliance Archive",
  "isHidden": true
}
```

`isHidden: true` hides the folder in Outlook. Whether items in hidden folders are indexed, searchable and retained the same as items in visible folders must be confirmed (verify against current Purview documentation). An operator that cannot confirm it SHOULD create the folder with `isHidden: false`.

Subfolders within the archive folder are organized as follows:

```
Agora Compliance Archive/
  ├── Space: <spaceName>/
  │     ├── Channel: <channelName>/
  │     └── ...
  └── Direct Messages/
```

The bridge creates subfolders lazily on first item for each Space and channel. Space and channel names come from the Space state document served by the CO's Space endpoint (spec §3.4); the channel is identified by the record's `channel` field (spec §7.4). Names are sanitized for Exchange folder name constraints (maximum 255 characters; the characters `\ / : * ? " < > |` are prohibited).

### 2.3 DID-to-M365 Identity Mapping

The bridge maintains a mapping table `{ agoraDID → m365UPN }`. The mapping is private CO data: it MUST be held only in the CO's directory, the DID provisioning service's database and the bridge's own store, and MUST NOT be written into any DID document, profile, Space state or other published or gossiped record (spec §2.5.2). The table is populated by one of the following methods:

1. **Provisioning-service record** (preferred for enterprise deployments): at onboarding (spec §2.5.3) the DID provisioning service validates the IdP token, whose SAML attribute (`urn:oid:1.2.840.113549.1.9.1` / email) or OIDC claim (`upn` or `email`) carries the M365 UPN. The provisioning service records `{ agoraDID → m365UPN }` in its private store, and the bridge reads it over an authenticated internal interface. The Agora client takes no part in the mapping.

2. **Manual provisioning**: an admin-supplied CSV mapping `agoraDID,m365UPN` loaded at bridge startup. This is the fallback for environments without SAML/OIDC integration.

The bridge MUST NOT derive a UPN from a DID. Employer-provisioned DIDs use a `localIdentifier` that is never derived from a name, email address or UPN (spec §2.5.2), so the DID carries no usable mailbox address.

The mapping is required for every DID in `regulatedMembers`, since those are the mailboxes items go to (§4.1). Senders need no mapping. If a regulated member has no mapping, the bridge MUST create that member's items in a designated catch-all mailbox (`agora-compliance-catchall@<tenant>`), with the member's DID in the `x-agora-target-did` header, and MUST alert the compliance officer. Items in the catch-all mailbox are subject to Purview policies like any other mailbox item.

---

## 3. Item Format

The bridge translates each `ComplianceRecord` (spec §7.4) into an Exchange item created through Microsoft Graph. Exchange and Purview treat these as mailbox items and apply compliance policies to them.

### 3.1 Graph API Deposit Call

The bridge creates each item directly in the target folder as a non-draft item. No message is sent, so no mail is delivered to anyone.

```http
POST https://graph.microsoft.com/v1.0/users/{targetUPN}/mailFolders/{folderId}/messages
Content-Type: application/json

{
  "subject": "[Agora] {spaceName} / {channelName}",
  "from":    { "emailAddress": { "name": "{senderDisplayName}", "address": "{senderAddress}" } },
  "toRecipients": [ { "emailAddress": { "address": "{targetUPN}" } } ],
  "body": { "contentType": "text", "content": "{rendered body, §3.4}" },
  "internetMessageHeaders": [
    { "name": "x-agora-record-version", "value": "1" },
    ...
  ],
  "singleValueExtendedProperties": [
    { "id": "Integer 0x0E07",        "value": "1" },
    { "id": "SystemTime 0x0039",     "value": "{loggedAt}" },
    { "id": "SystemTime 0x0E06",     "value": "{loggedAt}" },
    { "id": "String {bridge-GUID} Name AgoraDedupKey", "value": "{envelopeID}" }
  ]
}
```

- `Integer 0x0E07` is the MAPI `PidTagMessageFlags` property. Setting it to `1` (read) on create, without the unsent flag, makes Exchange store the item as a received item rather than a draft.
- `SystemTime 0x0039` (`PidTagClientSubmitTime`) and `SystemTime 0x0E06` (`PidTagMessageDeliveryTime`) set the item's sent and received times to the record's logged time, so the item's timestamp is the capture time rather than the deposit time.
- `AgoraDedupKey` is a named property in a GUID namespace the bridge operator generates once. It carries the record's `envelopeID` for the duplicate check in §4.1.
- Attachments (the signed record, §3.2, and file content, §3.5) are added after creation with `POST .../messages/{id}/attachments`, or with an attachment upload session for files above the inline request size limit.

This method depends on the following Graph behavior, none of which this profile has confirmed (verify against current Microsoft Graph documentation): that a message created with these extended properties is stored as a non-draft item; that `from` and `internetMessageHeaders` may be set on create, including any limit on the number or length of custom headers; that the MAPI time properties may be set on create; and the request size limits for inline and upload-session attachments. If custom header limits prevent writing every header in §3.3, the bridge writes the headers marked "required" in §3.3 and relies on the body marker block (§3.4) and the attached record for the rest.

The bridge MUST NOT call `/send`, `sendMail`, or any other Graph operation that transmits mail.

### 3.2 Item Structure

| Item property | Value |
|---|---|
| Subject | `[Agora] {spaceName} / {channelName}` for channel records; §4.2 for DM records |
| From | The sender's UPN if the sender's DID is in the mapping (§2.3); otherwise `{senderDisplayName} <agora-{hash}@agora.invalid>`, where `{hash}` is the first 16 hex characters of SHA-256 over the sender DID string |
| To | `{targetUPN}`, the regulated member whose mailbox holds the item |
| Sent and received time | Record `ts` (`loggedAt`) |
| Body | Text rendering (§3.4) |
| Internet message headers | `x-agora-*` headers (§3.3) |
| Attachment `agora-compliance-record.cbor` | The `ComplianceRecord` exactly as stored by the logger: its encoded typed envelope (spec §13.1), including the logger's JWS in `sig` (spec §13.1.1). Content type `application/cbor`. |
| Further attachments | File content (§3.5) |

The `ComplianceRecord` is a signed typed envelope whose `body` holds the record fields (`envelopeID`, `channel`, `senderDID`, `epoch`, `seq`, `ts`, `plaintextPayload`, `outerEnvelopeCID`, `prevRecordCID`; spec §7.4). `plaintextPayload` is the decrypted inner payload envelope, itself a typed envelope whose `type` names the payload (for example `urn:ietf:params:jmap:chat#Message`) and whose `body` holds the payload bytes as sent (spec §5.2.2). The attachment MUST be the exact stored bytes (spec §13.1.1 byte-for-byte rule) so an investigator can verify the logger's signature without Agora client software beyond a JWS and CBOR library.

`agora.invalid` uses the `.invalid` top-level domain (RFC 6761), which cannot be registered, so a synthetic sender address can never reach a real mailbox.

**Display names.** For a mapped sender, the display name is the M365 directory display name. For any other sender, it is the `displayName` in the sender's Agora profile (spec §2.3), cached for 1 hour. A display name is a label for investigators; identity matching uses `x-agora-sender-did`.

### 3.3 Custom Header Index (`x-agora-*`)

The bridge writes the following headers. A header whose value is absent for a given record MUST be omitted, not written as an empty string. All timestamps are RFC 3339 UTC strings, as carried in the record or payload.

| Header | Required | Source | Description |
|---|---|---|---|
| `x-agora-record-version` | yes | constant | Version of this item format. Currently `1`. |
| `x-agora-envelope-id` | yes | record `envelopeID` | Unique per logged MLS message. Duplicate-check key. |
| `x-agora-record-cid` | yes | logger | CID of the stored `ComplianceRecord` envelope. |
| `x-agora-prev-record-cid` | no | record `prevRecordCID` | Chain link to the previous record in the channel's log. |
| `x-agora-logger-did` | yes | record `sig` `kid` | DID of the logger that signed the record. |
| `x-agora-channel` | yes | record `channel` | The channel URI as logged. For a DM group, the logged value for that group. |
| `x-agora-space-name` | no | Space state (spec §3.4) | Space name at deposit time. Absent for DM records. |
| `x-agora-channel-name` | no | Space state (spec §3.4) | Channel name at deposit time. Absent for DM records. |
| `x-agora-is-dm` | yes | logger | `true` if the record came from a DM group (spec §4.6), else `false`. |
| `x-agora-dm-group-id` | no | `DMGroupDescriptor.dmGroupID` (spec §4.6) | Stable DM group identifier. Present only when `x-agora-is-dm` is `true`. |
| `x-agora-sender-did` | yes | record `senderDID` | Sender DID. Primary identity field. |
| `x-agora-target-did` | yes | §4.1 | DID of the regulated member whose mailbox, or whose catch-all entry, holds this item. |
| `x-agora-epoch` | yes | record `epoch` | MLS epoch of the message. |
| `x-agora-seq` | yes | record `seq` | Sender's per-channel sequence number (spec §5.1.1). |
| `x-agora-logged-at` | yes | record `ts` | Time the logger captured the message. Used for the item timestamp. |
| `x-agora-sent-at` | no | payload `sentAt` | Sender's claimed send time. Not authoritative (spec §5.1.1). |
| `x-agora-payload-type` | yes | payload envelope `type` | For example `urn:ietf:params:jmap:chat#Message`. |
| `x-agora-record-kind` | yes | derived (§6) | One of `message`, `edit`, `deletion`, `reaction`, `pins`, `other`. |
| `x-agora-sender-msg-id` | no | payload `senderMsgId` | For `message`: the Message's own ID. For `edit`, `deletion` and `reaction`: the target Message's ID. |
| `x-agora-reaction-id` | no | payload `senderReactionId` | For `reaction` only. |
| `x-agora-expires-at` | no | payload `senderExpiresAt` | Sender's requested expiry (spec §5.2.4), recorded for audit. Never acted on (§6.3). |
| `x-agora-vtc-session-id` | no | §5 | CID of the `VTCComplianceAuditEntry`, for VTC items only. |
| `x-agora-vtc-media-cid` | no | §5 | Comma-separated `mediaCID` values of the sealed recordings. |
| `x-agora-vtc-media-format` | no | §5 | `mediaFormat` from the `VTCComplianceRecord`. |
| `x-agora-vtc-epochs-recorded` | no | §5 | Comma-separated `epochsRecorded`. |
| `x-agora-vtc-epochs-gapped` | no | §5 | Comma-separated `epochsGapped`; omitted if empty. |

Whether Purview Communication Compliance conditions and eDiscovery keyword queries can match custom `x-` header values is not confirmed (verify against current Purview documentation). The bridge therefore also writes the identifiers that investigators search on into the body marker block (§3.4), which is ordinary body text.

### 3.4 Message Body Text

The text body MUST contain a human-readable rendering of the record, usable by Purview Communication Compliance classifiers and investigators without Agora client software. It begins with a marker block:

```
Agora-Envelope-ID: {envelopeID}
Agora-Sender-DID: {senderDID}
Agora-Channel: {channel}
Agora-Record-Kind: {recordKind}
Agora-Sender-Msg-ID: {senderMsgId, if present}
Agora-Logged-At: {ts}

```

The rendering that follows depends on the record kind (§6). `{ts}` is the record `ts`.

**`message`** (JMAP Chat `Message`, new):
```
[{ts}] {senderDisplayName} ({senderDID}):
{body, with Markdown formatting stripped if bodyType is text/markdown}

[Exact payload in agora-compliance-record.cbor]
```

**`edit`** (JMAP Chat `Message` body containing `editedAt`):
```
[{ts}] {senderDisplayName} EDITED message {target senderMsgId} at {editedAt}:
New text: {body, Markdown stripped}
Earlier text: see the item with Agora-Sender-Msg-ID {target senderMsgId}
```

**`deletion`** (JMAP Chat `Message` body containing `deletedAt`):
```
[{ts}] {senderDisplayName} DELETED message {target senderMsgId} for all members at {deletedAt}.
The original item is retained.
```

**`reaction`** (JMAP Chat `Reaction`):
```
[{ts}] {senderDisplayName} {added|removed} reaction {emoji} on message {target senderMsgId}
```

**`pins`** (JMAP Chat `Chat` with `pinnedMessageIds`):
```
[{ts}] {senderDisplayName} set pinned messages: {pinnedMessageIds}
```

**`other`** (any other logged type, for example `urn:agora:type:SystemEvent`):
```
[{ts}] {senderDisplayName} sent {payload type}.
[Exact payload in agora-compliance-record.cbor]
```

A new Message with `attachments` adds one line per attachment:
```
  Attachment: {name}, {size} bytes, {type}, blobId {blobId}
```

Markdown stripping for text bodies: remove `**bold**`, `*italic*`, `~~strikethrough~~`, `` `code` ``, and heading markers. Preserve URLs as plain text. The exact `body` and `bodyType` are preserved in the attached record (spec §5.2.7).

Whether Purview keyword search tokenizes the marker block lines so that a full DID or URN matches as one term is not confirmed (verify against current Purview documentation).

### 3.5 File Attachment Handling

An attachment's `blobId` is the CID of a group-encrypted blob (spec §5.2.2, spec §3.4). Only a group member can decrypt it, so the bridge never fetches blobs from IPFS or any relay. The logger, as a passive member, fetches and decrypts attachment blobs and passes the plaintext to the bridge over the record stream (§8.3).

1. If the file fits within the tenant's configured maximum message size and the Graph attachment upload limits (verify against current Microsoft Graph documentation), the bridge adds it as a file attachment with its original filename, sanitized for Exchange, and its declared media type, falling back to `application/octet-stream` if unknown.
2. If the file is too large, the bridge records only the metadata (name, size, type, `blobId`) in the body, and the item points investigators to the logger's archived copy on CO storage.
3. If the logger could not decrypt or fetch the blob, the bridge MUST log the failure, record the metadata in the body with the line `Attachment content not captured`, and create the item without the file. The bridge MUST NOT block the deposit pipeline on attachment failures.

The plaintext `sha256` of an attachment is CO data and stays on CO infrastructure (spec §5.2.2).

---

## 4. Message Routing in Exchange

### 4.1 Channel Messages (Space Channels)

Every record goes to the mailboxes of regulated members, and only those. For each record, the target set is the DIDs in `complianceLogging.regulatedMembers` (spec §7.2) that were members of the record's MLS group at the record's epoch. The logger supplies this set with each record (§8.3), since it holds the group roster.

For each DID in the target set, the bridge creates one item in that member's `Agora Compliance Archive` folder, or in the catch-all mailbox if the DID has no mapping (§2.3). If a channel has 40 members and 3 of them are regulated, each channel message produces 3 items with identical content and the same `x-agora-envelope-id`, differing only in `To:` and `x-agora-target-did`.

A record whose target set is empty is not deposited. The bridge marks it `skipped` with reason `no-regulated-member` (§7.1). The record remains in the IPLD compliance log.

The delivery state store (§7.1) is the primary duplicate check. When it has no `deposited` row for a `(envelopeID, targetDID)` pair but shows an earlier attempt, the bridge SHOULD query the target folder before creating the item, to cover a crash between creation and state update:

```http
GET https://graph.microsoft.com/v1.0/users/{targetUPN}/mailFolders/{folderId}/messages
  ?$filter=singleValueExtendedProperties/Any(ep: ep/id eq 'String {bridge-GUID} Name AgoraDedupKey' and ep/value eq '{envelopeID}')
  &$select=id
```

If a match is found, the bridge records it as `deposited` and creates nothing. (Filter syntax: verify against current Microsoft Graph documentation.)

### 4.2 DM Group Messages (spec §4.6)

DM compliance logging (spec §7.8) uses the same target rule as §4.1: the target set is this CO's regulated members in the DM group at the record's epoch. Items go under `Direct Messages/` in each target's archive folder. When a DM group holds regulated members of several COs, each CO's logger and bridge deposit only for that CO's own regulated members (spec §7.8.5).

For a two-party DM:
```
Subject: [Agora DM] {regulatedMemberDisplayName} ↔ {counterpartyDisplayName}
```

For a DM group with multiple participants:
```
Subject: [Agora DM] {p1}, {p2}, {p3} (Group DM)
```

The `x-agora-dm-group-id` header and the `Agora-Channel` marker line group related items in eDiscovery searches.

### 4.3 Compliance Folder Retention

Items in the Agora Compliance Archive folder MUST be covered by the organization's Purview retention configuration. The bridge operator configures this in the Purview portal:

| Setting              | Value                                                                       |
|----------------------|-----------------------------------------------------------------------------|
| Retention target     | The regulated members' mailboxes and the catch-all mailbox                  |
| Retention period     | At least `complianceLogging.retentionDays` from Space state                 |
| Retention action     | Retain only (do not delete at policy expiry without explicit legal review)  |
| Litigation hold      | Apply to all regulated user mailboxes independently of retention policy     |

The bridge creates items; Purview's retention machinery governs their lifecycle from that point.

---

## 5. VTC Compliance Records (spec §6.12)

The bridge handles VTC compliance records differently from text records. Media is not deposited into Exchange. The recorder stores each recording on CO storage, sealed with HPKE to the recorder's `keyAgreement` key (spec §6.12.4), and records its metadata as signed `VTCComplianceRecord` entries (one per epoch) and one `VTCComplianceAuditEntry` per session (spec §6.12.6). The bridge reads these from the recorder's record stream, which has the same form as the logger's (§8.3); the recorder may be the same principal as the logger (spec §7.6).

### 5.1 VTC Notification Item

For each `VTCComplianceAuditEntry`, the bridge creates one item per regulated member among the session's participants, using the method of §3.1:

| Item property | Value |
|---|---|
| Subject | `[Agora VTC] {spaceName} / {channelName} ({durationMinutes}min call)` |
| From | `Agora VTC Compliance <vtc-compliance@agora.invalid>` |
| To | `{targetUPN}` |
| Sent and received time | `callStart` |
| Headers | `x-agora-record-version`, `x-agora-record-kind: other`, `x-agora-payload-type: VTCComplianceAuditEntry`, `x-agora-vtc-session-id`, `x-agora-channel`, `x-agora-logger-did` (the recorder DID), `x-agora-target-did`, `x-agora-vtc-media-cid`, `x-agora-vtc-media-format`, `x-agora-vtc-epochs-recorded`, `x-agora-vtc-epochs-gapped`, `x-agora-is-dm` |
| Attachments | The `VTCComplianceAuditEntry` and each `VTCComplianceRecord` it lists, as their exact stored envelopes (`.cbor`) |

**Text body:**
```
Agora-VTC-Session-ID: {auditEntryCID}
Agora-Channel: {channel}

[{callStart}] Voice/video call in {spaceName} / {channelName}

Duration: {durationMinutes} minutes
Participants ({count}):
  - {displayName} ({did}), joined {joinTs}, left {leaveTs}
  - ...

Recording:
  Sealed media CIDs: {mediaCID, ...}
  Format: {mediaFormat}
  Epochs recorded: {epochsRecorded}
  Epochs with gaps: {epochsGapped or "none"}
  Recorder: {recorderLabel} ({recorderDID})
```

### 5.2 Media Retrieval for eDiscovery

When an eDiscovery investigator needs the recording:

1. Read the `x-agora-vtc-media-cid` values from the VTC notification item.
2. Request the media from the CO's recording archive operator. The media objects are sealed to the recorder's key and only the CO can unseal them (spec §6.12.4); a copy held on IO storage is ciphertext only.
3. Verify the JWS on the attached `VTCComplianceRecord` envelopes against the recorder's DID (spec §13.1.1), and confirm that each unsealed object's sealed form matches its `mediaCID`, before treating the media as authentic.

**Epoch gap handling:** If `x-agora-vtc-epochs-gapped` is present, the recording has gaps (spec §6.12.6). The investigator SHOULD check the compliance audit chain for a matching gap record. A gap the recorder documented (for example, the recorder was offline) is distinct from an undocumented gap, which may indicate a removal attempt; for DM voice groups the `DMComplianceAuditEntry` `removalAttempts` field (spec §7.8.8) records those.

---

## 6. Edit, Delete, and Expiry Handling

The bridge is append-only. It MUST NOT delete, move or modify any item it has created, for any reason, including a deletion record, an expiry time, or a later correction. Every change in the conversation is recorded as a new item.

The bridge classifies each record by its payload envelope `type` and body (spec §5.2.3):

| Payload | `x-agora-record-kind` |
|---|---|
| `urn:ietf:params:jmap:chat#Message`, body contains `deletedAt` | `deletion` |
| `urn:ietf:params:jmap:chat#Message`, body contains `editedAt` | `edit` |
| `urn:ietf:params:jmap:chat#Message`, otherwise | `message` |
| `urn:ietf:params:jmap:chat#Reaction` | `reaction` |
| `urn:ietf:params:jmap:chat#Chat` | `pins` |
| any other type | `other` |

### 6.1 Edit Events

For an edit (a `Message` update carrying the target's `senderMsgId`, the new `body` and `bodyType`, and `editedAt`):

1. Create a new item with `x-agora-record-kind: edit` and `x-agora-sender-msg-id` set to the target's `senderMsgId`.
2. Leave the original item unchanged.
3. The body carries the new text (§3.4); the attached record carries the exact edit payload.

Purview eDiscovery returns both the original item and the edit item when searching by channel or sender, giving investigators the full edit history.

### 6.2 Delete Events

For a deletion (a `Message` update carrying the target's `senderMsgId`, `deletedAt` and `deletedForAll: true`):

1. Create a new item with `x-agora-record-kind: deletion` and `x-agora-sender-msg-id` set to the target's `senderMsgId`.
2. Leave the original item unchanged. The original is part of the compliance record whether or not litigation hold applies.
3. The body is the deletion rendering of §3.4.

The investigator sees the original item followed by the deletion item. An Admin's moderation deletion of another member's Message (spec §4.5) is logged and deposited the same way, with the Admin as sender.

### 6.3 Expiry Override (spec §7.5)

Per spec §7.5, compliance logging overrides sender expiry. Expiry produces no record: no deletion message is sent when a Message expires, because every member already holds the deadline (spec §5.2.4). The bridge therefore records expiry on the item at the time it is created:

- The `x-agora-expires-at` header carries the Message's `senderExpiresAt`.
- The bridge MUST NOT schedule or perform any action on an item based on this header.
- Disposition at the end of the regulatory retention period is managed by the compliance officer through Purview, not through the bridge.

---

## 7. Bridge State and Delivery Tracking

### 7.1 Delivery State Store

The bridge maintains a local delivery state store (SQLite or equivalent). One row tracks one item: one record deposited for one target regulated member.

```sql
CREATE TABLE delivery_state (
  envelope_id       TEXT NOT NULL,      -- x-agora-envelope-id
  target_did        TEXT NOT NULL,      -- x-agora-target-did; '' for a skipped record with no target
  record_cid        TEXT NOT NULL,      -- CID of the stored ComplianceRecord envelope
  record_kind       TEXT NOT NULL,      -- message, edit, deletion, reaction, pins, other
  sender_did        TEXT NOT NULL,
  target_upn        TEXT,               -- mailbox used; catch-all address if unmapped
  exchange_item_id  TEXT,               -- Graph message ID after creation
  folder_id         TEXT,               -- Exchange folder ID
  status            TEXT NOT NULL,      -- pending | deposited | failed | skipped
  skip_reason       TEXT,               -- e.g. no-regulated-member
  attempt_count     INTEGER DEFAULT 0,
  last_attempt_ts   TEXT,
  error             TEXT,               -- last error message if failed
  created_ts        TEXT NOT NULL,
  deposited_ts      TEXT,
  PRIMARY KEY (envelope_id, target_did)
);
```

Status values:

- **`pending`:** queued for deposit.
- **`deposited`:** item created in Exchange.
- **`failed`:** all retry attempts exhausted; requires manual intervention.
- **`skipped`:** intentionally not deposited (the record's target set is empty, §4.1; or the payload type is excluded by operator configuration).

The store holds target UPNs, which are private CO mapping data (§2.3); it is subject to §8.2.

### 7.2 Retry Policy

Failed deposits retry with exponential backoff:

| Attempt | Delay      |
|---------|------------|
| 1       | immediate  |
| 2       | 30 seconds |
| 3       | 5 minutes  |
| 4       | 30 minutes |
| 5       | 2 hours    |
| 6+      | 6 hours    |

After 7 days without a successful deposit, the status transitions to `failed` and a compliance alert is raised. A row in `failed` state is a compliance gap requiring investigation.

Graph API throttling limits constrain throughput during backlog catch-up (current per-mailbox and per-app limits: verify against current Microsoft Graph documentation). The bridge SHOULD use a token bucket rate limiter set below those limits and MUST honor `Retry-After` on HTTP 429 responses.

### 7.3 IPLD Chain Cursor

The bridge tracks its read position in the IPLD compliance log per channel as a cursor: the CID of the last-processed `ComplianceRecord`. On restart, the bridge resumes from the cursor.

Gap detection: if a `ComplianceRecord`'s `prevRecordCID` does not match the bridge's last-processed record CID for that channel, a chain gap exists. The bridge MUST alert on this condition and MUST attempt to backfill by walking the chain backwards from the current head to the last-known cursor position.

---

## 8. Authentication and Security

### 8.1 Graph API Authentication

The bridge authenticates using the OAuth 2.0 client credentials flow. Token acquisition:

```http
POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={clientId}
&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
&client_assertion={signed-JWT-from-certificate}
&scope=https://graph.microsoft.com/.default
```

The bridge caches the token and refreshes it 5 minutes before its `expires_in` elapses. Token material MUST be stored in memory only and MUST NOT be written to disk.

### 8.2 Bridge Process Security

- The bridge process MUST run as a dedicated service account with no network access beyond the Microsoft endpoints in §1.3, the ComplianceLogger's local socket, the CO's mapping interface (§2.3), and the CO's DID and profile resolver (§3.2).
- The delivery state store MUST reside on an encrypted volume (LUKS or equivalent).
- The certificate private key for Entra authentication MUST be stored in an HSM or TPM-backed keystore, never in a file. `PKCS#11` or `tpm2-pkcs11` are the required interfaces on Linux.
- Bridge logs MUST NOT contain message plaintext or UPNs. Log `envelope_id`, `record_cid`, `sender_did`, `target_did`, and `status` only.

### 8.3 ComplianceLogger Payload Access

The bridge reads records from the logger via a local Unix domain socket (preferred) or shared memory queue. The bridge MUST NOT have access to MLS epoch secrets or the logger's key material.

The interface is:

```
LocalSocket: /run/agora-compliance/records.sock
Protocol:    newline-delimited JSON stream
Each line:   {
               "recordCID": "...",
               "record": "{base64url of the exact stored ComplianceRecord envelope}",
               "isDM": true | false,
               "dmGroupID": "urn:agora:dmgroup:<uuid>",      (DM records only)
               "regulatedRecipients": ["did:...", ...],       (target set, §4.1)
               "attachments": [ { "blobId": "...", "path": "/run/agora-compliance/blobs/..." } ]
             }
```

`attachments` lists decrypted attachment files the logger has written to a local directory readable by the bridge (§3.5); an entry without `path` means the logger could not capture that blob. The bridge SHOULD verify each record's JWS against the logger DID (spec §13.1.1) before depositing it, and MUST alert on a verification failure.

The bridge processes records in order. If the bridge is offline, the logger buffers records to a local queue (configurable; default 10,000 records). On bridge reconnect, the queue is drained in order.

---

## 9. Operational Monitoring

### 9.1 Required Metrics

The bridge MUST expose the following metrics (Prometheus format):

| Metric                                     | Type    | Description                                     |
|--------------------------------------------|---------|-------------------------------------------------|
| `agora_bridge_records_received_total`      | counter | Records received from ComplianceLogger          |
| `agora_bridge_items_deposited_total`       | counter | Items created in Exchange                       |
| `agora_bridge_items_failed_total`          | counter | Rows in `failed` state                          |
| `agora_bridge_records_skipped_total`       | counter | Records skipped, by reason                      |
| `agora_bridge_deposit_lag_seconds`         | gauge   | Seconds behind the live logger stream           |
| `agora_bridge_retry_queue_depth`           | gauge   | Number of items pending retry                   |
| `agora_bridge_graph_api_errors_total`      | counter | Graph API errors by status code                 |
| `agora_bridge_attachment_failures_total`   | counter | Attachments the logger could not capture        |
| `agora_bridge_did_unmapped_total`          | counter | Items routed to catch-all for unmapped regulated members |
| `agora_bridge_record_sig_failures_total`   | counter | Records whose logger JWS failed verification    |

### 9.2 Compliance Alerts

The following conditions MUST trigger an alert to the compliance officer (email to a configurable designated address):

- Any row transitions to `failed` status.
- Bridge delivery lag exceeds 15 minutes.
- IPLD chain gap detected.
- DID mapping failure for a regulated member.
- Record signature verification failure.
- VTC epoch gap (`epochsGapped` non-empty in a `VTCComplianceAuditEntry`).
- Logger removal attempt detected (`removalAttempts` non-empty in `DMComplianceAuditEntry`).
- Graph API authentication failure (token acquisition failure).
- Bridge process crash or restart.

---

## 10. Purview Policy Configuration

After the bridge is operational, the compliance administrator configures the following in the Microsoft Purview portal. Each configuration below must be checked against what the tenant's Purview edition supports (verify against current Purview documentation).

### 10.1 Communication Compliance Policy

Create a policy whose supervised users are the regulated members, with the following conditions:

- **Scope to Agora items** by the subject prefix `[Agora` or the body marker `Agora-Envelope-ID:`.
- **Record kind filter:** scope classifiers to items whose body contains `Agora-Record-Kind: message` or `Agora-Record-Kind: edit`, excluding reactions, pins and system events, since classifiers are designed for human-authored text.
- **Built-in classifiers:** financial regulatory language, sensitive information types (SSNs, account numbers), etc., applied to the item body.

### 10.2 Retention Policy

| Setting          | Value                                                                  |
|------------------|------------------------------------------------------------------------|
| Target           | Regulated members' mailboxes and the catch-all mailbox                 |
| Scope            | Agora items, selected by a retention label auto-applied on the subject prefix or body marker, or the whole mailbox |
| Duration         | At least `complianceLogging.retentionDays`: the period the firm's applicable rule requires (e.g., SEC Rule 17a-4(b)(4): three years, the first two easily accessible); many firms configure longer |
| Action           | Retain only                                                            |

Purview retention policies apply to whole mailboxes; selecting only the Agora items requires a retention label (verify against current Purview documentation).

### 10.3 Litigation Hold

Apply litigation hold to all regulated user mailboxes and the catch-all mailbox. Under hold, Exchange preserves items that any party deletes or edits, including in Recoverable Items (verify against current Purview documentation). The bridge never deletes items (§6), so the hold protects against deletion by users, administrators or other applications.

### 10.4 eDiscovery Search Templates

Recommended saved searches for Agora data. They use body marker text and the subject prefix, which are ordinary item content. Whether a full DID or URN matches as a single keyword term is not confirmed (§3.4); test each template against known items before relying on it.

```
# All items from a specific Agora DID
"Agora-Sender-DID: {did}"

# All items in a specific channel or DM group
"Agora-Channel: {channel}"

# All DM items in a regulated user's mailbox
subject:"[Agora DM]"            (run against that user's mailbox)

# All VTC sessions
subject:"[Agora VTC]"

# Edits, deletions and reactions on a specific Message
"Agora-Sender-Msg-ID: {senderMsgId}"
```

---

## 11. Open Issues

1. **Item creation method:** §3.1 depends on Graph creating a non-draft, unsent item when `PidTagMessageFlags` and the MAPI time properties are set on create, and on `from` and custom headers being settable on create. None of this is confirmed in this profile (verify against current Microsoft Graph documentation). If it does not hold, the alternative is the Exchange mailbox import interface that Graph exposes for migration tools, which must be evaluated for permissions, item format and availability before adoption.

2. **Header searchability:** Whether Purview Communication Compliance and eDiscovery can match `x-agora-*` header values is unconfirmed. This profile does not rely on it: searches and policies use the subject prefix and body marker block (§3.4, §10). If header matching is confirmed, operators MAY add header-based conditions.

3. **Large attachments:** Files above the tenant's message size or Graph upload limits are deposited as metadata with a pointer to the logger's archived copy on CO storage (§3.5). Whether a pointer to a CO-held archive satisfies the applicable retention rule SHOULD be confirmed with the organization's compliance counsel before production deployment.

4. **Catch-all mailbox governance:** Items deposited to the catch-all mailbox because a regulated member has no mapping are regulated communications. The compliance officer MUST review and resolve mapping gaps promptly. A backlog in the catch-all mailbox is a compliance gap as well as an operational issue.
