# 2. Identity

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 56–484 (§2).


*Binds: CO.*

## 2.1 User DID

Every user has a **Decentralized Identifier (DID)** as their persistent identity. Agora defines three user DID methods. The individual chooses the method; for an employer-provisioned identity the employer chooses (§2.5). Clients MUST support resolving all three and MUST offer `did:webvh` as the default when creating an identity.

| Capability | `did:webvh` (default) | `did:plc` (opt-in) | `did:key` (opt-in) |
|---|---|---|---|
| Document updates | Yes: hash-chained log, each entry signed by an update key | Yes: operations signed by a rotation key | No: document derived from the key |
| Verifiable history | Yes: the DID log | Yes: the PLC operation log | Not applicable |
| Device list (§2.2) | Yes | Yes | No: identity key copied to each device |
| Per-device revocation | Yes | Yes | No: remedy is a new identity |
| Profile pointer (§2.3) | `service` entry | `service` entry | Pkarr pointer record |
| KeyPackage location | `KeyPackageEndpoint` service entry | `KeyPackageEndpoint` service entry | Pkarr pointer record |
| Recovery (§2.4) | §2.4 | did:plc rotation keys and recovery window | The user's own backup only (§2.4.3) |
| Depends on | A web host serving the log (portable across hosts) | The PLC directory | Nothing (Mainline DHT for the pointer record) |

**`did:webvh`** ([DIF did:webvh v1.0](https://identity.foundation/didwebvh/)) is the default. The DID document is the latest entry of a hash-chained log; each entry is signed by an update key authorized by the previous entry. Resolvers MUST verify the full log and MUST reject a document whose log does not verify. The host serving the log therefore cannot add a key without producing an invalid history, and every change to the document, including who made it, is visible to anyone who resolves it. The DID embeds a self-certifying identifier (SCID) derived from the genesis entry, so the DID can move to a different host or domain while its log continues (§2.5.2). A holder MAY also publish a parallel `did:web` document for compatibility with other systems; Agora clients MUST resolve the `did:webvh` log and MUST NOT accept a key from the `did:web` document that is not in the verified log. The holder keeps the update keys: the user's devices and recovery keys for an individual (§2.4), the provisioning service for an employee (§2.5.1).

**`did:plc`** ([did:plc specification](https://web.plc.directory/spec/v0.1/did-plc)) is opt-in. Updates are operations signed by rotation keys and ordered by the PLC directory, with the recovery window defined by that specification. It relies on the PLC directory being available. It lets a Bluesky user use their existing identity in Agora. Agora keys and service entries are added to the document by ordinary PLC operations.

**`did:key`** is opt-in self-custody. The key is the identity: the document cannot be updated, so there is no device list, no key rotation and no recovery beyond the user's own backup (§2.4.3). A client MUST warn the user, before creating a `did:key` identity, that losing the key loses the identity permanently and that a lost or stolen device cannot be revoked. To use several devices, the user copies the identity private key to each device, for example by restoring an encrypted backup (§2.4.3); the identity key MUST therefore be exportable, unless the user keeps it on a single device or a portable hardware key. Each device is still a separate MLS leaf (§2.2), but removing a device's leaves does not revoke it, because the device retains the identity key; the remedy for a lost or compromised device is a new identity.

A `did:key` user publishes a **Pkarr pointer record**: a BEP-44 mutable item on the Mainline DHT, signed by the identity key and looked up by that key, encoded and refreshed as in §10.3.4.6. It carries only these TXT records:

| Record | Value | Required |
|---|---|---|
| `_agora.` | `v=1` | Yes |
| `_kp._agora.` | `url=<KeyPackageEndpoint URL>`: the user's `KeyPackageEndpoint` (§2.5.4, §7.8.2) | Yes |
| `_profile._agora.` | `cid=<profile CID>`: the current profile node (§2.3) | No |

Clients MUST verify the BEP-44 signature against the key in the `did:key` identifier before using any field. The record MUST NOT name a relay or other IO (ARCHITECTURE §2).

`did:key` also remains in use outside user identity, for device keys and for some service identities.

A user's DID document contains two key roles:

- **`authentication`** key: Ed25519 key used to sign all protocol messages, space state mutations, and moderation actions.
- **`keyAgreement`** key: X25519 key used as the source for MLS `KeyPackage` init keys and for encrypting per-device payloads such as social recovery shares.

**Reference implementations:** for `did:webvh` and `did:plc`, see the implementations listed by their specifications. `did-key` generation and resolution is implemented by:
- TypeScript/JS: [`@digitalbazaar/did-io`](https://github.com/digitalbazaar/did-io), [`@transmute/did-key`](https://github.com/transmute-industries/did-key.js)
- Go: [`github.com/nuts-foundation/go-did`](https://github.com/nuts-foundation/go-did)
- Rust: [`did-key` crate](https://crates.io/crates/did-key), [`ssi` crate (Spruce Systems)](https://github.com/spruceid/ssi)
- Python: [`pyld`](https://github.com/digitalbazaar/pyld) + [`pymultibase`](https://github.com/pinnaculum/py-multibase)

Example DID document:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:example.com:alice",
  "verificationMethod": [{
    "id": "did:webvh:QmSCID...:example.com:alice#keys-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:webvh:QmSCID...:example.com:alice",
    "publicKeyMultibase": "z6Mk..."
  }],
  "authentication": ["did:webvh:QmSCID...:example.com:alice#keys-1"],
  "keyAgreement": [{
    "id": "did:webvh:QmSCID...:example.com:alice#keys-2",
    "type": "X25519KeyAgreementKey2020",
    "controller": "did:webvh:QmSCID...:example.com:alice",
    "publicKeyMultibase": "zABC..."
  }]
}
```

The `keyAgreement` key is the source material for MLS KeyPackage generation. The `authentication` key signs all protocol messages.

## 2.2 Device Keys

A single user identity can span multiple physical devices. MLS handles multi-device membership natively: each device is a separate MLS leaf node in every group the user belongs to. For `did:webvh` and `did:plc`, the user's DID document lists all active device verification keys as separate `verificationMethod` entries, and this section applies. A `did:key` identity has no device list: every device holds the same identity key, and a device cannot be revoked (§2.1).

Each device signs with its own Ed25519 device key: its MLS leaf signatures, its KeyPackages and its JWS signatures (§13.1.1). A WebAuthn credential (passkey) is not a device key and MUST NOT be listed as a device `verificationMethod`, because an authenticator signs only `authenticatorData || SHA-256(clientDataJSON)` and cannot produce MLS signatures, JWS signatures, `did:webvh` log proofs or PLC operations. Passkeys serve only to authenticate the user to the identity host (the employer's provisioning service, §2.5, or the host the user chose, §2.1) when a device is registered, and to protect a stored browser device key (below). Only the identity host parses WebAuthn; no other Agora component verifies WebAuthn assertions.

Native apps SHOULD hold the device key in hardware-backed storage (§12.6). Browser clients generate the device key with WebCrypto Ed25519 and sign only through a non-extractable `CryptoKey`, so everyday signing needs no user gesture. A browser client SHOULD store its device key wrapped under a key derived from a passkey through the WebAuthn PRF extension and unwrap it once per session (§12.6); a copied browser profile is then useless without the passkey. WebCrypto Ed25519 is available in Firefox 129, Safari 17 and Chrome 137 and later; a browser without it MAY use a reviewed JavaScript or WebAssembly Ed25519 implementation, which holds key bytes in page memory and is weaker. This paragraph does not apply to `did:key`, whose identity key is exportable by design (§2.1).

A device whose stored key is lost, for example when browser storage is cleared, registers a new device key as a new device, and the user SHOULD revoke the old device as below. A stolen device is revoked as below, by removing its key from the DID document.

Revoking a device means removing its leaf node from all relevant MLS trees with an MLS `Remove` proposal for that device's leaf, committed by a member permitted to commit (any of the user's other devices, or another member authorized under Space state), and removing the corresponding `verificationMethod` from the DID document. An `Update` commit refreshes only the committer's own leaf and MUST NOT be used to revoke another device. Both operations must be performed for full revocation; removing only one leaves residual access.

## 2.3 User Display Profile

The user profile is stored separately from the DID document, as an IPLD node addressed by CID. For `did:webvh` and `did:plc`, the DID document links to the current profile CID via a `service` endpoint; a `did:key` user publishes it in the `_profile` field of the Pkarr pointer record (§2.1):

```json
{
  "service": [{
    "id": "did:webvh:QmSCID...:example.com:alice#profile",
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

Profile updates are signed by the user's authentication key and gossiped on `v1/agora/discovery`. Because the profile is content-addressed, clients can cache it indefinitely; a stale profile will produce a CID mismatch against the current DID document's `serviceEndpoint` (or the Pkarr `_profile` field), prompting a refresh.

## 2.4 Account Recovery

Loss of all device private keys is permanent identity loss with no protocol-level remedy unless recovery mechanisms are established in advance. Agora specifies three complementary recovery mechanisms. Clients SHOULD implement all three; users SHOULD activate at least one before they need it.

Applicability by DID method (§2.1):

- **`did:webvh`:** all of §2.4 applies. The recovery key (§2.4.1) and the social recovery key (§2.4.2) MUST also be authorized update keys of the DID log, so that the device key named in a `RecoveryAssertion` is written into the document by a log entry signed with the same key.
- **`did:plc`:** recovery uses did:plc rotation keys and the recovery window of the did:plc specification. The recovery key and the social recovery key are registered as did:plc rotation keys instead of `recoverableIdentity` verification methods, and a PLC operation signed with one of them takes the place of the `RecoveryAssertion`. Encrypted backup (§2.4.3) applies unchanged.
- **`did:key`:** only encrypted backup (§2.4.3) applies. There is no recovery once the identity key is lost.

### 2.4.1 Recovery Key

A **recovery key** is a dedicated Ed25519 keypair generated at account creation time and stored entirely separately from all device keys, typically printed as a recovery phrase, stored on an air-gapped device, or written to paper and placed somewhere physically secure. It is registered in the DID document as a verification method with a `recoverableIdentity` relationship:

```json
{
  "verificationMethod": [
    {
      "id": "did:webvh:QmSCID...:example.com:alice#keys-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:example.com:alice",
      "publicKeyMultibase": "z6Mk..."
    },
    {
      "id": "did:webvh:QmSCID...:example.com:alice#recovery-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:example.com:alice",
      "publicKeyMultibase": "zRECOVERY..."
    }
  ],
  "recoverableIdentity": ["did:webvh:QmSCID...:example.com:alice#recovery-1"]
}
```

The recovery key is **never used for normal protocol operations**. Its only function is to sign a `RecoveryAssertion` that rotates the DID document to a new device key when all other device keys are lost:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RecoveryAssertion",
  "did": "did:webvh:QmSCID...:example.com:alice",
  "newDeviceKey": "base64url(new Ed25519 pubkey)",
  "revokeAll": true,
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The assertion is signed per §13.1.1 by a key listed in the DID document's `recoverableIdentity` relationship: either the recovery key or the social recovery key (§2.4.2). Verifiers MUST reject a `RecoveryAssertion` whose signature does not verify under a `recoverableIdentity` key of the DID document in effect before the assertion. `revokeAll: true` instructs peers to treat all previously registered device keys as revoked once the assertion takes effect (§2.4.4). The `RecoveryAssertion` is published to `v1/agora/discovery` and appended to the user's profile IPLD chain. Relays take no action on a `RecoveryAssertion`: they hold no per-DID sessions, and a revoked device loses channel access when its leaves are Removed (§2.2).

**The recovery key is the root of trust for identity recovery.** Its private key MUST NOT leave a secure offline boundary (paper backup, air-gapped device, or hardware security key). It MUST NOT be imported into any networked device or software keystore under any circumstances during normal operation.

### 2.4.2 Social Recovery

Social recovery designates a set of **guardians**: other Agora users trusted to collectively authorize identity recovery. A threshold scheme (e.g., 3-of-5) ensures that no single guardian can unilaterally recover the account, and that losing any one guardian does not prevent recovery.

**Setup:** The client generates a random 256-bit recovery secret `S`, splits it into `N` shares using Shamir's Secret Sharing (SSS), and encrypts each share individually to a guardian's X25519 key agreement key. The client also derives the **social recovery key** from `S`:

```
seed = HKDF-SHA256(IKM = S, salt = "" (zero-length), info = "agora/v1/social-recovery-key", L = 32)
```

`seed` is used as an Ed25519 private key seed (RFC 8032 §5.1.5). The client MUST register the derived public key in the DID document as a verification method listed in `recoverableIdentity`, exactly as the recovery key is registered (§2.4.1), with fragment `#social-recovery-1`. This public key is the recovery commitment: it lets anyone check both a reconstruction of `S` and a `RecoveryAssertion` signed with the derived key. After registration the client MUST erase `S` and `seed`.

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "SocialRecoveryConfig",
  "did": "did:webvh:QmSCID...:example.com:alice",
  "threshold": 3,
  "totalShares": 5,
  "guardians": [
    {
      "guardianDID": "did:key:z6MkGuardian1...",
      "encryptedShare": "base64url..."
    }
  ],
  "recoveryKeyID": "did:webvh:QmSCID...:example.com:alice#social-recovery-1",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The `SocialRecoveryConfig` is signed per §13.1.1 by `did` and is stored in the user's profile IPLD chain; it carries only the encrypted shares and a `recoveryKeyID` pointer. The recovery commitment itself (the social recovery public key) is held only in the DID document, and verifiers MUST take it from there, not from the `SocialRecoveryConfig`.

**Recovery:** The user contacts `threshold` guardians out-of-band and requests their shares. Each guardian decrypts their encrypted share using their X25519 key and transmits it to the recovering user. The user reconstructs `S` from the shares, re-derives the social recovery key as above, and checks that its public key matches the `#social-recovery-1` key in the DID document; a mismatch means a share is wrong. The user then publishes a `RecoveryAssertion` (§2.4.1) naming a freshly generated device key in `newDeviceKey` and signed with the social recovery key. Because `S` is now known to the recovering device, the client SHOULD then re-run setup with a new `S` and replace the `#social-recovery-1` key.

`S` itself is never stored anywhere; it exists only transiently during setup (to split) and recovery (to reconstruct). Guardians hold shares only. They never hold `S`, the derived key, or any signing authority; relays hold nothing related to recovery.

**Guardian obligations:** Guardians SHOULD confirm their designation when first asked. The account owner SHOULD periodically verify that all guardians remain reachable and responsive, and should re-key shares when a guardian becomes unreachable or leaves the system.

**Reference implementations for SSS:** [`hashicorp/vault` SSS](https://github.com/hashicorp/vault/tree/main/shamir) (Go), [`secrets.js`](https://github.com/grempe/secrets.js) (JS), [`sharks` crate](https://crates.io/crates/sharks) (Rust).

### 2.4.3 Encrypted Backup

A client MAY export an encrypted backup of device key material and MLS state to a user-chosen location: a local file, cloud storage, IPFS, or any other storage the user controls. The backup is encrypted with a user-chosen passphrase using Argon2id key derivation:

```
backupKey = Argon2id(passphrase, salt, m=65536, t=3, p=4)
backup    = AEAD_AES_256_GCM(backupKey, backupPayload)
```

`backupPayload` is a CBOR-encoded structure. Its contents depend on the key storage model in use:

**Software keystore (extractable keys).** All key material is available for export:
- All device Ed25519 private keys
- All device X25519 private keys
- Current MLS key material for all group memberships
- The recovery key private key (if one was generated and held in software; see §2.4.1)
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

- **`did:webvh` identities.** The DID log is the ordering source: the assertion that takes effect is the one written into the log (§2.4). If a resolver sees two different log entries with the same version number for one DID, it MUST treat the DID as in conflict, MUST NOT apply either automatically, and SHOULD surface the conflict to the user.
- **`did:plc` identities.** The PLC directory orders operations, subject to the did:plc recovery window.
- **CO-provisioned identities (§2.5).** In addition, the assertion that takes effect is the one reflected in the DID document update made by the provisioning service and signed by it (§2.5.7); the order in which that service applies updates is the ordering source. The provisioning service MUST apply recovery assertions for a DID one at a time, and MUST NOT apply a second `RecoveryAssertion` for the same DID within 24 hours of applying one without administrator review; it MUST record the conflict in its audit log. Clients act on the signed DID document, not on the assertion alone.
- **`did:key` identities.** `RecoveryAssertion` does not apply (§2.4).

## 2.5 Enterprise Identity Provisioning (SAML / OIDC)

In enterprise deployments, user identities are managed by the organization via an existing Identity Provider (IdP) such as Microsoft Entra ID, Okta, Ping, or any SAML 2.0 / OIDC-compliant IdP. The employer chooses the DID method (§2.1), normally `did:webvh`; this section specifies how `did:webvh` identities are provisioned by the organization and how device keys are registered by user agents against that identity, maintaining the correct trust separation: the organization controls the identity namespace and can revoke it; the device controls the private key material, and the organization cannot use it (see §2.5.1 for the limits of this). Vendor-specific integrations are described non-normatively in `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md` and `profiles/universal-idp-did.md`.

### 2.5.1 Trust Separation

The constraint this section enforces:

- **The organization provisions and hosts the `did:webvh` log and holds an update key for it.** It controls the DNS domain and the HTTPS endpoint serving the log, and therefore has revocation authority: it can retire any DID it controls by writing a log entry that removes all keys or deactivates the DID.
- **The user agent generates and owns device private keys.** Private keys are generated inside the device's secure hardware boundary (Secure Enclave, StrongBox, TPM) and never leave it. The organization cannot generate, hold, or retrieve these keys. An organization holding an update key can still add a key it holds and sign as that user, but it can do so only by writing a log entry signed with its own update key. Every resolver of the DID sees that entry in the document history, so organizational impersonation is auditable by the user, her contacts and auditors without trusting the organization (§12.7.3).
- **Device public keys are registered into the `did:webvh` document** via an authenticated provisioning endpoint. Authentication uses the IdP token (proving user identity to the org); authorization uses an existing device key signature (proving key possession) or the IdP token alone for first-device enrollment.

This mirrors how S/MIME and WebAuthn work in enterprise: the org manages the certificate or credential binding; the private key never leaves the user's hardware.

### 2.5.2 DID Namespace and Document Hosting

The organization provisions `did:webvh` identities in a controlled namespace:

```
did:webvh:{SCID}:{orgDomain}:users:{localIdentifier}
```

Resolution: `GET https://{orgDomain}/users/{localIdentifier}/did.jsonl` (the DID log, verified per §2.1)

Example:
- `did:webvh:QmSCID...:acme.com:users:k7f3qd2m` → `GET https://acme.com/users/k7f3qd2m/did.jsonl`

The `localIdentifier` MUST be stable for the lifetime of the account and MUST NOT be reassigned to a different person after the original user departs. It MUST NOT be derived from a person's name, email address, UPN, or any other attribute that can change. The organization chooses the source: an employee ID, the IdP's immutable user ID, or a random value minted by the provisioning service. The provisioning service keeps the mapping to the IdP principal in its private store; the mapping is not published.

A DID is not a display name. Clients identify a person by the display profile (§2.3) and the organization's signed credentials, never by parsing the DID.

Because the DID is stable, group memberships, compliance records and audit trails stay keyed to one identifier for a person's whole tenure. A domain change does not break the identity: the provisioning service SHOULD create DIDs with did:webvh portability enabled, so that the log moves to the new domain with the same SCID and records the previous DID in `alsoKnownAs`. Clients MUST treat two `did:webvh` DIDs with the same SCID and one continuous verified log as the same identity.

The DID document is served by the organization's **DID Provisioning Service**, a lightweight HTTPS service, typically deployed alongside the organization's IdP or directory service. It is a CO component. Relays play no part in identity provisioning and never receive or verify IdP tokens; IdP authentication is between the client, the IdP and the provisioning service. The service:

- Maintains the authoritative DID document for each user in a backing store (LDAP attribute, database, or directory extension)
- Serves documents at the well-known URL path
- Accepts authenticated device key registration requests (§2.5.4)
- Accepts authenticated device revocation requests (§2.5.5)
- Publishes DID document updates to the Agora gossipsub discovery mesh (§3)

### 2.5.3 Initial Provisioning (Onboarding)

When a user is onboarded to Agora, the organization creates a stub DID document containing no device keys. This happens in the same workflow as email account creation, automated via HR system integration or the IdP's provisioning API (SCIM 2.0 is the standard mechanism):

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
  "verificationMethod": [],
  "authentication": [],
  "keyAgreement": [],
  "service": []
}
```

The DID document MUST NOT name an infrastructure operator (relay or other IO) as the user's service endpoint; clients choose IOs independently of identity (ARCHITECTURE §2). Service entries limited to CO- or user-chosen endpoints MAY be added. The provisioning service hosts its users' KeyPackages and MUST add a `KeyPackageEndpoint` service entry (§7.8.2) pointing at itself before the first device enrolls (§2.5.4).

The stub document is valid and resolvable. It has no keys, so no one can authenticate as Alice yet. The document becomes operational when Alice's first device key is registered in §2.5.4.

The provisioning service MUST record the creation timestamp and provisioning operator identity in an audit log.

### 2.5.4 Device Key Registration

When Alice installs the Agora client on a new device, the client performs the following enrollment sequence:

**Step 1: Key generation.** The client generates a new device keypair in the secure hardware boundary:
- Ed25519 keypair for `authentication` (signing)
- X25519 keypair for `keyAgreement` (MLS key packages, HPKE)

Neither private key leaves the secure enclave. The client holds only the public keys for transmission. A browser client generates its Ed25519 device key as a non-extractable WebCrypto key (§2.2, §12.6) and sets `secureEnclaveAttested` to `false`. If the user authenticates with a passkey during Step 2, the WebAuthn exchange is between the user and the IdP or the provisioning service; the passkey never becomes a device key (§2.2).

**Step 2: IdP authentication.** The client initiates an SAML 2.0 or OIDC authentication flow against the organization's IdP. The user authenticates (password + MFA) and the client receives an IdP token.

**Step 3: Registration request.** The client sends a signed registration request to the DID Provisioning Service:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "DeviceKeyRegistrationRequest",
  "did": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
  "deviceLabel": "Alice's MacBook Pro",
  "deviceEd25519PublicKey": "base64url(Ed25519 pubkey)",
  "deviceX25519PublicKey": "base64url(X25519 pubkey)",
  "platform": "macOS",
  "secureEnclaveAttested": true,
  "ts": "2026-03-12T12:00:00.000Z",
  "idpToken": "base64url(SAML assertion or OIDC id_token)"
}
```

The request is signed per §13.1.1 by an existing registered device key. For first-device enrollment the envelope `sig` is absent. For subsequent devices it MUST be present: the IdP token alone authorizes adding a device only on first enrollment; subsequent enrollment requires proof of an existing authorized device.

`secureEnclaveAttested` is `true` if the platform supports hardware attestation of key generation. When `true`, the provisioning service SHOULD verify the attestation before accepting the key.

**Step 4: Provisioning service validation.** The service:
1. Verifies the IdP token signature against the IdP's public key
2. Verifies the token is issued for the user matching the `did` in the request
3. Verifies the token is not expired and was issued for the Agora provisioning service audience
4. For non-first-device enrollment: verifies the request's signature (§13.1.1) against a currently registered device key in the DID document
5. Checks that the user account is active (not suspended or offboarded)
6. Checks that the number of registered devices does not exceed the org's configured limit (default: 10)

**Step 5: DID document update.** On successful validation, the service adds the new device keys to the DID document:

```json
{
  "verificationMethod": [
    {
      "id": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{deviceKeyFingerprint}",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
      "publicKeyMultibase": "z...",
      "meta": {
        "deviceLabel": "Alice's MacBook Pro",
        "platform": "macOS",
        "registeredAt": "2026-03-12T12:00:00.000Z",
        "secureEnclaveAttested": true
      }
    },
    {
      "id": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{deviceKeyFingerprint}-x25519",
      "type": "X25519KeyAgreementKey2020",
      "controller": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
      "publicKeyMultibase": "z..."
    }
  ],
  "authentication": ["did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{deviceKeyFingerprint}"],
  "keyAgreement": ["did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{deviceKeyFingerprint}-x25519"]
}
```

`deviceKeyFingerprint` is the first 16 bytes of the SHA-256 hash of the Ed25519 public key, hex-encoded.

**Step 6: Gossip publication.** The provisioning service gossips the updated DID document hash on `v1/agora/discovery`.

**Step 7: KeyPackage upload.** The newly enrolled client generates an initial batch of MLS KeyPackages (§5.2.1) and uploads them, signed with the new device key, to the user's `KeyPackageEndpoint` hosted by the provisioning service (§2.5.3), completing enrollment. KeyPackages live with whoever runs the user's identity: the employer's provisioning service for an employee, or a host the individual chooses or runs, named by the `KeyPackageEndpoint` service entry (`did:webvh`, `did:plc`) or the Pkarr pointer record (`did:key`) (§2.1). Relays hold no KeyPackages. The host rate-limits KeyPackage fetches to resist draining, and the client keeps a last-resort KeyPackage available there (§5.2.1.1).

### 2.5.5 Device Revocation

Device revocation can be initiated by the user (lost or retired device) or by the organization (employee departure, security incident).

**User-initiated revocation.** From any other enrolled device, the user sends:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "DeviceRevocationRequest",
  "did": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
  "revokeDeviceKeyID": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{fingerprint}",
  "reason": "device-lost | device-retired | security-incident",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The request is signed per §13.1.1 by a surviving device key of `did`.

**Organization-initiated revocation.** An IT administrator authenticates to the provisioning service admin interface and submits a revocation for any device key or for the entire DID (full account suspension):

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "AdminRevocationRequest",
  "did": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m",
  "revokeDeviceKeyID": "did:webvh:QmSCID...:acme.com:users:k7f3qd2m#device-{fingerprint}",
  "revokeAll": false,
  "reason": "employee-offboarding | security-incident | policy-violation",
  "adminDID": "did:webvh:QmSCID...:acme.com:users:it-admin",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The request is signed per §13.1.1 by `adminDID`. `revokeAll: true` removes all device keys from the DID document, effectively suspending the account. The DID document remains resolvable but has no `authentication` keys.

**Revocation mechanics.** On receipt of a valid revocation request, the provisioning service:

1. Removes the specified `verificationMethod` entry and its references from `authentication` and `keyAgreement`, by a DID log entry signed with its update key
2. Records the revocation in the audit log with timestamp, reason, and initiator
3. Gossips a `DeviceRevocation` control message on `v1/agora/discovery` carrying the revoked key ID, signed per §13.1.1 by the provisioning service's own signing key
4. Notifies the user's remaining enrolled devices via their push handles (if push proxy is configured)

Relays take no action on a `DeviceRevocation`: they never authenticate client identity (§12.5), and the revoked device loses channel access when its MLS leaves are Removed (below).

**MLS remediation.** Revocation of a device key does not automatically remove that device's MLS leaf nodes from all groups. The revoked device's client (if still running) SHOULD issue `Remove` self-proposals on all its group memberships. If the device is lost, other group members MUST issue `Remove` commits when they detect the key is revoked. Space administrators SHOULD run periodic reconciliation to ensure revoked device keys have no active MLS leaves in their channels.

### 2.5.6 Offboarding

When an employee leaves, the organization performs a full account suspension:

1. IdP account is disabled (blocks new IdP token issuance)
2. Admin issues `revokeAll: true` revocation via the provisioning service
3. The DID document is updated to remove all device keys
4. The provisioning service gossips the revocation
5. The organization retains the DID document (does not delete it) for the regulatory retention period
6. After the retention period, the document MAY be blanked (empty `verificationMethod`) but MUST NOT be removed; the URL must remain resolvable to avoid dangling references in archived compliance records

### 2.5.7 Provisioning Service DID Document

The provisioning service itself is a DID-bearing principal:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:acme.com:agora:provisioning",
  "verificationMethod": [{
    "id": "did:webvh:QmSCID...:acme.com:agora:provisioning#signing-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:webvh:QmSCID...:acme.com:agora:provisioning",
    "publicKeyMultibase": "z..."
  }],
  "authentication": ["did:webvh:QmSCID...:acme.com:agora:provisioning#signing-1"]
}
```

Every DID document update the provisioning service publishes MUST be signed per §13.1.1 by the provisioning service's key, with the JWS in the update's envelope `sig`. Clients MUST verify this signature when processing DID document updates received via gossip.

This creates a two-party integrity guarantee: the user's device key proves the user authorized the key, and the provisioner's signature proves the organization accepted and recorded the registration. The provisioner cannot forge an existing device's signature. It can add a new key, but only by a DID log entry signed with its update key, which every resolver sees (§2.5.1).

### 2.5.8 Relationship to §2.4 Recovery Mechanisms

For enterprise `did:webvh` identities, the recovery mechanisms of §2.4 interact with organizational authority as follows:

- **Recovery key (§2.4.1):** Valid, but the recovery key can only rotate device keys; it cannot override an organization-initiated `revokeAll`. Recovery keys are appropriate for individual-initiated recovery (lost device, not offboarding).

- **Social recovery (§2.4.2):** Valid for user-initiated recovery. The provisioning service accepts a `RecoveryAssertion` as equivalent to an IdP token for first-device enrollment, provided its signature verifies under the social recovery key (`#social-recovery-1`, a `recoverableIdentity` key) in the user's DID document.

- **Encrypted backup (§2.4.3):** Valid. The backup restores MLS state and device keys. The restored device still needs to be enrolled via §2.5.4 to update the DID document with the restored public key.

- **Org-initiated recovery (helpdesk):** When a user loses all devices and has no recovery key or guardians, the organization can initiate recovery on their behalf: an admin issues a provisioning request (with no existing-device signature, substituted by admin authorization) to add a new device key to the user's DID document. This path MUST be logged in the audit trail; it is a privileged operation, and the added key appears in the DID log as an entry signed with the provisioning service's update key.


---

