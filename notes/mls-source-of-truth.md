# MLS as source of truth: duplicated state in the spec

Scope: spec/ and ARCHITECTURE.md, checked against ARCHITECTURE S9 and the binding
decisions in `bd memories agora`. Analysis only; nothing in spec/ was edited.
RFC 9420 citations were checked against ~/PROJECT/IETF/specs/rfc9420.txt.

## Ranked summary

| # | Candidate | Payoff | Recommendation |
|---|-----------|--------|----------------|
| 1 | `DMGroupDescriptor` (members, loggers, host's user, consent model) | High: deletes a message type and a bug class already hit three times in review3 | (a) delete it; derive from the ratchet tree, move `consentModel` into a GroupContext extension |
| 2 | `DMMembers` at the DM admission host | High: the largest block of reconciliation text in the spec, plus a privacy cost | (c) put the admission key in the GroupContext so the host keeps no list; fallback (a) GroupInfo plus ratchet tree |
| 3 | `AddApproval` application messages (§4.6.1) | Medium: removes a split where members reach different policy verdicts | (c) drop DM add consent; fallback (a) approvals as a custom proposal inside the Commit |
| 4 | `SpaceMembership` record with `v` counters in the self-group (§2.6) | Medium-low: deletes a hand-built merge rule | (a) hold it as a self-group GroupContext extension |

Item 1 includes a live bug that should be fixed whatever is decided: 07:276
checks for the logger in the descriptor, while 07:314 checks the MLS membership.

---

## 1. `DMGroupDescriptor`

**Location.** spec/04-access-control.md:198-218, :220, :261-268; 07-compliance.md:219,
:276, :298; 06-calls.md:465; 05-messaging.md:373; 99-appendices.md:99, :137.

> 04:218 "`members` is the current member DID list. `complianceLoggers` is the list of
> `ComplianceLogger` DIDs that have been admitted to the group under §7.8. ... The
> committer of each membership or logger change sends the updated descriptor to the
> group as an MLS application message ..."

> 07:276 "Each regulated member's client MUST verify on group join that their Space's
> logger DID is present in this array, and add it if absent."

**What is duplicated.** Every field is either MLS state or derivable from it:

- `members`: the DIDs in the leaf credentials of the ratchet tree.
- `complianceLoggers`: the leaves whose DID document carries an
  `AgoraComplianceLogger` service (07:64-83). A regulated client needs only to know
  whether its own Space's `loggerDID` has a leaf, which it reads from the tree.
- `mlsGroupID`: the group it is sent in. 04:220 adds two rules (ignore on mismatch,
  leave on a mismatching first descriptor) that exist only because the field exists.
- `createdBy` / `admissionHostDID`: used only to define the "host's user" (04:261).
  The host's user can be derived: a member whose identity host (the origin of its
  `KeyPackageEndpoint`, §5.2.1.1) equals the origin in `agora_admission_host`.
- `consentModel`: real application state, but it must be identical at every member,
  which is what the GroupContext gives (RFC 9420 §8.1, §12.1.7).
- `created`: informational; nothing reads it.

The descriptor is authenticated only by its sender's MLS signature and any member may
send one, so members can hold different versions. That is the bug class:

- CRY3-6 (notes/review3/CRY3.md:44-51): any member can name anyone as
  `admissionHostDID` and steer the handover check.
- CRY3-7 and FIXCHECK (FIXCHECK.md:34-38): the same-host shortcut sends only a
  descriptor, so other members, seeing no Commit, move the group anyway. The fix added
  "lowest leaf index wins" rules for competing descriptors (04:268).
- 07:276 (current text): a joiner trusts the descriptor for logger presence. A member
  can send a descriptor that lists a logger it has already removed, and the joiner
  never saw the Remove. 07:314 states the correct rule ("whose current MLS membership
  lacks the Space's `loggerDID`"); the two lines contradict each other.
- `consentModel` divergence: two members holding different descriptors judge the same
  Add differently under §4.6.1 (see item 3).

**MLS mechanism.** Ratchet tree leaf credentials (RFC 9420 §4, §5.3, §7.3) give
membership. A new private-use GroupContext extension, `agora_dm_consent` (for example
0xF0A1, listed in `required_capabilities`, §11.1), carries the consent model. Any
member changes it by a GroupContextExtensions proposal (§12.1.7), which fits "no
member has authority" (04:241). A joiner receives the GroupContext in the Welcome
(§12.4.3.1), so it needs no first descriptor.

**Spec text.** Deleted: the schema and paragraph at 04:200-218; the descriptor rules
at 04:220; every "sends the updated `DMGroupDescriptor`" (04:198, :266, :268, :316;
07:219; 06:465); the `admissionHostDID` paragraph and the descriptor-competition
rule at 04:261 and :268; the 05:373 and 99:137 rows; the descriptor clause in the
99:99 timer row. Added: one sentence defining the host's user from the tree and
`agora_admission_host`; the extension definition (about 4 lines); 07:276 rewritten
to "present in the group's ratchet tree"; `DMComplianceAuditEntry.dmGroupDescriptorCID`
(07:298) replaced by `epoch` plus the GroupContext `tree_hash`, which the logger
holds as a member.

**Binding decisions.**
- Any-member removal, any-member host move: unchanged.
- Same-host handover (agora-dm-same-host): the shortcut becomes a no-op. If the
  remaining member is served by the current host, it is already the host's user and
  there is nothing to record. The 24-hour fallback then fires only when no remaining
  member is served by the current host, which is the right trigger.
- Logger never removable at host, FC-1, FC-2: not touched.

**Privacy.** No new party learns anything. The descriptor travelled only inside the
group; the tree is already there.

**Feasibility caveat.** Deriving the host's user needs each member's DID resolved to
its `KeyPackageEndpoint` origin. Clients already resolve member DIDs for the
credential binding (§5.2.1). A member that moves its identity host stops being the
host's user, which is also when the 30-day rule (04:274) stops counting it.

**Options.**
- (a) Delete the descriptor as above. Recommended.
- (b) Keep it but strip `members`, `complianceLoggers` and `mlsGroupID`, and make
  `admissionHostDID` valid only in the epoch of a Commit that set
  `agora_admission_host` (CRY3-6's first fix). Leaves the consent divergence.
- (c) Status quo, fixing only 07:276.

**Plain language.** The group's own encryption state already records who is in the
conversation, so a separate "who is here" message that anyone can send is a second
copy that can be wrong. Deleting it removes the copy and the bugs that came from
copies disagreeing.

---

## 2. `DMMembers` at the DM admission host

**Location.** spec/04-access-control.md:163-196, :265, :270, :274, :316;
07-compliance.md:217, :244, :288; 06-calls.md:465; 05-messaging.md:36, :394;
12-security.md:69-70, :245, :253; ARCHITECTURE.md:64, :264-268, :492-496.

> 04:194 "`seq` is an unsigned integer equal to the MLS epoch in which the listed
> membership takes effect ... the host accepts a `DMMembers` if its signature
> verifies, its `ts` is within 300 seconds ..., its `seq` is greater than that of the
> current list, it keeps every `complianceLoggers` entry ..."

> 04:196 "A client whose PUT is answered `403` or `409` fetches the current list,
> recomputes the list from its MLS membership, and retries ... A member that finds on
> the host's list a DID with no leaf in the group ... sends a list without it ..."

**What is duplicated.** A member list and an epoch counter (`seq`), updated by
client PUTs and reconciled with the tree by: PUT only after a win, 204 before the
Welcome (also 05:36), empty-Commit correction (FC-2), 403/409 recompute and retry,
lost-Add cleanup, stale-DID scrub, and backoff. S9 as written forbids this list.

**Why the host has a list at all.** It serves the admission key only to current
members (04:172) and rotates on removals. So the list exists to answer one question:
who may fetch the key.

### Option (a): signed GroupInfo plus public ratchet tree

The member PUTs an `MLSMessage` carrying a GroupInfo (RFC 9420 §12.4.3) with the
`ratchet_tree` extension (§12.4.3.3) and without `external_pub`, so it cannot be
used for an external join (§12.4.3.2).

What a non-member can verify with public keys only. RFC 9420 already defines this
check for joiners (§12.4.3.1, steps after decryption) and for external committers:
- the tree hash matches `group_context.tree_hash` (§7.8);
- every non-blank parent is parent-hash valid (§7.9.2);
- every leaf is valid (§7.3), including its credential, which for Agora means the
  §5.2.1 binding to a current DID `authentication` key (DID resolution needed);
- the GroupInfo signature verifies under the leaf at index `signer` (§12.4.3).

What it cannot verify: the `confirmation_tag` needs `confirmation_key`, an epoch
secret. So the host learns "a holder of leaf `signer` signed this tree for epoch E".
It does not learn that E is canonical, that the tree follows from the previous one
by valid Commits, or that any other member agrees.

Forgery by one malicious member. It can build a valid-looking tree for any epoch
number: its own leaf, other members' leaf nodes copied in place (an update- or
commit-sourced LeafNode signs `group_id` and `leaf_index`, §7.2, so it must stay at
its index; that is enough to drop members), KeyPackage-sourced leaves for anyone
whose KeyPackage it fetched (to add them), and all parent nodes blank (blank parents
are valid). It signs as itself. The host must keep today's rule that the signer's
DID is a member in the state the host already holds, or the forger could also sign
a tree containing only itself after being removed.

Compared with today: equal trust. Today any listed DID can PUT any list with any
higher `seq`. Under (a) the same DID can PUT any tree with any higher epoch. Both let
one member freeze the host with a huge epoch; the remedy in both is a host move. The
one gain: every DID on the host's view has a leaf signed under its own key, so a
member can no longer list a DID with no KeyPackage. The fake-logger limit
(12-security:69) is fixed only if the host also checks the logger's DID document for
`AgoraComplianceLogger` (07:64), and that check works equally under today's design.

What disappears: the client computing a list, the stale-DID scrub, the
`complianceLoggers` field (replaced by a host-side sticky set of logger DIDs ever
seen in an accepted tree, so "never removable at host" still holds). What stays:
PUT after win, 204 before the Welcome, FC-2's empty Commit (a correct GroupInfo for
the same epoch as a wrong one is still refused), 403/409 retry, FC-1 creation.

Privacy cost: today the host learns member DIDs and the epoch. Under (a) it also
learns each member's device count (leaves), leaf key churn and timing (activity
pattern), tree size, and all GroupContext extensions. That includes members it does
not serve. Bounded by sending only when the DID set changes, but each snapshot still
shows devices.

Implementation cost: the host must run MLS tree validation and resolve every member
DID. Libraries that support external joins already do the first part.

### Option (c): admission key in the GroupContext; host keeps no list

The host stops serving members. It generates the key, registers it with IOs as now,
and gives it to its own user's client. That client commits a GroupContextExtensions
proposal (§12.1.7) carrying `agora_admission_host` together with a new
`agora_admission_key` extension (seed, `keyEpoch`, `relays`). Members read the key
from their GroupContext; a new member gets it in the Welcome (§12.4.3.1); a removed
member never sees the next epoch. On any Commit that removes a DID, the host's
user's client fetches a fresh key from its host and commits the rotation. A host
move is the same GCE with a new host and key in one Commit.

Deleted: the `/members` GET and PUT, the `DMMembers` type and its acceptance rules,
"Keeping the list" in full (04:196), FC-2, the 204-before-Welcome ordering (05:36
DM clause), the handover squat (12-security:70) and the host side of FC-1 (the host
holds nothing per group to refuse), the request-state carve-out for authenticating to
the host (04:251, :253; 07:288), and the `/admission-key/<groupID>/<keyEpoch>` GET
(members keep old GroupContexts).

Added: the extension (about 5 lines); "the host's user rotates after a Commit that
removes a DID"; deregistration on its user's request, or 30 days after its user is
offboarded (§2.5.6).

What it proves and to whom: the key is agreed MLS state, so every member at an epoch
has the same key, and only members have it. Handshake messages are `PrivateMessage`
(05:73), so relays never see the extension.

Open issues to decide:
- A member could commit a GCE installing a key no relay has registered. Under
  agora-commit-authz this is MLS-valid and judged afterwards as a policy violation,
  which ends the group. This is no new power: under agora-dm-removal any member can
  already remove everyone. If wanted, the host can sign the key record and members
  check it after the fact.
- Rotation waits until the host's user's client is online. Today it happens when the
  remover PUTs. In the gap a removed member can post envelopes that members discard
  (the cost already accepted in 12-security:68).
- Compliance records carry `groupContext` (07:140), so the logger's archive holds the
  DM admission seed. The logger already fetches that key today, so nothing new is
  exposed.

Binding decisions affected: agora-dmmembers-seq, agora-dm-correction (FC-2),
agora-dm-creation (FC-1) and agora-dm-same-host are superseded. "Logger never
removable at host" loses its mechanism but keeps its goal: a removed logger is
re-added by Welcome, and the Welcome carries the current key, so it needs no relay
access in between. agora-dm-host-move and agora-dm-host-keyepoch carry over
unchanged in meaning. agora-doorkey-B holds (the key is still CO-issued and
registered). Needs Mark's decision.

Privacy: a large gain. The host learns only that its own user asked for keys for a
group ID, and when. 12-security:245 ("who is in the DM ... including members it does
not serve") and ARCHITECTURE:492-495 ("it knows the members by DID") no longer hold.

### Option (b): keep `DMMembers`, carve an S9 exception

S9 gets one sentence naming the DM admission host's list as an access cache rebuilt
from MLS on conflict. No spec change otherwise. Keeps all the reconciliation text and
its review churn.

**Recommendation.** (c). It deletes the most text, removes three review3 bug
families at the root, and improves privacy. If Mark wants to keep the host-side
logger rule as is, take (a) over (b): it satisfies S9 and removes the client-side
list computation, at the cost of host-side tree validation and device-level leakage
to the host.

**Plain language.** Today a server keeps its own copy of who is in each private
conversation and members must keep correcting it. The fix is to put the "door key"
inside the conversation's own encrypted state, so whoever is in the conversation
has the key and the server needs no list.

---

## 3. `AddApproval` application messages (§4.6.1)

**Location.** spec/04-access-control.md:230-234; 05-messaging.md:375; 04:141.

> 04:232 "Each member MUST check, when it processes the Commit, that the approvals it
> has received for that Add meet the model; an Add committed without them is a policy
> violation (§4.5)."

**What is duplicated / the bug.** Approval is an MLS-group decision kept outside the
Commit. Members that received different approval messages (delivery is best-effort,
5.1.1) reach different verdicts on the same Commit: some leave the group as a policy
violation (04:141), some stay. The `consentModel` threshold also comes from the
descriptor, which members may hold in different versions (item 1).

**MLS mechanism.** RFC 9420 §12.2: "An application may extend the above procedure by
additional rules, for example, requiring application-level permissions to add
members, or rules concerning non-default proposal types." Define a private-use
proposal type `AddApproval { ProposalRef add; }` (§13.2, §17.4; listed in
`required_capabilities`). Approvers send it as a proposal; the committer includes
the Add and its approvals by reference. Every member then evaluates the same
proposal list, so an under-approved Add is an invalid Commit for everyone, not a
group-ending policy violation. This fits agora-commit-authz ("winner chosen by MLS
validity only") because the rule depends on nothing outside the Commit. A member
missing a referenced proposal cannot process the Commit and fetches it, which fails
the same way at every member rather than diverging.

**Alternative constraint.** agora-dm-removal says DM membership is "deliberately
uncontrolled"; any member can remove anyone without consent. Add consent sits oddly
with that: it delays an Add but does not stop an unwanted member being added through
a cooperating majority, and members can remove or leave afterwards. Deleting it
removes §4.6.1, the `AddApproval` type, `consentModel`, and the consent case of the
policy-violation rule.

**Options.**
- (a) Custom proposal as above. Needs library support for custom proposals.
- (b) Keep application-message approvals; move `consentModel` to the GroupContext
  (item 1). Halves the divergence; delivery skew remains.
- (c) Drop DM add consent. Controlled membership already means a private Space
  channel (04:243).

**Recommendation.** (c), matching the removal decision. If Mark wants consent, (a).

**Privacy.** None of the options changes who learns what.

**Plain language.** Today each person's app counts "yes" votes it happened to
receive, so two apps can disagree and the group breaks. Either the votes go inside
the change itself, so every app counts the same votes, or, since anyone can already
remove anyone, the vote is dropped.

---

## 4. `SpaceMembership` record in the self-group (§2.6)

**Location.** spec/02-identity.md:508, :512-527; 05-messaging.md:379.

> 02:527 "A receiving device merges a record into the one it holds entry by entry,
> keyed by `space`, keeping the entry with the higher `v` (on equal `v`, `left` wins,
> then the lower `spaceEndpoint` list compared element by element ...)."

**What is duplicated.** Ordering. The self-group's devices need one agreed list; the
spec builds a per-entry version counter, tombstones and a three-level tie-break,
plus an ordering constraint on adding a device (02:508 step 3: send the record
before adding the device elsewhere). MLS epochs already order agreed group state.

**MLS mechanism.** A self-group GroupContext extension `agora_space_membership`
holding the list, changed by GroupContextExtensions (§12.1.7) and resolved by the
canonical-Commit rule like any Commit. A new device gets it in its self-group Welcome
(§12.4.3.1), so step 3's ordering constraint and the `left` tombstones go away (no
merge, no stale record to resurrect). Handshake messages are `PrivateMessage`
(05:73), so nothing new leaves the group.

**Cost.** One self-group Commit per Space join, leave or endpoint change; a user in
100 Spaces carries roughly 15 KB in the GroupContext, sent only in GCE proposals and
Welcomes. A losing concurrent change is re-proposed, which in a group of one user's
devices is rare.

**Options.** (a) GroupContext extension. (b) Keep the record but drop `v` and resolve
by MLS epoch of the message carrying it (still needs a rule for two records in one
epoch). (c) Status quo.

**Recommendation.** (a). Not urgent; it is correct today, just larger than needed.

**Binding decisions, privacy.** None affected; the data stays inside the self-group.

**Plain language.** A user's own devices keep a list of the user's communities and
today need a custom rule to settle disagreements. Storing the list in the shared
encrypted state of the devices' private group means they always agree, and a new
device gets the list when it joins.

---

## Checked and not duplicated

- **Sequencer (§5.1.1, §14.4).** Agree. RFC 9420 §14 puts Commit ordering in the
  delivery service; the sequencer is that role, holds no MLS state, and reads nothing.
- **Relay admission and `keyEpoch` (ARCHITECTURE:253-275, §5.2.2).** Agree. Relays
  must not see MLS epochs (S1), so tokens rotate on `keyEpoch`, a counter of admission
  keys, not of group state. Under item 2 option (c) the `keyEpoch` moves into the
  GroupContext but keeps this meaning.
- **Space roles and policy (`members`, admins, `commitPolicy`; 03:72, :179).** Agree.
  Space `members` is an authorization list (S4); a Space has members not in a given
  channel's group (03:28). The §4.8 coupling (a self-Remove in the Space group prompts
  the CO to update `members`) is the CO acting on MLS data, which S9 permits.
- **Compliance logger non-removability (§7.8.3).** Agree. Client-enforced policy on
  which Removes to commit; it does not track membership separately.
- **Per-sender `seq` (§5.1.1).** Not a duplicate. MLS generations (§9) reset each
  epoch and sit in encrypted sender data; Agora's `seq` spans epochs for gap detection.
- **`ParticipantState` (§6.2-6.3).** Not a duplicate. Call presence is not group
  membership, and 06:50 says so.
- **`CallBreakout.rooms[].members` (06:598).** Not a duplicate. It assigns people to
  rooms; the room group may hold more members.
- **Own-device Adds (02:510).** Already derived from the credential DID and the tree.
- **Chat membership in JMAP (14-jmap:61).** Already marked "derived" from MLS.
- **Message-request display (04:251).** Already reads members from the Welcome's tree.
