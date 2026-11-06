"""The public home page opens on the voice consultant, with no intro overlay."""

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "src/web/templates/landing.html"
PARTIAL = ROOT / "src/web/templates/partials/_voice_consultant.html"
VOICE_PAGE = ROOT / "src/web/static/voice-live.html"
VOICE_JS = ROOT / "src/web/static/js/voice-live-app.js"

INTRO_MARKERS = (
    'id="njIntro"',
    'id="intro"',
    'id="preloader"',
    "nj-intro",
    "narjis-intro",
    "preloader",
    "Skip intro",
)


def _home(lang: str) -> str:
    with TestClient(app) as client:
        response = client.get(f"/{lang}/home")
    assert response.status_code == 200
    return response.text


def test_home_templates_have_no_intro_markup() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    partial = PARTIAL.read_text(encoding="utf-8")
    for marker in INTRO_MARKERS:
        assert marker not in landing, marker
        assert marker not in partial, marker
    assert not (ROOT / "src/web/static/js/narjis-intro.js").exists()
    assert not (ROOT / "src/web/static/css/narjis-intro.css").exists()
    voice = VOICE_PAGE.read_text(encoding="utf-8")
    assert 'id="intro"' not in voice
    assert 'id="njIntro"' not in voice


def test_voice_consultant_is_the_first_thing_on_both_home_pages() -> None:
    arabic = _home("ar")
    english = _home("en")
    for page, heading, chat, start, idle in (
        (arabic, "مستشار النرجس", "دردشة", "ابدأ المكالمة", "اضغط للبدء"),
        (english, "Al-Narjis advisor", "Chat", "Start the call", "Tap to start"),
    ):
        for marker in INTRO_MARKERS:
            assert marker not in page, marker
        main = page.split("<main", 1)[1]
        voice_at = main.index('id="voiceConsultant"')
        assert voice_at < main.index('id="top"')
        assert voice_at < main.index('id="pricing"')
        block = main[voice_at:main.index('id="top"')]
        assert heading in block
        assert idle in block
        assert 'id="voiceOrb"' in block
        assert 'class="scroll-hint"' in block and 'href="#top"' in block
        assert f'id="chat"' in block and chat in block
        assert 'id="start"' in block and start in block
        assert 'id="chatPanel" hidden' in block
        assert "/static/js/voice-live-app.js" in page
        assert "Grok" not in block and "xAI" not in block
        assert "tel:" not in page
        assert "0540799266" not in page
    assert "790" in arabic and "1,490" in arabic and "2,990" in arabic
    assert "790" in english and "1,490" in english and "2,990" in english


def test_microphone_is_not_requested_until_the_visitor_starts() -> None:
    script = VOICE_JS.read_text(encoding="utf-8")
    partial = PARTIAL.read_text(encoding="utf-8")
    assert partial.count("getUserMedia") == 0
    assert script.count("getUserMedia") == 1
    attach = script.index("async function attachMic()")
    begin = script.index("async function beginCall")
    assert attach < script.index("getUserMedia") < begin
    assert "start.onclick = () =>" in script
    assert "beginCall({ mic: true })" in script
    assert "beginCall({ mic: false, text: true" in script
    # The status check on load must not open the microphone.
    load = script.index('fetch("/api/voice/status"')
    assert "getUserMedia" not in script[load:]
    assert "attachMic" not in script[load:]
