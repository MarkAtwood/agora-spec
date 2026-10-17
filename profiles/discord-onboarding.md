# Tool Specification: `agora-enroll`

**Version:** 0.1 Draft
**Depends On:** Agora Protocol Spec v0.1, `discord2agora` spec v0.1
**Status:** Pre-implementation design

---

## 1. Purpose

`agora-enroll` is the user-facing counterpart to `discord2agora`. It authenticates a user via Discord OAuth2, creates or loads their Agora DID and device keypair, and registers that DID against their provisional member record in a target Space. The result is a fully-enrolled Agora identity ready for immediate use.

**Scope: individuals.** This profile is for people who join a Space as themselves. Each user chooses their own DID method and host (§3.1, spec §2.1). Identities provisioned by an employer follow spec §2.5 and the employer profiles (`profiles/o365-employer-did.md`, `profiles/gsuite-employer-did.md`, `profiles/universal-idp-did.md`), in which the employer runs the DID log and KeyPackage host; `agora-enroll` is not used there.

Two delivery targets are supported:

- **Browser app** (`enroll.agora.example.com` or self-hosted): zero install, WebAuthn-primary, covers the majority of users.
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
9. **Keyfile export**: the tool produces the encrypted device-key and state backup file for the user to save. It never contains the recovery private key.
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

**`did:key`.** Before creating a `did:key` identity, the tool MUST show the warning required by spec §2.1: losing the key loses the identity permanently, a lost or stolen device cannot be revoked, and there is no recovery beyond the user's own encrypted backup. The user confirms explicitly. The tool then publishes the user's Pkarr pointer record (spec §2.1, §10.3.4.6) with `_kp._agora.` set to the `KeyPackageEndpoint` URL at the host the user picked; the record MUST NOT name a relay. The client re-publishes the record every 2 hours (spec §10.3.4.6). `did:key` is CLI-only because the Pkarr record must be signed by the raw Ed25519 identity key and the identity key must be exportable to reach the user's other devices (spec §2.1); a WebAuthn credential satisfies neither. The CLI offers `did:key` only with the encrypted file or OS keychain backend, or with PKCS#11 if the user accepts a single-device identity.

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

Discord explicitly permits loopback redirect URIs for installed applications. The port is OS-assigned (random) to avoid conflicts. The operator MUST register the loopback URI in Discord's developer portal either with a wildcard port or a fixed registered port.

---

## 5. Key Generation: Browser Path (WebAuthn-Primary)

### 5.1 Authenticator-Bound Key

The browser uses the WebAuthn API to create a credential bound to the user's hardware authenticator (security key, platform authenticator via Touch ID, Windows Hello, etc.):

```javascript
const credential = await navigator.credentials.create({
  publicKey: {
    challenge: enrollmentChallenge,      // 32 bytes from Enrollment Service
    rp: { name: "Agora Enrollment", id: rpId },
    user: {
      id: discordUserIdBytes,            // Discord user ID as bytes
      name: discordUsername,
      displayName: discordUsername
    },
    pubKeyCredParams: [
      { type: "public-key", alg: -8 },   // Ed25519 (preferred)
      { type: "public-key", alg: -7 }    // P-256 (fallback)
    ],
    authenticatorSelection: {
      residentKey: "preferred",
      userVerification: "required"
    },
    attestation: "none"
  }
});
```

Ed25519 (`alg: -8`) is preferred because Agora uses Ed25519 natively. P-256 (`alg: -7`) is the fallback for authenticators that do not support Ed25519 (most platform authenticators on Windows and older Android). When P-256 is used, the DID document uses a `P-256` verification method type instead of `Ed25519VerificationKey2020`; all other protocol behavior is identical.

The WebAuthn public key becomes the device's `authentication` verification method in the DID document (§5.3):

```javascript
const publicKeyBytes = credential.response.getPublicKey(); // COSE-encoded
const rawPublicKey = coseToRaw(publicKeyBytes);            // strip COSE wrapper
const publicKeyMultibase = multibaseEncode('ed25519-pub', rawPublicKey);
```

The private key never exists in JavaScript. The DID itself is not derived from this key: a `did:webvh` DID embeds the SCID of its genesis log entry, and a `did:plc` DID comes from its genesis operation (§3.1). The browser path does not offer `did:key` (§3.1).

### 5.2 Recovery Key (Offline)

The recovery key (Agora spec §2.4.1) MUST NOT be generated by the browser app or by any enrollment step that runs on a networked device, because spec §2.4.1 forbids its private key from entering a networked device or software keystore. The browser and the networked CLI handle only its public key.

The user generates the recovery key out of band with `agora-enroll recovery-keygen` (§6.6) on an offline device, or on a hardware security key, and gives the enrollment tool the resulting `publicKeyMultibase` (pasted, or scanned as a QR code). The tool MUST validate that the value decodes to a 32-byte Ed25519 public key and MUST show its fingerprint for the user to compare against the offline device.

Where the key is registered depends on the method (spec §2.4). For `did:webvh` it is listed as a `recoverableIdentity` verification method and as an authorized update key of the DID log. For `did:plc` it is registered as a rotation key. For `did:key` the tool MUST NOT ask for a recovery key, because no recovery mechanism other than encrypted backup applies (spec §2.4).

A `did:webvh` or `did:plc` user MAY skip this step. The DID document then omits `recoverableIdentity` (or the extra rotation key), and the app MUST warn that no recovery key is registered and point to the other recovery mechanisms (Agora spec §2.4.2, §2.4.3).

### 5.3 DID Document Assembly

For `did:webvh`, the DID document in the genesis log entry combines the WebAuthn-bound device key, the user-supplied recovery public key and the `KeyPackageEndpoint` at the chosen host:

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
    "serviceEndpoint": "https://host.example/alice/keypackages"
  }]
}
```

The `authentication` key is the WebAuthn-bound key. The `recoverableIdentity` key is the offline-generated recovery public key (§5.2); the log's parameters list it, with the device key, as an update key. The `keyAgreement` key is a fresh X25519 keypair generated by the browser (WebCrypto, extractable, included in the keyfile). A `did:plc` document carries the same verification methods and service entry; the recovery key appears as a rotation key instead of in `recoverableIdentity`.

### 5.4 Enrollment Challenge

Before key generation, the browser MUST fetch a short-lived challenge from the Enrollment Service:

```
GET /v1/enroll/challenge?discord_user_id=<id>
→ { "challenge": "<32-byte-base64url>", "expires": "<iso8601>", "space": "<agora-uri>" }
```

The challenge is used as the WebAuthn `challenge` field, binding the credential creation to this specific enrollment session. The Enrollment Service MUST verify the challenge on registration. Challenges expire in 5 minutes and are single-use; the service MUST mark a challenge consumed on first use.

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

`keyMaterial` is a CBOR struct containing the Ed25519 private key, X25519 private key, DID, and creation timestamp. The file format matches the Agora spec §2.4.3 encrypted backup format (`backupType: "full"`).

The passphrase is prompted at key generation and at each subsequent use. It MUST NOT be stored anywhere. The CLI MUST require the passphrase to be confirmed twice at generation.

### 6.4 PKCS#11 Backend

The CLI uses the PKCS#11 interface to generate a key on the hardware token. The private key is non-extractable (stays on device). The public key is retrieved for DID derivation. Supported mechanisms: `CKM_EDDSA` (Ed25519), `CKM_ECDSA` (P-256 fallback). The PKCS#11 library path is configurable in `~/.agora/config.toml`:

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
  "keyPackageEndpoint": "https://host.example/alice/keypackages",
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
  "stateBackup": {
    "description": "MLS group state; restores space membership continuity",
    "backupType": "stateOnly",
    "encryptedState": "<base64url-AES256GCM-ciphertext>"
  },
  "primaryKeyType": "webauthn",
  "primaryKeyCredentialId": "<base64url>",
  "primaryKeyPublicMultibase": "z6Mk...",
  "rpId": "enroll.agora.example.com"
}
```

For the CLI with an extractable keystore backend, `primaryKeyType` is `"software"` and the file additionally includes:

```json
"primaryKeypair": {
  "description": "Ed25519 primary signing key",
  "encryptedPrivateKey": "<base64url-AES256GCM-ciphertext>",
  "publicKeyMultibase": "z6Mk..."
}
```

For PKCS#11, `primaryKeyType` is `"pkcs11"` and `primaryKeypair` is omitted (non-extractable); only `primaryKeyPublicMultibase` is present.

**Passphrase derivation:** A single Argon2id invocation produces a 96-byte output. The first 32 bytes encrypt `keyAgreementKeypair.encryptedPrivateKey`; the second 32 bytes encrypt `stateBackup`. When a `primaryKeypair` is present, the third 32-byte block encrypts it. This avoids key reuse without requiring multiple passphrase entries.

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
  "webauthnAssertion": { ... },   // present only in browser/WebAuthn path
  "spaceURI": "agora://bafyrei.../"
}
```

**Proof payload** (the data signed to produce `proofOfPossession`):

```json
{
  "did": "did:webvh:QmSCID...:host.example:alice",
  "discordUserId": "123456789012345678",
  "challenge": "<challenge>",
  "spaceURI": "agora://bafyrei.../",
  "ts": "2026-03-13T00:00:00Z"
}
```

In the WebAuthn path, `proofOfPossession` is the WebAuthn assertion signature (the authenticator signs the challenge), and `webauthnAssertion` carries the full assertion object for verification. In the CLI path, `proofOfPossession` is a JWS over the proof payload signed by the device key (spec §13.1.1).

The request carries no KeyPackage. The client has already uploaded its KeyPackages to its own `KeyPackageEndpoint` (§3 step 6), and the enrollment agent fetches one from there (§8.2).

### 8.1 Enrollment Service Validation

On receipt of a registration request, the Enrollment Service MUST:

1. Verify the challenge exists, has not expired, and has not been consumed.
2. Verify `discordUserId` matches the active Discord OAuth2 session for this request.
3. Look up `discordUserId` in the provisional member list; return 404 if not found.
4. Check the provisional record's `status` field; if `"enrolled"`, return 409 with the existing DID (idempotent re-enrollment is allowed, but the DID MUST NOT change).
5. Resolve the DID (for `did:webvh`, verifying the full log; spec §2.1) and verify `proofOfPossession` against its `authentication` verification method.
6. In the WebAuthn path, additionally verify the WebAuthn assertion against the RP origin and the challenge.
7. Locate the user's `KeyPackageEndpoint`: the DID document service entry, or the `_kp._agora.` field of the verified Pkarr record for `did:key` (spec §2.1).
8. Mark the challenge consumed.
9. Update the provisional member record: `did = <did>`, `status = "enrolled"`.
10. Add the member to the Space's MLS groups (§8.2).
11. Return success with the space URI. The Welcome is delivered to the user's `KeyPackageEndpoint`, not in this response.

### 8.2 MLS Add Commit

The Enrollment Service holds the space enrollment agent's MLS credentials, specifically the ability to issue Add commits. This is either the space owner's signing key (if delegated) or a dedicated enrollment agent key added to the space's MLS group at setup time. The service:

1. Fetches one KeyPackage from the user's `KeyPackageEndpoint`; the fetch consumes it (spec §5.2.1.1). It validates the KeyPackage as in spec §5.2.1.1 (signature and leaf credential match the DID, not expired, ciphersuite matches the group).
2. Constructs the commit:

   ```
   MLSMessage {
     Add { KeyPackage: <fetched from the user's KeyPackageEndpoint> }
   }
   ```

3. Publishes the commit to the channel like any member's handshake message, with the epoch access proof the relay checks (spec §5.2.2). The relay carries ciphertext; it neither processes the commit nor learns who was added.
4. POSTs the Welcome, with the `ratchet_tree` extension, to the same `KeyPackageEndpoint` (spec §4.6, §5.2.1).
5. Updates the Space membership in Space state through the CO's Space endpoint (spec §3.4).

The client retrieves the Welcome from its identity host and initializes its local MLS state. It can decrypt space messages from the Add epoch forward.

---

## 9. Update Path (Re-enrollment)

A user who already has a DID (from a prior enrollment or manual setup) can update their record. The flow is identical to the create path except:

- At step 4 of §8.1: if the provisional record already has a DID, the service MUST verify that the new registration's DID matches the existing one. A DID change is not permitted through this flow. Loss of device keys is handled by recovery, which keeps the DID (Agora spec §2.4); a `did:key` identity has no recovery beyond its backup.
- Adding a new device (second hardware key, new phone) uses the standard Agora multi-device enrollment flow from the existing device, not this tool. For `did:key`, the user copies the identity key to the new device from the keyfile (spec §2.1).

The update path's primary use case is a user who enrolled but lost their keyfile and needs to re-download it. The tool re-generates the keyfile from the existing registered keypair if it is still accessible via the user's authenticator or CLI keystore.

---

## 10. Error Handling

| Condition | Browser UX | CLI UX |
|---|---|---|
| Discord user not in provisional list | "Your Discord account (@username) isn't on the list for this space. Ask the space admin to run the enrollment sync." | Same message; exit 1 |
| Already enrolled, same DID | "You're already enrolled. Here's your space link: [uri]. Re-download your keyfile?" | Prompt to re-export keyfile |
| Already enrolled, DID mismatch | "This Discord account is already enrolled with a different identity. Contact your space admin." | Same message; exit 1 |
| WebAuthn not supported | Fall back to software key generation with a prominent security warning | N/A |
| WebAuthn cancelled by user | "Enrollment paused. Come back when you have your security key ready." | N/A |
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
space_uri             = "agora://bafyrei.../"
relay_url             = "wss://relay.example.com"
provisional_members   = "/data/provisional-members.json"
admin_key             = "/secrets/enrollment-agent.key"
rp_id                 = "enroll.agora.example.com"
rp_origin             = "https://enroll.agora.example.com"
challenge_ttl_seconds = 300
```

`admin_key` is the enrollment agent's Ed25519 private key. This agent MUST be a member of the space's MLS group with permission to issue Add commits. It is added to the space at setup time; the `discord2agora` tool generates a placeholder enrollment agent entry in SpaceState when `--enrollment-service` is specified.

---

## 12. Browser App: Implementation Notes

**Framework:** Vanilla JS or Svelte. React MUST NOT be used: the key generation logic is security-sensitive, and a heavyweight component framework adds unnecessary attack surface and bundle complexity.

**WebCrypto availability:** Required. The app MUST check `window.crypto.subtle` on load and MUST display a hard error if absent (this only occurs on non-HTTPS origins, which MUST NOT occur in production).

**WebAuthn availability:** The app checks `window.PublicKeyCredential` and `PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()`. If WebAuthn is unavailable or the user has no platform authenticator, the app falls back to software key generation using `crypto.subtle.generateKey` with `extractable: true`, with a visible warning banner: "Your keys are software-generated and less secure than a hardware authenticator. Consider enrolling again with a security key."

**Key material lifetime:** All private key material the app generates (the X25519 keypair, and the software primary key in the fallback above) is held only in `CryptoKey` objects with `extractable: true`. Material MUST be exported to the keyfile immediately after generation, and all references MUST be dropped after the keyfile download is initiated. The app MUST NOT retain key material beyond keyfile export.

**Service worker restrictions:** The enrollment page MUST NOT be served with a service worker that could cache responses containing key material. CSP headers MUST include `Cache-Control: no-store` on all enrollment API responses.

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

**Identity host.** The host the user picks observes KeyPackage fetches and Welcome deliveries for that user (spec §4.6). A `did:webvh` host cannot add a key without producing an invalid log (spec §2.1), so a dishonest host can deny service but cannot impersonate the user. The user can move to a different host.

**Discord OAuth2 scope.** Discord identity is used to match users to provisional records only. It does not serve as a trust anchor beyond confirming control of a Discord account. The cryptographic proof-of-possession is the binding between DID and enrollment.

**Keyfile passphrase strength.** Users who choose weak passphrases expose their device and key-agreement keys. The browser and CLI MUST enforce a minimum entropy check (zxcvbn or equivalent) and MUST reject passphrases scoring below strength 3. Implementations MUST NOT enforce arbitrary character class rules, which reduce entropy by constraining the search space.

**Enrollment window.** The Enrollment Service SHOULD have a configurable window during which new enrollments are accepted. After initial migration, the operator SHOULD close enrollment and require out-of-band approval for new members. Leaving enrollment open indefinitely against the provisional list is a low-severity risk (an attacker would need a valid Discord account present on the list) but is unnecessary after migration is complete.

---

## 15. Open Questions

1. **Multi-space enrollment.** This spec handles enrollment into a single space per deployment. An operator running multiple spaces requires multiple Enrollment Service instances. A multi-space enrollment service that presents a list of spaces to the user after Discord auth is a useful extension.

2. **Provisional list sync.** The Enrollment Service loads the provisional member list from a static file. Users added to Discord after the initial `discord2agora` run will not be in the list. A `POST /v1/enroll/sync` endpoint is specified (§11), but the sync source (incremental re-execution of `discord2agora` or direct Discord API access) is not yet defined.

3. **Passphrase recovery.** If a user loses their keyfile passphrase, the keyfile contents are inaccessible; the offline recovery key (§5.2) is unaffected. There is no protocol-level remedy for the keyfile itself. Operators SHOULD communicate this clearly during enrollment. A Shamir-based guardian recovery scheme (Agora spec §2.4.2) is a natural extension but is out of scope for this tool.

4. **WebAuthn credential ID storage.** The keyfile stores the WebAuthn credential ID (`primaryKeyCredentialId`). A user who loses the keyfile retains their authenticator but may not know which credential to use if multiple are present. A credential hint stored via the authenticator's `residentKey` (if `residentKey: "preferred"` was honored) mitigates this.

5. **Platform authenticator sync behavior.** Platform authenticators on Windows (Hello) and macOS/iOS (iCloud Keychain) may sync credentials across devices via the platform. This is both a feature (multi-device from day one) and a concern (credentials leave the device). The app SHOULD inform users of this behavior and SHOULD recommend a FIDO2 roaming authenticator (YubiKey, etc.) for higher-assurance deployments.

6. **WebAuthn signatures as protocol signatures.** A WebAuthn authenticator signs `authenticatorData || SHA-256(clientDataJSON)`, not an arbitrary payload. It therefore cannot directly produce the `did:webvh` log proofs, PLC operations or JWS signatures (spec §13.1.1) that a device `authentication` key makes. The browser path as written depends on resolving this, either by a WebAuthn-compatible signature profile or by generating a separate software Ed25519 device key in the browser.
