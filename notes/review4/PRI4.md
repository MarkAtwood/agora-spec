# Review 4, lens PRI4: S9 (MLS is the source of truth) and the UX-MUST principle

Scope: spec/, profiles/, guides/, ARCHITECTURE.md at 4b76c3d. No P1.

Checked and clean for S9: §4.6 DM groups (host keeps key-issuance state only; `agora_admission` is GroupContext), §2.6 `agora_space_membership` (GroupContext), §7.8.2 `agora_compliance` (GroupContext), §5.2.1.5 `agora_credentials` (leaf extension), §5.1.1 and §14.4 ordering (delivery service, as S9 allows), Space `members` and roles (§3.3, §4.2: CO-signed state above MLS), §4.8 leave, Kick and Ban (MLS Removes), §8.6 guest key-issuance record, call participation (§6.2, §6.3), breakout `members` (§6.14.5), `speakerCap`, SpaceAd `memberCount` (Space-level CO claim), `broadcasters` (no MLS group), and the profiles.

Checked and clean for UX: every row of notes/ux-musts.md has been applied, except where the borderline rows recommended keeping the MUST. The kept anti-spoofing rules (02:120 bidi, 05:536 raw HTML, untrusted SFU `reason`, 10:467 directory sources) and the legal-notice gates (07:163, 07:207, 07:285, 07:289, 08:133, 06:360, 06:362, 06:367, 12:229) match the principle. 07:285 and 07:289 apply to different users (members present at admission, and later joiners), so each user gets one MUST present. Guides carry no UX MUSTs. In profiles, discord-onboarding.md:185 keeps a fingerprint-comparison MUST, as the borderline table recommended. The rest are CO-service alerting, which is not user agent UX.

### PRI4-1: JMAP `Chat` membership has two sources, and member edits have no MLS mapping
- Severity: P2
- Location: spec/14-jmap.md:61; spec/14-jmap.md:285-288 (§14.6.1 Overridden)
- Evidence:
  - 14:61: "`SpaceInvite`, `Chat` membership | derived | CO-signed Space state (§3.3), MLS group membership | ... Members never replicate these as JMAP writes."
  - §14.6.1 overrides only "`Space/set` and the other Space-family `/set` calls". It says nothing about `Chat` members.
  - draft-atwood-jmap-chat defines `Chat.members` ("Full membership list"), and `ChatMember.role` ("Either "admin" or "member". Admins may add and remove members"), `joinedAt` and `invitedBy`. Its send check requires that "the sender must be a member of the containing Space".
  - 04:293: "Leaving a channel ... Space state does not change: the member's roles still permit it to read the channel".
  - 04:221: a DM group "is owned by its members collectively".
- Problem:
  - Two stores can derive a channel Chat's members differently:
    - one store derives members from Space roles plus `channelAccess`, and still lists a member who left the channel;
    - another store reads the ratchet tree, and does not list that member.
  - A DM group has no admins, yet the draft's admin/member split, `joinedAt` and `invitedBy` have no Agora source.
  - A `Chat/set` that changes `members` has no translation to MLS Add or Remove. A store can therefore keep its own separately updated member list, which S9 forbids.
  - The draft's Space-member send check is not overridden to the MLS sender check.
- Fix:
  - Split the 14:61 row:
    - (a) "`Space`, `SpaceRole`, `SpaceMember`, `SpaceBan`, `Category`, `ChannelPermission`, `CustomEmoji`, `SpaceInvite` | derived | CO-signed Space state (§3.3)".
    - (b) "`Chat.members` | derived | the group's ratchet tree only (ARCHITECTURE S9)".
  - Add this text to §14.6.1 Overridden: "`Chat.members` is the DIDs with leaves in the group's current epoch. `ChatMember.role` is `member` for every DM group member (§4.6.2). A Space channel's admin standing comes from Space state. `joinedAt` and `invitedBy` are the local receipt time and the committer of the Commit that added the DID's first current leaf. A `Chat/set` change to `members` is translated into an MLS Add or Remove Commit, or rejected locally where Space state forbids it. The draft's member check on send is the MLS sender check of §5.2.1."
- Needs decision: no

### PRI4-2: Gateway "active" status is read from Space state only, and there is no removal path
- Severity: P3
- Location: spec/09-interop.md:83-87 (§9.3)
- Evidence:
  - "the `gateways` array in Space state is [the durable record]"
  - "Clients SHOULD display an indicator when a channel has active gateways."
  - "Members who joined after a gateway was added see the indicator from the `gateways` array in Space state".
  - spec/ has no text on removing or retiring a gateway.
- Problem:
  - The descriptor is legitimate CO authorization (S4). But "active" is undefined, and nothing ties the descriptor to the gateway's leaf.
  - If the leaf is removed but the descriptor stays, clients show a bridge that is gone.
  - If the descriptor is dropped but the leaf stays, a plaintext-holding member remains in the group while clients show no gateway. The gateway's send-gate covers only the start of bridging.
- Fix: add to §9.3:
  - "A gateway is active in a channel when its DID holds a leaf in the channel's group (ARCHITECTURE S9) and its `GatewayDescriptor` is in current Space state."
  - "To remove a gateway, an admin commits MLS Removes for every leaf of its DID, then publishes Space state without its descriptor."
  - "A gateway whose descriptor is no longer in current Space state MUST stop carrying messages."
- Needs decision: no

### PRI4-3: Ring duration cap is a MUST on notification behavior
- Severity: P3
- Location: spec/06-calls.md:512; spec/99-appendices.md:73
- Evidence:
  - 06:512: "Clients MUST NOT ring for more than 120 seconds after receipt, whatever `ringUntil` says."
  - 99:73: "| Ring duration | 120 s after receipt | MUST NOT exceed | §6.14.1 |"
- Problem: Ringing is local alerting. It sends nothing on the wire and does not affect interop. The rule constrains user agent notification, which is not one of the kept exceptions (memory agora-ux-musts).
- Fix:
  - 06:512: "Clients SHOULD NOT ring for more than 120 seconds after receipt, whatever `ringUntil` says."
  - 99:73: "SHOULD NOT exceed".
- Needs decision: no

### PRI4-4: Compliance recording disclosure has a second, content-level client MUST
- Severity: P3
- Location: spec/06-calls.md:373
- Evidence:
  - 06:360 already gates transmission: "a client MUST present the `participantDisclosure` string from the `RecordingGrant` to its user."
  - 06:373: "For compliance grants (`"purpose": "compliance"`), the disclosure a client presents MUST identify the `recorderLabel` from the Space's `vtcCompliance` block (§6.12.5) and the grant's `retentionDays`".
- Problem:
  - 06:373 is a second MUST on the same legal notice, and it constrains what the client renders. The principle allows one MUST present per notice.
  - It also makes the client compose text beyond the signed `participantDisclosure` string, so implementers will produce different text.
  - The CO already signs the grant, so the content duty is enforceable at the source.
- Fix: put the obligation on the signed data. Replace 06:373 with: "For compliance grants (`"purpose": "compliance"`), the grant's `participantDisclosure` MUST identify the `recorderLabel` from the Space's `vtcCompliance` block (§6.12.5) and the grant's `retentionDays`, with wording equivalent to:"
- Needs decision: no

### PRI4-5: "Notify Space admin of logger removal attempt" is a MUST with no mechanism
- Severity: P3
- Location: spec/07-compliance.md:263; spec/07-compliance.md:369; guides/counsel.md:236
- Evidence:
  - 07:263: "and notify the regulated member's Space admin of the removal attempt. ... The Space admin MUST be notified so they can assess the compliance gap."
  - 07:369: "| Notify Space admin of logger removal attempt | Regulated member's client | MUST |"
  - §7.8.9: "The compliance logger MUST record every capture gap it can detect ... including its own removal from a group ... as a `ComplianceGapEntry`".
- Problem:
  - No message type, endpoint or channel is defined for this notification, so implementers cannot meet it in a common way and conformance cannot be tested.
  - The CO already learns of the removal from the logger's signed `ComplianceGapEntry`, which is the enforceable record.
  - The passive "MUST be notified" names no actor.
- Fix:
  - 07:263: replace the last sentence with "The logger's `ComplianceGapEntry` (§7.8.9) is the CO's record of the gap. The client SHOULD also notify the Space admin through a channel the CO configures."
  - 07:369: change the cell to SHOULD.
  - guides/counsel.md:236: change "the spec requires notification to the Space administrator" to "the spec records the gap as a `ComplianceGapEntry` and recommends a client notification".
- Needs decision: no
