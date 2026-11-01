# Profile: DIDComm

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Draft, 2026-10-31
**Depends on:** ARCHITECTURE S1, §2.3, §5; spec §2.1, §5.2.1.1, §9, §11.3, §11.6, §11.8, §11.9
**Sources:** DIDComm Messaging v2 (DIF, https://identity.foundation/didcomm-messaging/spec/v2.1/); Trust Spanning Protocol (TSP) (https://trustoverip.github.io/tswg-tsp-specification/); `profiles/dtg-openvtc.md`; `profiles/gateways.md`

---

## 1. Summary

DIDComm is a transport between agents, not a message format. Agora keeps its own layers: jmap-chat `Message` objects (spec §14) are the content, MLS groups encrypt them, and relays carry the ciphertext. DIDComm does not replace any of these. It can carry Agora traffic to agents that are reached through DIDComm, in one of two ways:

- **Gateway**, for agents that do not run MLS. The gateway decrypts and re-encrypts, so it holds plaintext (spec §9).
- **Wallet transport**, for agents that do run MLS. It carries ciphertext only and holds no keys (spec §11.9).

This profile explains both for readers who know DIDComm. It adds no protocol. Everything in it that is a rule is a rule of the spec or ARCHITECTURE.md, cited where it appears.

## 2. Why DIDComm Does Not Replace MLS

A DIDComm message is encrypted to each recipient. A group of 500 means encrypting each message 500 times, with no shared group key, no forward secrecy across the group, and nothing that coordinates who is removed when. MLS gives one group key, member changes at O(log n) cost (RFC 9420), and a single agreed membership. Agora uses MLS for groups and treats DIDComm as one possible way to move MLS ciphertext.

DIDComm also routes through mediators, and a mediator sees which agent is receiving from which, and when. An infrastructure observer that Agora does not declare in its observation budget (ARCHITECTURE §5) would weaken operator separation, so Agora never requires a mediator on any path. Where DIDComm is used, the mediator belongs to the user's side (section 5).

## 3. Path 1: A Gateway

An agent that speaks DIDComm but not MLS can join an Agora channel only through a gateway. The gateway is a CO component with its own DID (spec §9). It is an MLS member of the channel, holds plaintext, and is disclosed to members before any message passes through it (spec §9.3). It decrypts MLS on one side and sends DIDComm messages on the other. DIDComm is encrypted to the agent, so the gateway's `unencryptedRemote` is `false` (spec §9.2). Members still see that a gateway sits on the channel and reads it.

A gateway suits a CO that wants agents or bots of another ecosystem in a channel. It does not give those agents end-to-end encryption with Agora members. `profiles/gateways.md` describes how gateways do their job.

## 4. Path 2: A Wallet Transport

An agent that implements Agora's MLS profile is an ordinary Agora client: a member of its groups, holding its own admission keys and signing its own envelopes. If it cannot keep a WebTransport or WebSocket connection open, for example a mobile wallet reached through a mediator, it can use a wallet transport (spec §11.9).

The wallet transport is an IO. It opens relay connections for the agent and passes each live-stream message through unchanged. It holds no MLS secret, signing key, admission key, or plaintext (ARCHITECTURE §2.3). A relay or the CO designates it, and it serves under a `wallet-transport` `ServiceAgreement`, as a push proxy does (spec §11.9.1).

A DIDComm v2 exchange looks like this:

1. The agent finds a wallet transport in a relay manifest or in Space state (`walletTransport`, spec §11.9.1), and resolves its DID to the DIDComm service endpoint in its DID document.
2. The agent creates a pairwise DID, typically `did:peer`, that it uses with this wallet transport and no other party (section 6).
3. It sends a DIDComm v2 message of type `urn:agora:type:WalletTransport`, encrypted with authcrypt, whose body carries a `WTOpen` naming a relay's WebSocket endpoint (spec §11.9.2, §11.9.3).
4. The wallet transport opens the connection, answers the relay's connection admission challenge itself (spec §11.6), and returns each relay message as a `WTFrame`.
5. The agent sends `ClientHello`, `Subscribe`, and signed `Publish` messages as `WTFrame`s, and receives `Deliver` messages the same way.

Frames carry sequence numbers, because DIDComm does not guarantee order (spec §11.9.2). If the agent misses messages while offline, it catches up through the relay sync API over HTTPS (spec §11.8).

## 5. Mediators

The agent's DIDComm mediators are its own network choice, like an internet service provider or an overlay network (spec §11.3, §11.9.4). They sit outside Agora's observation budget. A mediator sees when the wallet transport sends to the agent and how much. It sees only DIDComm ciphertext, and inside that only MLS ciphertext. A user who wants Agora's protections against traffic analysis picks a mediator accordingly, as they would pick an overlay network.

## 6. Identities

An Agora user has an Agora DID, by default `did:webvh` (spec §2.1), which their MLS leaves and credentials name. A wallet transport must never learn it. The agent MUST address each wallet transport with a pairwise DID it uses with no other party, and MUST NOT use its Agora DID for this (spec §11.9.4). Otherwise the wallet transport could link that DID to the routing tokens it subscribes to, which no IO may do (ARCHITECTURE S1). The pairwise DID plays the role a `pushHandle` plays for push (spec §11.7).

## 7. What Stays Off DIDComm

- **KeyPackage fetches and Welcome delivery.** These stay on the user's HTTPS `KeyPackageEndpoint` (spec §5.2.1.1). A mediator that forwarded Welcomes would see who starts a conversation with whom (`profiles/dtg-openvtc.md` §8).
- **History, blobs, and Space endpoint requests.** These use HTTPS (spec §11.8, §10.4.4, §3.4). An agent that uses a wallet transport still needs an HTTPS client.
- **Message formats.** DIDComm message bodies and the Trust Task envelope are not Agora content. Agora messages are typed payloads inside MLS (spec §13.1); a second envelope would duplicate them (`profiles/dtg-openvtc.md` §8).

## 8. TSP

The Trust Spanning Protocol binds the same way: each wallet-transport message is the payload of one TSP message between the agent's pairwise DID and the wallet transport's DID (spec §11.9.3). A wallet transport lists `didcomm-v2`, `tsp`, or both in `protocols`. Nothing in Agora depends on which protocol an agent uses. OpenVTC agents prefer TSP and then DIDComm v2 (`profiles/dtg-openvtc.md` §2).

## 9. Ecosystem Status

As of 2026-10-31. Items not checked against a current source are marked.

- DIF maintains DIDComm v2 as an approved specification. Its adoption survey (undated) shows use mostly in identity wallets for credential issuance, then agent-to-agent messaging.
- Descendants of Hyperledger Aries continue DIDComm v2 work on agents, mediators, and wallets. *Unverified:* the active Aries code moved to the OpenWallet Foundation (ACA-Py, Credo).
- Affinidi, behind OpenVTC, started with DIDComm and added TSP.
- TSP is a v1.0 Implementor's Draft at Trust Over IP and is independent of transport. Its task force considers carrying DIDComm over TSP possible with no change to either specification.
- *Unverified:* the EU Digital Identity Wallet uses OpenID4VCI, OpenID4VP, and ISO mdoc, not DIDComm. Agora handles credentials from such wallets through attesters (`profiles/attribute-bridging.md`), not through messaging.

## 10. Open Questions

- Whether any wallet vendor will implement Agora's MLS profile. Without one, the gateway is the only path in practice.
- Whether DIDComm or TSP becomes the common agent transport. The wallet transport supports both, so the answer changes nothing in Agora.
