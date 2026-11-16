"""The owner Start button stores real public demand as drafts and never sends."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.core.owner_auth import make_session_token
from src.main import app
from src.services.ceo_scout import parse_mostaql, parse_remotive

MOSTAQL = """
<a href="https://mostaql.com/project/create">مشروع جديد</a>
<a href="https://mostaql.com/project/1293342-برنامج-محاسبي">برنامج محاسبي لسوبرماركت</a>
<a href="https://mostaql.com/project/1293342-برنامج-محاسبي">برنامج محاسبي لسوبرماركت</a>
<a href="https://mostaql.com/project/88-تصميم-سوشيال">تصميم سوشيال ميديا</a>
"""

REMOTIVE = json.dumps({
    "jobs": [
        {
            "title": "Content Creator - YouTube",
            "url": "https://remotive.com/remote-jobs/marketing/content-creator-youtube-2091173",
            "company_name": "Metics Media",
            "salary": "$85k - $155k",
        },
        {"title": "No link", "url": "", "salary": "hidden"},
        {"title": "Skip", "url": "http://insecure.example/job"},
    ]
})


def test_parsers_keep_only_real_public_listings():
    mostaql = parse_mostaql(MOSTAQL)
    assert [item["title"] for item in mostaql] == ["برنامج محاسبي لسوبرماركت", "تصميم سوشيال ميديا"]
    assert mostaql[1]["agent"] == "marketing_agent"
    assert mostaql[0]["url"].startswith("https://mostaql.com/project/1293342")
    remote = parse_remotive(REMOTIVE)
    assert len(remote) == 1
    assert remote[0]["budget"] == "$85k - $155k"
    assert remote[0]["url"].startswith("https://remotive.com/")
    assert parse_remotive("not-json") == []
    assert parse_mostaql("") == []


def test_start_stores_drafts_and_approval_does_not_send(monkeypatch):
    calls = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        if "mostaql.com" in url:
            return MOSTAQL
        if "remotive.com" in url:
            return REMOTIVE
        raise AssertionError(url)

    def refuse_send(*_args, **_kwargs):
        raise AssertionError("scout must not send")

    monkeypatch.setattr("src.services.ceo_scout.fetch_url", fake_fetch)
    monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", refuse_send)
    monkeypatch.setattr("src.services.whatsapp_sender.send_now", refuse_send)

    with TestClient(app) as client:
        denied = client.post("/api/owner/ceo/start")
        assert denied.status_code == 401
        client.cookies.set("narjis_owner", make_session_token())
        started = client.post("/api/owner/ceo/start")
        assert started.status_code == 200, started.text
        payload = started.json()
        assert payload["phase"] == "done"
        assert payload["external_contact"] is False
        assert payload["found"] == 3
        assert calls and all(url.startswith("https://") for url in calls)
        titles = {item["title"] for item in payload["opportunities"]}
        assert "تصميم سوشيال ميديا" in titles
        assert "Content Creator - YouTube" in titles
        for item in payload["opportunities"]:
            assert item["status"] == "awaiting_approval"
            assert item["sent"] is False
            assert item["source_url"].startswith("https://")
            assert "provider_message_id" not in item

        marketing = next(item for item in payload["opportunities"] if "سوشيال" in item["title"])
        decided = client.post(
            f"/api/owner/ceo/opportunities/{marketing['key']}/decide",
            json={"decision": "approve"},
        )
        assert decided.status_code == 200
        body = decided.json()
        assert body["status"] == "approved"
        assert body["sent"] is False
        assert body["external_contact"] is False

        listed = client.get("/api/owner/ceo/scout").json()
        assert any(item["status"] == "approved" and item["sent"] is False for item in listed["opportunities"])
        missing = client.post(
            "/api/owner/ceo/opportunities/scout-nope/decide",
            json={"decision": "reject"},
        )
        assert missing.status_code == 404
