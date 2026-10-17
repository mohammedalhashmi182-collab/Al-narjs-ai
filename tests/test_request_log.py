"""Request ids are logged at the start and the end, including a missing status."""

from __future__ import annotations

import logging

from src.utils.request_log import RequestLogMiddleware


def _scope(path="/api/consult", headers=None):
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers or [],
    }


async def _receive():
    return {"type": "http.request", "body": b"{}", "more_body": False}


async def test_start_and_end_share_one_request_id(caplog):
    seen = {}

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": b"{}"})

    async def send(message):
        if message["type"] == "http.response.start":
            seen["headers"] = dict(message["headers"])

    caplog.set_level(logging.INFO)
    await RequestLogMiddleware(app)(
        _scope(headers=[(b"x-request-id", b"trace-consult-1")]),
        _receive,
        send,
    )
    assert seen["headers"][(b"x-request-id")] == b"trace-consult-1"
    starts = [r.message for r in caplog.records if r.message.startswith("http start")]
    ends = [r.message for r in caplog.records if r.message.startswith("http end")]
    assert starts == ["http start id=trace-consult-1 method=POST route=/api/consult"]
    assert len(ends) == 1
    assert ends[0].startswith(
        "http end id=trace-consult-1 method=POST route=/api/consult status=200 duration_ms="
    )


async def test_missing_status_is_logged_when_headers_never_start(caplog):
    async def app(scope, receive, send):
        return

    async def send(message):
        raise AssertionError("no response should be sent")

    caplog.set_level(logging.INFO)
    await RequestLogMiddleware(app)(_scope(path="/api/ai/ask"), _receive, send)
    assert any(
        r.levelno == logging.WARNING and "route=/api/ai/ask" in r.message and "status=-" in r.message
        for r in caplog.records
    )
    assert any(r.message.startswith("http start id=") and "route=/api/ai/ask" in r.message for r in caplog.records)


def test_server_keepalive_is_above_the_render_edge_and_stays_one_process():
    from pathlib import Path

    commands = [
        Path("Dockerfile").read_text(encoding="utf-8"),
        Path("Procfile").read_text(encoding="utf-8"),
        Path("docker-compose.yml").read_text(encoding="utf-8"),
    ]
    for text in commands:
        assert "--timeout-keep-alive 120" in text
        assert "--no-access-log" in text
        assert "--proxy-headers" in text
        assert "--workers" not in text


_PHONE = "966512345678"
_PAYMENT = "11111111-2222-3333-4444-555555555555"
_CONTACT = (
    "/api/portal/projects/"
    + _PAYMENT
    + "/contacts/"
    + _PHONE
    + "/reply"
)


class _Route:
    def __init__(self, path_format):
        self.path_format = path_format


async def test_phone_and_payment_id_never_appear_when_the_route_matched(caplog):
    async def app(scope, receive, send):
        scope["route"] = _Route("/api/portal/projects/{pid}/contacts/{contact}/reply")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    caplog.set_level(logging.INFO)
    scope = _scope(path=_CONTACT, headers=[])
    scope["query_string"] = b"code=oauth-secret-code&state=oauth-secret-state"
    await RequestLogMiddleware(app)(scope, _receive, _send_ok)
    text = "\n".join(r.message for r in caplog.records)
    assert _PHONE not in text
    assert _PAYMENT not in text
    assert "oauth-secret-code" not in text
    assert "oauth-secret-state" not in text
    assert "method=POST" in text
    assert "status=200" in text
    assert "duration_ms=" in text
    assert "route=/api/portal/projects/{pid}/contacts/{contact}/reply" in text


async def test_unmatched_invoice_and_payment_paths_mask_ids_and_phones(caplog):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    caplog.set_level(logging.INFO)
    for path in (
        f"/invoice/{_PAYMENT}",
        f"/api/payments/{_PAYMENT}",
        "/api/portal/projects/x/contacts/٠٥٥٥١٢٣٤٥٦٧/reply",
    ):
        await RequestLogMiddleware(app)(_scope(path=path), _receive, _send_ok)
    text = "\n".join(r.message for r in caplog.records)
    assert _PAYMENT not in text
    assert "٥٥٥١٢٣٤٥٦٧" not in text
    assert "05551234567" not in text
    assert "route=/invoice/{id}" in text
    assert "route=/api/payments/{id}" in text
    assert "route=/api/portal/projects/x/contacts/{n}/reply" in text


def test_real_router_logs_the_template_not_the_contact_phone(caplog):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(RequestLogMiddleware)

    @app.post("/api/portal/projects/{pid}/contacts/{contact}/reply")
    async def reply(pid: str, contact: str):
        return {"ok": True}

    @app.get("/invoice/{payment_id}")
    async def invoice(payment_id: str):
        return {"ok": True}

    @app.get("/api/payments/{payment_id}")
    async def payment(payment_id: str):
        return {"ok": True}

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        assert client.post(_CONTACT).status_code == 200
        assert client.get(f"/invoice/{_PAYMENT}").status_code == 200
        assert client.get(
            f"/api/payments/{_PAYMENT}",
            params={"code": "oauth-secret-code", "state": "oauth-secret-state"},
        ).status_code == 200
        assert client.get(f"/no/such/{_PAYMENT}").status_code == 404

    text = "\n".join(r.message for r in caplog.records)
    assert _PHONE not in text
    assert _PAYMENT not in text
    assert "oauth-secret-code" not in text
    assert "oauth-secret-state" not in text
    assert "route=/api/portal/projects/{pid}/contacts/{contact}/reply" in text
    assert "route=/invoice/{payment_id}" in text
    assert "route=/api/payments/{payment_id}" in text
    assert "method=POST" in text and "method=GET" in text
    assert "status=200" in text and "status=404" in text
    assert "duration_ms=" in text


async def _send_ok(message):
    return None
