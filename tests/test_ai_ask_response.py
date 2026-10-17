"""The Arabic /api/ai/ask body must arrive whole, with Content-Length in bytes.

Uvicorn writes the access line when response headers start, then closes the
socket if the body is longer or shorter than Content-Length. The client reports
that as an unexpected EOF. This drives httptools, not the in-process TestClient.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import textwrap
import time


_ANSWER = (
    "نعم، البوت يشتغل بالعربي ويرد على العملاء على مدار 24 ساعة يومياً. "
    "المتابعة البشرية بالبريد."
)


def test_httptools_delivers_arabic_json_with_matching_content_length():
    port = _free_port()
    script = textwrap.dedent(
        f"""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from src.main import SecurityHeadersMiddleware, StaticCacheMiddleware

        app = FastAPI()
        app.add_middleware(StaticCacheMiddleware)
        app.add_middleware(SecurityHeadersMiddleware)

        @app.post("/api/ai/ask")
        async def ask(body: dict):
            return JSONResponse({{"answer": {_ANSWER!r}, "reviewed": False}})

        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port={port}, log_level="warning", http="httptools")
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        raw = _post_when_up(port, b'{"question":"x"}')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    head, _, body = raw.partition(b"\r\n\r\n")
    text = head.decode("latin-1", "replace")
    assert " 200 " in text.split("\r\n", 1)[0]
    declared = None
    for line in text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            declared = int(line.split(":", 1)[1].strip())
    assert declared == len(body)
    payload = json.loads(body.decode("utf-8"))
    assert payload == {"answer": _ANSWER, "reviewed": False}
    assert "content-security-policy" in text.lower()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _post_when_up(port: int, payload: bytes) -> bytes:
    deadline = time.monotonic() + 20
    last = ""
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1) as sock:
                request = (
                    b"POST /api/ai/ask HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + payload
                )
                sock.sendall(request)
                chunks = []
                while True:
                    piece = sock.recv(65536)
                    if not piece:
                        break
                    chunks.append(piece)
                return b"".join(chunks)
        except (ConnectionRefusedError, ConnectionResetError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(0.1)
    raise AssertionError(f"server did not answer: {last}")
