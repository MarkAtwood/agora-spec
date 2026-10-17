# Review 2: SEP2 (operator separation applied to the new mechanisms)

Lens: ARCHITECTURE S1-S8, §5 budget, §9 accepted costs, §10 review test, applied to the mechanisms introduced or reworked in b07bead, a5fdf42 and 9e7711f. Only leaks or authority grants beyond what ARCHITECTURE accepts are listed.

### SEP2-1: Public broadcast channels publish their channelToken, so any IO can map that token (and the CO's billing DID) to a named Space and channel
- Severity: P2
- Location: spec/03-spaces.md:311, :297; spec/05-messaging.md:175; vs ARCHITECTURE.md:166-170 (§5 item 6), spec/10-relays.md:546 (§10.4.1), spec/12-security.md:39
- Evidence: 03:311 "For `public`, the CO publishes the channel's `BroadcastKey` and the subscriber form of its `ChannelAdmissionKey` as public Space state ... the endpoint serves them without authentication, and the CO MAY mirror them like other public Space state." 03:297 the subscriber form "carries `channelToken`". ARCHITECTURE §5 item 6: "An IO MUST NOT be able to map an admission key to a Space or channel". 10:546 relay testifies "I do not know which Space or channel any token belongs to".
- Problem: Any IO fetches the public subscriber form, reads the token, and maps it to a named Space and channel. That breaks a MUST in ARCHITECTURE, and §9 does not list it as an accepted cost. It goes further than the accepted "relay list disclosed by choice" (§9). The IO also learns that the billing DID under which the token is registered belongs to this Space's CO. It learns which network addresses and `pushHandle`s follow the channel, and through push clustering (§5 item 7) it can then tie those devices' other tokens under that CO to a known community. `keyAccess: public` is not limited to public Spaces either (03:245 says only "`broadcast` only").
- Suggested fix: Either (a) state in ARCHITECTURE §5 item 6 and §9 that a public broadcast channel's token is public by the CO's choice and is linked to its Space, limit `keyAccess: public` to public Spaces, and qualify §10.4.1 and §12.3. Or (b) keep tokens unpublished: publish only the `BroadcastKey` and the relay list, and have subscribers fetch the subscriber form from the endpoint without authentication but with rate limits. Under (b), MUST NOT mirror it to IO storage.
- Needs decision: yes. (a) accept and disclose (simplest, consistent with "public is public"); (b) narrow publication, which still lets any IO that fetches as a subscriber map the token, so it only raises the cost. Recommend (a), plus restricting `public` to public Spaces.

### SEP2-2: Admission key registrations disclose `keyEpoch`, which tells every IO a channel's removal count and when it was created
- Severity: P2
- Location: spec/10-relays.md:786-807, :837; spec/14-jmap.md:198, :207; spec/06-calls.md:134, :138, :167; vs ARCHITECTURE.md:166-168 (§5 item 6), :392-397 (§9)
- Evidence: 10:790 registration body carries `"keyEpoch": 3`. 10:807 "an IO whose signed admission messages carry `keyEpoch` (for example an SFU, §6.6) checks it against the registered value". 05:257 "The CO rotates the admission key, incrementing `keyEpoch`, when it authorizes the removal of a member". 10:837 "SHOULD batch registrations for new channels and DM groups and add random delay, so that registration timing does not reveal when a particular Space, channel or DM group was created".
- Problem: §5 item 6 budgets which keys are registered and when, not a per-channel rotation counter. Because rotation happens on every authorized removal, `keyEpoch` gives each IO a channel's cumulative removal count (exact where the CO does no periodic rotation). `keyEpoch = 0` flags a newly created channel or DM, which undoes the random delay 10:837 requires to hide creation time. `k+1` replacing `k` also makes successive-key linkage deterministic instead of the timing inference §9 accepts. No IO needs the value: 10:815 already fixes "A token is registered with at most one key", so `channelToken` alone identifies the key for the sequencer (14:207) and the SFU (06:167).
- Suggested fix: Remove `keyEpoch` from `AdmissionKeyRegistration`, `seq-auth`, `sfu-admission` and `sfu-admitted`. IOs match on `channelToken` only. Keep `keyEpoch` member-side (HKDF info, `ChannelAdmissionKey`, endpoint paths).
- Needs decision: no

### SEP2-3: A DM's or self-group's "CO" can be a single-user identity host, which gives the relay the initiator's identity; no billing-DID rule covers identity hosts
- Severity: P2
- Location: spec/10-relays.md:777, :696; spec/04-access-control.md:150; spec/12-security.md:53; spec/02-identity.md:496; vs ARCHITECTURE.md:166-170, S1, spec/10-relays.md:545
- Evidence: 10:777 "An identity host that an individual chose holds its own `ServiceAgreement`s under its own billing DID and registers under those, acting as the CO for this purpose." 10:696 billing "MUST NOT appear in Space state, SpaceAds, directory documents, or any other record that identifies a Space". 12:53 "a Relay learns whose agreement covers a DM token ... it does not learn who is in a DM". 02:496 the self-group "is admitted at relays like a DM group whose only member DID is the user, with the admission key issued by the user's identity host".
- Problem: The anonymity set for DM and self-group tokens is the identity host's user base. For a host that serves one person (common for `did:key` and self-hosted `did:webvh`), the billing DID and the registration's source address (the public `KeyPackageEndpoint` host) identify that person. The relay then knows that every token under that agreement is the person's self-group or a DM they started, which contradicts 12:53 and the §10.4.1 testimony "I do not know who is in any group". The billing-DID rule covers only Space-identifying records, so nothing stops a host from using the user's own DID or a DID listed in the user's DID document. ARCHITECTURE §9 accepts "A CO with one Space gets none" for Spaces, but has no equivalent for identity hosts.
- Suggested fix: Extend 10:696 so an identity host's billing DID MUST NOT appear in any DID document, Pkarr record or other user-identifying record. Add to ARCHITECTURE §9: "DM and self-group anonymity at the IO is only as large as the initiator's identity host; a host serving one user gives that user none (the IO learns the initiator of each such token)". Qualify 12:53 and 10:545 to match.
- Needs decision: no

### SEP2-4: ARCHITECTURE §9 says an identity-plus-relay operator "never learns ... channel", but as DM admission host it knows DM membership by DID, and as relay it sees each DM's traffic
- Severity: P2
- Location: ARCHITECTURE.md:405-408; profiles/corundum.md:30, :38; spec/04-access-control.md:158; spec/12-security.md:239
- Evidence: ARCHITECTURE:405 "A party that runs both a social or identity service and relays can link its own users to the COs whose traffic they use. It never learns content, channel or Space." corundum.md:30 "A CORUNDUM operator may host a user's `did:webvh` log and their `AgoraKeyPackageEndpoint`". 04:158 "The host learns the DM group's member DIDs". corundum.md:38 "That text is not in ARCHITECTURE.md yet."
- Problem: The KeyPackage host is the initiator's DM admission host. It issues the DM's token, holds its member DIDs, picks its relays (naturally its own), and authenticates each member by DID from that member's network address (§3.5, hourly key fetches, 05:256). As relay it then sees every envelope on that token, with the sender's address and timing. It can therefore attribute DM activity, and often individual envelopes, to named members. That is much more than "link its own users to the COs", and "never learns ... channel" is false for DMs. §2.4 allows the co-location, but the accepted-cost text understates what it costs. The profile's "not in ARCHITECTURE.md yet" is stale.
- Suggested fix: Rewrite the §9 bullet: "... can link its own users to the COs whose traffic they use. Where it is also the DM admission host (the KeyPackage host of the initiator), it knows each such DM's members and token and, at its relays, the DM's traffic timing and senders' network addresses. It never learns content." Mirror this in corundum.md §2 and drop "not in ARCHITECTURE.md yet". Optionally RECOMMEND that a DM admission host not list relays it operates.
- Needs decision: no

### SEP2-5: Any single DM member can rewrite the admission host's member list, silently cutting others off at relays or handing the admission key to non-members
- Severity: P2
- Location: spec/04-access-control.md:155-158, :259; spec/07-compliance.md:285; vs ARCHITECTURE.md §6.3 (:291-294), spec/04-access-control.md §4.6.1
- Evidence: 04:158 "any listed member replaces it after a membership change, by ... `DMMembers` ... signed ... by a device key of a DID on the current list. When a replacement drops a DID, the host rotates the key." The host "serves the key only to DIDs on the group's member list".
- Problem: The host cannot see MLS state, so it applies whatever list any one member signs. One member can drop the others: the host rotates the key and refuses them the new one, so after the deregistration they can no longer post or subscribe to the new token, although they are still MLS members and no Remove or consent took place. One member can also add arbitrary DIDs, which then get the admission key and token (traffic correlation, junk posting) without the §4.6.1 approvals. This is an admission decision made at a CO component on one member's word, bypassing the group's own membership rules. ARCHITECTURE §6.3 puts membership validation with clients.
- Suggested fix: Make the host accept a `DMMembers` replacement only when it (i) drops just the signer's own DID (self-leave), or (ii) carries the `AddApproval`s or Commit evidence the consent model requires, or is co-signed by the DIDs it removes. Otherwise let the host apply only additions it can tie to a Welcome it can see, which it cannot, so (i) and (ii) are the practical options. At minimum, state the risk in §4.6 and §12.
- Needs decision: yes. (a) self-only removals plus signed approvals for additions (recommended); (b) require k-of-n member signatures for any change; (c) accept and disclose.

### SEP2-6: A DM's admission host stays with the initiator's identity host after the initiator leaves or is offboarded, and the remaining members cannot replace it
- Severity: P2
- Location: spec/04-access-control.md:158, :259; spec/02-identity.md:447-456; spec/12-security.md:239; vs ARCHITECTURE.md §1 (:13-17)
- Evidence: 04:158 "The initiator's client MUST put that URL in the DM group's GroupContext as the `agora_admission_host` extension". 04:259 leaving a DM only "replaces the member list at the admission host". There is no procedure to change `agora_admission_host`.
- Problem: After the initiator leaves, or after an employer offboards the initiator (§2.5.6), a party outside the group keeps admission authority over it. That party still learns membership changes and hourly fetch and online patterns of the remaining members (05:256), and can stop rotating keys or drop its agreements, which stops delivery. ARCHITECTURE §1 puts every authority over a community with the community's own operator. The remaining members have no way to move the DM to a member's host. This is the CO-side counterpart of S5, and it is unspecified.
- Suggested fix: Define a handover: a remaining member's client commits a GroupContextExtensions proposal setting `agora_admission_host` to its own identity host, which issues a new admission key (new token) and registers it. Clients MUST perform this when the current host's user is no longer a member. Note in §12.11 that the initiator's host learns the other members' fetch timing.
- Needs decision: no

### SEP2-7: Undelayed removal rotations let an IO see that a member was removed and which subscriber was dropped
- Severity: P3
- Location: spec/10-relays.md:837, :564; spec/05-messaging.md:256; vs ARCHITECTURE.md:392-397 (§9), S1
- Evidence: 10:837 "It sends registrations for a rotation that follows a removal without added delay". 05:256 a client "subscribes to the new token and keeps the previous subscription until the relay reports the old token withdrawn". 10:564 "the same subscribers move across".
- Problem: Batched, delayed periodic rotations and immediate removal rotations look different, so an IO can tell removals apart. In each removal it sees which address or `pushHandle` stays on the old token and never moves. §9 accepts linking successive keys by timing. It does not state that the IO learns removal events and which (pseudonymous) device was removed, which is pseudonymous membership-change knowledge.
- Suggested fix: Add to §9 and §12.4: "An IO can tell a removal rotation from other rotations and can see which subscribers do not move to the new token." Optionally RECOMMEND sending periodic rotations undelayed as well, so that removal rotations are not distinguishable by timing alone.
- Needs decision: no

### SEP2-8: The self-group gives relays a token that only one person's devices hold, which links that person's devices, addresses and push handles
- Severity: P3
- Location: spec/02-identity.md:496; spec/04-access-control.md:158; vs ARCHITECTURE.md:398-401 (§9 "Push links a device's channels"), :395-397
- Evidence: 02:496 the self-group "is admitted at relays like a DM group whose only member DID is the user".
- Problem: Every device of the user subscribes to the self-group token, and no one else does. A relay therefore groups those devices (their addresses, sessions and `pushHandle`s) as one person, and the union of their token sets is that person's group set across COs. §9 accepts device-level push linkage and same-address clustering, not linkage across a person's devices on different networks.
- Suggested fix: Add to the §9 push/address bullet: "A user's self-group token is followed only by that user's devices, so a relay serving it can link those devices to one another." Optionally RECOMMEND that the self-group use a relay different from the user's other groups where possible.
- Needs decision: no

### SEP2-9: The SFrame KID gives the SFU a stable per-member pseudonym and epoch-change signal; §6.6 wrongly calls this within budget items 1-2
- Severity: P3
- Location: spec/06-calls.md:186, :191, :222; vs ARCHITECTURE.md:149-157 (§5 items 1-2)
- Evidence: 06:186 the SFU can observe "The SFrame KID, which holds an MLS leaf index, low epoch bits and a context ID, and no DID". 06:191 "These fall within the IO observation budget (ARCHITECTURE §5, items 1–2)."
- Problem: Item 2 lists routing-envelope fields only. A leaf index persists across calls, MLS epochs and admission-key rotations, so it is a per-member sender pseudonym the SFU can follow across sessions and networks. The epoch bits expose membership changes. Neither appears in the budget.
- Suggested fix: Add to ARCHITECTURE §5 (item 2 or a new SFU item) "for an SFU, the SFrame KID (sender leaf index, low epoch bits, context ID)", and to §9: "an SFU can follow one member's media across calls by leaf index without learning the DID." Correct the 06:191 citation.
- Needs decision: no

## Areas checked with nothing to report

- Live client-relay message set (11:65-169): every relay-visible field is in the §5 budget or the push item. The JMAP sync `Envelope` object adds no identity.
- Token suspension, recovery from backup and retirement (10:640-646): carriage decisions with notice to the CO. No membership knowledge and no community decision. Re-registration within 24 h needs no new data.
- Takedowns (10:628-632, 04:245): the CID-to-token lookup is within budget, and forwarding to the agreement `contact` reveals nothing to the requester.
- HTTP proof of work (10:760-773): carries no identity.
- Sequencer as relay and commit stream (14:134-255, 05:27): disclosed in §14.4.6 and §5 item 2 (`commitStamp`). Availability-only trust, and replacement via Space state preserves S5.
- Shared channels (08:93-102): only the home CO registers.
- KeyPackage host gating (04:217, 03:329): the caller DID is revealed to a CO component, as disclosed.
- MemberAuth (03:325-343): CO only. IOs are excluded.
- `IdentityChanged`, guardian transfer, social-recovery guardians: travel inside MLS or as CO-signed state.
- Pkarr service records (10:490-499): name no IO.
- Compliance record verification material (07:92-144): CO data. Requires encryption on IO storage.
- MIMI credential (09:28-48): only inside MLS. The fallback mapping is barred from relays.
- TURN (06:252-303): no identity reaches the TURN server.

Coverage: read in full ARCHITECTURE.md; spec/10-relays.md; spec/05-messaging.md §5.1-§5.2.5; spec/11-transport.md; spec/03-spaces.md §3.3 (from line 100)-§3.6; spec/04-access-control.md; spec/02-identity.md; spec/14-jmap.md §14.3-§14.4; spec/12-security.md §12.3-§12.5, §12.8-§12.12; spec/07-compliance.md §7.1-§7.4, §7.8-§7.9; spec/09-interop.md §9.1-§9.2 (part); spec/08-cross-space.md §8.3 (end)-§8.9; spec/06-calls.md §6.6-§6.11; profiles/corundum.md; notes/review/reconciliation.md (summary and open items); notes/review/SEP-verified.md headings.
