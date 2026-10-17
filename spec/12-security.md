# 12. Security Considerations

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 3223–3352 (§13).

## 12.1 Forward Secrecy

MLS provides forward secrecy by design. Each epoch derives a new application secret via the MLS key schedule. Compromise of a member's current epoch key material does not expose prior messages, which were encrypted under previous epoch secrets.

## 12.2 Post-Compromise Security

MLS `Update` proposals (triggered by devices or by time-based policy) ratchet the ratchet tree forward, healing from key compromise. A member whose keys were compromised but who subsequently performs an `Update` Commit regains security: the compromised old key material cannot decrypt new messages. Space operators SHOULD enforce periodic key rotation (recommended: 7-day maximum epoch lifetime for active channels).

Passive members (the compliance logger and recorder, §5.2.1.3) send no ordinary Updates. Each SHOULD send a scheduled self-update Commit, for example weekly (§7.3). Until it does, a compromise of its leaf Hybrid Public Key Encryption (HPKE) key exposes the path secrets of every UpdatePath encrypted to that leaf, in every group the passive member belongs to. Because one logger or recorder sits in many groups, its leaf keys are among the most exposed in a deployment; §7.9 gives the rotation and compromise procedure.

The channel admission key (§5.2.2) is not an MLS secret and gets no forward secrecy or post-compromise security from MLS. Its compromise lets the holder have envelopes admitted and recognize the channel's traffic at a relay until the Communications Operator (CO) rotates it (§12.4, §12.12); it gives no access to content.

## 12.3 Relay Trust and Legal Exposure

Relays are untrusted for message content and blind to membership and sender identity. The threat model here is a relay operator that receives a subpoena or legal demand: what can it produce?

What each operator can be compelled to produce is defined in ARCHITECTURE §4: an Infrastructure Operator (IO) yields only what is inside its observation budget (ARCHITECTURE §5), and a CO yields what its own retention policy keeps. The authoritative record for a regulated community is the CO's archive (§7), never a relay.

**What a relay can observe.** Exactly the ARCHITECTURE §5 observation budget: network-layer connection metadata within the retention declared in its manifest, ciphertext envelopes with their size, timing, `id`, `channelToken`, timestamp, and expiry hint, admission public keys and `admissionSig` values that do not identify the member, CIDs it stores, agreement-keyed quota state, the billing DID of each CO it holds an agreement with and which admission keys are registered under each agreement and when (ARCHITECTURE §5 item 6), push registrations if it serves push (ARCHITECTURE §5 item 7), and its own peering relationships.

Every envelope of a channel within one key epoch carries the same `channelToken`, so a relay links all of a channel's traffic within a key epoch. It also links successive key epochs of one channel: the registration of a rotated key names the token it replaces, and the old key is deregistered shortly after (§5.2.2, §10.5.3). It can see which subscribers do not move to a rotated key's token, and so can infer that a removal occurred and which connection or push handle it affected. It recognizes envelopes that carry a stamped Commit by their `commitStamp` (§5.2.2). A relay that serves push learns which `channelToken`s wake the same device (§11.7).

**What a relay cannot observe.**
- Message content (MLS end-to-end encryption; the relay never holds decryption keys)
- Sender identity for any message (MLS encrypts the sender data, and the sealed envelope hides the MLS framing, §5.2.2)
- Channel identity from `channelToken` (derived from the CO-issued admission key, §5.2.2, and not reversible to a `channelID` or MLS group ID without that key), except the token of a `keyAccess: public` broadcast channel, which the CO publishes with its public Space (§3.4)
- Group membership (no membership list at the relay layer)
- Message graphs or conversation structure

**What a relay cannot do.**
- Forge messages (each message carries the sender's MLS signature inside the sealed envelope, verified by recipients)
- Alter a message undetected: the MLS signature inside the sealed envelope covers its content
- Drop messages unnoticed: a relay can withhold envelopes, but members detect the gap in the sender's inner `seq` (§5.1.1) and fetch from another relay or another member (§5.2.5)
- Map a `channelToken` or admission key to a channel, Space, or member, except tokens a CO publishes (public broadcast channels, §3.4) and the direct message (DM) and self-group tokens of an identity host that serves one user (§12.4); it may link the key epochs of one channel (above), but not the channel to anything behind it

Clients SHOULD connect to multiple relays simultaneously. A single relay going dark (legal seizure, operator shutdown) does not partition a user from their channels as long as at least one other relay that the CO lists for the channel (§10.3.5) is reachable.

## 12.4 Metadata Leakage

MLS sender-data encryption and the sealed envelope keep sender identity, the MLS group ID, the MLS epoch, and the message kind away from the relay layer, with one exception: in a channel whose Space designates a sequencer, an envelope that carries a Commit also carries a `commitStamp` (§5.2.2), so Commits are visible there. Residual metadata leakage points:

**IP address.** A relay sees the connecting IP. Clients requiring IP-level anonymity SHOULD connect via Tor (preferring the relay's `.onion` endpoint where available, to avoid exit node exposure) or a trusted front-end proxy.

**Timing correlation.** A global passive adversary watching both sender and relay can correlate message timing. This is a known limitation of all low-latency messaging protocols. Mixing and batching (as in Katzenpost) defeats timing analysis but is incompatible with Discord-like UX latency targets. This is an accepted tradeoff.

**Subscriptions.** A relay observes which `channelToken`s a client subscribes to, and relays that carry a channel's topic between them (§10.3.1) observe the token. A token is stable for a whole key epoch and changes only when the CO rotates the admission key (§5.2.2), so a relay links a client's subscription to all of that channel's traffic in the key epoch. Decoy subscriptions do not hide membership from a relay, because a relay knows which tokens are registered with it. A client that wants to hide how many channels it follows from one relay SHOULD spread its subscriptions across several of the relays its COs list (§10.3.5).

**Tor subscription fingerprinting.** As noted in §11.3, a relay sees which `channelToken`s a connection subscribes to and when, whatever address the connection comes from. A client connecting via Tor can be recognized across circuits by its subscription set. This is a known residual risk for clients that need strong anonymity against a relay-level adversary.

**Channel token correlation.** The `channelToken` is derived from the seed of the channel admission key (§5.2.2). Anyone who holds a `ChannelAdmissionKey`, which every current member and the CO hold, can compute the token and recognize the channel's traffic at a relay. A removed member keeps that ability for the key epochs it held, including the current one until the CO rotates the key on its removal. A channel whose membership changes often SHOULD therefore have its key rotated promptly on each removal (§5.2.2).

**Presence, typing, and DM membership.** Presence and typing indicators are MLS application messages, and a DM is an ordinary MLS group addressed by `channelToken`. A relay sees them only as ciphertext envelopes within the ARCHITECTURE §5 budget; it cannot distinguish them from other traffic by type, and it does not learn who is in a DM, except as follows. A DM group's admission key is registered under the agreement of the group's admission host (one member's identity host, initially the initiator's, §4.6), so a relay learns whose agreement covers a DM token. When that host serves one user, its agreements stand for that user, and every DM and self-group token registered under them belongs to a group that user is in or recently left (§10.5.1, ARCHITECTURE §9). A self-group token is followed only by one user's devices, so a relay that carries it can link those devices, their network addresses, and their push handles. The admission host gives the key only to its own user, whose client puts it in the group's GroupContext (§4.6), so the host does not learn who else is in the DM (§12.11).

## 12.5 Denial of Service

Relays never authenticate client identity (ARCHITECTURE S1, ARCHITECTURE §8 Q2); a connection opens with a minimal unauthenticated hello that only negotiates the protocol version (§11). Abuse control rests on what a relay can check without knowing who the client is:

- **Writes** are accepted only with a valid `admissionSig` under an admission key registered with the relay (§5.2.2, §10.5.4); envelopes that fail it are rejected.
- **Admission key registration** requires a request signed by the CO's billing DID under a `ServiceAgreement` (§10.5.1, §10.5.3).
- **Storage and bandwidth** are bounded by the agreement's quotas (§10.5.1).
- **Connections, subscriptions, history reads, and push registrations** are rate-limited per network address and per `channelToken`. Relays MUST enforce per-`channelToken` rate limits on message publication.
- **Under load**, a relay MAY require a proof-of-work challenge (`AdmissionChallenge` and `AdmissionProof`, §11.6) before accepting a connection. This admits clients that share an address, such as Tor users behind one exit, without penalizing all of them for one abuser.
- **Removed members and leaked keys.** A removed member, or anyone who obtains an admission key, can have envelopes admitted until the CO rotates the key (§5.2.2). Members drop such envelopes because MLS processing fails, so the cost is relay capacity and member bandwidth, not content. The CO bounds it by rotating on every removal and on any suspected leak, and the relay's per-token rate limits bound it meanwhile. For a DM group, the rotation waits until the client of the admission host's user is online to request a new key from the host and commit it (§4.6), so the window lasts at least that long, or 24 hours if that client holds the group as a message request (§4.6.3). After the rotation, the replaced key stays registered until its issuee's client deletes it, and at most 7 days after the new key's issuee confirms the new key to the host (§4.6). If that confirmation never arrives, for example because the rotating client failed after its Commit won, the replaced key stays registered until its issuee deletes it or is offboarded. After a move to another host, the previous host's key stays registered until its issuee's client deletes it, 30 days after the move, or until that user is offboarded if the client never returns. Members no longer subscribe to it, so envelopes admitted under it reach no member (§4.6.4, §5.2.2).
- **Unopenable envelopes in a group with no sequencer.** Anyone who can have an envelope admitted under a group's admission key, such as a removed member before the key is rotated or deregistered or a holder of a leaked key (above), can publish bytes that open under no sealing key. In a group with no sequencer, which includes every DM group, each recipient holds such an envelope for up to 24 hours. If no Commit explains it, the recipient keeps its state for the group, and its client suggests to the user that the group may be out of sync and that a member re-add them (§5.1.1, §5.2.2). The sender learns no content and forges no message, but can raise that suggestion as often as it can have envelopes admitted, which can prompt needless re-adds and teach users to ignore the suggestion when a real split occurs. While a member is flagged, any member of the group in its held state can replace that state with a group of the adder's making by sending a Welcome (§4.3, §4.6); the member list the client then shows is the only sign. A Space avoids this by designating a sequencer. This is an accepted limit.
- **Bogus DM admission key.** Any DM member can commit a GroupContextExtensions proposal that sets `agora_admission` to a key no relay has registered (§4.6). Relays then refuse the members' envelopes under that key. Members recover with the previous key, which stays registered, because the issuee of a replaced key deletes it only after a relay has admitted the new key, and a host deregisters an earlier key on its own only 7 days after the issuee of a later key confirms that key (§4.6; see the stranding limit below). A host's user then rotates the key, or any other member moves the group to its own identity host (§4.6.4), and publishes that Commit under the previous key. A bogus same-host key can come only from a member whose `KeyPackageEndpoint` names that host's origin (§4.6), which any member that controls its own DID document or Pkarr record can arrange. This gives a member no new power, because any member may already remove every other member (§4.6).
- **False compliance entry.** A DM member can add a DID of its choosing with an `agora_compliance` entry (§7.8.2), which compliant clients then do not remove and show as a compliance logger. Members cannot check the entry against Space state they do not see; a member that objects can leave (§4.8). This is an accepted limit.
- **A DID served by the admission host strands the DM.** Any DID that the group's admission host serves and that knows the group ID, including every former member served by that host, can strand the group: it can deregister a key issued to it at once, or have a key issued for the group and confirm it, after which the host deregisters every earlier key 7 days later (§4.6). Relays then refuse every envelope under the group's keys, including a Commit that would move the group (§4.6.4), and its members start a new group. The same holds when every listed relay withdraws the current key, for example by token suspension (§10.4.7) or the end of the host's agreements, and no earlier key of the group is still admitted. This is an accepted limit.
- **Dormant DM groups and relay replacement.** A DM group or self-group follows its admission host's relay changes only when a host's user's client is online to rotate (§4.6). A group none of whose host's users comes online before its listed relays stop serving can no longer be used, and its members start a new one. This is an accepted limit.
- **Unauthorized Commits.** A channel member can submit a valid but unauthorized Commit; if it wins, every member leaves the group and an admin re-creates it (§4.5), after which the admin can remove the sender identified by its MLS signature.
- **Wake-ups.** Wake-ups carry no content and no urgency (§11.7), so a sender cannot cause a high-priority wake on a recipient's device.

Between relays, gossipsub v1.1 peer scoring and flood control apply (§10.3.1).

Privacy Pass tokens are a possible future extension. Spam control is local policy. There is no global reputation system, by design: global reputation systems become censorship infrastructure.

## 12.6 Key Storage: HSM and Secure Enclave Guidance

All private key operations in Agora (signing, key agreement, MLS leaf operations) SHOULD be performed inside a hardware-backed secure boundary wherever the platform provides one. The protocol is designed so that no operation requires extracting raw private key bytes to application memory.

**Platform secure boundaries and recommended APIs.**

| Platform | Boundary | API |
|---|---|---|
| macOS / iOS | Secure Enclave (T-series / M-series) | `SecKey` / CryptoKit `SecureEnclave.P256` |
| Android | StrongBox / TEE | `AndroidKeyStore` with `PURPOSE_SIGN` / `PURPOSE_AGREE_KEY` |
| Linux server | TPM 2.0 or hardware HSM | PKCS#11 (`opensc-pkcs11`, `SoftHSM2` for dev), or `tpm2-pkcs11` |
| YubiKey / hardware security key | Secure element | PKCS#11, PIV, or OpenPGP card interface |
| Browser | Browser key store (not hardware-backed) | WebCrypto Ed25519 with non-extractable `CryptoKey`; WebAuthn PRF extension to derive the wrapping key |

**Browser clients.** A browser has no hardware boundary that can sign arbitrary payloads: a WebAuthn authenticator signs only WebAuthn assertion structures, so a passkey cannot be the device key (§2.2). A browser client holds its Ed25519 device key in WebCrypto and signs only through a non-extractable `CryptoKey` (`extractable: false`); for browser clients that `CryptoKey` is the secure boundary this section refers to. A browser client SHOULD protect the stored key with a passkey through the WebAuthn PRF extension:

1. At registration, the client generates the Ed25519 key with `extractable: true`. It obtains the PRF output of the user's passkey with the PRF input `first` set to SHA-256 of the UTF-8 string `agora/v1/webauthn-prf`, and derives a 32-byte wrapping key as `HKDF-SHA256(IKM = PRF output, salt = "" (zero-length), info = "agora/v1/webauthn-prf-wrap", L = 32)`, imported as an AES-GCM key. It calls `wrapKey` with format `pkcs8` and `{name: "AES-GCM", iv}`, where `iv` is 12 fresh random bytes, stores only the wrapped key and `iv`, and drops the original `CryptoKey`. The client MUST NOT call `exportKey` on it.
2. Once per session, the client obtains the PRF output with a WebAuthn assertion using the same PRF input, derives the wrapping key as above, and calls `unwrapKey` with the stored `iv` and `extractable: false`. It signs with the resulting key until the session ends.

Where the authenticator does not support PRF, the client generates the key with `extractable: false` and stores the `CryptoKey` object itself in IndexedDB. Clearing browser storage destroys the device key; recovery is registering a new device (§2.2). A browser without WebCrypto Ed25519 MAY use a reviewed JavaScript or WebAssembly implementation, which exposes key bytes to page memory and is weaker than the paths above.

**Conformance requirements by operation.**

- **Authentication key signing** (Ed25519): MUST use a hardware-backed key where the platform supports Ed25519 in its secure boundary, and otherwise the best-protected software store the platform offers. Device keys are Ed25519 only (§2.2, §13.1.1), so a platform whose secure boundary supports only P-256 (such as the Secure Enclave) holds the device key in software. A `did:key` identity key used on several devices is exportable by design (§2.1) and so cannot be a non-extractable hardware key. The MLS leaf signature key of a `did:key` device is generated on that device and never copied (§5.2.1), so it falls under the next item.

- **MLS leaf operations** (KeyPackage generation, Commit signing, Update proposals): MUST use keys held in the secure boundary where the platform supports Ed25519 there, and otherwise in the best-protected software store. `openmls` supports pluggable crypto backends; implementations SHOULD provide a backend that delegates to the platform keystore rather than holding raw key bytes.

- **MLS key schedule / epoch secrets**: these are MLS-internal derived values, not persistent keys. They exist transiently in MLS stack memory during epoch processing and SHOULD NOT be exposed to application code. All operations requiring epoch secret access MUST use the MLS exporter interface (RFC 9420 §8.5) rather than accessing the epoch secret directly.

- **X25519 key agreement** (for encrypting social recovery shares, HPKE operations): SHOULD use hardware-backed key agreement where the platform supports it. Where hardware X25519 is unavailable, software implementation in a sandboxed process is the fallback.

- **Recovery key**: see §2.4.1. This key MUST NOT be in any software keystore. Its signing operation occurs exactly once per recovery event, on an air-gapped device or hardware security key, and the output (`RecoveryAssertion`) is transferred to the networked environment by QR code, USB, or a similar one-way channel.

**Application code and raw key bytes.** Application code MUST NOT have access to raw private key bytes for any of the above. Its API calls take the form "sign this payload with key handle K" or "agree on a shared secret using key handle K and this public key", with the output being a signature or shared secret, not a key.

**Relay operator key storage.** Relay signing keys SHOULD be held in an HSM or TPM-backed keystore on the relay host. Cloud HSM services (AWS CloudHSM, GCP Cloud HSM, Azure Dedicated HSM) are appropriate for hosted relay deployments. At minimum, keys SHOULD be stored in the OS keyring rather than on disk in plaintext.

## 12.7 Non-Repudiation and Organizational Non-Impersonation

Agora provides a stronger non-repudiation guarantee than any conventional enterprise messaging platform, and a structural property that prevents silent organizational impersonation of users. Both properties come from the architecture, not from policy.

### 12.7.1 Why Conventional Enterprise Platforms Cannot Provide This

In all conventional enterprise messaging and email systems (Microsoft Teams, Slack, Zoom, Exchange/Outlook with S/MIME, Google Workspace), the organization controls the root of trust end-to-end:

- **IdP-based systems (Teams, Slack, Zoom):** An identity provider (IdP) administrator can generate tokens asserting any identity in the tenant. There is no cryptographic artifact in a sent message that ties it to the sender's specific device key rather than to their organizational identity as asserted by the IdP. The organization can produce messages attributed to any user.
- **Enterprise S/MIME:** In a standard enterprise deployment, the CA generates the keypair and holds a copy in key escrow. The CA has the private key. The organization can sign messages as any user whose keypair it escrowed.
- **Exchange mailboxes:** `SendAs` and `FullAccess` permissions are a normal administrative operation. No cryptographic barrier prevents an Exchange admin from sending mail as any user in the tenant.

In all of these systems, impersonation by the organization leaves no mandatory cryptographic trace in the messages themselves.

### 12.7.2 The Agora Architecture

Agora separates the identity namespace from the signing key material at a structural level:

- **DID document (org-controlled, history public):** The organization hosts `did:webvh:{SCID}:{orgDomain}:users:{id}` and holds an update key; it can add, remove, and update key entries in the document (§2.5), but each change is a DID log entry signed with its update key and visible to every resolver (§2.1). This is the identity namespace.
- **Private key material (device-controlled):** Ed25519 device keys are generated on the device and held in its hardware-backed keystore where the platform supports Ed25519, or otherwise in its best-protected software store (§12.6). The DID document contains only the public key. The organization receives no copy of the private key at any point; there is no enrollment flow that transmits private key material to the provisioning service (§2.5.4).
- **Per-message signing:** Every Agora message carries an MLS signature by the sender's device key. The key is the signature key of the sender's MLS leaf, whose credential names the sender's DID (§2.2); recipients verify the signature against that leaf, so a message cannot be attributed to another leaf without failing verification.

Consequence: **the organization cannot sign a message as Alice without access to Alice's private key, which it does not have.** The DID document update authority (org-controlled) and the signing authority (device-controlled) are held by different parties and involve different, non-interchangeable key material.

### 12.7.3 The Residual Organizational Capability

The organization retains one path to producing a message attributable to Alice's DID: it can register a new device key via the admin enrollment path (§2.5.8, helpdesk recovery) and sign messages with that key. This operation:

1. **Creates a new DID document entry** with a distinct `deviceKeyFingerprint` and registration timestamp, different from Alice's existing device entries.
2. **Is recorded in the provisioning audit log** (§2.5.8).
3. **Is detectable** by any member who compares the MLS leaf signature key that signed a message against the DID document entry that was active at the time of message creation.

Cryptography does not prevent an organization holding an update key from adding a key to Alice's `did:webvh` document, inside or outside the enrollment path. It does make every such addition auditable: the key can enter the document only through a DID log entry signed with the organization's update key, the log is hash-chained, and resolvers reject a log that does not verify (§2.1). Hash chaining alone does not stop the organization from showing different resolvers different valid logs (a split view) or an old prefix of the log (a rollback). For that reason a CO-provisioned `did:webvh` MUST use witnesses: every log entry carries a proof from at least one witness the organization does not control, and clients MUST verify those proofs (§2.1). Hiding a key addition from Alice while showing it to her contacts then requires the collusion of such a witness, so Alice, her contacts, and auditors can see when each key was added and by which update key without trusting the organization alone. Silent impersonation (producing a message indistinguishable from one Alice sent herself) is therefore not possible without a colluding witness. An individual's `did:webvh` MAY omit witnesses; it then gets only the weaker guarantee that each entry a resolver receives was signed by an authorized update key, with no protection against a split view or a rollback by whoever holds an update key or serves the log (§2.1).

Implementations SHOULD surface device registration events to the DID subject (Alice) through out-of-band notification (such as email or push) at the time of admin-initiated registration. This converts a detectable-in-principle property into a detectable-in-practice one.

### 12.7.4 Non-Repudiation for Compliance

The combination of per-message device-key signatures and a tamper-evident IPLD compliance archive (§7) provides non-repudiation stronger than email with DKIM or S/MIME in typical enterprise deployment:

- **DKIM** authenticates the sending domain, not the individual sender. An admin with access to the DKIM private key can sign mail on behalf of any address at that domain.
- **Enterprise S/MIME** with key escrow allows the key custodian (typically the organization) to produce valid signatures for any escrowed identity.
- **Agora device-key signatures** can only be produced by the device that holds the private key, in a hardware-backed keystore where the platform supports Ed25519 there and otherwise in the best-protected software store (§12.6). The compliance logger is an MLS member and verifies each message's MLS signature against the sender's leaf before writing a signed `ComplianceRecord` (§7.4). The record carries the sender's MLS message as received, the keys that open that one message, the epoch's `GroupContext`, and the sender's `LeafNode`, so a regulator or court can re-verify the sender's own signature without trusting the logger, and can check in the DID log that the signing key was a device key of `senderDID` at the time (§7.4, Third-party verification). A `did:key` sender has no DID log, and its leaf signature key is not the identity key (§5.2.1), so the verifier instead checks the leaf's `agora_device_binding` extension under the key the DID encodes. That binding cannot be revoked, and every device of a `did:key` user holds the copied identity key, so it shows only that some holder of the identity key vouched for the leaf key.

This property is relevant for FINRA Rule 17a-4, SEC Rule 17a-4, and MiFID II recordkeeping requirements, where the integrity and authenticity of retained communications are material.

## 12.8 Operational Security of CO Services

*Binds: CO.*

The CO runs the online services that hold community authority: the registration service (§5.2.2, §10.5.3), Space endpoints (§3.4), KeyPackage hosts (§5.2.1.1), the provisioning service (§2.5), the TURN credential service (§6.11), and the compliance logger and recorder (§7.3, §6.12). Their conformance classes are listed in §1.4. These services are CO components (ARCHITECTURE §2.3), so what they learn is CO knowledge and not an IO observation; §12.11 lists it.

**Member authentication.** CO services that serve or issue something only to current members authenticate them with the exchange in §3.5. That exchange is the only member authentication between clients and CO services; relays and other IOs never use it.

**Key custody.** The billing key, the provisioning service's signing and DID update keys, the Space owner and admin keys used for online signing, and the keys of the compliance logger and recorder SHOULD be held in an HSM or equivalent hardware boundary, as for relay keys (§12.6). Channel admission private keys are not on this list: they are secrets the CO serves to every current member (§3.4, §5.2.2), so hardware custody at the CO adds nothing. The billing key SHOULD NOT be held on the same host as a Space endpoint: a Space endpoint is reachable by every member and holds Space-identifying records, while the billing DID MUST NOT appear in any Space-identifying record (ARCHITECTURE §6.1).

**Rate limits.** Every CO service SHOULD rate-limit requests per network address and per authenticated DID. A KeyPackage host SHOULD also rate-limit Welcome POSTs per source address and per target identity, and SHOULD reject a Welcome larger than it is prepared to store; fetch rate limits are in §5.2.1.1.

**Audit logging.** CO services SHOULD log security-relevant operations, including device key registrations and revocations (§2.5), admission key registrations, rotations, and deregistrations (§10.5.3), issuance of `ChannelAdmissionKey` and `BroadcastKey` records (§3.4), and administrative actions. Such logs are CO records kept under the CO's retention policy and are subject to the minimization guidance in §12.11.

**Availability.** Outages of these services fail closed for new access but leave existing access in place. In particular, while the Space endpoint or the registration service is unreachable, relays keep accepting the last registered admission key, so a member removed after that key was issued can still have envelopes admitted, though it cannot read, until the CO rotates the key (§5.2.2). A CO SHOULD run the registration service and Space endpoints redundantly and monitor them.

## 12.9 Time and Clocks

*Binds: both.*

Timestamps in documents are RFC 3339 date-times in UTC (`Z` suffix). The exceptions are fields that a section defines as integer Unix seconds, such as the RFC 9421 `created` parameter (§10.2.3) and the TURN credential username (§6.11).

Clients, relays, and CO services SHOULD keep their clocks synchronized to UTC, for example with NTP (RFC 5905). Unless a section states its own window, a party comparing another party's timestamp with its own clock MUST NOT treat an object as not yet valid unless its start time is more than 300 seconds ahead of its own clock, and checks expiry against its own clock with no added tolerance.

Message order does not depend on any clock: messages are ordered by `seq` (§5.1.1), competing Commits in a Space with a sequencer by commit stream position (§5.1.1), call coordination by epoch and envelope `id` (§6.14), and the routing envelope `ts` is set by an unidentified holder of the admission key (§5.2.2). Clocks do decide the following:

| Check | Whose clock | Defined in |
|---|---|---|
| `BroadcastKey` `notBefore`, which is also the cut-over that removes a subscriber | Poster | §3.4, §5.2.1.4 |
| `TimeoutRecord` `expiresAt` | Each receiving client | §4.5 |
| `SpaceInvite` expiry | Space endpoint and joining client | §4.3, §3.4 |
| KeyPackage `lifetime.not_after` | Committer adding the KeyPackage; Welcome recipient | §5.2.1.1 |
| `ParticipantState` `ttl`; ring limit | Receiving client | §6.2, §6.14.1 |
| Presence and typing timeouts | Receiving client | §5.3 |
| `RecordingGrant` `expiresAt` | Recorder and participating clients | §6.12.2 |
| TURN credential expiry | TURN server | §6.11 |
| Relay-to-relay request freshness | Receiving relay | §10.2.3 |
| Member authentication `ts` | CO service | §3.5 |
| Commit collection window in a group without a sequencer (elapsed time) | Each receiving client | §5.1.1 |
| 24-hour DM handover fallback | Each remaining member's client | §4.6.4 |
| `expiryHint` and envelope retention | Relay | §5.2.4, §10.4.3 |
| Push registration TTL | Relay | §11.7.3 |
| 24-hour `RecoveryAssertion` rule | Party applying the assertion | §2.4.4 |
| Last-writer-wins `at` | Author (sender-chosen) | §14.3.3 |

A poster whose clock is slow keeps encrypting under the previous `BroadcastKey` after a removal until its clock passes the new key's `notBefore`. A CO that rotates a `BroadcastKey` to remove a subscriber SHOULD therefore set `notBefore` no later than the time it publishes the key.

## 12.10 Required Disclosures: Accessibility and Language

*Binds: clients and CO.*

This section applies to the disclosures this specification requires a client to present:

- the `retentionNotice` (§7.5, §7.7), including the home Space notice shown to guests (§8.8)
- the `ComplianceDisclosureNotice` in DM groups (§7.8.4)
- the recording disclosure, from `participantDisclosure` (§6.12.3)

It also applies to the indicators the specification recommends:

- the compliance logging indicator (§7.7);
- the recording indicator (§6.12.3);
- the broadcast-channel indicator (§5.2.1.4);
- the gateway indicator and `e2eeNote` (§9.3).

**Text equivalent.** An indicator a client presents for a disclosure in this section SHOULD have a text equivalent exposed through the platform accessibility API. An icon or color alone does not meet a disclosure requirement.

**Devices without a display.** Presenting the recording disclosure (§6.12.3) does not require a display: a client on a device with no display, such as an audio-only or headless call endpoint, SHOULD present it as an audible announcement before it enables media transmission in a call with an active `RecordingGrant`. A device that can neither display nor announce the disclosure MUST NOT transmit media while a `RecordingGrant` is active.

**Language.** Each of the fields `retentionNotice`, `participantDisclosure`, and `e2eeNote` MAY be a language map instead of a string: a JSON object whose member names are language tags (RFC 5646) and whose values are strings. A language map MUST contain the member `und`. A client displays the value whose tag best matches the user's language preferences under RFC 4647 lookup, and the `und` value when none matches. Where this specification gives the wording of a notice ("wording equivalent to", §7.8.4; the guest notice, §8.8), clients SHOULD present that wording in the user's language.

## 12.11 Privacy Considerations

*Binds: both.*

This section collects what each party learns. It does not restate the IO limits, which are normative in ARCHITECTURE: what each operator can be compelled to produce (ARCHITECTURE §4), the IO observation budget (ARCHITECTURE §5), and the accepted costs of the design, including Space anonymity bounded by the size of the CO and address clustering (ARCHITECTURE §9). §12.3 and §12.4 describe the residual metadata visible to relays.

**What each party learns.**

| Party | Learns | Defined in |
|---|---|---|
| Relay, blob host | The ARCHITECTURE §5 budget, including the admission keys registered with it and, if it serves push, which tokens wake the same device | §12.3, §12.4, §10.4.1 |
| Push proxy | Device push handles and wake-up timing | ARCHITECTURE §5 item 7, §11.7.1 |
| TURN server | A valid credential, a source address, and opaque media | §6.11 |
| SFU | Participant connections, encrypted media frames, and the admission keys registered with it | §6.6 |
| Sequencer | As stated in §14.4.6 | §14.4.6 |
| Registration service (CO) | Which admission keys it registers with which IOs, and when | §5.2.2, §10.5.3 |
| Space endpoint (CO) | Which members and invitees fetch Space state, admission keys, and broadcast keys, and when | §3.4 |
| DM admission host (one member's identity host, initially the initiator's) | Which DM group IDs its own user's client requests admission keys for, and when, and, from later requests, when members or devices are removed or the group moves to it; not the group's other members, except its own users whose clients also request keys for the group | §4.6 |
| KeyPackage host (CO) | When a user's KeyPackages are fetched, and which groups send that user a Welcome | §5.2.1.1, §4.6 |
| TURN credential service (CO) | Which members request credentials, and so call attendance | §6.11 |
| Provisioning service (CO) | The employee's IdP identity, devices, registrations, and revocations | §2.5 |
| Compliance logger and recorder (CO) | Plaintext and media in scope of the compliance configuration | §7, §6.12 |
| Group members | Each other's DIDs and devices (MLS leaves), the credentials those leaves carry, presence, typing, and call state | §5.2.1, §5.2.1.5, §5.3, §6.2 |
| Anyone | DID documents and their full logs, display profiles, and public Space state and advertisements | §2.1, §2.3, §10.3.2 |

**DM admission host.** The admission host serves no member list and no member other than its own user, which authenticates to it by the §3.5 exchange (§4.6). Every other member reads the admission key from its GroupContext, so the host does not learn the other members' DIDs, except those of its own users whose clients also request keys for the group, or when they are active. When no host's user remains a member, the remaining members' clients move the `agora_admission` extension to another member's identity host (§4.6.4), after which the old host learns nothing more. An operator that runs both an identity host and relays sees, for a DM it hosts and carries, its own user's DID and the group's traffic at its relays (ARCHITECTURE §9). A DM admission host SHOULD therefore list relays it does not operate in the group's `relays`.

**Compliance archives and DM admission keys.** A compliance record carries the `GroupContext` of its epoch (§7.4), so a logger's archive of a DM group holds that group's admission key seed. The logger, as a member, already holds that key. Anyone given the archive can compute the group's channel tokens; this is accepted.

**Identity credentials.** Every member of a group, including a compliance logger or recorder, learns the claims disclosed in the `agora_credentials` entries of every leaf (§5.2.1.5). An entry placed in a published KeyPackage is also exposed to everyone allowed to fetch that KeyPackage, which is why clients omit it by default. Relays and other IOs never see the extension (ARCHITECTURE §5). Identical credential bytes in several groups let the members of those groups link the holder across them, beyond what the shared DID already links, and a fixed issuer signature or status-list index links the holder across issuers' verifiers as well. Clients SHOULD carry the fewest credentials and claims a group needs, and SHOULD use a selective-disclosure format such as SD-JWT VC with a fresh presentation for each group, disclosing only the claims that group's policy uses. Checking revocation can reveal the holder's activity to the status list's host; clients SHOULD fetch whole status lists and cache them rather than query per credential.

**Minimization.** A DID document and its log are public and permanent (§2.1, §2.5.6). A provisioning service SHOULD omit optional verification-method metadata such as `meta.deviceLabel` and `meta.platform` (§2.5.4), or use values that do not contain a person's name. CO services SHOULD NOT retain requester DIDs, network addresses, or request timing beyond what operation and abuse handling require, and SHOULD state their retention in the CO's member-facing policy.

**Deletion and erasure.** Content addressing and signed chains limit what can be erased:

- Can be removed: blobs and cached envelopes (unpin, expiry, and retention, §5.2.4, §10.4.3), display profiles (by publishing a new profile, §2.3), and records held only at a Space endpoint. Copies that other parties already hold under the same CID remain valid, so removal stops serving and does not recall.
- Cannot be removed without breaking verification: DID logs (a DID document MAY be blanked but MUST NOT be removed, §2.5.6), the Space state chain (§3.3), the moderation log (§4.5), and the compliance record chain (§7.4).
- Crypto-shredding: message ciphertext and group-encrypted blobs (§3.4) are keyed from MLS epoch secrets. Once every member has deleted an epoch's secrets (§12.1), ciphertext held by any IO for that epoch can no longer be decrypted.

**Out of scope.** Legal hold, archive disposal after `retentionDays`, and responses to data-subject requests are CO policy carried out on CO records under the CO's own controls (ARCHITECTURE §4). An IO holds nothing attributable to a member beyond network-layer metadata within its declared retention (ARCHITECTURE §5 item 1).

## 12.12 Key Compromise and Incident Response

*Binds: both.*

This section gives the response to the loss or compromise of each class of key that is not covered elsewhere. Device keys are revoked as in §2.2 and §2.5.5. MLS leaf keys heal through Updates (§12.2). A device key revoked in a DID log does not invalidate objects that were verified against the DID document in effect when they were accepted; it stops new objects from verifying (§13.1.1).

**Space owner key.** For a `did:webvh` or `did:plc` owner, loss of the owner's devices is repaired by recovering the owner's DID (§2.4, §2.5.8), after which the owner signs Space state again. Theft is worse: a thief can sign Space state, including a transfer of ownership to itself.

1. The owner revokes the stolen device key in its DID log (§2.2, §2.5.5) and sends an `IdentityChanged` notice (§2.7). Space state signed with that key after the revocation fails verification.
2. If the thief has already transferred ownership, or can keep signing because the owner cannot revoke the key, the guardians named in `guardian` transfer ownership to a DID the rightful owner controls (§4.1). The completion SHOULD replace `guardian` if a guardian was involved.
3. If the Space has no `guardian`, or the thief defeats the guardian procedure by objecting with the stolen key (§4.1), the only remedy is to found a new Space and move members to it.

A Space run by an organization avoids most of this by having an organization service DID as owner (§4.1), whose keys the organization holds under its own custody and recovery.

**Recovery and social recovery keys.** A thief who holds the recovery key or the social recovery key (§2.4.1, §2.4.2) can sign a `RecoveryAssertion` and take over the DID. Detection and the 24-hour rule of §2.4.4 apply. When the user suspects exposure, while it still controls the DID:

1. It writes a DID log entry (or, for `did:plc`, a PLC operation) that removes the exposed key from `recoverableIdentity` and from the authorized update keys, and in the same entry registers a new recovery key generated as in §2.4.1.
2. For a social recovery key, it generates a new recovery secret, distributes new shares to its guardians (§2.4.2), registers the new derived key, and removes the old one. Guardians SHOULD delete the old shares; an old share cannot reconstruct the new secret.
3. It sends an `IdentityChanged` notice (§2.7) so that members re-resolve the DID.

A `RecoveryAssertion` names the log head it applies to in `prev` (§2.4.1), so an assertion signed with the old key before the rotation cannot be replayed afterward.

**Provisioning service keys.** A thief who holds the provisioning service's DID update key can add device keys to every employee DID it hosts (§2.5). Each addition is a DID log entry visible to resolvers (§2.1). A provisioning service SHOULD use `did:webvh` pre-rotation, committing in each log entry to the hash of the next update key, so that a stolen current update key cannot authorize a successor of the thief's choosing. On detection the organization:

1. Rotates the update key: a log entry for each hosted DID, signed with a still-trusted or pre-rotated update key and carrying its witness proofs, that authorizes the new update key and removes the old one. If no such key remains for a DID, that DID cannot be taken back, and the organization provisions a new DID for the user (§2.5.3).
2. Lists every device key added by entries signed with the stolen key since the earliest possible compromise, and revokes each one not confirmed by its user (§2.5.5), in bulk.
3. Has each affected user's remaining devices remove the leaves of the revoked keys from the user's groups (§2.2) and send an `IdentityChanged` notice (§2.7).
4. Tells affected users and their Space admins which keys were revoked, so they can judge which messages to distrust. Messages signed by a revoked key before its revocation remain verifiable; whether to trust them is a human decision.

**Compliance logger and recorder keys.** The rotation and compromise procedure, including re-encryption of archives, is in §7.9.

**Channel admission key.** A leaked admission key lets its holder have envelopes admitted and recognize the channel's traffic at a relay (§12.4). It gives no access to content. The CO rotates the key (§5.2.2), registers the new key, and deregisters the old one (§10.5.3).

**Relay signing key.** A planned rotation keeps the old key as `deprecated` during an overlap (§10.2.6). On compromise the relay instead publishes its manifest with the key's `status` set to `"revoked"`. Peer relays MUST reject, with no overlap, every request signed with a key their latest copy of the manifest marks `revoked`, and SHOULD refetch a peer's manifest when a signature from that peer fails to verify, so that a revocation takes effect at the next failed or suspicious request. The relay operator also notifies each CO it holds a `ServiceAgreement` with through the agreement's contact. A relay key signs no member-visible content, so members need do nothing.

**Billing key.** The billing DID signs `ServiceAgreement`s and admission key registrations (§10.5.1, §10.5.3). For a planned rotation the CO adds a new key to the billing DID's document and signs new requests with it; agreements and registrations need not change. On compromise, a thief can register admission keys of its choosing under the CO's agreements, consuming the CO's quota, or deregister the CO's keys, interrupting delivery; it cannot read content or forge messages. The CO:

1. Removes the stolen key from the billing DID's document, or, if the billing DID itself is lost, creates a new billing DID.
2. Signs with each IO a new `ServiceAgreement` that supersedes the old one (§10.5.1). From then on the IO rejects registrations under the old agreement, and the keys registered under it lapse after one hour.
3. Within that hour, re-registers every current admission key under each new agreement (§10.5.3), including any key the thief deregistered.

Admission keys and `channelToken`s do not change in this procedure, so members notice nothing: channels survive renewal or replacement of an agreement. The billing key gives no access to admission private keys, so their rotation is not needed.

## 12.13 Identity Credentials

*Binds: clients.*

The credentials of §5.2.1.5 are claims by their issuers, not by Agora. A client that acts on them, for example by accepting a DM sender (§4.6.3) or by assigning a role (§4.2), relies on its own trust policy; two clients with different policies can treat the same leaf differently, and that is intended.

A credential in a leaf stays there until its holder replaces the leaf, so it can be expired or revoked while still present: a client that acts on a credential SHOULD check its expiry and status when it acts, not only when it first sees the leaf. A decision already taken, such as a role assignment, is not undone by the credential's later revocation; the CO undoes it by its usual means (§4.2, §4.5). A member can omit a credential it holds, so the absence of a credential proves nothing. The subject check of §5.2.1.5 prevents one member from presenting another's credential; it does not protect against an issuer that issues false claims or a compromised issuer key, which is the trusting client's risk.

---
