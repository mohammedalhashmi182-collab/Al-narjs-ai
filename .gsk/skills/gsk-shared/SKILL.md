---
name: gsk-shared
version: 1.0.0
description: "Shared foundation: authentication, global flags, output conventions, and security rules for all GSK CLI skills."
metadata:
  category: foundation
  requires:
    bins:
      - gsk
---

# GSK CLI — Shared Foundation

**PREREQUISITE:** Every GSK skill assumes this document has been read first.

## Installation

```bash
npm install -g @genspark/cli
```

Requires Node.js >= 18.

## Authentication

```bash
# Log in via browser (saves the API key and effective API endpoint)
gsk login

# Or provide an API key directly
export GSK_API_KEY="gsk_..."

# Check current identity
gsk me
```

## Global Flags

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--api-key <key>` | `GSK_API_KEY` | — | API key (required) |
| `--base-url <url>` | `GSK_BASE_URL` | `https://www.genspark.ai` | API base URL |
| `--project-id <id>` | `GSK_PROJECT_ID` | — | Project ID for access control |
| `--debug` | — | `false` | Enable debug output |
| `--timeout <ms>` | — | `1800000` | Request timeout (30 min default) |
| `--output <format>` | — | `json` | Output format: `json` or `text` |
| `--refresh` | — | — | Force refresh cached tool schemas |
| `-y`, `--yes` | — | `false` | Auto-confirm confirmation-gated actions (replaces the deprecated `--skip_confirmation`) |
| `--no-input` | — | `false` | Never prompt; a gated action without `--yes` exits 2 with no server call |
| `--config <path>` | `GSK_CONFIG` | `~/.genspark-tool-cli/config.json` | Config profile path |

## Output Conventions

| Stream | Content | Consumer |
|--------|---------|----------|
| **stdout** | JSON result | Programs / AI agents |
| **stderr** | Progress, debug, error messages | Human / logs |

Always parse stdout as JSON. Use `--output text` for human-readable output.

**Do NOT merge stderr into stdout when piping to a JSON parser.** `gsk ... 2>&1 | python3 -c "json.load(sys.stdin)"` fails — the stderr progress/spinner text lands ahead of the JSON and breaks the parse at the very first character (`Expecting value: line 1 column 2`). Pipe only stdout: drop stderr with `2>/dev/null`, or leave it on the terminal. Never `2>&1` a command whose stdout you intend to parse.

## Local File Handling

Most commands that accept URLs also accept local file paths. The CLI automatically uploads local files before passing them to the API:

```bash
gsk analyze "Describe this" -i ./photo.jpg
gsk img "Enhance this" -i ./photo.png -o ./result.png
```

Use `-o` / `--output-file` to save generated results directly to a local file.

### Task agent export (`gsk task create ... -o`)

For task agents (docs, slides, sheets), `-o` follows the run live (implies `--follow`) and exports to standard file formats once it completes:

```bash
gsk task create docs --task_name "Project report" --query "Write a project report" --instructions "Formal tone" -o ./report.docx
gsk task create slides --task_name "Pitch deck" --query "Create a pitch deck" --instructions "10 slides" -o ./deck.pptx
gsk task create sheets --task_name "Budget tracker" --query "Build a budget tracker" --instructions "Monthly view" -o ./budget.xlsx
```

| Task Type | Default Export Format |
|-----------|---------------------|
| docs | DOCX |
| slides | PPTX |
| sheets | XLSX |

In ACP mode (`--acp`), use `session/export` instead — see [gsk-acp-agents](../gsk-acp-agents/SKILL.md).

## Configuration Priority

1. **CLI options** (highest)
2. **Environment variables**
3. **Config file** (`~/.genspark-tool-cli/config.json`)

## Security Rules

- Never expose your API key in shared scripts or logs.
- Use `--project-id` for access control when sharing resources.
- The CLI auto-updates every 4 hours. Disable with `GSK_NO_AUTO_UPDATE=1`.

## Built-in Commands

These commands are implemented in the CLI frontend and have no backend adaptor.

### list-tools

List all available tools.

```bash
gsk list-tools    # or: gsk ls
```

### upload

Upload a local file and get a file wrapper URL for use in other commands.

```bash
gsk upload ./image.png
gsk upload ./document.pdf
```

Returns a JSON object with `upload_url` and `file_wrapper_url`.

### download

Download a file from a file wrapper URL.

```bash
# Get download URL only
gsk download "/api/files/s/abc123"

# Download and save to local file
gsk download "/api/files/s/abc123" -s ./downloaded.png
```

| Flag | Description |
|------|-------------|
| `-s, --save <path>` | Download and save to local file path |

Without `--save` the response carries `download_url`, a 24-hour signed URL you can hand to `curl` or an external service. With `--save` the response lists only the saved file — `file_name`, `content_type`, `local_path`, `size_bytes` — and no `download_url`/`original_url`.

### init-opencode

Generate an `opencode.json` config file for [OpenCode](https://opencode.ai), pre-configured to use Genspark's LLM proxy. The server supplies model-specific reasoning variants; select them in OpenCode. MiniMax M3 offers off/always-thinking modes, not depth levels. Unsupported or unverified effort controls are not advertised.

```bash
gsk init-opencode
gsk init-opencode --model claude-sonnet-4-6
gsk init-opencode -o ./my-project/opencode.json
```

| Flag | Default | Description |
|------|---------|-------------|
| `--model <name>` | Server-selected | Default model for OpenCode |
| `-o, --out <path>` | `opencode.json` | Output file path |

Regeneration overwrites the output file; preserve custom settings first.

### init-skills

Sync GSK skill documents into the current project for AI agent discovery. Generates a `CONTEXT.md` entry point and optionally agent-specific config files.

```bash
# Copy skills to .gsk/skills/ and generate CONTEXT.md
gsk init-skills

# Also generate .claude/ config for Claude Code
gsk init-skills --agent claude

# Generate config for all supported agents
gsk init-skills --agent all

# Custom output directory
gsk init-skills -o ./docs/gsk-skills
```

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --out <dir>` | `.gsk/skills` | Output directory for skills |
| `--agent <type>` | — | Generate agent config: `claude`, `gemini`, or `all` |

**Generated files:**
- `CONTEXT.md` — Universal agent entry point listing all available skills
- `.claude/settings.json` — Claude Code context includes (when `--agent claude`)
- `gemini-extension.json` — Gemini extension config (when `--agent gemini`)

### init-genspark-code-skills

Fetch the genspark-code (code sandbox) skill documents into the current project for AI agent discovery. Covers the full developer-skill set a sandbox can install — web / Cloudflare / Flutter / Shopify / HTML5-game development, hosted deployment, and GitHub workflows. The bundle is served by the backend, so newly edited skill docs reach released CLIs without a package update.

```bash
# Copy skills to .genspark-code/skills/
gsk init-genspark-code-skills

# Custom output directory
gsk init-genspark-code-skills -o ./docs/genspark-code-skills
```

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --out <dir>` | `.genspark-code/skills` | Output directory for skills |

A built-in whose requirement the caller doesn't satisfy — the org-only `gsk-hosted-org-member` for a non-member — is omitted, so an agent never sees docs for a capability the server would refuse. Unlike `init-skills`, this command does not generate or touch `CONTEXT.md`.

### AI Drive: local file upload

The `gsk drive upload` command supports streaming local files directly to AI Drive via `--local_file`. This is a CLI-only feature (not in the backend API).

```bash
# Upload a local file to AI Drive (streaming, supports 100MB+ files)
gsk drive upload --local_file ./report.pdf --upload_path /docs/report.pdf
gsk drive upload --local_file ./photo.png              # defaults to /photo.png
gsk drive upload --local_file ./doc.pdf --upload_path /docs/doc.pdf --overwrite true   # edit in place: same id, same link
gsk drive upload --local_file ./report.pdf --upload_path /docs/report.pdf --to ann@example.com   # upload and share; reply carries the link
```

| Flag | Description |
|------|-------------|
| `--local_file <path>` | Local file path to upload (streaming, no size limit) |
| `--overwrite true` | Replace the existing file at the destination path in place; the file keeps its id and share link (`--override` is the older spelling) |
| `--to`, `--general_access` | Share the uploaded file right away (My Drive); the reply's `url` opens for those people |

## Connectors (integrations)

For ANY third-party integration (email, chat, CRM, files, custom MCP
servers), use the unified flow in `../gsk-connector/SKILL.md`:
`gsk connector list` → `search` → `tools <id>` → `call <id> -t <tool> -a '<json>'`.
Never assume a connector is missing without running `gsk connector search` first.
The unified commands are rolling out behind a feature flag; if `gsk connector`
is unavailable (unknown-command error), use the per-service commands from the
`gsk-<service>` skills instead — they remain fully supported.
