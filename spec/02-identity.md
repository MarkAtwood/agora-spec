# 2. Identity

> Binds: CO. Source: import/agora-protocol-spec-unified.md lines 56–484 (§2).

## 2.1 User DID

Every user has a **Decentralized Identifier (DID)** as their persistent identity. Agora defines three user DID methods. The individual chooses the method; for an employer-provisioned identity the employer chooses (§2.5). Clients MUST support resolving all three, and SHOULD offer `did:webvh` as the default when creating an identity.

| Capability | `did:webvh` (default) | `did:plc` (opt-in) | `did:key` (opt-in) |
|---|---|---|---|
| Document updates | Yes: hash-chained log, each entry signed by an update key | Yes: operations signed by a rotation key | No: document derived from the key |
| Verifiable history | Yes: the DID log | Yes: the PLC operation log | Not applicable |
| Device list (§2.2) | Yes | Yes | No: identity key copied to each device; each device binds its own MLS leaf key (§5.2.1) |
| Per-device revocation | Yes | Yes | No: remedy is a new identity |
| Profile pointer (§2.3) | `service` entry | `service` entry | Pkarr pointer record |
| KeyPackage and Welcome location | `AgoraKeyPackageEndpoint` service entry | `AgoraKeyPackageEndpoint` service entry | Pkarr pointer record |
| Witnesses | Required for CO-provisioned DIDs, optional for individuals | Not applicable (the PLC directory orders operations) | Not applicable |
| Recovery (§2.4) | §2.4 | `did:plc` rotation keys and recovery window | The user's own backup only (§2.4.3) |
| Depends on | A web host serving the log (portable across hosts) | The PLC directory | Nothing (Mainline DHT for the pointer record) |

**`did:webvh`** ([DIF did:webvh v1.0](https://identity.foundation/didwebvh/)) is the default. The DID document is the latest entry of a hash-chained log. Each entry is signed by an update key authorized by the previous entry. The holder keeps the update keys: the user's devices and recovery keys for an individual (§2.4), the provisioning service for an employee (§2.5.1). Resolvers MUST verify the full log and MUST reject a document whose log does not verify. A host that does not hold an update key therefore cannot add a key without producing an invalid history. Every change in a log a resolver receives, including which update key made it, is visible to that resolver. Hash chaining alone does not stop a holder of an update key from serving different valid logs to different resolvers (a split view) or from serving an old prefix of the log (a rollback). Witnesses (below) address this.

The DID embeds a self-certifying identifier (SCID) derived from the genesis entry, so the DID can move to a different host or domain while its log continues (§2.5.2). A holder MAY also publish a parallel `did:web` document for compatibility with other systems. Agora clients MUST resolve the `did:webvh` log and MUST NOT accept a key from the `did:web` document that is not in the verified log.

**Witnesses.** A `did:webvh` DID provisioned by an employer or other Communications Operator (CO) (§2.5) MUST use `did:webvh` witnesses as defined by the `did:webvh` specification. Its `witness` parameter MUST list at least one witness DID that the organization does not control, and its threshold MUST be set so that every accepted log entry carries a proof from at least one such witness. Clients MUST verify witness proofs for such a DID and MUST reject a log entry that lacks the proofs its parameters require. An individual MAY use witnesses, and clients MUST verify them when the log declares them. Without witnesses, a verified log proves only that each entry a resolver received was signed by an authorized update key; it gives no protection against a split view or a rollback by whoever holds an update key or serves the log.

**`did:plc`** ([did:plc specification](https://web.plc.directory/spec/v0.1/did-plc)) is opt-in. Updates are operations signed by rotation keys and ordered by the PLC directory, with the recovery window defined by that specification. It relies on the PLC directory being available. It lets a Bluesky user use their existing identity in Agora. Agora keys and service entries are added to the document by ordinary PLC operations.

**`did:key`** is opt-in self-custody. The key is the identity: the document cannot be updated, so there is no device list, no key rotation and no recovery beyond the user's own backup (§2.4.3). A client SHOULD warn the user, before creating a `did:key` identity, that losing the key loses the identity permanently and that a lost or stolen device cannot be revoked.

To use several devices, the user copies the identity private key to each device, for example by restoring an encrypted backup (§2.4.3). The identity key MUST therefore be exportable, unless the user keeps it on a single device or a portable hardware key. The identity key is not an MLS leaf key. Each device generates its own MLS leaf signature key and signs it with the identity key in a device-binding statement carried in its leaf, which members verify (§5.2.1). The identity key signs the device's JWS signatures (§13.1.1) and KeyPackage publications (§5.2.1.1). Each device is a separate MLS leaf (§2.2), but there is no device list and no per-device revocation. Removing a device's leaves does not revoke it, because the device retains the identity key and can bind new leaf keys. The remedy for a lost or compromised device is a new identity.

`did:key` also remains in use outside user identity, for device keys and for some service identities.

A `did:key` user publishes a **Pkarr pointer record**: a BEP-44 mutable item on the Mainline DHT, signed by the identity key and looked up by that key, encoded and refreshed as in §10.3.4.6. It carries these TXT records, plus the optional service records listed in §10.3.4.6:

| Record | Value | Required |
|---|---|---|
| `_agora.` | `v=1` | Yes |
| `_kp._agora.` | `url=<KeyPackageEndpoint URL>`: the user's `KeyPackageEndpoint` (§5.2.1.1), which also receives the user's Welcomes | Yes |
| `_profile._agora.` | `cid=<profile CID>`: the bare CID, with no scheme, of the current profile node (§2.3) | No |

Clients MUST verify the BEP-44 signature against the key in the `did:key` identifier before using any field. The record MUST NOT name a relay or other Infrastructure Operator (IO) (ARCHITECTURE §2).

A **`KeyPackageEndpoint` service entry** is a DID document `service` entry whose `type` is `AgoraKeyPackageEndpoint` and whose `serviceEndpoint` is the endpoint URL. The endpoint protocol is defined in §5.2.1.1. A user's KeyPackages are fetched from, and the user's Welcomes are delivered by POST to, this endpoint. For `did:key` the endpoint is the one named in the Pkarr pointer record.

A user's DID document contains two key roles:

- **`authentication`** keys: the Ed25519 device keys (§2.2), one per device. A device signs its protocol messages, Space state mutations and moderation actions with its own key.
- **`keyAgreement`** keys: X25519 keys used only for Hybrid Public Key Encryption (HPKE) outside MLS groups, such as encrypting social recovery shares (§2.4.2). MLS KeyPackage init keys and leaf encryption keys are generated fresh for each KeyPackage and are unrelated to the DID document (§5.2.1.1).

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

**Reference implementations.** For `did:webvh` and `did:plc`, see the implementations listed by their specifications. `did-key` generation and resolution is implemented by:
- TypeScript/JS: [`@digitalbazaar/did-io`](https://github.com/digitalbazaar/did-io), [`@transmute/did-key`](https://github.com/transmute-industries/did-key.js)
- Go: [`github.com/nuts-foundation/go-did`](https://github.com/nuts-foundation/go-did)
- Rust: [`did-key` crate](https://crates.io/crates/did-key), [`ssi` crate (Spruce Systems)](https://github.com/spruceid/ssi)
- Python: [`pyld`](https://github.com/digitalbazaar/pyld) + [`pymultibase`](https://github.com/pinnaculum/py-multibase)

## 2.2 Device Keys

A single user identity can span multiple physical devices. MLS handles multi-device membership natively: each device is a separate MLS leaf node in every group the user belongs to. For `did:webvh` and `did:plc`, the user's DID document lists all active device verification keys as separate `verificationMethod` entries, and this section applies. A `did:key` identity has no device list: every device holds the same identity key, each device has its own MLS leaf signature key bound to the identity by a device-binding statement (§5.2.1), and a device cannot be revoked (§2.1).

Each device signs with its own Ed25519 device key: its MLS leaf signatures, its KeyPackages and its JWS signatures (§13.1.1). A WebAuthn credential (passkey) is not a device key and MUST NOT be listed as a device `verificationMethod`, because an authenticator signs only `authenticatorData || SHA-256(clientDataJSON)` and cannot produce MLS signatures, JWS signatures, `did:webvh` log proofs or PLC operations. Passkeys serve only to authenticate the user to the identity host (the employer's provisioning service, §2.5, or the host the user chose, §2.1) when a device is registered, and to protect a stored browser device key (below). Only the identity host parses WebAuthn; no other Agora component verifies WebAuthn assertions.

Native apps SHOULD hold the device key in hardware-backed storage (§12.6). Where the device's hardware cannot hold Ed25519 keys (for example, a secure enclave that supports only P-256), the device key is held in software and stored wrapped by a key that the hardware holds, so that the stored key is unusable without that hardware. The device key is still Ed25519; no other algorithm is used for device keys (§13.1.1). Browser clients generate the device key with WebCrypto Ed25519 and sign only through a non-extractable `CryptoKey`, so everyday signing needs no user gesture. A browser client SHOULD store its device key wrapped under a key derived from a passkey through the WebAuthn PRF extension and unwrap it once per session (§12.6); a copied browser profile is then useless without the passkey. WebCrypto Ed25519 is available in Firefox 129, Safari 17 and Chrome 137 and later; a browser without it MAY use a reviewed JavaScript or WebAssembly Ed25519 implementation, which holds key bytes in page memory and is weaker. This paragraph does not apply to `did:key`, whose identity key is exportable by design (§2.1).

Revoking a device takes two operations: a member permitted to commit (any of the user's other devices, or another member authorized under Space state) removes the device's leaf node from all relevant MLS trees by committing an MLS `Remove` proposal for that leaf, and the corresponding `verificationMethod` is removed from the DID document. Full revocation requires both operations; removing only one leaves residual access. An `Update` Commit refreshes only the committer's own leaf and MUST NOT be used to revoke another device. Other members learn of a revocation by resolving the DID, prompted by an `IdentityChanged` notice (§2.7).

A device whose stored key is lost, for example when browser storage is cleared, registers a new device key as a new device, and the user SHOULD revoke the old device as above. A stolen device is revoked as above, by removing its key from the DID document.

## 2.3 User Display Profile

The user profile is stored separately from the DID document, as an IPLD node addressed by CID. A `did:key` user publishes the current profile CID in the `_profile._agora` record of the Pkarr pointer record (§2.1). For `did:webvh` and `did:plc`, the DID document links to it with a `service` endpoint:

```json
{
  "service": [{
    "id": "did:webvh:QmSCID...:example.com:alice#profile",
    "type": "AgoraProfile",
    "serviceEndpoint": "ipfs://bafkrei..."
  }]
}
```

Profile schema:

```json
{
  "@type": "UserProfile",
  "did": "did:webvh:QmSCID...:example.com:alice",
  "displayName": "alice",
  "avatarCID": "bafkrei...",
  "statusText": "building things",
  "updatedAt": "2026-03-12T00:00:00Z"
}
```

A user updates the profile by publishing a new profile node and pointing the `AgoraProfile` service entry (a new DID log entry or PLC operation) or the `_profile._agora` record at its CID. Profile updates are not gossiped. Instead, the user's devices send an `IdentityChanged` notice (§2.7) to the user's groups. Because the profile is content-addressed, clients can cache it indefinitely. A stale profile produces a CID mismatch against the current DID document's `serviceEndpoint` (or the Pkarr `_profile._agora` record), which prompts a refresh.

`displayName` and `statusText` are free-form text for people to read. The publisher MUST store each in the form produced by the enforcement rule of the PRECIS Nickname profile (RFC 8266). Clients MUST apply that rule before displaying or comparing either string, and treat a string the rule rejects as absent. When displaying them, clients MUST isolate each string as a bidirectional run (Unicode Standard Annex #9, for example with U+2068 FIRST STRONG ISOLATE and U+2069 POP DIRECTIONAL ISOLATE) so that it cannot reorder surrounding text. Clients SHOULD apply the confusable detection of Unicode Technical Standard #39 to the display names of the members of a group or Space and SHOULD warn the user when two different DIDs have confusable display names, because clients identify a person by the display profile (§2.5.2). Length limits on these strings, where a client or CO sets them, count Unicode scalar values.

## 2.4 Account Recovery

Loss of all device private keys is permanent identity loss with no protocol-level remedy unless recovery mechanisms are established in advance. Agora specifies three complementary recovery mechanisms. Clients SHOULD implement all three; users SHOULD activate at least one before they need it.

Applicability by DID method (§2.1):

- **`did:webvh`.** All of §2.4 applies. For a self-hosted (individually held) `did:webvh`, the recovery key (§2.4.1) and the social recovery key (§2.4.2) MUST also be authorized update keys of the DID log, so that the device key named in a `RecoveryAssertion` is written into the document by a log entry signed with the same key. For a CO-provisioned `did:webvh`, they are `recoverableIdentity` keys only, and the provisioning service writes the log entry (§2.5.8).
- **`did:plc`.** Recovery uses `did:plc` rotation keys and the recovery window of the `did:plc` specification. The recovery key and the social recovery key are registered as `did:plc` rotation keys instead of `recoverableIdentity` verification methods, and a PLC operation signed with one of them takes the place of the `RecoveryAssertion`. Because `did:plc` gives earlier-listed rotation keys priority within the recovery window, the recovery key (§2.4.1) MUST be listed above the social recovery key (§2.4.2): a key kept offline outranks one reconstructed from guardians' shares. Encrypted backup (§2.4.3) applies unchanged.
- **`did:key`.** Only encrypted backup (§2.4.3) applies. There is no recovery once the identity key is lost.

### 2.4.1 Recovery Key

A **recovery key** is a dedicated Ed25519 keypair generated at account creation time and stored entirely separately from all device keys. It is typically printed as a recovery phrase, stored on an air-gapped device, or written to paper and placed somewhere physically secure. It is registered in the DID document as a verification method with a `recoverableIdentity` relationship:

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
  "@type": "RecoveryAssertion",
  "did": "did:webvh:QmSCID...:example.com:alice",
  "prev": "7-QmLogEntryHash...",
  "newDeviceKey": "base64url(new Ed25519 pubkey)",
  "revokeAll": true,
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The assertion is signed per §13.1.1 by a key listed in the DID document's `recoverableIdentity` relationship: either the recovery key or the social recovery key (§2.4.2). `prev` is the `versionId` of the DID log entry the assertion applies to. Verifiers MUST reject a `RecoveryAssertion` whose signature does not verify under a `recoverableIdentity` key of the DID document at `prev`, and MUST reject one whose `prev` is not the current head of the log, so that an old assertion cannot be replayed after later changes. `revokeAll: true` instructs peers to treat all previously registered device keys as revoked once the assertion takes effect (§2.4.4).

A `RecoveryAssertion` takes effect only through the DID log. For a self-hosted `did:webvh`, the recovering client writes the new device key into the log by an entry signed with the same `recoverableIdentity` key (§2.4). For a CO-provisioned identity, the recovering client submits the assertion to the provisioning service (§2.5.8). The assertion is not gossiped or otherwise published. Other members learn of the change by resolving the DID (§2.7). A recovered device holds no MLS state and joins the user's groups as a new device (§2.6). If the user has no other device, members permitted to add the recovered device must add it again. Relays take no action on a recovery: they hold no per-DID sessions, and a revoked device loses channel access when its leaves are Removed (§2.2).

**The recovery key is the root of trust for identity recovery.** Its private key MUST NOT leave a secure offline boundary (paper backup, air-gapped device, or hardware security key). It MUST NOT be imported into any networked device or software keystore under any circumstances during normal operation.

### 2.4.2 Social Recovery

Social recovery designates a set of **guardians**: other Agora users trusted to collectively authorize identity recovery. A threshold scheme (for example, 3-of-5) means that no single guardian can unilaterally recover the account, and that losing any one guardian does not prevent recovery.

**Setup.** The client generates a random 256-bit recovery secret `S`, splits it into `N` shares using Shamir's Secret Sharing (SSS), and encrypts each share individually to a guardian's X25519 key agreement key. SSS operates byte-wise over GF(2^8) with the reduction polynomial x^8 + x^4 + x^3 + x + 1 (the AES field). Each share is encoded as `x || y`: `x` is one nonzero byte, distinct per share, and `y` is the 32 bytes of the share values. Each encoded share is encrypted with HPKE (RFC 9180) in base mode with DHKEM(X25519, HKDF-SHA256), HKDF-SHA256 and AES-128-GCM. The recipient key is the first key listed in the guardian's `keyAgreement` relationship at setup. The encryption uses `info = "agora/v1/recovery-share" || did` (the owner's DID as UTF-8) and empty associated data. `encryptedShare` is the HPKE `enc` followed by the ciphertext. Implementations MUST produce this encoding whatever SSS library they use. The client also derives the **social recovery key** from `S`:

```
seed = HKDF-SHA256(IKM = S, salt = "" (zero-length), info = "agora/v1/social-recovery-key", L = 32)
```

`seed` is used as an Ed25519 private key seed (RFC 8032 §5.1.5). The client MUST register the derived public key in the DID document as a verification method listed in `recoverableIdentity`, exactly as the recovery key is registered (§2.4.1), with fragment `#social-recovery-1`. This public key is the recovery commitment: it lets anyone check both a reconstruction of `S` and a `RecoveryAssertion` signed with the derived key. After registration the client MUST erase `S` and `seed`.

The client records the setup in a `SocialRecoveryConfig`:

```json
{
  "@type": "SocialRecoveryConfig",
  "did": "did:webvh:QmSCID...:example.com:alice",
  "threshold": 3,
  "totalShares": 5,
  "guardians": [
    {
      "guardianDID": "did:key:z6MkGuardian1...",
      "guardianKeyID": "did:key:z6MkGuardian1...#z6LSGuardian1...",
      "encryptedShare": "base64url..."
    }
  ],
  "recoveryKeyID": "did:webvh:QmSCID...:example.com:alice#social-recovery-1",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The `SocialRecoveryConfig` is signed per §13.1.1 by `did`. `guardianKeyID` names the `keyAgreement` key each share was encrypted to. The client keeps the configuration in the user's self-group (§2.6) and sends each guardian its own entry in a direct message (DM) group (§4.6). The configuration is not published, because it names the user's guardians. It carries only the encrypted shares and a `recoveryKeyID` pointer. The recovery commitment itself (the social recovery public key) is held only in the DID document, and verifiers MUST take it from there, not from the `SocialRecoveryConfig`.

**Recovery.** The user contacts `threshold` guardians out of band and requests their shares. Each guardian decrypts their encrypted share using their X25519 key and returns it to the recovering user out of band, over a channel the two already trust. The user reconstructs `S` from the shares, re-derives the social recovery key as above, and checks that its public key matches the `#social-recovery-1` key in the DID document. A mismatch means a share is wrong. The user then creates a `RecoveryAssertion` (§2.4.1) naming a freshly generated device key in `newDeviceKey` and signed with the social recovery key. Because `S` is now known to the recovering device, the client SHOULD then re-run setup with a new `S` and replace the `#social-recovery-1` key.

`S` itself is never stored anywhere; it exists only transiently during setup (to split) and recovery (to reconstruct). Guardians hold shares only. They never hold `S`, the derived key, or any signing authority. Relays hold nothing related to recovery.

**Guardian obligations.** Guardians SHOULD confirm their designation when first asked. The account owner SHOULD periodically verify that all guardians remain reachable and responsive, and should re-key shares when a guardian becomes unreachable or leaves the system.

**Reference implementations for SSS.** [`hashicorp/vault` SSS](https://github.com/hashicorp/vault/tree/main/shamir) (Go), [`secrets.js`](https://github.com/grempe/secrets.js) (JS), [`sharks` crate](https://crates.io/crates/sharks) (Rust).

### 2.4.3 Encrypted Backup

A client MAY export an encrypted backup to a user-chosen location: a local file, cloud storage, IPFS, or any other storage the user controls. The backup is encrypted with a user-chosen passphrase using Argon2id key derivation:

```
backupKey = Argon2id(passphrase, salt, m=65536, t=3, p=4, L=32)
backup    = header || nonce || AES-256-GCM-Seal(backupKey, nonce, backupPayload, aad = header)
```

`salt` is 16 random bytes and `nonce` is 12 random bytes, both fresh for each backup. `header` is the CBOR encoding of the map below. It is bound as associated data so that its parameters cannot be swapped:

```cddl
BackupHeader = {
  v: 1,
  did: tstr,
  backupType: "keys" / "history" / "keys+history",
  argon2: { salt: bstr .size 16, m: uint, t: uint, p: uint },
  ts: tstr,                 ; RFC 3339 UTC
}

BackupPayload = {
  ? deviceKeys: [* { ed25519: bstr .size 32, x25519: bstr .size 32 }],  ; private keys
  ? history: bstr,          ; a HistoryArchive (§2.6)
}
```

`deviceKeys` is present only for a software keystore whose keys are extractable, and for `did:key` it holds the identity key. A backup from a non-extractable keystore (hardware-backed, or a non-extractable WebCrypto key) cannot contain private keys and carries only `history`. The recovery key MUST NOT be included in any backup (§2.4.1).

A backup MUST NOT contain MLS epoch secrets, secret-tree state or other ratchet state. Restoring a snapshot would rewind sender generations, which receivers that have already deleted those keys refuse, and would keep keys that the RFC 9420 §9.2 deletion schedule requires to be deleted. A restored device joins each of the user's groups as a new leaf (§2.6). Decryptable history comes from the `history` archive, not from MLS state. A device restored from backup MUST NOT use the restored device keys while the source device is active (§2.6). If the restored key is still listed in the DID document and the source device is lost, the restored device replaces it; otherwise the device registers a new device key (§2.2, §2.5.4).

Clients SHOULD clearly communicate to the user which type of backup their platform produces. Clients SHOULD prompt users to export an encrypted backup at account creation and after any device key change. Clients MUST NOT store the backup passphrase anywhere on the device.

**Reference implementations for Argon2id.** [`golang.org/x/crypto/argon2`](https://pkg.go.dev/golang.org/x/crypto/argon2) (Go), [`argon2` npm package](https://www.npmjs.com/package/argon2) (JS/Node), [`argon2` crate](https://crates.io/crates/argon2) (Rust), [`argon2-cffi`](https://pypi.org/project/argon2-cffi/) (Python).

### 2.4.4 Recovery Precedence and Conflict Resolution

The `ts` field of a `RecoveryAssertion` is self-asserted by its signer and MUST NOT be used to order competing assertions: any holder of a recovery credential could backdate it. If multiple recovery mechanisms produce conflicting valid `RecoveryAssertion` messages for the same DID, they are resolved as follows:

- **`did:webvh` identities.** The DID log is the ordering source: the assertion that takes effect is the one written into the log (§2.4). If a resolver sees two different log entries with the same version number for one DID, it MUST treat the DID as in conflict, MUST NOT apply either automatically, and SHOULD surface the conflict to the user. The recovery key (§2.4.1) and the social recovery key (§2.4.2) have equal authority, because both are update keys of the log: when assertions signed by each conflict, the first valid log entry wins. A later entry signed by the other key is an ordinary update applied after it in log order.
- **`did:plc` identities.** The PLC directory orders operations, subject to the `did:plc` recovery window.
- **CO-provisioned identities (§2.5).** In addition, the assertion that takes effect is the one reflected in the DID document update made by the provisioning service and signed by it (§2.5.7); the order in which that service applies updates is the ordering source. The provisioning service MUST apply recovery assertions for a DID one at a time, and MUST NOT apply a second `RecoveryAssertion` for the same DID within 24 hours of applying one without administrator review; it MUST record the conflict in its audit log. Clients act on the signed DID document, not on the assertion alone.
- **`did:key` identities.** `RecoveryAssertion` does not apply (§2.4).

## 2.5 Enterprise Identity Provisioning (SAML / OIDC)

In enterprise deployments, the organization manages user identities through an existing Identity Provider (IdP) such as Microsoft Entra ID, Okta, Ping, or any SAML 2.0 / OIDC-compliant IdP. The employer chooses the DID method (§2.1), normally `did:webvh`. This section specifies how the organization provisions `did:webvh` identities and how user agents register device keys against them. It keeps trust separated: the organization controls the identity namespace and can revoke it, and the device controls the private key material, which the organization cannot use (§2.5.1 gives the limits of this). Vendor-specific integrations are described non-normatively in `profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md` and `profiles/universal-idp-did.md`.

### 2.5.1 Trust Separation

The constraint this section enforces:

- **The organization provisions and hosts the `did:webvh` log and holds an update key for it.** It controls the DNS domain and the HTTPS endpoint serving the log, and therefore has revocation authority: it can retire any DID it controls by writing a log entry that removes all keys or deactivates the DID.
- **The user agent generates and owns device private keys.** Where the platform supports Ed25519 inside the device's secure hardware boundary, the user agent generates private keys there. Otherwise it holds them in software, wrapped by a hardware-held key (§2.2). Private keys never leave the device. The organization cannot generate, hold, or retrieve these keys. An organization holding an update key can still add a key it holds and sign as that user, but it can do so only by writing a log entry signed with its own update key. Because each entry must also carry a proof from a witness the organization does not control (§2.1), the organization cannot show such an entry to some resolvers and hide it from others, or roll a resolver back to an older log, without a witness colluding. Organizational impersonation is therefore auditable by the user, the user's contacts and auditors without trusting the organization alone (§12.7.3).
- **Device public keys are registered into the `did:webvh` document** via an authenticated provisioning endpoint. Authentication uses the IdP token (proving user identity to the organization); authorization uses an existing device key signature (proving key possession) or the IdP token alone for first-device enrollment.

This mirrors how S/MIME and WebAuthn work in enterprise: the organization manages the certificate or credential binding; the private key never leaves the user's hardware.

### 2.5.2 DID Namespace and Document Hosting

The organization provisions `did:webvh` identities in a controlled namespace:

```
did:webvh:{SCID}:{orgDomain}:users:{localIdentifier}
```

Resolution: `GET https://{orgDomain}/users/{localIdentifier}/did.jsonl` (the DID log, verified per §2.1)

Example:
- `did:webvh:QmSCID...:example.com:users:k7f3qd2m` → `GET https://example.com/users/k7f3qd2m/did.jsonl`

The `localIdentifier` MUST be stable for the lifetime of the account and MUST NOT be reassigned to a different person after the original user departs. It MUST NOT be derived from a person's name, email address, UPN, or any other attribute that can change. The organization chooses the source: an employee ID, the IdP's immutable user ID, or a random value minted by the provisioning service. The provisioning service keeps the mapping to the IdP principal in its private store. The mapping is not published.

Because the DID is stable, group memberships, compliance records and audit trails stay keyed to one identifier for a person's whole tenure. A domain change does not break the identity: the provisioning service SHOULD create DIDs with did:webvh portability enabled, so that the log moves to the new domain with the same SCID and records the previous DID in `alsoKnownAs`. Clients MUST treat two `did:webvh` DIDs with the same SCID and one continuous verified log as the same identity.

A DID is not a display name. Clients identify a person by the display profile (§2.3) and the organization's signed credentials, never by parsing the DID.

The DID document is served by the organization's **DID provisioning service**, a lightweight HTTPS service, typically deployed alongside the organization's IdP or directory service. It is a CO component. The service:

- Maintains the authoritative DID document for each user in a backing store (LDAP attribute, database, or directory extension)
- Serves documents at the well-known URL path
- Accepts authenticated device key registration requests (§2.5.4)
- Accepts authenticated device revocation requests (§2.5.5)
- Writes each document change as a DID log entry with the witness proofs that §2.1 requires

Relays play no part in identity provisioning and never receive or verify IdP tokens. IdP authentication is between the client, the IdP and the provisioning service.

### 2.5.3 Initial Provisioning (Onboarding)

When a user is onboarded to Agora, the organization creates a stub DID document containing no device keys. This happens in the same workflow as email account creation, automated via HR system integration or the IdP's provisioning API (SCIM 2.0 is the standard mechanism):

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
  "verificationMethod": [],
  "authentication": [],
  "keyAgreement": [],
  "service": []
}
```

The DID document MUST NOT name a relay or other IO as the user's service endpoint. Clients choose IOs independently of identity (ARCHITECTURE §2). Service entries limited to CO- or user-chosen endpoints MAY be added. The provisioning service hosts its users' KeyPackages. Before the first device enrolls (§2.5.4), it MUST add a `KeyPackageEndpoint` service entry (`type` `AgoraKeyPackageEndpoint`, §2.1, §5.2.1.1) that points at itself. It also adds an `AgoraProvisioning` service entry whose `serviceEndpoint` is its base URL, written `{prov}` below.

The stub document is valid and resolvable. It has no keys, so no one can authenticate as Alice yet. The document becomes operational when Alice's first device key is registered in §2.5.4.

The provisioning service MUST record the creation timestamp and provisioning operator identity in an audit log.

### 2.5.4 Device Key Registration

When Alice installs the Agora client on a new device, the client performs the following enrollment sequence:

**Step 1: Key generation.** The client generates a new device keypair, held as §2.2 describes:
- Ed25519 keypair for `authentication` (signing)
- X25519 keypair for `keyAgreement` (HPKE outside MLS groups, §2.1)

Neither private key leaves the device's key store. The client transmits only the public keys. A browser client generates its Ed25519 device key as a non-extractable WebCrypto key (§2.2, §12.6) and sets `secureEnclaveAttested` to `false`. If the user authenticates with a passkey during Step 2, the WebAuthn exchange is between the user and the IdP or the provisioning service; the passkey never becomes a device key (§2.2).

**Step 2: IdP authentication.** The client initiates a SAML 2.0 or OIDC authentication flow against the organization's IdP. The user authenticates (password and MFA) and the client receives an IdP token.

**Step 3: Registration request.** The client sends `POST {prov}/devices` with a typed payload envelope (§13.1) of type `urn:agora:type:DeviceKeyRegistrationRequest` whose body is:

```json
{
  "@type": "DeviceKeyRegistrationRequest",
  "did": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
  "deviceLabel": "Alice's MacBook Pro",
  "deviceEd25519PublicKey": "base64url(Ed25519 pubkey)",
  "deviceX25519PublicKey": "base64url(X25519 pubkey)",
  "platform": "macOS",
  "secureEnclaveAttested": true,
  "ts": "2026-03-12T12:00:00.000Z",
  "idpToken": "base64url(SAML assertion or OIDC id_token)"
}
```

Public keys are the raw 32-byte keys as unpadded base64url (RFC 4648 §5). `idpToken` is the OIDC ID token in compact serialization, an access token the IdP issued for the provisioning service's audience in compact serialization, or the unpadded base64url of the SAML assertion XML; the provisioning service states which it accepts.

The request is signed per §13.1.1 by the new device key, with `kid` the `did:key` form of `deviceEd25519PublicKey`. This signature proves possession of the key being registered. Because it covers `idpToken`, it also binds the key to that token. The IdP token alone authorizes adding a device only on first enrollment. Subsequent enrollment requires proof of an existing authorized device: for a subsequent device, the envelope also carries a second signature by an existing registered device key of `did` (a multi-signer envelope, §13.1.1).

`secureEnclaveAttested` is `true` only if the platform attests that the Ed25519 device key itself was generated and is held in hardware; a software key wrapped by a hardware key (§2.2) is `false`. When `true`, the provisioning service SHOULD verify the attestation before accepting the key.

**Step 4: Provisioning service validation.** The service:
1. Verifies the IdP token signature against the IdP's public key
2. Verifies the token is issued for the user matching the `did` in the request
3. Verifies the token is not expired and was issued for the Agora provisioning service audience
4. Verifies the signature by the new device key, and rejects a request that registers a key already present in any DID it serves
5. For non-first-device enrollment: verifies the second signature (§13.1.1) against a currently registered device key in the DID document
6. Checks that the user account is active (not suspended or offboarded)
7. Checks that the number of registered devices does not exceed the organization's configured limit (default: 10)

The service answers `201` with the new log entry's `versionId` as `text/plain`. It answers `400` for a malformed request, `401` for a failed token or signature check, `403` for an inactive account, `409` for a device limit reached or a duplicate key, and `429` when rate-limited.

**Step 5: DID document update.** On successful validation, the service adds the new device keys to the DID document:

```json
{
  "verificationMethod": [
    {
      "id": "did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{deviceKeyFingerprint}",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
      "publicKeyMultibase": "z...",
      "meta": {
        "deviceLabel": "Alice's MacBook Pro",
        "platform": "macOS",
        "registeredAt": "2026-03-12T12:00:00.000Z",
        "secureEnclaveAttested": true
      }
    },
    {
      "id": "did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{deviceKeyFingerprint}-x25519",
      "type": "X25519KeyAgreementKey2020",
      "controller": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
      "publicKeyMultibase": "z..."
    }
  ],
  "authentication": ["did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{deviceKeyFingerprint}"],
  "keyAgreement": ["did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{deviceKeyFingerprint}-x25519"]
}
```

`deviceKeyFingerprint` is the first 16 bytes of the SHA-256 hash of the Ed25519 public key, hex-encoded.

The service writes this change as a DID log entry with its witness proofs (§2.1).

**Step 6: KeyPackage upload.** The newly enrolled client generates an initial batch of MLS KeyPackages (§5.2.1) and publishes them, signed with the new device key, by `POST` (§5.2.1.1) to the user's `KeyPackageEndpoint` hosted by the provisioning service (§2.5.3). This completes enrollment. KeyPackages live with whoever runs the user's identity: the employer's provisioning service for an employee, or a host the individual chooses or runs. The `KeyPackageEndpoint` service entry (`did:webvh`, `did:plc`) or the Pkarr pointer record (`did:key`) names that host (§2.1). Relays hold no KeyPackages. The host rate-limits KeyPackage fetches to resist draining, and the client keeps a last-resort KeyPackage available there (§5.2.1.1).

**Step 7: Group join.** The user's existing devices add the new device to the user's self-group and to every group the user belongs to (§2.6).

### 2.5.5 Device Revocation

The user (lost or retired device) or the organization (employee departure, security incident) can initiate device revocation.

**User-initiated revocation.** From any other enrolled device, the user sends `POST {prov}/revocations` with a typed payload envelope of type `urn:agora:type:DeviceRevocationRequest` whose body is:

```json
{
  "@type": "DeviceRevocationRequest",
  "did": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
  "revokeDeviceKeyID": "did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{fingerprint}",
  "reason": "device-lost | device-retired | security-incident",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The request is signed per §13.1.1 by a surviving device key of `did`.

**Organization-initiated revocation.** An IT administrator authenticates to the provisioning service admin interface and submits a revocation for any device key or for the entire DID (full account suspension):

```json
{
  "@type": "AdminRevocationRequest",
  "did": "did:webvh:QmSCID...:example.com:users:k7f3qd2m",
  "revokeDeviceKeyID": "did:webvh:QmSCID...:example.com:users:k7f3qd2m#device-{fingerprint}",
  "revokeAll": false,
  "reason": "employee-offboarding | security-incident | policy-violation",
  "adminDID": "did:webvh:QmSCID...:example.com:users:r2v8n5xw",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

The request is signed per §13.1.1 by `adminDID`. `revokeAll: true` removes all device keys from the DID document, effectively suspending the account. The DID document remains resolvable but has no `authentication` keys.

**Revocation mechanics.** On receipt of a valid revocation request, the provisioning service:

1. Removes the specified `verificationMethod` entry and its references from `authentication` and `keyAgreement`, by a DID log entry signed with its update key and carrying its witness proofs (§2.1)
2. Records the revocation in the audit log with timestamp, reason, and initiator

It answers `204` on success, with the error codes of §2.5.4. It sends no push wake-up. The user's remaining devices send an `IdentityChanged` notice (§2.7) to the user's groups when they see the change in the DID log. Other members learn of the revocation when they resolve the DID. Relays take no action on a revocation: they never authenticate client identity (§12.5), and the revoked device loses channel access when its MLS leaves are Removed (below).

**MLS remediation.** Revocation of a device key does not automatically remove that device's MLS leaf nodes from all groups. The revoked device's client (if still running) SHOULD send a self-Remove proposal (§4.8) in each of its groups. If the device is lost, other group members MUST issue `Remove` Commits when they detect that the key is revoked. Space admins SHOULD periodically reconcile their channels so that revoked device keys have no active MLS leaves in them.

### 2.5.6 Offboarding

When an employee leaves, the organization performs a full account suspension:

1. The organization disables the IdP account, which blocks new IdP token issuance
2. An admin issues a `revokeAll: true` revocation through the provisioning service
3. The provisioning service updates the DID document to remove all device keys
4. Admins of the organization's Spaces Remove the user's leaves from their groups (§2.5.5). Members of groups outside the organization's control Remove them when they next resolve the DID. A member's client resolves each other member of each DM group it holds at least once every 7 days (§4.6)
5. The organization retains the DID document (does not delete it) for the regulatory retention period
6. After the retention period, the document MAY be blanked (empty `verificationMethod`) but MUST NOT be removed, so that its URL stays resolvable and archived compliance records have no dangling references

### 2.5.7 Provisioning Service DID Document

The provisioning service itself is a DID-bearing principal:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:example.com:agora:provisioning",
  "verificationMethod": [{
    "id": "did:webvh:QmSCID...:example.com:agora:provisioning#signing-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:webvh:QmSCID...:example.com:agora:provisioning",
    "publicKeyMultibase": "z..."
  }],
  "authentication": ["did:webvh:QmSCID...:example.com:agora:provisioning#signing-1"]
}
```

The provisioning service's update key for its users' DID logs is a verification method of this DID. Every log entry it writes carries a proof by that key and the witness proofs of §2.1, and clients verify both as part of log verification (§2.1). DID document changes are distributed only by the log (§2.7).

This creates a two-party integrity guarantee: the device's signature on the registration request proves possession of the key and, for a later device, approval by an existing device (§2.5.4), and the log entry proves the organization accepted and recorded the registration. The provisioner cannot forge an existing device's signature. It can add a new key, but only by a DID log entry signed with its update key and witnessed by a party it does not control (§2.1, §2.5.1).

### 2.5.8 Relationship to §2.4 Recovery Mechanisms

For enterprise `did:webvh` identities, the recovery mechanisms of §2.4 interact with organizational authority as follows:

- **Recovery key (§2.4.1).** Valid, but the recovery key can only rotate device keys; it cannot override an organization-initiated `revokeAll`. Recovery keys are appropriate for individual-initiated recovery (lost device, not offboarding).

- **Social recovery (§2.4.2).** Valid for user-initiated recovery. The provisioning service accepts a `RecoveryAssertion` as equivalent to an IdP token for first-device enrollment, provided its signature verifies under the social recovery key (`#social-recovery-1`, a `recoverableIdentity` key) in the user's DID document and its `prev` is the current head of the log (§2.4.1).

- **Encrypted backup (§2.4.3).** Valid. A backup from a software keystore restores device keys. If a restored key is still listed in the DID document and its source device is no longer active, the restored device uses it without re-enrollment. A backup from a non-extractable keystore restores no keys, and the device enrolls as a new device via §2.5.4. Neither restores MLS state (§2.4.3).

- **Org-initiated recovery (helpdesk).** When a user loses all devices and has no recovery key or guardians, the organization can initiate recovery on their behalf. An admin issues a provisioning request to add a new device key to the user's DID document, with admin authorization in place of an existing-device signature. This is a privileged operation. This path MUST be logged in the audit trail, and the added key appears in the DID log as an entry signed with the provisioning service's update key and witnessed (§2.1).

## 2.6 Multi-Device

Each of a user's devices is a separate leaf in every group the user belongs to (§2.2). This section defines how a user's devices share private state and how a new device joins the user's groups.

**Self-group.** When a user has more than one device, the devices MUST maintain a **self-group**: an MLS group, with a fresh random group ID, whose members are only the user's own devices. It never appears in Space state. It is admitted at relays like a DM group whose admission host is the user's own identity host, with the admission key in the self-group's `agora_admission` GroupContext extension (§4.6). The self-group carries:

- the user's private `single-author` data (§14.3), such as `ReadPosition` and `ChatContact`, including the block list (§4.6.3)
- the `SocialRecoveryConfig` (§2.4.2)
- optional history transfers (below)
- `IdentityChanged` notices (§2.7)
- the user's Space list, in the `agora_space_membership` GroupContext extension (below)

**Adding a new device.** An existing device of the user adds a new device when the new device key appears in the user's DID document (for an employee, after §2.5.4). For `did:key`, it does so when the user pairs the new device with an existing one and the existing device learns the new device's leaf signature key (for example from a QR code the new device shows). The existing device:

1. fetches a KeyPackage of the new device from the user's `KeyPackageEndpoint` with the `leaf` parameter set to the new device's leaf signature key (§5.2.1.1), and checks that the returned leaf carries that key
2. commits an Add of the new device to the self-group
3. commits an Add of a further KeyPackage of the new device to each other group the user belongs to

An Add of a leaf whose credential names the committer's own DID is an **own-device Add**. Members MUST accept an own-device Add in any group in which that DID is already a member, provided the added leaf satisfies the credential binding of §5.2.1 (a current `authentication` key of that DID, or for `did:key` a valid device binding): it needs no Space admin authority (§4.3) and is exempt from the message request state (§4.6.3).

**Space membership list.** A new device holds no Space state and no Space endpoint URLs, which it needs to validate own-device Welcomes to Space groups (§4.3) and to fetch channel keys (§3.4). The user's devices therefore keep the list of the user's Spaces in the self-group's GroupContext as the `agora_space_membership` extension, extension type 0xF0A3 from the RFC 9420 private-use range. Its `extension_data` is an `AgoraSpaceList`, in the TLS presentation language of RFC 9420:

```
struct {
    opaque url<V>;             /* UTF-8 */
} URL;

struct {
    opaque space<V>;           /* Space identifier (§3.2), UTF-8 */
    URL endpoints<V>;          /* Space endpoint URLs (§3.4) */
} SpaceEntry;

struct {
    SpaceEntry spaces<V>;
} AgoraSpaceList;
```

`spaces` has one entry for each Space the user is a member of, and no two entries have the same `space`. `endpoints` lists the Space endpoint URLs the device last used for that Space.

The device that creates the self-group puts `agora_space_membership` with the current list in its initial GroupContext, and every self-group GroupContext carries it. The self-group's `required_capabilities` lists 0xF0A3, so every device of the user lists it in its leaf `capabilities.extensions` (§5.2.1). A new device receives the list in its self-group Welcome (RFC 9420 §12.4.3.1).

A device that sees the user join or leave a Space, or a Space's endpoints change, commits a GroupContextExtensions proposal (RFC 9420 §12.1.7) carrying the whole updated list. Because that proposal replaces every GroupContext extension, it also carries the group's other extensions unchanged. An `agora_admission` carried unchanged is not a change to it (§4.6). Competing Commits are resolved by the canonical-Commit rule (§5.1.1). A device whose change lost re-proposes it against the winning list. Because it names Spaces, the list exists only in the self-group, whose handshake messages are `PrivateMessage`s (§5.2.1).

**History transfer.** A new device cannot decrypt messages from epochs before it joined. An existing device MAY send it a history transfer: an MLS application message in the self-group of type `urn:agora:type:HistoryTransfer` with body:

```json
{
  "blobId": "bafkrei...",
  "key": "base64url...",
  "size": 1048576
}
```

`blobId` names a blob stored like any other (§10.4.4) whose bytes are `nonce || AES-128-GCM-Seal(key, nonce, archive, aad = "agora/history/v1")`, with `key` 16 random bytes used for this blob only, `nonce` 12 random bytes, and `archive` the CBOR encoding of a `HistoryArchive`:

```cddl
HistoryArchive = [* HistoryEntry]
HistoryEntry = {
  group: bstr,      ; MLS group ID
  sender: tstr,     ; DID of the MLS sender, as authenticated when received
  received: tstr,   ; RFC 3339 UTC time the source device received it
  payload: bstr,    ; the decrypted typed payload envelope (§5.2.2)
}
```

The receiving device trusts the archive on the authority of the sending device, which is one of the user's own devices; entries carry no proof of the original senders' signatures. The same `HistoryArchive` format is used for the `history` field of an encrypted backup (§2.4.3).

**Restored state.** A backup carries no MLS state (§2.4.3), so a restored device always joins the user's groups as a new leaf. Device keys restored from a backup MUST NOT be used while the source device is active, because two devices signing with one device key cannot be told apart. If the source device is active, the restored device enrolls as a new device with a new device key and uses the backup only to read old history (§2.4.3).

## 2.7 Identity Change Notice

User identity records are never gossiped over relay connections. A user's keys, profile and `KeyPackageEndpoint` are discovered only by resolving the DID document (with its verified log, §2.1) or, for `did:key`, the Pkarr pointer record. Profile updates, recoveries and device revocations take effect through those records (§2.3, §2.4.1, §2.5.5).

To tell other members to re-resolve, a user's device sends an MLS application message of type `urn:agora:type:IdentityChanged` to each group the user belongs to, including the self-group, after any change to the user's DID document, DID log or profile. The body is the empty JSON object `{}` (content type `application/json`); the sender is the MLS sender (§13.1.1). On receipt, a client re-resolves the sender's DID and profile, verifies them per §2.1, and applies the result. Applying it includes Removing (§2.2) leaves that no longer satisfy the credential binding of §5.2.1, that is, a current `authentication` key of the DID or, for `did:key`, a valid device binding. The notice carries no authority: clients MUST act only on what the verified DID document, log or Pkarr record states. Clients MAY coalesce notices and MAY delay re-resolution.

## 2.8 Account Deletion

A user deletes an account in two steps:

1. The user's client leaves every Space and every other group the user belongs to by the procedures of §4.8. Each of the user's devices then deletes its self-group state.
2. The user retires the DID. For `did:webvh`, the user writes a DID log entry that deactivates the DID, signed with an update key and carrying its witness proofs (§2.1). For `did:plc`, the user submits a tombstone operation. A `did:key` cannot be deactivated; the user destroys every copy of the identity key, including backups (§2.4.3).

A deactivated DID has no `authentication` keys. A `did:key` cannot be deactivated: its leaves keep a valid device binding, so members cannot detect its deletion. A member that resolves a deactivated DID, for example after an `IdentityChanged` notice (§2.7) or on its own schedule, Removes any leaves of that DID that remain in its groups (§2.2). For a CO-provisioned identity, deletion is the organization's offboarding (§2.5.6), and the organization retains the DID document as that section requires. Deletion does not erase messages that other members, compliance loggers (§7) or relays already hold; relays drop envelopes when their retention expires (§5.2.5).


---
