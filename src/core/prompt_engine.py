from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined, Undefined, meta
from pydantic import BaseModel, ValidationError

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RenderedPrompt:
    system_prompt: str
    user_prompt: str
    variables_used: set[str]
    missing_variables: set[str]
    raw_rendered: str


class PromptEngine:
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            undefined=StrictUndefined if strict else Undefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["tojson"] = json.dumps
        self.env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)

    def parse_template(self, template_text: str) -> tuple[set[str], str]:
        try:
            ast = self.env.parse(template_text)
            variables = meta.find_undeclared_variables(ast)
            return variables, template_text
        except Exception as e:
            logger.warning(f"Failed to parse template: {e}")
            var_pattern = re.compile(r"\{\{(\w+)(?:\|.+?)?\}\}")
            variables = set(var_pattern.findall(template_text))
            return variables, template_text

    def render(
        self,
        template_text: str,
        variables: dict[str, Any],
        strict: bool | None = None,
    ) -> RenderedPrompt:
        strict_mode = strict if strict is not None else self.strict
        required_vars, _ = self.parse_template(template_text)
        provided_vars = set(variables.keys())
        missing = required_vars - provided_vars

        if strict_mode and missing:
            raise ValueError(f"Missing required variables: {missing}")

        try:
            template = self.env.from_string(template_text)
            rendered = template.render(**variables)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            if strict_mode:
                raise
            rendered = template_text
            for key, value in variables.items():
                rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

        system_prompt = ""
        user_prompt = rendered

        if "{{#system}}" in rendered:
            parts = rendered.split("{{#user}}", 1)
            system_prompt = parts[0].replace("{{#system}}", "").strip()
            user_prompt = parts[1].strip() if len(parts) > 1 else ""
        elif "{{#system}}" in rendered and "{{#user}}" not in rendered:
            system_prompt = rendered.replace("{{#system}}", "").strip()
            user_prompt = ""

        return RenderedPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            variables_used=required_vars & provided_vars,
            missing_variables=missing,
            raw_rendered=rendered,
        )

    def validate_template(self, template_text: str) -> tuple[bool, list[str]]:
        try:
            self.parse_template(template_text)
            return True, []
        except Exception as e:
            return False, [str(e)]

    def create_template_from_messages(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return f"{{{{#system}}}}\n{system_prompt}\n{{{{#user}}}}\n{user_prompt}"


class StructuredPromptEngine(PromptEngine):
    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self._schema_cache: dict[str, dict] = {}

    def render_structured(
        self,
        template_text: str,
        variables: dict[str, Any],
        response_model: type[BaseModel],
        strict: bool | None = None,
    ) -> tuple[RenderedPrompt, BaseModel | None]:
        rendered = self.render(template_text, variables, strict)

        structured_output = None
        if rendered.user_prompt:
            try:
                structured_output = response_model.model_validate_json(rendered.user_prompt)
            except (ValidationError, json.JSONDecodeError):
                try:
                    structured_output = response_model.model_validate(variables)
                except ValidationError as e:
                    logger.warning(f"Structured output validation failed: {e}")

        return rendered, structured_output

    def get_json_schema(self, model: type[BaseModel]) -> dict:
        model_name = f"{model.__module__}.{model.__name__}"
        if model_name not in self._schema_cache:
            self._schema_cache[model_name] = model.model_json_schema()
        return self._schema_cache[model_name]

    def inject_schema_instructions(self, template_text: str, response_model: type[BaseModel]) -> str:
        schema = self.get_json_schema(response_model)
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        return f"{template_text}\n\nRespond ONLY with valid JSON matching this schema:\n```json\n{schema_str}\n```"


def create_prompt_engine(strict: bool = False) -> PromptEngine:
    return PromptEngine(strict=strict)


def create_structured_prompt_engine(strict: bool = False) -> StructuredPromptEngine:
    return StructuredPromptEngine(strict=strict)
