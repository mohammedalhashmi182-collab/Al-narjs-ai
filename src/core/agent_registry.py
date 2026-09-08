from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import UUID

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentCategory(str, Enum):
    SUPPORT = "support"
    MARKETING = "marketing"
    CONTENT = "content"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    GENERAL = "general"


class PromptTemplate(BaseModel):
    name: str
    version: int
    template_text: str
    variables: list[str] = Field(default_factory=list)
    is_default: bool = False
    changelog: str = ""
    created_at: float = Field(default_factory=time.time)


class AgentDefinition(BaseModel):
    slug: str
    name: str
    description: str = ""
    category: AgentCategory = AgentCategory.GENERAL
    default_model: str
    default_parameters: dict = Field(default_factory=dict)
    prompt_templates: dict[str, PromptTemplate] = Field(default_factory=dict)
    is_system: bool = False
    created_by: UUID | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class AgentRegistry:
    def __init__(
        self,
        db_session_factory,
        base_path: Path = Path("agents"),
    ):
        self._db_session_factory = db_session_factory
        self.base_path = base_path
        self._cache: dict[str, AgentDefinition] = {}
        self._lock = asyncio.Lock()

    async def load_from_yaml(self, yaml_path: Path) -> AgentDefinition:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        prompt_templates = {}
        for name, template_data in data.get("prompts", {}).items():
            if isinstance(template_data, str):
                prompt_templates[name] = PromptTemplate(
                    name=name,
                    version=1,
                    template_text=template_data,
                    variables=self._extract_variables(template_data),
                    is_default=(name == "default"),
                )
            else:
                prompt_templates[name] = PromptTemplate(
                    name=name,
                    version=template_data.get("version", 1),
                    template_text=template_data["template"],
                    variables=template_data.get("variables", self._extract_variables(template_data["template"])),
                    is_default=template_data.get("is_default", name == "default"),
                    changelog=template_data.get("changelog", ""),
                )

        if not prompt_templates and "prompt" in data:
            prompt_templates["default"] = PromptTemplate(
                name="default",
                version=1,
                template_text=data["prompt"],
                variables=self._extract_variables(data["prompt"]),
                is_default=True,
            )

        return AgentDefinition(
            slug=yaml_path.stem,
            name=data["name"],
            description=data.get("description", ""),
            category=AgentCategory(data.get("category", "general")),
            default_model=data["model"],
            default_parameters=data.get("parameters", {}),
            prompt_templates=prompt_templates,
            is_system=data.get("is_system", False),
        )

    def _extract_variables(self, template: str) -> list[str]:
        import re
        return list(set(re.findall(r"\{\{(\w+)\}\}", template)))

    async def upsert_agent(self, defn: AgentDefinition) -> AgentDefinition:
        async with self._lock, self._db_session_factory() as session:
            from src.models import Agent
            from src.models import PromptTemplate as DBPromptTemplate

            result = await session.execute(select(Agent).where(Agent.slug == defn.slug))
            agent = result.scalar_one_or_none()

            if agent is None:
                agent = Agent(
                    slug=defn.slug,
                    name=defn.name,
                    description=defn.description,
                    category=defn.category.value,
                    default_model=defn.default_model,
                    default_parameters=defn.default_parameters,
                    is_system=defn.is_system,
                    created_by=defn.created_by,
                )
                session.add(agent)
                await session.flush()

            agent.name = defn.name
            agent.description = defn.description
            agent.category = defn.category.value
            agent.default_model = defn.default_model
            agent.default_parameters = defn.default_parameters
            agent.updated_at = datetime.now(timezone.utc)

            for tmpl_name, tmpl in defn.prompt_templates.items():
                result = await session.execute(
                    select(DBPromptTemplate).where(
                        DBPromptTemplate.agent_id == agent.id,
                        DBPromptTemplate.name == tmpl_name,
                    )
                )
                db_tmpl = result.scalar_one_or_none()
                if db_tmpl is None:
                    db_tmpl = DBPromptTemplate(
                        agent_id=agent.id,
                        name=tmpl_name,
                        version=tmpl.version,
                        template_text=tmpl.template_text,
                        variables=tmpl.variables,
                        is_default=tmpl.is_default,
                        changelog=tmpl.changelog,
                    )
                    session.add(db_tmpl)
                else:
                    db_tmpl.version = tmpl.version
                    db_tmpl.template_text = tmpl.template_text
                    db_tmpl.variables = tmpl.variables
                    db_tmpl.is_default = tmpl.is_default
                    db_tmpl.changelog = tmpl.changelog

            await session.commit()
            await session.refresh(agent)

            self._cache[defn.slug] = defn
            return defn

    async def sync_base_agents(self) -> list[AgentDefinition]:
        agents = []
        base_path = self.base_path / "base"
        if not base_path.exists():
            logger.warning(f"Base agents path not found: {base_path}")
            return agents

        for yaml_file in base_path.glob("*.yaml"):
            try:
                agent_def = await self.load_from_yaml(yaml_file)
                await self.upsert_agent(agent_def)
                agents.append(agent_def)
                logger.info(f"Synced agent: {agent_def.slug}")
            except Exception as e:
                logger.error(f"Failed to sync agent {yaml_file}: {e}")

        return agents

    async def get_agent(self, slug: str) -> AgentDefinition | None:
        if slug in self._cache:
            return self._cache[slug]

        async with self._db_session_factory() as session:
            from src.models import Agent
            from src.models import PromptTemplate as DBPromptTemplate

            result = await session.execute(select(Agent).where(Agent.slug == slug))
            agent = result.scalar_one_or_none()
            if not agent:
                return None

            result = await session.execute(
                select(DBPromptTemplate).where(DBPromptTemplate.agent_id == agent.id)
            )
            templates = result.scalars().all()

            prompt_templates = {}
            for tmpl in templates:
                prompt_templates[tmpl.name] = PromptTemplate(
                    name=tmpl.name,
                    version=tmpl.version,
                    template_text=tmpl.template_text,
                    variables=tmpl.variables,
                    is_default=tmpl.is_default,
                    changelog=tmpl.changelog,
                    created_at=tmpl.created_at.timestamp() if tmpl.created_at else time.time(),
                )

            defn = AgentDefinition(
                slug=agent.slug,
                name=agent.name,
                description=agent.description or "",
                category=AgentCategory(agent.category),
                default_model=agent.default_model,
                default_parameters=agent.default_parameters,
                prompt_templates=prompt_templates,
                is_system=agent.is_system,
                created_by=agent.created_by,
            )
            self._cache[slug] = defn
            return defn

    async def list_agents(self, category: AgentCategory | None = None) -> list[AgentDefinition]:
        async with self._db_session_factory() as session:
            from src.models import Agent

            query = select(Agent)
            if category:
                query = query.where(Agent.category == category.value)
            result = await session.execute(query)
            agents = result.scalars().all()

            defs = []
            for agent in agents:
                defn = await self.get_agent(agent.slug)
                if defn:
                    defs.append(defn)
            return defs

    async def delete_agent(self, slug: str) -> bool:
        async with self._db_session_factory() as session:
            from src.models import Agent

            result = await session.execute(select(Agent).where(Agent.slug == slug))
            agent = result.scalar_one_or_none()
            if not agent or agent.is_system:
                return False

            await session.delete(agent)
            await session.commit()
            self._cache.pop(slug, None)
            return True

    def invalidate_cache(self, slug: str | None = None):
        if slug:
            self._cache.pop(slug, None)
        else:
            self._cache.clear()
