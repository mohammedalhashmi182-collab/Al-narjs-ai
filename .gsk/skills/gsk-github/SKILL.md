---
name: gsk-github
version: 1.0.0
description: 'GitHub operations. Actions: list_repos, search_issues, create_issue,
  update_issue.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk github --help
---

# gsk-github

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

GitHub operations. Actions: list_repos, search_issues, create_issue, update_issue.

## Usage

```bash
gsk github [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list_repos': List repositories for the authenticated user; 'list_commits': List a repo's commits, filterable by author and ISO 8601 time range; 'get_commit': Read one commit's message, stats, and changed files; 'list_prs': List a repo's pull requests with author, state, and merged_at; 'list_contributors': List a repo's contributors (logins + commit counts) — the raw material for resolving a person's name to their GitHub login; 'user_activity': Recent activity feed (pushes/PRs/reviews/comments) for a GitHub login; private repos covered for the authenticated user only; 'search_issues': Search issues and pull requests; 'get_issue': Read a single issue by number; 'create_issue': Create a new issue; 'update_issue': Update an existing issue; 'list_comments': List comments on an issue or pull request; 'create_comment': Post a new comment on an issue or pull request; 'update_comment': Edit an existing comment by id (string, one of: list_repos, list_commits, get_commit, list_prs, list_contributors, user_activity, search_issues, get_issue, create_issue, update_issue, list_comments, create_comment, update_comment) |
| `--visibility` | No | [list_repos] Filter by repository visibility. Default: all. (string, one of: all, public, private) |
| `--affiliation` | No | [list_repos] Comma-separated list of affiliation types: owner, collaborator, organization_member. Default: owner,collaborator,organization_member. (string) |
| `--sort` | No | [list_repos] How to sort the results. Default: updated. \| [list_prs] How to sort the results. Default: created. \| [search_issues] How to sort results. If omitted, defaults to 'created' (newest-first) so recent issues surface first instead of GitHub's relevance ranking. Pass 'updated' to sort by last-updated, or another value to override. (string, one of: created, updated, pushed, full_name) |
| `--direction` | No | [list_repos] Sort direction. Default: desc (except for full_name). \| [list_prs] Sort direction. Default: desc. (string, one of: asc, desc) |
| `--per_page` | No | [list_repos] Number of results per page (max 100). Default: 30. \| [list_commits] Number of results per page (max 100). Default: 30. \| [list_prs] Number of results per page (max 100). Default: 30. \| [list_contributors] Number of results per page (max 100). Default: 30. \| [user_activity] Number of events per page (max 100). Default: 30. \| [search_issues] Number of results per page (max 100). Default: 30. \| [list_comments] Number of results per page (max 100). Default: 30. (integer) |
| `--page` | No | [list_repos] Page number of the results. Default: 1. \| [list_commits] Page number of the results. Default: 1. \| [list_prs] Page number of the results. Default: 1. \| [list_contributors] Page number of the results. Default: 1. \| [user_activity] Page number of the results. Default: 1. \| [search_issues] Page number of the results. Default: 1. \| [list_comments] Page number of the results. Default: 1. (integer) |
| `--owner` | No | [list_commits] The account owner of the repository (username or organization name). \| [get_commit] The account owner of the repository (username or organization name). \| [list_prs] The account owner of the repository (username or organization name). \| [list_contributors] The account owner of the repository (username or organization name). \| [get_issue] The account owner of the repository (username or organization name). \| [create_issue] The account owner of the repository (username or organization name). \| [update_issue] The account owner of the repository (username or organization name). \| [list_comments] The account owner of the repository (username or organization name). \| [create_comment] The account owner of the repository (username or organization name). \| [update_comment] The account owner of the repository (username or organization name). (string) |
| `--repo` | No | [list_commits] The name of the repository (without the owner prefix). \| [get_commit] The name of the repository (without the owner prefix). \| [list_prs] The name of the repository (without the owner prefix). \| [list_contributors] The name of the repository (without the owner prefix). \| [search_issues] Repository in 'owner/repo' format to search within. Will be added to the query. \| [get_issue] The name of the repository (without the owner prefix). \| [create_issue] The name of the repository (without the owner prefix). \| [update_issue] The name of the repository (without the owner prefix). \| [list_comments] The name of the repository (without the owner prefix). \| [create_comment] The name of the repository (without the owner prefix). \| [update_comment] The name of the repository (without the owner prefix). (string) |
| `--author` | No | [list_commits] Filter by commit author — a GitHub login or an email address. Omit to list all authors' commits. (string) |
| `--since` | No | [list_commits] Only commits after this ISO 8601 timestamp (e.g. '2026-06-27T00:00:00Z'). \| [list_comments] Only return comments updated at or after this ISO-8601 timestamp (e.g. '2025-01-01T00:00:00Z'). Useful for incremental polling. (string) |
| `--until` | No | [list_commits] Only commits before this ISO 8601 timestamp. (string) |
| `--path` | No | [list_commits] Only commits touching this file or directory path. (string) |
| `--sha` | No | [get_commit] The commit SHA (full or abbreviated) or a ref name. (string) |
| `--state` | No | [list_prs] Filter by PR state. Default: all. \| [search_issues] Filter by issue state. Will be added to the query. \| [update_issue] State of the issue. Use 'closed' to close the issue, 'open' to reopen it. (string, one of: open, closed, all) |
| `--username` | No | [user_activity] The GitHub login whose activity to fetch. (string) |
| `--q` | No | [search_issues] Search query using GitHub search syntax. Examples: 'repo:owner/repo is:issue is:open', 'author:username', 'label:bug', 'state:closed' (string) |
| `--labels` | No | [search_issues] Comma-separated list of labels to filter by. \| [create_issue] Labels to associate with this issue (e.g., ['bug', 'enhancement']). \| [update_issue] Labels to set on this issue (replaces existing labels). (string) |
| `--assignee` | No | [search_issues] Filter by assignee username. (string) |
| `--order` | No | [search_issues] Sort order. Default: desc. (string, one of: asc, desc) |
| `--issue_number` | No | [get_issue] The number of the issue to read (required). \| [update_issue] The number of the issue to update (required). \| [list_comments] The number of the issue (required). \| [create_comment] The number of the issue to comment on (required). (integer) |
| `--title` | No | [create_issue] The title of the issue (required). \| [update_issue] New title of the issue. (string) |
| `--body` | No | [create_issue] The contents/description of the issue. Supports Markdown. \| [update_issue] New contents/description of the issue. Supports Markdown. \| [create_comment] The contents of the comment. Supports Markdown. \| [update_comment] New contents of the comment. Supports Markdown. (string) |
| `--assignees` | No | [create_issue] Logins/usernames of users to assign to this issue. \| [update_issue] Logins/usernames to assign to this issue (replaces existing assignees). (array) |
| `--milestone` | No | [create_issue] The milestone number to associate with this issue. \| [update_issue] The milestone number to associate with this issue. Set to null to remove milestone. (integer) |
| `--comment_id` | No | [update_comment] The id of the comment to update (NOT the issue number — that's a different identifier). Get this from github_create_comment's response or github_list_comments. (integer) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
