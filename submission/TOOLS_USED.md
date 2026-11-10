# Tools used

Only tools that actually run in this project are listed.

- **PayPal Orders v2 API (Sandbox).** Create order, buyer approval, server-side GET, capture, independent readback. Five live Sandbox payments.
- **NVIDIA NIM**, model `nvidia/nemotron-3.5-lightning-30b-a3b`. The parties' and coordinator's decisions (27 per deal).
- **Python 3.11+.** Standard library for the app. `cryptography` (Ed25519) and `jsonschema` for the parties and the payment adapter.
- **LEGION Core, LEGION-Federation, LEGION-Marketplace.** External, pinned (PolyForm Noncommercial 1.0.0).
- **SQLite.** Payment ledger.
- **Windows DPAPI.** Credential sealing.
