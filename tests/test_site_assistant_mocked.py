"""Site assistant end-to-end with a MOCKED model (no live model was available).

Covers: the assistant answers through /api/consult; when the visitor wants a
person, the ticket flow returns an NRJ-xxxxxx reference and reply time, the
owner gets a Telegram alert and an email to the support inbox, and the ticket
appears in the owner's dashboard list. No network call is made.
"""
from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from src.core.owner_auth import _COOKIE_NAME, make_session_token
from src.main import app


class _Resp:
    def __init__(self, content):
        self.content = content


class _MockModel:
    def __init__(self):
        self.prompts = []

    async def complete_with_fallback(self, chain, request):
        self.prompts.append(request.prompt)
        return _Resp("أهلاً! باقة «رد» بـ 599 ريال شهرياً بدون رسوم تأسيس.")


@pytest.fixture()
def client():
    from src.utils import rate_limit
    for lim in (rate_limit.ticket_limiter, getattr(rate_limit, "consult_limiter", None)):
        if lim is not None and hasattr(lim, "_hits"):
            lim._hits.clear()
    with TestClient(app) as c:
        yield c


def test_assistant_answers_with_mocked_model(client, monkeypatch):
    mock = _MockModel()
    monkeypatch.setattr(app.state, "model_provider", mock)
    r = client.post("/api/consult", json={"messages": [{"role": "user", "content": "كم سعر باقة رد؟"}]})
    assert r.status_code == 200 and "599" in r.json()["reply"]
    assert mock.prompts and "كم سعر باقة رد؟" in mock.prompts[0]


def test_ticket_flow_reference_alert_email_and_owner_list(client, monkeypatch):
    from src.services import email_service, telegram_sender
    from src.services.support import SUPPORT_EMAIL

    alerts, mails = [], []

    async def fake_alert(text, *a, **k):
        alerts.append(text)
        return {"ok": True}

    async def fake_mail(to, subject, body, *a, **k):
        mails.append((to, subject, body))
        return True

    monkeypatch.setattr(telegram_sender, "send_owner_alert", fake_alert)
    monkeypatch.setattr(email_service, "send_email", fake_mail)
    q = f"أبي أكلم موظف عن الفاتورة {uuid.uuid4().hex[:6]}"
    r = client.post("/api/support/ticket", json={"name": "سارة", "email": "sara@example.com",
                                                 "question": q, "consent": True, "page": "/ar/pricing"})
    d = r.json()
    assert r.status_code == 200 and d["ok"]
    assert re.fullmatch(r"NRJ-\d{6}", d["reference"])
    assert d["response_time"] == "خلال يوم عمل"
    assert len(alerts) == 1 and d["reference"] in alerts[0] and q in alerts[0]
    assert len(mails) == 1 and mails[0][0] == SUPPORT_EMAIL and d["reference"] in mails[0][1]

    assert client.get("/api/owner/tickets").status_code == 401
    client.cookies.set(_COOKIE_NAME, make_session_token())
    lst = client.get("/api/owner/tickets").json()["tickets"]
    mine = [t for t in lst if t["reference"] == d["reference"]]
    assert mine and mine[0]["question"] == q and mine[0]["notify"] == {"telegram": True, "email": True}
    page = client.get("/owner/command")
    assert page.status_code == 200 and 'id="ticketsCard"' in page.text
    client.cookies.clear()
