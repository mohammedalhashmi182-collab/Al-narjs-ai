# Open Arabic voice chain: offline comparison

Status: experiment only. The public `/voice` page still uses the owner's xAI
Voice Agent (`src/services/voice_live.py`). Nothing in this branch changes that
route, `settings.py`, the database, or the deploy config.

## What this measures

A recorded Arabic test set runs through three stages, one clip at a time:

1. **ASR**: speech to text, on a self-hosted open model.
2. **LLM**: the existing Gemini chain (`ModelProvider.complete_with_fallback("gemini", ...)`),
   so every candidate chain uses the same reasoning step.
3. **TTS**: text to speech, on a self-hosted open model.

The report gives, per stage, the median and p95 latency of successful calls,
the number of failures, and the mean word error rate (WER) for clips that have
reference text. Failed stages are recorded, never filled in.

## What it does not measure yet

* **The xAI baseline.** A fair comparison needs the same timing points measured
  on a live xAI session (end of caller speech to first audio). That needs the
  owner's own key and agent and a live call, so it is not part of this branch.
* **Speech-to-speech.** No open Arabic speech-to-speech model was found that
  runs as one realtime model. The chain above is three steps, so its latency
  will be higher than a single realtime model would give.
* **Quality of replies.** The harness stores transcripts and replies for human
  review. It does not score them.

## Components to evaluate

These were shortlisted from public sources. Check each model card and licence
on the host before running. Nothing here has been run from this sandbox.

* ASR: Cohere Transcribe Arabic (listed as Apache 2.0)
* TTS, dialectal: Habibi
* TTS, Modern Standard Arabic: Fasih-TTS-V1
* TTS, small bilingual: SILMA TTS v1

## Endpoint contract

Host the models on a server you control (GPU). Expose two endpoints:

* **ASR**: `POST` multipart with field `file` (WAV) and form field `language`.
  Response: JSON `{"text": "..."}`.
* **TTS**: `POST` JSON `{"text": "...", "language": "ar"}`. Response: audio bytes
  (WAV).

Set these in the shell where you run the harness. Do not write them into the
repository:

```
VOICE_COMPARE_ASR_URL=https://<your-host>/asr
VOICE_COMPARE_TTS_URL=https://<your-host>/tts
VOICE_COMPARE_TOKEN=<optional bearer token>
```

`http://` is accepted only for `localhost` and `127.0.0.1`, so a token is never
sent in clear text to a remote host.

## Test set

Keep the test set outside the repository (for example `~/voice-test/`). Record
clips of real Saudi and Gulf Arabic questions, and write the reference text for
each. Add a `manifest.json`:

```json
[
  {"id": "q01", "audio": "q01.wav", "reference_text": "..."},
  {"id": "q02", "audio": "q02.wav"}
]
```

`audio` paths resolve from the manifest's folder. `reference_text` is optional.
Without it, the clip still gets timings and a transcript, but no WER.

## Run

From the project root:

```
python scripts/voice_compare.py --manifest ~/voice-test/manifest.json --out ~/voice-test/report.json
```

If an endpoint variable is missing, the script exits with code 2 and makes no
calls. A run where no clip completes exits with code 1.

## Before you read the numbers

Set the acceptance thresholds before the first run, not after it. The harness
does not set them for you.
