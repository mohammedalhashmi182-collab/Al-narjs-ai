"""CF-Connecting-IP is trusted only from a Cloudflare peer; otherwise the hop rule."""

from src.integrations.net import client_ip as store_client_ip
from src.integrations.net import trusted_hops
from src.utils.net import client_ip as shared_client_ip
from src.utils.rate_limit import client_ip


class _Client:
    def __init__(self, host):
        self.host = host


class _Request:
    def __init__(self, forwarded, host="10.0.0.8"):
        self.headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
        self.client = _Client(host)


def test_one_helper_serves_rate_limit_and_store_net():
    assert client_ip is shared_client_ip is store_client_ip
    assert trusted_hops.__module__ == "src.utils.net"


def test_spoofed_left_most_is_ignored(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_Request("1.2.3.4, 5.6.7.8")) == "5.6.7.8"


def test_zero_hops_uses_the_direct_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    assert client_ip(_Request("1.2.3.4, 5.6.7.8", host="9.9.9.9")) == "9.9.9.9"


def test_missing_header_uses_the_peer(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_ip(_Request(None, host="10.1.1.1")) == "10.1.1.1"


def test_short_forwarded_header_uses_the_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert client_ip(_Request("1.2.3.4", host="9.9.9.9")) == "9.9.9.9"


def test_cloudflare_header_is_ignored_unless_the_peer_is_cloudflare(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_IP_RANGES", raising=False)
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    req = _Request("1.2.3.4, 5.6.7.8", host="9.9.9.9")
    req.headers["CF-Connecting-IP"] = "203.0.113.9"
    assert client_ip(req) == "5.6.7.8"


def test_cloudflare_header_wins_when_the_connecting_hop_is_cloudflare(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_IP_RANGES", raising=False)
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    # 104.16.0.0/13 is in the bundled snapshot. The socket itself is Render's proxy.
    req = _Request("203.0.113.9, 104.16.1.2", host="10.0.0.8")
    req.headers["CF-Connecting-IP"] = "203.0.113.50"
    assert client_ip(req) == "203.0.113.50"


def test_direct_cloudflare_peer_trusts_the_header(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_IP_RANGES", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    req = _Request(None, host="2606:4700::1")
    req.headers["cf-connecting-ip"] = "198.51.100.7"
    assert client_ip(req) == "198.51.100.7"


def test_env_override_replaces_the_bundled_ranges(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_IP_RANGES", "9.9.9.9/32")
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    trusted = _Request(None, host="9.9.9.9")
    trusted.headers["CF-Connecting-IP"] = "198.51.100.8"
    assert client_ip(trusted) == "198.51.100.8"
    bundled = _Request("203.0.113.1, 104.16.1.2", host="10.0.0.8")
    bundled.headers["CF-Connecting-IP"] = "198.51.100.9"
    assert client_ip(bundled) == "104.16.1.2"


def test_blank_cloudflare_header_falls_back_to_hops(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    monkeypatch.delenv("CLOUDFLARE_IP_RANGES", raising=False)
    req = _Request("1.2.3.4, 5.6.7.8")
    req.headers["cf-connecting-ip"] = "  "
    assert client_ip(req) == "5.6.7.8"
