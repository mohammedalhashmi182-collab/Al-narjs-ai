"""Safety/spec tests for the Roza WhatsApp pilot (not a live API integration test)."""
import json
from pathlib import Path


PILOT = Path(__file__).resolve().parents[1] / "pilots" / "roza-ryd-awali" / "manifest.json"


def _pilot():
    return json.loads(PILOT.read_text(encoding="utf-8"))


def test_pilot_stays_review_only_until_customer_approves():
    data = _pilot()
    assert data["status"] == "draft_customer_approval_required"
    cfg = data["configuration"]
    assert cfg["reply_mode"] == "review"
    assert cfg["auto_send"] is False
    assert all(cfg[k] for k in (
        "customer_meta_authorization_required", "customer_project_required",
        "customer_wa_phone_id_required", "customer_wa_access_token_required",
    ))


def test_kb_is_scoped_to_customer_supplied_links_without_claiming_prices():
    data = _pilot()
    docs = data["knowledge_docs"]
    assert len(docs) == 3 and all(d["approval_required"] for d in docs)
    text = "\n".join(d["content"] for d in docs)
    assert "https://app.qlub.io/qr/sa/roza_ryd_awali/" in text
    assert "https://maps.app.goo.gl/SHfGq4RbHoMJy2D18" in text
    assert "https://www.tiktok.com/@hadiqat_ruza" in text
    assert not any(flag in text for flag in ("ر.س", "SAR", "توصيل متاح", "مفتوح 24"))


def test_handoff_cases_cover_prices_orders_delivery_and_human():
    tests = _pilot()["acceptance_tests"]
    assert len(tests) == 6
    assert sum(case["type"] == "handoff" for case in tests) >= 4
    assert all(case["incoming"] and case["expected"] for case in tests)
