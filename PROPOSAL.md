# Agora: A Proposal

Agora is an open protocol for end-to-end encrypted group communication in which
**operating the infrastructure is separate from operating the communications.**
We are asking for cryptographic review of one new mechanism, review by
compliance practitioners, and implementers for a reference relay and client.

## The problem

Every deployed group-messaging system gives the party that runs the servers
authority over the communities on them. Centralized platforms hold keys,
membership, and policy. Federated platforms spread the servers around, but each
server still sees and governs the communities it hosts. An organization that
wants someone else to run its infrastructure must therefore also trust that
party with its members, its metadata, and, often, its plaintext. Regulated firms
cannot accept that, and most others should not.

## The proposal

Agora defines two roles. Distinct principals with distinct keys hold them, even
when one company plays both:

- **Infrastructure Operators (IOs)** run relays, Selective Forwarding Units
  (SFUs), TURN, sequencers, and push proxies. They carry ciphertext, verify that
  traffic comes from some current member without learning which, enforce agreed
  quotas, and decide nothing else.
- **Communications Operators (COs)** run communities: identity, membership,
  roles, moderation, retention, compliance logging, and archives, all exercised
  with their own keys.

The only binding between them is a `ServiceAgreement`. It names no community.
The CO signs it with its billing DID, which appears in no community's state. A
CO can replace any IO without changing a community's identity, membership, or
history, and without re-enrolling anyone.

The normative statement is `ARCHITECTURE.md`: nine rules (S1–S9), a closed list
of what infrastructure may observe, and the review test every part of the
specification must pass.

## What the protocol guarantees

- A relay does not know who is in any group or who sent any message, and the
  protocol does not tell it which channel or Space a routing token belongs to.
  It learns which customer's service a network address used. A customer with
  one Space gets no cover, and timing and address clustering can link tokens
  (ARCHITECTURE §9).
- Community state is signed only by the community's CO. Clients reject state
  signed by infrastructure keys.
- Bans are MLS removals followed by rotation of the channel's admission key.
  The CO enforces policy that needs identity at its own endpoints: managed
  devices, the compliance logger, and the archive.
- Relays store only ciphertext or records the CO chose to publish.

What it does not guarantee: anonymity at the network layer, or compliance capture from a
tampered client. Both are stated as accepted costs.

## What is specified

| Part | Content |
|---|---|
| `spec/01`–`04` | Overview, identity (DIDs, recovery, employer provisioning), Spaces and state distribution, access control |
| `spec/05`–`06` | MLS messaging, channel admission, encrypted broadcast, voice and video |
| `spec/07`–`09` | Compliance logging, cross-Space channels, gateways |
| `spec/10`–`13` | Relays and federation, transport, security considerations, encoding and signing |
| `spec/14` | JMAP-family data on Agora: replicated stores, the blind sequencer, the Agora profile of each JMAP draft |
| `profiles/` | Non-normative deployment designs: Entra, Google Workspace, generic identity provider (IdP), Purview, Discord onboarding, compliance chain witnessing, CORUNDUM, Parlance, radio mesh gateway, gateways (Matrix, Slack, Teams; native More Instant Messaging Interoperability (MIMI) as a future option) |
| `guides/` | Relay operator, regulator, and counsel guides |

Built on MLS (RFC 9420), HPKE (RFC 9180), SFrame (RFC 9605), JMAP (RFC 8620),
JWS (RFC 7515, RFC 7797, RFC 8037), DIDs, and content addressing.

## Status

Draft specification, revision in progress. No conformant implementation. No
payments or cryptocurrency in the first release.

Design decisions made in this revision:

- **Channel admission (`spec/05` §5.2.2).** The CO issues each channel a random
  admission key. It registers the public half with the relays it has agreements
  with and serves the private half only to current members. Relays admit
  envelopes signed with the key without learning which member signed. The CO
  rotates the key when it removes a member, so a removed member's envelopes
  stop being admitted once the new key is registered. In a direct message (DM)
  group, a member's identity host (at first the initiator's) plays the CO's
  part for the key alone. It issues the key only to its own user, whose client
  puts it in the group's MLS state, and the host registers the key under its
  own agreements. A host that serves one user gives that user no anonymity at the
  relay. Channel admission is new design and the one item still awaiting
  external review.
- **No identity at relays.** Relays rate-limit connections by network address
  and routing token, with proof of work under load. There is no login.
- **KeyPackages.** KeyPackages live with whoever runs the user's identity,
  never on relays.
- **Identity.** `did:webvh` by default; `did:plc` for people who want to reuse
  a Bluesky identity; `did:key` for people who hold their own keys and accept
  that their backup is their only recovery. Communities may restrict which
  methods they accept.
- **Push.** Push is on by default. Wake-ups carry no content and no urgency,
  and relays jitter them. A relay serving push learns which routing tokens wake
  the same device. Users who do not accept that turn push off.
- **Discovery.** Discovery records are signed only by the party they describe.

## What we are asking for

1. **Cryptographic review of channel admission**, covering admission key
   issuance and rotation, the routing token derivation, the admission signature
   over the envelope, the canonical-Commit rule, and cost per envelope. The
   separation rests on this mechanism, and nothing should be implemented before
   it is reviewed.
2. **Compliance review** of capture, retention, and disclosure (`spec/07`,
   `profiles/purview-bridge.md`) by counsel and an auditor familiar with SEC
   17a-4, FINRA, and MiFID II.
3. **Implementers** for a reference relay and client, to find what the text
   gets wrong.
4. **MIMI participants'** view on the path to native MIMI interop, a future
   option described in `profiles/gateways.md`.

The longer case, including customers and risks, is in `PRFAQ.md`.
