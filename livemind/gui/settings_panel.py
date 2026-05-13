"""Settings panel — LLM provider, Ableton connection, preferences."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from livemind.gui import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_DARKEST,
    BG_INPUT,
    BORDER,
    CORNER_RADIUS,
    ERROR,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    PADDING,
    SUCCESS,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsPanel(ctk.CTkScrollableFrame):
    """Configuration panel with save callback."""

    def __init__(self, master: Any, config: dict[str, Any], on_save: Callable[[dict[str, Any]], None], **kwargs: Any) -> None:
        super().__init__(master, fg_color=BG_DARKEST, corner_radius=0, **kwargs)
        self.config = dict(config)
        self.on_save = on_save
        self.grid_columnconfigure(0, weight=1)
        self._entries: dict[str, Any] = {}
        row = 0

        # ── Title ───────────────────────────────────────────────────────
        title = ctk.CTkLabel(self, text="Settings", font=("SF Pro Display", FONT_SIZE_XL, "bold"), text_color=TEXT_PRIMARY)
        title.grid(row=row, column=0, sticky="w", padx=PADDING, pady=(PADDING, 24))
        row += 1

        # ── LLM Provider ───────────────────────────────────────────────
        row = self._section_header("LLM Provider", row)
        row = self._add_dropdown("llm_provider", "Provider", ["ollama", "cloudflare"], row)
        row = self._add_entry("ollama_url", "Ollama URL", row)
        row = self._add_entry("ollama_model", "Ollama Model", row)
        row = self._add_entry("cloudflare_account_id", "Cloudflare Account ID", row)
        row = self._add_entry("cloudflare_api_token", "Cloudflare API Token", row, show="•")
        row = self._add_entry("cloudflare_model", "Cloudflare Model", row)
        row = self._add_slider("temperature", "Temperature", 0.0, 2.0, row)
        row = self._add_entry("max_tokens", "Max Tokens", row)

        # ── Ableton Connection ──────────────────────────────────────────
        row = self._section_header("Ableton Connection", row)
        row = self._add_entry("ableton_host", "Ableton Host", row)
        row = self._add_entry("ableton_send_port", "Send Port (to Ableton)", row)
        row = self._add_entry("ableton_recv_port", "Receive Port (from Ableton)", row)

        # ── MIDI Output ─────────────────────────────────────────────────
        row = self._section_header("MIDI Output", row)
        row = self._add_entry("midi_output_dir", "MIDI Output Directory", row)

        # ── Safety ──────────────────────────────────────────────────────
        row = self._section_header("Safety", row)
        row = self._add_checkbox("confirm_destructive", "Confirm destructive actions", row)

        # ── Save button ─────────────────────────────────────────────────
        save_btn = ctk.CTkButton(
            self, text="Save Settings", fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("SF Pro Display", FONT_SIZE_MD, "bold"), height=44, corner_radius=CORNER_RADIUS,
            command=self._save,
        )
        save_btn.grid(row=row, column=0, sticky="ew", padx=PADDING, pady=(24, PADDING))

    def _section_header(self, text: str, row: int) -> int:
        label = ctk.CTkLabel(self, text=text, font=("SF Pro Display", 16, "bold"), text_color=TEXT_PRIMARY)
        label.grid(row=row, column=0, sticky="w", padx=PADDING, pady=(20, 8))
        return row + 1

    def _add_entry(self, key: str, label: str, row: int, show: str = "") -> int:
        lbl = ctk.CTkLabel(self, text=label, font=("SF Pro Display", FONT_SIZE_SM), text_color=TEXT_SECONDARY)
        lbl.grid(row=row, column=0, sticky="w", padx=PADDING, pady=(4, 0))
        entry = ctk.CTkEntry(
            self, fg_color=BG_INPUT, text_color=TEXT_PRIMARY,
            border_color=BORDER, corner_radius=8, height=36,
            font=("SF Pro Display", FONT_SIZE_SM),
        )
        if show:
            entry.configure(show=show)
        entry.insert(0, str(self.config.get(key, "")))
        entry.grid(row=row + 1, column=0, sticky="ew", padx=PADDING, pady=(2, 8))
        self._entries[key] = entry
        return row + 2

    def _add_dropdown(self, key: str, label: str, options: list[str], row: int) -> int:
        lbl = ctk.CTkLabel(self, text=label, font=("SF Pro Display", FONT_SIZE_SM), text_color=TEXT_SECONDARY)
        lbl.grid(row=row, column=0, sticky="w", padx=PADDING, pady=(4, 0))
        var = ctk.StringVar(value=str(self.config.get(key, options[0])))
        dropdown = ctk.CTkOptionMenu(
            self, values=options, variable=var,
            fg_color=BG_INPUT, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            font=("SF Pro Display", FONT_SIZE_SM), corner_radius=8, height=36,
        )
        dropdown.grid(row=row + 1, column=0, sticky="ew", padx=PADDING, pady=(2, 8))
        self._entries[key] = var
        return row + 2

    def _add_slider(self, key: str, label: str, from_: float, to: float, row: int) -> int:
        current = float(self.config.get(key, (from_ + to) / 2))
        lbl = ctk.CTkLabel(self, text=f"{label}: {current:.2f}", font=("SF Pro Display", FONT_SIZE_SM), text_color=TEXT_SECONDARY)
        lbl.grid(row=row, column=0, sticky="w", padx=PADDING, pady=(4, 0))
        slider = ctk.CTkSlider(
            self, from_=from_, to=to,
            fg_color=BORDER, progress_color=ACCENT, button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
        )
        slider.set(current)
        slider.configure(command=lambda v, l=lbl, lb=label: l.configure(text=f"{lb}: {v:.2f}"))
        slider.grid(row=row + 1, column=0, sticky="ew", padx=PADDING, pady=(2, 8))
        self._entries[key] = slider
        return row + 2

    def _add_checkbox(self, key: str, label: str, row: int) -> int:
        var = ctk.BooleanVar(value=bool(self.config.get(key, True)))
        cb = ctk.CTkCheckBox(
            self, text=label, variable=var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=("SF Pro Display", FONT_SIZE_SM), text_color=TEXT_PRIMARY,
        )
        cb.grid(row=row, column=0, sticky="w", padx=PADDING, pady=8)
        self._entries[key] = var
        return row + 1

    def _save(self) -> None:
        for key, widget in self._entries.items():
            if isinstance(widget, ctk.CTkEntry):
                val = widget.get()
                # Try to preserve numeric types.
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                self.config[key] = val
            elif isinstance(widget, (ctk.StringVar, ctk.BooleanVar)):
                self.config[key] = widget.get()
            elif isinstance(widget, ctk.CTkSlider):
                self.config[key] = round(widget.get(), 2)
        self.on_save(self.config)
