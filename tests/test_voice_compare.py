"""Tests for the offline Arabic voice comparison harness.

No network: HTTP stages use ``httpx.MockTransport``. The model stage is a fake.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from src.services import voice_compare as vc

ROOT = Path(__file__).resolve().parents[1]


def _stages(
    calls: list[str], *, asr_error: Exception | None = None, tts_error: Exception | None = None
):
    async def asr(audio: bytes, language: str) -> str:
        calls.append("asr")
        if asr_error:
            raise asr_error
        return "مرحبا كيف حالك"

    async def llm(text: str) -> str:
        calls.append("llm")
        return "أهلاً بك، كيف أقدر أساعدك؟"

    async def tts(text: str, language: str) -> bytes:
        calls.append("tts")
        if tts_error:
            raise tts_error
        return b"RIFF-fake-audio"

    return asr, llm, tts


def test_normalize_arabic_removes_diacritics_and_unifies_alef():
    assert vc.normalize_arabic("إِنَّ") == "ان"
    assert vc.normalize_arabic("مرحبا، كيف حالك؟") == "مرحبا كيف حالك"
    assert vc.normalize_arabic("مُـحَمَّد") == "محمد"


def test_word_error_rate_known_values():
    assert vc.word_error_rate("أنا أحب القهوة الحارة", "أنا أحب القهوة الحارة") == 0.0
    # one substitution across four reference words
    assert vc.word_error_rate("أنا أحب القهوة الحارة", "أنا أكره القهوة الحارة") == 0.25
    # one insertion across three reference words
    assert vc.word_error_rate("أنا أحب القهوة", "أنا أحب القهوة الحارة") == pytest.approx(1 / 3)
    assert vc.word_error_rate("", "أي شيء") is None


async def test_run_case_runs_stages_in_order_and_records_timing():
    calls: list[str] = []
    asr, llm, tts = _stages(calls)
    result = await vc.run_case(
        "c1", b"wav", asr=asr, llm=llm, tts=tts, reference_text="مرحبا كيف حالك"
    )
    assert calls == ["asr", "llm", "tts"]
    assert result.ok is True
    assert result.transcript == "مرحبا كيف حالك"
    assert result.audio_bytes == len(b"RIFF-fake-audio")
    assert result.wer == 0.0
    assert [s.name for s in result.stages] == ["asr", "llm", "tts"]
    assert all(s.ok and s.latency_ms >= 0 for s in result.stages)


async def test_asr_failure_stops_the_pipeline_and_is_recorded():
    calls: list[str] = []
    asr, llm, tts = _stages(calls, asr_error=RuntimeError("gpu busy"))
    result = await vc.run_case("c2", b"wav", asr=asr, llm=llm, tts=tts)
    assert calls == ["asr"]
    assert result.ok is False
    assert result.stages[0].name == "asr" and result.stages[0].ok is False
    assert "RuntimeError: gpu busy" in result.stages[0].error


async def test_empty_transcript_counts_as_a_failed_asr_stage():
    async def asr(audio: bytes, language: str) -> str:
        return "   "

    async def llm(text: str) -> str:  # pragma: no cover - must not run
        raise AssertionError("LLM should not be called")

    async def tts(text: str, language: str) -> bytes:  # pragma: no cover
        raise AssertionError("TTS should not be called")

    result = await vc.run_case("c3", b"wav", asr=asr, llm=llm, tts=tts)
    assert result.stages[-1].ok is False
    assert "empty text" in result.stages[-1].error


async def test_tts_failure_keeps_transcript_and_reply():
    calls: list[str] = []
    asr, llm, tts = _stages(calls, tts_error=ValueError("no audio"))
    result = await vc.run_case("c4", b"wav", asr=asr, llm=llm, tts=tts)
    assert calls == ["asr", "llm", "tts"]
    assert result.transcript and result.reply
    assert result.ok is False
    assert result.stages[-1].name == "tts" and result.stages[-1].ok is False


def test_summarize_reports_median_p95_failures_and_wer():
    def case(cid: str, latencies: dict[str, float], ok_tts: bool = True, wer: float | None = None):
        stages = [vc.StageResult(name, True, ms) for name, ms in latencies.items()]
        if not ok_tts:
            stages.append(vc.StageResult("tts", False, 5.0, "ValueError: no audio"))
        return vc.CaseResult(case_id=cid, stages=stages, wer=wer)

    results = [
        case("a", {"asr": 10, "llm": 100, "tts": 10}, wer=0.0),
        case("b", {"asr": 20, "llm": 200, "tts": 20}, wer=0.5),
        case("c", {"asr": 30, "llm": 300, "tts": 30}),
        case("d", {"asr": 40, "llm": 400}, ok_tts=False),
    ]
    summary = vc.summarize(results)
    assert summary["cases"] == 4
    assert summary["complete"] == 3
    assert summary["latency_ms"]["asr"] == {"median": 25.0, "p95": 40.0, "n": 4}
    assert summary["latency_ms"]["llm"]["median"] == 250.0
    assert summary["failures"] == {"tts": 1}
    assert summary["wer_mean"] == 0.25
    assert summary["wer_cases"] == 2


def test_summarize_empty_has_no_invented_numbers():
    summary = vc.summarize([])
    assert summary == {
        "cases": 0,
        "complete": 0,
        "latency_ms": {},
        "failures": {},
        "wer_mean": None,
        "wer_cases": 0,
    }


def test_endpoints_require_both_urls():
    with pytest.raises(vc.NotConfigured) as exc:
        vc.endpoints_from_env({vc.ENV_ASR_URL: "https://asr.example.com/asr"})
    assert exc.value.missing == [vc.ENV_TTS_URL]


def test_endpoints_reject_plain_http_for_remote_hosts_but_allow_localhost():
    with pytest.raises(ValueError):
        vc.endpoints_from_env(
            {
                vc.ENV_ASR_URL: "http://asr.example.com/asr",
                vc.ENV_TTS_URL: "https://tts.example.com/tts",
            }
        )
    endpoints = vc.endpoints_from_env(
        {
            vc.ENV_ASR_URL: "http://127.0.0.1:8000/asr",
            vc.ENV_TTS_URL: "https://tts.example.com/tts",
            vc.ENV_TOKEN: "t-123",
        }
    )
    assert endpoints.asr_url == "http://127.0.0.1:8000/asr"
    assert endpoints.token == "t-123"


async def test_http_stages_follow_the_endpoint_contract():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.setdefault("auth", set()).add(request.headers.get("authorization"))
        if request.url.path == "/asr":
            seen["asr_ct"] = request.headers.get("content-type", "")
            assert b'name="file"' in request.content and b'name="language"' in request.content
            return httpx.Response(200, json={"text": "مرحبا"})
        if request.url.path == "/tts":
            body = json.loads(request.content)
            seen["tts_body"] = body
            return httpx.Response(200, content=b"WAVDATA", headers={"content-type": "audio/wav"})
        return httpx.Response(404)

    endpoints = vc.Endpoints(
        "https://gpu.example.com/asr", "https://gpu.example.com/tts", token="t-123"
    )
    stages = vc.HttpVoiceStages(endpoints, transport=httpx.MockTransport(handler))
    try:
        assert await stages.asr(b"wav", "ar") == "مرحبا"
        assert await stages.tts("أهلاً", "ar") == b"WAVDATA"
    finally:
        await stages.aclose()
    assert seen["auth"] == {"Bearer t-123"}
    assert seen["asr_ct"].startswith("multipart/form-data")
    assert seen["tts_body"] == {"text": "أهلاً", "language": "ar"}


async def test_http_asr_without_text_field_is_a_failed_stage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": 1})

    endpoints = vc.Endpoints("https://gpu.example.com/asr", "https://gpu.example.com/tts")
    stages = vc.HttpVoiceStages(endpoints, transport=httpx.MockTransport(handler))

    async def llm(text: str) -> str:  # pragma: no cover
        raise AssertionError("LLM should not run")

    try:
        result = await vc.run_case("c5", b"wav", asr=stages.asr, llm=llm, tts=stages.tts)
    finally:
        await stages.aclose()
    assert result.ok is False
    assert "no 'text' field" in result.stages[0].error


async def test_llm_stage_uses_the_gemini_chain_and_rejects_empty_output():
    captured: dict[str, object] = {}

    class FakeProvider:
        async def complete_with_fallback(self, chain: str, request):
            captured["chain"] = chain
            captured["max_tokens"] = request.max_tokens
            captured["system"] = request.system_prompt
            return SimpleNamespace(content="  رد تجريبي  ")

    llm = vc.make_llm_stage(FakeProvider())
    assert await llm("سؤال") == "رد تجريبي"
    assert captured["chain"] == "gemini"
    assert captured["max_tokens"] == vc.LLM_MAX_TOKENS
    assert "لا تذكر أسعاراً" in str(captured["system"])


def test_manifest_loader_refuses_missing_audio(tmp_path: Path):
    from scripts import voice_compare as cli

    (tmp_path / "ok.wav").write_bytes(b"RIFF")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"id": "a", "audio": "ok.wav"}, {"id": "b", "audio": "missing.wav"}]),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError) as exc:
        cli.load_manifest(manifest)
    assert "missing.wav" in str(exc.value)


def test_cli_exits_without_running_when_not_configured(monkeypatch, tmp_path: Path, capsys):
    from scripts import voice_compare as cli

    monkeypatch.delenv(vc.ENV_ASR_URL, raising=False)
    monkeypatch.delenv(vc.ENV_TTS_URL, raising=False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"id": "a", "audio": "a.wav"}]), encoding="utf-8")
    assert cli.main(["--manifest", str(manifest)]) == cli.EXIT_NOT_CONFIGURED
    assert "No run was made" in capsys.readouterr().err


def test_live_voice_route_does_not_use_the_harness():
    """The public /voice path must stay on the xAI agent; the harness is offline only."""
    for relative in ("src/main.py", "src/services/voice_live.py", "src/config/settings.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "voice_compare" not in text, relative
