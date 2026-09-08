from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentContext:
    agent_slug: str
    conversation_id: UUID
    messages: list[ConversationMessage] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, metadata: dict | None = None):
        self.messages.append(ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        ))
        self.updated_at = time.time()

    def get_history(self, limit: int | None = None) -> list[ConversationMessage]:
        if limit:
            return self.messages[-limit:]
        return self.messages

    def get_messages_for_model(self, max_tokens: int = 4000) -> list[dict]:
        result = []
        token_count = 0
        for msg in reversed(self.messages):
            msg_tokens = len(msg.content) // 4
            if token_count + msg_tokens > max_tokens:
                break
            result.insert(0, {"role": msg.role, "content": msg.content})
            token_count += msg_tokens
        return result


class ContextManager:
    def __init__(self, max_contexts_per_agent: int = 1000, max_messages_per_context: int = 100):
        self.max_contexts_per_agent = max_contexts_per_agent
        self.max_messages_per_context = max_messages_per_context
        self._contexts: dict[str, dict[UUID, AgentContext]] = defaultdict(dict)
        self._access_times: dict[UUID, float] = {}

    def get_or_create_context(
        self,
        agent_slug: str,
        conversation_id: UUID | None = None,
        initial_variables: dict | None = None,
    ) -> AgentContext:
        if conversation_id is None:
            conversation_id = uuid4()

        if conversation_id in self._contexts.get(agent_slug, {}):
            self._access_times[conversation_id] = time.time()
            return self._contexts[agent_slug][conversation_id]

        if len(self._contexts[agent_slug]) >= self.max_contexts_per_agent:
            self._evict_oldest(agent_slug)

        context = AgentContext(
            agent_slug=agent_slug,
            conversation_id=conversation_id,
            variables=initial_variables or {},
        )
        self._contexts[agent_slug][conversation_id] = context
        self._access_times[conversation_id] = time.time()
        return context

    def get_context(self, agent_slug: str, conversation_id: UUID) -> AgentContext | None:
        context = self._contexts.get(agent_slug, {}).get(conversation_id)
        if context:
            self._access_times[conversation_id] = time.time()
        return context

    def delete_context(self, agent_slug: str, conversation_id: UUID) -> bool:
        if conversation_id in self._contexts.get(agent_slug, {}):
            del self._contexts[agent_slug][conversation_id]
            self._access_times.pop(conversation_id, None)
            return True
        return False

    def update_variables(self, agent_slug: str, conversation_id: UUID, variables: dict) -> bool:
        context = self.get_context(agent_slug, conversation_id)
        if context:
            context.variables.update(variables)
            context.updated_at = time.time()
            return True
        return False

    def get_variables(self, agent_slug: str, conversation_id: UUID) -> dict:
        context = self.get_context(agent_slug, conversation_id)
        return context.variables if context else {}

    def _evict_oldest(self, agent_slug: str):
        if not self._contexts[agent_slug]:
            return
        oldest_id = min(
            self._contexts[agent_slug].keys(),
            key=lambda cid: self._access_times.get(cid, 0)
        )
        del self._contexts[agent_slug][oldest_id]
        self._access_times.pop(oldest_id, None)

    def cleanup_expired(self, max_age_seconds: float = 3600):
        current_time = time.time()
        expired = [
            cid for cid, last_access in self._access_times.items()
            if current_time - last_access > max_age_seconds
        ]
        for cid in expired:
            for agent_slug in list(self._contexts.keys()):
                if cid in self._contexts[agent_slug]:
                    del self._contexts[agent_slug][cid]
            self._access_times.pop(cid, None)

    def get_stats(self) -> dict:
        total_contexts = sum(len(contexts) for contexts in self._contexts.values())
        return {
            "total_contexts": total_contexts,
            "contexts_per_agent": {
                slug: len(contexts) for slug, contexts in self._contexts.items()
            },
        }
