"""Ableton-inspired dark theme for the CustomTkinter GUI."""

from __future__ import annotations

# ── Color palette (matches Ableton Live 12 dark theme) ──────────────────────

BG_DARKEST = "#1a1a2e"      # Main background
BG_DARK = "#16213e"          # Sidebar / panels
BG_CARD = "#1e293b"          # Cards / input fields
BG_INPUT = "#0f172a"         # Text input backgrounds
BORDER = "#334155"           # Subtle borders
TEXT_PRIMARY = "#f1f5f9"     # Main text
TEXT_SECONDARY = "#94a3b8"   # Muted text
TEXT_DIM = "#64748b"         # Very muted
ACCENT = "#7c3aed"           # Purple accent (buttons, highlights)
ACCENT_HOVER = "#6d28d9"    # Hover state
ACCENT_LIGHT = "#a78bfa"    # Links, active states
SUCCESS = "#22c55e"          # Connected, success
WARNING = "#f59e0b"          # Caution
ERROR = "#ef4444"            # Error, disconnect
SCROLLBAR = "#475569"        # Scrollbar thumb

# ── Font configuration ──────────────────────────────────────────────────────

FONT_FAMILY = "SF Pro Display"
FONT_MONO = "SF Mono"
FONT_FALLBACK = ("Helvetica Neue", "Helvetica", "Arial")
FONT_MONO_FALLBACK = ("Menlo", "Monaco", "Courier New")

FONT_SIZE_SM = 12
FONT_SIZE_MD = 14
FONT_SIZE_LG = 16
FONT_SIZE_XL = 20
FONT_SIZE_TITLE = 28

# ── Widget dimensions ──────────────────────────────────────────────────────

SIDEBAR_WIDTH = 280
PADDING = 16
CORNER_RADIUS = 12
BUTTON_HEIGHT = 40
INPUT_HEIGHT = 42


def configure_theme() -> None:
    """Apply the LiveMind theme to CustomTkinter."""
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
