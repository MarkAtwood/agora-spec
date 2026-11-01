# AGORA at IIW: Index Card

## Front

**AGORA: The people who carry your messages don't run your community**

**Two roles, kept apart by keys.** Infrastructure Operators (relays, SFUs,
sequencers, push, wallet transports) carry encrypted bytes. Communications Operators (the
community or org) hold every decision: who's in, roles, moderation, retention,
compliance.

**The test:** anything that holds group secrets, signing keys, plaintext, or
the member list is a CO component. Everything else is IO, whoever runs it.
A DIDComm wallet transport that moves ciphertext is IO; a gateway that reads
the messages is CO.

**Swappable:** you can change relays without changing the community's
identity, members, history, or policy.

## Back

**Why it's still fast**

- **Control never sits in the message path.** The CO acts only when membership
  or policy changes. Ordinary messages go client → relay → client.
- **Infrastructure only does fast, simple work.** Relays forward ciphertext and
  check a pre-registered admission token, not an identity. Sequencers just
  stamp the order. SFUs forward encrypted media.
- **Clients do the checking.** Authorization is verified at the ends, so no
  server-side policy lookup slows each message down.
- **MLS:** group key updates cost O(log n) (RFC 9420).

## Speaker notes (not on the card)

- Source for the separation half: `ARCHITECTURE.md` §1–2.3 (the principle, the
  IO/CO roles, the key test).
- The speed half is a summary of existing design decisions. The spec makes no
  explicit performance claim.
- Likely pushback on "not in the message path": clients fetch admission keys
  from the Space endpoint, and the sequencer orders Commits. Answer: both
  happen on join or membership change, not on every message.
- Scale question on broadcast channels: the CO hands out the channel content
  key once, and relays fan out the ciphertext.
- Softer option: change the back's heading to "Why separation doesn't cost
  speed."

## Q&A: "Could it use DIDComm instead of jmap-chat?"

Short answer: No. It's a different layer. DIDComm is how two wallets reach
each other. jmap-chat is what a message says, and it travels inside an MLS
group. Putting DIDComm in that slot breaks the operator separation.

If pressed:

- **Layers.** jmap-chat is only the message format. The messages ride inside
  MLS groups. DIDComm is an envelope and transport between agents. So the real
  question is "DIDComm instead of MLS," not "instead of jmap-chat."
- **Groups.** MLS gives one shared group key, O(log n) member changes, and
  forward secrecy across the whole group. DIDComm is pairwise, so a 500-person
  channel means encrypting each message 500 times, and nothing coordinates
  removals.
- **Mediators.** DIDComm routes through mediators, and a mediator sees who is
  talking to whom. That's an observer the architecture doesn't account for
  (ARCHITECTURE §5). `profiles/dtg-openvtc.md` §8 already rules out DIDComm
  and TSP for KeyPackage and Welcome delivery for this reason.
- **Second envelope.** The same section rules out the Trust Task envelope as a
  message format, because it would duplicate Agora's typed payloads.

What to offer (`profiles/dtg-openvtc.md` §6, §9):

- An OpenVTC agent can be one of the user's Agora devices: self-hosted, with
  its own MLS leaf.
- A community can run a gateway between an Agora channel and DIDComm or TSP
  agents. It's an ordinary gateway that the community runs and discloses to
  members.
- Both use `did:webvh`, and DTG credentials can appear on an Agora member's
  leaf.

### Follow-up: "Could it have a DIDComm gateway? Do the messages get unwrapped?"

Short answer: Two paths. A gateway works with any DIDComm wallet but sees the
messages. A wallet that runs MLS can take Agora traffic over DIDComm through a
wallet transport that never decrypts. It's just a pipe, the same class as our
relays. Full walkthrough: `profiles/didcomm.md`.

- **Gateway (fits the spec today).** A CO component that is an MLS member,
  decrypts, and re-encrypts to DIDComm. It sees plaintext and must be
  disclosed before messages flow (spec §9). `unencryptedRemote` is `false`
  because DIDComm is encrypted to the agent. Works with wallets that have no
  MLS support.
- **Wallet transport (specified, spec §11.9).** An IO that opens relay
  connections for the wallet and passes live-stream messages through
  unchanged, over DIDComm v2 or TSP. It holds no keys or plaintext; the
  wallet signs everything. Engaged like a push proxy (`wallet-transport`
  service agreement, relay- or CO-designated). The wallet MUST use a pairwise
  DID with it, never its Agora DID.
- **Rejected: treating DIDComm mediators as relays.** It would mean fitting
  service agreements and observation limits onto mediators Agora neither runs
  nor binds.
- **On "DIDComm + MLS demos":** these usually carry MLS inside DIDComm, which
  is the wallet transport model. The wallet still has to implement Agora's MLS
  profile, Space state, and extensions.

### Context: is DIDComm still live? (checked 2026-10-31)

Alive but a niche. The big wallet ecosystems went with OpenID4VC. Expect a
mixed room.

- **Still in use:** DIF maintains DIDComm v2 as an approved spec. Its (undated)
  survey shows use mostly in wallets for issuing credentials, then
  agent-to-agent messaging. Aries descendants still work on DIDComm v2.
  Affinidi (OpenVTC) started with DIDComm and added TSP.
- **Where the field went (unverified, from training data):** the EUDI wallet
  uses OpenID4VCI/VP plus ISO mdoc, not DIDComm. Hyperledger Aries' active code
  moved to the OpenWallet Foundation (ACA-Py, Credo). Exact status and dates
  not confirmed.
- **Successor direction:** ToIP's Trust Spanning Protocol (TSP), still a v1.0
  Implementor's Draft, independent of the transport. ToIP considers running
  DIDComm over TSP worth trying, with no changes to either spec.
- **Line for the room:** "DIDComm or TSP, the answer is the same. A wallet
  that runs MLS can take Agora ciphertext through a wallet transport that
  sees nothing. Anything else is a gateway, and members are told it's there."

## Q&A: "What about OpenVTC?" (checked 2026-10-31)

Short answer: OpenVTC tells you who someone is. Agora is where the community
talks, and the community runs it, not whoever hosts the servers.

- **Why people are excited:** LF Decentralized Trust demoed the first
  open-source Verifiable Trust Community at Open Source Summit EU in Prague
  (2026-10-15): Linux kernel contributors proving identity with credentials
  instead of the PGP web of trust. LFDT announced Labs for the DTG credential
  and Verifiable Trust Infrastructure reference implementations.
- **Partner, not competitor:** OpenVTC has no chat, calls, or group messaging
  (`profiles/dtg-openvtc.md` §1). A trust community needs somewhere to talk.
- **Already fits:** shared `did:webvh` default; a Space can admit members on a
  trust community's credentials, or make the community a delegated admin; DTG
  credentials can sit on a member's MLS leaf; OpenVTC agents can reach relays
  over TSP through a wallet transport (spec §11.9).
- **Watch (verified 2026-10-31):** DTG Trust Tasks already has an MLS-based
  `rooms/*` family (~50 task types since 2026-09-02, still active): MLS
  KeyPackages, Welcomes, epochs, owner add/remove, and a host that sees only
  opaque epoch data. It overlaps directly with Agora. Expect the question
  "why not DTG rooms?" Also `chat/message` and ~40 `messaging/*` tasks for
  mediators and relays. (The `communications`/call proposal, PR 672, was
  closed unmerged on 2026-10-29.)
- **"Why not DTG rooms?"** Different jobs. A room is the community's filing
  cabinet: versioned records and files, owner as sole committer, pull-only
  sync. Agora is its meeting hall: live chat, DMs, channels, calls, any
  member commits. Same instinct on hosts (replaceable, sees ciphertext), but
  an Agora relay never learns who sent what on any tier, without needing
  zero-knowledge proofs. Rooms have running code (VTI); Agora is a spec.
- **"Does Agora have a filing cabinet / shared agent memory?"** Yes, and it
  speaks rooms' language. Every Space already has `FileNode` files and
  durable encrypted blobs. On top of that, provenance records
  (`draft-atwood-jmap-graph-provenance-00`, profiled in spec §14.6.15) let a
  record say *how* its author knows: `basis` is `declared`, `observed`,
  `verified`, or `inferred` (an agent's guess), with the author's own
  `confidence`, `validUntil`, and evidence as graph edges to what it rests on.
  Curators demote, retract (permanent), or pin under a separate `curate`
  permission. Field names match DTG rooms, so a gateway maps records
  one-to-one. Differences from rooms: any permitted member writes (no sole
  owner), records are data never instructions, evidence is never fetched.
- **Caution:** working drafts, frequent breaking releases, TSP revisions that
  don't interoperate. Agora pins versions in the profile; core references none.

### If "wallet comm" means OpenID4VP wallet flows instead

That's credential presentation, not messaging. Agora handles it through attesters, which issue
credentials to the member's DID.
