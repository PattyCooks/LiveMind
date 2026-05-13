# ⚡ LiveMind

**Free, local-first AI assistant for Ableton Live 12.** Chat naturally, generate MIDI, control your session — all from your machine. No subscriptions, no cloud required.

An open-source alternative to Yuma / AbletonGPT.

---

## Features

- **AI Chat Interface** — talk naturally about music production: *"Create a deep house chord progression in C minor"*, *"Add a reverb on track 5"*, *"Build me a four-on-the-floor techno pattern"*
- **Ableton Live 12 Control** — create tracks, load devices from the browser, insert MIDI clips with notes, adjust parameters, trigger scenes, read session state via a MIDI Remote Script bridge
- **MIDI Generation** — chord progressions, drum patterns, melodies exported as `.mid` files (drag into Ableton or auto-insert)
- **Music Theory Engine** — scales, chords, intervals, GM drum mapping, scale-snapping
- **Smart Command Parsing** — handles LLM quirks: strips JSON comments, fixes trailing commas, maps hallucinated commands to valid ones, normalizes key aliases
- **Device Loading** — loads Ableton instruments (Wavetable, Operator, Drum Rack) and effects (Reverb, Compressor, EQ Eight, Limiter) via the browser API
- **Local LLM (Ollama)** — runs fully offline with Llama 3.1, Mistral, Command-R, Phi-3, etc.
- **Cloudflare Workers AI** — optional free-tier cloud inference (`@cf/meta/llama-3.1-70b-instruct`, Gemma, Mistral)
- **Native macOS UI** — Ableton-dark themed CustomTkinter app
- **Settings Panel** — choose provider, model, temperature, Ableton ports, MIDI output dir
- **Safety** — destructive commands require confirmation, sandboxed execution

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/PattyCooks/LiveMind.git
cd LiveMind
pip install -r requirements.txt
```

Requires **Python 3.10+** (Apple Silicon and Intel).

### 2. Set up a local LLM

Install [Ollama](https://ollama.com/download):

```bash
# Install Ollama (if not already)
brew install ollama

# Pull a model
ollama pull llama3.1

# Start Ollama (runs on http://127.0.0.1:11434)
ollama serve
```

### 3. Install the Ableton Remote Script

Copy the Remote Script folder into Ableton's User Library:

```bash
cp -r remote_script/LiveMind ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

Then in **Ableton Live 12**:
1. Go to **Preferences → Link/Tempo/MIDI**
2. Under **Control Surface**, select **LiveMind** from the dropdown
3. No input/output device needed — communication is via UDP

### 4. Run LiveMind

```bash
python run.py
```

The GUI opens with the chat panel. Type a message and hit ⌘+Enter (or click Send).

---

## How It Works

```
┌──────────────┐     UDP/JSON      ┌──────────────────────┐
│   LiveMind   │ ◄──────────────► │  Ableton Live 12      │
│   Desktop    │   port 11000/01   │  (Remote Script)      │
│   App        │                   │  LiveMind/__init__.py  │
└──────┬───────┘                   └──────────────────────┘
       │
       │  HTTP
       ▼
┌──────────────┐
│  Ollama /    │
│  Cloudflare  │
│  Workers AI  │
└──────────────┘
```

1. You type a message in the chat
2. LiveMind sends it to the LLM with a system prompt that includes available Ableton commands
3. The LLM responds with natural text + structured command blocks
4. LiveMind parses the commands and sends them to the Remote Script inside Ableton via UDP
5. The Remote Script executes Live API calls and returns results
6. MIDI generation happens locally — `.mid` files are saved and can be dragged into Ableton

---

## Project Structure

```
LiveMind/
├── run.py                          # Entry point
├── requirements.txt
├── livemind/
│   ├── __init__.py
│   ├── app.py                      # Main orchestrator
│   ├── config.py                   # ~/.livemind/config.json
│   ├── gui/
│   │   ├── __init__.py             # Theme constants
│   │   ├── main_window.py          # Sidebar + content panels
│   │   ├── chat_panel.py           # Chat interface
│   │   └── settings_panel.py       # Settings UI
│   ├── llm/
│   │   ├── __init__.py             # LLMProvider base class
│   │   ├── ollama_provider.py      # Ollama HTTP client
│   │   ├── cloudflare_provider.py  # Cloudflare Workers AI client
│   │   └── prompts.py              # System prompts for Ableton control
│   ├── ableton/
│   │   ├── __init__.py             # AbletonBridge (UDP client)
│   │   └── commands.py             # Command parser + executor
│   └── midi/
│       ├── __init__.py             # Music theory (scales, chords, etc.)
│       └── generator.py            # MIDI file generation
├── remote_script/
│   └── LiveMind/
│       └── __init__.py             # Ableton MIDI Remote Script
└── tests/
    └── __init__.py                 # 26 tests (theory, MIDI gen, command parsing)
```

---

## Configuration

Settings are stored at `~/.livemind/config.json`. You can edit them in the Settings panel or directly:

| Key | Default | Description |
|-----|---------|-------------|
| `llm_provider` | `ollama` | `ollama` or `cloudflare` |
| `ollama_url` | `http://127.0.0.1:11434` | Ollama server URL |
| `ollama_model` | `llama3.1` | Model name |
| `cloudflare_account_id` | — | Your CF account ID |
| `cloudflare_api_token` | — | Workers AI API token |
| `cloudflare_model` | `@cf/meta/llama-3.1-70b-instruct` | CF model identifier |
| `ableton_send_port` | `11000` | UDP port the Remote Script listens on |
| `ableton_recv_port` | `11001` | UDP port LiveMind listens on for responses |
| `temperature` | `0.7` | LLM sampling temperature |
| `max_tokens` | `2048` | Max response tokens |
| `confirm_destructive` | `true` | Ask before deleting tracks/clips |
| `midi_output_dir` | `~/.livemind/midi` | Where generated .mid files are saved |

---

## Cloudflare Workers AI Setup (Optional)

For faster inference or if you don't have a GPU:

1. Create a free [Cloudflare account](https://dash.cloudflare.com/sign-up)
2. Go to **AI → Workers AI** in the dashboard
3. Copy your **Account ID** (from the sidebar)
4. Create an **API Token** with Workers AI permissions
5. Enter both in LiveMind's Settings panel

Free tier includes 10,000 neurons/day — enough for ~100+ chat messages.

---

## Available Ableton Commands

The LLM can generate these commands automatically from natural language:

| Command | Parameters | Description |
|---------|-----------|-------------|
| `create_midi_track` | name, index? | Create a new MIDI track |
| `create_audio_track` | name, index? | Create a new audio track |
| `create_return_track` | name | Create a return track |
| `delete_track` | index | Delete a track |
| `set_track_volume` | index, value (0–1) | Set track volume |
| `set_track_pan` | index, value (-1 to 1) | Set track pan |
| `arm_track` | index | Arm a track for recording |
| `mute_track` | index, muted | Mute/unmute |
| `solo_track` | index, soloed | Solo/unsolo |
| `load_device` | track, uri | Load a device (name-based) |
| `set_device_param` | track, device, param, value | Set a device parameter |
| `create_midi_clip` | track, scene, length, notes | Insert a MIDI clip with notes |
| `fire_clip` | track, scene | Launch a clip |
| `fire_scene` | scene | Launch a scene |
| `play` | — | Start transport |
| `stop` | — | Stop transport |
| `set_tempo` | bpm | Change tempo |
| `generate_midi_file` | type, ...params | Export a .mid file locally |
| `get_session_state` | — | Read current session info |

---

## Example Prompts

```
Create a deep house chord progression in C minor with 7th chords

Build me a techno kick pattern at 128 BPM with an offbeat hi-hat

Make a return track called "Hall Verb" and route track 1 to it

What scale would work for a dark melodic techno track?

Set the tempo to 140 and create 4 MIDI tracks: Bass, Lead, Pads, Drums

Generate a melody in F# minor pentatonic, 8 bars, for the lead track
```

---

## Tests

```bash
python -m unittest tests -v
```

26 tests covering music theory, MIDI generation, command parsing, JSON comment stripping, and hallucinated action mapping.

---

## Recommended Models

| Model | Size | Best For | Provider |
|-------|------|----------|----------|
| Llama 3.1 70B | 40GB | Most capable, best for complex tasks | Ollama / CF |
| Llama 3.1 8B | 5GB | Fast, good for simple commands | Ollama / CF |
| Mistral 7B | 4GB | Fast, decent music knowledge | Ollama / CF |
| Command-R | 35GB | Strong instruction following | Ollama |
| Phi-3 Medium | 8GB | Good balance of speed/quality | Ollama |

---

## License

MIT
