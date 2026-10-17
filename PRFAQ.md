# Agora PRFAQ

## Press Release

**SEATTLE, WA, [launch date]**

### Agora separates who runs the servers from who runs the conversation

*Hire anyone to carry your messages. Never hand them your keys, your members, or your rules.*

Today the Agora protocol launches: open, end-to-end encrypted group communication in which the infrastructure operator and the communications operator are different parties with different powers. The company that runs your relays carries ciphertext and decides nothing. Your organization holds every authority over its own communities: who is in them, what they permit, what they retain, and who may read the archive.

Every major platform today fuses those two roles. When Slack or Microsoft runs the servers, it also holds the membership lists, enforces the policies, and can produce your plaintext under subpoena or lose it in a breach. Federated systems such as Matrix and Mastodon move the servers around but keep the fusion: whoever runs a homeserver sees the membership and metadata of every community on it. Agora splits the roles in the protocol itself, so the split survives a change of vendor, a court order, or a careless operator.

**For the organization**, Agora means hosting without surrender. A managed provider can run your relays under a service agreement while your identity provider, your membership, your compliance archive and your policy stay with you. If the provider disappoints you, you replace it: your Spaces, members and history do not change and nobody re-enrolls.

**For the relay operator**, Agora means less liability. A relay routes envelopes by rotating tokens it cannot reverse. It does not know who your members are, who sent a message, or which of a customer's Spaces a message belongs to. Served with legal process, it can produce connection metadata and which customer's service an address used, and nothing about content, membership or senders.

**For regulated firms**, Agora captures communications without breaking encryption. A compliance logger, run by the firm, is a disclosed member of each regulated conversation, and the capture obligation follows a regulated employee into direct messages. Records flow into the firm's own archive and, through a gateway, into Microsoft Purview, where legal hold and e-discovery work as they do today.

Agora is built on MLS (RFC 9420), the IETF standard for group end-to-end encryption, and interoperates natively with MIMI, the IETF's cross-platform messaging work. Employees sign in through Okta, Entra or Google Workspace. The specification is public and anyone may implement a client, run a relay, or operate a community.

---

## Frequently Asked Questions

### Customer FAQs

**Q: What does the relay operator see?**

Network connection metadata (addresses, timing, volume), encrypted envelopes keyed by rotating tokens, and which customer agreement those tokens fall under. It does not see message content, senders, membership, channel names, or which of a customer's Spaces a message belongs to. The full list is closed and normative: anything not on it is a protocol violation, and any extension to it must be opt-in, declared, and visible to members. Agora is not anonymous at the network layer; members who need that use Tor.

**Q: What can our hosting provider do to us?**

Stop serving you, and nothing more. It cannot read your messages, change your membership, sign your Space's state, enforce your policies, or hold your history hostage. Your history is content-addressed, so another provider can serve the same records. Your service agreement is signed with a billing key that appears nowhere in your Spaces, so the provider cannot link your traffic to a particular Space.

**Q: We run many communities. Does that matter?**

It helps. A relay learns which customer's service an address used, never which Space. The more Spaces you run through the same provider, the less the provider can infer about any one of them.

**Q: How does IT provision accounts?**

Through your identity provider. Your organization's provisioning service issues each employee a stable DID under your own domain, driven by joiner/mover/leaver events from Okta, Entra, Google Workspace, SCIM or Active Directory. Device keys are generated on the device. Names, email addresses and UPNs can change without changing anyone's identity, so archives and audit trails stay keyed to one identifier for a person's whole tenure.

**Q: Can we send confidential announcements to the whole company?**

Yes. Broadcast channels are encrypted under a key your organization distributes to its members, so a message to 20,000 employees is unreadable to the relays that carry it. Public announcements use the same mechanism with the key published.

**Q: How does compliance capture work, and what are its limits?**

The firm designates which employees are regulated. The firm's compliance logger joins their channels and direct messages as a disclosed MLS member and archives every message to a tamper-evident chain under the firm's control. Calls are recorded by a firm-run recorder after a disclosure that every participant sees. Enforcement happens at the firm's own endpoints, the regulated employee's managed device and the logger, not at the relay. A tampered client can evade capture, which is the same trust boundary firms already rely on for every other channel, and the logger records the gaps it can detect.

**Q: How do our people talk to counterparties on Teams or Slack?**

Through a gateway your organization runs. E2EE does not survive the gateway, and every member of a bridged channel sees a persistent indicator saying so. With MIMI-compatible platforms, a single MLS group spans both systems and E2EE is preserved end to end.

**Q: What can Agora carry besides chat?**

Any typed data: JSON-LD, and the JMAP family of specifications, which covers chat, calendars, tasks, shared files, spatial scenes and call coordination. Data that only its author edits is replicated to each member's own device. Data that several people edit, such as a shared folder, gets its order from a sequencer that stamps encrypted edits without reading them. Fast real-time data, such as avatar movement in a scene, travels encrypted alongside call media.

**Q: How are voice and video handled?**

WebRTC with MLS-encrypted signaling. Calls of up to four people are peer-to-peer. Larger calls use a forwarding server that carries end-to-end encrypted media it cannot decode, and that is never a member of the conversation.

**Q: Can I use my own keys, or my Bluesky identity?**

Yes. The default identity is a `did:webvh` address on a host you choose, which keeps a signed history so the host cannot quietly add keys, and which moves with you if you change hosts. People who already have a Bluesky identity can use it (`did:plc`). People who want no server at all can use a bare key (`did:key`); they hold their own backup, and losing it means starting over. An employer chooses the method for the identities it issues, and a community can limit which methods it accepts.

**Q: Is Agora a replacement for Signal?**

No. For a person protecting one-to-one conversations, Signal remains the better tool. Agora is for organizations that need persistent channels, history, moderation, voice and video, and compliance capture, run by them and not by their vendor.

---

### Internal FAQs

**Q: What is built so far?**

A draft specification. Operator separation is stated as the protocol's first normative principle (`ARCHITECTURE.md`) and the protocol (`spec/`) has been revised against it. There is no conformant implementation. A one-week prototype from April 2026 predates the separation principle and violates it; it is kept for history only. The bridges, Purview gateway and identity integrations exist as designs in `profiles/`, not as software.

**Q: Why does the separation matter commercially?**

It creates a market that cannot lock its customers in. Relay operators compete on price, reliability and jurisdiction, while customers keep the authority a vendor would otherwise hold over them. That is the condition under which regulated firms can buy hosting at all, and under which an open-protocol business works: revenue from operating relays, compliance infrastructure, integration and support, with no Agora, Inc. owning the network.

**Q: Why not extend Matrix or XMPP?**

Both put community authority on the server. Matrix homeservers hold room state, including membership, in the clear; its Megolm encryption lacks post-compromise security. XMPP's E2EE is fragmented across extensions. Retrofitting MLS and operator separation into either means rebuilding the parts that make them what they are.

**Q: Who is the target customer?**

Regulated financial services and healthcare firms that must capture communications, including direct messages, and cannot do so today without handing plaintext to a vendor. Security-focused organizations that will not accept a SaaS vendor holding keys to legal, executive or M&A conversations. Organizations in jurisdictions where compelled disclosure by a communications vendor is a material risk.

**Q: What does the first release leave out?**

Payments and cryptocurrency of any kind; commercial terms between customers and relay operators are outside the protocol. Network-layer anonymity. Large-group cryptography beyond MLS groups of a few hundred, apart from broadcast.

**Q: What is still undecided?**

One thing: whether the epoch access proof, which lets relays admit only current members without learning which member, holds up under external cryptographic review. The design already closes one flaw found in internal review (a member being removed could have hijacked the relay's key chain). The other open protocol questions were decided in October 2026.

**Q: What are the top risks?**

First, the epoch access proof is new cryptographic design and has had no expert review. If it fails, relays lose their way to admit members blindly, and the separation needs another mechanism. It must be reviewed before anyone implements it.

Second, auditor certification. The compliance design is intended to satisfy SEC 17a-4, FINRA and MiFID II retention, but no auditor has certified it, and regulated firms will not deploy without that. Certification is a launch-parallel workstream.

Third, client-side enforcement. Moving policy off the relay means compliance capture depends on managed devices. Firms that let regulated employees use unmanaged devices will have capture gaps, and must be told so.

**Q: What would make us stop?**

An expert review that finds the separation cannot be made sound without giving relays membership knowledge. At that point Agora would be another federated chat protocol, and there are enough of those.

---

> **What is a PRFAQ?** A PRFAQ (Press Release / FAQ) is an Amazon-originated product planning technique. It starts with a fictional press release written as if the product has already launched successfully, forcing clarity on customer benefit and desired outcome. The FAQ section then anticipates hard internal and external questions. Writing the press release first ensures the team aligns on what success looks like before committing to implementation.
