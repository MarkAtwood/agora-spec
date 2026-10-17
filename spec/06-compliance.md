# Agora Protocol: Compliance Logging

> Binds: CO. Verbatim from `import/agora-protocol-spec-unified.md` lines 3621–3938 (§17). Section numbers are the source's and will be renumbered.

## 17. Compliance Logging

### 17.1 Overview

Organizations in regulated industries (financial services, healthcare, legal, government) are subject to message retention and audit requirements that conflict with the default Agora model of E2EE with relay-opaque content. Agora supports compliance logging as an **optional, space-level feature** that satisfies these requirements without architectural kludges.

Mechanically, compliance logging is implemented as a **passive member** (§6.1.3) — a `ComplianceLogger` principal — that silently receives and archives all messages in every MLS group it is admitted to. This applies to Space channels (§9) and Direct Message groups (§9.6) alike. It is structurally identical to a gateway (§16.2) but treated differently at the protocol and UI layers:

- It does not appear as a chat participant in client UI.
- It does not generate join/leave events in the message stream.
- Its presence is disclosed in space metadata and MLS group membership, but not in the message feed.
- It is added to channels automatically when logging is enabled, without requiring per-channel Admin action.

The result is compliant message capture that is cryptographically sound and tamper-evident, without a "Logger Bot joined #engineering" message appearing in every channel.

### 17.2 Enabling Compliance Logging

Compliance logging is enabled in the Space state document by the space owner:

```json
"complianceLogging": {
  "@type": "ComplianceLoggingConfig",
  "schemaVersion": "1",
  "enabled": true,
  "loggerDID": "did:key:z6MkLogger...",
  "loggerLabel": "Acme Corp Compliance Archive",
  "logStore": "ipfs://bafyrei...",
  "retentionDays": 2555,
  "scope": "all-channels",
  "enabledBy": "did:key:z6MkOwner...",
  "enabledAt": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

`loggerDID` is the DID of the compliance logging principal. `logStore` is the IPFS CID root of the compliance log — a content-addressed, append-only IPLD structure. `retentionDays` is the minimum retention period the logger is obligated to maintain. `scope` is `all-channels` or a list of channel path globs.

The `scope` field governs which Space channels receive the logger. The value `"all-channels"` causes the logger to be added to every channel in the Space, including channels created after compliance logging is enabled. A glob list (e.g., `["engineering/*", "legal/*"]`) limits logging to matching channel paths.

`scope` does **not** govern DM groups. DM group compliance logging is governed entirely by §17.8, which imposes an obligation on the regulated member's user agent independent of Space channel scope configuration.

Once `complianceLogging.enabled` is set to `true` and gossiped to the space topic, conformant clients MUST add the `loggerDID` to the MLS group of every channel matching `scope` on the next available Commit. This addition IS recorded in the MLS group membership (verifiable by any MLS-aware client) but MUST NOT produce a UI-visible join notification.

Disabling compliance logging requires a signed Space state mutation by the space owner. Clients remove the logger DID from channel MLS groups via Remove commits. The `complianceLogging` history in the IPLD space state chain retains a permanent record of when logging was enabled and disabled.

### 17.3 Logger Principal

The `ComplianceLogger` is a DID-identified principal operated by the space's compliance infrastructure — typically an on-premise archival system or a regulated third-party compliance service (e.g., a FINRA-registered archiving vendor).

The logger's DID document identifies it as a compliance logger:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:key:z6MkLogger...",
  "verificationMethod": [...],
  "service": [{
    "id": "did:key:z6MkLogger...#compliance",
    "type": "AgoraComplianceLogger",
    "serviceEndpoint": "https://archive.acme-corp.internal/v1/agora/compliance",
    "operator": "Acme Corp Legal",
    "regulatoryFramework": ["FINRA 17a-4", "SEC 17a-4"]
  }]
}
```

`regulatoryFramework` is an informational array of the regulatory requirements under which the logger operates. Clients MAY display this to members who inspect the space's compliance configuration.

The logger operates as a passive member (§6.1.3). It holds leaf credentials, participates in epoch ratchets, and receives `Welcome` messages when added to new channel groups. It does not send messages, publish presence events, generate typing indicators, or issue Commits or Proposals.

### 17.4 Log Record Format

Every message received by the logger is written as a signed `ComplianceRecord` to the IPLD log:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ComplianceRecord",
  "envelopeID": "urn:agora:msg:bafyrei...",
  "channel": "agora://bafyrei.../engineering/backend",
  "senderDID": "did:key:z6MkSender...",
  "epoch": 17,
  "seq": 1042,
  "ts": "2026-03-12T12:00:00.000Z",
  "plaintextPayload": "base64url...",
  "outerEnvelopeCID": "bafyrei...",
  "loggerSig": "base64url...",
  "prevRecordCID": "bafyrei..."
}
```

`plaintextPayload` is the decrypted inner payload (JSON-LD `ChatMessage` or other type), base64-encoded. `outerEnvelopeCID` links the compliance record to the tamper-evident message history. `loggerSig` is the logger's Ed25519 signature over the canonical record. `prevRecordCID` chains records into a linked list, making the log append-only and tamper-evident — inserting or deleting a record breaks the chain.

The log is organized as a per-channel IPLD DAG, with a space-level index mapping channel CIDs to their respective log chain heads.

### 17.5 Ephemeral Message and Expiry Handling

Ephemeral messages (`TypingEvent`, `PresenceEvent`) are never logged — they are excluded by type at the logger.

Messages with an `expiry` field present a deliberate tension: the sender expressed an intent for the message to be deleted, but the compliance obligation may override that intent. The resolution is explicit and must be disclosed:

- If `complianceLogging.enabled` is `true`, message expiry is honored for relay caches and client display, but the compliance logger retains the plaintext for `retentionDays` regardless of the sender's `expiry` value. This applies equally in DM groups where a compliance logger is present under §17.8 — the DM group member's expiry preference is honored in relay caches and client display, but the compliance logger retains the plaintext for the regulated member's `retentionDays` regardless.
- The Space state document MUST include a human-readable `retentionNotice` field when compliance logging is enabled:

```json
"retentionNotice": "This space is subject to regulatory message retention. Messages are archived for 2555 days regardless of expiry settings."
```

- Clients MUST display this notice to members when they first join a compliance-logging-enabled space, and MUST make it accessible from the space's information panel at any time.

This is the correct behavior for a regulated environment. The sender's expiry preference is preserved in the client and relay layers; the compliance layer overrides it with explicit disclosure.

### 17.6 Voice and Video Compliance Logging

VTC compliance recording is governed by the `RecordingGrant` mechanism and the `VTCComplianceConfig` space configuration, both fully specified in §10.12.

**Relationship to text compliance logging.** Text compliance logging (§17.1–§17.5) and VTC compliance recording (§10.12) are parallel mechanisms operating over the same MLS group. They are separately authorized and separately archived, but both feed into the same space IPLD compliance audit chain. A space with both `complianceLogging.enabled: true` and `vtcCompliance.enabled: true` captures the complete communication record — text, reactions, edits, deletions, and voice/video — in a unified, tamper-evident audit chain.

**Scope.** §17.1–§17.5 cover: text messages in space channels, reactions, edit events, delete events, file attachments, and DM text messages for regulated members (§17.8). §10.12 covers: audio and video media streams in space voice channels and DM voice groups for regulated members (§10.12.7).

**Same logger DID or separate.** The `complianceLogging.loggerDID` and `vtcCompliance.recorderDID` MAY be the same DID or different DIDs. Using the same DID is operationally simpler but requires the compliance principal to support both text archiving (passive member, §6.1.3) and VTC recording (HPKE key receipt and media decryption). Using separate DIDs allows specialist infrastructure for each function. Either configuration is conformant.

**`retentionDays` alignment.** The `vtcCompliance.retentionDays` SHOULD match `complianceLogging.retentionDays` to avoid a regulatory gap where text records are retained longer than corresponding voice records of the same conversation. If they differ, the longer value governs the overall retention obligation for the channel.

### 17.7 Member Disclosure

Compliance logging is not hidden from members. It is disclosed in space metadata and MLS group membership (which is visible to any technically capable member). Conformant clients MUST:

- Display a compliance logging indicator in the space information panel when `complianceLogging.enabled` is `true`.
- Display the `retentionNotice` to new members on first join.
- Allow members to inspect the full `ComplianceLoggingConfig` including `loggerDID`, `loggerLabel`, `retentionDays`, and `regulatoryFramework` from the space settings UI.
- NOT display a join/leave notification in any channel's message feed when the logger DID is added or removed from an MLS group.

The logger's MLS group membership is visible to any client that inspects raw MLS group state. This is intentional — the logger is not cryptographically hidden, only UI-silent. A technically capable member can always verify that a compliance logger is present.

In DM groups where a compliance logger is present under §17.8, disclosure obligations are governed by §17.8.4 rather than this section. The Space information panel disclosure requirements in this section apply only to Space channels.

### 17.8 Compliance Logging for Direct Message Groups

#### 17.8.1 Obligation

A Space member subject to compliance logging (i.e., a member of a Space where `complianceLogging.enabled` is `true`) carries that compliance obligation into every DM group they participate in, regardless of whether the DM group has any Space affiliation.

The compliance obligation follows the regulated user, not the channel. A regulated user who conducts business communication via DM is not exempt from their Space's retention requirements by virtue of using a DM group rather than a Space channel.

A conformant client for a regulated Space member MUST:

1. Add the Space's `loggerDID` to the MLS group of every DM group the regulated member creates or joins, prior to sending or receiving any application messages in that group.
2. Re-add the logger if it is removed by another member (see §17.8.3).
3. Notify all other DM group members of the logger's presence before their first message is sent (see §17.8.4).

The client MUST NOT permit the regulated member to send any application message in a DM group until the compliance logger has been admitted to the MLS group and the disclosure notice has been displayed to all members.

#### 17.8.2 MLS Mechanics

Logger addition in a DM group follows the standard MLS Add + Commit path:

1. The regulated member's client fetches a fresh `KeyPackage` for the Space's `loggerDID` from the logger's relay inbox or a published KeyPackage store.
2. The client issues an MLS Add Proposal for the logger DID.
3. The client immediately commits the proposal (no consent threshold applies to compliance logger additions — the regulated member's obligation is unilateral and does not require co-member approval).
4. The client updates the `DMGroupDescriptor` to add the logger DID to the `complianceLoggers` array and publishes the updated descriptor CID.
5. The logger's infrastructure issues a `Welcome` response, completing the logger's admission to the MLS group.

If the regulated member is joining an existing DM group (rather than creating one), steps 2–5 are performed at join time, before the member sends any application messages. Messages sent by other members before the regulated member joined are not retroactively accessible to the logger — the logger's archive begins at the MLS epoch of its admission.

**KeyPackage availability:** The logger's DID document MUST publish a `KeyPackageEndpoint` service entry so that client user agents can fetch fresh KeyPackages programmatically:

```json
{
  "id": "did:key:z6MkLogger...#keypackages",
  "type": "AgoraKeyPackageEndpoint",
  "serviceEndpoint": "https://archive.acme-corp.internal/v1/agora/keypackages"
}
```

The endpoint MUST return a fresh, unused `KeyPackage` on each GET request. Reusing KeyPackages breaks MLS forward secrecy guarantees and is a conformance violation.

#### 17.8.3 Logger Removal Prohibition

Once a compliance logger has been admitted to a DM group by a regulated member, no member — including the regulated member — MAY issue an MLS Remove commit for the logger DID for the duration of the regulatory retention period.

A conformant client for a regulated Space member MUST:

- Refuse to commit an MLS Remove proposal targeting the Space's `loggerDID`.
- On receiving a committed Remove for the Space's `loggerDID` (issued by another DM group member), immediately re-add the logger via the §17.8.2 procedure and notify the regulated member's Space admin of the removal attempt. The re-add creates a new MLS epoch; messages in the epoch between removal and re-add are not captured by the logger. The Space admin MUST be notified so they can assess the compliance gap.

This prohibition is enforced by the regulated member's client. It cannot be enforced protocol-wide — a non-regulated member's client can issue a Remove. The regulated member's client is responsible for detecting and remedying the gap.

DS-level enforcement (§17.8.9) strengthens this guarantee at group creation but does not prevent subsequent logger removal by other group members. The gap between removal and re-add represents a period of non-capture; its duration depends on how quickly the regulated member's client detects the removal event.

#### 17.8.4 Disclosure to DM Group Members

Before any regulated member sends a message in a DM group with a compliance logger present, their client MUST display a disclosure notice to all DM group members. The notice MUST be delivered as a system message visible to all current group members before the first application message in the epoch where the logger is admitted:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ComplianceDisclosureNotice",
  "dmGroupID": "urn:agora:dmgroup:<uuid>",
  "loggerDID": "did:key:z6MkLogger...",
  "loggerLabel": "Acme Corp Compliance Archive",
  "retentionDays": 2555,
  "regulatoryFramework": ["FINRA 17a-4", "SEC 17a-4"],
  "issuedBy": "did:key:z6MkRegulatedMember...",
  "ts": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

The disclosure notice is an MLS application message of type `ComplianceDisclosureNotice` sent in the same epoch as the logger's admission commit, prior to any other application messages. Clients MUST render it as a visible system notification — not a suppressable status line — with wording equivalent to:

> **[Display name of regulated member]'s messages in this conversation are subject to regulatory retention by [loggerLabel] for [retentionDays] days.**

Non-regulated members have no obligation to remain in the DM group after disclosure. They MAY leave the group (via standard MLS Remove self-proposal) at any time. Their messages prior to their departure remain in the compliance logger's archive for the regulated member's retention period.

#### 17.8.5 Multiple Regulated Members in a Single DM Group

If a DM group contains members from two or more compliance-logging Spaces, each regulated member's client MUST add their respective Space's logger DID to the group. The group may have multiple compliance logger DIDs present simultaneously.

Each logger receives the full message stream from its admission epoch forward, regardless of which regulated member's messages it was originally added to capture. A logger from Space A captures messages from Space B members and vice versa — the MLS group membership does not discriminate by sender. This is the correct behavior: both Spaces have independent retention obligations that apply to their respective regulated members' participation in the conversation.

The `complianceLoggers` array in the `DMGroupDescriptor` lists all admitted logger DIDs. Each regulated member's client MUST verify on group join that their Space's logger DID is present in this array, and add it if absent.

#### 17.8.6 Cross-Space DM: Regulated Member with Non-Space Participant

A DM group between a regulated Space member and a participant who has no Space affiliation (or a Space without compliance logging) is treated identically to §17.8.4. The non-space participant receives the same disclosure notice. The compliance obligation applies to the regulated member's participation regardless of the counterparty's affiliation.

#### 17.8.7 Offline and Deferred Join Scenarios

If a regulated member is offline when added to a DM group by another member, the compliance logger addition and disclosure notice MUST be performed by the regulated member's client when they next come online and process the pending MLS Welcome, before their client sends any application messages in the group.

Clients MUST queue the logger addition and disclosure as the first operations to perform on a pending DM group join, ahead of any queued outbound messages. If the client has queued outbound messages (e.g., drafted while offline), those messages MUST NOT be sent until the logger admission commit has been completed and acknowledged.

#### 17.8.8 Audit Trail

The regulated member's Space MUST record each DM group compliance logger admission in its IPLD compliance audit chain. The audit record is a `DMComplianceAuditEntry`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "DMComplianceAuditEntry",
  "dmGroupID": "urn:agora:dmgroup:<uuid>",
  "dmGroupDescriptorCID": "bafyrei...",
  "loggerDID": "did:key:z6MkLogger...",
  "admittedBy": "did:key:z6MkRegulatedMember...",
  "admittedAt": "2026-03-12T00:00:00Z",
  "removalAttempts": [],
  "sig": "base64url..."
}
```

`removalAttempts` is an array of timestamps and initiator DIDs for any Remove commits targeting the logger that the regulated member's client detected and remedied per §17.8.3. This gives the Space admin and compliance officer a complete record of logger presence in DM groups, including any attempted circumvention.

#### 17.8.9 DS-Level Enforcement (Recommended)

Client-side enforcement (§17.8.1–§17.8.2) depends on the regulated member's client being conformant. Two DS-level mechanisms provide enforcement independent of client behavior. **Mechanism B (External Commit) is preferred.**

**Note on relay metadata.** The relay already routes `Welcome` messages to recipient inboxes and therefore already knows which user DIDs are participating in any new group — this is an inherent property of operating as both KDS and DS. DS enforcement does not expose new metadata to the relay; it acts on metadata the relay already holds as part of normal routing.

##### Mechanism A: Welcome Inspection at Group Creation

When the relay receives the initial `Welcome` bundle for a new DM group:

1. The relay maps each `KeyPackageRef` in the `Welcome` envelope to a DID using its KDS index (the relay holds this mapping because it serves as the Key Distribution Service and issued or cached the `KeyPackage` when it was published).
2. If any recipient DID is a regulated member of a compliance-logging Space, the relay verifies the Space's `loggerDID` is also present in the `KeyPackageRef` list.
3. If the `loggerDID` is absent, the relay rejects the group creation with error `COMPLIANCE_LOGGER_REQUIRED` and does not route the `Welcome` to any recipient.

The client must still fetch the logger's `KeyPackage` and include it (steps 1–4 of §17.8.2). What Mechanism A adds is that the relay catches a client that failed to do so — the group simply cannot be created without the logger.

**Coverage: group creation only.** When a regulated member *joins* an existing DM group rather than creating one, there is no new group creation event for the relay to intercept. Client-side enforcement (§17.8.2) applies to the join case under Mechanism A.

**Coupling requirement.** This mechanism requires the relay to operate as both KDS and DS with shared KPRef→DID state. In deployments where KDS and DS are separate infrastructure components, an authenticated query path from DS to KDS is required.

##### Mechanism B: Compliance Logger External Commit (Preferred)

RFC 9420 §11.2.1 defines External Commits: a mechanism by which a new member joins an existing group using the group's `GroupInfo`, without being added by any current member. Because the relay already holds `GroupInfo` for every active group (required for standard group joins), the compliance logger infrastructure can self-join any DM group involving a regulated user with no client involvement.

**Procedure:**

1. The relay creates the new DM group normally, accepting the `Welcome` and routing it to invited members.
2. Before delivering any application messages for the group, the relay checks whether any member DID is a regulated member of a compliance-logging Space.
3. If yes, the relay enters **compliance hold**: application messages for this group are accepted and stored but not delivered until the logger has joined.
4. The relay notifies the compliance logger infrastructure via an authenticated internal event, providing the group's `GroupInfo`.
5. The logger performs an External Commit, joining the group as a passive member (§6.1.3).
6. The relay releases held messages; normal delivery resumes.

The client does not fetch the logger's `KeyPackage`, does not issue the Add commit, and cannot prevent logger admission. This mechanism is independent of client software version and configuration.

**Coverage: creation and join.** The relay applies the same compliance hold procedure when it detects a regulated member joining an existing group (by inspecting the Commit that adds them), not only at group creation.

**Hold timeout.** The relay MUST apply a compliance hold timeout (recommended: 5 seconds; configurable per Space). If the logger does not complete its External Commit within the timeout, the relay MUST NOT release held messages. It MUST surface an alert to the Space admin and compliance officer. The DM group remains in compliance hold until the logger joins or the Space admin takes remedial action. Silent timeout-and-release is a conformance violation.

**Availability: last-resort KeyPackages.** A compliance logger MUST pre-publish a set of last-resort `KeyPackage`s with the relay (per §6.1.3 passive member guidance) so that External Commits can be completed promptly without a live round-trip to the logger's `KeyPackageEndpoint`. The relay SHOULD alert the compliance operator when the last-resort set falls below a configurable threshold. If no `KeyPackage`s are available when a compliance hold fires and the timeout expires, this is a compliance outage that MUST be reported — not a silent capture gap.

**Removal gap.** Neither Mechanism A nor Mechanism B prevents a non-regulated group member from issuing an MLS `Remove` for the logger after admission. The regulated member's client remains responsible for detecting and remedying that removal (§17.8.3). The gap between removal and re-add is an inherent limitation of the current MLS group management model; future DS extension mechanisms may address per-commit enforcement.

#### §17.8 Conformance Summary

The following table summarizes the conformance requirements for DM group compliance logging:

| Requirement | Applies To | MUST / SHOULD |
|---|---|---|
| Add Space `loggerDID` to DM group before first message | Regulated member's client | MUST |
| Fetch fresh KeyPackage per logger addition | Regulated member's client | MUST |
| Display `ComplianceDisclosureNotice` to all DM members before first message | Regulated member's client | MUST |
| Re-add logger if removed by another member | Regulated member's client | MUST |
| Notify Space admin of logger removal attempt | Regulated member's client | MUST |
| Queue logger addition before queued outbound messages on deferred join | Regulated member's client | MUST |
| Publish `DMComplianceAuditEntry` to Space IPLD chain | Regulated member's client | MUST |
| Publish `KeyPackageEndpoint` in logger DID document | Compliance logger operator | MUST |
| Provide fresh (non-reused) KeyPackage per request | Compliance logger operator | MUST |
| Enforce logger inclusion via Welcome inspection at group creation (Mechanism A) | Relay operator (regulated deployment) | SHOULD |
| Enforce logger inclusion via External Commit with compliance hold (Mechanism B, preferred) | Relay operator (regulated deployment) | SHOULD |
| Use DM group for persistent named multi-party private conversation | Any user | SHOULD use private channel instead |


---

