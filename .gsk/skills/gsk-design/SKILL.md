---
name: gsk-design
version: 1.0.0
description: Hand off design work from Claude Code (or any AI coding agent) to
  Genspark Designer V2. Launches a local bridge so a visual design agent in the
  browser can read your project, build the UI, and write the result back into
  your repo.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk design --help
---

# gsk-design

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

`gsk design` hands a design task off to Genspark's visual designer agent. You stay in your terminal; the design agent runs in the browser and has read access to the current project so it can match your brand, copy, and existing layouts. When it's done, it writes a handoff bundle (HTML/CSS/assets + a build prompt) back into your working directory under `.cc-bridge-out/handoff_<timestamp>/`. You then ingest that handoff into your project.

## When to use

Use `gsk design` when the user wants a **polished visual artifact** built — a landing page, hero section, marketing page, slide deck, dashboard layout, or any UI that benefits from a dedicated design pass. The design agent is good at:

- Translating a brief into a coherent visual language (typography, color, spacing, motion)
- Producing brand-consistent layouts that read like a real product, not a wireframe
- Generating production-ready HTML/CSS you can drop into your codebase

**Do NOT use** for:

- Small in-place edits ("change this button color", "fix this margin") — just edit the CSS yourself.
- Backend or logic work.
- Debugging an existing layout — the design agent rebuilds, it doesn't repair.

A useful rule of thumb: if the user could plausibly describe the result with a single Dribbble shot, `gsk design` is the right tool. If they're describing a code change, it isn't.

## Prerequisites

- `gsk login` (or `GSK_API_KEY` env var) — see `gsk-shared`.
- Node.js ≥ 22 — the bridge daemon runs on Node.
- A browser on this machine — the design agent runs in the browser the daemon opens.

## Usage

```bash
gsk design [path] [options]
```

**Aliases:** `design`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `[path]` (positional) | No | Working directory for the design session. Defaults to the current directory. The design agent's file-read tools are scoped to this directory. |
| `--prompt <text>` | No | Initial build prompt sent to the design agent as the autostart message. If omitted, the agent waits for the user to type a brief in the browser. Prefer passing one — it skips a manual step and makes the run reproducible. |
| `--launch-url <url>` | No | Override the design page URL. Default: `https://www.genspark.ai/agents?type=design`. Useful for dev/staging or self-hosted Genspark deployments. |
| `--allow-build-tools` | No | Expand the `cc_exec` allowlist from read-only inspection (`ls`, `cat`, `head`, `wc`, …) to include build tools (`git`, `npm`, `python`, `rg`, …). Leave off unless the design agent needs to actually run scripts. |
| `--no-open` | No | Print the launch URL but don't open the browser. Used when you want to copy the URL manually or when you're scripting the bridge from a parent agent. |

## What happens when you run it

1. Two HTTP servers come up on `127.0.0.1` (loopback only — never exposed externally).
2. The launch URL is opened in the user's default browser; the URL embeds a one-shot nonce that the page redeems to obtain a bearer token for this session.
3. The design agent in the browser now has six tools scoped to this bridge session:
   - **`cc_ls`** — list files in your project
   - **`cc_read`** — read a file
   - **`cc_grep`** — search across files
   - **`cc_exec`** — run a command from the allowlist
   - **`cc_copy_to_project`** — write a file *into* the Genspark project (used while the agent is iterating)
   - **`back_to_cc`** — write the final handoff into your repo and end the session
4. The user (or the autostart prompt) tells the design agent what to build. It iterates in the right-hand canvas, occasionally reading files from your project for brand context.
5. When the agent calls `back_to_cc`, a handoff directory appears at `./.cc-bridge-out/handoff_<timestamp>/` in your working dir, containing the produced files plus a `_prompt.txt` describing how to wire them into the codebase.
6. The bridge closes; you can `Ctrl-C` the `gsk design` process (or just close the browser tab).

## Example: deterministic, one-shot run

```bash
cd /path/to/my-app
gsk design \
  --prompt "Design a hero section for our pricing page. Brand colors live in src/styles/tokens.css. The product is called Lumen — an AI-native invoicing tool for freelancers. Match the existing landing page tone."
```

After the design agent finishes:

```bash
ls .cc-bridge-out/handoff_*/
# → hero.html  hero.css  _prompt.txt
cat .cc-bridge-out/handoff_*/_prompt.txt
# Read the integration notes, then move the files into your project as instructed.
```

## Tips for the prompt

- **Anchor it to real files.** "Match `src/styles/tokens.css`" or "use the navigation from `components/Nav.vue`" gives the agent ground truth.
- **Name the product and the audience.** "for freelance invoicing" beats "for our app" — the design agent picks better defaults when it knows the domain.
- **Specify the shape.** "A 3-column pricing table with monthly/annual toggle" yields a usable page; "make pricing nice" yields a mood board.

## Security notes

- The bridge binds `127.0.0.1` only.
- The default `cc_exec` allowlist is read-only — file inspection commands only, no mutating tools.
- `--allow-build-tools` opens build CLIs (git/npm/python/etc.) but still blocks shell metacharacters, inline-code flags (`-c`, `--exec`), and newlines. Don't enable unless the prompt actually needs to run scripts.
- Path inputs are normalized; `..` escape, absolute paths, symlink-out are rejected.
- The handoff dir (`.cc-bridge-out/`) is auto-`.gitignore`'d by the daemon on first write.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags.
