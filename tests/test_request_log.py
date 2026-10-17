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
    assert starts == ["http start id=trace-consult-1 method=POST path=/api/consult"]
    assert len(ends) == 1
    assert ends[0].startswith(
        "http end id=trace-consult-1 method=POST path=/api/consult status=200 duration_ms="
    )


async def test_missing_status_is_logged_when_headers_never_start(caplog):
    async def app(scope, receive, send):
        return

    async def send(message):
        raise AssertionError("no response should be sent")

    caplog.set_level(logging.INFO)
    await RequestLogMiddleware(app)(_scope(path="/api/ai/ask"), _receive, send)
    assert any(
        r.levelno == logging.WARNING and "path=/api/ai/ask" in r.message and "status=-" in r.message
        for r in caplog.records
    )
    assert any(r.message.startswith("http start id=") and "path=/api/ai/ask" in r.message for r in caplog.records)


def test_server_keepalive_is_above_the_render_edge_and_stays_one_process():
    from pathlib import Path

    commands = [
        Path("Dockerfile").read_text(encoding="utf-8"),
        Path("Procfile").read_text(encoding="utf-8"),
        Path("docker-compose.yml").read_text(encoding="utf-8"),
    ]
    for text in commands:
        assert "--timeout-keep-alive 120" in text
        assert "--proxy-headers" in text
        assert "--workers" not in text
