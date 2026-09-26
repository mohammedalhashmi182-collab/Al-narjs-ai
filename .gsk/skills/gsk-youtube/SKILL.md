---
name: gsk-youtube
version: 1.0.0
description: 'YouTube operations. Actions: search (find videos by keyword), transcript
  (read a video''s spoken content by video id), comments, download (video/audio file,
  billed 1 credit/MB capped at 1024 credits, 1 GB cap; use -o to save locally).'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk yt --help
---

# gsk-youtube

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

YouTube operations. Actions: search (find videos by keyword), transcript (read a video's spoken content by video id), comments, download (video/audio file, billed 1 credit/MB capped at 1024 credits, 1 GB cap; use -o to save locally).

## Usage

```bash
gsk yt [options]
```

**Aliases:** `yt`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'search': Search YouTube videos by a keyword query; 'transcript': Get a video's transcript and metadata by video id — the video-understanding tool (subtitle text, no visual frames); 'comments': Scrape comments from a YouTube video; 'download': Download the video (mp4) or audio (m4a/webm) file and return a time-limited download URL — billed 1 credit/MB of delivered file (capped at 1024 credits), 1 GB estimated-size cap (string, one of: search, transcript, comments, download) |
| `--query` | No | [search] Keyword query to find videos (string) |
| `--video_id` | No | [transcript] The video id of the youtube video. \| [download] YouTube video id (11 chars) or a full youtube.com / youtu.be URL. (string) |
| `--provide_download_link` | No | [transcript] Whether to provide a download link for the video transcript. (boolean) |
| `--video_url` | No | [comments] YouTube video URL. Supports youtube.com/watch?v=, youtu.be/, and youtube.com/shorts/ formats. (string) |
| `--max_comments` | No | [comments] Maximum number of comments to fetch (default 100, max 500). Higher values take longer to scrape. (integer) |
| `--download_type` | No | [download] video = mp4 with audio (default); audio = audio-only file (m4a/webm, provider-chosen). (string, one of: video, audio) |
| `--video_quality` | No | [download] Target resolution for video downloads (default 720; falls back to best available below the target). (string, one of: 144, 360, 480, 720, 1080, 1440, 2160) |

## Local File Support

Parameters that accept URLs (`--video_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## Output File

Use `-o <path>` / `--output-file <path>` to download the generated result directly to a local file.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
