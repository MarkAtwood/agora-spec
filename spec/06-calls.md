# 6. Voice and Video

> Binds: both. Source: import/agora-protocol-spec-unified.md lines 2510–2919 (§10).


*Binds: both.*

Agora supports real-time group voice and video conferencing as a channel type. The design uses WebRTC for media transport, MLS-encrypted signaling for all control messages, and an optional SFU (Selective Forwarding Unit) for scalable multi-party sessions. Media never transits Relays.

## 6.1 Voice Channel Type

A channel with `"type": "voice"` is a VTC room. It has all the properties of a text channel (MLS group, channel CID, history) plus a persistent **call state**: a real-time record of who is currently in the call and their media states.

A voice channel is always "open"; there is no concept of starting or ending a call. Participants join and leave; the room exists as long as the channel exists.

**Transport constraints.** VTC requires UDP for ICE and media:

- **Clearnet or overlay (Tailscale, WireGuard):** Full VTC supported. Overlay networks provide ICE host candidates directly; NAT traversal is handled by the overlay.
- **Tor:** VTC is severely degraded. UDP is unavailable over Tor; only TURN-over-TCP paths are possible, adding 200–600ms latency. Clients operating in Tor-only mode SHOULD warn users before joining a voice channel and MAY disable VTC participation entirely.

## 6.2 Call State

Call state is ephemeral, gossip-propagated, and not stored in IPLD history. It is maintained as a set of `ParticipantState` records, one per active participant, gossiped on `v1/agora/channel/<channelToken>`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "ParticipantState",
  "sender": "did:key:z6Mk...",
  "channel": "agora://bafyrei.../voice/lounge",
  "status": "joined",
  "audioMuted": false,
  "videoEnabled": true,
  "screenSharing": false,
  "handRaised": false,
  "ts": "2026-03-12T12:00:00.000Z",
  "ttl": 15
}
```

`status` values: `joined`, `left`. A client whose `ParticipantState` has not been refreshed within `ttl` seconds is considered to have left. Clients MUST re-publish their state at least every `ttl / 2` seconds while in a call.

`audioMuted`, `videoEnabled`, `screenSharing`, and `handRaised` are advisory UI hints gossiped to other participants. They are not enforced at the media layer.

Call state events are delivered as MLS `PrivateMessage` application data, authenticated by the sender's MLS credentials and encrypted to the channel group. Relays and other IO components learn neither the sender nor who is in the call (ARCHITECTURE S1).

## 6.3 Join and Leave

**Join**: a client sends a `ParticipantState` with `status: "joined"` to the channel gossip topic, then initiates WebRTC negotiation with existing participants or the SFU.

**Leave**: a client sends `ParticipantState` with `status: "left"` and closes its WebRTC connections. Clients that disconnect without sending a leave message (crash, network drop) are timed out by other participants after `ttl` seconds.

Join and leave operations do NOT change MLS group membership. Being in the call means having an active `ParticipantState` with `status: "joined"` and live WebRTC connections.

## 6.4 Signaling

All WebRTC signaling (SDP offer/answer, ICE candidates) is delivered as `VoiceSignal` inner payloads, MLS-encrypted to the voice channel's group:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "VoiceSignal",
  "signalType": "offer",
  "targetDID": "did:key:z6MkTarget...",
  "sdp": "v=0\r\no=- ...",
  "candidates": [],
  "ts": "2026-03-12T12:00:00.000Z"
}
```

`signalType` values: `offer`, `answer`, `candidate`, `candidate-end`. `targetDID` is the intended recipient. All signals are broadcast to the channel MLS group; non-target recipients MUST ignore signals not addressed to them. `VoiceSignal` is used between participants only; signaling with an SFU, which is not an MLS member, uses the SFU endpoint (§6.6).

The consequences of MLS-encrypted signaling:
- **E2EE signaling**: Relays cannot read SDP or ICE candidates.
- **Authenticated signaling**: the MLS sender credential binds each signal to a verified DID.
- **Authenticated DTLS fingerprint**: the DTLS-SRTP fingerprint in the SDP is authenticated by the MLS signature, closing the identity binding loop: a participant's media stream is cryptographically bound to their DID (see §6.10).

## 6.5 Topology: Mesh vs SFU

**Mesh (≤4 participants, recommended)**: each participant establishes a direct WebRTC PeerConnection to every other participant. No SFU is required. Signaling is peer-to-peer via the MLS channel. Latency is minimized; bandwidth scales as O(n²).

**SFU (>4 participants, recommended)**: participants connect to a Selective Forwarding Unit which receives each participant's streams and forwards them selectively. Bandwidth scales as O(n). The SFU does not decode or re-encode media; it forwards RTP packets based on subscriber requests.

The threshold of 4 is a recommendation. Clients MAY negotiate mesh topology for larger groups if all participants have sufficient bandwidth and consent.

## 6.6 SFU Integration

### SFU Identity and Trust

An SFU is an IO component (ARCHITECTURE §2.3). It has a DID, but it MUST NOT be an MLS member of any channel group, and no client may add it to one. An SFU is admitted only by an `SFUDescriptor` entry in the CO-signed Space state document (ARCHITECTURE S4), which binds the SFU's DID to its endpoint. A participant's client MUST verify, before sending media, that the SFU it connects to is listed in current Space state and that the SFU's signaling messages are signed by the DID in that entry; any other SFU MUST be rejected. MLS secrets, exporter outputs and media E2EE keys (§6.9) MUST NOT be sent to an SFU.

### SFU Discovery

The Space owner (CO) publishes each admitted SFU's DID and WebRTC endpoint in the Space state document:

```json
"sfus": [
  {
    "@type": "SFUDescriptor",
    "did": "did:key:z6MkSFU...",
    "endpoint": "wss://sfu.example.com/v1/agora/sfu",
    "regions": ["us-west", "eu-central"],
    "maxParticipants": 500
  }
]
```

**Reference SFU implementations:** [`mediasoup`](https://mediasoup.org/) (Node.js/Rust), [`Pion SFU`](https://github.com/pion/ion-sfu) (Go), [`LiveKit`](https://github.com/livekit/livekit) (Go, open-source).

### SFU Signaling Flow

1. Client selects an `SFUDescriptor` from current Space state and opens a TLS WebSocket to its `endpoint`.
2. Client presents the MLS-membership access proof for the voice channel's `channelToken` (ARCHITECTURE §6.2). The SFU uses the `channelToken` as its room key and never learns the channel CID, Space, or any participant's DID.
3. Client sends its SDP offer; the SFU responds with an SDP answer signed by the SFU's DID key. The client verifies the signature against the DID in the `SFUDescriptor`.
4. ICE candidates are exchanged over the same connection.
5. DTLS handshake completes over the established ICE path; the fingerprint is the one carried in the signed SDP answer.
6. SRTP media flows, with SFrame-encrypted payloads (§6.9).

Participants map SFU-forwarded streams to DIDs using information exchanged among themselves in MLS-encrypted messages; the SFU sees only connection-scoped stream identifiers.

> **Open (agora-pozi.8):** the SFU admission proof in step 2 reuses the ARCHITECTURE §6.2 epoch access key and follows its resolution (Q1).

### SFU Media Opacity

The SFU terminates each client's DTLS-SRTP hop, so SRTP alone does not hide media from it. Media payloads sent through an SFU are therefore always SFrame-encrypted with keys the SFU does not hold (§6.9), and the SFU cannot read audio or video content. It CAN observe:
- Which connections are sending media (RTP SSRC → connection mapping, not → DID)
- Packet timing and sizes (traffic analysis)
- Whether a stream is active or silent

These fall within the IO observation budget (ARCHITECTURE §5, items 1–2).

### SFU Recording

An SFU MUST NOT be granted decryption rights for recording. Recording is performed by a CO-run recorder (§6.12), which may receive forwarded media from the SFU as an ordinary subscriber and decrypts it itself.

## 6.7 Simulcast and Bandwidth Adaptation

Clients SHOULD publish video in multiple simulcast layers (e.g., 1080p / 360p / 180p) to allow the SFU to forward the appropriate quality tier to each subscriber based on their available bandwidth. Layer selection is signaled via RTCP feedback from subscribers to the SFU.

For Scalable Video Coding (SVC) codecs (VP9, AV1), temporal and spatial scalability layers are used instead of discrete simulcast tracks. SFU implementations SHOULD support both simulcast (VP8, H.264) and SVC (VP9, AV1).

Audio is always single-layer. The SFU selects active speakers from the RTP audio-level header extension (RFC 6464), since media payloads are encrypted (§6.9), to forward only active speakers, with a configurable active-speaker window (default: 3 simultaneous speakers).

## 6.8 Screen Sharing

Screen sharing is a video track with a declared purpose. The sharing participant sets `"screenSharing": true` in their `ParticipantState` and adds a second video transceiver to their PeerConnection with a `content` attribute of `"screen"` in the SDP:

```
a=content:screen
```

Clients receiving a screen share track SHOULD display it distinctly from camera video. Multiple participants MAY share simultaneously; the SFU forwards all active screen share tracks.

Screen share tracks use a separate simulcast configuration from camera video: typically high resolution (up to 1080p or 1440p), low frame rate (5–15 fps).

## 6.9 End-to-End Encrypted Media

Because an SFU terminates DTLS-SRTP, it would see plaintext media without a second encryption layer, which would make it a CO component (ARCHITECTURE §2.3). E2EE media is therefore REQUIRED whenever media transits an SFU: clients MUST encrypt media payloads with SFrame (RFC 9605) via **WebRTC Insertable Streams** (W3C Encoded Transform) using participant-held keys, and MUST NOT send media to an SFU without it. In mesh topology, DTLS-SRTP is already end-to-end between participants and E2EE media is OPTIONAL.

In this mode:
- Each participant derives a media encryption key via the MLS exporter interface: `MLS-Exporter("agora-media-key", participantDID, 32)` (RFC 9420 §11.5).
- Outgoing media is encrypted by the sender's Insertable Streams transform before entering the RTP stack.
- The SFU forwards encrypted RTP packets opaquely.
- Each receiving participant's Insertable Streams transform decrypts using the sender's exported media key.

Media keys rotate with MLS epochs. A participant whose MLS leaf is removed loses their media key derivation capability for subsequent epochs. Media keys MUST NOT be disclosed to an SFU, TURN server, or any other IO component (ARCHITECTURE S3).

This mode requires browser/runtime support for Insertable Streams (available in Chromium-based browsers; partial in Firefox). It is declared in the channel state as `"e2eeMedia": true`, which MUST be set on any channel that uses an SFU. Clients that do not support Insertable Streams MUST NOT join a channel with `e2eeMedia: true` and MAY participate only in mesh calls.

## 6.10 DTLS-SRTP Identity Binding

WebRTC media is encrypted with DTLS-SRTP. The DTLS handshake uses a self-signed certificate; the certificate fingerprint is included in the SDP offer and answer. In standard WebRTC, this fingerprint is unauthenticated.

In Agora, the SDP carrying the fingerprint is delivered as a `VoiceSignal` inner payload, MLS-encrypted and signed by the sender's DID authentication key. Recipients verify the MLS signature before processing the SDP. This means:

- The DTLS fingerprint is authenticated by the sender's DID.
- A Relay or network attacker cannot substitute a different certificate without breaking the MLS signature.
- The media stream is cryptographically bound to the sending DID.

This closes the identity binding loop without requiring any PKI or certificate authority. The MLS group membership proof IS the identity assertion for media.

Through an SFU, the DTLS hop ends at the SFU, whose fingerprint is authenticated by its signed SDP answer and its `SFUDescriptor` (§6.6). Participant-to-participant binding is then provided by the SFrame keys (§6.9), which only current MLS members can derive.

## 6.11 TURN Server Integration

WebRTC ICE succeeds with direct peer connectivity in most cases but fails for participants behind **symmetric NAT**. TURN servers relay media packets between participants who cannot establish a direct path.

### TURN Server Identity

TURN servers are listed in the CO-signed Space state document (ARCHITECTURE S4):

```json
"turnServers": [
  {
    "@type": "TURNDescriptor",
    "uri": "turns:turn.example.com:5349",
    "credentialEndpoint": "https://turn-creds.acme.example/v1/agora/turn",
    "transport": "tcp",
    "regions": ["us-west", "eu-central"],
    "credentialScheme": "co-issued"
  }
]
```

`uri` follows the standard TURN URI format (RFC 7065). `credentialEndpoint` is the HTTPS URL of the CO credential service that issues credentials for this server (§6.11 TURN Credentials). A TURN server has no DID: it never signs anything a client verifies, and the TLS certificate of `uri` authenticates it. `turns:` (TLS) is required; `turn:` (plaintext) MUST NOT be used. A `TURNDescriptor` MUST NOT carry any shared secret or key from which TURN credentials can be computed.

**Reference implementations:** [`coturn`](https://github.com/coturn/coturn) is the standard open-source TURN/STUN server.

### TURN Credentials

TURN credentials (`credentialScheme: "co-issued"`) are short-lived RFC 8489 long-term credentials issued to members by a CO-run credential service, using the TURN REST pattern:

1. The TURN operator and the CO credential service share a secret. It is held only by those two parties and is never published.
2. A member requests credentials from the CO credential service at the descriptor's `credentialEndpoint`, which issues them only to current members of the Space.
3. The service returns `username = expiryUnixTime || ":" || randomNonce` and `password = HMAC(secret, username)`. The username MUST NOT contain a DID or any other persistent identifier.
4. The TURN server verifies the HMAC and the expiry without learning the client's DID or any persistent identity.

The TURN operator sees: a valid credential, a source IP, and opaque SRTP packets. It cannot link the session to a DID, channel, or space.

### ICE Candidate Priority

Clients MUST follow standard ICE candidate priority ordering:

1. Host candidates (direct LAN or overlay)
2. Server-reflexive candidates (STUN, public IP via NAT)
3. Peer-reflexive candidates (discovered during connectivity checks)
4. Relay candidates (TURN)

TURN candidates are only used if all higher-priority paths fail. Clients SHOULD include at least one TURN candidate in all offers to ensure connectivity for symmetric NAT participants.

### TURN Credential Distribution

TURN credentials are bearer tokens. Members MAY share them with other participants inside MLS-encrypted messages, and MUST NOT place them in the outer `RoutingEnvelope` or anywhere else an IO can read them.

TURN credentials MUST NOT be derived from MLS epoch secrets or exporter outputs: the TURN server would need the same value to verify them (ARCHITECTURE S3). Binding TURN access to membership is the job of the CO credential service, which issues only to current members.

## 6.12 Recording Grant Sub-Protocol

This section specifies the `RecordingGrant` mechanism referenced in §6.6: recorder admission and media access, participant disclosure and consent, the recording archive format, and compliance recording configuration.

There is no recording-specific key. The recorder is an MLS member of the voice channel's group and decrypts media exactly as any other member does: SRTP on its own DTLS hop (§6.10) and SFrame with exporter-derived media keys (§6.9). The `RecordingGrant` is the authorization and disclosure record for that membership; it carries no key material.

### 6.12.1 RecordingGrant Schema

A channel Admin or the Space Owner issues a `RecordingGrant` as an MLS application message to the voice channel's MLS group:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RecordingGrant",
  "channelCID": "bafyrei...",
  "grantedTo": "did:key:z6MkRecorder...",
  "grantedBy": "did:key:z6MkAdmin...",
  "scope": "audio-video",
  "purpose": "compliance",
  "retentionDays": 2555,
  "expiresAt": "2026-03-13T00:00:00Z",
  "participantDisclosure": "This call is being recorded for regulatory compliance by Acme Corp Compliance Archive.",
  "ts": "2026-03-12T12:00:00Z",
  "sig": "base64url..."
}
```

The grant is signed per §13.1.1 by `grantedBy`. Because only an Admin or Owner may issue it, it is a CO-signed record (ARCHITECTURE S4): recipients MUST verify that `grantedBy` holds the Admin or Owner role in current Space state and MUST ignore a grant that fails this check. The one exception is a grant whose `grantedTo` is the `vtcCompliance.recorderDID` of a Space in which `grantedBy` is a member and `vtcCompliance.enabled` is `true` (§6.12.5, §6.12.7): the CO-signed `vtcCompliance` block is then the authorization, and any member of that Space MAY issue the grant.

`grantedTo` is the DID of the recording principal. The recorder can derive media keys and produces plaintext, so it is a CO component (ARCHITECTURE §2.3) and MUST run under CO control (S8). Clients MUST NOT issue a `RecordingGrant` to, or add to a channel group as a recorder, a DID that appears in Space state as an SFU or relay, or as any other IO key. `scope` is `"audio-only"`, `"video-only"`, or `"audio-video"`. `purpose` is `"operational"` (ad-hoc recording by an admin) or `"compliance"` (regulatory retention obligation). `retentionDays` is the retention period the CO commits to for the archive (§6.12.4). `participantDisclosure` MUST be displayed to all channel participants before recording begins (§6.12.3).

A `RecordingRevoke` terminates the grant early:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "RecordingRevoke",
  "grantCID": "bafyrei...",
  "revokedBy": "did:key:z6MkAdmin...",
  "ts": "2026-03-12T14:00:00Z",
  "sig": "base64url..."
}
```

`RecordingRevoke` is signed per §13.1.1 by `revokedBy`, which MUST hold the Admin or Owner role in current Space state. Both `RecordingGrant` and `RecordingRevoke` are stored in the channel's IPLD history DAG, so the full grant and revocation history is permanently auditable.

### 6.12.2 Recorder Admission and Media Access

**Admission.** The issuer of a `RecordingGrant`, or another Admin or Owner, adds `grantedTo` to the voice channel's MLS group with an ordinary Add Commit using a KeyPackage from the recorder's `KeyPackageEndpoint` (§7.8.2), in the same epoch as, or before, the grant is sent. The recorder is a passive member (§5.2.1.3): it never issues Commits or Proposals.

**Media access.** The recorder joins the call (§6.3) as a receive-only participant and transmits no media. In SFU topology it subscribes through the SFU like any participant and removes SFrame (§6.9) with the senders' exporter-derived media keys; the SFU gains nothing (§6.6 SFU Recording). In mesh topology it is a mesh peer and decrypts SRTP on its own DTLS-SRTP connections (§6.10). No key is delivered to the recorder by any participant, and no participant action beyond normal call participation is required.

**Scope.** As a member, the recorder can technically decrypt every track in the call. `scope` is a CO obligation, not a cryptographic limit: the recorder MUST NOT store tracks outside `scope`.

**Grant end.** On a valid `RecordingRevoke` or when `expiresAt` passes, the recorder MUST stop recording. For an `"operational"` grant, the issuer (or, failing that, any Admin or Owner client that observes the grant end) MUST commit a Remove of the recorder's leaf; the recorder then cannot derive media keys for later epochs. A compliance recorder declared in `vtcCompliance` (§6.12.5) remains a member for as long as `vtcCompliance.enabled` is `true`.

**Epoch gaps.** The recorder can capture only media it receives while it is in the call. Epochs of an active call during which it captured no media are recorded as `epochsGapped` in the `VTCComplianceAuditEntry` (§6.12.6).

### 6.12.3 Participant Disclosure and Consent

Before recording begins, participating clients MUST display the `participantDisclosure` string from the `RecordingGrant` as a non-dismissable system message in the voice channel's text feed and as a visible indicator in the call UI. The indicator MUST persist for the full duration of the grant. Clients MUST also show the indicator whenever the channel group contains a leaf for the `vtcCompliance.recorderDID` of the Space.

A participant who joins a voice channel where a `RecordingGrant` is already active MUST be shown the disclosure immediately on join, before their audio or video is transmitted. Their client MUST NOT enable media transmission until the disclosure has been rendered.

**Consent model.** Recording is channel-level state, not a per-participant choice. Media keys are group-wide (§6.9), so a recorder that is a member can decrypt every participant, and the protocol does not offer per-participant exclusion. Consent depends on the grant's `purpose`:

- **Compliance grants** (`"purpose": "compliance"`). Recording is mandated for regulated members and cannot be vetoed. Consent is expressed by transmitting media after the disclosure is shown. A participant who does not consent MUST be able to remain muted with camera off, or leave.
- **Operational grants** (any other `purpose`). Each participant's client MUST obtain an explicit affirmative acknowledgement from its user before transmitting that user's media while the grant is active. A participant who declines remains in the call with media off. One participant's refusal does not stop the recording of others.

In either case, clients MUST NOT transmit a participant's media automatically on join while a grant is active.

The grant governs CO recording only. Any member can capture media it receives by other means; the protocol cannot prevent this.

For compliance grants (`"purpose": "compliance"`), the disclosure MUST include the `loggerLabel` from the space's `ComplianceLoggingConfig` and the grant's `retentionDays`:

> **This call is being recorded for regulatory compliance by [loggerLabel] and retained for [retentionDays] days.**

### 6.12.4 Recording Archive Format

The recorder writes each recording to CO-controlled storage (ARCHITECTURE S8) and records its metadata as a `VTCComplianceRecord`:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "VTCComplianceRecord",
  "grantCID": "bafyrei...",
  "channelCID": "bafyrei...",
  "epoch": 17,
  "startTs": "2026-03-12T12:00:00Z",
  "endTs": "2026-03-12T12:45:00Z",
  "participants": [
    {
      "did": "did:key:z6MkAlice...",
      "joinTs": "2026-03-12T12:00:00Z",
      "leaveTs": "2026-03-12T12:45:00Z"
    },
    {
      "did": "did:key:z6MkBob...",
      "joinTs": "2026-03-12T12:05:00Z",
      "leaveTs": "2026-03-12T12:45:00Z"
    }
  ],
  "mediaCID": "bafyrei...",
  "mediaFormat": "audio/ogg;codec=opus",
  "scope": "audio-video",
  "recorderSig": "base64url...",
  "prevRecordCID": "bafyrei..."
}
```

`mediaCID` is the CID of the encrypted media object. `prevRecordCID` chains records into the same append-only IPLD structure used for text compliance (§7.4), making the recording archive tamper-evident. `recorderSig` is the recorder's Ed25519 signature over all other fields, signed per §13.1.1. Records and media objects are stored on CO infrastructure and retained for the grant's `retentionDays`.

Media SHOULD be stored as Opus audio in an Ogg or WebM container (audio-only recordings) or VP8/VP9/AV1 video with Opus audio in a WebM container (audio-video recordings). The recorder decrypts SRTP and SFrame as a member (§6.12.2) and re-encodes to the archive format. Raw SRTP or SFrame packets MUST NOT be stored.

**Encryption at rest.** Each media file MUST be sealed before it leaves the recorder process, using HPKE single-shot `Seal` (RFC 9180, DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, AES-128-GCM) to the X25519 `keyAgreement` key in the recorder's DID document, with `info = "agora-recording-archive-v1" || grantCID_bytes`. `mediaCID` addresses the sealed object. Plaintext media MUST NOT be written to any IO component; a sealed object MAY be replicated to IO blob or pinning storage, which then holds only ciphertext.

Per-epoch media files are stored separately (one `mediaCID` per epoch) and linked by the `VTCComplianceRecord` chain.

### 6.12.5 VTC Compliance Configuration

To enable automatic compliance recording for a space's voice channels, the space owner adds a `vtcCompliance` block to the space state document:

```json
"vtcCompliance": {
  "@type": "VTCComplianceConfig",
  "schemaVersion": "1",
  "enabled": true,
  "recorderDID": "did:key:z6MkRecorder...",
  "recorderLabel": "Acme Corp VTC Compliance Recorder",
  "scope": "audio-video",
  "retentionDays": 2555,
  "autoGrant": true,
  "enabledBy": "did:key:z6MkOwner...",
  "enabledAt": "2026-03-12T00:00:00Z",
  "sig": "base64url..."
}
```

`recorderDID` is the DID of the compliance recording principal, a CO component run under CO control (ARCHITECTURE S8). `autoGrant` when `true` causes conformant clients to automatically issue a `RecordingGrant` for `recorderDID` on every voice channel in the space when a call begins, without requiring per-call admin action.

When `autoGrant` is `true`, the `RecordingGrant` is issued by the first Admin or Owner client that observes the call starting. The grant `expiresAt` is set to the call end plus a configurable grace period (default 5 minutes) to capture any reconnecting participants.

The recorder operates as a passive member (§5.2.1.3) of each voice channel's MLS group, admitted as in §6.12.2: it holds a leaf credential, derives media keys like any member, and does not issue Commits or Proposals. The recorder whose DID is declared in `vtcCompliance.recorderDID` MUST have a `KeyPackageEndpoint` service entry in its DID document (same requirement as the text compliance logger, §7.8.2) and MUST publish an X25519 `keyAgreement` key in its DID document for archive encryption (§6.12.4). Auto-issued grants carry `retentionDays` from this block.

### 6.12.6 VTC Compliance Audit Entry

The space's IPLD compliance audit chain receives a `VTCComplianceAuditEntry` for each compliance recording session:

```json
{
  "@context": "https://agora.protocol/ns/v1",
  "@type": "VTCComplianceAuditEntry",
  "channelCID": "bafyrei...",
  "grantCID": "bafyrei...",
  "recorderDID": "did:key:z6MkRecorder...",
  "callStart": "2026-03-12T12:00:00Z",
  "callEnd": "2026-03-12T12:45:00Z",
  "epochsRecorded": [17, 18, 19],
  "epochsGapped": [],
  "participantCount": 4,
  "vtcRecordCIDs": ["bafyrei...", "bafyrei..."],
  "sig": "base64url..."
}
```

`epochsGapped` is an array of epoch numbers of the call during which the recorder captured no media (§6.12.2), resulting in an unrecorded segment. An empty array means complete capture. Non-empty arrays are compliance gaps that must be reported to the compliance officer.

### 6.12.7 VTC Compliance in DM Voice Groups

A DM group (§4.6) may include a voice channel component. The obligation from §7.8 extends to voice: a regulated Space member participating in a DM voice group MUST add the space's `recorderDID` to the DM group's MLS group and issue a `RecordingGrant` for the recorder before any voice media is transmitted, following the same admission mechanics as §6.12.2. The `DMGroupDescriptor` `complianceLoggers` array records both text logger DIDs and VTC recorder DIDs.

Participant disclosure (§6.12.3) applies in DM voice groups identically to space voice channels. Non-regulated DM participants receive the disclosure notice and MAY leave before transmitting media.


---

