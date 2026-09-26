---
name: gsk-aidrive
version: 1.0.0
description: 'AI-Drive file storage and management, plus the generic web downloader:
  download_video / download_audio / download_file fetch a URL (YouTube, social media,
  direct file links) server-side into the drive and return a download link. Canonical
  actions: ls, find, mkdir, rm, move, get_readable_url, download, download_video,
  download_audio, download_file, compress, decompress, share, unshare, access, link,
  unlink, upload, list_trash, restore, tree, search, read, overview, copy. `copy`
  makes new entries with new ids in any folder you can write, like the web''s Copy
  to; they take that folder''s access, not the originals'' shares. Selected Context:
  reuse source/id directly; read a known file, search a known topic, tree for bounded
  structure and existing overviews. read returns a version, coverage, continuation
  and source url. overview returns cached summaries and queues missing/stale ones
  without blocking reads. `rm` moves native entries to recoverable trash and unlinks
  delegated aliases without touching their source. `ls` reads one directory; use indexed
  `find` to locate names across the drive. `shared_with_me` is a view across source
  containers; list it only when no source is known, then reuse `source_id`. A delegated
  LinkNode row returns `link_workspace_id`; reuse it as `--source` to mount the live
  source entry. `download <ai-drive-path> [local-path]` copies a drive file OUT to
  local disk (the path may be spelled `aidrive://...`); `download_file --file_url
  <url>` goes the opposite direction, saving an external URL INTO the drive. share
  / access / link replies carry `url`, the entry''s share link — hand that to the
  user; `readable_url` is a one-hour bytes URL for tools.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk drive --help
---

# gsk-aidrive

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

**SOURCE DISCOVERY:** `../gsk-second-brain/SKILL.md` explains Drive sources and addressing. With a selected source/id, use the Context commands below directly; consult that guide when the source is unknown.

AI-Drive file storage and management, plus the generic web downloader: download_video / download_audio / download_file fetch a URL (YouTube, social media, direct file links) server-side into the drive and return a download link. Canonical actions: ls, find, mkdir, rm, move, get_readable_url, download, download_video, download_audio, download_file, compress, decompress, share, unshare, access, link, unlink, upload, list_trash, restore, tree, search, read, overview, copy. `copy` makes new entries with new ids in any folder you can write, like the web's Copy to; they take that folder's access, not the originals' shares. Selected Context: reuse source/id directly; read a known file, search a known topic, tree for bounded structure and existing overviews. read returns a version, coverage, continuation and source url. overview returns cached summaries and queues missing/stale ones without blocking reads. `rm` moves native entries to recoverable trash and unlinks delegated aliases without touching their source. `ls` reads one directory; use indexed `find` to locate names across the drive. `shared_with_me` is a view across source containers; list it only when no source is known, then reuse `source_id`. A delegated LinkNode row returns `link_workspace_id`; reuse it as `--source` to mount the live source entry. `download <ai-drive-path> [local-path]` copies a drive file OUT to local disk (the path may be spelled `aidrive://...`); `download_file --file_url <url>` goes the opposite direction, saving an external URL INTO the drive. share / access / link replies carry `url`, the entry's share link — hand that to the user; `readable_url` is a one-hour bytes URL for tools.

## Usage

```bash
gsk drive [options]
```

**Aliases:** `drive`

## What this command reaches

`gsk drive` opens the **Drive** half of the user's Second Brain — My Drive,
Team Drive, and the Shared-with-me view. For selected Context, start with the
commands below. To find a Team Drive, or to create, replace, rename, move, or
share files, see "Finding drives", "Working with files", and "Sharing" further
down. Consult `../gsk-second-brain/SKILL.md` to resolve shortcuts or work with
GenTeam channel drives.

## Reading selected Context

Reuse the selected `source` and stable `id` without listing every shared source.
For a known file, call `read`; for a topic, call `search`; use `tree` when you
need structure. None of these requires generating an overview first.

If a new action or flag is rejected, retry once with `gsk --refresh aidrive ...`
to reload cached tool metadata. Do not refresh on every call. If the refreshed
manifest still lacks it, the backend has not enabled that capability; use the
existing supported commands and preserve their coverage limits.

```bash
gsk aidrive tree --source '<selected-source>' --depth 2 --limit 100
gsk aidrive search --source '<selected-source>' --query 'Benefits' --query_scope subtree
gsk aidrive search --source '<selected-source>' --queries '["Benefits", "PTO"]'
gsk aidrive read --source '<selected-source>' --id '<entry_id>' --char_limit 12000
gsk aidrive read --source '<selected-source>' --ids '<file-id-1>' '<file-id-2>' '<file-id-3>' --char_limit 2000
gsk aidrive read --source '<selected-source>' --id '<entry_id>' --offset 12000 --source_version '<version>'
gsk aidrive overview --source '<selected-source>' --id '<entry_id>'
gsk aidrive overview --source '<selected-source>' --ids '<entry-id-1>' '<entry-id-2>'
gsk aidrive overview --source '<selected-source>' --id '<entry_id>' --generate true
```

`tree` is breadth-first metadata, bounded by depth, nodes, bytes and query time.
Continue with its `cursor` and the same root/source/depth. Expand returned folder
IDs when deeper traversal or deferred expansion is needed. Overview fields are
existing source-language plain text; listing never generates them.
`directories` reports completed listings and proven-empty directories; do not
list them again. File `size_bytes` and short overview excerpts help select
representative content without opening many tiny placeholders.
Use them to choose query vocabulary and a starting folder, then search that
folder with its returned `entry_id`/`source_id`. Keep the user's selected root:
overview is not evidence that sibling folders lack relevant content. Missing
or stale overview does not block querying. Request up to 6 relevant overviews from
one source with `--ids` in one call; missing/stale summaries enqueue asynchronously.
Continue search/read while they prepare, then reuse ready summaries for navigation.
Read originals for exact facts. A folder overview may use names and child summaries;
it does not mean all descendants were read.

`search` supports `children`, `subtree` (default) and `drive` (drive-root only),
with `all`, `filename` or `content` search modes. Results are ranked index
candidates checked against the live selected scope. Follow the cursor even when
a bounded page is empty. `coverage`, `effective_mode` and `has_more` describe the
actual search; zero hits do not prove that unindexed source text is absent.
Use `queries` for up to three complementary queries sharing one output budget;
each result keeps its query and its own continuation cursor. Continue one query
with `query` and that cursor. Do not collapse distinct user conditions into one rewrite.
Index failure may explicitly fall back to filenames. Overview text is not indexed.

Pass each returned `entry_id` as `--id` and retain `source_id` as `--source`.
`read` returns character ranges from persisted text, its source version,
available coverage and a human-openable `url`. `coverage=complete` and
`source_complete` describe extraction, not how much this response contains.
`returned_characters` counts this response; `contains_full_document` is true
only when it includes the complete document from offset 0. For a whole-document
summary, start at offset 0 and copy `next_read` as flags to `gsk drive read`
until `next_offset` is null and `source_complete` is true. On older servers,
use `--id` with `next_offset` and the same `source_version`. A last page alone is not the
whole document; partial extraction can end without a next offset.
Bound output with `--char_limit`, `--limit` and `--byte_limit`, not `head` or
string slicing of the JSON: truncation can discard coverage and continuation.
The GSK JSON envelope puts Context query results directly in `data`.
For `get_readable_url`, `data.result` is prose; extract the structured URL from
`session_state.aidrive_result.readable_url`, not `data.aidrive_result`.
Small UTF-8 text files can read directly without a search index. Other reads
already wait briefly for indexing internally. For a folder introduction, use
one tree and `read --ids` for 2–4 representative files. A batch accepts at most
6 files; reads run concurrently, share a 16 KB text budget and return individual coverage and continuation in
`data.files`. State what you sampled; do not inspect every file by default.
For `index_pending`, do other useful reads first and retry once only if needed,
copying `retry_read` as flags (including its bounded `wait_seconds`) without
an extra shell sleep. Use `gsk --refresh` for the first retry with `wait_seconds`
to refresh an older cached schema. On older servers, respect `retry_after_seconds`. If text remains
unavailable or incomplete, use `get_readable_url --id <entry_id>` or `download`
with an appropriate parser and state what was actually read. `--entry_id` is
the restore selector; use `--id` for these reads. Do not retry denied access
through another tool. Successful reads can
refresh file and direct-parent overviews asynchronously from a complete cache.
Cite `[title](returned url)` with the source `url` verbatim, never a temporary
`readable_url`. Never prefix a Drive citation with `memo:`; that opens a vault
note instead and breaks the source link.
Reuse a human-openable `url` returned by `read` or `upload` directly; no `gsk me`
call or manual URL reconstruction is needed when the result already has it.

For active Office documents and edits, use **wo-peer** with the returned
collaboration identifiers. Indexed text is a persisted snapshot, not the live
room. Download only when local processing requires it; editing does not require
download, replace and re-upload.

## Finding drives

- `gsk drive ls -p /` lists My Drive. `gsk drive ls --workspace shared_drive`
  lists every shared drive you can open, and each text line says what it is:
  `(Team Drive, edit, directory)`; `(in Team Drive 'Finance', view, file)` for
  something shared out of a Team Drive rather than the drive itself;
  `(GenTeam channel, …)`, `(GenTeam direct message, …)`, `(Hub, …)`,
  `(Ask Org knowledge, …)`. `--workspace shared_with_me` adds what people
  shared from their own My Drive: `(shared by <name>, …)`. The JSON rows carry
  `source_id`, `source_type`, `is_drive_root`, `drive_source_name`, and `owner_name`.
- Work inside one with `--workspace shared_drive --source <source_id>`; paths
  are relative to it. A browser address `/.shared-workspace/<source_id>/…`
  works as `--path` or `--upload_path` on its own.
- Not listed: Team Drives an org admin sees on the web without holding access
  to them (admin access there is governance only). Creating, renaming, and
  deleting a Team Drive itself happens on the web.

## Working with files

| Task | My Drive | Team Drive (add `--workspace shared_drive --source <source_id>`) |
|---|---|---|
| New folder | `gsk drive mkdir --path /Reports` | same (editors) |
| Upload a local file | `gsk drive upload --local_file ./q3.pdf --upload_path /Reports/q3.pdf` | same |
| Replace a file, keeping its link | `… --upload_path /Reports/q3.pdf --on-conflict overwrite` | same |
| Rename | `gsk drive move --path /Reports/q3.pdf --target_path /Reports/q3-final.pdf` | same |
| Move into a folder | `gsk drive move --path /q3.pdf --target_path /Reports` | same, within one source |
| Delete | `gsk drive rm --path /Reports/old.pdf` (to trash) | same (editors) |
| Restore | `gsk drive list_trash`, then `restore --entry_id <id>` | on the web |
| Copy into a folder | `gsk drive copy --path /Reports/q3.pdf --target_path /Archive` | same; `--target_source my_drive` copies out to My Drive |
| Copy beside the original | `gsk drive copy --path /Reports/q3.pdf` (lands as `q3(1).pdf`) | same |

- `move` into an existing folder moves the entry; a new last segment renames
  it; a name that already exists is refused (move never overwrites). Rename
  and replace keep the entry's id, so its share link keeps working.
- An upload with `--file_content` needs its folder to exist (`mkdir` first);
  a local-file upload creates missing folders.
- `--upload_path` is the file's own full path: one that names a folder, or
  ends in `/`, is refused rather than saved as a copy beside the folder.
- gsk 1.14 and later also read paths given as operands: `gsk drive ls
  /Reports`, `gsk drive move /q3.pdf /Archive`, `gsk drive find budget
  /Reports`, `gsk drive upload ./q3.pdf /Reports/`. Earlier versions need the
  flags shown in the table. A list flag like `--ids` takes every word after
  it: give the destination before it, or as `--target_path`.
- `copy` works across drives: `--target_source` is `my_drive` or a
  `source_id` (default: the drive copied from) and `--target_path` a folder
  in it; a web address `/.shared-workspace/<source_id>/<folder>` names both.
  `--ids` copies up to 16 entries of one source in one job. Copies are new
  entries with new ids: they open for whoever can open the folder they land
  in, not for the originals' shares, and the reply lists each copy's link.
  A person runs one copy at a time. A copy still running after about 20
  seconds answers with a job id: read it back with `gsk drive copy --job_id
  <id>`; one that stopped continues with `--job_id <id> --retry true`,
  keeping what it copied. Copying needs download rights on the source and
  edit rights on the destination; GenTeam channel and DM drives take files,
  not folders.
- GenTeam channel and DM drives are flat: files go at the root, and only a
  channel admin can move, rename, or delete them.

## Sharing

| Audience | My Drive | Team Drive entry | GenTeam channel / DM / Hub drive |
|---|---|---|---|
| A person | `share --to a@x.com`; an address without an account becomes a pending invite | managers; the person needs an account | membership comes from the product |
| Your org | `share --to org` | `share --to org` (the drive's org) | — |
| A group | `share --to group:<uid>` | not available | — |
| Anyone with the link | `share --general_access link` | managers | — |
| A GenTeam channel | `share --to channel:<server_id>:<channel_id>` (posts a card unless `--post_card false`) | managers, same form | — |
| Undo | `unshare --to …`, or `unshare --general_access restricted` | managers | — |

- A new email share notifies that person with the link, on My Drive and Team
  Drives alike; org, group, and link access notify no one.
- General access is ONE setting: restricted, your org, or anyone with the
  link. `--to org` and `--general_access org` set the same thing and replace
  link access; `unshare --to org` returns it to restricted.
- `access` shows who can open an entry; for a Team Drive entry, managers see
  the full list, including what it inherits from the folders above it.
- `gsk drive link --path <My Drive entry> --workspace shared_drive --source
  <Team Drive, channel, or Hub> [--target_path <folder in it>]` places a
  shortcut to your file in a shared drive; its members open your original.
  `gsk drive unlink --workspace shared_drive --source <link_workspace_id>`
  removes the shortcut.

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform (string, one of: ls, find, mkdir, rm, move, get_readable_url, download, download_video, download_audio, download_file, compress, decompress, share, unshare, access, link, unlink, upload, list_trash, restore, tree, search, read, overview, copy) |
| `--workspace` | No | AI Drive location. my_drive owns your bytes and quota; shared_drive selects managed org, GenTeam, Hub, or authorized knowledge drives; shared_with_me is an ACL-filtered view across both kinds of container and owns no bytes or quota. GenTeam drives are flat: upload files or share source folders at the root; no native mkdir. In GenTeam channel and DM drives, moving, renaming, and deleting native files needs a channel admin; Team Drive editors can do all three. (string, one of: my_drive, shared_with_me, shared_drive, default: `my_drive`) |
| `--source` | No | Stable source_id returned by ls in shared_with_me or shared_drive. It identifies the storage-owning drive and entry; names are accepted only when unique. (string) |
| `--share` | No | Deprecated alias for source, retained for older gsk scripts. (string) |
| `--scope` | No | For find only: search My Drive, accessible shared sources, or both. Use all when only a filename is known. Cannot combine with source/id/url; a specific source keeps the existing directory search behavior. Aggregate search is bounded; inspect coverage before concluding a file is absent. (string, one of: mine, shared, all) |
| `--to` | No | Who to share with, for share/unshare: an email address; My Drive also accepts 'org' / 'group:<uid>' and 'channel:<server_id>:<channel_id>' (a GenTeam channel you belong to — the file is opened to its members and, unless post_card is false, posted there as a card). Managed Drive sources use email or general_access; a Team Drive source (workspace=shared_drive, source=<source_id>) also takes 'channel:…' — for its root, or for one entry inside it named by path (relative to the source) or id — when you manage sharing there. Also accepted by upload into My Drive: the file is shared the moment it lands and the reply carries the link that opens for them. A new email share notifies that person with the link. A Team Drive email share needs manager rights and an existing account; My Drive can share with an address before it signs up. (string) |
| `--post_card` | No | For share to a channel: also post the document card into the channel (default true). false opens the file to the channel's members without a message. (boolean, default: `True`) |
| `--permission` | No | What the recipient or delegated mount may do: view or edit (share/link). The public link audience can only ever view. (string, one of: view, edit, default: `view`) |
| `--link_name` | No | Optional destination alias for link. The source entry's current name is used when omitted. (string) |
| `--general_access` | No | Who else can open it, for share without a recipient: restricted, org, or link. Also accepted by upload into My Drive, to open the new file at once. (string, one of: restricted, org, link) |
| `--organization_id` | No | Which organization to share with, when you belong to more than one and use to=org or to=group:<uid>. (string) |
| `--expires_at` | No | Optional ISO-8601 UTC instant after which the access stops, e.g. 2026-12-31T00:00:00+00:00. (string) |
| `-p`, `--path` | No | Path to file or folder for ls, mkdir, rm, move, get_readable_url. For link: the existing source path in My Drive. For unlink: the LinkNode path in the selected managed source. For compress: folder path to compress. For decompress: archive file path to extract. For find: which directory to search. Omit it to search the whole of My Drive, or the root of the selected shared source. Naming a directory searches THAT DIRECTORY ONLY and does not descend into its subfolders — and a shared folder's own root is one such directory. To cover a subtree, use search with query_scope=subtree. tree/search/read/overview also accept a path relative to source or id. (string) |
| `-q`, `--query` | No | Search text. search uses ranked indexed text and names; see search_mode and query_scope. For find: case-insensitive substring matching on the entry name, and on stored search metadata for typed links. A multi-word query matches entries containing EVERY word, in any order — 'budget 2025' finds '2025 budget'. Words are split on spaces only, so a space-free script (Chinese, Japanese) stays one term. (string) |
| `-f`, `--filter_type` | No | Filter by entry type for ls (improves performance): all (default), file, directory. Use 'file' when only need files. (string, one of: all, file, directory) |
| `--file_type` | No | Filter by file MIME type for ls (improves performance): all (default), audio, video, image. Combine with filter_type='file' for best results. (string, one of: all, audio, video, image) |
| `--target_path` | No | Destination entry path for move; destination directory for restore (the original filename is retained); destination directory inside the selected Team Drive source for link; destination folder for copy, in target_source's drive (a web Drive address /.shared-workspace/<source_id>/<folder> names the drive by itself). (string) |
| `--target_source` | No | For copy: the drive the copies go to, my_drive or a source_id from `ls --workspace shared_drive`. Defaults to the drive being copied from. Without target_source and target_path, each copy lands beside its original as name(1).ext. (string) |
| `--job_id` | No | For copy: the job id a copy still in progress answered with. Alone, it reads that copy's progress and, once done, its links; with retry=true it continues a copy that stopped. (string) |
| `--retry` | No | For copy with job_id: true continues a copy that stopped (ran out of time, failed) from where it stopped; the entries already copied are kept. (boolean) |
| `--entry_id` | No | Stable entry id, required by restore. (string) |
| `--id` | No | Address most actions by a stable entry id instead of a path — a folder id for ls/find/upload/mkdir, a file id for get_readable_url/download/rm/move. Ids come from ls/find rows and from Drive URLs (#p_fid=…, ?id=…, /s/<owner>/<id>). Your own drive is tried first, then folders shared with you; pass --owner when the URL names one. (string) |
| `--owner` | No | Owner (cogen id) of the entry given by --id, as carried by /s/<owner>/<id> and ?link=<owner>:<folder> URLs. Optional. (string) |
| `--url` | No | A Drive URL copied from the browser (drive?path=…, #p_fid=…, ?id=…&link=…, /s/<owner>/<id>). The ids it carries are extracted and resolved exactly like --id/--owner. (string) |
| `--target_folder` | No | Destination folder for download_video, download_audio, and download_file (string) |
| `--video_url` | No | Video URL to save into Drive with download_video. YouTube: billed 1 credit per MB of the delivered file (min 1 credit); downloads estimated over 1 GB are rejected up front. (string) |
| `--audio_url` | No | Audio/video URL to save into Drive with download_audio. YouTube: billed 1 credit per MB of the delivered file (min 1 credit); downloads estimated over 1 GB are rejected up front. (string) |
| `--file_url` | No | External file URL to save into Drive with download_file (string) |
| `--file_name` | No | Filename for download_file (for example annual_report.pdf); inferred when omitted (string) |
| `--file_content` | No | Content to upload to AI Drive. Can be plain text or base64-encoded binary data. For text files (txt, md, json, csv, etc.), provide plain text content. For binary files, provide base64-encoded content with 'base64:' prefix. Size limit: 1MB without confirmation, 5MB absolute maximum. (string) |
| `--upload_path` | No | Where the upload lands: the full file path (must start with '/' and include the file name), relative to --source in a shared drive. A web Drive address /.shared-workspace/<source_id>/<path> selects that shared drive by itself. To upload a new version of an existing file, reuse the same path with overwrite=true instead of creating v2/_final name variants; give genuinely new artifacts (e.g. each run of a recurring workflow) their own path. In GenTeam drives, upload at the root. With file_content the parent folder must exist (mkdir first); a local-file upload creates missing folders. (string) |
| `--overwrite` | No | Set to true to replace the file at upload_path in place (upload only). It keeps the file's id, so a share link already handed out opens the new bytes. Without it, a file_content upload fails when the name exists and a local-file upload is saved as name(1).ext under a new id. Local-file uploads also take --on-conflict overwrite, which gsk 1.10 and later honor; gsk 1.13.1 and earlier ignore --overwrite for them. (boolean) |
| `--content_type` | No | MIME type of the content. If not provided, will be auto-detected from filename. Common types: text/plain, text/markdown, application/json, text/csv (string) |
| `--confirmed` | No | Set to true to confirm upload when: (1) file size > 1MB, or (2) content contains potentially sensitive patterns. If confirmation is required but not provided, upload will fail with a warning. (boolean) |
| `--ids` | No | Read up to 16 ids, automatically limited to 6 concurrent reads, with one shared output budget. Overview accepts up to 6 ids. Copy takes up to 16 ids from one source in one job. Retain source; omit id/path/offset. (array) |
| `--queries` | No | For search: up to 3 queries in one request. Each returns its own cursor; omit query/cursor. (array) |
| `--query_scope` | No | For search: children, subtree (default), or drive (requires a selected drive root). (string, one of: children, subtree, drive, default: `subtree`) |
| `--search_mode` | No | For search: all (names and indexed text), filename, or content. Coverage is reported explicitly. (string, one of: all, filename, content, default: `all`) |
| `--limit` | No | Maximum results: tree 1–200 (default 100), search 1–50 (default 20). (integer) |
| `--byte_limit` | No | Maximum query output bytes: tree 4096–65536 (default 20480), search 8192–65536 (default 32768). (integer, default: `32768`) |
| `--depth` | No | Tree breadth-first depth, 1–6 (default 2). Expand a returned folder id for deeper browsing. (integer, default: `2`) |
| `--cursor` | No | Read: pass only the returned cursor to continue the exact file/version and track contiguous coverage; omit selectors and offset. Tree/search: keep the same id/source/query. Restart if expired or changed. (string, default: ``) |
| `--offset` | No | Read character offset (default 0). Copy the previous result's next_read, including source_version. (integer, default: `0`) |
| `--char_limit` | No | Read character budget, 1–24000 (default 12000); larger integer budgets are capped at 24000. (integer, default: `12000`) |
| `--source_version` | No | Source version returned by read; required for continuation. (string, default: ``) |
| `--wait_seconds` | No | Read: wait for an empty pending index, 0–15 seconds (default 6). Reuse retry_read once. (number, default: `6.0`) |
| `--generate` | No | For overview: return cached summaries; missing/stale summaries are queued asynchronously. Continue search/read without waiting. True also requests refresh of an existing summary. (boolean, default: `False`) |

## Address by id or URL

- Most actions accept `--id <entry_id>` instead of a path: a folder id for `ls`/`find`/`upload`/`mkdir`, a file id for `get_readable_url`/`download`/`rm`/`move`/`share`/`access`. Ids appear in `ls`/`find` rows and in Drive URLs (`#p_fid=…`, `?id=…`, `/s/<owner>/<id>`). Your own drive is tried first, then folders shared with you. (`restore` takes `--entry_id`; `link` names its My Drive entry with `--path`.)
- Add `--owner <cogen_id>` when the URL names one (`/s/<owner>/<id>`, `?link=<owner>:<folder>`), or just pass the whole address with `--url <browser-url>` — the ids are extracted for you.
- With a folder id, a `--path`/`--upload_path` you also pass is RELATIVE to that folder: `mkdir --id <folder> --path reports` creates `<folder>/reports`; `upload --id <folder> --local_file x.pdf` lands in the folder.
- A web Drive address `/.shared-workspace/<source_id>/…` (the `path=` of a browser URL) works as `--path` and as `--upload_path`: it selects that shared drive under the same edit permission as `--source`. Pass it alone; together with `--source`, `--id` or `--url` it is refused.

## Local Drive Transfers

- Upload a file or directory with `gsk drive upload --local_file <local-path> --upload_path /folder/name.ext`, on any gsk version. gsk 1.14 and later also take `gsk drive upload <local-path> /folder/` (or `-p /folder/`): the upload goes into that folder under its own name, and a last name with the file's extension renames it; gsk 1.13.1 and earlier ignore both and land the file at the drive root. Missing folders on the path are created. For shared locations, also pass `--workspace shared_with_me|shared_drive --source <source_id>`. The source drive owns the uploaded bytes and quota. The reply carries the file's `id` and `url`.
- Edit in place: upload the new bytes to the SAME path with `--on-conflict overwrite`, which gsk 1.10 and later honor (newer gsk also accepts `--overwrite true`; gsk 1.13.1 ignores it for local files). The file keeps its id, so the link already sent keeps opening the new version; a same-name upload without it lands as `name(1).ext` under a new id, and `--on-conflict error` refuses instead. Office files open in the editor are edited through wo-peer, not uploaded over.
- Upload and share in one step: `gsk drive upload --local_file <path> --upload_path /<name> --to <email|org|channel:…>` or `--general_access link|org` (My Drive only). The reply's `url` then opens for those people, and each new email recipient is notified with the link.
- Download to this machine with `gsk drive download <drive-path> [local-path]`; this is distinct from `download_file`, which saves an external URL into Drive.

## Discover, resolve, and collaborate

- Only when the source is unknown, use `ls -p /` for My Drive, `ls --workspace shared_drive` for Team/channel/DM/Hub sources, or `ls --workspace shared_with_me` for all shared sources. Reuse source IDs; duplicate source names require an explicit ID.
- With only a name, use `find --scope all -q <name>`; `mine` and `shared` narrow it. Reuse a hit's `entry_locator` (workspace/source/path). Search is bounded and may use an incomplete index: inspect coverage and never interpret no matches as proof of absence.
- A LinkNode path follows its live source for reads, folder browsing and uploads. Its `content_source_id`/`link_workspace_id` also opens that source at `/`. Do not combine the content mount with the alias's old path. `rm`/`move` on the alias operate on the alias; on a child they operate inside its source. Cross-source moves are refused. Shared source roots cannot be removed. Source-owned shared projections cannot be moved/renamed; unlinking may end that audience's share, reported by share_ended, while preserving source bytes.
- `get_readable_url` returns the native `entry_id` and, for Office files, `collaboration.file_id` and `link_workspace_id`. For live editing use `wo-peer open <file_id> --link-workspace-id <context>` (omit the flag for My Drive). Never use the shortcut ID as the room ID. Minting rechecks edit access; PDF and project links are not Office rooms.
- A DM reference grants no source access by itself. Revoked/unavailable/view-only results are permission outcomes; retrying download on the LinkNode cannot fix them.

## Which link to hand the user

- `read`, `upload`, `share`, `access`, and `link` replies carry `url`, and a `copy` reply one `url` per copy: the entry's share link (`/second-brain/s/<drive>/<entry>`, or `/aidrive/s/…` where the sharer's org blocks Second Brain). It carries no access of its own — the server decides per visitor — so paste THAT into chat, email, or a card. Reuse it without an identity lookup or URL reconstruction.
- `upload` replies carry the new file's `url` too — but the link opens only for people the file is shared with, so share it (`--to` on the upload, or `gsk drive share --id <id> …`) before handing it out.
- `download_*`, `compress`, and `decompress` replies carry a browse-location link to the folder in the user's own drive.
- `ls`/`find` rows for shared shortcuts show their open link in the Type cell (`link:file → <url>`).
- `get_readable_url` is a one-hour bytes URL for tools (`curl`, media analysis). Never hand it to a person as "the link": it expires, and it opens for whoever holds it.

## YouTube Downloads

`download_video` / `download_audio` with a YouTube URL bill 1 credit per MB of the delivered file (min 1 credit); requests estimated over 1 GB are rejected up front. Time-range clipping is not supported for YouTube — provider clip downloads are broken, so download the full video and trim it locally.

## Local File Support

Parameters that accept URLs (`--video_url`, `--audio_url`, `--file_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
