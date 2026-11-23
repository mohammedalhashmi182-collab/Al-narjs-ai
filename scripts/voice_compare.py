"""Run the open Arabic voice chain on a recorded test set. Offline; never serves /voice.

Usage (from the project root; keep the test set outside the repository)::

    export VOICE_COMPARE_ASR_URL=https://<your-host>/asr
    export VOICE_COMPARE_TTS_URL=https://<your-host>/tts
    export VOICE_COMPARE_TOKEN=...   # optional bearer token
    python scripts/voice_compare.py --manifest ~/voice-test/manifest.json --out ~/voice-test/report.json

The manifest is a JSON list of ``{"id": "...", "audio": "clip.wav", "reference_text": "..."}``.
Relative audio paths resolve from the manifest's folder. ``reference_text`` is optional;
when present, the word error rate is computed for that clip.

Clips run one after another so the latency numbers reflect a single caller.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services import voice_compare as vc  # noqa: E402

EXIT_NOT_CONFIGURED = 2
EXIT_NO_COMPLETE_CASE = 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--manifest", required=True, type=Path, help="JSON list of test clips")
    parser.add_argument("--out", type=Path, help="write the JSON report here (default: stdout)")
    parser.add_argument("--language", default="ar", help="language code sent to ASR and TTS")
    return parser.parse_args(argv)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must be a non-empty JSON list")
    base = path.parent
    clips: list[dict[str, Any]] = []
    missing: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("audio"):
            raise ValueError(f"manifest entry {index} needs 'id' and 'audio'")
        audio_path = (base / str(entry["audio"])).expanduser()
        if not audio_path.is_file():
            missing.append(str(audio_path))
        clips.append({**entry, "audio_path": audio_path})
    if missing:
        raise FileNotFoundError("audio files not found: " + ", ".join(missing))
    return clips


async def run_suite(clips: list[dict[str, Any]], language: str) -> list[vc.CaseResult]:
    endpoints = vc.endpoints_from_env()
    stages = vc.HttpVoiceStages(endpoints)
    try:
        from src.config.settings import get_settings
        from src.core.model_provider import ModelProvider

        llm = vc.make_llm_stage(ModelProvider(get_settings()))
        results: list[vc.CaseResult] = []
        for clip in clips:
            audio = clip["audio_path"].read_bytes()
            result = await vc.run_case(
                str(clip["id"]),
                audio,
                asr=stages.asr,
                llm=llm,
                tts=stages.tts,
                reference_text=clip.get("reference_text"),
                language=language,
            )
            results.append(result)
            status = "ok" if result.ok else "incomplete"
            print(f"[{status}] {result.case_id}", file=sys.stderr)
        return results
    finally:
        await stages.aclose()


def build_report(results: list[vc.CaseResult], language: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "language": language,
        "llm_chain": vc.LLM_CHAIN,
        "summary": vc.summarize(results),
        "cases": [
            {
                "id": case.case_id,
                "ok": case.ok,
                "transcript": case.transcript,
                "reply": case.reply,
                "audio_bytes": case.audio_bytes,
                "wer": case.wer,
                "stages": [
                    {"name": s.name, "ok": s.ok, "latency_ms": s.latency_ms, "error": s.error}
                    for s in case.stages
                ],
            }
            for case in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        vc.endpoints_from_env()
    except vc.NotConfigured as exc:
        print(f"Not configured ({exc}). No run was made.", file=sys.stderr)
        return EXIT_NOT_CONFIGURED
    except ValueError as exc:
        print(f"Invalid endpoint: {exc}", file=sys.stderr)
        return EXIT_NOT_CONFIGURED
    try:
        clips = load_manifest(args.manifest.expanduser())
    except (OSError, ValueError) as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return EXIT_NOT_CONFIGURED

    results = asyncio.run(run_suite(clips, args.language))
    report = build_report(results, args.language)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.expanduser().write_text(payload + "\n", encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        print(payload)
    summary = report["summary"]
    print(
        f"cases={summary['cases']} complete={summary['complete']} wer_mean={summary['wer_mean']}",
        file=sys.stderr,
    )
    return 0 if summary["complete"] else EXIT_NO_COMPLETE_CASE


if __name__ == "__main__":
    raise SystemExit(main())
