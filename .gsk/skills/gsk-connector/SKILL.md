---
name: gsk-connector
description: Discover and invoke ANY user connector (Gmail, Slack, Notion, HubSpot, custom MCP servers, ...) through one fixed 4-command flow. Use this INSTEAD of per-connector commands — it covers every current and future connector with zero extra docs.
---

# Connectors — unified discovery & invocation

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Availability:** the unified `gsk connector` commands are rolling out
> behind a feature flag and may not be enabled for every account yet. If
> `gsk connector ...` returns an unknown-command / not-found error, fall
> back to the per-service commands documented in the sibling `gsk-<service>`
> skills (`gsk gmail ...`, `gsk slack ...`, `gsk mcp call ...`, ...) — those
> remain fully supported.

One flow covers every connector, present and future:

```bash
gsk connector list                      # 1. what is already connected?
gsk connector search <keyword>          # 2. does a connector for X exist?
gsk connector tools <identifier>        # 3. what can it do? (full JSON schema per tool)
gsk connector call <identifier> -t <tool> -a '<json>'   # 4. do it
```

- `<identifier>`: connector id (`gmail`, `slack`, `hubspot`), display name
  (`"Google Drive"`), or MCP slug (`figma_design`) — all returned by
  steps 1-2.
- `-a` takes the tool's argument object as a **JSON string**; `'{}'` for none.
- Every response embeds a `next`/`call` field with the exact follow-up
  command — copy it.

## Error codes (final NDJSON line, `status: "error"`)

| error_code | Meaning / what to do |
|---|---|
| `not_connected` / `account_not_connected` | Ask the user to connect it: Settings → Connectors in the Genspark web app. Do not retry until they confirm. |
| `connector_blocked_by_org_policy` | The org admin disabled this connector. Tell the user; do not retry. |
| `unknown_connector` / `unknown_tool` | Typo — use the `suggestions` field. |
| `scope_denied` | This API token cannot use that tool. |
| `rate_limited` | Back off; honor `retry_after`. |

## Example

```bash
gsk connector search crm
gsk connector tools hubspot
gsk connector call hubspot -t create_contact -a '{"email": "a@b.com", "firstname": "Ada"}'
```

Old per-connector commands (`gsk gmail ...`, `gsk mcp call ...`) still work
but are deprecated — prefer this flow.
