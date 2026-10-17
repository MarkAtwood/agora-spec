# Profile: Employer-Managed DIDs, Universal Identity Provider Support

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

**Status:** Pre-implementation design
**Version:** 0.1 Draft
**Depends on:** the Agora protocol specification (`spec/`, current draft), O365 DID Spec v0.1, Google Workspace DID Spec v0.1

---

## 1. Overview

This profile extends the DID sidecar's `IdentityProvider` interface to cover four categories of identity infrastructure beyond O365 and Google Workspace. The table lists each category's identity providers (IdPs) or directories and how the sidecar detects changes.

| Category | Examples | Change Detection |
|---|---|---|
| **Cat 1**: Webhook-capable IdPs | Okta, JumpCloud, Ping Identity, OneLogin | Native event webhook / push |
| **Cat 2**: SCIM-only providers | Any SCIM 2.0 directory without push | Polling only |
| **Cat 3**: SAML-only / legacy IdPs | AD FS, Shibboleth, legacy Ping Federate | HR system, AD-LDAP, or manual IT |
| **Cat 4**: On-premises Active Directory | Any Windows AD forest without Entra sync | LDAP DirSync control or USNChanged polling |

All four categories produce the same output: a `did:webvh` identity `did:webvh:{SCID}:did.example.com:users:{localIdentifier}` whose DID log is served at `https://did.example.com/users/{localIdentifier}/did.jsonl` (spec §2.1, §2.5.2). The same sidecar event handler, introduced in the Google Workspace spec, drives it in every category. The categories differ only in which `IdentityProvider` implementation feeds that handler and which joiner, mover, and leaver (JML) source drives user lifecycle events.

**The sidecar is the organization's DID provisioning service** (spec §2.5.2), a Communications Operator (CO) component. It holds an update key for every DID log it creates. Each organizational change to a document (stub creation, device key addition or removal, suspension, deactivation) is a log entry signed with that update key, and every resolver sees it in the DID history (spec §2.5.1).

The sidecar also hosts each user's KeyPackages. At stub creation it adds two service entries: a `KeyPackageEndpoint` service entry of type `AgoraKeyPackageEndpoint` that points at the sidecar, and an `AgoraProvisioning` service entry that names its provisioning endpoint `{prov}` (spec §2.5.3). It stores the KeyPackages the user's devices upload (spec §2.5.4 Step 6, §5.2.1.1) and accepts Welcomes by POST at the same endpoint (spec §4.6, §5.2.1.1). As the users' identity host, it also serves admission keys for their direct message (DM) groups and self-groups, exactly as O365 spec §6.7 describes; this profile defers to that section. Relays play no part in provisioning: they never see IdP tokens, DID logs, or KeyPackages.

**Witnesses.** These are CO-provisioned `did:webvh` identities, so spec §2.1 requires `did:webvh` witnesses. Each DID's `witness` parameter lists at least one witness DID that the organization does not control, with a threshold that makes every accepted log entry carry a proof from at least one such witness. The sidecar therefore publishes a log entry only once it holds the required witness proofs, and clients reject an entry that lacks them (spec §2.1, §2.5.2). The witnesses stop the sidecar, which holds every update key, from serving different logs to different resolvers or rolling a log back. The organization chooses its witnesses; this profile names none.

**DID path rule (all categories).** The `localIdentifier` follows spec §2.5.2 and O365 spec §2: stable, never reassigned, and never derived from a name, email, UPN, or `userName`. The recommended default is a random lowercase base32 value that the sidecar mints at provisioning (for example `k7f3qd2m`). The source's immutable user ID (Okta `id`, SCIM `externalId` or `id`, AD `objectGUID`, HR employee ID) is an allowed alternative. A sidecar-minted value is preferred because it survives a change of IdP or JML source. Either way, the sidecar keys its private user record on that source ID (`stableID`) and maps it to the `localIdentifier`; the mapping is never published. Renames and email or UPN changes update only the private record and credential claims, never the DID. A move of the DID host keeps the SCID: the sidecar creates DIDs with `did:webvh` portability enabled, so the log continues at the new domain and records the previous DID in `alsoKnownAs` (spec §2.5.2).

The verifiable credential (VC) issuance model is the same as in the Google Workspace spec: the org root key signs a self-issued `EmployeeCredential`, and revocation status is served through StatusList2021. No category requires an external VC platform. `profiles/attribute-bridging.md` sections 3 and 4 map directory attributes and IdP assurance to derived claims.

---

## 2. Shared Architecture

The sidecar event handler and DID document lifecycle (STUB → ACTIVE → SUSPENDED → DEACTIVATED) are unchanged from the Google Workspace spec. The `IdentityProvider` implementation and `JMLSource` configuration are the only per-deployment variables.

Every source's events reduce to five normalized actions. Each source section below maps its native events to these; §7 collects all mappings in one table.

| Normalized action | DID log entry (signed with the sidecar's update key) | `EmployeeCredential` | Resulting state |
|---|---|---|---|
| `PROVISION` | Create the stub log: no keys, a `KeyPackageEndpoint` service entry, and an `AgoraProvisioning` service entry (spec §2.5.3). No-op if the user already exists. | None until first device enrollment | `STUB` |
| `UPDATE` | None. Claims live in the credential, not the DID document. | Re-issue with new claims | Unchanged |
| `SUSPEND` | Remove all device keys (spec §2.5.5 `revokeAll`). The sidecar keeps the removed public keys in its private store. | Revoke | `SUSPENDED` |
| `REACTIVATE` | Restore the device keys removed at suspension. | Re-issue | `ACTIVE` (or `STUB` if no keys were held) |
| `TERMINATE` | Remove all device keys and deactivate the DID (spec §2.5.6). | Revoke | `DEACTIVATED` |

For `SUSPEND` and `TERMINATE` the sidecar also stops serving the user's KeyPackages and notifies the CO's Enrollment Service, which issues MLS Commits that Remove the user's leaves in the organization's groups. Members of groups outside the organization's control Remove those leaves when they next resolve the DID (spec §2.5.5, §2.5.6). `TERMINATE` also deletes stored KeyPackages. It is final: the log stays resolvable and is never deleted, so archived compliance records keep resolving (spec §2.5.6), and the `localIdentifier` is never reassigned. A returning employee gets a new DID.

```toml
# enrollment.toml

[sidecar]
did_base_url     = "https://did.example.com"
org_root_did     = "did:web:did.example.com"   # EmployeeCredential issuer
# Three separate Ed25519 keys, as in Google Workspace spec §7. Backends: §9.
signing_key_type = "file"            # or "awskms", "gcpkms", "azurekv", "pkcs11", "vault"
signing_key_path = "/secrets/org-root-ed25519.pem"   # VC issuer key only
update_key_type  = "file"
update_key_path  = "/secrets/did-log-update-ed25519.pem"   # did:webvh update key; signs DID log entries only
provisioning_signing_key_type = "file"
provisioning_signing_key_path = "/secrets/provisioning-ed25519.pem"   # sidecar's own DID key (spec §2.5.7)
# did:webvh witnesses (spec §2.1): at least one DID the organization does not control.
# With only such witnesses listed, a threshold of 1 meets the requirement.
witnesses         = ["did:key:z6Mk..."]
witness_threshold = 1

[identity_provider]
type = "okta"                        # okta | jumpcloud | ping | onelogin | scim | saml | ldap

[jml_source]
# Required when identity_provider has no lifecycle events of its own
# (Cat 3: saml-only) or when the operator designates HR as the primary trigger.
type = "none"                        # none | workday | bamboohr | ad-ldap | manual
```

One sidecar instance maps to one identity provider and one JML source. An organization using Okta sets `identity_provider.type = "okta"` and `jml_source.type = "none"`; Okta event hooks drive the full lifecycle. An organization using Shibboleth for authentication and Workday as HRIS sets `identity_provider.type = "saml"` and `jml_source.type = "workday"`.

**DM message requests for colleagues.** The organization's managed client configuration (MDM or enrollment policy) can add a rule to the user's accepted senders (spec §4.6.3), for example every DID under the organization's `did:webvh` domain, or every member of the organization's Spaces. DMs from matching senders then skip the message request state. Client configuration also decides whether users may decline or block colleagues. Attributes that must be trusted across organizations need a credential format and are out of scope here.

---

## 3. Category 1: Webhook-Capable IdPs

### 3.1 Covered Providers

| Provider | Event Mechanism | Relevant Events |
|---|---|---|
| **Okta** | Event Hooks (HTTPS POST, async) | `user.lifecycle.create`, `user.lifecycle.activate`, `user.lifecycle.deactivate`, `user.lifecycle.delete`, `user.lifecycle.suspend`, `user.lifecycle.unsuspend`, `group.user_membership.add`, `group.user_membership.remove` |
| **JumpCloud** | Webhooks (HTTPS POST, synchronous) | `user.create`, `user.update`, `user.delete`, `group.member.add`, `group.member.remove` |
| **Ping Identity** (PingOne) | Webhook subscriptions | `USER.CREATE`, `USER.UPDATE`, `USER.DELETE`, `ROLE.USER_ROLE_ASSIGNMENT_CREATED`, `ROLE.USER_ROLE_ASSIGNMENT_DELETED` (see §3.4) |
| **OneLogin** | Events API + webhooks | `user.created`, `user.deactivated`, `user.deleted`, `role.add_user`, `role.remove_user` |

All four providers' webhooks use the same sidecar webhook receiver (`POST /v1/notify`) with provider-specific payload adapters. For OneLogin, webhooks are a supplement to Events API polling (§3.5).

Event names and payload formats are as of October 2026; verify them against current vendor documentation (Okta, JumpCloud, PingOne, OneLogin) before implementation.

### 3.2 Okta (Reference Implementation)

Okta is the reference implementation for Cat 1. Other providers follow the same pattern with provider-specific field mappings.

**Webhook registration.**

```
POST https://{okta-domain}/api/v1/eventHooks
Authorization: SSWS {api-token}
Content-Type: application/json

{
  "name": "Agora DID Sidecar",
  "events": {
    "type": "EVENT_TYPE",
    "items": [
      "user.lifecycle.create",
      "user.lifecycle.activate",
      "user.lifecycle.deactivate",
      "user.lifecycle.delete",
      "user.lifecycle.suspend",
      "user.lifecycle.unsuspend",
      "group.user_membership.add",
      "group.user_membership.remove"
    ]
  },
  "channel": {
    "type": "HTTP",
    "version": "1.0.0",
    "config": {
      "uri": "https://did.example.com/v1/notify",
      "authScheme": {
        "type": "HEADER",
        "key": "Authorization",
        "value": "Bearer {sidecar-webhook-secret}"
      }
    }
  }
}
```

Okta requires a one-time GET verification before the hook becomes active. The sidecar handles this at `GET /v1/notify` by reading the `x-okta-verification-challenge` header and returning `{"verification": "<value>"}`.

**Event → action mapping.**

| Okta Event | Normalized Action (§2) |
|---|---|
| `user.lifecycle.create` | `PROVISION` |
| `user.lifecycle.activate` | `PROVISION` (no-op if already provisioned) |
| `user.lifecycle.deactivate` | `SUSPEND` |
| `user.lifecycle.suspend` | `SUSPEND` |
| `user.lifecycle.unsuspend` | `REACTIVATE` |
| `user.lifecycle.delete` | `TERMINATE` |
| `group.user_membership.add` | `UPDATE` (fetch groups, re-derive roles) |
| `group.user_membership.remove` | `UPDATE` (fetch groups, re-derive roles) |

**Payload extraction.**

```go
type OktaEventHookPayload struct {
    Data struct {
        Events []struct {
            EventType string `json:"eventType"`
            Target []struct {
                ID          string `json:"id"`
                Type        string `json:"type"`
                AlternateID string `json:"alternateId"` // email
                DisplayName string `json:"displayName"`
            } `json:"target"`
        } `json:"events"`
    } `json:"data"`
}
```

The target with `type: "User"` carries the Okta user ID (`id`) and email (`alternateId`). The sidecar keys on the Okta user ID, which is stable through email changes, and fetches the full user profile via the Okta Users API on each event before acting.

**Reconciliation.** Once a day, the sidecar's reconciliation poller queries the Okta System Log API for missed lifecycle events, using a stored cursor on the `published` timestamp: `GET /api/v1/logs?filter=eventType sw "user.lifecycle"`. The filter uses `sw` for the prefix match because the `eq` operator takes no wildcard. Verify the filter syntax against current Okta documentation. This approach is more reliable than a full directory scan because it fetches only change events.

**Limitations.** Okta event hooks are asynchronous, with up to a one-minute delivery delay, and do not guarantee delivery. Okta retries failed deliveries but may drop them after repeated failures. The System Log reconciliation poller is the reliability backstop.

### 3.3 JumpCloud

JumpCloud webhooks fire synchronously and block the admin operation until the sidecar responds with HTTP 200. The sidecar MUST respond within 10 seconds. To meet this requirement, the sidecar MUST respond 200 immediately, enqueue the event, and process it in a worker goroutine.

```toml
[identity_provider]
type           = "jumpcloud"
api_key        = "..."           # JumpCloud API key for profile fetches
webhook_secret = "..."           # HMAC-SHA256 secret for signature verification
org_id         = "..."
```

JumpCloud signs webhook payloads with HMAC-SHA256 over the request body. The sidecar MUST verify the `X-JumpCloud-Signature` header on every inbound request.

### 3.4 Ping Identity (PingOne)

PingOne uses a subscription model. The sidecar registers a subscription with this request:

```
POST https://api.pingone.com/v1/environments/{envId}/subscriptions
Authorization: Bearer {worker-app-token}

{
  "name": "Agora DID Sidecar",
  "enabled": true,
  "httpEndpoint": "https://did.example.com/v1/notify",
  "format": "ACTIVITY",
  "filterOptions": {
    "includedActionTypes": [
      "USER.CREATE", "USER.UPDATE", "USER.DELETE",
      "ROLE.USER_ROLE_ASSIGNMENT_CREATED",
      "ROLE.USER_ROLE_ASSIGNMENT_DELETED"
    ]
  }
}
```

PingOne verifies the endpoint with an initial POST containing `"verifyRequest": true`. The sidecar MUST echo the request body as the verification response.

### 3.5 OneLogin

OneLogin provides both a push-based webhook and a pull-based Events API. The Events API SHOULD be used as the primary source, polled at a short interval (1 minute), because it is more reliable. Webhooks MAY be used as a fast-path supplement.

```
GET https://api.us.onelogin.com/api/2/events?event_type_id={ids}&since={cursor}
Authorization: bearer {access-token}
```

Relevant events: user created, user updated, user deactivated, user activated, user deleted, user reactivated, role assigned to user (`event_type_id` 4), and role removed from user. OneLogin's public documentation confirms only the role-assigned ID, so this profile fixes no other IDs: the deployment obtains each event's `event_type_id` from `GET /api/1/events/types`, caches the result for up to 24 hours, and passes the IDs in `{ids}`. Because the poll includes the user-deleted event, the sidecar sees deletions without relying on a webhook.

---

## 4. Category 2: SCIM-Only Providers

### 4.1 Overview

SCIM 2.0 (RFC 7644) is a request/response provisioning protocol with no push notification model. The sidecar cannot register a webhook with a SCIM provider. Two modes are supported, and the operator configures which one is in use:

- **SCIM server mode.** The sidecar exposes a SCIM 2.0 endpoint, and the upstream provisioner pushes to it.
- **SCIM client mode.** The sidecar polls the upstream SCIM server for changes.

### 4.2 SCIM Server Mode

The sidecar exposes a SCIM 2.0-compliant Service Provider endpoint. The upstream IdP or provisioner (Okta, Microsoft Entra ID, Workday, and similar) is configured to provision users to this endpoint.

**Endpoints.**

```
POST   /scim/v2/Users              Create user → PROVISION
GET    /scim/v2/Users              List users (for reconciliation)
GET    /scim/v2/Users/{id}         Get user
PUT    /scim/v2/Users/{id}         Full replace → UPDATE, SUSPEND or REACTIVATE
PATCH  /scim/v2/Users/{id}         Partial update → UPDATE, SUSPEND or REACTIVATE
DELETE /scim/v2/Users/{id}         Hard delete → TERMINATE
POST   /scim/v2/Groups             Create group (role)
PUT    /scim/v2/Groups/{id}        Update group membership → UPDATE
PATCH  /scim/v2/Groups/{id}        Partial group update → UPDATE
DELETE /scim/v2/Groups/{id}        Delete group
```

**SCIM operation → sidecar action mapping.**

| SCIM Operation | User `active` Field | Normalized Action (§2) |
|---|---|---|
| `POST /Users` | `true` | `PROVISION` |
| `PUT/PATCH /Users` | `false` | `SUSPEND` |
| `PUT/PATCH /Users` | `true` (was `false`) | `REACTIVATE` |
| `PUT/PATCH /Users` (attribute changes) | `true` | `UPDATE` |
| `DELETE /Users` | (any) | `TERMINATE` |
| `PATCH /Groups` (membership add) | (any) | `UPDATE` (re-derive roles) |
| `PATCH /Groups` (membership remove) | (any) | `UPDATE` (re-derive roles) |

The SCIM endpoint authenticates callers with a Bearer token. The token is a pre-shared secret configured in the upstream provisioner and stored in the sidecar config. For Azure AD and Okta as upstream provisioners, this is the standard "provisioning secret token" in their SCIM connector configuration.

**User identifier mapping.** SCIM uses `externalId` (the upstream system's user ID) and `id` (the SCIM provider's internal ID). The sidecar keys the user record on `externalId`, falling back to the SCIM `id` (§4.4); this is the `stableID` mapped to the DID (§1).

### 4.3 SCIM Client Mode

When the sidecar cannot expose a public endpoint (an on-prem or firewall-restricted deployment), it polls the upstream SCIM server:

```
GET {scim-base-url}/Users?filter=meta.lastModified gt "{cursor}"&count=100
Authorization: Bearer {scim-token}
```

Cursoring on `meta.lastModified` is SCIM-standard for change detection. Not all SCIM servers implement this filter reliably. If a filtered query returns no results when changes are expected, the sidecar MUST fall back to a full diff (fetch all users, compare against stored state).

Deletion detection in SCIM client mode is unreliable: deleted users disappear from the user list without emitting a delete event. The sidecar detects deletions by computing the set difference between the last full sync and the current sync on each reconciliation pass and applies `TERMINATE` to those users.

```toml
[identity_provider]
type               = "scim-client"
scim_base_url      = "https://idp.example.com/scim/v2"
scim_token         = "..."
poll_interval      = "15m"
full_sync_interval = "24h"
```

### 4.4 Stable User ID Requirement

SCIM user identifiers MUST be stable through attribute changes (name changes, email changes, org unit moves). The sidecar MUST key its user records on `externalId` if present, falling back to the SCIM server's internal UUID (`id`). The sidecar MUST NOT key on `userName` or `emails[].value` because these can change.

If a provider rotates user IDs on attribute changes, the sidecar treats the rotation as `TERMINATE` of the old user and `PROVISION` of a new one, producing a new DID for the same person. The operator MUST configure `externalId` mapping to avoid this.

---

## 5. Category 3: SAML-Only / Legacy IdPs

### 5.1 Overview

SAML-only IdPs (AD FS, Shibboleth, legacy Ping Federate) provide authentication but expose no user management API. The sidecar can verify a SAML assertion during device key registration (§8), but it cannot receive JML events from the IdP itself.

For these deployments, JML MUST come from a separate source. Three options are available:

| JML Source | Mechanism | Latency |
|---|---|---|
| **HR system** (Workday, BambooHR) | HR system pushes employee events via webhook or SFTP | Near-real-time (webhook) or batch (SFTP) |
| **Active Directory** (LDAP) | DirSync or USNChanged polling against the underlying AD that feeds the IdP | Configurable poll interval (minimum 5 min) |
| **Manual IT** | IT calls the sidecar admin API (§5.5) directly | Immediate (human-dependent) |

These sources are not mutually exclusive. A production deployment SHOULD use at least two: the HR system as the primary source and AD-LDAP as the reconciliation backstop.

### 5.2 HR System: Workday

The sidecar exposes an inbound webhook endpoint for Workday HR events:

```
POST /v1/hr-event
Authorization: Bearer {workday-webhook-secret}
Content-Type: application/json

{
  "eventType": "HIRE" | "TERMINATE" | "TRANSFER" | "POSITION_CHANGE" | "LEAVE_OF_ABSENCE" | "RETURN_FROM_LEAVE",
  "worker": {
    "workdayId": "abc123",
    "firstName": "Alice",
    "lastName": "Smith",
    "email": "alice@example.com",
    "employeeId": "EMP-12345",
    "department": "Engineering",
    "jobTitle": "Senior Engineer",
    "costCenter": "CC-001",
    "hireDate": "2026-03-13",
    "terminationDate": null,
    "managerEmail": "bob@example.com"
  }
}
```

**Event → action mapping:**

| Workday Event | Normalized Action (§2) |
|---|---|
| `HIRE` | `PROVISION`, then queue enrollment invite |
| `TERMINATE` | `TERMINATE` |
| `TRANSFER` | `UPDATE` (department, cost center) |
| `POSITION_CHANGE` | `UPDATE` (job title, department) |
| `LEAVE_OF_ABSENCE` | `SUSPEND` |
| `RETURN_FROM_LEAVE` | `REACTIVATE` |

The sidecar matches Workday workers to DID records using `employeeId` as the `stableID` (`workdayId` is rarely surfaced in other systems). If the email changes (for example, after a legal name change), the sidecar updates its private record and re-issues the VC; the DID is unchanged (§1).

Workday integration setup (Workday Studio outbound integration or Report-as-a-Service) is the responsibility of the operator's Workday administrator and is outside the scope of this profile. The sidecar endpoint accepts the payload above regardless of which Workday integration mechanism produces it.

### 5.3 HR System: BambooHR

The operator registers a BambooHR webhook that monitors the relevant employee fields:

```
POST https://api.bamboohr.com/api/gateway.php/{company}/v1/webhooks
Authorization: Basic {api-key}
Content-Type: application/json

{
  "name": "Agora DID Sidecar",
  "monitorFields": [
    "status", "department", "jobTitle", "workEmail",
    "terminationDate", "hireDate"
  ],
  "postFields": {
    "employeeId": "id",
    "firstName": "firstName",
    "lastName": "lastName",
    "email": "workEmail",
    "department": "department",
    "jobTitle": "jobTitle",
    "status": "status",
    "terminationDate": "terminationDate"
  },
  "url": "https://did.example.com/v1/hr-event",
  "format": "json",
  "frequency": { "hour": 1 },
  "limit": 0,
  "includeCompanyDomain": true
}
```

BambooHR delivers webhooks on a configurable frequency, not immediately on change; the minimum interval is one hour. BambooHR does not emit discrete event types; it reports field changes. The sidecar infers the action from field values: `status == "Inactive"` with `terminationDate` set → `TERMINATE`; `status == "Active"` with no prior record → `PROVISION`; department or job title change → `UPDATE`.

Every JML source (Workday, BambooHR, SFTP batch, LDAP, manual) emits the same `HREvent` struct, whose `Action` is one of the normalized actions of §2:

```go
type HREvent struct {
    Action      string      // PROVISION | UPDATE | SUSPEND | REACTIVATE | TERMINATE (§2)
    SourceEvent string      // native event name, e.g. Workday "LEAVE_OF_ABSENCE"; audit only
    EmployeeID  string
    Email       string
    DisplayName string
    Department  string
    JobTitle    string
    HireDate    *time.Time
    TermDate    *time.Time
    Source      string      // "workday" | "bamboohr" | "manual" | "ldap" | "scim"
}
```

### 5.4 HR System: Generic SFTP Batch

For HRIS systems that export a nightly CSV or JSON file to an SFTP server, the sidecar includes a batch importer:

```toml
[jml_source]
type          = "sftp-batch"
host          = "sftp.example.com"
port          = 22
username      = "agora-importer"
identity_file = "/secrets/sftp-key"
remote_path   = "/exports/hr-daily.csv"
poll_interval = "1h"
format        = "csv"          # or "json"
csv_columns   = {
  employee_id = "EmployeeID",
  email       = "WorkEmail",
  status      = "EmploymentStatus",   # "Active" | "Terminated" | "OnLeave"
  department  = "Department",
  job_title   = "JobTitle",
  hire_date   = "HireDate",
  term_date   = "TerminationDate"
}
```

The importer downloads the file, diffs it against the previous import keyed on `employee_id`, and emits `HREvent` structs for each changed record: a record present in the new file but not the previous → `PROVISION`; `status` changed to `"Terminated"` → `TERMINATE`; `status` changed from `"Active"` to `"OnLeave"` → `SUSPEND`; `status` changed from `"OnLeave"` to `"Active"` → `REACTIVATE`; other column changes → `UPDATE`. A record that disappears from the file is not treated as a termination; the importer logs it for IT review.

### 5.5 Manual IT Operations

The sidecar admin API provides full lifecycle control without any automated JML source. This is the minimum viable path for small organizations or during initial rollout before HR integration is complete.

All operations require a Bearer token with `AgoraDIDAdmin` scope. The paths match the O365 and Google Workspace sidecars, one endpoint per normalized action (§2):

```
POST /v1/provision                   PROVISION
POST /v1/update-claims               UPDATE
POST /v1/suspend                     SUSPEND
POST /v1/reactivate                  REACTIVATE
POST /v1/tombstone                   TERMINATE
POST /v1/revoke-device-key           Revoke one device key (spec §2.5.5)
GET  /v1/status/{localIdentifier}    Current state of one DID
GET  /v1/audit/{localIdentifier}     Audit log for one DID
```

The sidecar applies manual calls with `Source = "manual"`.

The admin API is documented with an OpenAPI spec. A minimal web UI SHOULD be provided for the IT helpdesk, so that routine operations such as revoking a lost device need no raw API calls.

---

## 6. Category 4: On-Premises Active Directory (LDAP)

### 6.1 Change Detection Strategy

On-premises AD supports two change detection mechanisms with different privilege requirements:

| Mechanism | Privilege Required | Detects Deletions | Scope | Go Library |
|---|---|---|---|---|
| **DirSync control** | With the `LDAP_DIRSYNC_OBJECT_SECURITY` flag: read access only, and results are limited to objects and attributes the account can read. Without it: `DS-Replication-Get-Changes` on the naming context root | Yes (tombstones included, if readable) | Entire naming context | `go-ldap/ldap/v3` `DirSync()` |
| **USNChanged polling** | `List + Read` on target subtree (least privilege) | Only via full sync diff | Subtree-scoped | `go-ldap/ldap/v3` LDAP search |

This profile runs DirSync with the object-security flag (§6.3), so neither mechanism needs replication rights. USNChanged SHOULD be used where the account's read access is limited to a subtree. DirSync SHOULD be used where the account can read the whole naming context, including `CN=Deleted Objects`.

```toml
[identity_provider]
type = "ldap"

[ldap]
host              = "dc01.corp.example.com"
port              = 636
use_tls           = true
bind_dn           = "CN=AgoraSidecar,OU=ServiceAccounts,DC=corp,DC=example,DC=com"
bind_password     = "..."                 # or ldap_password_file
base_dn           = "OU=Users,DC=corp,DC=example,DC=com"
user_filter       = "(&(objectClass=user)(objectCategory=person))"
change_detection  = "usnchanged"          # or "dirsync"
poll_interval     = "5m"
full_sync_interval = "24h"
affiliate_dc      = "dc01.corp.example.com"  # USNChanged: must always bind to same DC
```

### 6.2 USNChanged Implementation

The USNChanged approach polls the directory for objects whose `uSNChanged` attribute exceeds the last processed value, bounded by `highestCommittedUSN` to avoid race conditions with concurrent writes.

Algorithm (run every `poll_interval`):

```go
func (p *LDAPProvider) PollChanges(ctx context.Context) ([]*UserRecord, error) {
    // 1. Read highestCommittedUSN from rootDSE before querying.
    rootDSE := p.fetchRootDSE()
    upperBound := rootDSE.HighestCommittedUSN

    // 2. Query for changed objects.
    filter := fmt.Sprintf(
        "(&%s(uSNChanged>=%d)(uSNChanged<=%d))",
        p.config.UserFilter,
        p.cursor + 1,
        upperBound,
    )
    results := p.ldapSearch(filter, userAttributes)

    // 3. Query Deleted Objects container for deletions.
    deletions := p.searchDeletedObjects(p.cursor + 1, upperBound)

    // 4. Advance cursor to upperBound, not to the max uSNChanged in results.
    p.cursor = upperBound

    return append(results, deletions...), nil
}
```

**Deletion detection.** AD moves deleted objects to `CN=Deleted Objects` rather than removing them immediately. Reading this container requires explicit `List Contents` permission on `CN=Deleted Objects` and the `LDAP_SERVER_SHOW_DELETED_OID` control. Deleted objects retain `objectGUID` and `lastKnownRDN` but lose most attributes. The sidecar looks up the user by `objectGUID` and applies `TERMINATE`.

**DC affinity.** `uSNChanged` is not replicated between domain controllers; values at two different DCs are independent. The sidecar MUST bind to the same DC on every poll, configured via `affiliate_dc`. If that DC is unreachable, the sidecar MUST wait rather than fail over to another DC, because failover can cause missed or duplicate events. After recovery, USNChanged resumes from the stored cursor.

**Attribute mapping.**

| AD Attribute | `UserRecord` Field |
|---|---|
| `objectGUID` | `stableID` (canonical key; never changes) |
| `userPrincipalName` | `upn` (not used in the DID) |
| `mail` | `email` |
| `displayName` | `displayName` |
| `sAMAccountName` | `username` |
| `department` | `department` |
| `title` | `jobTitle` |
| `memberOf` | `groups` (DNs resolved to names) |
| `userAccountControl` bit 0x0002 (`ACCOUNTDISABLE`) set | `SUSPEND` |
| `ACCOUNTDISABLE` cleared | `REACTIVATE` |
| Object in Deleted Objects container | `TERMINATE` |

`objectGUID` is the stable identifier and does not change on rename, move, or attribute modification. The DID path follows §1, so a UPN change updates only the sidecar's private record.

### 6.3 DirSync Implementation

DirSync is simpler to implement correctly, because the cookie manages cursor state automatically. With the `ldap.DirSyncObjectSecurity` flag used below, it needs no replication right: the domain controller returns only objects and attributes the service account can read. Without that flag the account needs `DS-Replication-Get-Changes`. The `go-ldap/ldap/v3` library provides native `DirSync()` support:

```go
func (p *LDAPProvider) PollDirSync(ctx context.Context) ([]*UserRecord, error) {
    req := &ldap.SearchRequest{
        BaseDN:     p.config.BaseDN,
        Scope:      ldap.ScopeWholeSubtree,
        Filter:     p.config.UserFilter,
        Attributes: userAttributes,
    }
    res, err := p.conn.DirSync(req, ldap.DirSyncObjectSecurity, 1000, p.cookie)
    if err != nil {
        return nil, err
    }
    p.cookie = res.Controls[0].(*ldap.ControlDirSync).Cookie
    p.storeCookie()  // persist to DB; loss of cookie requires full resync
    return mapEntries(res.Entries), nil
}
```

DirSync includes deleted objects (tombstones) automatically when the filter matches them. Tombstones retain only `objectGUID`, `isDeleted: TRUE`, and a few system attributes. The sidecar MUST map `isDeleted: TRUE` to `TERMINATE`.

**Cookie persistence.** The DirSync cookie MUST be persisted to durable storage (the same database as the DID logs). Loss of the cookie (for example, after a crash) requires a full resync: the sidecar fetches all objects and diffs against stored state.

### 6.4 Service Account Requirements

**For USNChanged:**
- `List Contents` on the target OU
- `Read All Properties` on user objects in the OU
- `List Contents` on `CN=Deleted Objects,DC=...`
- `Read All Properties` on deleted objects

**For DirSync:**
- With `DirSyncObjectSecurity` (as in §6.3): `Read All Properties` on user objects under the base DN and on `CN=Deleted Objects,DC=...`. Attributes the account cannot read are silently omitted, so grant read on every attribute in `userAttributes`.
- Without that flag: the `DS-Replication-Get-Changes` extended right on the domain naming context root, delegated explicitly. This profile does not use that mode.

The service account MUST be a dedicated account in a dedicated OU with all interactive login rights stripped. The account password MUST be rotated at least annually and MUST be stored in a secrets manager (HashiCorp Vault, AWS Secrets Manager, or equivalent); it MUST NOT be stored in a config file.

### 6.5 Multi-Domain Forests

AD forests with multiple child domains require one LDAP connection per domain. The sidecar supports multiple LDAP targets:

```toml
[[ldap.domains]]
host    = "dc01.corp.example.com"
base_dn = "OU=Users,DC=corp,DC=example,DC=com"

[[ldap.domains]]
host    = "dc01.eu.example.com"
base_dn = "OU=Users,DC=eu,DC=example,DC=com"
```

Each domain runs its own polling goroutine with its own cursor. `objectGUID` is globally unique across domains within a forest, so user records from different domains cannot collide in the sidecar's user registry.

If a Global Catalog is available and the operator prefers a single connection point for the whole forest, the sidecar MAY query the GC on port 3268. In this case, the USNChanged connector MUST be used, because DirSync cannot detect change events in sub-domains through the Global Catalog.

---

## 7. JML Source Composition

When `jml_source.type` is not `none`, the sidecar runs both the identity provider and the JML source concurrently, deduplicating events by the user's `stableID` and timestamp. This covers Cat 3 (SAML authentication with a separate JML source). It also applies to Cat 4 (LDAP for fast change detection, HR system as the authoritative source for hire and terminate decisions).

**Normalized lifecycle mapping.** Every source maps to the actions of §2 as follows. Termination is `TERMINATE` and nothing else: only a hard delete or an HR termination produces it. Disable, deactivate, and leave signals produce `SUSPEND`, which is reversible.

| Source | `PROVISION` | `UPDATE` | `SUSPEND` | `REACTIVATE` | `TERMINATE` |
|---|---|---|---|---|---|
| Okta (§3.2) | `user.lifecycle.create`, `user.lifecycle.activate` | `group.user_membership.add/remove` | `user.lifecycle.deactivate`, `user.lifecycle.suspend` | `user.lifecycle.unsuspend` | `user.lifecycle.delete` |
| JumpCloud (§3.3) | `user.create` | `user.update`, `group.member.add/remove` | `user.update` with account suspended | `user.update` with account unsuspended | `user.delete` |
| PingOne (§3.4) | `USER.CREATE` | `USER.UPDATE`, `ROLE.USER_ROLE_ASSIGNMENT_*` | `USER.UPDATE` with `enabled: false` | `USER.UPDATE` with `enabled: true` | `USER.DELETE` |
| OneLogin (§3.5) | user created | user updated, role assigned (4), role removed | user deactivated | user activated, user reactivated | user deleted |
| SCIM server (§4.2) | `POST /Users` | `PUT/PATCH /Users`, `/Groups` | `active: false` | `active: true` (was `false`) | `DELETE /Users` |
| SCIM client (§4.3) | new user in poll | changed attributes | `active: false` | `active: true` (was `false`) | user absent from full sync |
| Workday (§5.2) | `HIRE` | `TRANSFER`, `POSITION_CHANGE` | `LEAVE_OF_ABSENCE` | `RETURN_FROM_LEAVE` | `TERMINATE` |
| BambooHR (§5.3) | new `Active` record | department or title change | (not inferred) | (not inferred) | `Inactive` with `terminationDate` |
| SFTP batch (§5.4) | new record | column change | `Active` → `OnLeave` | `OnLeave` → `Active` | → `Terminated` |
| Manual (§5.5) | `/v1/provision` | `/v1/update-claims` | `/v1/suspend` | `/v1/reactivate` | `/v1/tombstone` |
| AD LDAP (§6) | new object | attribute change | `ACCOUNTDISABLE` set | `ACCOUNTDISABLE` cleared | object deleted |

**Deduplication.** If the same user receives the same action from two sources within a 60-second window, the second action is a no-op. If two sources disagree within that window, the more restrictive action wins, in the order `TERMINATE` > `SUSPEND` > `UPDATE` > `REACTIVATE` > `PROVISION`. Because `TERMINATE` is final (§2), no later event from any source reverses it.

For example, a Workday `TERMINATE` always overrides a concurrent LDAP `REACTIVATE`, which may reflect DC replication lag. Manual IT operations are exempt from deduplication: they are applied immediately and logged with a `manual-override` flag.

---

## 8. Enrollment Authentication

Device key registration follows spec §2.5.4: the Agora client authenticates the user against the organization's IdP by OIDC or SAML 2.0 and sends the resulting token as `idpToken` in a `DeviceKeyRegistrationRequest` to `POST {prov}/devices`. This profile sets `{prov}`, the `AgoraProvisioning` service endpoint (spec §2.5.3), to `https://did.example.com/v1`, so the path is `POST /v1/devices`. The new device key signs the request. For every device after the first, a currently registered device key also signs it (spec §2.5.4 Step 3). Once the key is in the log, the new device publishes KeyPackages to the sidecar and the user's existing devices add it to the user's self-group and to each of the user's groups (spec §2.5.4 Steps 6 and 7, §2.6). No separate enrollment tool is involved. (The enrollment tool in `profiles/discord-onboarding.md` serves individuals migrating from Discord and is not used in employer deployments.)

The sign-in protocol and the JML source are independent configurations. An org MAY use SAML for sign-in while LDAP drives JML. The sidecar links the sign-in token to the user record by the IdP's immutable user ID, never by email, UPN, or `userName`, which can change (spec §2.5.2):

| Sign-in | Token claim used | Must equal the user record's `stableID` source |
|---|---|---|
| Okta OIDC | `sub` (Okta user `id`) | Okta `id` (Cat 1) or SCIM `externalId` populated with it (Cat 2) |
| Entra OIDC | `oid` | Entra `objectId` (O365 spec) |
| Generic OIDC | `sub` | The directory's immutable ID that the issuer places in `sub` |
| SAML 2.0 | `NameID` with format `persistent`, or an attribute carrying the immutable ID (for example `objectGUID` for AD FS) | AD `objectGUID` (Cat 4) or the HR `employeeId` (Cat 3) |

The operator MUST configure the IdP to emit a claim that matches the `stableID` source of the configured `IdentityProvider` or JML source. If no such claim is available, the sidecar MUST refuse to register device keys for that configuration rather than fall back to email matching.

---

## 9. Signing Key Options

The self-issued `EmployeeCredential` requires the org to hold an Ed25519 signing key, and the sidecar signs DID log entries with its update key (§1). The sidecar holds three distinct Ed25519 keys: the VC issuer key (`signing_key_*`), the `did:webvh` update key (`update_key_*`), and the provisioning signing key (`provisioning_signing_key_*`), as in Google Workspace spec §7. The issuer key is separate from the update key, so it confers no authority over any employee's DID log. Each key is configured independently and can use any of the following backends:

| Backend | `*_key_type` value | Notes |
|---|---|---|
| File (PEM) | `file` | Key on disk; operator is responsible for backup and rotation. Acceptable for lab/pilot only. |
| AWS KMS | `awskms` | HSM-backed; key ARN in config; uses `aws-sdk-go-v2` |
| Google Cloud KMS | `gcpkms` | As in the Google Workspace spec |
| Azure Key Vault | `azurekv` | As in the O365 spec |
| PKCS#11 (HSM) | `pkcs11` | On-prem HSM (Thales, SafeNet, YubiHSM) via `miekg/pkcs11` |
| HashiCorp Vault | `vault` | Vault Transit secrets engine; key never leaves Vault |

For on-prem deployments (Cat 3 and Cat 4), the PKCS#11 and HashiCorp Vault backends SHOULD be used.

---

## 10. Deployment Topologies

| Category | Network Requirement | Recommended Topology |
|---|---|---|
| Cat 1 (Okta/JumpCloud) | Public HTTPS endpoint for webhook receipt | Cloud-hosted (AWS, GCP, Azure, Fly.io) |
| Cat 2 (SCIM server mode) | Public HTTPS endpoint for SCIM push receipt | Cloud-hosted |
| Cat 2 (SCIM client mode) | Outbound HTTPS to SCIM server | On-prem or VPN-accessible |
| Cat 3 + HR webhook | Public HTTPS endpoint for HR system webhook | Cloud-hosted with VPN or private link for AD access |
| Cat 3 + SFTP batch | Outbound SFTP to HRIS server | On-prem or co-located |
| Cat 4 (LDAP) | Outbound LDAPS to domain controller (port 636) | On-prem, or cloud with VPN/Direct Connect |

For hybrid deployments (Cat 3 + Cat 4: SAML auth from cloud IdP, LDAP from on-prem AD), the sidecar runs on-prem with a reverse proxy exposing only the public endpoints to the internet. The LDAP connection remains on the internal network.

```
Internet → [Reverse Proxy] → /v1/devices              (device enrollment, spec §2.5.4)
                           → /v1/revocations          (user-initiated device revocation, spec §2.5.5)
                           → /v1/notify               (IdP webhook)
                           → /v1/hr-event             (HR webhook)
                           → /users/*/did.jsonl       (DID log serving)
                           → /v1/agora/kp/*           (KeyPackageEndpoint, spec §5.2.1.1: fetch, publish, Welcome, auth)
                           → /v1/agora/admission-key/* (DM and self-group admission keys, spec §4.6; O365 spec §6.7)
                           → /auth                    (member authentication for admission keys, spec §3.5)

Internal only:
  LDAP polling  → DC on port 636
  DB            → PostgreSQL on internal network
  Signing key   → on-prem HSM via PKCS#11
```

---

## 11. Implementation Additions to Shared Codebase

New `IdentityProvider` implementations added to the shared Go binary:

```go
// Cat 1
type OktaProvider      struct { ... }
type JumpCloudProvider struct { ... }
type PingProvider      struct { ... }
type OneLoginProvider  struct { ... }

// Cat 2
type SCIMServerProvider struct { ... }   // sidecar acts as SCIM endpoint
type SCIMClientProvider struct { ... }   // sidecar polls upstream SCIM

// Cat 3: no IdentityProvider; SAML sign-in at device registration (§8), JML from a JMLSource.

// Cat 4
type LDAPProvider struct {
    mode   string  // "usnchanged" | "dirsync"
    conn   *ldap.Conn
    cursor int64   // USNChanged: last processed USN
    cookie []byte  // DirSync: opaque cookie
}
```

New `JMLSource` implementations:

```go
type WorkdayJMLSource   struct { ... }
type BambooHRJMLSource  struct { ... }
type SFTPBatchJMLSource struct { ... }
type ManualJMLSource    struct { ... }  // no-op source; admin API is the trigger
type LDAPJMLSource      struct { ... }  // same as LDAPProvider, used when IdP is SAML-only
```

New library dependencies:

| Function | Library |
|---|---|
| LDAP (DirSync + USNChanged) | `github.com/go-ldap/ldap/v3` |
| SCIM server | `github.com/elimity-com/scim` |
| SFTP client | `github.com/pkg/sftp` |
| AWS KMS | `github.com/aws/aws-sdk-go-v2/service/kms` |
| HashiCorp Vault | `github.com/hashicorp/vault/api` |
| PKCS#11 | `github.com/miekg/pkcs11` |

---

## 12. Open Questions

1. **Okta event hook delivery guarantees.** Okta event hooks are asynchronous and best-effort. The System Log API reconciliation poller covers missed events but has up to 24-hour latency. Regulated organizations requiring sub-minute termination enforcement should also call `POST /v1/tombstone` directly when terminating an employee rather than relying solely on the Okta hook.

2. **SCIM Groups vs. flat role attributes.** Some IdPs encode roles as user profile attributes rather than group membership. The sidecar's SCIM implementation supports both patterns, but the role derivation configuration must explicitly specify which is in use rather than auto-detecting.

3. **AD multi-forest trust.** This profile covers multi-domain single-forest scenarios. Multi-forest trust relationships are not addressed. Each forest requires its own sidecar deployment with its own DID namespace; cross-forest enrollment uses the SAML adapter for authentication with the appropriate forest's LDAP as the JML source.

4. **Workday RaaS vs. Studio.** Workday supports both Report-as-a-Service (no coding required) and Studio (full EIB, more control) for outbound data. This profile does not prescribe which Workday integration type to use; the operator's Workday administrator selects based on existing expertise. The sidecar endpoint accepts the same payload regardless of which mechanism produces it.

5. **Air-gapped deployments.** A sidecar in a fully air-gapped environment cannot receive webhooks from cloud IdPs. The sidecar may operate in a fully internal mode, serving DID logs and KeyPackages only on the internal network under an internal-only domain, with the relays also internal. This eliminates cross-org federation. It is an explicit architectural trade-off for non-discoverable deployments (spec §10.1.1).
