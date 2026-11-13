# Contributing

Keep microphone/network work outside the GUI thread. The standalone CLI and Dex adapter must share one implementation. Use isolated configs and a loopback WebSocket server in tests; do not use a contributor's real API key or desktop input as a fixture.

Run `python -m unittest discover -s tests -v`. Changes to dictation need coverage for cancellation, final-result ordering, ordinary Ctrl shortcuts, and preserving focus. Design changes start with the native Figma library and semantic tokens in `design/`.

Never commit settings, keys, audio, transcripts, local addresses or deployment paths. Do not add a silent cloud fallback or automatically start microphone/network work when Dex loads the plugin. Call out platform limitations and distinguish synthetic API checks from real microphone validation.
