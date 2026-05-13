"""Parse LLM output into executable Ableton commands and MIDI generation tasks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from livemind.ableton import AbletonBridge
from livemind.midi.generator import (
    generate_chord_progression_midi,
    generate_drum_pattern_midi,
    generate_melody_midi,
)


@dataclass
class CommandResult:
    action: str
    success: bool
    detail: str = ""
    midi_path: Path | None = None


def extract_commands(llm_output: str) -> list[dict[str, Any]]:
    """Extract command JSON blocks from LLM response text.

    Looks for ```commands ... ``` or ```json ... ``` fenced blocks containing
    a JSON array of command objects.
    """
    patterns = [
        r"```commands\s*\n(.*?)```",
        r"```json\s*\n(.*?)```",
    ]
    for pattern in patterns:
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            raw = match.group(1).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "commands" in parsed:
                    return parsed["commands"]
                return [parsed]
            except json.JSONDecodeError:
                continue
    return []


def strip_commands(llm_output: str) -> str:
    """Return the LLM response with command blocks removed (just the conversational text)."""
    cleaned = re.sub(r"```(?:commands|json)\s*\n.*?```", "", llm_output, flags=re.DOTALL)
    return cleaned.strip()


def execute_commands(
    commands: list[dict[str, Any]],
    bridge: AbletonBridge,
) -> list[CommandResult]:
    """Execute a list of parsed commands against Ableton and/or MIDI generators."""
    results: list[CommandResult] = []
    for cmd in commands:
        action = cmd.get("action", "")
        try:
            result = _dispatch(action, cmd, bridge)
            results.append(result)
        except Exception as exc:
            results.append(CommandResult(action=action, success=False, detail=str(exc)))
    return results


def _dispatch(action: str, cmd: dict[str, Any], bridge: AbletonBridge) -> CommandResult:
    # ── MIDI file generation (local, no Ableton needed) ─────────────
    if action == "generate_midi_file":
        return _handle_midi_generation(cmd)

    # ── Ableton bridge commands ─────────────────────────────────────
    resp = bridge.send(cmd)
    if resp is None:
        return CommandResult(action=action, success=False, detail="No response from Ableton (is the Remote Script loaded?)")
    if resp.get("error"):
        return CommandResult(action=action, success=False, detail=resp["error"])
    return CommandResult(action=action, success=True, detail=resp.get("detail", "OK"))


def _handle_midi_generation(cmd: dict[str, Any]) -> CommandResult:
    gen_type = cmd.get("type", "")
    bpm = float(cmd.get("bpm", 120))
    filename = cmd.get("filename")

    if gen_type == "chord_progression":
        path, _ = generate_chord_progression_midi(
            root=cmd.get("root", "C"),
            scale_type=cmd.get("scale", "minor"),
            degrees=cmd.get("degrees", [1, 4, 5, 1]),
            octave=int(cmd.get("octave", 3)),
            bpm=bpm,
            filename=filename,
        )
        return CommandResult(action="generate_midi_file", success=True, detail=f"Chord progression saved", midi_path=path)

    if gen_type == "drum_pattern":
        path, _ = generate_drum_pattern_midi(
            pattern=cmd.get("pattern", {"kick": [0, 2], "snare": [1, 3]}),
            bpm=bpm,
            filename=filename,
        )
        return CommandResult(action="generate_midi_file", success=True, detail="Drum pattern saved", midi_path=path)

    if gen_type == "melody":
        path, _ = generate_melody_midi(
            note_data=cmd.get("notes", []),
            bpm=bpm,
            filename=filename,
        )
        return CommandResult(action="generate_midi_file", success=True, detail="Melody saved", midi_path=path)

    return CommandResult(action="generate_midi_file", success=False, detail=f"Unknown MIDI type: {gen_type}")
