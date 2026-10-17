# Profile: Compliance Chain Witnessing

> Non-normative. Capitalized BCP 14 key words (RFC 2119, RFC 8174) in this profile state what a deployment that follows it requires of its own components; they bind only implementations that claim conformance to this profile and are not Agora protocol requirements, except where a sentence cites the spec or ARCHITECTURE.md as their source. Where this profile conflicts with the spec or ARCHITECTURE.md, those govern.

This profile is suggested practice for firms that run an Agora compliance
logger (spec §7). Publishing chain heads is a firm practice; the protocol
does not require it. This profile describes one consistent way to do it so
that examiners see the same evidence at every firm.

## 1. Why witness the chain

Each `ComplianceRecord` (spec §7.4) carries the sender's MLS message as
received, the keys that open only that message, the epoch's `GroupContext` and
the sender's leaf. A third party can therefore check that a device key of the
sender signed the archived plaintext without trusting the logger (spec §7.4,
"Third-party verification"). Those checks cover single records.

Each record also names the previous record by `prevRecordCID`, so altering,
inserting or deleting a record in the middle of a chain breaks every link after
it. The chain proves internal consistency. It does not prove that today's chain
is the chain that existed last month: whoever controls the archive could
rewrite everything after some point, or cut off the end, and the result would
still verify.

Closing that gap takes a witness outside the firm that saw a fingerprint of the
archive at the time. If the firm deposits fingerprints regularly with an
independent party, any later rewrite or truncation contradicts a fingerprint the
firm cannot recall. This is the property non-rewritable record rules such as
SEC Rule 17a-4 aim at.

## 2. The chain-head record

At each witnessing point the logger produces a `ComplianceChainHead` record.
The record is carried as a typed envelope (spec §13.1) with type
`urn:agora:practice:ComplianceChainHead` and content type `application/json`.
The logger DID signs it per spec §13.1.1.

```json
{
  "loggerDID": "did:webvh:QmSCID...:compliance.example.com:logger",
  "indexCID": "bafkrei...",
  "recordCount": 1834201,
  "ts": "2026-10-16T00:00:00Z",
  "reason": "scheduled",
  "prevHeadCID": "bafkrei..."
}
```

- `indexCID` is the CID of the Space-level index (spec §7.4), which names the
  head of every channel's chain. One CID commits to the whole archive.
- `recordCount` is the total number of records under the index.
- `reason` is one of `scheduled`, `prune`, `legal-hold` or `key-rotation`.
- `prevHeadCID` is the CID of the previous `ComplianceChainHead` envelope, so
  the heads form their own chain and a missing head is visible.

The record carries no channel names, member identities or content. A witness
learns that a firm's archive had a given fingerprint at a given time, and
nothing else.

## 3. When to produce one

The logger produces a head at each of these points:

- At least once a day
- Immediately before retention pruning removes records (`reason: prune`), so
  that lawful pruning is distinguishable from deletion (see §5)
- When a legal hold begins (`reason: legal-hold`)
- When the logger's signing key rotates (`reason: key-rotation`)

The logger signs a `key-rotation` head with the outgoing key while that key is
still in the logger's DID document. Under spec §7.9 the Communications Operator (CO) adds the new key to
the logger's DID document before removing the old one, so the head falls inside
that overlap.

## 4. Witnesses

The firm deposits the SHA-256 hash of each signed `ComplianceChainHead`
envelope with at least one independent witness it does not control, and keeps
the witness's receipt next to the record.

| Witness | Receipt | Notes |
|---|---|---|
| RFC 3161 timestamping authority | `TimeStampToken` | Suggested baseline. Widely available, recognized by auditors and verifiable offline. Use a TSA operated outside the firm. |
| The firm's designated third party or WORM custodian under its record-keeping rules | Custodian acknowledgement | Fits firms that already retain a third party for SEC 17a-4 or similar. |
| A public append-only transparency log | Inclusion proof | Lets anyone verify without contacting the firm. Only the hash is published. |

Using two witnesses of different kinds removes reliance on any single one.
Blockchain anchoring is outside this profile.

## 5. Pruning and legal hold

Retention pruning removes records lawfully, which changes `indexCID`. To keep
pruning distinguishable from tampering:

1. Witness a `prune` head before removing anything.
2. Append a prune record to each affected chain. A prune record is a typed
   payload envelope of the practice type
   `urn:agora:practice:CompliancePruneRecord` (spec §13.1). The logger DID
   signs it, and it links by `prevRecordCID` like any record. It names the
   pruned range (first and last record CID removed), the retention rule
   applied and the `prune` head's CID. A prune record is not a
   `ComplianceRecord`. It has no sender, so the per-message checks of
   spec §7.4 do not apply: verifiers exempt it from the sender check and
   check the logger signature and the chain link instead.
3. Witness the next scheduled head as usual.

An examiner then sees a witnessed head, a signed statement of what was removed
and why, and a later witnessed head that extends from the statement.

While a legal hold is in force, the firm does not prune the held chains.

## 6. How an examiner verifies

1. Obtain the series of `ComplianceChainHead` envelopes and their witness
   receipts for the period under review.
2. Verify each receipt with its witness (for RFC 3161, verify the
   `TimeStampToken` against the TSA certificate and the envelope hash).
3. Verify each envelope's JWS against the logger DID, and check the
   `prevHeadCID` links for gaps.
4. For the archive as produced, recompute the Space-level index and each
   channel chain, and verify sampled records by the third-party procedure of
   spec §7.4 (`guides/regulators.md`). Verify each record's signature against
   the logger DID document version in effect when it was signed, which the
   DID log preserves across key rotation (spec §7.9). Where an archive object
   was re-sealed after an archive-key compromise, an `ArchiveResealEntry`
   maps the CID a record names to the object's new CID (spec §7.9).
5. Confirm that every witnessed `indexCID` is reachable from the current
   archive by appending records, with any differences explained by signed
   prune records. A witnessed head that the current archive cannot extend is
   evidence of rewrite or truncation.

## 7. Open questions

1. Whether a later revision should make chain-head witnessing normative for
   Spaces with compliance logging enabled.
2. Whether a per-channel head series, in place of one Space-level index, suits
   firms whose examiners request single channels.
