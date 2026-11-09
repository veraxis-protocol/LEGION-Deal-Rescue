# Tools used (only those that actually run in this project)

- **PayPal Orders v2 API (Sandbox)**, via `paypal_adapter/`: create, server-side GET, capture, independent readback.
  - Mechanism-tested (42 tests).
  - Native dispatch not executed in this submission (see PAYPAL_STATUS.md).
- **NVIDIA NIM**, model `nvidia/nemotron-3.5-lightning-30b-a3b`: makes the owner-agent and coordinator decisions, 27 per run.
- **Python 3.14**: stdlib, `cryptography` (Ed25519), `jsonschema`.
- **LEGION Core / Federation / Marketplace**: external, PolyForm-NC, pinned.
- **Windows built-in tools**:
  - `System.Speech` for the narration voice;
  - `Windows.Media.Editing.MediaComposition` to encode the demo video;
  - headless Microsoft Edge, through Chrome DevTools Protocol screencast, to record the live app.

Not used in this submission, although they were used in earlier internal work: AG Grid / AG Studio, Channel3.
