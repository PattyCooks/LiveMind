#!/usr/bin/env python3
"""LiveMind — AI assistant for Ableton Live 12.

Usage:
    python run.py
"""

from livemind.app import LiveMindApp


def main() -> None:
    app = LiveMindApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
