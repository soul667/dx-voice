# Security and privacy

DX Voice is trusted local desktop software, not a sandbox. It passively observes current key state and mouse-button/wheel activity to detect Ctrl-only holds without taking over normal mouse shortcuts, opens a microphone during active dictation, sends audio to the configured transcription endpoint, and uses the clipboard plus a synthetic paste shortcut.

API keys remain in the user's config with owner-only permissions. Saved recordings and transcripts remain in the private state directory. Service logs contain status/timing rather than user transcripts. Successful recordings are deleted; failures are retained for explicit retry.

For a vulnerability that could expose credentials or user audio, report it privately to the repository owner before posting logs or reproduction data. Never include a real API key or recording in an issue.
