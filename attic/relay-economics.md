# Agora Protocol: Relay Economics (removed from shipping spec)

> Binds: n/a. Verbatim from `import/agora-protocol-spec-unified.md` lines 2995–3053, 3134–3187, 3208–3222 (§12.1, §12.3, §12.5). Section numbers are the source's and will be renumbered.

### 12.1 Payment Rails

#### PaymentPointer

All payment destinations in Agora are expressed as a `PaymentPointer` — an abstract type carrying a rail identifier and a rail-specific address. The protocol is not coupled to any single payment network; new rails can be registered via the Agora extension namespace.

```json
{
  "@type": "PaymentPointer",
  "scheme": "cashu",
  "address": "https://mint.example.com"
}
```

**Defined rails:**

| Rail | Network | Best for | Notes |
|---|---|---|---|
| `cashu` | Cashu ecash over Lightning | High-frequency micropayments | Chaumian blind tokens — mint cannot link issuance to redemption; bearer instrument, works offline |
| `bolt12` | Lightning Network | Service agreements, larger settlements | Reusable offers; routing reliability degrades for sub-sat amounts |
| `bolt11` | Lightning Network | Single-use invoice fallback | Use only when the counterparty cannot receive BOLT 12 |
| `pow` | Hashcash-style PoW | Spam deterrence, no payment | No money changes hands; see §12.4 |

Implementations that opt into micropayments MUST support at least one defined payment rail. `bolt12` SHOULD be supported for service agreements. `pow` is not a payment rail — it is a spam-deterrence alternative that requires no payment infrastructure; any implementation MAY support it independently.

#### Signed Bearer Tokens

Several of the defined rails — and any future rails following the same pattern — are instances of the **signed bearer token** model: a self-contained object, signed by an issuer, that proves entitlement to value or access by possession alone. Whoever holds the token can spend or present it; no live connection to the issuer is required at redemption time.

`cashu` is the primary example: a Cashu mint blindly signs tokens at issuance so it cannot link issuance to redemption; the token is the value, transferable by passing the object. Lightning payment preimages (`bolt12`/`bolt11`) are also bearer proofs — once a payment is made, the preimage proves it happened and can be presented to any verifier.

This pattern extends naturally to:

- **Pre-issued relay credits** — a relay signs a batch of credit tokens at purchase time; the client spends them per-message without any live payment network involvement. Useful for air-gapped or intermittently connected deployments.
- **Access tokens** — pay once via any rail, receive a signed token granting access to a channel or tier. The token is redeemable without re-contacting the payment network.
- **Game and application currency** — application-layer tokens signed by a trusted issuer (a game operator, a DAO, a relay cooperative) and redeemable within a defined scope.

New rails following the signed bearer token pattern MAY be registered in the Agora extension namespace using the rail identifier `bearer-<issuer-defined-name>`. The `PaymentPointer.address` for such rails is the issuer's verification endpoint or public key reference.

**x402 and L402.** x402 (HTTP 402 Payment Required) and its Lightning-specific predecessor L402 are standard HTTP handshake protocols for *obtaining* signed bearer tokens via payment. They sit above the payment rails, not beside them: a client requests a resource, receives an HTTP 402 response carrying payment terms (amount, rail, payment address), makes the payment via any accepted rail, and retries with a payment proof header. The server validates the proof and returns a signed bearer token granting access for a session or quota. x402 and L402 define the request/response handshake; the underlying value transfer uses an existing rail (`cashu`, `bolt12`, etc.). They are therefore a natural fit for automated and machine-to-machine access — including autonomous agents paying for relay services without human intervention.

#### SpaceTreasury

A Space MAY declare a treasury — a payment destination that receives a fraction of message fees and relay fee-sharing. The treasury is a `PaymentPointer` in the Space state document:

```json
"treasury": {
  "@type": "SpaceTreasury",
  "paymentPointers": [
    { "@type": "PaymentPointer", "scheme": "cashu",  "address": "https://mint.example.com" },
    { "@type": "PaymentPointer", "scheme": "bolt12", "address": "lno1pg..." }
  ],
  "description": "wolfSSL Dev infrastructure fund",
  "feeShareBps": 1000
}
```

`feeShareBps` is the basis points (0–10000) of relay service agreement revenue the Relay is expected to route to the treasury. Enforcement is by Relay selection — Space owners choose Relays that honor their declared fee-share terms.

### 12.3 Message Micropayments

Micropayments attach a small fee to individual message delivery. Purposes: Relay revenue for public traffic, and spam deterrence.

Micropayments are **optional and channel-scoped** via `messageFeePolicy` in the channel state document:

```json
"messageFeePolicy": [
  {
    "@type": "MessageFeePolicy",
    "scheme": "cashu",
    "feeAmount": "1",
    "feeDenomination": "sat",
    "relayShareBps": 7000,
    "spaceShareBps": 2000,
    "freeMessageQuota": 100,
    "senderRefundOnReply": true
  },
  {
    "@type": "MessageFeePolicy",
    "scheme": "pow",
    "difficulty": 18
  }
]
```

`relayShareBps` + `spaceShareBps` MUST sum to ≤ 10000. The remainder is burned to a provably unspendable address. `senderRefundOnReply`: if a recipient replies to a message, the sender's fee is refunded — a social mechanic incentivizing content worth responding to. `freeMessageQuota` is the number of messages per MLS epoch a member may send without payment.

#### Payment Flow

When a channel requires payment, the sending client attaches a `MessagePayment` to the outer `RoutingEnvelope` before submission:

```json
{
  "@type": "MessagePayment",
  "scheme": "cashu",
  "relayPaymentProof": "base64url...",
  "spacePaymentProof": "base64url...",
  "ts": "2026-03-12T12:00:00.000Z"
}
```

Both payments are made before submitting the envelope. The Relay verifies only its own payment proof before forwarding:

```
Sender
  ├── relayShareBps × feeAmount → Relay payment pointer
  └── spaceShareBps × feeAmount → Space treasury pointer
```

For `cashu`: `relayPaymentProof` is a spent-token proof presented to the Relay's trusted mint list. For `bolt12`/`bolt11`: it is a Lightning payment preimage.

The Relay tracks free quota consumption per `channelToken` per epoch. Space admins may grant extended free quotas to specific roles via a signed `QuotaGrant` message gossiped to the channel topic.

### 12.5 End-to-End Payment Flow Summary

| Direction | Mechanism | Purpose |
|---|---|---|
| Space owner → Relay | `RelayServiceAgreement` recurring payment | Reliable relay service, history retention, SLA |
| Relay → Space treasury | Fee-share from service agreement revenue | Community sustainability fund |
| Message sender → Relay | `MessagePayment` proof-of-payment | Relay revenue for public traffic, spam deterrence |
| Message sender → Space treasury | `MessagePayment` proof-of-payment | Community fund, spam deterrence |
| Message sender → (none) | `PowProof` | Spam deterrence only, no revenue |

All flows are optional. A self-hosted zero-fee deployment uses none of them. A large public space with anonymous users may use all of them simultaneously across different channels.


---

