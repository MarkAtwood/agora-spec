# SEP4 verified (review 4, checked at 4b76c3d)

Summary: 5 CONFIRMED (SEP4-1, -2, -3, -4, -5), 2 PARTIAL (SEP4-6, -7), 0 REJECTED.
Needs decision: SEP4-1 (member-side part only), SEP4-2.

### SEP4-1: `closingHeads` in a public Space's non-member view maps every channel's tokens to the Space
- Verdict: CONFIRMED.
  - The non-member view omits only `members` (03-spaces.md:179, :213) and, for hidden channels, "the channel path" (04-access-control.md:94). Nothing removes `closingHeads` (03-spaces.md:195, :221), so by the current text it is served unauthenticated to anyone for a public Space (03-spaces.md:321) and may be mirrored on IPFS (:325).
  - `stream` is `SHA-256("agora/commits/v1" || channelToken)` (05-messaging.md:27, 14-jmap.md:166). Every Relay and sequencer carrying the channel holds `channelToken`, and Relays see `commitStamp` in `signed` (05-messaging.md:276; ARCHITECTURE §5 item 2). So any IO maps each listed channel's token to its `channelID` and Space, and through the replacement chain of §10.5.3 to later tokens. `hash` does the same at the old sequencer and at any Relay that hashes the stamps it carries.
  - This violates S1 and §5 item 6 ("An IO MUST NOT be able to map an admission key to a Space or channel, except the token of a `keyAccess: public` broadcast channel"). §9 accepts the mapping only for public broadcast tokens. It also lists the channelIDs of hidden private channels, contrary to 04-access-control.md:94 "Non-members have no way to enumerate private channels".
  - Member-side leak confirmed as real: the sealed envelope hides `group_id` precisely so a relay cannot map traffic to a channel (05-messaging.md:315), and a member not permitted to read a private channel has no other way to learn its token. `closingHeads` gives every Space member `stream` and `hash` for every channel, so a member who also operates (or colludes with) a Relay or the sequencer can label that channel's traffic.
  - agora-sequencer-replacement places the heads in the Space state change; the fix below keeps that placement and only restricts the non-member view, so it is consistent.
- Severity: keep P1. Unauthenticated, mirrorable, and breaks S1 for every channel of a public Space at every replacement.
- Fix:
  - spec/03-spaces.md:221, Presence cell: "only in a state that replaces or removes the `sequencer` DID; omitted from the non-member view".
  - spec/03-spaces.md:195, append: "`closingHeads` is omitted from the non-member view (§4.4); the view served to eligible guest members of a shared channel (§8.6) carries only that channel's entry."
- Needs decision: yes, member-side part only.
  - Options: (a) record the member-side exposure in ARCHITECTURE §9; (b) move each channel's head out of Space state into the first new-`keyEpoch` `ChannelAdmissionKey` so only readers see it (reopens agora-sequencer-replacement, which put it in the Space state change); (c) leave unstated.
  - Recommendation: (a). It keeps the decided placement, needs no mechanism, and the exposure requires a member who is also an IO operator. Dropping `stream` alone would not help, because `hash` leaks the same mapping to any Relay. Text for §9, under "Space anonymity at the IO is only as large as the CO": "A sequencer replacement shows every Space member the closing commit-stream head of every channel (protocol spec §3.3), so a member who also runs or colludes with a Relay or the sequencer can recognise the traffic of channels it cannot read. It cannot read that traffic."
  - Plain language: when a community switches ordering servers, the switch record carries a fingerprint for every channel. Ordinary members may see fingerprints of channels they cannot read, which only matters if one of them also runs a server carrying that traffic.

### SEP4-2: Push proxy has no CO binding and no designation path; one handle links a device across COs
- Verdict: CONFIRMED, all three parts.
  - (1) 11-transport.md:262 lets a Relay designate a proxy; no agreement between the CO and that proxy exists, while §6.1 says the CO "engages every IO, whatever the service, by a `ServiceAgreement`". Retention of device tokens and wake-up timing is set nowhere for a Relay-designated proxy.
  - (2) grep for `pushProxy` / push proxy finds the designation only in the Relay manifest (11-transport.md:285). No Space state field, `ChannelAdmissionKey` member or agreement field names a CO-designated proxy, so "one designated by the client's CO" (:339) has no implementation path. The `push-proxy` agreement has no `endpoint` (10-relays.md:735), so clients cannot get it from there either.
  - (3) §11.7.3 step 4 sends one `pushHandle` and one `proxyEndpoint` to every Relay. With a CO-run proxy (agora-q4-push; ARCHITECTURE.md:62), that proxy sees wake-ups signed by the Relays of every other CO and DM host the device uses (:271). Reviewer missed the reverse leak, which is worse: every other CO's Relay sees the first CO's `proxyEndpoint` on the registration, so it can tie that CO's member device to its own tokens (an employer's push host labels the device "employee of X" at unrelated relays). §5 item 7 lists "its proxy endpoint" as observable, but §9 does not state this consequence. And 11-transport.md:359 ("unknown or untrusted Relay DIDs MUST be rejected") makes a strict CO proxy drop other COs' wake-ups.
- Severity: keep P2. The CO-designation MAY cannot be implemented as written, and the cross-CO linkage reaches IOs.
- Fix (recommended set):
  - (a) spec/11-transport.md §11.7.3, after step 4 add: "A client registers a separate `pushHandle` with each proxy it uses. It registers with a CO-designated proxy only the `channelToken`s of that CO's channels, and with a Relay-designated proxy all other tokens."
  - (b) spec/03-spaces.md, `ChannelAdmissionKey`: add optional member `pushProxy` (`{endpoint, proxyDID}`), "the push proxy the CO designates for this channel (§11.7); absent for DM groups and self-groups, which use the Relay's proxy." Serving it only with the key keeps it out of the public view.
  - (c) ARCHITECTURE S7 / §6.1 and spec/11-transport.md:262, add: "A Relay-designated push proxy is part of the Relay's service: the Relay's `relay` agreement covers its retention and observation-budget declaration, and the Relay's manifest declares it. A CO-designated proxy that is an IO is engaged by a `push-proxy` agreement."
- Needs decision: yes.
  - Options: (a)+(b)+(c); (d) drop CO-designated proxies (contradicts agora-q4-push "CO may run own proxy", so it reopens Q4); (e) keep one handle per device and add both linkages (proxy sees other COs' relays; other COs' relays see the CO's proxy endpoint) to ARCHITECTURE §9.
  - Recommendation: (a)+(b)+(c). Per-proxy handles remove both linkages by construction, (b) is the minimum field that makes the existing MAY work, and (c) is a sentence, not a mechanism.
  - Plain language: phones are woken through a push server, but the spec never says how a community tells members which push server to use, and a relay's push server has no contract with the community. If an employer runs its own push server and the phone uses one push identity everywhere, unrelated communities' relays can see the phone belongs to that employer's staff, and the employer sees which other relays wake it.

### SEP4-3: DM admission host learns co-membership of its own users
- Verdict: CONFIRMED. Two users of one host each POST for the same `<groupID>` under their own DIDs (04-access-control.md:175), and the 24-hour rule (:200) makes every host's user do so routinely. The host also records each key's issuee. The four "not the other members" statements are therefore false for co-hosted members. One more location the reviewer missed: spec/12-security.md:258 "so the host does not learn the other members' DIDs". (The same party as KeyPackage host may already infer some co-membership from Welcome deliveries, which strengthens the case for correcting the wording.)
- Severity: keep P3. Wording, no IO impact.
- Fix:
  - spec/04-access-control.md:177: "It does not learn the group's other members, except which of its own users also request or confirm keys for the group, and no IO learns them."
  - spec/12-security.md:250 cell: "...; not the group's other members, except its own users whose clients also request keys for the group".
  - spec/12-security.md:258: "so the host does not learn the other members' DIDs, except those of its own users whose clients also request keys for the group, or when they are active."
  - ARCHITECTURE.md:498: "not the other members, except those of its own users whose clients also request keys for the group,".
  - profiles/corundum.md:38: "It does not learn the group's other members, except its own users whose clients also request keys for the group."
  - profiles/discord-onboarding.md:531: "it does not learn the groups' other members, except its own users whose clients also request keys for them (spec §4.6)."
- Needs decision: no.

### SEP4-4: DM and self-group keys registered with SFUs and sequencers that cannot serve them
- Verdict: CONFIRMED. 04-access-control.md:165 and 10-relays.md:820 register with every IO whose `serviceType` receives registrations, including `sfu` and `sequencer`. DM groups have no sequencer (14-jmap.md:159). DM voice groups exist (06-calls.md:465) but a client may use only an SFU "listed in current Space state" (06-calls.md:86), which a DM lacks, so DM calls are mesh only. 10-relays.md:820 itself says the `sfu` and `sequencer` agreements "are named in Space state". The registrations are pure surplus observation (tokens plus rotation timing) at IOs that never carry the traffic.
- Severity: keep P3. Within the §5 item 6 budget, but needless.
- Fix:
  - spec/04-access-control.md:165: replace "with every IO holding a `ServiceAgreement` with it whose `serviceType` receives registrations (§10.5.1, §10.5.3)" with "with every Relay holding a `relay` `ServiceAgreement` with it (§10.5.1, §10.5.3), and with no SFU or sequencer".
  - spec/10-relays.md:820, after "(§4.6)." add: "A DM group or self-group has no Space state, so its admission host registers its keys only under `relay` agreements."
  - profiles/o365-employer-did.md:690: replace "with every IO (relay, SFU, sequencer) that holds a `ServiceAgreement` with the organization whose `serviceType` receives registrations" with "with every relay that holds a `relay` `ServiceAgreement` with the organization".
- Needs decision: no.

### SEP4-5: Sequencer DID in `commitStamp` lets Relays partition a CO's tokens by sequencer
- Verdict: CONFIRMED. `commitStamp` sits in `signed` (05-messaging.md:276; ARCHITECTURE §5 item 2) and is a signed envelope whose `kid` names the sequencer DID (13-encoding.md:70). A CO with per-Space sequencers (allowed; 03-spaces.md:193 and 14-jmap.md:263 are SHOULDs) lets each Relay group its tokens by sequencer, and a public Space's state names its sequencer, tying that group to the Space. 14-jmap.md:263 states this only for the sequencer; ARCHITECTURE §9 does not list it.
- Severity: keep P3. Disclosure gap behind an existing SHOULD.
- Fix:
  - spec/14-jmap.md:263, append: "Every Relay carrying a sequenced channel also reads the sequencer DID in each `commitStamp` (§5.2.2), so a CO that uses different sequencers for different Spaces lets its Relays group its tokens by sequencer, and tie a group to any public Space that names its sequencer."
  - ARCHITECTURE §9, bullet "Space anonymity at the IO is only as large as the CO", append: "A CO that uses different sequencers for different Spaces lets its Relays group its tokens by the sequencer DID in each Commit's stamp."
- Needs decision: no. (Turning the SHOULD into a MUST would be a constraint alternative, but it would forbid staged sequencer moves; documenting is enough.)

### SEP4-6: Self-group not excluded from DM compliance capture
- Verdict: PARTIAL. The rule exists elsewhere: spec/02-identity.md:496 defines the self-group as an MLS group "whose members are only the user's own devices", a MUST, so adding a logger already violates the spec. The self-group is never called a DM group; it is "admitted at relays like a DM group". What remains is a missing cross-reference in §7.8.1, whose "every DM group" a careless reader could stretch. No new rule is needed.
- Severity: adjust to P3 editorial (no behavior gap).
- Fix: spec/07-compliance.md §7.8.1, end of the first paragraph: "A self-group (§2.6) is not a DM group; its members are only the user's own devices, so no logger or recorder is added to it."
- Needs decision: no.

### SEP4-7: Gateway in a DM group has no controlling CO and no disclosure record
- Verdict: PARTIAL. The send-gate already blocks it: "A gateway MUST NOT carry messages in either direction until its `GatewayDescriptor` is in the channel's current Space state" (09-interop.md:68). A DM group has no Space state, so a conformant gateway can never carry DM traffic, and §9.1 says a gateway is "added by a channel Admin". The gap is only that the consequence is implicit; implementers would converge on "no gateways in DMs" from the send-gate. Members cannot tell a gateway DID from any other DID, so a Welcome-refusal rule binds only the gateway, which the send-gate already binds.
- Severity: adjust to P3 editorial.
- Fix: spec/09-interop.md §9.1, end of "Identity and admission": "A DM group or self-group has no Space state, so no gateway can satisfy §9.3 there; a gateway joins only Space channel groups."
- Needs decision: no.
