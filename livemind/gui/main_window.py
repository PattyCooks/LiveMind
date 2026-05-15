"""Main application window — sidebar + content panels."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from livemind.gui import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    BG_CARD,
    BG_DARK,
    BG_DARKEST,
    BORDER,
    CORNER_RADIUS,
    ERROR,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_TITLE,
    PADDING,
    SIDEBAR_WIDTH,
    SUCCESS,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    configure_theme,
)
from livemind.gui.chat_panel import ChatPanel
from livemind.gui.generator_panel import GeneratorPanel
from livemind.gui.settings_panel import SettingsPanel


class MainWindow(ctk.CTk):
    """LiveMind main application window."""

    def __init__(
        self,
        config: dict[str, Any],
        on_send: Callable[[str], None],
        on_save_settings: Callable[[dict[str, Any]], None],
    ) -> None:
        configure_theme()
        super().__init__()

        self.title("LiveMind — AI Assistant for Ableton Live 12")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARKEST)

        self.config_data = config
        self._on_send = on_send
        self._on_save_settings = on_save_settings

        # ── Layout: sidebar + main content ──────────────────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

    # ── Sidebar ─────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, fg_color=BG_DARK, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(5, weight=1)

        # Logo / title
        logo = ctk.CTkLabel(
            sidebar, text="⚡ LiveMind",
            font=("SF Pro Display", FONT_SIZE_TITLE, "bold"),
            text_color=TEXT_PRIMARY,
        )
        logo.grid(row=0, column=0, padx=PADDING, pady=(24, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            sidebar, text="AI for Ableton Live 12",
            font=("SF Pro Display", FONT_SIZE_SM),
            text_color=TEXT_DIM,
        )
        subtitle.grid(row=1, column=0, padx=PADDING, pady=(0, 24), sticky="w")

        # Navigation buttons
        self._nav_chat = ctk.CTkButton(
            sidebar, text="💬  Chat", anchor="w",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("SF Pro Display", FONT_SIZE_MD), height=40,
            corner_radius=CORNER_RADIUS,
            command=lambda: self._show_panel("chat"),
        )
        self._nav_chat.grid(row=2, column=0, padx=PADDING, pady=4, sticky="ew")

        self._nav_settings = ctk.CTkButton(
            sidebar, text="⚙️  Settings", anchor="w",
            fg_color="transparent", hover_color=BG_CARD,
            font=("SF Pro Display", FONT_SIZE_MD), height=40,
            corner_radius=CORNER_RADIUS,
            command=lambda: self._show_panel("settings"),
        )
        self._nav_settings.grid(row=3, column=0, padx=PADDING, pady=4, sticky="ew")

        self._nav_generator = ctk.CTkButton(
            sidebar, text="🎛  Generator", anchor="w",
            fg_color="transparent", hover_color=BG_CARD,
            font=("SF Pro Display", FONT_SIZE_MD), height=40,
            corner_radius=CORNER_RADIUS,
            command=lambda: self._show_panel("generator"),
        )
        self._nav_generator.grid(row=4, column=0, padx=PADDING, pady=4, sticky="ew")

        # Spacer
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.grid(row=5, column=0, sticky="ns")

        # Connection status
        self._status_frame = ctk.CTkFrame(sidebar, fg_color=BG_CARD, corner_radius=CORNER_RADIUS)
        self._status_frame.grid(row=6, column=0, padx=PADDING, pady=PADDING, sticky="ew")

        self._ableton_status = ctk.CTkLabel(
            self._status_frame, text="● Ableton: Disconnected",
            text_color=ERROR, font=("SF Pro Display", FONT_SIZE_SM),
        )
        self._ableton_status.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")

        self._llm_status = ctk.CTkLabel(
            self._status_frame, text="● LLM: Not checked",
            text_color=TEXT_DIM, font=("SF Pro Display", FONT_SIZE_SM),
        )
        self._llm_status.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    # ── Content panels ──────────────────────────────────────────────────

    def _build_content(self) -> None:
        self._content_frame = ctk.CTkFrame(self, fg_color=BG_DARKEST, corner_radius=0)
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.grid_rowconfigure(0, weight=1)
        self._content_frame.grid_columnconfigure(0, weight=1)

        self.chat_panel = ChatPanel(self._content_frame, on_send=self._on_send)
        self.settings_panel = SettingsPanel(
            self._content_frame, config=self.config_data, on_save=self._on_save_settings,
        )
        self.generator_panel = GeneratorPanel(self._content_frame)

        self._panels = {"chat": self.chat_panel, "settings": self.settings_panel, "generator": self.generator_panel}
        self._current_panel = "chat"
        self.chat_panel.grid(row=0, column=0, sticky="nsew")

    def _show_panel(self, name: str) -> None:
        if name == self._current_panel:
            return
        self._panels[self._current_panel].grid_forget()
        self._panels[name].grid(row=0, column=0, sticky="nsew")
        self._current_panel = name

        # Update nav button highlights.
        for key, btn in [("chat", self._nav_chat), ("settings", self._nav_settings), ("generator", self._nav_generator)]:
            if key == name:
                btn.configure(fg_color=ACCENT)
            else:
                btn.configure(fg_color="transparent")

    # ── Public API for the app orchestrator ─────────────────────────────

    def set_ableton_status(self, connected: bool) -> None:
        if connected:
            self._ableton_status.configure(text="● Ableton: Connected", text_color=SUCCESS)
        else:
            self._ableton_status.configure(text="● Ableton: Disconnected", text_color=ERROR)

    def set_llm_status(self, ok: bool, provider: str = "") -> None:
        if ok:
            self._llm_status.configure(text=f"● LLM: {provider} ready", text_color=SUCCESS)
        else:
            self._llm_status.configure(text=f"● LLM: Not available", text_color=ERROR)
