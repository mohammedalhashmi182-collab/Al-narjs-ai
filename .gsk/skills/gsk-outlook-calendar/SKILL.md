---
name: gsk-outlook-calendar
version: 1.0.0
description: 'Outlook Calendar operations. Actions: list, free_busy, create, respond,
  modify, delete.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk outlook_calendar --help
---

# gsk-outlook-calendar

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Outlook Calendar operations. Actions: list, free_busy, create, respond, modify, delete.

## Usage

```bash
gsk outlook_calendar [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list': List upcoming calendar events. Returns at most 'limit' (default 20) events; the response sets truncated=true when more events exist in the window; 'free_busy': Query free/busy availability for people (any org member) in a time window (find open meeting slots); 'create': Create a new calendar event. By default this returns a LOCAL DRAFT only — nothing lands in the calendar until the user confirms it in the Genspark UI. Callers without a confirmation UI (e.g. gsk) must confirm the create (gsk: `--yes`) to write the event directly. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'respond': RSVP (accept / decline / tentative) to an existing invite. Supports --comment and --proposed_new_time (Outlook-only counter-proposal); 'modify': Modify (Graph PATCH /me/events/{id}) an existing event in place without delete+create; 'delete': Delete a calendar event. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes). (string, one of: list, free_busy, create, respond, modify, delete) |
| `--filter_query` | No | [list] Text to filter calendar events by subject. Empty for listing all events in the time range. (string) |
| `--time_min` | No | [list] Optional. Start time for the calendar view (ISO 8601 timestamp). Defaults to 30 days ago. (string) |
| `--time_max` | No | [list] Optional. End time for the calendar view (ISO 8601 timestamp). Defaults to 60 days from now. (string) |
| `--from_account` | No | [list] Optional: Email address of the Outlook account to use. Use this when the user has multiple Outlook accounts connected. If not specified, uses the default Outlook account. \| [create] Optional: Email address of the Outlook account to use. Use this when the user has multiple Outlook accounts connected. If not specified, uses the default Outlook account. \| [respond] Optional: Email address of the Outlook account to use. Defaults to the user's primary Outlook account. \| [modify] Optional: Email address of the Outlook account to use. \| [delete] Optional: Email address of the Outlook account to use. Use this when the user has multiple Outlook accounts connected. If not specified, uses the default Outlook account. (string) |
| `--full_description` | No | [list] Return complete readable descriptions instead of 500-character previews. Defaults to false. When true, limit defaults to 5 and must be at most 5; narrow filter_query and time_min/time_max to the desired event. (boolean, default: `False`) |
| `--limit` | No | [list] Optional. Maximum number of events to return. Defaults to 20 (5 with full_description=true). (integer) |
| `--start_time` | No | [free_busy] Window start, ISO 8601 date-time WITHOUT offset (e.g. '2026-07-20T09:00:00') — interpreted in 'timezone'. \| [create] Start time of the event in ISO 8601 format, must include correct timezone offset (e.g., 'yyyy-mm-ddThh:mm:ss+hh:mm') \| [modify] New start time (ISO 8601 with timezone offset). Pass with --end_time when rescheduling. (string) |
| `--end_time` | No | [free_busy] Window end, ISO 8601 (same rule). \| [create] End time of the event in ISO 8601 format, must include correct timezone offset (e.g., 'yyyy-mm-ddThh:mm:ss-hh:mm') \| [modify] New end time (ISO 8601 with timezone offset). Required if start_time is given. (string) |
| `--schedules` | No | [free_busy] Email addresses to check. Default: the signed-in user's own address. (array) |
| `--timezone` | No | [free_busy] Windows or IANA time zone name for interpreting start/end and the response (e.g. 'China Standard Time', 'UTC'). Default: 'UTC'. (string) |
| `--interval_minutes` | No | [free_busy] Granularity of the availability view in minutes (5/10/15/30/60). Default: 30. (integer) |
| `--summary` | No | [create] The title of the event \| [modify] New event title (maps to Outlook's 'subject' field). (string) |
| `--location` | No | [create] The location of the event \| [modify] New event location. (string) |
| `--description` | No | [create] Description or details of the event. Supports restricted HTML formatting (safe subset rendered via Vue v-html): <a>, <b>, <strong>, <i>, <em>, <u>, <br>, <p>, <ul>, <ol>, <li>, <span>, <img>. Use for links, bold, italics, lists, line breaks, images. \| [modify] New event body (HTML allowed — Outlook renders the same restricted subset as create). (string) |
| `--time_zone` | No | [create] Time zone for the event (e.g., 'GMT-07:00') \| [respond] Optional time zone used for the proposed_new_time payload (IANA name, e.g. 'America/Los_Angeles'). Defaults to UTC. \| [modify] Optional IANA time zone for start/end (e.g. 'America/Los_Angeles'). Defaults to UTC. (string) |
| `--time_zone_name` | No | [create] Time zone name for the event (e.g., 'America/Los_Angeles') (string) |
| `--attendees` | No | [create] List of email addresses of attendees \| [modify] REPLACE the attendee list with this set of emails. Mutually exclusive with add_attendees / remove_attendees. (array) |
| `--calendar_id` | No | [create] The calendar identifier. Use 'primary' for the user's primary calendar or provide a specific calendar email address (string) |
| `--event_id` | No | [create] The event identifier. If the request is to modify an existing event, provide the event_id of the event to be modified. If the request is to create a new event, leave this field empty. \| [respond] Outlook event id of the invitation to respond to (from a prior outlook_calendar_list call). \| [modify] Outlook event id to modify. \| [delete] The Outlook Calendar event ID to delete (string) |
| `--recurrence` | No | [create] Recurrence pattern for the event (object) |
| `--send_notifications` | No | [create] Whether to send email notifications to attendees \| [modify] Whether attendees get a notification of the change. Default true. (boolean) |
| `--importance` | No | [create] Event importance (low, normal, high) \| [modify] Event importance: low / normal / high. (string) |
| `--sensitivity` | No | [create] Event sensitivity (normal, personal, private, confidential) \| [modify] Event sensitivity: normal / personal / private / confidential. (string) |
| `--show_as` | No | [create] Show as status (free, tentative, busy, oof, workingElsewhere, unknown) \| [modify] Show-as status: free / tentative / busy / oof / workingElsewhere / unknown. (string) |
| `--is_all_day` | No | [create] Whether to create an all-day busy/block event. (boolean, default: `False`) |
| `--all_day` | No | [create] Alias for is_all_day. (boolean, default: `False`) |
| `--skip_conflict_check` | No | [create] Set true ONLY after the user has explicitly confirmed they want to book despite a conflict/warning surfaced by a prior needs_confirmation result. Leave false (default) normally. (boolean, default: `False`) |
| `--response` | No | [respond] RSVP value. 'accept' / 'decline' / 'tentative' (Yes / No / Maybe). When proposed_new_time is provided, this is forced to 'tentative' because Graph rejects counter-proposals on accept / decline. (string, one of: accept, decline, tentative) |
| `--comment` | No | [respond] Optional free-text comment shown to the organizer alongside the response. (string) |
| `--proposed_new_time` | No | [respond] Optional counter-proposal slot in '<START_ISO>..<END_ISO>' form (e.g. '2026-05-21T14:00:00-07:00..2026-05-21T14:30:00-07:00'). Forces response='tentative' — Graph rejects proposedNewTime on accept / decline. (string) |
| `--scope` | No | [respond] Recurring-series scope. 'single' (default) responds for the specific occurrence only; 'series' resolves the seriesMasterId and responds for the entire series. \| [modify] Recurring-series scope. 'single' (default) patches the specific occurrence; 'series' resolves the seriesMasterId and patches the master event. (string, one of: single, series, default: `single`) |
| `--send_response` | No | [respond] Whether Graph should notify the organizer of the response. Default true. (boolean, default: `True`) |
| `--add_attendees` | No | [modify] Append these attendees to the existing list. (array) |
| `--remove_attendees` | No | [modify] Remove these attendees from the existing list (case-insensitive email match). (array) |
| `--delete_series` | No | [delete] If true and the event is recurring, delete the entire series. If false, only delete the single instance. Default is false. (boolean, default: `False`) |

## Write Confirmation

Confirmation-gated actions: `create`, `delete`. The CLI shows a preview and asks `[y/N]` on stderr before the single server call; pass `--yes` (`-y`) for unattended runs. `--no-input` (or `--args-file -`, which consumes stdin) makes a gated call exit 2 with no server call instead of hanging. Never re-run a command to 'confirm' it — every call is a real execution. `--skip_confirmation true` / `--auto_skip_confirmation` are deprecated on this CLI (still accepted, warn on stderr): use `--yes`.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
