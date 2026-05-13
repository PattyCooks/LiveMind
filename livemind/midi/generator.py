"""MIDI file generation from structured note data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mido

from livemind.config import MIDI_OUTPUT_DIR
from livemind.midi import GM_DRUM_MAP, build_chord, chord_progression, note_name_to_midi


@dataclass
class Note:
    pitch: int
    start: float       # In beats (quarter notes).
    duration: float    # In beats.
    velocity: int = 100
    channel: int = 0


def notes_from_json(data: list[dict[str, Any]]) -> list[Note]:
    """Parse note dicts from LLM output into Note objects."""
    notes: list[Note] = []
    for entry in data:
        pitch = entry.get("pitch", 60)
        if isinstance(pitch, str):
            pitch = note_name_to_midi(pitch)
        notes.append(Note(
            pitch=max(0, min(127, int(pitch))),
            start=float(entry.get("start", 0)),
            duration=float(entry.get("duration", 1)),
            velocity=max(1, min(127, int(entry.get("velocity", 100)))),
            channel=int(entry.get("channel", 0)),
        ))
    return notes


def notes_to_midi(
    notes: list[Note],
    bpm: float = 120.0,
    ticks_per_beat: int = 480,
) -> mido.MidiFile:
    """Convert a list of Notes to a MIDI file object."""
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))

    # Build list of (absolute_tick, message) then sort and convert to deltas.
    events: list[tuple[int, mido.Message]] = []
    for note in notes:
        on_tick = int(note.start * ticks_per_beat)
        off_tick = on_tick + int(note.duration * ticks_per_beat)
        events.append((on_tick, mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=note.channel)))
        events.append((off_tick, mido.Message("note_off", note=note.pitch, velocity=0, channel=note.channel)))

    events.sort(key=lambda e: (e[0], e[1].type == "note_on"))
    prev_tick = 0
    for tick, msg in events:
        msg.time = tick - prev_tick
        track.append(msg)
        prev_tick = tick

    return mid


def save_midi(
    notes: list[Note],
    filename: str | None = None,
    bpm: float = 120.0,
    output_dir: str | Path | None = None,
) -> Path:
    """Generate a .mid file and return the path."""
    output = Path(output_dir or MIDI_OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    if not filename:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"livemind_{stamp}.mid"
    if not filename.endswith(".mid"):
        filename += ".mid"
    path = output / filename
    mid = notes_to_midi(notes, bpm=bpm)
    mid.save(str(path))
    return path


# ── High-level generators called by the command executor ────────────────────


def generate_chord_progression_midi(
    root: str,
    scale_type: str,
    degrees: list[int],
    octave: int = 3,
    beats_per_chord: float = 4.0,
    velocity: int = 90,
    bpm: float = 120.0,
    filename: str | None = None,
) -> tuple[Path, list[Note]]:
    """Build a chord progression and export to MIDI."""
    chords = chord_progression(root, scale_type, degrees, octave)
    notes: list[Note] = []
    for i, chord_notes in enumerate(chords):
        start = i * beats_per_chord
        for pitch in chord_notes:
            notes.append(Note(pitch=pitch, start=start, duration=beats_per_chord - 0.25, velocity=velocity))
    path = save_midi(notes, filename=filename, bpm=bpm)
    return path, notes


def generate_drum_pattern_midi(
    pattern: dict[str, list[float]],
    length_beats: float = 4.0,
    velocity: int = 100,
    bpm: float = 120.0,
    filename: str | None = None,
) -> tuple[Path, list[Note]]:
    """Generate a drum pattern from a {drum_name: [beat_positions]} dict.

    Example:
        pattern = {"kick": [0, 2], "snare": [1, 3], "closed_hat": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]}
    """
    notes: list[Note] = []
    for drum_name, hits in pattern.items():
        pitch = GM_DRUM_MAP.get(drum_name.lower())
        if pitch is None:
            continue
        for beat in hits:
            notes.append(Note(pitch=pitch, start=beat, duration=0.25, velocity=velocity, channel=9))
    path = save_midi(notes, filename=filename, bpm=bpm)
    return path, notes


def generate_melody_midi(
    note_data: list[dict[str, Any]],
    bpm: float = 120.0,
    filename: str | None = None,
) -> tuple[Path, list[Note]]:
    """Generate a melody from raw note dicts (from LLM output)."""
    notes = notes_from_json(note_data)
    path = save_midi(notes, filename=filename, bpm=bpm)
    return path, notes
