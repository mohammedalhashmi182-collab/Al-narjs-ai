"""Multi-tenant Salla and Zid store integration.

The public site keeps the coming-soon copy until ``STORE_INTEGRATIONS_ENABLED``
is turned on. Tokens are encrypted per tenant. Order answers require the
customer's own phone to match the order. Policy answers come only from the
merchant's saved shipping/returns/payment text.
"""

from src.integrations.config import enabled

__all__ = ["enabled"]
