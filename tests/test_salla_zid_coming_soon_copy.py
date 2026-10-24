"""Salla/Zid is «قريباً» on pricing; the assistant's policy text must not call it available."""
from pathlib import Path

from src.services import policies

ROOT = Path(__file__).resolve().parents[1]


def test_policy_prompt_does_not_claim_salla_zid_available():
    assert "Salla/Zid read-only connectors" not in policies.POLICY_PROMPT
    assert "coming soon" in policies.POLICY_PROMPT


def test_owner_faq_marks_salla_zid_coming_soon():
    assert "ربط سلة وزد بصلاحية قراءة فقط" not in policies.OWNER_FAQ_AR
    assert "ربط سلة أو زد «قريباً»" in policies.OWNER_FAQ_AR


def test_agent_yaml_does_not_claim_salla_zid_available():
    for name in ("customer_service.yaml", "sales_closer.yaml"):
        text = (ROOT / "agents" / "base" / name).read_text(encoding="utf-8")
        assert "Salla/Zid read-only connectors" not in text
