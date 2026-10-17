# Agora

A federated, end-to-end encrypted group communication protocol in which
**operating the infrastructure is separate from operating the communications.**
Relays carry ciphertext and decide nothing; the community or organization that
owns a Space holds every authority over it. See [ARCHITECTURE.md](ARCHITECTURE.md).

Agora carries typed data of any kind, including JSON-LD. The JMAP family of
specifications (chat, calendars, tasks, files, scenes, calls) is carried as
first-class payloads.

Status: draft specification. No conformant implementation exists.

## Layout

| Path | What | Normative |
|---|---|---|
| `PROPOSAL.md` | What Agora proposes, what is open, what we are asking for | no |
| `PRFAQ.md` | Press release and FAQ: customers, risks, status | no |
| `ARCHITECTURE.md` | Operator separation: roles, rules S1–S9, observation budget | yes, governs on conflict |
| `spec/` | Protocol, in parts; each part states which operator it binds | yes |
| `profiles/` | Deployment profiles: employer-managed DIDs (O365, Google Workspace, generic identity provider (IdP)), Purview export, Discord onboarding, compliance chain witnessing, CORUNDUM identity sharing, Parlance device data, radio mesh gateway, gateways to other networks (Matrix, Slack, Teams) and the path to native More Instant Messaging Interoperability (MIMI) | no |
| `guides/` | Relay operator guide, regulators' guide, counsel's guide | no |
| `attic/` | Out of scope for first ship: relay economics and payments, futures, CIO assessment | no |
| `import/` | Frozen verbatim source from nie, with provenance | no, reference only |
| `notes/` | Research and backport inventory | no |

Payments and cryptocurrency are out of scope for the first release.

Work is tracked in Beads (`bd ready`, epic `agora-pozi`).
