"""Persistent configuration stored at ~/.livemind/config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_HOME = Path.home() / ".livemind"
CONFIG_PATH = APP_HOME / "config.json"
MIDI_OUTPUT_DIR = APP_HOME / "midi"

DEFAULTS: dict[str, Any] = {
    "llm_provider": "ollama",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "llama3.1",
    "cloudflare_account_id": "",
    "cloudflare_api_token": "",
    "cloudflare_model": "@cf/meta/llama-3.1-70b-instruct",
    "ableton_host": "127.0.0.1",
    "ableton_send_port": 11000,
    "ableton_recv_port": 11001,
    "midi_output_dir": str(MIDI_OUTPUT_DIR),
    "temperature": 0.7,
    "max_tokens": 2048,
    "confirm_destructive": True,
    "theme": "dark",
}


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        merged = {**DEFAULTS, **data}
        return merged
    save_config(DEFAULTS, path)
    return dict(DEFAULTS)


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
