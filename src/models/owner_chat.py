"""Owner chat: custom agents, instruction overrides, and conversation history.

Additive tables. Startup ``create_all`` creates them; alembic 0019 mirrors them.
Nothing here stores provider keys or raw model errors.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class OwnerAgentProfile(Base):
    """One row per agent the owner has customised or switched off.

    Built-in catalog agents keep their identity in ``catalog.py``. This row
    only stores an enable flag and extra instructions. Custom agents store
    their name, role and instructions here.
    """

    __tablename__ = "owner_agent_profiles"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # builtin | custom
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    name_ar: Mapped[str | None] = mapped_column(String(80))
    role_ar: Mapped[str | None] = mapped_column(String(240))
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OwnerConversation(Base):
    """One owner chat thread. ``participants`` is the ordered agent slug list."""

    __tablename__ = "owner_conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    participants: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OwnerChatMessage(Base):
    __tablename__ = "owner_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("owner_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    speaker_slug: Mapped[str | None] = mapped_column(String(80))
    speaker_name: Mapped[str | None] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
