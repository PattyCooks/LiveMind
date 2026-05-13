"""UDP bridge to the LiveMind Remote Script running inside Ableton Live."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Callable


class AbletonBridge:
    """Sends JSON commands to the Ableton Remote Script and receives state updates."""

    def __init__(
        self,
        ableton_host: str = "127.0.0.1",
        send_port: int = 11000,
        recv_port: int = 11001,
    ) -> None:
        self.ableton_host = ableton_host
        self.send_port = send_port
        self.recv_port = recv_port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(5.0)
        self._listener: socket.socket | None = None
        self._listen_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._connected = False
        self._last_state: dict[str, Any] = {}

    # ── Connection ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin listening for responses from Ableton."""
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", self.recv_port))
        self._listener.settimeout(1.0)
        self._stop.clear()
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="ableton-recv")
        self._listen_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._listener:
            self._listener.close()

    def _listen_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _ = self._listener.recvfrom(65536)  # type: ignore[union-attr]
                payload = json.loads(data.decode("utf-8"))
                self._last_state = payload
                self._connected = True
                for cb in self._callbacks:
                    try:
                        cb(payload)
                    except Exception:
                        pass
            except socket.timeout:
                continue
            except OSError:
                break

    def on_state_update(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_state(self) -> dict[str, Any]:
        return self._last_state

    # ── Send commands ───────────────────────────────────────────────────

    def send(self, command: dict[str, Any]) -> dict[str, Any] | None:
        """Send a command to the Ableton Remote Script. Returns response if received within timeout."""
        payload = json.dumps(command).encode("utf-8")
        self._sock.sendto(payload, (self.ableton_host, self.send_port))
        try:
            data, _ = self._sock.recvfrom(65536)
            resp = json.loads(data.decode("utf-8"))
            self._connected = True
            return resp
        except socket.timeout:
            return None

    def send_batch(self, commands: list[dict[str, Any]]) -> list[dict[str, Any] | None]:
        """Send multiple commands sequentially."""
        return [self.send(cmd) for cmd in commands]

    # ── Convenience helpers ─────────────────────────────────────────────

    def ping(self) -> bool:
        """Check if the Remote Script is responding."""
        resp = self.send({"action": "ping"})
        return resp is not None and resp.get("status") == "ok"

    def get_session_state(self) -> dict[str, Any] | None:
        return self.send({"action": "get_session_state"})

    def create_midi_track(self, name: str, index: int = -1) -> dict[str, Any] | None:
        return self.send({"action": "create_midi_track", "name": name, "index": index})

    def create_audio_track(self, name: str, index: int = -1) -> dict[str, Any] | None:
        return self.send({"action": "create_audio_track", "name": name, "index": index})

    def create_return_track(self, name: str) -> dict[str, Any] | None:
        return self.send({"action": "create_return_track", "name": name})

    def set_track_volume(self, index: int, value: float) -> dict[str, Any] | None:
        return self.send({"action": "set_track_volume", "index": index, "value": value})

    def set_track_pan(self, index: int, value: float) -> dict[str, Any] | None:
        return self.send({"action": "set_track_pan", "index": index, "value": value})

    def arm_track(self, index: int) -> dict[str, Any] | None:
        return self.send({"action": "arm_track", "index": index})

    def mute_track(self, index: int, muted: bool = True) -> dict[str, Any] | None:
        return self.send({"action": "mute_track", "index": index, "muted": muted})

    def solo_track(self, index: int, soloed: bool = True) -> dict[str, Any] | None:
        return self.send({"action": "solo_track", "index": index, "soloed": soloed})

    def load_device(self, track: int, uri: str) -> dict[str, Any] | None:
        return self.send({"action": "load_device", "track": track, "uri": uri})

    def set_device_param(self, track: int, device: int, param: int, value: float) -> dict[str, Any] | None:
        return self.send({"action": "set_device_param", "track": track, "device": device, "param": param, "value": value})

    def create_midi_clip(self, track: int, scene: int, length: float, notes: list[dict]) -> dict[str, Any] | None:
        return self.send({"action": "create_midi_clip", "track": track, "scene": scene, "length": length, "notes": notes})

    def fire_clip(self, track: int, scene: int) -> dict[str, Any] | None:
        return self.send({"action": "fire_clip", "track": track, "scene": scene})

    def fire_scene(self, scene: int) -> dict[str, Any] | None:
        return self.send({"action": "fire_scene", "scene": scene})

    def play(self) -> dict[str, Any] | None:
        return self.send({"action": "play"})

    def stop_playback(self) -> dict[str, Any] | None:
        return self.send({"action": "stop"})

    def set_tempo(self, bpm: float) -> dict[str, Any] | None:
        return self.send({"action": "set_tempo", "bpm": bpm})
