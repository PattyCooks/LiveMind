"""Music theory utilities — scales, chords, intervals, MIDI ↔ note names."""

from __future__ import annotations

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ENHARMONIC = {"Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B"}

# Intervals as semitone offsets from root.
SCALE_INTERVALS: dict[str, tuple[int, ...]] = {
    "major":            (0, 2, 4, 5, 7, 9, 11),
    "minor":            (0, 2, 3, 5, 7, 8, 10),
    "natural_minor":    (0, 2, 3, 5, 7, 8, 10),
    "harmonic_minor":   (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor":    (0, 2, 3, 5, 7, 9, 11),
    "dorian":           (0, 2, 3, 5, 7, 9, 10),
    "phrygian":         (0, 1, 3, 5, 7, 8, 10),
    "lydian":           (0, 2, 4, 6, 7, 9, 11),
    "mixolydian":       (0, 2, 4, 5, 7, 9, 10),
    "locrian":          (0, 1, 3, 5, 6, 8, 10),
    "pentatonic_major": (0, 2, 4, 7, 9),
    "pentatonic_minor": (0, 3, 5, 7, 10),
    "blues":            (0, 3, 5, 6, 7, 10),
    "chromatic":        tuple(range(12)),
    "whole_tone":       (0, 2, 4, 6, 8, 10),
}

CHORD_FORMULAS: dict[str, tuple[int, ...]] = {
    "major":     (0, 4, 7),
    "minor":     (0, 3, 7),
    "dim":       (0, 3, 6),
    "aug":       (0, 4, 8),
    "sus2":      (0, 2, 7),
    "sus4":      (0, 5, 7),
    "7":         (0, 4, 7, 10),
    "maj7":      (0, 4, 7, 11),
    "min7":      (0, 3, 7, 10),
    "dim7":      (0, 3, 6, 9),
    "m7b5":      (0, 3, 6, 10),
    "add9":      (0, 4, 7, 14),
    "min9":      (0, 3, 7, 10, 14),
    "maj9":      (0, 4, 7, 11, 14),
    "9":         (0, 4, 7, 10, 14),
    "11":        (0, 4, 7, 10, 14, 17),
    "13":        (0, 4, 7, 10, 14, 17, 21),
    "6":         (0, 4, 7, 9),
    "min6":      (0, 3, 7, 9),
}

# Standard GM drum map (kick, snare, hats, toms, cymbals).
GM_DRUM_MAP: dict[str, int] = {
    "kick": 36, "snare": 38, "rimshot": 37, "clap": 39,
    "closed_hat": 42, "open_hat": 46, "pedal_hat": 44,
    "low_tom": 41, "mid_tom": 47, "high_tom": 50,
    "crash": 49, "ride": 51, "ride_bell": 53,
    "cowbell": 56, "tambourine": 54, "shaker": 70,
}


def note_name_to_midi(name: str) -> int:
    """Convert e.g. 'C4' → 60, 'F#3' → 54, 'Bb5' → 82."""
    name = name.strip()
    if not name:
        raise ValueError("Empty note name")
    # Separate pitch class from octave.
    i = 0
    while i < len(name) and not (name[i].isdigit() or (name[i] == "-" and i > 0)):
        i += 1
    pitch_class = name[:i]
    octave_str = name[i:]
    if not octave_str:
        raise ValueError(f"No octave in note name: {name!r}")
    octave = int(octave_str)
    # Normalize enharmonics.
    pitch_class = ENHARMONIC.get(pitch_class, pitch_class)
    if pitch_class not in NOTE_NAMES:
        raise ValueError(f"Unknown pitch class: {pitch_class!r}")
    return NOTE_NAMES.index(pitch_class) + (octave + 1) * 12


def midi_to_note_name(midi_num: int) -> str:
    """Convert e.g. 60 → 'C4', 54 → 'F#3'."""
    if not 0 <= midi_num <= 127:
        raise ValueError(f"MIDI number out of range: {midi_num}")
    octave = (midi_num // 12) - 1
    note = NOTE_NAMES[midi_num % 12]
    return f"{note}{octave}"


def build_scale(root: str, scale_type: str = "major", octave: int = 4) -> list[int]:
    """Return MIDI note numbers for one octave of a scale."""
    intervals = SCALE_INTERVALS.get(scale_type)
    if intervals is None:
        raise ValueError(f"Unknown scale type: {scale_type!r}. Available: {sorted(SCALE_INTERVALS)}")
    root_midi = note_name_to_midi(f"{root}{octave}")
    return [root_midi + i for i in intervals]


def build_chord(root: str, chord_type: str = "major", octave: int = 4) -> list[int]:
    """Return MIDI note numbers for a chord."""
    formula = CHORD_FORMULAS.get(chord_type)
    if formula is None:
        raise ValueError(f"Unknown chord type: {chord_type!r}. Available: {sorted(CHORD_FORMULAS)}")
    root_midi = note_name_to_midi(f"{root}{octave}")
    return [root_midi + i for i in formula]


def chord_progression(root: str, scale_type: str, degrees: list[int], octave: int = 3) -> list[list[int]]:
    """Build a chord progression from scale degrees (1-indexed).

    Example: chord_progression("C", "minor", [1, 4, 5, 1]) returns the chords
    for i–iv–v–i in C minor.
    """
    scale = build_scale(root, scale_type, octave)
    all_intervals = SCALE_INTERVALS[scale_type]
    result: list[list[int]] = []
    for deg in degrees:
        idx = (deg - 1) % len(all_intervals)
        chord_root = note_name_to_midi(f"{root}{octave}") + all_intervals[idx]
        # Determine chord quality from scale intervals.
        third_interval = all_intervals[(idx + 2) % len(all_intervals)] - all_intervals[idx]
        if third_interval < 0:
            third_interval += 12
        fifth_interval = all_intervals[(idx + 4) % len(all_intervals)] - all_intervals[idx]
        if fifth_interval < 0:
            fifth_interval += 12
        result.append([chord_root, chord_root + third_interval, chord_root + fifth_interval])
    return result


def snap_to_scale(midi_note: int, root: str, scale_type: str = "major") -> int:
    """Snap a MIDI note to the nearest note in a scale (any octave)."""
    intervals = set(SCALE_INTERVALS.get(scale_type, SCALE_INTERVALS["major"]))
    root_class = NOTE_NAMES.index(ENHARMONIC.get(root, root))
    note_class = midi_note % 12
    relative = (note_class - root_class) % 12
    if relative in intervals:
        return midi_note
    # Find closest interval.
    closest = min(intervals, key=lambda i: min(abs(relative - i), 12 - abs(relative - i)))
    diff = closest - relative
    if diff > 6:
        diff -= 12
    elif diff < -6:
        diff += 12
    return midi_note + diff
