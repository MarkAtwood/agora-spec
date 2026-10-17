# Agora: Plans, Ideas, Hopes, and Dreams

**Status:** Speculative. Nothing in this document is committed to the protocol spec.
**Date:** 2026-04-24

---

## What Agora Already Is

Agora is a decentralized, end-to-end encrypted, real-time group communication protocol. It is designed to support a user experience comparable to Discord (servers with hierarchical channels, presence, voice/video) without any central authority owning identity, routing, or message storage.

That framing is accurate but undersells the architecture. The protocol provides:

- **Self-sovereign identity** at every scale, from an individual with a keypair to a government agency with a DNS-anchored DID namespace
- **Authenticated, encrypted group state** via MLS, where group membership is cryptographically enforced and the relay is structurally blind
- **Content-addressed persistent storage** via IPLD, where history is tamper-evident
- **Federated real-time fanout** via libp2p gossipsub, permissionless and without a central directory
- **Micropayments** via MobileCoin, already wired into the relay economics model
- **Cross-topology reachability**: a `.gov` user and a `.onion` user can DM each other; the protocol doesn't care

Together these make a substrate for more than chat.

---

## The OASIS

Ready Player One's OASIS is the most useful mental model for where this could go: a persistent, federated virtual world where identity, property, social structure, and economic activity are real, and where what you build, own and earn has weight beyond the platform that hosts it.

Every prior attempt at a metaverse was owned by a company. When the company dies or pivots or gets acquired, the world ends, along with your avatar, your property and your relationships.

Agora's architecture makes a different bet. Identity is self-certifying. History is content-addressed. The relay is blind and replaceable. No single company can pull the plug on a namespace it doesn't control.

A VR metaverse built on Agora would be a collection of Spaces: some publicly discoverable, some invite-only, some air-gapped from the rest. Each Space is a world or a region or an instance. Channels are zones. The gossipsub mesh is the nervous system. MLS groups are the rooms you're in.

The DNS-namespace-as-root principle that governs relay discoverability applies here too. A game studio or world operator roots its platform in a DNS name. Players get identities under that namespace, or bring their own `did:key` identities from outside. The world persists as long as someone pins the IPLD state: the operator, the players, or both.

---

## Spatial Presence

The current presence model (§7) is chat presence: online, away, do-not-disturb, typing. That is insufficient for VR.

Spatial presence needs:

- **Position and orientation**: where you are in a 3D space and which direction you're facing
- **Avatar state**: expression, gesture, animation blend weights
- **Spatial audio zones**: who you can hear depends on where you are, not who's in the channel
- **Proximity fanout**: you receive presence updates only from entities within some spatial radius; flooding the whole channel with everyone's position at 60fps is not viable

The gossipsub fanout model suits this well if you add spatial sharding. A zone or region becomes a gossip topic. When you move between zones you subscribe and unsubscribe. Within a zone, position updates are ephemeral gossip messages: no storage, no IPLD, high frequency, best-effort delivery. The MLS group for the zone handles authentication; the gossip mesh handles delivery.

Spatial audio would integrate with the existing SFU model (§10). The SFU already handles media routing; spatial attenuation based on position state is an application-layer concern on top of the WebRTC stack.

---

## Gaming

### The General Case

Any game needs authenticated participants, shared state, ordered events, and some notion of who's allowed to do what. Agora provides all of these.

A game session is an MLS group. Players are members. Game events are MLS application messages: authenticated, ordered (via the IPLD linked list), and encrypted from the relay. The session starts when the group is formed and ends when it's abandoned or the history is archived.

Lobbies are Spaces. Game instances are channels or sub-groups. Leaderboards and persistent player records are IPLD documents pinned by whoever cares about them.

### RPG: Persistent Worlds and Character Identity

RPG is the richest case. A persistent RPG world needs:

- **Character identity**: a DID for your character, separate from your user DID and controlled by it. Your character can have a name, a history, inventory and stats, all in an IPLD document chain. You own the keys; no game company can delete your character.
- **World state**: the authoritative state of the world (who's where, what's happened, what exists) is an IPLD DAG. The game operator pins it. Players can pin it too. Forks are possible; canonical state requires a designated authority.
- **Game Master authority**: the GM is a DID with special commit rights over world-state MLS messages. The relay remains blind and plays no part in this. The GM is a participant in the MLS group with elevated permissions, like a Space admin in the current model.
- **NPC identity**: NPCs are DIDs too, controlled by the world operator or by autonomous agents. An NPC that can be talked to, traded with, or killed is a DID with a message loop on the other end. That loop could be a human GM, a script, or an LLM.

### Card and Table Games

Card games (poker, Magic, collectible card games) and table games (chess, Go, board games) are the clearest case for the **referee principal** model.

A blind relay can't prevent cheating: if it can't see the game state, it can't verify that a move is legal. Instead of giving the relay sight, the game adds a **referee** as a participant in the MLS group.

The referee is a DID that all players agree on before the session starts, named in the game session descriptor. The referee is the only participant authorized to commit game-state-advancing messages. Players submit proposed moves to the referee (or to the group, and the referee validates). The referee commits the authoritative state. The relay routes the messages and still sees nothing useful.

The referee can be:
- A trusted third-party service
- One of the players, by agreement (honor system)
- An autonomous program whose source is published and whose DID is derived from a hash of that source (so players can verify what they're trusting)

Card games with hidden information (poker hole cards, MTG hand) use MLS subgroups: each player has a private channel to the referee for their hidden state. The referee knows all hands; the relay knows nothing.

For collectible card games, the cards are IPLD assets: content-addressed, owned via DID-signed transfer records. A card you earned or bought has a provenance chain. A deck is a signed list of card CIDs. Counterfeiting is structurally impossible.

---

## Person-to-Person Payments

MobileCoin is already in the spec as the payment mechanism for relay economics and message micropayments (§12). Extending it to P2P payments between users is a short step.

The vision:

- **Tipping and gifting**: send MOB to any DID you can resolve. The payment message is an MLS application message in a DM group, authenticated by both parties, private from the relay.
- **In-game transactions**: buy an item, pay entry to a tournament, split a bill after a virtual dinner. All P2P, all auditable by the parties, none visible to the relay or any third party.
- **Escrow for game stakes**: a poker pot, a tournament prize pool, a bounty on a quest. A smart escrow is a DID-identified service that holds funds and releases them on a signed trigger from the referee principal.
- **Creator payments**: a world operator or content creator publishes a Space; access requires a signed payment receipt. No payment processor sits in the middle; the receipt is a MOB transaction on-chain.

The key primitive is the DID-to-payment-address binding. If your DID document includes your MOB address, anyone who can resolve your DID can pay you, with no username lookup, payment handle, or intermediary.

---

## Asset Ownership

Virtual assets (VR items, game inventory, collectible cards, land parcels in a virtual world) need a provenance model that survives platform death.

IPLD already provides one. An asset is an IPLD document: a description, an image CID, a set of properties, and an ownership record. Ownership is a DID-signed transfer chain. The current owner is whoever holds the private key for the most recent transfer's target DID.

Minting (creating a new asset) is a signed assertion by the world operator's DID. Transferring is a signed message from current owner to new owner, witnessed by the game's referee principal or gossiped to the mesh. The full provenance chain is content-addressed and tamper-evident.

There is no blockchain here: no global consensus, no proof-of-work, no token. It is a signed linked list, which is sufficient for any game or VR context where the issuing authority is known and trusted by the participants.

---

## What This Implies About the Protocol

Agora is currently framed as "decentralized Discord." That framing helps adoption, since Discord users understand it immediately, but it undersells what's been built.

A more accurate description: Agora is a decentralized substrate for authenticated real-time interaction between self-sovereign identities, with content-addressed persistent state, blind transport, and optional payments.

That substrate supports:
- Chat (what it was designed for)
- Voice and video (already specified)
- VR spatial presence (extension of the presence model)
- Gaming of all kinds (MLS groups + referee principal)
- A metaverse (Spaces as worlds, IPLD as the world state, DIDs as everything)
- P2P payments (MobileCoin already wired in)
- Asset ownership (IPLD + DID-signed transfer chains)

None of these require changing the core. They are additive extensions on a foundation that was, by accident or by design, general enough to hold them.

---

## Tensions and Open Questions

**Relay blindness vs. game integrity.** The relay cannot referee. The referee principal model resolves this, but players must agree on and trust a referee DID before a session starts. Centralized game servers do not impose that coordination cost. Whether it is acceptable depends on the game.

**Spatial presence at scale.** A zone with 10,000 concurrent avatars cannot gossip everyone's position to everyone. Spatial sharding and progressive detail (full fidelity for nearby; low fidelity for distant; nothing beyond some radius) are the standard solutions. Game networking has solved these problems; integrating them with the gossipsub model needs design work.

**World state authority and forks.** A persistent RPG world needs a canonical world state. IPLD gives you tamper-evident history, but not a single authoritative tip. If two GMs advance the world state at the same time, you get a fork. Resolving forks requires either a single designated authority (simple, centralized) or a consensus mechanism (complex, decentralized). The right answer probably depends on the scale and governance model of the world.

**Asset ownership without global consensus.** The DID-signed transfer chain works if you trust the issuing authority and the transfer witnesses. Without a trusted referee or a global ledger, it does not prevent double-spending (transferring the same asset to two parties at once). For low-stakes game items this is acceptable. For high-value assets it may not be.

**Performance.** The current spec is designed for human-paced interaction: messages, presence updates, typing indicators. Game physics and VR presence run at 60–120Hz, which is a different engineering problem. WebTransport/QUIC is the right transport; the framing and gossip models need profiling at game-relevant message rates.

**Privacy in a VR world.** Spatial presence leaks location within a world. A blind relay that routes position updates is less blind in practice than one routing encrypted chat. The threat model for VR presence differs from the one for messaging, and the spec will need to address it explicitly.

---

## What to Build Next

In rough priority order, the protocol extensions that enable the most:

1. **Spatial presence message type**: position, orientation, avatar state, zone subscription model. Unblocks VR and spatial audio.
2. **Referee principal model**: a named authority participant in an MLS group with commit-gating rights. Unblocks card games, table games, anything requiring adjudication.
3. **Asset descriptor and transfer chain**: IPLD schema for owned assets and DID-signed transfer records. Unblocks collectibles, inventory, land.
4. **P2P payment message type**: MOB transfer receipt as an MLS application message. Unblocks tipping, in-game transactions, escrow triggers.
5. **Game session descriptor**: a structured IPLD document naming the game type, referee DID, participants, stakes, and rules reference CID. Unblocks matchmaking and session bootstrapping.
6. **NPC/agent identity model**: a DID controlled by an autonomous process, with a published behavior specification. Unblocks NPCs, bots, and AI participants.

---

*This document records ideas, not commitments. Everything here depends on someone deciding to build it.*
