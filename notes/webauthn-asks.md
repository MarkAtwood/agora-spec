# WebAuthn asks from Agora (draft for Mark)

Status: draft, 2026-10-16. Mark sends; nothing here has been filed or posted upstream.

## Summary

Agora wants passkeys to sign a small number of high-value, non-WebAuthn payloads, and wants PRF to behave the same everywhere. The asks:

1. Standardize the arbitrary-payload signing extension (today `previewSign`, w3c/webauthn PR #2078) in Level 4, and include Ed25519 alongside ESP256.
2. Keep signing keys gesture-bound for web callers: user verification on every signature, with no web-exposed option for unattended keys. Agora explicitly does not want gesture-free per-message signing.
3. Make PRF dependable: the same credential and salt must yield the same output on-device, over hybrid, and across synced devices, and `getClientCapabilities()` should report `extension:prf` only when the authenticator will actually return a result.

None of these block Agora. The current design works without them; each ask removes a weakness in it.

## Agora's use case

Agora is a decentralized messaging protocol built on MLS, with users identified by DIDs (`did:webvh`, `did:plc`, `did:key`). Each device holds its own Ed25519 device key, listed as a `verificationMethod` in the user's DID document. That key signs MLS leaf nodes, KeyPackages, commits and JWS records (spec §2.2, §13.1.1).

Signing happens at three rates:

- Everyday signing (MLS operations, routine JWS) runs constantly and must be silent. A user gesture per message would make the product unusable.
- Device registration happens once per device. The user authenticates to an identity host (an employer provisioning service or a host they chose) with a passkey. Only that host parses WebAuthn.
- High-value signatures are rare: `did:webvh` log entries (adding or removing a device key, rotating keys), and JWS records with lasting effect, such as organizational authority grants. These happen a few times per year per user, and a fresh user-verified gesture for each one is acceptable and desirable.

The third category is where WebAuthn falls short today. A WebAuthn assertion signs only `authenticatorData || SHA-256(clientDataJSON)`, so a passkey cannot produce a `did:webvh` log proof or a JWS that a generic verifier accepts. Agora therefore cannot list a passkey as a verification method (spec §2.2), and the most sensitive operations get signed by the same software-held browser key as everything else.

## What Agora does today

The design was decided on 2026-10-16 (spec §2.2, §12.6):

- Browser clients generate an Ed25519 key with WebCrypto and sign only through a non-extractable `CryptoKey`. WebCrypto Ed25519 ships in Firefox 129, Safari 17 and Chrome 137 and later.
- Where the passkey supports PRF, the client wraps the device key under an AES key derived by HKDF from the PRF output, stores only the wrapped key, and unwraps it as non-extractable once per session. A copied browser profile is useless without the passkey.
- Where PRF is missing, the client stores the non-extractable `CryptoKey` directly in IndexedDB.
- Cleared storage means registering a new device. A stolen device is revoked by removing its key from the DID document and its leaves from MLS groups.
- Native apps use hardware-backed keystores (Secure Enclave, StrongBox, TPM).

The weakness: in a browser, the key that signs a `did:webvh` log entry is a software key with no per-operation user verification. Once a session has unwrapped it, script running in that origin can sign anything. A passkey-bound signing key with UV on every signature would let Agora require, for example, that `did:webvh` log entries from browser clients carry a signature from a key the user must actively approve.

## Ask 1: a standard arbitrary-payload signing extension, with Ed25519

The `previewSign` draft (Emil Lundberg, Yubico) is close to what Agora needs. It signs the input unaltered, using a key associated with but distinct from the credential key, so the WebAuthn domain binding of the credential itself is preserved. That signing key could appear in a DID document as its own verification method.

Current state, as verified:

- PR #2078 "Add 'sign' extension" is a draft, labeled `stat:Discuss`, on the L4 milestone, with activity as recent as September 2026.
- The standalone draft is at version 4 (snapshot 2025-08-21) under the identifier `previewSign`.
- The W3C explainer lists ESP256 (-9), ESP256-split (-300, preliminary) and ARKG-derived P-256 keys. Ed25519 is not mentioned in the explainer, the Yubico developer page, or the PR discussion we read.
- YubiKey firmware 5.8 implements it in early access, with `ARKG_P256_ESP256` (algorithm ID -65539, marked not final).
- The explainer records "No signals" from Chrome, Firefox, Safari and Edge.
- WebAuthn Level 3 became a W3C Recommendation on 2026-08-25 without any signing extension.

The ask: adopt the extension in Level 4 and name Ed25519 as an allowed algorithm (the fully specified COSE identifier, or EdDSA -8 with Ed25519). Agora's device keys, DID verification methods and JWS records are Ed25519 throughout. Agora can accept ES256 on devices whose hardware lacks Ed25519 (spec §12.6 already allows this for Secure Enclave), but without Ed25519 every Agora verifier has to carry a second algorithm for the browser path. Browser vendor signals are the real gate, so the most useful thing Agora can add is a second concrete, non-wallet use case.

## Ask 2: user verification on every signature, never unattended web signing

The explainer fixes a signing key's UP/UV policy at creation time, for the life of the key, and says web applications cannot create keys without user presence. Agora supports this and asks the WG to keep it:

- A web-created signing key should require user verification, not only presence, for every signature. A touch-only key lets any script that holds a tab open collect signatures with one tap; UV ties each signature to the user.
- Agora does not want a gesture-free or session-scoped signing mode exposed to the web. Silent everyday signing is already served by non-extractable WebCrypto keys. A gesture-free passkey signer would erase the distinction that makes passkey signatures worth asking for.
- Because the signature does not cover authenticator data, a verifier cannot see the UP/UV flags. It would help if the key's fixed policy were provable to a remote verifier, for example through attestation over the signing key's creation, so that a `did:webvh` resolver can check that a key really requires UV.

## Ask 3: PRF that behaves the same everywhere

PRF (§10.1.4) is in the Level 3 Recommendation, and support is now broad. A third-party matrix (Corbado, statuses as of August 2026) reports PRF on create and get for iCloud Keychain (macOS 15+, iOS 18.4+), Google Password Manager, Windows Hello (only after the February 2026 Windows 11 update, with Chrome/Edge 147+ or Firefox 148+ for create), 1Password, and YubiKeys in Chrome, Edge and Firefox. Gaps reported by the same source and by developer forums:

- Different PRF outputs for the same passkey and salt depending on on-device versus hybrid use (Apple developer forums, Safari 18.x). For a key-wrapping design this is data loss: the device key cannot be unwrapped.
- Bitwarden returns PRF inconsistently. Microsoft Password Manager supports create but fails get. Samsung Pass is the reverse. The Chrome profile authenticator has no PRF.
- Security keys that skip PIN entry can return null. Safari security-key PRF needs 26.4+ and has open WebKit bugs.
- Capability flags overstate support: Chrome has reported `extension:prf` for managers that then returned nothing.

The ask: state normatively that a credential's PRF output for a given salt is stable across sync, hybrid transport and platforms; add conformance tests for that; and require `getClientCapabilities()` to reflect real authenticator behavior. Agora's fallback already covers missing PRF. Agora cannot detect wrong PRF output without a failed unwrap, so it has to keep a recovery path for this case.

## What we could not verify

- The per-signature UV text in the `previewSign` v4 spec body. Our summary of the UP/UV policy comes from the W3C explainer, not the normative draft.
- Whether any non-Yubico authenticator or any shipping browser implements `previewSign`.
- The 1Password and Windows Hello PRF status comes from a single third-party source (Corbado). A 1Password community thread from mid-2026 reports broken PRF in its Chrome and Firefox extensions, which conflicts with it. We did not check vendor release notes.
- Whether Apple's hybrid PRF mismatch is fixed in current releases.
- The exact COSE identifier for fully specified Ed25519 (we believe -19) was not re-checked against the IANA registry.

## Sources

- WebAuthn Level 3 Recommendation, 2026-08-25, PRF §10.1.4: https://www.w3.org/TR/webauthn-3/
- PR #2078, "Add 'sign' extension": https://github.com/w3c/webauthn/pull/2078
- Raw signing extension explainer: https://github.com/w3c/webauthn/blob/main/explainers/raw-signing-extension.md
- `previewSign` draft, version 4: https://yubicolabs.github.io/webauthn-sign-extension/4/
- Yubico, Signing Extension Preview: https://developers.yubico.com/Passkeys/Passkey_concepts/Security_key_capabilities/Signing_Extension_Preview.html
- ARKG, draft-bradleylundberg-cfrg-arkg-08: https://www.ietf.org/archive/id/draft-bradleylundberg-cfrg-arkg-08.html
- Corbado, PRF support matrix (updated 2026-09-29): https://www.corbado.com/blog/passkeys-prf-webauthn
- Apple developer forums, PRF over hybrid in Safari: https://developer.apple.com/forums/thread/774112
- 1Password community, PRF in browser extension: https://www.1password.community/developers-69/browser-extension-webauthn-prf-extension-not-spec-compliant-24672
- Chromium Intent to Ship, PRF: https://groups.google.com/a/chromium.org/g/blink-dev/c/iTNOgLwD2bI/m/Oz1C7oEYAgAJ
