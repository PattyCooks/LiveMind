"""Ollama local LLM provider."""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from livemind.llm import LLMProvider, LLMResponse, Message


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:0.6b") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(base_url=self.base_url, timeout=300.0)

    def generate(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": False,
            "options": {},
        }
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        resp = self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "think": False,
            "options": {},
        }
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                import json
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break

    def list_models(self) -> list[str]:
        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except httpx.HTTPError:
            return []

    def health_check(self) -> bool:
        try:
            resp = self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
