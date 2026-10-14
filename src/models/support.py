"""Support tickets opened from the site assistant (human handoff).

Strictly additive table, created by ``create_all`` at startup like the other
additive models (self-heal). The public reference is ``NRJ-`` + zero-padded id.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

TICKET_STATUSES = ("open", "answered", "closed")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str] = mapped_column(String(5), nullable=False, default="ar")
    page: Mapped[Optional[str]] = mapped_column(String(300))
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open", index=True)
    notify_result: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def reference(self) -> str:
        return f"NRJ-{self.id:06d}"
