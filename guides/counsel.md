# Agora Compliance & Legal Reference Guide

**Audience:** Compliance Officers, General Counsel, Outside Counsel, Regulatory Affairs
**Purpose:** What Agora captures, how it captures it, what you can produce, what you cannot, and what your obligations are
**Document version:** Aligned to Agora Protocol Specification v0.1 + DM Compliance patch

---

> **Preliminary note.** This document explains how the Agora protocol works from a compliance and legal standpoint. It is not legal advice. No FINRA-registered archiving vendor or HIPAA-qualified auditor has yet validated the compliance logging architecture described here. Regulated organizations should obtain independent validation before relying on Agora for regulatory compliance.

---

## Part 1: What Gets Captured and What Doesn't

### What the Compliance Logger Captures

When compliance logging is enabled for a space (your organization's Agora workspace), a designated **compliance logger**, a cryptographically credentialed system principal, is automatically added as a silent member of every relevant message group. It receives and archives:

- **Voice and video media streams** in covered voice channels, stored as decrypted Opus/WebM archives in IPFS, with per-call metadata records including participant join/leave timestamps and a tamper-evident chain of `VTCComplianceRecord` entries
- **All text messages** in covered channels, in original form, including edits (preserved as separate records) and deletions (tombstone records with deletion timestamp and the deleting user's identity)
- **All file attachments and media**, stored by content hash (CID). The CID matches the original's, so authenticity is mathematically verifiable.
- **All reactions** (emoji responses to messages). These are MLS application messages and are captured identically to text messages.
- **All direct messages** sent or received by any regulated employee, subject to the DM compliance provisions in Part 2
- **Message metadata**: sender identity (DID, which maps to a user account), timestamp, channel, sequence number, MLS epoch

### What the Compliance Logger Does Not Capture

- **Messages sent before the logger was admitted.** The logger's archive for each group begins at the MLS epoch when the logger joined it, and cannot capture earlier messages. If you enabled logging after your organization started using Agora, there is a gap.
- **Messages in channels outside the configured scope.** If `scope` is a channel path glob (e.g., `engineering/*`) rather than `all-channels`, messages in unscoped channels are not captured. Review your scope configuration carefully.
- **Pre-join messages in DM groups.** The logger joins a DM group when the regulated employee does; messages sent before then are not retroactively accessible.

### Archive Format

The logger stores every captured message as a `ComplianceRecord` in an append-only, tamper-evident IPLD (content-addressed) archive. Each record contains:

- The full decrypted message content (`plaintextPayload`) in its original format (CommonMark text)
- The sender's DID (maps to a user identity)
- Timestamp, channel identity, MLS epoch, and sequence number
- A link to the prior record in the chain (`prevRecordCID`). Verifying the chain hashes detects any alteration or deletion of a record.
- The logger's cryptographic signature over the record

The archive is your organization's property, stored on infrastructure you control (or a contracted archiving vendor's infrastructure). No third party holds a copy unless you have contracted one.

**Authenticity verification.** The logger signs each `ComplianceRecord`, and the records form a hash-linked chain, so you can produce records in an eDiscovery proceeding and demonstrate mathematically that they have not been altered since capture. Conventional archiving solutions rely on access controls instead of cryptographic proof.

---

## Part 2: Direct Message Compliance

### The Obligation

A regulated employee (a member of a space with compliance logging enabled) **carries their compliance obligation into every direct message group they participate in**, whether or not the DM group has any connection to the organization's space infrastructure.

The Agora specification (§17.8.1) states:

> The compliance obligation follows the regulated user, not the channel. A regulated user who conducts business communication via DM is not exempt from their Space's retention requirements by virtue of using a DM group rather than a Space channel.

### How It Works

When a regulated employee's Agora client creates or joins a DM group:

1. The client fetches a fresh encryption credential (`KeyPackage`) for the compliance logger.
2. The client adds the logger to the DM group's MLS group via a cryptographic commit. The logger becomes a full member with decryption rights.
3. The client updates the DM group's descriptor to record the logger's presence.
4. The client sends a **mandatory disclosure notice** to all other DM group participants before any message is sent.

The disclosure notice is a visible system message that participants cannot suppress. It reads:

> **[Employee name]'s messages in this conversation are subject to regulatory retention by [your organization's compliance archive] for [retention period] days.**

External counterparties see this notice before they send any message and may leave the DM group then. Messages they sent before leaving remain in the archive for the regulated employee's retention period.

### Logger Removal Protection

Once admitted to a DM group, the compliance logger cannot be removed for the duration of the retention period:

- The regulated employee's client refuses to process any request to remove the logger.
- If another DM group member removes the logger, the regulated employee's client detects this immediately, re-adds the logger, and **notifies the compliance officer and space admin** of the removal attempt.

Each removal attempt is recorded in the organization's audit chain as a `DMComplianceAuditEntry` with the timestamp and the identity of the user who attempted it.

### Gap Analysis

**The gap Agora closes.** FINRA and SEC examiners have focused heavily on business communications conducted via personal messaging applications (WhatsApp, Signal, iMessage, personal SMS) that firm archiving systems do not capture. Policy prohibition has proven ineffective. Agora's client software captures regulated employees' DMs automatically and mandatorily, instead of relying on employee self-reporting or retrospective device examination.

**The gap Agora does not close.** Agora cannot capture business communications a regulated employee conducts in a non-Agora application.

**Practical implication.** Agora closes the DM gap only when the employee and their counterparties all use Agora. This is most tractable for intra-firm communications and for firms that can contractually require counterparties to use Agora-compliant communication channels.

---

## Part 3: Responding to Legal Process

### What a Relay Operator Can Produce

Agora relays are designed to hold nothing useful in response to a subpoena or legal demand. A conformant relay knows:

- A set of rotating, anonymous channel tokens, which cannot be linked to any channel name, space, or identity without the epoch secret (which the relay does not hold)
- A set of encrypted message blobs addressed by content hash
- Connection metadata: IP addresses and timestamps of connected clients during the connection. The protocol does not require a persistent connection log.

A relay cannot produce:

- Plaintext message content (it does not hold decryption keys)
- The identity of message senders (sender identity is hidden inside the MLS ciphertext)
- The mapping from channel tokens to channel identities or member lists
- Message history beyond what it has cached (relay caching is configurable)

**Practical consequence for legal hold.** If a relay operator serving your organization receives a third-party subpoena, the accurate response is that it holds encrypted blobs it cannot read and does not know who sent them. This describes what the relay holds; it is not a legal opinion. Whether this satisfies the subpoena depends on jurisdiction and the specific legal process; consult counsel.

### What Your Organization Can Produce

Your organization's compliance archive is the authoritative source for legal hold and eDiscovery. It contains:

- Full plaintext of all captured messages, in order, with cryptographic proof of authenticity
- Complete sender identity for each message (DID, mapping to a named employee)
- Timestamps and channel context
- Edit history and deletion records (a deleted message is tombstoned; the tombstone records when it was deleted and by whom)
- DM group compliance audit records, including any logger removal attempts

For eDiscovery, the compliance archive supports export by date range, channel, sender DID, or keyword. Keyword search runs against the plaintext `text` fields, which are CommonMark: readable as-is, or easily stripped of markup.

### Legal Hold Procedure

When a legal hold is triggered:

1. **Identify the relevant DIDs.** Each employee corresponds to one or more DIDs. Your identity management system maintains the mapping from employee name to DID (it can also be derived from your space's member list and DID documents).

2. **Suspend archive pruning for affected DIDs and channels.** The compliance archive is append-only. If your archive configuration includes a purge policy (e.g., deleting records older than `retentionDays` once the retention period expires), you must suspend that purge for held content.

3. **Export the relevant records.** The compliance archive is an IPLD-structured, content-addressed dataset. Export tools should query by sender DID, channel CID, and date range, producing a set of `ComplianceRecord` objects with their authentication proofs.

4. **Verify chain integrity.** Before producing records, verify that the `prevRecordCID` chain is intact for the exported range. A broken chain indicates a record was altered or deleted; you must investigate and disclose it.

5. **Preserve `DMComplianceAuditEntry` records** for any DM groups involving the relevant employees. These records document logger presence and any removal attempts.

---

## Part 4: Employee Disclosure and Consent

### Employee Disclosure

Employees in a compliance-logging-enabled space receive a mandatory disclosure at first join:

> "This space is subject to regulatory message retention. Messages are archived for [N] days regardless of expiry settings."

The client displays this notice and does not let the employee dismiss it without acknowledgment. It remains available from the space's information panel.

When a regulated employee's client adds the compliance logger to a DM group, it sends a `ComplianceDisclosureNotice` to all DM participants as a visible system message before any application message. The notice identifies the logger by label (e.g., "Acme Corp Compliance Archive"), states the retention period, and lists the regulatory frameworks under which the logger operates.

### Counterparty Disclosure

External counterparties who receive DMs from regulated employees see the compliance disclosure notice before they send any message. The disclosure is informational; they are not asked to consent, and they may leave the DM group. This mirrors the recording disclosure on regulated telephone calls ("this call may be recorded for compliance purposes"), applied at the messaging layer.

**Open legal question.** Whether this disclosure satisfies wiretapping statutes and analogous communication privacy laws in all relevant jurisdictions is a question for counsel. The one-party consent model (the regulated firm consenting on behalf of its employee) is standard for broker-dealer call recording but has not been tested for end-to-end encrypted messaging. Obtain counsel's opinion before deploying in jurisdictions where this is uncertain.

---

## Part 5: Compliance Configuration Checklist

Before deploying Agora in a regulated environment, verify the following.

**Capture scope**
- [ ] `complianceLogging.enabled` is `true` in the space state document
- [ ] `scope` is set to `all-channels` or explicitly confirmed to cover all channels where regulated business communication may occur
- [ ] `retentionDays` is set to meet your regulatory requirement (FINRA/SEC 17a-4: 2555 days = 7 years; HIPAA: 2190 days = 6 years minimum for most records)
- [ ] DM compliance (§17.8) is active: confirm that the regulated employee's client software version supports §17.8 and that the `loggerDID` is correctly configured

**Logger infrastructure**
- [ ] The `loggerDID` is a DID controlled by your organization or a contracted compliance vendor, and by no other third party
- [ ] The `logStore` IPFS endpoint is on infrastructure subject to your legal hold and data governance policies
- [ ] The logger's DID document includes a `KeyPackageEndpoint` service entry and the endpoint is operational. If this endpoint is down, regulated employees' clients cannot add the logger to new DM groups.
- [ ] The logger runs in a mode that prevents deletion of records within the retention period. The append-only chain structure helps, but operational controls must prevent administrative deletion of the underlying IPFS data.

**Audit and monitoring**
- [ ] `DMComplianceAuditEntry` records are being produced and are accessible to your compliance team
- [ ] Alerts are configured for logger removal attempts (the spec requires client-level notification; confirm it is routed to compliance staff)
- [ ] Archive integrity verification (chain hash checks) runs on a schedule
- [ ] A process exists to map DID to employee name for eDiscovery production

**Disclosure**
- [ ] `retentionNotice` text in the space state document is accurate and legally reviewed
- [ ] Employee notification has been provided through HR/legal channels (the protocol disclosure is necessary but may not satisfy your jurisdiction's employment law requirements)

**VTC compliance**
- [ ] `vtcCompliance.enabled` is `true` in the space state document if voice channels are used for regulated communications
- [ ] `vtcCompliance.recorderDID` is configured and the recorder's DID document has a `KeyPackageEndpoint` and an HPKE-capable `keyAgreement` entry
- [ ] `vtcCompliance.retentionDays` matches `complianceLogging.retentionDays`, or the longer value is documented as the governing retention period
- [ ] `autoGrant` is `true`, so compliance recording starts automatically when a call begins without per-call admin action
- [ ] `VTCComplianceAuditEntry` records are being produced and `epochsGapped` is monitored; non-empty gap arrays require compliance officer notification

**Acknowledged gaps**
- [ ] Independent compliance auditor validation has not yet been completed: document this and the plan to obtain it
- [ ] Non-Agora communication channels (email, phone, personal messaging) are not covered: confirm existing archiving solutions cover those channels and document residual risk

---

## Part 6: Regulatory Framework Quick Reference

| Regulation | Key Requirement | Agora Coverage | Gap |
|---|---|---|---|
| FINRA 17a-4 / SEC 17a-4 | 7-year retention of business communications, non-erasable, non-alterable | Covered for text channels, DMs (§17.8), and voice/video (§10.12); tamper-evident chain | Auditor validation pending |
| FINRA Rule 4511 | Books and records: communications with the public | Covered for Agora-channel communications including voice | Non-Agora channels not covered |
| HIPAA Security Rule (§164.312) | Technical safeguards for ePHI in electronic communications | MLS E2EE satisfies technical safeguard requirement; voice recording covered | BAA with relay operator needed |
| MiFID II Article 16 | 5-year retention of communications related to transactions | Covered for text and voice; 7-year retention configuration available | Cross-border jurisdiction issues |
| GDPR Article 17 (right to erasure) | Ability to delete personal data on request | Records in the compliance archive cannot be deleted during the retention period, which conflicts directly with erasure rights for regulated communications. The standard exemption for legal retention obligations applies; document the basis. | Legal analysis required per jurisdiction |
| UK FCA COBS 11.8 | Recording and retention of telephone and electronic communications | Text and voice covered | |
