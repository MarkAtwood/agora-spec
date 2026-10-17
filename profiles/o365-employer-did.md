# Specification: Employer-Managed DIDs via Microsoft Entra ID

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Version:** 0.1 Draft
**Depends On:** the Agora protocol specification (`spec/`, current draft)
**Status:** Pre-implementation design

---

## 1. Architecture Overview

This specification defines how an organization using Microsoft 365 / Entra ID manages Agora `did:webvh` identities for its employees (provisioning them automatically at hire, updating claims on role changes, and revoking them at termination) without the organization ever holding or touching employee private keys. `did:webvh` is the method spec §2.1 makes the default and spec §2.5 uses for employer-provisioned identities.

Two components perform this work.

**The DID Sidecar** is the organization's DID Provisioning Service (spec §2.5.2), a CO component, here a lightweight HTTPS service registered as an Entra application. It owns the namespace `https://did.example.com/users/{localIdentifier}/` and serves each user's `did:webvh` log (`did.jsonl`). It holds the update key for every employee log, receives provisioning events from Graph Lifecycle Workflows via a Logic App bridge, accepts authenticated device key registration requests from employees during Agora enrollment, and hosts each employee's `KeyPackageEndpoint` (spec §5.2.1.1). It is the only component that writes DID log entries, and every entry it writes carries a proof from at least one witness the organization does not control (spec §2.1, §6.6 below). As each employee's identity host, it also issues the admission keys of the DM groups its employees start and of each employee's self-group (spec §4.6, §6.7 below).

**Entra Verified ID** issues a signed `EmployeeCredential` verifiable credential to each enrolled employee's wallet (Microsoft Authenticator). The VC is the organization's cryptographic attestation that the holder is a current employee with specific claims (department, role, clearance level). It is issued after the first device key is registered (§4.2), and Spaces MAY require it for admission (§4.3). VC revocation blocks future Space admissions (§4.3) without writing a DID log entry. It does not cut off access the employee already has: membership in the MLS group is the only access control, so access ends when the Enrollment Service issues the MLS Remove commits (§5.4, Action C).

Relays play no part in this profile. They never receive or verify Entra tokens; IdP authentication runs between the client, Entra and the sidecar (spec §2.5.2).

These two components are intentionally independent and address different concerns:

| Concern                                               | Component                                                        |
| ----------------------------------------------------- | ---------------------------------------------------------------- |
| Org controls identity namespace and can revoke        | DID Sidecar (deactivates the DID log)                            |
| Org attests employee status with auditable trail      | Entra Verified ID (EmployeeCredential)                           |
| Employee controls private key                         | DID Sidecar (device key generated and registered by client, never by org) |
| Org key insertion is auditable                        | DID log (every update-key entry is visible to all resolvers)     |
| Block future Space admissions without DID deactivation | Entra Verified ID (VC revocation)                               |
| Access cut-off in existing Spaces                     | Enrollment Service (MLS Remove commits)                          |
| Specific device revocation (lost device)              | DID Sidecar (log entry removing one `verificationMethod`)        |
| KeyPackage hosting and Welcome delivery               | DID Sidecar (`KeyPackageEndpoint`)                               |
| Admission keys for DM groups and self-groups          | DID Sidecar (identity host, spec §4.6)                           |

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
│  POST /v1/devices                 Device key registration           │
│  POST /v1/revoke-device-key       Device key removal (IT/MDM)       │
│  POST /v1/tombstone               DID deactivation                  │
│  *    /v1/agora/kp/{id}           KeyPackageEndpoint                │
│  *    /v1/agora/admission-key/{groupID} DM and self-group keys      │
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

Each user's DID log moves through the following states. Every transition is a new log entry signed with the sidecar's update key and co-signed by witnesses (§6.6).

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

The stub document contains no organization key: an org key listed as a `verificationMethod` in a user's document would let the org sign as that user. The org's authority over the document is the update key in the log `parameters` (§3.2). A client that tries to add this DID to a group finds no KeyPackage at its `KeyPackageEndpoint` (spec §5.2.1.1 returns HTTP 404) and no `authentication` key, so it cannot complete the Add; it should queue the Add (spec §5.2.1.1, KeyPackage Exhaustion) and tell the user the person has not enrolled yet.

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
    "portable": true,
    "witness": {
      "threshold": 1,
      "witnesses": [{ "id": "did:key:z6MkWITNESS..." }]
    }
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
        "type": "AgoraKeyPackageEndpoint",
        "serviceEndpoint": "https://did.example.com/v1/agora/kp/k7f3qd2m"
      },
      {
        "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m#provisioning",
        "type": "AgoraProvisioning",
        "serviceEndpoint": "https://did.example.com/v1"
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

`portable: true` MUST be set in the genesis entry, because `did:webvh` allows portability only when enabled at creation; it is what lets the identity survive a domain change (§6.4, spec §2.5.2). The `KeyPackageEndpoint` and `AgoraProvisioning` entries are present before the first device enrolls, as spec §2.5.3 requires; the `AgoraProvisioning` value is the base URL `{prov}` under which the sidecar serves `POST {prov}/devices` and `POST {prov}/revocations` (spec §2.5.4, §2.5.5). The `witness` parameter is required for a CO-provisioned DID (spec §2.1, §6.6 below). The document names no relay or other IO.

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
        "registeredVia": "entra-step-up"
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
        "registeredVia": "entra-step-up"
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
      "type": "AgoraKeyPackageEndpoint",
      "serviceEndpoint": "https://did.example.com/v1/agora/kp/k7f3qd2m"
    },
    {
      "id": "...#provisioning",
      "type": "AgoraProvisioning",
      "serviceEndpoint": "https://did.example.com/v1"
    },
    {
      "id": "...#profile",
      "type": "AgoraProfile",
      "serviceEndpoint": "ipfs://bafkrei..."
    }
  ]
}
```

The `meta` fields on device keys are non-standard extensions for operator tooling; they allow IT to identify which key belongs to which device when issuing targeted revocations. They are informational only and carry no cryptographic weight. A client that does not recognize them should ignore them, as DID Core requires consumers to do for unrecognized properties.

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
4. **KeyPackage upload.** The client uploads its initial KeyPackages to the sidecar's `KeyPackageEndpoint` (spec §2.5.4 Step 6).
5. **Space admission.** The Enrollment Service checks the VC if the Space requires it (§4.3) and then issues the MLS Add commit.

Later devices register with a request signed by an existing device key (§5.6); the org MAY additionally require a VC presentation for them, since by then the employee holds one. A later device needs no new Space admission: once its key is in the log, one of the employee's existing devices adds it to the employee's self-group and to every group the employee belongs to by an own-device Add (spec §2.5.4 Step 7, §2.6).

The sidecar calls the Verified ID Request Service issuance API. Verify the path and request schema against current Microsoft documentation (written 2026-10, not re-verified):

```http
POST https://verifiedid.did.msidentity.com/v1.0/verifiableCredentials/createIssuanceRequest
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

### 4.4 Carrying the EmployeeCredential in Groups (Non-Normative)

The employee's client can also carry the `EmployeeCredential`, or a presentation of it, in the `agora_credentials` leaf extension (spec §5.2.1.5), with the media type of its encoding: `application/vc+jwt` for a VC secured per W3C VC-JOSE-COSE, or `application/jwt` for a VC Data Model 1.1 JWT such as the one above. Its subject (`credentialSubject.id`, or the JWT `sub`) is the employee's DID, so it satisfies the spec's subject check. Other members' clients can then verify it from the leaf: a colleague's client whose policy trusts `did:web:verifiedid.example.com` can treat the employee as an accepted DM sender (spec §4.6.3, §9.3 here), and a Space admin's client can assign roles from its claims (spec §4.2). By default the client leaves it out of published KeyPackages and adds it to each group by updating its own leaf after joining. Every member of the group, including members outside the organization, sees the claims it carries, so the organization should decide which claims, such as `employeeId`, `department` or `officeLocation`, employees carry into groups shared with outsiders.

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
  "spaceURI": "agora://bafkrei.../"
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

**Action A: VC Revocation (immediate):** The sidecar calls the Verified ID revocation API for the user's current `EmployeeCredential`. Revocation takes effect within seconds and stops the user from being admitted to any Space that requires the VC (§4.3). It does not remove the user from Spaces they already belong to; Action C does that.

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

The log stays resolvable with this entry as its last (spec §2.5.6). Members of groups outside the organization's control Remove the user's leaves when they next resolve the DID and find no `authentication` keys (spec §2.5.5, §2.5.6, §2.7). The reason and initiator are recorded in the sidecar's audit log, not in the public document. Nothing is gossiped: DID document changes are distributed only by the log (spec §2.5.7, §2.7).

**Action C: MLS Removal (the access cut-off, via Enrollment Service):** The sidecar notifies the Enrollment Service, which issues MLS Remove commits for the user from all spaces they belong to. After these commits propagate, the user's device keys cannot decrypt new messages even if the private key is retained.

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
3. Sends no announcement: the user's remaining devices send an `IdentityChanged` notice (spec §2.7) to the user's groups when they see the new log entry, and other members learn of the revocation when they resolve the DID (spec §2.5.5)
4. Notifies the Enrollment Service, which issues MLS Remove commits for that device's leaf in all groups (an `Update` commit cannot remove another device's leaf; spec §2.2)

Other device keys (the user's phone, recovery key) are unaffected. The user retains access via remaining enrolled devices and can re-enroll the lost device after obtaining a replacement.

If the revoked key was the user's only device key, the document returns to `STUB` state and the user must re-enroll. The user's DID is preserved: the user's leaves were removed from every group, so after re-enrollment the user must be re-added to each group.

### 5.6 MFA Step-Up for Device Key Registration

Device key registration (the moment a new device public key is written to the DID log) is the highest-stakes operation in the system: a successful registration grants a new device full access to all the user's spaces. Step-up MFA is REQUIRED regardless of the user's current session MFA state.

The DID Sidecar enforces this with a Conditional Access authentication context. The organization defines an authentication context (for example `c1`, labelled "Agora device registration") and a Conditional Access policy that requires the phishing-resistant MFA authentication strength (Windows Hello for Business, FIDO2 security key, or certificate-based authentication) for that context. The sidecar requires a short-lived Entra access token whose `acrs` claim contains that context ID. If the token lacks it, the sidecar returns a claims challenge naming the context, and the client re-authenticates. Clients signal that they can handle claims challenges with the `xms_cc` client capability. The sidecar does not rely on `acr` (in Entra access tokens it is only `0` or `1`, and only in v1.0 tokens) or on specific `amr` values, since Entra's documented `amr` values do not distinguish phishing-resistant methods. Verify the claim names and the claims-challenge flow against current Entra documentation (checked 2026-10).

```http
POST /v1/devices
Content-Type: application/cbor

<encoded typed payload envelope (spec §13.1)>
```

This is `POST {prov}/devices` of spec §2.5.4 Step 3, with `{prov}` the `AgoraProvisioning` base URL (§3.2). The envelope has `type` `urn:agora:type:DeviceKeyRegistrationRequest`, `contentType` `application/json`, and a `body` that is the spec §2.5.4 Step 3 request, with the step-up access token as `idpToken`:

```json
{
  "@type": "DeviceKeyRegistrationRequest",
  "did": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
  "deviceLabel": "Alice's MacBook Pro",
  "deviceEd25519PublicKey": "base64url(Ed25519 pubkey)",
  "deviceX25519PublicKey": "base64url(X25519 pubkey)",
  "platform": "macOS",
  "secureEnclaveAttested": true,
  "ts": "2026-03-12T12:00:00.000Z",
  "idpToken": "<step-up access token>"
}
```

The step-up access token travels in `idpToken`, so the device-key signature covers it (spec §2.5.4 Step 3).

The envelope `sig` (spec §13.1.1) carries the signatures. For the first device it holds one entry, by the new `deviceEd25519PublicKey`, as proof of possession. This is a device-key signature, not a WebAuthn assertion: a passkey or FIDO2 key that the user presents to Entra during step-up never becomes a device key (spec §2.2). For every later device it also holds an entry by a currently registered device key (spec §2.5.4 Step 3).

The sidecar MUST validate all of the following before writing the key:

1. `idpToken` is a valid Entra access token for the sidecar's audience
2. Token `acrs` contains the configured authentication context ID (password-only MFA cannot satisfy the policy behind it)
3. Token `oid` maps, in the sidecar's private store, to the `did` in the request body
4. First device: the DID is in `STUB` state and `sig` has no entry from a registered key. Later devices: `sig` has an entry that verifies against a device key in the current verified log
5. `sig` has an entry that verifies against `deviceEd25519PublicKey` over the exact `body` bytes
6. The remaining checks of spec §2.5.4 Step 4 (account active, device limit, and rejecting a key already present in any DID the service serves)

No VC is required for the first device (§4.2). If org policy requires a VC for later devices, the request also carries a `vcPresentation`, validated as in §4.3.

On success the sidecar appends a log entry adding the key, signed with its update key and co-signed by witnesses (§6.6), and, for the first device, starts VC issuance (§4.2). Nothing is gossiped (spec §2.5.7). The new device then uploads its KeyPackages (spec §2.5.4 Step 6), and for a later device the employee's existing devices add it to the self-group and every group the employee belongs to (spec §2.5.4 Step 7, §2.6).

---

## 6. DID Sidecar Service

### 6.1 Endpoints

```
# Public (no auth)
GET    /users/{localIdentifier}/did.jsonl  Serve DID log
GET    /users/{localIdentifier}/did.json   Parallel did:web document (optional, §2)

# KeyPackageEndpoint (spec §5.2.1.1)
POST   /v1/agora/kp/{localIdentifier}          Device publishes KeyPackages (signed by a device key in the log)
GET    /v1/agora/kp/{localIdentifier}          Committer fetches one KeyPackage per device (consumed atomically, rate-limited)
GET    /v1/agora/kp/{localIdentifier}?leaf=    Existing device fetches a KeyPackage of one new device (spec §2.6)
POST   /v1/agora/kp/{localIdentifier}/welcome  Committer delivers an MLS Welcome
POST   /v1/agora/kp/{localIdentifier}/auth     Caller authentication, if fetches are gated by sender (spec §3.5, §4.6.3)

# Admission keys for DM groups and self-groups (spec §4.6, §6.7 below)
POST   /v1/agora/admission-key/{groupID}                       Issue a new ChannelAdmissionKey to the calling employee (spec §3.5)
POST   /v1/agora/admission-key/{groupID}/{keyEpoch}/committed  Confirm that the key's Commit won (its issuee only)
DELETE /v1/agora/admission-key/{groupID}/{keyEpoch}            Deregister that key (its issuee only)
POST   /auth                                                   Member authentication (spec §3.5)

# Device registration and user revocation ({prov} = /v1, spec §2.5.4, §2.5.5)
POST   /v1/devices                       Register a new device key (Entra step-up token)
POST   /v1/revocations                   Self-service device key removal (signed by a surviving device key)

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

The KeyPackage and Welcome endpoints are the only ones other users' Agora clients call; only the organization's own employees call the admission-key endpoints. Relays never call the sidecar and hold no KeyPackages; the sidecar calls relays only to register admission keys (§6.7).

### 6.2 Authentication

| Endpoint group              | Auth mechanism                    | Required claims                                                     |
| --------------------------- | --------------------------------- | ------------------------------------------------------------------- |
| Public DID logs             | None                              | None                                                                |
| KeyPackage upload           | Signature by a device key in the user's verified log | None                                             |
| KeyPackage fetch, Welcome   | None (rate-limited); a §3.5 bearer token if the org gates by sender (spec §4.6.3) | None                                |
| Admission-key endpoints     | Spec §3.5 bearer token            | Caller's DID is one the sidecar serves; for DELETE and confirmation, the key's issuee (spec §4.6) |
| Device key registration     | Entra access token                | `acrs` contains the authentication context ID, `oid` maps to the DID |
| User device revocation      | Spec §13.1.1 signature by a surviving device key of the DID | None                                     |
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
3. **It publishes.** The new host serves the continued log, with its witness proofs (§6.6), and the sidecar records the migration in the audit log. Nothing is gossiped: each employee's devices send an `IdentityChanged` notice (spec §2.7) when they see the migration entry, and other members pick up the move when they next resolve the DID.
4. **The old host keeps answering.** The old URL keeps serving the log, or an HTTP redirect to the new location, for at least the regulatory retention period (spec §2.5.6), so archived references still resolve.

Clients MUST treat the old and new DIDs as one identity when they share the SCID and form one continuous verified log (spec §2.5.2). This replaces the earlier cross-signature check between two hosts: continuity is a property of the log. The migration entry verifies only if it is signed by an update key authorized in the preceding entry, so no one but the holder of that key can move an identity, and the same check applied to the sidecar's own log shows that the post-migration sidecar is the same provisioning service. Device keys do not need to be re-registered, and Space state entries naming the old DID remain valid; the CO MAY update them to the new form at its next routine Space state update.

### 6.5 Sidecar DID

The sidecar is a DID-bearing principal (spec §2.5.7). This profile gives it a portable `did:webvh`, e.g. `did:webvh:QmSCIDp...:did.example.com:agora:provisioning`, so that its identity survives a domain change through its own log (§6.4). As spec §2.5.7 requires, the update key of the user logs is a verification method of this DID; it is also listed in each user log's `updateKeys` parameter and is never a verification method in any user document (§3.2). Its own log uses witnesses like the user logs (§6.6).

### 6.6 Witnesses

Spec §2.1 requires every CO-provisioned `did:webvh` DID to use did:webvh witnesses. The sidecar therefore publishes witness-co-signed log updates: each user log, and the sidecar's own log, declares in its `witness` parameter at least one witness DID that the organization does not control, with a threshold such that every entry carries a proof from at least one such witness. The sidecar obtains the witness proofs for an entry before it serves that entry, and serves them beside `did.jsonl` as the did:webvh specification defines. Agora clients verify those proofs and reject an entry that lacks the proofs its parameters require (spec §2.1).

The organization chooses its witnesses. What matters is that the organization does not control them: a witness run by the organization itself adds nothing, because the purpose is to stop the holder of the update key from showing different logs to different resolvers, or an old log to one of them, without a second party noticing (spec §2.1, §2.5.1). If the witnesses are unreachable, the sidecar cannot publish new entries; device registrations, revocations and deactivations wait until a proof is obtained, so the organization should name more than one witness and set the threshold below their number.

### 6.7 Admission Keys for DM Groups and Self-Groups

The sidecar hosts each employee's `KeyPackageEndpoint`, so it is the employee's identity host in the sense of spec §4.6 and plays the CO's part for admission of every DM group an employee initiates or moves to it (spec §4.6.4) and of each employee's self-group (spec §2.6). For each such group it generates the admission key, registers it by `AdmissionKeyRegistration` with every relay that holds a `relay` `ServiceAgreement` with the organization (spec §10.5.3), and deregisters a key when its issuee asks, 7 days after the issuee of a later key for the same group confirms that key, or 30 days after that employee is offboarded (spec §4.6, §10.5.3). Rotation and handover are client actions: an employee's client POSTs for a new key and commits it to the group's `agora_admission` GroupContext extension (spec §4.6, §4.6.4). Registrations are signed by the organization's billing DID (spec §10.5.1), so the sidecar needs a signing path to that key, for example through the CO's registration service; it never signs them with its own DID. Its `<host>`, which the employee's client puts in the group's `agora_admission` extension (spec §4.6), is `https://did.example.com`, the origin of the employees' `KeyPackageEndpoint`s; it serves the §6.1 admission-key endpoints under `/v1/agora/admission-key/` and the spec §3.5 exchange at `POST /auth`. It issues keys only to its own employees after the spec §3.5 exchange and keeps no member list; it learns that an employee asked for keys for a group ID, and when, but not the group's other members (spec §4.6). Relays learn neither the group nor the members, only that the token is covered by the organization's agreement, so a DM's anonymity at a relay is as large as the organization's set of users (ARCHITECTURE §9).

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

Verifiable Credentials Service Request:
  VerifiableCredential.Create.All            (call the Request Service to issue EmployeeCredential)

Verified ID Service Admin:
  VerifiableCredential.Authority.ReadWrite   (manage the authority and contracts)
  VerifiableCredential.Credential.Revoke     (revoke individual credentials)
```

Verify the permission names against current Microsoft documentation (written 2026-10, not re-verified).

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

### 9.3 DM Message Requests for Colleagues

The organization's managed client configuration (MDM or enrollment policy) can add a rule to the user's accepted senders (spec §4.6.3), for example every DID under the organization's `did:webvh` domain, or every member of the organization's Spaces. DMs from matching senders then skip the message request state. Whether users may decline or block colleagues is also client configuration. Attributes that must be trusted across organizations need a credential format and are out of scope here.

---

## 10. Open Questions

1. **Verified ID VC auto-accept in Authenticator.** Authenticator supports auto-accept of VCs from trusted issuers, but requires the user to have the trust relationship configured. For corporate deployments, this SHOULD be pushed via Intune MDM policy. The enrollment issuance UX depends on this being configured; without it, the user receives a notification requiring a manual tap. This specification assumes MDM-managed Authenticator; unmanaged devices require a documented fallback.

2. **StatusList2021 revocation scalability.** The Verified ID service uses StatusList2021 for VC revocation status. Each status list holds up to 131,072 entries and is served as a public URL, which is adequate for large organizations. For organizations with privacy concerns about public enumerability of revocation state (an external party can observe which entries are revoked over time), the Bitstring Status List specification (the StatusList2021 successor) does not address this: it defines no encrypted entries. Mitigations are large lists with random index assignment, or a status list served only to authorized verifiers.

3. **Non-Authenticator wallets.** This specification assumes Microsoft Authenticator as the VC wallet. The Verified ID service supports OID4VC-compliant third-party wallets in principle, but compatibility varies. Organizations that want employees to use a different wallet (e.g., a corporate-branded wallet) MUST validate compatibility against the specific Verified ID API version in use.

4. **On-premises AD hybrid identity.** Organizations with on-premises AD synced to Entra via Entra Connect have UPNs controlled by on-premises AD. UPN changes on-premises propagate to Entra via sync, which can trigger the Mover workflow; they do not change the DID (§2). The default sync interval (30 minutes) introduces lag between an on-premises change and the sidecar update. For terminations, this lag is a risk: the specification calls for immediate on-demand workflow execution to bypass the sync cycle, but this requires the termination to be processed in Entra ID directly, or for the HR system to trigger both on-premises AD and Entra simultaneously.

5. **Intune integration for device key registration.** Device key registration requires phishing-resistant MFA (the authentication strength behind the §5.6 authentication context). On Intune-managed devices, Windows Hello for Business satisfies this requirement automatically. On unmanaged or BYOD devices, a FIDO2 security key is the only option. The organization MUST decide whether to allow BYOD enrollment or require managed devices; this policy decision significantly affects the enrollment UX.
