# OpenVTC ideas considered for Agora

Status: decision record, 2026-10-17. Non-normative. Sources are public: the
Trust over IP DTG working group repositories and trusttasks.org.

## 1. Durations from signed timestamps (decision A: no change)

OpenVTC Trust Ceremonies check `maxDuration` against signed `issuedAt`
values, never the current time, so a flow completed offline stays valid when
it syncs late.

Agora already covers this:

- Spec §12.9 names whose clock judges every time check and sets the skew
  tolerances.
- The guardian transfer (§4.1) measures its objection period from its own
  signed `ts`, which is the same pattern.

No Agora flow completes offline and validates later. Joining needs a live
adder, a KeyPackage, and the Space endpoint. The radio-mesh gateway profile
bridges messages, not admission. A general rule would have nothing to apply
to.

## 2. Owner lapse, successor, and reclaim (decision A: one sentence)

OpenVTC data rooms lapse to read-only, become reclaimable after a retention
period set at creation, let the owner name a successor, and let renewal
defeat a pending claim.

Agora's guardian transfer already covers each part:

| OpenVTC | Agora |
|---|---|
| Named successor | `guardian` with one DID and `threshold` 1 (§3.3, §4.1) |
| Reclaim after a retention period | Guardian transfer after `delaySeconds`, set in the genesis state |
| Renewal defeats a pending claim | The owner's objection wins (§4.1 step 2) |
| Read-only | Archival (§3.6) |

Spec §4.1 now says so in one sentence. An automatic inactivity lapse was
rejected: "inactive" is not reliably observable without the CO watching the
owner, and a guardian makes the same call with a human decision.

## 3. In-person verification (decision A: profile)

Written as `profiles/in-person-verification.md`.
