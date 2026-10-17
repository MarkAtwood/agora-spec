# Triage check: commit a3e5b66

Scope: `git diff HEAD~1 HEAD` checked against `notes/copyedit-defects-triaged.md` (fixes 1-90, D1-D13 with all choices A except D7=B and D11=B), plus the resolved facts for fix 10 (named OneLogin events, IDs looked up via `GET /api/1/events/types`, only ID 4 fixed) and fix 11 (`draft-ietf-webtrans-http3-16`).

Result: every section 1 fix and every decision landed as specified, except D10 (TC-4). The diff adds no em dashes. Tables, JSON, and fenced blocks are well formed, including the re-indented list items in spec/05 and spec/07. Every BCP 14 change traces to a fix or decision. The normative content removed from spec/10 §10.2 by fix 3 remains in §10.2.2, and the duplicate MUSTs removed by fixes 16 and 72 remain at spec/13 §13.1.1 and universal-idp §4.4. All new § references resolve and say what the new text claims: spec §6.9, §6.10, "SFU Media Opacity", §7.2, §7.3, §7.6, §7.8.4, §7.9, §10.2.5, §10.2.6, §10.3.5, §10.5.1, §10.5.3, §12.6; relay-operator §5.2 and §10.3; o365 §6.7; purview §2.3 and §9.2; discord §5.4; gsuite §2.2; radio-mesh §5.1.

Counts: P1 0, P2 1, P3 4.

### TC-1

**Severity:** P2

**Location:** spec/03-spaces.md:166 and :168 (D2)

**Evidence:** New text: "Clients MUST reject a state document that changes `guardian` and is not signed by the owner." The same rule is added for `admins`. spec/03-spaces.md:160 lists the guardian transfer documents as exceptions to the signer rule: "a completion signed by `pendingTransfer.newOwner` after `ts + delaySeconds`." spec/04-access-control.md §4.1 adds: "A completion SHOULD also replace `guardian` if a guardian was involved in the loss."

**Problem:** A completion is signed by `newOwner`, who is not the owner under the prior state. Read against the prior state, the new MUST requires clients to reject exactly the completion that §4.1 says SHOULD replace `guardian`. Read against the document's own `owner`, it would instead accept the completion but reject an ordinary ownership transfer that also changes `admins`. "The owner" does not say which state it is taken from, so clients can diverge on the same document.

**Fix:** In both sentences, replace "and is not signed by the owner." with "and is signed neither by the owner under the prior state nor, in a guardian transfer completion, by `pendingTransfer.newOwner` (§4.1)."

### TC-2

**Severity:** P3

**Location:** profiles/parlance.md:68

**Evidence:** "Interactive MLS groups cap at 200 members (spec §5.2.1, `interactive` mode)." Under D6, spec/05-messaging.md:61 now reads: "Intended for up to about 200 members; the only enforced limit is the 4096-leaf cap below."

**Problem:** After D6 the profile cites a cap that the spec no longer sets.

**Fix:** "Interactive MLS groups are intended for up to about 200 members (spec §5.2.1, `interactive` mode)."

### TC-3

**Severity:** P3

**Location:** profiles/discord-onboarding.md:101 and :415; spec/10-relays.md:510-512

**Evidence:** Fix 44 changed the spec/02-identity.md §2.1 table to `_agora`, `_kp._agora`, and `_profile._agora`. The discord profile still says "with `_kp._agora.` set to the `KeyPackageEndpoint` URL" (101) and "the `_kp._agora.` field of the verified Pkarr record" (415). The spec §10.3.4.6 record-format block still lists `_agora.`, `_profile._agora.`, and `_kp._agora.`.

**Problem:** After fix 44, the same Pkarr record names appear in two forms. In master-file syntax a trailing dot makes a name absolute, but these names are relative to the key's zone.

**Fix:** Drop the trailing dot in discord-onboarding.md:101 and :415 and in the three owner names at spec/10-relays.md:510-512.

### TC-4

**Severity:** P3

**Location:** D10 (style sheet §4)

**Evidence:** D10 A adds to style sheet §4: "Exception: examination request lists and examiner checklists in guides/ stay numbered so items can be cited." The commit changes no style sheet. No tracked file holds the style sheet: `git ls-files | grep -i style` matches only the triage note, and the only style item in `bd memories` is `agora-style-serial-comma`.

**Problem:** The decision is not recorded. A later style pass could still convert regulators.md Parts 3 and 4 to bullets.

**Fix:** Add the exception wherever the style sheet lives, which is likely a bead or decision record outside this commit's file set. The lead should confirm the location.

### TC-5

**Severity:** P3 (unverified)

**Location:** profiles/universal-idp-did.md:224 and :228

**Evidence:** The poll is `GET https://api.us.onelogin.com/api/2/events?event_type_id={ids}&since={cursor}`. The new text has the deployment call `GET /api/1/events/types`.

**Problem:** I believe OneLogin's Events API exists only as v1 (`/api/1/events`), so the poll path may not exist. I did not check this against OneLogin's documentation. The `/api/2/` path predates this commit, but fix 10 now puts it next to a v1 call.

**Fix:** Check OneLogin's documentation. If it confirms that events are v1 only, change line 224 to `/api/1/events`.
