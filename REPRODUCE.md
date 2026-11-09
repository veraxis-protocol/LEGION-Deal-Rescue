# Reproduce

## A. Replay + audit (any OS, Python 3.11+, no secrets, ~5 s)

```bash
python -B scripts/build_and_serve.py --evidence demo_evidence --no-serve   # rebuild dossiers, economics, audit
python -B -m unittest discover -s tests -v                                 # 5 release tests
python -B scripts/build_and_serve.py --evidence demo_evidence              # serve http://127.0.0.1:8795/
```

Expected:
- Both runs Judge `PASS_COMPLETED` (63/63 checks);
- provenance coverage 100% (88 figures, 75 events per run);
- negative matrix 13 attempted / 13 passed / 2 blocked (N10, N14: need a live PayPal leg);
- harness 25/25 with 0 forbidden effects;
- contribution 0 cents; PayPal $0.

## B. Fresh seven-owner run (Windows PowerShell, ~1–3 min after install)

Prerequisites: git, Python 3.11+ (3.14 used), internet, your own NVIDIA NIM key file.

```powershell
.\scripts\run_live_e2e.ps1 -NimKeyFile C:\path\to\nvapi.txt
```

Pinned external sources (PolyForm Noncommercial 1.0.0, cloned into `external/`):

| Repo | Commit |
|---|---|
| LEGION (Core) | `d083c44af2526e38068e0220891cd0bb5fce52af` |
| LEGION-Federation | `9d2a32a5c32758bea1ad2200955da1cc9213356c` |
| LEGION-Marketplace | `906ec0f553c0f8076127f7abab98825e188342ef` |

The Judge source SHA-256 is checked before the run: `9146122791d2d2a6f4cada2019c825b2c4925b6e4182fe91f55a7bae74f2992f`.

Model: `nvidia/nemotron-3.5-lightning-30b-a3b`. Override with env `LMF_NIM_MODEL`.

A fresh run is a new first attempt. Its outcome is whatever the Judge returns. The counted WO-004 history is 2/2 first-attempt PASS. The earlier 2026-11-07 campaign was 1 PASS in 3 attempts; those failures are documented in `demo_evidence/COUNTERFACTUAL_A0_A1_A2_A3.json`.

## C. PayPal adapter

```powershell
cd paypal_adapter
python -m pip install -r requirements.lock
python -B -m unittest discover -s tests -t .      # 42 mechanism tests, fake provider
```

Native Sandbox use requires operator-provisioned authority; see `PAYPAL_STATUS.md` and `paypal_adapter/A04_README.md`.
