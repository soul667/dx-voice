# DX Voice: product review and reuse plan

Review date: 2026-11-14. Focus: the user's Linux desktop, low-friction dictation, pure shell-command output, and one place for settings/history.

## Primary-source references

| Project | Verified capability | Adopted in DX Voice |
| --- | --- | --- |
| [Handy](https://github.com/cjpais/Handy), [post-processing docs](https://handy.computer/docs/post-processing) | Optional AI processing after transcription, configurable provider/model/prompts | Separate fast raw dictation from an optional light cleanup step |
| [OpenWhispr](https://github.com/OpenWhispr/openwhispr) | Desktop dictation with local/cloud choices, BYOK, AI text processing | Keep provider/model selection explicit and use the existing API key |
| [VoiceInk](https://tryvoiceink.com/docs/introduction), [source](https://github.com/Beingpax/VoiceInk) | Modes combine recognition, optional enhancement and delivery; history supports finding/copying results; vocabulary support | Distinct dictation/command modes, local recoverable history, custom vocabulary hints |
| [Wispr Flow cleanup](https://docs.wisprflow.ai/articles/4283510616-Auto-Cleanup:-control-how-much-Flow-edits-your-dictation) | Commercial reference, not an open-source dependency: adjustable raw/light/stronger cleanup | Cleanup must be optional and conservative, rather than rewriting every utterance |

These are capability references, not claims that their complete engines have been embedded. No source code from the compared applications was copied. Runtime integration reuses **Textual widgets/workers**, the existing **DX TUI theme engine**, Python's **SQLite**, and the **official OpenAI SDK**. The existing working streaming/capture layer remains in place.

## Delivered in v0.4

- **One terminal entry:** `dx v`. Overview, voice, rewrite, command, tools, history and connection tabs. Every setting in the application configuration schema is editable there. No independent graphical settings dialog.
- **Three explicit gestures:** `Ctrl` alone held for the configured threshold starts dictation; `Ctrl+Win` held for ~0.4 seconds selects command mode; `Alt+Win` held for ~0.4 seconds selects registered experimental DX/workspace actions. Mouse actions and other key chords take precedence. The former standalone GNOME Super overview binding can also be managed cleanly on shutdown.
- **Fast path:** raw dictation is the default and makes no second model call. Light cleanup is optional, uses a small model, preserves protected paths/numbers/URLs, and falls back to the raw transcript on failure. Original and output can be recovered in history.
- **Command path:** Terra generates one command via the SDK without tools. The app checks syntax with a shell's parse-only mode; it never executes the generated command. Default delivery is clipboard-only. Current login-shell defaults are respected; shell and delivery can be changed in the terminal UI.
- **One private history file:** `~/.local/state/dx-voice/history.db`, owner-only permissions. One row per turn/attempt stores time, mode, original, result and outcome. Cancelled turns keep metadata rather than partial speech. The view loads the latest 100 rows; older rows are not silently deleted. Successful audio is deleted as before; failed audio remains available for explicit retry.
- **Less repetition:** custom vocabulary is passed as realtime recognition hints. The terminal history highlights a row to preview its original/result and offers explicit copy actions.
- **Truthful progress:** command generation runs in a Textual worker, disables duplicate submits and exposes the busy state. A failed command does not fall back to pasting the spoken request as if it were shell code.

## Timing evidence and tradeoffs

One synthetic SDK probe using the configured provider returned a light cleanup in about 2.8 seconds and a simple Terra command in about 3.6 seconds. These are examples, not latency guarantees. A separate v0.3 synthetic live check delivered normal dictation to a GTK input field about 0.74 seconds after release; command speech became the clipboard-only result `pwd` about 4.29 seconds after release, including final ASR and Terra. Both original/result pairs were verified in an isolated private history file. Realtime dictation had previously been tested at about 0.94 seconds from release to insertion with a synthetic audio source.

Because cleanup can add noticeable delay, it is **off by default**. The Rewrite tab can enable it. A cleanup timeout retains the original wording; command-generation errors retain the request for recovery and produce no command output.

## Product priorities

### P0: protect ordinary work

The key must not fight with zoom, window shortcuts or typing. Mode selection and output destination must be clear. Preserve the existing target-window check and never send Enter. These are higher priority than adding more generation modes.

### P1: recovery and perceived responsiveness

History and original/result comparison are delivered. Next candidates: a search box for history, visible microphone/no-speech diagnostics, a clean indication when a new utterance cannot start while an earlier result is processing, and application-specific output profiles. These should be evaluated using real microphone samples and the user's normal applications, not synthetic audio alone.

### P2: voice-to-task workflow

Extract draft todos and suggest an executor such as Codex, Dot, Moz or Grokbot. Keep this separate from ordinary dictation and command generation. Task extraction, dispatch, progress tracking and agent integrations are **not implemented in v0.4**. A future implementation should compose existing orchestration tools rather than turn this input plugin into a new agent platform.

## Deliberately out of scope

No large local speech-model download, GPU allocation, automatic shell execution, implicit screen/clipboard harvesting for model context, or automatic task dispatch. None is necessary for the current requested workflow.

## v0.4 additions

- ASR provider factory and independent speech/text connections; OpenAI is bundled, Qwen requires a future adapter.
- Optional screenshot-assisted rewrite using MSS/Pillow and SDK image input. Both switches must be enabled; images remain in RAM. A synthetic screenshot API probe succeeded in about 3.79 seconds; no private desktop image was uploaded for verification.
- Frosted local HUD snapshot blur, separate from model context permission.
- Experimental registered DX Tools actions. A real display-status request selected and executed `display.status` in about 2.21 seconds; document opener argv was checked in dry-run mode. No generated shell was executed.

## v0.5 additions

- **Local SQLite FTS5 workspace context index (`modules/context.py`):** inspects active X11 focus, terminal/editor `/proc` `cwd`, project manifests/branches, and key source symbols (`~/.local/state/dx-voice/context.db`, mode `0600`) with automatic secret redaction and sensitive-file exclusion. Enriches realtime ASR prompts/vocabulary (delivered via in-place `session.update` without reconnecting), optional light cleanup, pure command generation, and DX Tools workspace actions (`workspace.status`, `context.inspect`, workspace-aware `open.path`).
- **`Alt+Win` XKB & chord threshold fix:** includes `Mod1`/`Meta_L` and `Mod4`/`Hyper_L` modifier-mapping codes in `resolve_modifier_codes()` and keeps 2-key chords (`Ctrl+Win`, `Alt+Win`) at ~0.4s even when single-key `hotkey_hold_ms` is long.
- **Event-driven runtime & 0% idle CPU:** replaces polling loops with passive XI2 key/pointer wakeup on `GLib.io_add_watch`, a dedicated blocking WebSocket reader thread, chunk coalescing, `parec`/`arecord` capture fallback, and background-thread screenshot capture on key release.
- **60 FPS adaptive HUD & history search:** adds spring-smoothed symmetric waveform bars, animated `processing` shimmer, luminance-adaptive smoked frosted glass (in-memory Cairo BGRA blur), dynamic chord keycaps (`Ctrl`, `Ctrl+Win`, `Alt+Win`), live `dx v` context refresh, and real-time history search filtering.
