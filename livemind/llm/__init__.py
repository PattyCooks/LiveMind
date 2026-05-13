"""Base LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for LLM backends (Ollama, Cloudflare, etc.)."""

    @abstractmethod
    def generate(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Send a chat completion request and return the full response."""

    @abstractmethod
    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        """Stream tokens from a chat completion request."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available model names."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable."""
