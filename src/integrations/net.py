"""Client address for store rate limits.

The implementation lives in :mod:`src.utils.net` so the public AI rate limit
and the store webhooks share one rule: ``CF-Connecting-IP`` first, then
``TRUSTED_PROXY_HOPS`` on ``X-Forwarded-For``.
"""

from src.utils.net import client_ip, trusted_hops

__all__ = ["client_ip", "trusted_hops"]
