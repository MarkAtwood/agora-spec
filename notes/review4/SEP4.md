# SEP4: operator separation (review 4, commit 4b76c3d)

Lens: ARCHITECTURE S1-S9, §5 budget, §6 CO-IO interface, §9 accepted costs,
§10 review test. Checked against `bd memories agora` (agora-dm-key-in-group,
agora-dm-key-cap, agora-dm-host-move, agora-self-group-spaces,
agora-credentials, agora-dm-compliance-ext, agora-sequencer-replacement,
agora-gateways-profile, agora-q4-push, agora-blob-token-free).

Clean under this lens: the DM `agora_admission` design (host keeps no member
list; key reaches non-host members only through the GroupContext; handshakes
are `PrivateMessage` inside the sealed envelope, so no IO sees the
extension); `agora_compliance` (GroupContext only, logger KeyPackage endpoint
is CO); `agora_space_membership` (self-group GroupContext only);
`agora_credentials` (leaf extension, omitted from published KeyPackages by
default, ratchet tree never served by an IO, spec/05-messaging.md:64);
registration bodies; SFU admission; TURN; the §5.1.1 commit rule (sequencer
sees only stream names derived from tokens, §14.4.6); §9 gateways for Space
channels.

### SEP4-1: `closingHeads` maps every channel's routing tokens to its Space in a public Space's non-member view
- Severity: P1
- Location: spec/03-spaces.md:195, spec/03-spaces.md:221, spec/04-access-control.md:94, spec/14-jmap.md:166, spec/14-jmap.md:257
- Evidence:
  - 03-spaces.md:195: "`closingHeads` ... is an array with one entry `{channelID, stream, n, hash}` per channel that has an MLS group: `stream` is the commit stream (§14.4.2) of the channel's current `channelToken` under the prior state".
  - 14-jmap.md:166: "its **commit stream**, named `SHA-256("agora/commits/v1" || channelToken)`".
  - The field index (03-spaces.md:213) omits only `members` from the non-member view ("required; omitted from the non-member view"); `closingHeads` (:221) has no such note. §4.4 (04-access-control.md:94) omits only "the channel path" of hidden channels and says "Non-members have no way to enumerate private channels they are not members of."
  - 03-spaces.md:321: "For a public Space, the endpoint serves non-members the access-controlled view of §4.4", unauthenticated; 03-spaces.md:325 lets the CO mirror public state on IPFS.
- Problem: Every Relay and sequencer holds the channel's `channelToken` and can compute `SHA-256("agora/commits/v1" || channelToken)`; Relays also see the `stream` in every `commitStamp` (05-messaging.md:276). A public Space's non-member view that carries `closingHeads` therefore lets any IO map the token of every channel with an MLS group, private channels included, to its `channelID` and Space, and through `replaces` (10-relays.md:850) to every later token of that channel. `hash` alone does the same for the old sequencer, which can look the stamp up in its log. That breaks S1 and §5 item 6 ("An IO MUST NOT be able to map an admission key to a Space or channel, except the token of a `keyAccess: public` broadcast channel") and contradicts §4.4. The accepted cost in ARCHITECTURE §9 covers only public broadcast tokens. A secondary leak: members of any Space who cannot read a private channel learn its `stream` and `hash`, which lets a member who is also an IO operator (trivial in an open public Space) recognise that channel's traffic.
- Fix: spec/03-spaces.md:221, change the Presence cell to "only in a state that replaces or removes the `sequencer` DID; omitted from the non-member view". Add to 03-spaces.md:195: "`closingHeads` is omitted from the non-member view (§4.4); the view served to guest members of a shared channel (§8.6) carries only that channel's entry." For the member-side leak see the decision below.
- Needs decision: yes, for the member-side part only (the non-member omission needs none). (a) Record in ARCHITECTURE §9 that a sequencer replacement shows every Space member the commit-stream head of every channel, so a member who also runs an IO can recognise channels it cannot read. (b) Keep the head in the Space state change as agora-sequencer-replacement decided, but give each entry as `{channelID, keyEpoch, n, hash}` and serve the full entry only in the channel's `ChannelAdmissionKey` of the first new `keyEpoch`, so only channel readers see it. (c) Leave as is. Recommendation: (a), because it keeps the decided placement and the exposure needs a member who is also an IO operator. Plain language: when a community switches its ordering server, the switch record lists a fingerprint for every channel, and a public community hands that record to anyone, including the servers that carry the traffic, which lets them label every channel's traffic. Hiding that list from outsiders fixes the serious part; whether ordinary members may see fingerprints of channels they cannot read is a smaller judgment call.

### SEP4-2: Push proxy engagement has no CO binding and no designation path, and a CO-run proxy sees a device's other communities
- Severity: P2
- Location: spec/11-transport.md:262, spec/11-transport.md:339, spec/11-transport.md:359, spec/10-relays.md:735, ARCHITECTURE.md:121-126, ARCHITECTURE.md:213-215
- Evidence:
  - ARCHITECTURE S7: "The only binding between a CO and an IO is the `ServiceAgreement` ... This holds for every IO service type: relay, SFU, TURN, sequencer and push proxy." §6.1: "It engages every IO, whatever the service, by a `ServiceAgreement`".
  - 11-transport.md:262: "A Relay MAY designate a push proxy in its manifest (§11.7.2), and a CO MAY designate its own push proxy for its members."
  - 11-transport.md:339: "The Relay sends the wake-up to whichever proxy the client registered, its own or one designated by the client's CO."
  - 10-relays.md:735: the agreement's `endpoint` "is absent for service types that receive no registrations" (`push-proxy` receives none, :733).
  - 11-transport.md:271: the proxy learns "The `relayDID` that signed each wake-up request"; :359: "Wake-up requests from unknown or untrusted Relay DIDs MUST be rejected."
- Problem: (1) A relay-designated proxy is engaged by the Relay, not by any CO, so no `ServiceAgreement` fixes its retention of device tokens and wake-up timing or its budget declaration, contrary to S7 and §5 item 1 ("Retention is set by the `ServiceAgreement`"). (2) No record tells a member's client which proxy its CO designated: Space state, `ChannelAdmissionKey` and the agreement carry no proxy endpoint, so "designated by the client's CO" cannot be implemented and clients will diverge. (3) §11.7.3 gives a device one `pushHandle` registered with one proxy and sent to every Relay. A CO-run proxy (ARCHITECTURE.md:62 "a CO MAY run its own") then receives wake-ups signed by the Relays of every other CO and DM host the device uses, with timing, and the CO knows which member owns its managed device. That links a named member to the other communities' relays, a linkage not in ARCHITECTURE §9. Under (3) a proxy that applies :359 strictly instead drops other COs' wake-ups, so push silently fails.
- Fix: (a) spec/11-transport.md §11.7, add: "A client registers a separate `pushHandle` with each proxy it uses, and registers with a proxy only the `channelToken`s of groups whose CO designated that proxy; it uses a Relay-designated proxy for all other tokens." (b) Add a `pushProxy` member (`{endpoint, proxyDID}`) to the `ChannelAdmissionKey` (03-spaces.md:288) as the CO's designation, absent for DM groups. (c) ARCHITECTURE S7 and §6.1: state that a Relay-designated proxy is the Relay's subcontractor, bound by the Relay's agreement and covered by its manifest declaration, or require a `push-proxy` agreement for any proxy that receives a CO's members' registrations.
- Needs decision: yes. (a)+(b)+(c) as above (recommended: per-proxy handles remove the cross-CO linkage by construction; the designation field is the minimum needed for the existing MAY to work). (d) Drop CO-designated proxies entirely and use only Relay-designated ones bound through the Relay's agreement. (e) Keep one handle per device and add the cross-CO linkage to ARCHITECTURE §9. Plain language: phones get woken through a push server, but the spec never says how a community tells its members which push server to use, and a push server picked by the relay has no contract with the community at all. If an employer runs its own push server, it can also see which other communities' servers wake an employee's phone, unless phones keep a separate push identity per push server.

### SEP4-3: DM admission host learns co-membership of its own users, contrary to four statements that it learns no other members
- Severity: P3
- Location: spec/04-access-control.md:167, :175, :177, :200; spec/12-security.md:250; ARCHITECTURE.md:496-499
- Evidence:
  - 04-access-control.md:167: "A group can have more than one host's user."
  - :175: "All three requests are authenticated by the §3.5 exchange ... records the requesting DID as the key's **issuee**".
  - :200: "another host's user's client MAY do the same. If no Commit that changes `agora_admission` has arrived 24 hours after such a Commit, every host's user's client MUST do so."
  - :177: "It does not learn the group's other members". 12-security.md:250: "not the group's other members". ARCHITECTURE §9: "it knows its own user's DID and the group's ID, not the other members".
- Problem: When two or more members share an identity host (two employees, or two users of one large individual host), each one that POSTs for the same `<groupID>` authenticates with its own DID, so the host learns that those users are in one DM group. The 24-hour rule makes this routine, not exceptional. For an employer this is inside its own CO; for a shared individual host (profiles/corundum.md, profiles/discord-onboarding.md) it is a social graph among its users that the spec says it does not get. No IO learns anything new.
- Fix: Change 04-access-control.md:177 to "It does not learn the group's other members, except which of its own users also request or confirm keys for the group." Make the same change in the 12-security.md:250 cell and ARCHITECTURE §9 ("not the other members, except those of its own users whose clients also request keys for the group"), and in profiles/corundum.md:38 and profiles/discord-onboarding.md:531.
- Needs decision: no.

### SEP4-4: DM and self-group keys are registered with SFUs and sequencers that can never serve them
- Severity: P3
- Location: spec/04-access-control.md:165, spec/10-relays.md:820, spec/06-calls.md:86, spec/14-jmap.md:159, profiles/o365-employer-did.md:690
- Evidence:
  - 04-access-control.md:165: the admission host "registers it by `AdmissionKeyRegistration` with every IO holding a `ServiceAgreement` with it whose `serviceType` receives registrations".
  - 14-jmap.md:159: "DM groups have no Space and no sequencer".
  - 06-calls.md:86: a client "MUST verify, before sending media, that the SFU it connects to is listed in current Space state"; DM groups have no Space state.
  - o365-employer-did.md:690: "registers it ... with every IO (relay, SFU, sequencer)".
- Problem: For an employer host the employer's SFU and sequencer receive every employee DM and self-group token, with creation and rotation timing (rotations after removals are sent without delay, 10-relays.md:880), though neither IO can ever carry that traffic. This is within §5 item 6 but is pure surplus observation at extra IOs, and §10.5.3's own description of which agreements a registration service uses ("its `sfu` and `sequencer` agreements are named in Space state") does not fit a DM host.
- Fix: spec/04-access-control.md:165, replace "with every IO holding a `ServiceAgreement` with it whose `serviceType` receives registrations (§10.5.1, §10.5.3)" with "with every Relay holding a `relay` `ServiceAgreement` with it (§10.5.1, §10.5.3); it registers DM and self-group keys with no SFU or sequencer". Same change in profiles/o365-employer-did.md:690 ("every relay that holds a `ServiceAgreement` with the organization").
- Needs decision: no.

### SEP4-5: The stamp signer in `commitStamp` lets every Relay partition a CO's tokens by sequencer and tie them to public Spaces
- Severity: P3
- Location: spec/14-jmap.md:263, spec/05-messaging.md:276, spec/13-encoding.md (§13.1.1 `kid`)
- Evidence:
  - 05-messaging.md:276: `commitStamp` is "the encoded `SequenceStamp` envelope", visible in `signed`; §13.1.1 puts the signer's DID URL in each `kid`.
  - 14-jmap.md:263: "A CO that uses one sequencer for all its Spaces makes the set of Spaces the sequencer cannot tell apart every Space the CO serves through it", stated only for the sequencer.
- Problem: Every Relay carrying a sequenced channel reads the sequencer DID on each Commit. If a CO uses different sequencers for different Spaces (allowed; the rule is a SHOULD), each Relay can split the CO's tokens by Space group, and a public Space's state names its sequencer, so tokens stamped by a sequencer only that public Space uses map to it. ARCHITECTURE §9 does not list this; §14.4.6 gives the SHOULD's reason only for the sequencer.
- Fix: spec/14-jmap.md:263, append: "Every Relay carrying a channel also reads the sequencer DID in each `commitStamp` (§5.2.2), so a CO that uses different sequencers for different Spaces lets its Relays group its tokens by sequencer, and tie them to any public Space that names that sequencer." Add the same sentence to the ARCHITECTURE §9 bullet "Space anonymity at the IO is only as large as the CO."
- Needs decision: no.

### SEP4-6: Nothing excludes the self-group from DM compliance capture, which would hand one CO's logger other COs' plaintext
- Severity: P3
- Location: spec/07-compliance.md:197, :203; spec/02-identity.md:496, :531-551
- Evidence:
  - 07-compliance.md:197: "A regulated member carries that compliance obligation into every DM group they participate in"; :203: "Add the Space's `loggerDID` to the MLS group of every DM group the regulated member creates or joins".
  - 02-identity.md:496: the self-group "is admitted at relays like a DM group whose admission host is the user's own identity host" and carries the Space list, block list, `SocialRecoveryConfig` and `HistoryTransfer`, whose archive holds decrypted payloads of every group (:546-549).
- Problem: The spec never says whether a self-group is a "DM group" for §7.8. A client that treats it as one adds the employer's logger, which then receives the user's full Space list and history transfers carrying plaintext of other COs' channels and DMs. That puts one CO's plaintext into another CO's archive (S8 assigns plaintext to the CO operating the channel) and contradicts 02-identity.md:529 ("Because it names Spaces, the list exists only in the self-group").
- Fix: spec/07-compliance.md §7.8.1, after the first paragraph add: "A self-group (§2.6) is not a DM group for this section; a regulated member's client MUST NOT add a logger or recorder to it."
- Needs decision: no.

### SEP4-7: Gateway rules assume a Space channel; a gateway in a DM group has no controlling CO and no disclosure record
- Severity: P3
- Location: spec/09-interop.md:12, :37, :66; spec/04-access-control.md:214
- Evidence:
  - 09-interop.md:12: a gateway "MUST run under the control of the CO operating the channel".
  - :66: "Every gateway is disclosed to all channel members before messages flow through it. The obligation is on the wire: the `GatewayDescriptor` in Space state and the `gateway-added` `SystemEvent`."
  - 04-access-control.md:214: "Any member of a DM group MAY add anyone by an MLS Add and Commit."
- Problem: A DM group has no CO and no Space state, so a gateway added to one has no S8 owner and no `GatewayDescriptor`; the send-gate (:68) cannot be met, and nothing says whether that forbids gateways in DMs or leaves them undisclosed. Implementers of bridge software will diverge.
- Fix: spec/09-interop.md §9.1, add: "A gateway joins only Space channel groups. It MUST NOT join a DM group or self-group, and its client MUST refuse a Welcome to one."
- Needs decision: no.
