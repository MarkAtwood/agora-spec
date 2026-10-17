# Agora Compliance & Legal Reference Guide

**Audience:** Compliance Officers, General Counsel, Outside Counsel, Regulatory Affairs
**Companion document:** `guides/regulators.md` (the examiner's view of the same architecture)
**Purpose:** What Agora captures, how it captures it, what you can produce, what you cannot, and what your obligations are
**Document version:** Aligned to the Agora Protocol Specification v0.2 (Draft, `spec/`) and `ARCHITECTURE.md` (2026-10-16). Section references are to those documents. No conformant implementation exists yet.

---

> **Preliminary note.** This document explains how the Agora protocol works from a compliance and legal standpoint. It is not legal advice. No qualified third-party archiving vendor (or designated third party under SEC Rule 17a-4(f)) or HIPAA-qualified auditor has yet validated the compliance logging architecture described here. Regulated organizations should obtain independent validation before relying on Agora for regulatory compliance.

---

## Part 1: What Gets Captured and What Doesn't

### Who Holds What

Agora separates two operators (ARCHITECTURE §1–§2), and the separation decides what each can be compelled to produce:

- **Relay and other infrastructure providers are Infrastructure Operators (IOs).** They carry ciphertext and decide nothing about your communities. They never learn who is in a group or who sent a message. You can replace them without changing your identities, membership, history, or policy.
- **Your organization is the Communications Operator (CO).** You hold identity provisioning, membership, roles, policy, the compliance logger, and the archive. You exercise every authority over your communications with your keys, and your archive is the authoritative record (ARCHITECTURE §4).

If you run your own relays, you fill both roles, with distinct keys for each (ARCHITECTURE §2.4). Your relays still hold only what any relay holds.

The compliance logger, call recorder, archive, gateways, and bridges are your components. They run under your control and are never a function or configuration option of a relay (ARCHITECTURE S8; spec §7.3). A vendor may host them for you under contract as your processor; they remain your principals with your keys.

### What the Compliance Logger Captures

When compliance logging is enabled for a Space (your organization's Agora workspace), a designated **compliance logger** is automatically added to every covered message group as a **disclosed member** (spec §7.7). The logger is a system principal with its own cryptographic identity. It shows no join notice in the message feed. Its presence is disclosed in four places:

- The Space's compliance configuration
- The retention notice every member sees on joining
- The disclosure notice in every direct message (DM) group it enters
- The group's MLS (RFC 9420) membership, which any member can inspect

The logger receives and archives:

- **Text messages.** All text messages in covered channels, as JMAP Chat `Message` objects in their exact original bytes (spec §5.2.3). Edits are preserved as separate records. A deletion is a separate record with the deletion timestamp and the deleting user's identity; the original stays in the archive.
- **File attachments.** Each captured message records, for every attached file, the file's SHA-256 hash and size, the key that decrypts it, and the content identifier (CID) of its encrypted copy (spec §5.2.2). The logger also captures the file itself: it fetches the encrypted file from the relays, decrypts it, checks it against the recorded SHA-256 hash, and stores the plaintext in your archive for the record's retention period (spec §7.4). A file that cannot be fetched or fails the check is recorded as a capture gap naming the message and the missing file (spec §7.4, §7.8.9). Files are encrypted and stored in 256 KiB pieces, up to 4 GiB per file (spec §14.3.4); the piecing is transparent to the archive, which holds the whole file. A produced file is authenticated by matching its SHA-256 hash against the hash in the archived signed message, not by the CID, which identifies only the encrypted copy.
- **Reactions.** All reactions (emoji responses to messages). These are JMAP Chat `Reaction` objects carried as ordinary group messages and captured identically to text messages.
- **Direct messages.** All DMs sent or received by any regulated employee, subject to the DM compliance provisions in Part 2.
- **Voice and video.** Media streams in covered voice channels, captured by a compliance recorder (spec §6.12). Media is stored as Opus audio (Ogg or WebM) or WebM video, sealed at rest to your recorder's key. Each call also has metadata records, including participant join and leave timestamps, and a tamper-evident chain of `VTCComplianceRecord` entries.
- **Message metadata.** Sender identity (DID, which maps to a user account), timestamp, channel, sequence number, and MLS epoch.

### What the Compliance Logger Does Not Capture

- **Messages sent before the logger was admitted.** The logger's archive for each group begins at the MLS epoch when the logger joined it, and cannot capture earlier messages. If you enabled logging after your organization started using Agora, there is a gap.
- **Messages in channels outside the configured scope.** If `scope` is a list of channel path globs (for example, `["engineering/*"]`) rather than `all-channels`, messages in unscoped channels are not captured. Review your scope configuration carefully.
- **Pre-join messages in DM groups.** The logger joins a DM group when the regulated employee does; messages sent before then are not retroactively accessible.
- **Groups formed by tampered clients.** A modified or non-conformant client can create or join a group without the logger, and no infrastructure component will stop it (spec §7.8.9). Your controls are managed devices and audit reconciliation (Part 2).

**Not a gap: DMs held as message requests.** When someone the regulated employee has not accepted adds them to a DM group, the client holds the group as a message request (spec §4.6.3). For a regulated employee, the client still processes the Welcome, admits the logger, and captures as in any other DM group (spec §4.6.3, §7.8.7). The request state suppresses only what the employee sees: notifications, read receipts, and typing indicators. Messages sent while the request is pending are therefore captured. Only messages sent before the logger's admission fall under the pre-join gap above.

### Archive Format

The logger stores every captured message as a `ComplianceRecord` (spec §7.4) in an append-only, tamper-evident IPLD (content-addressed) archive, organized as one chain per channel with a Space-level index of chain heads. Each record is a signed envelope: a typed payload envelope (spec §13.1) whose body is the record and whose `sig` field carries the logger's JWS signature over the exact record bytes (spec §13.1.1). The record contains:

- The decrypted message envelope (`plaintextPayload`), byte-for-byte as received; for chat, a JMAP Chat `Message`, whose text is normally CommonMark
- The sender's DID (maps to a user identity)
- Timestamp, channel identity, MLS epoch, and sequence number
- The hash of the encrypted message as it travelled (`outerEnvelopeCID`)
- Verification material: the sender's encrypted MLS message exactly as received (`senderMessage`), the keys that open that one message and no other (`messageKeys`), the group's MLS context for the epoch (`groupContext`), and the sender's MLS leaf with its signature key and credential (`senderLeaf`)
- A link to the prior record in the chain (`prevRecordCID`), so that verifying the chain hashes detects any alteration or deletion of a record

The archive is your organization's property, stored on infrastructure you control (or a contracted archiving vendor's infrastructure). Any copy placed on IO storage must be encrypted under a key you hold and the IO does not (spec §7.2). No third party holds a readable copy unless you have contracted one.

**Authenticity verification.** The logger signs each `ComplianceRecord`, and the records form a hash-linked chain, so you can produce records in an eDiscovery proceeding and demonstrate that they have not been altered since capture. Conventional archiving solutions rely on access controls instead of cryptographic proof. The verification material goes further: a party who does not trust your logger can check that a device key of the named sender signed the archived message (spec §7.4). That check does not show that anyone other than the logger received the message. Records signed before a rotation of the logger's key still verify against the logger's DID log (spec §7.9).

Record chain heads at regular intervals in a system independent of the archive. The protocol does not do this for you, and examiners will ask for that log.

---

## Part 2: Direct Message Compliance

### The Obligation

A regulated employee is one your organization lists by DID in `complianceLogging.regulatedMembers` in its signed Space state. Membership of a logging-enabled Space does not by itself make anyone regulated. Regulated status is an explicit per-user designation (spec §7.2, §7.8.1). A regulated employee **carries their compliance obligation into every direct message group they participate in**, whether or not the DM group has any connection to the organization's Space.

The Agora specification (spec §7.8.1) states:

> The compliance obligation follows the regulated user, not the channel. A regulated user who conducts business communication via DM is not exempt from their Space's retention requirements by virtue of using a DM group rather than a Space channel.

### How It Works

When a regulated employee's Agora client creates or joins a DM group:

1. The client fetches a fresh encryption credential (`KeyPackage`) for the compliance logger from the logger's `KeyPackageEndpoint`, which you host.
2. The client adds the logger to the DM group's MLS group with an MLS Commit and delivers the logger's `Welcome` to that same endpoint. The logger becomes a full member with decryption rights.
3. The client sends a **mandatory disclosure notice** to all other DM group participants before any message is sent.

The client will not send any message into the group until the logger is a member and the client has sent the disclosure notice (spec §7.8.1). Adding the logger needs no other member's consent (spec §4.6.1, §7.7).

The disclosure notice is a system message, normally shown as a system notification. It reads:

> **[Employee name]'s messages in this conversation are subject to regulatory retention by [your organization's compliance archive] for [retention period] days.**

External counterparties see this notice before they send any message and may leave the DM group then. Messages they sent before leaving remain in the archive for the regulated employee's retention period.

### Where Enforcement Happens

DM capture is enforced only at your organization's endpoints (ARCHITECTURE §6.3; spec §7.8.9):

- **The regulated employee's client**, ideally on a device you issue and manage, configured so the user cannot disable the logger check.
- **The compliance logger**, which records every capture gap it can detect, including its own removal and re-admission.
- **Your archive and audit pipeline**, which should reconcile `DMComplianceAuditEntry` records against the groups the logger actually holds and alert the compliance officer to discrepancies.

Relays do not know who is in a DM group or who is regulated, and they do not inspect group creation, hold messages, or enforce logger presence. The accepted cost is that a tampered client can evade capture (ARCHITECTURE §9). The mitigation is the managed endpoint, the same trust boundary you rely on for email, phones, and every other channel.

### Logger Removal Protection

Once admitted to a DM group, the compliance logger may not be removed (spec §7.8.3):

- The regulated employee's client refuses to commit any removal of the logger.
- If another DM group member removes the logger, the regulated employee's client detects the removal and re-adds the logger. Messages in the interval between removal and re-add are not captured. The logger records the missing epochs.

Each removal attempt is recorded in the `removalAttempts` list of the group's `DMComplianceAuditEntry` in your compliance audit chain, with the timestamp and the identity of the user who attempted it (spec §7.8.8).

### Gap Analysis

**The gap Agora closes.** FINRA and SEC examiners have focused heavily on business communications conducted via personal messaging applications (WhatsApp, Signal, iMessage, personal SMS) that firm archiving systems do not capture. Policy prohibition has proven ineffective. Agora's client software captures regulated employees' DMs automatically, instead of relying on employee self-reporting or retrospective device examination.

**The gap Agora does not close.** Agora cannot capture business communications a regulated employee conducts in a non-Agora application, or through a client you do not control.

**Practical implication.** Agora closes the DM gap only when the regulated employee uses a conformant client and the conversation takes place on Agora (directly or through one of your bridges). This is most tractable for intra-firm communications and for firms that can contractually require counterparties to use Agora-compliant communication channels.

---

## Part 3: Responding to Legal Process

### What a Relay Operator Can Produce

Agora relays are designed to hold nothing about content or membership. A subpoena or other legal demand on a relay operator yields only what falls within the relay's observation budget (ARCHITECTURE §4–§5; spec §10.4.1):

- Network-layer connection metadata (source address, timing, volume) for the retention period set in its service agreement with you and declared publicly in its relay manifest (spec §10.2.1)
- Opaque ciphertext, its size and timing, and rotating routing tokens; the relay knows which tokens your organization registered under its agreement, but cannot link a token to any channel, Space, or person
- The recent encrypted envelopes it holds for each of those tokens, for the retention period in your agreement (spec §10.4.6)
- The identity of each customer it holds a service agreement with (a billing DID), which admission keys each customer registered and when, and quota counters per agreement
- For push proxies, opaque device push handles and wake-up timing; a relay that serves push also knows which routing tokens wake the same device, and users may turn push off (ARCHITECTURE §5 item 7)

A relay can therefore say which network addresses used your organization's service. It cannot say which Space, channel, or sender any traffic belonged to: your agreement with it names no Space or channel, and your billing identity appears in no Space record (ARCHITECTURE §6.1). If you run several Spaces through one relay, the relay cannot tell them apart.

A relay cannot produce:

- Plaintext message content (it does not hold decryption keys)
- The identity of message senders (sender identity is hidden inside the encryption)
- Group membership, or which users are regulated
- The mapping from routing tokens to channel identities or member lists
- User accounts (relays do not authenticate users)
- Message history older than the recent envelopes it holds under your agreement's retention period

**Practical consequence for legal process.** If a relay operator serving your organization receives a third-party subpoena, the accurate response is that it holds encrypted data it cannot read, does not know who sent it, and holds connection metadata for its declared retention period. This describes what the relay holds. It is not a legal opinion. Whether this satisfies the subpoena depends on jurisdiction and the specific legal process; consult counsel.

### Takedown Notices and Abuse Reports

A relay that receives a takedown notice naming a stored CID cannot read the content. It forwards the notice, with the CID, to the contact named in its service agreement with you, and may stop serving and delete its own copy as a storage decision under its own policy and law (spec §10.4.5). Identifying the content and deciding what to do is your moderation process (spec §4.5, §4.7). Keep the agreement's contact address routed to staff who can act on legal notices.

Members report abuse to a Space owner or admin with an `AbuseReport`, which carries the reported messages as the reporter's client decrypted them (spec §4.7). Agora has no message franking, so a third party cannot verify a report: you must trust the reporter's account or compare it with your own copy. Where the compliance logger was in the group, the archived `ComplianceRecord` for the same message can be checked independently (spec §7.4).

### What Your Organization Can Produce

Your organization's compliance archive is the authoritative source for legal hold and eDiscovery. A demand served on you reaches everything your own policy retains, under your own retention and legal-hold controls (ARCHITECTURE §4). The archive contains:

- Full plaintext of all captured messages, in order, with cryptographic proof of authenticity
- Complete sender identity for each message (DID, mapping to a named employee)
- Timestamps and channel context
- Edit history and deletion records (a deletion is a separate record; the original message record remains)
- DM group compliance audit records, including any logger removal attempts and the logger's gap records

Copies also exist outside the archive. Relays hold recent ciphertext; encrypted attachments are copied among the relays serving a channel, at least two by default, and each relay keeps them only for its service agreement's retention period unless pinned (spec §10.4.4). Each member's client keeps its own store of messages it received, and a user's devices pass private data and message history among themselves through the user's self-group (spec §2.6, §5.2.5). Those copies sit on the user's devices; on devices you manage, your device policy governs them. They are not the authoritative record.

For eDiscovery, the compliance archive supports export by date range, channel, sender DID, or keyword. Keyword search runs against the `body` text of archived JMAP Chat `Message` objects, which is normally CommonMark: readable as-is, or easily stripped of markup.

### Legal Hold Procedure

When a legal hold is triggered:

1. **Identify the relevant DIDs.** Each employee corresponds to one DID. For identities your provisioning service issues, the DID contains a stable local identifier that is never reassigned to another person and never derived from a name or email address (spec §2.5.2). The provisioning service keeps the mapping from that identifier to your directory record.

2. **Suspend archive pruning for affected DIDs and channels.** The compliance archive is append-only. If your archive configuration includes a purge policy (for example, deleting records older than `retentionDays` once the retention period expires), you must suspend that purge for held content.

3. **Export the relevant records.** The compliance archive is an IPLD-structured, content-addressed dataset. Export tools should query by sender DID, channel, and date range, producing the signed `ComplianceRecord` envelopes exactly as stored, so their signatures still verify.

4. **Verify chain integrity.** Before producing records, verify that the `prevRecordCID` chain is intact for the exported range and that each logger signature verifies against the logger's DID document version in effect when the record was signed (spec §7.9). A broken chain indicates a record was altered or deleted; you must investigate and disclose it. Where authorship of a message is disputed, run the sender-signature check of spec §7.4 on its record.

5. **Preserve `DMComplianceAuditEntry` records** for any DM groups involving the relevant employees. These records document logger presence and any removal attempts.

---

## Part 4: Employee Disclosure and Consent

### Employee Disclosure

Employees in a compliance-logging-enabled Space receive a mandatory disclosure, taken from the `retentionNotice` in Space state (spec §7.5):

> "This space is subject to regulatory message retention. Messages are archived for [N] days regardless of expiry settings."

The client displays this notice before the user first sends. It keeps the notice available from the Space's information panel, together with the logger's label, retention period, and regulatory frameworks (spec §7.7).

When a regulated employee's client adds the compliance logger to a DM group, it sends a `ComplianceDisclosureNotice` to all DM participants as a visible system message before any application message (spec §7.8.4). The notice identifies the logger by label (for example, "Acme Corp Compliance Archive"), states the retention period, and lists the regulatory frameworks under which the logger operates.

### Counterparty Disclosure

External counterparties who receive DMs from regulated employees see the compliance disclosure notice before they send any message. The disclosure is informational; they are not asked to consent, and they may leave the DM group. This mirrors the recording disclosure on regulated telephone calls ("this call may be recorded for compliance purposes"), applied at the messaging layer.

### Call Recording Consent

Agora splits call recording into two consent models (spec §6.12.3):

- **Compliance recording** (`purpose: "compliance"`). Disclosure plus participation: every participant sees the disclosure before recording begins, and transmitting audio or video after that is the participant's consent. There is no veto. A participant who does not accept the recording can remain muted with camera off, or leave.
- **Operational recording** (any other purpose). Each participant's client must obtain that participant's explicit acknowledgement before sending their audio or video while the recording is active. A participant who declines stays in the call with media off; one refusal does not stop recording of others.

In both cases a participant's media is never sent automatically on join while a recording is active.

**Open legal question.** Whether these disclosures satisfy wiretapping statutes and analogous communication privacy laws in all relevant jurisdictions is a question for counsel. The one-party consent model (the regulated firm consenting on behalf of its employee) is standard for broker-dealer call recording but has not been tested for end-to-end encrypted (E2EE) messaging. Obtain counsel's opinion before deploying in jurisdictions where this is uncertain, particularly all-party-consent jurisdictions, where the compliance model's lack of a veto deserves specific analysis.

---

## Part 5: Compliance Configuration Checklist

Before deploying Agora in a regulated environment, verify the following.

**Capture scope**
- [ ] `complianceLogging.enabled` is `true` in the Space state
- [ ] `complianceLogging.regulatedMembers` lists every employee you treat as regulated, and you have a process to update it on hiring, role change, and departure
- [ ] `scope` is set to `all-channels` or explicitly confirmed to cover all channels where regulated business communication may occur
- [ ] `retentionDays` is set to meet your regulatory requirement and your own policy. Examples, to be confirmed by counsel for each record class: SEC Rule 17a-4(b)(4) business communications, at least 1095 days (3 years, the first 2 easily accessible); HIPAA, 6 years under 45 CFR 164.316(b)(2), which covers required Security Rule documentation rather than communications generally
- [ ] DM compliance (spec §7.8) is active: regulated employees use client software that conforms to spec §7.8, and the `loggerDID` is correctly configured

**Endpoint enforcement**
- [ ] Regulated employees communicate from devices you issue and manage
- [ ] Managed clients are configured so the user cannot disable the logger check or install an unmanaged client for business use
- [ ] Your audit pipeline reconciles `DMComplianceAuditEntry` records against the groups the logger holds and alerts compliance staff to discrepancies

**Logger infrastructure**
- [ ] The `loggerDID` is a DID controlled by your organization or a contracted compliance vendor acting for you, and by no other third party
- [ ] The logger, recorder, and archive run on infrastructure under your control (or your contracted processor's), and not as part of any relay operator's service
- [ ] The `logStore` archive is on infrastructure subject to your legal hold and data governance policies; any copy on IO storage is encrypted under a key you hold
- [ ] The logger's DID document includes a `KeyPackageEndpoint` service entry and the endpoint is operational. If this endpoint is down, a conformant client cannot admit the logger to a new DM group and will not let the regulated employee send in it.
- [ ] The logger issues its scheduled self-update in each group, for example weekly, so that a leaked old leaf key stops exposing later messages (spec §7.3)
- [ ] A key management policy covers the logger's and recorder's signing, MLS leaf, and archive keys: planned rotation, compromise response, and keeping each old archive private key until every archive sealed to it has passed its retention period (spec §7.9)
- [ ] If the logger's DID is a `did:webvh` DID you provision, its log names at least one witness you do not control, as spec §2.1 requires
- [ ] The logger runs in a mode that prevents deletion of records within the retention period. The append-only chain structure helps, but operational controls must prevent administrative deletion of the underlying storage.

**Audit and monitoring**
- [ ] `DMComplianceAuditEntry` records and logger gap records are being produced and are accessible to your compliance team
- [ ] Alerts are configured for logger removal attempts (alert on non-empty `removalAttempts` in `DMComplianceAuditEntry` records and on logger `ComplianceGapEntry` records; confirm alerts reach compliance staff)
- [ ] Archive integrity verification (chain hash and signature checks) runs on a schedule
- [ ] Chain heads are recorded at regular intervals with an independent witness (suggested practice: `profiles/compliance-chain-witness.md`)
- [ ] A process exists to map DID to employee name for eDiscovery production

**Continuity and infrastructure agreements**
- [ ] The Space is owned by an organization service DID rather than an individual's DID, and Space state names a `guardian` that can transfer ownership if the owner key is lost (spec §3.3, §4.1). Without one, losing the owner key means founding a new Space
- [ ] Each relay `ServiceAgreement` sets a retention period you have reviewed and a `contact` that reaches staff who handle legal notices (spec §10.4.5, §10.5.1)

**Disclosure**
- [ ] `retentionNotice` text in the Space state is accurate and legally reviewed
- [ ] Employee notification has been provided through HR/legal channels (the protocol disclosure is necessary but may not satisfy your jurisdiction's employment law requirements)

**Video teleconferencing (VTC) compliance**
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
| SEC Rule 17a-4 / FINRA Rule 4511 | Business communications kept at least 3 years, first 2 easily accessible (17a-4(b)(4)); WORM storage or a complete time-stamped audit trail (17a-4(f)(2)(i), as amended 2022) | Covered for text channels, DMs (spec §7.8), and voice/video (spec §6.12); tamper-evident chain | Auditor validation pending; capture depends on conformant clients |
| FINRA Rule 4511 | Books and records: communications with the public | Covered for Agora-channel communications including voice | Non-Agora channels not covered |
| HIPAA Security Rule (§164.312) | Technical safeguards for ePHI in electronic communications | MLS E2EE protects ePHI in transit and in relay storage; voice recording covered; archive holds plaintext and is a covered system | Whether a BAA is needed with the relay operator is a question for counsel. Facts: the relay holds ciphertext and connection metadata, no keys and no plaintext (ARCHITECTURE §4–§5). Parties running the logger, recorder, or archive hold plaintext |
| MiFID II Article 16 | 5-year retention of communications related to transactions | Covered for text and voice; 7-year retention configuration available | Cross-border jurisdiction issues |
| GDPR Article 17 (right to erasure) | Ability to delete personal data on request | Records in the compliance archive cannot be deleted during the retention period, which conflicts directly with erasure rights for regulated communications. The standard exemption for legal retention obligations applies; document the basis. | Legal analysis required per jurisdiction |
| UK FCA COBS 11.8 | Recording and retention of telephone and electronic communications | Text and voice covered; compliance call recording is disclosed and cannot be vetoed (spec §6.12.3) | |
