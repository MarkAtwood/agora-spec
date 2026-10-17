# 12. Security Considerations

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 3223–3352 (§13).


*Binds: both.*

## 12.1 Forward Secrecy

MLS provides forward secrecy by design. Each epoch derives a new application secret via the MLS key schedule. Compromise of a member's current epoch key material does not expose prior messages, which were encrypted under previous epoch secrets.

## 12.2 Post-Compromise Security

MLS `Update` proposals (triggered by devices or by time-based policy) ratchet the ratchet tree forward, healing from key compromise. A member whose keys were compromised but who subsequently performs an `Update` commit regains security: the compromised old key material cannot decrypt new messages. Space operators SHOULD enforce periodic key rotation (recommended: 7-day maximum epoch lifetime for active channels).

## 12.3 Relay Trust and Legal Exposure

Relays are untrusted for message content and blind to membership and sender identity. The threat model addressed here is: a Relay operator receives a subpoena or legal demand. What can they produce?

What each operator can be compelled to produce is defined in ARCHITECTURE.md §4: an IO yields only what is inside its observation budget (ARCHITECTURE.md §5), and a CO yields what its own retention policy keeps. The authoritative record for a regulated community is the CO's archive (§7), never a Relay.

**What a Relay can observe:** exactly the ARCHITECTURE.md §5 observation budget: network-layer connection metadata within the retention declared in its manifest, ciphertext envelopes with their size, timing, `channelToken` and expiry hint, verification material and proofs that do not identify the member, CIDs it stores, agreement-keyed quota state, and its own peering relationships.

**What a Relay cannot observe:**
- Message content (MLS E2EE; the Relay never holds decryption keys).
- Sender identity for any message (MLS encrypts the sender data, and the sealed envelope hides the MLS framing, §5.2.2).
- Channel identity from `channelToken` (epoch-rotating derivation from the MLS exporter, non-reversible without group secrets).
- Group membership (no membership list at the Relay layer).
- Message graphs or conversation structure.

**What a Relay cannot do:**
- Forge messages (each message carries the sender's MLS signature inside the sealed envelope, verified by recipients).
- Silently modify history (IPLD content addressing detects tampering).
- Map routing tables across epochs without MLS group secrets.

Clients SHOULD connect to multiple Relays simultaneously. A single Relay going dark (legal seizure, operator shutdown) does not partition a user from their channels as long as at least one other Relay serving that `channelToken` is reachable.

## 12.4 Metadata Leakage

MLS sender-data encryption and the sealed envelope keep sender identity, the MLS group ID and the message kind away from the Relay layer. Residual metadata leakage points:

**IP address**: a Relay sees the connecting IP. Clients requiring IP-level anonymity SHOULD connect via Tor (preferring the Relay's `.onion` endpoint where available, to avoid exit node exposure) or a trusted front-end proxy.

**Timing correlation**: a global passive adversary watching both sender and Relay can correlate message timing. This is a known limitation of all low-latency messaging protocols. Mixing/batching (as in Katzenpost) defeats timing analysis but is incompatible with Discord-like UX latency targets. This is an accepted tradeoff.

**Gossipsub topic subscription**: Relays and mesh peers observe which `channelTokens` a peer subscribes to. Since tokens rotate per epoch, long-term correlation requires capturing multiple epochs' tokens. Clients MAY subscribe to decoy `channelTokens` (random values indistinguishable from real tokens) to obscure their actual channel membership count and pattern. Clients requiring strong subscription privacy SHOULD maintain a fixed subscription count (padding with decoys to a constant) and rotate decoy selections each epoch.

**Presence, typing and DM membership**: presence and typing indicators are MLS application messages, and a DM is an ordinary MLS group addressed by `channelToken`. A Relay sees them only as ciphertext envelopes within the ARCHITECTURE.md §5 budget; it cannot distinguish them from other traffic by type, and it does not learn who is in a DM.

**Tor gossipsub fingerprinting**: as noted in §11.3, gossipsub peer scoring observes message timing and subscription behavior independently of IP. A client connecting via Tor is not fully anonymous at the gossipsub layer. Clients requiring strong anonymity against a Relay-level adversary should treat this as a known residual risk.

**Channel token to channel CID correlation**: the `channelToken` is derived from the MLS exporter with a dedicated label and the `channelCID` as context (§5.2.2). An adversary who obtains a member's group state for an epoch (e.g., via member compromise) can compute the token for any channel they know the CID of. This is acceptable: that compromise already implies full message compromise for that epoch; the token mapping adds no new capability beyond what the compromised group state already provides.

## 12.5 Denial of Service

Gossipsub v1.1 includes peer scoring and flood control built-in. Relays never authenticate client identity (ARCHITECTURE.md S1, §4); a connection opens with a minimal unauthenticated hello that only negotiates the protocol version (§11). Abuse control rests on what a Relay can check without knowing who the client is:

- **Writes** are accepted only with a valid epoch access proof (§5.2.2); envelopes that fail it are rejected.
- **Group registration** requires the CO's billing key under a `RelayServiceAgreement` (§10.5.1).
- **Storage and bandwidth** are bounded by the agreement's quotas (§10.5.1).
- **Connections, subscriptions, history reads and push registrations** are rate-limited per network address and per `channelToken`. Relays MUST enforce per-`channelToken` rate limits on message publication.
- **Under load**, a Relay MAY require a proof-of-work challenge before accepting a connection. This admits clients that share an address, such as Tor users behind one exit, without penalizing all of them for one abuser.

Privacy Pass tokens are a possible future extension. Spam control is local policy; there is no global reputation system (by design; global reputation systems become censorship infrastructure).

## 12.6 Key Storage: HSM and Secure Enclave Guidance

All private key operations in Agora (signing, key agreement, MLS leaf operations) SHOULD be performed inside a hardware-backed secure boundary wherever the platform provides one. The protocol is designed so that no operation requires extracting raw private key bytes to application memory.

**Platform secure boundaries and recommended APIs:**

| Platform | Boundary | API |
|---|---|---|
| macOS / iOS | Secure Enclave (T-series / M-series) | `SecKey` / CryptoKit `SecureEnclave.P256` |
| Android | StrongBox / TEE | `AndroidKeyStore` with `PURPOSE_SIGN` / `PURPOSE_AGREE_KEY` |
| Linux server | TPM 2.0 or hardware HSM | PKCS#11 (`opensc-pkcs11`, `SoftHSM2` for dev), or `tpm2-pkcs11` |
| YubiKey / hardware security key | Secure element | PKCS#11, PIV, or OpenPGP card interface |
| Browser | Platform Authenticator | WebAuthn `PRF` extension (for key derivation); `SubtleCrypto` with non-extractable `CryptoKey` (`extractable: false`) |

**Conformance requirements by operation:**

- **Authentication key signing** (Ed25519 / P-256): MUST use hardware-backed key where available. On platforms that do not support Ed25519 in the secure boundary (such as Secure Enclave, which supports P-256 only), P-256 (`ES256`) MAY be used as the authentication key algorithm for that device. The DID document MUST reflect the actual key type in use. A `did:key` identity key used on several devices is exportable by design (§2.1) and so cannot be a non-extractable hardware key.

- **MLS leaf operations** (KeyPackage generation, Commit signing, Update proposals): MUST use keys held in the secure boundary. `openmls` supports pluggable crypto backends; implementations SHOULD provide a backend that delegates to the platform keystore rather than holding raw key bytes.

- **MLS key schedule / epoch secrets**: these are MLS-internal derived values, not persistent keys. They exist transiently in MLS stack memory during epoch processing and SHOULD NOT be exposed to application code. All operations requiring epoch secret access MUST use the MLS exporter interface (RFC 9420 §11.5) rather than accessing the epoch secret directly.

- **X25519 key agreement** (for encrypting social recovery shares, HPKE operations): SHOULD use hardware-backed key agreement where the platform supports it. Where hardware X25519 is unavailable, software implementation in a sandboxed process is the fallback.

- **Recovery key**: see §2.4.1. This key MUST NOT be in any software keystore. Its signing operation occurs exactly once per recovery event, on an air-gapped device or hardware security key, and the output (`RecoveryAssertion`) is transferred to the networked environment by QR code, USB, or similar one-way channel.

**What the spec does NOT require from application code:** application code MUST NOT have access to raw private key bytes for any of the above. API calls should be of the form "sign this payload with key handle K" or "agree on a shared secret using key handle K and this public key", with the output being a signature or shared secret, not a key.

**Relay operator key storage:** Relay signing keys SHOULD be held in an HSM or TPM-backed keystore on the relay host. Cloud HSM services (AWS CloudHSM, GCP Cloud HSM, Azure Dedicated HSM) are appropriate for hosted relay deployments. At minimum, keys SHOULD be stored in the OS keyring rather than on-disk in plaintext.

## 12.7 Non-Repudiation and Organizational Non-Impersonation

Agora provides a stronger non-repudiation guarantee than any conventional enterprise messaging platform, and a structural property that prevents silent organizational impersonation of users. Both properties emerge from the architecture rather than from policy.

### 12.7.1 Why Conventional Enterprise Platforms Cannot Provide This

In all conventional enterprise messaging and email systems (Microsoft Teams, Slack, Zoom, Exchange/Outlook with S/MIME, Google Workspace), the organization controls the root of trust end-to-end:

- **IdP-based systems (Teams, Slack, Zoom):** An IdP administrator can generate tokens asserting any identity in the tenant. There is no cryptographic artifact in a sent message that ties it to the sender's specific device key rather than to their organizational identity as asserted by the IdP. The organization can produce messages attributed to any user.
- **Enterprise S/MIME:** Standard enterprise deployment involves the CA generating the keypair and holding a copy in key escrow. The CA has the private key. The organization can sign messages as any user whose keypair it escrowed.
- **Exchange mailboxes:** `SendAs` and `FullAccess` permissions are a normal administrative operation. No cryptographic barrier prevents an Exchange admin from sending mail as any user in the tenant.

In all of these systems, impersonation by the organization leaves no mandatory cryptographic trace in the messages themselves.

### 12.7.2 The Agora Architecture

Agora separates the identity namespace from the signing key material at a structural level:

- **DID document (org-controlled, history public):** The organization hosts `did:webvh:{SCID}:{orgDomain}:users:{id}` and holds an update key; it can add, remove, and update key entries in the document (§2.5), but each change is a DID log entry signed with its update key and visible to every resolver (§2.1). This is the identity namespace.
- **Private key material (device-controlled):** Ed25519 signing keys are generated inside the device's secure enclave and never leave it (§12.6). The DID document contains only the public key. The organization receives no copy of the private key at any point; there is no enrollment flow that transmits private key material to the provisioning service (§2.5.4).
- **Per-message signing:** Every Agora message is signed by the sender's device key. The signing key fingerprint is embedded in the message's MLS authenticated data; it is bound to the ciphertext and cannot be altered without invalidating the message's authentication tag.

Consequence: **the organization cannot sign a message as Alice without access to Alice's private key, which it does not have.** The DID document update authority (org-controlled) and the signing authority (device-controlled) are held by different parties and involve different, non-interchangeable key material.

### 12.7.3 The Residual Organizational Capability

The organization retains one path to producing a message attributable to Alice's DID: it can register a new device key via the admin enrollment path (§2.5.8, helpdesk recovery) and sign messages with that key. This operation:

1. **Creates a new DID document entry** with a distinct `deviceKeyFingerprint` and registration timestamp, different from Alice's existing device entries.
2. **Is recorded in the provisioning audit log** (§2.5.5).
3. **Is detectable** by any party that compares the signing key fingerprint in a message against the DID document entry that was active at the time of message creation.

Cryptography does not prevent an organization holding an update key from adding a key to Alice's `did:webvh` document, inside or outside the enrollment path. It does make every such addition auditable: the key can enter the document only through a DID log entry signed with the organization's update key, the log is hash-chained, and resolvers reject a log that does not verify (§2.1). The organization cannot rewrite or hide the entry without producing an invalid history, so Alice, her contacts and auditors can see when each key was added and by which update key, without trusting the organization. Silent impersonation (producing a message indistinguishable from one Alice sent herself) is therefore not possible.

Detectable impersonation through the enrollment path (registering a new device key under Alice's DID) requires a logged admin action and produces a cryptographic artifact that auditors and Alice herself can inspect.

Implementations SHOULD surface device registration events to the DID subject (Alice) via out-of-band notification (email, push) at the time of admin-initiated registration. This converts a detectable-in-principle property into a detectable-in-practice one.

### 12.7.4 Non-Repudiation for Compliance

The combination of per-message device-key signatures and a tamper-evident IPLD compliance archive (§7) provides non-repudiation stronger than email with DKIM or S/MIME in typical enterprise deployment:

- **DKIM** authenticates the sending domain, not the individual sender. An admin with access to the DKIM private key can sign mail on behalf of any address at that domain.
- **Enterprise S/MIME** with key escrow allows the key custodian (typically the organization) to produce valid signatures for any escrowed identity.
- **Agora device-key signatures** can only be produced by the specific hardware device that holds the private key. The compliance archive records both the message content and the signing key fingerprint. A regulator or court can verify that a specific message was produced by a specific device key, and can cross-reference that key's registration in the DID log (§2.1).

This property is relevant for FINRA Rule 17a-4, SEC Rule 17a-4, and MiFID II recordkeeping requirements, where the integrity and authenticity of retained communications are material.

---

