"""X-Forwarded-For is trusted only at the right-most proxy hop Render appends."""

from src.utils.rate_limit import client_ip


class _Client:
    def __init__(self, host):
        self.host = host


class _Request:
    def __init__(self, forwarded, host="10.0.0.8"):
        self.headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
        self.client = _Client(host)


def test_spoofed_left_most_is_ignored(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_Request("1.2.3.4, 5.6.7.8")) == "5.6.7.8"


def test_zero_hops_uses_the_direct_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    assert client_ip(_Request("1.2.3.4, 5.6.7.8", host="9.9.9.9")) == "9.9.9.9"


def test_missing_header_uses_the_peer(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_Request(None, host="10.1.1.1")) == "10.1.1.1"
