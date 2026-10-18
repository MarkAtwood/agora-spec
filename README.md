# Agora

A federated, end-to-end encrypted group communication protocol in which
**operating the infrastructure is separate from operating the communications.**
Relays carry ciphertext and decide nothing; the community or organization that
owns a Space holds every authority over it.

Agora carries typed data of any kind, including JSON-LD. The JMAP family of
specifications (chat, calendars, tasks, files, scenes, calls) is carried as
first-class payloads.

Status: draft specification. No conformant implementation exists.

## Start here

| If you want to... | Read |
|---|---|
| Understand what Agora is and why it matters, in 10 minutes | [FUNDING.md](FUNDING.md) |
| See the customer view: press release and hard questions | [PRFAQ.md](PRFAQ.md) |
| See what is proposed, what is open, and what is asked for | [PROPOSAL.md](PROPOSAL.md) |
| Learn the design rules everything else must obey | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Implement Agora | [ARCHITECTURE.md](ARCHITECTURE.md), then the [specification](#specification) in order, then the [test vectors](test-vectors/README.md) |
| Run a relay | [Relay operations guide](guides/relay-operator.md) |
| Examine Agora as a financial regulator | [Examiner's reference guide](guides/regulators.md) |
| Advise on legal and compliance questions | [Compliance and legal reference guide](guides/counsel.md) |
| Deploy Agora with an existing identity system or network | [Deployment profiles](#deployment-profiles) |

## Architecture

[ARCHITECTURE.md](ARCHITECTURE.md) defines the two operator roles, the rules
S1 to S9 that keep them separate, what each party may observe, and the costs
the design accepts. It governs the specification on any conflict.

## Specification

Normative. Each part states which operator it binds.

| Part | Covers |
|---|---|
| [1. Overview](spec/01-overview.md) | Version policy, design principles, requirements language, and conformance classes |
| [2. Identity](spec/02-identity.md) | DIDs, device keys, provisioning, and recovery |
| [3. Spaces and Space State](spec/03-spaces.md) | Spaces, channels, signed Space state, and lifecycle |
| [4. Access Control and Moderation](spec/04-access-control.md) | Owners, admins, guardians, invites, roles, direct messages, and moderation |
| [5. Messaging](spec/05-messaging.md) | MLS groups, commit ordering, message format, and credentials in leaves |
| [6. Voice and Video](spec/06-calls.md) | Calls over WebRTC with MLS-derived keys |
| [7. Compliance Logging](spec/07-compliance.md) | Disclosed compliance capture for regulated communities |
| [8. Cross-Space Channel Sharing](spec/08-cross-space.md) | Channels shared between Spaces of different operators |
| [9. Interoperability](spec/09-interop.md) | Gateways and other networks |
| [10. Relays, Federation, and Discovery](spec/10-relays.md) | Relays, admission keys, service agreements, and the peer API |
| [11. Transport](spec/11-transport.md) | Connections, the live protocol, and push |
| [12. Security Considerations](spec/12-security.md) | Threats, clocks, privacy, and accepted limits |
| [13. Encoding and Extensions](spec/13-encoding.md) | Signing, encoding, and extension points |
| [14. JMAP-Family Data on Agora](spec/14-jmap.md) | Carrying JMAP data types, files, and history |
| [Appendices](spec/99-appendices.md) | Dependencies, open questions, limits, and registries |

## Deployment profiles

Non-normative. A profile shows how to deploy Agora in a setting; it adds no
protocol rules.

| Profile | For |
|---|---|
| [Employer-managed DIDs: Microsoft Entra ID](profiles/o365-employer-did.md) | Organizations on Microsoft 365 |
| [Employer-managed DIDs: Google Workspace](profiles/gsuite-employer-did.md) | Organizations on Google Workspace |
| [Employer-managed DIDs: any identity provider](profiles/universal-idp-did.md) | Organizations on Okta, Ping, AD FS, Shibboleth, on-premises Active Directory, or any SCIM directory |
| [Attribute bridging](profiles/attribute-bridging.md) | Verifying members against directories, IdPs, CAC/PIV smartcards, and the EU Digital Identity Wallet through listed attesters |
| [In-person verification](profiles/in-person-verification.md) | Two people confirming each other's identity face to face |
| [OpenVTC and the Decentralized Trust Graph](profiles/dtg-openvtc.md) | Working with OpenVTC trust communities and credentials |
| [Microsoft Purview bridge](profiles/purview-bridge.md) | Ingesting compliance records into Exchange Online for Purview review, eDiscovery, and retention |
| [Compliance chain witnessing](profiles/compliance-chain-witness.md) | Publishing compliance-log chain heads to independent witnesses so examiners can check them |
| [Gateways to other networks](profiles/gateways.md) | A Matrix gateway, Slack and Teams placeholders, and the path to native MIMI |
| [Discord onboarding](profiles/discord-onboarding.md) | Moving a Discord community to Agora |
| [Constrained radio mesh gateway](profiles/radio-mesh-gateway.md) | Gatewaying IRONWEED and LICHEN radio meshes into Agora |
| [CORUNDUM](profiles/corundum.md) | One DID across CORUNDUM (public posts) and Agora (private messaging) |
| [Parlance](profiles/parlance.md) | Parlance device data on Agora |

## Guides

Non-normative, written for a specific reader.

- [Relay operations guide](guides/relay-operator.md): running relay infrastructure as an infrastructure operator.
- [Examiner's reference guide](guides/regulators.md): for financial regulators reviewing record-keeping.
- [Compliance and legal reference guide](guides/counsel.md): for counsel advising operators and firms.

## Test vectors

[test-vectors/](test-vectors/README.md): values computed by two independent
toolchains, with their generators.

## Background and design records

Non-normative. Useful for understanding why the specification says what it
says.

- [MLS as source of truth](notes/mls-source-of-truth.md): analysis of state the specification duplicated from MLS, with recommendations.
- [UX requirements](notes/ux-musts.md): sweep of BCP 14 requirements on client UX and which to soften.
- [MIMI vs JMAP Chat](notes/mimi-vs-jmap-chat.md): where the IETF MIMI work and JMAP Chat overlap and differ.
- [EU Digital Identity Wallet](notes/eudi-wallet.md): research behind the wallet part of attribute bridging.
- [OpenVTC ideas considered](notes/openvtc-adoptions.md): what Agora took from OpenVTC and why.
- [Review rounds](notes/): findings and verifications from five review rounds (`notes/review*/`).

## Other directories

| Path | What |
|---|---|
| [attic/](attic/) | Out of scope for the first release: [relay economics and payments](attic/relay-economics.md), [futures](attic/futures.md), and a [CIO assessment](attic/cio-assessment.md) |
| [import/](import/PROVENANCE.md) | Frozen verbatim source from nie, with provenance; reference only |

Payments and cryptocurrency are out of scope for the first release.

Work is tracked in Beads (`bd ready`, epic `agora-pozi`).
