"""Generator controls panel — toggles and sliders for music generation."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from livemind.gui import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_DARK,
    BG_DARKEST,
    BG_INPUT,
    BORDER,
    CORNER_RADIUS,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    PADDING,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


class GeneratorPanel(ctk.CTkFrame):
    """Panel with toggles and sliders controlling music generation."""

    def __init__(self, parent: Any, **kwargs: Any) -> None:
        super().__init__(parent, fg_color=BG_DARKEST, corner_radius=0, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Scrollable container ──
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARKEST, corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=TEXT_DIM,
        )
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        container = self._scroll
        row = 0

        # ── Title ──
        title = ctk.CTkLabel(
            container, text="🎛  Generator Controls",
            font=("SF Pro Display", FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        )
        title.grid(row=row, column=0, padx=PADDING, pady=(PADDING, 4), sticky="w")
        row += 1

        subtitle = ctk.CTkLabel(
            container, text="Shape what LiveMind generates",
            font=("SF Pro Display", FONT_SIZE_SM),
            text_color=TEXT_DIM,
        )
        subtitle.grid(row=row, column=0, padx=PADDING, pady=(0, PADDING), sticky="w")
        row += 1

        # ── Mode Toggle: LLM vs Preset ──
        row = self._add_section(container, row, "Generation Mode")
        self.mode_var = ctk.StringVar(value="preset")
        mode_frame = ctk.CTkFrame(container, fg_color="transparent")
        mode_frame.grid(row=row, column=0, padx=PADDING, pady=(0, 12), sticky="ew")
        ctk.CTkRadioButton(
            mode_frame, text="Presets (reliable)", variable=self.mode_var,
            value="preset", font=("SF Pro Display", FONT_SIZE_SM),
            text_color=TEXT_SECONDARY, fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(
            mode_frame, text="LLM (creative)", variable=self.mode_var,
            value="llm", font=("SF Pro Display", FONT_SIZE_SM),
            text_color=TEXT_SECONDARY, fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).pack(side="left")
        row += 1

        # ── Intensity Slider ──
        row = self._add_section(container, row, "🔥 Intensity / Degen Level")
        self.intensity_var = ctk.DoubleVar(value=0.5)
        intensity_frame = ctk.CTkFrame(container, fg_color="transparent")
        intensity_frame.grid(row=row, column=0, padx=PADDING, pady=(0, 4), sticky="ew")
        intensity_frame.grid_columnconfigure(0, weight=1)
        self._intensity_slider = ctk.CTkSlider(
            intensity_frame, from_=0, to=1, variable=self.intensity_var,
            fg_color=BG_INPUT, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._on_intensity_change,
        )
        self._intensity_slider.grid(row=0, column=0, sticky="ew")
        self._intensity_label = ctk.CTkLabel(
            intensity_frame, text="Medium",
            font=("SF Pro Display", FONT_SIZE_SM), text_color=WARNING,
        )
        self._intensity_label.grid(row=0, column=1, padx=(8, 0))
        row += 1

        # ── Element Toggles ──
        row = self._add_section(container, row, "🎵 Elements to Include")

        self.toggle_drums = ctk.BooleanVar(value=True)
        self.toggle_bass = ctk.BooleanVar(value=True)
        self.toggle_chords = ctk.BooleanVar(value=True)
        self.toggle_melody = ctk.BooleanVar(value=False)
        self.toggle_pad = ctk.BooleanVar(value=True)
        self.toggle_fx = ctk.BooleanVar(value=False)

        toggles = [
            ("🥁 Drums / Beats", self.toggle_drums),
            ("🎸 Bass", self.toggle_bass),
            ("🎹 Chords", self.toggle_chords),
            ("🎶 Melody / Lead", self.toggle_melody),
            ("🌫  Pad / Atmosphere", self.toggle_pad),
            ("✨ FX / Risers", self.toggle_fx),
        ]
        for label, var in toggles:
            row = self._add_toggle(container, row, label, var)

        # ── Structure Toggles ──
        row = self._add_section(container, row, "🏗  Structure")

        self.toggle_drops = ctk.BooleanVar(value=True)
        self.toggle_buildup = ctk.BooleanVar(value=False)
        self.toggle_breakdown = ctk.BooleanVar(value=False)

        structure_toggles = [
            ("💥 Drops", self.toggle_drops),
            ("📈 Buildup / Riser", self.toggle_buildup),
            ("🌊 Breakdown", self.toggle_breakdown),
        ]
        for label, var in structure_toggles:
            row = self._add_toggle(container, row, label, var)

        # ── Clip Length ──
        row = self._add_section(container, row, "📏 Clip Length (bars)")
        self.bars_var = ctk.IntVar(value=4)
        bars_frame = ctk.CTkFrame(container, fg_color="transparent")
        bars_frame.grid(row=row, column=0, padx=PADDING, pady=(0, 12), sticky="ew")
        for val in [2, 4, 8, 16]:
            ctk.CTkRadioButton(
                bars_frame, text=str(val), variable=self.bars_var,
                value=val, font=("SF Pro Display", FONT_SIZE_SM),
                text_color=TEXT_SECONDARY, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                width=50,
            ).pack(side="left", padx=(0, 12))
        row += 1

        # ── Record to Arrangement ──
        row = self._add_section(container, row, "🎬 Output")
        self.toggle_arrangement = ctk.BooleanVar(value=True)
        row = self._add_toggle(container, row, "Record to Arrangement View", self.toggle_arrangement)

    def _add_section(self, container: Any, row: int, title: str) -> int:
        label = ctk.CTkLabel(
            container, text=title,
            font=("SF Pro Display", FONT_SIZE_MD, "bold"),
            text_color=TEXT_PRIMARY,
        )
        label.grid(row=row, column=0, padx=PADDING, pady=(16, 8), sticky="w")
        return row + 1

    def _add_toggle(self, container: Any, row: int, label: str, variable: ctk.BooleanVar) -> int:
        switch = ctk.CTkSwitch(
            container, text=label, variable=variable,
            font=("SF Pro Display", FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
            fg_color=BG_INPUT, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color=ACCENT_HOVER,
        )
        switch.grid(row=row, column=0, padx=PADDING + 8, pady=3, sticky="w")
        return row + 1

    def _on_intensity_change(self, value: float) -> None:
        if value < 0.25:
            label = "Chill"
        elif value < 0.5:
            label = "Medium"
        elif value < 0.75:
            label = "Hard"
        else:
            label = "DEGEN 🔥"
        self._intensity_label.configure(text=label)

    def get_settings(self) -> dict[str, Any]:
        """Return all generator settings as a dict."""
        return {
            "mode": self.mode_var.get(),
            "intensity": self.intensity_var.get(),
            "bars": self.bars_var.get(),
            "elements": {
                "drums": self.toggle_drums.get(),
                "bass": self.toggle_bass.get(),
                "chords": self.toggle_chords.get(),
                "melody": self.toggle_melody.get(),
                "pad": self.toggle_pad.get(),
                "fx": self.toggle_fx.get(),
            },
            "structure": {
                "drops": self.toggle_drops.get(),
                "buildup": self.toggle_buildup.get(),
                "breakdown": self.toggle_breakdown.get(),
            },
            "record_to_arrangement": self.toggle_arrangement.get(),
        }
