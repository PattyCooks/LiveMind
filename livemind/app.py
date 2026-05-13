"""LiveMind application orchestrator — wires LLM, Ableton bridge, and GUI together."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from livemind.ableton import AbletonBridge
from livemind.ableton.commands import CommandResult, execute_commands, extract_commands, strip_commands
from livemind.config import load_config, save_config
from livemind.llm import LLMProvider, Message
from livemind.llm.prompts import SYSTEM_PROMPT


class LiveMindApp:
    """Main application: manages state, routes messages, executes commands."""

    def __init__(self) -> None:
        self.config = load_config()
        self.bridge = AbletonBridge(
            ableton_host=self.config.get("ableton_host", "127.0.0.1"),
            send_port=int(self.config.get("ableton_send_port", 11000)),
            recv_port=int(self.config.get("ableton_recv_port", 11001)),
        )
        self.provider: LLMProvider | None = None
        self.messages: list[Message] = [Message(role="system", content=SYSTEM_PROMPT)]
        self.window: Any = None  # Set after GUI init.

        self._init_provider()
        self.bridge.start()

    def _init_provider(self) -> None:
        provider_name = self.config.get("llm_provider", "ollama")
        if provider_name == "ollama":
            from livemind.llm.ollama_provider import OllamaProvider
            self.provider = OllamaProvider(
                base_url=self.config.get("ollama_url", "http://127.0.0.1:11434"),
                model=self.config.get("ollama_model", "llama3.1"),
            )
        elif provider_name == "cloudflare":
            from livemind.llm.cloudflare_provider import CloudflareProvider
            self.provider = CloudflareProvider(
                account_id=self.config.get("cloudflare_account_id", ""),
                api_token=self.config.get("cloudflare_api_token", ""),
                model=self.config.get("cloudflare_model", "@cf/meta/llama-3.1-70b-instruct"),
            )

    # ── Message handling ────────────────────────────────────────────────

    def handle_user_message(self, text: str) -> None:
        """Process a user message: send to LLM, parse commands, execute, update GUI."""
        if not self.window:
            return
        self.window.chat_panel.set_thinking(True)
        thread = threading.Thread(target=self._process_message, args=(text,), daemon=True)
        thread.start()

    def _process_message(self, text: str) -> None:
        self.messages.append(Message(role="user", content=text))

        # Append current Ableton state as context if connected.
        if self.bridge.connected:
            state = self.bridge.get_session_state()
            if state:
                context_msg = f"[Current Ableton state: {_summarize_state(state)}]"
                self.messages.append(Message(role="system", content=context_msg))

        if not self.provider:
            self._post_response("LLM provider not configured. Go to Settings to set up Ollama or Cloudflare.")
            return

        try:
            response = self.provider.generate(
                self.messages,
                temperature=self.config.get("temperature", 0.7),
                max_tokens=int(self.config.get("max_tokens", 2048)),
            )
            llm_text = response.content
        except Exception as exc:
            self._post_response(f"LLM error: {exc}")
            return

        self.messages.append(Message(role="assistant", content=llm_text))

        # Extract and execute commands.
        commands = extract_commands(llm_text)

        # If the user likely asked for an action but the LLM only gave text,
        # retry once with a nudge to produce commands.
        if not commands and _looks_like_action_request(text):
            nudge = Message(
                role="user",
                content="Now output the ```commands block with the JSON array to execute what you just described. Commands only, no explanation.",
            )
            try:
                retry = self.provider.generate(
                    self.messages + [nudge],
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=int(self.config.get("max_tokens", 2048)),
                )
                commands = extract_commands(retry.content)
                if commands:
                    llm_text += "\n" + strip_commands(retry.content)
            except Exception:
                pass

        display_text = strip_commands(llm_text)
        midi_paths: list[Path] = []

        if commands:
            results = execute_commands(commands, self.bridge)
            result_lines: list[str] = []
            for r in results:
                icon = "✅" if r.success else "❌"
                result_lines.append(f"{icon} {r.action}: {r.detail}")
                if r.midi_path:
                    midi_paths.append(r.midi_path)
            display_text += "\n\n" + "\n".join(result_lines)

        self._post_response(display_text, midi_paths)

    def _post_response(self, text: str, midi_paths: list[Path] | None = None) -> None:
        if self.window:
            self.window.after(0, self._add_response, text, midi_paths)

    def _add_response(self, text: str, midi_paths: list[Path] | None) -> None:
        self.window.chat_panel.add_message("assistant", text, midi_paths=midi_paths)
        self.window.chat_panel.set_thinking(False)

    # ── Settings ────────────────────────────────────────────────────────

    def save_settings(self, new_config: dict[str, Any]) -> None:
        self.config.update(new_config)
        save_config(self.config)
        self._init_provider()
        self.bridge.stop()
        self.bridge = AbletonBridge(
            ableton_host=self.config.get("ableton_host", "127.0.0.1"),
            send_port=int(self.config.get("ableton_send_port", 11000)),
            recv_port=int(self.config.get("ableton_recv_port", 11001)),
        )
        self.bridge.start()
        self._check_connections()

    # ── Connection checks ───────────────────────────────────────────────

    def _check_connections(self) -> None:
        def check() -> None:
            ableton_ok = self.bridge.ping()
            llm_ok = self.provider.health_check() if self.provider else False
            provider_name = self.config.get("llm_provider", "unknown")
            if self.window:
                self.window.after(0, self.window.set_ableton_status, ableton_ok)
                self.window.after(0, self.window.set_llm_status, llm_ok, provider_name)
        threading.Thread(target=check, daemon=True).start()

    # ── Lifecycle ───────────────────────────────────────────────────────

    def run(self) -> None:
        from livemind.gui.main_window import MainWindow
        self.window = MainWindow(
            config=self.config,
            on_send=self.handle_user_message,
            on_save_settings=self.save_settings,
        )
        self.window.after(500, self._check_connections)
        # Periodic connection check.
        def periodic_check() -> None:
            self._check_connections()
            if self.window:
                self.window.after(15000, periodic_check)
        self.window.after(15000, periodic_check)
        self.window.mainloop()
        self.bridge.stop()

    def shutdown(self) -> None:
        self.bridge.stop()


def _summarize_state(state: dict[str, Any]) -> str:
    """Create a compact text summary of Ableton session state for the LLM context."""
    parts = [f"Tempo: {state.get('tempo', '?')} BPM"]
    tracks = state.get("tracks", [])
    if tracks:
        names = [f"{t['index']}:{t['name']}" for t in tracks[:16]]
        parts.append(f"Tracks: {', '.join(names)}")
    return " | ".join(parts)


_ACTION_WORDS = {
    "create", "add", "make", "set", "change", "build", "setup", "start",
    "delete", "remove", "load", "arm", "mute", "solo", "play", "stop",
    "fire", "launch", "record", "generate", "tempo", "bpm", "track",
    "clip", "scene", "device", "project", "beat", "drum", "pattern",
}


def _looks_like_action_request(text: str) -> bool:
    """Heuristic: does this message look like it wants Ableton commands?"""
    words = set(text.lower().split())
    return len(words & _ACTION_WORDS) >= 2
