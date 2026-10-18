# Agora: What It Is and Why to Fund It

*2026-10-17*

Fund Agora's move from a feature-complete draft specification to working, audited,
interoperable software. Agora is an open protocol for group messaging and
calls. The companies that run its servers cannot read, censor, or control the
conversations, while organizations keep the policy, compliance, and identity
control they need. The specification is feature-complete in draft and has been
through four internal review rounds. External cryptographic review is still to
come. Funding pays for:

- two independent reference implementations;
- an external cryptographic audit;
- interoperability testing;
- pilot deployments.

Open question: the amount and term of the ask, to be set once the
implementation plan is costed.

## What Agora is

Agora separates running the servers from running the conversations. Today one
company does both. Whoever carries your messages also decides who may speak,
holds your keys, and can be compelled to hand over your data.

Agora splits that into two roles:

- **Infrastructure operators** run relays, media servers, and connection
  helpers. They move encrypted traffic and sell capacity under contract. They
  learn as little as possible: not who is in a group, not what a group is
  called (except channels a community chooses to make public), and never the
  content.
- **Communications operators** run the communities: a company, a school, a
  union, an open-source project. They set membership and policy, hold
  identity, and run compliance archiving where the law requires it.

Either role can be replaced without the other noticing. A community can move
to new servers without losing members or history. A server operator
carrying a community's traffic learns its communications operator's billing
identity, but not its members, its channels, or what is said.

Agora covers:

- community spaces with channels and roles;
- direct messages;
- voice and video calls;
- file sharing;
- regulated compliance capture.

It is built on published standards:

- MLS (RFC 9420) for end-to-end group encryption;
- decentralized identifiers for identity;
- WebRTC for calls;
- JMAP data formats for messages.

## The problem

Every widely used option forces a trade between control, privacy, and
compliance.

| Option | Who controls the conversation | Who can read it | Compliance fit | Can you leave? |
| --- | --- | --- | --- | --- |
| Slack, Teams | The vendor | The vendor and the customer admin | Strong | Hard: data and identity sit with the vendor |
| Signal, WhatsApp | The vendor | Only participants | Weak: regulated firms cannot archive it | No: one network, one operator |
| Matrix | Each homeserver | Participants, with metadata exposed to servers | Partial | Yes, but servers see who talks to whom |
| Discord | The vendor | The vendor | Weak | No |
| Agora | The communications operator | Only participants and disclosed compliance archivers | Built in, without weakening encryption for others | Yes: replace any server or operator |

The gap shows up as real cost:

- Regulators have fined financial firms heavily for staff using personal
  messaging apps that the firm cannot archive.
- Communities that grow on Discord or Slack cannot take their members and
  history elsewhere.
- Organizations that want end-to-end encryption give up policy control, and
  those that keep policy control give up encryption.

## How Agora solves it

Agora keeps every decision about a community with its operator, and gives the
servers nothing to decide with.

- **Blind relays.** Relays route encrypted envelopes by an opaque token. They
  never learn a group's members or content, or its name unless the community
  makes the channel public. A relay served with a subpoena can produce
  connection metadata, routing tokens, and ciphertext, but not who is in a
  community or what they said.
- **Door keys instead of member lists.** A communications operator issues each
  channel an admission key and registers only its public half with the relays.
  Relays admit traffic signed with it and know nothing else. Removing a member
  rotates the key.
- **End-to-end encryption by MLS.** Every channel, DM, and call encryption key
  derived from MLS lives only on members' devices. No infrastructure operator
  holds any. MLS gives forward secrecy and recovery after a device
  compromise, and scales to large groups.
- **Portable identity.** Users are identified by decentralized identifiers,
  employer-issued or self-held. No messaging vendor owns a user's identity.
- **Compliance without a backdoor.** In regulated communities, a disclosed
  compliance logger joins the group as a member. Members are told of it through
  a retention notice and the Space settings, and any member's client can verify
  it is in the group. It archives what it is entitled to. No other party gets
  access.
- **Replaceable everything.** Operators and servers are bound only by published
  contracts and verification keys, so any one can be swapped without changing
  the community.

## Who it is for

| Who | What they get that they cannot get today |
| --- | --- |
| Regulated firms (finance, healthcare, legal) | End-to-end encrypted chat that still meets record-keeping rules, including DMs with outside parties |
| Enterprises | Employee identity from their own directory (Microsoft Entra, Google Workspace, any identity provider), with no lock-in to one vendor's servers |
| Communities and open-source projects | A home they can move between hosts, with members, roles, and history intact |
| Public sector and NGOs | Infrastructure they can buy from any provider, including in-country, without that provider seeing content or membership |
| Hosting and network providers | A new market: selling relay and media capacity under contract to many communities |

The specification already includes deployment profiles for:

- Microsoft 365 identity;
- Google Workspace identity;
- Microsoft Purview compliance archiving;
- Discord community migration;
- radio-mesh gateways for disconnected field use.

## Why now

The building blocks became standards only recently, and the pressure to use
them is rising.

- **Group encryption is standardized.** MLS was published as RFC 9420 in 2023.
  Before it, end-to-end encryption for large groups meant each vendor's own
  design.
- **Interoperability is becoming law.** The EU Digital Markets Act requires the
  largest messengers to open up to others. The IETF MIMI working group is
  building the cross-provider standard on MLS. Agora is MLS-native, so it can
  join that ecosystem rather than bolt onto it.
- **Regulators are enforcing record-keeping on chat.** US regulators have fined
  financial firms well over a billion dollars in total (approximate) for
  business conversations on unarchived messaging apps. Firms need encrypted
  chat they can archive.
- **Decentralized identity is usable.** Employer-issued and self-held
  identifiers, and verifiable credentials, now have published standards and
  production tooling.
- **EU identity wallets arrive in December 2026.** Every EU state must offer
  its residents a digital identity wallet. Agora's attribute-bridging profile
  lets a community admit members on derived claims from attesters it lists in
  its Space state (`trustedAttesters`, spec §3.3). The communications operator
  may run its own attester or list a third party. Attesters check EU wallets,
  US CAC and PIV smartcards, and enterprise directories. Other members see only
  the claims a member chooses to show, and infrastructure operators see
  nothing.
- **Trust in single-vendor platforms is low.** Communities have watched
  platforms change terms, prices, and moderation rules overnight, and want a
  home they can leave.

## Works with OpenVTC and the Decentralized Trust Graph

Agora is designed to work with OpenVTC, the open-source implementation of the
Decentralized Trust Graph credential stack, through a deployment profile with
no change to the core protocol. The profile defines four connections, all on
the specification as written:

- **Strangers in DMs.** A client can show who sent a message request from the
  sender's trust-graph credentials, checked against a public trust registry.
- **Credential-gated Spaces.** A Space can admit members on a trust
  community's admission decision.
- **Shared identities.** Both use the same default decentralized identifier
  method, so identities work on both sides unchanged.
- **Personal agents.** A user's always-on trust agent runs as one of the
  user's own devices.

OpenVTC has no calls. Agora's call design is ready for the trust-graph work
to adopt rather than reinvent.

## Where it stands

The protocol specification is feature-complete in draft. What does not exist
yet is production software or external review.

| Piece | Status |
| --- | --- |
| Architecture | 9 normative rules for keeping operators separate, with an accepted-costs register and a review test every section must pass |
| Protocol specification | 14 parts plus appendices: identity, spaces, access control, messaging, calls, compliance, cross-community channels, interoperability, relays, transport, security, encoding, data formats |
| Internal review | 4 full review rounds covering consistency, operator separation, cryptography, and implementability, with every finding fixed or decided |
| Test vectors | 11 vector files; every value computed by two independent cryptographic implementations that agree |
| Deployment profiles | 12, including Microsoft 365, Google Workspace, Microsoft Purview, Discord migration, and radio-mesh gateways |
| Operator guides | 3: relay operators, financial regulators, legal counsel |
| Implementation | An earlier prototype codebase exists; no implementation of the current specification yet |

Two items were deliberately left for the implementation phase:

- test vectors that need a working MLS stack or a second HPKE implementation;
- an external cryptographic review of the admission-key design.

## What funding buys

Funding buys four phases. Each ends at a gate that must be passed before the
next begins.

| Phase | Work | Gate to the next phase |
| --- | --- | --- |
| 1. Build | Two independent implementations; interoperability test suite; MLS and HPKE test vectors | Interop suite passes |
| 2. Audit | External cryptographic audit; compliance review; fix all findings | Audit closed |
| 3. Pilot | Two independent relay operators; pilot communities, including one regulated firm; one community moves hosts; an OpenVTC interop demonstration | Daily use by pilots |
| 4. Standardize | Stable 1.0 specification; standards submission; native MIMI interoperability path | (end of funded period) |

The phases do the following:

- **Build** produces two independent implementations of the client, relay, and
  community-operator services. Separate teams write them from the
  specification alone, so that every ambiguity surfaces.
- **Audit** puts the cryptography and the compliance design in front of
  outside experts.
- **Pilot** puts real communities on real, independently run infrastructure.
- **Standardize** freezes a stable 1.0 and prepares it for a standards body.

Open question: duration and cost per phase.

## Risks and how they are handled

| Risk | Handling |
| --- | --- |
| A flaw in the new admission-key design | External cryptographic audit before any production release; the design reuses MLS and standard signatures rather than new primitives |
| Two implementations read the spec differently | Fund two independent implementations and a shared interoperability test suite; shared test vectors already exist |
| Network effect: users stay where their contacts are | Start with communities that need what incumbents lack, such as regulated firms and communities leaving a platform; bridge to existing networks through gateways |
| No one runs the infrastructure | The operator split creates a hosting market; pilots seed it with at least two independent relay operators |
| Standards move under us (MIMI, DMA rules) | Agora is MLS-native and keeps native MIMI interoperability as a documented next step rather than a rewrite |
| A modified client evades DM capture | Capture of DMs relies on firm-managed devices, the same boundary regulated firms already rely on; the logger records every capture gap it can detect |
| Compliance claims are not accepted by examiners | Independent compliance review of the archiving design in the pilot phase; the regulators guide is written for examiners |

## Why fund it now

The hardest and cheapest part is done. The design is feature-complete and
internally reviewed, so funding goes straight to building rather than to
research. Every month without
encrypted, portable, compliant group messaging costs something:

- regulated firms keep paying fines;
- communities keep losing their homes;
- the interoperability standards take shape without an operator-separated
  design at the table.

Success at the end of the funded period looks like this:

- Two independent implementations pass a shared interoperability suite.
- An external cryptographic audit is complete, with findings fixed.
- At least two independent relay operators carry real traffic.
- Pilot communities, including at least one regulated firm, run on Agora
  daily, and one has moved hosts without losing members or history.
- The specification is published as a stable 1.0, ready for standards
  submission.
