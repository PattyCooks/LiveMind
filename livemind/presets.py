"""Genre preset engine — generates musically-correct Ableton commands.

When the LLM is too small to produce proper note patterns, this module
detects genre keywords and builds commands with real music theory.
Patterns are tiled across multiple bars with fills, drops, buildups,
and breakdowns to avoid simple repetition.
"""

from __future__ import annotations

import random
from typing import Any


# ── Helpers ─────────────────────────────────────────────────────────────


def _tile(base_notes: list[dict], bars: int, bar_len: float = 4.0,
          humanize: float = 0.05, fill_every: int = 4,
          fill_notes: list[dict] | None = None,
          variations: list[list[dict]] | None = None) -> list[dict]:
    """Repeat a 1-bar note pattern across *bars* bars with variation.

    - humanize: random velocity ± range (fraction of 127)
    - fill_every: replace every Nth bar with fill_notes (0 = no fills)
    - fill_notes: alternative pattern for fill bars
    - variations: list of alternate 1-bar patterns to cycle through.
      If provided, bars cycle: base → var[0] → var[1] → ... → base → ...
      Fill bars still override when fill_every triggers.
    """
    result: list[dict] = []
    vel_range = int(127 * humanize)
    # Build the cycle of patterns
    if variations:
        cycle = [base_notes] + variations
    else:
        cycle = [base_notes]
    for bar in range(bars):
        is_fill = fill_every and fill_notes and (bar + 1) % fill_every == 0
        if is_fill:
            src = fill_notes
        else:
            src = cycle[bar % len(cycle)]
        for note in src:
            vel = note["velocity"] + random.randint(-vel_range, vel_range)
            result.append({
                "pitch": note["pitch"],
                "start": round(note["start"] + bar * bar_len, 4),
                "duration": note["duration"],
                "velocity": max(1, min(127, vel)),
            })
    return result


def _buildup_snare_roll(bar_offset: float, bars: int = 1,
                        bar_len: float = 4.0, pitch: int = 38) -> list[dict]:
    """Generate an accelerating snare roll over N bars — classic buildup."""
    notes: list[dict] = []
    total_beats = bars * bar_len
    # Start with quarter notes, accelerate to 32nd notes
    t = 0.0
    step = 0.5  # start at 8th notes
    while t < total_beats:
        progress = t / total_beats  # 0→1
        vel = int(70 + progress * 57)  # 70→127
        notes.append({
            "pitch": pitch,
            "start": round(bar_offset + t, 4),
            "duration": round(min(step, 0.25), 4),
            "velocity": min(127, vel),
        })
        # Accelerate: halve the step as we progress
        step = max(0.0625, 0.5 * (1.0 - progress * 0.9))
        t += step
    return notes


def _breakdown_sustain(bar_offset: float, bars: int, key_root: int,
                       bar_len: float = 4.0) -> list[dict]:
    """Sparse atmospheric notes for a breakdown section."""
    length = bars * bar_len
    return [
        {"pitch": key_root + 24, "start": bar_offset, "duration": length, "velocity": 40},
        {"pitch": key_root + 31, "start": bar_offset, "duration": length, "velocity": 35},
        {"pitch": key_root + 36, "start": bar_offset, "duration": length, "velocity": 30},
    ]


def _drop_crash(bar_offset: float) -> list[dict]:
    """Crash cymbal + hard kick at the drop point."""
    return [
        {"pitch": 49, "start": bar_offset, "duration": 1.0, "velocity": 127},  # crash
        {"pitch": 36, "start": bar_offset, "duration": 0.5, "velocity": 127},  # kick
    ]


def detect_genre(text: str) -> str | None:
    """Detect genre keyword from user message. Returns genre name or None."""
    text_lower = text.lower()
    genre_keywords: dict[str, list[str]] = {
        "dubstep": ["dubstep", "wobble", "wobby", "filthy", "riddim", "brostep"],
        "trap": ["trap", "808", "hi-hat rolls"],
        "house": ["house", "four on the floor", "tech house", "deep house"],
        "dnb": ["drum and bass", "dnb", "d&b", "jungle", "liquid dnb"],
        "lofi": ["lo-fi", "lofi", "lo fi", "chill", "chillhop"],
    }
    for genre, keywords in genre_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                return genre
    return None


def detect_element(text: str) -> str | None:
    """Detect a single-element request (bass line, drums, melody, etc.)."""
    text_lower = text.lower()
    element_keywords: dict[str, list[str]] = {
        "bass": ["bass line", "bassline", "bass riff", "sub bass", "808 bass",
                 "make a bass", "sweet bass", "heavy bass", "deep bass", "fat bass"],
        "drums": ["drum beat", "drum pattern", "beat", "rhythm", "drums",
                  "kick pattern", "breakbeat", "boom bap"],
        "melody": ["melody", "lead", "lead line", "riff", "hook", "topline"],
        "chords": ["chord progression", "chords", "harmony", "pad",
                   "chord pattern", "keys", "piano"],
        "arp": ["arpeggio", "arp", "arpeggiate"],
    }
    for element, keywords in element_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                return element
    return None


def detect_plugin_request(text: str) -> str | None:
    """Detect if the user asked for a specific third-party or Ableton device."""
    text_lower = text.lower()
    # Built-in Ableton instruments — map common names to exact browser names.
    ableton_devices: dict[str, str] = {
        "wavetable": "Wavetable", "operator": "Operator", "analog": "Analog",
        "simpler": "Simpler", "sampler": "Sampler", "collision": "Collision",
        "tension": "Tension", "electric": "Electric", "drift": "Drift",
        "meld": "Meld", "drum rack": "Drum Rack",
    }
    for key, name in ableton_devices.items():
        if key in text_lower:
            return name
    # Third-party plugins — user might request these; pass the raw name
    # and let load_device try the browser search.
    plugin_hints = [
        "neural dsp", "parallax", "archetype", "serum", "vital", "massive",
        "omnisphere", "kontakt", "guitar rig", "amp sim", "bias fx",
        "amplitube", "helix", "line 6", "kemper", "axe fx",
    ]
    for hint in plugin_hints:
        if hint in text_lower:
            # Extract the most likely full plugin name from the text.
            # Return the hint capitalized as a best-effort device name.
            return hint.title()
    return None


def generate_preset(genre: str, settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Generate a complete set of Ableton commands for a genre."""
    if settings is None:
        settings = _default_settings()
    generators = {
        "dubstep": _dubstep,
        "trap": _trap,
        "house": _house,
        "dnb": _dnb,
        "lofi": _lofi,
    }
    gen = generators.get(genre)
    if gen:
        return gen(settings)
    return []


def generate_element(element: str, settings: dict[str, Any] | None = None,
                     device_override: str | None = None,
                     user_text: str = "") -> list[dict[str, Any]]:
    """Generate commands for a single element (bass, drums, melody, etc.).

    This is the fallback when the user asks for something specific that
    doesn't match a full genre preset — e.g. "make a sweet bass line".
    """
    if settings is None:
        settings = _default_settings()

    intensity = settings.get("intensity", 0.5)
    bars = settings.get("bars", 4)
    bar_len = 4.0
    key_root = random.choice([36, 38, 41, 43])

    generators: dict[str, Any] = {
        "bass": _element_bass,
        "drums": _element_drums,
        "melody": _element_melody,
        "chords": _element_chords,
        "arp": _element_arp,
    }
    gen = generators.get(element)
    if not gen:
        return []
    return gen(settings, key_root, device_override)


def _default_settings() -> dict[str, Any]:
    return {
        "intensity": 0.5,
        "bars": 4,
        "elements": {"drums": True, "bass": True, "chords": True, "melody": False, "pad": True, "fx": False},
        "structure": {"drops": True, "buildup": False, "breakdown": False},
        "record_to_arrangement": True,
    }


# ── Single-element generators ──────────────────────────────────────────


def _element_bass(settings: dict[str, Any], key_root: int,
                  device_override: str | None = None) -> list[dict[str, Any]]:
    """Generate a standalone bass track with interesting note patterns."""
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    bar_len = 4.0
    device = device_override or "Analog"

    # Two contrasting bass patterns that alternate
    base_pattern = [
        {"pitch": key_root, "start": 0, "duration": 0.75, "velocity": 110},
        {"pitch": key_root, "start": 1.0, "duration": 0.5, "velocity": 100},
        {"pitch": key_root + 5, "start": 1.75, "duration": 0.5, "velocity": 105},
        {"pitch": key_root + 7, "start": 2.5, "duration": 0.5, "velocity": 100},
        {"pitch": key_root + 5, "start": 3.0, "duration": 0.5, "velocity": 95},
        {"pitch": key_root, "start": 3.5, "duration": 0.5, "velocity": 100},
    ]
    var_pattern = [
        {"pitch": key_root + 7, "start": 0, "duration": 0.5, "velocity": 105},
        {"pitch": key_root + 5, "start": 0.5, "duration": 0.5, "velocity": 100},
        {"pitch": key_root + 3, "start": 1.0, "duration": 0.75, "velocity": 110},
        {"pitch": key_root, "start": 2.0, "duration": 0.5, "velocity": 115},
        {"pitch": key_root + 7, "start": 2.75, "duration": 0.25, "velocity": 95},
        {"pitch": key_root + 5, "start": 3.0, "duration": 0.25, "velocity": 100},
        {"pitch": key_root + 3, "start": 3.25, "duration": 0.25, "velocity": 105},
        {"pitch": key_root, "start": 3.5, "duration": 0.5, "velocity": 110},
    ]
    # High intensity: add slides and extra movement
    if intensity > 0.7:
        base_pattern += [
            {"pitch": key_root + 12, "start": 1.5, "duration": 0.15, "velocity": 90},
            {"pitch": key_root + 10, "start": 2.25, "duration": 0.15, "velocity": 85},
        ]

    bass_notes = _tile(base_pattern, bars, fill_every=2, fill_notes=var_pattern, humanize=0.04)

    commands: list[dict[str, Any]] = [
        {"action": "create_midi_track", "name": "Bass"},
        {"action": "load_device", "track": 0, "uri": device},
        {"action": "create_midi_clip", "track": 0, "scene": 0, "length": bars, "notes": bass_notes},
    ]
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


def _element_drums(settings: dict[str, Any], key_root: int,
                   device_override: str | None = None) -> list[dict[str, Any]]:
    """Generate a standalone drum track."""
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)

    base_drums = [
        {"pitch": 36, "start": 0, "duration": 0.25, "velocity": 120},
        {"pitch": 36, "start": 2.0, "duration": 0.25, "velocity": 115},
        {"pitch": 38, "start": 1.0, "duration": 0.25, "velocity": 110},
        {"pitch": 38, "start": 3.0, "duration": 0.25, "velocity": 110},
        {"pitch": 42, "start": 0.5, "duration": 0.1, "velocity": 80},
        {"pitch": 42, "start": 1.5, "duration": 0.1, "velocity": 80},
        {"pitch": 42, "start": 2.5, "duration": 0.1, "velocity": 80},
        {"pitch": 42, "start": 3.5, "duration": 0.1, "velocity": 80},
        {"pitch": 39, "start": 1.0, "duration": 0.25, "velocity": 95},
        {"pitch": 39, "start": 3.0, "duration": 0.25, "velocity": 95},
    ]
    fill_drums = base_drums + [
        {"pitch": 38, "start": 3.25, "duration": 0.1, "velocity": 75},
        {"pitch": 38, "start": 3.5, "duration": 0.1, "velocity": 85},
        {"pitch": 38, "start": 3.75, "duration": 0.1, "velocity": 100},
        {"pitch": 49, "start": 0, "duration": 0.5, "velocity": 90},
    ]
    if intensity > 0.7:
        base_drums += [
            {"pitch": 42, "start": 0.25, "duration": 0.1, "velocity": 65},
            {"pitch": 42, "start": 0.75, "duration": 0.1, "velocity": 60},
            {"pitch": 42, "start": 1.25, "duration": 0.1, "velocity": 65},
            {"pitch": 42, "start": 1.75, "duration": 0.1, "velocity": 60},
        ]

    drum_notes = _tile(base_drums, bars, fill_every=4, fill_notes=fill_drums)
    commands: list[dict[str, Any]] = [
        {"action": "create_midi_track", "name": "Drums"},
        {"action": "load_device", "track": 0, "uri": DRUM_KITS["default"]},
        {"action": "create_midi_clip", "track": 0, "scene": 0, "length": bars, "notes": drum_notes},
    ]
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


def _element_melody(settings: dict[str, Any], key_root: int,
                    device_override: str | None = None) -> list[dict[str, Any]]:
    """Generate a standalone melody track."""
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    bar_len = 4.0
    device = device_override or "Wavetable"
    scale = [0, 2, 4, 5, 7, 9, 11, 12]  # major scale

    melody_notes: list[dict] = []
    for bar in range(bars):
        num = random.randint(4, 7) if intensity > 0.5 else random.randint(3, 5)
        t = 0.0
        prev_interval = 0
        for _ in range(num):
            # Prefer stepwise motion with occasional leaps
            step = random.choice([-2, -1, -1, 0, 1, 1, 2])
            idx = max(0, min(len(scale) - 1, scale.index(min(scale, key=lambda x: abs(x - prev_interval))) + step))
            interval = scale[idx]
            prev_interval = interval
            dur = random.choice([0.25, 0.5, 0.5, 0.75, 1.0])
            if t + dur > bar_len:
                break
            melody_notes.append({
                "pitch": key_root + 36 + interval,
                "start": round(bar * bar_len + t, 4),
                "duration": dur,
                "velocity": random.randint(75, 100),
            })
            t += dur + random.choice([0.0, 0.0, 0.25])

    commands: list[dict[str, Any]] = [
        {"action": "create_midi_track", "name": "Melody"},
        {"action": "load_device", "track": 0, "uri": device},
        {"action": "create_midi_clip", "track": 0, "scene": 0, "length": bars, "notes": melody_notes},
    ]
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


def _element_chords(settings: dict[str, Any], key_root: int,
                    device_override: str | None = None) -> list[dict[str, Any]]:
    """Generate a standalone chord progression track."""
    bars = settings.get("bars", 4)
    bar_len = 4.0
    device = device_override or "Electric"

    # i - iv - v - iv in minor, with 7th extensions
    voicings = [
        [key_root + 24, key_root + 27, key_root + 31, key_root + 34],   # i min7
        [key_root + 29, key_root + 33, key_root + 36, key_root + 39],   # iv min7
        [key_root + 31, key_root + 35, key_root + 38, key_root + 41],   # v min7
        [key_root + 29, key_root + 33, key_root + 36, key_root + 39],   # iv min7
    ]
    chord_notes: list[dict] = []
    for bar in range(bars):
        ch = voicings[bar % len(voicings)]
        for i, p in enumerate(ch):
            chord_notes.append({
                "pitch": p, "start": bar * bar_len,
                "duration": bar_len,
                "velocity": max(1, min(127, 70 - i * 5 + random.randint(-3, 3))),
            })

    commands: list[dict[str, Any]] = [
        {"action": "create_midi_track", "name": "Chords"},
        {"action": "load_device", "track": 0, "uri": device},
        {"action": "create_midi_clip", "track": 0, "scene": 0, "length": bars, "notes": chord_notes},
    ]
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


def _element_arp(settings: dict[str, Any], key_root: int,
                 device_override: str | None = None) -> list[dict[str, Any]]:
    """Generate an arpeggio track."""
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    bar_len = 4.0
    device = device_override or "Wavetable"

    # Arpeggiate through chord tones
    chord_tones = [0, 3, 7, 12, 15, 19, 24]  # minor arp across 2 octaves
    arp_notes: list[dict] = []
    step = 0.25 if intensity > 0.5 else 0.5

    for bar in range(bars):
        t = 0.0
        direction = 1 if bar % 2 == 0 else -1
        tones = chord_tones if direction == 1 else list(reversed(chord_tones))
        idx = 0
        while t < bar_len:
            interval = tones[idx % len(tones)]
            arp_notes.append({
                "pitch": key_root + 24 + interval,
                "start": round(bar * bar_len + t, 4),
                "duration": step * 0.8,
                "velocity": random.randint(70, 95),
            })
            t += step
            idx += 1

    commands: list[dict[str, Any]] = [
        {"action": "create_midi_track", "name": "Arp"},
        {"action": "load_device", "track": 0, "uri": device},
        {"action": "create_midi_clip", "track": 0, "scene": 0, "length": bars, "notes": arp_notes},
    ]
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


# ── Genre-specific drum kit presets ─────────────────────────────────────
# These are Core Library kits in Ableton Live 12 Suite.
# Using preset names instead of bare "Drum Rack" (which loads empty).
DRUM_KITS = {
    "dubstep": "808 Core Kit",
    "trap": "808 Core Kit",
    "house": "909 Core Kit",
    "dnb": "909 Core Kit",
    "lofi": "606 Core Kit",
    "default": "808 Core Kit",
}


# ── Chord progressions ─────────────────────────────────────────────────
# Each progression is a list of semitone offsets from key_root.
# Format: list of (root_offset, [intervals]) per bar-slot in a 4-bar cycle.

def _make_chord_progression(key_root: int, progression: list[tuple[int, list[int]]],
                            bars: int, bar_len: float = 4.0,
                            velocity: int = 65, octave: int = 24,
                            rhythm: str = "sustain") -> list[dict]:
    """Generate chord notes from a progression definition.

    rhythm options:
      "sustain" — whole-bar sustain
      "stab"    — off-beat stabs
      "pump"    — side-chain style (hit + gap)
    """
    notes: list[dict] = []
    for bar in range(bars):
        root_off, intervals = progression[bar % len(progression)]
        pitches = [key_root + octave + root_off + iv for iv in intervals]

        if rhythm == "stab":
            positions = [0.5, 1.5, 2.5, 3.5] if bar % 2 == 0 else [0.5, 1.5, 3.0]
            for pos in positions:
                for i, p in enumerate(pitches):
                    notes.append({
                        "pitch": p,
                        "start": round(bar * bar_len + pos, 4),
                        "duration": 0.25 if pos != 3.0 else 0.5,
                        "velocity": max(1, min(127, velocity - i * 5 + random.randint(-3, 3))),
                    })
        elif rhythm == "pump":
            for i, p in enumerate(pitches):
                notes.append({
                    "pitch": p, "start": bar * bar_len,
                    "duration": 0.25,
                    "velocity": max(1, min(127, velocity + 10 - i * 5)),
                })
                notes.append({
                    "pitch": p, "start": bar * bar_len + 2.0,
                    "duration": 0.25,
                    "velocity": max(1, min(127, velocity - i * 5)),
                })
        else:  # sustain
            for i, p in enumerate(pitches):
                notes.append({
                    "pitch": p, "start": bar * bar_len,
                    "duration": bar_len,
                    "velocity": max(1, min(127, velocity - i * 5 + random.randint(-3, 3))),
                })
    return notes


def _bass_from_progression(key_root: int, progression: list[tuple[int, list[int]]],
                           bars: int, patterns: list[list[dict]],
                           bar_len: float = 4.0) -> list[dict]:
    """Generate bass notes that follow a chord progression's root movement.

    Each bar uses the next pattern from `patterns` (cycling), transposed to
    the chord root for that bar.
    """
    notes: list[dict] = []
    for bar in range(bars):
        root_off, _ = progression[bar % len(progression)]
        pat = patterns[bar % len(patterns)]
        for n in pat:
            vel = n["velocity"] + random.randint(-4, 4)
            notes.append({
                "pitch": key_root + root_off + n["pitch_offset"],
                "start": round(bar * bar_len + n["start"], 4),
                "duration": n["duration"],
                "velocity": max(1, min(127, vel)),
            })
    return notes


# ── Dubstep ─────────────────────────────────────────────────────────────


def _dubstep(settings: dict[str, Any]) -> list[dict[str, Any]]:
    bpm = 140
    intensity = settings.get("intensity", 0.5)
    bars = settings.get("bars", 4)
    elements = settings.get("elements", {})
    structure = settings.get("structure", {})
    key_root = random.choice([36, 37, 38])  # C1, C#1, D1

    vel_boost = int(intensity * 27)
    base_vel = 100 + vel_boost
    bar_len = 4.0

    commands: list[dict[str, Any]] = [{"action": "set_tempo", "bpm": bpm}]
    track_idx = 0

    # ── Chord progression: i → VI → III → VII ──
    # Intervals: [root, quality]
    prog = [
        (0, [0, 3, 7]),       # i  minor
        (8, [0, 4, 7]),       # VI major
        (3, [0, 4, 7]),       # III major
        (10, [0, 4, 7]),      # VII major
    ]

    has_buildup = structure.get("buildup", False) and bars >= 4
    has_breakdown = structure.get("breakdown", False) and bars >= 8
    has_drops = structure.get("drops", True)

    # ── Drums ──
    if elements.get("drums", True):
        base_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": min(127, base_vel + 20)},
            {"pitch": 36, "start": 2.75, "duration": 0.5, "velocity": min(127, base_vel + 10)},
            {"pitch": 38, "start": 2.0, "duration": 0.5, "velocity": 127},
            {"pitch": 42, "start": 0.5, "duration": 0.25, "velocity": 70},
            {"pitch": 42, "start": 1.0, "duration": 0.25, "velocity": 80},
            {"pitch": 42, "start": 1.5, "duration": 0.25, "velocity": 65},
            {"pitch": 42, "start": 2.5, "duration": 0.25, "velocity": 75},
            {"pitch": 42, "start": 3.0, "duration": 0.25, "velocity": 70},
            {"pitch": 42, "start": 3.5, "duration": 0.25, "velocity": 80},
            {"pitch": 46, "start": 1.75, "duration": 0.25, "velocity": 90},
            {"pitch": 39, "start": 2.0, "duration": 0.25, "velocity": min(127, base_vel)},
        ]
        # Variation: different kick placement + ghost notes
        var_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": min(127, base_vel + 20)},
            {"pitch": 36, "start": 1.5, "duration": 0.25, "velocity": min(127, base_vel)},
            {"pitch": 36, "start": 3.0, "duration": 0.5, "velocity": min(127, base_vel + 10)},
            {"pitch": 38, "start": 2.0, "duration": 0.5, "velocity": 127},
            {"pitch": 38, "start": 0.75, "duration": 0.1, "velocity": 50},
            {"pitch": 42, "start": 0.5, "duration": 0.25, "velocity": 75},
            {"pitch": 42, "start": 1.0, "duration": 0.25, "velocity": 70},
            {"pitch": 42, "start": 1.5, "duration": 0.25, "velocity": 80},
            {"pitch": 42, "start": 2.5, "duration": 0.25, "velocity": 70},
            {"pitch": 42, "start": 3.0, "duration": 0.25, "velocity": 75},
            {"pitch": 42, "start": 3.5, "duration": 0.25, "velocity": 85},
            {"pitch": 46, "start": 3.75, "duration": 0.25, "velocity": 85},
            {"pitch": 39, "start": 2.0, "duration": 0.25, "velocity": min(127, base_vel - 5)},
        ]
        # Fill pattern — busier kick + ghost snares
        fill_drums = base_drums + [
            {"pitch": 36, "start": 1.0, "duration": 0.25, "velocity": min(127, base_vel)},
            {"pitch": 38, "start": 0.75, "duration": 0.1, "velocity": 55},
            {"pitch": 38, "start": 1.5, "duration": 0.1, "velocity": 50},
            {"pitch": 38, "start": 3.25, "duration": 0.1, "velocity": 60},
            {"pitch": 38, "start": 3.5, "duration": 0.1, "velocity": 70},
            {"pitch": 38, "start": 3.75, "duration": 0.1, "velocity": 80},
            {"pitch": 49, "start": 0, "duration": 0.5, "velocity": 90},
        ]
        drum_notes = _tile(base_drums, bars, fill_every=4, fill_notes=fill_drums,
                           variations=[var_drums])

        if has_buildup:
            buildup_bar = max(0, (bars // 2) - 1)
            drum_notes = [n for n in drum_notes if not (buildup_bar * bar_len <= n["start"] < (buildup_bar + 1) * bar_len)]
            drum_notes += _buildup_snare_roll(buildup_bar * bar_len)

        if has_drops and bars >= 4:
            drop_bar = bars // 2 if has_buildup else 0
            drum_notes += _drop_crash(drop_bar * bar_len)

        if has_breakdown and bars >= 8:
            bd_start = int(bars * 0.625)
            bd_end = bd_start + max(1, bars // 8)
            drum_notes = [n for n in drum_notes
                          if not (bd_start * bar_len <= n["start"] < bd_end * bar_len)
                          or n["pitch"] == 42]

        if intensity > 0.7:
            for bar in range(bars):
                drum_notes += [
                    {"pitch": 38, "start": bar * bar_len + 0.75, "duration": 0.1, "velocity": 50},
                    {"pitch": 38, "start": bar * bar_len + 3.75, "duration": 0.1, "velocity": 55},
                ]

        commands += [
            {"action": "create_midi_track", "name": "Drums"},
            {"action": "load_device", "track": track_idx, "uri": DRUM_KITS["dubstep"]},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": drum_notes},
        ]
        track_idx += 1

    # ── Sub Bass — follows chord roots ──
    if elements.get("bass", True):
        bass_patterns = [
            # Pattern A: long root note + 5th movement
            [
                {"pitch_offset": 0, "start": 0, "duration": 1.5, "velocity": min(127, base_vel + 10)},
                {"pitch_offset": 0, "start": 2.0, "duration": 0.5, "velocity": min(127, base_vel)},
                {"pitch_offset": 7, "start": 2.75, "duration": 0.75, "velocity": min(127, base_vel + 5)},
                {"pitch_offset": 0, "start": 3.5, "duration": 0.5, "velocity": min(127, base_vel - 5)},
            ],
            # Pattern B: syncopated with octave jump
            [
                {"pitch_offset": 0, "start": 0, "duration": 0.75, "velocity": min(127, base_vel + 10)},
                {"pitch_offset": 12, "start": 0.75, "duration": 0.25, "velocity": min(127, base_vel - 10)},
                {"pitch_offset": 7, "start": 1.0, "duration": 0.75, "velocity": min(127, base_vel + 5)},
                {"pitch_offset": 0, "start": 2.0, "duration": 1.0, "velocity": min(127, base_vel)},
                {"pitch_offset": 5, "start": 3.0, "duration": 0.5, "velocity": min(127, base_vel - 5)},
                {"pitch_offset": 0, "start": 3.5, "duration": 0.5, "velocity": min(127, base_vel + 5)},
            ],
            # Pattern C: driving eighth note feel
            [
                {"pitch_offset": 0, "start": 0, "duration": 0.5, "velocity": min(127, base_vel + 10)},
                {"pitch_offset": 0, "start": 0.5, "duration": 0.5, "velocity": min(127, base_vel - 10)},
                {"pitch_offset": 7, "start": 1.0, "duration": 0.5, "velocity": min(127, base_vel + 5)},
                {"pitch_offset": 5, "start": 1.5, "duration": 0.5, "velocity": min(127, base_vel)},
                {"pitch_offset": 0, "start": 2.0, "duration": 1.5, "velocity": min(127, base_vel + 10)},
                {"pitch_offset": 0, "start": 3.5, "duration": 0.5, "velocity": min(127, base_vel)},
            ],
            # Pattern D: sparse (tension)
            [
                {"pitch_offset": 0, "start": 0, "duration": 2.0, "velocity": min(127, base_vel + 15)},
                {"pitch_offset": 7, "start": 2.5, "duration": 1.5, "velocity": min(127, base_vel)},
            ],
        ]
        bass_notes = _bass_from_progression(key_root, prog, bars, bass_patterns)

        if has_breakdown and bars >= 8:
            bd_start = int(bars * 0.625)
            bd_end = bd_start + max(1, bars // 8)
            bass_notes = [n for n in bass_notes
                          if not (bd_start * bar_len <= n["start"] < bd_end * bar_len)]

        commands += [
            {"action": "create_midi_track", "name": "Sub Bass"},
            {"action": "load_device", "track": track_idx, "uri": "Operator"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": bass_notes},
        ]
        track_idx += 1

    # ── Wobble Bass ──
    if has_drops:
        base_wobble = [
            {"pitch": key_root + 12, "start": 0, "duration": 0.25, "velocity": min(127, base_vel + 20)},
            {"pitch": key_root + 12, "start": 0.25, "duration": 0.25, "velocity": min(127, base_vel - 10)},
            {"pitch": key_root + 12, "start": 0.5, "duration": 0.5, "velocity": 127},
            {"pitch": key_root + 12, "start": 1.0, "duration": 0.25, "velocity": min(127, base_vel + 10)},
            {"pitch": key_root + 12, "start": 1.25, "duration": 0.75, "velocity": 127},
            {"pitch": key_root + 17, "start": 2.0, "duration": 0.25, "velocity": min(127, base_vel + 20)},
            {"pitch": key_root + 17, "start": 2.25, "duration": 0.25, "velocity": min(127, base_vel - 10)},
            {"pitch": key_root + 17, "start": 2.5, "duration": 0.5, "velocity": 127},
            {"pitch": key_root + 12, "start": 3.0, "duration": 0.25, "velocity": min(127, base_vel + 10)},
            {"pitch": key_root + 12, "start": 3.25, "duration": 0.25, "velocity": min(127, base_vel)},
            {"pitch": key_root + 12, "start": 3.5, "duration": 0.5, "velocity": 127},
        ]
        # Variation wobble — triplet feel
        var_wobble_a = [
            {"pitch": key_root + 12, "start": 0, "duration": 0.33, "velocity": 127},
            {"pitch": key_root + 19, "start": 0.33, "duration": 0.33, "velocity": min(127, base_vel + 15)},
            {"pitch": key_root + 12, "start": 0.67, "duration": 0.33, "velocity": min(127, base_vel)},
            {"pitch": key_root + 17, "start": 1.0, "duration": 0.5, "velocity": 127},
            {"pitch": key_root + 12, "start": 1.5, "duration": 0.5, "velocity": min(127, base_vel + 20)},
            {"pitch": key_root + 19, "start": 2.0, "duration": 0.5, "velocity": 127},
            {"pitch": key_root + 17, "start": 2.5, "duration": 0.25, "velocity": min(127, base_vel + 10)},
            {"pitch": key_root + 12, "start": 2.75, "duration": 0.25, "velocity": 127},
            {"pitch": key_root + 12, "start": 3.0, "duration": 0.5, "velocity": min(127, base_vel + 20)},
            {"pitch": key_root + 17, "start": 3.5, "duration": 0.5, "velocity": 127},
        ]
        # Variation wobble B — half-time
        var_wobble_b = [
            {"pitch": key_root + 12, "start": 0, "duration": 1.0, "velocity": 127},
            {"pitch": key_root + 19, "start": 1.0, "duration": 1.0, "velocity": min(127, base_vel + 15)},
            {"pitch": key_root + 17, "start": 2.0, "duration": 0.5, "velocity": 127},
            {"pitch": key_root + 12, "start": 2.5, "duration": 0.5, "velocity": min(127, base_vel + 10)},
            {"pitch": key_root + 12, "start": 3.0, "duration": 1.0, "velocity": 127},
        ]
        wobble_notes = _tile(base_wobble, bars, fill_every=0,
                             variations=[var_wobble_a, var_wobble_b])

        if has_buildup and bars >= 4:
            buildup_bar = max(0, (bars // 2) - 1)
            wobble_notes = [n for n in wobble_notes
                            if not (buildup_bar * bar_len <= n["start"] < (buildup_bar + 1) * bar_len)]

        if has_breakdown and bars >= 8:
            bd_start = int(bars * 0.625)
            bd_end = bd_start + max(1, bars // 8)
            wobble_notes = [n for n in wobble_notes
                            if not (bd_start * bar_len <= n["start"] < bd_end * bar_len)]

        if intensity > 0.75:
            for _ in range(bars * 3):
                wobble_notes.append({
                    "pitch": key_root + 12 + random.choice([0, 5, 7, 12]),
                    "start": round(random.uniform(0, bars * bar_len - 0.1), 2),
                    "duration": round(random.uniform(0.05, 0.2), 2),
                    "velocity": random.randint(100, 127),
                })

        commands += [
            {"action": "create_midi_track", "name": "Wobble"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": wobble_notes},
        ]
        track_idx += 1

    # ── Chords — real progression ──
    if elements.get("chords", True):
        chord_notes = _make_chord_progression(key_root, prog, bars, velocity=65)
        if has_breakdown and bars >= 8:
            bd_start = int(bars * 0.625)
            bd_end = bd_start + max(1, bars // 8)
            for n in chord_notes:
                if bd_start * bar_len <= n["start"] < bd_end * bar_len:
                    n["velocity"] = max(1, n["velocity"] - 25)

        commands += [
            {"action": "create_midi_track", "name": "Chords"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": chord_notes},
        ]
        track_idx += 1

    # ── Melody / Lead ──
    if elements.get("melody", False):
        scale = [0, 3, 5, 7, 10, 12, 15]  # minor pentatonic intervals
        melody_notes: list[dict] = []
        prev_pitch = key_root + 36
        for bar in range(bars):
            root_off, _ = prog[bar % len(prog)]
            num_notes = random.randint(3, 5) if intensity > 0.5 else random.randint(2, 4)
            t = 0.0
            for _ in range(num_notes):
                # Stepwise motion from previous note, biased toward chord tones
                step = random.choice([-2, -1, -1, 0, 1, 1, 2])
                idx = max(0, min(len(scale) - 1, (scale.index(min(scale, key=lambda x: abs(x - (prev_pitch - key_root - 36)))) + step)))
                interval = scale[idx]
                pitch = key_root + 36 + interval
                dur = random.choice([0.25, 0.5, 0.75, 1.0])
                if t + dur > bar_len:
                    break
                melody_notes.append({
                    "pitch": pitch,
                    "start": round(bar * bar_len + t, 4),
                    "duration": dur,
                    "velocity": random.randint(75, 95),
                })
                prev_pitch = pitch
                t += dur + random.choice([0.0, 0.25, 0.5])

        commands += [
            {"action": "create_midi_track", "name": "Lead"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": melody_notes},
        ]
        track_idx += 1

    # ── Dark Pad ──
    if elements.get("pad", True):
        pad_notes: list[dict] = []
        voicings = [
            [key_root + 24, key_root + 27, key_root + 31],          # i
            [key_root + 24 + 8, key_root + 28 + 8, key_root + 31 + 8],  # VI
            [key_root + 24 + 3, key_root + 28 + 3, key_root + 31 + 3],  # III
            [key_root + 24 + 10, key_root + 28 + 10, key_root + 31 + 10],  # VII
        ]
        for bar in range(0, bars, 2):
            chord = voicings[(bar // 2) % len(voicings)]
            length = min(2, bars - bar) * bar_len
            for i, p in enumerate(chord):
                pad_notes.append({
                    "pitch": p, "start": bar * bar_len,
                    "duration": length, "velocity": 60 - i * 5,
                })
        if has_breakdown and bars >= 8:
            bd_bar = int(bars * 0.625)
            pad_notes += _breakdown_sustain(bd_bar * bar_len, max(1, bars // 8), key_root)

        commands += [
            {"action": "create_midi_track", "name": "Dark Pad"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": pad_notes},
        ]
        track_idx += 1

    # ── FX / Riser ──
    if elements.get("fx", False) and has_buildup and bars >= 4:
        buildup_bar = max(0, (bars // 2) - 1)
        riser_notes = [
            {"pitch": key_root + 48, "start": buildup_bar * bar_len,
             "duration": bar_len, "velocity": 80},
            {"pitch": key_root + 48 + 12, "start": buildup_bar * bar_len + bar_len * 0.5,
             "duration": bar_len * 0.5, "velocity": 100},
        ]
        commands += [
            {"action": "create_midi_track", "name": "FX Riser"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": riser_notes},
        ]
        track_idx += 1

    commands.append({"action": "create_return_track", "name": "Reverb"})

    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})

    return commands


# ── Trap ────────────────────────────────────────────────────────────────


def _trap(settings: dict[str, Any]) -> list[dict[str, Any]]:
    bpm = 150
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    elements = settings.get("elements", {})
    structure = settings.get("structure", {})
    key_root = random.choice([36, 38, 41])
    bar_len = 4.0

    commands: list[dict[str, Any]] = [{"action": "set_tempo", "bpm": bpm}]
    track_idx = 0

    # Progression: i → VII → VI → V
    prog = [
        (0, [0, 3, 7]),       # i minor
        (10, [0, 4, 7]),      # VII major
        (8, [0, 4, 7]),       # VI major
        (7, [0, 3, 7]),       # v minor
    ]

    has_buildup = structure.get("buildup", False) and bars >= 4
    has_drops = structure.get("drops", True)

    # ── 808 Drums ──
    if elements.get("drums", True):
        hats: list[dict] = []
        for i in range(32):
            start = i * 0.125
            vel = random.randint(60, 100) if i % 4 != 0 else random.randint(100, 127)
            hats.append({"pitch": 42, "start": start, "duration": 0.1, "velocity": vel})
        for pos in [0.75, 1.75, 2.75, 3.75]:
            hats.append({"pitch": 46, "start": pos, "duration": 0.25, "velocity": 95})

        base_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": 127},
            {"pitch": 36, "start": 1.5, "duration": 0.5, "velocity": 110},
            {"pitch": 36, "start": 3.0, "duration": 0.5, "velocity": 120},
            {"pitch": 38, "start": 1.0, "duration": 0.5, "velocity": 120},
            {"pitch": 38, "start": 3.0, "duration": 0.5, "velocity": 115},
            {"pitch": 39, "start": 1.0, "duration": 0.25, "velocity": 100},
        ] + hats

        # Variation: different kick placement
        var_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": 127},
            {"pitch": 36, "start": 0.75, "duration": 0.25, "velocity": 100},
            {"pitch": 36, "start": 2.0, "duration": 0.5, "velocity": 115},
            {"pitch": 36, "start": 3.5, "duration": 0.25, "velocity": 110},
            {"pitch": 38, "start": 1.0, "duration": 0.5, "velocity": 120},
            {"pitch": 38, "start": 3.0, "duration": 0.5, "velocity": 115},
            {"pitch": 39, "start": 1.0, "duration": 0.25, "velocity": 100},
        ] + hats

        fill_drums = base_drums + [
            {"pitch": 36, "start": 3.25, "duration": 0.25, "velocity": 127},
            {"pitch": 36, "start": 3.5, "duration": 0.25, "velocity": 127},
            {"pitch": 36, "start": 3.75, "duration": 0.25, "velocity": 127},
            {"pitch": 49, "start": 0, "duration": 0.5, "velocity": 100},
        ]
        drum_notes = _tile(base_drums, bars, fill_every=4, fill_notes=fill_drums,
                           variations=[var_drums])

        if has_buildup:
            bu_bar = max(0, (bars // 2) - 1)
            drum_notes = [n for n in drum_notes if not (bu_bar * bar_len <= n["start"] < (bu_bar + 1) * bar_len)]
            drum_notes += _buildup_snare_roll(bu_bar * bar_len)

        if has_drops and bars >= 4:
            drum_notes += _drop_crash((bars // 2) * bar_len)

        commands += [
            {"action": "create_midi_track", "name": "808 Drums"},
            {"action": "load_device", "track": track_idx, "uri": DRUM_KITS["trap"]},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": drum_notes},
        ]
        track_idx += 1

    # ── 808 Bass — follows chord roots ──
    if elements.get("bass", True):
        bass_patterns = [
            [
                {"pitch_offset": 0, "start": 0, "duration": 1.0, "velocity": 127},
                {"pitch_offset": 0, "start": 1.5, "duration": 1.0, "velocity": 110},
                {"pitch_offset": 7, "start": 3.0, "duration": 1.0, "velocity": 120},
            ],
            [
                {"pitch_offset": 0, "start": 0, "duration": 0.75, "velocity": 127},
                {"pitch_offset": 12, "start": 0.75, "duration": 0.25, "velocity": 100},
                {"pitch_offset": 7, "start": 1.0, "duration": 0.75, "velocity": 115},
                {"pitch_offset": 5, "start": 2.0, "duration": 0.75, "velocity": 120},
                {"pitch_offset": 3, "start": 3.0, "duration": 0.5, "velocity": 110},
                {"pitch_offset": 0, "start": 3.5, "duration": 0.5, "velocity": 120},
            ],
            [
                {"pitch_offset": 0, "start": 0, "duration": 2.0, "velocity": 127},
                {"pitch_offset": 5, "start": 2.0, "duration": 1.0, "velocity": 115},
                {"pitch_offset": 0, "start": 3.0, "duration": 1.0, "velocity": 120},
            ],
        ]
        bass_notes = _bass_from_progression(key_root, prog, bars, bass_patterns)
        commands += [
            {"action": "create_midi_track", "name": "808 Bass"},
            {"action": "load_device", "track": track_idx, "uri": "Operator"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": bass_notes},
        ]
        track_idx += 1

    # ── Melody ──
    if elements.get("melody", True):
        scale = [0, 3, 5, 7, 10, 12]
        melody_notes: list[dict] = []
        prev_pitch = key_root + 24
        for bar in range(bars):
            root_off, _ = prog[bar % len(prog)]
            num = random.randint(3, 6) if intensity > 0.5 else random.randint(2, 4)
            t = 0.0
            for _ in range(num):
                step = random.choice([-2, -1, -1, 0, 1, 1, 2])
                idx = max(0, min(len(scale) - 1, (scale.index(min(scale, key=lambda x: abs(x - (prev_pitch - key_root - 24)))) + step)))
                interval = scale[idx]
                p = key_root + 24 + root_off + interval
                dur = random.choice([0.25, 0.5, 0.75])
                if t + dur > bar_len:
                    break
                melody_notes.append({
                    "pitch": p, "start": round(bar * bar_len + t, 4),
                    "duration": dur, "velocity": random.randint(75, 95),
                })
                prev_pitch = p
                t += dur + random.choice([0.0, 0.25])
        commands += [
            {"action": "create_midi_track", "name": "Lead"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": melody_notes},
        ]
        track_idx += 1

    # ── Chords — real progression ──
    if elements.get("chords", True):
        chord_notes = _make_chord_progression(key_root, prog, bars, velocity=60)
        commands += [
            {"action": "create_midi_track", "name": "Pad"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": chord_notes},
        ]
        track_idx += 1

    commands.append({"action": "create_return_track", "name": "Reverb"})
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


# ── House ───────────────────────────────────────────────────────────────


def _house(settings: dict[str, Any]) -> list[dict[str, Any]]:
    bpm = 124
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    elements = settings.get("elements", {})
    structure = settings.get("structure", {})
    key_root = random.choice([36, 38, 41, 43])
    bar_len = 4.0

    commands: list[dict[str, Any]] = [{"action": "set_tempo", "bpm": bpm}]
    track_idx = 0
    has_buildup = structure.get("buildup", False) and bars >= 4
    has_breakdown = structure.get("breakdown", False) and bars >= 8

    # ── Drums ──
    if elements.get("drums", True):
        base_drums = [
            {"pitch": 36, "start": 0, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "start": 1, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "start": 2, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "start": 3, "duration": 0.25, "velocity": 120},
            {"pitch": 39, "start": 1, "duration": 0.25, "velocity": 105},
            {"pitch": 39, "start": 3, "duration": 0.25, "velocity": 105},
            {"pitch": 42, "start": 0.5, "duration": 0.25, "velocity": 85},
            {"pitch": 42, "start": 1.5, "duration": 0.25, "velocity": 85},
            {"pitch": 42, "start": 2.5, "duration": 0.25, "velocity": 85},
            {"pitch": 42, "start": 3.5, "duration": 0.25, "velocity": 85},
        ]
        # Shaker sixteenths
        for i in range(16):
            base_drums.append({"pitch": 51, "start": i * 0.25, "duration": 0.1,
                               "velocity": 50 if i % 2 == 0 else 40})

        fill_drums = base_drums + [
            {"pitch": 38, "start": 3.25, "duration": 0.1, "velocity": 80},
            {"pitch": 38, "start": 3.5, "duration": 0.1, "velocity": 90},
            {"pitch": 38, "start": 3.75, "duration": 0.1, "velocity": 100},
            {"pitch": 49, "start": 0, "duration": 0.5, "velocity": 85},
        ]
        drum_notes = _tile(base_drums, bars, fill_every=4, fill_notes=fill_drums)

        if has_buildup:
            bu_bar = max(0, (bars // 2) - 1)
            drum_notes = [n for n in drum_notes if not (bu_bar * bar_len <= n["start"] < (bu_bar + 1) * bar_len)]
            drum_notes += _buildup_snare_roll(bu_bar * bar_len, pitch=39)

        if has_breakdown and bars >= 8:
            bd_start = int(bars * 0.625)
            bd_end = bd_start + max(1, bars // 8)
            drum_notes = [n for n in drum_notes
                          if not (bd_start * bar_len <= n["start"] < bd_end * bar_len)
                          or n["pitch"] in (42, 51)]  # keep hats in breakdown

        commands += [
            {"action": "create_midi_track", "name": "Drums"},
            {"action": "load_device", "track": track_idx, "uri": DRUM_KITS["house"]},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": drum_notes},
        ]
        track_idx += 1

    # ── Bass ──
    if elements.get("bass", True):
        base_bass = [
            {"pitch": key_root, "start": 0, "duration": 0.5, "velocity": 110},
            {"pitch": key_root, "start": 0.75, "duration": 0.25, "velocity": 90},
            {"pitch": key_root + 5, "start": 1, "duration": 0.5, "velocity": 100},
            {"pitch": key_root + 7, "start": 2, "duration": 0.5, "velocity": 105},
            {"pitch": key_root + 5, "start": 2.75, "duration": 0.25, "velocity": 90},
            {"pitch": key_root, "start": 3, "duration": 0.5, "velocity": 100},
            {"pitch": key_root, "start": 3.75, "duration": 0.25, "velocity": 85},
        ]
        var_bass = [
            {"pitch": key_root + 7, "start": 0, "duration": 0.5, "velocity": 105},
            {"pitch": key_root + 5, "start": 0.75, "duration": 0.25, "velocity": 90},
            {"pitch": key_root + 3, "start": 1, "duration": 0.5, "velocity": 100},
            {"pitch": key_root, "start": 2, "duration": 0.75, "velocity": 110},
            {"pitch": key_root + 5, "start": 3, "duration": 0.5, "velocity": 100},
            {"pitch": key_root + 7, "start": 3.5, "duration": 0.5, "velocity": 95},
        ]
        bass_notes = _tile(base_bass, bars, fill_every=2, fill_notes=var_bass)
        commands += [
            {"action": "create_midi_track", "name": "Bass"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": bass_notes},
        ]
        track_idx += 1

    # ── Chords — house stabs ──
    if elements.get("chords", True):
        # Progression: i → iv → VI → V
        house_prog = [
            (0, [0, 3, 7, 10]),       # i min7
            (5, [0, 3, 7, 10]),       # iv min7
            (8, [0, 4, 7, 11]),       # VI maj7
            (7, [0, 4, 7]),           # V major
        ]
        chord_notes = _make_chord_progression(key_root, house_prog, bars,
                                              velocity=80, rhythm="stab")
        commands += [
            {"action": "create_midi_track", "name": "Chords"},
            {"action": "load_device", "track": track_idx, "uri": "Electric"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": chord_notes},
        ]
        track_idx += 1

    # ── Pad ──
    if elements.get("pad", True):
        pad_voicings = [
            [key_root + 24, key_root + 27, key_root + 31],
            [key_root + 29, key_root + 32, key_root + 36],
            [key_root + 32, key_root + 36, key_root + 39],
            [key_root + 31, key_root + 35, key_root + 38],
        ]
        pad_notes: list[dict] = []
        for bar in range(0, bars, 2):
            ch = pad_voicings[(bar // 2) % len(pad_voicings)]
            length = min(2, bars - bar) * bar_len
            for i, p in enumerate(ch[:3]):
                pad_notes.append({"pitch": p, "start": bar * bar_len, "duration": length,
                                  "velocity": 50 - i * 5})
        commands += [
            {"action": "create_midi_track", "name": "Pad"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": pad_notes},
        ]
        track_idx += 1

    commands.append({"action": "create_return_track", "name": "Reverb"})
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


# ── DnB ─────────────────────────────────────────────────────────────────


def _dnb(settings: dict[str, Any]) -> list[dict[str, Any]]:
    bpm = 174
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    elements = settings.get("elements", {})
    structure = settings.get("structure", {})
    key_root = random.choice([36, 38, 41])
    bar_len = 4.0

    commands: list[dict[str, Any]] = [{"action": "set_tempo", "bpm": bpm}]
    track_idx = 0
    has_buildup = structure.get("buildup", False) and bars >= 4
    has_drops = structure.get("drops", True)

    # ── Breaks ──
    if elements.get("drums", True):
        base_breaks = [
            {"pitch": 36, "start": 0, "duration": 0.25, "velocity": 120},
            {"pitch": 42, "start": 0.25, "duration": 0.1, "velocity": 80},
            {"pitch": 38, "start": 0.5, "duration": 0.25, "velocity": 115},
            {"pitch": 42, "start": 0.75, "duration": 0.1, "velocity": 75},
            {"pitch": 36, "start": 1.0, "duration": 0.25, "velocity": 110},
            {"pitch": 36, "start": 1.25, "duration": 0.25, "velocity": 100},
            {"pitch": 38, "start": 1.5, "duration": 0.25, "velocity": 120},
            {"pitch": 42, "start": 1.75, "duration": 0.1, "velocity": 80},
            {"pitch": 36, "start": 2.0, "duration": 0.25, "velocity": 120},
            {"pitch": 42, "start": 2.25, "duration": 0.1, "velocity": 80},
            {"pitch": 38, "start": 2.5, "duration": 0.25, "velocity": 115},
            {"pitch": 42, "start": 2.75, "duration": 0.1, "velocity": 75},
            {"pitch": 36, "start": 3.0, "duration": 0.25, "velocity": 115},
            {"pitch": 42, "start": 3.25, "duration": 0.1, "velocity": 85},
            {"pitch": 38, "start": 3.5, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "start": 3.75, "duration": 0.25, "velocity": 105},
        ]
        # Variation break — different kick placement, ghost snares
        var_breaks = [
            {"pitch": 36, "start": 0, "duration": 0.25, "velocity": 125},
            {"pitch": 38, "start": 0.25, "duration": 0.1, "velocity": 60},
            {"pitch": 42, "start": 0.5, "duration": 0.1, "velocity": 85},
            {"pitch": 38, "start": 0.75, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "start": 1.0, "duration": 0.25, "velocity": 115},
            {"pitch": 42, "start": 1.25, "duration": 0.1, "velocity": 75},
            {"pitch": 36, "start": 1.5, "duration": 0.25, "velocity": 105},
            {"pitch": 38, "start": 1.75, "duration": 0.25, "velocity": 127},
            {"pitch": 42, "start": 2.0, "duration": 0.1, "velocity": 80},
            {"pitch": 36, "start": 2.25, "duration": 0.25, "velocity": 120},
            {"pitch": 38, "start": 2.5, "duration": 0.25, "velocity": 110},
            {"pitch": 38, "start": 2.75, "duration": 0.1, "velocity": 55},
            {"pitch": 36, "start": 3.0, "duration": 0.25, "velocity": 120},
            {"pitch": 42, "start": 3.25, "duration": 0.1, "velocity": 80},
            {"pitch": 38, "start": 3.5, "duration": 0.1, "velocity": 70},
            {"pitch": 38, "start": 3.75, "duration": 0.25, "velocity": 110},
        ]
        drum_notes = _tile(base_breaks, bars, fill_every=2, fill_notes=var_breaks)

        if has_buildup:
            bu_bar = max(0, (bars // 2) - 1)
            drum_notes = [n for n in drum_notes if not (bu_bar * bar_len <= n["start"] < (bu_bar + 1) * bar_len)]
            drum_notes += _buildup_snare_roll(bu_bar * bar_len)

        if has_drops and bars >= 4:
            drum_notes += _drop_crash((bars // 2) * bar_len)

        commands += [
            {"action": "create_midi_track", "name": "Breaks"},
            {"action": "load_device", "track": track_idx, "uri": DRUM_KITS["dnb"]},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": drum_notes},
        ]
        track_idx += 1

    # ── Reese Bass ──
    if elements.get("bass", True):
        base_bass = [
            {"pitch": key_root, "start": 0, "duration": 0.75, "velocity": 120},
            {"pitch": key_root + 5, "start": 1.0, "duration": 0.5, "velocity": 110},
            {"pitch": key_root + 3, "start": 1.5, "duration": 0.5, "velocity": 105},
            {"pitch": key_root, "start": 2.0, "duration": 0.75, "velocity": 120},
            {"pitch": key_root + 7, "start": 3.0, "duration": 0.5, "velocity": 115},
            {"pitch": key_root + 5, "start": 3.5, "duration": 0.5, "velocity": 100},
        ]
        var_bass = [
            {"pitch": key_root + 7, "start": 0, "duration": 0.5, "velocity": 115},
            {"pitch": key_root + 5, "start": 0.5, "duration": 0.5, "velocity": 110},
            {"pitch": key_root, "start": 1.0, "duration": 1.0, "velocity": 120},
            {"pitch": key_root + 3, "start": 2.0, "duration": 0.5, "velocity": 110},
            {"pitch": key_root + 5, "start": 2.5, "duration": 0.5, "velocity": 115},
            {"pitch": key_root, "start": 3.0, "duration": 1.0, "velocity": 120},
        ]
        bass_notes = _tile(base_bass, bars, fill_every=2, fill_notes=var_bass)
        commands += [
            {"action": "create_midi_track", "name": "Reese Bass"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": bass_notes},
        ]
        track_idx += 1

    # ── Atmospheric Pad ──
    if elements.get("pad", True):
        pad_notes: list[dict] = []
        voicings = [
            [key_root + 24, key_root + 31, key_root + 36],
            [key_root + 22, key_root + 29, key_root + 36],
            [key_root + 24, key_root + 31, key_root + 38],
        ]
        for bar in range(0, bars, 2):
            ch = voicings[(bar // 2) % len(voicings)]
            length = min(2, bars - bar) * bar_len
            for i, p in enumerate(ch):
                pad_notes.append({"pitch": p, "start": bar * bar_len,
                                  "duration": length, "velocity": 50 - i * 5})
        commands += [
            {"action": "create_midi_track", "name": "Atmosphere"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": pad_notes},
        ]
        track_idx += 1

    # ── Melody ──
    if elements.get("melody", False):
        scale = [0, 3, 5, 7, 10, 12, 15]
        mel_notes: list[dict] = []
        for bar in range(bars):
            num = random.randint(3, 6) if intensity > 0.5 else random.randint(2, 4)
            t = 0.0
            for _ in range(num):
                p = key_root + 36 + random.choice(scale)
                dur = random.choice([0.25, 0.5, 0.75])
                if t + dur > bar_len:
                    break
                mel_notes.append({
                    "pitch": p, "start": round(bar * bar_len + t, 4),
                    "duration": dur, "velocity": random.randint(70, 95),
                })
                t += dur + random.choice([0.0, 0.25])
        commands += [
            {"action": "create_midi_track", "name": "Lead"},
            {"action": "load_device", "track": track_idx, "uri": "Wavetable"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": mel_notes},
        ]
        track_idx += 1

    commands.append({"action": "create_return_track", "name": "Reverb"})
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands


# ── Lo-fi ───────────────────────────────────────────────────────────────


def _lofi(settings: dict[str, Any]) -> list[dict[str, Any]]:
    bpm = 82
    bars = settings.get("bars", 4)
    intensity = settings.get("intensity", 0.5)
    elements = settings.get("elements", {})
    structure = settings.get("structure", {})
    key_root = random.choice([36, 38, 40, 41, 43])
    bar_len = 4.0

    commands: list[dict[str, Any]] = [{"action": "set_tempo", "bpm": bpm}]
    track_idx = 0

    # ── Drums ──
    if elements.get("drums", True):
        base_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": 95},
            {"pitch": 42, "start": 0.5, "duration": 0.1, "velocity": 60},
            {"pitch": 38, "start": 1.0, "duration": 0.25, "velocity": 85},
            {"pitch": 42, "start": 1.5, "duration": 0.1, "velocity": 55},
            {"pitch": 36, "start": 2.0, "duration": 0.5, "velocity": 90},
            {"pitch": 36, "start": 2.5, "duration": 0.25, "velocity": 70},
            {"pitch": 38, "start": 3.0, "duration": 0.25, "velocity": 80},
            {"pitch": 42, "start": 3.5, "duration": 0.1, "velocity": 55},
        ]
        # Variation: slight swing feel
        var_drums = [
            {"pitch": 36, "start": 0, "duration": 0.5, "velocity": 90},
            {"pitch": 42, "start": 0.5, "duration": 0.1, "velocity": 55},
            {"pitch": 42, "start": 0.75, "duration": 0.1, "velocity": 45},
            {"pitch": 38, "start": 1.0, "duration": 0.25, "velocity": 80},
            {"pitch": 36, "start": 1.75, "duration": 0.25, "velocity": 65},
            {"pitch": 36, "start": 2.0, "duration": 0.5, "velocity": 85},
            {"pitch": 42, "start": 2.5, "duration": 0.1, "velocity": 50},
            {"pitch": 38, "start": 3.0, "duration": 0.25, "velocity": 75},
            {"pitch": 42, "start": 3.25, "duration": 0.1, "velocity": 40},
            {"pitch": 42, "start": 3.5, "duration": 0.1, "velocity": 50},
        ]
        drum_notes = _tile(base_drums, bars, humanize=0.08, fill_every=2, fill_notes=var_drums)
        commands += [
            {"action": "create_midi_track", "name": "Drums"},
            {"action": "load_device", "track": track_idx, "uri": DRUM_KITS["lofi"]},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": drum_notes},
        ]
        track_idx += 1

    # ── Mellow Bass ──
    if elements.get("bass", True):
        base_bass = [
            {"pitch": key_root, "start": 0, "duration": 1.0, "velocity": 85},
            {"pitch": key_root + 5, "start": 1.0, "duration": 0.75, "velocity": 80},
            {"pitch": key_root + 7, "start": 2.0, "duration": 1.0, "velocity": 85},
            {"pitch": key_root + 3, "start": 3.0, "duration": 0.75, "velocity": 75},
        ]
        var_bass = [
            {"pitch": key_root + 7, "start": 0, "duration": 0.75, "velocity": 80},
            {"pitch": key_root + 5, "start": 1.0, "duration": 0.75, "velocity": 80},
            {"pitch": key_root + 3, "start": 2.0, "duration": 0.75, "velocity": 80},
            {"pitch": key_root, "start": 3.0, "duration": 1.0, "velocity": 85},
        ]
        bass_notes = _tile(base_bass, bars, humanize=0.06, fill_every=2, fill_notes=var_bass)
        commands += [
            {"action": "create_midi_track", "name": "Bass"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": bass_notes},
        ]
        track_idx += 1

    # ── Jazz Chords — evolving voicings ──
    if elements.get("chords", True):
        voicings = [
            # Cmaj7, Dm7, Em7, Dm7 — classic lofi progression
            [key_root + 24, key_root + 28, key_root + 31, key_root + 35],
            [key_root + 26, key_root + 29, key_root + 33, key_root + 36],
            [key_root + 28, key_root + 31, key_root + 35, key_root + 38],
            [key_root + 26, key_root + 29, key_root + 33, key_root + 36],
        ]
        chord_notes: list[dict] = []
        for bar in range(bars):
            ch = voicings[bar % len(voicings)]
            for i, p in enumerate(ch):
                chord_notes.append({
                    "pitch": p, "start": bar * bar_len,
                    "duration": bar_len,
                    "velocity": max(1, min(127, 65 - i * 5 + random.randint(-4, 4))),
                })
        commands += [
            {"action": "create_midi_track", "name": "Keys"},
            {"action": "load_device", "track": track_idx, "uri": "Electric"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": chord_notes},
        ]
        track_idx += 1

    # ── Melody — gentle pentatonic ──
    if elements.get("melody", False):
        scale = [0, 2, 4, 7, 9, 12]  # major pentatonic
        mel_notes: list[dict] = []
        for bar in range(bars):
            num = random.randint(2, 4)
            t = 0.0
            for _ in range(num):
                p = key_root + 36 + random.choice(scale)
                dur = random.choice([0.5, 0.75, 1.0, 1.5])
                if t + dur > bar_len:
                    break
                mel_notes.append({
                    "pitch": p, "start": round(bar * bar_len + t, 4),
                    "duration": dur, "velocity": random.randint(55, 75),
                })
                t += dur + random.choice([0.25, 0.5])
        commands += [
            {"action": "create_midi_track", "name": "Melody"},
            {"action": "load_device", "track": track_idx, "uri": "Electric"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": mel_notes},
        ]
        track_idx += 1

    # ── Pad ──
    if elements.get("pad", True):
        pad_notes: list[dict] = []
        for bar in range(0, bars, 2):
            ch = voicings[(bar // 2) % len(voicings)] if elements.get("chords", True) else [key_root + 24, key_root + 28, key_root + 31]
            length = min(2, bars - bar) * bar_len
            for i, p in enumerate(ch[:3]):
                pad_notes.append({"pitch": p, "start": bar * bar_len,
                                  "duration": length, "velocity": 40 - i * 5})
        commands += [
            {"action": "create_midi_track", "name": "Ambient Pad"},
            {"action": "load_device", "track": track_idx, "uri": "Analog"},
            {"action": "create_midi_clip", "track": track_idx, "scene": 0, "length": bars, "notes": pad_notes},
        ]
        track_idx += 1

    commands.append({"action": "create_return_track", "name": "Reverb"})
    if settings.get("record_to_arrangement", True):
        commands.append({"action": "record_to_arrangement", "scene": 0, "bars": bars})
    else:
        commands.append({"action": "fire_scene", "scene": 0})
    return commands
