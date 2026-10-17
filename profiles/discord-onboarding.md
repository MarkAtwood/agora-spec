# Tool Specification: `agora-enroll`

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Version:** 0.1 Draft
**Depends On:** the Agora protocol specification (`spec/`, current draft); the `discord2agora` import tool, an external tool specified outside this repository
**Status:** Pre-implementation design

---

## 1. Purpose

`agora-enroll` is the user-facing counterpart to `discord2agora`. It authenticates a user via Discord OAuth2, creates or loads their Agora DID and device keypair, and registers that DID against their provisional member record in a target Space. The result is a fully-enrolled Agora identity ready for immediate use.

**Scope: individuals.** This profile is for people who join a Space as themselves. Each user chooses their own DID method and host (§3.1, spec §2.1). Identities provisioned by an employer follow spec §2.5 and the employer profiles (`profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`, `profiles/universal-idp-did.md`), in which the employer runs the DID log and KeyPackage host; `agora-enroll` is not used there.

Two delivery targets are supported:

- **Browser app** (`enroll.agora.example.com` or self-hosted): zero install, WebCrypto device key protected by a passkey, covers the majority of users.
- **CLI binary** (`agora-enroll`): for operators, power users, and users who require explicit keystore control.

Both targets share the same backend protocol; the browser and CLI are different frontends to the same enrollment flow.

---

## 2. System Components

```
┌─────────────────────────────────────────────────────────────┐
│  User Device                                                │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Browser App     │    │  CLI Binary                  │  │
│  │  (WebCrypto /    │    │  (OS keychain / file /       │  │
│  │   WebAuthn)      │    │   PKCS#11)                   │  │
│  └────────┬─────────┘    └──────────────┬───────────────┘  │
│           │                             │                   │
└───────────┼─────────────────────────────┼───────────────────┘
            │  HTTPS                      │  HTTPS
            └──────────────┬──────────────┘
                 ┌─────────┴─────────────────────────┐
                 ▼                                   ▼
┌──────────────────────────────────┐  ┌──────────────────────────────┐
│  Enrollment Service (CO)         │  │  User's identity host        │
│                                  │  │  (chosen by the user)        │
│  - Discord OAuth2 callback       │  │                              │
│  - Provisional member registry   │  │  - did:webvh log (if used)   │
│  - DID registration endpoint     │  │  - KeyPackageEndpoint:       │
│  - Enrollment agent: MLS Add,    ├─▶│    KeyPackages, Welcomes     │
│    Welcome delivery              │  └──────────────────────────────┘
└───────────────┬──────────────────┘
                │
     ┌──────────┴──────────┬────────────────────┐
     ▼                     ▼                    ▼
 Discord API          Agora Relay          CO Space endpoint
 (OAuth2)             (carries MLS         (Space state,
                       ciphertext only)     spec §3.4)
```

The Enrollment Service is a CO component. It is stateless beyond the provisional member list. It MUST NOT hold users' private keys or session state between requests (beyond a short-lived OAuth2 state token). Its only write path into channels is the enrollment agent's MLS Add commits (§8.2), which a relay carries as ciphertext like any member's commit. The relay learns neither the new member nor the Space.

The user's identity host has duties beyond the two the diagram shows. The spec, not this profile, defines them (spec §4.6, §10.5.3); the tool only checks that a host it offers can meet them. As identity host it plays the CO's part for admission of every DM group the user starts or moves to it (spec §4.6.4) and of the user's self-group (spec §2.6). It therefore serves the admission-key endpoints `GET <host>/admission-key/<groupID>`, `GET <host>/admission-key/<groupID>/<keyEpoch>`, `GET <host>/admission-key/<groupID>/members` and `PUT <host>/admission-key/<groupID>/members`. GETs use member authentication by the spec §3.5 exchange; a PUT is authorized by the signature of its `DMMembers`. It holds its own `ServiceAgreement`s with relays, signed with its own billing DID, and registers and deregisters those groups' admission keys under them (spec §10.5.1, §10.5.3).

---

## 3. Enrollment Flow

Both browser and CLI follow the same logical sequence:

1. **Discord OAuth2**: user authenticates with Discord; the tool obtains their Discord user ID.
2. **Lookup**: the tool queries the Enrollment Service to confirm the Discord user ID is in the provisional member list.
3. **Method and host**: the user chooses a DID method and an identity host (§3.1).
4. **Key operation**: the tool generates a device keypair (create path) or loads an existing one (update path), and, for `did:webvh` and `did:plc`, accepts the public half of a recovery key the user generated offline (§5.2).
5. **Identity publication**: the tool creates the DID with a `KeyPackageEndpoint` at the chosen host: a `did:webvh` genesis log entry published at the host, a `did:plc` genesis operation, or, for `did:key`, a Pkarr pointer record (§3.1).
6. **KeyPackage upload**: the tool uploads an initial batch of MLS KeyPackages and one last-resort KeyPackage to the user's `KeyPackageEndpoint` (spec §5.2.1.1). KeyPackages never go to a relay or to the Enrollment Service.
7. **Registration**: the tool POSTs the DID and a signed proof-of-possession to the Enrollment Service (§8).
8. **MLS Add**: the enrollment agent fetches a KeyPackage from the user's `KeyPackageEndpoint`, commits the Add, and POSTs the Welcome to that endpoint (§8.2).
9. **Keyfile export**: the tool produces the encrypted key backup file for the user to save (§7). It never contains the recovery private key or any MLS state.
10. **Confirmation**: the tool displays the space URI and the user's DID.

### 3.1 DID Method Choice

The user picks one of the three user DID methods of spec §2.1. The tool MUST offer `did:webvh` as the default.

| Method | Identity host | Recovery | Available in |
|---|---|---|---|
| `did:webvh` (default) | A did:webvh host the user picks, or their own domain. It serves the DID log and the `KeyPackageEndpoint`. | Recovery key (§5.2) and social recovery (spec §2.4.1, §2.4.2), plus backup | Browser and CLI |
| `did:plc` (opt-in) | The PLC directory holds the document; the user picks a host for the `KeyPackageEndpoint`. | did:plc rotation keys (spec §2.4) | Browser and CLI |
| `did:key` (opt-in) | None for the document; the user picks a host for the `KeyPackageEndpoint`, named in a Pkarr pointer record. | Encrypted backup only (spec §2.4.3) | CLI only |

**`did:webvh`.** The tool asks for the host's URL and MAY suggest hosts from operator configuration; any host the user names is accepted, including one the Space operator does not run. The tool builds the genesis log entry with the device key and the recovery public key (§5.2) as authorized update keys (spec §2.4), signs it with the device key, and uploads it through the host's publishing interface, which Agora does not specify. The DID embeds the SCID derived from that entry. The host cannot add a key without breaking the log, and the user can later move to another host while keeping the SCID (spec §2.1, §2.5.2).

**`did:plc`.** Intended for users who already have a Bluesky identity. The tool adds the device verification method and a `KeyPackageEndpoint` service entry by an ordinary PLC operation, signed by a rotation key the user controls (for an existing identity, this may require the user's PDS to sign). A new `did:plc` identity uses the device key and the recovery public key as rotation keys.

**`did:key`.** Before creating a `did:key` identity, the tool MUST show the warning required by spec §2.1: losing the key loses the identity permanently, a lost or stolen device cannot be revoked, and there is no recovery beyond the user's own encrypted backup. The user confirms explicitly. The tool then publishes the user's Pkarr pointer record (spec §2.1, §10.3.4.6) with `_kp._agora.` set to the `KeyPackageEndpoint` URL at the host the user picked; the record MUST NOT name a relay. The client re-publishes the record every 2 hours (spec §10.3.4.6). The identity key is not an MLS leaf key: each device generates its own leaf signature key and carries a device binding signed by the identity key in its leaf, which members verify (spec §2.2, §5.2.1). The identity key signs the KeyPackage publications (spec §5.2.1.1) and the registration proof (§8). `did:key` is CLI-only because the identity key must be exportable to reach the user's other devices (spec §2.1), and the browser device key is not (§5.1). The CLI offers `did:key` only with the encrypted file or OS keychain backend, or with PKCS#11 if the user accepts a single-device identity.

---

## 4. Discord OAuth2

### 4.1 Scopes

```
identify
```

`identify` is the only required scope. The tool needs the user's Discord ID and username; it does not require email, space membership read, or any write permissions.

### 4.2 Browser Flow (PKCE)

Standard OAuth2 Authorization Code flow with PKCE. The browser app:

1. Generates a `code_verifier` (cryptographically random, 43–128 chars).
2. Derives `code_challenge = BASE64URL(SHA256(code_verifier))`.
3. Redirects to Discord's authorization endpoint with `response_type=code`, `code_challenge_method=S256`, and a short-lived `state` token stored in `sessionStorage`.
4. Discord redirects back to the enrollment app's callback URL with `code`.
5. The app exchanges `code` and `code_verifier` for an access token via the Enrollment Service backend (the client secret lives on the server, not in the browser).
6. The Enrollment Service returns only the Discord user ID and username to the browser; the access token stays server-side and is discarded after the `/users/@me` call.

The `state` token MUST be a 32-byte random value, base64url-encoded, stored in `sessionStorage`. It MUST be verified on callback and then deleted. It MUST NOT be stored in `localStorage` or a cookie.

### 4.3 CLI Flow (Loopback)

Standard OAuth2 loopback redirect (RFC 8252 §7.3):

1. The CLI binds a listener on `http://127.0.0.1:<random-port>/callback`.
2. The CLI opens the system browser to Discord's authorization endpoint with `redirect_uri=http://127.0.0.1:<port>/callback`.
3. Discord redirects to the loopback listener with `code`.
4. The CLI exchanges `code` for an access token directly (client ID only, no client secret; the CLI is a public client).
5. The CLI calls `/users/@me`, extracts Discord user ID and username, and discards the token.

RFC 8252 §7.3 requires authorization servers to accept any port on a loopback redirect URI. Whether Discord does so, or requires an exact registered port, is not confirmed here; verify against current Discord developer documentation. The operator MUST register the loopback URI in Discord's developer portal. If Discord matches the port exactly, the CLI MUST bind the fixed registered port instead of a random one.

---

## 5. Key Generation: Browser Path (WebCrypto Device Key)

### 5.1 Device Key and Passkey

The browser generates the device key with WebCrypto Ed25519 and signs only through a non-extractable `CryptoKey` (spec §2.2, §12.6). The key signs the `did:webvh` genesis log entry or `did:plc` genesis operation, the KeyPackages and the registration proof (§8) without user interaction. Because the key never leaves the origin's storage, the browser app MUST be served from the origin of the Agora web client that will use the key, or be part of that client.

The app first creates a passkey for its origin and requests the WebAuthn PRF extension, because whether the device key may be extractable depends on PRF support (spec §12.6):

```javascript
const credential = await navigator.credentials.create({
  publicKey: {
    challenge: crypto.getRandomValues(new Uint8Array(32)),
    rp: { name: "Agora", id: rpId },
    user: {
      id: discordUserIdBytes,            // Discord user ID as bytes
      name: discordUsername,
      displayName: discordUsername
    },
    pubKeyCredParams: [
      { type: "public-key", alg: -8 },
      { type: "public-key", alg: -7 }
    ],
    authenticatorSelection: {
      residentKey: "preferred",
      userVerification: "required"
    },
    extensions: { prf: { eval: { first: prfSalt } } }
  }
});
```

If the creation response carries no PRF result, the app obtains it with a `navigator.credentials.get` assertion carrying the same `prf` input. If neither yields a PRF output, the authenticator does not support PRF. Only then does the app generate the device key:

```javascript
// PRF path: extractable only so that wrapKey can wrap it; exportKey is never called on the private key.
// No-PRF path: non-extractable from the start (spec §12.6).
const deviceKey = await crypto.subtle.generateKey({ name: "Ed25519" }, prfSupported, ["sign", "verify"]);
const rawPublicKey = await crypto.subtle.exportKey("raw", deviceKey.publicKey);
const publicKeyMultibase = multibaseEncode('ed25519-pub', new Uint8Array(rawPublicKey));
```

On the PRF path the app wraps the device key under a key derived from the PRF output, stores only the wrapped key with the credential ID and `prfSalt`, and drops the original `CryptoKey` (spec §12.6). In later sessions the Agora web client unwraps the key once per session as non-extractable. On the no-PRF path the app stores the non-extractable `CryptoKey` itself, as spec §12.6 allows, and warns that the stored key is not protected by the passkey. The genesis log entry or genesis operation, the KeyPackages and the registration proof are signed after this step, with the key in its final form.

The passkey is not a device key and does not appear in the DID document (spec §2.2). Its assertions never leave the browser; the Enrollment Service does not parse WebAuthn. The DID itself is not derived from the device key: a `did:webvh` DID embeds the SCID of its genesis log entry, and a `did:plc` DID comes from its genesis operation (§3.1). The browser path does not offer `did:key` (§3.1).

### 5.2 Recovery Key (Offline)

The recovery key (Agora spec §2.4.1) MUST NOT be generated by the browser app or by any enrollment step that runs on a networked device, because spec §2.4.1 forbids its private key from entering a networked device or software keystore. The browser and the networked CLI handle only its public key.

The user generates the recovery key out of band with `agora-enroll recovery-keygen` (§6.6) on an offline device, or on a hardware security key, and gives the enrollment tool the resulting `publicKeyMultibase` (pasted, or scanned as a QR code). The tool MUST validate that the value decodes to a 32-byte Ed25519 public key and MUST show its fingerprint for the user to compare against the offline device.

Where the key is registered depends on the method (spec §2.4). For `did:webvh` it is listed as a `recoverableIdentity` verification method and as an authorized update key of the DID log. For `did:plc` it is registered as a rotation key. For `did:key` the tool MUST NOT ask for a recovery key, because no recovery mechanism other than encrypted backup applies (spec §2.4).

A `did:webvh` or `did:plc` user MAY skip this step. The DID document then omits `recoverableIdentity` (or the extra rotation key), and the app MUST warn that no recovery key is registered and point to the other recovery mechanisms (Agora spec §2.4.2, §2.4.3).

### 5.3 DID Document Assembly

For `did:webvh`, the DID document in the genesis log entry combines the WebCrypto device key (§5.1), the user-supplied recovery public key and the `KeyPackageEndpoint` at the chosen host:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCID...:host.example:alice",
  "verificationMethod": [
    {
      "id": "did:webvh:QmSCID...:host.example:alice#keys-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:host.example:alice",
      "publicKeyMultibase": "z6Mk..."
    },
    {
      "id": "did:webvh:QmSCID...:host.example:alice#recovery-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCID...:host.example:alice",
      "publicKeyMultibase": "zRECOVERY..."
    }
  ],
  "authentication": ["did:webvh:QmSCID...:host.example:alice#keys-1"],
  "keyAgreement": [...],
  "recoverableIdentity": ["did:webvh:QmSCID...:host.example:alice#recovery-1"],
  "service": [{
    "id": "did:webvh:QmSCID...:host.example:alice#keypackages",
    "type": "AgoraKeyPackageEndpoint",
    "serviceEndpoint": "https://host.example/v1/agora/kp/alice"
  }]
}
```

The `authentication` key is the device key (§5.1). The `recoverableIdentity` key is the offline-generated recovery public key (§5.2); the log's parameters list it, with the device key, as an update key. The `keyAgreement` key is a fresh X25519 keypair generated by the browser (WebCrypto, extractable, included in the keyfile). A `did:plc` document carries the same verification methods and service entry; the recovery key appears as a rotation key instead of in `recoverableIdentity`.

### 5.4 Enrollment Challenge

Before key generation, the browser MUST fetch a short-lived challenge from the Enrollment Service:

```
GET /v1/enroll/challenge?discord_user_id=<id>
→ { "challenge": "<32-byte-base64url>", "expires": "<iso8601>", "space": "<agora-uri>" }
```

The challenge is included in the proof payload (§8), binding the registration to this specific enrollment session. The Enrollment Service MUST verify the challenge on registration. Challenges expire in 5 minutes and are single-use; the service MUST mark a challenge consumed on first use.

---

## 6. Key Generation: CLI Path

### 6.1 Keystore Selection

On first run, the CLI prompts the user to select a keystore backend:

```
Where should your Agora keys be stored?

  [1] OS keychain  (Keychain on macOS, Credential Manager on Windows, libsecret on Linux)
  [2] Encrypted file  (~/.agora/keystore.enc)
  [3] Hardware key via PKCS#11  (YubiKey, SoftHSM, etc.)

Choice [1]:
```

The selection is stored in `~/.agora/config.toml` as `keystore_backend`. Subsequent runs use the configured backend without re-prompting.

### 6.2 OS Keychain Backend

Stores the Ed25519 private key bytes (raw, 32 bytes) under service name `agora` and account name equal to the DID. Platform implementations:

- **macOS:** Security framework (`SecItemAdd` / `SecItemCopyMatching`)
- **Windows:** DPAPI via `CryptProtectData` stored in Credential Manager
- **Linux:** libsecret (Secret Service API); falls back to `~/.agora/keystore.enc` with a warning if no Secret Service is available

### 6.3 Encrypted File Backend

An Argon2id-derived key from a user passphrase encrypts the key material:

```
backupKey = Argon2id(passphrase, salt, m=65536, t=3, p=4)
ciphertext = AES-256-GCM(backupKey, keyMaterial)
```

`keyMaterial` is a CBOR struct containing the Ed25519 private key, X25519 private key, DID, and creation timestamp. This file is the local keystore. The user's backup is the keyfile (§7); the tool can also export the spec §2.4.3 backup format with `backupType` `"keys"`.

The passphrase is prompted at key generation and at each subsequent use. It MUST NOT be stored anywhere. The CLI MUST require the passphrase to be confirmed twice at generation.

### 6.4 PKCS#11 Backend

The CLI uses the PKCS#11 interface to generate a key on the hardware token. The private key is non-extractable (stays on device). The public key is retrieved for DID derivation. The mechanism is `CKM_EDDSA` (Ed25519). Device keys are Ed25519 only (spec §2.2), so a token without `CKM_EDDSA` cannot hold the device key; the CLI then refuses the PKCS#11 backend and offers the other two. The PKCS#11 library path is configurable in `~/.agora/config.toml`:

```toml
[keystore]
backend = "pkcs11"
pkcs11_lib = "/usr/lib/x86_64-linux-gnu/libykcs11.so"
pkcs11_slot = 0
```

Common defaults are pre-configured for YubiKey (`libykcs11.so`), SoftHSM2 (`libsofthsm2.so`), and OpenSC (`opensc-pkcs11.so`).

### 6.5 Key Generation (Non-PKCS#11)

For the OS keychain and encrypted file backends, the CLI generates keys from the OS CSPRNG:

```go
privKey := ed25519.GenerateKey(rand.Reader)   // stdlib crypto/ed25519
x25519Priv := generateX25519(rand.Reader)      // golang.org/x/crypto/curve25519
did := createDID(method, host, privKey, recoveryPub) // did:webvh genesis, did:plc genesis, or did:key from privKey.Public() (§3.1)
```

For `did:key` the CLI also generates a separate Ed25519 leaf signature key for this device and signs its device binding with `privKey` (spec §5.2.1).

The CLI MUST NOT generate the recovery key during enrollment; for `did:webvh` and `did:plc` it accepts the recovery public key as in §5.2.

### 6.6 Offline Recovery Key Generation

`agora-enroll recovery-keygen` generates the recovery key. It MUST refuse to run if any non-loopback network interface is up, MUST NOT write the private key to any keystore or file, and MUST output the private key only as a recovery phrase for the user to write on paper (or generate it on a PKCS#11 token, which keeps it non-extractable). It prints the `publicKeyMultibase` and its fingerprint, as text and as a QR code, for transfer to the enrolling device. When recovery is needed, `agora-enroll recovery-sign`, under the same offline constraints, takes the recovery phrase (or token) and signs a `RecoveryAssertion` (Agora spec §2.4.1) for transfer back to a networked device.

---

## 7. Keyfile Format

Both browser and CLI produce a single downloadable keyfile, the user's backup artifact. It holds the recovery public key only (absent for `did:key` or if the user skipped §5.2); the recovery private key never enters it. For `did:key` the keyfile is the identity's only recovery path (spec §2.4.3) and is also how the user copies the identity key to another device (spec §2.1). It uses a JSON envelope (chosen over binary for human-inspectability and cross-tool compatibility):

```json
{
  "version": "1",
  "type": "agora-keyfile",
  "did": "did:webvh:QmSCID...:host.example:alice",
  "didMethod": "webvh",
  "keyPackageEndpoint": "https://host.example/v1/agora/kp/alice",
  "createdAt": "2026-03-13T00:00:00Z",
  "source": "discord-enrollment",
  "discordUserId": "123456789012345678",
  "discordUsername": "alice",
  "kdf": {
    "algorithm": "argon2id",
    "salt": "<base64url>",
    "m": 65536,
    "t": 3,
    "p": 4
  },
  "recoveryPublicKeyMultibase": "zRECOVERY...",
  "keyAgreementKeypair": {
    "description": "X25519 key agreement key",
    "encryptedPrivateKey": "<base64url-AES256GCM-ciphertext>",
    "publicKeyMultibase": "zABC..."
  },
  "primaryKeyType": "webcrypto",
  "primaryKeyPublicMultibase": "z6Mk..."
}
```

For the browser, `primaryKeyType` is `"webcrypto"` and `primaryKeypair` is omitted: the device key stays in the browser's storage (§5.1). If that storage is cleared, the user registers a new device from another device or, with none left, through recovery (spec §2.2, §2.4).

For the CLI with an extractable keystore backend, `primaryKeyType` is `"software"` and the file additionally includes:

```json
"primaryKeypair": {
  "description": "Ed25519 primary signing key",
  "encryptedPrivateKey": "<base64url-AES256GCM-ciphertext>",
  "publicKeyMultibase": "z6Mk..."
}
```

For PKCS#11, `primaryKeyType` is `"pkcs11"` and `primaryKeypair` is omitted (non-extractable); only `primaryKeyPublicMultibase` is present.

The keyfile holds no MLS state. Spec §2.4.3 forbids epoch secrets and ratchet state in a backup, because restoring them would rewind sender generations. A device restored from the keyfile joins each of the user's groups as a new leaf (spec §2.6) and does not use the restored keys while the source device is active (spec §2.4.3).

**Passphrase derivation:** A single Argon2id invocation produces a 64-byte output. The first 32 bytes encrypt `keyAgreementKeypair.encryptedPrivateKey`. When a `primaryKeypair` is present, the second 32 bytes encrypt it. This avoids key reuse without requiring multiple passphrase entries.

**Filename:** `agora-<displayName>-<YYYY-MM-DD>.keyfile.json`. The `.keyfile.json` double extension is intentional: systems that hide extensions will display `.keyfile`, which is less likely to be opened naively than `.json` alone.

---

## 8. Registration Protocol

After key generation, the client sends a signed registration request to the Enrollment Service:

```
POST /v1/enroll/register
Content-Type: application/json

{
  "did": "did:webvh:QmSCID...:host.example:alice",
  "discordUserId": "123456789012345678",
  "challenge": "<challenge from §5.4>",
  "proofOfPossession": "<signature over the proof payload, see below>",
  "spaceURI": "agora://bafkrei.../"
}
```

**Proof payload** (the data signed to produce `proofOfPossession`):

```json
{
  "did": "did:webvh:QmSCID...:host.example:alice",
  "discordUserId": "123456789012345678",
  "challenge": "<challenge>",
  "spaceURI": "agora://bafkrei.../",
  "ts": "2026-03-13T00:00:00Z"
}
```

In both the browser and the CLI path, `proofOfPossession` is a JWS over the proof payload signed by the device key (spec §13.1.1).

The request carries no KeyPackage. The client has already uploaded its KeyPackages to its own `KeyPackageEndpoint` (§3 step 6), and the enrollment agent fetches one from there (§8.2).

### 8.1 Enrollment Service Validation

On receipt of a registration request, the Enrollment Service MUST:

1. Verify the challenge exists, has not expired, and has not been consumed.
2. Verify `discordUserId` matches the active Discord OAuth2 session for this request.
3. Look up `discordUserId` in the provisional member list; return 404 if not found.
4. Check the provisional record's `status` field; if `"enrolled"`, return 409 with the existing DID (idempotent re-enrollment is allowed, but the DID MUST NOT change).
5. Resolve the DID (for `did:webvh`, verifying the full log; spec §2.1) and verify `proofOfPossession` against its `authentication` verification method.
6. Locate the user's `KeyPackageEndpoint`: the DID document service entry, or the `_kp._agora.` field of the verified Pkarr record for `did:key` (spec §2.1).
7. Mark the challenge consumed.
8. Update the provisional member record: `did = <did>`, `status = "enrolled"`.
9. Add the member to the Space's MLS groups (§8.2).
10. Return success with the space URI. The Welcome is delivered to the user's `KeyPackageEndpoint`, not in this response.

### 8.2 MLS Add Commit

The Enrollment Service holds the space enrollment agent's MLS credentials, specifically the ability to issue Add commits. This is either the space owner's signing key (if delegated) or a dedicated enrollment agent key added to the space's MLS group at setup time. The service:

1. Fetches one KeyPackage from the user's `KeyPackageEndpoint`; the fetch consumes it (spec §5.2.1.1). It validates the KeyPackage as in spec §5.2.1.1 (signature and leaf credential match the DID, not expired, ciphersuite matches the group).
2. Constructs the commit:

   ```
   MLSMessage {
     Add { KeyPackage: <fetched from the user's KeyPackageEndpoint> }
   }
   ```

3. Publishes the commit to the channel like any member's handshake message, signed with the channel admission key (`admissionSig`, spec §5.2.2), which the enrollment agent holds as a channel member. The relay checks only that signature and carries ciphertext; it neither processes the commit nor learns who was added.
4. POSTs the Welcome, with the `ratchet_tree` extension, to the same `KeyPackageEndpoint` (spec §4.6, §5.2.1).
5. Updates the Space membership in Space state through the CO's Space endpoint (spec §3.4).

The client retrieves the Welcome from its identity host and initializes its local MLS state. It then fetches each channel's `ChannelAdmissionKey` from the Space endpoint (spec §5.2.2), so that it can subscribe and publish. It can decrypt space messages from the Add epoch forward.

---

## 9. Update Path (Re-enrollment)

A user who already has a DID (from a prior enrollment or manual setup) can update their record. The flow is identical to the create path except:

- At step 4 of §8.1: if the provisional record already has a DID, the service MUST verify that the new registration's DID matches the existing one. A DID change is not permitted through this flow. Loss of device keys is handled by recovery, which keeps the DID (Agora spec §2.4); a `did:key` identity has no recovery beyond its backup.
- Adding a new device (second hardware key, new phone) uses the multi-device flow of spec §2.6, not this tool: once the new device's key is in the DID document, an existing device adds it to the user's self-group and to each of the user's groups. For `did:key`, the user copies the identity key to the new device from the keyfile (spec §2.1); the new device generates its own leaf signature key and device binding (spec §5.2.1), and the user pairs it with an existing device so that device learns the new leaf key (spec §2.6).

The update path's primary use case is a user who enrolled but lost their keyfile and needs to re-download it. The tool re-generates the keyfile from the existing registered keypair if it is still accessible in the browser's storage or the CLI keystore.

---

## 10. Error Handling

| Condition | Browser UX | CLI UX |
|---|---|---|
| Discord user not in provisional list | "Your Discord account (@username) isn't on the list for this space. Ask the space admin to run the enrollment sync." | Same message; exit 1 |
| Already enrolled, same DID | "You're already enrolled. Here's your space link: [uri]. Re-download your keyfile?" | Prompt to re-export keyfile |
| Already enrolled, DID mismatch | "This Discord account is already enrolled with a different identity. Contact your space admin." | Same message; exit 1 |
| WebCrypto Ed25519 not supported | Fall back to a reviewed JavaScript or WebAssembly Ed25519 implementation with a prominent security warning (spec §2.2) | N/A |
| Passkey creation cancelled by user | "Enrollment paused. Come back when you're ready to create a passkey." | N/A |
| Challenge expired | Re-fetch challenge automatically and retry once; display error on second failure | Same |
| Relay unreachable | "Your identity was created but couldn't be registered with the space yet. Your keyfile is safe. Try again later." | Same |
| Identity host unreachable | "Your identity host (host.example) isn't responding, so the space can't fetch your keys. Try again later or choose another host." | Same |
| `did:key` chosen in browser | Not offered; the method list explains that `did:key` requires the CLI | N/A |
| Keyfile passphrase mismatch (CLI) | N/A | Re-prompt up to 3 times, then abort |

---

## 11. Enrollment Service API

Endpoints:

```
GET  /v1/enroll/challenge          Fetch enrollment challenge (§5.4)
POST /v1/enroll/register           Submit DID registration (§8)
GET  /v1/enroll/status/:discord_id Check enrollment status
POST /v1/enroll/sync               Operator: reload provisional member list from file
GET  /v1/enroll/space              Return space URI and display metadata for this enrollment instance
```

Configuration (`config.toml`):

```toml
[enrollment]
discord_client_id     = "..."
discord_client_secret = "..."
space_uri             = "agora://bafkrei.../"
relay_url             = "wss://relay.example.com"
provisional_members   = "/data/provisional-members.json"
admin_key             = "/secrets/enrollment-agent.key"
challenge_ttl_seconds = 300
```

`admin_key` is the enrollment agent's Ed25519 private key. This agent MUST be a member of the space's MLS group with permission to issue Add commits. It is added to the space at setup time; the `discord2agora` tool generates a placeholder enrollment agent entry in SpaceState when `--enrollment-service` is specified. The genesis Space state should also set the `guardian` field, which spec §3.3 recommends and which lets named guardians transfer ownership after a delay if the owner's key is lost (spec §4.1). For a migrated community the owner should be a key the community's operators control, not the enrollment agent.

---

## 12. Browser App: Implementation Notes

**Framework:** Vanilla JS or Svelte. React MUST NOT be used: the key generation logic is security-sensitive, and a heavyweight component framework adds unnecessary attack surface and bundle complexity.

**WebCrypto availability:** Required. The app MUST check `window.crypto.subtle` on load and MUST display a hard error if absent (this only occurs on non-HTTPS origins, which MUST NOT occur in production).

**Ed25519 and passkey availability:** The app checks for WebCrypto Ed25519 by attempting `crypto.subtle.generateKey({ name: "Ed25519" }, ...)`. If it fails, the app uses a reviewed JavaScript or WebAssembly Ed25519 implementation (spec §2.2) with a visible warning banner: "Your browser cannot protect your signing key. Consider enrolling with a current browser or the CLI." The app checks `window.PublicKeyCredential` before creating the passkey (§5.1).

**Key material lifetime:** The device key is held as described in §5.1 and is never exported. The X25519 keypair is held in a `CryptoKey` with `extractable: true`; it MUST be exported to the keyfile immediately after generation, and all references to the extractable object MUST be dropped after the keyfile download is initiated.

**Service worker restrictions:** The enrollment page MUST NOT be served with a service worker that could cache responses containing key material. All enrollment API responses MUST carry the HTTP header `Cache-Control: no-store`, which is separate from the Content Security Policy.

---

## 13. CLI: Implementation Notes

**Language:** Go. Same rationale as `discord2agora`: consistent toolchain, mature keychain libraries.

**Key dependencies:**

| Function         | Library                               |
|------------------|---------------------------------------|
| OS keychain      | `github.com/zalando/go-keyring`       |
| PKCS#11          | `github.com/miekg/pkcs11`             |
| Ed25519          | `crypto/ed25519` (stdlib)             |
| X25519           | `golang.org/x/crypto/curve25519`      |
| Argon2id         | `golang.org/x/crypto/argon2`          |
| MLS KeyPackage   | `openmls` via CGo or pre-built binary |
| Discord OAuth2   | `golang.org/x/oauth2`                 |
| CBOR             | `github.com/fxamacker/cbor/v2`        |

**Binary distribution:** Single static binary per platform (Linux/amd64, Linux/arm64, macOS/amd64, macOS/arm64, Windows/amd64). The PKCS#11 backend requires a platform-specific shared library (not bundled); all other backends are fully static.

---

## 14. Security Considerations

**Enrollment Service privilege.** The Enrollment Service holds the enrollment agent key, which grants the ability to add members to the space MLS group. Compromise of the Enrollment Service allows an attacker to add arbitrary DIDs to the space. The service MUST be hardened accordingly: minimal attack surface, no public write endpoints beyond the registration flow, rate-limited per Discord user ID. The enrollment agent key SHOULD be rotated after the initial enrollment wave completes, or the agent SHOULD be removed from the MLS group entirely if no further enrollments are expected.

**Identity host.** The host the user picks observes KeyPackage fetches and Welcome deliveries for that user (spec §4.6). As admission host of the DM groups the user starts or moves to it, it also learns those groups' member DIDs and relay lists (spec §4.6, §12.4, §12.11). It registers the tokens of those groups and of the user's self-group under its own billing DID, so a relay can group them as one host's traffic; a host serving only this user gives that user no anonymity at the relay (ARCHITECTURE §9). A `did:webvh` host cannot add a key without producing an invalid log (spec §2.1), so a dishonest host can deny service but cannot impersonate the user. The user can move to a different host.

**Direct messages.** Enrollment admits the user to the Space's channels only. This tool imports no Discord friendships as accepted senders, so a DM from another migrated member starts in the message request state until the user accepts it (spec §4.6.3).

**Discord OAuth2 scope.** Discord identity is used to match users to provisional records only. It does not serve as a trust anchor beyond confirming control of a Discord account. The cryptographic proof-of-possession is the binding between DID and enrollment.

**Keyfile passphrase strength.** Users who choose weak passphrases expose their device and key-agreement keys. The browser and CLI MUST enforce a minimum entropy check (zxcvbn or equivalent) and MUST reject passphrases scoring below strength 3. Implementations MUST NOT enforce arbitrary character class rules, which reduce entropy by constraining the search space.

**Enrollment window.** The Enrollment Service SHOULD have a configurable window during which new enrollments are accepted. After initial migration, the operator SHOULD close enrollment and require out-of-band approval for new members. Leaving enrollment open indefinitely against the provisional list is a low-severity risk (an attacker would need a valid Discord account present on the list) but is unnecessary after migration is complete.

---

## 15. Open Questions

1. **Multi-space enrollment.** This spec handles enrollment into a single space per deployment. An operator running multiple spaces requires multiple Enrollment Service instances. A multi-space enrollment service that presents a list of spaces to the user after Discord auth is a useful extension.

2. **Provisional list sync.** The Enrollment Service loads the provisional member list from a static file. Users added to Discord after the initial `discord2agora` run will not be in the list. A `POST /v1/enroll/sync` endpoint is specified (§11), but the sync source (incremental re-execution of `discord2agora` or direct Discord API access) is not yet defined.

3. **Passphrase recovery.** If a user loses their keyfile passphrase, the keyfile contents are inaccessible; the offline recovery key (§5.2) is unaffected. There is no protocol-level remedy for the keyfile itself. Operators SHOULD communicate this clearly during enrollment. A Shamir-based guardian recovery scheme (Agora spec §2.4.2) is a natural extension but is out of scope for this tool.

4. **WebAuthn credential ID storage.** Resolved by §5.1: the keyfile holds no WebAuthn credential ID. The passkey's credential ID is stored beside the wrapped device key in browser storage, and the two are lost together.

5. **Platform authenticator sync behavior.** Platform authenticators on Windows (Hello) and macOS/iOS (iCloud Keychain) may sync credentials across devices via the platform. This is both a feature (multi-device from day one) and a concern (credentials leave the device). The app SHOULD inform users of this behavior and SHOULD recommend a FIDO2 roaming authenticator (YubiKey, etc.) for higher-assurance deployments.

6. **WebAuthn signatures as protocol signatures.** Resolved (spec §2.2, §12.6). A WebAuthn authenticator signs only `authenticatorData || SHA-256(clientDataJSON)`, so a passkey cannot be the device key. The browser signs with a non-extractable WebCrypto Ed25519 device key, and the passkey only protects the stored key through the PRF extension (§5.1).
