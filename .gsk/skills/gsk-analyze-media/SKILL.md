---
name: gsk-analyze-media
version: 1.0.0
description: Analyze various types of media content including images, audio, and video.
  Returns per-file JSON with the analysis answer inline under `analysis` (full payload
  at `analysis_result_url`).
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk media-analyze --help
---

# gsk-analyze-media

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Analyze various types of media content including images, audio, and video. Returns per-file JSON with the analysis answer inline under `analysis` (full payload at `analysis_result_url`).

## Usage

```bash
gsk media-analyze [options]
```

**Aliases:** `media-analyze`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `-i`, `--media_urls` | Yes | Media URLs / AI Drive paths / repo paths to analyze. (array) |
| `--repo_id` | No | Project repo id from your first-turn context. Required only for repo-relative paths in `media_urls`. (string) |
| `--video_metadata` | No | Video-specific metadata for analysis (optional)Unless the user requires, it is not required to provide (object) |
| `-r`, `--requirements` | No | Always provide this unless analyze_type='video_style_replication'. Must in English, Detailed analysis requirements and goals. Please clearly describe: - What is the purpose of the analysis? - What information needs to be extracted from the media? - What information is most important to you? - How will these analysis results be used? - What are the clips that can be extracted from the video? What are their corresponding time ranges (in milliseconds) and descriptions? - ... (You can add more requirements here) - Specific requirements for different media types (images, audio, video)  For example: 'I need to analyze these materials for emotional tone, main content, use cases for a marketing campaign, other requirements...'  Always ask first what the media semantically depicts (scene, objects, on-screen content) before stylistic, texture, or usage aspects.  Note: This parameter is ignored when analyze_type='video_style_replication'. (string) |
| `--analyze_type` | No | Type of analysis to perform. Options: - '' (empty/default): Standard content analysis based on requirements - 'video_style_replication': Analyze video's cinematography style, expression techniques, and production methods to enable replicating its visual language in new content. When this type is used, a specialized prompt guides the analysis to extract filmmaking craft, aesthetic decisions, and technical approaches that define the video's unique character. The output is suitable for guiding AI video generation systems to replicate similar styles. (string, one of: , video_style_replication) |
| `--analysis_model` | No | Model used for the analysis. Defaults to gemini-3-flash-preview (fast). Use gemini-3.1-pro-preview for quality-critical review passes — e.g. music/audio QC, where the flash default is unreliable. (string, one of: gemini-3-flash-preview, gemini-3.1-pro-preview) |

## Local File Support

Parameters that accept URLs (`--media_urls`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
