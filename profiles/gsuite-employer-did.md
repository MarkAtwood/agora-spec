# Specification: Employer-Managed DIDs via Google Workspace

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Version:** 0.1 Draft
**Depends On:** the Agora protocol specification (`spec/`, current draft) and `profiles/o365-employer-did.md`
**Status:** Pre-implementation design

---

## 1. Architecture Overview

The Google Workspace architecture is structurally parallel to the O365 spec but collapses the two-component model (Verified ID + DID Sidecar) into one. Google has no native verifiable credential issuance platform and no declarative JML workflow engine. The DID Sidecar, the organization's DID Provisioning Service (spec §2.5.2) and a CO component, carries all three responsibilities that the O365 architecture distributes across three components:

| Concern | O365 Component | Google Workspace Component |
| ------- | -------------- | -------------------------- |
| DID document hosting | DID Sidecar | DID Sidecar |
| Org attestation / VC issuance | Entra Verified ID | DID Sidecar (self-issued VC) |
| JML lifecycle automation | Graph Lifecycle Workflows + Logic App | DID Sidecar (Directory API push + polling fallback) |

As in the O365 profile, employee identities are `did:webvh` (spec §2.1, §2.5): the sidecar holds the update key of each employee's DID log, and every change it makes is a log entry visible to all resolvers (O365 spec §3). Each entry is co-signed by at least one witness the organization does not control, which spec §2.1 requires for a CO-provisioned DID, and clients verify those proofs (O365 spec §6.6). The sidecar also hosts each employee's `KeyPackageEndpoint` (spec §5.2.1.1) and, as the employee's identity host, issues the admission keys of DM groups its employees start and of their self-groups (spec §4.6, O365 spec §6.7). Relays play no part in provisioning: they never receive or verify Google tokens (spec §2.5.2) and hold no KeyPackages (spec §5.2.1.1).

The VC layer uses the W3C VC Data Model with the org's own `did:web` as issuer (§3.2). JML automation uses the Directory API push notification channel plus a daily reconciliation polling loop as a reliability backstop, because the push channel expires and has delivery lag.

```
┌──────────────────────────────────────────────────────────────┐
│  Google Workspace Tenant                                     │
│                                                              │
│  ┌────────────────────┐   ┌────────────────────────────┐    │
│  │  Admin SDK         │   │  Google OAuth 2.0 / OIDC   │    │
│  │  Directory API     │   │  (employee authentication) │    │
│  │  (Users resource)  │   └──────────────┬─────────────┘    │
│  └─────────┬──────────┘                  │                   │
│            │ push notifications           │ id_token          │
└────────────┼─────────────────────────────┼───────────────────┘
             │                             │
             ▼                             ▼
┌──────────────────────────────────────────────────────────────┐
│  DID Sidecar  (operator-hosted, registered as GCP OAuth app) │
│                                                              │
│  GET  /users/{id}/did.jsonl             Serve DID log        │
│  *    /v1/agora/kp/{id}                 KeyPackageEndpoint   │
│  *    /v1/agora/admission-key/{groupID} DM admission keys    │
│  GET  /.well-known/did.json             Org root DID         │
│  GET  /.well-known/did-configuration.json  Domain linkage    │
│  POST /v1/notify                        Directory API push   │
│  POST /v1/devices                       Device key reg       │
│  POST /v1/revoke-device-key             IT key removal        │
│  POST /v1/tombstone                     DID deactivation      │
│  POST /v1/suspend                       Suspend DID           │
│  POST /v1/reactivate                    Reactivate DID        │
│  GET  /v1/credentials/:id/employee      Serve employee VC     │
│  GET  /v1/status/:id                    DID state            │
│  GET  /v1/audit/:id                     Audit log            │
│                                                              │
│  Background workers:                                         │
│  - Channel renewal (refreshes push subscription)            │
│  - Reconciliation poller (daily full Directory API scan)     │
│  - VC expiry reissuance (annual re-attestation)              │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Google Workspace API Access

### 2.1 OAuth Scopes

The DID Sidecar authenticates to Google using a service account with domain-wide delegation. The following scopes are required:

| Scope | Purpose |
| ----- | ------- |
| `https://www.googleapis.com/auth/admin.directory.user.readonly` | Read user records for provisioning |
| `https://www.googleapis.com/auth/admin.directory.user` | Watch Users resource for push notifications |
| `https://www.googleapis.com/auth/admin.directory.group.readonly` | Read group membership for role derivation |
| `https://www.googleapis.com/auth/admin.reports.audit.readonly` | Read Admin Audit log (login events, account changes) |

Domain-wide delegation MUST be granted in the Google Admin console (`Security → API controls → Domain-wide delegation`). The service account MUST be granted the `User Management Admin` role.

### 2.2 Push Notification Channel

The Directory API supports push notifications for changes to the Users resource via a webhook callback URL registered as a notification channel. The sidecar MUST register a channel on startup and renew it before expiry.

Channel registration request:

```http
POST https://admin.googleapis.com/admin/directory/v1/users/watch
Authorization: Bearer <service-account-token>
Content-Type: application/json

{
  "id": "agora-did-sidecar-channel-<uuid>",
  "type": "web_hook",
  "address": "https://did.example.com/v1/notify",
  "token": "<secret-token>",
  "expiration": <requested expiry, unix ms>
}
```

Push notification channels expire. Google sets the channel's expiration to the more restrictive of the requested value and its own internal limits, and returns the actual value in the watch response. The sidecar MUST run a background worker that renews the channel 24 hours before that returned `expiration` (or at half the channel lifetime, if the lifetime is shorter than 48 hours). If renewal fails, the sidecar MUST fall back to the reconciliation poller (§2.3) until the channel is re-established. Channel expiry MUST trigger a monitoring alert; IT SHOULD be notified if the sidecar has operated in polling-only mode for more than one hour.

The webhook endpoint MUST verify incoming requests by comparing the `X-Goog-Channel-Token` header against the registered `token` value. Requests with an invalid or missing token MUST be rejected with HTTP 403.

Directory API push notifications are minimal. The `X-Goog-Resource-State` header is `sync` for the initial channel message, or the event name (`add`, `delete`, `makeAdmin`, `undelete` or `update`). The notification does not carry the full user object. On receipt, the sidecar MUST fetch the full user record via `GET /admin/directory/v1/users/{userId}` before acting.

### 2.3 Reconciliation Poller

The reconciliation poller runs daily (configurable; default 02:00 local time) and performs a full directory scan:

```http
GET https://admin.googleapis.com/admin/directory/v1/users
    ?domain=example.com&maxResults=500&orderBy=email
```

The poller compares the full user list against the sidecar's DID document registry and reconciles discrepancies:

- A user present in the Directory but absent from the sidecar MUST be provisioned as a stub DID (Joiner missed by push).
- A user in the sidecar with `ACTIVE` or `STUB` state but suspended in the Directory MUST be transitioned to `SUSPENDED`.
- A user in the sidecar with `ACTIVE` or `STUB` state but deleted from the Directory MUST be deactivated immediately.
- A user in the sidecar with `SUSPENDED` state but active in the Directory MUST be reactivated.

The reconciliation poller is the reliability backstop, not the primary path. Worst-case latency from a leaver event to DID deactivation via the poller is 24 hours (push channel down, event missed, poller not yet run). For this reason §4.4 runs revocation and MLS removal immediately on any push notification, without waiting for the poller.

---

## 3. DID Document Structure

The DID log and document structure, the absence of an org `controller`, and the lifecycle states (`STUB`, `ACTIVE`, `SUSPENDED`, `DEACTIVATED`) are identical to the O365 spec (§3), including the `KeyPackageEndpoint` and `AgoraProvisioning` service entries and the `witness` parameter in the genesis entry, and the optional parallel `did:web` document (O365 spec §2). The two differences follow.

### 3.1 DID Naming

The naming rule is the same as O365 spec §2 and spec §2.5.2: the DID is `did:webvh:<SCID>:did.example.com:users:<localIdentifier>`, where the path segment is a stable `localIdentifier` that is never reassigned and MUST NOT be derived from the primary email, name or any other changeable attribute.

```
did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m
https://did.example.com/users/k7f3qd2m/did.jsonl
```

**Recommended default:** the sidecar mints a random lowercase base32 value at Joiner time (§4.2), checks it for uniqueness, and stores the mapping to the Google user `id` (the Directory API `id` field, which is also the OIDC `sub` claim) in its private DB. The mapping is never published.

**Allowed alternatives:** the Google user `id`, or an HR employee ID that is never reused. A sidecar-minted random value is preferred because it survives a move to a different IdP; the Google user `id` does not.

A `primaryEmail` change does not change the DID; it is an attribute update handled as a Mover event (§4.3). Only a move of the DID host changes the DID string, and the identity survives it through `did:webvh` portability with the same SCID, handled as in O365 spec §6.4.

### 3.2 Org Root DID

The org root DID is served at:

```
https://did.example.com/.well-known/did.json
```

This is the org's signing identity for EmployeeCredential issuance. It carries one key: the org's Ed25519 signing key, stored in Google Cloud KMS. It stays a `did:web` because general VC verifiers and the DID Configuration linkage below expect one. It is a separate principal from the sidecar's own provisioning DID (a portable `did:webvh`, O365 spec §6.5) and its key is separate from the update key of the employee logs (§7), so it confers no authority over any employee's DID log. After a domain change (O365 spec §6.4) the sidecar re-issues current credentials under the new issuer DID.

A Well-Known DID Configuration document, following the DIF Well Known DID Configuration specification, links the org's DID to its domain:

```
https://did.example.com/.well-known/did-configuration.json
```

```json
{
  "@context": "https://identity.foundation/.well-known/did-configuration/v1",
  "linked_dids": [
    "<JWT signed by org signing key, binding did:web:did.example.com to https://did.example.com>"
  ]
}
```

This domain binding allows VC verifiers to confirm that the issuer DID is legitimately controlled by the domain operator without trusting any external registry.

---

## 4. JML Lifecycle Automation

There is no declarative workflow engine in the Google Workspace architecture. All JML logic resides in the sidecar's event handler, which processes Directory API push notifications and reconciliation scan results through the same code path.

### 4.1 Event Handler

```go
type DirectoryEvent struct {
    Kind             string   // "admin#directory#user"
    ID               string   // Google unique user ID (stable, unlike email)
    PrimaryEmail     string
    Suspended        bool
    Deleted          bool     // inferred from 404 on fetch after a `delete` notification
    OrgUnitPath      string
    CustomAttributes map[string]interface{}
    Groups           []string // fetched separately from groups.list
}

func (s *Sidecar) handleEvent(event DirectoryEvent) error {
    existing := s.store.Get(event.ID)

    switch {
    case event.Deleted && existing != nil:
        return s.tombstone(existing, "directory-deletion")

    case event.Suspended && existing != nil && existing.State == StateActive:
        return s.suspend(existing, "directory-suspension")

    case !event.Suspended && existing != nil && existing.State == StateSuspended:
        return s.reactivate(existing)

    case existing == nil && !event.Deleted && !event.Suspended:
        return s.provision(event)  // new user

    case existing != nil && s.claimsChanged(existing, event):
        return s.updateClaims(existing, event)  // Mover
    }
    return nil
}
```

The handler MUST be idempotent: running it twice on the same event MUST produce the same result. Push notifications MAY be delivered more than once.

### 4.2 Joiner

Triggered by a push notification for a new user, or by the reconciliation poller finding a user in the Directory that is absent from the sidecar.

Actions:

1. Fetch the full user record including custom schema attributes (§4.6) and group memberships.
2. Derive Agora roles from group membership (§4.7).
3. Mint the `localIdentifier` (§3.1) and write the genesis log entry (state: `STUB`), including the `KeyPackageEndpoint` service entry (spec §2.5.3).
4. Store the user record in the sidecar DB keyed by Google user ID, with the private mapping to the `localIdentifier`.
5. Send an enrollment invitation email via Google Workspace SMTP relay or Gmail API, including an enrollment URL pre-populated with the user's DID.

The enrollment invitation email is sent using the Gmail API with domain-wide delegation, impersonating an admin account or a dedicated `noreply@example.com` address. Example:

```
Subject: Your Agora encrypted workspace is ready

Hi Alice,

Your organization has set up end-to-end encrypted communication via Agora.
Click the link below to enroll your device:

https://enroll.example.com/?did=did%3Awebvh%3AQmSCIDa...%3Adid.example.com%3Ausers%3Ak7f3qd2m

This link expires in 7 days. If you need a new link, contact IT.
```

### 4.3 Mover

Triggered by a push notification for an existing user with changed attributes (`orgUnitPath`, `primaryEmail`, custom schema attributes, or group membership changes). A `primaryEmail` change updates only the sidecar's private record and, if a credential claim changed, the `EmployeeCredential`; the DID is unchanged (§3.1).

Group membership changes do not trigger a user-level push notification; the Directory API push fires only on user object changes. The sidecar MUST therefore poll `groups.list` on a configurable schedule (default: 1 hour) for users with active DID documents, comparing group membership against stored state. This is the primary limitation relative to the O365 Mover workflow, which triggers declaratively on group membership changes.

Actions:

1. Derive updated Agora roles from new group membership.
2. Revoke the existing `EmployeeCredential` VC (mark the status entry as revoked in the status list).
3. Issue a new `EmployeeCredential` VC with updated `agoraRoles` and department claims.
4. Notify the Enrollment Service via webhook to update space role assignments.

The DID log is not changed: the document carries no employment attributes (O365 spec §3.3).

### 4.4 Leaver

Triggered by a push notification for a user with `suspended: true` (soft leaver) or a deleted user (hard leaver), or by the reconciliation poller finding a discrepancy.

Google has no real-time termination trigger equivalent to Entra Lifecycle Workflows' on-demand execution, and the push notification channel has delivery lag. On receiving a suspension or deletion notification, the sidecar MUST immediately revoke the VC, which blocks future Space admissions, and notify the Enrollment Service. Membership in the MLS group is the only read access control (ARCHITECTURE §6.2), so the MLS Remove commits in Phase 1 are what cut off the user's access to Spaces they already belong to. VC revocation alone does not.

**Phase 1: Immediate** (on notification receipt; target latency: <30 seconds):

- Mark the `EmployeeCredential` status entry as revoked in the status list.
- Append a log entry moving the DID to `SUSPENDED` (soft leaver) or `DEACTIVATED` (hard leaver), as in O365 spec §3.1 and §5.4.
- Notify the Enrollment Service to initiate MLS Remove commits. This is the access cut-off.

**Phase 2: Confirmed** (after the reconciliation poller next runs, or on explicit IT action):

- Verify deletion or suspension state against the live Directory API.
- Confirm MLS Remove commits have propagated (via Enrollment Service ACK).
- Log the final leaver audit record.

**Soft vs. hard leaver:**

- `suspended: true` → transition to `SUSPENDED`; preserve device public keys in DB. If the user is later reactivated (`suspended: false`), a further log entry restores the keys and the document returns to `ACTIVE`. Both entries are visible in the log.
- Deletion from Directory → deactivate immediately. The log stays resolvable (spec §2.5.6), and device public keys remain in its history for compliance audit purposes.

**Worst-case latency:** If the push channel is down and the poller has not run, a terminated employee retains an active DID for up to 24 hours. This is an accepted operational risk. IT MUST call `POST /v1/tombstone` directly with an admin token for immediate effect when performing involuntary terminations, bypassing the automated path.

### 4.5 Lost Device

Initiated directly by IT via the sidecar admin API, identical to O365 spec §5.5: a witnessed log entry removing the key, no gossiped announcement (the user's remaining devices send an `IdentityChanged` notice, spec §2.7), and MLS Remove of the device's leaves:

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

The admin token is an ordinary Google OAuth token for the staff member, requesting only Google-defined scopes (`openid profile email`) and obtained via the standard Google OAuth device flow or browser-based consent. Google defines no custom scope for this. The sidecar authorizes an admin call by mapping the token `sub` (the Google user `id`) to its admin list, which it keeps in its private DB or derives from membership of a designated Google group. That mapping is the `AgoraDIDAdmin` role.

### 4.6 Custom Schema Attributes

Google Workspace supports custom schema attributes on user objects. The sidecar reads these for DID provisioning and VC claim population. Recommended schema:

```
Schema name: AgoraIdentity
Fields:
  - agoraRoles (string, multi-value)     : explicit role override
  - agoraDIDState (string)               : admin override for DID state
  - agoraEnrollmentExpiry (string, date) : enrollment link expiry date
```

Custom schemas are optional. When absent, roles are derived entirely from group membership (§4.7). The `agoraDIDState` field allows an admin to force-suspend or force-deactivate a DID from the Google Admin console without API access.

### 4.7 Role Derivation from Groups

When custom schema attributes are absent, the sidecar derives Agora roles from Google Workspace group membership using a configurable mapping:

```toml
[roles]
# Group email → Agora role name
"agora-admins@example.com"     = "admin"
"agora-moderators@example.com" = "moderator"
"agora-members@example.com"    = "member"
"agora-guests@example.com"     = "guest"
# Default role for users not in any of the above groups:
default = "member"
```

A user's Agora roles are the union of all matched group mappings. A user in both `agora-moderators` and `agora-members` has roles `["moderator", "member"]`.

---

## 5. EmployeeCredential Issuance

### 5.1 Self-Issued VC

The sidecar issues `EmployeeCredential` VCs directly, signed by the org root DID's Ed25519 key stored in Google Cloud KMS. The credential schema is identical to the O365 spec (§4.1) with the issuer DID changed:

```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://did.example.com/credentials/employee/v1"
  ],
  "type": ["VerifiableCredential", "EmployeeCredential"],
  "issuer": "did:web:did.example.com",
  "issuanceDate": "2026-03-13T00:00:00Z",
  "expirationDate": "2027-03-13T00:00:00Z",
  "credentialSubject": {
    "id": "did:webvh:QmSCIDa...:did.example.com:users:k7f3qd2m",
    "employeeId": "EMP-12345",
    "displayName": "Alice Smith",
    "department": "Engineering",
    "jobTitle": "Senior Engineer",
    "employmentStatus": "active",
    "agoraRoles": ["member", "engineer"]
  },
  "credentialStatus": {
    "id": "https://did.example.com/v1/status/2026#42",
    "type": "StatusList2021Entry",
    "statusListIndex": "42",
    "statusListCredential": "https://did.example.com/v1/status/2026"
  }
}
```

### 5.2 Status List

The sidecar maintains a StatusList2021 credential for VC revocation. The status list is a bitstring where each bit corresponds to one VC's revocation status, served publicly at:

```
GET https://did.example.com/v1/status/2026
→ StatusList2021Credential (JWT-encoded, signed by org key)
```

One status list is maintained per year (configurable), with a maximum of 131,072 entries. Status list indices are assigned at VC issuance and MUST NOT be reused. The status list MUST be regenerated and re-signed whenever a VC is revoked.

**Privacy note:** A public status list is observable: an external party can infer employee terminations by monitoring newly flipped bits. For orgs with privacy requirements, large lists with random index assignment reduce what an observer learns, and the list can be served only to authorized verifiers. The W3C Bitstring Status List specification (the StatusList2021 successor) defines no encrypted entries, so migrating to it does not address this. Migration is still a matter of changing the served format and updating the `type` field; the `statusListCredential` pointer in the credential schema is unchanged.

### 5.3 VC Delivery

The sidecar has no push wallet to deliver VCs to. Three delivery options are supported:

**Option A, deep link in enrollment email:** The enrollment invitation includes a second link for VC acceptance. When clicked, the browser calls the sidecar's issuance endpoint, which returns the signed VC as a JSON file download for import into a W3C VC-compatible wallet.

**Option B, Agora client built-in wallet:** The Agora client (web or CLI) stores the `EmployeeCredential` in its local keystore alongside device keys and presents the VC automatically during space enrollment. This option requires no external wallet app and keeps the credential collocated with the keys it attests.

**Option C, OID4VCI:** The sidecar implements the OpenID for Verifiable Credential Issuance protocol, allowing any OID4VCI-compatible wallet to pull the VC via a standard issuance flow. This is the most interoperable option and the correct long-term path as wallet support matures.

For initial deployment, Option B is the recommended choice. Options A and C are extensions for orgs with existing wallet infrastructure.

In every option the VC is issued only after the first device key is registered, following the bootstrap order of O365 spec §4.2: the first device registers without a VC (§6), and the VC then names the active DID as its subject. The Option A acceptance link is therefore sent after first-device enrollment, not in the initial invitation.

### 5.4 VC Serving Endpoint

```http
GET /v1/credentials/{localIdentifier}/employee
Authorization: Bearer <employee's Google OAuth token>

→ 200 OK
Content-Type: application/json

{
  "credential": "<JWT-encoded VC>",
  "format": "jwt_vc_json"
}
```

Only the credential subject MAY fetch their own VC (the token `sub`, the Google user `id`, MUST map in the sidecar's private DB to the credential subject's DID). Admins holding the sidecar-side `AgoraDIDAdmin` role (§4.5, the `sub` mapping to the sidecar's admin list) MAY fetch any user's VC for audit purposes.

---

## 6. MFA Step-Up for Device Key Registration

Google does not provide `acr`/`amr` claims in standard OAuth tokens for most Workspace tiers. The step-up enforcement mechanism varies by Workspace edition.

Step-up for device key registration in this profile has two parts, on every Workspace edition:

1. **Google-enforced 2-Step Verification with security keys.** The organization SHOULD enforce 2SV with security keys only for the users who enroll Agora devices, so that the Google sign-in that yields the enrollment OAuth token requires a hardware key. Google enforces this at sign-in; the token does not say which second factor was used, so the sidecar cannot check it, and the guarantee rests on the Workspace policy. Google issues only Google-defined OAuth scopes, so the profile does not rely on a custom scope gated by Context-Aware Access. Enterprise Plus deployments MAY add Context-Aware Access rules that apply to the enrollment OAuth client, if their edition supports this. Verify both controls against current Google documentation (written 2026-10, not re-verified).
2. **Device-key signatures.** Every registration request is signed by the new device key as proof of possession, and every later device's request is also signed by a device key already in the verified log (spec §2.5.4 Step 3).

The sidecar runs no WebAuthn or PKCS#11 challenge of its own. It has no enrolled credential to check one against, and a passkey is never a device key (spec §2.2). Business Starter, Standard and Plus have no Context-Aware Access, so for them the two parts above are the whole of step-up. An organization that does not enforce security-key 2SV gets, at first-device enrollment, only the strength of its ordinary Google sign-in policy; later devices still need a signature from an existing device.

The remaining registration checks are those of O365 spec §5.6: the token `sub` maps in the private DB to the requested DID; the first device registers into a `STUB` DID with no existing-device signature and no VC; every later device's request carries a spec §13.1.1 signature by a device key in the current verified log (spec §2.5.4). On success the sidecar appends a log entry signed with its update key and co-signed by witnesses (O365 spec §6.6) and, for the first device, issues the `EmployeeCredential` (§5).

---

## 7. GCP App Registration and Service Account

### Service Account (Directory API access)

- Created in the GCP project linked to the Workspace tenant.
- Domain-wide delegation granted in Google Admin console.
- Scopes: as listed in §2.1.
- Key: JSON service account key stored in Secret Manager, rotated annually.

### OAuth 2.0 Client ID (employee authentication during enrollment)

- Application type: Web application.
- Authorized redirect URIs: `https://enroll.example.com/v1/enroll/callback`.
- Scopes requested at enrollment: `openid profile email`.

### Sign-in policy for the enrollment OAuth client

- No custom OAuth scope: Google issues only Google-defined scopes.
- In Google Admin, enforce 2-Step Verification with security keys only for the organizational unit or group whose members enroll Agora devices.
- Enterprise Plus MAY add Context-Aware Access rules for the enrollment OAuth client. Verify availability against current Google documentation (written 2026-10, not re-verified).

### Cloud KMS (org root DID signing key)

- Key ring: `agora-did-keys`.
- Key: `org-root-signing-key` (Ed25519, HSM-backed): VC issuer key (§3.2).
- Key: `did-log-update-key` (Ed25519, HSM-backed): `did:webvh` update key for employee DID logs. Used only to sign log entries.
- Key: `provisioning-signing-key` (Ed25519, HSM-backed): `authentication` key of the sidecar's own DID (O365 spec §6.5). As spec §2.5.7 requires, `did-log-update-key` is also a verification method of that DID.
- IAM: sidecar service account MUST have `roles/cloudkms.signerVerifier`.

### Secret Manager

- `agora-did-service-account-key`: service account JSON key.
- `agora-did-webhook-token`: Directory API push channel secret token.
- `agora-did-enrollment-client-secret`: OAuth client secret.

---

## 8. DID Sidecar Deployment

The sidecar deploys as a Cloud Run service or GKE workload. Cloud Run is recommended for most deployments: it handles TLS termination, scales automatically, and supports workload identity in place of a JSON key file.

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: agora-did-sidecar
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/service-account: agora-did-sidecar@project.iam.gserviceaccount.com
    spec:
      containers:
        - image: gcr.io/project/agora-did-sidecar:latest
          env:
            - name: WORKSPACE_DOMAIN
              value: "example.com"
            - name: DID_BASE_URL
              value: "https://did.example.com"
            - name: KMS_KEY_NAME
              value: "projects/project/locations/global/keyRings/agora-did-keys/cryptoKeys/org-root-signing-key/cryptoKeyVersions/1"
            - name: STORAGE_BACKEND
              value: "cloudsql"    # or "cloudspanner" for higher scale
```

**Storage:** Cloud SQL (PostgreSQL) for most deployments. Schema is identical to the O365 sidecar PostgreSQL option.

**Background workers:** Cloud Scheduler triggers Cloud Tasks for the reconciliation poller and channel renewal worker. These run as separate invocations of the same service binary, not as persistent goroutines in the main serving instance.

---

## 9. Differences from O365 Architecture

| Aspect | O365 | Google Workspace |
| ------ | ---- | ---------------- |
| JML automation | Graph Lifecycle Workflows (declarative, UI-configurable) | Directory API push + sidecar event handler (code) |
| JML reliability | Push + Logic App retry + Entra audit log | Push + polling fallback (24h worst-case lag) |
| Immediate termination | On-demand Lifecycle Workflow execution (seconds) | IT calls `/v1/tombstone` directly (manual step) |
| VC issuance | Entra Verified ID (managed service, Authenticator wallet) | Sidecar self-issued VC, Agora client wallet |
| Admission block speed (VC revocation) | StatusList2021 via Verified ID (seconds) | StatusList2021 served by sidecar (seconds, same) |
| MFA step-up enforcement | Entra Conditional Access authentication context (`acrs` claim; requires Entra ID P1) | Google-enforced security-key 2SV (not visible to the sidecar), optional CAA (Enterprise Plus), plus device-key signatures (spec §2.5.4) |
| Org signing key | Azure Key Vault (managed) | Google Cloud KMS (managed, equivalent) |
| Hosting | Azure Container Apps / App Service | Cloud Run / GKE |
| License cost | Entra ID P1 + Entra ID Governance | No extra license; Enterprise Plus only for optional CAA |
| Group membership change detection | Declarative (Mover workflow triggers on group change) | Polling (1-hour default lag for role updates) |

For high-security deployments where role changes require immediate enforcement, the group membership polling interval MAY be shortened to 5 minutes at the cost of increased Directory API quota consumption.

---

## 10. Implementation Notes

### 10.1 Shared Codebase with O365 Sidecar

The DID Sidecar is the same Go binary for both O365 and Google Workspace deployments. Platform-specific behavior is isolated behind interfaces:

```go
type IdentityProvider interface {
    // WatchUsers registers a push notification channel or polling subscription.
    WatchUsers(ctx context.Context, callbackURL string) error

    // GetUser fetches the current user record by stable ID.
    GetUser(ctx context.Context, id string) (*UserRecord, error)

    // ListUsers returns all active users in the domain.
    ListUsers(ctx context.Context) ([]*UserRecord, error)

    // GetGroupsForUser returns group names/emails for a user.
    GetGroupsForUser(ctx context.Context, id string) ([]string, error)
}

type CredentialSigner interface {
    // Sign produces an Ed25519 signature using the org root key.
    Sign(ctx context.Context, payload []byte) ([]byte, error)

    // PublicKey returns the org root signing public key.
    PublicKey(ctx context.Context) (ed25519.PublicKey, error)
}
```

Implementations:

- `EntraIdentityProvider`: uses Microsoft Graph
- `WorkspaceIdentityProvider`: uses Admin SDK Directory API
- `AzureKeyVaultSigner`: uses Azure Key Vault
- `CloudKMSSigner`: uses Google Cloud KMS

### 10.2 Key Dependencies (Google Workspace)

| Function | Library |
| -------- | ------- |
| Google Admin SDK | `google.golang.org/api/admin/directory/v1` |
| Google OAuth2 | `golang.org/x/oauth2/google` |
| Cloud KMS | `cloud.google.com/go/kms/apiv1` |
| Cloud SQL | `cloud.google.com/go/cloudsql` |
| W3C VC issuance | Internal implementation over `crypto/ed25519` |
| `did:webvh` log | As O365 spec §9.1 |
| StatusList2021 | Internal implementation (bitstring + JWT signing) |

### 10.3 DM Message Requests for Colleagues

The organization's managed client configuration (MDM or enrollment policy) can add a rule to the user's accepted senders (spec §4.6.3), for example every DID under the organization's `did:webvh` domain, or every member of the organization's Spaces. DMs from matching senders then skip the message request state. Whether users may decline or block colleagues is also client configuration. Attributes that must be trusted across organizations need a credential format and are out of scope here.

---

## 11. Open Questions

1. **Google Workspace Events API vs. Directory API push.** The newer Google Workspace Events API (`workspace.googleapis.com`) supports subscriptions to changes across Workspace applications and may eventually supersede the Directory API's per-resource push channels. It currently supports Chat, Meet, and limited Workspace resources; Directory/user events may be added. The sidecar's `IdentityProvider` interface is designed so migration is a drop-in replacement rather than a rewrite.

2. **Primary email as DID path.** Resolved: the DID path is a stable `localIdentifier`, not the email (§3.1).

3. **OID4VCI implementation scope.** §5.3 Option C identifies OID4VCI as the long-term VC delivery path but defers implementation. When implemented, the sidecar acts as an OID4VCI Authorization Server and Credential Issuer. The OAuth authorization server endpoint is the same Google OAuth app used for enrollment auth; the credential endpoint is `/v1/credentials/{localIdentifier}/employee`. The primary outstanding question is wallet interoperability: no widely-deployed mobile wallet currently handles org-issued `EmployeeCredential` types with custom `credentialSubject` schemas.

4. **Restricted Workspace editions.** The Admin SDK Directory API is available on all Workspace editions, but domain-wide delegation requires a Super Admin to configure it. The service account JSON key approach (§7) works on all editions. The Cloud KMS dependency requires a linked GCP project, which is standard for Workspace Business/Enterprise but may require additional setup for legacy G Suite Basic accounts.

5. **HR system integration.** Both this spec and the O365 spec treat the directory as the system of record, but most orgs use an HRIS (Workday, BambooHR, etc.) as the upstream source of truth, synced into the directory. Sync lag between the HRIS and the directory adds latency on top of the push notification lag. For regulated environments where termination must be effective within minutes of an HRIS update, a direct HRIS webhook to the sidecar that bypasses the directory is a candidate extension.
