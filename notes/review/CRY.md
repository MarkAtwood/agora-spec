# CRY review: MLS (RFC 9420) and cryptographic correctness

Reviewer lens: CRY. References checked against local copies of RFC 9420 and
RFC 9605 (/home/mark/PROJECT/IETF/specs/). Items that only need the pending
external review (agora-pozi.8) are not listed as defects. Every finding below is
a gap in the text itself, or a claim the text contradicts.

### CRY-1: No canonical-Commit rule, and the countersignature does not prevent the lockout it was added for
- Severity: P1
- Location: spec/05-messaging.md:203-205, spec/05-messaging.md:23, spec/04-access-control.md:16, ARCHITECTURE.md:196-201
- Evidence: "The service countersigns only an announcement requested by a DID it authenticates as a current member of the channel under Space state, and at most one announcement per chain and `epoch`." / "The countersignature exists because the previous epoch's access private key is also held by a member being removed, who could otherwise announce a key only they know, keep relay access, and lock out the remaining members." / "Relays MAY provide **sequence attestations** ... as an optional ordering anchor"
- Problem: (a) RFC 9420 §14 says "Applications MUST have an established way to resolve conflicting Commit messages for the same epoch" and says the Welcome "MUST NOT be delivered ... until it's clear that the Commit has been accepted". Agora gossips Commits with no ordering authority and has no rule for this. The committer also POSTs the Welcome straight away (§4.6, §5.2.1). (b) The registration service is not an MLS member, so it cannot check that the announced access public key is the one derived from `MLS-Exporter("agora access", …)` for the real next epoch. A member about to be removed is still a "current member under Space state", so it can be the first to request a countersignature for epoch N+1 with a key only it knows. The "one per epoch" rule then blocks the legitimate committer. That is exactly the lockout the text says the countersignature prevents. The same failure happens without malice when two honest Commits race and the service countersigns one while members adopt the other.
- Suggested fix: Make the countersigned announcement the definition of the canonical Commit. The announcement carries a hash of the Commit (and the epoch), clients MUST adopt only the Commit whose hash a valid `billingSig` announcement names, and a committer delivers Welcomes only after getting the countersignature. Every member MUST check that the announced access public key equals the one it derives after processing the Commit. On a mismatch, the member reports to the CO, and the CO's service re-registers a fresh chain with a new `AccessChainRegistration`. Also define what happens to losing Commits (they are discarded and their proposals re-sent).
- Needs decision: yes. Options: (A) the countersignature names the canonical Commit hash, plus member verification and CO re-registration on mismatch (recommended: fits the existing service, and the CO already knows membership); (B) the registration service is backed by a CO-run MLS member (like the logger) that derives the access key itself before countersigning (stronger, but puts a CO member in every group, DMs included); (C) restrict `commitPolicy` to a single committer per group (simple, but a single point of failure and it does not address a malicious committer).

### CRY-2: Sealed-envelope AEAD has no nonce rule, under a key shared by every member for the whole epoch
- Severity: P1
- Location: spec/05-messaging.md:214-220
- Evidence: "The sealing key is `MLS-Exporter(\"agora sealed envelope\", channelCID, Nk)`, used with the AEAD of the group's ciphersuite. The AEAD associated data MUST bind ..." (no nonce is defined anywhere; the `sealedEnvelope` byte layout is not defined either)
- Problem: Every member uses the same AES-128-GCM key for every message in the epoch. The text gives neither a nonce construction nor a wire layout. A per-sender counter, the natural choice for anyone used to MLS, would repeat (key, nonce) across senders, and GCM nonce reuse loses both confidentiality and integrity. Compare the broadcast payload (05:141-144) and the group-encrypted blob (03:190), which both specify a random nonce carried in the clear.
- Suggested fix: Define `sealedEnvelope = nonce || AEAD-Seal(key, nonce, MLSMessage, aad)`, where nonce is 12 bytes, freshly random for each message, and sent in the clear. Require a new epoch (an empty Commit) before 2^32 seals under one key, as §5.2.1.4 does for broadcast.
- Needs decision: no

### CRY-3: SFrame (base_key, KID, CTR) uniqueness is not guaranteed across streams or restarts; RFC 9605 §5.2 is misdescribed
- Severity: P1
- Location: spec/06-calls.md:160, spec/06-calls.md:410
- Evidence: "each sender's base key is derived from it and the sender's MLS leaf index, and the SFrame key identifier (KID) is built from the leaf index and the low bits of the MLS epoch"
- Problem: RFC 9605 §9.1: "Applications MUST ensure that each (base_key, KID, CTR) combination is used for at most one SFrame encryption operation", and the CTR must be persisted before use. RFC 9605 §5.2 provides the Context ID field of the KID ("to allow a single sender to send multiple, uncoordinated outbound media streams"). Agora leaves the Context ID out. A sender's audio, camera and screen-share tracks therefore share one KID within an epoch. Insertable Streams transforms run once per track, so in practice they keep separate counters, which reuses GCM nonces. A browser reload or reconnect in the same epoch also restarts CTR at 0 under the same key. Separately, the text describes the pre-RFC draft scheme ("epoch secret", per-index base key). The RFC itself uses one `base_key = MLS-Exporter("SFrame 1.0 Base Key", "", AEAD.Nk)` per epoch and derives per-KID keys from it.
- Suggested fix: Describe the RFC 9605 §5.2 derivation correctly, with only the label replaced. Require a distinct Context ID for each outbound track or data channel per sender. Require the CTR to be persisted per (epoch, KID) as in RFC 9605 §9.1, or, when CTR state is lost, require the client to commit an Update before sending again in the current epoch.
- Needs decision: no

### CRY-4: KeyPackage init keys are described as coming from the long-term DID `keyAgreement` key
- Severity: P1
- Location: spec/02-identity.md:44, spec/02-identity.md:74, spec/02-identity.md:314; also spec/06-calls.md:345, spec/12-security.md:95
- Evidence: "`keyAgreement` key: X25519 key used as the source for MLS `KeyPackage` init keys and for encrypting per-device payloads such as social recovery shares." / "X25519 keypair for `keyAgreement` (MLS key packages, HPKE)"
- Problem: RFC 9420 §10: init_key "MUST be unique among the set of KeyPackages created by this client". KeyPackages are single-use so that a Welcome's HPKE secret is protected with forward secrecy. Read literally, one long-term X25519 key is the init key for every Welcome, so compromising it decrypts every Welcome ever sent to that device. The same key is also used for social-recovery shares and recording-archive HPKE, which is key reuse across purposes. No derivation that would make "source" safe is defined.
- Suggested fix: State that init_key and leaf encryption_key are fresh, ephemeral HPKE keys generated per KeyPackage and unrelated to the DID document. Keep `keyAgreement` only for out-of-group encryption (recovery shares, archive sealing). Preferably also give each of those purposes its own HPKE `info` label.
- Needs decision: no

### CRY-5: Hardware-key requirements cannot be met for Ed25519/X25519 on major platforms, and the ES256 escape hatch contradicts the fixed algorithms
- Severity: P1
- Location: spec/12-security.md:89, spec/12-security.md:91, spec/12-security.md:74; spec/02-identity.md:255, spec/02-identity.md:316; spec/12-security.md:122, spec/12-security.md:147; vs spec/13-encoding.md:59 and spec/05-messaging.md:46
- Evidence: "P-256 (`ES256`) MAY be used as the authentication key algorithm for that device" / "**MLS leaf operations** ... MUST use keys held in the secure boundary" / "Private keys are generated inside the device's secure hardware boundary (Secure Enclave, StrongBox, TPM) and never leave it" vs "`alg` | `\"EdDSA\"`" and "All MLS groups in Agora MUST use `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519`"
- Problem: Apple's Secure Enclave supports only P-256, and TPM 2.0 generally has no Ed25519. Because the MLS leaf signature key must be Ed25519 (ciphersuite 0x0001) and JWS must be EdDSA, an ES256 device can produce neither, and a conformant iOS/macOS client cannot meet the unconditional "MUST use keys held in the secure boundary". The non-repudiation and organizational non-impersonation claims in §12.7 ("can only be produced by the specific hardware device") rest on this property.
- Suggested fix: Delete the ES256 MAY. Change "MUST use keys held in the secure boundary" to "where the platform supports Ed25519/X25519 in hardware". Otherwise use OS-protected software keys (Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`, or equivalent). Make §2.5.1 and §12.7 claim only what that delivers.
- Needs decision: yes. Options: (A) Ed25519 everywhere, with hardware where available and claims weakened to match (recommended); (B) add a P-256 MLS ciphersuite (0x0002) and ES256 JWS as a second profile (two code paths and two group types, against the single-suite decision); (C) a hardware P-256 key certifies a software Ed25519 key (complex, and the Ed25519 key is still in software).

### CRY-6: Nothing stops relays accepting previous-epoch access signatures, so a removed member keeps write access
- Severity: P2
- Location: spec/05-messaging.md:206-208, spec/10-relays.md:527
- Evidence: "Relays MUST verify `accessSig` against the access public key for the envelope's `channelToken` and `epoch`" / "A removed member does not hold the next epoch's access key, so bans and removals take effect at the relay through the MLS Remove alone."
- Problem: The removed member still holds epoch N's key and still knows epoch N's token. Unless relays stop accepting epoch N once a countersigned N+1 announcement is accepted, removal has no effect at the relay. No rule says when an old epoch is retired.
- Suggested fix: After accepting a countersigned announcement for epoch N+1, a relay MUST reject envelopes for epoch N or earlier on that chain, after a short fixed grace period (for example 60 s) for in-flight traffic. State that the grace period is the residual write window for a removed member.
- Needs decision: no

### CRY-7: The shared epoch access key signs several structures with no domain separation; the SFU admission proof is undefined and replayable
- Severity: P2
- Location: spec/05-messaging.md:203, spec/05-messaging.md:206, spec/05-messaging.md:368, spec/06-calls.md:111
- Evidence: "`accessSig` is an Ed25519 signature under the current epoch's access private key over the routing envelope with `accessSig` omitted" / "Client presents the MLS-membership access proof for the voice channel's `channelToken`"
- Problem: One raw Ed25519 key signs routing envelopes, `accessKeyAnnouncement`s (with the previous epoch's key), pin/unpin instructions and SFU admission. None of these carry a context prefix, and the SFU proof has no defined content or challenge. If the proof is an existing signed envelope, anyone who saw gossip can replay it to an SFU. If it is a signature over SFU-supplied bytes, the SFU (an IO) has a signing oracle and can, for example, obtain a valid unpin instruction.
- Suggested fix: Prefix every message signed with the access key with a distinct context string ("agora/access/envelope/v1", "agora/access/announce/v1", "agora/access/pin/v1", "agora/access/sfu/v1"). Define the SFU proof as a signature over the context string, the SFU DID, a fresh SFU nonce, and the `channelToken`.
- Needs decision: no

### CRY-8: The routing-envelope signing input is undefined, `id` is circular, and the "ts not authenticated" claim is wrong
- Severity: P2
- Location: spec/05-messaging.md:181-196, spec/05-messaging.md:204, spec/05-messaging.md:313, spec/10-relays.md:673
- Evidence: "`id` is the CID of the canonical outer envelope" (but `id` is a member of that envelope) / "`ts` ... is not authenticated at the outer layer" / "`billingSig` ... signed per §13.1.1 over the announcement with `billingSig` omitted"
- Problem: §13.1 says "Agora computes no canonical form", yet `accessSig` covers a JSON routing envelope "with `accessSig` omitted" and no byte encoding is given. The same applies to `billingSig`: an announcement embedded in the envelope is not a typed-envelope `body`. `id` cannot be the CID of an envelope that contains it, and PoW hashes `envelopeBytes` while the envelope also carries `powProof`. Because `accessSig` covers `ts` and `expiryHint`, they are authenticated (by any member). The text says they are not.
- Suggested fix: Define the routing envelope as a CBOR map with a fixed signing input: every field except `id`, `accessSig` and `powProof`, under the domain prefix from CRY-7. Compute `id` over the signed bytes. Make `accessKeyAnnouncement` a typed envelope (`urn:agora:type:AccessKeyAnnouncement`) so that `billingSig` is an ordinary §13.1.1 JWS over its `body`. Correct the `ts`/`expiryHint` sentences.
- Needs decision: no

### CRY-9: Cross-epoch unlinkability claims contradict the chain-following design (and ARCHITECTURE §5)
- Severity: P2
- Location: spec/10-relays.md:518, spec/12-security.md:34, spec/12-security.md:40, spec/12-security.md:46, spec/05-messaging.md:133, spec/05-messaging.md:216; vs ARCHITECTURE.md:156-159, spec/05-messaging.md:203
- Evidence: "A Relay that captures routing tables across epochs cannot correlate them without also capturing the epoch secrets" / "cannot ... Map routing tables across epochs without MLS group secrets" / "tokens of different key epochs are unlinkable without the keys" / "the sealed envelope keep[s] ... the message kind away from the Relay layer" vs "The relay thereby follows the chain from token to token"
- Problem: Every `accessKeyAnnouncement` is a cleartext link from the old token to the new one, carried in a gossiped routing envelope. Relays, and any gossip peer, therefore link every epoch of a chain. ARCHITECTURE §5 item 6 says so. The routing envelope also shows `epoch` in the clear, and an attached announcement marks which envelopes carry Commits. So the sealed envelope does not hide epoch boundaries or Commits (05:216). It hides only `group_id`, which the chain already links in effect. The decoy-subscription advice (12:46) rests on the same false premise.
- Suggested fix: Rewrite the claims. Relays and gossip observers can link a chain across epochs but cannot map it to a channel or Space. Commits and epoch numbers are visible. Restate the sealed envelope's benefit as hiding `group_id`, `content_type` and sender data from parties that do not follow the chain. If hiding Commits matters, move the announcement inside a separate envelope type that is indistinguishable from others.
- Needs decision: no

### CRY-10: DM groups have no defined exporter context, chain registration or countersigner
- Severity: P2
- Location: spec/04-access-control.md:125, spec/05-messaging.md:194, spec/05-messaging.md:202-204, spec/05-messaging.md:218, spec/10-relays.md:612
- Evidence: "`dmGroupToken` is derived each epoch ... as `MLS-Exporter(\"agora-dm-token\", \"\", 32)`" vs access, sealing and token keys all using context `channelCID`, and "The service countersigns only an announcement requested by a DID it authenticates as a current member of the channel under Space state"
- Problem: A DM group has no `channelCID`. Its `DMGroupCID` changes on every membership change (04:145), so it cannot be a stable exporter context. A DM also has no Space state against which a registration service could authenticate members, and no rule says which CO's billing DID registers and countersigns its chain. As written, DM envelopes cannot carry a valid access proof.
- Suggested fix: Define a single exporter context for all groups, for example the MLS `group_id`, which is constant and known only to members. Specify which CO registers and countersigns DM chains (for example the creator's identity host or CO) and what membership check that service performs.
- Needs decision: yes. Options: (A) the creator's CO registers the chain and countersigns based on DM membership asserted by the requesting member (recommended; the CO learns the DM's existence, not its content); (B) DMs are exempt from the access proof and rely on per-token rate limits (weaker spam control at relays); (C) the regulated member's CO, when there is one.

### CRY-11: MLS credential format and Authentication Service checks are undefined; KeyPackage validation is assigned to the wrong party
- Severity: P2
- Location: spec/05-messaging.md:55, spec/05-messaging.md:77-84, spec/02-identity.md:43, spec/02-identity.md:80
- Evidence: "MLS leaf node credentials are bound to DID verification keys, so verifying an MLS credential means verifying a DID." / "Recipients of a Welcome MUST validate the KeyPackage used to construct it" / "`authentication` key: Ed25519 key used to sign all protocol messages" vs "Each device signs with its own Ed25519 device key"
- Problem: No credential type is specified (Basic with the DID as `identity`? a custom type?). No rule requires that the leaf `signature_key` equal a device `verificationMethod` key in the DID's `authentication` relationship. The checks that matter, for every member processing an Add, Update or Commit path, and for a joiner validating every leaf of the `ratchet_tree` (RFC 9420 §12.4.3.1), are not stated. Instead the Welcome recipient is told to validate its own KeyPackage, which proves nothing. §2.1 also says a single user authentication key signs everything, which contradicts per-device keys.
- Suggested fix: Specify `BasicCredential.identity` = UTF-8 DID. Members MUST check that a leaf's `signature_key` is a current `authentication` verification method of that DID at each Add, Update and path, and joiners MUST check every leaf in the tree. The committer validates fetched KeyPackages under RFC 9420 §10.1. Change §2.1 to say device keys.
- Needs decision: no

### CRY-12: Client-side rejection of valid Commits has no fork semantics; the DM consent model is not implementable in MLS
- Severity: P2
- Location: spec/04-access-control.md:103, spec/04-access-control.md:159, spec/04-access-control.md:78
- Evidence: "Clients MUST reject a Commit that adds a DID with a standing `BanRecord`" / "The Add is not committed until a configurable consent threshold of existing members issues a matching Commit or explicit approval signal."
- Problem: Each MLS epoch has exactly one Commit, issued by one member, so "a threshold of members issues a matching Commit" cannot happen. Any member can commit an Add unilaterally. A client that "rejects" an otherwise valid Commit is forked from the group (RFC 9420 §14). It can no longer decrypt or send, and the spec does not say what it does next (leave, rejoin, alert).
- Suggested fix: Define consent as signed approval application messages that must precede the Commit and that every member checks. Define the reaction to a policy-violating Commit: the client treats the group as compromised, leaves it, notifies the user, and an authorized member re-creates the group. Ban and consent violations take the same path.
- Needs decision: no

### CRY-13: Passive members can never update their leaf, so post-compromise security is permanently lost for the most exposed keys
- Severity: P2
- Location: spec/05-messaging.md:113, spec/07-compliance.md:88; vs spec/12-security.md:14
- Evidence: "A **passive member** ... MUST NOT issue Commits or Proposals." vs "A member whose keys were compromised but who subsequently performs an `Update` commit regains security"
- Problem: A logger or recorder keeps the leaf HPKE key from its KeyPackage for its whole membership. Every later Commit path encrypts to it. Compromising one logger's state therefore gives ongoing access to the path secrets of every group it sits in, which may be thousands, until it is removed, and nothing can heal that. §12.2's PCS claim does not hold for those groups.
- Suggested fix: Allow passive members to send self-update Commits (empty Commit with path) on a schedule, for example once per 7 days, and keep forbidding every other proposal type. Alternatively, require admins to Remove and re-Add the logger periodically. State the residual risk in §12.2.
- Needs decision: no

### CRY-14: The sequencer receives raw MLSMessage bytes, which expose `group_id` and `epoch`
- Severity: P2
- Location: spec/14-jmap.md:158-159, spec/14-jmap.md:193; vs spec/05-messaging.md:216
- Evidence: "The resulting MLS message bytes are the **operation**." / "POST {endpoint}/submit with a CBOR map { \"stream\": <channelToken bytes>, \"op\": <operation bytes> }" / "It learns no member identity, membership or content."
- Problem: An MLSMessage carries `group_id`, `epoch` and `content_type` in the clear. The sealed envelope exists precisely to hide these from IOs. The sequencer, an IO, gets them directly, plus a constant per-channel identifier that links streams across epochs. §14.4.6 does not disclose this.
- Suggested fix: Make the operation the sealed-envelope ciphertext (§5.2.2 wrapper) of the MLSMessage, keyed and bound to `stream`. Also dedupe by `opHash` before MLS decryption, because the RFC 9420 §9.2 deletion schedule makes a second decryption of the same PrivateMessage fail.
- Needs decision: no

### CRY-15: Overclaim that media is bound to a DID through an SFU
- Severity: P2
- Location: spec/06-calls.md:74, spec/06-calls.md:178, spec/06-calls.md:182
- Evidence: "a participant's media stream is cryptographically bound to their DID" / "Participant-to-participant binding is then provided by the SFrame keys (§6.9), which only current MLS members can derive."
- Problem: Every member can derive every sender's SFrame key from the epoch base key. RFC 9605 §6.1.1: "in order to prevent impersonation by a malicious participant (not the SFU), a mechanism based on digital signature would be required. SFrame does not protect against such attacks." Through an SFU, media is authenticated to the group, not to a DID. §6.13 says this correctly for data channels (06:412).
- Suggested fix: Restrict the DID-binding claim to mesh DTLS-SRTP. For SFU media, state group-only authentication, as §6.13 does.
- Needs decision: no

### CRY-16: Non-repudiation claim is not supported by the archive format
- Severity: P2
- Location: spec/12-security.md:123, spec/12-security.md:147; vs spec/07-compliance.md:94-109
- Evidence: "The signing key fingerprint is embedded in the message's MLS authenticated data" / "The compliance archive records both the message content and the signing key fingerprint. A regulator or court can verify that a specific message was produced by a specific device key"
- Problem: Nothing defines a fingerprint in MLS `authenticated_data`. The `ComplianceRecord` stores only the decrypted inner envelope and the logger's own JWS. It keeps neither the sender's MLS signature nor the FramedContentTBS / GroupContext needed to verify it (RFC 9420 §6.1). A third party therefore cannot verify sender origin from the archive, and in-group objects carry no `sig` (13:23).
- Suggested fix: Either archive the MLS `FramedContent`, signature, leaf `signature_key` and `GroupContext` per message, so the sender signature can be re-verified offline, or weaken §12.7 to "attested by the CO's logger". Delete the authenticated_data sentence or specify it.
- Needs decision: yes. Options: (A) archive the verification material (recommended for 17a-4 claims; larger records); (B) weaken the claim to logger attestation.

### CRY-17: JWS verification does not say which DID-document state a key is checked against
- Severity: P2
- Location: spec/13-encoding.md:76; affects spec/07-compliance.md:109, spec/02-identity.md:163, spec/10-relays.md:588
- Evidence: "`kid` is a DID URL whose DID resolves (§2.1) to a DID document containing a verification method whose `id` equals `kid`"
- Problem: Verifying against the current document makes archived objects (compliance records, agreements, Space state) fail once their device key is revoked. Verifying against an unspecified historical document lets a revoked or stolen key keep signing new objects. Only `RecoveryAssertion` (02:163) states a time rule.
- Suggested fix: For newly received objects, verify against the current document. For stored objects, verify against the document version in effect when the object was accepted, recorded by `versionId` (did:webvh) or operation CID (did:plc) alongside the object. State that revocation does not retroactively invalidate stored objects.
- Needs decision: no

### CRY-18: did:webvh split-view and rollback are unaddressed; "auditable without trusting the organization" is overstated
- Severity: P2
- Location: spec/02-identity.md:23, spec/02-identity.md:241, spec/02-identity.md:255; spec/12-security.md:135
- Evidence: "Every resolver of the DID sees that entry in the document history, so organizational impersonation is auditable by the user, her contacts and auditors without trusting the organization"
- Problem: The log host controls HTTPS. It can serve a forked log, signed with its own update key, to a targeted resolver, or serve a stale log that hides a device revocation. Hash chaining does not prevent either. Detection needs the different views to be compared ("if a resolver sees two different log entries" only covers a resolver that already sees both). did:webvh v1.0 provides witnesses and watchers for this. Agora requires neither.
- Suggested fix: Require CO-provisioned identities to use did:webvh witnesses (threshold that includes a party other than the organization) or publish to watchers, and require clients to check witness proofs. Otherwise weaken the claim to "auditable by anyone who compares log copies".
- Needs decision: yes. Options: (A) require witnesses for employer-hosted DIDs (recommended); (B) clients gossip log heads on `v1/agora/discovery` and compare; (C) weaken the claim.

### CRY-19: A `RecoveryAssertion` can be replayed; nothing binds it to the identity state it replaces
- Severity: P2
- Location: spec/02-identity.md:153-163, spec/02-identity.md:467
- Evidence: fields `did`, `newDeviceKey`, `revokeAll`, `ts` only; "The provisioning service accepts a `RecoveryAssertion` as equivalent to an IdP token for first-device enrollment"
- Problem: Assertions are published to `v1/agora/discovery`, and `ts` must not be used for ordering. An old assertion can be resubmitted to a provisioning service to re-enroll a device key that was later revoked, for example a device that was then stolen.
- Suggested fix: Add `prevVersionId` (did:webvh) or `prev` operation CID (did:plc): the state the assertion applies to. Verifiers and provisioning services MUST reject an assertion whose `prev…` is not the current head.
- Needs decision: no

### CRY-20: Backing up MLS state undermines forward secrecy and risks nonce reuse on restore; the "stateOnly" claim is wrong
- Severity: P2
- Location: spec/02-identity.md:220, spec/02-identity.md:225, spec/02-identity.md:229, spec/02-identity.md:469; vs spec/12-security.md:10
- Evidence: "Current MLS key material for all group memberships" / "The MLS group state exported via the MLS key export interface (RFC 9420 §11)" / "restores MLS continuity"
- Problem: Restoring a snapshot rewinds the secret-tree generations. The device then re-sends under (key, nonce) pairs it already used (RFC 9420 §9) and re-derives keys the deletion schedule (§9.2) requires to be gone. The MLS exporter (§8.5, not §11) derives secrets and does not export state. A "stateOnly" backup without the leaf signature key cannot sign, so it cannot send or commit, which is not "continuity". §12.1's forward-secrecy statement does not mention this exception.
- Suggested fix: Do not back up live MLS ratchet state. A restored device re-joins as a new leaf (new KeyPackage), and an existing device Removes the old leaf. If decryptable history is wanted, back up decrypted message plaintext instead. Fix the citation and add the trade-off to §12.1.
- Needs decision: no

### CRY-21: Device enrollment has no proof of possession of the new key
- Severity: P3
- Location: spec/02-identity.md:336
- Evidence: "For first-device enrollment the envelope `sig` is absent. For subsequent devices it MUST be present" (signed by an existing device)
- Problem: The new device's private key is never shown to be held by the requester, so anyone with the IdP token can register an arbitrary public key, including another party's. This is the classic proof-of-possession gap that CSRs close with a self-signature.
- Suggested fix: Require a signature by the new device key over the request (with the IdP token's `nonce`/`jti` bound inside it), in addition to the existing-device signature when one applies.
- Needs decision: no

### CRY-22: Underspecified parameters in several primitives
- Severity: P3
- Location: spec/02-identity.md:211-212, spec/02-identity.md:171, spec/12-security.md:82-83, spec/06-calls.md:215
- Evidence: "backup = AEAD_AES_256_GCM(backupKey, backupPayload)" / "encrypts each share individually to a guardian's X25519 key agreement key" / "an AES key derived by HKDF from the PRF output" / "password = HMAC(secret, username)"
- Problem: Backup: no salt length, no nonce, and the self-describing header (Argon2id parameters, DID, `backupType`) is not bound as AAD. Recovery shares: the encryption scheme is unnamed. PRF wrapping: no PRF `eval` salt, HKDF info or wrap IV. TURN: no HMAC hash, and the TURN REST convention is HMAC-SHA1 with base64. Two implementations will not interoperate, and the unbound backup header can be swapped.
- Suggested fix: Backup: 16-byte random salt, 12-byte random nonce, AAD = encoded header. Shares: HPKE base mode, suite as §6.12.4, `info = "agora/v1/recovery-share" || did`. PRF: fixed salt `SHA-256("agora/v1/prf")`, HKDF info `"agora/v1/device-key-wrap"`, AES-GCM wrap with stored random IV. TURN: name the hash.
- Needs decision: no

### CRY-23: The broadcast content key is used both as an AES key and as HKDF input
- Severity: P3
- Location: spec/05-messaging.md:133, spec/05-messaging.md:141
- Evidence: "`channelToken = HKDF-SHA256(IKM = key, ...)`" and "AEAD-Seal(key, nonce, plaintext, ...)"
- Problem: Using one secret directly in two primitives breaks key-separation hygiene. No practical attack is known, but there is no reason for it.
- Suggested fix: Derive both: `encKey = HKDF(key, info="agora broadcast enc"||keyEpoch, 16)` and `channelToken = HKDF(key, info="agora broadcast token"||keyEpoch, 32)`.
- Needs decision: no

### CRY-24: External commits and external proposals are not addressed
- Severity: P3
- Location: spec/05-messaging.md:48-53, spec/04-access-control.md:78 (no mention anywhere; grep for "external" finds nothing in the MLS sections)
- Evidence: "MLS operations follow RFC 9420 exactly" followed by a list that covers KeyPackage, Welcome, Commit and Proposal only
- Problem: RFC 9420 §12.4.3.2 (external commits via GroupInfo `external_pub`) and §12.1.8 (external senders) let a party join or propose without the Welcome authorization path that §4.3 relies on. A member who publishes GroupInfo would let anyone join by external commit.
- Suggested fix: State that Agora groups use neither. Clients MUST reject Commits whose sender type is `new_member_commit` and proposals from `external` / `new_member_proposal` senders, and MUST NOT include `external_pub` in GroupInfo.
- Needs decision: no

### CRY-25: RFC section citations are wrong
- Severity: P3
- Location: spec/05-messaging.md:55, spec/02-identity.md:225, spec/12-security.md:93
- Evidence: "Delivery Service role (as defined in RFC 9420 §10.3)" / "MLS key export interface (RFC 9420 §11)" / "MLS exporter interface (RFC 9420 §11.5)"
- Problem: RFC 9420 §10 is Key Packages and §11 is Group Creation. The exporter is §8.5. The Delivery Service is described in RFC 9750 (MLS Architecture), not RFC 9420 §10.3.
- Suggested fix: Cite RFC 9420 §8.5 for the exporter and RFC 9750 for the DS/AS roles.
- Needs decision: no

## Areas checked with no defect found
- JWS profile (§13.1.1): `b64:false` with `crit:["b64"]` is protected as RFC 7797 §6 requires. The detached unencoded payload is correct. The signing-input construction is correct. `cty`/`agoraType` binding is sound. Requiring exact header members is fine.
- Ed25519 seed derivation from the exporter (`accessSeed`) and from HKDF (social recovery key): acceptable, because each output has one purpose and the seed is hashed per RFC 8032 §5.1.5.
- Broadcast payload: random 96-bit nonce, 2^32 limit, AAD bound to the token, and inner `channelCID`/`keyEpoch`/`senderDID` checks prevent cross-channel and cross-epoch re-targeting.
- Group-encrypted blob format, `ratchet_tree` extension requirement (RFC 9420 §12.4.3.3 cited correctly), single-use KeyPackages with last resort, sequencer stamp chaining and fork proof, TURN credential separation from MLS secrets, HPKE archive sealing parameters, did:plc rotation-key priority, did:webvh SCID and path resolution, WebAuthn statements (an authenticator signs only `authenticatorData || SHA-256(clientDataJSON)`) and the WebCrypto wrap/unwrap flow.

Coverage: read fully ARCHITECTURE.md §5-§6; spec/02-identity.md (all); spec/04-access-control.md (all); spec/05-messaging.md (all); spec/06-calls.md (all); spec/07-compliance.md §7.3-§7.8; spec/10-relays.md §10.4-§10.5 (incl. RelayServiceAgreement, AccessChainRegistration, PoW); spec/12-security.md (all); spec/13-encoding.md (all); spec/14-jmap.md §14.3.2-§14.4.6; spec/03-spaces.md §3.4 BroadcastKey and group-encrypted blob paragraphs. Cross-checked RFC 9420 §10, §14, §17.8 and RFC 9605 §5.2, §6.1.1, §9.1 from local copies.
