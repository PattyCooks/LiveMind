"""Tests for music theory utilities and MIDI generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from livemind.midi import (
    build_chord,
    build_scale,
    chord_progression,
    midi_to_note_name,
    note_name_to_midi,
    snap_to_scale,
)
from livemind.midi.generator import (
    Note,
    generate_chord_progression_midi,
    generate_drum_pattern_midi,
    generate_melody_midi,
    notes_from_json,
    notes_to_midi,
    save_midi,
)
from livemind.ableton.commands import extract_commands, strip_commands


class TheoryTests(unittest.TestCase):
    def test_note_name_to_midi(self) -> None:
        self.assertEqual(note_name_to_midi("C4"), 60)
        self.assertEqual(note_name_to_midi("A4"), 69)
        self.assertEqual(note_name_to_midi("C-1"), 0)
        self.assertEqual(note_name_to_midi("G9"), 127)
        self.assertEqual(note_name_to_midi("F#3"), 54)
        self.assertEqual(note_name_to_midi("Bb5"), 82)

    def test_midi_to_note_name(self) -> None:
        self.assertEqual(midi_to_note_name(60), "C4")
        self.assertEqual(midi_to_note_name(69), "A4")
        self.assertEqual(midi_to_note_name(0), "C-1")

    def test_round_trip(self) -> None:
        for midi_num in [0, 36, 48, 60, 72, 84, 127]:
            name = midi_to_note_name(midi_num)
            self.assertEqual(note_name_to_midi(name), midi_num)

    def test_build_scale_c_major(self) -> None:
        scale = build_scale("C", "major", 4)
        self.assertEqual(scale, [60, 62, 64, 65, 67, 69, 71])

    def test_build_scale_a_minor(self) -> None:
        scale = build_scale("A", "minor", 4)
        self.assertEqual(scale, [69, 71, 72, 74, 76, 77, 79])

    def test_build_chord_c_major(self) -> None:
        chord = build_chord("C", "major", 4)
        self.assertEqual(chord, [60, 64, 67])

    def test_build_chord_a_minor(self) -> None:
        chord = build_chord("A", "minor", 3)
        self.assertEqual(chord, [57, 60, 64])

    def test_build_chord_seventh(self) -> None:
        chord = build_chord("G", "7", 3)
        self.assertEqual(chord, [55, 59, 62, 65])

    def test_chord_progression(self) -> None:
        chords = chord_progression("C", "major", [1, 4, 5, 1], octave=4)
        self.assertEqual(len(chords), 4)
        self.assertEqual(chords[0][0], 60)  # C root

    def test_snap_to_scale_in_scale(self) -> None:
        self.assertEqual(snap_to_scale(60, "C", "major"), 60)  # C is in C major

    def test_snap_to_scale_out_of_scale(self) -> None:
        snapped = snap_to_scale(61, "C", "major")  # C# not in C major
        self.assertIn(snapped, [60, 62])  # Should snap to C or D

    def test_unknown_scale_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_scale("C", "doesnt_exist")

    def test_unknown_chord_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_chord("C", "doesnt_exist")


class MidiGeneratorTests(unittest.TestCase):
    def test_notes_from_json(self) -> None:
        data = [
            {"pitch": 60, "start": 0, "duration": 1, "velocity": 100},
            {"pitch": "E4", "start": 1, "duration": 0.5},
        ]
        notes = notes_from_json(data)
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0].pitch, 60)
        self.assertEqual(notes[1].pitch, 64)

    def test_notes_to_midi_creates_valid_file(self) -> None:
        notes = [Note(pitch=60, start=0, duration=1), Note(pitch=64, start=1, duration=1)]
        mid = notes_to_midi(notes)
        self.assertEqual(len(mid.tracks), 1)
        # Should have tempo + note_on + note_off events.
        messages = [m for m in mid.tracks[0] if not m.is_meta]
        self.assertEqual(len(messages), 4)

    def test_save_midi_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            notes = [Note(pitch=60, start=0, duration=1)]
            path = save_midi(notes, filename="test.mid", output_dir=tmpdir)
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "test.mid")

    def test_generate_chord_progression_midi(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path, notes = generate_chord_progression_midi(
                root="C", scale_type="minor", degrees=[1, 4, 5, 1],
                bpm=120, filename="chords.mid",
            )
            # Just check it returns notes and the path has .mid extension.
            self.assertGreater(len(notes), 0)
            self.assertTrue(str(path).endswith(".mid"))

    def test_generate_drum_pattern_midi(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pattern = {"kick": [0, 2], "snare": [1, 3], "closed_hat": [0, 0.5, 1, 1.5]}
            path, notes = generate_drum_pattern_midi(pattern=pattern, bpm=128)
            self.assertGreater(len(notes), 0)
            # Drum notes should be on channel 9.
            self.assertTrue(all(n.channel == 9 for n in notes))


class CommandParserTests(unittest.TestCase):
    def test_extract_commands_from_fenced_block(self) -> None:
        text = '''Here's what I'll do:

```commands
[{"action": "create_midi_track", "name": "Bass"}, {"action": "set_tempo", "bpm": 128}]
```

Done!'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["action"], "create_midi_track")

    def test_extract_commands_from_json_block(self) -> None:
        text = '''```json
[{"action": "play"}]
```'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 1)

    def test_extract_commands_empty(self) -> None:
        self.assertEqual(extract_commands("Just some text, no commands."), [])

    def test_strip_commands(self) -> None:
        text = '''Hello!

```commands
[{"action": "play"}]
```

Done!'''
        stripped = strip_commands(text)
        self.assertNotIn("commands", stripped)
        self.assertIn("Hello!", stripped)
        self.assertIn("Done!", stripped)

    def test_normalize_command_alias(self) -> None:
        """LLMs sometimes use 'command' instead of 'action' as the key."""
        text = '''```commands
[{"command": "create_midi_track", "name": "Bass"}, {"cmd": "set_tempo", "bpm": 128}]
```'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["action"], "create_midi_track")
        self.assertEqual(commands[1]["action"], "set_tempo")

    def test_normalize_skips_empty_action(self) -> None:
        """Commands with no recognizable action key are silently dropped."""
        text = '''```commands
[{"foo": "bar"}, {"action": "play"}]
```'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["action"], "play")

    def test_json_with_comments(self) -> None:
        """LLMs sometimes inject // comments into JSON."""
        text = '''```commands
[
  // Set up the project
  {"action": "set_tempo", "bpm": 140},
  {"action": "create_midi_track", "name": "Bass"}, // bass track
]
```'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["action"], "set_tempo")
        self.assertEqual(commands[1]["action"], "create_midi_track")

    def test_hallucinated_action_mapping(self) -> None:
        """Hallucinated actions like 'create_track' map to valid ones."""
        text = '''```commands
[{"action": "create_track", "name": "Lead"}, {"action": "create_aux_track", "name": "FX"}]
```'''
        commands = extract_commands(text)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["action"], "create_midi_track")
        self.assertEqual(commands[1]["action"], "create_return_track")


if __name__ == "__main__":
    unittest.main()
