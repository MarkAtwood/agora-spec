# Review 4, lens PRI4: verification

Verified against the working tree at 4b76c3d, the jmap-chat draft at
/home/mark/PROJECT/jmap-chat-spec/draft-atwood-jmap-chat-00.md, and `bd memories agora`
(agora-ux-musts, agora-dm-removal, agora-dm-no-add-consent, agora-recording-consent,
agora-gateways-profile).

Summary: 3 CONFIRMED, 2 PARTIAL, 0 REJECTED. No finding needs a decision.

### PRI4-1: JMAP `Chat` membership has two sources, and member edits have no MLS mapping
- Verdict: PARTIAL.
  - Rejected part: the channel case. The draft gives channel Chats no member list: "`members` (ChatMember[]): **Group chats only.** Full membership list." and "Channel Chats do not carry a `members` field; membership and access control are determined by the containing Space." So no store derives a channel Chat's members at all, and 04:293 (leaving a channel) creates no conflict. The 14:61 row split is not needed.
  - Rejected part: the send check. For a group Chat the draft's check is "a ChatMember record exists", which becomes MLS membership once `members` is the ratchet tree. A channel message arrives only as an MLS message from a leaf, and §14.6.1 already moves channel permission checks onto Space state. No separate override is needed.
  - Confirmed part: DM groups (draft `group` Chats). The draft says `ChatMember.role` is "Either "admin" or "member". Admins may add and remove members", and `addMembers`, `removeMembers` and `updateMemberRoles` "all require admin role". This contradicts 04:202 and 04:221 ("Any member can add (§4.6.1) or remove (§4.6) any other member; no member has authority over the rest") and memories agora-dm-removal and agora-dm-no-add-consent. §14.6.5 replaces `Peer/groupUpdate` with MLS Commits, but no text says what a store does with a `Chat/set` member patch, or where `joinedAt` and `invitedBy` come from.
- Severity: P3 (was P2). The 14:61 row already sources `Chat` membership from MLS group membership, so S9 is stated. What is missing is a local API mapping. The wire behavior (MLS Add and Remove Commits, and 04:202 "members MUST NOT treat such a Commit as a policy violation") is already fixed, so two stores cannot disagree on the wire.
- Fix: add one bullet to §14.6.1 Overridden (spec/14-jmap.md, after the `Space/set` bullet):
  - "A DM group (§4.6) is a `group` Chat. Its `members` are the DIDs with leaves in the group's current epoch (ARCHITECTURE S9), and every `ChatMember.role` is `member` (§4.6.2). `joinedAt` is the local receipt time of the Commit that added the DID's first current leaf, and `invitedBy` is that Commit's committer. The store translates `addMembers` and `removeMembers` into an MLS Add or Remove Commit (§4.6.1, §4.6), which any member may make, and rejects `updateMemberRoles` locally."
- Needs decision: no

### PRI4-2: Gateway "active" status is read from Space state only, and there is no removal path
- Verdict: PARTIAL. The gap is real: "active" is undefined, and spec/ and profiles/gateways.md have no removal text. The send-gate reads as a one-time gate ("MUST NOT carry messages ... until its `GatewayDescriptor` is in the channel's current Space state"). The proposed definition of active is wrong, though. "Active when its DID holds a leaf ... and its `GatewayDescriptor` is in current Space state" turns the indicator off in exactly the dangerous case the finding names: a leaf with plaintext access and no descriptor. Fix the ordering instead, so that case cannot arise from a correct admin, and define active from the descriptor alone. The finding's third sentence is better phrased as a change to the existing send-gate than as a new rule.
- Severity: P3, keep.
- Fix (spec/09-interop.md §9.3):
  - Send-gate, replace "A gateway MUST NOT carry messages in either direction until its `GatewayDescriptor` is in the channel's current Space state and it has received that `SystemEvent`." with "A gateway MUST carry messages in either direction only while its `GatewayDescriptor` is in the channel's current Space state, and only after it has received that `SystemEvent`."
  - After the send-gate paragraph, add: "**Removal.** An Admin removes a gateway by committing MLS Removes for every leaf of its DID, and only after that Commit has won (§5.1.1) publishes Space state without its `GatewayDescriptor`. A channel has an active gateway while a `GatewayDescriptor` for it is in the channel's current Space state."
- Needs decision: no

### PRI4-3: Ring duration cap is a MUST on notification behavior
- Verdict: CONFIRMED. 06:512 and 99:73 match the quotes. notes/ux-musts.md does not list the line as a kept exception. Memory agora-ux-musts names notification as UX ("never constrain user agent UX (display, notification, prompts, rendering)"). The anti-spoofing exceptions cover forged or injected text, not alert duration. The cap does limit abuse from a peer-set `ringUntil`, but the user can decline, and a SHOULD still guides every implementer.
- Severity: P3, keep.
- Fix: as proposed. spec/06-calls.md:512: "Clients SHOULD NOT ring for more than 120 seconds after receipt, whatever `ringUntil` says." spec/99-appendices.md:73: change the third cell to "SHOULD NOT exceed".
- Needs decision: no

### PRI4-4: Compliance recording disclosure has a second, content-level client MUST
- Verdict: CONFIRMED. 06:360 already holds the one MUST present ("a client MUST present the `participantDisclosure` string"). 06:373 adds a second client MUST on what the client renders. The example grant at 06:324 already carries that wording in the signed string, so putting the duty on the signed data costs nothing. This matches agora-recording-consent (compliance grants are disclosure plus participation). One thing the fix must cover: under 12:231, `participantDisclosure` MAY be a language map, so the duty applies to every value.
- Severity: P3, keep.
- Fix: replace the sentence at spec/06-calls.md:373 with "For compliance grants (`"purpose": "compliance"`), the issuer MUST write a `participantDisclosure` that identifies the `recorderLabel` from the Space's `vtcCompliance` block (§6.12.5) and the grant's `retentionDays`, in every value if it is a language map (§12.10), with wording equivalent to:". Keep the quoted wording that follows unchanged.
- Needs decision: no

### PRI4-5: "Notify Space admin of logger removal attempt" is a MUST with no mechanism
- Verdict: CONFIRMED. The quotes match. No message type or endpoint for the notification exists in spec/ ("notif" in 07 appears only at 54, 185, 205, 263, 285, 289, 313, 369). The finding misses that a second CO record already exists: §7.8.8 `removalAttempts` (07:334: "timestamps and initiator DIDs for any Remove commits targeting the logger ... This gives the Space admin and compliance officer a complete record"), which the logger publishes in `DMComplianceAuditEntry` (07:370). CO-side alerting on it is already described in profiles/purview-bridge.md:607. The proposed SHOULD "through a channel the CO configures" adds an undefined mechanism. The constraint fix is to delete the client notification and name the existing records as the notice. The finding also misses two guide lines that promise the notification: guides/counsel.md:104 and guides/regulators.md:332.
- Severity: P3, keep.
- Fix:
  - spec/07-compliance.md:263: change "... restores its `agora_compliance` entry, and notify the regulated member's Space admin of the removal attempt." to "... restores its `agora_compliance` entry." Replace the last sentence, "The Space admin MUST be notified so they can assess the compliance gap.", with "The removal attempt is recorded in `removalAttempts` (§7.8.8) and the gap as a `ComplianceGapEntry` (§7.8.9); these records are how the Space admin learns of it."
  - spec/07-compliance.md:369: delete the row "Notify Space admin of logger removal attempt".
  - guides/counsel.md:104: change "re-adds the logger, and **notifies your Space administrator** of the removal attempt." to "re-adds the logger. The attempt is recorded in your compliance audit chain (below)."
  - guides/counsel.md:236: change "(the spec requires notification to the Space administrator; confirm it is routed to compliance staff)" to "(alert on non-empty `removalAttempts` in `DMComplianceAuditEntry` records and on logger `ComplianceGapEntry` records; confirm alerts reach compliance staff)".
  - guides/regulators.md:332: change "Each removal attempt is a compliance event and should have been reported to the firm's administrator at the time." to "Each removal attempt is a compliance event; confirm the firm alerts on these records."
- Needs decision: no
