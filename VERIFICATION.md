# Verification record

These results were recorded on 2026-11-10 from a fresh `git clone` of this repository at `7668f2c`, on Windows 11 with
Python 3.14 and `core.autocrlf=true`, with the auditor fix that followed. GitHub Actions repeats the replay, test, audit and
scan checks on every push.

## Recorded runs and app (credential-free)

| Check | Result |
|---|---|
| `python -B scripts/build_and_serve.py --evidence demo_evidence --no-serve` | dossiers rebuilt from raw records; `audit_all_pass: true` |
| `python -B -m unittest discover -s tests` | **5/5 OK** |
| UI (served from the clone) | Every run loads without errors. Each run has 80 linked figures, 0 missing. Deal Dossier and Execution Passport download (HTTP 200). |
| `run-2` payments | **5 of 5 paid, $495.00 (Sandbox)**. Five distinct captures; each one checked against the readback, the ledger and the event journal. |
| `run-1` and the fresh live run | no payment shown: they have different contract hashes |
| Raw evidence after the build | unchanged (`git diff` clean on `runs/`, `paypal_runs/`, `negatives/`) |
| Payment adapter equals the payment runtime | byte-identical to LEGION-Commerce `0bb385f` (`docs/PAYMENT_RUNTIME.json`) |
| Secrets, private identifiers, machine paths | none found |

## Payment adapter (Windows)

| Check | Result |
|---|---|
| `cd paypal_adapter && python -B -m unittest discover -s tests -t .` | **46/46 OK**, fake provider |
| `python -B scripts/run_payment_negatives.py` | N07 duplicate capture, N09 lost capture response, N10 payee/payer substitution, N14 capture without provider approval: **all pass** |

## Fresh seven-party run from the clean clone

Command: `.\scripts\run_live_e2e.ps1 -NimKeyFile <file> -NoServe`. It finished with exit 0 in 2 min 50 s, including cloning the
pinned dependencies, creating the virtual environment and installing packages.

| Check | Result |
|---|---|
| Pinned dependencies | LEGION `d083c44`, LEGION-Federation `9d2a32a`, LEGION-Marketplace `906ec0f`; Judge source hash verified |
| Live run, first attempt (recorded as `A2-live-20261109T192815`) | contract `3b30f413…`. Version 1, $480: FAILED (price shock). Version 2, $540: FAILED (5 buyers refused). Version 3, $495: FULFILLED. |
| Independent Judge | **PASS_COMPLETED, 63/63**, 4/4 tamper tests detected |
| Model activity | 27 decisions: 25 by the parties, 2 by the coordinator |
| Adversarial negatives against live parties | **25/25**, 0 forbidden effects |
| Auditor on the live run | 100% provenance; negative matrix **15/15** |
| PayPal on the live run | none: a new contract has no payment authorization |

## Track record

| Campaign | First-attempt Judge passes |
|---|---|
| Fresh runs (2026-11-09/10): `run-1`, `run-2`, two live runs from clean clones | **4/4** |
| First campaign (2026-11-07) | 1 pass in 3 attempts: one AI provider error failed closed; one private-data leak caught by the Judge |

## PayPal Sandbox payments (2026-11-09/10)

| Check | Result |
|---|---|
| Captures | 5 captures, $495.00, each `COMPLETED` |
| Independent readback | each `VERIFIED_COMPLETED` |
| Provider POSTs | 10, with 0 retries and 0 duplicates |

See [PAYPAL_STATUS.md](PAYPAL_STATUS.md). No new payment was made for this verification.
