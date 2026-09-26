---
name: gsk-phone-call
version: 1.0.0
description: Make a real AI phone call on the user's behalf. Validates prerequisites
  (membership, phone setup, credits), resolves the contact, then dials and returns
  status, real audio duration, dial attempts, summary, and transcript. After every
  call, present the outcome, disclose every dial attempt, point to call_log or call_detail,
  and show short transcripts inline. Never fabricate a phone number or Maps place_id;
  contact_info must have verified lineage. A dry run validates only and never places
  a call. On code=setup_incomplete, show setup_url, wait for setup, and use phone_call_setup_status
  before retrying. For sending a real text message instead, use the SMS sibling `gsk
  telephony sms send` — same setup, lineage, and disclosure rules.
metadata:
  category: phone-call
  requires:
    bins:
    - gsk
  cliHelp: gsk telephony call dial --help
---

# gsk-phone-call

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Make a real AI phone call on the user's behalf. Validates prerequisites (membership, phone setup, credits), resolves the contact, then dials and returns status, real audio duration, dial attempts, summary, and transcript. After every call, present the outcome, disclose every dial attempt, point to call_log or call_detail, and show short transcripts inline. Never fabricate a phone number or Maps place_id; contact_info must have verified lineage. A dry run validates only and never places a call. On code=setup_incomplete, show setup_url, wait for setup, and use phone_call_setup_status before retrying. For sending a real text message instead, use the SMS sibling `gsk telephony sms send` — same setup, lineage, and disclosure rules.

## Usage

```bash
gsk telephony call dial [options]
```

## SMS sibling: `gsk telephony sms send`

Send a real SMS on the user's behalf. The message body is sent VERBATIM — pass exactly the text the user approved, never compose or embellish it. Validates prerequisites (membership, phone setup, credits), destination number lineage, and the per-country segment budget (South Korea: single segment only, 70 chars for Korean text; Japan: max 5 segments), then sends and returns the delivery handle (sid), segments, and credits charged. Over-budget messages are rejected, never truncated.
Destination numbers must have verifiable lineage (user-provided, prior tool results, or a calllog: contact_ref) — never fabricate a number.
Use dry_run=true first when unsure: it validates and prices (encoding, segment count, credits) without sending.
MANDATORY after every send: report to the user the recipient, delivery status, segment count, and credits charged.

```bash
gsk telephony sms send [options]   # see `gsk telephony sms send --help`
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<recipient>` (positional) | Yes | The name of the person or business to call. Examples: - Personal: 'John Smith', 'Dr. Sarah Johnson' - Business: 'Starbucks George Street', 'Hilton Hotel Downtown' (string) |
| `-c`, `--contact_info` | Yes | Contact information — a phone number, a calllog: contact_ref, or a Google Maps place_id; the type is detected automatically from its shape.  **Phone numbers**: include the international country code ('+1-555-123-4567'); numbers without one are treated as US. MUST have verified data lineage from (1) user-provided info, (2) previous tool results, or (3) explicit context — NEVER fabricate, estimate, or infer a number.  **calllog: contact_ref** (from the call_log tool's contacts view, `--view contacts`): the preferred way to re-dial someone previously called — their real number stays masked.  **Google Maps place_id** (e.g. 'ChIJcawkWTyuEmsRG56o5LAc0LQ'): must come from maps_search results — never fabricate or guess one. The call then uses the business's Maps phone number and enriches the call record with the place data. (string) |
| `-p`, `--purpose` | Yes | The clear reason for making the call (e.g., 'Check reservation availability', 'Inquire about business hours'). (string) |

> **CAUTION:** This command performs a write/send operation. Double-check parameters before executing.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
