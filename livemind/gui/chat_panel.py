"""Chat panel — the main conversation interface."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

from livemind.gui import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    BG_CARD,
    BG_DARKEST,
    BG_INPUT,
    BORDER,
    CORNER_RADIUS,
    ERROR,
    FONT_MONO,
    FONT_MONO_FALLBACK,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    PADDING,
    SUCCESS,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ChatMessage(ctk.CTkFrame):
    """Single message bubble in the chat history."""

    def __init__(
        self,
        master: Any,
        role: str,
        content: str,
        midi_paths: list[Path] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=CORNER_RADIUS, fg_color=BG_CARD, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        is_user = role == "user"
        label_color = ACCENT_LIGHT if is_user else SUCCESS
        label_text = "You" if is_user else "LiveMind"

        header = ctk.CTkLabel(
            self, text=label_text, text_color=label_color,
            font=(FONT_MONO, FONT_SIZE_SM, "bold"), anchor="w",
        )
        header.grid(row=0, column=0, sticky="w", padx=PADDING, pady=(PADDING, 4))

        body = ctk.CTkTextbox(
            self, height=1, fg_color="transparent", text_color=TEXT_PRIMARY,
            font=("SF Pro Display", FONT_SIZE_MD), wrap="word", activate_scrollbars=False,
        )
        body.insert("1.0", content)
        body.configure(state="disabled")
        # Auto-size height based on content.
        lines = content.count("\n") + 1
        char_width = 80
        wrapped_lines = sum(max(1, len(line) // char_width + 1) for line in content.split("\n"))
        body.configure(height=max(30, wrapped_lines * 22))
        body.grid(row=1, column=0, sticky="ew", padx=PADDING, pady=(0, PADDING))

        if midi_paths:
            for p in midi_paths:
                midi_label = ctk.CTkLabel(
                    self, text=f"🎵 {p.name}", text_color=ACCENT_LIGHT,
                    font=(FONT_MONO, FONT_SIZE_SM), cursor="hand2",
                )
                midi_label.grid(row=2, column=0, sticky="w", padx=PADDING, pady=(0, 8))
                midi_label.bind("<Button-1>", lambda e, path=p: self._open_file(path))

    def _open_file(self, path: Path) -> None:
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])


class ChatPanel(ctk.CTkFrame):
    """Full chat panel with message history and input."""

    def __init__(self, master: Any, on_send: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(master, fg_color=BG_DARKEST, corner_radius=0, **kwargs)
        self.on_send = on_send
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Scrollable message history ──────────────────────────────────
        self.history = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARKEST, corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=TEXT_DIM,
        )
        self.history.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.history.grid_columnconfigure(0, weight=1)
        self._msg_count = 0

        # ── Welcome message ─────────────────────────────────────────────
        welcome = ctk.CTkLabel(
            self.history,
            text="Welcome to LiveMind\nYour AI assistant for Ableton Live 12",
            text_color=TEXT_SECONDARY,
            font=("SF Pro Display", 18),
            justify="center",
        )
        welcome.grid(row=0, column=0, pady=60)
        self._welcome = welcome

        # ── Input area ──────────────────────────────────────────────────
        input_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=CORNER_RADIUS)
        input_frame.grid(row=1, column=0, sticky="ew", padx=PADDING, pady=PADDING)
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(
            input_frame, height=60, fg_color=BG_INPUT, text_color=TEXT_PRIMARY,
            font=("SF Pro Display", FONT_SIZE_MD), corner_radius=CORNER_RADIUS,
            border_width=1, border_color=BORDER, wrap="word",
        )
        self.input_box.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)  # Allow shift+enter for newlines.

        self.send_btn = ctk.CTkButton(
            input_frame, text="Send", width=80, height=40,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("SF Pro Display", FONT_SIZE_MD, "bold"),
            command=self._send,
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 8), pady=8)

        # ── Hint ────────────────────────────────────────────────────────
        hint = ctk.CTkLabel(
            self, text="⌘+Enter to send • Shift+Enter for newline",
            text_color=TEXT_DIM, font=("SF Pro Display", 11),
        )
        hint.grid(row=2, column=0, sticky="w", padx=PADDING + 8, pady=(0, 8))

    def _on_enter(self, event: tk.Event) -> str:
        if event.state & 0x1:  # Shift held.
            return ""
        self._send()
        return "break"

    def _send(self) -> None:
        text = self.input_box.get("1.0", "end-1c").strip()
        if not text:
            return
        self.input_box.delete("1.0", "end")
        self.add_message("user", text)
        self.on_send(text)

    def add_message(self, role: str, content: str, midi_paths: list[Path] | None = None) -> None:
        if self._welcome:
            self._welcome.destroy()
            self._welcome = None
        self._msg_count += 1
        msg = ChatMessage(self.history, role=role, content=content, midi_paths=midi_paths)
        msg.grid(row=self._msg_count, column=0, sticky="ew", padx=8, pady=6)
        self.after(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        self.history._parent_canvas.yview_moveto(1.0)

    def set_thinking(self, thinking: bool) -> None:
        if thinking:
            self.send_btn.configure(state="disabled", text="...")
        else:
            self.send_btn.configure(state="normal", text="Send")
