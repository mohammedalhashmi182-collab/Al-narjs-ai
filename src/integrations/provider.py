"""Shared store types. Platform clients in ``salla`` and ``zid`` implement ``StoreProvider``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class StoreApiError(Exception):
    """Safe to log: operation name and HTTP status only. Never a response body."""

    def __init__(self, operation: str, status: int) -> None:
        self.operation = operation
        self.status = status
        super().__init__(f"{operation}:{status}")


@dataclass
class OrderHit:
    reference: str
    status: str
    phone: str
    masked: bool
    platform: str


@dataclass
class ProductHit:
    name: str
    price: Optional[str]
    available: bool
    platform: str


@dataclass
class StoreInfo:
    merchant_id: str
    store_ref: Optional[str]
    name: Optional[str]
    platform: str


class StoreProvider(Protocol):
    platform: str

    async def fetch_order(self, reference: str) -> Optional[OrderHit]:
        """Order by the number the customer gave. Includes the phone for verification only."""

    async def search_products(self, query: str) -> list[ProductHit]:
        """Name, price, and availability. Hidden products are omitted."""

    async def fetch_store(self) -> StoreInfo:
        """Store id and display name. No email, phone, or address."""
