"""Live single-page prototypes produced by the prototype engineer.

Additive table, created by ``create_all`` at startup like the other additive
models. An alembic mirror is pending owner approval (CLAUDE.md rule 6).
The HTML is the deliverable. The customer's raw idea is not stored.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class LivePrototype(Base):
    __tablename__ = "live_prototypes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    idea_title: Mapped[str] = mapped_column(String(160), default="", server_default="")
    html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
