"""LiveMind MIDI Remote Script for Ableton Live 12.

Installation:
    Copy this entire 'LiveMind' folder to:
        macOS:  ~/Music/Ableton/User Library/Remote Scripts/LiveMind/
        Windows: ~\\Documents\\Ableton\\User Library\\Remote Scripts\\LiveMind\\

    Then in Ableton Live → Preferences → Link/Tempo/MIDI → Control Surface:
        Select "LiveMind" from the dropdown.

This script starts a UDP listener inside Ableton that receives JSON commands
from the LiveMind desktop app and executes them via the Live Object Model.
All communication uses plain UDP + JSON (no external dependencies).
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import traceback
from typing import Any

# Ableton's Python environment provides these.
# These imports only work inside Ableton Live.
try:
    from _Framework.ControlSurface import ControlSurface  # type: ignore[import-untyped]
    import Live  # type: ignore[import-untyped]
except ImportError:
    # Allow importing outside Ableton for syntax checking.
    ControlSurface = object  # type: ignore[assignment,misc]

RECV_PORT = 11000  # LiveMind app sends commands here.
SEND_PORT = 11001  # We send responses/state back here.
SEND_HOST = "127.0.0.1"
BUFFER_SIZE = 65536


def create_instance(c_instance: Any) -> LiveMindControlSurface:
    """Factory function called by Ableton Live on script load."""
    return LiveMindControlSurface(c_instance)


class LiveMindControlSurface(ControlSurface):  # type: ignore[misc]
    """Remote Script that bridges LiveMind ↔ Ableton Live via UDP."""

    def __init__(self, c_instance: Any) -> None:
        super().__init__(c_instance)
        self._sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_recv.bind(("127.0.0.1", RECV_PORT))
        self._sock_recv.settimeout(0.5)
        self._sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._stop = threading.Event()
        self._listener = threading.Thread(target=self._listen, daemon=True, name="livemind-udp")
        self._listener.start()
        self.log_message("LiveMind Remote Script loaded — listening on port %d" % RECV_PORT)

    def disconnect(self) -> None:
        self._stop.set()
        self._sock_recv.close()
        self._sock_send.close()
        self.log_message("LiveMind Remote Script disconnected")
        super().disconnect()

    # ── UDP listener ────────────────────────────────────────────────────

    def _listen(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock_recv.recvfrom(BUFFER_SIZE)
                command = json.loads(data.decode("utf-8"))
                # schedule_message only accepts (delay, callback) or (delay, callback, one_param).
                # Bundle command+addr into a single parameter via lambda.
                self.schedule_message(0, lambda cmd=command, a=addr: self._handle_command(cmd, a))
            except socket.timeout:
                continue
            except Exception:
                self.log_message("LiveMind recv error: %s" % traceback.format_exc())

    def _handle_command(self, command: dict[str, Any], addr: tuple[str, int]) -> None:
        try:
            result = self._dispatch(command)
            self._respond(result, addr)
        except Exception as exc:
            self._respond({"error": str(exc)}, addr)

    def _respond(self, payload: dict[str, Any], addr: tuple[str, int]) -> None:
        data = json.dumps(payload).encode("utf-8")
        try:
            # Respond to the actual sender (host + port) so the calling
            # socket receives the reply, not a hard-coded port.
            self._sock_send.sendto(data, addr)
        except Exception:
            pass

    # ── Command dispatch ────────────────────────────────────────────────

    def _dispatch(self, cmd: dict[str, Any]) -> dict[str, Any]:
        action = cmd.get("action", "")
        song = self.song()  # type: ignore[attr-defined]  # Live.Song.Song

        if action == "ping":
            return {"status": "ok", "tempo": song.tempo, "tracks": len(song.tracks)}

        if action == "get_session_state":
            return self._get_session_state(song)

        if action == "create_midi_track":
            idx = cmd.get("index", -1)
            song.create_midi_track(idx if idx >= 0 else len(song.tracks))
            track = song.tracks[idx if idx >= 0 else -1]
            if cmd.get("name"):
                track.name = cmd["name"]
            return {"status": "ok", "detail": "MIDI track created", "index": list(song.tracks).index(track)}

        if action == "create_audio_track":
            idx = cmd.get("index", -1)
            song.create_audio_track(idx if idx >= 0 else len(song.tracks))
            track = song.tracks[idx if idx >= 0 else -1]
            if cmd.get("name"):
                track.name = cmd["name"]
            return {"status": "ok", "detail": "Audio track created", "index": list(song.tracks).index(track)}

        if action == "create_return_track":
            song.create_return_track()
            track = song.return_tracks[-1]
            if cmd.get("name"):
                track.name = cmd["name"]
            return {"status": "ok", "detail": "Return track created"}

        if action == "delete_track":
            idx = cmd["index"]
            song.delete_track(idx)
            return {"status": "ok", "detail": f"Track {idx} deleted"}

        if action == "set_track_name":
            song.tracks[cmd["index"]].name = cmd["name"]
            return {"status": "ok"}

        if action == "set_track_volume":
            track = song.tracks[cmd["index"]]
            track.mixer_device.volume.value = max(0.0, min(1.0, cmd["value"]))
            return {"status": "ok"}

        if action == "set_track_pan":
            track = song.tracks[cmd["index"]]
            track.mixer_device.panning.value = max(-1.0, min(1.0, cmd["value"]))
            return {"status": "ok"}

        if action == "arm_track":
            song.tracks[cmd["index"]].arm = True
            return {"status": "ok"}

        if action == "mute_track":
            song.tracks[cmd["index"]].mute = cmd.get("muted", True)
            return {"status": "ok"}

        if action == "solo_track":
            song.tracks[cmd["index"]].solo = cmd.get("soloed", True)
            return {"status": "ok"}

        if action == "load_device":
            track_idx = cmd.get("track", 0)
            track = song.tracks[track_idx]
            uri = cmd.get("uri", "")
            if not uri:
                return {"error": "load_device requires a 'uri' parameter"}
            song.view.selected_track = track
            app = Live.Application.get_application()
            browser = app.browser
            item = self._find_browser_item(uri, browser.instruments)
            if not item:
                item = self._find_browser_item(uri, browser.audio_effects)
            if not item:
                item = self._find_browser_item(uri, browser.midi_effects)
            if not item:
                item = self._find_browser_item(uri, browser.drums)
            if item:
                browser.load_item(item)
                return {"status": "ok", "detail": "Loaded %s on track %d" % (item.name, track_idx)}
            return {"error": "Device '%s' not found in browser" % uri}

        if action == "set_device_param":
            track = song.tracks[cmd["track"]]
            device = track.devices[cmd["device"]]
            param = device.parameters[cmd["param"]]
            param.value = max(param.min, min(param.max, cmd["value"]))
            return {"status": "ok"}

        if action == "delete_device":
            track = song.tracks[cmd["track"]]
            track.delete_device(cmd["device"])
            return {"status": "ok"}

        if action == "create_midi_clip":
            track = song.tracks[cmd["track"]]
            if not track.has_midi_input:
                return {"error": "MIDI clips can only be created on MIDI tracks"}
            scene_idx = cmd["scene"]
            # Ensure enough scenes exist.
            while len(song.scenes) <= scene_idx:
                song.create_scene(-1)
            clip_slot = track.clip_slots[scene_idx]
            if clip_slot.has_clip:
                clip_slot.delete_clip()
            length = float(cmd.get("length", 4.0))
            clip_slot.create_clip(length)
            clip = clip_slot.clip
            clip.name = cmd.get("name", "LiveMind")
            # Add notes.
            notes = cmd.get("notes", [])
            if notes:
                clip.deselect_all_notes()
                for n in notes:
                    pitch = int(n.get("pitch", 60))
                    start = float(n.get("start", 0))
                    dur = float(n.get("duration", 1))
                    vel = int(n.get("velocity", 100))
                    # Live API: add_new_notes expects a tuple-of-tuples.
                    clip.set_notes(((pitch, start, dur, vel, False),))
            return {"status": "ok", "detail": f"MIDI clip created on track {cmd['track']} scene {scene_idx}"}

        if action == "delete_clip":
            track = song.tracks[cmd["track"]]
            track.clip_slots[cmd["scene"]].delete_clip()
            return {"status": "ok"}

        if action == "fire_clip":
            track = song.tracks[cmd["track"]]
            track.clip_slots[cmd["scene"]].fire()
            return {"status": "ok"}

        if action == "stop_clip":
            track = song.tracks[cmd["track"]]
            track.clip_slots[cmd["scene"]].stop()
            return {"status": "ok"}

        if action == "fire_scene":
            song.scenes[cmd["scene"]].fire()
            return {"status": "ok"}

        if action == "create_scene":
            song.create_scene(cmd.get("index", -1))
            return {"status": "ok"}

        if action == "play":
            song.start_playing()
            return {"status": "ok"}

        if action == "stop":
            song.stop_playing()
            return {"status": "ok"}

        if action == "set_tempo":
            song.tempo = max(20.0, min(999.0, float(cmd["bpm"])))
            return {"status": "ok", "tempo": song.tempo}

        return {"error": f"Unknown action: {action}"}

    # ── State reporting ─────────────────────────────────────────────────

    def _find_browser_item(self, name: str, root: Any, depth: int = 0) -> Any:
        """Recursively search browser tree for a device by name (max depth 3)."""
        if depth > 3:
            return None
        try:
            for item in root.children:
                if name.lower() == item.name.lower() and item.is_loadable:
                    return item
            # Partial match on second pass.
            for item in root.children:
                if name.lower() in item.name.lower() and item.is_loadable:
                    return item
            # Recurse into children.
            for item in root.children:
                found = self._find_browser_item(name, item, depth + 1)
                if found:
                    return found
        except Exception:
            pass
        return None

    def _get_session_state(self, song: Any) -> dict[str, Any]:
        tracks = []
        for i, track in enumerate(song.tracks):
            devices = []
            for d in track.devices:
                devices.append({"name": d.name, "class_name": d.class_display_name})
            clips = []
            for j, slot in enumerate(track.clip_slots):
                if slot.has_clip:
                    clip = slot.clip
                    clips.append({"scene": j, "name": clip.name, "length": clip.length, "is_playing": clip.is_playing})
            tracks.append({
                "index": i,
                "name": track.name,
                "is_midi": track.has_midi_input,
                "is_armed": track.arm,
                "is_muted": track.mute,
                "is_soloed": track.solo,
                "volume": track.mixer_device.volume.value,
                "pan": track.mixer_device.panning.value,
                "devices": devices,
                "clips": clips,
            })
        return {
            "status": "ok",
            "tempo": song.tempo,
            "is_playing": song.is_playing,
            "track_count": len(song.tracks),
            "scene_count": len(song.scenes),
            "tracks": tracks,
        }
