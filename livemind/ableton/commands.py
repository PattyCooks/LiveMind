"""Parse LLM output into executable Ableton commands and MIDI generation tasks."""

from __future__ import annotations

import json
import re
import time
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
    raw_response: dict[str, Any] | None = None  # Full response from Ableton.


def extract_commands(llm_output: str) -> list[dict[str, Any]]:
    """Extract command JSON blocks from LLM response text.

    Looks for ```commands ... ``` or ```json ... ``` fenced blocks containing
    a JSON array of command objects.  Also handles truncated (unclosed) blocks.
    """
    patterns = [
        r"```commands\s*\n(.*?)```",
        r"```json\s*\n(.*?)```",
        # Unclosed fenced block (model ran out of tokens).
        r"```commands\s*\n(.*)",
        r"```json\s*\n(.*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            raw = match.group(1).strip()
            # Strip // comments that LLMs sometimes inject into JSON.
            raw = re.sub(r'//[^\n]*', '', raw)
            # Strip trailing commas before ] or }.
            raw = re.sub(r',\s*([\]\}])', r'\1', raw)
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return _normalize_commands(parsed)
                if isinstance(parsed, dict) and "commands" in parsed:
                    return _normalize_commands(parsed["commands"])
                return _normalize_commands([parsed])
            except json.JSONDecodeError:
                # Truncated JSON — try to salvage complete objects.
                salvaged = _salvage_truncated_json(raw)
                if salvaged:
                    return _normalize_commands(salvaged)
                continue
    return []


def _salvage_truncated_json(raw: str) -> list[dict[str, Any]]:
    """Try to recover valid command objects from truncated JSON arrays."""
    # Find last complete object by looking for the last "},"  or "}" before truncation.
    # Strategy: keep removing trailing incomplete content until we get valid JSON.
    raw = raw.rstrip()
    # Try closing the array at successively earlier positions.
    for i in range(len(raw) - 1, 0, -1):
        if raw[i] == '}':
            attempt = raw[:i + 1] + ']'
            # Ensure it starts with [
            if not attempt.lstrip().startswith('['):
                attempt = '[' + attempt.lstrip()
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                continue
    return []


# Map invalid/hallucinated actions to the closest valid action.
_ACTION_ALIASES: dict[str, str] = {
    "create_track": "create_midi_track",
    "create_clip": "create_midi_clip",
    "create_aux_track": "create_return_track",
    "create_bus": "create_return_track",
    "create_mix_bus": "create_return_track",
    "create_group": "create_midi_track",
    "create_group_track": "create_midi_track",
    "rename_track": "set_track_name",
    "tempo": "set_tempo",
    "volume": "set_track_volume",
    "pan": "set_track_pan",
    "add_device": "load_device",
    "add_clip": "create_midi_clip",
    "set_bpm": "set_tempo",
    "mute": "mute_track",
    "solo": "solo_track",
    "arm": "arm_track",
    "add_track_to_group": "",
    "group_tracks": "",
    "move_track": "",
}


def _normalize_commands(commands: list[Any]) -> list[dict[str, Any]]:
    """Normalize command dicts: fix key aliases and map hallucinated actions."""
    result: list[dict[str, Any]] = []
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        # Accept common key aliases for the action field.
        if "action" not in cmd:
            for alias in ("command", "cmd", "type", "name"):
                if alias in cmd:
                    cmd["action"] = cmd.pop(alias)
                    break
        action = cmd.get("action", "")
        # Map hallucinated actions to valid ones.
        if action in _ACTION_ALIASES:
            cmd["action"] = _ACTION_ALIASES[action]
        # Skip entries with no recognizable action.
        if cmd.get("action"):
            result.append(cmd)
    return result


def strip_commands(llm_output: str) -> str:
    """Return the LLM response with command blocks removed (just the conversational text)."""
    cleaned = re.sub(r"```(?:commands|json)\s*\n.*?```", "", llm_output, flags=re.DOTALL)
    return cleaned.strip()


def execute_commands(
    commands: list[dict[str, Any]],
    bridge: AbletonBridge,
) -> list[CommandResult]:
    """Execute a list of parsed commands against Ableton and/or MIDI generators.

    Handles track index remapping: presets use sequential indices (0, 1, 2...)
    but Ableton may already have tracks, so create_midi_track returns the real
    index and we remap all subsequent track references.
    """
    results: list[CommandResult] = []
    # Map preset track index → actual Ableton track index.
    track_map: dict[int, int] = {}
    next_preset_idx = 0  # Which preset index we're on.

    for cmd in commands:
        action = cmd.get("action", "")

        # Remap track index for commands that reference a track.
        if "track" in cmd and action not in ("create_midi_track", "create_audio_track"):
            preset_idx = cmd["track"]
            if preset_idx in track_map:
                cmd = {**cmd, "track": track_map[preset_idx]}

        try:
            result = _dispatch(action, cmd, bridge)

            # When a track is created, capture its real index for remapping.
            if action in ("create_midi_track", "create_audio_track"):
                actual_idx = _extract_track_index(result, bridge)
                if actual_idx is not None:
                    track_map[next_preset_idx] = actual_idx
                next_preset_idx += 1

            results.append(result)
            # Delay after load_device / create_*_track so Ableton
            # finishes processing before the next command arrives.
            if action in ("create_midi_track", "create_audio_track", "create_return_track"):
                time.sleep(0.3)
            elif action == "load_device":
                time.sleep(0.5)  # Devices need more time to load fully.
        except Exception as exc:
            results.append(CommandResult(action=action, success=False, detail=str(exc)))
    return results


def _extract_track_index(result: CommandResult, bridge: AbletonBridge) -> int | None:
    """Extract the actual track index from a create_track response."""
    # Best case: remote script returned the index directly.
    if result.raw_response and "index" in result.raw_response:
        return result.raw_response["index"]
    # Fallback (e.g. timeout): ping Ableton for current track count.
    # The last track is the most recently created one.
    resp = bridge.send({"action": "ping"})
    if resp and "tracks" in resp:
        return resp["tracks"] - 1
    return None


def _dispatch(action: str, cmd: dict[str, Any], bridge: AbletonBridge) -> CommandResult:
    # ── MIDI file generation (local, no Ableton needed) ─────────────
    if action == "generate_midi_file":
        return _handle_midi_generation(cmd)

    # ── Ableton bridge commands ─────────────────────────────────────
    resp = bridge.send(cmd)
    if resp is None:
        return CommandResult(action=action, success=False, detail="No response from Ableton (timeout)")
    if resp.get("error"):
        return CommandResult(action=action, success=False, detail=resp["error"], raw_response=resp)
    return CommandResult(action=action, success=True, detail=resp.get("detail", "OK"), raw_response=resp)


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
