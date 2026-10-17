# Copyedit defects: triaged

Source: `notes/copyedit-defects.md` (122 raw items), after verification and de-duplication. Each item below was checked against the current text. Line numbers are approximate where marked `~`.

Settled by Mark (2026-10-17), so they are not listed as decisions:

- **Serial comma:** follow W3C. The `agora-style-serial-comma` decision adopts the W3C Manual of Style, which defers to Chicago, and Chicago uses the serial comma. Fixes below that touch lists use it.
- **Bead IDs in reader-facing text** (for example "Open (agora-pozi.8)" and the profile "Sources:" lines) stay.

## 1. Fixes needing no decision

Ordered by severity. P2 items can make implementers diverge. P3 items are wording, cross-reference, or rendering fixes.

### P2

1. **Sequencer replacement head can force group-state deletion.** spec/14-jmap.md §14.4.5. The MUST covers only winning Commits, but §5.1.1 needs gap-free positions.
   Replace "every winning Commit (§5.1.1) at or below it is available" with "every position at or below it is available".
2. **"Direct peer connections are mandatory for voice and video" contradicts SFU topology.** spec/11-transport.md:217.
   Replace the sentence with: "Voice and video media travel over WebRTC, either directly between peers or through an SFU (§6.5), and MUST NOT transit relays. Direct data channels for text messaging are optional (latency optimization)."
3. **HTTP fallback is "or" in §10.2 and "and" in §10.2.2.** spec/10-relays.md:41.
   Replace the whole sentence starting "The Peer API (§10.2.2) SHOULD be served over **HTTP/3**" with "The Peer API is served over HTTP/3 with an HTTP/1.1 and HTTP/2 fallback (§10.2.2)."
4. **Revocation removes "all members of the foreign Space", which is the home Space when the guest revokes.** spec/08-cross-space.md §8.7 step 1.
   Replace "for all members of the foreign Space" with "for all guest Space members".
5. **SFU stream-to-DID mapping cites an undefined exchange and understates what the SFU sees.** spec/06-calls.md §6.6 (~187).
   Replace the paragraph with: "Participants map each SFU-forwarded stream to its sender through the leaf index in the stream's SFrame KID (§6.9) and that leaf's credential in the ratchet tree. This mapping is not authenticated (§6.10). What the SFU can observe is listed under SFU Media Opacity."
6. **Admin token: §5.1 says reload, §10.3 says restart.** guides/relay-operator.md §5.1 (~909).
   Replace "rotated via `POST /admin/reload` after updating the environment variable" with "rotated by updating the environment variable and restarting the relay (§10.3)".
7. **Role change described as an MLS Commit that leaves group membership unchanged; spec §4.2 says otherwise.** profiles/o365-employer-did.md §5.3.
   Replace the paragraph body with: "When `agoraRoles` changes, the Enrollment Service (notified by webhook from the sidecar), acting as a Space admin, signs a Space state mutation of `members` that sets the user's new roles (spec §4.2, §3.3). It then commits MLS Adds and Removes for the channel groups that the new roles grant or withdraw."
   Also capitalize "Commit(s)": §1 table "MLS Remove Commits", §5.4 "After these Commits propagate", §6.1 "Acknowledgment of MLS Remove Commit".
8. **VC acceptance link: in the invitation (Option A) or after first-device enrollment (last paragraph).** profiles/gsuite-employer-did.md §5.3.
   Replace "The enrollment invitation includes a second link for VC acceptance." with "After first-device enrollment, the sidecar emails the user a link for VC acceptance."
9. **Invitation transport inconsistent, and the Gmail send scope is missing.** profiles/gsuite-employer-did.md §4.2 step 5 and §2.1.
   Step 5: "via Google Workspace SMTP relay or Gmail API" to "via the Gmail API (see below)". Add §2.1 row: | `https://www.googleapis.com/auth/gmail.send` | Send enrollment invitation and VC acceptance emails as the sender address (§4.2, §5.3) |.
10. **OneLogin event IDs look wrong, and polling never sees deletions.** profiles/universal-idp-did.md §3.5 and §7 OneLogin row.
   §3.5: poll `event_type_id=4,13,14,15,16,17,32,<role-removed id>` (13 created, 14 updated, 15 deactivated, 16 activated, 17 deleted, 32 reactivated, 4 role assigned, <id> role removed). §7: PROVISION 13; UPDATE 14, 4, <id>; SUSPEND 15; REACTIVATE 16, 32; TERMINATE 17.
   Unverified: the source table is deprecated. Confirm every ID with `GET /api/1/events/types` before committing.

### P3: spec

11. **WebTransport cited as RFC 9000 (QUIC).** spec/01-overview.md:46, spec/99-appendices.md:17, spec/11-transport.md:15.
    01 and 99: "WebTransport (RFC 9000)" to "WebTransport over HTTP/3 (draft-ietf-webtrans-http3)". 11: "(IETF RFC 9000 / HTTP/3 over QUIC)" to "(WebTransport over HTTP/3, draft-ietf-webtrans-http3; HTTP/3 is RFC 9114 and runs over QUIC, RFC 9000)".
    Before committing, check the datatracker. Use the RFC number if one has been published; otherwise pin the draft revision, as the corpus does for `draft-ietf-mls-extensions-09`. Do not use RFC 9220 (that covers WebSockets).
12. **TURN cites obsoleted RFC 5766.** spec/99-appendices.md:21: "RFC 5766 / RFC 7065" to "RFC 8656 / RFC 7065".
13. **DM admission host: "or when they are active" is garbled.** spec/12-security.md:258.
    Replace "except those of its own users whose clients also request keys for the group, or when they are active." with "except those of its own users whose clients also request or confirm keys for the group, and when they do so (§4.6)."
14. **SHOULD on "a channel" weakens mandatory rotation on removal.** spec/12-security.md:54.
    Replace with "The CO therefore SHOULD register the rotated key, and deregister the old one, promptly after each removal (§5.2.2, §10.5.3)."
15. **Expiry rule is a lowercase clause inside a MUST NOT.** spec/12-security.md:185.
    Replace ", and checks expiry against its own clock with no added tolerance." with ". It MUST treat an object as expired once its own clock reaches the expiry time, with no added tolerance." Optional Appendix C row: "Clock skew tolerance for expiry | 0 s | MUST | §12.9".
16. **Duplicate-DID rejection stated twice.** spec/13-encoding.md:59 (optional).
    Change to "A verifier MUST require valid entries from at least k distinct DIDs in the candidate set and MUST reject an entry whose DID is not in the candidate set." Line 86 keeps the rule.
17. **Withdrawn-token recovery: scope and "its token" unclear.** spec/11-transport.md:201.
    Replace the last two sentences with: "If the current key's token differs from the refused one, the client uses the current key. Otherwise the client uses another relay in the key's relay list (§10.3.5); in a DM group or self-group, if every listed relay it can reach refuses that token, the client applies the recovery of §4.6 instead of retrying."
18. **Phantom "read-only" mark; envelopes called blobs.** spec/11-transport.md:482, 486. Delete "Methods marked **read-only** have no `/set`." Change "Returns encrypted blobs." to "Returns envelopes."
19. **"JMAP is used only for history and blobs" ignores the management API.** spec/11-transport.md:9: replace with "The sync API carries only history and blobs;".
20. **Push list switches actor at step 3.** spec/11-transport.md:368. Move step 3 after the list as: "On receiving it, the proxy maps `pushHandle → deviceToken` and sends a push notification with no content to APNs or FCM."
21. **`knownPeers` "current" vs 7-day retention.** spec/10-relays.md:116: "`knownPeers` lists the relay's peers, including any peer marked unreachable within the last 7 days (§10.2.6)."
22. **DNS-SD called mDNS.** spec/10-relays.md:366: replace "mDNS for LAN or overlay discovery (§10.2.5)." with "SRV and TXT records under a configured domain, including overlay-internal DNS (§10.2.5)."
23. **RelayAd "all available endpoint URIs" conflicts with §10.5.1.** spec/10-relays.md:639: "including all available endpoint URIs." to "listing its client-facing endpoints (§10.5.1)."
24. **Broadcast gateway described only in MLS terms.** spec/09-interop.md:11, 13 (82 optional).
    11: "On an MLS channel it signs routing envelopes with the channel admission key it obtains as a member (§5.2.2); on a broadcast channel it posts as any poster does, under the `BroadcastKey` and the complete `ChannelAdmissionKey` served to holders of a role in `broadcasterRoles` (§5.2.1.4)." 13: append "(on a broadcast channel, as the post's `senderDID`, §5.2.1.4)". 82 optional: "and, for a channel with `keyAccess` `public`, its DID in the channel's `broadcasters` list (§5.2.1.4)".
25. **"their own Space's profile" names no defined object.** spec/08-cross-space.md §8.4: "Clients SHOULD display the guest member's display name from that member's profile (§2.3), with the foreign Space indicator making affiliation clear."
26. **"the home CO does this" scope.** spec/08-cross-space.md §8.7 step 1: "When the guest admin revokes, the home CO rotates the key and stops serving it as soon as it receives the revocation."
27. **retentionNotice timing reads stricter than the MUST.** spec/08-cross-space.md §8.8: "For example, the client can display the notice on first entry to the shared channel:"
28. **"The regulated member's Space MUST record".** spec/07-compliance.md:328: "The compliance logger MUST record each of its DM group admissions in the regulated member's Space's IPLD compliance audit chain."
29. **`loggerLabel`, `enabledBy`, `enabledAt` undefined.** spec/07-compliance.md after L41, add: "- `loggerLabel` is a human-readable name for the logger, shown in disclosure notices (§7.8.4)." and "- `enabledBy` is the DID that enabled logging and `enabledAt` the time it was enabled (RFC 3339). Both are informational; the Space state signature (§13.1.1) is the authority." Optional L186: "and `retentionDays`, and the logger's `regulatoryFramework` (§7.3),".
30. **Ambiguous parenthetical.** spec/07-compliance.md:316: "a participant who has no Space affiliation, or whose Space has no compliance logging," and "That participant receives".
31. **Lists broken by column-0 fences.** spec/07-compliance.md:357-369 (indent two spaces, blank line before L370); spec/05-messaging.md:122-130 (indent two spaces, blank lines before each block).
32. **Lowercase "must" with no actor.** spec/06-calls.md §6.12.6: "A non-empty array records a compliance gap. This entry is how the compliance officer learns of the gap."
33. **"no client may add it".** spec/06-calls.md §6.6: "and clients MUST NOT add it to one."
34. **"only an admin or owner" contradicted by the next sentence.** spec/06-calls.md §6.12.1: "Except as described below, only an admin or owner may issue it, so it is a CO-signed record".
35. **Out-of-sync flag has two end conditions.** spec/05-messaging.md:42: "The member keeps its state until it accepts a Welcome for the group, which replaces that state (§4.3, §4.6). It clears the flag when it accepts such a Welcome or when it processes a Commit for a later epoch issued by another member."
36. **Withdrawn-token clause scope.** spec/05-messaging.md:305: "(§4.6); when a relay reports a token withdrawn, it first fetches" to "(§4.6), and when a relay reports a token withdrawn it first fetches".
37. **Retired headings over live rules.** spec/05-messaging.md:482/484, 493/495, 630/632 (numbers unchanged; no anchors cited).
    482 "#### Pin List"; 484 drop "Retired. " and append "(Agora's former `pins` array is retired.)". 493 "#### Pin Updates"; 495 "A pin or unpin (formerly PinEvent and UnpinEvent) is". 630 "#### 5.2.8.2 Reaction Body"; 632 "A reaction (formerly ReactionEvent) is". Leave §5.2.7.
38. **Takedown restatement.** spec/04-access-control.md:302: "it forwards the request to the CO at the agreement's `contact` and can stop serving and delete the CID."
39. **Request-state skip reads as removal-only.** spec/04-access-control.md:223: "A client that holds the group in the message request state (§4.6.3) skips this duty and the periodic rotation below, so rotation can then wait for the fallbacks."
40. **"accepted a Subscribe" used before definition.** spec/04-access-control.md: move the definition sentence from the start of the L227 paragraph to the start of the L215 paragraph.
41. **"Every channel has a mode".** spec/03-spaces.md:17: "Every text channel has a **mode**".
42. **Wrong cross-reference.** spec/03-spaces.md:170: "(§3.4)" to "(§4.4)".
43. **Stale "well-known URL path".** spec/02-identity.md:297: "- Serves each user's DID log (`did.jsonl`) at the URL derived from the DID, as given above".
44. **Pkarr names with trailing dots.** spec/02-identity.md:39-41: drop the trailing dot from `_agora.`, `_kp._agora.`, `_profile._agora.`.
45. **`did-key` for the method.** spec/02-identity.md:74: "`did:key` generation and resolution is implemented by:".
46. **Actorless audit MUST.** spec/02-identity.md:493: "The provisioning service MUST record this operation in its audit log, and the added key".
47. **Missing manifest cross-reference.** spec/01-overview.md:23: "A relay's manifest `capabilities` array (§10.2.1) declares which versions it supports."
48. **Number grouping (Chicago).** spec/99-appendices.md:59, 60 and spec/10-relays.md:318 and spec/14-jmap.md:223: "65536 bytes" to "65,536 bytes"; spec/99-appendices.md:99: "259200 s" to "259,200 s". Prose and tables only; leave code and 4-digit values.

### P3: ARCHITECTURE, PROPOSAL, PRFAQ, README

49. **Registration service said to issue DM keys.** ARCHITECTURE.md §6.2 bullet 1: "for each channel and each direct message (DM) group, numbered by a counter `keyEpoch`." to "for each channel, numbered by a counter `keyEpoch`."
50. **Re-propose rule placed under the no-sequencer path only.** ARCHITECTURE.md §6.2: delete "Clients discard the losing Commit and re-propose." and add after the no-sequencer sentence: "In either case, a client whose Commit lost discards it and, if the change is still wanted, re-proposes it in the winning epoch."
51. **"capture" ambiguous.** PROPOSAL.md:54: "or capture from a" to "or compliance capture from a".
52. **Opt-in actor and list unnamed.** PRFAQ.md:31: "The full list (ARCHITECTURE §5) is closed and normative. Anything not on it is a protocol violation, and any extension to it must be opted into by the Communications Operator and declared in the relay manifest, where members can see it."
53. **"first ship" vs "first release".** README.md:24: "Out of scope for the first release".
54. **Abbreviations not expanded on first use.**
    profiles/gateways.md:15 "Native More Instant Messaging Interoperability (MIMI) interop would not", and L93 "MIMI is". spec/02-identity.md:288 "User Principal Name (UPN)", :306 "System for Cross-domain Identity Management (SCIM) 2.0", :335 "multi-factor authentication (MFA)". README.md:24 "chief information officer (CIO) assessment".
    profiles/radio-mesh-gateway.md:15 "Object Security for Constrained RESTful Environments (OSCORE, RFC 8613) security"; :53 "LICHEN trust on first use (TOFU)"; :136 "position location information (PLI)"; :138 "Ephemeral Diffie-Hellman Over COSE (EDHOC, RFC 9528)"; :174 "Compact Cursor on Target (CoT)".

### P3: guides

55. **base64url vs `openssl rand -base64`.** guides/relay-operator.md §5.1 (~903): "base64url-encoded" to "base64-encoded".
56. **Relay removes itself from its own `knownPeers`.** guides/relay-operator.md §16.5: delete step 2, renumber step 3.
57. **Diagram says primary/replica; text recommends active-active.** guides/relay-operator.md §15.1 (~2221): `│  (primary)  │      │  (replica)   │` to `│  (active)   │      │  (active)    │`.
58. **Local blob store under the S3 heading.** guides/relay-operator.md §11.3: "clients fetch blobs through the relay process on existing ports, never directly from the object store".
59. **Undefined "control requirement".** guides/regulators.md 17a-4: "so the firm can produce records promptly without depending on a platform operator."
60. **Redundant "(not later)".** guides/regulators.md GDPR "What to verify": delete " (not later)".
61. **Mixed fragment and sentence bullets.** guides/regulators.md.
    Push proxy: "- For push proxies, opaque device push handles, wake-up timing, and which routing tokens wake the same device (users may turn push off; ARCHITECTURE §5 item 7)". Archive Completeness 1: "- Verify the archive starts from the date compliance logging was first enabled", move the rest to a paragraph after the list. DM Compliance: "- Review removal attempt records and confirm the firm alerts on each one (each removal attempt is a compliance event)".
62. **Logger vs recorder.** guides/counsel.md Part 1 Voice and video: append "The recorder may be the same principal as the logger or a separate one (spec §7.6)."
63. **MiFID 7-year figure unexplained.** guides/counsel.md Part 6: Key Requirement "5-year retention of communications related to transactions (up to 7 years where the competent authority requests, Art. 16(7))"; Coverage "Covered for text and voice; `retentionDays` can be set to 7 years (2555 days)".
64. **Missing period.** guides/counsel.md Part 6 HIPAA Gap cell: "hold plaintext. |".

### P3: profiles

65. **"Relays play no part" vs admission-key registration.** profiles/o365-employer-did.md §1: "Relays play no part in IdP authentication or DID provisioning. They never receive or verify Entra tokens; identity provider (IdP) authentication runs between the client, Entra, and the sidecar (spec §2.5.2). The sidecar's only contact with relays is registering admission keys (§6.7)."
66. **"The two components" table lists four parts.** profiles/o365-employer-did.md §1: "The two components are independent and address different concerns. The table maps each concern to the part that handles it, including the DID log and the Enrollment Service:"
67. **Recovery key called a device key.** profiles/o365-employer-did.md §5.5: "The user's other keys (the phone's device key and the recovery key) are unaffected."
68. **Bare § means spec.** profiles/o365-employer-did.md:645: "a spec §3.5 bearer token".
69. **Stub paragraph placement** (optional). profiles/o365-employer-did.md: move §3.1 paragraph 3 to the end of §3.2; "(§3.2)" to "(above)".
70. **`SourceEvent` vs `Source`.** profiles/universal-idp-did.md §5.5: `Source = "manual"`.
71. **"All four providers use the webhook receiver".** profiles/universal-idp-did.md §3.1: "All four providers' webhooks use the same sidecar webhook receiver (`POST /v1/notify`) with provider-specific payload adapters. For OneLogin, webhooks are a supplement to Events API polling (§3.5)."
72. **Duplicate MUST.** profiles/universal-idp-did.md §4.2: "The sidecar keys the user record on `externalId`, falling back to the SCIM `id` (§4.4); this is the `stableID` mapped to the DID (§1)."
73. **BCP 14 keywords binding humans in Open Issues.** profiles/purview-bridge.md:679 "SHOULD be confirmed with" to "needs confirmation from"; :681 "The compliance officer needs to review and resolve mapping gaps as they are alerted (§2.3, §9.2)."
74. **Actorless rotation SHOULD.** profiles/purview-bridge.md:86: "The operator SHOULD automate certificate rotation with Azure Key Vault or an equivalent HSM-backed credential store." Leave §2.3.
75. **Over-broad write scope.** profiles/gsuite-employer-did.md §2.1: delete the `admin.directory.user` row; read-only row purpose "Read user records for provisioning and watch the Users resource for push notifications (§2.2)".
76. **"for DID derivation".** profiles/discord-onboarding.md §6.4: "The CLI retrieves the public key for the DID document (and, for `did:key`, to derive the DID)."
77. **Orphan CSP clause.** profiles/discord-onboarding.md §12: delete ", which is separate from the Content Security Policy".
78. **PKCS#11 path hidden in a parenthetical.** profiles/discord-onboarding.md §6.6: "... MUST NOT write the private key to any software keystore or file. It MUST either output the private key only as a recovery phrase for the user to write on paper, or generate it as a non-extractable key on a PKCS#11 token."
79. **"stateless" vs challenge records.** profiles/discord-onboarding.md §2: "It is stateless beyond the provisional member list and outstanding enrollment challenges (§5.4). It MUST NOT hold users' private keys or session state between requests (beyond a short-lived OAuth2 state token and the challenge record)."
80. **Re-publish actor.** profiles/discord-onboarding.md §3.1: "After enrollment, the user's Agora client SHOULD re-publish the record every 2 hours (spec §10.3.4.6)."
81. **Orphan §5.2.** profiles/radio-mesh-gateway.md:81 "### 5.1 Batching and padding"; :59 "(§5.1)".
82. **"Radio command traffic" undefined.** profiles/radio-mesh-gateway.md:37: "IRONWEED command (C2) traffic (SPEC §11.4) is never bridged, whatever the filter lists."
83. **Bare "C" reads as a broken decision ID.** profiles/corundum.md:156-157: "Resolved (Mark, 2026-10-17):".
84. **"None made" vs a checked item.** profiles/corundum.md:119: append "The one checked item was made on the Agora side."
85. **Depends on omits cited sections.** profiles/corundum.md:6: add spec §4.6, §10.4.4, §10.5.3 in order.
86. **`loggerDID` and `ts` undefined.** profiles/compliance-chain-witness.md §2: before `indexCID` add "- `loggerDID` is the Space's `complianceLogging.loggerDID` (spec §7.2), the DID that signs the envelope."; after `recordCount` add "- `ts` is the time the logger produced the head, as an RFC 3339 UTC timestamp."
87. **Re-seal mapping gives no examiner action.** profiles/compliance-chain-witness.md:124-126: "Where an archive object was re-sealed after an archive-key compromise, follow the `ArchiveResealEntry` whose `oldCID` is the CID the record names to its `newCID`, repeating for each later re-seal. Verify each entry's signature and its place in the audit chain, then match the object held against the last `newCID` (spec §7.9)."
88. **Missing header fields.** profiles/compliance-chain-witness.md after line 3: "**Status:** Draft" and "**Depends on:** spec §7, §7.4". Add no Sources lines anywhere.
89. **Passive "members should be told".** profiles/gateways.md §4.3: "**Disclosure.** The peer provider learns the room's participant list, so native interop would need a disclosure to members comparable to the gateway disclosure in spec §9.3."
90. **Two added keys unnamed.** profiles/parlance.md:39: "plus two keys, `topic` and `catalogue`:".

## 2. Decisions for Mark

Ordered by severity.

### D1. §12.2 periodic key rotation and the Appendix C "7-day MLS epoch lifetime" row (P2)

spec/12-security.md:11 and spec/99-appendices.md:69. The SHOULD binds an undefined "Space operator", nothing can enforce it, and a maximum epoch lifetime does not heal a compromised leaf.

- A) Client duty: each active member updates its own leaf at least every 7 days. Text: "A member's client SHOULD send a Commit with an UpdatePath that replaces its own leaf in each channel group it belongs to at least every 7 days while it is active in that group." Appendix C: "Own-leaf update interval | 7 days maximum | SHOULD | §12.2".
- B) New Space-state field (maximum leaf age) that admins enforce by removing stale leaves.
- C) Drop the SHOULD and the row.

**Recommendation: A.** It is a constraint that fits the existing weekly passive self-update and adds no mechanism.

Plain language: The spec asks an undefined party to rotate keys and gives no way to do it. Option A makes each device refresh its own key weekly, which is what actually restores security after a compromise.

### D2. Owner-only changes to `guardian` and `admins` have no client check (P2)

spec/03-spaces.md:166, 168. "Only the owner may change" is lowercase prose, so a `["*"]` admin could rewrite `guardian` (who can transfer ownership) or promote itself.

- A) "Clients MUST reject a state document that changes `guardian` and is not signed by the owner." and the same for `admins`, matching the existing `deleted` rule.
- B) One MUST-reject rule in §4.1 covering every owner-only change, referenced from §3.3.
- C) Leave descriptive.

**Recommendation: A.** It closes a takeover path with two sentences in a form the spec already uses.

Plain language: Nothing currently stops a broad admin from changing who controls the Space. Option A tells clients to refuse such a change unless the owner signed it.

### D3. HR-sync conflict rules disagree (P2)

profiles/universal-idp-did.md §7. "Most restrictive wins" and a source trust hierarchy give different answers for HR REACTIVATE vs LDAP SUSPEND.

- A) Restrictiveness is the only rule; delete the trust hierarchy; manual calls skip deduplication.
- B) Trust hierarchy decides between sources; restrictiveness breaks ties within one source.
- C) Restrictiveness wins, except a higher-trust source can lift a SUSPEND (not a TERMINATE).

**Recommendation: A.** One fixed rule, and it fails safe for access control. Fix text: delete the "Trust hierarchy for conflicting events" heading and block; following paragraph: "For example, a Workday `TERMINATE` always overrides a concurrent LDAP `REACTIVATE`, which may reflect DC replication lag. Manual IT operations are exempt from deduplication: they are applied immediately and logged with a `manual-override` flag."

Plain language: Two rules for settling conflicting HR signals can point in opposite directions. Option A keeps only "the stricter action wins", so a mistake locks someone out rather than letting them back in.

### D4. "Protect the compliance mailbox accordingly" (P2)

profiles/purview-bridge.md:316. The items hold attachment keys, so whoever reads them can decrypt attachments, and the only mitigation names no actor or control.

- A) "The operator SHOULD limit read access to the `Agora Compliance Archive` folders and the catch-all mailbox to the compliance and eDiscovery roles authorized to read the captured content."
- B) Same text with MUST.
- C) Non-normative: "Access to these items is access to the attachment plaintext, and the operator's mailbox permissions need to reflect that."

**Recommendation: A.** It names the actor and a concrete control and matches the profile's other operator SHOULDs. MUST would bind tenant policy the bridge cannot test.

Plain language: Anyone who can read the compliance mailbox can open the archived attachments. Option A tells the operator to limit who can read it.

### D5. "no member ... MAY issue" a logger Remove (P3)

spec/07-compliance.md:269.

- A) "a member, including the regulated member, MUST NOT issue", matching the `agora-dm-removal` decision ("never removable").
- B) Lowercase "no member may issue"; rely on the regulated client's MUSTs at L271-274.

**Recommendation: A.** It matches the recorded decision and the existing conformance row.

Plain language: The sentence uses a word that grants permission where a prohibition is meant. Option A says plainly that no one may remove the compliance logger.

### D6. "Maximum 200 members" in interactive channels (P3)

spec/05-messaging.md:61 (also 03-spaces.md:21, 99-appendices.md:49). Appendix C calls 200 descriptive, but §5.2.1 reads as a hard cap, so one client may reject the 201st Add and another allow 4096.

- A) Descriptive: "Intended for up to about 200 members; the only enforced limit is the 4096-leaf cap below." Optionally 03 "(≤ 200)" to "(about 200)".
- B) Enforced: add a committer MUST NOT and member reject at 200 DIDs, and change Appendix C to MUST.

**Recommendation: A.** It matches Appendix C, and the 4096-leaf cap already exists with no stated reason for a second one.

Plain language: The spec says both that 200 is a limit and that it is only a guideline. Option A makes it a guideline everywhere, so 4096 devices stays the only hard limit.

### D7. §4.1 lowercase "recommended" (P3)

spec/04-access-control.md:15.

- (a) RECOMMENDED. (b) "In large public channels, restricting Commit authority to a smaller set reduces competing Commits." (c) Leave.

**Recommendation: (b).** "Large" is undefined, so a keyword would not be testable, and the strength stays the same.

Plain language: A lowercase "recommended" in a spec looks like a keyword someone forgot to capitalize. Option (b) rewords it as plain advice so nobody reads it as a requirement.

### D8. Guardian re-key modal (P3)

spec/02-identity.md:214, "SHOULD periodically verify ... and should re-key shares".

- A) Drop the second modal so one SHOULD covers both verbs. B) Separate non-normative sentence. C) Second explicit SHOULD.

**Recommendation: A.**

Plain language: The sentence mixes a formal "SHOULD" with an informal "should". Option A makes both actions the same formal recommendation, which is almost certainly what was meant.

### D9. Where an API peer block is stored (P3)

guides/relay-operator.md DELETE /admin/peers/{did} (~992). It says unblocking needs a restart, but `peering.blocked_peers` is reloadable.

- A) The API block appends the DID to `peering.blocked_peers` in relay.toml. Text: "to unblock, remove the peer from `peering.blocked_peers` and call `POST /admin/reload` (§5.2)."
- B) The block lives in the database, which needs a separate unblock path.

**Recommendation: A.** One sentence and no new mechanism.

Plain language: The guide says unblocking a peer needs a restart, but the setting can be reloaded live. Option A stores blocks in the config file, so unblocking is an edit plus a reload.

### D10. Numbered lists in the regulators guide (P3)

guides/regulators.md Part 3 and Part 4 are numbered but not sequences.

- A) Keep numbers; add to style sheet §4: "Exception: examination request lists and examiner checklists in guides/ stay numbered so items can be cited."
- B) Convert to bullets.

**Recommendation: A.** Examiners cite request items by number.

Plain language: The style rule says to use bullets for unordered lists. Keeping the numbers here lets an examiner write "request item 3".

### D11. BCP 14 keywords in profile Open Questions (P3)

profiles/o365-employer-did.md §10.1, §10.3, §10.5; same pattern in profiles/universal-idp-did.md and profiles/discord-onboarding.md Open Questions.

- A) Keep the keywords and move each into the section it governs. B) Lowercase them as deployment advice. C) Leave.

**Recommendation: B.** These are organization policy choices with no interop effect, so BCP 14 does not apply.

Plain language: Formal requirement words sit in a list of open questions and bind organizational choices. Option B turns them into ordinary advice.

### D12. "PKCS#11 or tpm2-pkcs11 are the required interfaces" (P3)

profiles/purview-bridge.md:549. The status is unclear, and tpm2-pkcs11 is a PKCS#11 provider, not an alternative.

- A) "On Linux, PKCS#11 is the usual interface (for a TPM, through `tpm2-pkcs11`; see spec §12 key storage table)."
- B) "On Linux, the bridge MUST access the key through a PKCS#11 interface (for a TPM, through `tpm2-pkcs11`)."

**Recommendation: A.** The existing MUST (HSM or TPM, never a file) already provides the security, and B would forbid valid paths such as tpm2-tss.

Plain language: The sentence reads as a requirement but has no formal keyword, and it lists one thing as two. Option A makes it an example and corrects the pairing.

### D13. "material compliance deficiency" vs "material compliance event" (P3)

guides/regulators.md:115 and :235 use different terms for the same event.

- A) "deficiency" in both places (L235: "is a material compliance deficiency."). B) "event" in both. C) Drop the label and point to the section.

**Recommendation: A.** L115 addresses examiners, and "deficiency" is their word for findings. "Event" could suggest a reporting duty no regulator has set.

Plain language: The guide uses two labels with different regulatory weight for one situation. Option A uses the examiner's word in both places.

## 3. Rejected or already fixed

- spec/14 §14.4.2 n = 0 `prev` stated twice: the two statements agree; the second adds the operation-stream case.
- spec/14 §14.4.4 run-in list with semicolons: valid Chicago run-in style, used in 14 other places; splitting would detach the MUST.
- spec/13 §13.1.1 verification scope split across paragraphs: complete and consistent together.
- spec/10 §10.1 lowercase "recommended": deployment advice; lowercase is correct under RFC 8174.
- spec/10 §10.3.4.6 Pkarr "names no IO" vs `_corundum._agora`: corundum.md:27 says the operator is a CO.
- spec/09 §9.3 "Members need to be able to determine this": non-normative by design under `agora-ux-musts`.
- spec/09 §9.3 passive "Every gateway is disclosed": summary sentence; the rules after it name each actor.
- spec/07 §7.4 base64url scope: agrees with §7.8.8.
- spec/06 §6.9 `e2eeMedia` "in the channel state": that is the corpus term for the channel's entry in Space state (§3.3).
- spec/05 passive-member eviction exemption stated twice: consistent and cross-referenced.
- spec/04 out-of-sync Welcome scope differs between §4.3 and §4.6: DM groups never have a sequencer, so the scopes are equal.
- spec/03 §3.4 fixed 12-byte nonce: only one ciphersuite is allowed (AES-128-GCM).
- spec/02 §2.5.6 step 6 passive: the actor is clear from the lead-in and step 5.
- spec/01 §1.2.2 lowercase "should": design goal; lowercase is plain English by the spec's own rule.
- ARCHITECTURE §9 SHOULD in Accepted costs: matches spec §4.6 and §12; moving it is style only.
- PRFAQ "decided in October 2026": absolute date, matches ARCHITECTURE §8.
- gsuite §6 "on every Workspace edition": the baseline is the same on all editions; only the optional CAA layer varies.
- purview §7.1 status-value punctuation: consistent within the list.
- radio-mesh lowercase should/must: intentionally non-normative (agora-pozi.33.3); capitalizing would add requirements.
- parlance `ttl_ms` "must": lowercase in a non-normative profile; not a keyword.
- parlance lowercase advisory words: same reason.
- parlance padding bullet vs Q5: permission and open question do not conflict.
- Appendix C 7-day row has no source: the source exists (§12.2); merged into D1.
- Appendix A/C interactive 200 row (99:49): merged into D6.
- spec/11 and spec/01 WebTransport duplicates: merged into fix 11.
- spec/07 retentionNotice "This space": example display text, outside `agora-ux-musts` scope.
- discord §10 UI strings with lowercase "space": sample UI copy.
- spec/10 manifest example omits `retiresAt`: optional field, example shows a relay with no planned end.
- Mixed Depends-on forms (S-rules, §, whole file): each form is unambiguous.
- gsuite "O365 profile §N" short form: file named once in Depends on; unambiguous.
- "Enrollment Service" capitalized vs "provisioning service": component name vs generic term; consistent.
- "Admin API" capitalization: consistent everywhere.
- PROPOSAL `spec/NN` citation form: consistent within the file.
- Missing Sources lines in o365, gsuite, universal-idp, purview, discord: Sources appears only in derived profiles; adding them would be new content.
- gateways §1 broadcast "instead": already fixed; current text matches spec §9.3.
