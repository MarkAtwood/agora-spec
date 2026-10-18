# FUND5: FUNDING.md and README.md claims review

Scope: FUNDING.md and README.md, checked against ARCHITECTURE.md, spec/, profiles/, guides/, test-vectors/, and notes/review*/.

Summary: 9 findings, 5 P2 and 4 P3.

Verified correct, no finding:

- "9 normative rules": ARCHITECTURE §3 defines S1 to S9.
- "14 parts plus appendices": spec/01 to spec/14 plus spec/99-appendices.md. The 13 topics FUNDING lists match parts 2 to 14.
- "4 full review rounds": notes/review, review2, review3, and review4. Round 4's FINALCHECK FN-1 fix is present at spec/04-access-control.md:91. I did not re-check every earlier finding against "every finding fixed or decided".
- "11 vector files", "two independent cryptographic implementations": test-vectors/ holds 11 JSON files. test-vectors/README.md documents the Python and Go toolchains, which share no code.
- "12 deployment profiles": profiles/ holds 12 files. README's profile list names all 12 and nothing else.
- "3 operator guides": guides/relay-operator.md, regulators.md, and counsel.md.
- OpenVTC "four connections", "no change to the core protocol", "same default DID method" (`did:webvh`, spec §2.1), "personal agent as one of the user's devices", and "OpenVTC has no calls" all match profiles/dtg-openvtc.md §1, §3, §5, §6, §7, and §9.
- Community moves without losing members or history: ARCHITECTURE S5. CO ownership change: guardian transfer, spec §4.1.

### FUND5-1: "Blind relays" and the subpoena claim overstate what an IO learns
Severity: P2 (misleading)
Location: FUNDING.md:29-31, FUNDING.md:82-84
Evidence: FUNDING says relays "never learn a group's members, name, or content" and that a relay operator under subpoena "can truthfully say it holds nothing useful". ARCHITECTURE §4 says a demand on an IO yields "connection metadata within its retention window, opaque ciphertext, routing tokens". ARCHITECTURE §9 accepts the following costs:
- a `keyAccess: public` broadcast token is mapped to its named Space and billing DID;
- push links a device's tokens across sessions and network addresses;
- an IO can infer removals;
- under legal demand an IO "can produce which network addresses used a given CO's service".
Lines 29-31 also say an IO does not learn "what a group is called", which is false for public broadcast channels.
Fix: Replace the subpoena sentence with the ARCHITECTURE §4 wording: "A relay served with a subpoena can produce connection metadata, routing tokens, and ciphertext, but not who is in a community or what they said." Add "except channels a community chooses to make public" to the group-name clause.

### FUND5-2: "Without being able to tell them apart" contradicts the accepted costs
Severity: P2 (misleading)
Location: FUNDING.md:37-38
Evidence: "A server operator can carry many communities without being able to tell them apart." ARCHITECTURE §9 says "Space anonymity at the IO is only as large as the CO. A CO with one Space gets none." It also accepts several ways an IO can group or name traffic:
- it knows each CO's billing DID (ARCHITECTURE §8 Q6);
- it can cluster tokens by network address and by sequencer DID;
- it can link successive admission keys;
- it can map public broadcast tokens to a named Space.
Fix: "A server operator carrying a community's traffic learns its operator's billing identity, but not its members, its channels, or what is said."

### FUND5-3: "Already interoperates with OpenVTC" claims software that does not exist
Severity: P2 (misleading)
Location: FUNDING.md:150-152
Evidence: "Agora already interoperates with OpenVTC". README.md:12 says "No conformant implementation exists", and FUNDING.md:179 agrees. profiles/dtg-openvtc.md is "Draft, 2026-10-17, Version 0.1". FUNDING.md:195 lists "an OpenVTC interop demonstration" as Phase 3 work, so FUNDING contradicts itself.
Fix: "Agora is designed to interoperate with OpenVTC ... A deployment profile defines four connections, all on the spec as written:"

### FUND5-4: Compliance logger is described as "visible", and the capture-evasion cost is omitted
Severity: P2 (misleading)
Location: FUNDING.md:94-96; also FUNDING.md:66 ("Built in") and FUNDING.md:105 ("including DMs with outside parties")
Evidence: FUNDING says the logger "joins the group as a visible member ... everyone is told it is there". Spec §7.7 says clients SHOULD NOT show a join notification and that "the logger is UI-silent but not cryptographically hidden". Disclosure comes through the `retentionNotice`, the Space information panel, and, in DMs, the §7.8.4 notice. It does not come from seeing the logger as a member. Spec §7.8.9 and ARCHITECTURE §9 also accept that "a modified or non-conformant client can create or join a DM group without the logger", with managed endpoints as the mitigation. A funder in a regulated firm would read "Built in" as unconditional.
Fix: "a disclosed compliance logger joins the group as a member. Members are told of it through a retention notice and Space settings, and any client can verify it is present." Add to the regulated-firms row or the Risks table: "Capture of DMs relies on firm-managed devices; the logger records the gaps it can detect."

### FUND5-5: "Complete" and "independent review" contradict README and FUNDING's own deferred-items list
Severity: P2 (misleading)
Location: FUNDING.md:5, FUNDING.md:8-9, FUNDING.md:168, FUNDING.md:175, FUNDING.md:223
Evidence: FUNDING calls the specification "finished" and "complete" and says it "has passed four rounds of independent review". README.md:12 says "Status: draft specification." ARCHITECTURE §8 leaves Q1 open, and §6.2 marks the admission mechanism "pending external cryptographic review". Every profile is "Version 0.1 Draft". The notes/review* passes are the project's own review rounds. No external reviewer is recorded, and FUNDING.md:184 itself defers "an external cryptographic review of the admission-key design".
Fix: "The specification is feature-complete in draft and has been through four internal review rounds; external cryptographic review is the first funded step." Make the same change at lines 168, 175, and 223.

### FUND5-6: Attribute-bridging summary predates the attester model and overstates "never"
Severity: P3 (minor)
Location: FUNDING.md:139-143
Evidence: "lets public bodies and firms verify members against EU wallets ... then show other members only derived claims, never legal identity". In profiles/attribute-bridging.md §1 and §2.4, an attester verifies the source, either one the CO runs or a third party. The CO lists the attester's DID in Space state `trustedAttesters` (spec §3.3) and admits on its credential. Profile §2.1 lets raw attributes into a credential "unless the member asks for them", so "never" is too strong. The infrastructure-operator claim ("show infrastructure operators nothing") matches the profile.
Fix: "lets a community admit members on derived claims from attesters it lists, whether its own or a third party, that check EU wallets, US CAC and PIV smartcards, and enterprise directories. Other members see only the claims a member chooses to show, and infrastructure operators see nothing."

### FUND5-7: Deferred test-vector list is incomplete
Severity: P3 (minor)
Location: FUNDING.md:181-184
Evidence: The only deferred vectors listed are those "that need a working MLS stack". test-vectors/README.md "Not covered" also lists HPKE labels, which are missing because pyca/cryptography 41.0.7 has no HPKE and so there is no second toolchain. It also lists the Shamir share encoding and the WebAuthn `wrapKey` output. FUNDING.md:193 does put HPKE vectors in Phase 1, so only this list is stale.
Fix: "test vectors that need a working MLS stack or a second HPKE implementation;"

### FUND5-8: "Every ... key lives only on members' devices" ignores CO-held keys
Severity: P3 (minor)
Location: FUNDING.md:89-90
Evidence: "Every channel, DM, and call key lives only on members' devices." For broadcast channels, the CO generates the content key and serves it from the Space endpoint (spec §3.4, `BroadcastKey`). The CO registration service also generates and holds every channel admission private key (ARCHITECTURE §6.2). This fits the model, since the CO is not infrastructure, but the sentence as written is false.
Fix: "Every channel, DM, and call encryption key derived from MLS lives only on members' devices; no infrastructure operator holds any."

### FUND5-9: README layout table omits test-vectors/ and misses a serial comma
Severity: P3 (minor)
Location: README.md:14-27, README.md:23
Evidence: test-vectors/ is a top-level directory that FUNDING.md:176 cites ("11 vector files"), but the Layout table has no row for it. The notes/ row says "Research and backport inventory", but notes/ also holds the review rounds behind FUNDING's "4 full review rounds". In README.md:23, the top-level profile list ends "gateways to other networks (Matrix, Slack, Teams) and the path to native ... (MIMI)" with no serial comma before "and".
Fix: Add the row `| test-vectors/ | Test vectors computed by two independent toolchains, with generators | no |`. Change the notes/ description to "Research, backport inventory, and review rounds". Insert a comma before "and the path to native".
