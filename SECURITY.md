# Security and privacy

DX Voice is trusted local desktop software, not a sandbox. It passively observes current key state and mouse-button/wheel activity to detect Win-only and Ctrl+Win holds without taking over normal mouse shortcuts, opens a microphone during active dictation, sends audio to the configured transcription endpoint, and uses the clipboard plus a synthetic paste shortcut.

API keys remain in the user's config with owner-only permissions. Saved recordings, transcripts and the SQLite history remain in the private state directory. Optional cleanup and command generation send the current text to the selected API model through a tool-free SDK request; generated commands are never executed. Service logs contain status/timing rather than user transcripts. Successful recordings are deleted; failures are retained for explicit retry.

For a vulnerability that could expose credentials or user audio, report it privately to the repository owner before posting logs or reproduction data. Never include a real API key or recording in an issue.

Rewrite screenshot context is an independent default-off option. Only when both rewrite and screenshot context are enabled does normal dictation capture the mouse pointer's current monitor and upload it to the configured text model. Images remain in RAM and are not written to history or logs. Screen contents are untrusted context, not instructions. The frosted HUD captures a small local background region for its visual effect only; those pixels are not uploaded.

Alt+Win selects the separate experimental DX Tools module. A typed action ID chooses a fixed local argv, executed without a shell, for bounded status queries or explicit document/directory/HTTP(S) open requests. This is real local action execution, unlike Ctrl+Win command generation. It does not execute arbitrary generated shell or delegate to agents.
