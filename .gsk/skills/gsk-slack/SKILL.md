---
name: gsk-slack
version: 1.0.0
description: 'Slack messaging operations. Actions: send, search, search_files, read,
  download_file, lookup, react, upload, update, delete, permalink.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk slack --help
---

# gsk-slack

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Slack messaging operations. Actions: send, search, search_files, read, download_file, lookup, react, upload, update, delete, permalink.

## Usage

```bash
gsk slack [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'send': Send a message to a channel or user. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'search': Search messages by keyword; 'search_files': Search files shared in Slack by keyword; each hit's id feeds download_file; 'read': Read recent message history of a channel (or one thread), including each message's emoji reactions and uploaded files; 'download_file': Download one file shared in Slack by its id; returns a file URL; 'lookup': Look up users, channels, or groups; 'react': Emoji-react to a message (or remove your reaction). Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'invite': Invite workspace members into a channel. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'upload': Upload a file into a channel, group, or DM. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'update': Edit one of the user's own messages. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'delete': Delete one of the user's own messages. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes).; 'permalink': Get the permanent link for a message (string, one of: send, search, search_files, read, download_file, lookup, react, invite, upload, update, delete, permalink) |
| `--message` | No | [send] The message content to send. Supports Slack markdown formatting. To @mention someone, embed '<@USER_ID>' (e.g. '<@U01234567>') in the text — a plain '@Name' renders as literal text and notifies nobody. User IDs come from the lookup action. 'content' is accepted as an alias for this parameter. (string) |
| `--recipient` | No | [send] Optional recipient: 'self' (default), channel ID (e.g., 'C01234567'), or user ID (e.g., 'U01234567'). If not specified, sends to yourself. (string) |
| `--title` | No | [send] Optional title for the message. If provided, creates a rich formatted message with a header. \| [upload] Optional title shown on the Slack file card. Defaults to the file name. (string) |
| `--fields` | No | [send] Optional array of field objects with 'title' and 'value' keys to create a structured message layout. (array) |
| `--thread_ts` | No | [send] Optional thread timestamp to reply in a thread. \| [read] Timestamp ('ts') of a thread's parent message. When set, returns that thread's replies instead of the channel timeline. \| [upload] Optional thread timestamp — share the file as a reply in this thread instead of the conversation root. (string) |
| `--workspace` | No | Optional. Which linked Slack workspace to act in: its team id (e.g. 'T0123ABCD') or its workspace name. Omit to use the default (most recently connected) workspace. The lookup action with lookup_type='workspaces' lists the choices. (string) |
| `--query` | No | [search] The search query. You can use modifiers like 'in:#channel', 'from:@user', 'has:link', 'before:yyyy-mm-dd'. \| [search_files] Search terms; Slack modifiers such as 'in:#channel', 'from:@user', 'before:yyyy-mm-dd' are honored. (string) |
| `--count` | No | [search] The maximum number of messages to return. Default is 100. \| [search_files] Maximum files to return (default 20, max 100). (integer) |
| `--sort` | No | [search] Sort order of results. 'score' for relevance or 'timestamp' for time. Default is 'score'. \| [search_files] 'score' (relevance, default) or 'timestamp' (newest first). (string) |
| `--question` | No | [search] A specific question to answer based on the search results. (string) |
| `--channel` | No | [read] Conversation ID (channel 'C…', private group 'G…', or DM 'D…') or a channel name (e.g. '#general' or 'general'). IDs come from the lookup action. \| [react] Conversation ID containing the message (channel 'C…', private group 'G…', or DM 'D…'). \| [invite] Conversation ID of the channel to invite into (public 'C…' or private group 'G…'). \| [upload] Target conversation ID (channel 'C…', private group 'G…', or DM 'D…') the file is shared into. \| [update] Conversation ID containing the message (channel 'C…', private group 'G…', or DM 'D…'). \| [delete] Conversation ID containing the message (channel 'C…', private group 'G…', or DM 'D…'). \| [permalink] Conversation ID containing the message (channel 'C…', private group 'G…', or DM 'D…'). (string) |
| `--limit` | No | [read] Maximum messages to return (default 20, max 100). \| [lookup] Maximum number of results to return. Default: 50 (integer) |
| `--cursor` | No | [read] Pagination cursor from a previous call's next_cursor to fetch older messages. (string) |
| `--file_id` | No | [download_file] Slack file id (starts with 'F'), from a message's files list (read action) or a search_files hit. (string) |
| `--lookup_type` | No | [lookup] What to look up: 'users' for team members, 'channels' for channels/conversations, 'all' for both, 'workspaces' for the Slack workspaces linked to this account (their team_id feeds the 'workspace' parameter). (string, one of: users, channels, all, workspaces) |
| `--search_query` | No | [lookup] Optional search query to filter results by name. Case-insensitive partial match on name, display name, or real name. (string) |
| `--include_bots` | No | [lookup] Whether to include bot users in results. Default: false (boolean) |
| `--timestamp` | No | [react] The message's 'ts' value (e.g. '1752600000.000100'). \| [update] The message's 'ts' value (e.g. '1752600000.000100'). Must be a message the connected user authored. \| [delete] The message's 'ts' value (e.g. '1752600000.000100'). Must be a message the connected user authored. \| [permalink] The message's 'ts' value (e.g. '1752600000.000100'). (string) |
| `--reaction` | No | [react] Slack emoji name without colons, e.g. 'thumbsup', '+1', 'heart', 'joy'. (string) |
| `--remove` | No | [react] Set true to remove your existing reaction of this emoji instead of adding it. Default: false. (boolean) |
| `--user_ids` | No | [invite] Slack user IDs to invite (e.g. ['U0123ABCD']). Up to 30 per call. (array) |
| `--content` | No | [upload] Text content to upload as a file (UTF-8). Provide exactly one of 'content' or 'file_path'. (string) |
| `--file_path` | No | [upload] File to upload: a local server file path, a Genspark file-wrapper URL (https://…/api/files/s/<code>), or an AI Drive path (aidrive://…). Provide exactly one of 'content' or 'file_path'. (string) |
| `--file_name` | No | [upload] File name shown in Slack (include the extension, e.g. 'report.pdf'). Required with 'content'; defaults to the path basename for 'file_path'. (string) |
| `--initial_comment` | No | [upload] Optional message text posted together with the file. (string) |
| `--text` | No | [update] The full replacement text (mrkdwn) — Slack replaces the whole message body, not a diff. (string) |

## Write Confirmation

Confirmation-gated actions: `send`, `react`, `invite`, `upload`, `update`, `delete`. The CLI shows a preview and asks `[y/N]` on stderr before the single server call; pass `--yes` (`-y`) for unattended runs. `--no-input` (or `--args-file -`, which consumes stdin) makes a gated call exit 2 with no server call instead of hanging. Never re-run a command to 'confirm' it — every call is a real execution. `--skip_confirmation true` / `--auto_skip_confirmation` are deprecated on this CLI (still accepted, warn on stderr): use `--yes`.

Interactive-only actions: `send`, `react`, `invite`, `upload` (the action excludes the skip params, e.g. Marketplace policy on Slack) — `--yes` is ignored and a real `[y/N]` answer is required.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
