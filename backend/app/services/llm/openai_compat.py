"""OpenAI-compatible and Azure OpenAI Chat Completions providers (plain httpx, no SDK dependency)."""

from __future__ import annotations

import time

import httpx

from app.services.llm.base import SYSTEM_PROMPT, LLMError, LLMProvider, LLMResponse, build_user_message


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str = "", timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def _request(self) -> tuple[str, dict[str, str]]:
        return f"{self.base_url}/chat/completions", {"Authorization": f"Bearer {self.api_key}"}

    def generate(self, prompt: str, context: list[str]) -> LLMResponse:
        url, headers = self._request()
        body = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(prompt, context)},
            ],
        }
        t0 = time.perf_counter()
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"{self.name} provider request failed: {type(exc).__name__}") from exc
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return LLMResponse(
            text=(choice.get("message") or {}).get("content", "") or "",
            provider=self.name,
            model=data.get("model", self.model),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop") or "stop",
        )


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Azure OpenAI: OPENAI_BASE_URL is the resource endpoint, OPENAI_MODEL the deployment name."""

    name = "azure"

    def __init__(self, api_key: str, model: str, base_url: str, api_version: str, timeout: float = 30.0) -> None:
        super().__init__(api_key, model, base_url, timeout)
        self.api_version = api_version

    def _request(self) -> tuple[str, dict[str, str]]:
        url = f"{self.base_url}/openai/deployments/{self.model}/chat/completions?api-version={self.api_version}"
        return url, {"api-key": self.api_key}
