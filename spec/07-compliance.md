# 7. Compliance Logging

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 3621–3938 (§17).


*Binds: CO.*

## 7.1 Overview

Organizations in regulated industries (financial services, healthcare, legal, government) are subject to message retention and audit requirements that conflict with the default Agora model of E2EE with relay-opaque content. Agora supports compliance logging as an **optional, space-level feature** that satisfies these requirements without architectural kludges.

Mechanically, compliance logging is implemented as a **passive member** (§5.2.1.3), a `ComplianceLogger` principal, that silently receives and archives all messages in every MLS group it is admitted to. This applies to Space channels (§4) and Direct Message groups (§4.6) alike. It is structurally identical to a gateway (§9.2) but treated differently at the protocol and UI layers:

- It does not appear as a chat participant in client UI.
- It does not generate join/leave events in the message stream.
- Its presence is disclosed in space metadata and MLS group membership, but not in the message feed.
- It is added to channels automatically when logging is enabled, without requiring per-channel Admin action.

The result is compliant message capture that is cryptographically sound and tamper-evident, without a "Logger Bot joined #engineering" message appearing in every channel.

## 7.2 Enabling Compliance Logging

Compliance logging is enabled in the Space state document by the space owner:

```json
"complianceLogging": {
  "@type": "ComplianceLoggingConfig",
  "schemaVersion": "1",
  "enabled": true,
  "loggerDID": "did:webvh:QmSCID...:compliance.example.com:logger",
  "loggerLabel": "Example Corp Compliance Archive",
  "logStore": "ipfs://bafyrei...",
  "retentionDays": 2555,
  "scope": "all-channels",
  "enabledBy": "did:key:z6MkOwner...",
  "enabledAt": "2026-03-12T00:00:00Z"
}
```

The block carries no signature of its own; it is covered by the space owner's signature on the Space state document (§13.1.1). `loggerDID` is the DID of the compliance logging principal. `logStore` is the IPFS CID root of the compliance log: a content-addressed, append-only IPLD structure. The compliance log and the compliance audit chain (§7.8.8) hold plaintext and member DIDs and are CO data (ARCHITECTURE S8); any copy stored on IO infrastructure MUST be encrypted under a key the CO holds and the IO does not. `retentionDays` is the minimum retention period the logger is obligated to maintain. `scope` is `all-channels` or a list of channel path globs.

The `scope` field governs which Space channels receive the logger. The value `"all-channels"` causes the logger to be added to every channel in the Space, including channels created after compliance logging is enabled. A glob list (e.g., `["engineering/*", "legal/*"]`) limits logging to matching channel paths.

`scope` does **not** govern DM groups. DM group compliance logging is governed entirely by §7.8, which imposes an obligation on the regulated member's user agent independent of Space channel scope configuration.

`regulatedMembers` (optional) is an array of member DIDs that the space owner designates as regulated for the purposes of §7.8:

```json
"regulatedMembers": ["did:key:z6MkRegulatedMember..."]
```

The field is part of the `ComplianceLoggingConfig` and is covered by the Space state signature. Only DIDs listed here are regulated members; membership of a Space with `complianceLogging.enabled: true` does not by itself make a member regulated.

Once `complianceLogging.enabled` is set to `true` and published as Space state (§3.4), conformant clients MUST add the `loggerDID` to the MLS group of every channel matching `scope` on the next available Commit. This addition IS recorded in the MLS group membership (verifiable by any MLS-aware client) but MUST NOT produce a UI-visible join notification.

Disabling compliance logging requires a signed Space state mutation by the space owner. Clients remove the logger DID from channel MLS groups via Remove commits. The `complianceLogging` history in the IPLD space state chain retains a permanent record of when logging was enabled and disabled.

## 7.3 Logger Principal

The `ComplianceLogger` is a DID-identified principal operated by the space's compliance infrastructure, typically an on-premise archival system or a regulated third-party compliance service (e.g., a FINRA-registered archiving vendor).

The logger is a CO component (ARCHITECTURE §2.3, S8). It MUST run under CO control, with its own DID and keys, and is never a function or configuration option of a relay or other IO component. Where it is co-located on IO hardware, that is a contract under which the IO acts as the CO's processor; the logger remains a CO principal.

The logger's DID document identifies it as a compliance logger:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:compliance.example.com:logger",
  "verificationMethod": [{
    "id": "did:webvh:QmSCID...:compliance.example.com:logger#key-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:webvh:QmSCID...:compliance.example.com:logger",
    "publicKeyMultibase": "z6MkLogger..."
  }],
  "service": [{
    "id": "did:webvh:QmSCID...:compliance.example.com:logger#compliance",
    "type": "AgoraComplianceLogger",
    "serviceEndpoint": "https://archive.example.com/v1/agora/compliance",
    "operator": "Example Corp Legal",
    "regulatoryFramework": ["FINRA 17a-4", "SEC 17a-4"]
  }]
}
```

`regulatoryFramework` is an informational array of the regulatory requirements under which the logger operates. Clients MAY display this to members who inspect the space's compliance configuration.

The logger operates as a passive member (§5.2.1.3). It holds leaf credentials, participates in epoch ratchets, and receives a `Welcome` from the committing member when added to a group. Its only part in its own admission is supplying a `KeyPackage` (§7.8.2). It does not send messages, publish presence events, generate typing indicators, or issue Commits or Proposals.

## 7.4 Log Record Format

Every message received by the logger is written as a signed `ComplianceRecord` to the IPLD log:

```json
{
  "@type": "ComplianceRecord",
  "channel": "agora://bafyrei.../engineering/backend",
  "senderDID": "did:key:z6MkSender...",
  "epoch": 17,
  "seq": 1042,
  "ts": "2026-03-12T12:00:00.000Z",
  "plaintextPayload": "base64url...",
  "outerEnvelopeCID": "bafyrei...",
  "prevRecordCID": "bafyrei..."
}
```

`plaintextPayload` is the decrypted inner payload envelope (§13.1), for example a JMAP Chat `Message` (§5.2.3), base64url-encoded from the exact bytes received. `outerEnvelopeCID` links the compliance record to the tamper-evident message history. A `ComplianceRecord` is verified outside the MLS group, so it is signed per §13.1.1 by the logger DID: the JWS is carried in the record's envelope `sig`, not in the body. `prevRecordCID` chains records into a linked list, making the log append-only and tamper-evident: inserting or deleting a record breaks the chain.

The log is organized as a per-channel IPLD DAG, with a space-level index mapping channel CIDs to their respective log chain heads.

## 7.5 Ephemeral Message and Expiry Handling

Ephemeral messages (`ChatTypingEvent`, `ChatPresenceEvent`, `ParticipantState`; §5.2.3) are never logged; they are excluded by type at the logger.

Messages with a `senderExpiresAt` field (§5.2.4) present a deliberate tension: the sender expressed an intent for the message to be deleted, but the compliance obligation may override that intent. The resolution is explicit and must be disclosed:

- If `complianceLogging.enabled` is `true`, message expiry is honored for relay caches and client display, but the compliance logger retains the plaintext for `retentionDays` regardless of the sender's `senderExpiresAt` value. This applies equally in DM groups where a compliance logger is present under §7.8: the DM group member's expiry preference is honored in relay caches and client display, but the compliance logger retains the plaintext for the regulated member's `retentionDays` regardless.
- The Space state document MUST include a human-readable `retentionNotice` field when compliance logging is enabled:

```json
"retentionNotice": "This space is subject to regulatory message retention. Messages are archived for 2555 days regardless of expiry settings."
```

- Clients MUST display this notice to members when they first join a compliance-logging-enabled space, and MUST make it accessible from the space's information panel at any time.

The sender's expiry preference is preserved in the client and relay layers; the compliance layer overrides it with explicit disclosure.

## 7.6 Voice and Video Compliance Logging

VTC compliance recording is governed by the `RecordingGrant` mechanism and the `VTCComplianceConfig` space configuration, both fully specified in §6.12.

**Relationship to text compliance logging.** Text compliance logging (§7.1–§7.5) and VTC compliance recording (§6.12) are parallel mechanisms operating over the same MLS group. They are separately authorized and separately archived, but both feed into the same space IPLD compliance audit chain. A space with both `complianceLogging.enabled: true` and `vtcCompliance.enabled: true` captures the complete communication record (text, reactions, edits, deletions, and voice/video) in a unified, tamper-evident audit chain.

**Scope.** §7.1–§7.5 cover: text messages in space channels, reactions, edit events, delete events, file attachments, and DM text messages for regulated members (§7.8). §6.12 covers: audio and video media streams in space voice channels and DM voice groups for regulated members (§6.12.7).

**Same logger DID or separate.** The `complianceLogging.loggerDID` and `vtcCompliance.recorderDID` MAY be the same DID or different DIDs. Using the same DID is operationally simpler but requires the compliance principal to support both text archiving (passive member, §5.2.1.3) and VTC recording (admission to call groups and media decryption, §6.12.2). Using separate DIDs allows specialist infrastructure for each function. Either configuration is conformant.

**`retentionDays` alignment.** The `vtcCompliance.retentionDays` SHOULD match `complianceLogging.retentionDays` to avoid a regulatory gap where text records are retained longer than corresponding voice records of the same conversation. If they differ, the longer value governs the overall retention obligation for the channel.

## 7.7 Member Disclosure

Compliance logging is not hidden from members. It is disclosed in space metadata and MLS group membership (which is visible to any technically capable member). Conformant clients MUST:

- Display a compliance logging indicator in the space information panel when `complianceLogging.enabled` is `true`.
- Display the `retentionNotice` to new members on first join.
- Allow members to inspect the full `ComplianceLoggingConfig` including `loggerDID`, `loggerLabel`, `retentionDays`, and `regulatoryFramework` from the space settings UI.
- NOT display a join/leave notification in any channel's message feed when the logger DID is added or removed from an MLS group.

The logger's MLS group membership is visible to any client that inspects raw MLS group state. This is intentional: the logger is UI-silent but not cryptographically hidden. A technically capable member can always verify that a compliance logger is present.

Adding a compliance logger to a Space channel or a DM group is governed by the CO's compliance policy and by the disclosure requirements of this section and §7.8.4, not by member consent. No consent threshold (§4.6) applies to a logger addition. A member who does not accept the retention MAY leave the group.

In DM groups where a compliance logger is present under §7.8, disclosure obligations are governed by §7.8.4 rather than this section. The Space information panel disclosure requirements in this section apply only to Space channels.

## 7.8 Compliance Logging for Direct Message Groups

### 7.8.1 Obligation

A regulated member is a Space member whose DID the space owner lists in `complianceLogging.regulatedMembers` (§7.2) while `complianceLogging.enabled` is `true`. Regulated status is an explicit CO designation per user; it MUST NOT be inferred from membership of a logging-enabled Space. A regulated member carries that compliance obligation into every DM group they participate in, regardless of whether the DM group has any Space affiliation.

The compliance obligation follows the regulated user, not the channel. A regulated user who conducts business communication via DM is not exempt from their Space's retention requirements by virtue of using a DM group rather than a Space channel.

A conformant client for a regulated Space member MUST:

1. Add the Space's `loggerDID` to the MLS group of every DM group the regulated member creates or joins, prior to sending or receiving any application messages in that group.
2. Re-add the logger if it is removed by another member (see §7.8.3).
3. Notify all other DM group members of the logger's presence before their first message is sent (see §7.8.4).

The client MUST NOT permit the regulated member to send any application message in a DM group until the compliance logger has been admitted to the MLS group and the disclosure notice has been displayed to all members. This client is the enforcement point for DM capture (§7.8.9); on CO-managed devices the CO SHOULD configure it so the user cannot disable this check.

### 7.8.2 MLS Mechanics

Logger addition in a DM group follows the standard MLS Add + Commit path:

1. The regulated member's client fetches a fresh `KeyPackage` for the Space's `loggerDID` from the logger's `KeyPackageEndpoint` (below).
2. The client issues an MLS Add Proposal for the logger DID.
3. The client immediately commits the proposal. No consent threshold applies (§7.7).
4. The client, as committer, delivers the MLS `Welcome` by POST to the logger's `KeyPackageEndpoint`, completing the logger's admission to the MLS group. The logger does not issue a `Welcome`; it only supplies the `KeyPackage`.
5. The client updates the `DMGroupDescriptor` to add the logger DID to the `complianceLoggers` array and sends the updated descriptor to the group (§4.6).

If the regulated member is joining an existing DM group (rather than creating one), steps 2–5 are performed at join time, before the member sends any application messages. Messages sent by other members before the regulated member joined are not retroactively accessible to the logger; the logger's archive begins at the MLS epoch of its admission.

**KeyPackage availability:** The logger's DID document MUST publish a `KeyPackageEndpoint` service entry (§2.1) so that client user agents can fetch fresh KeyPackages programmatically:

```json
{
  "id": "did:webvh:QmSCID...:compliance.example.com:logger#keypackages",
  "type": "AgoraKeyPackageEndpoint",
  "serviceEndpoint": "https://archive.example.com/v1/agora/kp/logger"
}
```

The endpoint follows §5.2.1.1. It MUST return a fresh, unused `KeyPackage` on each fetch, never a last-resort KeyPackage, and MUST accept a `Welcome` by POST. The logger operator is the CO, so this endpoint is CO-hosted and the CO's knowledge of which groups admit its logger is not an IO observation. Reusing KeyPackages breaks MLS forward secrecy guarantees and is a conformance violation.

### 7.8.3 Logger Removal Prohibition

Once a compliance logger has been admitted to a DM group by a regulated member, no member, including the regulated member, MAY issue an MLS Remove commit for the logger DID for the duration of the regulatory retention period.

A conformant client for a regulated Space member MUST:

- Refuse to commit an MLS Remove proposal targeting the Space's `loggerDID`.
- On receiving a committed Remove for the Space's `loggerDID` (issued by another DM group member), immediately re-add the logger via the §7.8.2 procedure and notify the regulated member's Space admin of the removal attempt. The re-add creates a new MLS epoch; messages in the epoch between removal and re-add are not captured by the logger. The Space admin MUST be notified so they can assess the compliance gap.

This prohibition is enforced by the regulated member's client. It cannot be enforced protocol-wide: a non-regulated member's client can issue a Remove. The regulated member's client is responsible for detecting and remedying the gap.

The gap between removal and re-add represents a period of non-capture; its duration depends on how quickly the regulated member's client detects the removal event. The logger records the gap (§7.8.9).

### 7.8.4 Disclosure to DM Group Members

Before any regulated member sends a message in a DM group with a compliance logger present, their client MUST display a disclosure notice to all DM group members. The notice MUST be delivered as a system message visible to all current group members before the first application message in the epoch where the logger is admitted:

```json
{
  "@type": "ComplianceDisclosureNotice",
  "dmGroupID": "urn:agora:dmgroup:<uuid>",
  "loggerDID": "did:webvh:QmSCID...:compliance.example.com:logger",
  "loggerLabel": "Example Corp Compliance Archive",
  "retentionDays": 2555,
  "regulatoryFramework": ["FINRA 17a-4", "SEC 17a-4"],
  "ts": "2026-03-12T00:00:00Z"
}
```

The disclosure notice is an MLS application message of type `urn:agora:type:ComplianceDisclosureNotice` (§5.2.3) sent in the same epoch as the logger's admission commit, prior to any other application messages. It carries no object signature; the MLS sender signature of the regulated member authenticates it (§13.1.1). Clients MUST render it as a visible system notification (not a suppressable status line) with wording equivalent to:

> **[Display name of regulated member]'s messages in this conversation are subject to regulatory retention by [loggerLabel] for [retentionDays] days.**

Non-regulated members have no obligation to remain in the DM group after disclosure. They MAY leave the group (via standard MLS Remove self-proposal) at any time. Their messages prior to their departure remain in the compliance logger's archive for the regulated member's retention period.

### 7.8.5 Multiple Regulated Members in a Single DM Group

If a DM group contains members from two or more compliance-logging Spaces, each regulated member's client MUST add their respective Space's logger DID to the group. The group may have multiple compliance logger DIDs present simultaneously.

Each logger receives the full message stream from its admission epoch forward, regardless of which regulated member's messages it was originally added to capture. A logger from Space A captures messages from Space B members and vice versa; the MLS group membership does not discriminate by sender. This is the correct behavior: both Spaces have independent retention obligations that apply to their respective regulated members' participation in the conversation.

The `complianceLoggers` array in the `DMGroupDescriptor` lists all admitted logger DIDs. Each regulated member's client MUST verify on group join that their Space's logger DID is present in this array, and add it if absent.

### 7.8.6 Cross-Space DM: Regulated Member with Non-Space Participant

A DM group between a regulated Space member and a participant who has no Space affiliation (or a Space without compliance logging) is treated identically to §7.8.4. The non-space participant receives the same disclosure notice. The compliance obligation applies to the regulated member's participation regardless of the counterparty's affiliation.

### 7.8.7 Offline and Deferred Join Scenarios

If a regulated member is offline when added to a DM group by another member, the compliance logger addition and disclosure notice MUST be performed by the regulated member's client when they next come online and process the pending MLS Welcome, before their client sends any application messages in the group.

Clients MUST queue the logger addition and disclosure as the first operations to perform on a pending DM group join, ahead of any queued outbound messages. If the client has queued outbound messages (e.g., drafted while offline), those messages MUST NOT be sent until the logger admission commit has been completed and acknowledged.

### 7.8.8 Audit Trail

The regulated member's Space MUST record each DM group compliance logger admission in its IPLD compliance audit chain. The audit record is a `DMComplianceAuditEntry`:

```json
{
  "@type": "DMComplianceAuditEntry",
  "dmGroupID": "urn:agora:dmgroup:<uuid>",
  "dmGroupDescriptorCID": "bafyrei...",
  "loggerDID": "did:webvh:QmSCID...:compliance.example.com:logger",
  "admittedBy": "did:key:z6MkRegulatedMember...",
  "admittedAt": "2026-03-12T00:00:00Z",
  "removalAttempts": []
}
```

A `DMComplianceAuditEntry` is verified outside the MLS group and is signed per §13.1.1 by `loggerDID`, the writer of the compliance audit chain, with the JWS in its envelope `sig`. `admittedBy` is the MLS sender of the Commit that added the logger.

`removalAttempts` is an array of timestamps and initiator DIDs for any Remove commits targeting the logger that the regulated member's client detected and remedied per §7.8.3. This gives the Space admin and compliance officer a complete record of logger presence in DM groups, including any attempted circumvention.

### 7.8.9 Enforcement Points and Capture Gaps

DM compliance capture is enforced only at CO enforcement points (ARCHITECTURE §6.3): the regulated member's client, the compliance logger, and the CO's archive and audit pipeline. Relays and other IO components do not know DM group participants or which users are regulated (S1), and MUST NOT inspect Welcomes, hold messages, or otherwise enforce logger presence (S2).

- The regulated member's client MUST NOT send any application message into a DM group whose current MLS membership lacks the Space's `loggerDID` (§7.8.1). Regulated members SHOULD communicate from CO-managed devices, where the CO controls the client and its configuration.
- The compliance logger MUST record every capture gap it can detect in the Space's IPLD compliance audit chain, including its own removal from a group (the epoch of the Remove commit) and its re-admission (the epoch of the re-add), so the missing epochs are identified. It records each gap as a `ComplianceGapEntry`, signed per §13.1.1 by `loggerDID`:

```json
{
  "@type": "ComplianceGapEntry",
  "dmGroupID": "urn:agora:dmgroup:<uuid>",
  "loggerDID": "did:webvh:QmSCID...:compliance.example.com:logger",
  "removedAtEpoch": 41,
  "readmittedAtEpoch": 43,
  "detectedAt": "2026-03-12T00:00:00Z"
}
```

For a Space channel, `channel` (the channel path URI, as in `ComplianceRecord`) replaces `dmGroupID`. `readmittedAtEpoch` is `null` while the logger has not been re-admitted.
- The CO's audit pipeline SHOULD reconcile `DMComplianceAuditEntry` records (§7.8.8) against the groups the logger actually holds and alert the compliance officer to discrepancies.

**Accepted cost.** A modified or non-conformant client can create or join a DM group without the logger, and no infrastructure component will stop it; such groups are invisible to the logger. The mitigation is the managed endpoint, the same trust boundary regulated firms already rely on for every other channel (ARCHITECTURE §9).

#### §7.8 Conformance Summary

The following table summarizes the conformance requirements for DM group compliance logging:

| Requirement | Applies To | MUST / SHOULD |
|---|---|---|
| Add Space `loggerDID` to DM group before first message | Regulated member's client | MUST |
| Fetch fresh KeyPackage per logger addition | Regulated member's client | MUST |
| Display `ComplianceDisclosureNotice` to all DM members before first message | Regulated member's client | MUST |
| Re-add logger if removed by another member | Regulated member's client | MUST |
| Notify Space admin of logger removal attempt | Regulated member's client | MUST |
| Queue logger addition before queued outbound messages on deferred join | Regulated member's client | MUST |
| Publish `DMComplianceAuditEntry` to Space IPLD chain | Compliance logger | MUST |
| Publish `KeyPackageEndpoint` in logger DID document | Compliance logger operator | MUST |
| Provide fresh (non-reused) KeyPackage per request | Compliance logger operator | MUST |
| Refuse to send in a DM group lacking the logger | Regulated member's client | MUST |
| Send `Welcome` to the logger's `KeyPackageEndpoint` when committing its Add | Committing client | MUST |
| Accept `Welcome` by POST at the `KeyPackageEndpoint` | Compliance logger operator | MUST |
| Record detectable capture gaps in the compliance audit chain | Compliance logger | MUST |
| Use DM group for persistent named multi-party private conversation | Any user | SHOULD use private channel instead |


---

