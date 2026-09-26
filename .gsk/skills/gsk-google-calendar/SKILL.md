---
name: gsk-google-calendar
version: 1.0.0
description: 'Google Calendar operations. Actions: list, free_busy, create, respond,
  modify, delete.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk google_calendar --help
---

# gsk-google-calendar

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Google Calendar operations. Actions: list, free_busy, create, respond, modify, delete.

## Usage

```bash
gsk google_calendar [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list': List upcoming calendar events. Returns at most 'limit' (default 20) events; the response sets truncated=true when more events exist in the window; 'free_busy': Query free/busy intervals for calendars in a time window (find open meeting slots); 'create': Create a new calendar event. By default this returns a LOCAL DRAFT only — nothing lands in the calendar until the user confirms it in the Genspark UI. Callers without a confirmation UI (e.g. gsk) must confirm the create (gsk: `--yes`) to write the event directly. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'respond': RSVP (accept / decline / tentative) to an existing invite so the organizer's UI reflects the response; 'modify': Modify (events.patch) an existing event in place without delete+create; 'delete': Delete a calendar event. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes). (string, one of: list, free_busy, create, respond, modify, delete) |
| `--filter_query` | No | [list] Text to filter calendar events, empty for listing all events (string) |
| `--time_min` | No | [list] Optional. Start time of the search range (RFC3339 timestamp) (string) |
| `--time_max` | No | [list] Optional. End time of the search range (RFC3339 timestamp) (string) |
| `--from_account` | No | [list] Optional: Email address of the Gmail account to use. Use this when the user has multiple Gmail accounts connected. If not specified, uses the default Gmail account. \| [create] Optional: Email address of the Gmail account to use. Use this when the user has multiple Gmail accounts connected. If not specified, uses the default Gmail account. \| [respond] Optional: Email address of the Gmail account to use. Defaults to the user's primary Gmail account. \| [modify] Optional: Email address of the Gmail account to use. \| [delete] Optional: Email address of the Gmail account to use. Use this when the user has multiple Gmail accounts connected. If not specified, uses the default Gmail account. (string) |
| `--full_description` | No | [list] Return complete readable descriptions instead of 500-character previews. Defaults to false. When true, limit defaults to 5 and must be at most 5; narrow filter_query and time_min/time_max to the desired event. (boolean, default: `False`) |
| `--limit` | No | [list] Optional. Maximum number of events to return. Defaults to 20 (5 with full_description=true). (integer) |
| `--start_time` | No | [free_busy] Window start, RFC3339 (e.g. '2026-07-20T09:00:00+08:00' or '2026-07-20T01:00:00Z'). \| [create] Start time of the event in ISO 8601 format, must include correct timezone offset (e.g., 'yyyy-mm-ddThh:mm:ss+hh:mm') \| [modify] New start time (ISO 8601 with timezone offset, e.g. '2026-05-20T10:00:00-07:00'). Pass with --end_time when rescheduling. (string) |
| `--end_time` | No | [free_busy] Window end, RFC3339. \| [create] End time of the event in ISO 8601 format, must include correct timezone offset (e.g., 'yyyy-mm-ddThh:mm:ss-hh:mm') \| [modify] New end time (ISO 8601 with timezone offset). Required if start_time is given. (string) |
| `--calendars` | No | [free_busy] Calendar IDs to check — 'primary' or email addresses. Default: ['primary']. (array) |
| `--timezone` | No | [free_busy] IANA time zone used for interpreting the response (e.g. 'Asia/Shanghai'). Optional. (string) |
| `--summary` | No | [create] The title of the event \| [modify] New event title (optional). (string) |
| `--location` | No | [create] The location of the event \| [modify] New event location (optional). (string) |
| `--description` | No | [create] Description or details of the event. Supports restricted HTML formatting (safe subset rendered via Vue v-html): <a>, <b>, <strong>, <i>, <em>, <u>, <br>, <p>, <ul>, <ol>, <li>, <span>, <img>. Use for links, bold, italics, lists, line breaks, images. \| [modify] New event description (optional). Supports the same restricted HTML subset as create. (string) |
| `--time_zone` | No | [create] Time zone for the event (e.g., 'GMT-07:00') \| [modify] Optional time zone for start/end (e.g. 'America/Los_Angeles' or 'GMT-07:00'). (string) |
| `--time_zone_name` | No | [create] Time zone name for the event (e.g., 'America/Los_Angeles') (string) |
| `--attendees` | No | [create] List of email addresses of attendees \| [modify] REPLACE the attendee list with this set of emails. Mutually exclusive with add_attendees / remove_attendees. (array) |
| `--calendar_id` | No | [create] The calendar identifier. Use 'primary' for the user's primary calendar or provide a specific calendar email address (string) |
| `--event_id` | No | [create] The event identifier. If the request is to modify an existing event, provide the event_id of the event to be modified. If the request is to create a new event, leave this field empty. \| [respond] Google Calendar event id of the invitation to respond to. For a recurring-series instance, the id has shape '<seriesId>_<startTs>'. \| [modify] Google Calendar event id to modify. For a recurring-series instance, the id has shape '<seriesId>_<startTs>'. \| [delete] The Google Calendar event ID to delete (string) |
| `--recurrence` | No | [create] Recurrence rules (e.g., ['RRULE:FREQ=DAILY;COUNT=2']) \| [modify] New recurrence rules (e.g. ['RRULE:FREQ=WEEKLY;BYDAY=MO']). Only honored when scope=series. (array) |
| `--send_notifications` | No | [create] Whether to send email notifications to attendees \| [respond] Whether Google should notify the organizer of the response. Default true. \| [modify] Whether attendees get a notification of the change. Default true. (boolean) |
| `--is_all_day` | No | [create] Whether to create an all-day busy/block event. (boolean, default: `False`) |
| `--all_day` | No | [create] Alias for is_all_day. (boolean, default: `False`) |
| `--skip_conflict_check` | No | [create] Set true ONLY after the user has explicitly confirmed they want to book despite a conflict/warning surfaced by a prior needs_confirmation result. Leave false (default) normally. (boolean, default: `False`) |
| `--response` | No | [respond] RSVP value. 'accept' / 'decline' / 'tentative' (Yes / No / Maybe). (string, one of: accept, decline, tentative) |
| `--comment` | No | [respond] Optional free-text comment shown to the organizer alongside the response. (string) |
| `--scope` | No | [respond] Recurring-series scope. 'single' (default) responds for the specific instance only; 'series' responds for the entire series (patches the master event). \| [modify] Recurring-series scope. 'single' (default) patches the specific instance; 'following' updates this and future occurrences by splitting the series; 'series' patches the master event so the change applies to every occurrence. (string, one of: single, series, default: `single`) |
| `--add_attendees` | No | [modify] Append these attendees to the existing list. Combine with remove_attendees for an additive edit; both leave attendees the caller didn't name alone. (array) |
| `--remove_attendees` | No | [modify] Remove these attendees from the existing list (case-insensitive email match). (array) |
| `--delete_series` | No | [delete] If true and the event is recurring, delete the entire series. If false, only delete the single instance. Default is false. (boolean, default: `False`) |

## Write Confirmation

Confirmation-gated actions: `create`, `delete`. The CLI shows a preview and asks `[y/N]` on stderr before the single server call; pass `--yes` (`-y`) for unattended runs. `--no-input` (or `--args-file -`, which consumes stdin) makes a gated call exit 2 with no server call instead of hanging. Never re-run a command to 'confirm' it — every call is a real execution. `--skip_confirmation true` / `--auto_skip_confirmation` are deprecated on this CLI (still accepted, warn on stderr): use `--yes`.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
