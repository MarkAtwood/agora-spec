# Review 4: IMP4 (implementability)

Scope: spec at 4b76c3d, read as independent implementers of a client, a Relay, a CO Space endpoint, a DM admission host (KeyPackage host class) and a sequencer. Focus on §4.6, §7.8, §2.6, §5.2.1.5, §5.1.1, §9 and §1.4. Binding decisions checked against `bd memories agora` and spec §12.5 accepted limits; the accepted limit "Removed host's user withdraws the DM key" (spec/12-security.md:71) is not re-reported. The sequencer path (§5.1.1, §14.4, `closingHeads`) read as complete; I found nothing there that independent implementers would build differently.

### IMP4-1: A DM host cannot replace a Relay; a relay list frozen in the GroupContext partitions DM groups and self-groups when their Relays go away
- Severity: P1
- Location: spec/04-access-control.md:177, spec/04-access-control.md:194, spec/04-access-control.md:196, spec/10-relays.md:555, spec/10-relays.md:688, ARCHITECTURE.md:110
- Evidence:
  - §4.6: "The key's `relays` list is the DM group's relay list; members publish and subscribe there." and "`key_epoch`, `seed` and `relays` are the `keyEpoch`, `seed` and `relays` of a `ChannelAdmissionKey` that `host` issued".
  - §10.3.5: "To remove a Relay, the CO removes it from `relays`, then deregisters the keys. Because members' MLS state, Space state and admission keys do not change, a CO adds, removes or replaces a Relay without touching Space identity or membership (ARCHITECTURE S5)."
  - §10.4.7: "A CO removes the Relay from its relay lists (§10.3.5) and deregisters its keys there before `retiresAt`."
  - S5: "A CO MUST be able to add, remove or replace any IO without changing ... MLS group state".
  - §4.6 recovery: "A member that finds the key in the current GroupContext not admitted by the group's relays, because no Relay in its `relays` that it can reach accepts a Subscribe to its channel token, each answering `unknown-token` (§11.4), rotates the key if it is a host's user and otherwise moves the group (§4.6.4). It publishes that Commit under the last admitted key it holds".
- Problem: For a DM group or self-group the relay list is part of MLS state and changes only when a host's user commits a new key. The host, which holds the agreements, has no way to change it and no way to ask its user to rotate. Nothing requires periodic rotation. So when a host retires or replaces its Relays (provider switch, `retiresAt`, agreement end):
  - Every DM group and self-group whose `relays` lists only departing Relays stops working. The §4.6 recovery does not fire reliably: retired Relays are unreachable, not answering `unknown-token`, and "no Relay ... that it can reach" with zero reachable Relays is read either way.
  - If one member does rotate or move, it publishes the Commit at the new Relays (the host registered the old key there under §10.5.3 "every current key with an IO that it engages"). The other members are still listening at the old, gone Relays and never receive it. Non-host's-user members each move the group to their own host, at different Relays. The group partitions with no rule that rejoins it.
  This also contradicts S5 for DM groups: replacing an IO requires a change of MLS group state.
- Fix: Give the host a path to change Relays without a member-side race. Options below.
- Needs decision: yes. (a) The relay list leaves the extension: `agora_admission` keeps `host`, `key_epoch`, `seed`, and members read the host's current relay list from a host-published document (for example `GET <host>/v1/agora/relays`, or the host's own manifest), which the host may change at will, as a CO changes `ChannelAdmissionKey.relays`. (b) Keep relays in the extension and require each host's user's client to rotate at a fixed interval (for example every 7 days) and whenever its host's POST response lists different relays from the group's current key, with the host keeping old Relays registered until all its keys of the old list have been replaced or deregistered. (c) Accept and record in §12.5 and ARCHITECTURE §9 that DM groups do not survive Relay replacement. Recommend (a): it restores S5 with one fetch, and the relay list was never secret from the host. In plain terms: today a DM group's Relays are written into the encrypted group itself, so the host cannot move them. Option (a) lets the host change Relays the way a community operator does.

### IMP4-2: Routine withdrawal of a DM group's current key has no trigger to move first, and the DM path loops on `token-withdrawn`
- Severity: P2
- Location: spec/04-access-control.md:175, spec/04-access-control.md:196, spec/04-access-control.md:200, spec/04-access-control.md:243, spec/04-access-control.md:247, spec/02-identity.md:454, spec/11-transport.md:196
- Evidence:
  - §4.6: "The host also deregisters every key it issued to a DID 30 days after that DID is offboarded (§2.5.6)."
  - §4.6.4: "When no host's user remains a member, because the last one left (§4.8), was removed (§4.6) or was offboarded (§2.5.6), the client of the remaining member with the lowest leaf index ... moves the group by default." and "Remaining members complete any handover within that period."
  - §2.5.6 step 4: "members of groups outside the organization's control Remove them when they next resolve the DID". No section sets when a member resolves a DID other than on an `IdentityChanged` notice (§2.7), which an offboarded user, having no device keys, cannot send.
  - §4.6 recovery fires only on "each answering `unknown-token`".
  - §11.4: "It answers a later `Subscribe`, `Publish` or `PinInstruction` naming that token with `token-withdrawn` for as long as it still holds envelopes under the token, and with `unknown-token` after that." and "In a DM group or a self-group, the client instead fetches that token's history (§11.8), processes the Commits in it, and uses the key in `agora_admission` (§4.6)."
- Problem: An employer offboards a user whose key is current in a DM group with outside members. Nobody re-resolves the DID, so nobody learns that no host's user remains, and no one moves the group. On day 30 the host deregisters the key. Relays answer `token-withdrawn` (for up to `retentionDays`), not `unknown-token`, so the §4.6 recovery does not fire; the §11.4 DM path fetches history, finds no new Commit, keeps the same key and is refused again, with no exit. Even if a member noticed, §12.5 says a Commit under a withdrawn key cannot be published, so the group is lost. The same loop follows a Relay token suspension (§10.4.7) or the end of the host's agreement at every listed Relay. The DELETE gate has the mirror ambiguity: "accepted a Subscribe ..., that is, has not answered it with `unknown-token`" counts a `token-withdrawn` answer as acceptance.
- Fix: (1) Require each DM member's client to re-resolve every other member's DID (or Pkarr record) at least once every 24 hours while it holds the group, and on failure of the credential binding to Remove the leaves (§2.2), so offboarding is seen well inside 30 days. (2) In the §4.6 recovery and §11.4 DM path, treat `token-withdrawn` like `unknown-token` for the current key. (3) Define "accepted a Subscribe" as answered with `Ack` and no per-token `Error`.
- Needs decision: no

### IMP4-3: §10.5.3 registration-service rules contradict the §4.6 DM host rules
- Severity: P2
- Location: spec/10-relays.md:850, spec/10-relays.md:873, spec/10-relays.md:880, spec/10-relays.md:882, spec/04-access-control.md:175
- Evidence:
  - §10.5.3 names the DM host as a registration service ("for a DM group or a self-group (§2.6), by the group's admission host") and then: "After a rotation, the registration service deregisters the previous key once members have had time to move to the new token, after a grace period RECOMMENDED to be 300 seconds." and "The registration service also deregisters every key of a channel or DM group that is deleted".
  - "`replaces` is present when the key is a rotation (§5.2.2) ... the registration service MUST set it in the first registration of each rotated key with each IO, and MUST omit it for a new channel's or DM group's first key."
  - "It SHOULD batch registrations for new channels and DM groups and add random delay".
  - §4.6: "Until a later key is confirmed, the host keeps an earlier key registered until its issuee DELETEs it or the host deregisters it under §2.5.6." and "For each POST that issues a key, the host generates a new key ..., registers it, records the requesting DID as the key's issuee, and returns it".
- Problem: A host implementer reading §10.5.3 deregisters key k 300 s after issuing k+1. If the Commit carrying k+1 lost (concurrent rotations are expected, §4.6), the group's current key is gone and the group is stranded. The host cannot know which key a POST replaces (it does not know which earlier key won), cannot tell a creation POST from a move POST (both look identical), and cannot know a DM group was "deleted", so the `replaces` MUST and the deletion rule are uncheckable for it. The batching SHOULD either delays the synchronous POST response or, if applied after the response, lets a creator publish under an unregistered key and trip the §4.6 "not admitted" recovery on a brand-new group.
- Fix: In §10.5.3 state that for DM groups and self-groups §4.6 alone governs deregistration; the host omits `replaces` (Relays then send no `token-rotated`, which DM clients ignore anyway, §11.4); no deletion rule applies; and the host completes registration with every listed IO before it returns the key, with any batching delay inside the POST.
- Needs decision: no

### IMP4-4: The "host's user" policy-violation check depends on live DID and Pkarr resolution with no freshness or comparison rule, so members split
- Severity: P2
- Location: spec/04-access-control.md:167, spec/04-access-control.md:196
- Evidence: "The **host's user** is a member whose identity host, the origin of its `KeyPackageEndpoint` (§5.2.1.1), equals `host` in the group's `agora_admission` extension. A member learns each other member's `KeyPackageEndpoint` from its DID document ... or for `did:key` by fetching its Pkarr pointer record (§2.1)." and "Members MUST treat as a policy violation (§4.5) a Commit that changes `agora_admission`, keeps `host`, and either keeps `key_epoch` or has a committer that is not a host's user."
- Problem: A policy violation makes every conformant member delete its group state (§4.5), so this check must give the same answer at every member. It does not:
  - Members hold DID documents of different ages. A user who moves to a new identity host just after a legitimate rotation is a host's user to members with a cached document and not to members that re-resolved, so some leave and some stay.
  - A Pkarr lookup can fail (DHT records expire unless republished). Nothing says what a member does when it cannot resolve the committer.
  - "equals" is not defined for origins (case, default port, IDN, trailing slash), and `host` is "UTF-8" while `KeyPackageEndpoint` is a URL.
  §5.1.1 already handles the same problem for Space state ("first fetches the current head ... and re-checks"); §4.6 has no counterpart.
- Fix: Define the comparison as byte equality of the RFC 6454 ASCII serialization of both origins. Before treating such a Commit as a violation, a member re-resolves the committer's DID or Pkarr record fresh; if resolution fails, it does not treat the Commit as a violation. State that the check uses the committer's DID document current at processing time after that re-resolution.
- Needs decision: no

### IMP4-5: The Client conformance row omits the member-side duties of §7.8 that every client must perform
- Severity: P2
- Location: spec/01-overview.md:79, spec/01-overview.md:81, spec/07-compliance.md:240, spec/07-compliance.md:285, spec/07-compliance.md:289, spec/07-compliance.md:363
- Evidence:
  - Client row: "§7.2, §7.5, §7.7 (adding the logger, expiry under logging, member disclosure)". §7.8 appears only in the Regulated-member row: "every row of the §7.8 Conformance Summary that applies to the regulated member's client or the committing client".
  - §7.8.2, binding every member: "Every other GroupContextExtensions proposal ... carries `agora_compliance` unchanged. Members MUST treat as a policy violation (§4.5) a Commit that adds an entry without adding a leaf of that DID, or that removes or changes an entry otherwise than this paragraph allows."
  - §7.8.4: "A receiving client MUST present it to its user." and "A client that joins a DM group whose GroupContext has an `agora_compliance` extension (§7.8.2) MUST, before the user sends any message in the group, present to its user a notice for each listed DID".
  - The §7.8 Conformance Summary has no row for a non-regulated receiving client.
- Problem: An implementer of a plain Client follows §1.4 and skips §7.8. Its client does not enforce the `agora_compliance` policy-violation rule, so on a Commit that drops a logger entry improperly, conformant members leave and it stays, splitting the group; and it never shows the DM disclosure notices that the consent model rests on (agora-q2 decision: disclosure plus participation is consent).
- Fix: Add to the Client row "§7.8.2 (`agora_compliance` handling and checks), §7.8.4 (presenting disclosure notices)", and add the corresponding "Any member's client" rows to the §7.8 Conformance Summary.
- Needs decision: no

### IMP4-6: Gateways have no conformance class, and the recorder class lacks the duties DM recording needs
- Severity: P2
- Location: spec/01-overview.md:79, spec/01-overview.md:89, spec/01-overview.md:95, spec/09-interop.md:12, spec/09-interop.md:33, spec/09-interop.md:68, spec/06-calls.md:465, spec/07-compliance.md:254
- Evidence:
  - §1.4: "A component that is not listed has no conformance definition in this version." No Gateway row exists.
  - §9.1: "it MUST run under the control of the CO operating the channel and MUST NOT run in or as part of a relay"; "A gateway MUST NOT keep decrypted message content beyond the time needed"; §9.3: "A gateway MUST NOT carry messages in either direction until its `GatewayDescriptor` is in the channel's current Space state and it has received that `SystemEvent`."
  - Client row cites "§9.3 (gateway indicators)", while §9.3 also binds the adding Admin's client: "MUST publish the Space state update that adds its `GatewayDescriptor` before committing the MLS Add ... and MUST send the `gateway-added` `SystemEvent`".
  - Compliance recorder row: "§6.12.1 to §6.12.6, §12.8". The logger row adds "the KeyPackage host class for its own DID", the recorder row does not, yet §6.12.7 adds the recorder to DM groups by the §7.8.2 procedure, whose endpoint "MUST return a fresh, unused `KeyPackage` on each fetch, never a last-resort KeyPackage".
- Problem: The §9 MUSTs bind no class, so a gateway product can claim nothing and be held to nothing; the Admin-side send-gate is hidden behind the "indicators" label, so client implementers skip it and gateways wait forever for a `SystemEvent` that is never sent. A recorder built to its row has no KeyPackage endpoint obligations and may serve last-resort KeyPackages to many DM groups, which §5.2.1.3 says must never happen.
- Fix: Add a "Gateway | CO | §9.1, §9.2, §9.3, §5.2.1, §5.2.2, §12.8" row; relabel the Client citation "§9.3 (gateway send-gate for adding Admins, indicators)"; add "§5.2.1.3, §6.12.7, the KeyPackage host class for its own DID, §7.8.2 (KeyPackage availability)" to the recorder row.
- Needs decision: no

### IMP4-7: "Send in the epoch the Add creates" is unsatisfiable when the epoch moves first; strict clients then block the regulated user and gateways forever
- Severity: P2
- Location: spec/07-compliance.md:207, spec/07-compliance.md:271, spec/07-compliance.md:285, spec/07-compliance.md:311, spec/09-interop.md:68, spec/04-access-control.md:289
- Evidence:
  - §7.8.4: "The notice MUST be sent as an application message in the epoch where the logger is admitted, before any other application message the client sends in that epoch" and "sent in the same epoch as the logger's admission commit".
  - §7.8.1: "The client MUST NOT permit the regulated member to send any application message in a DM group until the compliance logger has been admitted to the MLS group and the client has sent the `ComplianceDisclosureNotice`".
  - §9.3: the Admin "MUST send the `gateway-added` `SystemEvent` in the epoch that Add creates".
  - §4.8: "A member ... that receives a self-Remove proposal MUST commit it before sending any further application message in that group".
  - §7.8.7: "until the logger admission commit has been completed and acknowledged".
- Problem: Another member's Commit (a self-update, an Add, a removal, or a self-Remove the sender must commit first under §4.8) can open epoch N+1 before the regulated client or Admin sends. The MUST then cannot be met. A strict implementation never sends the notice, so under §7.8.1 its user can never post in that group; a lax one sends it in N+1. A strict gateway waits for a `SystemEvent` that the Admin's client now cannot send. "Acknowledged" has no meaning in a DM group, which has no sequencer and no acknowledgement; implementers will read it as "Relay `Ack`" or "won under §5.1.1".
- Fix: Replace each epoch clause with "as its first application message in the group after the Commit that admits the logger (or gateway) has won (§5.1.1), in whatever epoch is then current"; state that members who missed it are covered by the later-joiner rule of §7.8.4 and the `gateways` array of §9.3. Replace "completed and acknowledged" with "has won (§5.1.1)".
- Needs decision: no

### IMP4-8: Removal-attempt reporting has no mechanism, and `removalAttempts` cannot be filled
- Severity: P2
- Location: spec/07-compliance.md:263, spec/07-compliance.md:332, spec/07-compliance.md:334, spec/07-compliance.md:369
- Evidence: "immediately re-add the logger via the §7.8.2 procedure ... and notify the regulated member's Space admin of the removal attempt ... The Space admin MUST be notified"; Summary: "Notify Space admin of logger removal attempt | Regulated member's client | MUST". `DMComplianceAuditEntry` "is signed per §13.1.1 by `loggerDID`"; "`removalAttempts` is an array of timestamps and initiator DIDs for any Remove commits targeting the logger that the regulated member's client detected and remedied per §7.8.3."
- Problem: No message type, endpoint or channel carries the notification, so two clients will notify in incompatible ways (an `AbuseReport`, an email, a private type), and a compliance pipeline cannot consume them. The admission entry is written and signed by the logger when it is admitted, before any removal; it is a hash-chained record that cannot be amended, and the logger never learns what the client detected (it learns its own removal and records it as a `ComplianceGapEntry`). So `removalAttempts` is always empty or requires an undefined update.
- Fix: Define the notification as an MLS application message of a new type (for example `urn:agora:type:ComplianceRemovalNotice` with `mlsGroupID`, `removedBy`, `removedAtEpoch`, `readmittedAtEpoch`) sent in a DM group with the Space's `loggerDID` (the logger already receives every message there and writes the chain), or drop the MUST to the existing `ComplianceGapEntry`. Remove `removalAttempts` from `DMComplianceAuditEntry`, or move the initiator DID into `ComplianceGapEntry` as `removedBy`, which the logger can read from the removing Commit's sender.
- Needs decision: yes. (a) new notice type to the logger, logger records `removedBy` in the gap entry; (b) drop the admin-notification MUST and rely on `ComplianceGapEntry` with `removedBy`. Recommend (b): the logger already sees the removal and its sender, so one signed record covers it with no new client duty. In plain terms: today the spec tells the client to "notify the admin" but gives no way to do it. Option (b) lets the archive record the removal and who did it, which is what the admin needs.

### IMP4-9: No rule for DM groups that exist when a member becomes regulated
- Severity: P2
- Location: spec/07-compliance.md:197, spec/07-compliance.md:203, spec/07-compliance.md:340
- Evidence: §7.8.1: "Add the Space's `loggerDID` to the MLS group of every DM group the regulated member creates or joins, prior to sending or receiving any application messages in that group." §7.8.9: "The regulated member's client MUST NOT send any application message into a DM group whose current MLS membership lacks the Space's `loggerDID` (§7.8.1)."
- Problem: When an owner adds a DID to `regulatedMembers`, the user is already in DM groups it neither "creates" nor "joins". One client adds the logger and sends the disclosure in each; another only blocks sending there (per §7.8.9) and leaves the group unlogged; a third does nothing until a new group. Capture and disclosure then depend on the vendor. The reverse case (removed from `regulatedMembers`, or `enabled` set to false) is also silent, while §7.8.3 still forbids removing the logger "for the duration of the regulatory retention period", which no client can compute.
- Fix: Add: "When a client learns from Space state that its user has become a regulated member, it performs §7.8.2 and §7.8.4 in every DM group the user belongs to before the user next sends there." For the reverse, state that loggers already admitted stay and the client stops adding new ones.
- Needs decision: no

### IMP4-10: Rotation and handover duties are assigned by other members' local request state
- Severity: P3
- Location: spec/04-access-control.md:167, spec/04-access-control.md:200, spec/04-access-control.md:243
- Evidence: "the client of the host's user with the lowest leaf index among those not holding the group in the message request state (§4.6.3) MUST POST for a new key"; "A client that holds the group in the message request state (§4.6.3) neither rotates the key nor moves the group."; handover: "the client of the remaining member with the lowest leaf index, other than a DID listed in `agora_compliance` (§7.8.2), moves the group by default."
- Problem: Request state is local and invisible to other members, so no client can compute "lowest among those not in request state". Each client assumes the lower-leaf member acts; if that member holds a request, nobody rotates (or moves) until the 24-hour fallback, extending a removed member's admission window to a day in exactly the case §4.6.3 makes common (a host's user added by a stranger).
- Fix: Assign the default duty by leaf index alone ("the host's user with the lowest leaf index") and let a client in request state skip it, so the 24-hour fallback is the documented bound; or state that bound explicitly in §12.5.
- Needs decision: no

### IMP4-11: DM admission host API loose ends
- Severity: P3
- Location: spec/04-access-control.md:175, spec/13-encoding.md:141, spec/03-spaces.md:333
- Evidence: "All three requests are authenticated by the §3.5 exchange, whose `service` is `<host>`"; §3.5: "The client sends `POST <service>/auth`"; §13.2: "DM admission host API | v1 | URL path prefix `/v1/agora/admission-key/`"; errors: "the host answers `400` ..., `401` ..., `403` ..., `404` ..., and `429`"; "the host records when it arrived and returns `204`".
- Problem: (1) The auth path is `<host>/auth`, outside the versioned prefix, so a host serving both a KeyPackage endpoint (`{kp}/auth`) and this API has two auth paths and no version on one. (2) Other CO and IO HTTP APIs return `{ "error": "<code>" }` (§10.5.3, §14.4.3); this one defines bare statuses, so a client cannot tell a rate limit from a missing proof of work (§10.5.2 uses 429 for both). (3) A repeated confirmation is undefined: one host overwrites the arrival time (pushing the 7-day deregistration out), another keeps the first. (4) If registration with one IO fails, the host may still return the key listing that IO, or fail the POST; clients cannot tell.
- Fix: Use `POST <host>/v1/agora/admission-key/auth`; give the error table with JSON codes; state that the host keeps the first confirmation time and answers repeats `204`; state that the host lists in `relays` only IOs that accepted the registration and answers `503` if none did.
- Needs decision: no

### IMP4-12: No rule tells a client whether a Welcome is for a Space group or a DM group
- Severity: P3
- Location: spec/04-access-control.md:90, spec/04-access-control.md:204
- Evidence: §4.3: "If no channel in the client's copy of Space state declares that group ID, the client MUST fetch the current Space state (§3.4) before deciding. If no Space endpoint is reachable, the client holds the Welcome, retries with backoff, and discards the Welcome if it still cannot decide after 7 days." §4.6: "MUST reject a DM Welcome whose GroupContext lacks `agora_admission`."
- Problem: A DM group ID is never in any Space state. A client that applies §4.3 to every Welcome polls every Space endpoint it knows on each DM Welcome (telling each CO when the user receives a DM) and, with one endpoint down, holds DM Welcomes for up to 7 days. The intended classification (presence of `agora_admission`) is implied but not stated.
- Fix: State: "A Welcome whose GroupContext carries `agora_admission` is a DM group or self-group Welcome and is decided by §4.6 and §2.6; any other Welcome is decided by this section."
- Needs decision: no

### IMP4-13: A member regulated by more than one Space has no rule
- Severity: P3
- Location: spec/07-compliance.md:203, spec/07-compliance.md:297
- Evidence: "Add the Space's `loggerDID`"; §7.8.5: "If a DM group contains members from two or more compliance-logging Spaces, each regulated member's client MUST add their respective Space's logger DID".
- Problem: "the Space" is singular. A user listed in `regulatedMembers` of two Spaces (a contractor, or two entities of one group) gets one logger from one client and both from another.
- Fix: "For each Space whose `regulatedMembers` lists the user, the client adds that Space's `loggerDID`."
- Needs decision: no
