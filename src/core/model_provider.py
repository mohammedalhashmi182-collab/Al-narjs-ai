from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    MOONSHOT = "moonshot"
    CODE_EXECUTOR = "code_executor"


class ModelRole(str, Enum):
    PRIMARY = "primary"
    FALLBACK = "fallback"
    CODE = "code"
    EMBEDDING = "embedding"


@dataclass
class ModelSpec:
    provider: ModelProviderType
    model_name: str
    role: ModelRole = ModelRole.PRIMARY
    priority: int = 0

    @classmethod
    def parse(cls, spec: str) -> ModelSpec:
        parts = spec.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid model spec: {spec}. Expected 'provider:model_name'")
        provider_str, model_name = parts
        try:
            provider = ModelProviderType(provider_str.lower())
        except ValueError:
            raise ValueError(f"Unknown provider: {provider_str}")
        return cls(provider=provider, model_name=model_name)

    def __str__(self) -> str:
        return f"{self.provider.value}:{self.model_name}"


@dataclass
class ModelResponse(Generic[T]):
    content: str
    structured_output: T | None = None
    tokens_used: int = 0
    latency_ms: int = 0
    model: str = ""
    provider: ModelProviderType = ModelProviderType.OLLAMA
    raw_response: dict = field(default_factory=dict)


@dataclass
class ModelRequest:
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    stop_sequences: list[str] = field(default_factory=list)
    response_model: type[BaseModel] | None = None
    stream: bool = False
    metadata: dict = field(default_factory=dict)


class ModelProviderError(Exception):
    def __init__(self, message: str, provider: ModelProviderType, model: str, original_error: Exception | None = None):
        self.provider = provider
        self.model = model
        self.original_error = original_error
        super().__init__(message)


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        if self.failure_count >= self.failure_threshold:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                return False
            return True
        return False

    async def record_success(self):
        async with self._lock:
            self.failure_count = 0
            self.last_failure_time = None

    async def record_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

    async def __aenter__(self):
        if self.is_open:
            raise CircuitBreakerOpen("Circuit breaker open, failing fast")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.record_failure()
        else:
            await self.record_success()
        return False


class BaseModelClient(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("circuit_breaker_threshold", 5),
            recovery_timeout=config.get("circuit_breaker_timeout", 60.0),
        )
        self._client: httpx.AsyncClient | None = None

    @property
    @abstractmethod
    def provider_type(self) -> ModelProviderType:
        pass

    @abstractmethod
    async def _complete_raw(self, request: ModelRequest) -> dict:
        pass

    @abstractmethod
    async def _stream_raw(self, request: ModelRequest) -> AsyncIterator[str]:
        pass

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                connect=10.0,
                read=self.config.get("timeout", 120.0),
                write=10.0,
                pool=5.0,
            )
            limits = httpx.Limits(
                max_connections=self.config.get("max_connections", 10),
                max_keepalive_connections=self.config.get("max_keepalive", 5),
            )
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, ModelProviderError)),
    )
    async def complete(self, request: ModelRequest) -> ModelResponse:
        async with self.circuit_breaker:
            start_time = time.perf_counter()
            try:
                raw_response = await self._complete_raw(request)
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                content = self._extract_content(raw_response)
                tokens = self._extract_tokens(raw_response)

                structured = None
                if request.response_model:
                    structured = self._parse_structured(content, request.response_model)

                return ModelResponse(
                    content=content,
                    structured_output=structured,
                    tokens_used=tokens,
                    latency_ms=latency_ms,
                    model=request.metadata.get("model_name", ""),
                    provider=self.provider_type,
                    raw_response=raw_response,
                )
            except Exception as e:
                logger.error(f"{self.provider_type.value} completion failed: {e}")
                raise ModelProviderError(str(e), self.provider_type, request.metadata.get("model_name", ""), e)

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        async with self.circuit_breaker:
            async for chunk in self._stream_raw(request):
                yield chunk

    def _extract_content(self, response: dict) -> str:
        raise NotImplementedError

    def _extract_tokens(self, response: dict) -> int:
        return response.get("usage", {}).get("total_tokens", 0)

    def _parse_structured(self, content: str, model: type[T]) -> T:
        try:
            return model.model_validate_json(content)
        except ValidationError as e:
            logger.warning(f"Failed to parse structured output: {e}")
            try:
                import json
                return model.model_validate(json.loads(content))
            except Exception:
                raise ModelProviderError(f"Structured output parsing failed: {e}", self.provider_type, "")


class OllamaClient(BaseModelClient):
    @property
    def provider_type(self) -> ModelProviderType:
        return ModelProviderType.OLLAMA

    async def _complete_raw(self, request: ModelRequest) -> dict:
        client = await self.get_client()
        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "deepseek-r1")),
            "prompt": request.prompt,
            "system": request.system_prompt or None,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": False,
            "format": "json" if request.response_model else None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        response = await client.post(
            f"{self.config['base_url']}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def _stream_raw(self, request: ModelRequest) -> AsyncIterator[str]:
        client = await self.get_client()
        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "deepseek-r1")),
            "prompt": request.prompt,
            "system": request.system_prompt or None,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": True,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        async with client.stream("POST", f"{self.config['base_url']}/api/generate", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue

    def _extract_content(self, response: dict) -> str:
        return response.get("response", "")

    def _extract_tokens(self, response: dict) -> int:
        return response.get("eval_count", 0) + response.get("prompt_eval_count", 0)


class OpenAICompatibleClient(BaseModelClient):
    def __init__(self, config: dict, provider_type: ModelProviderType):
        super().__init__(config)
        self._provider_type = provider_type

    @property
    def provider_type(self) -> ModelProviderType:
        return self._provider_type

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
        }

    def _get_base_url(self) -> str:
        return self.config.get("base_url", "https://api.openai.com/v1")

    async def _complete_raw(self, request: ModelRequest) -> dict:
        client = await self.get_client()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model")),
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": False,
        }
        if request.response_model:
            payload["response_format"] = {"type": "json_object"}

        payload = {k: v for k, v in payload.items() if v is not None}

        response = await client.post(
            f"{self._get_base_url()}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def _stream_raw(self, request: ModelRequest) -> AsyncIterator[str]:
        client = await self.get_client()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model")),
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": True,
        }

        async with client.stream(
            "POST",
            f"{self._get_base_url()}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    def _extract_content(self, response: dict) -> str:
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def _extract_tokens(self, response: dict) -> int:
        return response.get("usage", {}).get("total_tokens", 0)


class OpenAIClient(OpenAICompatibleClient):
    def __init__(self, config: dict):
        super().__init__(config, ModelProviderType.OPENAI)


class GroqClient(OpenAICompatibleClient):
    def __init__(self, config: dict):
        super().__init__(config, ModelProviderType.GROQ)

    def _get_base_url(self) -> str:
        return self.config.get("base_url", "https://api.groq.com/openai/v1")


class GeminiClient(OpenAICompatibleClient):
    def __init__(self, config: dict):
        super().__init__(config, ModelProviderType.GEMINI)

    def _get_base_url(self) -> str:
        return self.config.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai")

    async def _complete_raw(self, request: ModelRequest) -> dict:
        client = await self.get_client()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "gemini-3.6-flash")),
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": False,
        }
        if request.response_model:
            payload["response_format"] = {"type": "json_object"}

        payload = {k: v for k, v in payload.items() if v is not None}

        response = await client.post(
            f"{self._get_base_url()}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class MoonshotClient(OpenAICompatibleClient):
    def __init__(self, config: dict):
        super().__init__(config, ModelProviderType.MOONSHOT)

    def _get_base_url(self) -> str:
        return self.config.get("base_url", "https://api.moonshot.ai/v1")

    async def _complete_raw(self, request: ModelRequest) -> dict:
        client = await self.get_client()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "kimi-k2.7-code")),
            "messages": messages,
            "temperature": request.temperature,
            "max_completion_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stop": request.stop_sequences or None,
            "stream": False,
            "reasoning_effort": "max",
        }
        if request.response_model:
            payload["response_format"] = {"type": "json_object"}

        payload = {k: v for k, v in payload.items() if v is not None}

        response = await client.post(
            f"{self._get_base_url()}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class AnthropicClient(BaseModelClient):
    @property
    def provider_type(self) -> ModelProviderType:
        return ModelProviderType.ANTHROPIC

    def _get_headers(self) -> dict:
        return {
            "x-api-key": self.config["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def _complete_raw(self, request: ModelRequest) -> dict:
        client = await self.get_client()
        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "claude-3-opus-20240229")),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
        }
        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def _stream_raw(self, request: ModelRequest) -> AsyncIterator[str]:
        client = await self.get_client()
        payload = {
            "model": request.metadata.get("model_name", self.config.get("default_model", "claude-3-opus-20240229")),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": True,
        }
        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=self._get_headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue

    def _extract_content(self, response: dict) -> str:
        content = response.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return ""

    def _extract_tokens(self, response: dict) -> int:
        return response.get("usage", {}).get("input_tokens", 0) + response.get("usage", {}).get("output_tokens", 0)


class CodeExecutorClient(BaseModelClient):
    @property
    def provider_type(self) -> ModelProviderType:
        return ModelProviderType.CODE_EXECUTOR

    async def _complete_raw(self, request: ModelRequest) -> dict:
        code = request.prompt
        language = request.metadata.get("language", "python")
        timeout = request.metadata.get("timeout", self.config.get("default_timeout", 30))

        if language == "python":
            result = await self._execute_python(code, timeout)
        else:
            result = {"error": f"Unsupported language: {language}", "output": "", "exit_code": -1}

        return {
            "output": result.get("output", ""),
            "error": result.get("error", ""),
            "exit_code": result.get("exit_code", 0),
            "execution_time_ms": result.get("execution_time_ms", 0),
        }

    async def _stream_raw(self, request: ModelRequest) -> AsyncIterator[str]:
        result = await self._complete_raw(request)
        if result.get("output"):
            yield result["output"]
        if result.get("error"):
            yield f"\n[ERROR] {result['error']}"

    async def _execute_python(self, code: str, timeout: int) -> dict:
        import os
        import tempfile

        start = time.perf_counter()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "python", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                exit_code = proc.returncode
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "output": "",
                    "error": f"Execution timeout after {timeout}s",
                    "exit_code": -1,
                    "execution_time_ms": int((time.perf_counter() - start) * 1000),
                }
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            return {
                "output": stdout.decode("utf-8", errors="replace"),
                "error": stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "execution_time_ms": int((time.perf_counter() - start) * 1000),
            }
        except Exception as e:
            return {
                "output": "",
                "error": str(e),
                "exit_code": -1,
                "execution_time_ms": int((time.perf_counter() - start) * 1000),
            }

    def _extract_content(self, response: dict) -> str:
        output = response.get("output", "")
        error = response.get("error", "")
        if error:
            return f"{output}\n[ERROR] {error}"
        return output

    def _extract_tokens(self, response: dict) -> int:
        return 0


class ModelProvider:
    def __init__(self, settings):
        self.settings = settings
        self._clients: dict[ModelProviderType, BaseModelClient] = {}
        self._fallback_chains: dict[str, list[ModelSpec]] = {}
        self._initialize_clients()

    def _initialize_clients(self):
        ollama_config = {
            "base_url": self.settings.ollama_base_url,
            "default_model": self.settings.ollama_default_model,
            "timeout": self.settings.ollama_timeout,
            "max_connections": self.settings.ollama_max_connections,
        }
        self._clients[ModelProviderType.OLLAMA] = OllamaClient(ollama_config)

        if self.settings.openai_api_key:
            self._clients[ModelProviderType.OPENAI] = OpenAIClient({
                "api_key": self.settings.openai_api_key,
                "base_url": self.settings.openai_base_url,
                "default_model": self.settings.openai_default_model,
            })

        if self.settings.groq_api_key:
            self._clients[ModelProviderType.GROQ] = GroqClient({
                "api_key": self.settings.groq_api_key,
                "default_model": self.settings.groq_default_model,
            })

        if self.settings.anthropic_api_key:
            self._clients[ModelProviderType.ANTHROPIC] = AnthropicClient({
                "api_key": self.settings.anthropic_api_key,
                "default_model": self.settings.anthropic_default_model,
            })

        if self.settings.gemini_api_key:
            self._clients[ModelProviderType.GEMINI] = GeminiClient({
                "api_key": self.settings.gemini_api_key,
                "base_url": self.settings.gemini_base_url,
                "default_model": self.settings.gemini_default_model,
            })

        if self.settings.moonshot_api_key:
            self._clients[ModelProviderType.MOONSHOT] = MoonshotClient({
                "api_key": self.settings.moonshot_api_key,
                "base_url": self.settings.moonshot_base_url,
                "default_model": self.settings.moonshot_default_model,
            })

        self._clients[ModelProviderType.CODE_EXECUTOR] = CodeExecutorClient({
            "default_timeout": self.settings.code_executor_timeout,
        })

        gemini_chain: list[ModelSpec] = []
        if self.settings.gemini_api_key:
            gemini_chain.append(ModelSpec(
                provider=ModelProviderType.GEMINI,
                model_name=self.settings.gemini_default_model,
                priority=10,
            ))
        if self.settings.moonshot_api_key:
            gemini_chain.append(ModelSpec(
                provider=ModelProviderType.MOONSHOT,
                model_name=self.settings.moonshot_default_model,
                priority=20,
            ))
        if gemini_chain:
            self.register_fallback_chain("gemini", gemini_chain)

    def get_client(self, provider: ModelProviderType) -> BaseModelClient | None:
        return self._clients.get(provider)

    def register_fallback_chain(self, name: str, specs: list[ModelSpec]):
        self._fallback_chains[name] = sorted(specs, key=lambda s: s.priority)

    async def complete(
        self,
        model_spec: str | ModelSpec,
        request: ModelRequest,
    ) -> ModelResponse:
        if isinstance(model_spec, str):
            model_spec = ModelSpec.parse(model_spec)

        request.metadata["model_name"] = model_spec.model_name
        client = self._clients.get(model_spec.provider)
        if not client:
            raise ModelProviderError(f"Provider {model_spec.provider} not configured", model_spec.provider, model_spec.model_name)

        return await client.complete(request)

    async def complete_with_fallback(
        self,
        chain_name: str,
        request: ModelRequest,
    ) -> ModelResponse:
        chain = self._fallback_chains.get(chain_name)
        if not chain:
            raise ValueError(f"Fallback chain '{chain_name}' not registered")

        last_error = None
        for spec in chain:
            try:
                logger.info(f"Trying model: {spec}")
                request.metadata["model_name"] = spec.model_name
                client = self._clients.get(spec.provider)
                if not client:
                    logger.warning(f"Provider {spec.provider} not available, skipping")
                    continue

                return await client.complete(request)
            except CircuitBreakerOpen:
                logger.warning(f"Circuit breaker open for {spec}, skipping")
                last_error = ModelProviderError("Circuit breaker open", spec.provider, spec.model_name)
            except Exception as e:
                logger.warning(f"Model {spec} failed: {e}")
                last_error = e
                continue

        raise ModelProviderError(
            f"All models in fallback chain '{chain_name}' failed",
            ModelProviderType.OLLAMA,
            "",
            last_error,
        )

    async def stream(
        self,
        model_spec: str | ModelSpec,
        request: ModelRequest,
    ) -> AsyncIterator[str]:
        if isinstance(model_spec, str):
            model_spec = ModelSpec.parse(model_spec)

        request.metadata["model_name"] = model_spec.model_name
        client = self._clients.get(model_spec.provider)
        if not client:
            raise ModelProviderError(f"Provider {model_spec.provider} not configured", model_spec.provider, model_spec.model_name)

        async for chunk in client.stream(request):
            yield chunk

    async def close(self):
        for client in self._clients.values():
            await client.close()

    @asynccontextmanager
    async def session(self):
        try:
            yield self
        finally:
            await self.close()
