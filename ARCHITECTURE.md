# Agora Architecture: Operator Separation

Status: Draft, normative. 2026-10-16.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in
all capitals.

## 1. The principle

**Operating the infrastructure is separate from operating the communications.**

The party that runs relays and other infrastructure services decides nothing
about any community, and it MUST be replaceable without changing that
community's identity, membership, history or policy. Every authority over a
community (who is in it, what it permits, what it retains, who may see it) is
held by the community's own operator and exercised with that operator's keys.

This is Agora's first design principle. Where any other part of this
specification conflicts with it, this document governs and the conflict is an
erratum.

Relay blindness (protocol spec §10.4.1) limits what infrastructure can *know*.
Operator separation limits what infrastructure can *decide*, and guarantees it
can be *swapped*. Blindness without separation produces a relay that is
ignorant but still in charge; separation without blindness produces a relay
that is powerless but still watching. Agora requires both.

## 2. Roles

### 2.1 Infrastructure Operator (IO)

Runs services that carry, store or forward data for communities without being
part of them: relays (routing, fan-out, envelope cache, gossip, peering), blob
and IPFS pinning, SFUs, TURN, push proxies, and sequencers that stamp an order
on encrypted operations.

### 2.2 Communications Operator (CO)

Runs a community. For a Space this is the Space owner and its delegated admins;
for an organization it is the org. The CO owns identity provisioning,
membership, roles, moderation, Space state, retention policy, compliance
logging, archives, gateways and bridges, enrollment, and the endpoint devices it
issues.

### 2.3 The key test

A component's role is determined by what it holds, not by who runs it:

- A component that holds MLS group secrets, user signing keys, or plaintext,
  or that must know group membership or sender identity to do its job, is a
  **CO component**, regardless of operator or hosting location.
- A component that holds none of these and needs no such knowledge is an
  **IO component**.

| Component | Role | Notes |
|---|---|---|
| Relay | IO | |
| Blob / IPFS pinning | IO | |
| TURN | IO | |
| Sequencer | IO | Stamps order on encrypted operations and Commits; members' clients validate the stamps (protocol spec §14.4). Bound like a relay: `ServiceAgreement`, registered admission keys, learns the CO and not the Space. A CO SHOULD use one sequencer across its Spaces and SHOULD designate a relay it already has an agreement with |
| Push proxy | IO | Observation budget includes device push handles (§5); a CO MAY run its own |
| SFU | IO | MUST NOT be an MLS member (§7, item 6) |
| KeyPackage host | CO | Run by whoever runs the user's identity (§8, Q3). Issues the admission key of each DM group and self-group whose admission host it is (§6.2) and gives it only to its own user, never to other members. MAY refuse KeyPackage fetches and Welcome deliveries from senders the user has blocked, or by policy |
| Admission key registration service | CO | Generates and holds channel admission private keys; registers the public keys with IOs (§6.2) |
| Compliance logger | CO | MLS member; holds plaintext |
| Archive / Purview bridge | CO | Holds plaintext |
| IdP / DID sidecar, enrollment service | CO | Holds or controls identity keys |
| Gateways (Matrix, Slack, Teams) | CO | Break E2EE by design |
| MIMI hub or follower (future option, `profiles/gateways.md`) | CO | Knows room membership |
| Community-mode SpeakerBot | CO | MLS member |
| Managed endpoint devices | CO | Enforcement point for org policy (§6.3) |

### 2.4 One party, two roles

A single entity MAY act as both IO and CO, for example an organization that
self-hosts its relays. The protocol nonetheless treats the two roles as distinct
principals:

- IO keys (`relayDID`, `operatorDID`) and CO keys (Space owner, admins, org
  provisioning key) MUST be distinct.
- No protocol operation grants an IO key authority over community state because
  it happens to share an operator with a CO key.

## 3. Normative requirements

**S1. No membership knowledge.** An IO component MUST be able to perform every
function it is specified to perform without knowing group membership, sender
identity, or the mapping from routing tokens to channel or Space identities.

**S2. No community policy at the infrastructure.** An IO component MUST NOT
make or enforce decisions about community membership, roles, moderation, content
or retention beyond what a CO has expressed in a form the IO can verify without
learning S1-protected information. The only such forms are those defined in
§6.

**S3. No community keys at the infrastructure.** An IO component MUST NOT hold
MLS group secrets, epoch secrets, MLS exporter outputs, channel admission
private keys, user signing keys, or plaintext. The only key material an IO
holds for a community is the verification material of §6.2 (registered
admission public keys and the routing tokens registered with them) and the
TURN shared secret of §6.4, which authenticates the CO credential service and
identifies no member.

**S4. Community state is CO-signed.** Space state, channel state, role
assignments, moderation records and retention policy MUST be signed by CO keys.
An IO key MUST NOT sign community state, and clients MUST reject community
state signed by an IO key.

**S5. Replaceability.** A CO MUST be able to add, remove or replace any IO
without changing Space identity (genesis CID), member identities, MLS group
state or history, and without re-enrolling any member. History survives an IO
departure because members' stores and the CO archive hold it; envelopes held by
relays are a recent window kept under the agreement's retention.

**S6. Bounded observation.** An IO component MUST NOT observe, log or retain
anything outside the observation budget in §5. Any extension that enlarges the
budget MUST be opt-in by the CO and MUST be declared in the relay manifest,
where members can see it.

**S7. Contracts, not configuration.** The only binding between a CO and an IO is
the `ServiceAgreement` (protocol spec §10.5.1) and the verification material
defined in §6, including the TURN shared secret of a `turn` agreement (§6.4).
This holds for every IO service type: relay, SFU, TURN,
sequencer and push proxy. An IO MUST NOT require CO data beyond these as a condition of
service.

**S8. Plaintext stays on CO infrastructure.** Any component that produces or
stores plaintext (compliance logger, archive, bridges, gateways) MUST run under
CO control. Co-location on IO hardware is permitted only under contract with the
IO acting as the CO's processor, and the component remains a CO principal with
its own DID and keys.

**S9. MLS is the source of truth for groups.** Who is in an MLS group, and in
which epoch, is what the group's MLS state says. A component that needs a
group's membership derives it from MLS data (the epoch, the ratchet tree, a
signed GroupInfo) and MUST NOT keep a separately updated membership list for
that group. Ordering competing Commits is the delivery service's job, which
RFC 9420 places outside the group (the sequencer, or the no-sequencer rule,
protocol spec §5.1.1). Space roles and policy sit above MLS as CO-signed state
(S4). Relays never see MLS state (S1).

## 4. What each operator can be compelled to produce

The separation is meant to be legible to counsel and regulators. It is testable
by asking what a legal demand served on each party yields.

- **Served on an IO:** connection metadata within its retention window, opaque
  ciphertext, routing tokens, and whatever else is in §5. Nothing about who is
  in a community or what they said.
- **Served on a CO:** everything the CO's own policy retains, from its own
  archive, under its own retention and legal-hold controls.

The authoritative record for any regulated community is the CO's archive, never
an IO.

## 5. Infrastructure observation budget

An IO MAY observe the following and nothing else:

1. Network-layer connection metadata: source address, timing, volume, transport.
   Retention is set by the `ServiceAgreement` and MUST be declared in the
   relay manifest.
2. Routing envelopes: size, timing, the envelope `id`, and the routing fields in
   the envelope's `signed` part (routing token `channelToken`, timestamp,
   expiry hint and, on a Commit in a channel with a sequencer, the sequencer's
   `commitStamp`; protocol spec §5.2.2), and the per-envelope `powProof` where
   one is required (protocol spec §10.5.2). The payload they carry is
   ciphertext.
3. Verification material and proofs defined in §6 (registered admission public
   keys and `admissionSig` values), connection-level proof of work (protocol
   spec §11.6) and proof of work on HTTP endpoints (protocol spec §10.5.2).
   None of these reveals which member produced it.
4. Content identifiers (CIDs) it stores or pins, and pin/unpin instructions
   authorized under §6. This includes CIDs it replicates to or pulls from
   other IOs carrying the same routing token, which already carry that
   token (protocol spec §10.4.4). An IO never announces or requests private
   ciphertext on the public IPFS network.
5. Quota state under a `ServiceAgreement`, keyed to the agreement and
   never to member identity. Commercial terms between CO and IO are outside the
   protocol.
6. The billing DID of each CO it holds an agreement with, which admission keys
   (§6.2) are registered under each agreement, and when each was registered
   and deregistered, and which registered token a rotated key replaces
   (protocol spec §10.5.3). An IO MUST NOT be able to map an admission key to
   a Space or channel, except the token of a `keyAccess: public` broadcast
   channel, which the CO publishes with its public Space (§9): the set of
   Spaces it cannot tell apart is every Space that CO serves through it. This
   applies to sequencers and SFUs as to relays.
7. Push. A push proxy observes opaque device push handles, the platform device
   tokens they map to, and wake-up timing. A relay that serves push observes
   each registered `pushHandle`, its proxy endpoint and the set of
   `channelToken`s registered to it, and so learns which routing tokens wake
   the same device (protocol spec §11.7). Wake-ups carry no content and no
   urgency. Users MAY disable push; a client with push disabled registers
   nothing with either party.
8. Its own peering relationships with other IOs.
9. SFrame key IDs. An SFU observes the KID of each media frame (protocol spec
   §6.9), which carries the sender's MLS leaf index, stable across calls in
   the group, the MLS epoch modulo 16, and a context ID the sender chooses
   per track (RFC 9605 §5.2). It carries no DID. It can therefore
   tell the senders of one group apart under stable pseudonyms and see when
   the group's MLS epoch changes.

Agora does not claim network-layer anonymity against an IO. Members who need it
use an overlay transport (protocol spec §10.1, §11). This matches the privacy
whitepaper: "Agora is not anonymous."

## 6. The CO–IO interface

### 6.1 Space state and the ServiceAgreement

The CO publishes signed Space state (S4). It engages every IO, whatever the
service, by a `ServiceAgreement` (protocol spec §10.5.1). The agreement's
`serviceType` is one of `relay`, `sfu`, `turn`, `sequencer` or `push-proxy`.
It is signed per protocol spec §13.1.1 by the IO and by the CO's billing DID,
and it fixes retention, quotas and observation-budget declarations in the same
way for every service type. Commercial terms are out of band. Enforcement is by
selection: a CO that is unhappy with an IO replaces it (S5).

An agreement identifies the CO only by a **billing DID**: a key dedicated to
agreements that MUST NOT appear in Space state or any other Space-identifying
record. An agreement names no Space and no channel. Coverage is expressed by
registering channel admission keys (§6.2) under the agreement through a CO-run
registration service, so members can create groups without holding the
billing key. Registration gives every IO whose `serviceType` receives
registrations (relay, SFU and sequencer; protocol spec §10.5.1) a way to admit
members only, without learning their identity. Agreements and registrations are
private between the two parties and are not gossiped or published.

An IO therefore learns which CO an admission key belongs to, never which of
that CO's Spaces. A CO that operates many Spaces through the same IO gives each
of them a correspondingly large anonymity set.

When an agreement is renewed or replaced, or the CO moves to a new billing DID,
the CO signs the new agreement and registers its current admission keys under
it. A CO that suspects its billing key is compromised does the same under a new
billing DID and has the IO end the old agreement. Until then the holder of the
stolen key can register and deregister keys under that agreement: it can spend
the CO's quota and deny service, but it cannot read or post as a member,
because it holds no admission private key and no MLS state.

### 6.2 Admission by CO-issued key

Membership in the MLS group is the only read access control: only members can
decrypt. Write admission at an IO uses a **channel admission key** that the CO
issues to current members. An IO verifies that an envelope comes from a holder
of the current key without learning which member sent it.

*Mechanism (protocol spec §5.2.2, §10.5.1), pending external cryptographic
review (§8 Q1):*

- The CO registration service generates a random Ed25519 admission key pair
  for each channel and each DM group, numbered by a counter `keyEpoch`.
- It registers the public key with every IO holding a `ServiceAgreement`
  with the CO whose `serviceType` receives registrations (protocol spec
  §10.5.1), by an `AdmissionKeyRegistration` sent over HTTPS and signed by
  the billing DID per protocol spec §13.1.1. The registration carries the key's
  `channelToken` and, for a rotated key, the token it replaces, but no
  `keyEpoch`. An `AdmissionKeyDeregistration` tells an IO to stop accepting
  a key. Neither is ever gossiped.
- It serves the private key to authenticated current members (protocol spec
  §3.5) as a `ChannelAdmissionKey` from the Space endpoint, at
  `<spaceEndpoint>/admission-key/<channelID>`. For a DM group or self-group,
  the admission host, initially the initiator's identity host (the host that
  serves the initiator's KeyPackages, §8 Q3), issues the key and gives it only
  to its own user, whose client puts it in the group's MLS GroupContext.
  Members read it there, so the host keeps no member list (S9). After a Commit
  that removes a member or device, the host's user's client requests a new key
  and commits it. When that host's user is no longer a member, a remaining
  member's client moves the role to its own identity host (protocol spec
  §4.6). For a shared
  channel, the home Space's CO issues and registers it. Broadcast channels use
  this same mechanism; their content key is distributed the same way.
- The routing token is derived from the key:
  `channelToken = HKDF-SHA256(IKM = admission private key seed, salt = "",
  info = "agora channel token" || keyEpoch as uint64 big-endian, L = 32)`.
  Tokens therefore rotate with `keyEpoch`, not with MLS epochs.
- Every envelope carries `admissionSig`, an Ed25519 signature under the
  admission private key over the exact bytes of the envelope's `signed` field
  (protocol spec §5.2.2). The IO rejects an envelope whose `admissionSig` does
  not verify under the key registered for its `channelToken`.
- The CO rotates the key (new `keyEpoch`, registration of the new key,
  deregistration of the old) whenever it authorizes a removal, and otherwise
  when needed, for example periodically or after a suspected compromise. An
  MLS epoch change alone does not rotate it.
- When the CO adds an IO or renews an agreement, it registers the current key
  of every channel it serves through that IO, so the IO can join live groups
  (S5).

Consequences:

- **Bans and removals are MLS Removes plus a key rotation.** A removed member
  cannot read after the Remove and cannot post after the rotation. Relays do
  not keep DID ban lists.
- **Timeouts and mutes are client-enforced.** Members' clients drop messages
  from a timed-out member. An IO cannot enforce a timeout without learning the
  sender, so it does not try.
- **Pin and unpin instructions** are authorized by the same key (a
  `PinInstruction` signed under it, protocol spec §11.4), plus a CO-signed role
  check that clients, not IOs, perform. An IO enforces storage quotas by
  agreement, not pin semantics by content.
- **Endpoint outage.** If the registration service or Space endpoint is
  unreachable, the last registered key keeps working. A member removed in the
  meantime can post ciphertext until the rotation, which members' clients
  drop, but cannot read it. This cost is accepted in §9.
- **Commit conflicts.** When two Commits target the same MLS epoch, the one
  the channel's sequencer stamps first wins, among stamped Commits that are
  valid MLS Commits for that epoch, whether or not they were published.
  Members fill gaps in the stamp order from the sequencer's log, so the log
  is the sole referee and no clock is consulted; the others are skipped by
  every member alike. Authorization under Space state is checked after the
  winner is chosen, and an unauthorized winner is a policy violation. Once a rotated admission key is
  registered, the sequencer stamps no Commit on the old token's commit
  stream. If the Space designates no
  sequencer, the Commit with the lowest envelope `id` among those received
  within a 5-second window wins. Clients discard the losing Commit and
  re-propose. The normative rule is protocol spec §5.1.1. The admission key
  plays no part in Commit ordering.

### 6.3 Policy enforcement points

Policy that requires knowing who someone is (compliance capture, DM rules,
regulated-user status) is enforced at CO enforcement points:

- member clients, especially managed devices the CO issues and controls;
- CO-run MLS members such as the compliance logger;
- the CO's archive and audit pipeline.

The infrastructure is never an enforcement point for such policy.

Clients validate membership changes, deletes and role actions against signed
Space state. A client MUST accept an MLS Welcome only from a sender authorized
to add members under current Space state, and a Welcome MUST NOT replace an
existing group.

### 6.4 TURN shared secret

A CO that uses a TURN server shares one secret with the TURN operator under
their `turn` agreement (protocol spec §6.11). The CO credential service uses it
to issue short-lived credentials to members, and the TURN server uses it to
check them. It authenticates the CO credential service, not a member, and it
gives no access to MLS state, admission keys or content.

## 7. Disposition of conflicts in the imported specs

Each item below is an erratum against the imported documents
(`import/`, see `notes/research-2026-10-16.md` for line references). Section
and line numbers in this list are those of the imported documents, not of
`spec/`. The restructured specification resolves each as stated.

1. **Relay ban and timeout enforcement** (protocol spec §9.5, §11.3, l.2439–2441).
   Removed. Replaced by §6.2: bans are MLS Removes plus an admission key
   rotation, timeouts are client-enforced.
2. **Relay pin-limit and DeleteEvent enforcement** (§6.6, §11.3, l.1536, 1542,
   2962). The relay can't read these instructions, which sit inside ciphertext.
   Replaced by §6.2: storage quotas by agreement, pin semantics client-side.
3. **Compliance hold, Mechanisms A/B** (§17.8.9, l.3878–3911; regulators guide
   l.306–308). Removed from the relay. Enforcement moves to CO enforcement points
   (§6.3). Cost accepted in §9.
4. **channelToken→channel mapping and relay-side JMAP** (§8.8, l.2325, vs
   §11.2). The relay never learns a `channelID` or MLS group ID. The JMAP Space, membership,
   role and invite API runs in the client or on CO infrastructure, not on the
   relay, as nie's daemon does (`notes/nie-backport-inventory.md`). The relay
   offers only token-keyed envelope sync.
5. **Presence and typing events in the clear** (§7, l.1797–1824). Move inside
   MLS application messages.
6. **SFU as an MLS member** (§10.6, l.2594). An SFU holding epoch secrets could
   derive media keys, so it would be a CO component holding plaintext. The SFU
   MUST NOT be an MLS member. It is admitted by a CO-signed entry in Space state,
   and media E2EE keys never reach it.
7. **Relay admin API exposing Space and channel structure** (ops spec
   l.1004–1050). The admin API reports per-token and per-agreement counters
   only, never names, types or member counts.
8. **Relay-hosted compliance logger** (ops spec `operate_logger`, l.502–516). The
   logger is a CO component (S8). The ops spec option is removed. Co-location,
   where used, is a contractual arrangement outside the relay's configuration.
9. **Client–relay DID authentication** (§8.6; ops spec l.2212). An IO that
   authenticates member DIDs knows who its users are, contrary to §11.1. Access
   is by §6.2 admission key and quota is by agreement. Resolved: §8 Q2.
10. **Relay signing community state** (prototype code,
    `~/GIT/Agora-historical/relay/src/ws.rs` ~1068–1117). Forbidden by S4.
11. **Relay access-log retention** (ops spec l.1323, 2437, vs regulators guide
    l.133). Retention is whatever the `ServiceAgreement` sets, declared in
    the manifest (§5 item 1). Both documents are rewritten to say so.

## 8. Decisions and open questions

All resolved 2026-10-16 except the external review in Q1.

- **Q1. Write admission.** Revised 2026-10-16. The CO-issued channel admission
  key (§6.2) replaces the earlier design, in which members derived an epoch
  access key from the MLS exporter, announced each epoch's key on the Commit,
  and the CO registration service countersigned each announcement. Commit
  conflicts are resolved by the sequencer stamp or, without a sequencer, by
  lowest hash (§6.2; protocol spec §5.1.1). Still open: external cryptographic review, which targets
  the new design: the admission key's issuance and rotation, the
  `channelToken` derivation, `admissionSig` over the `signed` bytes, the
  canonical-Commit rule (protocol spec §5.1.1), and cost per envelope.
- **Q2. Admission without identity.** An IO never authenticates client
  identity. Writes need an `admissionSig` (§6.2); registration needs the
  billing key; storage and bandwidth follow agreement quotas. Connections,
  subscriptions and reads are rate-limited by network address and routing
  token, and an IO MAY require proof of work before accepting a connection
  under load.
- **Q3. KeyPackage placement.** KeyPackages live with whoever runs the user's
  identity, found through the DID document's `KeyPackageEndpoint` (or a Pkarr
  record for `did:key`). IOs hold none.
- **Q4. Push.** Push is in the §5 budget by default. Wake-ups carry no content
  and no urgency: relays send every wake-up the same way, and the device
  decides how to notify after it decrypts. A relay serving push learns which
  routing tokens wake the same device (§5 item 7). IOs SHOULD add jitter and
  coalesce wake-ups; a CO MAY run its own push proxy; users MAY disable push.
- **Q5. Discovery.** Every discovery record is signed by the party it describes.
  IOs forward and cache records but never author or modify a Space record.
  Only public Spaces advertise. Users are not advertised: a user is found
  through the DID document or Pkarr record, and recovery is read from the DID
  log. Clients send no DID-signed record over a relay connection; a user who
  changes identity material tells their groups with an MLS application message
  of type `urn:agora:type:IdentityChanged`.
- **Q6. Which Spaces an IO serves.** Resolved 2026-10-16: an IO knows the CO's
  billing DID and the admission keys registered under each agreement, never
  the Space (§5 item 6, §6.1).

## 9. Accepted costs

- **A malicious member client can evade CO policy that the infrastructure used
  to enforce,** for example DM compliance capture. The mitigation is the managed
  endpoint: regulated users communicate from CO-issued devices, and the
  compliance logger records gaps it can detect. This is the same trust boundary
  regulated firms already rely on for every other channel.
- **Timeouts can't be enforced at the infrastructure.** A timed-out member can
  still send ciphertext until removed. Members' clients drop it.
- **Removal reaches the infrastructure only at the next key rotation.** If the
  registration service or Space endpoint is down, the last registered
  admission key keeps working, and a removed member can post junk ciphertext
  until the CO rotates the key. It cannot read: the MLS Remove already cut it
  off. Members' clients drop what it sends.
- **One unauthorized Commit can force a channel's group to be re-created.**
  Authorization is checked after the winning Commit is chosen, so a channel
  member whose valid but unauthorized Commit wins makes every member leave
  the group; an admin re-creates it and can then remove the sender, whom its
  MLS signature identifies (protocol spec §4.5, §5.1.1).
- **Some infrastructure-level abuse controls get coarser.** Without identity, an
  IO rate-limits by routing token, agreement and network address.
- **Space anonymity at the IO is only as large as the CO.** A CO with one Space
  gets none. The same holds for an identity host acting as the CO for DM
  groups and self-groups (protocol spec §10.5.3): their anonymity set at the
  IO is that host's users, and a host that serves one user gives none, since
  its agreements then stand for that user. An IO can also correlate
  registration timing with a newly advertised public Space, can link
  successive admission keys of one channel through the token a registration
  replaces, and can cluster routing tokens that the same network address
  subscribes to. It cannot name such a cluster without outside information.
- **An IO can infer removals.** After a rotation, an IO can see which
  subscribers do not move to the new key's token, and so can infer that a
  removal occurred and which connection or push handle it affected. It does
  not learn who was removed.
- **Public broadcast channels are mapped to their Space.** A `keyAccess:
  public` broadcast channel exists only in a public Space, and the CO
  publishes its token with that Space (protocol spec §3.4). An IO can
  therefore map that token, and the billing DID it is registered under, to the
  named Space. This ties the CO's billing DID to a Space that already
  advertises itself and its relays, and lets push and address clustering tie
  the followers' other tokens under that CO to a known community. The
  Space's public view also names every DID that may post to such a channel.
  Privacy claims about tokens elsewhere in this document and the protocol spec exclude
  these published tokens.
- **Push links a device's channels at its relay.** A relay serving push holds
  each `pushHandle` with its registered routing tokens, so it can cluster
  those tokens as one device across sessions and network addresses. It learns
  no DID and no channel identity. Users who do not accept this disable push.
  A user's self-group token is followed only by that user's devices, so a
  relay that carries it can link those devices, their addresses and their
  push handles even across networks; a user who does not accept this can
  have the self-group served from a relay that carries none of their other
  channels. A Space that publishes its relay list has disclosed that it uses
  those relays, by choice. Under legal demand an IO can produce which network
  addresses used a given CO's service, not which Space, channel or sender.

- **Public content on the public IPFS network cannot be withdrawn.** Public
  Space records and the envelopes and blobs of public broadcast channels MAY
  be published to the public IPFS network (protocol spec §10.4.4). Once
  announced there, copies outlive any deletion or takedown by the CO, and DHT
  participants and the peers that serve those CIDs see the network addresses
  that request them. Private ciphertext is never announced or requested
  there, so this applies only to content its CO already made public.

- **An SFU sees stable sender pseudonyms and MLS epoch changes.** The SFrame
  KID (§5 item 9) is fixed by RFC 9605. An SFU can tell a group's senders
  apart across calls and see when its MLS epoch changes, without learning any
  DID.

- **A party that runs both a social or identity service and relays can link
  its own users to the COs whose traffic they use.** For Spaces it never
  learns content, channel or Space. For a DM group whose admission host it
  runs (protocol spec §4.6), it knows its own user's DID and the group's ID,
  not the other members, and if the group's relays are its own, it also sees
  that group's traffic: it then knows which token is its user's DM and when it
  is used, though never its content. A DM
  admission host SHOULD list relays it does not operate. Users and
  communities can choose relays run by someone else (§2.4;
  profiles/corundum.md).

## 10. Review test

Every section of the specification MUST be able to answer:

1. Which operator does this bind: IO, CO, or both?
2. Does any IO behavior here require S1-protected knowledge?
3. Does any IO behavior here make a community decision (S2)?
4. Could the CO replace every IO after this operation without loss (S5)?
5. Does anything here enlarge the §5 observation budget? If so, is it opt-in,
   declared and visible (S6)?
6. Does anything here keep group membership or epoch order outside MLS (S9)?
