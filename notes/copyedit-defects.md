# Possible spec defects reported during the 2026-10-17 copyedit

Reported by per-file copyeditors; not yet verified or triaged.

## spec/99-appendices.md

- Appendix A, Primary transport row: WebTransport is cited as 'RFC 9000', which is QUIC. WebTransport itself is defined by W3C WebTransport and IETF drafts (draft-ietf-webtrans-http3). The citation may be intentional, but it looks wrong.
- Appendix A, TURN relay row: it cites RFC 5766, which RFC 8656 replaced. That may matter if the spec body cites RFC 8656.
- Appendix C, row 'Members of an `interactive` channel group': it lists both §3.2 and §5.2.1 as the defining sections. I did not check whether the two sections agree on 200.

## spec/14-jmap.md

- §14.4.2: the n = 0 `prev` rule appears twice, in the commit-stream paragraph and again at the end of the stamp description ('(above)'). I kept both: the second is the only statement that operation streams start with `prev` null.
- §14.4.5 Replacement: 'A Commit that was stamped but never published ... therefore lies above the head' is presented as a consequence of the MUST-choose-heads rule. But that rule only requires heads to cover available Commits. It does not force an unavailable Commit above the head unless the head is also the highest available position. Possibly underspecified.
- §14.4.4 step list ends items with semicolons as lowercase fragments of one 'MUST, for each:' sentence. I left it as is to avoid detaching the MUST, but it departs from the style sheet's bullet punctuation rule.

## spec/13-encoding.md

- §13.1.1 Threshold signers and the paragraph after the Verification list both say to reject two entries whose `kid` names the same DID. The repetition is harmless, but it was likely patched in twice. I left both because the threshold paragraph also carries the candidate-set rule.
- §13.1.1 Verification: the lead sentence applies checks 1 to 5 only to entries for required signers. The next paragraph then rejects any failing entry, including one from a signer who is not required. The two are consistent, but the scope is split across two paragraphs. Merging them would be a structural change, so I did not make it.

## spec/12-security.md

- §12.11 'DM admission host': '...the host does not learn the other members' DIDs, except those of its own users whose clients also request keys for the group, or when they are active.' I left 'or when they are active' alone. It is ambiguous: it is not clear who 'they' are, or what the host learns when they are active.
- §12.4 Channel token correlation: 'A channel whose membership changes often SHOULD therefore have its key rotated promptly' puts the SHOULD on the channel, not on a named actor (the CO). I kept the subject to avoid changing who the normative statement applies to.
- §12.9: 'a party ... MUST NOT treat an object as not yet valid unless ..., and checks expiry against its own clock with no added tolerance'. The expiry clause is written as a lowercase statement of fact inside a normative sentence, so it is unclear whether it is meant as a requirement. I left it unchanged.
- §12.2: 'Space operators SHOULD enforce periodic key rotation' uses 'Space operators', which is not a defined term in the style sheet (CO or Space owner/admin would be). I did not change it because changing it would change the subject of the SHOULD.

## spec/11-transport.md

- §11.1: 'WebTransport (IETF RFC 9000 / HTTP/3 over QUIC)'. RFC 9000 is QUIC, not WebTransport; HTTP/3 is RFC 9114, and WebTransport over HTTP/3 is an IETF draft. The citation looks wrong. I left it alone.
- §11.4 Withdrawn tokens: 'If that key is the refused one at every listed relay, the client applies the recovery of §4.6 instead of retrying. If its token is the one refused, the client uses another relay in the key's relay list (§10.3.5).' The logical order seems reversed: fail over first, recover only when every relay refuses. The scope is also unclear: does the §4.6 recovery apply only to DM groups and self-groups, or to all channels? And what does 'its token' refer to? I did not reorder because reordering could change the scope.
- §11.8.5: 'Methods marked **read-only** have no `/set`', but the table marks no method read-only. The table entry for `Envelope/get` says 'Returns encrypted blobs' where it means envelopes. I left both because they are table values.
- Intro: 'JMAP is used only for history and blobs', while §11.8.9 says the management API is also JMAP (JMAP Chat). The sentence means the relay sync API. Consider 'The relay sync API carries only history and blobs.'
- §11.7.4: the numbered list says 'the relay: 1. Looks up… 2. Sends… 3. The proxy maps…'. Step 3 changes actor in the middle of the procedure. I left it alone.
- §11.5: 'Direct peer connections are mandatory for voice and video' uses a lowercase 'mandatory' next to a BCP 14 MUST NOT. I did not decide whether it should be REQUIRED.

## spec/10-relays.md

- 10.2 transport paragraph says relays 'MUST also support HTTP/1.1 or HTTP/2 over TLS as a fallback', but 10.2.2 says relays 'MUST continue to accept HTTP/1.1 and HTTP/2 over TLS on the same `peerAPI` URL'. 'or' and 'and' differ in what a conforming relay must implement. The two sections also repeat the HTTP/3 SHOULD and the Alt-Svc SHOULD.
- 10.1 Private overlay: 'This is the recommended topology for private organizational deployments' uses lowercase 'recommended'. It could be read as a SHOULD or as a plain description. Left as is.
- 10.2.6 says a peer stays in `knownPeers` for 7 days after it becomes unreachable, but `knownPeers` in 10.2.1 is described as the relay's 'current peer list'. These may be in tension.
- 10.3.3 item 4 calls DNS-SD lookups 'mDNS for LAN or overlay discovery', but 10.2.5 Method 3 describes unicast DNS SRV/TXT records under `<domain>`. 10.4.4 also forbids clients announcing on a local network by mDNS. Whether clients may do mDNS lookups (as opposed to announcements) is unclear.
- 10.3.4.6 says the Pkarr record names no relay or other IO, while the optional `_corundum._agora` record carries an operator content endpoint URL. Whether that operator counts as an IO is not stated.
- 10.4.3 SHOULD 'Announce itself on `v1/agora/discovery` with a signed `RelayAd` including all available endpoint URIs', but 10.5.1 requires a RelayAd to leave out the relay-to-relay and CO-facing endpoints (`peerAPI`, `gossipQuic`, `admissionKeys`). 'All available endpoint URIs' conflicts with that.

## spec/09-interop.md

- §9.3 Channel state disclosure: the original sentence 'members must be able to determine this without reading protocol documentation' used a lowercase 'must'. I rephrased it as a non-normative statement of purpose. If the authors intended a real requirement, it would need a BCP 14 keyword and a named actor, which I did not add.
- §9.3 intro: 'Every gateway is disclosed to all channel members before messages flow through it' is passive and has no named actor. The rules that do the disclosing are Send-gate and Broadcast channels. I left it alone because naming an actor would mean choosing between the admin and the gateway.
- §9.1 says a gateway 'reads from and publishes to the channel's relays as a member does, signing routing envelopes with the channel admission key it obtains as a member'. It does not say how this works for a broadcast-channel gateway, which is not an MLS member. The text is ambiguous here and I left it unchanged.

## spec/08-cross-space.md

- §8.4: 'Clients SHOULD display the member's display name from their own Space's profile'. 'their' can mean the guest member or the viewing client. I left it as is because choosing a reading would change the meaning.
- §8.7 step 1: 'When the guest admin revokes, the home CO does this as soon as it receives the revocation'. It is unclear whether 'this' means the key rotation only or also the MLS Remove Commits, since step 1 says the revoking admin issues the Removes. I left it unchanged.
- §8.7 step 1 has the 'revoking admin' remove 'all members of the foreign Space'. When the home admin revokes, it removes guest members. When the guest admin revokes, 'foreign Space' from the guest's point of view would literally be the home Space. The intent is presumably to remove guest members in both cases.
- §8.8: the MUST is to present the retentionNotice before the user first sends, while the descriptive text says the client displays it on first entry. These timings are compatible but not identical. I kept both, without making the second normative.

## spec/07-compliance.md

- §7.8.8 says 'The regulated member's Space MUST record each DM group compliance logger admission' and also says the entry is signed by `loggerDID`, 'the writer of the compliance audit chain'. The conformance table gives 'Publish DMComplianceAuditEntry' to the compliance logger. The MUST's subject (the Space) is not an actor and does not match the table.
- §7.2 defines `loggerLabel`, `enabledBy` and `enabledAt` nowhere except in the JSON example.
- §7.8.6 says a participant 'who has no Space affiliation (or a Space without compliance logging)'. The parenthetical is grammatically ambiguous and probably means 'or whose Space has no compliance logging'. I left it because rewording it could change who is covered.
- §7.4 says the same base64url encoding applies to 'the other records of §7 (§7.8.4, §7.8.8, §7.8.9)' and names only `mlsGroupID` and `channelID`. `DMComplianceAuditEntry.treeHash` is also byte-valued and is stated separately in §7.8.8, so the two statements overlap but do not conflict.
- §7.8.3's first sentence uses 'no member ... MAY issue'. This is a prohibition written with MAY rather than MUST NOT, and its BCP 14 strength is ambiguous. I left it unchanged per the invariants.
- §7.8.9 places the `ComplianceGapEntry` JSON block and its explanatory paragraph inside a bullet list, which breaks the list in most Markdown renderers. I did not restructure it because moving the code block would change section layout beyond a copyedit.

## spec/06-calls.md

- §6.12.6: 'Non-empty arrays are compliance gaps that must be reported to the compliance officer.' This is a lowercase 'must' in normative text with no named actor (recorder? CO?). Making it BCP 14 would add a requirement, so I left it.
- §6.6: 'no client may add it to one' is a lowercase 'may' that works as a prohibition (effectively MUST NOT). I left it as written.
- §6.12.1: 'Because only an admin or owner may issue it' conflicts in wording with the exception in the next sentence: under vtcCompliance any member may issue a grant to the recorderDID. I left it alone.
- §6.6 SFU Signaling Protocol: the 'Participants map SFU-forwarded streams to DIDs...' paragraph sits after 'Leaving and errors' with no lead-in. It does not define how participants exchange that mapping (message type or field).
- §6.9: the last paragraph says e2eeMedia is declared in 'the channel state'. Other text puts channel attributes in Space state. The location of `e2eeMedia` may need confirming against spec/03 and spec/04.

## spec/05-messaging.md

- §5.1.1 No-sequencer out-of-sync flag: the text says the member 'keeps its state, and the flag, until it accepts a Welcome', and also that 'It clears the flag when it processes a Commit for a later epoch issued by another member.' Together these read as two conflicting end conditions for the flag. Probably either event ends it, but the wording says 'until' a Welcome only. I left it unchanged.
- §5.2.2 Member duties: 'In a DM group or a self-group it fetches nothing and instead uses the key in `agora_admission` (§4.6); when a relay reports a token withdrawn, it first fetches that token's history...' It is unclear whether the token-withdrawn clause applies only to DM groups and self-groups or to all channels. I kept the original semicolon so I would not resolve it either way.
- Passive members exempt from idle eviction: the rule is stated normatively twice, in §5.2.1.2 'Compliance logging' (loggers) and in §5.2.1.3 'Idle eviction' (all passive members, which includes VTC recorders). The two agree, but they are duplicated across subsections. I left both because each is normative in its own subsection.
- §5.2.1 says 'interactive mode... Maximum 200 members', but the group configuration allows up to 4096 leaves, and multiple devices per user each take a leaf. It is unclear whether 200 counts members or leaves. I did not change it.

## spec/04-access-control.md

- §4.1 MLS group committer: 'Restricting Commit authority to a smaller set is recommended for large public channels' uses lowercase 'recommended' in a normative file. It is unclear whether RECOMMENDED was intended. Left at its original strength.
- §4.7 Takedowns: 'may drop the CID' uses lowercase 'may' while restating §10.4.5. Left as is.
- The out-of-sync Welcome exception differs between sections: §4.3 limits it to 'a group with no sequencer (§5.1.1)', but the §4.6 DM version says only 'a group (§5.1.1)'. This may be intentional because DM groups have no sequencer, but the two should be checked for consistency.
- §4.6 Rotation: the request-state skip sentence names 'this duty' right after the removal-triggered duty. Whether it also covers the 7-day periodic duty comes only from the general §4.6 statement that a client in the request state 'neither rotates the key nor moves the group'. Left unchanged.

## spec/03-spaces.md

- §3.2 says 'Every channel has a **mode**', but the field index makes `mode` required only on a `text` channel, and the voice and category entries in the example have no mode.
- §3.4 says `nonce` is 12 bytes, 'the AES-128-GCM nonce length', but the AEAD for a group-encrypted blob is 'that of the group's ciphersuite'. A ciphersuite with a different nonce length (for example ChaCha20-Poly1305, which also uses 12, or a future AEAD) makes the fixed length worth checking.
- The `guardian` and `admins` rules say 'Only the owner may change...' with a lowercase 'may'. That reads as a normative restriction that is not in BCP 14 form. I left it alone because making it a keyword would change normative strength.
- The `members` paragraph in §3.3 says the non-member view is defined in §3.4, but the access-controlled view is actually specified in §4.4, which §3.4 points to. The ref resolves, but it is indirect.

## spec/02-identity.md

- §2.5.2 service duty list says the provisioning service 'Serves documents at the well-known URL path', but the resolution path given is `https://{orgDomain}/users/{localIdentifier}/did.jsonl`, which is not under `.well-known`. Either the bullet or the path is stale.
- §2.4.2 Guardian obligations: 'The account owner SHOULD periodically verify ... and should re-key shares when a guardian becomes unreachable'. The lowercase 'should' sits next to a BCP 14 SHOULD. Making it SHOULD would add a requirement and rewording it as fact would drop one, so I left it for an author decision.
- Pkarr record names are inconsistent: the §2.1 table lists `_profile._agora.` (trailing dot), while §2.3 prose writes `_profile._agora` (no dot). I left both because they are record identifiers.
- §2.1 reference implementations line says '`did-key` generation and resolution'. This probably means `did:key` (the method), but `did-key` is also a crate name in the list, so I left it.
- §2.5.8 Org-initiated recovery: 'This path MUST be logged in the audit trail' is passive with no named actor (presumably the provisioning service). I kept the passive because naming an actor would change the requirement's subject.
- §2.5.6 step 6 'the document MAY be blanked ... but MUST NOT be removed' is also actorless passive (presumably the organization). Kept for the same reason.

## spec/01-overview.md

- §1.2.1 lists 'WebTransport (RFC 9000)', but RFC 9000 is QUIC. WebTransport is defined in IETF drafts, or RFC 9220 for HTTP/3 extended CONNECT. Left unchanged.
- §1.2.2 Relay blindness says 'A relay operator served a subpoena should be able to say truthfully...'. This is a lowercase 'should' in a design-goal sentence. It is not normative, but the intent is ambiguous, so I left it alone.
- §1.1 says the Relay-to-relay Peer API version is declared in the manifest `capabilities` array, but no section is cited. A cross-reference to the manifest section may be missing.

## ARCHITECTURE.md

- §6.2 Mechanism bullet 1 says the CO registration service generates a key pair 'for each channel and each DM group'. The DM bullet and the §2.3 KeyPackage host row say the DM admission host (the user's identity host) issues DM and self-group keys. Bullet 1 omits self-groups and implies the CO registration service issues DM keys. Possible contradiction. Not changed.
- §6.2 Commit conflicts: 'Clients discard the losing Commit and re-propose' follows the no-sequencer rule and may or may not also apply to the sequencer path. I kept its original position after the no-sequencer sentence.
- §9 'A DM admission host SHOULD list relays it does not operate' is a normative SHOULD inside the Accepted costs list. It may belong in §3 or spec §4.6. Not moved.

## PROPOSAL.md

- 'What it does not guarantee: ... capture from a tampered client.' The word 'capture' is ambiguous here. It probably means compliance capture, but it could be read as key or data capture. I left it unchanged because rewording would change meaning.

## PRFAQ.md

- Line 31 describes the relay-observation list as 'closed and normative' and says 'any extension to it must be opt-in, declared and visible to members'. That restates a spec rule in non-normative text. I left it unchanged, since it is description, not a new rule.
- Line 99 says 'The other protocol questions were decided in October 2026', which is the current month. That will go stale and may need a fixed date or rewording at release.

## guides/relay-operator.md

- §5.1 says to rotate the admin token 'via POST /admin/reload after updating the environment variable'. But §10.3 step 3 says to restart the relay because 'the admin token cannot be reloaded live', and the reloadable-fields list in §5.2 POST /admin/reload does not include the token. These contradict each other.
- §5.1 says the admin token is 'base64url-encoded', but the command it gives, `openssl rand -base64 32`, produces standard base64, not base64url.
- §5.2 DELETE /admin/peers/{did} says to unblock by restarting the relay with the peer removed from `peering.blocked_peers`. §5.2 POST /admin/reload lists `peering.blocked_peers` as reloadable, so a restart should not be needed. It is also unclear whether the API block is ever written to the config.
- §16.5 step 2, 'Update the relay manifest to remove the relay from `knownPeers` entries gossiped by this relay', is unclear. A relay would not list itself in its own knownPeers.
- The §15.1 diagram labels relay-1 'primary' and relay-2 'replica', but §15.2 recommends active-active, where both instances serve traffic.
- §11.3, under 'Blob store (S3 backend only)', says 'the local blob store serves via the relay process'. That mentions the local backend under the S3 heading.

## guides/regulators.md

- Part 3 'What to Request' and Part 4 'What an Examiner Should Check' are numbered lists that are not sequences. Style sheet §4 says to use bullets. I left them numbered because examination document requests are usually cited by item number.
- Part 6 17a-4 'What Agora provides' says owning the archive 'supports the control requirement', but the requirement summary never names a control requirement.
- Part 6 GDPR 'delete records promptly (not later)': the parenthetical is redundant and unclear. I left it to avoid changing the wording of the obligation.
- Some bullet lists mix fragment bullets and full-sentence bullets, against style sheet §4: the push proxy bullet in 'What a Relay Operator Can Produce', the first bullet under 'Archive Completeness', and the removal-attempt bullet under 'DM Compliance'. I left them because rewriting them means restructuring content.

## guides/counsel.md

- Part 1 says the compliance logger 'receives and archives' voice and video. The same bullet says a separate compliance recorder (spec §6.12) captures it. This guide does not say whether the recorder and the logger are the same principal.
- The Part 6 table row for MiFID II says '5-year retention' and also lists a '7-year retention configuration available'. The table never explains where the 7-year figure comes from. I left the table values unchanged.
- In the Part 6 table, the HIPAA 'Gap' cell holds several sentences but has no final period. Table content was off-limits, so I left it.

## profiles/o365-employer-did.md

- §1 says 'Relays play no part in this profile.' But §6.7 and the end of §6.1 have the sidecar register admission keys with relays by AdmissionKeyRegistration under a relay ServiceAgreement. The statement is too broad. It probably means relays play no part in IdP authentication or DID provisioning. I left it, because rewording it changes a factual claim.
- §1 says 'These/The two components are independent' and introduces a table, but the table also assigns concerns to the Enrollment Service and to the DID log, which are not among the two components.
- §3.1's third paragraph is about the stub document and about clients trying to Add a stub DID. It reads as belonging in §3.2. I did not move it because that would cross sections.
- §5.5: 'Other device keys (the user's phone, recovery key) are unaffected' calls the recovery key a device key. §3.3 lists it under recoverableIdentity, not authentication.
- §5.3 and §5.4 say 'Space role update commit' and 'MLS Remove commits'. Under the MLS capitalization rule these may need to be 'Commit' where they mean the MLS message. I left them, because it is unclear whether the Space role update is an MLS Commit at all.
- §10.1 'this SHOULD be pushed via Intune MDM policy' and §10.3 and §10.5 MUST statements sit in Open Questions. Open Questions are an odd place for profile requirements, but I did not change them because the invariant forbids touching BCP 14 strength.

## profiles/universal-idp-did.md

- §5.5: 'The sidecar applies manual calls with `SourceEvent = "manual"`'. In the §5.3 HREvent struct, "manual" is a value of `Source`, while `SourceEvent` is the native event name. The field is probably meant to be `Source`. I left it unchanged.
- §7: deduplication says the more restrictive action wins (TERMINATE > SUSPEND > UPDATE > REACTIVATE > PROVISION). A separate trust hierarchy ranks sources (HR > LDAP > SCIM > webhook IdP > manual). The text does not say which rule applies when they disagree, for example HR REACTIVATE against LDAP SUSPEND within 60 s.
- §3.1 says all four Cat 1 providers use the `POST /v1/notify` webhook receiver. §3.5 says OneLogin SHOULD use Events API polling as its primary source.
- §7 table: OneLogin TERMINATE is the `user.deleted` webhook, but the §3.5 Events API list has no delete event_type_id. If a deployment uses only Events API polling, nothing detects deletions.
- §4.2 and §4.4 both state the externalId→id fallback as MUST requirements, in slightly different words ('store as stableID' vs 'key its user records on'). The duplicate is harmless, but it was likely introduced by patching.

## profiles/purview-bridge.md

- §11 item 3 ('SHOULD be confirmed with ... counsel') and item 4 ('The compliance officer MUST review and resolve mapping gaps promptly') put BCP 14 requirements in an Open Issues list. Item 4 also binds a human role with an unmeasurable 'promptly'. I left both as they are.
- §2.1 'Certificate rotation SHOULD be automated' and §2.3 'MUST be held only in...' are passive and name no actor (operator or bridge). I did not assign one, because that could change who the requirement binds.
- §8.2 says '`PKCS#11` or `tpm2-pkcs11` are the required interfaces on Linux'. This is a requirement written in lowercase prose with no BCP 14 keyword, so it is unclear whether it is normative.
- §7.1: in the status-values list, the `skipped` entry is a sentence fragment that ends with a period, mixed with similar fragments. I left it, because the glossary-style colon block is consistent within itself.
- §3.5: 'Protect the compliance mailbox accordingly' is an imperative with no actor and no stated control. It may be meant as a SHOULD on the operator.

## profiles/gsuite-employer-did.md

- §5.3 contradicts itself. Option A says 'The enrollment invitation includes a second link for VC acceptance', but the last paragraph says 'The Option A acceptance link is therefore sent after first-device enrollment, not in the initial invitation.' I left both, because reconciling them changes what the profile describes.
- §4.2 is inconsistent about how the sidecar sends the invitation. Step 5 says 'via Google Workspace SMTP relay or Gmail API', and the next paragraph says the email 'is sent using the Gmail API with domain-wide delegation'.
- §6 says the two-part step-up applies 'on every Workspace edition', but the opening sentence says that enforcement varies by edition. I reworded the opening to 'what Google can enforce varies by Workspace edition' to reduce the clash, but the author should confirm the intent.
- §2.1 asks for the `admin.directory.user` scope, which grants read and write access, only to watch for push notifications, while also asking for the read-only scope. This may grant more access than the sidecar needs. I did not touch it.

## profiles/discord-onboarding.md

- §6.4 says the CLI retrieves the PKCS#11 public key "for DID derivation", but §5.1 and §3.1 say a did:webvh or did:plc DID is not derived from the device key (only a did:key DID is). The wording is probably stale. I left it.
- §12 Service worker restrictions: "`Cache-Control: no-store`, which is separate from the Content Security Policy" looks like a leftover from a patch. CSP is not mentioned anywhere else, so it is unclear what the clause is distinguishing. I left it.
- §6.6: "MUST output the private key only as a recovery phrase ... (or generate it on a PKCS#11 token, which keeps it non-extractable)" puts an alternative key-generation path inside the parenthetical of an output MUST. I kept it as written because splitting it could change the MUST's scope.
- §2: the Enrollment Service is described as "stateless beyond the provisional member list", yet §5.4 requires it to track single-use challenges and mark them consumed. That is state beyond the member list. I left it.
- §3.1 did:key: "The client re-publishes the record every 2 hours" switches the actor from "the tool" to "the client" without saying which client keeps doing this after enrollment. I left it.

## profiles/radio-mesh-gateway.md

- The profile has '### 5.2 Batching and padding' with no §5.1. I kept the heading number as the invariants require
- Lowercase 'should' and 'must' appear throughout ('Bridged channels must not claim MLS-grade security', 'must keep their frames separate', 'the gateway should refuse to bridge...'). I left them lowercase because capitalizing them would add profile rules
- §2 says 'Radio command traffic is never bridged'. It is unclear whether 'never' is a filter rule the operator can override or an absolute rule. I did not change it
- PLI, TOFU, OSCORE, EDHOC and CoT are not expanded on first use. They are radio-domain terms not on the style sheet's expansion list, and I did not guess at their expansions

## profiles/corundum.md

- §9 questions 3 and 4 give their decision label as a bare 'C' ('Resolved (2026-10-17, C)'). It looks truncated (perhaps C4a or C1a), unlike the 'C2a' and 'C2b' labels of questions 1 and 2. I left it unchanged.
- §8 opens with 'None of these changes have been made in CORUNDUM', but one item is checked: [x] Define the `did:key` pointer `_corundum._agora` (spec §10.3.4.6). The checked change was made on the Agora side, so the two statements are not strictly in conflict, but readers may find it confusing. I left it unchanged.
- §2 'Disclosed cost' cites spec §4.6 and §10.5.3, and §3/§5 cite spec §10.2.5 and §10.4.4. None of these are on the Depends on line. I did not add them, because that would change the metadata's scope.

## profiles/compliance-chain-witness.md

- §2's field bullets explain `indexCID`, `recordCount`, `reason` and `prevHeadCID`, but not `loggerDID` or `ts`.
- §6 step 4 says an `ArchiveResealEntry` maps old CIDs to new ones, but does not say what the examiner does with that mapping during verification.

## profiles/gateways.md

- §4.3 Disclosure: 'so members should be told' uses a lowercase 'should' with no named actor. I left it alone because making it SHOULD would add a rule to a non-normative profile. The author should decide who tells members and whether it is a recommendation.
- §1 broadcast case: the original parenthetical could be read as saying a broadcast gateway is also an MLS member. I added 'instead' to match spec §9.1 ('joins no MLS group'). Please confirm that is the intended reading.

## profiles/parlance.md

- §4: '`ttl_ms` must allow for relay latency' uses a lowercase 'must' in a profile that gives capitalized keywords a defined meaning. Left as is, because capitalizing it would add a requirement.
- §3: 'Its `e2eeNote` should say...' and §6: 'should batch', 'should not name sensitive zones' and 'may pad' are lowercase advisory words. Left as is for the same reason.
- §2: 'The SPEC-Substrate §11.3 state event, unchanged, plus two keys' never names the two added keys. They are presumably `topic` and `catalogue`, but that cannot be confirmed without the Parlance sources.
- §6 timing bullet and §8 Q5 both raise padding beyond 256-byte buckets. This is intentional overlap (a statement and its open question), so it was kept.

## Corpus-wide (cross-file pass, left as substantive)

- spec/99-appendices.md Appendix C row 'MLS epoch lifetime | 7 days maximum | Recommended | §12.2' has no source. Nothing in §12.2 or elsewhere in spec/ states a 7-day epoch lifetime limit. Either the requirement was dropped from §12.2 or the row is stale. Needs an author decision; not changed.
- Serial comma: the style sheet contradicts itself (§4 says 'use it', its recommendation says 'omit it'), and files mix both forms. Every editor left commas alone. This needs one corpus-wide decision before anyone sweeps.
- Bead IDs in reader-facing text: spec/05 '> **Open (agora-pozi.8):**', spec/13 '> **Open (agora-pozi.31.69):**', README's last line ('epic agora-pozi'), and the profiles/gateways, parlance and radio-mesh **Sources:** lines. Keeping or removing them is a corpus-wide call.
- guides/regulators.md calls an unexplained chain break a 'material compliance deficiency' (line 115) and a 'material compliance event' (line 235). The two terms carry different regulatory weight, so merging them is not purely wording; Mark should pick one.
- spec/07-compliance.md line 164: the `retentionNotice` JSON example says 'This space is subject…' with lowercase 'space'. It is inside a frozen code block, and guides/counsel.md line 195 quotes it verbatim. Change both together if wanted.
- profiles/discord-onboarding.md §10 error table: the quoted UI strings use lowercase 'space' ('this space', 'space admin', 'space link'). They are table values, frozen by the invariants.
- spec/10-relays.md §10.2.1 describes `retiresAt`, but the manifest JSON example omits it. The code block is frozen.
- spec/05-messaging.md §5.2.1.1: the fenced JSON block and the paragraph after it are not indented under the list item, so the list breaks. Fixing it means re-indenting a code block.
- spec/05-messaging.md: retired §5.2.6, §5.2.7 and §5.2.8.2 subsections keep their old headings, which have 'Retired.' bodies. Retitling them needs a check of every place that cites them.
- spec/04-access-control.md: 'accepted a Subscribe' is defined in §4.6 Rotation but used earlier in the agora_admission paragraph. It could instead be defined once at §11.4.
- Profiles without a **Sources:** field: o365-employer-did, universal-idp-did, purview-bridge, gsuite-employer-did, discord-onboarding and compliance-chain-witness (which also lacks **Status:** and **Depends on:**). Supplying these is new content.
- profiles/gateways.md **Depends on:** writes 'ARCHITECTURE S1, S3, S8' (correct rule form), but parlance and radio-mesh write 'ARCHITECTURE.md;' to mean the whole file. That is defensible, but inconsistent across profiles.
- profiles/gsuite-employer-did.md cites the O365 profile about 20 times as 'O365 profile §N' rather than as a `profiles/o365-employer-did.md` path. Left as is.
- profiles/o365-employer-did.md line 645 table cell 'a §3.5 bearer token' means spec §3.5, but the 'spec' prefix is missing. Left because it is a table cell.
- 'Enrollment Service' is capitalized throughout discord-onboarding, o365, gsuite and universal-idp, while the analogous 'provisioning service' is lowercase. The style sheet has no entry for it.
- 'Admin API' / 'Relay Admin API' stay capitalized in guides/relay-operator.md as an interface name, the same way 'Peer API' is capitalized. Change it everywhere at once if wanted.
- Abbreviations not expanded on first use, because the expansion would read badly or the term is a product name: MIMI in PROPOSAL line 116 (in a bold lead-in) and profiles/gateways line 15; 'Google Cloud KMS' in gsuite (product name); E2EE, SFU, MIMI and IdP that first appear in table label cells (ARCHITECTURE §2.3, spec/03 §3.2, spec/99 Appendix A); SCIM, MFA and UPN in spec/02; CIO and O365 in README.
- Mixed number formatting ('65536 bytes' and '262,144 bytes') in spec/14 and Appendix C. Numbers are frozen.
- PROPOSAL.md cites the spec as '`spec/05` §5.2.2'; the style sheet defines no form for PROPOSAL. README's `attic/` row says 'first ship' and the line under the table says 'first release'. Both left as is.

