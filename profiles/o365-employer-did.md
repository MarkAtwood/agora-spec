# Specification: Employer-Managed DIDs via Microsoft Entra ID

**Version:** 0.1 Draft
**Depends On:** the Agora protocol specification (`spec/`, current draft)
**Status:** Pre-implementation design

---

## 1. Architecture Overview

This specification defines how an organization using Microsoft 365 / Entra ID manages Agora `did:webvh` identities for its employees (provisioning them automatically at hire, updating claims on role changes, and revoking them at termination) without the organization ever holding or touching employee private keys. `did:webvh` is the method spec §2.1 makes the default and spec §2.5 uses for employer-provisioned identities.

Two components perform this work.

**The DID Sidecar** is the organization's DID Provisioning Service (spec §2.5.2), a CO component, here a lightweight HTTPS service registered as an Entra application. It owns the namespace `https://did.example.com/users/{localIdentifier}/` and serves each user's `did:webvh` log (`did.jsonl`). It holds the update key for every employee log, receives provisioning events from Graph Lifecycle Workflows via a Logic App bridge, accepts authenticated device key registration requests from employees during Agora enrollment, and hosts each employee's `KeyPackageEndpoint` (spec §5.2.1.1). It is the only component that writes DID log entries.

**Entra Verified ID** issues a signed `EmployeeCredential` verifiable credential to each enrolled employee's wallet (Microsoft Authenticator). The VC is the organization's cryptographic attestation that the holder is a current employee with specific claims (department, role, clearance level). It is issued after the first device key is registered (§4.2), and Spaces MAY require it for admission (§4.3). VC revocation is the organization's mechanism for immediately invalidating access without writing a DID log entry.

Relays play no part in this profile. They never receive or verify Entra tokens; IdP authentication runs between the client, Entra and the sidecar (spec §2.5.2).

These two components are intentionally independent and address different concerns:

| Concern                                               | Component                                                        |
| ----------------------------------------------------- | ---------------------------------------------------------------- |
| Org controls identity namespace and can revoke        | DID Sidecar (deactivates the DID log)                            |
| Org attests employee status with auditable trail      | Entra Verified ID (EmployeeCredential)                           |
| Employee controls private key                         | DID Sidecar (device key generated and registered by client, never by org) |
| Org key insertion is auditable                        | DID log (every update-key entry is visible to all resolvers)     |
| Immediate access revocation without DID deactivation  | Entra Verified ID (VC revocation)                                |
| Specific device revocation (lost device)              | DID Sidecar (log entry removing one `verificationMethod`)        |
| KeyPackage hosting and Welcome delivery               | DID Sidecar (`KeyPackageEndpoint`)                               |

```
┌─────────────────────────────────────────────────────────────────────┐
│  Microsoft Entra ID Tenant                                          │
│                                                                     │
│  ┌─────────────────────────┐   ┌──────────────────────────────┐    │
│  │  Lifecycle Workflows    │   │  Verified ID                 │    │
│  │  (Joiner/Mover/Leaver)  │   │  (EmployeeCredential issuer) │    │
│  └──────────┬──────────────┘   └──────────────┬───────────────┘    │
│             │ customTaskExtension              │ issuance API       │
│             ▼                                 ▼                    │
│  ┌──────────────────────┐      ┌──────────────────────────────┐    │
│  │  Azure Logic App     │      │  Entra Verified ID Service   │    │
│  │  (JML bridge)        │      │  (credential lifecycle)      │    │
│  └──────────┬───────────┘      └──────────────────────────────┘    │
│             │ HTTPS POST                                            │
└─────────────┼───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DID Sidecar  (CO-hosted provisioning service, Entra app)           │
│                                                                     │
│  GET  /users/{id}/did.jsonl       Serve DID log (public)           │
│  POST /v1/provision               JML event receiver                │
│  POST /v1/register-device-key     Device key registration           │
│  POST /v1/revoke-device-key       Device key removal (IT/MDM)       │
│  POST /v1/tombstone               DID deactivation                  │
│  *    /v1/keypackages/{id}        KeyPackageEndpoint                │
│                                                                     │
│  Storage: per-user DID logs in Azure Blob or Postgres               │
│  Keys: log update key in Azure Key Vault (HSM)                      │
│  Auth: Entra app registration, managed identity                     │
└─────────────────────────────────────────────────────────────────────┘
              │
              │  serves
              ▼
  did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m   (Alice's Agora DID)
  did:webvh:QmSCIDb...:did.example.com:users:p2x9rw4c   (Bob's Agora DID)
```

---

## 2. DID Naming Convention

Each employee's DID takes the form (spec §2.5.2):

```
did:webvh:<SCID>:did.example.com:users:<localIdentifier>
```

`<SCID>` is the self-certifying identifier derived from the genesis entry of the user's DID log. Each user has their own SCID.

Per spec §2.5.2, `<localIdentifier>` MUST be stable for the life of the account, MUST NOT be reassigned, and MUST NOT be derived from the UPN, email address, display name or any other attribute that can change. A DID is not a display name; clients show the display profile (spec §2.3), never a parsed DID.

**Recommended default:** the sidecar mints a random lowercase base32 value at Joiner time (the examples use 8 characters), checks it for uniqueness, and stores the mapping to the Entra `objectId` (`aadObjectId`, the token `oid` claim) in its private store (§6.3). The mapping is never published.

**Allowed alternatives:** the Entra `objectId`, or an HR employee ID that is never reused. A sidecar-minted random value is preferred because it survives a move to a different tenant or IdP; an `objectId` does not.

```
did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m
```

The `did:webvh` method maps the part after the SCID to an HTTPS URL as `did:web` does, with the log file `did.jsonl` in place of `did.json`. This DID resolves to:

```
https://did.example.com/users/k7f3qd2m/did.jsonl
```

Resolvers fetch the whole log and verify it (spec §2.1); the DID document is the state in the last verified entry.

**Parallel `did:web` document (optional).** For systems outside Agora that only resolve `did:web`, the sidecar MAY also serve `https://did.example.com/users/k7f3qd2m/did.json`, the current document under the DID `did:web:did.example.com:users:k7f3qd2m`. It is generated from the latest log entry and adds nothing to it. Agora clients MUST resolve the `did:webvh` log and MUST NOT accept a key from the `did:web` document that is not in the verified log (spec §2.1).

**UPN changes:** a UPN change (name change, email domain change) does not change the DID. It is a directory attribute update handled by the Mover workflow (§5.3). The sidecar identifies users by `aadObjectId`; the `upn` in Logic App payloads is informational. Only a change of the DID host (`did.example.com`) changes the DID string, and the identity survives it with the same SCID (§6.4).

---

## 3. DID Document Lifecycle

### 3.1 Document States

Each user's DID log moves through the following states. Every transition is a new log entry signed with the sidecar's update key.

```
[not exist] → STUB → ACTIVE → SUSPENDED → DEACTIVATED
                ↑                  ↓            ↑
                └──────────────────┘            │
                     (re-activation)            │
                                                │
                    ACTIVE ──────────────────────┘
                           (direct deactivation on termination)
```

| State         | Description                                                           | Latest log entry                                          |
| ------------- | --------------------------------------------------------------------- | --------------------------------------------------------- |
| `STUB`        | Provisioned by Joiner workflow; no device keys yet                    | Genesis entry: no `verificationMethod`, service entries only |
| `ACTIVE`      | At least one device key registered; fully functional                  | Full document                                             |
| `SUSPENDED`   | VC revoked (e.g., leave of absence); device public keys kept in the sidecar DB | Entry removing all keys; re-activation is a later entry restoring them |
| `DEACTIVATED` | Employee terminated; DID permanently retired                          | Final entry with `deactivated: true` and no keys          |

The log is always served with `200` and stays resolvable after deactivation for the regulatory retention period and beyond (spec §2.5.6). Because every transition is a log entry, suspension and re-activation are visible in the history; a suspension cannot be hidden by stripping keys from a served response.

The stub document contains no organization key: an org key listed as a `verificationMethod` in a user's document would let the org sign as that user. The org's authority over the document is the update key in the log `parameters` (§3.2). Agora clients that resolve this DID during a Space Add operation will find no usable authentication key; the Add commit MUST fail gracefully and prompt enrollment.

### 3.2 Stub Document (Pre-Enrollment)

The genesis log entry, created at Joiner time (spec §2.5.3). One line of `did.jsonl`, shown expanded:

```json
{
  "versionId": "1-QmHASH1...",
  "versionTime": "2026-03-12T09:00:00Z",
  "parameters": {
    "method": "did:webvh:1.0",
    "scid": "QmSCIDa...",
    "updateKeys": ["z6MkSIDECAR_UPDATE_KEY..."],
    "portable": true
  },
  "state": {
    "@context": "https://www.w3.org/ns/did/v1",
    "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
    "verificationMethod": [],
    "authentication": [],
    "keyAgreement": [],
    "service": [
      {
        "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#keypackages",
        "type": "KeyPackageEndpoint",
        "serviceEndpoint": "https://did.example.com/v1/keypackages/k7f3qd2m"
      },
      {
        "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#enrollment",
        "type": "AgoraEnrollmentEndpoint",
        "serviceEndpoint": "https://enroll.example.com/v1/enroll"
      }
    ]
  },
  "proof": [{
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "did:key:z6MkSIDECAR_UPDATE_KEY...#z6MkSIDECAR_UPDATE_KEY...",
    "proofPurpose": "assertionMethod",
    "proofValue": "z..."
  }]
}
```

`portable: true` MUST be set in the genesis entry, because `did:webvh` allows portability only when enabled at creation; it is what lets the identity survive a domain change (§6.4, spec §2.5.2). The `KeyPackageEndpoint` entry is present before the first device enrolls, as spec §2.5.3 requires. The document names no relay or other IO.

The document has no `controller` property naming the organization. With `did:webvh`, authority to change the document comes from the `updateKeys` parameter of the log, not from the DID Core `controller` property. Listing the org's DID as `controller` would add nothing for updates and, under DID Core, could let verification methods in the org's own DID document be accepted as acting for the user, a power spec §2.5.1 does not grant. Each `verificationMethod` names the user's DID as its `controller`.

What the sidecar's update key permits: adding and removing keys and service entries, deactivating the DID, and moving it to a new domain. Each such action is a signed, permanent log entry that every resolver sees. The update key does not let the org sign as the user. To do that the org would first have to add a key it holds, in a visible log entry signed with its update key, so organizational impersonation is auditable without trusting the organization (spec §2.5.1, §12.7.3). Employees hold no update key in this profile; their devices hold the `authentication` and `keyAgreement` keys only (spec §2.1).

### 3.3 Active Document (Post-Enrollment)

The `state` of the latest log entry after two devices and a recovery key are registered:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
  "verificationMethod": [
    {
      "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#device-macbook-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
      "publicKeyMultibase": "zDEVICE_KEY_1...",
      "meta": {
        "deviceLabel": "Alice's MacBook Pro",
        "registeredAt": "2026-03-13T00:00:00Z",
        "registeredVia": "webauthn"
      }
    },
    {
      "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#device-iphone-2",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
      "publicKeyMultibase": "zDEVICE_KEY_2...",
      "meta": {
        "deviceLabel": "Alice's iPhone 16",
        "registeredAt": "2026-03-13T06:00:00Z",
        "registeredVia": "webauthn"
      }
    },
    {
      "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#recovery-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
      "publicKeyMultibase": "zRECOVERY_KEY...",
      "meta": {
        "deviceLabel": "Recovery key",
        "registeredAt": "2026-03-13T00:00:00Z",
        "registeredVia": "keyfile"
      }
    }
  ],
  "authentication": [
    "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#device-macbook-1",
    "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#device-iphone-2"
  ],
  "keyAgreement": [...],
  "recoverableIdentity": [
    "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#recovery-1"
  ],
  "service": [
    {
      "id": "...#keypackages",
      "type": "KeyPackageEndpoint",
      "serviceEndpoint": "https://did.example.com/v1/keypackages/k7f3qd2m"
    },
    {
      "id": "...#profile",
      "type": "AgoraProfile",
      "serviceEndpoint": "ipfs://bafyrei..."
    }
  ]
}
```

The `meta` fields on device keys are non-standard extensions for operator tooling; they allow IT to identify which key belongs to which device when issuing targeted revocations. They are informational only and carry no cryptographic weight. Agora clients MUST ignore unknown fields in `verificationMethod` entries.

Employment attributes (department, role, status) are not published in the DID document. They live in the `EmployeeCredential` (§4.1). Putting them in the document would write every Mover change into the permanent public log, and spec §2.5.3 limits service entries to CO- or user-chosen endpoints.

---

## 4. Entra Verified ID: EmployeeCredential

### 4.1 Credential Schema

The organization defines one credential type in Verified ID: `EmployeeCredential`. This is an org-signed assertion that the holder is a current employee with specific attributes.

```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://did.example.com/credentials/employee/v1"
  ],
  "type": ["VerifiableCredential", "EmployeeCredential"],
  "issuer": "did:web:verifiedid.example.com",
  "issuanceDate": "2026-03-13T00:00:00Z",
  "expirationDate": "2027-03-13T00:00:00Z",
  "credentialSubject": {
    "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
    "employeeId": "EMP-12345",
    "displayName": "Alice Smith",
    "department": "Engineering",
    "jobTitle": "Senior Engineer",
    "officeLocation": "Seattle",
    "employmentStatus": "active",
    "agoraRoles": ["member", "engineer"]
  },
  "credentialStatus": {
    "id": "https://verifiedid.did.msidentity.com/v1.0/<tenant>/status/<statusId>",
    "type": "StatusList2021Entry",
    "statusListIndex": "42",
    "statusListCredential": "https://verifiedid.did.msidentity.com/v1.0/<tenant>/statuslist"
  }
}
```

The issuer is the Verified ID authority's own DID, a service identity separate from the employee DIDs and from the sidecar's update key.

`agoraRoles` is a custom claim read by the Enrollment Service to assign space roles at enrollment time. Mover events update this claim by issuing a new VC with revised `agoraRoles` and revoking the previous one.

`expirationDate` is one year from issuance. Annual re-issuance is automatic, triggered by a scheduled Lifecycle Workflow, providing a natural re-attestation cadence without IT action for stable employees.

### 4.2 Issuance Flow

The credential names the employee's DID as its subject, and that DID has no keys until the first device enrolls. The first-device bootstrap therefore runs in this order:

1. **Joiner (§5.2).** The sidecar writes the genesis log entry (§3.2). No VC exists yet.
2. **First device key registration (§5.6).** The client authenticates to Entra with step-up MFA and registers its device key with a proof of possession. No VC is presented or required. The sidecar writes a log entry adding the key.
3. **VC issuance.** The sidecar requests issuance of the `EmployeeCredential` to the now-active DID (below).
4. **KeyPackage upload.** The client uploads its initial KeyPackages to the sidecar's `KeyPackageEndpoint` (spec §2.5.4 Step 7).
5. **Space admission.** The Enrollment Service checks the VC if the Space requires it (§4.3) and then issues the MLS Add commit.

Later devices register with a request signed by an existing device key (§5.6); the org MAY additionally require a VC presentation for them, since by then the employee holds one.

The sidecar calls the Verified ID issuance API:

```http
POST https://verifiedid.did.msidentity.com/v1.0/<tenant>/verifiableCredentials/createIssuanceRequest
Authorization: Bearer <app token>
Content-Type: application/json

{
  "includeQRCode": false,
  "authority": "did:web:verifiedid.example.com",
  "registration": {
    "clientName": "Agora Enrollment"
  },
  "callback": {
    "url": "https://enroll.example.com/v1/vc-callback",
    "state": "<enrollment-session-id>",
    "headers": { "Authorization": "Bearer <callback-token>" }
  },
  "type": "EmployeeCredential",
  "manifest": "https://verifiedid.example.com/v1.0/credentials/employee",
  "claims": {
    "employeeId": "EMP-12345",
    "displayName": "Alice Smith",
    "department": "Engineering",
    "jobTitle": "Senior Engineer",
    "officeLocation": "Seattle",
    "employmentStatus": "active",
    "agoraRoles": "member,engineer"
  }
}
```

Verified ID returns a deep link or QR code that the enrollment app presents to the user. The user taps it in Microsoft Authenticator to add the credential to their wallet. Verified ID calls back to the enrollment service when issuance completes.

The VC is the product of completing first-device enrollment, not a precondition for it. The precondition is a valid Entra OIDC token with step-up MFA (proving the user can authenticate against the org's IdP), which the provisioning service already requires at enrollment.

### 4.3 VC as Space Admission Precondition (Optional Enforcement)

Spaces MAY require a valid `EmployeeCredential` VC as an admission precondition. When configured, the Enrollment Service MUST verify the VC presentation before issuing the MLS Add commit:

```json
POST /v1/enroll/register
{
  ...
  "vcPresentation": {
    "type": "VerifiablePresentation",
    "verifiableCredential": ["<JWT-encoded VC>"],
    "proof": { ... }
  }
}
```

The Enrollment Service validates:

1. VC issuer DID resolves to the expected org (`did:web:verifiedid.example.com`)
2. VC `credentialSubject.id` matches the registering DID
3. VC has not expired
4. VC status (StatusList2021) shows not revoked
5. VC `credentialSubject.employmentStatus` is `"active"`

This check is optional because the Teams/Entra OIDC auth already establishes org membership. It provides belt-and-suspenders assurance for high-security spaces and enables the Mover use case: a user whose department changes receives a new VC with updated `agoraRoles`, and space admission policies can enforce role-based access on VC claims rather than static provisional list entries.

---

## 5. Graph Lifecycle Workflow Integration

### 5.1 Integration Mechanism

Lifecycle Workflows support custom task extensions that call out to external systems via Azure Logic Apps in either "launch and continue" (fire-and-forget) or "launch and wait" (synchronous with timeout) modes. The DID sidecar integration uses "launch and wait" for Joiner events (so IT can confirm DID provisioning before the workflow completes) and "launch and continue" for Leaver events (immediate deactivation; no confirmation is required before revoking access).

A Microsoft Entra ID Governance license is required to use Lifecycle Workflows.

The Logic App is the bridge: it receives the workflow event from Entra, formats and signs a provisioning request, and calls the DID Sidecar's `/v1/provision` endpoint. The sidecar authenticates the request using the Logic App's managed identity token.

### 5.2 Joiner Workflow

**Trigger:** New user account created in Entra ID with `employeeHireDate` set.
**Execution:** On or before hire date (configurable; default: day of hire).
**Mode:** Launch and wait (30-second timeout).

Tasks execute in sequence:

1. Built-in: `EnableUserAccount`
2. Built-in: `AddUserToGroup` (add to Agora-users security group)
3. Custom: `ProvisionAgoraDID` (calls Logic App → DID Sidecar)
4. Built-in: `SendWelcomeEmail` (includes enrollment link)

The `ProvisionAgoraDID` Logic App payload:

```json
{
  "event": "joiner",
  "upn": "alice@example.com",
  "aadObjectId": "aad-uuid",
  "employeeId": "EMP-12345",
  "displayName": "Alice Smith",
  "department": "Engineering",
  "jobTitle": "Senior Engineer",
  "officeLocation": "Seattle",
  "agoraRoles": ["member", "engineer"],
  "spaceURI": "agora://bafyrei.../"
}
```

On receipt, the sidecar mints the `localIdentifier` (§2), writes the genesis log entry (§3.2), and records the creation and the provisioning operator in its audit log (spec §2.5.3). Synchronous response (within 30 s):

```json
{
  "did": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
  "state": "stub",
  "enrollmentURL": "https://enroll.example.com/?did=did%3Awebvh%3A..."
}
```

The `enrollmentURL` is included in the welcome email sent by the subsequent built-in task, pre-populating the enrollment app with the user's DID.

### 5.3 Mover Workflow

**Trigger:** User attribute change: `department`, `jobTitle`, `userPrincipalName`, or membership in role-mapped security groups. A `userPrincipalName` change does not change the DID (§2); the sidecar updates its private mapping (§6.3), and a name change that alters `displayName` re-issues the `EmployeeCredential`.
**Mode:** Launch and continue.

The Mover event updates the **EmployeeCredential**: the sidecar calls the Verified ID API to revoke the existing VC and issue a new one with updated claims. The new VC is delivered to the user's wallet automatically if Authenticator is configured for auto-accept from trusted issuers; otherwise the user receives a notification. The DID document is not changed, because it carries no employment attributes (§3.3).

Logic App payload:

```json
{
  "event": "mover",
  "upn": "alice@example.com",
  "aadObjectId": "aad-uuid",
  "changedAttributes": {
    "department": "Security",
    "jobTitle": "Security Engineer",
    "agoraRoles": ["member", "engineer", "security"]
  }
}
```

**Space role update:** When `agoraRoles` changes, the Enrollment Service (notified by webhook from the sidecar) issues a space role update commit for the user's existing MLS membership. This updates only the Agora role claims in the space state document; MLS group membership itself is unchanged.

### 5.4 Leaver Workflow

**Trigger:** `employeeLeaveDateTime` reached, or on-demand execution for immediate termination.
**Mode:** Launch and continue.

On-demand workflow execution handles urgent terminations without waiting for the scheduled run.

Three actions execute in parallel:

**Action A: VC Revocation (immediate):** The sidecar calls the Verified ID revocation API for the user's current `EmployeeCredential`. Revocation takes effect within seconds. Any space configured to require VC validation MUST reject the user's next message or MLS epoch participation check. This is the fast path: VC revocation is effective before the DID deactivation completes.

**Action B: DID Deactivation (within minutes):** The sidecar appends a final log entry, signed with its update key, that removes all keys and sets `deactivated: true` (the `revokeAll` offboarding of spec §2.5.5 and §2.5.6):

```json
{
  "versionId": "7-QmHASH7...",
  "versionTime": "2026-03-13T00:00:00Z",
  "parameters": { "deactivated": true, "updateKeys": [] },
  "state": {
    "@context": "https://www.w3.org/ns/did/v1",
    "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
    "verificationMethod": [],
    "authentication": [],
    "keyAgreement": []
  },
  "proof": [ ... ]
}
```

The log stays resolvable with this entry as its last (spec §2.5.6). Agora clients that resolve a deactivated DID MUST treat the identity as permanently invalid and issue MLS Remove commits for its leaves in all groups they share with it. The reason and initiator are recorded in the sidecar's audit log, not in the public document. The sidecar gossips a `DeviceRevocation` for the removed keys, signed by its own key (spec §2.5.5).

**Action C: MLS Removal (async, via Enrollment Service):** The sidecar notifies the Enrollment Service, which issues MLS Remove commits for the user from all spaces they belong to. After these commits propagate, the user's device keys cannot decrypt new messages even if the private key is retained.

Logic App payload:

```json
{
  "event": "leaver",
  "upn": "alice@example.com",
  "aadObjectId": "aad-uuid",
  "reason": "termination",
  "effectiveAt": "2026-03-13T00:00:00Z",
  "revokeVCImmediately": true,
  "tombstoneGracePeriodSeconds": 0
}
```

For voluntary departures, `tombstoneGracePeriodSeconds` MAY be set to a positive value (e.g., 86400 for a 24-hour grace period) to allow orderly knowledge transfer. For involuntary terminations, it MUST be 0.

### 5.5 Lost Device Workflow

This workflow is triggered on-demand by IT via the Entra admin portal, the sidecar admin UI, or an MDM system such as Intune via Graph API. It does not use Lifecycle Workflows; it calls the DID Sidecar directly via an admin API call authenticated with an Entra admin token:

```http
POST /v1/revoke-device-key
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "did": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
  "keyId": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#device-macbook-1",
  "reason": "lost-device",
  "revokedBy": "helpdesk@example.com"
}
```

The sidecar (spec §2.5.5):

1. Appends a log entry, signed with its update key, that removes the `verificationMethod` entry and its references in `authentication` and `keyAgreement`
2. Logs the revocation with timestamp, reason, and revoking admin identity
3. Gossips a `DeviceRevocation` signed by its own key
4. Notifies the Enrollment Service, which issues MLS Remove commits for that device's leaf in all groups (an `Update` commit cannot remove another device's leaf; spec §2.2)

Other device keys (the user's phone, recovery key) are unaffected. The user retains access via remaining enrolled devices and can re-enroll the lost device after obtaining a replacement.

If the revoked key was the user's only device key, the document returns to `STUB` state and the user must re-enroll. The user's DID is preserved: space membership is retained, but the user cannot send or receive messages until re-enrollment completes.

### 5.6 MFA Step-Up for Device Key Registration

Device key registration (the moment a new device public key is written to the DID log) is the highest-stakes operation in the system: a successful registration grants a new device full access to all the user's spaces. Step-up MFA is REQUIRED regardless of the user's current session MFA state.

The DID Sidecar enforces this by requiring a step-up token: a short-lived Entra ID token with the `acr` claim set to `"mfa"` and the `amr` array including a phishing-resistant method (`"hwk"` for Windows Hello, `"fido"` for FIDO2/WebAuthn).

```http
POST /v1/register-device-key
Authorization: Bearer <step-up-token>
Content-Type: application/json

{
  "did": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
  "devicePublicKey": "zDEVICE_KEY...",
  "deviceLabel": "Alice's MacBook Pro",
  "registeredVia": "webauthn",
  "proofOfPossession": "...",
  "sig": { ... }
}
```

`sig` is the envelope signature of spec §13.1.1 by a currently registered device key. It is absent for the first device and REQUIRED for every later device (spec §2.5.4 Step 3).

The sidecar MUST validate all of the following before writing the key:

1. Token `acr` is `"mfa"`
2. Token `amr` includes `"hwk"` or `"fido"` (password-only MFA is not sufficient)
3. Token `oid` maps, in the sidecar's private store, to the `did` in the request body
4. First device: the DID is in `STUB` state and `sig` is absent. Later devices: `sig` verifies against a device key in the current verified log
5. `proofOfPossession` is a valid Ed25519 signature by `devicePublicKey` over the canonical proof payload
6. The remaining checks of spec §2.5.4 Step 4 (account active, device limit)

No VC is required for the first device (§4.2). If org policy requires a VC for later devices, the request also carries a `vcPresentation`, validated as in §4.3.

On success the sidecar appends a log entry adding the key, signed with its update key, gossips the update announcement signed by its own key (spec §2.5.4 Step 6, §2.5.7), and, for the first device, starts VC issuance (§4.2).

---

## 6. DID Sidecar Service

### 6.1 Endpoints

```
# Public (no auth)
GET    /users/{localIdentifier}/did.jsonl  Serve DID log
GET    /users/{localIdentifier}/did.json   Parallel did:web document (optional, §2)

# KeyPackageEndpoint (spec §5.2.1.1)
POST   /v1/keypackages/{localIdentifier}          Device uploads KeyPackages (signed by a device key in the log)
GET    /v1/keypackages/{localIdentifier}          Committer fetches one KeyPackage (consumed atomically, rate-limited)
POST   /v1/keypackages/{localIdentifier}/welcome  Committer delivers an MLS Welcome

# Enrollment (Entra OIDC token, step-up MFA required)
POST   /v1/register-device-key           Register a new device key
DELETE /v1/device-key/{keyId}            Self-service device key removal

# Admin (Entra admin token, Authentication Policy Administrator role)
POST   /v1/provision                     JML event receiver (from Logic App)
POST   /v1/revoke-device-key             IT-initiated device key removal
POST   /v1/tombstone                     IT-initiated DID deactivation
POST   /v1/suspend                       Suspend DID (leave of absence)
POST   /v1/reactivate                    Reactivate suspended DID
GET    /v1/audit/{localIdentifier}       Full audit log for a user's DID
GET    /v1/status/{localIdentifier}      Current DID state

# Enrollment Service webhook (internal, mTLS)
POST   /v1/internal/enrollment-complete  Called by Enrollment Service post-MLS-Add
POST   /v1/internal/mls-remove-ack       Acknowledgment of MLS Remove commit
```

The KeyPackage and Welcome endpoints are the only ones other Agora clients call. Relays never call the sidecar and hold no KeyPackages.

### 6.2 Authentication

| Endpoint group              | Auth mechanism                    | Required claims                                                     |
| --------------------------- | --------------------------------- | ------------------------------------------------------------------- |
| Public DID logs             | None                              | None                                                                |
| KeyPackage upload           | Signature by a device key in the user's verified log | None                                             |
| KeyPackage fetch, Welcome   | None (rate-limited)               | None                                                                |
| Device key registration     | Entra OIDC bearer token           | `acr: mfa`, `amr: [hwk\|fido]`, `oid` maps to the DID              |
| Admin operations            | Entra bearer token                | `Authentication Policy Administrator` role or `AgoraDIDAdmin` app role |
| Logic App bridge            | Entra managed identity token      | `AgoraDIDProvisioner` app role                                      |
| Enrollment Service webhook  | mTLS with pre-shared cert         | None                                                                |

### 6.3 Storage

The sidecar stores DID logs, KeyPackages and audit logs. Two deployment options are supported:

**Azure Blob Storage (preferred for Azure deployments):**
One append-only blob per user at `did-documents/{localIdentifier}/did.jsonl`. Audit log at `did-documents/{localIdentifier}/audit.jsonl`. A private `principals.json` maps each `localIdentifier` to the Entra `objectId` and current UPN.

**PostgreSQL:**
Table `did_principals(local_id TEXT PK, aad_object_id TEXT UNIQUE, upn TEXT, state TEXT)`. Table `did_log(local_id TEXT, seq INT, entry JSONB, PRIMARY KEY (local_id, seq))`, append-only. Table `did_audit(id BIGSERIAL, local_id TEXT, event TEXT, actor TEXT, payload JSONB, ts TIMESTAMPTZ)`. The `aad_object_id` and `upn` columns are the private mapping (spec §2.5.2) and are never served.

The update key is held in Azure Key Vault (HSM-backed) and used only to sign log entries. The sidecar's data store is the authoritative source; logs are served directly from it with no caching layer, because serving a stale log could present a deactivated identity as active. All DID log endpoints MUST return `Cache-Control: no-store, no-cache`.

### 6.4 UPN Change and Domain Migration

A UPN change does not change the DID (§2). The sidecar updates the UPN in its private mapping (§6.3); if a credential claim such as `displayName` changed, the Mover workflow (§5.3) re-issues the `EmployeeCredential`. No DID log entry is needed. The user updates their own display profile (spec §2.3), which the org does not sign.

The DID string changes only when the organization moves the DID host (e.g. `did.example.com` to `did.example.net`). This is an org-side migration, not a recovery: the org MUST NOT sign a `RecoveryAssertion` for it (spec §2.4.1, §2.4.2). `did:webvh` portability (spec §2.1, §2.5.2) keeps the identity intact:

1. **The sidecar moves its own identity first.** The sidecar's DID is itself a portable `did:webvh` (§6.5). It appends an entry to its own log that changes its DID to the new domain with the same SCID and lists the old DID in `alsoKnownAs`, signed with its current update key.
2. **The sidecar moves each user's log.** For each user it appends an entry, signed with the user log's update key, that changes the DID to `did:webvh:<same SCID>:did.example.net:users:<same localIdentifier>` and adds the old DID to `alsoKnownAs`. Keys, service entries and history carry over; the `KeyPackageEndpoint` URL is updated to the new host in the same entry.
3. **It publishes and announces.** The new host serves the continued log; the sidecar gossips the update announcements on `v1/agora/discovery` and records the migration in the audit log.
4. **The old host keeps answering.** The old URL keeps serving the log, or an HTTP redirect to the new location, for at least the regulatory retention period (spec §2.5.6), so archived references still resolve.

Clients MUST treat the old and new DIDs as one identity when they share the SCID and form one continuous verified log (spec §2.5.2). This replaces the earlier cross-signature check between two hosts: continuity is a property of the log. The migration entry verifies only if it is signed by an update key authorized in the preceding entry, so no one but the holder of that key can move an identity, and the same check applied to the sidecar's own log shows that the post-migration sidecar is the same provisioning service. Device keys do not need to be re-registered, and Space state entries naming the old DID remain valid; the CO MAY update them to the new form at its next routine Space state update.

### 6.5 Sidecar DID

The sidecar is a DID-bearing principal (spec §2.5.7). This profile gives it a portable `did:webvh`, e.g. `did:webvh:QmSCIDp...:did.example.com:agora:provisioning`, so that its identity survives a domain change through its own log (§6.4). Its document lists the signing key that signs gossiped update announcements and `DeviceRevocation` messages per spec §13.1.1. The update keys of the user logs are separate keys, also listed in each user log's `parameters`, and are not listed as verification methods in any user document (§3.2).

---

## 7. Entra App Registration

The DID Sidecar requires one Entra app registration configured as follows.

**Expose an API:**

```
Application ID URI: api://did.example.com
Scope: AgoraDIDAdmin        (for IT admin operations)
Scope: AgoraDIDProvisioner  (for Logic App managed identity)
```

**App roles:**

```
AgoraDIDAdmin        : assigned to helpdesk/IT security groups
AgoraDIDProvisioner  : assigned to Logic App managed identity
```

**API permissions (outbound calls from the sidecar):**

```
Microsoft Graph:
  User.Read.All              (read user attributes for provisioning)
  AuditLog.Read.All          (read sign-in logs for device registration audit)

Verified ID Service Admin:
  VerifiableCredential.Authority.ReadWrite   (issue/revoke EmployeeCredential)
  VerifiableCredential.Credential.Revoke     (revoke individual credentials)
```

All permissions are application permissions (not delegated); the sidecar runs as a service with no user context.

---

## 8. License Requirements

| Feature                                              | Required License                                          |
| ---------------------------------------------------- | --------------------------------------------------------- |
| Lifecycle Workflows (JML automation)                 | Microsoft Entra ID Governance (P2+)                       |
| Entra Verified ID                                    | Microsoft Entra ID (all tiers for basic issuance)         |
| Conditional Access (MFA step-up enforcement)         | Microsoft Entra ID P1                                     |
| Custom task extensions (Logic App bridge)            | Microsoft Entra ID Governance                             |
| Verified ID Face Check (high-assurance re-enrollment) | Verified ID premium add-on                               |

The minimum viable deployment requires **Entra ID P1** (MFA step-up) and **Entra ID Governance** (Lifecycle Workflows). P2 adds risk-based Conditional Access, which can strengthen the step-up policy for device key registration.

---

## 9. Implementation Notes

### 9.1 Language and Stack

The DID Sidecar is a Go service deployed as an Azure Container App or Azure App Service.

| Function              | Library                                                              |
| --------------------- | -------------------------------------------------------------------- |
| HTTP server           | `net/http` (stdlib)                                                  |
| Entra token validation | `github.com/AzureAD/microsoft-authentication-library-for-go`       |
| Azure Blob client     | `github.com/Azure/azure-sdk-for-go/sdk/storage/azblob`              |
| Azure Key Vault (update key) | `github.com/Azure/azure-sdk-for-go/sdk/security/keyvault/azkeys` |
| Verified ID API       | HTTP client against `verifiedid.did.msidentity.com`                  |
| Ed25519               | `crypto/ed25519` (stdlib)                                            |
| `did:webvh` log       | Internal implementation of DIF did:webvh v1.0 (`eddsa-jcs-2022` proofs over JCS, RFC 8785), or an implementation listed by that specification |

### 9.2 Logic App

The JML Logic App is a Consumption-tier Logic App with:

- HTTP trigger (receives events from the Lifecycle Workflows custom task extension)
- Managed identity authentication for calls to the DID Sidecar
- "Launch and wait" response sent back to Lifecycle Workflows on Joiner events
- "Launch and continue" on Leaver events (no response required)

The Logic App contains no business logic; it is a thin authenticated bridge. All logic resides in the sidecar.

---

## 10. Open Questions

1. **Verified ID VC auto-accept in Authenticator.** Authenticator supports auto-accept of VCs from trusted issuers, but requires the user to have the trust relationship configured. For corporate deployments, this SHOULD be pushed via Intune MDM policy. The enrollment issuance UX depends on this being configured; without it, the user receives a notification requiring a manual tap. This specification assumes MDM-managed Authenticator; unmanaged devices require a documented fallback.

2. **StatusList2021 revocation scalability.** The Verified ID service uses StatusList2021 for VC revocation status. Each status list holds up to 131,072 entries and is served as a public URL, which is adequate for large organizations. For organizations with privacy concerns about public enumerability of revocation state (an external party can observe which entries are revoked over time), the Bitstring Status List specification (the StatusList2021 successor) adds encrypted status entries and is worth monitoring.

3. **Non-Authenticator wallets.** This specification assumes Microsoft Authenticator as the VC wallet. The Verified ID service supports OID4VC-compliant third-party wallets in principle, but compatibility varies. Organizations that want employees to use a different wallet (e.g., a corporate-branded wallet) MUST validate compatibility against the specific Verified ID API version in use.

4. **On-premises AD hybrid identity.** Organizations with on-premises AD synced to Entra via Entra Connect have UPNs controlled by on-premises AD. UPN changes on-premises propagate to Entra via sync, which can trigger the Mover workflow; they do not change the DID (§2). The default sync interval (30 minutes) introduces lag between an on-premises change and the sidecar update. For terminations, this lag is a risk: the specification calls for immediate on-demand workflow execution to bypass the sync cycle, but this requires the termination to be processed in Entra ID directly, or for the HR system to trigger both on-premises AD and Entra simultaneously.

5. **Intune integration for device key registration.** Device key registration requires phishing-resistant MFA (`hwk` or `fido`). On Intune-managed devices, Windows Hello for Business satisfies this requirement automatically. On unmanaged or BYOD devices, a FIDO2 security key is the only option. The organization MUST decide whether to allow BYOD enrollment or require managed devices; this policy decision significantly affects the enrollment UX.
