"""Multi-tenant Salla and Zid store integration.

The public site offers the connection on request (set up by Al-Narjs, read-only).
Install, OAuth callback, portal store API, store answers and non-uninstall
webhooks all stay off until ``STORE_INTEGRATIONS_ENABLED`` and
``STORE_TOKEN_ENC_KEY`` are both set. Tokens are encrypted per tenant. Order answers require the
customer's own phone to match the order. Policy answers come only from the
merchant's saved shipping/returns/payment text.
"""

from src.integrations.config import enabled

__all__ = ["enabled"]
