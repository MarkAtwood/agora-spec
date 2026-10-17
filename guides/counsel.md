# Agora Compliance & Legal Reference Guide

**Audience:** Compliance Officers, General Counsel, Outside Counsel, Regulatory Affairs
**Companion document:** `guides/regulators.md` (the examiner's view of the same architecture)
**Purpose:** What Agora captures, how it captures it, what you can produce, what you cannot, and what your obligations are
**Document version:** Aligned to the Agora Protocol Specification 0.2 (Draft, `spec/`) and `ARCHITECTURE.md` (2026-10-16). Section references are to those documents. No conformant implementation exists yet.

---

> **Preliminary note.** This document explains how the Agora protocol works from a compliance and legal standpoint. It is not legal advice. No FINRA-registered archiving vendor or HIPAA-qualified auditor has yet validated the compliance logging architecture described here. Regulated organizations should obtain independent validation before relying on Agora for regulatory compliance.

---

## Part 1: What Gets Captured and What Doesn't

### Who Holds What

Agora separates two operators (ARCHITECTURE §1-§2), and the separation decides what each can be compelled to produce:

- **Your organization is the communications operator.** You hold identity provisioning, membership, roles, policy, the compliance logger, and the archive. Every authority over your communications is exercised with your keys, and the authoritative record is your archive (ARCHITECTURE §4).
- **Relay and other infrastructure providers are infrastructure operators.** They carry ciphertext, decide nothing about your communities, never learn who is in a group or who sent a message, and can be replaced without changing your identities, membership, history, or policy.

If you run your own relays, you fill both roles, with distinct keys for each (ARCHITECTURE §2.4). Your relays still hold only what any relay holds.

The compliance logger, call recorder, archive, gateways, and bridges are your components. They run under your control and are never a function or configuration option of a relay (ARCHITECTURE S8; spec §7.3). A vendor may host them for you under contract as your processor; they remain your principals with your keys.

### What the Compliance Logger Captures

When compliance logging is enabled for a Space (your organization's Agora workspace), a designated **compliance logger**, a system principal with its own cryptographic identity, is automatically added to every covered message group as a **disclosed member** (spec §7.7). It shows no join notice in the message feed, and its presence is disclosed in the Space's compliance configuration, in the retention notice every member sees on joining, in the disclosure notice in every DM group it enters, and in the group's MLS membership, which any member can inspect. It receives and archives:

- **Voice and video media streams** in covered voice channels, captured by a compliance recorder (spec §6.12), stored as Opus audio (Ogg or WebM) or WebM video sealed at rest to your recorder's key, with per-call metadata records including participant join/leave timestamps and a tamper-evident chain of `VTCComplianceRecord` entries
- **All text messages** in covered channels, as JMAP Chat `Message` objects in their exact original bytes (spec §5.2.3), including edits (preserved as separate records) and deletions (separate records with the deletion timestamp and the deleting user's identity; the original stays in the archive)
- **All file attachments and media**, stored by content hash (CID). The CID matches the original's, so authenticity is verifiable.
- **All reactions** (emoji responses to messages). These are JMAP Chat `Reaction` objects carried as ordinary group messages and captured identically to text messages.
- **All direct messages** sent or received by any regulated employee, subject to the DM compliance provisions in Part 2
- **Message metadata**: sender identity (DID, which maps to a user account), timestamp, channel, sequence number, MLS epoch

### What the Compliance Logger Does Not Capture

- **Messages sent before the logger was admitted.** The logger's archive for each group begins at the MLS epoch when the logger joined it, and cannot capture earlier messages. If you enabled logging after your organization started using Agora, there is a gap.
- **Messages in channels outside the configured scope.** If `scope` is a list of channel path globs (e.g., `["engineering/*"]`) rather than `all-channels`, messages in unscoped channels are not captured. Review your scope configuration carefully.
- **Pre-join messages in DM groups.** The logger joins a DM group when the regulated employee does; messages sent before then are not retroactively accessible.
- **Groups formed by tampered clients.** A modified or non-conformant client can create or join a group without the logger, and no infrastructure component will stop it (spec §7.8.9). Your controls are managed devices and audit reconciliation (Part 2).

### Archive Format

The logger stores every captured message as a `ComplianceRecord` (spec §7.4) in an append-only, tamper-evident IPLD (content-addressed) archive, organized as one chain per channel with a Space-level index of chain heads. Each record is a signed envelope: a typed payload envelope (spec §13.1) whose body is the record and whose `sig` field carries the logger's JWS signature over the exact record bytes (spec §13.1.1). The record contains:

- The decrypted message envelope (`plaintextPayload`), byte-for-byte as received. For chat this is a JMAP Chat `Message`, whose text is normally CommonMark
- The sender's DID (maps to a user identity)
- Timestamp, channel identity, MLS epoch, and sequence number
- The hash of the encrypted message as it travelled (`outerEnvelopeCID`)
- A link to the prior record in the chain (`prevRecordCID`). Verifying the chain hashes detects any alteration or deletion of a record.

The archive is your organization's property, stored on infrastructure you control (or a contracted archiving vendor's infrastructure). Any copy placed on infrastructure-operator storage must be encrypted under a key you hold and they do not (spec §7.2). No third party holds a readable copy unless you have contracted one.

**Authenticity verification.** The logger signs each `ComplianceRecord`, and the records form a hash-linked chain, so you can produce records in an eDiscovery proceeding and demonstrate that they have not been altered since capture. Conventional archiving solutions rely on access controls instead of cryptographic proof. Record chain heads at regular intervals in a system independent of the archive; the protocol does not do this for you, and examiners will ask for that log.

---

## Part 2: Direct Message Compliance

### The Obligation

A regulated employee is one your organization lists by DID in `complianceLogging.regulatedMembers` in its signed Space state. Membership of a logging-enabled Space does not by itself make anyone regulated; regulated status is an explicit per-user designation (spec §7.2, §7.8.1). A regulated employee **carries their compliance obligation into every direct message group they participate in**, whether or not the DM group has any connection to the organization's Space.

The Agora specification (§7.8.1) states:

> The compliance obligation follows the regulated user, not the channel. A regulated user who conducts business communication via DM is not exempt from their Space's retention requirements by virtue of using a DM group rather than a Space channel.

### How It Works

When a regulated employee's Agora client creates or joins a DM group:

1. The client fetches a fresh encryption credential (`KeyPackage`) for the compliance logger from the logger's `KeyPackageEndpoint`, which you host.
2. The client adds the logger to the DM group's MLS group via a cryptographic commit and delivers the logger's `Welcome` to that same endpoint. The logger becomes a full member with decryption rights.
3. The client updates the DM group's descriptor to record the logger's presence.
4. The client sends a **mandatory disclosure notice** to all other DM group participants before any message is sent.

The client will not send any message into the group until the logger is a member and the disclosure has been shown (spec §7.8.1). No consent threshold applies to adding the logger (spec §7.7).

The disclosure notice is a visible system message that participants cannot suppress. It reads:

> **[Employee name]'s messages in this conversation are subject to regulatory retention by [your organization's compliance archive] for [retention period] days.**

External counterparties see this notice before they send any message and may leave the DM group then. Messages they sent before leaving remain in the archive for the regulated employee's retention period.

### Where Enforcement Happens

DM capture is enforced only at your organization's endpoints (ARCHITECTURE §6.3; spec §7.8.9):

- **The regulated employee's client**, ideally on a device you issue and manage, configured so the user cannot disable the logger check.
- **The compliance logger**, which records every capture gap it can detect, including its own removal and re-admission.
- **Your archive and audit pipeline**, which should reconcile `DMComplianceAuditEntry` records against the groups the logger actually holds and alert the compliance officer to discrepancies.

Relays do not know who is in a DM group or who is regulated, and they do not inspect group creation, hold messages, or enforce logger presence. The accepted cost is that a tampered client can evade capture (ARCHITECTURE §9). The mitigation is the managed endpoint, the same trust boundary you rely on for email, phones, and every other channel.

### Logger Removal Protection

Once admitted to a DM group, the compliance logger may not be removed for the duration of the retention period (spec §7.8.3):

- The regulated employee's client refuses to commit any removal of the logger.
- If another DM group member removes the logger, the regulated employee's client detects this, re-adds the logger, and **notifies your Space administrator** of the removal attempt. Messages in the interval between removal and re-add are not captured; the logger records the missing epochs.

Each removal attempt is recorded in the `removalAttempts` list of the group's `DMComplianceAuditEntry` in your compliance audit chain, with the timestamp and the identity of the user who attempted it (spec §7.8.8).

### Gap Analysis

**The gap Agora closes.** FINRA and SEC examiners have focused heavily on business communications conducted via personal messaging applications (WhatsApp, Signal, iMessage, personal SMS) that firm archiving systems do not capture. Policy prohibition has proven ineffective. Agora's client software captures regulated employees' DMs automatically, instead of relying on employee self-reporting or retrospective device examination.

**The gap Agora does not close.** Agora cannot capture business communications a regulated employee conducts in a non-Agora application, or through a client you do not control.

**Practical implication.** Agora closes the DM gap only when the regulated employee uses a conformant client and the conversation takes place on Agora (directly or through one of your bridges). This is most tractable for intra-firm communications and for firms that can contractually require counterparties to use Agora-compliant communication channels.

---

## Part 3: Responding to Legal Process

### What a Relay Operator Can Produce

Agora relays are designed to hold nothing about content or membership in response to a subpoena or legal demand. A demand on a relay operator yields only what falls within its observation budget (ARCHITECTURE §4-§5; spec §10.4.1):

- Network-layer connection metadata (source address, timing, volume) for the retention period set in its service agreement with you and declared publicly in its relay manifest (spec §10.2.1)
- Opaque ciphertext, its size and timing, and rotating routing tokens that cannot be linked to any channel, Space, or identity without group secrets the relay does not hold
- The identity of each customer it holds a service agreement with (a billing DID), and quota counters per agreement
- For push proxies, opaque device push handles and wake-up timing

A relay can therefore say which network addresses used your organization's service. It cannot say which Space, channel, or sender any traffic belonged to: your agreement with it names no Space or channel, and your billing identity appears in no Space record (ARCHITECTURE §6.1). If you run several Spaces through one relay, the relay cannot tell them apart.

A relay cannot produce:

- Plaintext message content (it does not hold decryption keys)
- The identity of message senders (sender identity is hidden inside the encryption)
- Group membership, or which users are regulated
- The mapping from routing tokens to channel identities or member lists
- User accounts (relays do not authenticate users)
- Message history beyond what it has cached under its retention window

**Practical consequence for legal process.** If a relay operator serving your organization receives a third-party subpoena, the accurate response is that it holds encrypted data it cannot read, does not know who sent it, and holds connection metadata for its declared retention period. This describes what the relay holds; it is not a legal opinion. Whether this satisfies the subpoena depends on jurisdiction and the specific legal process; consult counsel.

### What Your Organization Can Produce

Your organization's compliance archive is the authoritative source for legal hold and eDiscovery. A demand served on you reaches everything your own policy retains, under your own retention and legal-hold controls (ARCHITECTURE §4). The archive contains:

- Full plaintext of all captured messages, in order, with cryptographic proof of authenticity
- Complete sender identity for each message (DID, mapping to a named employee)
- Timestamps and channel context
- Edit history and deletion records (a deletion is a separate record; the original message record remains)
- DM group compliance audit records, including any logger removal attempts and the logger's gap records

For eDiscovery, the compliance archive supports export by date range, channel, sender DID, or keyword. Keyword search runs against the `body` text of archived JMAP Chat `Message` objects, which is normally CommonMark: readable as-is, or easily stripped of markup.

### Legal Hold Procedure

When a legal hold is triggered:

1. **Identify the relevant DIDs.** Each employee corresponds to one DID. For identities your provisioning service issues, the DID contains a stable local identifier that is never reassigned to another person and never derived from a name or email address (spec §2.5.2). The provisioning service keeps the mapping from that identifier to your directory record.

2. **Suspend archive pruning for affected DIDs and channels.** The compliance archive is append-only. If your archive configuration includes a purge policy (e.g., deleting records older than `retentionDays` once the retention period expires), you must suspend that purge for held content.

3. **Export the relevant records.** The compliance archive is an IPLD-structured, content-addressed dataset. Export tools should query by sender DID, channel, and date range, producing the signed `ComplianceRecord` envelopes exactly as stored, so their signatures still verify.

4. **Verify chain integrity.** Before producing records, verify that the `prevRecordCID` chain is intact for the exported range and that each logger signature verifies. A broken chain indicates a record was altered or deleted; you must investigate and disclose it.

5. **Preserve `DMComplianceAuditEntry` records** for any DM groups involving the relevant employees. These records document logger presence and any removal attempts.

---

## Part 4: Employee Disclosure and Consent

### Employee Disclosure

Employees in a compliance-logging-enabled Space receive a mandatory disclosure at first join, from the `retentionNotice` in Space state (spec §7.5):

> "This space is subject to regulatory message retention. Messages are archived for [N] days regardless of expiry settings."

The client displays this notice on first join and keeps it available from the Space's information panel, together with the logger's label, retention period, and regulatory frameworks (spec §7.7).

When a regulated employee's client adds the compliance logger to a DM group, it sends a `ComplianceDisclosureNotice` to all DM participants as a visible system message before any application message (spec §7.8.4). The notice identifies the logger by label (e.g., "Acme Corp Compliance Archive"), states the retention period, and lists the regulatory frameworks under which the logger operates.

### Counterparty Disclosure

External counterparties who receive DMs from regulated employees see the compliance disclosure notice before they send any message. The disclosure is informational; they are not asked to consent, and they may leave the DM group. This mirrors the recording disclosure on regulated telephone calls ("this call may be recorded for compliance purposes"), applied at the messaging layer.

### Call Recording Consent

Agora splits call recording into two consent models (spec §6.12.3):

- **Compliance recording** (`purpose: "compliance"`). Disclosure plus participation: every participant sees the disclosure before recording begins, and transmitting audio or video after that is the participant's consent. There is no veto. A participant who does not accept the recording can remain muted with camera off, or leave.
- **Operational recording** (any other purpose). Each participant's client must obtain that participant's explicit acknowledgement before sending their audio or video while the recording is active. A participant who declines stays in the call with media off; one refusal does not stop recording of others.

In both cases a participant's media is never sent automatically on join while a recording is active.

**Open legal question.** Whether these disclosures satisfy wiretapping statutes and analogous communication privacy laws in all relevant jurisdictions is a question for counsel. The one-party consent model (the regulated firm consenting on behalf of its employee) is standard for broker-dealer call recording but has not been tested for end-to-end encrypted messaging. Obtain counsel's opinion before deploying in jurisdictions where this is uncertain, particularly all-party-consent jurisdictions, where the compliance model's lack of a veto deserves specific analysis.

---

## Part 5: Compliance Configuration Checklist

Before deploying Agora in a regulated environment, verify the following.

**Capture scope**
- [ ] `complianceLogging.enabled` is `true` in the Space state
- [ ] `complianceLogging.regulatedMembers` lists every employee you treat as regulated, and you have a process to update it on hiring, role change, and departure
- [ ] `scope` is set to `all-channels` or explicitly confirmed to cover all channels where regulated business communication may occur
- [ ] `retentionDays` is set to meet your regulatory requirement (FINRA/SEC 17a-4: 2555 days = 7 years; HIPAA: 2190 days = 6 years minimum for most records)
- [ ] DM compliance (spec §7.8) is active: regulated employees use client software that conforms to §7.8, and the `loggerDID` is correctly configured

**Endpoint enforcement**
- [ ] Regulated employees communicate from devices you issue and manage
- [ ] Managed clients are configured so the user cannot disable the logger check or install an unmanaged client for business use
- [ ] Your audit pipeline reconciles `DMComplianceAuditEntry` records against the groups the logger holds and alerts compliance staff to discrepancies

**Logger infrastructure**
- [ ] The `loggerDID` is a DID controlled by your organization or a contracted compliance vendor acting for you, and by no other third party
- [ ] The logger, recorder, and archive run on infrastructure under your control (or your contracted processor's), and not as part of any relay operator's service
- [ ] The `logStore` archive is on infrastructure subject to your legal hold and data governance policies; any copy on infrastructure-operator storage is encrypted under a key you hold
- [ ] The logger's DID document includes a `KeyPackageEndpoint` service entry and the endpoint is operational. If this endpoint is down, a conformant client cannot admit the logger to a new DM group and will not let the regulated employee send in it.
- [ ] The logger runs in a mode that prevents deletion of records within the retention period. The append-only chain structure helps, but operational controls must prevent administrative deletion of the underlying storage.

**Audit and monitoring**
- [ ] `DMComplianceAuditEntry` records and logger gap records are being produced and are accessible to your compliance team
- [ ] Alerts are configured for logger removal attempts (the spec requires notification to the Space administrator; confirm it is routed to compliance staff)
- [ ] Archive integrity verification (chain hash and signature checks) runs on a schedule
- [ ] Chain heads are recorded at regular intervals with an independent witness (suggested practice: `profiles/compliance-chain-witness.md`)
- [ ] A process exists to map DID to employee name for eDiscovery production

**Disclosure**
- [ ] `retentionNotice` text in the Space state is accurate and legally reviewed
- [ ] Employee notification has been provided through HR/legal channels (the protocol disclosure is necessary but may not satisfy your jurisdiction's employment law requirements)

**VTC compliance**
- [ ] `vtcCompliance.enabled` is `true` in the Space state if voice channels are used for regulated communications
- [ ] `vtcCompliance.recorderDID` is configured and the recorder's DID document has a `KeyPackageEndpoint` and an X25519 `keyAgreement` entry for archive encryption
- [ ] `vtcCompliance.retentionDays` matches `complianceLogging.retentionDays`, or the longer value is documented as the governing retention period
- [ ] `autoGrant` is `true`, so compliance recording starts automatically when a call begins without per-call admin action
- [ ] `VTCComplianceAuditEntry` records are being produced and `epochsGapped` is monitored; non-empty gap arrays require compliance officer notification

**Acknowledged gaps**
- [ ] Independent compliance auditor validation has not yet been completed: document this and the plan to obtain it
- [ ] Non-Agora communication channels (email, phone, personal messaging) are not covered: confirm existing archiving solutions cover those channels and document residual risk
- [ ] Tampered or unmanaged clients can evade DM capture: document the residual risk and your managed-device controls

---

## Part 6: Regulatory Framework Quick Reference

| Regulation | Key Requirement | Agora Coverage | Gap |
|---|---|---|---|
| FINRA 17a-4 / SEC 17a-4 | 7-year retention of business communications, non-erasable, non-alterable | Covered for text channels, DMs (spec §7.8), and voice/video (spec §6.12); tamper-evident chain | Auditor validation pending; capture depends on conformant clients |
| FINRA Rule 4511 | Books and records: communications with the public | Covered for Agora-channel communications including voice | Non-Agora channels not covered |
| HIPAA Security Rule (§164.312) | Technical safeguards for ePHI in electronic communications | MLS E2EE protects ePHI in transit and in relay storage; voice recording covered; archive holds plaintext and is a covered system | Whether a BAA is needed with the relay operator is a question for counsel. Facts: the relay holds ciphertext and connection metadata, no keys and no plaintext (ARCHITECTURE §4-§5). Parties running the logger, recorder, or archive hold plaintext |
| MiFID II Article 16 | 5-year retention of communications related to transactions | Covered for text and voice; 7-year retention configuration available | Cross-border jurisdiction issues |
| GDPR Article 17 (right to erasure) | Ability to delete personal data on request | Records in the compliance archive cannot be deleted during the retention period, which conflicts directly with erasure rights for regulated communications. The standard exemption for legal retention obligations applies; document the basis. | Legal analysis required per jurisdiction |
| UK FCA COBS 11.8 | Recording and retention of telephone and electronic communications | Text and voice covered; compliance call recording is disclosed and cannot be vetoed (spec §6.12.3) | |
