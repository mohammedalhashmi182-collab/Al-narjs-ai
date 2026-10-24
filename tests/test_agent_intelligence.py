"""Regression contract for Al-Narjis Agent Intelligence v1."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services import agent_profiles, agent_runtime, catalog


def _category(value):
    return SimpleNamespace(value=value)


def _response(content: str, *, model: str = "fake:model", tokens: int = 10):
    return SimpleNamespace(
        content=content,
        model=model,
        tokens_used=tokens,
        latency_ms=1,
        structured_output=None,
    )


def test_every_catalog_agent_has_runtime_skills():
    assert len(catalog.EMPLOYEES) >= 35
    for slug in catalog.EMPLOYEES:
        path = Path("agents/base") / f"{slug}.yaml"
        assert path.exists(), slug
        import yaml
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = agent_profiles.profile_for(slug, raw.get("category"))
        assert len(profile.skills) >= 6, (slug, profile.skills)
        assert profile.evidence_mode in {"strict", "grounded", "creative"}
        assert profile.min_tokens >= 2200
        assert profile.temperature_cap <= 0.65


def test_specialists_receive_real_runtime_capabilities():
    assert "web_search" in agent_profiles.profile_for("market_analyst", "analysis").tools
    assert "market_research" in agent_profiles.profile_for("market_analyst", "analysis").skills
    assert "arithmetic_verification" in agent_profiles.profile_for("finance_pricing", "analysis").skills
    assert "saudi_pdpl" in agent_profiles.profile_for("legal_privacy", "analysis").skills
    assert "python_engineering" in agent_profiles.profile_for("software_engineer", "automation").skills
    assert "knowledge_base" in agent_profiles.profile_for("customer_service", "support").tools
    assert "consultative_selling" in agent_profiles.profile_for("sales_closer", "marketing").skills


def test_no_legacy_project_identity_in_runtime_agent_definitions():
    offenders = []
    for path in Path("agents/base").glob("*.yaml"):
        if "x_tasami" in path.read_text(encoding="utf-8"):
            offenders.append(str(path))
    registry = Path("src/core/architecture/registry/agent_catalog.py").read_text(encoding="utf-8")
    assert "x_tasami" not in registry
    assert not offenders, offenders


def test_orchestrator_no_longer_claims_fixed_ten_agent_platform():
    text = Path("agents/base/orchestrator.yaml").read_text(encoding="utf-8")
    assert "منصة 10 وكلاء" not in text
    assert "النرجس AI" in text


def test_all_execution_surfaces_use_central_runtime():
    files = {
        "src/main.py": 2,
        "src/automation/queue_worker.py": 1,
        "src/automation/workflow_engine.py": 1,
        "src/services/schedule_service.py": 1,
        "src/interfaces/web_ui.py": 1,
        "src/services/__init__.py": 1,
        "src/interfaces/cli.py": 1,
    }
    for name, minimum in files.items():
        text = Path(name).read_text(encoding="utf-8")
        assert text.count("agent_runtime.execute") >= minimum, name


class CorrectingProvider:
    def __init__(self):
        self.primary_requests = []
        self.fallback_requests = []
        self.n = 0

    async def complete(self, _spec, request):
        self.primary_requests.append(request)
        return _response("قصير")

    async def complete_with_fallback(self, _chain, request):
        self.fallback_requests.append(request)
        self.n += 1
        if self.n == 1:
            return _response('{"verdict":"RETURN","issues":["الإجابة ناقصة ولا تشرح المنهج أو القيود"]}')
        if self.n == 2:
            return _response(
                "## تحليل مصحح\n"
                "اعتمد هذا التحليل فقط على بيانات العميل والمصادر المرفقة. "
                "لا توجد أرقام سوق مؤكدة في المدخلات، لذلك لن أختلق حجماً للسوق. "
                "الخطوة الأولى هي جمع حجم الطلب، المنافسين، الأسعار والقنوات من المصادر المتاحة، "
                "ثم فصل الحقائق عن الافتراضات وبناء توصيات قابلة للقياس."
            )
        return _response('{"verdict":"PASS","issues":[]}')


@pytest.mark.asyncio
async def test_bad_strict_agent_draft_is_corrected_before_delivery():
    provider = CorrectingProvider()
    agent = SimpleNamespace(
        slug="market_analyst",
        category=_category("analysis"),
        default_model="fake:model",
        default_parameters={"temperature": 0.9, "max_tokens": 500, "top_p": 0.9},
    )
    result = await agent_runtime.execute(
        provider,
        agent,
        prompt="حلل السوق بناءً على البيانات المتاحة فقط",
        system_prompt="أنت محلل سوق.",
        tool_context="[نتائج بحث ويب حديثة]\n- مصدر موثوق — https://example.sa\n  بيانات وصفية فقط",
        locale="ar",
        client_name="عميل تجريبي",
        quality_gate=True,
    )
    assert result.quality["passed"] is True
    assert result.quality["corrected"] is True
    assert "market_research" in result.quality["skills"]
    assert "web_search" in result.quality["tools"]
    assert "لن أختلق" in result.content
    assert provider.primary_requests[0].temperature <= 0.35
    assert provider.primary_requests[0].max_tokens >= 2400


class RejectingProvider(CorrectingProvider):
    async def complete_with_fallback(self, _chain, request):
        self.fallback_requests.append(request)
        self.n += 1
        if self.n == 1:
            return _response('{"verdict":"RETURN","issues":["unsupported market claim"]}')
        if self.n == 2:
            return _response(
                "هذا نص طويل بما يكفي للاختبار لكنه ما زال يدعي أرقاماً خارجية بلا دليل واضح، "
                "ولذلك يجب ألا يصل إلى العميل في وضع الأدلة الصارم مهما بدا منسقاً أو مقنعاً."
            )
        return _response('{"verdict":"RETURN","issues":["still unsupported"]}')


@pytest.mark.asyncio
async def test_strict_evidence_agent_fails_closed_after_bad_correction():
    provider = RejectingProvider()
    agent = SimpleNamespace(
        slug="market_analyst",
        category=_category("analysis"),
        default_model="fake:model",
        default_parameters={},
    )
    with pytest.raises(RuntimeError, match="strict evidence answer failed"):
        await agent_runtime.execute(
            provider,
            agent,
            prompt="اعطني أرقاماً عن السوق",
            system_prompt="",
            tool_context="",
            locale="ar",
            quality_gate=True,
        )
