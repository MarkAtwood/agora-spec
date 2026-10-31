# AGORA at IIW: Index Card

## Front

**AGORA: The people who carry your messages don't run your community**

**Two roles, kept apart by keys.** Infrastructure Operators (relays, SFUs,
sequencers, push) carry encrypted bytes. Communications Operators (the
community or org) hold every decision: who's in, roles, moderation, retention,
compliance.

**The test:** anything that holds group secrets, signing keys, plaintext, or
the member list is a CO component. Everything else is IO, whoever runs it.

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
translator that never decrypts. That translator is just a pipe, the same class
as our relays.

- **Gateway (fits the spec today).** A CO component that is an MLS member,
  decrypts, and re-encrypts to DIDComm. It sees plaintext and must be
  disclosed before messages flow (spec §9). `unencryptedRemote` is `false`
  because DIDComm is encrypted to the agent. Works with wallets that have no
  MLS support.
- **Ciphertext translator (proposed, not specified).** An IO component at
  Agora's edge. It subscribes to relays with the channel token for the wallet
  and repackages MLS ciphertext envelopes as DIDComm messages. It holds no
  keys or plaintext. The wallet is a real MLS member, so nothing is unwrapped
  in the middle. Relays see only another subscriber.
- **Rejected: treating DIDComm mediators as relays.** It would mean fitting
  service agreements and observation limits onto mediators Agora neither runs
  nor binds.
- **On "DIDComm + MLS demos":** these usually carry MLS inside DIDComm, which
  is the translator model. The wallet still has to implement Agora's MLS
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
  that runs MLS can take Agora ciphertext through a translator that sees
  nothing. Anything else is a gateway, and members are told it's there."

### If "wallet comm" means OpenID4VP wallet flows instead

That's credential presentation, not messaging. Agora handles it through attesters, which issue
credentials to the member's DID.
