# DOC2: Non-normative documents versus the final spec

Lens: README.md, PROPOSAL.md, PRFAQ.md, ARCHITECTURE.md (claims only), guides/*.md, profiles/*.md, checked against spec/ at HEAD (9e7711f). The focus is on what b07bead, a5fdf42 and 9e7711f introduced or left behind. Items already decided or fixed (notes/review/reconciliation.md, bd memories) are not re-reported.

### DOC2-1: Relay guide's restore procedure brings back deregistered admission keys
- Severity: P1
- Location: guides/relay-operator.md:1614 (§8.5 step 7); also :1479, :1487 (§8.1 lists registration state as backed-up state). Conflicts with spec/10-relays.md:644 (§10.4.7 "Recovery from backup").
- Evidence: Guide: "A restored database holds the registrations of the backup time: keys the CO deregistered since then are admitted again ... ask it to re-send its current registrations and the deregistrations it made since then." Spec: "MUST NOT reinstate admission key registrations from the backup, because a key deregistered after the backup was taken would be admitted again. It starts with no registrations and answers `unknown-token` for every token".
- Problem: An operator who follows the guide breaks a spec MUST. It also reopens posting for members removed after the backup, for as long as the CO takes to respond. a5fdf42 added §10.4.7 to close exactly this window, but did not update the guide. The guide also leaves out the spec's recovery path: the relay sends a lost-registrations notice, the CO re-registers "without delay" (§10.5.3), and the 24-hour re-send is the fallback.
- Suggested fix: Rewrite step 7. After a restore, purge every admission key registration and every per-token `ts` record, and answer `unknown-token` until the CO re-registers. Notify each agreement's `contact` that registrations were lost (spec §10.4.7, §10.5.3). Keep restored envelopes and blobs within their retention, and serve them once their token is registered again. In §8.1, mark the registration tables as never restored.
- Needs decision: no

### DOC2-2: Relay guide says a relay cannot suspend a token; spec §10.4.7 now allows it, with a mandatory CO notice
- Severity: P2
- Location: guides/relay-operator.md:1060 (§5.2), :2373 (§17.2), the §17.2 action table (:2365-2371), and the `cause` labels of the withdrawn-token metric (:1195). Conflicts with spec/10-relays.md:642 and spec/11-transport.md §11.4 (`token-withdrawn` causes).
- Evidence: Guide: "There is no admin operation that suspends or blocks a token." / "The relay has no control that blocks a single token". Spec: "A Relay MAY stop admitting envelopes, pin instructions and blob uploads for one registered `channelToken` ... It MUST notify the CO at the `contact` ... naming the token, the time and the reason."
- Problem: The guide still describes the design that a5fdf42 replaced. An operator facing an abusive token or a legal demand is told the only tools are terminating the whole agreement or deleting CIDs. It never learns about the per-token tool, or that using it obliges the relay to notify the CO.
- Suggested fix: Document a suspend/lift admin operation. Its behaviour: it sends `token-withdrawn` to subscribers, it survives re-registration of the same token, and it requires a notice to `contact` giving token, time and reason. Add a "Suspend a token" row to the §17.2 table and a `suspended` cause label. Delete the two "no control" sentences.
- Needs decision: no

### DOC2-3: Relay guide's retirement procedure uses an invented `maintenance` field and drains before `retiresAt`
- Severity: P2
- Location: guides/relay-operator.md:2225-2238 (§16.2), :2242-2254 (§16.3). Conflicts with spec/10-relays.md:112 (`retiresAt`) and :646 (§10.4.7 "Retirement").
- Evidence: Guide: `"maintenance": { "status": "retiring", "retirementDate": ... }` / "`maintenance` is an operational extension, not a field defined in spec §10.2.1" / "Notify every loaded agreement's CO ... as the agreement's notice terms require." Spec: "MUST set `retiresAt` in its manifest ... and MUST notify the CO at the `contact` of each agreement it holds, both at least 30 days before that time ... Until `retiresAt` the Relay keeps admitting registered tokens."
- Problem: The guide never mentions `retiresAt`, which is the field COs and clients actually read. It puts the CO notice under contract terms instead of the spec's 30-day MUST. Its drain step stops accepting connections before shutdown, which contradicts "keeps admitting until `retiresAt`".
- Suggested fix: §16.2 should set `retiresAt` at least 30 days ahead, unless a CO agreed a different period out of band, and notify every `contact` at the same time, citing §10.4.7. Drop `maintenance`, or demote it to an optional hint. §16.3 should start the drain no earlier than `retiresAt`, or once every CO has deregistered its keys.
- Needs decision: no

### DOC2-4: Counsel and regulators guides promise attachment capture that the spec does not provide
- Severity: P2
- Location: guides/counsel.md:33; guides/regulators.md:65. Spec: spec/07-compliance.md §7.4 and §7.6 (:171); spec/05-messaging.md:317; spec/14-jmap.md:120-127.
- Evidence: Counsel: "**All file attachments and media**, stored by content hash (CID). The CID matches the original's, so authenticity is verifiable." Regulators: "**File attachments and media.** Stored by content hash (CID) ... If the content hash of a file produced in a proceeding matches the hash in the original conversation, the file has not been altered." Spec: "its `blobId` is the CID of the ciphertext ... `size` and `sha256` describe the plaintext file" (05:317). §7 lists "file attachments" in scope (07:171), but no text requires the logger to fetch, decrypt or retain an attachment blob.
- Problem: Since a5fdf42, an attachment is a content-key blob held only at the uploading relays, for the agreement's retention window. The logger archives the `Message`, which carries `contentKey` and `sha256`, but the spec never makes it fetch and keep the blob. After relay retention expires, the archive holds a pointer to nothing. The "CID matches the original's" claim also describes the retired design: the CID now hashes ciphertext, and plaintext integrity comes from `Attachment.sha256` inside the signed Message. Telling examiners that attachments are archived is a claim the spec does not back.
- Suggested fix: Spec §7.4 should require the logger, on archiving a Message with attachments, to fetch each blob (§10.4.4), check `sha256` after decryption, and store it in the archive (re-sealed under the archive key), recording any fetch failure as a gap. Then update both guides: the archive holds the decrypted file, and its integrity is shown by the `sha256` in the archived Message. Until the spec says this, change both guides to "attachments are captured only if the logger fetches them before relay retention expires".
- Needs decision: yes. Options: (a) the logger MUST fetch and archive attachment blobs (recommended; it matches the guides and examiner expectations); (b) state in §7 and both guides that attachments are captured by reference only, and record this as a capture gap.

### DOC2-5: DM and self-group keys registered by an individually chosen identity host are grouped per host; the docs' anonymity claims cover only Spaces
- Severity: P2
- Location: ARCHITECTURE.md §5 item 6 (:166-170), §6.1 (:205-207), §9 "Space anonymity at the IO is only as large as the CO" (:392-397); PROPOSAL.md:44-48 (file lines); PRFAQ.md:31, :39. Spec: spec/10-relays.md:777 (§10.5.3, added in a5fdf42); spec/12-security.md:53.
- Evidence: Spec §10.5.3: "An identity host that an individual chose holds its own `ServiceAgreement`s under its own billing DID and registers under those, acting as the CO for this purpose." Spec §12.4: "it cannot distinguish them from other traffic by type ... a Relay learns whose agreement covers a DM token." ARCHITECTURE §9 discusses only "Space anonymity" and "A CO with one Space gets none."
- Problem: Under an agreement held by an individual's identity host, every registered token is a DM group or a self-group (§2.6) initiated by that host's users. A relay therefore can tell DM traffic from Space traffic for that agreement, contradicting §12.4 "cannot distinguish them ... by type". For a host with one user (a self-hosted individual), every DM that person starts, plus their self-group, sits under one billing DID. The accepted-costs list and the PRFAQ/PROPOSAL privacy claims say nothing about this, although it is the DM analogue of "a CO with one Space gets none".
- Suggested fix: Add an accepted cost to ARCHITECTURE §9: "An identity host's agreement covers only the DM groups and self-groups its users initiate; the anonymity set is that host's users, and a single-user host gets none." Qualify spec §12.4 to match. Add one sentence to PRFAQ "What does the relay operator see?", and recommend that individuals use shared identity hosts.
- Needs decision: yes. Options: (a) document it as an accepted cost (recommended; it is consistent with the Q6 rationale); (b) let individual identity hosts register under a pooled agreement shared by several hosts; (c) have DM keys registered under the agreement of a Space the initiator belongs to, which leaks Space affiliation instead.

### DOC2-6: Guides cite §7.8.2 for the message-request capture rule
- Severity: P3
- Location: guides/counsel.md:43; guides/regulators.md:205.
- Evidence: Counsel: "the client still processes the Welcome, admits the logger and captures as in any other DM group (spec §7.8.2)". Regulators: "admits the logger and captures while the request is pending (spec §7.8.2)". The rule is at spec/04-access-control.md §4.6.3 "Regulated members" and spec/07-compliance.md §7.8.7 "Message requests" (:285). §7.8.2 is the generic Add procedure and does not mention message requests.
- Problem: Counsel and examiners following the citation will not find the rule they are relying on. Both guides otherwise state the a5fdf42 rule correctly.
- Suggested fix: Cite "spec §4.6.3, §7.8.7" in both places.
- Needs decision: no

### DOC2-7: HTTP proof-of-work text calls the sequencer a CO endpoint
- Severity: P3
- Location: spec/10-relays.md:760 (§10.5.2 "HTTP endpoints", added in a5fdf42), versus ARCHITECTURE.md §2.3 table (:61) and §5 item 3 (:158-160).
- Evidence: Spec: "A CO HTTP endpoint that requires proof of work before serving a request, such as a `KeyPackageEndpoint` host (§4.6.3), an invite endpoint ... or a sequencer (§14.4)". ARCHITECTURE: "| Sequencer | IO | ... Bound like a relay". ARCHITECTURE §5 item 3 lists only connection-level PoW (§11.6) among the proofs an IO observes.
- Problem: The sequencer is an IO under ARCHITECTURE, which governs. The new HTTP PoW sentence classes it as CO, and the closed observation budget does not list HTTP PoW challenges at an IO. The budget gap is harmless in substance (a challenge carries no identity), but it is a new contradiction with the governing document.
- Suggested fix: Reword §10.5.2 to "An HTTP endpoint, whether a CO endpoint (a `KeyPackageEndpoint` host, an invite endpoint) or an IO endpoint (a sequencer)". Extend ARCHITECTURE §5 item 3 to "connection-level and HTTP proof of work (§11.6, §10.5.2)".
- Needs decision: no

### DOC2-8: PROPOSAL still calls the guides "pending revision"
- Severity: P3
- Location: PROPOSAL.md:71.
- Evidence: "| `guides/` | Relay operator, regulator and counsel guides (pending revision) |"
- Problem: The guides were revised in c87ed3e and b07bead. Counsel and regulators now track the final spec. The relay guide's remaining gaps are DOC2-1 to DOC2-3.
- Suggested fix: Drop "(pending revision)" once DOC2-1 to DOC2-3 are fixed.
- Needs decision: no

### DOC2-9: CORUNDUM profile says the combined-operator cost is not yet in ARCHITECTURE
- Severity: P3
- Location: profiles/corundum.md:38, versus ARCHITECTURE.md:405-408.
- Evidence: Profile: "C5 records this as an accepted cost for ARCHITECTURE §9. That text is not in ARCHITECTURE.md yet." ARCHITECTURE §9: "**A party that runs both a social or identity service and relays can link its own users to the COs whose traffic they use.**"
- Problem: Stale. 61b7d43 added the text to ARCHITECTURE §9 but did not update the profile.
- Suggested fix: Replace the sentence with "ARCHITECTURE §9 lists it as an accepted cost."
- Needs decision: no

### DOC2-10: Chain-witness profile records pruning as a `ComplianceRecord`
- Severity: P3
- Location: profiles/compliance-chain-witness.md:89-91, versus spec/07-compliance.md §7.4 (:96-133).
- Evidence: "Write a `ComplianceRecord` to each affected chain describing the pruned range (first and last `prevRecordCID` removed), the retention rule applied, and the `prune` head's CID."
- Problem: Since b07bead, a `ComplianceRecord` is a per-message record that must carry `senderDID`, `plaintextPayload`, `senderMessage`, `messageKeys`, `groupContext` and `senderLeaf`, and it must pass the §7.4 third-party check. A prune statement has none of these. An examiner who runs that check on every record (as this profile's own step 6.4 and regulators Step 4 suggest) will see the prune statements fail. This misuses a normative type.
- Suggested fix: Define a practice type `urn:agora:practice:CompliancePruneRecord` (body: pruned range, rule, `pruneHeadCID`), signed by the logger DID and chained by `prevRecordCID`. Say that verifiers skip the §7.4 sender check for it.
- Needs decision: no

### DOC2-11: Relay guide key-loss text treats the relay DID as derived from the key
- Severity: P3
- Location: guides/relay-operator.md:1478, :1491, :1509; contradicts the guide's own default `relay_did = "did:web:..."` (:286-289) and :1789.
- Evidence: "If lost, the relay DID is permanently lost ... The DID is derived from the public key and cannot be reconstructed without it."
- Problem: This holds only for a `did:key` relay. For the default `did:web` relay, a lost key means publishing a new key in `did.json` and the manifest, and the DID and its ServiceAgreements survive. An operator would needlessly re-sign every agreement.
- Suggested fix: Limit both statements to `did:key` relays, and give the `did:web` recovery steps.
- Needs decision: no

### DOC2-12: Relay guide's Tor mapping cannot serve the advertised `ws://` onion endpoint
- Severity: P3
- Location: guides/relay-operator.md:1909, :1917.
- Evidence: "HiddenServicePort 80 127.0.0.1:443" together with "`endpoints.onion` as `ws://examplerelay3xyz.onion/v1/agora/ws`".
- Problem: Plaintext WebSocket traffic on onion port 80 is forwarded to the TLS listener, so the handshake fails. The onion endpoint that spec §10.1/§11.3 advertise would not work.
- Suggested fix: Forward to a plaintext WebSocket listener (for example 127.0.0.1:8080, with a matching config key), or advertise `wss://` on onion port 443.
- Needs decision: no

### DOC2-13: Universal-IdP profile omits the sidecar's role as admission-key host for DM groups and self-groups
- Severity: P2
- Location: profiles/universal-idp-did.md:22, :686-697 (the reverse-proxy path list). Compare profiles/o365-employer-did.md:602-606 and :677-679 (§6.7). Spec: spec/04-access-control.md §4.6; spec/10-relays.md:777 (§10.5.3).
- Evidence: l.22 lists only the KeyPackage duties ("hosts each user's KeyPackages ... accepts Welcomes by POST"). The public proxy list exposes `/v1/devices`, `/v1/revocations`, `/v1/notify`, `/v1/hr-event`, `/users/*/did.jsonl` and `/v1/agora/kp/*`. The words "admission" and "ServiceAgreement" appear nowhere in the file (grep count 0).
- Problem: §4.6 and §10.5.3 (a5fdf42) make the employer provisioning service the identity host. It issues admission keys for the DM groups and self-groups (§2.6) its users start, registers them under the employer CO's billing DID, rotates them and serves them. If an operator follows this profile's topology, `/admission-key/*` and the §3.5 auth endpoint are unreachable from outside. Users then cannot start DMs, and multi-device self-groups get no relay admission.
- Suggested fix: Add a section deferring to O365 §6.7 (key generation, registration under the employer billing DID, rotation on `DMMembers`, §3.5 authentication). Add the admission-key and auth paths to the reverse-proxy list.
- Needs decision: no

### DOC2-14: Discord onboarding omits the identity host's admission-key and ServiceAgreement duties, and understates what the host learns
- Severity: P2
- Location: profiles/discord-onboarding.md:42-48, :83-85, :527.
- Evidence: The identity-host box lists only "did:webvh log (if used)" and "KeyPackageEndpoint: KeyPackages, Welcomes". The security section says only: "The host the user picks observes KeyPackage fetches and Welcome deliveries for that user (spec §4.6)." Spec §10.5.3: "An identity host that an individual chose holds its own `ServiceAgreement`s under its own billing DID and registers under those".
- Problem: A user who picks a host that only serves the DID log and KeyPackages cannot start DMs and cannot use a second device (no self-group admission). The privacy note also leaves out that the host learns the member DIDs of every DM the user starts (spec §4.6, §12.11). See also DOC2-5 on what relays learn from such a host's agreement.
- Suggested fix: Add both duties (the admission-key endpoints; the host's own ServiceAgreements and billing DID) to the host requirements. Extend the "Identity host" privacy item to include DM member DIDs.
- Needs decision: no

### DOC2-15: Employer profiles give employees no update key, but spec §2.4 requires recovery keys to be update keys for every did:webvh
- Severity: P2
- Location: profiles/o365-employer-did.md:149, :194, :227-246 (gsuite and universal inherit this); spec/02-identity.md:128 versus :171 and §2.5.8 (:480-490).
- Evidence: Profile: `"updateKeys": ["z6MkSIDECAR_UPDATE_KEY..."]` and "Employees hold no update key in this profile", while the document lists a recovery key under `recoverableIdentity`. Spec §2.4: "`did:webvh`: all of §2.4 applies. The recovery key (§2.4.1) and the social recovery key (§2.4.2) MUST also be authorized update keys of the DID log". Spec §2.5.8 says the recovery key cannot override an organization-initiated revocation.
- Problem: The profile follows the evident intent of §2.5.8, but it contradicts the literal MUST of §2.4, which has no carve-out for CO-provisioned DIDs. Read literally, §2.4 hands employees an update key. They could then write log entries that undo a suspension, which breaks §2.5.8.
- Suggested fix: Change the spec, not the profile. Scope the §2.4 MUST to individually held `did:webvh` DIDs. For CO-provisioned DIDs, state that recovery keys are `recoverableIdentity` only and that the provisioning service writes the recovery entry (§2.4.1, §2.5.8).
- Needs decision: yes. Options: (a) scope §2.4 as above (recommended); (b) profiles add employee recovery keys to `updateKeys`, and the "cannot override" rule in §2.5.8 is dropped.

### DOC2-16: Purview bridge never receives audit-chain entries, so gap alerts are incomplete and re-sealed media fails verification
- Severity: P2
- Location: profiles/purview-bridge.md:403-406 (§5.2 step 3), :548-559 (§8.3 record stream), :586-598 (§9.2 alerts); spec/07-compliance.md:312-325 (`ComplianceGapEntry`), :374-386 (`ArchiveResealEntry`).
- Evidence: §5.2: "confirm that each unsealed object's sealed form matches its `mediaCID`". The §8.3 stream carries only `ComplianceRecord`s, yet §9.2 alerts on `removalAttempts`, which appear only in `DMComplianceAuditEntry`. `ComplianceGapEntry` and `ArchiveResealEntry` (both added in b07bead) are never mentioned.
- Problem: The bridge never gives the compliance officer the logger's text-capture gap records. After an archive-key compromise, an investigator following §5.2 would reject authentic re-sealed media, because the re-sealed object's CID no longer matches the signed `mediaCID`.
- Suggested fix: Add the audit-chain entry types (`DMComplianceAuditEntry`, `ComplianceGapEntry`, `ArchiveResealEntry`, `VTCComplianceAuditEntry`) to the §8.3 stream, and alert on gap entries. In §5.2, follow `ArchiveResealEntry` from `oldCID` to `newCID`.
- Needs decision: no

### DOC2-17: Purview bridge describes the retired group-encrypted attachment blob
- Severity: P3
- Location: profiles/purview-bridge.md:300; spec/05-messaging.md:317; spec/14-jmap.md:120-127.
- Evidence: "An attachment's `blobId` is the CID of a group-encrypted blob (spec §5.2.2, spec §3.4). Only a group member can decrypt it". Spec: "An attachment's file is stored as a content-key blob (§14.3.4). The `Attachment` carries the random per-attachment key in its `contentKey` member".
- Problem: This is the retired scheme. "Only a group member can decrypt it" is now false: anyone holding the plaintext Message can decrypt the relay-held ciphertext, including any holder of the Exchange copy of the `ComplianceRecord`. That copy is therefore plaintext-equivalent for attachments too. (The same line assumes the logger fetches attachment blobs, a duty the spec does not state; see DOC2-4.)
- Suggested fix: Describe decryption with the `contentKey` from the captured Message. Note that Exchange items carry `contentKey` and `sha256` and must be protected as plaintext.
- Needs decision: no

### DOC2-18: gsuite profile still relies on a custom `AgoraDIDAdmin` OAuth scope
- Severity: P3
- Location: profiles/gsuite-employer-did.md:299 (also :410), versus :446.
- Evidence: l.299: "The admin token is a Google OAuth token with the `AgoraDIDAdmin` scope (§7)". l.446: "No custom OAuth scope: Google issues only Google-defined scopes." §7 defines no such scope.
- Problem: The fix for DOC-6 left this behind. It describes an admin authorization mechanism that Google cannot provide.
- Suggested fix: Authorize admin calls by mapping the token's `sub` to an admin list or Google group in the sidecar, and reword l.299 and l.410 to match.
- Needs decision: no

### DOC2-19: Employer profiles leave out the `AgoraProvisioning` service entry that spec §2.5.3 requires
- Severity: P3
- Location: profiles/o365-employer-did.md:247-258; profiles/universal-idp-did.md:22, :40; spec/02-identity.md §2.5.3.
- Evidence: The O365 active-document `service` array lists only `#keypackages` and `#profile`. Universal: "Create the stub log: no keys, one `KeyPackageEndpoint` service entry (spec §2.5.3)." Spec: "It also adds an `AgoraProvisioning` service entry whose `serviceEndpoint` is its base URL, written `{prov}` below."
- Problem: Clients find `{prov}` through this entry for self-service device revocation (§2.5.5). Profiles that omit it produce documents in which that flow fails.
- Suggested fix: Add the `AgoraProvisioning` entry to the O365 example and to universal l.22 and l.40.
- Needs decision: no

### DOC2-20: O365 profile registers DM admission keys only with relays
- Severity: P3
- Location: profiles/o365-employer-did.md:679; spec/10-relays.md §10.5.1 table and §10.5.3 (:777).
- Evidence: "registers it by `AdmissionKeyRegistration` with every relay the organization holds a `ServiceAgreement` with". Spec: "with every IO that holds a `ServiceAgreement` with it whose `serviceType` receives registrations", which includes `sfu` and `sequencer`.
- Problem: A DM voice call through the employer's SFU would fail admission (§6.6 admits by registered keys).
- Suggested fix: Say "every IO (relay, SFU, sequencer) whose agreement receives registrations (spec §10.5.3)".
- Needs decision: no

### DOC2-21: Five profiles use BCP 14 key words as rules and carry no non-normative banner
- Severity: P3
- Location: profiles/o365-employer-did.md:1, :190, :508; gsuite-employer-did.md:1, :280; universal-idp-did.md:1; discord-onboarding.md:1, :490; purview-bridge.md:1-12.
- Evidence: o365 is titled "# Specification: Employer-Managed DIDs via Microsoft Entra ID". Examples: "For involuntary terminations, it MUST be 0" (o365:508); "`portable: true` MUST be set" (o365:190, where spec §2.5.2 says SHOULD); "React MUST NOT be used" (discord:490); "IT MUST call `POST /v1/tombstone` directly" (gsuite:280). The four other profiles (corundum, parlance, radio-mesh, compliance-chain-witness) open with "Non-normative".
- Problem: README marks profiles/ non-normative, but these read as specifications, and some of them tighten spec SHOULDs into MUSTs. The relay guide was already cleaned of this under DOC-9.
- Suggested fix: See options.
- Needs decision: yes. Options: (a) add the standard banner ("Non-normative; where it conflicts with the spec or ARCHITECTURE.md, those govern") and state that key words bind only implementations claiming conformance to the profile (recommended; least churn); (b) lowercase the key words, as was done in the relay guide.

## Checked and clean

- PRFAQ: the dateline is "SEATTLE, WA, [launch date]", and the closing "What is a PRFAQ?" footer is present and verbatim. Its open-question text accurately gives why the countersign design was replaced (matches notes/review/CRY-verified.md). Its witness, push, broadcast, MIMI-caveat and DID-method claims match spec §2.1, §11.7, §5.2.1.4 and §9.1.
- README profile list is now complete. PROPOSAL's channel-admission description matches spec §5.2.2 and §10.5.3.
- ARCHITECTURE citations checked (§10.4.1, §5.2.2, §10.5.1-§10.5.3, §11.4, §11.6, §11.7, §13.1.1, §3.5, §5.1.1, §14.4) all resolve and say what is claimed.
- Counsel and regulators guides correctly cover verifiable compliance records (§7.4 third-party check), logger self-update, logger key rotation (§7.9), witnesses for a CO-provisioned logger DID, the stable localIdentifier, guardian, recording consent split, ServiceAgreement `contact` routing for takedowns, and the message-request capture rule (apart from the citation, DOC2-6).
- The relay operator guide contains no retired designs (exporter keys, countersigning, DID login, transparency log, prices, push urgency, user gossip, channelCID, relay-held KeyPackages) and no BCP 14 key words. It covers the AdmissionKeyRegistration endpoint, ServiceAgreement supersession, the per-token floor and push serving. HTTP PoW (§10.5.2) applies to CO endpoints and sequencers, not relays, so the relay guide does not need it.
- Parlance and radio-mesh profiles: the padding, admission-key token rotation, broadcast and envelope-size updates match spec §5.2.1, §5.2.1.4 and §5.2.2.

Coverage: read in full README.md, PROPOSAL.md, PRFAQ.md, ARCHITECTURE.md, guides/counsel.md, guides/regulators.md, guides/relay-operator.md, and all nine profiles (compliance-chain-witness, corundum, parlance, radio-mesh-gateway, o365-employer-did, gsuite-employer-did, universal-idp-did, discord-onboarding, purview-bridge). Spec read for verification: spec/07-compliance.md and spec/10-relays.md §10.4-§10.5 in full; spec/04-access-control.md §4.6-§4.8; spec/05-messaging.md §5.1, §5.2.1.2-§5.2.2; spec/06-calls.md §6.5 and §6.12; spec/02-identity.md §2.1 and §2.5.1-§2.5.4; spec/13-encoding.md §13.1.1 and common encodings; spec/09-interop.md §9.1; spec/11-transport.md and spec/10-relays.md in full (relay-guide pass). Relay-guide and employer-profile passes were run as parallel sub-reviews; each finding taken from them was spot-checked against the cited text.
