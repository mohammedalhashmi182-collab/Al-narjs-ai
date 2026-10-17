"""Contract tests for ``POST /api/consult``.

Why this file exists at all: the consultant went fully dark in production and
**nothing failed**. The endpoint answered ``HTTP 200`` on every call, including
the one where every model provider was dead, and put an apology string in the
``reply`` field. A green uptime check, a green log scan and a green test suite
all passed while the product's main conversion surface returned nothing.

The five tests below lock the failure modes that were missed:

1. a successful generation returns a real answer, not a placeholder;
2. an exhausted chain returns a **non-2xx**, so a monitor can see the outage;
3. a configured provider is actually reachable through the chain, not merely
   registered as a client and then ignored;
4. no configuration means the chain is refused before any network call;
5. the response body shape is preserved on both paths, so ``consult.html`` --
   which renders ``data.reply`` without checking the status -- keeps working.

No provider is contacted in these tests. A stubbed provider stands in, so the
suite stays deterministic and costs nothing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.core.model_provider import ModelProviderError, ModelProviderType, ModelSpec
from src.main import app

CONSULT = "/api/consult"
BODY = {"messages": [{"role": "user", "content": "ما هي باقاتكم؟"}]}

# a reply that is unmistakably a real answer, so a test can tell it apart from
# any placeholder or apology the endpoint might emit
# (uses a real catalog price: invented numbers are now handed off, see test_rag_site_assistant.py)
REAL_ANSWER = "لدينا ثلاث باقات تبدأ من 599 ريال شهرياً، وكل باقة تفتح وكلاء متخصصين."


class _StubResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _WorkingProvider:
    """Stands in for ``app.state.model_provider`` when generation succeeds."""

    def __init__(self, content: str = REAL_ANSWER) -> None:
        self.content = content
        self.calls: list[str] = []

    async def complete_with_fallback(self, chain_name, request):
        self.calls.append(chain_name)
        return _StubResponse(self.content)


class _DeadProvider:
    """Every model is unusable, exactly as in the production outage."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._error = error or ModelProviderError(
            "All models in fallback chain 'gemini' failed",
            ModelProviderType.OLLAMA,
            "",
            RuntimeError("exceeded_current_quota_error"),
        )

    async def complete_with_fallback(self, chain_name, request):
        self.calls.append(chain_name)
        raise self._error


@pytest.fixture()
def client(monkeypatch):
    """Bypass the shared rate limiter; these tests make several calls per IP."""
    import src.utils.rate_limit as rl

    monkeypatch.setattr(rl.consult_limiter, "reset", lambda: None, raising=False)
    with TestClient(app) as c:
        yield c


def _use(monkeypatch, provider) -> None:
    monkeypatch.setattr(app.state, "model_provider", provider, raising=False)


# --------------------------------------------------------------------------
# 1. the happy path still works, and the contract is unchanged
# --------------------------------------------------------------------------


def test_a_real_answer_returns_200_with_the_reply_field(client, monkeypatch):
    _use(monkeypatch, _WorkingProvider())
    r = client.post(CONSULT, json=BODY)
    assert r.status_code == 200
    assert r.json()["reply"] == REAL_ANSWER
    # the success contract is exactly what it was before this change
    assert set(r.json()) == {"reply"}


def test_the_gemini_chain_is_the_one_used(client, monkeypatch):
    provider = _WorkingProvider()
    _use(monkeypatch, provider)
    client.post(CONSULT, json=BODY)
    assert provider.calls == ["gemini"]


def test_an_empty_model_answer_is_a_failure_not_a_success(client, monkeypatch):
    """A blank bubble in the transcript is a broken consultant, not an answer."""
    _use(monkeypatch, _WorkingProvider(content="   "))
    r = client.post(CONSULT, json=BODY)
    assert r.status_code == 503


def test_a_lead_marker_is_stripped_from_the_visible_reply(client, monkeypatch):
    from src.core.karma_persona import LEAD_MARK

    _use(monkeypatch, _WorkingProvider(content=f'باقة البداية 599 ريال. {LEAD_MARK}{{"name":"x"}}'))
    r = client.post(CONSULT, json=BODY)
    assert r.status_code == 200
    assert LEAD_MARK not in r.json()["reply"], "the internal lead marker reached the user"
    assert "باقة البداية" in r.json()["reply"]


# --------------------------------------------------------------------------
# 2. the outage is now visible: non-2xx on total failure
# --------------------------------------------------------------------------


def test_total_provider_failure_returns_a_service_error(client, monkeypatch):
    _use(monkeypatch, _DeadProvider())
    r = client.post(CONSULT, json=BODY)
    assert r.status_code == 503, "a dead chain must not answer 200"


def test_the_failure_body_still_carries_a_reply(client, monkeypatch):
    """consult.html renders data.reply without checking the status."""
    _use(monkeypatch, _DeadProvider())
    body = client.post(CONSULT, json=BODY).json()
    assert body["reply"].strip(), "the page would render an empty bubble"
    assert body["error"] == "consult_unavailable"
    assert body["retryable"] is True


def test_the_failure_message_is_arabic_and_safe(client, monkeypatch):
    _use(monkeypatch, _DeadProvider())
    body = client.post(CONSULT, json=BODY).json()
    assert any("\u0600" <= ch <= "\u06ff" for ch in body["reply"])
    for leak in ("sk-", "api_key", "Traceback", "429", "401"):
        assert leak not in body["reply"], f"the failure message leaks: {leak}"


def test_the_failure_never_leaks_the_underlying_exception(client, monkeypatch):
    secret = "sk-test-abcdefghijklmnopqrstuvwxyz0123456789"
    _use(monkeypatch, _DeadProvider(error=RuntimeError(f"boom {secret}")))
    payload = client.post(CONSULT, json=BODY).text
    assert secret not in payload
    assert "boom" not in payload


def test_an_empty_request_is_rejected_before_any_provider_call(client, monkeypatch):
    provider = _DeadProvider()
    _use(monkeypatch, provider)
    r = client.post(CONSULT, json={"messages": []})
    assert r.status_code == 400
    assert provider.calls == [], "a rejected request must not reach the provider"


# --------------------------------------------------------------------------
# 3. a configured provider is reachable through the chain, not merely registered
# --------------------------------------------------------------------------


def _provider_with(**overrides):
    """Build a ModelProvider against a settings stub, without touching env."""
    from src.core.model_provider import ModelProvider

    class _Settings:
        def __init__(self, **kw):
            defaults = {
                "openai_api_key": None,
                "openai_base_url": "https://api.openai.com/v1",
                "openai_default_model": "gpt-4o-mini",
                "gemini_api_key": None,
                "gemini_default_model": "gemini-3.6-flash",
                "moonshot_api_key": None,
                "moonshot_base_url": "https://api.moonshot.ai/v1",
                "moonshot_default_model": "kimi-k2.7-code",
                "openrouter_api_key": None,
                "openrouter_base_url": "https://openrouter.ai/api/v1",
                "openrouter_default_model": "openai/gpt-4o-mini",
                "ollama_base_url": "http://localhost:11434",
                "ollama_default_model": "deepseek-r1",
                "ollama_timeout": 120.0,
                "ollama_max_connections": 10,
                "groq_api_key": None,
                "anthropic_api_key": None,
                "openai_base_url_default": None,
                "code_executor_timeout": 30.0,
                "domain": "karmaai.online",
            }
            defaults.update(kw)
            for key, value in defaults.items():
                setattr(self, key, value)

    provider = ModelProvider.__new__(ModelProvider)
    provider.settings = _Settings(**overrides)
    provider._clients = {}
    provider._fallback_chains = {}
    provider._circuit_breakers = {}
    ModelProvider._initialize_clients(provider)
    return provider


def _chain_specs(provider, chain: str = "gemini") -> list[str]:
    """Providers in a chain, or an empty list when the chain was not registered.

    Absence is a meaningful outcome here -- it is what "nothing is configured"
    looks like -- so it must not raise.
    """
    return [spec.provider.value for spec in provider._fallback_chains.get(chain, [])]


def test_a_configured_openai_key_is_reachable_through_the_chain():
    """The defect: OpenAI registered as a client but was never chained."""
    provider = _provider_with(openai_api_key="sk-configured-not-a-real-key")
    assert "openai" in _chain_specs(provider)


def test_openai_is_omitted_when_it_is_not_configured():
    provider = _provider_with(openai_api_key=None)
    assert "openai" not in _chain_specs(provider)


def test_openai_is_omitted_when_its_configuration_is_incomplete():
    """A key with no model name is not a usable configuration."""
    provider = _provider_with(openai_api_key="sk-x", openai_default_model=None)
    assert "openai" not in _chain_specs(provider)


def test_the_chain_survives_a_single_dead_provider():
    """The production shape: Moonshot out of credit, OpenAI present."""
    provider = _provider_with(
        moonshot_api_key="sk-moonshot-suspended",
        openai_api_key="sk-openai-invalid",
    )
    specs = _chain_specs(provider)
    assert specs.count("moonshot") == 1
    assert "openai" in specs
    assert provider._fallback_chains["gemini"], "the chain must still exist"


def test_the_chain_is_not_registered_when_nothing_is_configured():
    provider = _provider_with()
    assert "gemini" not in provider._fallback_chains, (
        "an empty chain must be absent, so the call fails before any network use"
    )


def test_no_api_key_is_embedded_in_the_chain():
    provider = _provider_with(
        moonshot_api_key="sk-moonshot-value",
        openai_api_key="sk-openai-value",
    )
    rendered = repr(provider._fallback_chains["gemini"])
    assert "sk-moonshot-value" not in rendered
    assert "sk-openai-value" not in rendered


# --------------------------------------------------------------------------
# 4. logging keeps the diagnostic and drops the secret
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_provider_failure_logs_the_type_and_not_the_key():
    """A 401 body from an OpenAI-compatible endpoint echoes the key back.

    The seam is ``_complete_raw``: replacing ``complete`` itself would bypass the
    very logging under test, because ``OpenAIClient`` inherits ``complete`` from
    ``BaseModelClient`` and patching it would remove the code being asserted.
    """
    from structlog.testing import capture_logs

    from src.core.model_provider import ModelRequest, OpenAIClient

    secret = "sk-leak-canary-000111222333"
    client_obj = OpenAIClient({
        "api_key": secret,
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    })

    async def _raw_with_echoing_error(_self, _request):
        # shaped like a real 401: the provider repeats the submitted key
        raise RuntimeError(f"Incorrect API key provided: {secret}")

    original = OpenAIClient._complete_raw
    OpenAIClient._complete_raw = _raw_with_echoing_error
    try:
        with capture_logs() as captured:
            with pytest.raises(Exception):
                await client_obj.complete(ModelRequest(prompt="ping"))
    finally:
        OpenAIClient._complete_raw = original

    emitted = "\n".join(
        event.get("event", "") + " " + repr(event.get("positional_args", ()))
        for event in captured
    )
    assert emitted, "the failure produced no log output at all"
    assert secret not in emitted, "the key reached the log"
    assert "RuntimeError" in emitted, "the failure type is no longer diagnosable"


@pytest.mark.asyncio
async def test_the_fallback_loop_does_not_log_the_provider_message():
    """The second log site: a failing spec must not print the provider's text."""
    from structlog.testing import capture_logs

    from src.core.model_provider import ModelRequest, ModelProvider, ModelProviderType, ModelSpec

    secret = "sk-chain-canary-999888777666"

    provider = ModelProvider.__new__(ModelProvider)
    provider.settings = None
    provider._fallback_chains = {}
    provider._circuit_breakers = {}

    class _AlwaysFails:
        async def complete(self, _request):
            raise RuntimeError(f"Incorrect API key provided: {secret}")

    provider._clients = {ModelProviderType.OPENAI: _AlwaysFails()}
    provider.register_fallback_chain(
        "gemini", [ModelSpec(provider=ModelProviderType.OPENAI, model_name="m", priority=10)]
    )

    with capture_logs() as captured:
        with pytest.raises(Exception):
            await provider.complete_with_fallback("gemini", ModelRequest(prompt="ping"))

    emitted = "\n".join(
        event.get("event", "") + " " + repr(event.get("positional_args", ()))
        for event in captured
    )
    assert emitted, "the exhausted chain produced no log output"
    assert secret not in emitted, "the provider message reached the log"
    assert "trying the next one" in emitted or "RuntimeError" in emitted