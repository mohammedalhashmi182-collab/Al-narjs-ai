---
name: gsk-audio-generation
version: 1.0.0
description: Generate audio (TTS, sound effects, music) with per-model params; query
  get_model_info for each model's params_schema.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk audio --help
---

# gsk-audio-generation

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Generate audio (TTS, sound effects, music) with per-model params; query get_model_info for each model's params_schema.

## Usage

```bash
gsk audio [options]
```

**Aliases:** `audio`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<prompt>` (positional) | No | What to generate: narration text for TTS (model-specific format — see the model's prompting guide), or a description for music / sound effects. For voice-clone models this text is narrated with the cloned voice. (string) |
| `-m`, `--model` | No | Model id. Query get_model_info with it before generating. (string, one of: CassetteAI/music-generator, alibaba/qwen-audio-3-tts, bytedance/seed-audio-1.0, elevenlabs/music, elevenlabs/sound-effects, elevenlabs/v3-tts, elevenlabs/v4-tts, elevenlabs/voice-changer, elevenlabs/voice-clone, fal-ai/elevenlabs/sound-effects, fal-ai/elevenlabs/tts/multilingual-v2, fal-ai/minimax/speech-2.8-hd, fal-ai/minimax/voice-clone, fal-ai/vibevoice/7b, google/gemini-3.1-flash-tts-preview, google/gemini-3.8-flash-lite-tts, google/gemini-3.8-flash-tts, google/lyria-music, minimax/music-3.0, mureka, nova-sr) |
| `-p`, `--params` | No | Model-specific parameters (speakers, speed/pitch/volume, duration, voice_files, lyrics, composition_plan, output_format, ...). MUST follow the `params_schema` that get_model_info returns for the chosen model. (object) |
| `-f`, `--file_name` | No | Name for the generated audio. (string, default: `audio`) |
| `--audio_type` | No |  (string, one of: speech, music, sound_effect, default: `speech`) |
| `--query_file` | No | Optional repo-relative path to a UTF-8 text file used verbatim as the prompt (long scripts by path). Requires `repo_id`. (string) |
| `--repo_id` | No | Optional Second Brain repo id; required only when URL fields use repo-relative paths. (string) |
| `--speaker` | No | Model-specific preset voice (prefer putting it in `params`). (string) |
| `-d`, `--duration` | No | Duration in seconds for sound-effect/music models (prefer `params`). (integer) |
| `-l`, `--lyrics` | No | Lyrics for song models (prefer `params`). (string) |
| `--voice_files` | No | Voice sample URLs for cloning models (prefer `params`). (array) |
| `--source_audio_file` | No | Source audio URL for voice-changer / enhancement models (prefer `params`). (string) |
| `--custom_voice_id` | No | Cloned voice id for TTS models (prefer `params`). (string) |
| `--image_urls` | No | Deprecated: first entry maps to image conditioning when the model supports it. (array) |
| `-r`, `--requirements` | No | Deprecated inner-agent field; ignored. Use `params` per the model's params_schema. (string) |
| `--query` | No | Deprecated alias of `prompt` (pre-refactor scripts); ignored when `prompt` is set. (string) |
| `--previous_audio_params` | No | A prior generation's `params` dict, replayed for voice consistency (explicit `params` wins on conflict). (object) |

## Local File Support

Parameters that accept URLs (`--image_urls`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## Output File

Use `-o <path>` / `--output-file <path>` to download the generated result directly to a local file.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
