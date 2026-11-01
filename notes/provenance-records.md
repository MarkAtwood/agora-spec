# Provenance Records: Exploration

Status: exploration for bead agora-gnaz, 2026-10-31. Not a decision. Nothing here
changes the spec or the JMAP drafts.

## Recommendation

Do it as a **JMAP Graph application profile**, not a new standalone type, and
**park it until a concrete user appears** (an agent-memory deployment, or interop
with OpenVTC/Keyring). When it is picked up it is one small companion draft
(`draft-atwood-jmap-graph-provenance`, owner's call per D5) plus one Agora
§14.6 profile section for Graph and its provenance profile.

Why a Graph profile: `draft-atwood-jmap-graph-00` already defines `GraphNode`
and `GraphEdge` with no semantics and leaves "application profiles" to future
documents (graph-00 Scope). A provenance record is a node; its evidence is
edges. The family's extension rule (PROJECT.md: new data goes in its own
capability using existing extension points) favours a profile over a new type.

## What DTG rooms do (the source)

From `specs/rooms/_shared/0.2/room.schema.json`, `records/put/0.4`,
`records/curate/0.1`, `records/prune/0.2`, `retention/set/0.1` in
`trustoverip/dtgwg-trust-tasks-tf`:

- **Record:** `key`, room-wide monotonic `version`, `updatedAt`, `status`
  (`active` | `deprecated` | `retracted`), `pinned`, `author`; sealed body with
  `title`, `description`, markdown `body` ("rendered inert"), `tags`, one
  `file`.
- **Provenance:** `basis` enum (`declared`, `observed`, `verified`,
  `inferred`); `confidence` 0..1, the author's own estimate, never ranked
  across authors, absent never means 1; `evidence` list of 1 to 32 typed
  references (`record` key/version, or `credential` id/digest), "a reference,
  never a locator, never proof", readers MUST NOT fetch it; `validFor`
  (purposes as DPV IRIs, plus a note that is "never instructions");
  `validUntil`, which hides from listing and agent recall but does not delete.
- **Curation:** separate `curate` grant, not implied by `write`.
  `deprecated` keeps the body; `retracted` drops it to a tombstone and is
  irreversible; `pinned` is independent of status.
- **Retention:** `recordDays` and `tombstoneDays` by age from `updatedAt`;
  pinned records exempt; prune leaves a marker with a count that forces
  caches to rebuild.
- **Concurrency:** compare-and-set by `expectedVersion`; no history kept.
- **Signing:** `eddsa-jcs-2022` Data Integrity proof by the author over the
  body, bound to room, key, and version.

## Mapping to Agora and the JMAP family

| Rooms concept | Proposed mapping | Notes |
|---|---|---|
| Record | `GraphNode` with the profile's extension properties | Content in `blobId`/`mediaType` or an inline body property |
| `basis`, `confidence`, `validUntil`, `validFor` | Extension properties on `GraphNode`, defined by the profile | Typed properties, not `annotations` strings: annotations are `String[*]` and would need parsing |
| `evidence` `kind: record` | `GraphEdge` of a profile-defined type (`evidence`) to the cited node | Evidence becomes ordinary graph structure: queryable, and it survives without a new reference format |
| `evidence` `kind: credential` | Edge or property carrying a digest of the credential's exact bytes | Agora signs and hashes exact bytes (D1), so no JCS form |
| `status`, `pinned`, `reason` | A separate curation property written under `sequenced-v1` by holders of a `curate` permission | Mirrors `Chat.pinnedMessageIds` (§14.2.3), which is written by holders of `pin` |
| Content edits | `single-author` by the node's author, per-property last-writer-wins (§14.3.3) | A Space can select `sequenced-v1` for shared editing, as for `Task` |
| `version`, `expectedVersion` | JMAP `state`, `/changes`, `ifInState` | Already in RFC 8620; no new mechanism |
| History | JMAP-OBJ-HISTORY (`includeReplaced`/`includeDestroyed`), as chat-00 notes for Message | Rooms keep none; JMAP can if a deployment wants |
| Retracted tombstone | `destroyed` plus a tombstone like Message `deletedAt` | Irreversible, as in rooms and chat-00 |
| Retention by age | Same pattern as `Chat.messageExpirySeconds`: enforced locally by each member store | No server enforces it on Agora; CO archive keeps its own retention |
| Author `proof` | Not needed in-group: MLS authenticates the sender of every application message | Records exported outside the group carry a detached JWS (D6), not Data Integrity |

## What to keep from rooms

- The `basis` enum, including `inferred` for model output. It is the most
  useful single idea: it lets a reader tell a person's statement from an
  agent's guess.
- Confidence as the author's own estimate, with the "never rank across
  authors" and "absent is not 1" rules.
- Evidence as references, never locators: readers do not fetch what a record
  cites. This closes an exfiltration and SSRF path for agents.
- Body and notes are data, never instructions, for any agent that reads them.
  This is a security rule (prompt injection), so it can be a MUST under
  agora-ux-musts: it constrains machine behaviour, not display.
- `validUntil` hides; it does not delete.
- Curation separate from writing, with its own permission.

## What not to take

- Owner as sole committer: Agora lets any permitted member write.
- Host-side compare-and-set as the only ordering: Agora uses its consistency
  models (§14.2).
- JCS and Data Integrity signing of bodies: Agora signs exact bytes (D1, D6).
- Room tiers (`open`, `attributed`, `private`): an Agora channel is already
  sealed, and relays never learn the author on any channel.

## Cost

- Owner: one companion draft defining the profile's extension properties,
  edge type, curation property, and capability URN.
- Agora: one §14.6 section profiling Graph and the provenance profile, plus
  rows in the §14.2.3 table. This is a small core addition, not zero: Graph
  is not yet profiled in §14.6.
- No change to MLS, relays, Space state structure, or ARCHITECTURE.md, except
  a `curate` permission alongside `pin` (§5.2.6).

## Open questions

- Whether the use case is real for Agora's first ship, or only for agent
  deployments. Without a user, this stays parked.
- Whether to align field names and enum values exactly with DTG rooms so a
  gateway can map records one-to-one. Exact alignment is cheap now and
  expensive later.
- Whether inline body text belongs on `GraphNode` or always in a blob.
