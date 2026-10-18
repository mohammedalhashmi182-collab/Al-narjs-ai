"""Site assistant (/api/consult) grounded in Al-Narjis's own KB via RAG (mocked model)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app


class _Resp:
    def __init__(self, content):
        self.content = content


class _Model:
    def __init__(self, reply):
        self.reply, self.requests = reply, []

    async def complete_with_fallback(self, chain, request):
        self.requests.append(request)
        return _Resp(self.reply)


@pytest.fixture()
def client():
    from src.utils import rate_limit

    for lim in vars(rate_limit).values():
        if hasattr(lim, "_hits"):
            lim._hits.clear()
    with TestClient(app) as c:
        yield c


def _ask(client, monkeypatch, reply, q):
    m = _Model(reply)
    monkeypatch.setattr(app.state, "model_provider", m)
    r = client.post("/api/consult", json={"messages": [{"role": "user", "content": q}]})
    return r, m


def test_owner_kb_sources_reach_the_prompt(client, monkeypatch):
    r, m = _ask(client, monkeypatch, "باقة «البداية» بـ 790 ريال شهرياً.", "كم سعر باقة البداية شهريا؟")
    assert r.status_code == 200 and "790" in r.json()["reply"] and "handoff" not in r.json()
    assert "SOURCES" in m.requests[0].system_prompt


def test_invented_price_is_never_shown(client, monkeypatch):
    r, _ = _ask(client, monkeypatch, "باقة رد بـ 449 ريال فقط هذا الشهر!", "كم سعر باقة رد؟")
    body = r.json()
    assert r.status_code == 200 and "449" not in body["reply"]
    assert body["handoff"] == "ungrounded" and "خدمة العملاء" in body["reply"]  # UI offers the ticket


def test_invented_link_is_never_shown(client, monkeypatch):
    r, _ = _ask(client, monkeypatch, "ادفع هنا https://pay.example.com/x", "كيف أدفع؟")
    assert r.json().get("handoff") == "ungrounded"


def test_numbered_list_markers_are_not_facts(client, monkeypatch):
    r, _ = _ask(client, monkeypatch, "الخطوات:\n1. اختر الباقة\n2. ادفع عبر /portal", "كيف أبدأ؟")
    assert "handoff" not in r.json()


async def test_consult_never_sees_tenant_docs(client, monkeypatch):
    from src.models import ClientProject
    from src.services.agent_tools import knowledge_base

    secret = f"سر-المستأجر-{uuid.uuid4().hex[:6]}"
    async with app.state.session_factory() as s:
        p = ClientProject(client_name="مستأجر تجريبي", phone="0555999000", package="radd", status="active")
        s.add(p)
        await s.flush()
        await knowledge_base.add_doc(s, "خاص", f"كلمة المرور الداخلية للعيادة: {secret} ساعات العمل", project_id=p.id)
    r, m = _ask(client, monkeypatch, "أهلاً", f"وش ساعات العمل {secret}")
    assert secret not in m.requests[0].system_prompt
