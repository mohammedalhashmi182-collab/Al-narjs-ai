import pytest
from pydantic import BaseModel, Field
from src.core.model_provider import (
    ModelProvider,
    ModelProviderType,
    ModelSpec,
    ModelRequest,
    ModelResponse,
    CodeExecutorClient,
    CircuitBreaker,
    CircuitBreakerOpen,
)


class TestOutput(BaseModel):
    result: str = Field(description="The result")
    confidence: float = Field(ge=0, le=1, description="Confidence score")


def test_model_spec_parsing():
    spec = ModelSpec.parse("ollama:deepseek-r1")
    assert spec.provider == ModelProviderType.OLLAMA
    assert spec.model_name == "deepseek-r1"

    spec2 = ModelSpec.parse("openai:gpt-4o")
    assert spec2.provider == ModelProviderType.OPENAI
    assert spec2.model_name == "gpt-4o"

    with pytest.raises(ValueError):
        ModelSpec.parse("invalid")


def test_model_spec_str():
    spec = ModelSpec(provider=ModelProviderType.OLLAMA, model_name="llama3.1")
    assert str(spec) == "ollama:llama3.1"


def test_model_request_defaults():
    req = ModelRequest(prompt="Hello")
    assert req.temperature == 0.7
    assert req.max_tokens == 2000
    assert req.system_prompt == ""


def test_model_request_with_structured_output():
    req = ModelRequest(prompt="Test", response_model=TestOutput)
    assert req.response_model == TestOutput


def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
    assert not cb.is_open

    cb.failure_count = 2
    cb.last_failure_time = 1000.0  # old failure, but within recovery_timeout if now is close
    # Need to set a recent failure time to test open state
    import time
    cb.last_failure_time = time.time()
    assert cb.is_open

    # After recovery timeout, should be closed
    cb.last_failure_time = time.time() - 2.0
    assert not cb.is_open


@pytest.mark.asyncio
async def test_circuit_breaker_context_manager():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)

    async with cb:
        pass
    assert cb.failure_count == 0

    with pytest.raises(Exception):
        async with cb:
            raise ValueError("test")
    assert cb.failure_count == 1
    assert cb.is_open


@pytest.mark.asyncio
async def test_code_executor_python():
    client = CodeExecutorClient({"default_timeout": 10})

    request = ModelRequest(
        prompt='print("Hello from Python")',
        metadata={"language": "python"},
    )

    response = await client.complete(request)
    assert "Hello from Python" in response.content
    assert response.provider == ModelProviderType.CODE_EXECUTOR
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_code_executor_error():
    client = CodeExecutorClient({"default_timeout": 5})

    request = ModelRequest(
        prompt="raise ValueError('test error')",
        metadata={"language": "python"},
    )

    response = await client.complete(request)
    assert "[ERROR]" in response.content or "test error" in response.content
    assert response.provider == ModelProviderType.CODE_EXECUTOR


@pytest.mark.asyncio
async def test_code_executor_timeout():
    client = CodeExecutorClient({"default_timeout": 1})

    request = ModelRequest(
        prompt="import time; time.sleep(5)",
        metadata={"language": "python"},
    )

    response = await client.complete(request)
    assert "timeout" in response.content.lower() or "TimeoutError" in response.content


class TestModelProviderIntegration:
    @pytest.fixture
    def mock_settings(self):
        class MockSettings:
            ollama_base_url = "http://localhost:11434"
            ollama_default_model = "deepseek-r1"
            ollama_timeout = 30.0
            ollama_max_connections = 5
            openai_api_key = None
            openai_base_url = "https://api.openai.com/v1"
            openai_default_model = "gpt-4o-mini"
            groq_api_key = None
            groq_default_model = "llama-3.1-70b-versatile"
            anthropic_api_key = None
            anthropic_default_model = "claude-3-5-sonnet-20241022"
            code_executor_timeout = 30

        return MockSettings()

    def test_provider_initialization(self, mock_settings):
        provider = ModelProvider(mock_settings)
        assert ModelProviderType.OLLAMA in provider._clients
        assert ModelProviderType.CODE_EXECUTOR in provider._clients
        assert ModelProviderType.OPENAI not in provider._clients

    def test_fallback_chain_registration(self, mock_settings):
        provider = ModelProvider(mock_settings)
        chain = [
            ModelSpec(provider=ModelProviderType.OLLAMA, model_name="model1", priority=1),
            ModelSpec(provider=ModelProviderType.OLLAMA, model_name="model2", priority=2),
        ]
        provider.register_fallback_chain("test_chain", chain)
        assert "test_chain" in provider._fallback_chains
        assert len(provider._fallback_chains["test_chain"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])