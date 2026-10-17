# BCP 14 requirements on user agent UX

Sweep of spec/*.md, ARCHITECTURE.md, profiles/ and guides/ (working tree, 2026-10-17) against the principle: "we really can't enforce MUSTs on the UX of commercial and open source user agents."

Classes:

- **UX**: constrains what a client shows, how it notifies, prompts, warns, labels, sorts or renders. Proposed: SHOULD, MAY, or descriptive text.
- **KEEP**: affects the wire, interop, verification, key handling, what leaves the device, or compliance capture. Some need a wording fix so they stop reading as display rules.
- **BORDERLINE**: security- or disclosure-relevant display rules. Listed at the end with recommendations.

Existing SHOULD/MAY UX text (for example 02:120 confusables, 05:156, 05:158, 06:19, 11:44, 12:225) is already correctly weighted and is not listed. The guides/ files carry no UX requirements. Operator alerting in profiles/purview-bridge.md and profiles/gsuite-employer-did.md is on CO services, not user agents, and is out of scope.

## §4.6.3 consistency check

§4.6.3 (uncommitted) matches the principle: request state, notification and fetch are SHOULD / SHOULD NOT, and the only MUSTs are wire rules (no receipts or typing indicators, 04:227) and compliance capture (04:230). One residual:

- 04:230 "Only notification, read receipts, typing indicators and display of the group's messages remain suppressed until the user accepts." Read alone, this reads as a mandatory suppression of notification and display, while 04:226 and 04:228 make those SHOULD NOT. Proposed: "Until the user accepts, it still sends no read receipts or typing indicators, and the recommendations above on notification and fetching still apply."

The same file still has a UX MUST at 04:141 ("MUST alert its user"), listed below.

## spec/02-identity.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/02-identity.md:10 | "Clients MUST support resolving all three and MUST offer `did:webvh` as the default when creating an identity." | UX (second MUST) | "Clients MUST support resolving all three, and SHOULD offer `did:webvh` as the default when creating an identity." |
| spec/02-identity.md:30 | "A client MUST warn the user, before creating a `did:key` identity, that losing the key loses the identity permanently and that a lost or stolen device cannot be revoked." | UX | "A client SHOULD warn the user, before creating a `did:key` identity, that ..." (rest unchanged) |
| spec/02-identity.md:120 | "Clients MUST apply that rule before displaying or comparing either string, and treat a string the rule rejects as absent." | KEEP | Input validation; affects comparison as well as display. No change. |

## spec/04-access-control.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/04-access-control.md:141 | "A client that receives one MUST NOT process later messages in that group, MUST alert its user, and MUST leave the group by deleting its group state" | UX (middle MUST only) | "A client that receives one MUST NOT process later messages in that group and MUST leave the group by deleting its group state, and SHOULD tell its user; ..." |
| spec/04-access-control.md:227 | "MUST NOT send read receipts, typing indicators or any other message to the group" | KEEP | What leaves the device. |
| spec/04-access-control.md:230 | "The client of a regulated member (§7.8.1) MUST process the Welcome and perform the logger admission and disclosure ..." | KEEP | Compliance capture. |

## spec/05-messaging.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/05-messaging.md:208 | "Recipients MUST verify `sig` per §13.1.1 ... before displaying the message" | KEEP | Verification gate. |
| spec/05-messaging.md:210 | "A non-member subscriber MUST NOT display a post whose `senderDID` is not listed for the channel in a `broadcasters` entry" | KEEP | Authorization check. Optional rewording: "MUST discard a post whose ..." so it reads as acceptance, not display. |
| spec/05-messaging.md:500 | "Clients MUST support CommonMark rendering and `text/plain`." | UX | "Clients MUST accept `text/markdown` (CommonMark) and `text/plain` bodies and SHOULD render CommonMark." |
| spec/05-messaging.md:500 | "Clients that cannot render CommonMark MUST display `body` verbatim." | UX | "Clients that do not render CommonMark display `body` verbatim." (descriptive) |
| spec/05-messaging.md:502 | "The following are not in the CommonMark baseline and MUST NOT be rendered unless the `bodyType` names an extension that includes them" | KEEP | Format semantics: what the sender's bytes mean. |
| spec/05-messaging.md:524 | "MUST render a `body` whose `bodyType` it does not recognize as `text/plain`" | KEEP | Format fallback semantics (interpretation of bytes). Optional rewording: "MUST treat a `body` whose `bodyType` it does not recognize as `text/plain`." |
| spec/05-messaging.md:609 | "A receiving client MUST treat such a second add as a no-op and MUST NOT display it as a separate reaction." | KEEP (first MUST); UX (second) | "A receiving client MUST treat such a second add as a no-op." The display clause follows from the no-op and can be dropped. |
| spec/05-messaging.md:613 | "A reaction count of zero MUST NOT be displayed." | UX | "A client SHOULD NOT display a reaction count of zero." |
| spec/05-messaging.md:615 | "clients MUST NOT display reactions for it." | UX | "clients SHOULD NOT display reactions for it." |
| spec/05-messaging.md:647 | "Clients that cannot resolve it MUST display the `emoji` string `:space:example_logo:` as a fallback." | UX | "Clients that cannot resolve it SHOULD display the `emoji` string ... as a fallback." |
| spec/05-messaging.md:655 | "clients MUST stop rendering it after the next space state refresh." | UX | "clients SHOULD stop rendering it after the next space state refresh." |

## spec/06-calls.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/06-calls.md:369 | "In either case, clients MUST NOT transmit a participant's media automatically on join while a grant is active." | KEEP | What leaves the device. |
| spec/06-calls.md:585 | "A participant's client MUST apply the policy to its own user unless that user is a moderator" | KEEP | What the client transmits. |

Recording disclosure rows (06:331, 06:360, 06:362, 06:366, 06:367, 06:373) and 06:177 are BORDERLINE, below.

## spec/07-compliance.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/07-compliance.md:54 | "This addition IS recorded in the MLS group membership ... but MUST NOT produce a UI-visible join notification." | UX | "... but clients need not show it as a join notification; the `retentionNotice` (§7.2) is the member-facing disclosure." |
| spec/07-compliance.md:208 | "The client MUST NOT permit the regulated member to send any application message in a DM group until the compliance logger has been admitted to the MLS group and the disclosure notice has been displayed to all members." | KEEP (needs rewrite) | The sender cannot know what other clients display. "... until the compliance logger has been admitted to the MLS group and the client has sent the `ComplianceDisclosureNotice` (§7.8.4)." |
| spec/07-compliance.md:240 | "The Space admin MUST be notified so they can assess the compliance gap." | KEEP | Compliance reporting to the CO, not end-user UX. |
| spec/07-compliance.md:248 | "their client MUST display a disclosure notice to all DM group members." | KEEP (needs rewrite) | "their client MUST send a `ComplianceDisclosureNotice` to the group." |
| spec/07-compliance.md:248 | "The notice MUST be delivered as a system message visible to all current group members before the first application message in the epoch where the logger is admitted" | KEEP (needs rewrite) | "The notice MUST be sent as an application message in the epoch where the logger is admitted, before any other application message the client sends in that epoch." |
| spec/07-compliance.md:340 | "Display `ComplianceDisclosureNotice` to all DM members before first message \| Regulated member's client \| MUST" | KEEP (needs rewrite) | "Send `ComplianceDisclosureNotice` before first message \| Regulated member's client \| MUST" |
| spec/07-compliance.md:342 | "Notify Space admin of logger removal attempt" | KEEP | Compliance reporting. |
| spec/07-compliance.md:344 | "Admit logger and send disclosure while the DM is a message request" | KEEP | Compliance capture. |

07:163 and 07:262 are BORDERLINE, below.

## spec/08-cross-space.md

08:133 is BORDERLINE, below.

## spec/09-interop.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/09-interop.md:194 | "Any gateway admitted to an Agora channel ... MUST be disclosed to all channel members." | KEEP | The disclosure on the wire is the `gateways` array in Space state plus the `SystemEvent`. Optional clarification: "MUST be listed in the channel's `gateways` array (§9.2)." |
| spec/09-interop.md:213 | "Clients MUST render a persistent banner or channel badge indicating gateway presence." | UX | Duplicates 09:196 at presentation level. "Clients SHOULD render a persistent banner or channel badge indicating gateway presence." |
| spec/09-interop.md:213 | "The banner MUST NOT be dismissible per-session without re-appearing on reconnect." | UX | "A dismissed banner SHOULD reappear on reconnect." |

09:96, 09:182 and 09:196 are BORDERLINE, below.

## spec/10-relays.md

10:467 is BORDERLINE, below.

## spec/12-security.md

12:221 and 12:223 are BORDERLINE, below.

## spec/13-encoding.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/13-encoding.md:113 | "A recipient that does not understand an envelope's `type` MUST ignore the payload: it MUST NOT display it, MUST NOT treat it as an error, and MUST continue processing" | UX (display clause only) | "MUST ignore the payload: it does not display it, MUST NOT treat it as an error, and MUST continue processing ..." The extensibility rule is "ignore"; display follows. |

## spec/14-jmap.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| spec/14-jmap.md:49 | "it MAY display objects it holds, and MUST NOT send operations on that type." | KEEP | Wire rule. |

## ARCHITECTURE.md

| Location | Quote | Class | Proposed |
|---|---|---|---|
| ARCHITECTURE.md:119 | "Any extension that enlarges the budget MUST be opt-in by the CO, MUST be declared in the relay manifest, and MUST be visible to members." | KEEP (clarify) | "Visible" here means discoverable from data, not a UI mandate. "... and MUST be declared in the relay manifest, where members can see it." |

## profiles/discord-onboarding.md

This profile specifies one tool. If the project ships it as the reference implementation, MUST is defensible as a product spec; if third parties implement it, these are UX and SHOULD fits.

| Location | Quote | Class | Proposed |
|---|---|---|---|
| profiles/discord-onboarding.md:83 | "The tool MUST offer `did:webvh` as the default." | UX | "The tool SHOULD offer `did:webvh` as the default." (matches 02:10 change) |
| profiles/discord-onboarding.md:95 | "Before creating a `did:key` identity, the tool MUST show the warning required by spec §2.1" | UX | "the tool SHOULD show the warning that spec §2.1 recommends" (matches 02:30 change; "required" becomes wrong otherwise) |
| profiles/discord-onboarding.md:187 | "For `did:key` the tool MUST NOT ask for a recovery key" | UX | "For `did:key` the tool does not ask for a recovery key, because ..." (descriptive) |
| profiles/discord-onboarding.md:189 | "the app MUST warn that no recovery key is registered" | UX | "the app SHOULD warn that no recovery key is registered" |
| profiles/discord-onboarding.md:276 | "The CLI MUST require the passphrase to be confirmed twice at generation." | UX | "The CLI SHOULD require the passphrase to be entered twice at generation." |
| profiles/discord-onboarding.md:496 | "The app MUST check `window.crypto.subtle` on load and MUST display a hard error if absent" | UX (second MUST) | "The app MUST check `window.crypto.subtle` on load and MUST NOT proceed if it is absent, and SHOULD show an error." |
| profiles/discord-onboarding.md:307 | "MUST NOT write the private key to any keystore or file, and MUST output the private key only as a recovery phrase" | KEEP | Key handling. |

## BORDERLINE

Recommended rule for disclosures, applied uniformly below: the enforceable obligation is on the wire (the notice is sent, the field is in signed Space state, media is not transmitted). Keep those as MUST. For presentation, either (a) one outcome-level MUST per disclosure ("MUST present X to the user before Y") with all presentation detail as SHOULD, or (b) SHOULD throughout. I recommend (a) for legally driven notices (compliance retention, recording), because a conformance claim needs one testable gate there, and (b) for security-property indicators (broadcast, gateway), where the signed data already is the disclosure.

| Location | Quote | Recommendation |
|---|---|---|
| spec/02-identity.md:120 | "When displaying them, clients MUST isolate each string as a bidirectional run ... so that it cannot reorder surrounding text." | Keep MUST. Anti-spoofing on peer-controlled bytes, cheap, and peers rely on others not being able to forge surrounding UI text. |
| spec/05-messaging.md:511 | "Clients MUST strip or escape any raw HTML in a Markdown `body` rather than rendering it." | Keep MUST. A sender can attack receivers' clients; this is injection defense, not presentation. |
| spec/06-calls.md:177 | "clients MUST NOT display `reason` as trusted text." | Keep as a security rule, reworded off display: "clients MUST treat `reason` as untrusted text from the SFU." |
| spec/05-messaging.md:212 | "Clients MUST display a visible indicator (e.g., a megaphone icon, with a text equivalent per §12.10) on broadcast channels" | Option (b): "Clients SHOULD indicate broadcast channels (for example a megaphone icon with a text equivalent, §12.10), because the channel has the weaker properties stated below." `keyAccess: public` in signed Space state is the disclosure. |
| spec/06-calls.md:331 | "`participantDisclosure` MUST be displayed to all channel participants before recording begins (§6.12.3)." | Option (a): replace with a pointer: "Clients present `participantDisclosure` as §6.12.3 describes." The gate lives in §6.12.3. |
| spec/06-calls.md:360 | "participating clients MUST display the `participantDisclosure` string ... as a non-dismissable system message in the voice channel's text feed and as a visible indicator in the call UI." | Option (a): "Before it transmits its user's media while a grant is active, a client MUST present `participantDisclosure` to its user. It SHOULD show it as a non-dismissable system message in the channel's text feed and as an indicator in the call UI." |
| spec/06-calls.md:360 | "The indicator MUST persist for the full duration of the grant." | "The indicator SHOULD persist for the full duration of the grant." |
| spec/06-calls.md:360 | "Clients MUST also show the indicator whenever the channel group contains a leaf for the `vtcCompliance.recorderDID`" | "Clients SHOULD also show the indicator whenever ..." The leaf in the group is the on-wire fact. |
| spec/06-calls.md:362 | "A participant who joins ... MUST be shown the disclosure immediately on join, before their audio or video is transmitted." | Fold into the 06:360 gate (same outcome). Delete as a separate MUST. |
| spec/06-calls.md:362 | "Their client MUST NOT enable media transmission until the disclosure has been rendered." | Keep MUST: transmission gate. Reword "rendered" to "presented to its user" so headless devices (12:223) fit. |
| spec/06-calls.md:366 | "A participant who does not consent MUST be able to remain muted with camera off, or leave." | Descriptive: "A participant who does not consent can remain muted with camera off, or leave; nothing in the protocol requires a member to transmit." |
| spec/06-calls.md:367 | "Each participant's client MUST obtain an explicit affirmative acknowledgement from its user before transmitting that user's media while the grant is active." | Keep MUST: it gates what leaves the device and is the consent basis for operational recording. How acknowledgement is asked stays unspecified. |
| spec/06-calls.md:373 | "the disclosure MUST include the `recorderLabel` ... and the grant's `retentionDays`" | Option (a): keep as content of the outcome MUST ("the disclosure a client presents MUST identify `recorderLabel` and `retentionDays`"); the quoted sentence stays "wording equivalent to", which is already non-binding. |
| spec/07-compliance.md:163 | "Clients MUST display this notice to members when they first join a compliance-logging-enabled space" | Option (a): "A client MUST present `retentionNotice` to its user before the user first sends in a compliance-logging-enabled Space." |
| spec/07-compliance.md:163 | "and MUST make it accessible from the space's information panel at any time." | "and SHOULD keep it available to the user afterward." (Names a UI element; pure UX.) |
| spec/07-compliance.md:262 | "Clients MUST render it as a visible system notification (not a suppressable status line) with wording equivalent to:" | SHOULD. The receiving client belongs to an arbitrary, possibly non-regulated party on any vendor's software; the regulated firm's enforceable obligation is the send in 07:248. "Receiving clients SHOULD show it as a system notification, not a status line that can be suppressed, with wording equivalent to:" |
| spec/08-cross-space.md:133 | "Guest space members MUST be notified of this at channel join time." | Option (a), matching 07:163: "A guest member's client MUST present the home Space's `retentionNotice` to its user, attributed to the home Space, before the user first sends in the shared channel." The following descriptive sentence and quoted wording stay. |
| spec/09-interop.md:96 | "**E2EE is broken at the gateway: the gateway holds plaintext.** This MUST be made visible to all participants (§9.3)." | Option (b): "This is disclosed to all participants by §9.3." (The MUST is met on the wire by the `gateways` array and `SystemEvent`.) |
| spec/09-interop.md:182 | "This MUST be disclosed to Agora channel members (§9.3)." | Same as 09:96. Note §9.3 currently has no field that says the Matrix room lacks Megolm; if this disclosure is wanted on the wire, `SystemEvent.e2eeNote` or the `gateways` entry needs to carry it. Flagged, not proposed. |
| spec/09-interop.md:196 | "Clients MUST display a visible indicator when a channel has active gateways." | Option (b): "Clients SHOULD display an indicator when a channel has active gateways." |
| spec/09-interop.md:196 | "The indicator MUST identify the gateway protocol and target system." | "The indicator SHOULD identify the gateway protocol and target system." |
| spec/12-security.md:221 | "Every required indicator MUST have a text equivalent that the client exposes through the platform accessibility API." | Follows the parent decisions. If indicators become SHOULD: "An indicator a client presents for a disclosure in this section SHOULD have a text equivalent exposed through the platform accessibility API." Under option (a), the outcome MUST is "present to the user", which an icon-only indicator for a screen-reader user does not meet, so the sentence "An icon or color alone does not meet a disclosure requirement" can stay as descriptive text. |
| spec/12-security.md:223 | "A client on a device with no display ... MUST play an audible announcement of the recording disclosure before it enables media transmission" | Fold into the 06:360 gate: "presenting" includes an audible announcement. Make the announcement a SHOULD-level example. |
| spec/12-security.md:223 | "A device that can neither display nor announce the disclosure MUST NOT transmit media while a `RecordingGrant` is active." | Keep MUST: transmission gate. |
| spec/10-relays.md:467 | "Clients MUST NOT auto-add directory sources from space state documents, relay advertisements, or any other protocol message without explicit user confirmation." | Keep MUST NOT: a peer-supplied message must not change a client's trust configuration. Reword the UX tail: "MUST NOT add a directory source because a protocol message names it; sources are added only by the user or by whoever manages the device." |
| profiles/discord-onboarding.md:185 | "MUST show its fingerprint for the user to compare against the offline device." | Keep MUST if the tool is the reference implementation: the comparison is the only check that the registered key is the offline one. Otherwise SHOULD. |

Also update the scope list at spec/12-security.md:211 ("every disclosure this specification requires a client to present") once the above is decided; under option (b) for broadcast and gateway indicators, those two entries move out of "requires".

## Counts

- UX: 20 (14 spec, 6 profile)
- KEEP: 22 (5 need rewording off display: 07:208, 07:248 x2, 07:340, ARCHITECTURE:119)
- BORDERLINE: 27
