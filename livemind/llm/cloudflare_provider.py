"""Cloudflare Workers AI provider (free tier)."""

from __future__ import annotations

from typing import Any, Iterator

import httpx

from livemind.llm import LLMProvider, LLMResponse, Message

CF_BASE = "https://api.cloudflare.com/client/v4/accounts"

# Free-tier models available on Workers AI.
CF_MODELS = [
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3-8b-instruct",
    "@cf/mistral/mistral-7b-instruct-v0.2",
    "@cf/google/gemma-7b-it",
    "@hf/thebloke/deepseek-coder-6.7b-instruct-awq",
]


class CloudflareProvider(LLMProvider):
    def __init__(self, account_id: str, api_token: str, model: str = CF_MODELS[0]) -> None:
        self.account_id = account_id
        self.model = model
        self._client = httpx.Client(
            base_url=f"{CF_BASE}/{account_id}/ai",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=120.0,
        )

    def generate(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        model = kwargs.get("model", self.model)
        payload: dict[str, Any] = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        resp = self._client.post(f"/run/{model}", json=payload)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", {})
        return LLMResponse(
            content=result.get("response", ""),
            model=model,
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        model = kwargs.get("model", self.model)
        payload: dict[str, Any] = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        with self._client.stream("POST", f"/run/{model}", json=payload) as resp:
            resp.raise_for_status()
            import json
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk_str = line[6:]
                if chunk_str.strip() == "[DONE]":
                    break
                chunk = json.loads(chunk_str)
                token = chunk.get("response", "")
                if token:
                    yield token

    def list_models(self) -> list[str]:
        return list(CF_MODELS)

    def health_check(self) -> bool:
        try:
            resp = self._client.post(
                f"/run/@cf/meta/llama-3.1-8b-instruct",
                json={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=15.0,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
