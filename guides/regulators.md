# Agora Protocol: Examiner's Reference Guide

**Audience:** FINRA, SEC, FCA, BaFin, and MiFID II examination staff; supervisory technology analysts; enforcement counsel
**Companion document:** `guides/counsel.md` (for the regulated firm's compliance team and counsel)
**Purpose:** How Agora's communications archive works, what an examination will find, how to verify authenticity, and what a regulated firm is and is not required to produce
**Document version:** Aligned to the Agora Protocol Specification 0.2 (Draft, `spec/`) and `ARCHITECTURE.md` (2026-10-16). Section references are to those documents. No conformant implementation exists yet.

---

> **Preliminary note.** This document describes the technical architecture of the Agora open communication protocol from the perspective of regulatory examination. It is not legal advice and does not create regulatory obligations. Whether a specific Agora deployment satisfies a particular regulatory requirement depends on applicable law and regulatory interpretation in the relevant jurisdiction.

---

## Part 1: What Agora Is and How It Differs From Conventional Platforms

### The Core Architecture

Agora is an open protocol for end-to-end encrypted (E2EE) group communication. In Microsoft Teams, Slack, or Bloomberg Terminal, the platform operator holds message encryption keys and can produce plaintext in response to a subpoena. Agora's architecture prevents any server from reading message content.

This follows from the encryption design itself, independent of any policy or contractual commitment.

**Two operators, two roles.** Agora separates the party that runs infrastructure from the party that runs the communications (ARCHITECTURE §1-§2):

- An **infrastructure operator** runs relays, storage pinning, media servers, and push proxies. It carries ciphertext, decides nothing about any community, and can be replaced without changing the firm's identities, membership, history, or policy.
- The **communications operator** is the regulated firm itself. It holds identity provisioning, membership, roles, policy, compliance logging, and the archive. Every authority over the firm's communications is exercised with the firm's keys.

A firm may run its own relays, in which case it fills both roles with distinct keys (ARCHITECTURE §2.4). The relay still holds only what any relay holds.

**Key architectural elements for examiners:**

**MLS encryption (RFC 9420).** The sender's device encrypts every message before it leaves that device. Relays receive and route ciphertext only. A relay does not hold decryption keys and cannot produce message plaintext.

**Compliance logger.** The obvious examination concern is how a regulator can examine communications the servers cannot read. The answer is the compliance logger: a firm-operated system with its own cryptographic identity, admitted as a member of every covered message group (spec §7). Like any other group member, it receives and can decrypt every message. Unlike human members, it archives each decrypted message to a tamper-evident, content-addressed record store that only the firm (or its contracted compliance vendor, acting for the firm) controls. The logger always runs under the firm's control. It is never a relay function or a relay configuration option (ARCHITECTURE S8; spec §7.3).

**IPLD content-addressed archive.** The compliance archive uses IPLD (InterPlanetary Linked Data), a data structure in which every record is identified by a cryptographic hash of its contents. Altering or deleting a record breaks the hash chain, so alteration is detectable without relying on access controls alone.

**Practical consequence.** An examination of a firm using Agora obtains message content from the firm's own compliance archive, with no third-party platform operator involved. The examination access model is the same as for firms that self-host their communication archives.

### Why This Architecture Matters for Examiners

**It addresses the DM capture gap at the firm's endpoints.** FINRA and SEC examinations have found, with increasing frequency, that regulated employees conduct business communications via personal messaging applications (WhatsApp, Signal, iMessage, personal SMS) that firm archiving systems do not capture. Policy prohibition has not been effective. In Agora, a regulated employee's capture obligation follows them into every direct message conversation (spec §7.8.1). The regulated employee's client adds the compliance logger to the DM group automatically and will not send a message into a group that lacks it.

**Enforcement sits at the firm's endpoints.** Relays do not know who is in a group or who is regulated, so they cannot and do not enforce capture (spec §7.8.9). Enforcement happens at the firm's own enforcement points: the client software on managed devices the firm issues and controls, the compliance logger, and the firm's archive and audit pipeline (ARCHITECTURE §6.3). The accepted cost is that a tampered or non-conformant client can create a group without the logger, and no infrastructure component will stop it (ARCHITECTURE §9). The mitigation is the managed endpoint, the same trust boundary firms rely on for every other channel.

**It does not address non-Agora communications.** Agora does not capture business communications a regulated employee conducts on another platform. Firms should be expected to document residual risk from non-Agora channels.

**The relay is not the archive.** A demand served on a relay operator produces connection metadata within its declared retention window and opaque ciphertext, with no message content, sender identity, membership, or channel structure (ARCHITECTURE §4). The firm's compliance archive is the authoritative record for any regulated community and the appropriate subject of an examination document request.

---

## Part 2: The Compliance Archive: What It Contains and How to Read It

### Archive Contents

A properly configured Agora compliance archive contains the following for every covered communication:

**Text messages.** Each chat message is a JMAP Chat `Message` object (spec §5.2.3), archived as the exact bytes the sender's device produced. Message text is in its original format, normally CommonMark, readable as plain text (spec §5.2.7.3). Each record includes:
- The sender's decentralized identifier (DID), a cryptographic identifier that maps to a named employee in the firm's identity system
- Timestamp (UTC, millisecond precision)
- Channel identifier
- MLS epoch and sequence number (establishing order within the group)
- Edits: each edit is a separate `Message` record referencing the original; the original and every version are preserved
- Deletions: a deletion is a separate record carrying the deletion timestamp, sent by the original sender (or, for moderation, by an administrator); the original message record remains in the archive

**File attachments and media.** Stored by content hash (CID). The same hash identifies the file wherever it is stored. If the content hash of a file produced in a proceeding matches the hash in the original conversation, the file has not been altered.

**Reactions.** Emoji responses to messages are JMAP Chat `Reaction` objects carried as ordinary group messages and archived identically to text messages.

**Direct messages.** DM groups involving regulated employees are subject to compliance capture (spec §7.8). The archive contains the full text of those DMs, including conversations with external counterparties, subject to the disclosure requirements in Part 4.

**Voice and video call records.** When voice/video compliance recording is enabled (spec §6.12), the archive contains:
- Opus audio (Ogg or WebM) and, where in scope, WebM video recordings of covered calls, sealed at rest to a key the firm's recorder holds
- Per-call metadata: participants, join/leave timestamps, call duration
- A tamper-evident chain of `VTCComplianceRecord` entries (spec §6.12.4)
- A `VTCComplianceAuditEntry` per call, listing any epochs of the call that were not captured (spec §6.12.6)

**Audit records.** The firm's compliance audit chain includes a `DMComplianceAuditEntry` for each DM group the logger was admitted to, with a list of any removal attempts (timestamp and the identity of the party who made the attempt), and gap records written by the logger identifying epochs it did not capture (spec §7.8.8, §7.8.9).

### Archive Format and Structure

The archive is a sequence of `ComplianceRecord` objects (spec §7.4) in a per-channel IPLD structure, with a Space-level index pointing to the head of each channel's chain. Each record is a signed envelope: a typed payload envelope (spec §13.1) whose body is the record and whose `sig` field holds the logger's JWS signature (spec §13.1.1). The record body contains:

```
ComplianceRecord {
  envelopeID         // identifier of the archived message
  channel            // identifies the channel
  senderDID          // the sender's cryptographic identifier
  epoch              // MLS group epoch at the time of the message
  seq                // sender's sequence number within the channel
  ts                 // UTC, millisecond precision
  plaintextPayload   // the decrypted message envelope, exact bytes as received
                     // (for chat, a JMAP Chat Message)
  outerEnvelopeCID   // hash of the encrypted message as it travelled
  prevRecordCID      // hash of the immediately preceding record in the chain
}
sig                  // logger's JWS signature over the record bytes
```

The `prevRecordCID` field creates a hash-linked chain. Altering or deleting a record, or inserting one out of order, breaks the chain at that point. Chain verification requires only the chain head and the records themselves; no trusted third party is involved.

### How to Verify Archive Integrity

**Step 1: Obtain the chain heads.** The archive's Space-level index names the current head of each channel's chain. The protocol does not require periodic publication of heads; firms should record them at regular intervals (daily or weekly is typical) in a system independent of the archive. For examination purposes, request that log of recorded heads alongside the archive export.

**Step 2: Verify the chain.** Each record's CID is the hash of the signed record envelope as stored (spec §13.1). Starting from a recorded head, verify that each record's `prevRecordCID` equals the CID of the record before it. A complete chain from the oldest record to the head, with all hashes matching, shows that no record in that range was altered or deleted.

**Step 3: Verify logger signatures.** Each record carries the compliance logger's JWS signature in its envelope (spec §13.1.1). The logger's public key is published in its DID document. A valid signature confirms the firm's logger produced the record and that nobody altered its bytes afterwards.

**What a broken chain means.** If the hash chain is broken between records at time T1 and T2, one of the following occurred: (a) a record was altered after archiving, (b) a record was deleted from the chain, or (c) records were inserted out of order. The firm is required to investigate and disclose a broken chain before producing records in a proceeding. Examiners should treat an unexplained chain break as a material compliance deficiency.

---

## Part 3: Requesting Records in an Examination

### What to Request From the Firm

A standard Agora records request should include:

1. **The compliance archive export** for the relevant custodians, date range, and channels. Archive exports can be filtered by:
   - Sender DID (maps to named employees; request the DID-to-employee mapping separately)
   - Channel identifier
   - Date range
   - Message type (text, file, reaction, DM, voice)

2. **The DID-to-employee mapping.** The archive identifies each employee by DID. For firm-provisioned identities, each DID contains a stable local identifier that the firm never reassigns to another person and never derives from a name or email address (spec §2.5.2). The firm's provisioning service holds the mapping from that identifier to the employee's directory record. Request the mapping, with job title and employment period, as a separate document.

3. **The chain integrity verification report.** A report, produced by tooling independent of the archive, that the `prevRecordCID` chain is intact and every logger signature verifies for the exported date range.

4. **The logger's DID document.** The public key document for the compliance logger, needed to verify logger signatures on the records.

5. **The log of recorded chain heads.** The firm's historical record of chain heads with timestamps. Cross-referencing archive content against this log confirms that no records were added, altered, or removed retroactively.

6. **DM compliance audit records.** All `DMComplianceAuditEntry` records for relevant custodians, showing logger admission to DM groups and any removal attempts, and the logger's gap records.

7. **VTC compliance records.** If voice/video communications are within scope: call recordings, per-call metadata, and `VTCComplianceAuditEntry` records for the relevant period.

8. **Space state history.** The current and historical configuration of the firm's Agora workspace (a "Space"), signed with the firm's keys and served from the firm's own Space endpoint (spec §3.4). It shows the compliance logging settings, the explicit list of regulated employees (`regulatedMembers`), scope, retention period, and when compliance logging took effect.

### What You Cannot Get From a Relay Operator

Do not issue production requests to relay operators for message content. A conformant relay operator (spec §10.4.1):
- Does not hold decryption keys
- Cannot read any message content
- Cannot identify the sender of any message (sender identity is inside the encryption)
- Does not know who is in any group, or which users are regulated
- Cannot map routing tokens to a channel or Space
- Does not authenticate users and keeps no user accounts

A relay operator's accurate response to a production request for message content is that it holds encrypted data it cannot decrypt. This is expected. Message content is available only from the firm's compliance archive.

### What a Relay Operator Can Produce

A demand on a relay operator yields only what falls within its observation budget (ARCHITECTURE §4-§5):
- Network-layer connection metadata (source address, timing, volume) for the retention period set in its service agreement with the firm and declared publicly in its relay manifest (`observationBudget.connectionLogRetentionDays`, spec §10.2.1)
- Opaque ciphertext, its size and timing, and the rotating routing tokens it was addressed to
- The identity of each customer it holds a service agreement with (the customer's billing DID), and quota counters per agreement
- For push proxies, opaque device push handles and wake-up timing

From these a relay operator can say which network addresses used a given firm's service. It cannot say which Space, channel, or sender any traffic belonged to: the firm's agreement names no Space or channel, and the billing identity never appears in any Space record (ARCHITECTURE §6.1). If a firm runs several Spaces through one relay, the relay cannot tell them apart.

---

## Part 4: Direct Message Compliance: The Examiner's View

### The Structural Mechanism

The DM compliance problem in regulated communications is well documented: employees who use personal messaging applications for business communications produce records their firm cannot archive. Policy prohibition has been ineffective because it relies on employee compliance instead of technical enforcement.

Agora addresses this in the client software. A regulated employee is one the firm lists by DID in `regulatedMembers` in its signed Space state; membership of a logging-enabled Space does not by itself make anyone regulated (spec §7.2, §7.8.1). When a regulated employee's Agora client creates or joins any DM group, whether the counterparty uses Agora or another platform accessed through a firm-operated bridge, the client:

1. Fetches a fresh cryptographic credential for the firm's compliance logger from the logger's own endpoint, which the firm hosts
2. Adds the logger to the DM group as a group member with full decryption rights
3. Sends a mandatory disclosure notice to all other DM participants before any message is sent

The client will not send any message into the group until both steps are complete (spec §7.8.1). The compliance logger then receives and archives every subsequent message in that DM group to the same tamper-evident archive as Space channel messages.

**This is an endpoint control.** On a managed device, the regulated employee cannot disable it. The DM counterparty cannot prevent it, though they can leave the group after receiving the disclosure. No member may remove the logger during the retention period: if another participant removes it, the regulated employee's client re-adds it and notifies the firm's Space administrator, and the removal is recorded in the `DMComplianceAuditEntry` (spec §7.8.3). The messages sent between removal and re-add are not captured; the logger records the missing epochs (spec §7.8.9).

The control depends on the regulated employee's client being conformant. Relays play no part and cannot detect a group that lacks the logger.

### What the Archive Shows for DM Compliance

For any DM group involving a regulated employee, the archive contains:

- The full text of all messages from the time the logger was admitted
- The compliance disclosure notice sent to all participants
- The identity of all participants (DIDs and, for external counterparties, their display identities)
- Any removal attempts, listed in the group's `DMComplianceAuditEntry` with the timestamp and identity of the party who attempted the removal, and the logger's record of any uncaptured epochs

**Gap: pre-join messages.** The compliance logger is added when the regulated employee joins the DM group. Messages sent in that group before then are not captured. This is inherent to MLS group encryption: the logger cannot decrypt messages from before it was a group member.

**Gap: non-Agora applications.** DM compliance applies to conversations conducted via Agora (including bridged conversations where the counterparty uses Slack, Teams, or a MIMI-compatible platform). If the regulated employee conducts the same conversation via WhatsApp, iMessage, or another non-Agora application, Agora does not capture it.

**Gap: tampered clients.** A modified client can join or create a DM group without the logger. Such a group is invisible to the logger. The firm's controls here are managed devices and reconciliation of audit records against the groups the logger actually holds (spec §7.8.9).

### What an Examiner Should Check

When examining a firm's DM compliance program:

1. **Confirm the logger is configured.** The Space state should show `complianceLogging.enabled: true`, a valid `loggerDID`, and a `regulatedMembers` list that includes every employee the firm treats as regulated.

2. **Verify DM audit records are being generated.** Request `DMComplianceAuditEntry` records for the examination period. Their existence confirms the logging mechanism is active.

3. **Check for removal attempts.** Review the `removalAttempts` lists. Removal attempts are a compliance concern and should be investigated: who attempted to remove the logger, and what was said in the uncaptured epochs?

4. **Look for gaps.** The absence of DM records for a regulated employee during a period when DM activity is otherwise documented is a potential gap. The employee may have used a non-Agora application or an unmanaged device, or compliance logging may not have been active at the time.

5. **Verify disclosure notices were sent.** For each DM group in the archive, a `ComplianceDisclosureNotice` should precede any application message in the epoch where the logger was admitted (spec §7.8.4). A missing disclosure notice suggests a configuration problem or a non-conformant client.

6. **Verify reconciliation.** Ask for evidence that the firm's audit pipeline reconciles `DMComplianceAuditEntry` records against the groups the logger holds and alerts the compliance officer to discrepancies.

---

## Part 5: Cryptographic Verification: A Non-Technical Summary

Examiners do not need to perform cryptographic verification themselves. Archive verification tooling can check the chain and signatures automatically and produce a report readable by non-technical staff. This section explains what is being verified and why it matters.

### Why Cryptographic Verification Is Stronger Than Access Controls

Conventional communication archives (for example, Exchange Online in-place holds, or Bloomberg message archiving) prevent alteration through access controls: only authorized users can access the archive, and the archive system logs administrative actions. The archive's integrity depends on whether the access controls and audit logs are trustworthy.

In Agora's archive, each record contains the cryptographic hash of the previous record. A hash is a mathematical fingerprint: changing a single character in a record changes its hash completely. Because each record's hash is embedded in the next record, any alteration breaks the chain at that point, and anyone can detect the break without consulting the firm, the archive vendor, or any authority.

**Practical consequence for examinations.** A firm cannot silently delete or alter an archived message and produce a clean archive that passes verification against previously recorded chain heads. A deletion produces a chain break, which the firm is required to investigate and disclose before producing records. A chain break the firm cannot explain is a material compliance event.

### What Logger Signatures Prove

Each `ComplianceRecord` is a signed envelope: the compliance logger signs the exact bytes of the record with a standard JWS signature (spec §13.1.1). The logger's public key is in its DID document, published independently of the archive. As a result:

- You can verify that the firm's designated compliance logger produced each record and that nobody altered it after the fact
- You can verify the signature without trusting the firm's archive infrastructure
- A record whose signature does not verify against the logger's public key was either altered or produced by a different system

The archived message inside each record also carries proof of where it came from: `outerEnvelopeCID` is the hash of the encrypted message as it travelled through the network.

### The Role of the Chain Heads

The head of each chain commits to every record before it. If the firm records chain heads at regular intervals in a system independent of the archive (for example, a separate audit log or a public timestamp service), an examiner can verify that the current archive is internally consistent and also that it matches the archive as it existed on any prior date when a head was recorded.

A firm with chain heads recorded in an independent system, and a chain that verifies against all of them, has an archive that is tamper-evident over its entire history. `profiles/compliance-chain-witness.md` describes a suggested practice: signed chain-head records deposited with an independent witness such as an RFC 3161 timestamping authority.

---

## Part 6: Regulatory Framework: The Examiner's Perspective

### FINRA Rule 4511 / SEC Rule 17a-4

**Requirement summary.** Six-year retention (two years in accessible storage) for most records; seven years for certain records. Non-erasable, non-alterable storage (WORM). Ability to produce records promptly.

**What Agora provides.** The IPLD hash chain makes alteration detectable. The Space state sets the retention period (`retentionDays`). The firm owns the archive, with no third-party platform operator involved, which supports the control requirement.

**What to verify in an examination.**
- `retentionDays` is set to ≥ 2555 (7 years)
- Archive pruning is suspended for any records subject to legal hold
- The archive backend (the storage system the compliance logger writes to) is configured to prevent administrative deletion during the retention period
- An independent auditor has reviewed the archive configuration and issued a written opinion (no such opinion yet exists for Agora deployments; this is a known gap firms are expected to be actively working to close)

**Examiner note: the auditor gap.** As of this writing, no FINRA-registered third-party archiving vendor has issued a written certification that a specific Agora deployment satisfies Rule 17a-4, and no conformant implementation exists. Firms relying on Agora for Rule 17a-4 compliance should be required to produce a timeline and vendor engagement for obtaining third-party certification. Absence of a certification plan is a deficiency.

### MiFID II Article 16 / FCA COBS 11.8

**Requirement summary.** Five-year retention (seven years where directed by competent authority) of communications related to transactions. Recording of telephone and electronic communications.

**What Agora provides.** The compliance logger captures text, and the compliance recorder captures voice and video, into tamper-evident chains. Voice recordings include per-call metadata. The retention period can be configured to meet the seven-year requirement.

**Recording consent.** Agora distinguishes two kinds of call recording (spec §6.12.3). A compliance recording, configured by the firm for regulated employees, is disclosed to every participant before recording begins and cannot be vetoed; a participant who does not accept it can stay muted with camera off, or leave. An operational recording (any other purpose) requires each participant's explicit acknowledgement before that participant's audio or video is sent.

**Cross-border note.** Firms with employees in multiple MiFID II jurisdictions should verify that the compliance logger scope covers all channels where transaction-related communications may occur, and that the retention period satisfies the longest applicable national requirement.

### HIPAA Security Rule (§164.312): Electronic Communications Containing ePHI

**Requirement summary.** Technical safeguards for electronic protected health information in electronic communications. Business Associate Agreements (BAA) with service providers that create, receive, maintain, or transmit ePHI.

**What Agora provides.** MLS end-to-end encryption protects ePHI in transit and in relay storage: a relay holds only ciphertext it cannot decrypt, plus connection metadata within its declared retention window (ARCHITECTURE §4-§5). The compliance archive contains plaintext ePHI and must be treated as a covered system under the Security Rule.

**What to verify.**
- The firm has a documented legal determination on whether its relay operator requires a BAA, based on what the relay holds (ciphertext and connection metadata, no keys and no plaintext). That determination is for the firm's counsel; this guide states only the facts
- A BAA is in place with any contracted compliance archive vendor or other party that runs the logger, recorder, or archive, since those hold plaintext
- The compliance archive's access controls satisfy the Minimum Necessary standard
- The HIPAA-required audit log for access to ePHI in the compliance archive is operational

### GDPR Article 17 and Analogous Privacy Frameworks

**The tension.** GDPR Article 17 grants data subjects the right to erasure of personal data. Compliance records cannot be deleted during the retention period. For communications involving EU data subjects, these obligations conflict directly.

**The standard exemption.** GDPR Article 17(3)(b) exempts retention "for compliance with a legal obligation" and Article 17(3)(e) exempts retention "for the establishment, exercise or defence of legal claims." Both exemptions apply to communications retained under financial services regulatory requirements. The firm must document the specific legal retention obligation and retention period, apply the exemption only for the duration of the retention period, and delete records promptly when the retention period expires.

**What to verify.** The firm has a documented legal basis for retention that covers the GDPR Article 17 conflict, and a mechanism to identify and delete records promptly (not later) after the retention period expires. Records retained beyond the retention period without a documented basis fall outside the exemption.

---

## Part 7: What to Look for in an Agora Compliance Examination

These checkpoints correspond to the configuration items in the firm's compliance setup.

### Capture Scope Verification

- Request the Space state and verify `complianceLogging.enabled` is `true`
- Verify `regulatedMembers` lists every employee the firm treats as regulated; only listed employees carry the DM capture obligation
- Verify `scope` is set to `all-channels` or that the configured scope demonstrably covers all channels where regulated business communication has occurred
- Verify `retentionDays` meets the applicable requirement: 2555 days (7 years) for FINRA/SEC, 1825 days (5 years) for MiFID II unless the competent authority has directed seven years
- Verify regulated employees use client software that conforms to spec §7.8 and runs on firm-managed devices

### Archive Completeness

- Verify the archive starts from the date compliance logging was first enabled. No archive exists for the period before the compliance logger was added to the group. This is a known limitation; the question is whether the firm's records show when logging was enabled and whether that date is consistent with when the firm adopted Agora.
- Check for channel scope gaps: if the configured scope excludes certain channels, verify that no regulated business communications occurred in them
- Review the logger's gap records and the `epochsGapped` lists in `VTCComplianceAuditEntry` records

### Chain Integrity

- Request a chain integrity verification report for the examination period
- Verify that tooling independent of the archive produced the report (the firm's own self-attestation does not qualify)
- Investigate any chain breaks

### DM Compliance

- Verify `DMComplianceAuditEntry` records are present for regulated employees
- Review removal attempt records. Each removal attempt is a compliance event and should have been reported to the firm's administrator at the time.
- Sample DM groups and verify disclosure notices precede any message content

### Logger Infrastructure

- Verify the `loggerDID` is controlled by the firm or a contracted compliance vendor acting for the firm, and by no other third party
- Verify the logger, recorder, and archive run under the firm's control and not as part of any relay operator's service (ARCHITECTURE S8)
- Verify the logger's `KeyPackageEndpoint`, which the firm hosts, has been operational. While it is unavailable, a conformant client cannot admit the logger to a new DM group and so will not let the regulated employee send in that group; ask how the firm handled any outage and whether employees moved to other channels during it
- Verify the archive backend is configured to prevent administrative deletion during the retention period

### Client Enforcement and Managed Devices

Agora has one enforcement model for compliance capture: the firm's own endpoints (ARCHITECTURE §6.3; spec §7.8.9). Relays do not inspect group creation, hold messages, or enforce logger presence, because they do not know group membership or who is regulated.

When examining a firm's Agora deployment:

- Ask what controls ensure regulated employees use conformant clients: managed devices, client version pinning, and device policy that prevents disabling the logger check.
- Ask for the firm's reconciliation of `DMComplianceAuditEntry` records against the groups the logger holds, and how discrepancies reach the compliance officer.
- Document the firm's assessment of residual risk from tampered or unmanaged clients, which Agora accepts as a cost of keeping enforcement off the network (ARCHITECTURE §9).
- A firm without documented managed-device controls over regulated employees' clients has a material gap in its DM compliance architecture; treat it as a deficiency requiring a remediation plan.

### Auditor Certification

- Request documentation of any third-party auditor engagement for compliance certification
- If no engagement exists, treat this as a deficiency and require a remediation plan with a timeline

---

## Part 8: Glossary for Examiners

**CID (Content Identifier).** A cryptographic hash used as a file or record identifier. Because the hash is computed from the content, the same content always has the same CID. Any change to the content produces a different CID, so alteration is detectable.

**Communications operator.** The party that runs a community: for a regulated firm, the firm itself. It holds identity, membership, policy, compliance logging, and the archive.

**Compliance logger.** A firm-operated participant in the Agora message group that receives and archives all messages. It shows no join notice in the message feed, and its presence is disclosed in the Space's compliance configuration, in the retention notice members see on joining, in DM disclosure notices, and in the group's membership (spec §7.7). It is a passive member: it receives all messages but sends none.

**DID (Decentralized Identifier).** A cryptographic identifier for a user or system. In Agora, each employee has a DID, which maps to a named employee in the firm's identity management system. The archive identifies message senders by DID; the firm maintains the DID-to-employee mapping.

**Infrastructure operator.** A party that runs relays or other infrastructure for communities without being part of them. It holds ciphertext and connection metadata, decides nothing about any community, and can be replaced by the firm at will.

**IPLD (InterPlanetary Linked Data).** A data model for content-addressed records, used in Agora for the compliance archive. Each record is identified by a hash of its content; records link to prior records by hash, forming a tamper-evident chain.

**JWS (JSON Web Signature).** The IETF standard signature format (RFC 7515) Agora uses for every record verified outside an encrypted group, including compliance records.

**MLS (Messaging Layer Security, RFC 9420).** The IETF standard for end-to-end encrypted group messaging, and Agora's sole key agreement mechanism. The sender's device encrypts each message; only group members hold decryption keys.

**Passive member.** An MLS group member that holds full decryption rights and receives all messages but does not issue group management operations (commits or proposals). The compliance logger is a passive member. It cannot alter the group membership or message history.

**Regulated member.** An employee the firm lists by DID in `regulatedMembers` in its Space state. Only regulated members carry the DM capture obligation.

**Relay.** The server infrastructure that routes Agora messages. Holds only ciphertext and connection metadata. Cannot read messages, identify senders, or know group membership.

**Space.** An organization's Agora workspace: the deployment unit within which channels, members, and compliance settings are configured. Equivalent to a "workspace" or "tenant" in other communication platforms.

**VTC compliance recorder.** A firm-operated passive member added to voice/video calls for compliance recording, analogous to the compliance logger for text channels.

**WORM (Write Once Read Many).** Storage that cannot be modified after writing. Rule 17a-4 requires WORM storage for retained records. The IPLD hash chain provides a technical WORM property: modification is detectable even if the underlying storage does not enforce write-once constraints. The underlying storage should still have operational controls preventing administrative deletion.

---

*Read this guide alongside `guides/counsel.md`, which covers the same architecture from the regulated firm's compliance team's perspective and contains the configuration checklist, legal hold procedures, and employee disclosure requirements.*
