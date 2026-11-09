# Judge access

- **No account, key or payment is needed.** Clone the repo and run `python -B scripts/build_and_serve.py --evidence demo_evidence`. Then open `http://127.0.0.1:8795/?run=WO004-A2-fresh-2`.
- This replays two real fresh runs. It rebuilds and re-audits every figure from the raw records.
- Run the tests with `python -B -m unittest discover -s tests -v` (5 tests) and `cd paypal_adapter && python -B -m unittest discover -s tests -t .` (42 tests).
- **Fresh AI run** (Windows, your own free NVIDIA NIM key): `.\scripts\run_live_e2e.ps1 -NimKeyFile <file>`.
- **No hosted instance is provided.** Not hosted (Z).
- **PayPal:** no live Sandbox checkout is available to judges in this submission. See PAYPAL_STATUS.md.
