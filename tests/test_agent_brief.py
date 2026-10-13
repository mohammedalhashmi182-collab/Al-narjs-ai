"""Every agent's interview answers reach its prompt (audit: ~20 agents dropped them)."""
from pathlib import Path

import yaml

from src.core.prompt_engine import PromptEngine
from src.services import agent_brief, catalog


def test_every_agent_renders_with_no_empty_variables_and_keeps_answers():
    engine = PromptEngine()
    for slug, emp in catalog.EMPLOYEES.items():
        tmpl = yaml.safe_load(Path(f"agents/base/{slug}.yaml").read_text())["prompts"]["default"]
        answers = {q["key"]: f"جواب-{q['key']}" for q in emp.get("questions", [])}
        variables = agent_brief.build_variables(tmpl, answers, "مقهى الياسمين")
        assert agent_brief.template_vars(tmpl) <= set(variables), slug
        rendered = engine.render(tmpl, variables).user_prompt
        prompt = rendered + agent_brief.brief_block(answers, emp.get("questions"), "مقهى الياسمين")
        for value in answers.values():
            assert value in prompt, (slug, value)


def test_saudi_context_and_token_floor():
    assert "SAR" in agent_brief.SAUDI_CONTEXT and "PDPL" in agent_brief.SAUDI_CONTEXT
    assert agent_brief.MIN_MAX_TOKENS >= 2000
