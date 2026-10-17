# Agora: A Proposal

Agora is an open protocol for end-to-end encrypted group communication in which
**operating the infrastructure is separate from operating the communications.**
We are asking for cryptographic review of one new mechanism, review by
compliance practitioners, and implementers for a reference relay and client.

## The problem

Every deployed group-messaging system gives the party that runs the servers
authority over the communities on them. Centralized platforms hold keys,
membership and policy. Federated platforms spread the servers around, but each
server still sees and governs the communities it hosts. An organization that
wants someone else to run its infrastructure must therefore also trust that
party with its members, its metadata and, often, its plaintext. Regulated firms
cannot accept that, and most others should not.

## The proposal

Two roles, held by distinct principals with distinct keys even when one company
plays both:

- **Infrastructure operators** run relays, SFUs, TURN and push proxies. They
  carry ciphertext, verify that traffic comes from some current member without
  learning which, enforce agreed quotas, and decide nothing else.
- **Communications operators** run communities: identity, membership, roles,
  moderation, retention, compliance logging and archives, all exercised with
  their own keys.

The only binding between them is a `RelayServiceAgreement` signed by the
communications operator's billing key, which names no community. A
communications operator can replace any infrastructure operator without
changing a community's identity, membership or history, and without
re-enrolling anyone.

The normative statement is `ARCHITECTURE.md`: eight rules (S1–S8), a closed list
of what infrastructure may observe, and the review test every part of the
specification must pass.

## What the protocol guarantees

- A relay does not know who is in any group, who sent any message, or which
  channel or Space a routing token belongs to. It learns which customer's
  service a network address used.
- Community state is signed only by the community's operator. Clients reject
  state signed by infrastructure keys.
- Bans are MLS removals. Policy that needs identity is enforced at the
  communications operator's own endpoints: managed devices, the compliance
  logger, the archive.
- Relays store only ciphertext or records the communications operator chose to
  publish.

What it does not guarantee: anonymity at the network layer, or capture from a
tampered client. Both are stated as accepted costs.

## What is specified

| Part | Content |
|---|---|
| `spec/01`–`04` | Overview, identity (DIDs, recovery, employer provisioning), Spaces and state distribution, access control |
| `spec/05`–`06` | MLS messaging, epoch access proof, encrypted broadcast, voice and video |
| `spec/07`–`09` | Compliance logging, cross-Space channels, MIMI and gateways |
| `spec/10`–`13` | Relays and federation, transport, security considerations, encoding and signing |
| `spec/14` | JMAP-family data on Agora: replicated stores, the blind sequencer, the Agora profile of each JMAP draft |
| `profiles/` | Non-normative deployment designs: Entra, Google Workspace, generic IdP, Purview, Discord onboarding |
| `guides/` | Relay operator, regulator and counsel guides (pending revision) |

Built on MLS (RFC 9420), HPKE (RFC 9180), SFrame (RFC 9605), JMAP (RFC 8620),
JWS (RFC 7515, RFC 7797, RFC 8037), DIDs, and content addressing.

## Status

Draft specification, revision in progress. No conformant implementation. No
payments or cryptocurrency in the first release.

Design decisions made in this revision:

- **Epoch access proof** (`spec/05` §5.2.2). Members derive a shared signing
  key per epoch from the MLS exporter, so a relay can admit current members
  without identifying them. Each new epoch key is countersigned by the
  communications operator, so a member being removed cannot hijack the chain.
  This is new design and the one item still awaiting external review.
- **No identity at relays.** Relays rate-limit connections by network address
  and routing token, with proof of work under load. There is no login.
- **KeyPackages live with whoever runs the user's identity**, never on relays.
- **Identity.** `did:webvh` by default; `did:plc` for people who want to reuse
  a Bluesky identity; `did:key` for people who hold their own keys and accept
  that their backup is their only recovery. Communities may restrict which
  methods they accept.
- **Push** is on by default with content-free, jittered wake-ups.
- **Discovery** records are signed only by the party they describe.

## What we are asking for

1. **Cryptographic review of the epoch access proof**, against MLS's security
   properties: exporter use, removal races, commit ordering across relays. This
   is the mechanism the separation rests on; nothing should be implemented
   before it is reviewed.
2. **Compliance review** of capture, retention and disclosure (`spec/07`,
   `profiles/purview-bridge.md`) by counsel and an auditor familiar with SEC
   17a-4, FINRA and MiFID II.
3. **Implementers** for a reference relay and client, to find what the text gets
   wrong.
4. **MIMI participants'** view on aligning content formats and delivery with
   `spec/09`.

The longer case, including customers and risks, is in `PRFAQ.md`.
