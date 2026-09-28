"""Every agent definition must render: valid YAML, valid category, valid model
spec, parameters in range, and a prompt template that actually compiles under
Jinja. Guards the launch funnel (portal run path) against broken templates."""

from pathlib import Path

import pytest
import yaml
from jinja2 import Environment
from jinja2.exceptions import TemplateError

from src.core.model_provider import ModelSpec

BASE = Path(__file__).resolve().parent.parent / "agents" / "base"
VALID_CATEGORIES = {"support", "marketing", "content", "analysis", "automation", "general"}


def _default_prompt(data: dict) -> str:
    prompts = data.get("prompts") or {}
    assert prompts, f"no prompts block"
    default = prompts.get("default")
    assert default, f"no prompts.default"
    assert isinstance(default, str) and default.strip(), "prompts.default empty"
    return default


@pytest.mark.parametrize("yaml_path", sorted(BASE.glob("*.yaml")), ids=lambda p: p.stem)
def test_agent_yaml_definitions_compile(yaml_path: Path):
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data, f"{yaml_path.name}: empty YAML"

    assert data.get("name"), f"{yaml_path.name}: missing name"
    assert data.get("category") in VALID_CATEGORIES, f"{yaml_path.name}: invalid category {data.get('category')}"
    spec = data.get("model")
    assert spec, f"{yaml_path.name}: missing model"
    parsed = ModelSpec.parse(spec)  # raises on malformed spec

    params = data.get("parameters") or {}
    temp = params.get("temperature")
    assert temp is not None and 0.0 <= float(temp) <= 2.0, f"{yaml_path.name}: temperature invalid"
    top_p = params.get("top_p")
    assert top_p is not None and 0.0 <= float(top_p) <= 1.0, f"{yaml_path.name}: top_p invalid"
    max_tokens = params.get("max_tokens")
    assert max_tokens is not None and max_tokens >= 1, f"{yaml_path.name}: max_tokens invalid"

    env = Environment()
    prompt = _default_prompt(data)
    try:
        env.from_string(prompt)
    except TemplateError as e:
        pytest.fail(f"{yaml_path.name}: prompt template does not compile: {e}")


def test_gemini_flash_is_used_for_all_agents():
    for yaml_path in sorted(BASE.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["model"] == "gemini:gemini-3.6-flash", f"{yaml_path.name}: unexpected model {data['model']}"


def test_known_agent_count_stays_35():
    assert len(list(BASE.glob("*.yaml"))) == 35