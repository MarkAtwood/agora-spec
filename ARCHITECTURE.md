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
| Sequencer | IO | Stamps order on encrypted operations; members' clients validate them (protocol spec §14.4) |
| Push proxy | IO | Observation budget includes device push handles (§5); a CO MAY run its own |
| SFU | IO | MUST NOT be an MLS member (§7, item 6) |
| KeyPackage host | CO | Run by whoever runs the user's identity (§8, Q3) |
| Compliance logger | CO | MLS member; holds plaintext |
| Archive / Purview bridge | CO | Holds plaintext |
| IdP / DID sidecar, enrollment service | CO | Holds or controls identity keys |
| Gateways (Matrix, Slack, Teams) | CO | Break E2EE by design |
| MIMI provider endpoint | CO | Knows room membership |
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
MLS group secrets, epoch secrets, exporter outputs other than those
specifically derived for IO verification (§6.2), user signing keys, or
plaintext.

**S4. Community state is CO-signed.** Space state, channel state, role
assignments, moderation records and retention policy MUST be signed by CO keys.
An IO key MUST NOT sign community state, and clients MUST reject community
state signed by an IO key.

**S5. Replaceability.** A CO MUST be able to add, remove or replace any IO
without changing Space identity (genesis CID), member identities, MLS group
state or history, and without re-enrolling any member. History survives an IO
departure if at least one remaining IO or the CO holds its CIDs.

**S6. Bounded observation.** An IO component MUST NOT observe, log or retain
anything outside the observation budget in §5. Any extension that enlarges the
budget MUST be opt-in by the CO, MUST be declared in the relay manifest, and
MUST be visible to members.

**S7. Contracts, not configuration.** The only binding between a CO and an IO is
the `RelayServiceAgreement` (protocol spec §10.5.1) and the verification material
defined in §6. An IO MUST NOT require CO data beyond these as a condition of
service.

**S8. Plaintext stays on CO infrastructure.** Any component that produces or
stores plaintext (compliance logger, archive, bridges, gateways) MUST run under
CO control. Co-location on IO hardware is permitted only under contract with the
IO acting as the CO's processor, and the component remains a CO principal with
its own DID and keys.

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
   Retention is set by the `RelayServiceAgreement` and MUST be declared in the
   relay manifest.
2. Ciphertext envelopes: size, timing, routing token (`channelToken`), and
   expiry hint.
3. Verification material and proofs defined in §6, which by construction do not
   reveal which member produced them.
4. Content identifiers (CIDs) it stores or pins, and pin/unpin instructions
   authorized under §6.
5. Quota state under a `RelayServiceAgreement`, keyed to the agreement and
   never to member identity. Commercial terms between CO and IO are outside the
   protocol.
6. The billing DID of each CO it holds an agreement with, and which access-key
   chains (§6.2) are registered under each agreement. An IO MUST NOT be able to
   map a chain to a Space or channel: the set of Spaces it cannot tell apart is
   every Space that CO serves through it.
7. For push proxies only: opaque device push handles and wake-up timing.
8. Its own peering relationships with other IOs.

Agora does not claim network-layer anonymity against an IO. Members who need it
use an overlay transport (protocol spec §10.1, §11). This matches the privacy
whitepaper: "Agora is not anonymous."

## 6. The CO–IO interface

### 6.1 Space state and the RelayServiceAgreement

The CO publishes signed Space state (S4). It engages IOs by
`RelayServiceAgreement`, which fixes retention, quotas and observation-budget
declarations. Commercial terms are out of band. Enforcement is by selection: a
CO that is unhappy with an IO replaces it (S5).

An agreement identifies the CO only by a **billing DID**: a key dedicated to
agreements that MUST NOT appear in Space state or any other Space-identifying
record. An agreement names no Space and no channel. Coverage is expressed by
registering access-key chains (§6.2) under the agreement, through a CO-run
registration service, so that members can create groups without holding the
billing key. Agreements are private between the two parties and are not
gossiped or published.

An IO therefore learns which CO a chain belongs to, never which of that CO's
Spaces. A CO that operates many Spaces through the same IO gives each
of them a correspondingly large anonymity set.

### 6.2 Access control by MLS membership

Membership in the MLS group is the only access control. An IO verifies that an
envelope comes from a current member without learning which member.

*Mechanism (protocol spec §5.2.2), pending external cryptographic review:* each
epoch, members derive a shared signing key pair from the MLS exporter
(label `"agora access"`). The committer publishes the epoch's public key with
the commit, signed by the previous epoch's access key and countersigned by the
CO's registration service, so the IO can follow the chain. The countersignature
is required because a member being removed also holds the previous epoch's key
and could otherwise announce a key of its own. Envelopes carry a signature under
the current epoch access key. The IO rejects envelopes that fail verification.

Consequences:

- **Bans and removals are MLS Removes.** A removed member does not hold the next
  epoch's access key. Relays do not keep DID ban lists.
- **Timeouts and mutes are client-enforced.** Members' clients drop messages
  from a timed-out member. An IO cannot enforce a timeout without learning the
  sender, so it does not try.
- **Pin and delete instructions** are authorized by the same proof, plus a
  CO-signed role check that clients, not IOs, perform. An IO enforces storage
  quotas by agreement, not pin semantics by content.

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

## 7. Disposition of conflicts in the imported specs

Each item below is an erratum against the imported documents
(`import/`, see `notes/research-2026-10-16.md` for line references). Section
and line numbers in this list are those of the imported documents, not of
`spec/`. The restructured specification resolves each as stated.

1. **Relay ban and timeout enforcement** (protocol spec §9.5, §11.3, l.2439–2441).
   Removed. Replaced by §6.2: bans are MLS Removes, timeouts are client-enforced.
2. **Relay pin-limit and DeleteEvent enforcement** (§6.6, §11.3, l.1536, 1542,
   2962). The relay can't read these instructions, which sit inside ciphertext.
   Replaced by §6.2: storage quotas by agreement, pin semantics client-side.
3. **Compliance hold, Mechanisms A/B** (§17.8.9, l.3878–3911; regulators guide
   l.306–308). Removed from the relay. Enforcement moves to CO enforcement points
   (§6.3). Cost accepted in §9.
4. **channelToken→channelCid mapping and relay-side JMAP** (§8.8, l.2325, vs
   §11.2). The relay never learns channel CIDs. The JMAP Space, membership,
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
   is by §6.2 proof and quota is by agreement. Open question Q2.
10. **Relay signing community state** (prototype code,
    `~/GIT/Agora-historical/relay/src/ws.rs` ~1068–1117). Forbidden by S4.
11. **Relay access-log retention** (ops spec l.1323, 2437, vs regulators guide
    l.133). Retention is whatever the `RelayServiceAgreement` sets, declared in
    the manifest (§5 item 1). Both documents are rewritten to say so.

## 8. Decisions and open questions

All resolved 2026-10-16 except the external review in Q1.

- **Q1. Epoch access key.** Announcements are countersigned by the CO
  registration service (§6.2). Still open: external cryptographic review of
  exporter use, commit ordering across relays, and cost per envelope.
- **Q2. Admission without identity.** An IO never authenticates client
  identity. Writes need the §6.2 proof; registration needs the billing key;
  storage and bandwidth follow agreement quotas. Connections, subscriptions and
  reads are rate-limited by network address and routing token, and an IO MAY
  require proof of work before accepting a connection under load.
- **Q3. KeyPackage placement.** KeyPackages live with whoever runs the user's
  identity, found through the DID document's `KeyPackageEndpoint` (or a Pkarr
  record for `did:key`). IOs hold none.
- **Q4. Push.** Push is in the §5 budget by default. Wake-ups carry no content;
  IOs SHOULD add jitter and coalesce wake-ups; a CO MAY run its own push proxy;
  users MAY disable push.
- **Q5. Discovery.** Every discovery record is signed by the party it describes.
  IOs forward and cache records but never author or modify a Space or user
  record. Only public Spaces advertise.
- **Q6. Which Spaces an IO serves.** Resolved 2026-10-16: an IO knows the CO's
  billing DID and the chains registered under each agreement, never the Space
  (§5 item 6, §6.1).

## 9. Accepted costs

- **A malicious member client can evade CO policy that the infrastructure used
  to enforce,** for example DM compliance capture. The mitigation is the managed
  endpoint: regulated users communicate from CO-issued devices, and the
  compliance logger records gaps it can detect. This is the same trust boundary
  regulated firms already rely on for every other channel.
- **Timeouts can't be enforced at the infrastructure.** A timed-out member can
  still send ciphertext until removed. Members' clients drop it.
- **Some infrastructure-level abuse controls get coarser.** Without identity, an
  IO rate-limits by routing token, agreement and network address.
- **Space anonymity at the IO is only as large as the CO.** A CO with one Space
  gets none. An IO can also correlate registration timing with a newly
  advertised public Space, and can cluster chains that the same network
  address subscribes to. It cannot name such a cluster without outside
  information. A Space that publishes its relay list has disclosed that it uses
  those relays, by choice. Under legal demand an IO can produce which network
  addresses used a given CO's service, not which Space, channel or sender.

## 10. Review test

Every section of the specification MUST be able to answer:

1. Which operator does this bind: IO, CO, or both?
2. Does any IO behavior here require S1-protected knowledge?
3. Does any IO behavior here make a community decision (S2)?
4. Could the CO replace every IO after this operation without loss (S5)?
5. Does anything here enlarge the §5 observation budget? If so, is it opt-in,
   declared and visible (S6)?
