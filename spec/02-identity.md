# 2. Identity

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 56–484 (§2).


*Binds: CO.*

## 2.1 User DID

Every user has a **Decentralized Identifier (DID)** as their persistent identity. DIDs are self-certifying: possession of the private key proves identity without any registry or certificate authority. The recommended methods are:

- **`did:key`** — derives the DID directly from the public key. Entirely self-contained, no DNS dependency, works offline. Preferred for individuals.
- **`did:web`** — anchors identity to a DNS domain. Appropriate for organizations that want verifiable institutional identity tied to their domain name.

> **Open (agora-pozi.6):** A `did:key` document is derived from its key and cannot be updated, so `did:key` alone cannot carry the device-key additions (§2.2), profile `service` entry (§2.3), or recovery-key registration and rotation (§2.4) this section relies on; the DID method that provides these is undecided.

A user's DID document contains two key roles:

- **`authentication`** key — Ed25519 key used to sign all protocol messages, space state mutations, and moderation actions.
- **`keyAgreement`** key — X25519 key used as the source for MLS `KeyPackage` init keys and for encrypting per-device payloads such as social recovery shares.

**Reference implementations:** `did-key` generation and resolution is implemented by:
- TypeScript/JS: [`@digitalbazaar/did-io`](https://github.com/digitalbazaar/did-io), [`@transmute/did-key`](https://github.com/transmute-industries/did-key.js)
- Go: [`github.com/nuts-foundation/go-did`](https://github.com/nuts-foundation/go-did)
- Rust: [`did-key` crate](https://crates.io/crates/did-key), [`ssi` crate (Spruce Systems)](https://github.com/spruceid/ssi)
- Python: [`pyld`](https://github.com/digitalbazaar/pyld) + [`pymultibase`](https://github.com/pinnaculum/py-multibase)

Example DID document:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:key:z6Mk...",
  "verificationMethod": [{
    "id": "did:key:z6Mk...#keys-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:key:z6Mk...",
    "publicKeyMultibase": "z6Mk..."
  }],
  "authentication": ["did:key:z6Mk...#keys-1"],
  "keyAgreement": [{
    "id": "did:key:z6Mk...#keys-2",
    "type": "X25519KeyAgreementKey2020",
    "controller": "did:key:z6Mk...",
    "publicKeyMultibase": "zABC..."
  }]
}
```

The `keyAgreement` key is the source material for MLS KeyPackage generation. The `authentication` key signs all protocol messages.

## 2.2 Device Keys

A single user identity can span multiple physical devices. MLS handles multi-device membership natively — each device is a separate MLS leaf node in every group the user belongs to. Where the DID method supports document updates, the user's DID document lists all active device verification keys as separate `verificationMethod` entries.

> **Open (agora-pozi.6):** `did:key` documents are immutable and cannot list additional device keys; how a `did:key` user's devices are bound to the identity is undecided.

Revoking a device means removing its leaf node from all relevant MLS trees with an MLS `Remove` proposal for that device's leaf, committed by a member permitted to commit (any of the user's other devices, or another member authorized under Space state), and removing the corresponding `verificationMethod` from the DID document. An `Update` commit refreshes only the committer's own leaf and MUST NOT be used to revoke another device. Both operations must be performed for full revocation; removing only one leaves residual access.

## 2.3 User Display Profile

The user profile is stored separately from the DID document, as an IPLD node addressed by CID. Where the DID method supports `service` entries in an updatable document, the DID document links to the current profile CID via a `service` endpoint:

```json
{
  "service": [{
    "id": "did:web:example.com:users:alice#profile",
    "type": "AgoraProfile",
    "serviceEndpoint": "ipfs://bafyrei..."
  }]
}
```

Profile schema (JSON-LD):

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "UserProfile",
  "did": "did:key:z6Mk...",
  "displayName": "alice",
  "avatarCID": "bafyrei...",
  "statusText": "building things",
  "updatedAt": "2026-03-12T00:00:00Z"
}
```

Profile updates are signed by the user's authentication key and gossiped on `v1/agora/discovery`. Because the profile is content-addressed, clients can cache it indefinitely — a stale profile will produce a CID mismatch against the current DID document's `serviceEndpoint`, prompting a refresh.

## 2.4 Account Recovery

`did:key` identities are self-certifying — the private key is the identity. Loss of all device private keys is permanent identity loss with no protocol-level remedy unless recovery mechanisms are established in advance. Agora specifies three complementary recovery mechanisms. Clients SHOULD implement all three; users SHOULD activate at least one before they need it.

> **Open (agora-pozi.6):** Registering a recovery key and rotating device keys both require an updatable DID document, which `did:key` does not provide; recovery for `did:key` users awaits the DID method decision.

### 2.4.1 Recovery Key

A **recovery key** is a dedicated Ed25519 keypair generated at account creation time and stored entirely separately from all device keys — typically printed as a recovery phrase, stored on an air-gapped device, or written to paper and placed somewhere physically secure. It is registered in the DID document as a verification method with a `recoverableIdentity` relationship:

```json
{
  "verificationMethod": [
    {
      "id": "did:web:example.com:users:alice#keys-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:web:example.com:users:alice",
      "publicKeyMultibase": "z6Mk..."
    },
    {
      "id": "did:web:example.com:users:alice#recovery-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:web:example.com:users:alice",
      "publicKeyMultibase": "zRECOVERY..."
    }
  ],
  "recoverableIdentity": ["did:web:example.com:users:alice#recovery-1"]
}
```

The recovery key is **never used for normal protocol operations**. Its only function is to sign a `RecoveryAssertion` that rotates the DID document to a new device key when all other device keys are lost:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RecoveryAssertion",
  "did": "did:web:example.com:users:alice",
  "newDeviceKey": "base64url(new Ed25519 pubkey)",
  "revokeAll": true,
  "ts": "2026-03-12T12:00:00.000Z",
  "recoverySig": "base64url..."
}
```

`recoverySig` is an Ed25519 signature by the recovery key, signed per §13.1.1. `revokeAll: true` instructs peers to treat all previously registered device keys as revoked once the assertion takes effect (§2.4.4). The `RecoveryAssertion` is published to `v1/agora/discovery` and appended to the user's profile IPLD chain. Relays take no action on a `RecoveryAssertion`: they hold no per-DID sessions, and a revoked device loses channel access when its leaves are Removed (§2.2).

**The recovery key is the root of trust for identity recovery.** Its private key MUST NOT leave a secure offline boundary — paper backup, air-gapped device, or hardware security key. It MUST NOT be imported into any networked device or software keystore under any circumstances during normal operation.

### 2.4.2 Social Recovery

Social recovery designates a set of **guardians** — other Agora users trusted to collectively authorize identity recovery. A threshold scheme (e.g., 3-of-5) ensures that no single guardian can unilaterally recover the account, and that losing any one guardian does not prevent recovery.

**Setup:** The client generates a random 256-bit recovery secret `S`, splits it into `N` shares using Shamir's Secret Sharing (SSS), and encrypts each share individually to a guardian's X25519 key agreement key:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SocialRecoveryConfig",
  "did": "did:key:z6Mk...",
  "threshold": 3,
  "totalShares": 5,
  "guardians": [
    {
      "guardianDID": "did:key:z6MkGuardian1...",
      "encryptedShare": "base64url..."
    }
  ],
  "recoveryCommitment": "base64url(SHA256(S))",
  "ts": "2026-03-12T12:00:00.000Z",
  "sig": "base64url..."
}
```

The `SocialRecoveryConfig` is stored in the user's profile IPLD chain. `recoveryCommitment` is a SHA-256 hash of `S` used to verify share reconstruction without revealing `S` before recovery begins.

**Recovery:** The user contacts `threshold` guardians out-of-band and requests their shares. Each guardian decrypts their encrypted share using their X25519 key and transmits it to the recovering user. The user reconstructs `S` from the shares, verifies it against `recoveryCommitment`, then uses `S` to derive a new signing key and publish a `RecoveryAssertion` signed with it.

`S` itself is never stored anywhere — it exists only transiently during setup (to split) and recovery (to reconstruct). Guardians hold encrypted shares; relays hold nothing related to recovery.

**Guardian obligations:** Guardians SHOULD confirm their designation when first asked. The account owner SHOULD periodically verify that all guardians remain reachable and responsive, and should re-key shares when a guardian becomes unreachable or leaves the system.

**Reference implementations for SSS:** [`hashicorp/vault` SSS](https://github.com/hashicorp/vault/tree/main/shamir) (Go), [`secrets.js`](https://github.com/grempe/secrets.js) (JS), [`sharks` crate](https://crates.io/crates/sharks) (Rust).

### 2.4.3 Encrypted Backup

A client MAY export an encrypted backup of device key material and MLS state to a user-chosen location — a local file, cloud storage, IPFS, or any other storage the user controls. The backup is encrypted with a user-chosen passphrase using Argon2id key derivation:

```
backupKey = Argon2id(passphrase, salt, m=65536, t=3, p=4)
backup    = AEAD_AES_256_GCM(backupKey, backupPayload)
```

`backupPayload` is a CBOR-encoded structure. Its contents depend on the key storage model in use:

**Software keystore (extractable keys).** All key material is available for export:
- All device Ed25519 private keys
- All device X25519 private keys
- Current MLS key material for all group memberships
- The recovery key private key (if one was generated and held in software — see §2.4.1)
- Timestamp and DID

**HSM / Secure Enclave / non-extractable keys.** Private keys cannot be exported by design. The backup contains only:
- The MLS group state exported via the MLS key export interface (RFC 9420 §11)
- Public keys and DID document
- Timestamp and DID

A backup from a non-extractable-key environment restores MLS continuity but cannot restore the private keys themselves. Restoring identity on a new device requires either (a) the social recovery mechanism (§2.4.2), or (b) generating a new device keypair and having an existing device add it as a new MLS leaf.

Clients SHOULD clearly communicate to the user which type of backup their platform produces. The backup file is self-describing: it includes the Argon2id parameters, the DID, and a `backupType` field (`"full"` or `"stateOnly"`).

Clients SHOULD prompt users to export an encrypted backup at account creation and after any significant key rotation event. Clients MUST NOT store the backup passphrase anywhere on the device.

**Reference implementations for Argon2id:** [`golang.org/x/crypto/argon2`](https://pkg.go.dev/golang.org/x/crypto/argon2) (Go), [`argon2` npm package](https://www.npmjs.com/package/argon2) (JS/Node), [`argon2` crate](https://crates.io/crates/argon2) (Rust), [`argon2-cffi`](https://pypi.org/project/argon2-cffi/) (Python).

### 2.4.4 Recovery Precedence and Conflict Resolution

The `ts` field of a `RecoveryAssertion` is self-asserted by its signer and MUST NOT be used to order competing assertions: any holder of a recovery credential could backdate it. If multiple recovery mechanisms produce conflicting valid `RecoveryAssertion` messages for the same DID, they are resolved as follows:

- **CO-provisioned identities (§2.5).** The assertion that takes effect is the one reflected in the DID document update signed by the provisioning service (`provisionerSig`, §2.5.7); the order in which that service applies updates is the ordering source. The provisioning service MUST apply recovery assertions for a DID one at a time, and MUST NOT apply a second `RecoveryAssertion` for the same DID within 24 hours of applying one without administrator review; it MUST record the conflict in its audit log. Clients act on the signed DID document, not on the assertion alone.
- **Identities with no provisioning service.** This specification defines no external ordering source. Clients MUST treat competing valid assertions for the same DID as a conflict, MUST NOT apply either automatically, and SHOULD surface the conflict to the user.

> **Open (agora-pozi.6):** An externally ordered record (e.g. a transparency log) for recovery assertions of identities without a provisioning service is undecided.

## 2.5 Enterprise Identity Provisioning (SAML / OIDC)

In enterprise deployments, user identities are managed by the organization via an existing Identity Provider (IdP) — Microsoft Entra ID, Okta, Ping, or any SAML 2.0 / OIDC-compliant IdP. This section specifies how `did:web` identities are provisioned by the organization and how device keys are registered by user agents against that identity, maintaining the correct trust separation: the organization controls the identity namespace and can revoke it; the device controls the private key material, and the organization cannot use it (see §2.5.1 for the limits of this). Vendor-specific integrations are described non-normatively in `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md` and `profiles/universal-idp-did.md`.

### 2.5.1 Trust Separation

The fundamental constraint this section enforces:

- **The organization provisions and owns the `did:web` document.** It controls the DNS domain, the HTTPS endpoint serving the document, and therefore has revocation authority — it can retire any DID it controls by taking down or blanking the document.
- **The user agent generates and owns device private keys.** Private keys are generated inside the device's secure hardware boundary (Secure Enclave, StrongBox, TPM) and never leave it. The organization cannot generate, hold, or retrieve these keys. However, an organization that controls a user's `did:web` document can technically add a key it holds and sign as that user; "the organization cannot impersonate the user" is therefore a policy and audit property (provisioning audit log, `provisionerSig`), not a cryptographic one, unless device keys are anchored independently of the document.
- **Device public keys are registered into the `did:web` document** via an authenticated provisioning endpoint. Authentication uses the IdP token (proving user identity to the org); authorization uses an existing device key signature (proving key possession) or the IdP token alone for first-device enrollment.

This mirrors how S/MIME and WebAuthn work in enterprise: the org manages the certificate or credential binding; the private key never leaves the user's hardware.

> **Open (agora-pozi.6):** Whether device keys are anchored independently of an org-controlled `did:web` document, so that key insertion by the org is detectable or prevented, is undecided.

### 2.5.2 DID Namespace and Document Hosting

The organization provisions `did:web` identities in a controlled namespace:

```
did:web:{orgDomain}:users:{localIdentifier}
```

Resolution: `GET https://{orgDomain}/users/{localIdentifier}/did.json`

Examples:
- `did:web:acme.com:users:alice` → `GET https://acme.com/users/alice/did.json`
- `did:web:acme.com:users:alice.chen` → `GET https://acme.com/users/alice.chen/did.json`

The `localIdentifier` SHOULD be derived from the user's IdP principal (UPN, username, or employee ID) and MUST be stable for the lifetime of the account. It MUST NOT be reassigned to a different person after the original user departs.

The DID document is served by the organization's **DID Provisioning Service** — a lightweight HTTPS service, typically deployed alongside the organization's IdP or directory service. It is a CO component. Relays play no part in identity provisioning and never receive or verify IdP tokens; IdP authentication is between the client, the IdP and the provisioning service. The service:

- Maintains the authoritative DID document for each user in a backing store (LDAP attribute, database, or directory extension)
- Serves documents at the well-known URL path
- Accepts authenticated device key registration requests (§2.5.4)
- Accepts authenticated device revocation requests (§2.5.5)
- Publishes DID document updates to the Agora gossipsub discovery mesh (§3)

### 2.5.3 Initial Provisioning (Onboarding)

When a user is onboarded to Agora, the organization creates a stub DID document containing no device keys. This happens in the same workflow as email account creation — automated via HR system integration or the IdP's provisioning API (SCIM 2.0 is the standard mechanism):

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:web:acme.com:users:alice",
  "verificationMethod": [],
  "authentication": [],
  "keyAgreement": [],
  "service": [{
    "id": "did:web:acme.com:users:alice#agora",
    "type": "AgoraRelay",
    "serviceEndpoint": "wss://relay.acme.com/v1/agora/ws"
  }]
}
```

The stub document is valid and resolvable. It has no keys, so no one can authenticate as Alice yet. The document becomes operational when Alice's first device key is registered in §2.5.4.

The provisioning service MUST record the creation timestamp and provisioning operator identity in an audit log.

### 2.5.4 Device Key Registration

When Alice installs the Agora client on a new device, the client performs the following enrollment sequence:

**Step 1 — Key generation.** The client generates a new device keypair in the secure hardware boundary:
- Ed25519 keypair for `authentication` (signing)
- X25519 keypair for `keyAgreement` (MLS key packages, HPKE)

Neither private key leaves the secure enclave. The client holds only the public keys for transmission.

**Step 2 — IdP authentication.** The client initiates an SAML 2.0 or OIDC authentication flow against the organization's IdP. The user authenticates (password + MFA) and the client receives an IdP token.

**Step 3 — Registration request.** The client sends a signed registration request to the DID Provisioning Service:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "DeviceKeyRegistrationRequest",
  "did": "did:web:acme.com:users:alice",
  "deviceLabel": "Alice's MacBook Pro",
  "deviceEd25519PublicKey": "base64url(Ed25519 pubkey)",
  "deviceX25519PublicKey": "base64url(X25519 pubkey)",
  "platform": "macOS",
  "secureEnclaveAttested": true,
  "ts": "2026-03-12T12:00:00.000Z",
  "idpToken": "base64url(SAML assertion or OIDC id_token)",
  "existingDeviceSig": "base64url(...) | absent for first device"
}
```

`existingDeviceSig` is a signature by an existing registered device key, signed per §13.1.1. For first-device enrollment it is absent. For subsequent devices it MUST be present — the IdP token alone authorizes adding a device only on first enrollment; subsequent enrollment requires proof of an existing authorized device.

`secureEnclaveAttested` is `true` if the platform supports hardware attestation of key generation. When `true`, the provisioning service SHOULD verify the attestation before accepting the key.

**Step 4 — Provisioning service validation.** The service:
1. Verifies the IdP token signature against the IdP's public key
2. Verifies the token is issued for the user matching the `did` in the request
3. Verifies the token is not expired and was issued for the Agora provisioning service audience
4. For non-first-device enrollment: verifies `existingDeviceSig` against a currently registered device key in the DID document
5. Checks that the user account is active (not suspended or offboarded)
6. Checks that the number of registered devices does not exceed the org's configured limit (default: 10)

**Step 5 — DID document update.** On successful validation, the service adds the new device keys to the DID document:

```json
{
  "verificationMethod": [
    {
      "id": "did:web:acme.com:users:alice#device-{deviceKeyFingerprint}",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:web:acme.com:users:alice",
      "publicKeyMultibase": "z...",
      "meta": {
        "deviceLabel": "Alice's MacBook Pro",
        "platform": "macOS",
        "registeredAt": "2026-03-12T12:00:00.000Z",
        "secureEnclaveAttested": true
      }
    },
    {
      "id": "did:web:acme.com:users:alice#device-{deviceKeyFingerprint}-x25519",
      "type": "X25519KeyAgreementKey2020",
      "controller": "did:web:acme.com:users:alice",
      "publicKeyMultibase": "z..."
    }
  ],
  "authentication": ["did:web:acme.com:users:alice#device-{deviceKeyFingerprint}"],
  "keyAgreement": ["did:web:acme.com:users:alice#device-{deviceKeyFingerprint}-x25519"]
}
```

`deviceKeyFingerprint` is the first 16 bytes of the SHA-256 hash of the Ed25519 public key, hex-encoded.

**Step 6 — Gossip publication.** The provisioning service gossips the updated DID document hash on `v1/agora/discovery`.

**Step 7 — KeyPackage upload.** The newly enrolled client generates an initial batch of MLS KeyPackages (§5.2.1) and uploads them to its KeyPackage store, completing enrollment.

> **Open (agora-pozi.10):** Where KeyPackages are stored (CO-hosted endpoint via the DID document, or an IO store as a declared budget extension) is undecided.

### 2.5.5 Device Revocation

Device revocation can be initiated by the user (lost or retired device) or by the organization (employee departure, security incident).

**User-initiated revocation.** From any other enrolled device, the user sends:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "DeviceRevocationRequest",
  "did": "did:web:acme.com:users:alice",
  "revokeDeviceKeyID": "did:web:acme.com:users:alice#device-{fingerprint}",
  "reason": "device-lost | device-retired | security-incident",
  "ts": "2026-03-12T12:00:00.000Z",
  "requestingSig": "base64url(signature by a surviving device key)"
}
```

**Organization-initiated revocation.** An IT administrator authenticates to the provisioning service admin interface and submits a revocation for any device key or for the entire DID (full account suspension):

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "AdminRevocationRequest",
  "did": "did:web:acme.com:users:alice",
  "revokeDeviceKeyID": "did:web:acme.com:users:alice#device-{fingerprint}",
  "revokeAll": false,
  "reason": "employee-offboarding | security-incident | policy-violation",
  "adminDID": "did:web:acme.com:users:it-admin",
  "adminSig": "base64url(...)",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

`revokeAll: true` removes all device keys from the DID document, effectively suspending the account. The DID document remains resolvable but has no `authentication` keys.

**Revocation mechanics.** On receipt of a valid revocation request, the provisioning service:

1. Removes the specified `verificationMethod` entry and its references from `authentication` and `keyAgreement`
2. Records the revocation in the audit log with timestamp, reason, and initiator
3. Gossips a `DeviceRevocation` control message on `v1/agora/discovery` carrying the revoked key ID and a signature by the provisioning service's own signing key
4. Notifies the user's remaining enrolled devices via their push handles (if push proxy is configured)

Relays take no action on a `DeviceRevocation`: they do not authenticate member DIDs, and the revoked device loses channel access when its MLS leaves are Removed (below).

> **Open (agora-pozi.9):** How an IO admits and meters clients without authenticating their DIDs is undecided.

**MLS remediation.** Revocation of a device key does not automatically remove that device's MLS leaf nodes from all groups. The revoked device's client (if still running) SHOULD issue `Remove` self-proposals on all its group memberships. If the device is genuinely lost, other group members MUST issue `Remove` commits when they detect the key is revoked. Space administrators SHOULD run periodic reconciliation to ensure revoked device keys have no active MLS leaves in their channels.

### 2.5.6 Offboarding

When an employee leaves, the organization performs a full account suspension:

1. IdP account is disabled (blocks new IdP token issuance)
2. Admin issues `revokeAll: true` revocation via the provisioning service
3. The DID document is updated to remove all device keys
4. The provisioning service gossips the revocation
5. The organization retains the DID document (does not delete it) for the regulatory retention period
6. After the retention period, the document MAY be blanked (empty `verificationMethod`) but MUST NOT be removed — the URL must remain resolvable to avoid dangling references in archived compliance records

### 2.5.7 Provisioning Service DID Document

The provisioning service itself is a DID-bearing principal:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:web:acme.com:agora:provisioning",
  "verificationMethod": [{
    "id": "did:web:acme.com:agora:provisioning#signing-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:web:acme.com:agora:provisioning",
    "publicKeyMultibase": "z..."
  }],
  "authentication": ["did:web:acme.com:agora:provisioning#signing-1"]
}
```

Every DID document update the provisioning service publishes MUST include a `provisionerSig` field: an Ed25519 signature over the updated DID document by the provisioning service's key, signed per §13.1.1. Clients MUST verify this signature when processing DID document updates received via gossip.

This creates a two-party integrity guarantee: the user's device key proves the user authorized the key, and the provisioner's signature proves the organization accepted and recorded the registration. The provisioner cannot forge an existing device's signature, but it can add a new key (§2.5.1).

### 2.5.8 Relationship to §2.4 Recovery Mechanisms

For enterprise `did:web` identities, the recovery mechanisms of §2.4 interact with organizational authority as follows:

- **Recovery key (§2.4.1):** Valid, but the recovery key can only rotate device keys — it cannot override an organization-initiated `revokeAll`. Recovery keys are appropriate for individual-initiated recovery (lost device, not offboarding).

- **Social recovery (§2.4.2):** Valid for user-initiated recovery. The provisioning service accepts a `RecoveryAssertion` signed by the social recovery reconstructed key as equivalent to an IdP token for first-device enrollment, provided the `recoveryCommitment` in the DID document verifies.

- **Encrypted backup (§2.4.3):** Valid. The backup restores MLS state and device keys. The restored device still needs to be enrolled via §2.5.4 to update the DID document with the restored public key.

- **Org-initiated recovery (helpdesk):** When a user loses all devices and has no recovery key or guardians, the organization can initiate recovery on their behalf: an admin issues a provisioning request (with `existingDeviceSig` absent, substituted by admin authorization) to add a new device key to the user's DID document. This path MUST be logged in the audit trail — it is a privileged operation.


---

