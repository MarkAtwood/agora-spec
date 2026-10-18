# SPEC5: review of spec changes since 33d5565

Scope: `git diff 33d5565 -- spec/ ARCHITECTURE.md` (7cd5949 format-rule verification in §5.2.1.5; 2c5714d `trustedAttesters` in §3.3, §5.2.1.5, Appendix C/D; c35d1b9 ARCHITECTURE §2.3 personal-agent sentence).

Checked and clean: § references in the new text resolve (§4.4 defines the non-member view; §2.6, §3.3, §5.2.1.5, §8.6, §12.13 exist). The guest view omits the list (§3.3, §8.6), and the list does not apply to a shared channel from the guest Space side ("the channels of other Spaces"). Calls (§6) use channel or DM groups, so the group enumeration is complete. The list lives only in the members' chain at the CO's Space endpoint (§3.4), so no IO sees it (S1, S4). The ARCHITECTURE sentence is consistent with the key test in §2.3. The over-limit rule matches Appendix C. No BCP 14 language on UX, no em dashes, and serial commas are correct in all added text. The 7cd5949 Data Integrity wording is fine.

### SPEC5-1: Issuer identifier and issuing key are undefined for the trustedAttesters match

Severity: P2

Location: spec/03-spaces.md §3.3 (`trustedAttesters` paragraph); spec/05-messaging.md §5.2.1.5 Binding

Evidence: §3.3: "when the entry's issuer identifier equals a listed DID as an exact string, its signature verifies under a key in that DID's document". §5.2.1.5 defines extraction for the subject only: "The verifier extracts the subject by the rules of the entry's format, for example `credentialSubject.id` of a W3C VC or `sub` of an SD-JWT VC". No rule in spec/ defines "issuer identifier", and none names a verification relationship (`assertionMethod` appears nowhere). §2.2 puts every device key in the DID document: "**`authentication`** keys: the Ed25519 device keys (§2.2), one per device", and the recovery key is in the document under `recoverableIdentity` (§2.4.1).

Problem: Implementers will extract the issuer differently. A W3C VC `issuer` can be a string or an object whose `id` is the DID, and a JOSE- or COSE-secured VC or an SD-JWT VC also carries `iss`. One client compares the object form's `id` and another compares the raw member and fails, so the same leaf shows as trusted on one client and untrusted on another. "A key in that DID's document" also lets a credential signed by any device `authentication` key, or by the recovery key that "is never used for normal protocol operations", pass, while a client following VC convention requires `assertionMethod`. Under the loose reading, any device or hosted agent of a listed DID can mint credentials that members' clients trust.

Fix: In §5.2.1.5 Binding, after the subject sentence, add: "The verifier extracts the issuer identifier by the rules of the entry's format in the same way, for example `issuer`, or the `id` of an `issuer` object, of a W3C VC, or `iss` of an SD-JWT VC, and accepts a signature only under a key that the issuer's DID document lists under `assertionMethod`." In §3.3, change "under a key in that DID's document" to "under a key listed under `assertionMethod` in that DID's document (§5.2.1.5)".

Needs decision: no

### SPEC5-2: No rule says who may change trustedAttesters

Severity: P2

Location: spec/03-spaces.md §3.3 (`trustedAttesters`, `admins`); spec/04-access-control.md §4.1

Evidence: §3.3 `admins`: "`["*"]` covers the whole Space, including Space-level mutations other than those reserved to the owner (§4.1)." §4.1: "The Space owner has sole authority to ... sign Space state mutations affecting top-level structure." §3.3: "Clients MUST reject Space or channel state that is not signed by the owner or by an admin authorized under the prior state." `guardian` and `admins` each say "Only the owner may change"; the `trustedAttesters` paragraph says nothing.

Problem: `trustedAttesters` is literally a top-level member of the document, but so are `members` and `roles`, which admins change (§4.2), so "top-level structure" does not decide the question. One client treats a `["*"]` admin's change to the list as valid and another rejects the state under the MUST above, which splits the members' view of Space state. The list is a trust anchor, which makes the answer security-relevant: whoever can change it can make any issuer's claims show as trusted to every member. The same gap exists for other Space-level fields (`sequencer`, `pushProxy`, `acceptedDIDMethods`), but that predates this change and is not reported here.

Fix: Add one sentence to the `trustedAttesters` paragraph that names who may change the list (see options), with the same "Clients MUST reject a state document that changes `trustedAttesters` and is signed by neither ..." form used for `admins`.

Needs decision: yes. Options: (A) the owner or an admin whose scope is `["*"]` may change it; (B) only the owner may change it, as for `admins` and `guardian`. Recommendation: A. A `["*"]` admin can already assign roles based on credentials (§4.2) and change every other Space-level field, so option B adds no real protection and would keep the attester list out of an operator's routine admin workflow.

### SPEC5-3: §5.2.1.5 states the list's scope more broadly than §3.3

Severity: P3

Location: spec/05-messaging.md §5.2.1.5 Verification and trust

Evidence: §5.2.1.5: "In the groups of a Space, a client MAY also trust the issuers that the CO lists in the Space's `trustedAttesters` (§3.3)". §3.3: "the leaf carrying it is in the group of a channel whose home Space is this Space, or in the Space's own group. The list applies to no other group: not to DM groups, self-groups, or the channels of other Spaces."

Problem: Neither section defines "the groups of a Space". A guest Space shows the shared channel in its sidebar through `sharedChannels` (§8.5), and §4.8 talks about leaving "every group of the Space". A reader of §5.2.1.5 alone can therefore apply a guest Space's list in a shared channel, which §3.3 forbids.

Fix: Replace "In the groups of a Space" with "In the groups to which §3.3 applies it".

Needs decision: no

### SPEC5-4: §4.2 and §12.13 still say issuer trust is purely the client's own

Severity: P3

Location: spec/04-access-control.md §4.2 (last paragraph); spec/12-security.md §12.13

Evidence: §4.2: "Which issuers and claims qualify is the CO's policy, and the admin's client applies it. Space state carries no credential policy." §12.13: "relies on its own trust policy" and "a compromised issuer key, which is the trusting client's risk."

Problem: Space state now carries `trustedAttesters`, a CO-published issuer list, so "Space state carries no credential policy" is false. §12.13 never says that a client following the list takes on the risk of issuers the CO chose, or that a compromised owner or admin key can add an issuer.

Fix: In §4.2, replace "Space state carries no credential policy." with "Space state carries no credential policy beyond the issuer list `trustedAttesters` (§3.3)." In §12.13, append: "A client that follows a Space's `trustedAttesters` (§3.3) also relies on the CO's choice of issuers, and on the keys that may change that list."

Needs decision: no
