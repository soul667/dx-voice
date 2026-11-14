# DX Voice

**Ctrl → dictate. Ctrl+Win → a shell command. Alt+Win → DX/workspace actions. `dx v` → settings, context & history.**

Streaming voice input for Linux, standalone or as a [Dex](https://github.com/soul667/Dex) plugin. The terminal workspace is assembled from [Textual](https://textual.textualize.io/) widgets and the existing DX theme engine. Models are called through the official OpenAI SDK; local records and workspace indexing use SQLite.

[Live website](https://soul667.github.io/dx-voice/) · [Editable Figma workspace](https://www.figma.com/design/dTUUsl2mSeFExFV2VFQa6k?node-id=17-110) · [Product/reuse review](docs/product-review.md) · [Component library](design/README.md)

![dx v workspace design](design/terminal-workspace.png)

## What runs

- **Hold Ctrl for the configured threshold:** live dictation. Release to insert the final text into the original input field. No Enter is sent.
- **Hold Ctrl+Win for about 0.4 seconds:** dictate a command request (independent of long single-key `hotkey_hold_ms`). Terra returns only a command. It is copied by default, ready for manual paste. The app never runs it.
- **Hold Alt+Win for about 0.4 seconds:** experimental registered DX & workspace actions: local status queries, indexed workspace Git status (`workspace.status`), context inspection (`context.inspect`), and opening explicit documents/directories/URLs. Executes fixed registered `argv`, independently of command generation.
- **`dx v`:** terminal Overview (with live workspace context preview and one-click refresh), Voice, Rewrite, Command, Tools, History (with live search filtering), and Connection tabs. All settings stay centralized here; `~/.config/dx-voice/settings.txt` remains the private backing file without a separate GUI settings window.
- **Lightweight workspace context index:** locally tracks active X11 focus, terminal/editor `cwd` via `/proc`, and project folders via SQLite FTS5 (`~/.local/state/dx-voice/context.db`, mode `0600`). Automatically redacts secrets/tokens and excludes `.env`/key files, injecting workspace vocabulary and active-project hints into realtime ASR (via in-place `session.update` without reconnecting), optional cleanup, command generation, and DX actions—giving accurate domain terminology and homophone recovery without slow screenshots.
- **Optional light cleanup:** remove verbal fillers/repetition, fix technical/domain homophones using workspace context, and improve punctuation with a small model. Raw, fast dictation is the default; timeouts preserve the original text.
- **Opt-in screen context:** independently enable screenshot context in Rewrite. At release, capture runs on a background thread so UI/audio commit stays non-blocking; only the monitor containing the mouse pointer is resized and kept in RAM. Both `cleanup_mode` and `rewrite_use_screen` must be enabled.
- **Vocabulary and history:** prioritized user + workspace recognition hints; original/result records, search filtering, and re-copy actions in one local SQLite file.

Mouse-button/wheel activity and unrelated chords suppress dictation until Ctrl is released. Passive XI2 key/pointer events wake the hold watcher only while modifiers are active, keeping idle CPU near zero. Only HUD action buttons catch mouse input; the rest lets clicks/scroll through.

The HUD (**Carbon Fluid Glass**, `v0.6.0`) renders inside a fixed transparent X11 stage (`520×320`) as a single spring-morphing capsule at 60 FPS: an optional pre-hold charge pill (`arming`), compact active strip (`396×60`), and content-adaptive expanded card (`452×136..190`) with 24-bar harmonic waveforms, animated processing perimeter light beam, streaming text caret, animated checkmark stroke, tactile 3D keycaps (`Ctrl`, `Ctrl+Win`, `Alt+Win`), context chip, and luminance-adaptive smoked frosted glass. Terminal colors follow `dx tui.engine` with a card-based Overview dashboard, grouped settings sections, live HUD preview trigger, and master-detail History search.

## Install

Supported: GNOME/X11 Linux, PulseAudio or PipeWire's PulseAudio service, Python 3.10–3.12. Wayland/macOS/Windows support is not implemented. An API key with realtime transcription and Responses access is required; a chat-only compatible endpoint is insufficient.

```bash
sudo apt install python3-venv python3-gi python3-cairo python3-gi-cairo \
  gir1.2-gtk-3.0 gir1.2-pango-1.0 gir1.2-rsvg-2.0 pulseaudio-utils xdotool xclip x11-utils
# Optional tray icon:
sudo apt install gir1.2-ayatanaappindicator3-0.1

git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/dx-voice setup
.venv/bin/dx-voice tui
```

Enter your key in Connection, save with Ctrl+S, then start the service from Overview. Inter and Noto Sans SC provide the floating UI's reference typography. The Textual UI uses your terminal's font and respects its color capabilities.

## Dex integration

```bash
dx plugin install /absolute/path/to/dx-voice --enable
# Run once from the Python environment containing the dependencies:
.venv/bin/dx-voice setup
dx v
```

From a Dex checkout: `git submodule update --init plugins/voice`, then `dx plugin install builtin:voice --enable`. The plugin is an independent Git submodule at `plugins/voice`.

`dx v` and `dx voice` use the same implementation. The lightweight adapter can load under a newer Dex host Python; the audio process uses the interpreter recorded by setup. `DX_VOICE_PYTHON` can override that interpreter explicitly. Installing/enabling the CLI plugin alone does not start a microphone, make model calls or install missing dependencies.

## Settings

`dx v` is the primary interface. Every field from [settings.example.txt](settings.example.txt) is represented there. Save with Ctrl+S; changes apply to the next turn. `dx v settings --file` opens the underlying `~/.config/dx-voice/settings.txt` when direct editing is needed.

Important controls:

| Field | Meaning |
| --- | --- |
| `hotkey_hold_ms` | Hold threshold; default 400 ms |
| `cleanup_mode` | `none` fastest, or `light` optional cleanup |
| `cleanup_model` | Defaults to `gpt-5.4-nano` |
| `command_model` | Defaults to `gpt-6.1-terra` |
| `command_shell` | Target bash/fish/zsh/sh; defaults to a supported login shell |
| `command_output` | `clipboard` default, or `paste` into the original field; neither sends Enter |
| `vocabulary` | Comma-separated recognition hints (user entries prioritized ahead of indexed workspace terms) |
| `context_enabled` | `true` default; local SQLite FTS5 active-window and project context indexer |
| `context_roots` | Optional comma-separated project directories to index (auto-scans `~/project`, `~/Projects`, etc. when empty) |
| `history_enabled` | Local history on/off; on by default |
| `proxy_url` | Proxy used by the user service, if required |
| `theme` | Floating HUD frosted/light/dark/auto; terminal theme stays with DX |

Credentials stay in the private user config. A normal speech turn streams audio to the configured realtime endpoint. Cleanup and command mode additionally send the transcript/request to the chosen text model. Idle preconnection does not open the microphone.

## Local history and recovery

The single record file is `~/.local/state/dx-voice/history.db` (0600, parent directory 0700). Each turn records its time, mode, original, final output and outcome, rather than verbose debug traces. The History tab displays the latest 100 rows and can copy either original or result. Older rows are not automatically discarded. Cancelled turns retain status metadata, not interim speech.

Successful audio is deleted; failed audio stays in the private state directory for explicit retry. API keys, recordings and history are never part of the public repository. `last-transcript.txt` remains a small latest-result fallback.

```bash
dx v status
dx v context --refresh
dx v history --path
dx v history --limit 5
dx v command 'Find regular files larger than 1 GB under the current directory'
dx v stop
dx v start
dx v retry
```

`dx v command` prints the command alone; no generated shell command is executed. Syntax checking uses the target shell's parse-only mode with user startup config disabled where supported. Invalid/multiline/model-error output is not pasted as a command.

## Development and scope

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Preview the interactive React product showcase locally with `cd site && bun install && bun run dev` (or `bun run build && bun run preview` on `127.0.0.1:8765`).

Tests use temporary private files, a loopback WebSocket fixture and Textual's headless pilot. They make no paid model calls. Coverage includes key-chord mode selection/release order, mouse precedence, settings masking/save validation, private history, copying commands without execution, model-failure fallback, connection reuse and target-window protection.

The [product review](docs/product-review.md) compares Handy, OpenWhispr, VoiceInk and the commercial Wispr Flow experience, and separates shipped functionality from future work. Todo extraction and agent dispatch are future work, not hidden side effects of dictation.

A prior synthetic realtime test inserted text about 0.94 seconds after release. Separate synthetic probes returned cleanup in about 2.8 seconds and a simple Terra command in about 3.6 seconds. These are examples, not human-speech accuracy or latency guarantees.

MIT. Dependencies retain their own licenses.

## Module boundaries

`modules/asr.py` defines the speech backend factory. OpenAI is the only bundled provider; installed adapters can register the `dx_voice.asr` entry-point group. Audio capture prefers `parec` (PulseAudio/PipeWire) with `arecord` raw fallback, and the realtime client maintains a warm WebSocket with a blocking reader thread and in-place `session.update` refreshes. `context.py`, `rewrite.py`, `command.py` and `tools.py` own their separate workflows.

The frosted HUD uses MSS + Pillow (downsampled 4× and blurred in-memory via Cairo BGRA pixels) to tint a small local background snapshot with dark/light luminance adaptation when it appears. This local visual effect does not upload background pixels; model screenshot context has its own default-off switch.

`dx v modules`, `dx v asr providers`, `dx v context` and `dx v tools list` show supported modules/providers/context/actions. Arbitrary shell execution, arbitrary agent dispatch and automatic todo execution are not implemented.
