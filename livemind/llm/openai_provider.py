"""OpenAI provider (GPT-4o-mini, GPT-4o, etc.)."""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from livemind.llm import LLMProvider, LLMResponse, Message

OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
]


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = OPENAI_MODELS[0]) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        )

    def generate(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        model = kwargs.get("model", self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        resp = self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        model = kwargs.get("model", self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        import json

        with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk_str = line[6:]
                if chunk_str.strip() == "[DONE]":
                    break
                chunk = json.loads(chunk_str)
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    yield token

    def list_models(self) -> list[str]:
        return list(OPENAI_MODELS)

    def health_check(self) -> bool:
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
                timeout=15.0,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
