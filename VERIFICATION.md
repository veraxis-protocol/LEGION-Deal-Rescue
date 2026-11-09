# Release verification (2026-11-09)

| Check | Result | When / where |
|---|---|---|
| Fresh `git clone` of this repo at `fe2db38` (Windows 11, `core.autocrlf=true`) | OK | 23:03Z, clean temp dir |
| `python -B -m unittest discover -s tests` | **5/5 OK** | clean clone |
| `paypal_adapter`: `python -B -m unittest discover -s tests -t .` | **42/42 OK** (fake provider; no network) | release tree |
| `scripts/run_live_e2e.ps1` from the clean clone (pinned deps cloned from GitHub, venv, NIM) | **exit 0, 1 min 42 s** | 23:04Z |
| ↳ fresh seven-owner A2 first attempt `A2-live-20261109T180437` | Judge **PASS_COMPLETED 63/63**, 4/4 tamper mutants detected; v1 $480 FAILED (shock), v2 $540 FAILED (5 REJECT), v3 $495 FULFILLED; 27 model decisions | clean clone |
| ↳ adversarial negatives against live owners | **25/25**, 0 forbidden effects | clean clone |
| ↳ UI evidence audit (provenance, claims, N01–N15) | 100% figures/events resolved; 13 passed / 0 failed / 2 blocked (N10, N14 need a live PayPal leg) | clean clone |
| WO-004 fresh first attempts so far | **3/3 PASS** (`A2-fresh-1`, `A2-fresh-2`, clean-clone run). The earlier 2026-11-07 campaign was 1 of 3 | — |
| PayPal | **1/5 Sandbox payment confirmed**: b1 $99.00, order 21U22496GM957054P / capture 0DR81708WC9477605 COMPLETED, independent readback VERIFIED_COMPLETED; 2 POSTs, 0 duplicates | 2026-11-09 23:42Z |
