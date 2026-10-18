"""Uvicorn's default 5s keep-alive closes an idle socket with no status line.

Render's edge keeps the upstream connection for about 75s and then reuses it.
If this process already closed it, the client sees a clean close and no HTTP
status, and the application never logs an exception. A keep-alive longer than
the edge idle time leaves the close to the edge.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import textwrap
import time

import pytest


@pytest.mark.allow_hosts(["127.0.0.1"])
def test_idle_keepalive_close_sends_no_status_until_the_timeout_is_raised():
    closed = _exchange(timeout_keep_alive=1, pause=1.6)
    assert closed["first"] == 200
    assert closed["second_error"]
    assert closed["second_status"] is None

    kept = _exchange(timeout_keep_alive=3, pause=1.0)
    assert kept["first"] == 200
    assert kept["second_error"] is None
    assert kept["second_status"] == 200


_REQUEST = b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n"


def _exchange(*, timeout_keep_alive: int, pause: float) -> dict:
    port = _free_port()
    script = textwrap.dedent(
        f"""
        async def app(scope, receive, send):
            if scope["type"] != "http":
                return
            await send({{"type": "http.response.start", "status": 200, "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", b"2"),
            ]}})
            await send({{"type": "http.response.body", "body": b"ok"}})

        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port={port}, log_level="error", http="httptools",
                    timeout_keep_alive={timeout_keep_alive}, access_log=False)
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_until_up(port)
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        sock.settimeout(3)
        try:
            sock.sendall(_REQUEST)
            first = _read_response(sock)
            time.sleep(pause)
            second_status = None
            second_error = None
            try:
                sock.sendall(_REQUEST)
                second = _read_response(sock)
                line = second.split(b"\r\n", 1)[0]
                if line.startswith(b"HTTP/"):
                    second_status = int(line.split()[1])
                else:
                    second_error = "no-status"
            except Exception as exc:
                second_error = type(exc).__name__
            return {
                "first": int(first.split(b"\r\n", 1)[0].split()[1]),
                "second_status": second_status,
                "second_error": second_error,
            }
        finally:
            sock.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _read_response(sock: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        part = sock.recv(4096)
        if not part:
            break
        data += part
    if b"\r\n\r\n" not in data:
        return data
    head, _, rest = data.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    while len(rest) < length:
        part = sock.recv(4096)
        if not part:
            break
        rest += part
    return head + b"\r\n\r\n" + rest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_up(port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("uvicorn did not listen")
