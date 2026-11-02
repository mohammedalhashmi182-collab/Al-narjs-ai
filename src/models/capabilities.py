"""Style profiles and evaluation score logs.

Additive tables, created by ``create_all`` at startup like the other additive
models. An alembic mirror is pending owner approval (CLAUDE.md rule 6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ClientStyleProfile(Base):
    """Brand voice for one client. Injected into that client's agent prompts."""

    __tablename__ = "client_style_profiles"

    client_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    brand_ar: Mapped[str] = mapped_column(String(120), default="", server_default="")
    brand_en: Mapped[str] = mapped_column(String(120), default="", server_default="")
    register: Mapped[str] = mapped_column(String(16), default="msa", server_default="msa")
    tone: Mapped[str] = mapped_column(String(200), default="", server_default="")
    banned_words: Mapped[list] = mapped_column(JSON, default=list)
    colours: Mapped[str] = mapped_column(String(200), default="", server_default="")
    fonts: Mapped[str] = mapped_column(String(200), default="", server_default="")
    signature: Mapped[str] = mapped_column(Text, default="", server_default="")
    learned: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CapabilityEvalLog(Base):
    """One scoring round. The deliverable text itself is not stored."""

    __tablename__ = "capability_eval_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_slug: Mapped[str] = mapped_column(String(80), default="", index=True)
    client_key: Mapped[str] = mapped_column(String(64), default="", index=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    overall: Mapped[float] = mapped_column(Float, default=0)
    rounds: Mapped[int] = mapped_column(Integer, default=1)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
