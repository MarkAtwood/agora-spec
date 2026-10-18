# Private boards: large private forums ("web BBS") in Agora

Status: design note, non-normative proposal. 2026-10-18. Sources: Agora `spec/03` (§3.4), `spec/04` (§4.5), `spec/05` (§5.2.1.2–§5.2.1.4, §5.2.3, §5.2.5), `spec/10` (§10.4.4, §10.5.1), `spec/14`; CORUNDUM at c014c29 (`docs/spec/07-reply-protocol.md`, `08-social-graph.md`).

**Verdict.** A large private forum does not need a new protocol or a new channel mode. It is a **broadcast channel** (§5.2.1.4) that lets every member post. That needs four additions, all small:

1. a sentence permitting many-poster broadcast channels;
2. message deletion for broadcast channels;
3. a source of history that outlives relay retention;
4. an index for thread listing and search.

The cost is a weaker security model than MLS, and the spec has to state it plainly.

## 1. What a board is

A board is what web BBSes and private forums are:

- **Large.** Thousands to hundreds of thousands of members, most reading and few posting.
- **Archival.** Threads last for years, and the archive is the product. A member admitted today reads 2019's threads.
- **Searchable.** Members search the whole history.
- **Moderated by its operators.** Sysops remove posts and members, and they can read everything.
- **Private.** Non-members, including the infrastructure that carries and stores the board, cannot read it.

## 2. Why the existing pieces don't fit as they stand

- **CORUNDUM** has the right shape (signed posts, reply trees, a permanent archive) but is public by construction. Every activity's `to` includes `as:Public` (CORUNDUM Ch 11), and its content sits in public IPFS.
- **Agora `community` and `interactive` channels** have MLS properties a board does not want. A member can decrypt only epochs in which it held a leaf (§5.2.1.2, "History access"), so a newcomer cannot read the archive. The speaker group is capped at 500 (§5.2.1.2), and MLS Commit cost grows with group size.
- **Agora `broadcast` channels** are close. They use one content key per `keyEpoch` that the CO distributes, have no MLS group, keep the sender hidden from relays, and sign each post inside the ciphertext. The Space endpoint already serves the `BroadcastKey` and admission key of *any* `keyEpoch` to a currently permitted reader (§3.4: `GET <spaceEndpoint>/broadcast-key/<channelID>/<keyEpoch>`), so a newcomer can already decrypt old epochs. Messages already carry `replyTo` and `threadRootId` (§5.2.3).

## 3. The proposal: a board is a broadcast channel

A board is a `broadcast` channel whose `broadcasterRoles` includes the ordinary member role, so every member who can read it can also post. The mechanism needs no change for this. Posters get the full `ChannelAdmissionKey` so relays admit their envelopes, and recipients authorize each post by its inner signature against `broadcasterRoles` (§5.2.1.4).

What has to be added:

**3.1 Permit many-poster broadcast.** §5.2.1.4 says broadcast is "appropriate for one-to-many announcements; channels that need MLS properties MUST use `community` or `interactive` mode." A board does not need MLS properties, but the text reads as if many-poster use were out of bounds. Add one sentence saying that a broadcast channel whose `broadcasterRoles` covers every reader is a board, with the security properties of §5. Clients SHOULD mark boards distinctly, as they mark broadcast channels (§12.10).

**3.2 Message deletion in boards.** §4.5 defines a message delete as "an MLS application message" carrying a JMAP Chat retraction. A broadcast channel has no MLS group. Define the delete for broadcast channels as a `BroadcastMessage` carrying the same retraction, valid when posted by the message's author or by a holder of a moderator role. Moderation is after the fact: posts reach relays directly, so a board cannot hold posts for approval without adding a CO service to the posting path (see §6).

**3.3 History beyond relay retention.** Today history comes from relays for their retention period, from members' stores, or from a CO archive, which "MAY" exist and has no member-facing API (§5.2.5). A board needs one reliable source. Two options, and the first adds no mechanism:

- **(a) Long relay retention (preferred).** The CO buys relay service with unbounded or long retention for the board's `channelToken`s (§10.5.1). Relays are IOs and hold only ciphertext, so this keeps the blindness rules. A member reads old epochs as it does recent ones: it fetches the subscriber form of each past epoch's admission key for the `channelToken`, syncs envelopes through JMAP (§11.8), and decrypts them with that epoch's `BroadcastKey`. Attachments follow the blob rules (§10.4.4).
- **(b) A CO archive with a read API.** The CO keeps the archive and serves it to members with the channel's read permission. This means more to specify, and it puts the CO on the read path.

**3.4 Thread listing and search.** At board scale, a client cannot download years of a channel to build the thread list or to search it. Something has to index plaintext, and only the CO can, since relays must not see plaintext (§10.4.1). Specify an optional CO index service: thread listings (`threadRootId`, latest activity, reply count) and full-text search, served to members with read permission. A board without it works, but only for clients willing to sync the whole history.

## 4. What does not change

- Membership, roles, invites, kicks, and bans stay Space mechanisms (§3, §4).
- Kick and Ban already make the CO stop serving keys and rotate the admission key (§4.5); for a broadcast channel that rotation also rotates the content key (§5.2.1.4).
- Rotation at least every 30 days, and before 2^32 messages per key, already applies (§5.2.1.4). A board with frequent bans has many epochs; clients fetch past epoch keys lazily, only for history they open.
- Compliance logging already works for broadcast channels (§5.2.1.4).

## 5. Security model (state it plainly)

A board protects its content against infrastructure and non-members. It does not protect against its members or its operator:

- **Every member can read everything** they are permitted to read, keep it, and leak it. With thousands of members, assume a leak.
- **Removal is forward-only.** A removed member keeps every epoch key and message they had.
- **One key covers a whole epoch.** There is no forward secrecy or post-compromise security within an epoch, and a leaked epoch key exposes that epoch to anyone holding its ciphertext.
- **The CO reads plaintext** if it runs the index of §3.4 or moderates by content. This is how forums already work; the board's operator is its sysop.
- **Relays learn little.** They learn the `channelToken`, timing, and envelope sizes; with option 3.3 (a), they also learn how long the board's history is.

## 6. Alternatives considered

- **CORUNDUM-style gated threads.** In CORUNDUM, the parent post's operator accepts each reply into its reply tree, which allows pre-moderation (CORUNDUM Ch 21). For a board this means every post goes through a CO service before it reaches relays, a second posting path next to Agora's relay model. Rejected for now: post-moderation through §3.2 covers most forums, and gated boards can be added later as a CO bot that holds posts in a staging channel.
- **Large MLS groups for boards.** Rejected. A board wants newcomers to read history, which MLS forward secrecy prevents by design, and MLS Commit cost at 100,000 members is unattractive even with partial-member work (§5.2.1.3, "Future standard alignment").
- **Encrypting CORUNDUM content to a membership.** Rejected. It would bring Agora's key management into CORUNDUM, against the public/private split of `profiles/corundum.md`.

## 7. Questions for Mark

1. **Scale target.** Hundreds of members, or hundreds of thousands? Above a few thousand, the broadcast design is the only practical one; below that, a `community` channel might be acceptable for small private forums that want MLS properties and accept no pre-join history.
2. **Sysop reads.** Is "the CO can read the board" acceptable? If not, §3.4 (server index) and content-based moderation are out, and boards depend on clients syncing full history.
3. **History policy.** Today a currently permitted reader can fetch every past epoch's keys. Is "newcomers read everything" the right default, or does a board need a per-channel limit (for example, "only epochs since join")? The constraint-first answer is to keep today's behavior and not add a knob until a deployment needs one.
4. **Archive source.** 3.3 (a) long relay retention, or (b) a CO archive API?
5. **Pseudonymity.** Members see each poster's `senderDID`. Should boards recommend a per-Space DID for members who want a forum pseudonym, or is that out of scope?
