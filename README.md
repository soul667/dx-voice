# DX Voice

**Hold Ctrl. Speak. Release.** Streaming dictation for Linux, standalone or as a [Dex](https://github.com/soul667/Dex) plugin.

DX Voice streams microphone PCM to a realtime transcription API, previews words as they arrive, and pastes the final text into the window where dictation started. It does not press Enter or send your message.

> Alpha. The working GTK interface is a prototype. The new [Figma component library](https://www.figma.com/design/dTUUsl2mSeFExFV2VFQa6k) is the design source for the next UI; it has not yet been implemented in GTK.

## Design

![DX Voice design library](design/cover.png)

[Open the editable Figma library](https://www.figma.com/design/dTUUsl2mSeFExFV2VFQa6k?node-id=8-2) · [Design and component mapping](design/README.md)

Seven component families, 22 variants, seven swappable icons, and semantic light/dark variables. The design references the lightweight surfaces, voice feedback, and explicit completion states of [Doubao Input](https://ime.doubao.com/pc), alongside the desktop simplicity of [Handy](https://github.com/cjpais/Handy). No third-party logos or product screenshots are shipped in this repository.

## Supported environment

- Linux with a GNOME/X11 desktop; Python 3.10–3.12.
- PulseAudio, or PipeWire with its PulseAudio compatibility service.
- An API key with realtime transcription access. A ChatGPT login alone is not an API key.
- Wayland, Windows and macOS support are not implemented.

Install system dependencies on Ubuntu:

```bash
sudo apt install python3-venv python3-gi python3-cairo gir1.2-gtk-3.0 \
  gir1.2-pango-1.0 pulseaudio-utils xdotool xclip x11-utils
# Optional tray icon:
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

Install the Python package with access to the system GTK bindings:

```bash
git clone https://github.com/soul667/dx-voice.git
cd dx-voice
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/dx-voice doctor
.venv/bin/dx-voice setup
.venv/bin/dx-voice settings
```

Put your API key in `~/.config/dx-voice/settings.txt`, then start:

```bash
.venv/bin/dx-voice start
```

`setup` writes user-level service and desktop files. `start` explicitly enables the service at graphical login. Neither command installs missing dependencies or downloads a speech model.

## Dex plugin

The repository includes a native Dex CLI manifest. Installing the plugin only registers commands; it does not start a microphone or connect to the speech API.

```bash
dx plugin install /absolute/path/to/dx-voice --enable
dx voice doctor
dx voice setup
dx voice settings
dx voice start
dx voice status
```

Run setup from the package virtualenv once to record its interpreter. Alternatively, set `DX_VOICE_PYTHON` to the Python executable with GTK and the required packages installed. `dx voice` delegates to the same `dx_voice.cli` implementation as `dx-voice`. The lightweight Dex adapter can load under a newer host Python; the audio process still requires Python 3.10–3.12.

The parent Dex repository includes this project at `plugins/voice` as an independent Git submodule. Use `git submodule update --init plugins/voice` when working from a Dex checkout, then `dx plugin install builtin:voice --enable`.

## Dictation

Focus your input field, hold either Ctrl for about 0.4 seconds, then speak. Release Ctrl to finalize and insert the text. A tap or a normal Ctrl+C/V shortcut does not start dictation. Pressing another key during recording cancels that recording.

The waveform is driven by actual microphone audio. Interim words are previews; only the final transcript is inserted. If the active window changes, the result is copied to the clipboard rather than pasted into a different window. The clipboard's current content is replaced.

The realtime connection is prepared while idle. The microphone is opened only after dictation is triggered. Audio is sent to the configured cloud endpoint during recording; this is not offline speech recognition.

## Settings and recovery

See [settings.example.txt](settings.example.txt). Important fields:

| Setting | Purpose |
| --- | --- |
| `api_key` | Your API key; stored only in the private user config |
| `base_url` | OpenAI-compatible base URL, including `/v1` |
| `realtime_model` | Defaults to `gpt-live-transcribe` |
| `realtime_delay` | `low` balances accuracy and delay; `minimal` prioritizes speed |
| `source` | PulseAudio microphone name; empty uses the system default |
| `proxy_url` | Optional proxy for the user service, e.g. `http://127.0.0.1:7890` |
| `max_seconds` | Default 300 seconds, capped at 600 |
| `model` | File-transcription model used only for manual retries |

An API-compatible chat endpoint may not implement realtime audio. This application requires the transcription WebSocket endpoint described in the [OpenAI realtime transcription documentation](https://developers.openai.com/api/docs/guides/realtime-transcription).

Successful recordings are deleted. Failed recordings remain under `~/.local/state/dx-voice/`, with the latest final text in `last-transcript.txt`. `dx voice retry` explicitly uploads the most recent failed recording through the file API and can incur another API charge. It does not silently pretend that a file upload is realtime.

```bash
dx voice stop
dx voice start
dx voice cancel
dx voice retry
```

For the earlier local prototype, `dx voice setup --migrate` copies the private settings file and stops its user service. This is explicit and does not publish the file. Start DX Voice afterwards. Roll back by stopping `dx-voice.service` and re-enabling `openai-voice-input.service`; the old settings remain intact.

## Development

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary configs and a loopback WebSocket server; they make no paid API calls. Coverage includes partial text before commit, clean cancellation, connection reuse, ordinary Ctrl shortcuts, proxy routing, target-window protection, private configuration migration, and the Dex adapter.

Synthetic Chinese speech was previously checked through the actual API and a GTK input field: live words arrived before release and final insertion took about 0.94 seconds after release. This is one synthetic test, not a latency guarantee or a human-speech accuracy evaluation.

Do not add recordings, transcripts, API keys, local network settings, or personal deployment paths to the repository.

## License

MIT. Dependencies retain their respective licenses.
